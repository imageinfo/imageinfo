"""Literal authored adversarial witnesses, independent of the fixture runner."""
import struct
from pathlib import Path
import tempfile
import unittest

import audit


def atom(kind, payload):
    return struct.pack('>I4s', 8 + len(payload), kind) + payload


def tiff(value=b'INVENTED\0', tail=b'\x91\x72', order='<'):
    prefix = b'II' if order == '<' else b'MM'
    return (prefix + struct.pack(order + 'HIH', 42, 8, 1)
            + struct.pack(order + 'HHII', 0x12, 2, len(value), 26)
            + struct.pack(order + 'I', 0) + value + tail)


def fixture():
    date = (b'II*\0\x08\0\0\0\x01\0\x03\x90\x02\0\x14\0\0\0'
            b'\x1a\0\0\0\0\0\0\0' + b'2002:03:04 05:06:07\0')
    return atom(b'ftyp', b'crx \0\0\0\0crx ') + atom(
        b'moov', atom(b'uuid', audit.CANON + atom(b'CMT2', date) + atom(b'CMT4', tiff())))


class ByteWitnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (Path(__file__).resolve().parents[2] / '.local').mkdir(exist_ok=True)

    def test_literal_value_and_gap_in_both_orders(self):
        for order in ('<', '>'):
            result = audit.parse_tiff(tiff(order=order))
            self.assertEqual(result['entries'][0]['valueHex'], '494e56454e54454400')
            self.assertEqual(result['gaps'], [{'offset': 35, 'length': 2, 'hex': '9172'}])

    def test_zero_padding_is_not_nonzero_preservation(self):
        old = audit.parse_tiff(tiff())
        new = audit.parse_tiff(tiff(tail=b'\0\0'))
        self.assertNotEqual(old['gaps'], new['gaps'])
        self.assertEqual(old['entries'], new['entries'])

    def test_removed_storage_is_absent_not_equal_empty(self):
        old = audit.parse_tiff(tiff())
        new = audit.parse_tiff(tiff(tail=b''))
        self.assertTrue(old['gaps'])
        self.assertEqual(new['gaps'], [])

    def test_pointer_into_directory_is_rejected(self):
        data = bytearray(tiff())
        struct.pack_into('<I', data, 18, 12)
        with self.assertRaises(audit.Refused):
            audit.parse_tiff(bytes(data))

    def test_pointer_escape_and_unknown_width_refuse(self):
        for position, format_, value in ((18, 'I', 0xffffffff), (12, 'H', 99)):
            data = bytearray(tiff())
            struct.pack_into('<' + format_, data, position, value)
            with self.assertRaises(audit.Refused):
                audit.parse_tiff(bytes(data))

    def test_next_directory_cycle_refuses(self):
        data = bytearray(tiff())
        struct.pack_into('<I', data, 22, 8)
        with self.assertRaises(audit.Refused):
            audit.parse_tiff(bytes(data))

    def test_full_literal_date_and_box_coverage(self):
        result = audit.inspect(fixture())
        self.assertEqual(bytes.fromhex(result['selectedDateHex']), b'2002:03:04 05:06:07\0')
        self.assertEqual(result['boxes'][-1]['end'], len(fixture()))
        self.assertEqual(result['cmts']['CMT4']['entries'][0]['tag'], 18)

    def test_duplicate_directory_and_truncated_box_refuse(self):
        original = fixture()
        body = audit.CANON + atom(b'CMT2', b'') + atom(b'CMT2', b'')
        for malformed in (original[:-1], atom(b'moov', atom(b'uuid', body))):
            with self.assertRaises(audit.Refused):
                audit.inspect(malformed)

    def test_duplicate_json_keys_refuse(self):
        with self.assertRaises(audit.Refused):
            audit.strict_json('{"a":1,"a":2}')

    def test_comparison_rejects_wrong_date_and_unselected_value(self):
        old_bytes = fixture()
        old = audit.inspect(old_bytes)
        cell = {'id': 'invented-control', 'assignment': 'changed'}
        good = old_bytes.replace(b'2002:03:04 05:06:07\0', b'2007:08:09 10:11:12\0')
        self.assertTrue(audit.compare_output(old_bytes, good, old, cell)['reachableValuesVerified'])
        for bad in (old_bytes, good.replace(b'INVENTED\0', b'ALTERED!\0'),
                    good.replace(b'crx ', b'crz ', 1)):
            with self.assertRaises(audit.Refused):
                audit.compare_output(old_bytes, bad, old, cell)

    def test_zero_generated_storage_has_distinct_measured_relationship(self):
        before = fixture()
        after = before.replace(b'2002:03:04 05:06:07\0', b'2007:08:09 10:11:12\0')[:-2] + b'\0\0'
        result = audit.compare_output(before, after, audit.inspect(before),
                                      {'id': 'invented-control', 'assignment': 'changed'})
        self.assertEqual(result['storageRelationship'], 'equal-length-zero-generated-storage')

    def test_evidence_path_traversal_and_hash_substitution_refuse(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2] / '.local') as directory:
            root = Path(directory).resolve()
            (root / 'file').write_bytes(b'abc')
            for item in ({'path': '../outside', 'size': 3, 'sha256': audit.digest(b'abc')},
                         {'path': 'file', 'size': 3, 'sha256': audit.digest(b'xyz')},
                         {'path': '/outside', 'size': 3, 'sha256': audit.digest(b'abc')}):
                with self.assertRaises(audit.Refused):
                    audit.file_bytes(root, item)


if __name__ == '__main__':
    unittest.main()
