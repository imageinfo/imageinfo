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
        self.assertEqual(len(cells), 32)
        self.assertEqual(len({cell["id"] for cell in cells}), 32)
        for cell in cells:
            data = runner.fixture(cell["order"], cell["storage"])
            self.assertLessEqual(len(data), 65536)
            self.assertIn(b"2001:02:03 04:05:06\0", data)
            self.assertNotIn(b"2007:08:09 10:11:12\0", data)
            size, kind = struct.unpack_from(">I4s", data)
            self.assertEqual((size, kind), (20, b"ftyp"))

    def test_invented_storage_is_not_aliased(self):
        for order in ("II", "MM"):
            absent = runner.fixture(order, "absent")
            nonzero = runner.fixture(order, "nonzero")
            self.assertEqual(nonzero[-24:], bytes(range(1, 25)))
            self.assertEqual(len(nonzero) - len(absent), 24)
            self.assertIn(b"AUTHORED-0109\0", runner.fixture(order, "reachable"))
            self.assertNotIn(b"AUTHORED-0109\0", absent)

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


if __name__ == "__main__":
    unittest.main()
