"""Windows read-only observer controls, using only fresh authored files."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import audit_storage_vmoff_175 as audit


@unittest.skipUnless(os.name == "nt", "native Windows observer")
class NativeObserverTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1]
        self.reader = root / "scripts" / "read_storage_artifacts_175.ps1"
        parent = root / ".local" / "175-independent-reader-controls"
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cell = self.root / "cell"
        self.cell.mkdir()
        (self.cell / "source.bin").write_bytes(audit.SOURCE)
        self.unit = self.cell / "unit"
        self.unit.mkdir()
        (self.unit / "candidate.bin").write_bytes(audit.CANDIDATE)

    def invoke(self, destination):
        return subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                               str(self.reader), "-CellDirectory", str(self.cell), "-Destination", str(destination)],
                              capture_output=True, timeout=30)

    def test_separate_reader_preserves_native_facts(self):
        first, second = self.root / "first.json", self.root / "second.json"
        for output in (first, second):
            result = self.invoke(output)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        one, two = [json.loads(path.read_text(encoding="utf-8")) for path in (first, second)]
        self.assertEqual(one["errors"], [])
        self.assertEqual(audit.stable_snapshot(one), audit.stable_snapshot(two))
        rows = audit.read_snapshot(one)
        self.assertEqual(audit.file_bytes(rows["source.bin"]), audit.SOURCE)
        self.assertEqual(audit.file_bytes(rows["unit/candidate.bin"]), audit.CANDIDATE)
        self.assertNotEqual(rows["source.bin"]["file_index"], rows["unit/candidate.bin"]["file_index"])
        self.assertEqual(one["boot_utc"], two["boot_utc"])

    def test_destination_inside_cell_refuses_before_effects(self):
        for destination in (self.cell / "new.json", self.unit / "foreign.record"):
            before = sorted(str(path.relative_to(self.cell)) for path in self.cell.rglob("*"))
            result = self.invoke(destination)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b"DESTINATION_MUST_BE_OUTSIDE_CELL", result.stderr)
            self.assertFalse(destination.exists())
            self.assertEqual(before, sorted(str(path.relative_to(self.cell)) for path in self.cell.rglob("*")))

    def test_reusing_destination_preserves_original(self):
        destination = self.root / "occupied.json"
        destination.write_bytes(b"protected diagnostic\n")
        result = self.invoke(destination)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(destination.read_bytes(), b"protected diagnostic\n")

    def test_named_stream_is_observed_and_rejected_by_auditor(self):
        source = self.cell / "source.bin"
        Path(str(source) + ":authored-control").write_bytes(b"separate authored stream")
        destination = self.root / "stream.json"
        result = self.invoke(destination)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        value = json.loads(destination.read_text(encoding="utf-8"))
        source_row = next(row for row in value["files"] if row["path"] == "source.bin")
        self.assertIn(":authored-control:$DATA", source_row["streams"])
        with self.assertRaises(ValueError):
            audit.read_snapshot(value)
        self.assertEqual(source.read_bytes(), audit.SOURCE)

    def test_hardlink_is_observed_and_rejected_by_auditor(self):
        source = self.cell / "source.bin"
        os.link(source, self.root / "authored-source-link.bin")
        destination = self.root / "links.json"
        result = self.invoke(destination)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        value = json.loads(destination.read_text(encoding="utf-8"))
        source_row = next(row for row in value["files"] if row["path"] == "source.bin")
        self.assertEqual(source_row["links"], 2)
        with self.assertRaises(ValueError):
            audit.read_snapshot(value)


if __name__ == "__main__":
    unittest.main()
