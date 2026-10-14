"""Reconcile external-history native captures; publish bounded marker facts only."""
import argparse
import hashlib
import json
from pathlib import Path

from restart_qualify import flags
from custody_qualify import source_binding


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while block := stream.read(65536):
            digest.update(block)
    return digest.hexdigest()


def run(root, binary, public):
    root = Path(root).resolve()
    binary = Path(binary).resolve()
    report = json.loads((root/'report.private.json').read_text(encoding='utf-8'))
    original_binding = json.loads((root/'source-binding.private.json').read_text(encoding='utf-8'))
    assert source_binding(binary) == original_binding
    assert report['caseCount'] == len(report['cases']) == len({c['id'] for c in report['cases']})
    cases = []
    captures = 0
    unchanged = 0
    for case in report['cases']:
        folder = root/case['id']
        snapshots = json.loads((folder/'inventories.private.json').read_text(encoding='utf-8'))
        assert snapshots['custodyBeforeInspect'] == snapshots['custodyAfterInspect']
        assert all(snapshots['transactionBefore']['source.marker'] == snapshots[key]['source.marker']
                   for key in ['transactionAfter', 'afterOwnedAction'])
        if not case['publicationReleased']:
            assert snapshots['transactionBefore'] == snapshots['transactionAfter']
        history = case['supervisorHistory']
        assert history[:2] == ['original-blocked-before-publication', 'captured-snapshot-save-complete']
        if case['publicationReleased']:
            assert history.index('release-fence-snapshot-save-complete') < history.index('original-publication-continuation-sent')
            assert 'original-process-exit-confirmed-without-publication-release' not in history
        elif case['branch'] == 'stopped':
            assert history.index('original-process-exit-confirmed-without-publication-release') < history.index('stop-attestation-snapshot-save-complete')
        calls = []
        # Actual child captures independently bind the reported custody calls.
        for capture in sorted(folder.iterdir()):
            if not capture.is_dir() or capture.name not in ['inspect', 'save-1', 'save-2', 'save-3', 'save-4', 'save-stale', 'save-invalid', 'replacement-save']:
                continue
            events = [json.loads(line) for line in (capture/'stdout.jsonl').read_text(encoding='utf-8').splitlines()]
            flags(events)
            terminal = next((e for e in reversed(events) if 'outcome' in e), None)
            code = json.loads((capture/'exit.json').read_text(encoding='utf-8'))['exitCode']
            matching = [call for call in case['calls'] if call['terminal'] == terminal and call['exitCode'] == code]
            assert matching
            if terminal:
                assert not terminal['callerAuthorityAuthenticated'] and not terminal['custodyFreshnessProven']
                assert terminal['transactionMutations'] == 0 and terminal['rootRetained']
            captures += 1
            calls.append({'operation': capture.name, 'exitCode': code,
                          'outcome': terminal['outcome'] if terminal else None,
                          'custodyState': terminal.get('custodyState') if terminal else None,
                          'diagnostic': terminal.get('diagnostic') if terminal else None,
                          'contextCandidatePresent': bool((terminal or {}).get('callerContextCandidate')),
                          'actors': matching[0]['actors'],
                          'barriers': matching[0]['barriers']})
        live = [json.loads(line) for line in (folder/'live/stdout.jsonl').read_text(encoding='utf-8').splitlines()]
        flags(live)
        assert any(e.get('barrier') == 'before-namespace-call' for e in live)
        live_barriers = [e['barrier'] for e in live if 'barrier' in e]
        controls = json.loads((folder/'live/controls.json').read_text(encoding='utf-8'))
        assert controls == ['continue'] * (len(live_barriers)-1)
        assert (len(controls) > live_barriers.index('before-namespace-call')) == case['publicationReleased']
        assert json.loads((folder/'live/exit.json').read_text(encoding='utf-8'))['exitCode'] != 0
        safe = {key: case[key] for key in ['id', 'branch', 'change', 'malformed', 'stop', 'stopAt',
            'lateExtraAt', 'heldActor', 'publicationReleased', 'sourceRetained', 'custodyInspectUnchanged',
            'candidateStage', 'remainingCustodyLeaves', 'transactionLeaves', 'supervisorHistory']}
        safe['calls'] = calls
        safe['ownedActionOutcome'] = case['ownedAction']['outcome'] if case['ownedAction'] else None
        safe['transactionUnchangedBeforeCallerAction'] = snapshots['transactionBefore'] == snapshots['transactionAfter']
        cases.append(safe)
        unchanged += int(safe['transactionUnchangedBeforeCallerAction'])
    manifest = {}
    inaccessible = []
    for path in root.rglob('*'):
        if not path.is_file() or path.name == 'artifact-manifest.private.json':
            continue
        try:
            manifest[str(path.relative_to(root))] = {'sha256': sha(path), 'size': path.stat().st_size}
        except PermissionError:
            inaccessible.append(str(path.relative_to(root)))
        stream = Path(str(path)+':probe')
        try:
            manifest[str(path.relative_to(root))+':probe'] = {'sha256': sha(stream), 'size': stream.stat().st_size}
        except FileNotFoundError:
            pass
        except PermissionError:
            inaccessible.append(str(path.relative_to(root))+':probe')
    (root/'artifact-manifest.private.json').write_text(json.dumps({
        'readablePaths': manifest, 'inaccessibleRetainedWithoutRepair': inaccessible}, indent=2), encoding='utf-8')
    result = {'schemaVersion': 1, 'observedOn': '2026-10-14', 'data': 'authored marker bytes only',
              'caseCount': len(cases), 'cases': cases, 'custodyCapturesAudited': captures,
              'unchangedTransactionInventoriesBeforeCallerAction': unchanged,
              'unchangedCustodyInspectionInventories': len(cases),
              'readableArtifactPathsHashed': len(manifest), 'inaccessiblePathsRetained': len(inaccessible),
              'enabledProfiles': 0, 'physicalPowerLossRuns': 0,
              'callerAuthorityAuthenticated': False, 'custodyFreshnessProven': False,
              'committed': False, 'namespaceAcknowledged': False, 'repairAllowed': False,
              'productionPublicationAllowed': False,
              'limits': 'Trusted supervisor history representation and finite native ordering tests. Same-byte snapshot replacement is accepted; missing terminal snapshots never establish nonrelease. No authentication, antirollback, durable commit, automatic repair or storage-profile admission.'}
    Path(public).write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({key: result[key] for key in ['caseCount', 'custodyCapturesAudited',
        'unchangedTransactionInventoriesBeforeCallerAction', 'readableArtifactPathsHashed', 'inaccessiblePathsRetained']}))


if __name__ == '__main__':
    if not __debug__:
        raise RuntimeError('Audit requires assertions')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    parser.add_argument('--binary', required=True)
    parser.add_argument('--public', required=True)
    args = parser.parse_args()
    run(args.root, args.binary, args.public)
