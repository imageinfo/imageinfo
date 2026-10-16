"""Authored #0144 projection, refusal and independent-audit controls."""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import audit_read_resources_144 as audit
import measure_read_resources_144 as measure
import qualify_batch_read as authored


class ResourceGridTests(unittest.TestCase):
    def test_projection_preserves_original_and_exact_non_display_values(self):
        original = authored.expected_envelope()
        before = copy.deepcopy(original)
        raw = measure.project(original, "EXIF:ISO", "raw")
        self.assertEqual(original, before)
        self.assertTrue(raw["files"][0]["snapshot"]["occurrences"])
        for occurrence in raw["files"][0]["snapshot"]["occurrences"]:
            self.assertEqual((occurrence["tag"]["namespace"], occurrence["tag"]["name"]), ("exif", "ISO"))
            prior = next(o for o in original["files"][0]["snapshot"]["occurrences"] if o["id"] == occurrence["id"])
            for key in ("raw", "normalized", "normalization"):
                self.assertEqual(occurrence["values"][key], prior["values"][key])

    def test_public_destination_refuses_before_evidence_load(self):
        with patch.object(measure.b, "load") as load, self.assertRaises(ValueError):
            measure.collect(measure.batch.ROOT / "docs")
        load.assert_not_called()

    def test_missing_task_permission_refuses_before_source_read(self):
        with patch.object(measure.b, "digest") as digest, self.assertRaises(ValueError):
            measure.rights({"taskAdmission": {}})
        digest.assert_not_called()

    def test_authored_native_grid(self):
        binary = os.environ.get("IMAGEINFO_144_BINARY")
        if not binary:
            self.skipTest("explicit frozen binary required for native authored control")
        root = measure.batch.ROOT
        with tempfile.TemporaryDirectory(dir=root / ".local", prefix="144-authored-") as temporary:
            folder = Path(temporary)
            source = folder / "fixture.rs"
            helper = json.dumps((root / "tests/support/mod.rs").as_posix())
            source.write_text(f'#[allow(dead_code)] #[path={helper}] mod support;\nfn main() {{std::fs::write(std::env::args_os().nth(1).unwrap(),support::fixture().bytes).unwrap();}}')
            generator = folder / "fixture.exe"
            subprocess.run(["rustc", "--edition=2024", str(source), "-o", str(generator)], check=True, capture_output=True, timeout=45)
            files = [folder / f"authored-{n}.cr3" for n in range(4)]
            for file in files:
                subprocess.run([str(generator), str(file)], check=True, capture_output=True, timeout=10)
            original = authored.expected_envelope()
            for selection, view, shape in measure.GRID:
                operands = files[:4 if shape == "four" else 1]
                if shape == "duplicate":
                    operands *= 4
                argv = [binary, "metadata", "read", "--values", view, "--output", "json"]
                if selection != "full":
                    argv += ["--tag", selection]
                argv += ["--", *map(str, operands)]
                result = subprocess.run(argv, capture_output=True, timeout=30, check=True)
                self.assertEqual(result.stderr, b"")
                actual = audit.canonical(json.loads(result.stdout))
                expected = measure.batch.normalized_envelope(measure.project(original, selection, view))
                expected["files"] *= 4 if shape == "four" else 1
                expected["summary"]["counts"].update(discovered=len(expected["files"]), deduplicated=3 if shape == "duplicate" else 0,
                    byState={"read": len(expected["files"])})
                self.assertEqual(audit.wire(actual), audit.wire(expected), (selection, view, shape))


if __name__ == "__main__":
    unittest.main()
