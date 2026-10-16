"""Independent literal ownership and semantic challenges; never imports runner."""
import struct
from pathlib import Path
import tempfile
import unittest

import audit


def atom(kind, body):
    return struct.pack('>I4s', len(body) + 8, kind) + body


def directory(order='<', shape='outline', date=audit.ORIGINAL, altered=None):
    """Separately authored flat TIFF: explicit directory and data extents."""
    prefix = b'II' if order == '<' else b'MM'
    extras = shape != 'baseline'
    address = 38 if extras else 26
    date_entry = struct.pack(order + 'HHII', 0x9003, 2, 20, address)
    extra, payload = b'', date
    if extras:
        kind, count = {'inline': (7, 4), 'outline': (7, 14),
                       'alias': (2, 20), 'checksum': (4, 1)}[shape]
        if shape == 'inline':
            slot = b'\x91\x72\x53\x34' if altered is None else altered
        elif shape == 'outline':
            slot = struct.pack(order + 'I', address + 20)
            payload += b'AUTHORED-0113\0' if altered is None else altered
        elif shape == 'alias':
            slot = struct.pack(order + 'I', address)
        else:
            # Literal original-date checksum: sum of the twenty invented bytes.
            slot = struct.pack(order + 'I', 959 if altered is None else altered)
        extra = struct.pack(order + 'HHI', 0xdffe, kind, count) + slot
    return (prefix + struct.pack(order + 'HIH', 42, 8, 2 if extras else 1)
            + date_entry + extra + bytes(4) + payload)


def fixture(order='<', shape='outline', date=audit.ORIGINAL, altered=None):
    companion = (b'II' if order == '<' else b'MM') + struct.pack(order + 'HIH', 42, 8, 1)
    companion += struct.pack(order + 'HHI', 0, 1, 4) + b'\x02\x03\0\0' + bytes(4)
    body = (atom(b'CNCV', b'CanonCR3_0113\0')
            + atom(b'CMT2', directory(order, shape, date, altered)) + atom(b'CMT4', companion))
    return atom(b'ftyp', b'crx \0\0\0\0crx ') + atom(b'moov', atom(b'uuid', audit.CANON + body))


def cell(shape='outline', assignment='changed', order='<'):
    return {'id': 'independent', 'storage': shape, 'assignment': assignment,
            'order': 'II' if order == '<' else 'MM', 'pad': False}


class OwnershipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (Path(__file__).resolve().parents[2] / '.local').mkdir(exist_ok=True)

    def test_complete_literal_values_in_both_orders(self):
        for order in ('<', '>'):
            block = audit.parse_tiff(directory(order))
            self.assertEqual(block['entries'][1]['valueHex'], '415554484f5245442d3031313300')
            self.assertEqual(sum(part['length'] for part in block['partition']), 72)
            self.assertEqual(block['gaps'], [])
            self.assertEqual(b''.join(bytes.fromhex(p['hex']) for p in block['partition']), directory(order))

    def test_shared_allocation_keeps_both_owners_one_denominator(self):
        block = audit.parse_tiff(directory(shape='alias'))
        shared = [part for part in block['partition'] if part['owners'] == ['value:0', 'value:1']]
        self.assertEqual([(part['offset'], part['length']) for part in shared], [(38, 20)])
        self.assertEqual(sum(part['length'] for part in block['partition']), 58)

    def test_partial_overlap_is_explicit(self):
        data = bytearray(directory(shape='alias') + b'Z')
        struct.pack_into('<I', data, 30, 39)
        block = audit.parse_tiff(bytes(data))
        self.assertEqual(audit.alias_relationship(*block['entries']), 'partial-overlap')
        self.assertEqual(sum(p['length'] for p in block['partition'] if len(p['owners']) == 2), 19)

    def test_duplicate_tags_have_distinct_ordinals(self):
        data = bytearray(directory(shape='alias'))
        struct.pack_into('<H', data, 22, 0x9003)
        entries = audit.parse_tiff(bytes(data))['entries']
        self.assertEqual([e['duplicate'] for e in entries], [0, 1])
        with self.assertRaises(audit.Refused):
            audit.inspect(fixture(shape='alias').replace(bytes.fromhex('fedf0200'), bytes.fromhex('03900200')))

    def test_structure_overlap_pointer_escape_width_and_cycle_refuse(self):
        for at, format_, value in ((18, 'I', 12), (30, 'I', 0xffffffff),
                                   (24, 'H', 99), (34, 'I', 8)):
            data = bytearray(directory())
            struct.pack_into('<' + format_, data, at, value)
            with self.assertRaises(audit.Refused):
                audit.parse_tiff(bytes(data))

    def test_added_and_missing_are_distinct_from_equal_empty(self):
        before = fixture(shape='outline')
        after = fixture(shape='baseline', date=audit.CHANGED)
        result = audit.compare_output(before, after, audit.inspect(before), cell())
        self.assertEqual(result['unknownEntryState'], 'removed')
        self.assertTrue(any(change['outputHex'] is None for change in result['logicalValueChanges']))
        baseline = fixture(shape='baseline')
        added = audit.compare_output(baseline, fixture(date=audit.CHANGED), audit.inspect(baseline), cell('baseline'))
        self.assertEqual(added['unknownEntryState'], 'added')

    def test_changed_unknown_bytes_are_measured_not_called_preserved(self):
        before = fixture()
        after = fixture(date=audit.CHANGED, altered=b'CORRUPTED-011\0')
        result = audit.compare_output(before, after, audit.inspect(before), cell())
        self.assertEqual(result['unknownEntryState'], 'value-changed')

    def test_wrong_date_and_leaf_corruption_refuse(self):
        before = fixture()
        for after in (before, fixture(date=audit.CHANGED).replace(b'CanonCR3_0113', b'CanonCR3_BAD!')):
            with self.assertRaises(audit.Refused):
                audit.compare_output(before, after, audit.inspect(before), cell())

    def test_stale_and_updated_invented_checksum_are_distinct(self):
        for order in ('<', '>'):
            before = fixture(order, 'checksum')
            audit.verify_input(before, cell('checksum', order=order))
            stale = audit.compare_output(before, fixture(order, 'checksum', audit.CHANGED),
                                         audit.inspect(before), cell('checksum', order=order))
            updated = audit.compare_output(before, fixture(order, 'checksum', audit.CHANGED, 968),
                                           audit.inspect(before), cell('checksum', order=order))
            self.assertEqual(stale['unknownEntryState'], 'value-preserved')
            self.assertFalse(stale['fixtureDefinedChecksumConsistent'])
            self.assertTrue(updated['fixtureDefinedChecksumConsistent'])
            self.assertFalse(updated['checksumIsCanonAlgorithm'])

    def test_complete_alias_is_not_inferred_from_equal_values(self):
        source = fixture(shape='alias')
        old = audit.inspect(source)
        # Two separate equal date values have no physical alias relationship.
        tiff = bytearray(directory(shape='alias'))
        struct.pack_into('<I', tiff, 30, len(tiff))
        tiff.extend(audit.ORIGINAL)
        parsed = audit.parse_tiff(bytes(tiff))
        self.assertEqual(audit.alias_relationship(*parsed['entries']), 'separate-storage')
        self.assertEqual(audit.alias_relationship(*old['cmts']['CMT2']['entries']), 'exact-shared-storage')

    def test_source_shape_and_endian_substitution_refuse(self):
        for data in (fixture('>'), fixture(altered=b'WRONG-VALUE!!\0')):
            with self.assertRaises(audit.Refused):
                audit.verify_input(data, cell())

    def test_duplicate_json_and_evidence_substitution_refuse(self):
        with self.assertRaises(audit.Refused):
            audit.strict_json('{"a":1,"a":2}')
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2] / '.local') as name:
            root = Path(name).resolve()
            (root / 'value').write_bytes(b'abc')
            for path, hash_ in (('../value', audit.digest(b'abc')), ('value', audit.digest(b'xyz'))):
                with self.assertRaises(audit.Refused):
                    audit.file_bytes(root, {'path': path, 'size': 3, 'sha256': hash_})


if __name__ == '__main__':
    unittest.main()
