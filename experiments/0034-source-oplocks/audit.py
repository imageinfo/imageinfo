"""Bind actual worker/actor captures and hash retained readable evidence."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while block := stream.read(65536):
            digest.update(block)
    return digest.hexdigest()


def run(root, binary, public):
    root = Path(root).resolve()
    binary = Path(binary).resolve()
    report = json.loads((root/'report.json').read_text(encoding='utf-8'))
    assert report['caseCount'] == len(report['cases']) == 75
    assert len({case['id'] for case in report['cases']}) == 75
    captures = 0
    observed = 0
    for case in report['cases']:
        worker = root/case['id']/'worker'
        events = [json.loads(line) for line in (worker/'stdout.jsonl').read_text(encoding='utf-8').splitlines()]
        assert all(not e['productionPublicationAllowed'] and not e['committed'] for e in events)
        if 'observed' in case:
            assert case['observed'] == next(e for e in events if e.get('outcome') == 'held-source-observed')
            assert case['observed']['identityUnchanged'] and case['observed']['contentUnchanged']
            observed += 1
        if 'actorResult' in case:
            actor = root/case['id']/'actor'
            assert case['actorResult'] == json.loads((actor/'stdout.jsonl').read_text(encoding='utf-8').splitlines()[-1])
            assert json.loads((actor/'exit.json').read_text())['exitCode'] == 0
        if case.get('guardRefused'):
            assert events[0]['outcome'] == 'source-guard-refused' and events[0]['winError'] == 300
        captures += 1
    assert observed == 63
    source_root = HERE.parents[1]
    sources = sorted(HERE.glob('src/*.rs')) + [HERE/name for name in ['Cargo.toml', 'Cargo.lock', 'actor.py', 'qualify.py', 'audit.py']]
    sources += [HERE.parent/'0032-windows-publication'/'src/native.rs', HERE.parent/'0033-owner-rights'/'actor.py']
    binding = {'binarySha256': sha(binary), 'sourceHashes': {str(path.relative_to(source_root)): sha(path) for path in sources}}
    (root/'source-binding.private.json').write_text(json.dumps(binding, indent=2)+'\n', encoding='utf-8')
    manifest = {}
    denied = []
    streams = 0
    for path in root.rglob('*'):
        if path.is_file() and path.name != 'capture-manifest.private.json':
            name = str(path.relative_to(root))
            try:
                manifest[name] = {'sha256': sha(path), 'size': path.stat().st_size}
            except PermissionError:
                assert path.suffix == '.marker'
                denied.append(name)
            if path.suffix == '.marker':
                alternate = Path(str(path)+':probe')
                try:
                    with alternate.open('rb') as stream:
                        data = stream.read(65537)
                    assert data == b'foreign-marker'
                    manifest[name+':probe'] = {'sha256': hashlib.sha256(data).hexdigest(), 'size': len(data)}
                    streams += 1
                except (FileNotFoundError, PermissionError):
                    pass
    (root/'capture-manifest.private.json').write_text(json.dumps({'readable': manifest, 'inaccessibleMarkersRetainedWithoutRepair': denied}, indent=2)+'\n', encoding='utf-8')
    report.update({'observedOn': '2026-10-13', 'workerCapturesAudited': captures,
                   'heldObservationsAudited': observed, 'readableArtifactsHashed': len(manifest),
                   'inaccessibleMarkerPathsRetained': len(denied), 'alternateStreamPathsHashed': streams,
                   'completeSourcePropertyGuardQualified': False, 'restartCustodyQualified': False,
                   'osCrashRuns': 0, 'physicalPowerLossRuns': 0,
                   'rootProductionUnsafePolicyChanged': False, 'enabledProfiles': 0})
    Path(public).write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({key: report[key] for key in ['caseCount', 'workerCapturesAudited', 'heldObservationsAudited', 'readableArtifactsHashed', 'inaccessibleMarkerPathsRetained', 'alternateStreamPathsHashed']}))


if __name__ == '__main__':
    if not __debug__:
        raise RuntimeError('Audit assertions require Python without -O')
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['root', 'binary', 'public']:
        parser.add_argument('--'+name, required=True)
    args = parser.parse_args()
    run(args.root, args.binary, args.public)
