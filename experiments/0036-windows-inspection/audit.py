"""Bind the 35-case read-only inspector captures without publishing private IDs."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while block := stream.read(65536):
            digest.update(block)
    return digest.hexdigest()


def run(root, binary, public):
    root = Path(root).resolve()
    binary = Path(binary).resolve()
    report = json.loads((root/'report.json').read_text())
    assert report['caseCount'] == len(report['cases']) == 35
    assert len({case['id'] for case in report['cases']}) == 35
    inventories = 0
    for case in report['cases']:
        capture = root/case['id']/'inspection'
        assert case['report'] == json.loads((capture/'stdout.jsonl').read_text())
        assert not case['report']['committed'] and not case['report']['productionPublicationAllowed']
        if case.get('inventoryUnchanged'):
            before = json.loads((capture/'inventory-before.private.json').read_text())
            after = json.loads((capture/'inventory-after.private.json').read_text())
            assert before == after
            assert not case['report']['repairAllowed'] and not case['report']['cleanupAllowed']
            inventories += 1
    assert inventories == 32
    source_root = Path(__file__).resolve().parents[2]
    sources = list((source_root/'experiments/0032-windows-publication/src').glob('*.rs'))
    sources += [source_root/name for name in ['experiments/0032-windows-publication/Cargo.toml', 'experiments/0032-windows-publication/Cargo.lock', 'experiments/0036-windows-inspection/qualify.py', 'experiments/0036-windows-inspection/audit.py', 'experiments/0034-source-oplocks/qualify.py']]
    binding = {'binarySha256': sha(binary), 'sourceHashes': {str(path.relative_to(source_root)): sha(path) for path in sources}}
    (root/'source-binding.private.json').write_text(json.dumps(binding, indent=2)+'\n', encoding='utf-8')
    manifest = {str(path.relative_to(root)): {'sha256': sha(path), 'size': path.stat().st_size}
                for path in root.rglob('*') if path.is_file() and path.name != 'capture-manifest.private.json'}
    (root/'capture-manifest.private.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    report.update({'observedOn': '2026-10-13', 'inspectionCapturesAudited': 35,
                   'unchangedInventories': inventories, 'readableArtifactsHashed': len(manifest),
                   'rootUnsafePolicyChanged': False, 'newOsApis': 0,
                   'encryptionOrReceiptKeys': False, 'osCrashRuns': 0, 'physicalPowerLossRuns': 0})
    Path(public).write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({key: report[key] for key in ['caseCount', 'inspectionCapturesAudited', 'unchangedInventories', 'readableArtifactsHashed']}))


if __name__ == '__main__':
    if not __debug__:
        raise RuntimeError('Audit assertions require Python without -O')
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['root', 'binary', 'public']:
        parser.add_argument('--'+name, required=True)
    args = parser.parse_args()
    run(args.root, args.binary, args.public)
