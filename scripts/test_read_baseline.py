"""Portable verifier checks with authored JSON and invented durations; no media."""
import copy
import hashlib
import json
import math
from pathlib import Path
import tempfile
import unittest

import audit_read_baseline as audit


def document():
    return {'schemaVersion': 1, 'requestId': 'authored-1',
            'request': {'requestId': 'authored-1', 'operation': 'metadata read'},
            'summary': {'requestId': 'authored-1', 'exitStatus': 0, 'selectionComplete': True,
                        'outputComplete': True, 'interrupted': False, 'artifacts': [],
                        'counts': {'discovered': 1, 'excluded': 0, 'deduplicated': 0,
                                   'byState': {'read': 1}}},
            'files': [{'requestId': 'authored-1', 'path': 'authored-input', 'state': 'read',
                       'effects': {'publicationMayHaveOccurred': False, 'changed': False,
                                   'cleanupPending': False, 'recoveryIds': [], 'notes': []},
                       'snapshot': {'id': 'authored-1-snapshot-1',
                                    'sources': [{'displayPath': 'authored-input'}],
                                    'coverage': [{'state': 'partial'}],
                                    'authoredValue': 1}}]}


def attempt(stdout, stderr=b''):
    return {'index': 3, 'phase': 'sample', 'elapsedNs': 100,
            'outcome': 'exited', 'exitCode': 0, 'censored': False,
            'correctness': 'pass', 'eligible': True,
            **{channel + suffix: value for channel, wire in [('stdout', stdout), ('stderr', stderr)]
               for suffix, value in [('Bytes', len(wire)), ('CapturedBytes', len(wire)),
                                     ('Sha256', hashlib.sha256(wire).hexdigest())]}}


class BaselineAuditTests(unittest.TestCase):
    def test_nearest_rank_and_even_median(self):
        result = audit.distribution(list(range(1, 21)))
        self.assertEqual(result['median'], 10.5)
        self.assertEqual(result['p95NearestRank'], 19)
        self.assertEqual(result['sum'], 210)
        self.assertEqual(result['medianAbsoluteDeviation'], 5)
        self.assertAlmostEqual(result['sampleStandardDeviation'], math.sqrt(35))
        self.assertAlmostEqual(result['coefficientOfVariation'], math.sqrt(35) / 10.5)

    def test_no_distribution_or_estimated_variance_without_samples(self):
        self.assertIsNone(audit.distribution([]))
        result = audit.distribution([7])
        self.assertEqual(result['p95NearestRank'], 7)
        self.assertIsNone(result['sampleStandardDeviation'])
        self.assertIsNone(result['coefficientOfVariation'])
        with self.assertRaises(ValueError):
            audit.distribution([0])

    def test_raw_oracle_validation_and_digest_rejection(self):
        value = document()
        stdout = json.dumps(value).encode()
        expected = audit.semantic_wire(audit.normalized(value))
        result = audit.audit_attempt(attempt(stdout), stdout, b'', expected, 3, 3, 1048576)
        self.assertTrue(result['eligible'])
        corrupt = attempt(stdout)
        corrupt['stdoutSha256'] = '0' * 64
        with self.assertRaises(ValueError):
            audit.audit_attempt(corrupt, stdout, b'', expected, 3, 3, 1048576)

    def test_boolean_is_not_integer_metadata(self):
        original = document()
        changed = copy.deepcopy(original)
        changed['files'][0]['snapshot']['authoredValue'] = True
        stdout = json.dumps(changed).encode()
        expected = audit.semantic_wire(audit.normalized(original))
        with self.assertRaises(ValueError):
            audit.audit_attempt(attempt(stdout), stdout, b'', expected, 3, 3, 1048576)

    def test_duplicate_nonfinite_and_cross_request_id_refuse(self):
        for wire in ['{"x":1,"x":2}', '{"x":NaN}']:
            with self.assertRaises(ValueError):
                audit.decode(wire)
        value = document()
        value['summary']['requestId'] = 'different'
        with self.assertRaises(ValueError):
            audit.normalized(value)

    def test_timeout_stays_in_ledger_and_is_ineligible(self):
        item = attempt(b'')
        item.update(outcome='timeout', exitCode=-1, censored=True,
                    correctness='not-checked', eligible=False)
        result = audit.audit_attempt(item, b'', b'', '', 3, 3, 1048576)
        self.assertEqual(result['outcome'], 'timeout')
        self.assertTrue(result['censored'])
        self.assertFalse(result['eligible'])

    def test_exclusive_output_preserves_existing_evidence(self):
        scratch = Path(__file__).resolve().parent.parent / '.local'
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch, prefix='baseline-audit-') as folder:
            path = Path(folder) / 'evidence.json'
            audit.write_result(path, {'authored': 1})
            original = path.read_bytes()
            self.assertNotIn(b'\r', original)
            with self.assertRaises(FileExistsError):
                audit.write_result(path, {'replacement': True})
            self.assertEqual(path.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
