"""Public structural controls contain no camera bytes or camera-derived results."""
import importlib.util
import hashlib
from pathlib import Path
import struct
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('reference_effects', Path(__file__).with_name('qualify_private.py'))
q = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(q)


def atom(kind, body):
    return struct.pack('>I4s', len(body) + 8, kind) + body


def authored(order='<', alias=False):
    # One date and one unrelated ASCII entry; these are structural markers, not
    # a claimed decodable Canon sensor sample or accepted production fixture.
    header = b'II' if order == '<' else b'MM'
    tiff = bytearray(header + struct.pack(order + 'HI', 42, 8))
    tiff.extend(struct.pack(order + 'H', 2))
    payload = 8 + 2 + 24 + 4
    tiff.extend(struct.pack(order + 'HHII', 0x9003, 2, 20, payload))
    tiff.extend(struct.pack(order + 'HHII', 0x9004, 2, 20, payload if alias else payload + 20))
    tiff.extend(struct.pack(order + 'I', 0))
    tiff.extend(b'2020:02:29 12:34:56\0')
    tiff.extend(b'2021:02:28 01:02:03\0')
    return atom(b'ftyp', b'crx \0\0\0\0') + atom(b'moov', atom(b'uuid', q.CANON + atom(b'CMT2', tiff))) + atom(b'mdat', b'authored-not-raw')


class Controls(unittest.TestCase):
    def test_little_and_big_endian_unique_target_inventory(self):
        for order, expected in [('<', 'little'), ('>', 'big')]:
            value = q.layout(authored(order))
            self.assertEqual(value['target']['byteOrder'], expected)
            self.assertEqual(value['target']['length'], 20)
            self.assertEqual(len(value['allocations']), 2)

    def test_allocation_alias_is_rejected_before_candidate_comparison(self):
        with self.assertRaises(q.Refused):
            q.layout(authored(alias=True))

    def test_exact_fixed_patch_and_differing_run_partition(self):
        original = authored()
        inventory = q.layout(original)
        offset = inventory['target']['offset']
        candidate = original[:offset] + q.DATE + original[offset + 20:]
        comparison = q.compare(original, candidate, inventory, q.layout(candidate))
        self.assertTrue(comparison['exactFixedDatePatch'])
        self.assertTrue(comparison['mdatPayloadsEqualInOrder'])
        actual = {index for index, (a, b) in enumerate(zip(original, candidate)) if a != b}
        reported = {index for run in comparison['runs'] for index in range(run['offset'], run['offset'] + run['length'])}
        self.assertEqual(reported, actual)
        self.assertTrue(all(run['sourceClasses'] == ['selected-date-allocation'] for run in comparison['runs']))

    def test_extra_effect_is_reported_not_silently_expanded(self):
        original = authored()
        before = q.layout(original)
        offset = before['target']['offset']
        candidate = bytearray(original[:offset] + q.DATE + original[offset + 20:])
        candidate[-1] ^= 1
        comparison = q.compare(original, candidate, before, q.layout(candidate))
        self.assertFalse(comparison['exactFixedDatePatch'])
        self.assertFalse(comparison['mdatPayloadsEqualInOrder'])
        self.assertIn('mdat-payload', comparison['runs'][-1]['sourceClasses'])

    def test_runs_cross_buffers_and_include_explicit_growth(self):
        before = b'a' * (65536 * 2)
        after = before[:65535] + b'bb' + before[65537:] + b'extra'
        self.assertEqual(q.differing_runs(before, after), [(65535, 2), (len(before), 5)])
        self.assertEqual(q.differing_runs(b'abc', b'abc'), [])

    def test_truncated_cyclic_and_unknown_width_structures_refuse(self):
        original = authored()
        for data in [original[:7], original[:-1]]:
            with self.assertRaises(q.Refused):
                q.layout(data)
        inventory = q.layout(original)
        base = next(box['body'] for box in inventory['boxes'] if box['kind'] == 'CMT2')
        cyclic = bytearray(original)
        struct.pack_into('<I', cyclic, base + 8 + 2 + 24, 8)
        with self.assertRaises(q.Refused):
            q.layout(cyclic)
        width = bytearray(original)
        struct.pack_into('<H', width, base + 8 + 2 + 2, 255)
        with self.assertRaises(q.Refused):
            q.layout(width)

    def test_missing_or_ambiguous_tag_and_inline_structure_overlap_refuse(self):
        original = authored()
        inventory = q.layout(original)
        base = next(box['body'] for box in inventory['boxes'] if box['kind'] == 'CMT2')
        for first, second in [(0x9005, 0x9004), (0x9003, 0x9003)]:
            changed = bytearray(original)
            struct.pack_into('<H', changed, base + 10, first)
            struct.pack_into('<H', changed, base + 22, second)
            with self.assertRaises(q.Refused):
                q.layout(changed)
        changed = bytearray(original)
        struct.pack_into('<I', changed, base + 18, 8)
        with self.assertRaises(q.Refused):
            q.layout(changed)

    def test_metadata_difference_separates_derived_and_file_effects(self):
        source = {'SourceFile': 'old', 'File:System:FileName': 'old',
                  'Composite:SubSecDateTimeOriginal': 'old', 'EXIF:ExifIFD:DateTimeOriginal': 'old'}
        candidate = {key: 'new' for key in source}
        changes = q.metadata_changes(source, candidate)
        self.assertEqual({row['class'] for row in changes},
                         {'source-locator', 'filesystem-observation', 'derived-composite', 'stored-or-other'})

    def test_duplicate_reference_json_keys_refuse(self):
        with self.assertRaises(q.Refused):
            q.strict_json('{"same":1,"same":2}')

    def test_distribution_binding_detects_changed_component(self):
        scratch = Path(__file__).resolve().parents[2] / '.local/0099-authored-controls'
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            root = Path(directory)
            module = root / 'authored-marker.pm'
            module.write_bytes(b'authored tool marker')
            manifest = root / 'distribution.json'
            q.dump(manifest, {'root': str(root), 'files': [
                {'path': module.name, 'byteLength': str(module.stat().st_size), 'sha256': q.sha(module)}]})
            pinned = q.sha(manifest)
            self.assertEqual(q.verify_distribution(manifest, pinned)['verifiedFileCount'], 1)
            module.write_bytes(b'tampered tool marker')
            with self.assertRaises(q.Refused):
                q.verify_distribution(manifest, pinned)
            with self.assertRaises(q.Refused):
                q.verify_distribution(manifest, '0' * 64)

    def test_complete_streamed_summary_keeps_bounded_samples(self):
        before, after = b'a' * 40, b'ba' * 20
        summary = q.summarize_runs(before, after, 3)
        expected = [(index, 1) for index in range(0, 40, 2)]
        self.assertEqual(summary['runCount'], 20)
        self.assertEqual(summary['changedBytes'], 20)
        self.assertEqual(summary['samples'], expected[:3])
        self.assertFalse(summary['retainedRunListComplete'])
        digest = hashlib.sha256(b''.join(struct.pack('>QQ', *run) for run in expected)).hexdigest()
        self.assertEqual(summary['completeRunSequenceSha256'], digest)

    def test_aligned_partition_distinguishes_relocation_from_payload_change(self):
        before = authored()
        old = q.layout(before)
        date = old['target']['offset']
        candidate = before[:date] + q.DATE + before[date + 20:]
        mdat = next(box['start'] for box in old['boxes'] if box['kind'] == 'mdat')
        candidate = candidate[:mdat] + atom(b'free', b'authored relocation marker') + candidate[mdat:]
        new = q.layout(candidate)
        comparison = q.compare(before, candidate, old, new)
        self.assertFalse(comparison['exactFixedDatePatch'])
        self.assertTrue(comparison['mdatPayloadsEqualInOrder'])
        mdat_payload = next(row for row in comparison['alignedRegions'] if row['path'] == (('mdat', 0),) and row['part'] == 'payload')
        self.assertTrue(mdat_payload['contentEqual'] and mdat_payload['equalContentMoved'])
        for data, inventory in [(before, old), (candidate, new)]:
            spans = q.partition(data, inventory).values()
            self.assertEqual(sum(end - start for start, end in spans), len(data))


if __name__ == '__main__':
    unittest.main()
