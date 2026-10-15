"""Authored structural attribution controls; no camera input or observation."""
import importlib.util
from pathlib import Path
import struct
import unittest

SPEC = importlib.util.spec_from_file_location('attribute', Path(__file__).with_name('attribute_private.py'))
a = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(a)


def atom(kind, body):
    return struct.pack('>I4s', len(body) + 8, kind) + body


def authored(order='<', gap=0, tail=24, date=b'2020:02:29 12:34:56\0', wide=True, data_index=1):
    base = 8 + 2 + 24 + 4
    tiff = ((b'II' if order == '<' else b'MM') + struct.pack(order + 'HIH', 42, 8, 2)
            + struct.pack(order + 'HHII', 0x9003, 2, 20, base + gap)
            + struct.pack(order + 'HHI', 0x100, 3, 1) + struct.pack(order + 'H', 7) + b'\0\0'
            + struct.pack(order + 'I', 0) + b'\0' * gap + date + b'\0' * tail)
    payload = b'HEADabcdeTAIL'

    def movie(mdat_start):
        body = mdat_start + 8
        ctbo = atom(b'CTBO', struct.pack('>IIQQ', 1, 1, mdat_start, 8 + len(payload)))
        description = atom(b'stsd', struct.pack('>III4s6sH', 0, 1, 16, b'CRAW', b'\0' * 6, data_index))
        offsets = atom(b'co64' if wide else b'stco', struct.pack('>II', 0, 1) + struct.pack('>Q' if wide else '>I', body + 4))
        sizes = atom(b'stsz', struct.pack('>III', 0, 5, 1))
        mapping = atom(b'stsc', struct.pack('>IIIII', 0, 1, 1, 1, 1))
        table = atom(b'stbl', description + mapping + sizes + offsets)
        refs = atom(b'dinf', atom(b'dref', struct.pack('>III4sI', 0, 1, 12, b'url ', 1)))
        track = atom(b'trak', atom(b'mdia', atom(b'minf', refs + table)))
        return atom(b'moov', atom(b'uuid', a.CANON + ctbo + atom(b'CMT2', tiff)) + track)

    prefix = atom(b'ftyp', b'crx \0\0\0\0')
    first = movie(0)
    return prefix + movie(len(prefix) + len(first)) + atom(b'mdat', payload)


class Controls(unittest.TestCase):
    def test_all_allocations_preserve_identity_and_values_except_exact_date(self):
        for order in ('<', '>'):
            before = authored(order)
            after = authored(order, gap=12, tail=0, date=a.DATE)
            report = a.analyze(before, after)
            unchanged = [row for row in report['allocations'] if not row['selectedDate']]
            self.assertTrue(all(row['bytesEqual'] for row in unchanged))
            selected = next(row for row in report['allocations'] if row['selectedDate'])
            self.assertTrue(selected['selectedDateMatchesIntent'])
            self.assertFalse(selected['bytesEqual'])
            self.assertTrue(report['pointers']['ctbo'][0]['sameResolvedTarget'])
            self.assertTrue(report['pointers']['samples'][0]['sameBoundedSample'])
            meanings = {row['attribution'] for row in report['cellComparisons']}
            self.assertIn('parsed-tiff-allocation-address-rewrite', meanings)
            self.assertIn('validated-ctbo-target-relocation', meanings)
            self.assertIn('validated-sample-relocation', meanings)
            self.assertFalse(report['productionMutationAllowed'])

    def test_complete_partition_counts_each_byte_once_and_gaps_are_not_assumed_safe(self):
        data = authored()
        parsed = a.inspect(data)
        coverage = [0] * len(data)
        for row in parsed['partition']:
            for index in range(row['start'], row['end']):
                coverage[index] += 1
        self.assertTrue(all(count == 1 for count in coverage))
        after = authored(gap=12, tail=0, date=a.DATE)
        report = a.analyze(data, after)
        self.assertTrue(all(row['nonzeroBytes'] == 0 for row in report['sourceGaps']))
        self.assertTrue(any(row['attribution'] == 'unexplained-or-unallocated-byte-change'
                            for row in report['cellComparisons']))

    def test_nonzero_unallocated_storage_is_explicit(self):
        data = bytearray(authored())
        parsed = a.inspect(data)
        start, end = parsed['cmts']['CMT2']['gaps'][-1]
        data[start] = 0x7f
        summary = a.gap_summary(data, a.inspect(data))
        self.assertEqual(sum(row['nonzeroBytes'] for row in summary), 1)
        self.assertTrue(all('semantics-not-inferred' in row['meaning'] for row in summary))

    def test_both_chunk_widths_bind_the_same_sample(self):
        for wide, name in [(True, 'co64'), (False, 'stco')]:
            data = authored(wide=wide)
            report = a.analyze(data, data)
            sample = report['pointers']['samples'][0]
            self.assertEqual(sample['source']['offsetKind'], name)
            self.assertTrue(sample['sameBoundedSample'])

    def test_external_sample_reference_and_offset_overflow_refuse(self):
        with self.assertRaises(a.Refused):
            a.analyze(authored(), authored(data_index=2))
        data = bytearray(authored())
        parsed = a.inspect(data)
        chunk = next(box for box in parsed['boxes'] if box['kind'] == 'co64')
        struct.pack_into('>Q', data, chunk['body'] + 8, (1 << 64) - 1)
        with self.assertRaises(a.Refused):
            a.analyze(authored(), data)

    def test_missing_duplicate_and_out_of_bounds_ctbo_refuse(self):
        duplicate = struct.pack('>I', 2) + struct.pack('>IQQ', 1, 0, 0) * 2
        with self.assertRaises(a.Refused):
            a.ctbo(duplicate, 0, len(duplicate))
        overflow = struct.pack('>IIQQ', 1, 1, (1 << 64) - 1, 2)
        with self.assertRaises(a.Refused):
            a.ctbo(overflow, 0, len(overflow))
        with self.assertRaises(a.Refused):
            a.ctbo(b'\0\0\0\1', 0, 4)

    def test_missing_or_duplicate_date_and_overlapping_owner_refuse(self):
        original = authored()
        parsed = a.inspect(original)
        rows = list(parsed['cmts']['CMT2']['allocations'].values())
        date = next(row for row in rows if row['key'][2] == 0x9003)
        other = next(row for row in rows if row['key'][2] != 0x9003)
        for replacement in (0x9004, 0x100):
            data = bytearray(original)
            struct.pack_into('<H', data, date['entry'], replacement)
            with self.assertRaises(a.Refused):
                a.analyze(original, data)
        data = bytearray(original)
        struct.pack_into('<HHII', data, other['entry'], 0x9003, 2, 20,
                         date['offset'] - parsed['cmts']['CMT2']['base'])
        with self.assertRaises(a.Refused):
            a.analyze(original, data)
        struct.pack_into('<H', data, other['entry'], 0x9004)
        with self.assertRaises(a.Refused):
            a.analyze(original, data)

    def test_ifd_cycle_unknown_width_and_truncation_refuse(self):
        data = bytearray(authored())
        parsed = a.inspect(data)
        base = parsed['cmts']['CMT2']['base']
        struct.pack_into('<I', data, base + 8 + 2 + 24, 8)
        with self.assertRaises(a.Refused):
            a.inspect(data)
        data = bytearray(authored())
        struct.pack_into('<H', data, base + 12, 255)
        with self.assertRaises(a.Refused):
            a.inspect(data)
        with self.assertRaises(a.Refused):
            a.inspect(authored()[:-1])

    def test_allocation_matching_never_uses_payload_value(self):
        old = authored()
        new = bytearray(old)
        row = next(row for row in a.inspect(old)['cmts']['CMT2']['allocations'].values() if row['key'][2] == 0x100)
        struct.pack_into('<H', new, row['entry'], 0x101)
        report = a.analyze(old, new)
        unmatched = [row for row in report['allocations'] if row['source'] is None or row['candidate'] is None]
        self.assertEqual(len(unmatched), 2)
        self.assertTrue(all(not row['bytesEqual'] for row in unmatched))

    def test_declared_duplicate_tag_ordinal_remains_distinct(self):
        data = authored()
        parsed = a.inspect(data)
        block = parsed['cmts']['CMT2']
        # Standalone TIFF parser supports duplicate non-date tag identities.
        raw = bytearray(data)
        rows = list(block['allocations'].values())
        struct.pack_into('<H', raw, rows[0]['entry'], 0x100)
        revised = a.inspect(raw)['cmts']['CMT2']
        ordinals = sorted(key[3] for key in revised['allocations'])
        self.assertEqual(ordinals, [0, 1])

    def test_orphan_offset_cell_cannot_borrow_another_tracks_witness(self):
        source = authored() + atom(b'co64', struct.pack('>IIQ', 0, 1, 0))
        candidate = authored() + atom(b'co64', struct.pack('>IIQ', 0, 1, 1))
        report = a.analyze(source, candidate)
        orphan = next(row for row in report['cellComparisons']
                      if row['role'] == 'chunk-offset:' + a.key_text((('co64', 0),)))
        self.assertEqual(orphan['attribution'], 'unexplained-or-unallocated-byte-change')


if __name__ == '__main__':
    unittest.main()
