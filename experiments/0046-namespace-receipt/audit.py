"""Audit native captures independently; publish marker observations without local data."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
from importlib.util import spec_from_file_location, module_from_spec

spec = spec_from_file_location('receipt_qualify', Path(__file__).with_name('qualify.py'))
qualification = module_from_spec(spec)
spec.loader.exec_module(qualification)
binding, flags, SUCCESS = qualification.binding, qualification.flags, qualification.SUCCESS


def expected_ids():
    result = {'success', 'short-record-producer', 'foreign-receipt-winner'}
    result.update(stop+'-'+phase for phase in qualification.PHASES for stop in ['cancel', 'fail', 'kill'])
    result.update('extra-'+phase for phase in ['observation-parent-flushed', 'receipt-written', 'receipt-file-flushed', 'receipt-parent-flushed', 'final-checked'])
    for role in ['source.marker', 'output.marker', 'receipt.record', 'root']:
        for action in ['write', 'delete', 'rename'] if role != 'root' else ['rename']:
            result.update(['held-'+role+'-'+action, 'inspect-held-'+role+'-'+action])
    result.update(action+'-'+phase for phase in ['observation-parent-flushed', 'receipt-written', 'receipt-file-flushed', 'receipt-parent-flushed'] for action in ['mtime', 'ads', 'link'])
    result.update(role+'-property-'+action for role in ['source.marker', 'receipt.record'] for action in ['mtime', 'readonly', 'ads', 'link', 'dacl'])
    result.update('inspect-'+change for change in ['missing', 'malformed', 'stale', 'identity', 'digest', 'prior-digest', 'unknown-authority', 'receipt-corrupt', 'receipt-replaced', 'receipt-missing', 'intent-corrupt', 'source-edit', 'output-edit', 'extra', 'mtime', 'readonly', 'ads', 'link', 'dacl'])
    result.update('inspect-late-mtime-'+role for role in ['source.marker', 'output.marker', 'receipt.record'])
    return result


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        while block := stream.read(65536):
            result.update(block)
    return result.hexdigest()


def run(root, binary, public):
    root = Path(root).resolve()
    assert read(root/'source-binding.private.json') == binding(binary)
    report = read(root/'report.private.json')
    assert report['caseCount'] == len(report['cases']) == len({c['id'] for c in report['cases']})
    assert {case['id'] for case in report['cases']} == expected_ids()
    cases = []
    captures = 0
    unchanged = 0
    success_count = 0
    for case in report['cases']:
        folder = root/case['id']
        history = case['supervisorHistory']
        assert history[:4] == ['original-blocked-before-publication',
            'captured-snapshot-save-complete', 'release-fence-snapshot-save-complete',
            'original-publication-continuation-sent']
        live = [json.loads(line) for line in (folder/'worker/stdout.jsonl').read_text(encoding='utf-8').splitlines()]
        flags(live)
        assert read(folder/'worker/exit.json')['exitCode'] == case['exitCode']
        terminal = next((event for event in reversed(live) if 'outcome' in event), None)
        assert terminal == case['terminal']
        barriers = [event['barrier'] for event in live if 'barrier' in event]
        controls = read(folder/'worker/controls.json')
        before_index = barriers.index('before-namespace-call')
        assert controls[before_index] == 'continue'
        if not case['stop']:
            assert controls == ['continue']*len(barriers)
        for save_name in ['save-captured', 'save-fence']:
            saved = [json.loads(line) for line in (folder/save_name/'stdout.jsonl').read_text(encoding='utf-8').splitlines()]
            assert saved[-1]['outcome'] == 'custody-snapshot-recorded'
            assert read(folder/save_name/'exit.json')['exitCode'] == 0
        receipt_context = read(folder/'receipt-context.private.json')
        if receipt_context:
            exports = [event['receiptContext'] for event in live if 'receiptContext' in event]
            assert exports[-1] == receipt_context
            assert receipt_context['prior']['stage'] == 'after-publication'
            assert len(receipt_context['prior']['records']) == 3
        inventories = read(folder/'inventories.private.json')
        if case['inspectAction'] == 'mtime':
            expected = copy.deepcopy(inventories['beforeInspect'])
            role = case['role']
            assert expected[role]['mtime'] != inventories['afterInspect'][role]['mtime']
            expected[role]['mtime'] = inventories['afterInspect'][role]['mtime']
            assert expected == inventories['afterInspect']
        else:
            assert inventories['beforeInspect'] == inventories['afterInspect']
        if case['inspection']:
            inspected = [json.loads(line) for line in (folder/'inspect/stdout.jsonl').read_text(encoding='utf-8').splitlines()]
            flags(inspected)
            observed = next((event for event in reversed(inspected) if 'outcome' in event), None)
            assert observed == case['inspection']['terminal']
            assert read(folder/'inspect/exit.json')['exitCode'] == case['inspection']['exitCode']
            unchanged += int(inventories['beforeInspect'] == inventories['afterInspect'])
            captures += 1
        for actor in case['actors'] + (case['inspection'] or {}).get('actors', []):
            assert actor['allowed'] == (actor['action'] not in ['write', 'delete', 'rename'])
        bad_live = case['stop'] or case['change'] or case['mode'].endswith('short-record') or case['action'] in ['mtime', 'readonly', 'ads', 'link', 'dacl']
        if not bad_live:
            assert (terminal or {}).get('outcome') == SUCCESS
        else:
            assert (terminal or {}).get('outcome') != SUCCESS
        if case['inspection'] and (case['inspectChange'] or case['change'] or case['action'] in ['mtime', 'readonly', 'ads', 'link', 'dacl'] or case['inspectAction'] == 'mtime'):
            assert (case['inspection']['terminal'] or {}).get('outcome') != SUCCESS
        success = (terminal or {}).get('outcome') == SUCCESS
        if success:
            assert all(terminal[key] for key in ['receiptWritten', 'receiptFileFlushSucceeded',
                'receiptParentFlushSucceeded', 'finalCheckPassed'])
            assert all(phase in barriers for phase in ['receipt-written', 'receipt-file-flushed',
                'receipt-parent-flushed', 'final-checked'])
            success_count += 1
        assert case['rootRetained'] and case['sourceRetained']
        safe = {key: case[key] for key in ['id', 'mode', 'phase', 'stop', 'change', 'action',
            'role', 'inspectChange', 'inspectAction', 'supervisorHistory', 'actors',
            'sourceRetained', 'rootRetained', 'inspectionUnchanged',
            'receiptContextCaptured', 'transactionLeaves']}
        safe.update({'exitCode': case['exitCode'], 'outcome': (terminal or {}).get('outcome'),
                     'diagnostic': (terminal or {}).get('diagnostic'), 'barriers': barriers,
                     'inspectionOutcome': ((case['inspection'] or {}).get('terminal') or {}).get('outcome'),
                     'legacyInspectionOutcome': case['legacyInspection']['outcome'],
                     'legacyRestartOutcome': (case['legacyRestart'] or {}).get('outcome')})
        cases.append(safe)
        captures += 1
    manifest = {}
    inaccessible = []
    for path in root.rglob('*'):
        if not path.is_file() or path.name == 'artifact-manifest.private.json':
            continue
        for candidate, suffix in [(path, ''), (Path(str(path)+':probe'), ':probe')]:
            try:
                manifest[str(path.relative_to(root))+suffix] = {'sha256': digest(candidate), 'size': candidate.stat().st_size}
            except FileNotFoundError:
                pass
            except PermissionError:
                inaccessible.append(str(path.relative_to(root))+suffix)
    (root/'artifact-manifest.private.json').write_text(json.dumps({
        'readablePaths': manifest, 'inaccessibleRetainedWithoutRepair': inaccessible}, indent=2), encoding='utf-8')
    result = {'schemaVersion': 1, 'observedOn': '2026-10-14', 'data': 'authored marker bytes only',
        'caseCount': len(cases), 'cases': cases, 'liveAndReceiptInspectionCapturesAudited': captures,
        'successfulLiveObservations': success_count, 'unchangedReceiptInspectionInventories': unchanged,
        'readableArtifactPathsHashed': len(manifest), 'inaccessiblePathsRetained': len(inaccessible),
        'enabledProfiles': 0, 'physicalPowerLossRuns': 0, 'guestInterruptionRuns': 0,
        'committed': False, 'namespaceAcknowledged': False, 'repairAllowed': False,
        'productionPublicationAllowed': False, 'callerAuthorityAuthenticated': False,
        'limits': 'Finite native Windows marker observations. Flush returns are unqualified. Trusted supervisor saved capture and release fence before publication continuation. No receipt authentication, history freshness, durable commit, production or RAW admission. Control fail and short-record producer cases are labeled injections, not native full-disk/device failures.'}
    Path(public).write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({key: result[key] for key in ['caseCount', 'successfulLiveObservations',
        'unchangedReceiptInspectionInventories', 'readableArtifactPathsHashed', 'inaccessiblePathsRetained']}))


if __name__ == '__main__':
    if not __debug__:
        raise RuntimeError('Audit requires assertions')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    parser.add_argument('--binary', required=True)
    parser.add_argument('--public', required=True)
    args = parser.parse_args()
    run(args.root, args.binary, args.public)
