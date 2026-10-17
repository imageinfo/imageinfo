"""#0147 authored collector/oracle qualification; no performance baseline."""
import copy
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import audit_output_consumers as a
import output_consumers as c
import read_telemetry

ROOT = Path(__file__).resolve().parents[1]


class Consumers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Invented records exercise the auditor. These are not measured attempts.
        cls.scratch = tempfile.TemporaryDirectory(dir=ROOT / '.local', prefix='consumer-audit-authored-')
        cls.addClassCleanup(cls.scratch.cleanup)
        cls.folder = Path(cls.scratch.name)
        cls.fixture = cls.folder / 'fixture'
        cls.fixture.mkdir()
        (cls.fixture / 'authored.cr3').write_bytes(b'invented fixture binding control')
        cls.binary = cls.folder / 'invented-executable-binding.exe'
        cls.binary.write_bytes(b'invented executable binding control; never executed')
        cls.bindings = (cls.binary, cls.fixture, 'a' * 40, 'b' * 64)
        cls.record = {'revision': c.REVISION, 'warmups': 2, 'repeats': 10, 'timeoutMs': 30000,
                      'captureBytes': 262144, 'sourceUnchanged': True, 'binaryUnchanged': True,
                      'sourceRevision': cls.bindings[2], 'sourceFreezeSha256': cls.bindings[3],
                      'binaryPath': str(cls.binary.resolve()), 'fixturePath': str((cls.fixture / 'authored.cr3').resolve()),
                      'binarySha256': a.digest(cls.binary), 'fixtureSha256': a.digest(cls.fixture / 'authored.cr3'),
                      'environment': {'kind': 'invented test data; no experiment'}, 'python': 'invented',
                      'platform': 'invented', 'validationBindings': a.validation_bindings(), 'attempts': []}
        cls.record.update({field: a.digest(path) for field, path in a.TOOL_PATHS.items()})
        from audit_read_telemetry import ALL
        values = dict.fromkeys(ALL, 0)
        values['physicalIoBytes'] = None
        errors = {'physicalIoBytes': 'not instrumented'}
        telemetry = {'pid': 1, 'requestedIntervalMs': 10, 'maxSamples': 2048,
                     'membership': 'direct-only-observed', 'observedDescendantPids': [],
                     'valid': True, 'errors': [], 'stopReason': None, 'observerWallNs': 200,
                     'sampledMaxima': {'workingSetBytes': 0, 'privateCommitBytes': 0},
                     'samples': [{'beginOffsetNs': 300, 'endOffsetNs': 400, 'final': False,
                                  'values': copy.deepcopy(values), 'errors': copy.deepcopy(errors)},
                                 {'beginOffsetNs': 401_000_000, 'endOffsetNs': 401_000_100, 'final': True,
                                  'values': copy.deepcopy(values), 'errors': copy.deepcopy(errors)}]}
        for mode in ('json', 'jsonl'):
            for consumer in ('fast', 'slow', 'close'):
                for ordinal in range(1 if consumer == 'close' else 12):
                    index = len(cls.record['attempts'])
                    stdout = b'' if consumer == 'close' else a.expected(mode, 'req-1-2' if mode == 'json' else 'r147')
                    stderr = b'OUTPUT_INCOMPLETE: Could not finish output (BrokenPipe).\n' if consumer == 'close' else b''
                    attempt = {'index': index, 'mode': mode, 'consumer': consumer,
                               'phase': 'control' if consumer == 'close' else 'warmup' if ordinal < 2 else 'sample',
                               'outcome': 'exited', 'exitCode': 1 if consumer == 'close' else 0, 'censored': False,
                               'firstByteNs': None, 'firstUsableNs': None, 'deliveryCompleteNs': None,
                               'processLaunchBeginNs': 100, 'processSpawnedNs': 200,
                               'exitObservedNs': 400_000_000, 'consumerClosedNs': 50 if consumer == 'close' else None,
                               'elapsedNs': 500_000_000, 'reads': [], 'errors': [],
                               'argv': [str(cls.binary.resolve()), *(a.TOKENS[:2] + ['--output=json'] + a.TOKENS[2:]
                                       if mode == 'json' else ['session', 'read'])],
                               'cwd': str(cls.fixture.resolve()),
                               'stdinSha256': hashlib.sha256(a.stdin_expected(mode)).hexdigest(),
                               'telemetry': copy.deepcopy(telemetry),
                               'correctness': 'control' if consumer == 'close' else 'pass',
                               'eligible': consumer != 'close' and ordinal >= 2,
                               'controlOutputFailure': consumer == 'close'}
                    total = 0
                    if consumer != 'close':
                        for part, offset in enumerate(range(0, len(stdout) + 1024, 1024)):
                            block = stdout[offset:offset + 1024]
                            end = 1_000_000 + part * 5_000_000 + 100
                            attempt['reads'].append({'beginNs': end - 100, 'endNs': end, 'bytes': len(block)})
                            total += len(block)
                            if block and attempt['firstByteNs'] is None:
                                attempt['firstByteNs'] = end
                            prefix = stdout[:total]
                            if attempt['firstUsableNs'] is None and ((mode == 'json' and prefix.endswith(b'\n')) or
                                                                   (mode == 'jsonl' and prefix.count(b'\n') >= 2)):
                                attempt['firstUsableNs'] = end
                            if not block:
                                attempt['deliveryCompleteNs'] = end
                                break
                    for name, data in (('stdout', stdout), ('stderr', stderr)):
                        filename = f'{index:02d}-{mode}-{consumer}.{name}'
                        (cls.folder / filename).write_bytes(data)
                        attempt.update({name + 'File': filename, name + 'Bytes': len(data),
                                        name + 'CapturedBytes': len(data), name + 'Sha256': hashlib.sha256(data).hexdigest()})
                    cls.record['attempts'].append(attempt)

    def audit(self, record):
        return a.audit(record, self.folder, *self.bindings)

    def child(self, script, mode='json', consumer='fast', **kwargs):
        observer = read_telemetry.Observer(10)
        return c.run_process([sys.executable, '-c', script], str(ROOT), mode, consumer,
                             observer=observer, **kwargs)

    def test_independent_oracle_schema_ids_and_complements(self):
        for mode in ('json', 'jsonl'):
            data = a.expected(mode, 'req-1-2' if mode == 'json' else 'r147')
            self.assertTrue(a.validate_output(mode, data))
            self.assertLess(len(data), 262144)
            mutations = [data[:-1], data + b'\n', data.replace(b'"Canon"', b'"Other"', 1),
                         data.replace(b'"changed":false', b'"changed":true', 1)]
            if mode == 'jsonl':
                lines = data.splitlines(keepends=True)
                mutations += [b''.join(lines[::-1]), b''.join(lines[:-1]), data.replace(b'r147', b'wrong')]
            for changed in mutations:
                self.assertNotEqual(changed, data)
                with self.assertRaises((ValueError, AssertionError, KeyError)):
                    a.validate_output(mode, changed)

    def test_fast_and_slow_are_raw_bounded_reads(self):
        data = a.expected('json', 'req-1-2')
        script = "import sys;sys.path.insert(0,'scripts');import audit_output_consumers as a;sys.stdout.buffer.write(a.expected('json','req-1-2'));sys.stdout.flush()"
        for consumer in ('fast', 'slow'):
            result, stdout, stderr = self.child(script, consumer=consumer)
            self.assertEqual(result['outcome'], 'exited')
            self.assertEqual(result['exitCode'], 0)
            self.assertEqual(stdout, data)
            self.assertEqual(stderr, b'')
            self.assertTrue(a.validate_output('json', stdout))
            self.assertEqual(result['stdoutBytes'], sum(r['bytes'] for r in result['reads']))
            self.assertLessEqual(max(r['bytes'] for r in result['reads']), 1024)
            self.assertEqual(result['deliveryCompleteNs'], result['reads'][-1]['endNs'])
            self.assertLessEqual(result['firstByteNs'], result['firstUsableNs'])
            if consumer == 'slow':
                self.assertTrue(all(y['beginNs'] - x['beginNs'] >= 5_000_000
                                    for x, y in zip(result['reads'], result['reads'][1:])))

    def test_jsonl_first_usable_is_result_after_ready(self):
        data = a.expected('jsonl')
        script = "import sys;sys.path.insert(0,'scripts');import audit_output_consumers as a;sys.stdin.buffer.read();sys.stdout.buffer.write(a.expected('jsonl'));sys.stdout.flush()"
        result, stdout, _ = self.child(script, mode='jsonl', consumer='slow')
        self.assertEqual(stdout, data)
        self.assertGreater(result['firstUsableNs'], result['firstByteNs'])
        self.assertTrue(a.validate_output('jsonl', stdout))

    def test_watchdog_retains_censored_attempt(self):
        result, _, _ = self.child('import time;time.sleep(10)', timeout_ms=30)
        self.assertEqual(result['outcome'], 'timeout')
        self.assertTrue(result['censored'])
        self.assertIsNone(result['firstByteNs'])

    def test_capture_overflow_retains_prefix(self):
        result, stdout, _ = self.child("import sys;sys.stdout.buffer.write(b'x'*1000000);sys.stdout.flush()", capture=1024)
        self.assertEqual(result['outcome'], 'output-limit')
        self.assertTrue(result['censored'])
        self.assertEqual(len(stdout), 1024)
        self.assertGreater(result['stdoutBytes'], len(stdout))

    def test_close_is_before_spawn_and_no_final_frame_is_assumed(self):
        for mode in ('json', 'jsonl'):
            result, stdout, _ = self.child("import sys;sys.stdout.buffer.write(b'x'*8192);sys.stdout.flush()",
                                           mode=mode, consumer='close')
            self.assertEqual(result['outcome'], 'exited')
            self.assertNotEqual(result['exitCode'], 0)
            self.assertIsNotNone(result['consumerClosedNs'])
            self.assertEqual(result['reads'], [])
            self.assertEqual(stdout, b'')
            self.assertIsNone(result['deliveryCompleteNs'])

    def test_failed_launch_retained(self):
        observer = read_telemetry.Observer(10)
        result, stdout, _ = c.run_process([str(ROOT / '.local/no-such-147.exe')], str(ROOT),
                                          'json', 'fast', observer=observer)
        self.assertEqual(result['outcome'], 'launch-error')
        self.assertIsNone(result['exitCode'])
        self.assertTrue(result['censored'])
        self.assertEqual(stdout, b'')
        self.assertFalse(result['telemetry']['valid'])

    def test_audit_requires_complete_denominator(self):
        record = copy.deepcopy(self.record)
        record['attempts'] = []
        with self.assertRaisesRegex(ValueError, '48 measured'):
            self.audit(record)
        for field, value in (('sourceUnchanged', False), ('warmups', 0), ('captureBytes', 999999)):
            changed = copy.deepcopy(record)
            changed[field] = value
            with self.assertRaises(ValueError):
                self.audit(changed)

    def test_complete_invented_record_passes_independent_audit(self):
        self.assertEqual(self.audit(self.record), {'attempts': 50, 'completeOutputs': 48,
                                                  'eligibleSamples': 40, 'closeControls': 2, 'closeOutputFailures': 2})

    def test_audit_rejects_unbound_frozen_inputs_and_tools(self):
        for field in ('binarySha256', 'fixtureSha256', 'sourceRevision', 'sourceFreezeSha256',
                      'binaryPath', 'fixturePath', 'environment', 'validationBindings', *a.TOOL_PATHS):
            changed = copy.deepcopy(self.record)
            changed[field] = None
            with self.subTest(field=field), self.assertRaises((ValueError, KeyError, TypeError)):
                self.audit(changed)

    def test_audit_rejects_impossible_endpoints_schedule_counters_and_outcomes(self):
        mutations = [lambda x: x.update(exitObservedNs=None), lambda x: x.update(exitCode=None),
                     lambda x: x.update(outcome='not-a-real-outcome', censored=True),
                     lambda x: x.update(processSpawnedNs=500_000_001),
                     lambda x: x.update(stdinSha256='0' * 64), lambda x: x.update(argv=['other']),
                     lambda x: x.update(cwd='other'), lambda x: x.update(errors=['unknown error']),
                     lambda x: x.update(deliveryCompleteNs=None),
                     lambda x: x['telemetry'].update(requestedIntervalMs=999),
                     lambda x: x['telemetry'].update(pid=2),
                     lambda x: x['telemetry']['samples'][-1].update(beginOffsetNs=399_999_999),
                     lambda x: x['telemetry']['samples'][-1]['values'].update(readTransferBytes=None),
                     lambda x: x['reads'][1].update(beginNs=x['reads'][0]['beginNs']),
                     lambda x: x.update(outcome='timeout', censored=True),
                     lambda x: x.update(outcome='output-limit', censored=True),
                     lambda x: x.update(outcome='consumer-error', censored=True)]
        # Oracle correctness has a separate unpatched whole-output test. Avoid
        # revalidating the same invented output in every semantic mutation case.
        with patch.object(a, 'validate_output', return_value=True):
            for mutate in mutations:
                changed = copy.deepcopy(self.record)
                mutate(changed['attempts'][0])
                with self.subTest(mutation=mutate), self.assertRaises(ValueError):
                    self.audit(changed)
            for mutate in (lambda x: x.update(outcome='not-a-real-outcome', exitCode=None, censored=True),
                           lambda x: x.update(consumerClosedNs=201),
                           lambda x: x.update(controlOutputFailure=False)):
                changed = copy.deepcopy(self.record)
                mutate(changed['attempts'][24])
                with self.subTest(close=mutate), self.assertRaises(ValueError):
                    self.audit(changed)

    def test_negative_close_observations_are_retained_without_failure_claim(self):
        changed = copy.deepcopy(self.record)
        changed['attempts'][24].update(exitCode=0, controlOutputFailure=False)
        with patch.object(a, 'validate_output', return_value=True):
            result = self.audit(changed)
        self.assertEqual(result['closeOutputFailures'], 1)
        self.assertFalse(changed['attempts'][24]['eligible'])


if __name__ == '__main__':
    unittest.main()
