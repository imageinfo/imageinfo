"""Authored-only independent batch-audit tests; no camera media or timing data."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import audit_batch_read as audit


def oracle(index=0):
    snapshot = json.loads((audit.ROOT/'docs/legacy-compatibility/native-read-json/example.v1.json').read_text(encoding='utf-8'))
    request = f'authored-{index}'
    path = f'authored-{index}.cr3'
    snapshot['id'] = request+'-snapshot-0'
    snapshot['sources'][0]['displayPath'] = path
    return {'schemaVersion': 1, 'requestId': request,
            'request': {'schemaVersion': 1, 'kind': 'request', 'requestId': request,
                        'operation': 'metadata read', 'mode': 'read', 'issues': []},
            'files': [{'schemaVersion': 1, 'kind': 'file', 'requestId': request, 'inputId': 'input-0',
                       'path': path, 'state': 'read', 'snapshot': snapshot, 'transactionId': None,
                       'effects': {'publicationMayHaveOccurred': False, 'changed': False,
                                   'cleanupPending': False, 'recoveryIds': [], 'notes': []}, 'issues': []}],
            'summary': {'schemaVersion': 1, 'kind': 'summary', 'requestId': request, 'exitStatus': 0,
                        'selectionComplete': True, 'outputComplete': True, 'interrupted': False,
                        'counts': {'discovered': 1, 'excluded': 0, 'deduplicated': 0, 'byState': {'read': 1}},
                        'artifacts': [], 'issues': []}}


def batch(size):
    oracles = [oracle(index) for index in range(size)]
    fixtures = [{'id': f'AUTHORED-{index}', 'input': f'authored-{index}.cr3'} for index in range(size)]
    value = copy.deepcopy(oracles[0])
    request = 'batch-authored'
    for row in (value, value['request'], value['summary']):
        row['requestId'] = request
    value['files'] = []
    for index, original in enumerate(oracles):
        row = copy.deepcopy(original['files'][0])
        row['requestId'] = request
        row['inputId'] = f'input-{index}'
        row['snapshot']['id'] = f'{request}-snapshot-{index}'
        value['files'].append(row)
    value['summary']['counts'] = {'discovered': size, 'excluded': 0, 'deduplicated': 0, 'byState': {'read': size}}
    return value, fixtures, audit.oracle_files(oracles)


def attempt(value, fixtures, expected, slot=(1, 1, 2, 'sample'), outcome='exited'):
    stdout = json.dumps(value).encode() if value is not None else b''
    stderr = b''
    row = {'round': slot[0], 'size': slot[1], 'index': slot[2], 'phase': slot[3], 'elapsedNs': 100,
           'outcome': outcome, 'exitCode': 0 if outcome == 'exited' else None,
           'censored': outcome in ('timeout', 'output-limit', 'consumer-error')}
    for name, data in [('stdout', stdout), ('stderr', stderr)]:
        row[name+'Bytes'] = row[name+'CapturedBytes'] = len(data)
        row[name+'Sha256'] = hashlib.sha256(data).hexdigest()
    row['files'], row['batchCorrectness'] = audit.classify(stdout, stderr, row, fixtures, expected)
    row['eligible'] = slot[3] == 'sample' and row['batchCorrectness'] == 'pass'
    return row, stdout, stderr


class IndependentAudit(unittest.TestCase):
    def scratch(self):
        parent = audit.ROOT/'.local/batch-audit-authored-tests'
        parent.mkdir(parents=True, exist_ok=True)
        return Path(tempfile.mkdtemp(dir=parent))

    def test_exact_all_sizes_and_denominators(self):
        grid = audit.schedule()
        self.assertEqual(len(grid), 144)
        self.assertEqual(sum(slot[3] == 'sample' for slot in grid), 120)
        self.assertEqual(sum(slot[1] for slot in grid), 540)
        self.assertEqual(sum(slot[1] for slot in grid if slot[3] == 'sample'), 450)
        for size in audit.SIZES:
            value, fixtures, expected = batch(size)
            row, stdout, stderr = attempt(value, fixtures, expected, (1, size, 2, 'sample'))
            result = audit.audit_attempt(row, stdout, stderr, fixtures, expected, (1, size, 2, 'sample'))
            self.assertTrue(result['eligible'])
            self.assertEqual(len(result['files']), size)

    def test_whole_envelope_cannot_hide_contract_changes(self):
        original, fixtures, expected = batch(1)
        for path, value in [(['summary', 'counts', 'discovered'], True),
                            (['schemaVersion'], True), (['summary', 'exitStatus'], False),
                            (['request', 'mode'], 'preview'), (['unexpected'], 'field'),
                            (['summary', 'issues'], [{'invented': 'issue'}])]:
            changed = copy.deepcopy(original)
            current = changed
            for key in path[:-1]:
                current = current[key]
            current[path[-1]] = value
            _, correctness = audit.classify(json.dumps(changed).encode(), b'', {'outcome': 'exited', 'exitCode': 0}, fixtures, expected)
            self.assertEqual(correctness, 'fail', path)

    def test_each_file_path_identity_value_order_and_coverage_checked(self):
        original, fixtures, expected = batch(2)
        changes = [(['files', 1, 'path'], 'wrong.cr3'),
                   (['files', 1, 'inputId'], 'input-0'),
                   (['files', 1, 'snapshot', 'id'], 'batch-authored-snapshot-0'),
                   (['files', 1, 'snapshot', 'coverage', 0, 'state'], 'complete'),
                   (['files', 1, 'effects', 'changed'], True),
                   (['files', 1, 'snapshot', 'occurrences', 0, 'values', 'raw', 'value', 'decimal'], '999')]
        for path, value in changes:
            changed = copy.deepcopy(original)
            current = changed
            for key in path[:-1]:
                current = current[key]
            current[path[-1]] = value
            _, correctness = audit.classify(json.dumps(changed).encode(), b'', {'outcome': 'exited', 'exitCode': 0}, fixtures, expected)
            self.assertEqual(correctness, 'fail', path)

    def test_failures_censors_warmups_and_false_eligibility_retained(self):
        value, fixtures, expected = batch(1)
        for outcome in ('timeout', 'output-limit', 'consumer-error', 'launch-error'):
            row, stdout, stderr = attempt(None, fixtures, expected, outcome=outcome)
            result = audit.audit_attempt(row, stdout, stderr, fixtures, expected, (1, 1, 2, 'sample'))
            self.assertFalse(result['eligible'])
            self.assertEqual(result['files'][0]['state'], 'not-observed')
        row, stdout, stderr = attempt(value, fixtures, expected, (1, 1, 0, 'warmup'))
        self.assertFalse(audit.audit_attempt(row, stdout, stderr, fixtures, expected, (1, 1, 0, 'warmup'))['eligible'])
        row['eligible'] = True
        with self.assertRaises(ValueError):
            audit.audit_attempt(row, stdout, stderr, fixtures, expected, (1, 1, 0, 'warmup'))

    def test_captures_and_schedule_cannot_be_rewritten(self):
        value, fixtures, expected = batch(1)
        row, stdout, stderr = attempt(value, fixtures, expected)
        for key, replacement in [('index', 3), ('elapsedNs', True), ('stdoutSha256', '0'*64),
                                 ('stdoutCapturedBytes', 0), ('censored', True)]:
            changed = copy.deepcopy(row)
            changed[key] = replacement
            with self.assertRaises(ValueError):
                audit.audit_attempt(changed, stdout, stderr, fixtures, expected, (1, 1, 2, 'sample'))

    def test_all_failed_and_slow_samples_keep_positions_and_windows(self):
        rows = []
        for round_index, size, index, phase in audit.schedule():
            rows.append({'round': round_index, 'size': size, 'index': index, 'phase': phase,
                         'elapsedNs': 100+index, 'outcome': 'exited', 'censored': False,
                         'batchCorrectness': 'pass', 'eligible': phase == 'sample'})
        rows[2].update(outcome='timeout', censored=True, batchCorrectness='not-checked', eligible=False)
        rows[7].update(batchCorrectness='fail', eligible=False)
        rows[11]['elapsedNs'] = 1000000000
        summary = audit.summarize(rows)
        self.assertEqual(len(summary['allAttempts']), 144)
        self.assertEqual(summary['sampleCensoredAttempts'], 1)
        size1 = summary['bySize'][0]
        self.assertEqual(size1['eligibleBatchSamples'], 28)
        self.assertEqual(size1['successConditionalBatchElapsed']['maximum'], 1000000000)
        windows = size1['rounds'][0]['attemptWindows']
        self.assertEqual([window['eligible'] for window in windows], [4, 4])
        self.assertEqual(audit.summarize(rows[:3])['unrecordedBatchOpportunities'], 141)

    def test_statistics_are_descriptive_nearest_rank_and_sample_sd(self):
        result = audit.distribution(list(range(1, 21)))
        self.assertEqual(result['median'], 10.5)
        self.assertEqual(result['p95NearestRank'], 19)
        self.assertAlmostEqual(result['sampleStandardDeviation'], 35**0.5)
        self.assertEqual(result['medianAbsoluteDeviation'], 5)
        self.assertIsNone(audit.distribution([]))
        self.assertIsNone(audit.distribution([4])['sampleStandardDeviation'])

    def test_duplicate_nonfinite_json_and_grid_coercion_refuse(self):
        for payload in ('{"value":1,"value":2}', '{"value":NaN}', '{"value":Infinity}',
                        '{"value":"\\ud800"}', '{"\\udfff":"value"}'):
            with self.assertRaises(ValueError):
                audit.decode(payload)
        self.assertEqual(audit.decode('{"value":"\\ud83e\\udd86"}'), {'value': '\U0001f986'})
        altered = copy.deepcopy(audit.ORDERS)
        altered[0][0] = True
        with self.assertRaises(ValueError):
            audit.schedule(altered)

    def test_camera_report_export_is_private_and_exclusive(self):
        root = self.scratch()
        (root/'.local').mkdir()
        with patch.object(audit, 'ROOT', root):
            public = root/'public.json'
            with self.assertRaises(ValueError):
                audit.write_private(public, {'rights': {'publishReportsAllowed': False}})
            self.assertFalse(public.exists())
            private = root/'.local/report.private.json'
            audit.write_private(private, {'authored': True})
            with self.assertRaises(FileExistsError):
                audit.write_private(private, {'overwrite': True})

    def test_grants_are_checked_without_opening_missing_media_or_oracles(self):
        root = self.scratch()

        def save(name, value):
            path = root/name
            path.write_text(json.dumps(value), encoding='utf-8', newline='\n')
            return str(path)

        grant = save('grant.json', {'originals': 'never opened for writing'})
        privacy = save('privacy.json', {'status': 'restricted', 'publicClearance': False})
        evidence = {path: audit.digest(path) for path in (grant, privacy)}
        fixtures = []
        for index in range(1, 9):
            identifier = f'FX-R5-{index:03}'
            source_sha, oracle_sha = '0'*64, '1'*64
            admitted = save(f'admitted-{index}.json', {
                'id': identifier, 'admission': 'admitted', 'revision': 2,
                'rights': {'analyze': True}, 'artifact': {'sha256': source_sha},
                'media': {'format': 'CR3', 'captureMode': 'full-raw'}})
            provenance = save(f'provenance-{index}.json', {
                'purpose': 'operational', 'revision': 2, 'review': {'state': 'approved'},
                'artifact': {'sha256': source_sha},
                'rights': {'permissions': {'store': 'allowed', 'analyze': 'allowed', 'publishReports': 'denied'}},
                'evidence': [{'id': 'EV-GRANT', 'sha256': evidence[grant]},
                             {'id': 'EV-PRIVACY', 'sha256': evidence[privacy]}]})
            correctness = save(f'correctness-{index}.json', {
                'execution': 'executed', 'verdict': 'pass', 'operation': 'read',
                'fixtures': [{'id': identifier, 'sha256': source_sha}],
                'candidate': {'stdout': {'sha256': oracle_sha}}})
            for path in (admitted, provenance, correctness):
                evidence[path] = audit.digest(path)
            fixtures.append({'id': identifier, 'input': str(root/f'MISSING-{index}.cr3'),
                             'oracle': str(root/f'MISSING-{index}.stdout'),
                             'inputSha256': source_sha, 'oracleSha256': oracle_sha,
                             'admission': admitted, 'provenance': provenance, 'correctness': correctness})
        protocol = {'taskAdmission': {'ticket': 63, 'scope': 'private-read-only-batch-analysis',
                                      'sourceMutationAllowed': False},
                    'primaryGrant': grant, 'privacyReview': privacy,
                    'fixtureSet': fixtures, 'evidenceSha256': evidence}
        self.assertEqual(audit.rights_before_data(protocol), {
            'analysisAllowed': True, 'publishReportsAllowed': False, 'publicCameraResultsExported': False})
        denied = audit.load(fixtures[0]['provenance'])
        denied['rights']['permissions']['analyze'] = 'denied'
        Path(fixtures[0]['provenance']).write_text(json.dumps(denied), encoding='utf-8', newline='\n')
        evidence[fixtures[0]['provenance']] = audit.digest(fixtures[0]['provenance'])
        with self.assertRaisesRegex(ValueError, 'analysis permission'):
            audit.rights_before_data(protocol)
        self.assertFalse(any(root.glob('MISSING*')))


if __name__ == '__main__':
    unittest.main()
