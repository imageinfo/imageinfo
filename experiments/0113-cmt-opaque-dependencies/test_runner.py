import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

import runner


class AuthoredRunnerTests(unittest.TestCase):
    def test_literal_empty_tiff_byte_orders(self):
        self.assertEqual(runner.tiff("II", []), bytes.fromhex("49492a0008000000000000000000"))
        self.assertEqual(runner.tiff("MM", []), bytes.fromhex("4d4d002a00000008000000000000"))

    def test_literal_inline_tiff(self):
        self.assertEqual(runner.tiff("II", [(0, 1, 4, b"\x02\x03\0\0")]),
                         bytes.fromhex("49492a0008000000010000000100040000000203000000000000"))

    def test_declared_finite_matrix_and_bound(self):
        cells = runner.matrix()
        self.assertEqual(len(cells), 20)
        self.assertEqual(len({cell["id"] for cell in cells}), 20)
        for cell in cells:
            data = runner.fixture(cell["order"], cell["storage"])
            self.assertLessEqual(len(data), 65536)
            self.assertIn(b"2001:02:03 04:05:06\0", data)
            self.assertNotIn(b"2007:08:09 10:11:12\0", data)
            size, kind = struct.unpack_from(">I4s", data)
            self.assertEqual((size, kind), (20, b"ftyp"))

    def test_authored_dependency_shapes(self):
        for order in ("II", "MM"):
            endian = "<" if order == "II" else ">"
            for storage in runner.STORAGES:
                data = runner.fixture(order, storage)
                base = data.index(order.encode() + struct.pack(endian + "H", 42))
                count = struct.unpack_from(endian + "H", data, base + 8)[0]
                self.assertEqual(count, 1 if storage == "baseline" else 2)
                self.assertEqual(data.count(runner.ORIGINAL), 1)
                if storage == "alias":
                    self.assertEqual(data[base + 18:base + 22], data[base + 30:base + 34])
                elif storage == "checksum":
                    self.assertEqual(struct.unpack_from(endian + "I", data, base + 30)[0],
                                     sum(b"2001:02:03 04:05:06\0"))
                elif storage == "inline":
                    self.assertEqual(data[base + 30:base + 34], bytes.fromhex("91725334"))
                elif storage == "outline":
                    pointer = struct.unpack_from(endian + "I", data, base + 30)[0]
                    self.assertEqual(data[base + pointer:base + pointer + 14], b"AUTHORED-0113\0")

    def test_invented_checksum_changes_with_selected_date(self):
        self.assertNotEqual(runner.checksum(runner.ORIGINAL), runner.checksum(runner.CHANGED))

    def test_unknown_fixture_shape_refuses(self):
        with self.assertRaises(ValueError):
            runner.fixture("II", "camera")

    def test_launch_failure_retained_without_overwriting(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            root = Path(directory)
            cell = runner.matrix()[0]
            with patch("runner.subprocess.run", side_effect=OSError("authored launch failure")):
                result = runner.execute(root, cell, Path("perl"), Path("reference"), {})
            self.assertIsNone(result["output"])
            self.assertEqual(result["input"], result["inputAfter"])
            self.assertEqual(result["command"]["launchError"], "authored launch failure")
            retained = json.loads((root / (cell["id"] + ".result.json")).read_text())
            self.assertEqual(retained, result)

    def test_timeout_preserves_partial_captures(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            root = Path(directory)
            error = runner.subprocess.TimeoutExpired(["authored"], 120, output=b"partial", stderr=b"warning")
            with patch("runner.subprocess.run", side_effect=error):
                result = runner.execute(root, runner.matrix()[0], Path("perl"), Path("reference"), {})
            self.assertTrue(result["command"]["timedOut"])
            self.assertEqual((root / result["command"]["stdout"]["path"]).read_bytes(), b"partial")
            self.assertEqual((root / result["command"]["stderr"]["path"]).read_bytes(), b"warning")

    def test_existing_source_or_destination_refuses_without_command(self):
        for suffix in ("input", "output"):
            with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
                root = Path(directory)
                cell = runner.matrix()[0]
                protected = root / (cell["id"] + "." + suffix + ".cr3")
                protected.write_bytes(b"AUTHORED EXISTING")
                with patch("runner.subprocess.run") as command:
                    with self.assertRaises((ValueError, FileExistsError)):
                        runner.execute(root, cell, Path("perl"), Path("reference"), {})
                    command.assert_not_called()
                self.assertEqual(protected.read_bytes(), b"AUTHORED EXISTING")

    def test_namespace_choice_records_sources_and_refuses_definition(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            root = Path(directory)
            folder = root / "lib/Image/ExifTool"
            folder.mkdir(parents=True)
            (folder / "Exif.pm").write_text("0x9003 => {},\n")
            (folder / "Canon.pm").write_text("CMT2 => {},\n")
            choice = runner.namespace_choice(root)
            self.assertEqual(choice["tag"], 57342)
            self.assertEqual(len(choice["checkedSources"]), 2)
            for literal in ("0xDFFE", "57342"):
                (folder / "Exif.pm").write_text(literal + " => {},\n")
                with self.assertRaises(ValueError):
                    runner.namespace_choice(root)


if __name__ == "__main__":
    unittest.main()
