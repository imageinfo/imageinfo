"""Audit owned-handle cleanup captures and preserve inaccessible roots untouched."""
import argparse,hashlib,json
from pathlib import Path
def sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as source:
        while block:=source.read(65536):digest.update(block)
    return digest.hexdigest()
def run(root,binary,public):
    root=Path(root).resolve();binary=Path(binary).resolve()
    report=json.loads((root/'report.json').read_text())
    assert report['caseCount']==len(report['cases'])==27 and len({c['id'] for c in report['cases']})==27
    for case in report['cases']:
        capture=root/case['id']/'worker'
        events=[json.loads(line) for line in (capture/'stdout.jsonl').read_text().splitlines()]
        assert all(not e['committed'] and not e['productionPublicationAllowed'] for e in events)
        if case.get('terminal'):
            assert case['terminal']==events[-1] and case['rootRetained']
            if case['terminal']['publicationAttempted']:assert not case['markedRoles']
        elif case.get('workerKilled'):assert not any('outcome' in e for e in events)
    source_root=Path(__file__).resolve().parents[2]
    sources=list((source_root/'experiments/0038-staging-cleanup/src').glob('*.rs'))
    sources+=[source_root/name for name in ['experiments/0038-staging-cleanup/Cargo.toml','experiments/0038-staging-cleanup/Cargo.lock','experiments/0038-staging-cleanup/qualify.py','experiments/0038-staging-cleanup/actor.py','experiments/0038-staging-cleanup/audit.py','experiments/0032-windows-publication/src/native.rs','experiments/0034-source-oplocks/src/path.rs','experiments/0034-source-oplocks/qualify.py','experiments/0033-owner-rights/actor.py']]
    (root/'source-binding.private.json').write_text(json.dumps({'binarySha256':sha(binary),'sourceHashes':{str(p.relative_to(source_root)):sha(p) for p in sources}},indent=2)+'\n',encoding='utf-8')
    manifest={};inaccessible=[]
    for path in root.rglob('*'):
        if path.is_dir():
            try:list(path.iterdir())
            except PermissionError:inaccessible.append(str(path.relative_to(root)))
        elif path.is_file() and path.name!='capture-manifest.private.json':
            try:manifest[str(path.relative_to(root))]={'sha256':sha(path),'size':path.stat().st_size}
            except PermissionError:inaccessible.append(str(path.relative_to(root)))
    (root/'capture-manifest.private.json').write_text(json.dumps({'readable':manifest,'inaccessibleRetainedWithoutRepair':inaccessible},indent=2)+'\n',encoding='utf-8')
    report.update({'observedOn':'2026-10-13','workerCapturesAudited':27,'readableArtifactsHashed':len(manifest),'inaccessiblePathsRetained':len(inaccessible),'osCrashRuns':0,'physicalPowerLossRuns':0,'productionUnsafePolicyChanged':False})
    Path(public).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ['caseCount','workerCapturesAudited','readableArtifactsHashed','inaccessiblePathsRetained']}))
if __name__=='__main__':
    if not __debug__:raise RuntimeError('Audit requires Python without -O')
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['root','binary','public']:p.add_argument('--'+name,required=True)
    a=p.parse_args();run(a.root,a.binary,a.public)
