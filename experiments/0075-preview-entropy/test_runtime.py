"""Pre-load binding refusal tests. These never load a JPEG decoder."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import runtime


class RuntimeBindingTests(unittest.TestCase):
    def test_component_pin_and_source_references(self):
        self.assertEqual(runtime.component_profile()["schemaVersion"], 1)

    def test_changed_component_profile_refuses(self):
        profile = runtime.component_profile()
        profile["binaryReproducibilityProven"] = True
        with patch.object(Path, "read_text", return_value=json.dumps(profile)):
            with self.assertRaises(runtime.RuntimeRefusal):
                runtime.component_profile()

    def test_preload_file_mismatch_refuses(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2] / ".local") as directory:
            path = Path(directory) / "component"
            path.write_bytes(b"changed")
            with self.assertRaises(runtime.RuntimeRefusal):
                runtime._check(path, {"byteLength": 0, "sha256": "0" * 64})

    def test_relative_escape_refuses(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2] / ".local") as directory:
            root = Path(directory) / "root"
            root.mkdir()
            foreign = Path(directory) / "foreign"
            foreign.write_bytes(b"outside")
            with self.assertRaises(runtime.RuntimeRefusal):
                runtime._inside(root, "../foreign")

    def test_actual_preload_and_caller_manifest_refusal(self):
        # Explicitly fail if this pre-load test accidentally opens the DLL.
        with patch.object(runtime.C, "CDLL", side_effect=AssertionError("native load")):
            verified = runtime.verify_runtime()
            self.assertEqual(verified.identity()["componentProfileCanonicalSha256"],
                             runtime.COMPONENT_PROFILE_CANONICAL_SHA256)
            with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2] / ".local") as directory:
                path = Path(directory) / "wrong.json"
                path.write_text("{}", encoding="utf-8")
                with self.assertRaises(runtime.RuntimeRefusal):
                    runtime.verify_runtime(path)


if __name__ == "__main__":
    unittest.main()
