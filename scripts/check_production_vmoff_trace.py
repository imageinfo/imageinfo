"""Check the fixed #0175 method and private evidence references; never certify effects.

No VM, subprocess, storage operation or repair action is performed. Evidence hashes
prove the selected bytes only. Independent semantic reconciliation is separate.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / 'docs/write-safety/production-vmoff-cells.json'
CELL_IDS = ('normal', 'kill-candidate-ready', 'kill-intent-ready',
            'kill-possible-publication', 'kill-installed-ack',
            'kill-receipt-before-ack', 'kill-final-success-response',
            'vmoff-possible-publication', 'vmoff-receipt-before-ack',
            'vmoff-completed-predicate', 'kill-restart-finalize',
            'kill-partial-cleanup')
CHECKPOINTS = ('none', 'candidate-ready', 'intent-ready', 'possible-publication',
               'installed-ack', 'receipt-before-ack', 'final-success-response',
               'possible-publication', 'receipt-before-ack', 'completed-predicate',
               'finalize-receipt-created', 'cleanup-one-removed')


def require(value, reason):
    if not value:
        raise ValueError(reason)


def read_json(path):
    require(path.stat().st_size <= 2 * 1024 * 1024, 'JSON exceeds bound')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'duplicate JSON member')
            result[key] = value
        return result
    def invalid(value):
        raise ValueError('nonfinite JSON: ' + value)
    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique,
                      parse_constant=invalid)


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(65536), b''):
            digest.update(block)
    return digest.hexdigest()


def evidence(root, ref):
    require(isinstance(ref, dict) and set(ref) == {'path', 'sha256'}, 'invalid evidence reference')
    relative = Path(ref['path'])
    require(not relative.is_absolute() and '..' not in relative.parts, 'evidence path escapes root')
    path = (root / relative).resolve()
    require(path.is_relative_to(root.resolve()) and path.is_file(), 'missing/outside evidence')
    require(sha256(path) == ref['sha256'], 'evidence digest mismatch')
    return path


def check_ledger(ledger):
    require(ledger['schema'] == 'imageinfo-0175-method-v1', 'method schema')
    require(ledger['state'] == 'prepared', 'public ledger must retain prepared state')
    require(ledger['production_profile_admitted'] is False and ledger['raw_admitted'] is False,
            'method confers no admission')
    require(ledger['possible_publication_selection'] == 'pre-api-conservative', 'boundary selection')
    require(ledger['vmoff_mechanism'] == 'qmp-quit-graceful-emulator-exit', 'VM-off mechanism')
    require(ledger['vmoff_limits'] == ['emulator-cleanup-may-flush', 'host-caches-survive',
                                       'no-abrupt-sigkill-claim'], 'VM-off limits')
    require(ledger['diagnostic_transport'] == {
        'guest_log': 'buffered-no-device-cache-flush',
        'checkpoint': 'host-retained-owned-child-stdout-lf-prefix-http-eventFileBase64',
        'stdout': 'schema-pid-validated-owned-child-private-pipe',
        'guest_file_capture': 'guestDiagnosticBase64-separate-nondurable-not-gate-source',
        'protocol_flush_schedule': 'unchanged'}, 'diagnostic transport/flush schedule')
    cells = ledger['cells']
    require(tuple(c['id'] for c in cells) == CELL_IDS, 'fixed twelve-cell denominator/order')
    require(tuple(c['checkpoint'] for c in cells) == CHECKPOINTS, 'fixed checkpoint boundary')
    for index, cell in enumerate(cells):
        expected_kind = 'normal' if index == 0 else 'vm-off' if 7 <= index <= 9 else 'process-kill'
        expected_mode = 'finalize' if index == 10 else 'cleanup' if index == 11 else 'run'
        require(cell['kind'] == expected_kind and cell['mode'] == expected_mode, 'cell mechanism')
        require(cell['status'] == 'prepared', 'public cells cannot claim execution')
        require(cell['nr'] and len(set(cell['nr'])) == len(cell['nr'])
                and all(n in {f'NR-{i:02}' for i in range(1, 17)} for n in cell['nr']),
                'invalid/duplicate cell NR mapping')
    rows = ledger['nr_trace']
    require([r['id'] for r in rows] == [f'NR-{n:02}' for n in range(1, 17)], 'NR denominator/order')
    for row in rows:
        require(row['status'] == 'prepared' and row['obligation'], 'NR prepared obligation')
        expected = [c['id'] for c in cells if row['id'] in c['nr']]
        require(row['cells'] == expected and expected, 'NR/cell mapping mismatch')
        require(row['controls'], 'missing software complement')
        for control in row['controls']:
            ref = ledger['control_sources'][control]
            require(ref['kind'] in ('model', 'native-software'), 'distinct evidence kinds')
            path = (ROOT / ref['path']).resolve()
            require(path.is_relative_to(ROOT) and path.is_file(), 'control source missing')
            require('fn ' + ref['test'] + '(' in path.read_text(encoding='utf-8'), 'test selector missing')
    require(len(set(ledger['profile_required_fields'])) == len(ledger['profile_required_fields']),
            'duplicate profile fields')


def check_trace(trace, ledger, root):
    require(trace['schema'] == 'imageinfo-0175-trace-v1', 'trace schema')
    require(trace['method_sha256'] == sha256(LEDGER), 'trace differs from frozen ledger')
    require(trace['production_profile_admitted'] is False and trace['raw_admitted'] is False,
            'trace cannot admit profile or RAW')
    manifest = read_json(evidence(root, trace['profile']))
    for key in ledger['profile_required_fields']:
        require(key in manifest and manifest[key] not in (None, '', [], {}), 'missing exact profile: ' + key)
    require(manifest['guest_filesystem'] == 'NTFS' and manifest['guest_volume_kind'] == 'local',
            'unsupported filesystem/volume kind')
    for key, value in manifest.items():
        if key.endswith('_sha256'):
            require(isinstance(value, str) and len(value) == 64
                    and all(c in '0123456789abcdef' for c in value), 'invalid exact digest: ' + key)
    require(manifest['method_ledger_sha256'] == trace['method_sha256'], 'profile method mismatch')
    require(manifest['host_cache_survives_vmoff'] is True, 'VM-off cache limit missing')
    require(manifest['freeze_before_first_cell'] is True, 'unfrozen campaign')
    require(manifest['physical_power_claim'] is False, 'physical claim unsupported')
    require(tuple(c['id'] for c in trace['cells']) == CELL_IDS, 'missing/extra/repeated cells')
    for cell, planned in zip(trace['cells'], ledger['cells']):
        status = cell['status']
        require(status in ('prepared', 'refused', 'actual'), 'invalid evidence state')
        require(cell['checkpoint'] == planned['checkpoint'], 'changed requested checkpoint')
        if status == 'prepared':
            require(cell.get('verdict') == 'not-run', 'prepared is not a passing outcome')
            continue
        evidence(root, cell['before'])
        evidence(root, cell['after'])
        evidence(root, cell['classification'])
        evidence(root, cell['independent_audit'])
        if status == 'refused':
            require(cell['verdict'] == 'unsupported' and cell['reason'], 'refusal is not positive coverage')
            evidence(root, cell['refusal'])
            continue
        require(cell['verdict'] in ('consistent', 'counterexample', 'inconclusive'), 'actual verdict')
        evidence(root, cell['events'])
        if planned['kind'] != 'normal':
            evidence(root, cell['gate_confirmation'])
            evidence(root, cell['fault_confirmation'])
        if planned['kind'] == 'vm-off':
            evidence(root, cell['guest_restart_confirmation'])
        assertions = cell['assertions']
        require(set(assertions) == set(ledger['assertions_required']), 'missing independent effects assertion')
        for assertion in assertions.values():
            require(assertion['result'] in ('holds', 'contradicted', 'unknown'), 'assertion result')
            evidence(root, assertion['evidence'])
        results = [a['result'] for a in assertions.values()]
        if cell['verdict'] == 'consistent':
            require(all(r == 'holds' for r in results), 'consistent hides unresolved assertions')
        if 'contradicted' in results:
            require(cell['verdict'] == 'counterexample', 'contradiction hidden')
        if cell['verdict'] == 'counterexample':
            require(cell['contradicted_predicate'], 'counterexample must name predicate')
            evidence(root, cell['correction_scope'])
    require([r['id'] for r in trace['nr_trace']] == [r['id'] for r in ledger['nr_trace']], 'NR trace denominator')
    for row, planned in zip(trace['nr_trace'], ledger['nr_trace']):
        require(row['status'] in ('prepared', 'model', 'native-software', 'actual-interruption', 'refused'),
                'NR evidence kind')
        require(row['controls'] == planned['controls'], 'changed software complement')
        if row['status'] != 'prepared':
            evidence(root, row['evidence'])
        # Test-source presence and checked evidence references cannot establish NR sufficiency.
    return {'actual': sum(c['status'] == 'actual' for c in trace['cells']),
            'refused': sum(c['status'] == 'refused' for c in trace['cells']),
            'prepared': sum(c['status'] == 'prepared' for c in trace['cells'])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trace', type=Path)
    parser.add_argument('--evidence-root', type=Path)
    args = parser.parse_args()
    ledger = read_json(LEDGER)
    check_ledger(ledger)
    output = {'method': 'prepared', 'cells': 12, 'nr': 16, 'qualification': False}
    if args.trace:
        require(args.evidence_root is not None, 'trace requires evidence root')
        output['reference_integrity_only'] = check_trace(read_json(args.trace), ledger, args.evidence_root)
    print(json.dumps(output, sort_keys=True))


if __name__ == '__main__':
    main()
