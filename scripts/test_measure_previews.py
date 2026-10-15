"""Authored-only vectors for retained preview audit; no camera media or baseline."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import sys
import unittest
from unittest.mock import patch

import audit_previews as audit
import measure_previews as measure


class PreviewAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # A fresh checkout has no ignored .local directory yet.
        (audit.ROOT/'.local').mkdir(exist_ok=True)

    def test_aborted_collection_retains_finite_denominator(self):
        with tempfile.TemporaryDirectory(dir=audit.ROOT/'.local') as directory:
            root = Path(directory)
            fixture = root/'fixture'
            fixture.mkdir()
            resources, data = [], bytearray()
            for tag, size in zip(audit.TAGS, audit.LENGTHS):
                resource = b'x'*size
                (fixture/(tag+'.bin')).write_bytes(resource)
                resources.append({'tag': tag, 'bytes': size, 'offset': len(data),
                                  'sha256': hashlib.sha256(resource).hexdigest()})
                data.extend(resource)
            (fixture/'source.cr3').write_bytes(data)
            protocol = {'schemaVersion': 1, 'protocolRevision': 'preview-collector-v1',
                'status': 'fixed-before-collection', 'fixedUtc': '2020-01-01T00:00:00+00:00',
                'fixtureKind': 'authored-structural-no-camera-data', 'sourcePins': {},
                'sourceSha256': hashlib.sha256(data).hexdigest(), 'sourceBytes': len(data),
                'binarySha256': audit.digest(sys.executable), 'resources': resources,
                'warmups': 2, 'repeats': 10, 'timeoutMs': 1000, 'captureBytes': 1000,
                'maxBytes': 8388608, 'maxPreviewBytes': 67108864}
            path = root/'protocol.json'
            path.write_text(json.dumps(protocol), encoding='utf-8')
            with patch.object(measure.bounded, 'run_process', side_effect=OSError('authored injected start failure')):
                record = measure.collect(path, sys.executable, fixture, root/'run')
            self.assertEqual(record['status'], 'aborted')
            self.assertEqual(record['plannedAttempts'], 54)
            self.assertEqual(record['remainingAttempts'], 54)
            self.assertEqual(record['attempts'], [])
            self.assertIn('authored injected start failure', record['abortReason'])
            self.assertTrue((root/'run/record.json').is_file())

    def test_exact_schedule_denominators(self):
        cells = audit.schedule()
        self.assertEqual(len(cells), 54)
        self.assertEqual(sum(cell['phase'] == 'sample' for cell in cells), 40)
        self.assertEqual(sum(cell['phase'] == 'warmup' for cell in cells), 8)
        self.assertEqual(sum(cell['phase'] == 'control' for cell in cells), 6)
        self.assertEqual(cells, measure.schedule({'warmups': 2, 'repeats': 10}))

    def test_unexpected_non_temporary_output_is_not_hidden(self):
        with tempfile.TemporaryDirectory(dir=audit.ROOT/'.local') as directory:
            root = Path(directory)
            (root/'outputs').mkdir()
            (root/'outputs/attempt-001.bin').write_bytes(b'owned')
            rows = [{'id': 'attempt-001', 'targetAfter': {'bytes': 5}}]
            self.assertEqual(audit.output_inventory(root, rows, True), [])
            (root/'outputs/unexpected.bin').write_bytes(b'retained')
            with self.assertRaises(ValueError):
                audit.output_inventory(root, rows, True)
            self.assertEqual(audit.output_inventory(root, rows, False), [str(root/'outputs/unexpected.bin')])

    def test_process_failure_censor_and_capture_integrity(self):
        for outcome in ('exited', 'launch-error', 'timeout', 'output-limit', 'consumer-error'):
            row = {'outcome': outcome, 'elapsedNs': 100, 'exitCode': None if outcome == 'launch-error' else 0,
                   'censored': outcome in ('timeout', 'output-limit', 'consumer-error')}
            for channel in ('stdout', 'stderr'):
                row[channel+'Bytes'] = row[channel+'CapturedBytes'] = 0
                row[channel+'Sha256'] = None if outcome == 'launch-error' else hashlib.sha256(b'').hexdigest()
            audit.process_check(row, b'', b'', 100)
            changed = copy.deepcopy(row)
            changed['censored'] = not row['censored']
            with self.assertRaises(ValueError):
                audit.process_check(changed, b'', b'', 100)
            changed = copy.deepcopy(row)
            changed['stdoutSha256'] = 'unrelated'
            with self.assertRaises(ValueError):
                audit.process_check(changed, b'', b'', 100)
        for duration in (0, -1, True, 1.5):
            row['elapsedNs'] = duration
            with self.assertRaises(ValueError):
                audit.process_check(row, b'', b'', 100)

    def test_strict_json_and_contained_paths(self):
        for value in (b'{"x":1,"x":2}', b'{"x":NaN}'):
            with self.assertRaises(ValueError):
                audit.decode(value)
        with tempfile.TemporaryDirectory(dir=audit.ROOT/'.local') as directory:
            root = Path(directory)
            with self.assertRaises(ValueError):
                audit.bounded(root, '../outside')
            self.assertEqual(audit.bounded(root, 'capture'), root/'capture')

    def test_empty_and_finite_distribution(self):
        self.assertIsNone(audit.distribution([]))
        result = audit.distribution(list(range(1, 11)))
        self.assertEqual(result, {'n': 10, 'minNs': 1, 'medianNs': 5.5,
                                'p95NearestRankNs': 10, 'maxNs': 10, 'totalNs': 55})

    def test_resource_hashes_bind_order_ranges_and_padding(self):
        with tempfile.TemporaryDirectory(dir=audit.ROOT/'.local') as directory:
            root = Path(directory)
            source = bytearray(b'header')
            references, occurrences, resources = {}, [], []
            for index, (tag, length) in enumerate(zip(audit.TAGS, audit.LENGTHS)):
                payload = b'\xff\xd8' + bytes([65+index])*(length-7) + b'\xff\xd9\0\0\0'
                path = root/f'{tag}.bin'
                path.write_bytes(payload)
                references[tag] = path
                ref = f'preview-{index}'
                occurrences.append({'tag': {'name': tag}, 'origin': {'resourceRef': ref},
                    'values': {key: {'value': {'resourceRef': ref}} for key in ('raw', 'normalized')}})
                resources.append({'id': ref, 'byteLength': str(length), 'mediaType': 'image/jpeg',
                    'content': {'kind': 'source-ranges', 'ranges': [{
                        'ref': 'src-raw', 'space': 'source', 'offset': str(len(source)), 'length': str(length)}]}})
                source.extend(payload)
            path = root/'source.cr3'
            path.write_bytes(source)
            original = {'files': [{'state': 'read', 'snapshot': {'coverage': [{'state': 'partial'}],
                'occurrences': occurrences, 'resources': resources}}]}
            result = audit.resource_check(original, path, references)
            self.assertEqual([result[tag]['bytes'] for tag in audit.TAGS], list(audit.LENGTHS))
            self.assertEqual(result[audit.TAGS[0]]['sha256'], hashlib.sha256(references[audit.TAGS[0]].read_bytes()).hexdigest())
            changed = copy.deepcopy(original)
            changed['files'][0]['snapshot']['occurrences'].reverse()
            with self.assertRaises(ValueError):
                audit.resource_check(changed, path, references)
            changed = copy.deepcopy(original)
            changed['files'][0]['snapshot']['resources'][0]['content']['ranges'][0]['offset'] = '0'
            with self.assertRaises(ValueError):
                audit.resource_check(changed, path, references)
            references[audit.TAGS[0]].write_bytes(references[audit.TAGS[0]].read_bytes()[:-3])
            with self.assertRaises(ValueError):
                audit.resource_check(original, path, references)


if __name__ == '__main__':
    unittest.main()
