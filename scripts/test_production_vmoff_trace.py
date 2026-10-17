"""Authored controls for #0175 trace bookkeeping; these are not guest evidence."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

import check_production_vmoff_trace as method


class TraceControls(unittest.TestCase):
    def setUp(self):
        self.ledger = method.read_json(method.LEDGER)
        temp_root = method.ROOT / '.local' / '175-method-controls'
        temp_root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=temp_root)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.ref = self.write('authored.txt', 'authored control; no actual execution')
        profile = {key: '0' * 64 if key.endswith('_sha256') else 'authored-only'
                   for key in self.ledger['profile_required_fields']}
        profile.update(guest_filesystem='NTFS', guest_volume_kind='local', method_ledger_sha256=method.sha256(method.LEDGER),
                       host_cache_survives_vmoff=True, freeze_before_first_cell=True,
                       physical_power_claim=False)
        self.trace = dict(schema='imageinfo-0175-trace-v1', method_sha256=method.sha256(method.LEDGER),
                          profile=self.write('profile.json', json.dumps(profile)),
                          production_profile_admitted=False, raw_admitted=False,
                          cells=[dict(id=c['id'], checkpoint=c['checkpoint'], status='prepared', verdict='not-run')
                                 for c in self.ledger['cells']],
                          nr_trace=[dict(id=r['id'], status='prepared', controls=r['controls'])
                                    for r in self.ledger['nr_trace']])

    def write(self, name, content):
        path = self.root / name
        path.write_text(content, encoding='utf-8')
        return dict(path=name, sha256=method.sha256(path))

    def check(self, value):
        return method.check_trace(value, self.ledger, self.root)

    def actual(self, index):
        cell = self.trace['cells'][index]
        cell.update(status='actual', verdict='consistent')
        for key in ('before', 'after', 'classification', 'independent_audit', 'events',
                    'gate_confirmation', 'fault_confirmation', 'guest_restart_confirmation'):
            cell[key] = self.ref
        cell['assertions'] = {key: dict(result='holds', evidence=self.ref)
                              for key in self.ledger['assertions_required']}
        return cell

    def test_diagnostic_sync_or_unretained_checkpoint_transport_refuses(self):
        for key, value in (('guest_log', 'sync-all'), ('checkpoint', 'guest-file-only'),
                           ('protocol_flush_schedule', 'extra-diagnostic-flush'),
                           ('stdout', 'guest-file'), ('guest_file_capture', 'gate-source')):
            ledger = deepcopy(self.ledger)
            ledger['diagnostic_transport'][key] = value
            with self.assertRaises(ValueError):
                method.check_ledger(ledger)

    def test_vmoff_mechanism_and_limits_cannot_be_relabeled(self):
        for key, value in (('vmoff_mechanism', 'abrupt-sigkill'), ('vmoff_limits', [])):
            ledger = deepcopy(self.ledger)
            ledger[key] = value
            with self.assertRaises(ValueError):
                method.check_ledger(ledger)

    def test_prepared_denominator_never_claims_actual(self):
        method.check_ledger(self.ledger)
        self.assertEqual(self.check(self.trace), dict(actual=0, refused=0, prepared=12))

    def test_authored_reference_shape_only_is_accepted(self):
        self.actual(7)
        self.assertEqual(self.check(self.trace)['actual'], 1)
        # This tests reference bookkeeping only, deliberately not audit truth.

    def test_refusal_is_separate_from_actual(self):
        cell = self.trace['cells'][1]
        cell.update(status='refused', verdict='unsupported', reason='authored early refusal')
        for key in ('before', 'after', 'classification', 'independent_audit', 'refusal'):
            cell[key] = self.ref
        self.assertEqual(self.check(self.trace)['refused'], 1)

    def test_fixed_matrix_rejects_duplicates_missing_and_changed_checkpoint(self):
        for mutation in ('duplicate', 'missing', 'checkpoint'):
            trace = deepcopy(self.trace)
            if mutation == 'duplicate':
                trace['cells'].append(trace['cells'][0])
            elif mutation == 'missing':
                trace['cells'].pop()
            else:
                trace['cells'][3]['checkpoint'] = 'publication-api-response'
            with self.assertRaises(ValueError):
                self.check(trace)

    def test_frozen_ledger_and_admission_cannot_change(self):
        for key, value in (('method_sha256', '0' * 64), ('raw_admitted', True),
                           ('production_profile_admitted', True)):
            trace = deepcopy(self.trace)
            trace[key] = value
            with self.assertRaises(ValueError):
                self.check(trace)

    def test_missing_profile_and_cache_limit_refuse(self):
        for mutation in ('missing', 'cache', 'physical', 'unfrozen'):
            profile = method.read_json(self.root / 'profile.json')
            if mutation == 'missing':
                profile.pop('controller_model')
            elif mutation == 'cache':
                profile['host_cache_survives_vmoff'] = False
            elif mutation == 'physical':
                profile['physical_power_claim'] = True
            else:
                profile['freeze_before_first_cell'] = False
            trace = deepcopy(self.trace)
            trace['profile'] = self.write('bad-profile.json', json.dumps(profile))
            with self.assertRaises(ValueError):
                self.check(trace)

    def test_missing_gate_off_or_boot_confirmation_refuses(self):
        cell = self.actual(7)
        for key in ('gate_confirmation', 'fault_confirmation', 'guest_restart_confirmation'):
            trace = deepcopy(self.trace)
            trace['cells'][7].pop(key)
            with self.assertRaises((KeyError, ValueError)):
                self.check(trace)
        self.assertEqual(cell['checkpoint'], 'possible-publication')

    def test_changed_bytes_or_outside_reference_refuse(self):
        for ref in (dict(path='authored.txt', sha256='0' * 64),
                    dict(path='../escape', sha256='0' * 64)):
            with self.assertRaises(ValueError):
                method.evidence(self.root, ref)

    def test_counterexample_requires_predicate_and_concrete_correction(self):
        cell = self.actual(2)
        cell['assertions']['source-object-bytes-preserved']['result'] = 'contradicted'
        with self.assertRaises(ValueError):
            self.check(self.trace)
        cell.update(verdict='counterexample', contradicted_predicate='authored predicate',
                    correction_scope=self.ref)
        self.assertEqual(self.check(self.trace)['actual'], 1)
        cell.pop('correction_scope')
        with self.assertRaises(KeyError):
            self.check(self.trace)

    def test_unknown_assertion_cannot_be_consistent(self):
        cell = self.actual(0)
        cell['assertions']['properties-compared-with-original']['result'] = 'unknown'
        with self.assertRaises(ValueError):
            self.check(self.trace)
        cell['verdict'] = 'inconclusive'
        self.check(self.trace)

    def test_duplicate_json_and_nonfinite_refuse(self):
        for text in ('{"a":1,"a":2}', '{"a":NaN}'):
            path = self.root / 'bad.json'
            path.write_text(text, encoding='utf-8')
            with self.assertRaises(ValueError):
                method.read_json(path)

    def test_unknown_or_duplicate_nr_obligation_refuses(self):
        for value in (['NR-99'], ['NR-01', 'NR-01']):
            ledger = deepcopy(self.ledger)
            ledger['cells'][0]['nr'] = value
            with self.assertRaises(ValueError):
                method.check_ledger(ledger)

    def test_missing_nr_and_changed_software_mapping_refuse(self):
        for mutation in ('missing', 'mapping'):
            trace = deepcopy(self.trace)
            if mutation == 'missing':
                trace['nr_trace'].pop()
            else:
                trace['nr_trace'][0]['controls'] = []
            with self.assertRaises(ValueError):
                self.check(trace)


if __name__ == '__main__':
    unittest.main()
