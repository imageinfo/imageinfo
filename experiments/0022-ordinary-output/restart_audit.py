"""Reconcile restart captures and emit only bounded, sanitized marker observations."""
import argparse
import hashlib
import json
from pathlib import Path

from restart_qualify import FLAGS, flags


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        while block := stream.read(65536):
            h.update(block)
    return h.hexdigest()


def run(root, binary, public):
    root = Path(root).resolve()
    binary = Path(binary).resolve()
    report = json.loads((root/'report.private.json').read_text(encoding='utf-8'))
    assert report['caseCount'] == len(report['cases']) == len({case['id'] for case in report['cases']})
    cases = []
    unchanged = 0
    captures = 0
    for case in report['cases']:
        folder = root/case['id']
        events = [json.loads(line) for line in (folder/'restart/stdout.jsonl').read_text(encoding='utf-8').splitlines()]
        flags(events)
        terminal = next((event for event in reversed(events) if 'outcome' in event), None)
        code = json.loads((folder/'restart/exit.json').read_text(encoding='utf-8'))['exitCode']
        assert code == case['exitCode'] and terminal == case['terminal']
        live = [json.loads(line) for line in (folder/'live/stdout.jsonl').read_text(encoding='utf-8').splitlines()]
        flags(live)
        assert live[-1]['barrier'] == case['liveStop']
        assert any('callerContext' in event for event in live)
        assert json.loads((folder/'live/exit.json').read_text(encoding='utf-8'))['exitCode'] != 0
        snapshot = json.loads((folder/'inventories.private.json').read_text(encoding='utf-8'))
        assert case['unchanged'] == (snapshot['before'] == snapshot['after'])
        assert snapshot['before']['source.marker'] == snapshot['after']['source.marker'] == snapshot['afterReaderRelease']['source.marker']
        transaction = folder/'transaction.marker'
        assert (transaction/'source.marker').exists()
        assert sorted(path.name for path in transaction.iterdir()) == case['remainingDirectoryEntries']
        if case['outputRetained']:
            assert snapshot['before']['output.marker'] == snapshot['after']['output.marker'] == snapshot['afterReaderRelease']['output.marker']
        if case['change'] or case.get('preexisting'):
            assert case['unchanged'] and (case['outcome'] == 'restart-refused-before-effects' or code == 5)
        if case.get('lateExtraAt'):
            assert case['outcome'] == 'restart-partial-or-uncertain'
            assert (transaction/'foreign.marker').read_bytes() == b'foreign-after-record'
            assert (transaction/'observation.record').exists()
        captures += 1
        unchanged += int(case['unchanged'])
        safe = {key: case[key] for key in ['id', 'liveMode', 'liveStop', 'change', 'stop', 'stopPhase',
                                          'foreignReinsertion', 'readerDeferral', 'sourceRetained',
                                          'outputRetained', 'unchanged', 'remainingLeaves', 'exitCode', 'outcome', 'actors', 'barriers']}
        cases.append(safe)
        for key in ['preexisting', 'lateExtraAt', 'remainingDirectoryEntries']:
            safe[key] = case.get(key)
    source_root = Path(__file__).resolve().parents[2]
    source_paths = list((source_root/'experiments/0032-windows-publication/src').glob('*.rs'))
    source_paths += [source_root/name for name in [
        'experiments/0032-windows-publication/Cargo.toml',
        'experiments/0032-windows-publication/Cargo.lock',
        'experiments/0038-staging-cleanup/src/staging.rs',
        'experiments/0038-staging-cleanup/src/disposition.rs',
        'experiments/0033-owner-rights/actor.py',
        'experiments/0034-source-oplocks/actor.py',
        'experiments/0034-source-oplocks/qualify.py',
        'experiments/0022-ordinary-output/qualify.py',
        'experiments/0022-ordinary-output/restart_qualify.py',
        'experiments/0022-ordinary-output/restart_audit.py']]
    (root/'source-binding.private.json').write_text(json.dumps({
        'binarySha256': sha(binary),
        'sources': {str(path.relative_to(source_root)): sha(path) for path in source_paths}}, indent=2), encoding='utf-8')
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
              'caseCount': len(cases), 'cases': cases, 'workerCapturesAudited': captures,
              'inventorySnapshotsAudited': captures, 'unchangedInventories': unchanged,
              'readableArtifactPathsHashed': len(manifest), 'inaccessiblePathsRetained': len(inaccessible),
              'enabledProfiles': 0, 'physicalPowerLossRuns': 0,
              'callerAuthority': 'context captured externally from the interrupted live caller channel'}
    result.update({key: False for key in FLAGS})
    Path(public).write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({key: result[key] for key in ['caseCount', 'workerCapturesAudited',
                                                'inventorySnapshotsAudited', 'unchangedInventories',
                                                'readableArtifactPathsHashed', 'inaccessiblePathsRetained']}))


if __name__ == '__main__':
    if not __debug__:
        raise RuntimeError('Audit requires assertions')
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['root', 'binary', 'public']:
        parser.add_argument('--'+name, required=True)
    args = parser.parse_args()
    run(args.root, args.binary, args.public)
