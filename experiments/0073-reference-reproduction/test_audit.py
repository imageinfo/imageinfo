"""Authored controls only; no camera captures or derived outcomes."""
import unittest
import hashlib
from pathlib import Path
import tempfile

from audit import Refused, compare_capture, strict_json, verify_descriptor, json_safe


class CaptureAuditTests(unittest.TestCase):
    def test_descriptor_rehashed(self):
        # Keep authored temporary evidence under the declared workspace root.
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as directory:
            path = Path(directory) / 'authored.bin'
            path.write_bytes(b'authored')
            descriptor = {'path': str(path), 'byteLength': '8',
                          'sha256': hashlib.sha256(b'authored').hexdigest()}
            self.assertEqual(verify_descriptor(descriptor), path)
            path.write_bytes(b'changed!')
            with self.assertRaises(Refused):
                verify_descriptor(descriptor)

    def test_object_order_is_irrelevant(self):
        self.assertTrue(compare_capture(b'{"a":1,"b":2}', b'{"b":2,"a":1}', 'json')
                        ['equalAfterDeclaredExclusions'])

    def test_array_order_is_preserved(self):
        self.assertFalse(compare_capture(b'[1,2]', b'[2,1]', 'json')
                         ['equalAfterDeclaredExclusions'])

    def test_primitive_types_are_preserved(self):
        for other in (b'true', b'"1"', b'null'):
            self.assertFalse(compare_capture(b'1', other, 'json')['equalAfterDeclaredExclusions'])

    def test_duplicate_members_refused(self):
        with self.assertRaises(Refused):
            strict_json(b'{"x":1,"x":2}')

    def test_nonfinite_refused(self):
        for value in (b'NaN', b'Infinity', b'-Infinity'):
            with self.assertRaises(Refused):
                strict_json(value)

    def test_decimal_precision_is_exact(self):
        result = compare_capture(b'9007199254740992.0', b'9007199254740993.0', 'json')
        self.assertFalse(result['equalAfterDeclaredExclusions'])
        evidence = json_safe(result)['differences'][0]
        self.assertEqual(evidence['left'], {'kind': 'exact-json-decimal', 'text': '9007199254740992.0'})
        self.assertEqual(evidence['right'], {'kind': 'exact-json-decimal', 'text': '9007199254740993.0'})

    def test_decimal_exponent_does_not_overflow(self):
        self.assertFalse(compare_capture(b'1e999', b'2e999', 'json')['equalAfterDeclaredExclusions'])
        self.assertTrue(compare_capture(b'1.0', b'1.00', 'json')['equalAfterDeclaredExclusions'])

    def test_json_has_one_exact_numeric_kind(self):
        result = compare_capture(b'1', b'1.0', 'json')
        self.assertTrue(result['equalAfterDeclaredExclusions'])
        self.assertFalse(result['byteEqual'])
        self.assertFalse(compare_capture(b'true', b'1.0', 'json')['equalAfterDeclaredExclusions'])

    def test_declared_scalar_keeps_both_observations(self):
        result = compare_capture(b'{"path":"a"}', b'{"path":"b"}', 'json',
                                 [{'path': '/path', 'reason': 'Declared transport path'}])
        self.assertTrue(result['equalAfterDeclaredExclusions'])
        self.assertEqual(result['excluded'][0]['left'], 'a')
        self.assertEqual(result['excluded'][0]['right'], 'b')

    def test_other_platform_difference_is_retained(self):
        result = compare_capture(b'{"path":"a","mode":1}', b'{"path":"b","mode":2}',
                                 'json', [{'path': '/path', 'reason': 'Transport path'}])
        self.assertFalse(result['equalAfterDeclaredExclusions'])
        self.assertEqual(result['differences'][0]['path'], '/mode')

    def test_absent_exclusion_refused(self):
        with self.assertRaises(Refused):
            compare_capture(b'{"a":1}', b'{}', 'json', [{'path': '/a', 'reason': 'Missing'}])

    def test_container_and_root_exclusions_refused(self):
        for path in ('', '/a'):
            with self.assertRaises(Refused):
                compare_capture(b'{"a":[]}', b'{"a":[]}', 'json',
                                [{'path': path, 'reason': 'Too broad'}])

    def test_binary_is_exact(self):
        self.assertFalse(compare_capture(b'abc', b'abd', 'bytes')['equalAfterDeclaredExclusions'])
        with self.assertRaises(Refused):
            compare_capture(b'a', b'b', 'bytes', [{'path': '/a', 'reason': 'No'}])

    def test_escaped_pointer(self):
        result = compare_capture(b'{"a/b":{"~x":1}}', b'{"a/b":{"~x":2}}', 'json',
                                 [{'path': '/a~1b/~0x', 'reason': 'Authored control'}])
        self.assertTrue(result['equalAfterDeclaredExclusions'])

    def test_invalid_duplicate_exclusions(self):
        for exclusion in ([{'path': '/a', 'reason': ''}],
                          [{'path': '/a', 'reason': 'x'}] * 2,
                          [{'path': '/~q', 'reason': 'x'}]):
            with self.assertRaises(Refused):
                compare_capture(b'{"a":1}', b'{"a":2}', 'json', exclusion)

    def test_missing_array_member_is_visible(self):
        result = compare_capture(b'[1,2]', b'[1]', 'json')
        self.assertEqual(result['differences'][0]['kind'], 'array-length')


if __name__ == '__main__':
    unittest.main()
