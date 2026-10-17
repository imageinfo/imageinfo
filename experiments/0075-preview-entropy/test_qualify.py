"""Pure closure-gate regressions; no Pillow, native codec or media operations."""
from copy import deepcopy
import unittest
from unittest.mock import patch

import qualify


class EncoderRuntime:
    def __init__(self):
        self.expected = {"python/python.exe": {"byteLength": 1, "sha256": "a" * 64}}
        self.profile = {"loadedEncoderNonOsModules": deepcopy(self.expected),
                        "loadedNonOsModules": {"decoder-only": {"sha256": "b" * 64}}}
        self.before = deepcopy(self.expected)
        self.after = deepcopy(self.expected)
        self.calls = []

    def prepare_encoder(self):
        self.calls.append("prepare")
        return self.before

    def assert_encoder_closure(self):
        self.calls.append("assert")
        return self.after


class EncoderClosureGateTests(unittest.TestCase):
    def invoke(self, runtime):
        def source(_):
            runtime.calls.append("source")
            return "source-hash"

        def encode(_, verify_encoder):
            runtime.calls.append("build")
            verify_encoder()
            return b"authored-fake"

        with patch.object(qualify.controls, "source_pixel_digest", side_effect=source) as pixels:
            with patch.object(qualify.controls, "build_control", side_effect=encode) as encoder:
                result = qualify._encode_with_verified_closure("formula-64-444", runtime)
        return result, pixels, encoder

    def test_exact_separate_closure_precedes_operations_and_is_rechecked(self):
        runtime = EncoderRuntime()
        result, _, _ = self.invoke(runtime)
        self.assertEqual(runtime.calls, ["prepare", "source", "build", "assert", "assert"])
        self.assertEqual(result, (b"authored-fake", "source-hash", runtime.expected, runtime.expected))
        self.assertNotEqual(runtime.profile["loadedNonOsModules"], runtime.expected)

    def test_preparation_refusal_prevents_source_and_image_operations(self):
        runtime = EncoderRuntime()
        with patch.object(runtime, "prepare_encoder", side_effect=ValueError("unbound component")):
            with patch.object(qualify.controls, "source_pixel_digest") as source:
                with patch.object(qualify.controls, "build_control") as encoder:
                    with self.assertRaises(ValueError):
                        qualify._encode_with_verified_closure("formula-64-444", runtime)
                    source.assert_not_called()
                    encoder.assert_not_called()

    def test_preoperation_extra_missing_and_changed_modules_refuse(self):
        for change in ("extra", "missing", "changed"):
            with self.subTest(change=change):
                runtime = EncoderRuntime()
                if change == "extra":
                    runtime.before["extra"] = {"byteLength": 1, "sha256": "c" * 64}
                elif change == "missing":
                    runtime.before.clear()
                else:
                    runtime.before["python/python.exe"]["sha256"] = "d" * 64
                with patch.object(qualify.controls, "source_pixel_digest") as source:
                    with patch.object(qualify.controls, "build_control") as encoder:
                        with self.assertRaisesRegex(ValueError, "pre-operation"):
                            qualify._encode_with_verified_closure("formula-64-444", runtime)
                        source.assert_not_called()
                        encoder.assert_not_called()

    def test_postoperation_extra_missing_and_changed_modules_refuse(self):
        for change in ("extra", "missing", "changed"):
            with self.subTest(change=change):
                runtime = EncoderRuntime()
                if change == "extra":
                    runtime.after["extra"] = {"byteLength": 1, "sha256": "c" * 64}
                elif change == "missing":
                    runtime.after.clear()
                else:
                    runtime.after["python/python.exe"]["sha256"] = "d" * 64
                with self.assertRaisesRegex(ValueError, "post-operation"):
                    self.invoke(runtime)


if __name__ == "__main__":
    unittest.main()
