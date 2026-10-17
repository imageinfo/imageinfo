"""Pure-byte construction tests; no encoder, native decoder or media access."""

import unittest

import corruption
import syntax


def _segment(marker, payload):
    return bytes((255, marker)) + (len(payload) + 2).to_bytes(2, "big") + payload


def synthetic_envelope():
    """Authored structural bytes only; deliberately no native-validity claim."""
    q = _segment(219, b"\x00" + bytes((1,)) * 64)
    frame = _segment(192, b"\x08\x00\x40\x00\x40\x03"
                     b"\x01\x11\x00\x02\x11\x00\x03\x11\x00")
    counts = bytes((1,)) + bytes(15)
    huffman = _segment(196, b"\x00" + counts + b"\x00"
                       + b"\x10" + counts + b"\x00")
    scan = _segment(218, b"\x03\x01\x00\x02\x00\x03\x00\x00\x3f\x00")
    return b"\xff\xd8" + q + frame + huffman + scan + b"\x11\x22\xff\x00\x33\x44\x55\x66" + b"\xff\xd9"


class CorruptionTests(unittest.TestCase):
    def test_fixed_unique_declarations_and_fresh_metadata(self):
        rows = corruption.specs()
        self.assertEqual(len(rows), 16)
        self.assertEqual(len({row["id"] for row in rows}), 16)
        self.assertEqual(sum(row["expected"]["nativeWarningOrErrorRequired"] for row in rows), 2)
        self.assertEqual(sum(row["expected"]["nativeInvoked"] for row in rows), 2)
        rows[0]["expected"]["syntaxAccepted"] = "changed"
        self.assertIs(corruption.specs()[0]["expected"]["syntaxAccepted"], False)
        self.assertIs(corruption.declaration()["historicalPillowStrictCandidateAccepted"], False)

    def test_every_mutation_matches_declared_syntax_and_preserves_input(self):
        original = synthetic_envelope()
        saved = bytes(original)
        self.assertTrue(syntax.inspect_extent(original)["accepted"])
        outputs = set()
        for spec in corruption.specs():
            with self.subTest(spec["id"]):
                result = corruption.build_corruption(spec["id"], original)
                self.assertIs(type(result), bytes)
                self.assertNotEqual(result, original)
                self.assertEqual(original, saved)
                self.assertEqual(syntax.inspect_extent(result)["accepted"],
                                 spec["expected"]["syntaxAccepted"])
                outputs.add(result)
        self.assertEqual(len(outputs), 16)

    def test_entropy_cut_and_suffix_are_exact(self):
        original = synthetic_envelope()
        _, scan, eoi = corruption._layout(original)
        cut = scan + (eoi - scan) // 2
        self.assertEqual(corruption.build_corruption("entropy-truncated", original), original[:cut])
        self.assertEqual(corruption.build_corruption("early-eoi", original), original[:cut] + b"\xff\xd9")
        self.assertEqual(corruption.build_corruption("immediate-eoi", original), original[:scan] + b"\xff\xd9")
        self.assertEqual(corruption.build_corruption("suffix-zero33", original), original + bytes(33))
        for case_id, position in (("suffix-nonzero", 0), ("suffix-nonzero-middle", 16),
                                  ("suffix-nonzero-last", 31)):
            suffix = bytearray(32)
            suffix[position] = 1
            self.assertEqual(corruption.build_corruption(case_id, original), original + bytes(suffix))
        for obsolete in ("suffix-zero1", "suffix-zero31"):
            with self.assertRaises(ValueError):
                corruption.build_corruption(obsolete, original)
        self.assertEqual(corruption.build_corruption("suffix-second-jpeg", original), original * 2)

    def test_unknown_or_incomplete_or_mutable_base_refuses(self):
        with self.assertRaises(ValueError):
            corruption.build_corruption("not-declared", synthetic_envelope())
        for data in (b"", b"\xff\xd8\xff\xd9", synthetic_envelope()[:-1],
                     synthetic_envelope() + bytes(32)):
            with self.subTest(length=len(data)), self.assertRaises(ValueError):
                corruption.build_corruption("early-eoi", data)
        with self.assertRaises(TypeError):
            corruption.build_corruption("early-eoi", bytearray(synthetic_envelope()))


if __name__ == "__main__":
    unittest.main()
