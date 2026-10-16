"""Authored-only Windows telemetry qualification and independent retained-record QA."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator
import read_benchmark as b
import read_telemetry as t
from audit_read_telemetry import audit

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'docs/performance/read-telemetry'


class TelemetryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vector = json.loads((DATA / 'synthetic-record.v2.json').read_text())
        schema = json.loads((DATA / 'record.v2.schema.json').read_text())
        Draft202012Validator.check_schema(schema)
        cls.validator = Draft202012Validator(schema)
        (ROOT / '.local').mkdir(exist_ok=True)

    def retain(self, name, attempt, observer, cap=8192):
        attempt.update(index=0, phase='sample', correctness='not-checked', eligible=False)
        core = copy.deepcopy(self.vector['elapsedRecord'])
        core['attempts'] = [attempt]
        core['configuration']['captureBytes'] = cap
        if attempt['outcome'] == 'cancelled':
            core['status'] = 'cancelled'
        record = t.extension(core, [observer.report()], "authored-child-qualification")
        # Final authored identity is validated even without optional disk retention.
        record['elapsedRecord']['argv'] = self.last_argv
        record['elapsedRecord']['driverSha256'] = b.digest(b.__file__)
        record['elapsedRecord']['pythonExecutableSha256'] = b.digest(sys.executable)
        record['elapsedRecord']['pythonVersion'] = sys.version.split()[0]
        self.validator.validate(record)
        serialized = json.dumps(record, indent=2) + '\n'
        reloaded = json.loads(serialized)
        self.validator.validate(reloaded)
        audit(reloaded)
        retained = os.environ.get('IMAGEINFO_TELEMETRY_QA_RECORDS')
        if retained:
            destination = Path(retained)
            destination.mkdir(parents=True, exist_ok=True)
            # Fixture/oracle placeholders are inherited from the explicitly synthetic
            # example, not passing media admission/correctness evidence.
            path = destination / (name + '.private.json')
            with path.open('x', encoding='utf-8') as stream:
                stream.write(serialized)
            # Audit the serialized artifact, not only a live Python object.
            reloaded = json.loads(path.read_text())
            self.validator.validate(reloaded)
            audit(reloaded)
        return observer.report()

    def child(self, name, script, deadline=2000, cap=8192, factory=None, cancel=None):
        observer = t.Observer(10, factory)
        self.last_argv = [sys.executable, '-c', script]
        result = b.run_process(self.last_argv, str(ROOT), dict(os.environ), deadline, cap, observer, cancel)
        telemetry = self.retain(name, result[0], observer, cap)
        return result, telemetry

    def test_schema_vector_and_independent_audit(self):
        self.validator.validate(self.vector)
        self.assertEqual(audit(self.vector)['telemetryValid'], 1)

    def test_audit_rejects_counter_and_membership_contradictions(self):
        mutations = [
            lambda r: r['telemetry'][0]['samples'][0]['values'].update(physicalIoBytes=0),
            lambda r: r['telemetry'][0]['sampledMaxima'].update(workingSetBytes=999),
            lambda r: r['telemetry'][0].update(observedDescendantPids=[456]),
            lambda r: r['telemetry'][0].update(valid=False),
            lambda r: r['telemetry'][0].update(observerWallNs=0),
            lambda r: r['telemetry'][0]['samples'][0]['values'].update(peakWorkingSetBytes=1),
            lambda r: r['telemetry'][0]['samples'][0]['errors'].update(cpu='unavailable'),
            lambda r: r['telemetry'][0]['samples'][0].update(endOffsetNs=2000000),
            lambda r: r['telemetry'].clear(),
        ]
        for mutate in mutations:
            value = copy.deepcopy(self.vector)
            mutate(value)
            with self.assertRaises(ValueError):
                audit(value)

    def test_schema_rejects_bounds_units_and_unknowns(self):
        mutations = [
            lambda r: r.update(schemaVersion=1),
            lambda r: r['metrics']['readTransferBytes'].update(method='physical disk traffic'),
            lambda r: r['telemetry'][0].update(requestedIntervalMs=0),
            lambda r: r['telemetry'][0].update(maxSamples=2049),
            lambda r: r['telemetry'][0]['samples'][0]['values'].update(userCpuNs=-1),
            lambda r: r['telemetry'][0]['samples'][0]['values'].update(physicalIoBytes=0),
            lambda r: r['telemetry'][0].update(unknown=True),
        ]
        for mutate in mutations:
            value = copy.deepcopy(self.vector)
            mutate(value)
            self.assertTrue(list(self.validator.iter_errors(value)))

    def test_cancellation_with_later_source_invalidity(self):
        value = copy.deepcopy(self.vector)
        value['elapsedRecord']['status'] = 'invalid-measurement'
        value['elapsedRecord']['sourceUnchanged'] = False
        value['elapsedRecord']['configuration']['repeats'] = 2
        value['elapsedRecord']['attempts'][0].update(
            outcome='cancelled', censored=True, correctness='not-checked', eligible=False)
        self.validator.validate(value)
        audit(value)

    @unittest.skipUnless(os.name == 'nt', 'Windows counter qualification')
    def test_actual_cpu_memory_logical_io(self):
        with tempfile.TemporaryDirectory(dir=ROOT / '.local') as directory:
            path = str(Path(directory) / 'authored.bin')
            script = ("import time,os; a=bytearray(16*1024*1024); "
                      f"p={path!r}; f=open(p,'wb'); f.write(a); f.close(); "
                      "f=open(p,'rb'); f.read(); f.close(); "
                      "end=time.perf_counter()+.2\nwhile time.perf_counter()<end: pass\nprint('authored')")
            (r, stdout, _), telemetry = self.child('activity', script)
        self.assertEqual(r['exitCode'], 0)
        self.assertEqual(stdout.strip(), b'authored')
        self.assertTrue(telemetry['valid'])
        final = telemetry['samples'][-1]['values']
        self.assertGreater(final['userCpuNs'] + final['systemCpuNs'], 0)
        self.assertGreaterEqual(final['readTransferBytes'], 16 * 1024 * 1024)
        self.assertGreaterEqual(final['writeTransferBytes'], 16 * 1024 * 1024)
        self.assertGreater(telemetry['sampledMaxima']['workingSetBytes'], 8 * 1024 * 1024)
        self.assertGreaterEqual(final['peakWorkingSetBytes'], telemetry['sampledMaxima']['workingSetBytes'])
        self.assertIsNone(final['physicalIoBytes'])

    @unittest.skipUnless(os.name == 'nt', 'Windows counter qualification')
    def test_actual_short_and_nonzero_exit(self):
        for name, script, expected in (('short', 'pass', 0), ('nonzero', 'raise SystemExit(7)', 7)):
            (record, _, _), telemetry = self.child(name, script)
            self.assertEqual(record['exitCode'], expected)
            self.assertTrue(telemetry['valid'])
            self.assertTrue(telemetry['samples'][-1]['final'])

    @unittest.skipUnless(os.name == 'nt', 'Windows counter qualification')
    def test_actual_deadline_and_capture_bounds(self):
        (record, _, _), _ = self.child('timeout', 'import time; time.sleep(10)', deadline=80)
        self.assertEqual(record['outcome'], 'timeout')
        self.assertTrue(record['censored'])
        (record, stdout, _), _ = self.child('overflow', "import sys; sys.stdout.buffer.write(b'x'*1000000)", cap=64)
        self.assertEqual(record['outcome'], 'output-limit')
        self.assertLessEqual(len(stdout), 64)

    @unittest.skipUnless(os.name == 'nt', 'Windows counter qualification')
    def test_actual_cancellation_retained(self):
        cancel = threading.Event()
        cancel.set()
        (record, _, _), _ = self.child('cancelled', 'import time; time.sleep(10)', cancel=cancel)
        self.assertEqual(record['outcome'], 'cancelled')
        self.assertTrue(record['censored'])

    @unittest.skipUnless(os.name == 'nt', 'Windows counter qualification')
    def test_actual_descendant_invalidates_membership(self):
        script = ("import subprocess,sys,time; p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(.2)'],"
                  "stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(.3); p.wait()")
        (_, _, _), telemetry = self.child('descendant', script)
        self.assertFalse(telemetry['valid'])
        self.assertEqual(telemetry['membership'], 'invalid-descendants')
        self.assertTrue(telemetry['observedDescendantPids'])

    def test_actual_child_with_counter_unavailable(self):
        class Missing:
            def __init__(self, process):
                pass
            def read(self):
                raise OSError('authored counter-unavailable injection')
            def descendants(self):
                return []
        (record, _, _), telemetry = self.child('counter-unavailable', 'print(123)', factory=Missing)
        self.assertEqual(record['exitCode'], 0)
        self.assertFalse(telemetry['valid'])
        self.assertTrue(all(s['values']['userCpuNs'] is None for s in telemetry['samples']))

    def test_actual_child_with_membership_unavailable(self):
        class MissingMembership:
            def __init__(self, process):
                self.backend = t.WindowsCounters(process)
            def read(self):
                return self.backend.read()
            def descendants(self):
                raise OSError('authored membership-unavailable injection')
        if os.name != 'nt':
            self.skipTest('Windows counter qualification')
        (_, _, _), telemetry = self.child('membership-unavailable', 'print(123)', factory=MissingMembership)
        self.assertFalse(telemetry['valid'])
        self.assertEqual(telemetry['membership'], 'unavailable')

    def test_launch_error_and_unsupported_setup_retained(self):
        observer = t.Observer()
        self.last_argv = [str(ROOT / 'missing-telemetry-child')]
        r, _, _ = b.run_process(self.last_argv, str(ROOT), {}, 100, 64, observer)
        self.retain('launch-error', r, observer, 64)
        self.assertEqual(r['outcome'], 'launch-error')
        self.assertFalse(observer.report()['valid'])
        def unavailable(process):
            raise OSError('authored unsupported counter setup')
        (_, _, _), telemetry = self.child('setup-unavailable', 'pass', factory=unavailable)
        self.assertFalse(telemetry['valid'])
        self.assertEqual(telemetry['samples'], [])

    @unittest.skipUnless(os.name == 'nt', 'Windows counter qualification')
    def test_sample_limit_censors_direct_child(self):
        # Force a tiny effective bound to exercise the production stopping branch.
        # Restore declared retained-record bound before schema/audit validation.
        observer = t.Observer(1)
        self.last_argv = [sys.executable, '-c', 'import time; time.sleep(10)']
        with patch.object(t, 'MAX_SAMPLES', 3):
            r, _, _ = b.run_process(self.last_argv, str(ROOT), dict(os.environ), 2000, 64, observer)
        telemetry = self.retain('sample-limit', r, observer, 64)
        self.assertEqual(r['outcome'], 'telemetry-limit')
        self.assertFalse(telemetry['valid'])
        self.assertTrue(r['censored'])
        self.assertEqual(len(telemetry['samples']), 3)


if __name__ == '__main__':
    unittest.main()
