"""Authored structural vectors only; these never invoke a JPEG decoder."""
import unittest

from syntax import DECODED_LIMIT, DIMENSION_LIMIT, INPUT_LIMIT, PROFILE_ID, inspect_extent


def segment(marker, payload):
    return bytes((255, marker)) + (len(payload) + 2).to_bytes(2, "big") + payload


def frame(width=19, height=17, components=None):
    components = components or b"\x01\x22\x00\x02\x11\x00\x03\x11\x00"
    return segment(0xC0, b"\x08" + height.to_bytes(2, "big") + width.to_bytes(2, "big") + b"\x03" + components)


QUANT = segment(0xDB, b"\x00" + bytes((1,)) * 64)
HUFFMAN = segment(0xC4, b"\x00\x01" + bytes(15) + b"\x00" + b"\x10\x01" + bytes(15) + b"\x00")
SCAN = segment(0xDA, b"\x03\x01\x00\x02\x00\x03\x00\x00\x3f\x00")


def authored(width=19, height=17, entropy=b"\x15\xff\x00\xd9\x04", suffix=b""):
    return b"\xff\xd8" + QUANT + HUFFMAN + frame(width, height) + SCAN + entropy + b"\xff\xd9" + suffix


class SyntaxTests(unittest.TestCase):
    def rejected(self, data, reason=None):
        result = inspect_extent(data)
        self.assertFalse(result["accepted"], result)
        if reason:
            self.assertEqual(result["reason"], reason)

    def test_success_offsets_and_input_unchanged(self):
        data = authored()
        original = bytes(data)
        result = inspect_extent(data)
        self.assertTrue(result["accepted"])
        self.assertEqual((result["width"], result["height"], result["decodedBytes"]), (19, 17, 19 * 17 * 3))
        self.assertEqual(result["scanStart"], len(data) - 7)
        self.assertEqual(result["eoiEnd"], len(data))
        self.assertEqual(result["inputBytes"], len(data))
        self.assertEqual(data, original)

    def test_zero_padding_interval_policy_and_extent_retention(self):
        original = authored()
        for count in range(33):
            with self.subTest(suffixBytes=count):
                data = original + bytes(count)
                result = inspect_extent(data)
                self.assertTrue(result["accepted"])
                self.assertEqual(result["profileId"], PROFILE_ID)
                self.assertEqual(result["suffixBytes"], count)
                self.assertEqual(result["eoiEnd"], len(original))
                self.assertEqual(result["inputBytes"], len(data))
                self.assertEqual(data, original + bytes(count))
        for suffix in (bytes(33), bytes(64), b"\xff\xd9", authored(), bytes(16) + authored()):
            with self.subTest(length=len(suffix)):
                self.rejected(authored(suffix=suffix), "unsupported-suffix")

    def test_every_nonzero_suffix_position_refuses(self):
        for length in range(1, 33):
            for offset in range(length):
                for value in (1, 255):
                    suffix = bytes(offset) + bytes((value,)) + bytes(length - offset - 1)
                    with self.subTest(length=length, offset=offset, value=value):
                        self.rejected(authored(suffix=suffix), "unsupported-suffix")

    def test_entropy_and_marker_payload_cannot_fake_eoi(self):
        embedded = segment(0xE1, b"\xff\xd9\xff\xd8")
        data = authored()
        result = inspect_extent(data[:2] + embedded + data[2:])
        self.assertTrue(result["accepted"])
        self.assertEqual(result["eoiEnd"], len(data) + len(embedded))
        self.rejected(authored(entropy=b"\xff\x00\xd9")[:-2], "incomplete-extent")

    def test_fill_and_stuffing(self):
        self.assertTrue(inspect_extent(authored(entropy=b"\x12\xff"))["accepted"])
        self.rejected(authored(entropy=b"\xff\xff\x00"), "invalid-entropy-stuffing")
        for ending in (b"\xff", b"\xff\xff"):
            self.rejected(authored()[:-2] + ending, "incomplete-extent")

    def test_parser_does_not_claim_entropy_correctness(self):
        # Empty and arbitrary entropy deliberately remain decoder obligations.
        for entropy in (b"", b"\x00", b"\x01\x02\x03"):
            self.assertTrue(inspect_extent(authored(entropy=entropy))["accepted"])

    def test_dimensions_and_packed_output(self):
        for width, height in ((1, 1), (8192, 1), (1, 8192), (8192, 8192)):
            result = inspect_extent(authored(width, height))
            self.assertTrue(result["accepted"])
            self.assertEqual(result["decodedBytes"], width * height * 3)
            self.assertLessEqual(result["decodedBytes"], DECODED_LIMIT)
        self.assertLessEqual(DIMENSION_LIMIT ** 2 * 3, DECODED_LIMIT)
        for width, height in ((0, 1), (1, 0), (8193, 1), (1, 8193), (65535, 65535)):
            self.rejected(authored(width, height), "dimension-bound")

    def test_input_bound_and_type(self):
        self.rejected(bytes(INPUT_LIMIT + 1), "input-bound")
        for value in (bytearray(authored()), memoryview(authored()), None, "jpeg"):
            self.rejected(value, "input-type")

    def test_start_and_lengths(self):
        for value in (b"", b"\xff", b"\xff\xd9", b"other" + authored()):
            self.rejected(value, "missing-soi")
        for tail in (b"\xff\xdb", b"\xff\xdb\x00", b"\xff\xdb\x00\x01", b"\xff\xdb\xff\xff"):
            self.rejected(b"\xff\xd8" + tail, "segment-length")
        self.rejected(b"\xff\xd8\x01", "expected-marker")

    def test_unsupported_frames_and_coding_markers(self):
        for marker in (0xC1, 0xC2, 0xC3, 0xC9, 0xCC, 0xDD, 0xD0, 0xD8, 0, 0x01):
            self.rejected(b"\xff\xd8" + bytes((255, marker)), "unsupported-marker")
        self.rejected(b"\xff\xd8\xff\xd9", "missing-frame-or-scan")
        self.rejected(b"\xff\xd8" + frame() + frame(), "unsupported-frame")
        self.rejected(b"\xff\xd8" + segment(0xC0, b"\x0c" + frame()[5:]), "unsupported-frame")

    def test_frame_components(self):
        for components, reason in ((b"\x01\x11\x00" * 3, "duplicate-component"),
                                   (b"\x01\x01\x00\x02\x11\x00\x03\x11\x00", "unsupported-frame-component"),
                                   (b"\x01\x44\x00\x02\x11\x00\x03\x11\x00", "unsupported-mcu-block-count"),
                                   (b"\x01\x11\x04\x02\x11\x00\x03\x11\x00", "unsupported-frame-component")):
            self.rejected(b"\xff\xd8" + frame(components=components), reason)

    def test_tables_required_and_bounded(self):
        data = authored()
        self.rejected(data.replace(QUANT, b""), "missing-quantization-table")
        self.rejected(data.replace(HUFFMAN, b""), "missing-or-unsupported-huffman-table")
        for payload in (b"", b"\x10" + bytes((1,)) * 64, b"\x00\x01"):
            self.rejected(data.replace(QUANT, segment(0xDB, payload)))
        self.rejected(data.replace(QUANT, segment(0xDB, bytes(65))), "zero-quantization-value")
        for payload in (b"", b"\x00", b"\x20\x01" + bytes(16), b"\x00" + bytes((255,)) * 16):
            self.rejected(data.replace(HUFFMAN, segment(0xC4, payload)))
        self.rejected(data.replace(HUFFMAN, HUFFMAN[:-1] + b"\xff")[:-1])

    def test_scan_shape_selectors_and_postscan(self):
        data = authored()
        self.rejected(b"\xff\xd8" + SCAN, "unsupported-scan")
        for payload, reason in ((b"\x03\x01\x00\x02\x00\x02\x00\x00\x3f\x00", "scan-components"),
                                (b"\x03\x01\x11\x02\x00\x03\x00\x00\x3f\x00", "missing-or-unsupported-huffman-table"),
                                (b"\x03\x01\x00\x02\x00\x03\x00\x01\x3f\x00", "unsupported-scan")):
            self.rejected(data.replace(SCAN, segment(0xDA, payload)), reason)
        for tail in (b"\xff\xd0", SCAN, segment(0xFE, b"comment"), b"\xff\xc2"):
            self.rejected(data[:-2] + tail + b"\xff\xd9", "unsupported-postscan-marker")

    def test_every_incomplete_prefix_refuses(self):
        data = authored()
        for offset in range(len(data)):
            self.rejected(data[:offset])


if __name__ == "__main__":
    unittest.main()
