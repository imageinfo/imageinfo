"""Pre-load binding refusal tests. These never load a JPEG decoder."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
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

    def test_encoder_and_decoder_are_distinct_pinned_closures(self):
        profile = runtime.component_profile()
        decoder = profile["loadedNonOsModules"]
        encoder = profile["loadedEncoderNonOsModules"]
        self.assertIn("python/DLLs/_decimal.pyd", encoder)
        self.assertNotIn("python/DLLs/_decimal.pyd", decoder)
        self.assertIn("native/libheif/libheif/bin/turbojpeg.dll", decoder)
        self.assertNotIn("native/libheif/libheif/bin/turbojpeg.dll", encoder)
        for path in encoder.keys() & decoder.keys():
            self.assertEqual(encoder[path], decoder[path])
        self.assertIn("python/Lib/site-packages/PIL/PngImagePlugin.py",
                      profile["encoderSourceModules"])
        self.assertIn("python/Lib/fractions.py", profile["encoderSourceModules"])

    def test_encoder_preparation_checks_files_before_import_registration(self):
        profile = runtime.component_profile()
        events = []
        fake_image = SimpleNamespace(preinit=lambda: events.append("preinit"))
        root = Path(__file__).resolve().parent
        with patch.object(runtime, "_inside", side_effect=lambda root, relative: root / relative):
            verified = runtime.VerifiedRuntime(root, profile)
            with patch.object(runtime, "_check", side_effect=lambda *args: events.append("check")), \
                    patch.dict(sys.modules, {"PIL": SimpleNamespace(Image=fake_image)}), \
                    patch.object(runtime, "loaded_components", return_value=profile["loadedEncoderNonOsModules"]):
                self.assertEqual(verified.prepare_encoder(), profile["loadedEncoderNonOsModules"])
        checks = len(profile["loadedEncoderNonOsModules"]) + len(profile["encoderSourceModules"])
        self.assertEqual(events, ["check"] * checks + ["preinit"])

    def test_encoder_component_mismatch_prevents_plugin_preparation(self):
        profile = runtime.component_profile()
        fake_image = SimpleNamespace(preinit=lambda: self.fail("plugin import after mismatch"))
        root = Path(__file__).resolve().parent
        with patch.object(runtime, "_inside", side_effect=lambda root, relative: root / relative):
            verified = runtime.VerifiedRuntime(root, profile)
            with patch.object(runtime, "_check", side_effect=runtime.RuntimeRefusal("authored mismatch")), \
                    patch.dict(sys.modules, {"PIL": SimpleNamespace(Image=fake_image)}):
                with self.assertRaisesRegex(runtime.RuntimeRefusal, "authored mismatch"):
                    verified.prepare_encoder()

    def test_encoder_inventory_rejects_extra_missing_and_changed_modules(self):
        profile = runtime.component_profile()
        expected = profile["loadedEncoderNonOsModules"]
        first = next(iter(expected))
        variants = [dict(expected, unexpected={"byteLength": 0, "sha256": "0" * 64}),
                    {key: value for key, value in expected.items() if key != first},
                    dict(expected, **{first: {"byteLength": 0, "sha256": "0" * 64}})]
        with patch.object(runtime, "_inside", return_value=Path("authored-library")):
            verified = runtime.VerifiedRuntime(Path("authored-root"), profile)
            for actual in variants:
                with patch.object(runtime, "loaded_components", return_value=actual):
                    with self.assertRaisesRegex(runtime.RuntimeRefusal, "encoder non-OS module closure"):
                        verified.assert_encoder_closure()


if __name__ == "__main__":
    unittest.main()
