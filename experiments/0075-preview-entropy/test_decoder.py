"""Portable adapter controls using Python fake functions, never a native codec.

The fake ABI layout is explicitly mocked only while exercising these Python
functions. These tests establish adapter control flow, not JPEG qualification.
"""
import ctypes as C
import hashlib
import unittest
from unittest.mock import patch

import decoder


class FakeFunction:
    def __init__(self, callback):
        self.callback = callback

    def __call__(self, *args):
        return self.callback(*args)


class FakeLibrary:
    """No CDLL, imports of encoders, file input or codec calls are used."""
    def __init__(self, *, header=0, decode=0, width=2, destroy=0,
                 severity=0, message=b"authored fake diagnostic"):
        self.calls = []
        self.message = C.create_string_buffer(message)
        self.tjInitDecompress = FakeFunction(lambda: 123)

        def header_call(handle, source, length, w, h, sampling, colorspace):
            self.calls.append(("header", bytes(source), length))
            for pointer, value in ((w, width), (h, 1), (sampling, 0), (colorspace, 1)):
                C.cast(pointer, C.POINTER(C.c_int))[0] = value
            return header

        def decode_call(handle, source, length, pixels, *args):
            self.calls.append(("decode", bytes(source), length, args))
            for index in range(6):
                pixels[index] = index
            return decode

        self.tjDecompressHeader3 = FakeFunction(header_call)
        self.tjDecompress2 = FakeFunction(decode_call)
        self.tjGetErrorStr2 = FakeFunction(lambda handle: C.addressof(self.message))
        self.tjGetErrorCode = FakeFunction(lambda handle: severity)
        self.tjDestroy = FakeFunction(
            lambda handle: self.calls.append(("destroy", handle)) or destroy)


class DecoderFakeTests(unittest.TestCase):
    def setUp(self):
        # Dimensions and source are authored fake values. Actual syntax is
        # independently tested in test_syntax; no production bypass is added.
        self.syntax_patch = patch.object(decoder, "inspect_extent", return_value={
            "accepted": True, "width": 2, "height": 1, "decodedBytes": 6})
        self.syntax_patch.start()
        self.addCleanup(self.syntax_patch.stop)
        actual_sizeof = C.sizeof

        def fake_abi_sizeof(value):
            if value is C.c_ulong:
                return 4
            if value is C.c_void_p:
                return 8
            return actual_sizeof(value)

        for context in (patch.object(decoder.sys, "platform", "win32"),
                        patch.object(decoder.C, "sizeof", side_effect=fake_abi_sizeof)):
            context.start()
            self.addCleanup(context.stop)

    def run_fake(self, library, **kwargs):
        closure = []
        result = decoder.decode(b"unchanged extent\x00\x00", load_library=lambda: library,
                                verify_loaded=lambda: closure.append(True), **kwargs)
        self.assertEqual(closure, [True])
        self.assertEqual(library.calls[-1], ("destroy", 123))
        return result

    def test_complete_extent_rgb_flags_and_full_hash(self):
        library = FakeLibrary()
        result = self.run_fake(library)
        self.assertTrue(result["accepted"])
        self.assertEqual(result["decodedBytes"], 6)
        self.assertEqual(result["pixelSha256"], hashlib.sha256(bytes(range(6))).hexdigest())
        for call in library.calls[:2]:
            self.assertEqual(call[1:3], (b"unchanged extent\x00\x00", 18))
        self.assertEqual(library.calls[1][3], (2, 0, 1, 0, 8192))
        self.assertFalse(result["decode"]["severityMeaningful"])
        self.assertEqual(result["decode"]["severity"], "not-meaningful-on-success")
        self.assertEqual(library.tjDecompress2.argtypes,
                         [C.c_void_p, C.c_void_p, C.c_ulong, C.c_void_p,
                          C.c_int, C.c_int, C.c_int, C.c_int, C.c_int])
        self.assertIs(library.tjDecompress2.restype, C.c_int)

    def test_warning_refuses_without_pixel_hash(self):
        result = self.run_fake(FakeLibrary(decode=-1))
        self.assertFalse(result["accepted"])
        self.assertEqual(result["decode"]["severity"], "warning")
        self.assertNotIn("pixelSha256", result)

    def test_fatal_refuses(self):
        result = self.run_fake(FakeLibrary(decode=-1, severity=1))
        self.assertFalse(result["accepted"])
        self.assertEqual(result["decode"]["severity"], "fatal")

    def test_header_refuses_without_decode(self):
        library = FakeLibrary(header=-1)
        self.assertEqual(self.run_fake(library)["outcome"], "header-refused")
        self.assertEqual(len(library.calls), 2)

    def test_header_mismatch_without_decode(self):
        library = FakeLibrary(width=3)
        self.assertEqual(self.run_fake(library)["outcome"], "header-syntax-mismatch")
        self.assertEqual(len(library.calls), 2)

    def test_syntax_refusal_without_native_load(self):
        def forbidden():
            raise AssertionError("native callback invoked")
        with patch.object(decoder, "inspect_extent", return_value={
                "accepted": False, "reason": "authored-refusal"}):
            result = decoder.decode(b"unsupported", load_library=forbidden,
                                    verify_loaded=forbidden)
        self.assertFalse(result["nativeInvoked"])
        self.assertEqual(result["outcome"], "syntax-refused")

    def test_syntax_bound_inconsistency_refuses_before_load(self):
        with patch.object(decoder, "inspect_extent", return_value={
                "accepted": True, "width": 2, "height": 1, "decodedBytes": 7}):
            with self.assertRaisesRegex(RuntimeError, "adapter bounds"):
                decoder.decode(b"authored", load_library=lambda: self.fail("loaded"),
                               verify_loaded=lambda: self.fail("verified"))

    def test_sink_complete_readonly_and_released(self):
        views = []
        def sink(view):
            self.assertTrue(view.readonly)
            self.assertEqual(bytes(view), bytes(range(6)))
            views.append(view)
        result = self.run_fake(FakeLibrary(), pixel_sink=sink)
        self.assertTrue(result["pixelSinkCompleted"])
        self.assertFalse(result["pixelsRetainedByAdapter"])
        with self.assertRaises(ValueError):
            views[0].tobytes()

    def test_sink_failure_destroys_and_propagates(self):
        library, closure = FakeLibrary(), []
        def sink(view):
            raise OSError("authored write failure")
        with self.assertRaisesRegex(OSError, "authored write failure"):
            decoder.decode(b"authored", load_library=lambda: library,
                           verify_loaded=lambda: closure.append(True), pixel_sink=sink)
        self.assertEqual(library.calls[-1], ("destroy", 123))
        self.assertEqual(closure, [True])

    def test_warning_never_invokes_sink(self):
        result = self.run_fake(FakeLibrary(decode=-1),
                               pixel_sink=lambda view: self.fail("refused pixels leaked"))
        self.assertFalse(result["pixelSinkCompleted"])

    def test_destroy_failure_invalidates_result(self):
        with self.assertRaisesRegex(RuntimeError, "destroy failed"):
            self.run_fake(FakeLibrary(destroy=-1))

    def test_unknown_failure_severity_invalidates_and_destroys(self):
        library = FakeLibrary(decode=-1, severity=9)
        with self.assertRaisesRegex(RuntimeError, "unknown native failure severity"):
            self.run_fake(library)
        self.assertEqual(library.calls[-1], ("destroy", 123))

    def test_oversized_diagnostic_invalidates_and_destroys(self):
        library = FakeLibrary(message=b"x" * 241)
        with self.assertRaisesRegex(RuntimeError, "diagnostic exceeds"):
            self.run_fake(library)
        self.assertEqual(library.calls[-1], ("destroy", 123))

    def test_immutable_bytes_required(self):
        with self.assertRaises(TypeError):
            decoder.decode(bytearray(b"x"), load_library=lambda: None,
                           verify_loaded=lambda: None)

    def test_unsupported_platform_refused(self):
        with patch.object(decoder.sys, "platform", "unsupported"):
            with self.assertRaisesRegex(RuntimeError, "Windows x64 ABI"):
                decoder.configure_library(FakeLibrary())

    def test_unsupported_word_sizes_refused(self):
        for ulong, pointer in ((8, 8), (4, 4)):
            with self.subTest(ulong=ulong, pointer=pointer):
                with patch.object(decoder.C, "sizeof", side_effect=lambda value:
                                  ulong if value is C.c_ulong else pointer):
                    with self.assertRaisesRegex(RuntimeError, "Windows x64 ABI"):
                        decoder.configure_library(FakeLibrary())


if __name__ == "__main__":
    unittest.main()
