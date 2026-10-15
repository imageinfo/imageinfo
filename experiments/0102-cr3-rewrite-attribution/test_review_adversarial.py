"""Independent authored challenges of the attribution implementation, no media."""
import struct
import unittest
from copy import deepcopy

import attribute_private as subject
import independent_audit as audit
from test_independent_audit import atom, classic


def complete_file(offset_delta=0, data_reference=1, pointer_to_header=False):
    cmt = atom(b'CMT2', classic(nonzero_gap=True))

    def movie(media_start):
        ctbo = atom(b'CTBO', struct.pack('>IIQQ', 1, 3, media_start, 16))
        entry = struct.pack('>I4s6sH', 16, b'CRAW', b'\0' * 6, data_reference)
        description = atom(b'stsd', struct.pack('>II', 0, 1) + entry)
        sizes = atom(b'stsz', struct.pack('>III', 0, 8, 1))
        mapping = atom(b'stsc', struct.pack('>IIIII', 0, 1, 1, 1, 1))
        offset = media_start if pointer_to_header else media_start + 8
        offsets = atom(b'stco', struct.pack('>III', 0, 1, offset))
        local = atom(b'dinf', atom(b'dref', struct.pack('>III4sI', 0, 1, 12, b'url ', 1)))
        track = atom(b'trak', atom(b'mdia', atom(b'minf', local + atom(b'stbl', description + sizes + mapping + offsets))))
        return atom(b'moov', atom(b'uuid', subject.CANON + cmt + ctbo) + track)

    prefix = atom(b'ftyp', b'authored')
    gap = atom(b'free', b'x' * offset_delta) if offset_delta else b''
    media_start = len(prefix) + len(movie(0)) + len(gap)
    return prefix + movie(media_start) + gap + atom(b'mdat', b'01234567')


class AttributionReviewControls(unittest.TestCase):
    def test_real_local_data_reference_index_is_required(self):
        valid = complete_file()
        self.assertTrue(subject.analyze(valid, valid)['pointers']['samples'][0]['sameBoundedSample'])
        invalid = complete_file(data_reference=2)
        with self.assertRaises(subject.Refused):
            subject.analyze(invalid, invalid)

    def test_same_sample_relocation_is_distinct_from_changed_bytes(self):
        before, moved = complete_file(), complete_file(offset_delta=11)
        report = subject.analyze(before, moved)
        sample = report['pointers']['samples'][0]
        self.assertTrue(sample['sameBoundedSample'])
        self.assertNotEqual(sample['source']['offset'], sample['candidate']['offset'])
        self.assertTrue(report['pointers']['ctbo'][0]['sameResolvedTarget'])
        damaged = bytearray(moved)
        damaged[-1] ^= 1
        self.assertFalse(subject.analyze(before, damaged)['pointers']['samples'][0]['sameBoundedSample'])

    def test_sample_pointer_to_box_header_refuses(self):
        invalid = complete_file(pointer_to_header=True)
        with self.assertRaises(subject.Refused):
            subject.analyze(invalid, invalid)

    def test_opaque_stored_value_change_is_not_hidden(self):
        before = complete_file()
        inventory = subject.inspect(before)
        allocation = next(row for row in inventory['cmts']['CMT2']['allocations'].values()
                          if row['key'][2] == 0x9004)
        changed = bytearray(before)
        changed[allocation['offset']] ^= 1
        row = next(row for row in subject.analyze(before, changed)['allocations']
                   if row['key'][2] == 0x9004)
        self.assertFalse(row['bytesEqual'])
        self.assertFalse(row['selectedDate'])

    def test_nonzero_gap_and_complete_partition_are_preserved_as_facts(self):
        data = complete_file()
        report = subject.analyze(data, data)
        self.assertTrue(any(gap['nonzeroBytes'] for gap in report['sourceGaps']))
        partition = report['sourceInventory']['partition']
        position = 0
        for row in partition:
            self.assertEqual(row['start'], position)
            self.assertTrue(row['roles'])
            position = row['end']
        self.assertEqual(position, len(data))
        self.assertFalse(report['productionMutationAllowed'])
        self.assertFalse(report['formatAdmissionAttempted'])

    def test_unknown_in_bounds_ctbo_target_remains_unresolved(self):
        data = bytearray(complete_file())
        table = next(box for box in subject.inspect(data)['boxes'] if box['kind'] == 'CTBO')
        struct.pack_into('>QQ', data, table['body'] + 8, 1, 1)
        row = subject.analyze(data, data)['pointers']['ctbo'][0]
        self.assertEqual(row['source']['relationship'], 'unknown-target')
        self.assertFalse(row['sameResolvedTarget'])

    def test_independent_witness_rejects_tampered_report_claims(self):
        data = complete_file()
        witness = audit.inspect(data)
        report = subject.analyze(data, data)
        audit.verify_attribution(report, data, data, witness, witness)
        alterations = [
            lambda r: r['allocations'][0].update(bytesEqual=False),
            lambda r: r['allocations'][0].update(sourceSha256='0' * 64),
            lambda r: r['sourceGaps'][0].update(nonzeroBytes=999),
            lambda r: r['pointers']['samples'][0]['source'].update(offset=0),
            lambda r: r['pointers']['ctbo'][0]['source'].update(relationship='unknown-target'),
            lambda r: r['sourceInventory']['partition'].pop(0),
        ]
        for alter in alterations:
            changed = deepcopy(report)
            alter(changed)
            with self.assertRaises(audit.Refused):
                audit.verify_attribution(changed, data, data, witness, witness)


if __name__ == '__main__':
    unittest.main()
