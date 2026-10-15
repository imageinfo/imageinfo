"""Authored adversarial controls for the separate byte witness, no camera data."""
import struct
import unittest

import independent_audit as audit


def atom(kind, body):
    return struct.pack('>I4s', len(body) + 8, kind) + body


def classic(order='<', alias=False, nonzero_gap=False):
    value = b'2024:02:29 12:34:56\0'
    # Two equal tag IDs remain distinct occurrences; the second is inline.
    data = bytearray((b'II' if order == '<' else b'MM') + struct.pack(order + 'HI', 42, 8))
    data += struct.pack(order + 'H', 2)
    data += struct.pack(order + 'HHII', 0x9003, 2, 20, 40)
    data += struct.pack(order + 'HHI', 0x9003 if alias else 0x9004, 3, 1) + b'\x05\0\0\0'
    data += struct.pack(order + 'I', 0)
    data += b'X\0' if nonzero_gap else b'\0\0'
    data += value
    return data


def fixture(chunk64=False):
    cmt = atom(b'uuid', audit.CANON + atom(b'CMT2', classic()))
    chunk = lambda offset: atom(b'co64' if chunk64 else b'stco',
                                struct.pack('>II', 0, 1) + offset.to_bytes(8 if chunk64 else 4, 'big'))
    track = lambda offset: atom(b'trak', atom(b'mdia', atom(b'minf', atom(b'stbl', chunk(offset)))))
    references = lambda offset: atom(b'CTBO', struct.pack('>IIQQ', 1, 3, offset, 16))
    header = atom(b'ftyp', b'authored')
    movie = atom(b'moov', cmt + references(0) + track(0))
    media_start = len(header) + len(movie)
    movie = atom(b'moov', cmt + references(media_start) + track(media_start + 8))
    return header + movie + atom(b'mdat', b'01234567')


class IndependentControls(unittest.TestCase):
    def test_both_orders_preserve_complete_value_bytes(self):
        for order in ('<', '>'):
            result = audit.tiff(classic(order))
            self.assertEqual(result['byteOrder'], order)
            self.assertEqual(result['values'][0]['sha256'], audit.digest(b'2024:02:29 12:34:56\0'))
            self.assertEqual(result['coveredBytes'] + sum(g['length'] for g in result['gaps']), result['length'])

    def test_duplicate_tags_keep_occurrence_identity(self):
        values = audit.tiff(classic(alias=True))['values']
        self.assertEqual([(v['tag'], v['duplicate']) for v in values], [(0x9003, 0), (0x9003, 1)])

    def test_nonzero_unallocated_gap_is_explicit(self):
        result = audit.tiff(classic(nonzero_gap=True))
        self.assertEqual(result['gaps'], [{'offset': 38, 'length': 2, 'allZero': False,
                                          'sha256': audit.digest(b'X\0')}])

    def test_aliased_value_extents_do_not_double_count(self):
        data = classic()
        struct.pack_into('<HHII', data, 22, 0x9004, 2, 20, 40)
        result = audit.tiff(data)
        self.assertEqual(result['values'][0]['offset'], result['values'][1]['offset'])
        self.assertEqual(result['coveredBytes'], 58)

    def test_next_ifd_has_distinct_logical_path(self):
        data = classic()
        struct.pack_into('<I', data, 34, len(data))
        data += struct.pack('<H', 1) + struct.pack('<HHII', 0x1234, 4, 1, 7) + struct.pack('<I', 0)
        self.assertEqual(audit.tiff(data)['values'][-1]['directory'], ('root', 'next'))

    def test_cycle_and_structure_overlap_refuse(self):
        for offset in (8, 10):
            data = classic()
            struct.pack_into('<I', data, 34, offset)
            with self.assertRaises(audit.Refused):
                audit.tiff(data)

    def test_unknown_width_and_escaping_value_refuse(self):
        data = classic()
        struct.pack_into('<H', data, 12, 99)
        with self.assertRaises(audit.Refused):
            audit.tiff(data)
        data = classic()
        struct.pack_into('<I', data, 18, 0xffffffff)
        with self.assertRaises(audit.Refused):
            audit.tiff(data)

    def test_ctbo_exact_extent_and_chunk_relative_binding(self):
        for wide in (False, True):
            result = audit.inspect(fixture(wide))
            self.assertEqual(result['ctbo'][0]['exactBoxMatches'], [(('mdat', 0),)])
            self.assertEqual(result['chunks'][0]['relativeOffset'], 0)
            self.assertEqual(result['chunks'][0]['mdatPath'], (('mdat', 0),))

    def test_chunk_at_media_end_is_not_a_payload_start(self):
        data = bytearray(fixture())
        table = next(b for b in audit.boxes(data) if b['kind'] == 'stco')
        struct.pack_into('>I', data, table['body'] + 8, len(data))
        with self.assertRaises(audit.Refused):
            audit.inspect(data)

    def test_ctbo_extent_and_entry_count_refuse(self):
        data = bytearray(fixture())
        table = next(b for b in audit.boxes(data) if b['kind'] == 'CTBO')
        struct.pack_into('>Q', data, table['body'] + 16, len(data))
        with self.assertRaises(audit.Refused):
            audit.inspect(data)
        data = bytearray(fixture())
        struct.pack_into('>I', data, table['body'], 2)
        with self.assertRaises(audit.Refused):
            audit.inspect(data)

    def test_extended_box_size_and_partial_header(self):
        extended = struct.pack('>I4sQ', 1, b'free', 19) + b'abc'
        self.assertEqual(audit.boxes(extended)[0]['body'], 16)
        for data in (extended[:-1], b'1234567'):
            with self.assertRaises(audit.Refused):
                audit.boxes(data)


if __name__ == '__main__':
    unittest.main()
