"""Finite ledger/model refusal checks. No worker, VM or target mutator is run."""
import argparse
import copy
import hashlib
import itertools
import json
from pathlib import Path
import re
import tempfile

from admission import (CONFIGURATION, CRITERIA, REQUIRED, SECONDARY_CONFIGURATION, STATUSES, Refused,
                       hypothetical_conjunction, inspect, load, members, validate)
from build_ledger import ROOT, build


def qualify():
    ledger_path = ROOT/'docs/write-safety/profile-admission-ledger.json'
    ledger = load(ledger_path)
    assert ledger == build(), 'ledger generator/evidence bindings stale'
    cases = []

    def checked(name, action):
        action()
        cases.append({'name': name, 'passed': True})

    def refuses(action):
        try:
            action()
        except (Refused, FileNotFoundError):
            return
        raise AssertionError('expected refusal')

    def actual(item):
        result = inspect(item, CONFIGURATION, ROOT)
        assert result['outcome'] == 'refused-before-target-effects'
        assert result['targetEffects'] == 0
        assert len(result['blockingCells']) == len(REQUIRED)
        assert {cell['cell'] for cell in result['blockingCells']} == set(REQUIRED)
        assert not any(result[key] for key in ('profileAdmitted', 'productionPublicationAllowed',
                                               'rawAdmissionAllowed', 'repairAllowed',
                                               'automaticRecoveryAllowed'))

    checked('actual-bound-ledger-refuses-every-target-effect', lambda: actual(ledger))
    checked('eleven-correctness-cells-without-physical-power-prerequisite', lambda: assert_required_scope(ledger))
    for status in sorted(STATUSES | {'qualified'}):
        altered = copy.deepcopy(ledger)
        altered['cells'].append({'id': 'physical-power', 'status': status,
                                 'scope': 'obsolete-physical-fixture',
                                 'finding': 'Fabricated obsolete physical qualification claim.', 'evidence': []})
        checked('obsolete-physical-power-cell-'+status+'-refuses',
                lambda: refuses(lambda: actual(altered)))
    altered = copy.deepcopy(ledger)
    altered['criteriaTrace']['WS-024']['cells'].append('physical-power')
    checked('obsolete-physical-power-criterion-reference-refuses', lambda: refuses(lambda: actual(altered)))
    altered = copy.deepcopy(ledger)
    altered['physicalPowerQualified'] = True
    checked('fabricated-physical-qualification-field-refuses', lambda: refuses(lambda: actual(altered)))
    altered = copy.deepcopy(ledger)
    altered['configuration']['hostStorageQualification'] = 'absent'
    checked('obsolete-host-hardware-qualification-field-refuses', lambda: refuses(lambda: actual(altered)))
    altered = copy.deepcopy(ledger)
    altered['combinations']['secondaryObservationConfiguration']['hostStorageQualification'] = 'qualified'
    checked('fabricated-secondary-host-hardware-qualification-field-refuses', lambda: refuses(lambda: actual(altered)))
    for identifier in REQUIRED:
        altered = copy.deepcopy(ledger)
        altered['cells'] = [c for c in altered['cells'] if c['id'] != identifier]
        checked(identifier+'-absent-refuses', lambda: refuses(lambda: actual(altered)))
        altered = copy.deepcopy(ledger)
        altered['cells'].append(copy.deepcopy(next(c for c in altered['cells'] if c['id'] == identifier)))
        checked(identifier+'-duplicate-refuses', lambda: refuses(lambda: actual(altered)))
        for status in sorted(STATUSES):
            altered = copy.deepcopy(ledger)
            next(c for c in altered['cells'] if c['id'] == identifier)['status'] = status
            checked(identifier+'-'+status+'-cannot-qualify', lambda: actual(altered))
        altered = copy.deepcopy(ledger)
        next(c for c in altered['cells'] if c['id'] == identifier)['status'] = 'qualified'
        checked(identifier+'-editable-qualified-claim-refuses', lambda: refuses(lambda: actual(altered)))

    for field in CONFIGURATION:
        requested = dict(CONFIGURATION)
        requested[field] = 'unsupported-or-different'
        checked('configuration-'+field+'-mismatch-refuses',
                lambda: refuses(lambda: inspect(ledger, requested, ROOT)))
    checked('secondary-fixture-cannot-substitute-for-primary-configuration',
            lambda: refuses(lambda: inspect(ledger, SECONDARY_CONFIGURATION, ROOT)))
    for field in SECONDARY_CONFIGURATION:
        altered = copy.deepcopy(ledger)
        altered['combinations']['secondaryObservationConfiguration'][field] = 'unsupported-or-different'
        checked('secondary-configuration-'+field+'-mismatch-refuses',
                lambda: refuses(lambda: actual(altered)))
    altered = copy.deepcopy(ledger)
    altered['combinations']['secondaryObservationConfiguration']['diskCapacityBytes'] = 134217728.0
    checked('secondary-integer-capacity-type-is-exact', lambda: refuses(lambda: actual(altered)))
    for criterion in sorted(CRITERIA):
        altered = copy.deepcopy(ledger)
        del altered['criteriaTrace'][criterion]
        checked(criterion+'-missing-trace-refuses', lambda: refuses(lambda: actual(altered)))
    altered = copy.deepcopy(ledger)
    altered['cells'][0]['evidence'][0]['sha256'] = '0' * 64
    checked('changed-evidence-refuses', lambda: refuses(lambda: actual(altered)))
    altered = copy.deepcopy(ledger)
    altered['cells'][0]['evidence'][0]['path'] = 'docs/nonexistent-admission-evidence.json'
    checked('missing-evidence-refuses', lambda: refuses(lambda: actual(altered)))
    altered = copy.deepcopy(ledger)
    altered['cells'][0]['evidence'][0]['path'] = 'docs/../AGENTS.md'
    checked('nonpublic-evidence-path-refuses', lambda: refuses(lambda: actual(altered)))
    checked('duplicate-json-member-refuses', lambda: refuses(
        lambda: json.loads('{"profile":1,"profile":2}', object_pairs_hook=members)))
    altered = copy.deepcopy(ledger)
    altered['combinations']['supportedActualProfiles'] = ['imported-json-cannot-authorize']
    checked('imported-supported-profile-claim-refuses', lambda: refuses(lambda: actual(altered)))
    altered = copy.deepcopy(ledger)
    altered['domain'] = 'hypothetical'
    checked('hypothetical-domain-cannot-enter-actual-inspector', lambda: refuses(lambda: actual(altered)))

    # The declared finite logical truth table has exactly one satisfying row.
    satisfied = 0
    for values in itertools.product((False, True), repeat=len(REQUIRED)):
        result = hypothetical_conjunction(dict(zip(REQUIRED, values)))
        assert result == all(values)
        satisfied += result
    assert satisfied == 1
    checked('hypothetical-eleven-true-premises-need-no-physical-power',
            lambda: assert_true(hypothetical_conjunction(dict.fromkeys(REQUIRED, True))))
    checked('hypothetical-obsolete-physical-premise-refuses', lambda: assert_false(
        hypothetical_conjunction({**dict.fromkeys(REQUIRED, True), 'physical-power': True})))
    checked('hypothetical-missing-key-refuses', lambda: assert_false(hypothetical_conjunction({})))
    checked('hypothetical-truthy-nonboolean-refuses', lambda: assert_false(
        hypothetical_conjunction(dict.fromkeys(REQUIRED, 1))))

    # The model does not take a target or construct a worker. A target witness
    # remains byte/name identical while all public refusal paths are evaluated.
    scratch_parent = ROOT/'.local/0051-profile-admission'
    scratch_parent.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(dir=scratch_parent))
    witness = scratch/'target.marker'
    witness.write_bytes(b'target-witness')
    before = witness.read_bytes(), witness.stat().st_mtime_ns
    actual(ledger)
    assert before == (witness.read_bytes(), witness.stat().st_mtime_ns)
    assert [p.name for p in scratch.iterdir()] == ['target.marker']
    checked('target-witness-byte-name-mtime-unchanged', lambda: None)
    for invalid in (None, [], 1, True, 'qualified'):
        checked('malformed-root-'+str(type(invalid).__name__), lambda: refuses(lambda: validate(invalid)))
    for field in ('cells', 'criteriaTrace', 'combinations', 'limitations'):
        altered = copy.deepcopy(ledger)
        altered[field] = None
        checked('malformed-'+field, lambda: refuses(lambda: actual(altered)))
    altered = copy.deepcopy(ledger)
    altered['combinations']['unknownAuthority'] = True
    checked('unknown-nested-combination-field', lambda: refuses(lambda: actual(altered)))
    checked('all-normative-criteria-traced', lambda: assert_trace(ledger))
    source_paths = sorted(Path(__file__).parent.glob('*.py'))
    return {'ticket': 51, 'observed': '2026-10-15', 'kind': 'portable-read-only-model-checks',
            'caseCount': len(cases), 'cases': cases, 'allPassed': True,
            'requiredCells': len(REQUIRED), 'WScriteria': 24, 'SAFcriteria': 16,
            'powerTestPolicy': 'VM-off-only; no physical-power or dedicated-hardware admission prerequisite',
            'hypotheticalTruthTableRows': 2 ** len(REQUIRED), 'hypotheticalSatisfyingRows': 1,
            'hypotheticalRowsAreActualEvidence': False, 'targetEffects': 0,
            'profileAdmitted': False, 'productionPublicationAllowed': False,
            'rawAdmissionAllowed': False, 'repairAllowed': False,
            'ledgerSha256': hashlib.sha256(ledger_path.read_bytes()).hexdigest(),
            'modelSourceSha256': {str(p.relative_to(ROOT)).replace('\\', '/'):
                                  hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths}}


def assert_false(value):
    assert value is False


def assert_true(value):
    assert value is True


def assert_required_scope(ledger):
    assert len(REQUIRED) == 11
    assert 'physical-power' not in REQUIRED
    assert 'hostStorageQualification' not in CONFIGURATION
    assert 'hostStorageQualification' not in SECONDARY_CONFIGURATION
    assert {cell['id'] for cell in ledger['cells']} == set(REQUIRED)
    assert all(set(criterion['cells']) <= set(REQUIRED) for criterion in ledger['criteriaTrace'].values())


def assert_trace(ledger):
    ws = set(re.findall(r'\*\*(WS-\d{3}) —', (ROOT/'docs/write-safety/README.md').read_text(encoding='utf-8')))
    saf = set(re.findall(r'\| (SAF-\d{3}) \|', (ROOT/'docs/write-safety/acceptance-scenarios.md').read_text(encoding='utf-8')))
    assert ws | saf == set(ledger['criteriaTrace']) == CRITERIA
    validate(ledger)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--public', type=Path, required=True)
    args = parser.parse_args()
    result = qualify()
    args.public.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'allPassed': True, 'caseCount': result['caseCount'],
                      'hypotheticalRows': result['hypotheticalTruthTableRows']}))
