"""Audit readable captures and retain/report deliberately inaccessible markers."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        while block:=stream.read(65536):digest.update(block)
    return digest.hexdigest()


def run(root,binary,public):
    root=Path(root).resolve();binary=Path(binary).resolve()
    report=json.loads((root/'report.json').read_text(encoding='utf-8'))
    assert len(report['cases'])==report['caseCount']==66
    assert len({c['id'] for c in report['cases']})==66 and not report['productionPublicationAllowed']
    captures=0
    for case in report['cases']:
        capture=root/case['id']/'worker'
        if not capture.exists():continue
        events=json.loads((capture/'events.json').read_text(encoding='utf-8'))
        raw=(capture/'stdout.jsonl').read_text(encoding='utf-8')
        assert events==[json.loads(line) for line in raw.splitlines() if line.startswith('{')]
        assert all(not e.get('productionPublicationAllowed',False) and not e.get('committed',False) for e in events)
        if case.get('policy')=='fresh-sealed':
            observed=next(e for e in events if e.get('outcome')=='owned-marker-observed')
            assert all(observed[key] for key in ['identityUnchanged','contentUnchanged','privatePropertyPolicyMatches','mtimeUnchanged','attributesUnchanged','defaultStreamOnly'])
            assert observed['linkCount']==1
        captures+=1
    manifest={};denied=[];streams=0
    for path in root.rglob('*'):
        if path.is_file() and path.name!='capture-manifest.private.json':
            try:manifest[str(path.relative_to(root))]={'sha256':sha(path),'size':path.stat().st_size}
            except PermissionError:denied.append({'path':str(path.relative_to(root)),'reason':'deliberately changed marker ACL; retained without repair'})
            if path.suffix=='.marker':
                stream=Path(str(path)+':probe')
                try:
                    with stream.open('rb') as data:blob=data.read(65537)
                    manifest[str(path.relative_to(root))+':probe']={'sha256':hashlib.sha256(blob).hexdigest(),'size':len(blob)};streams+=1
                except FileNotFoundError:pass
                except PermissionError:pass
    sources=['experiments/0033-owner-rights/src/main.rs','experiments/0033-owner-rights/src/windows.rs',
             'experiments/0033-owner-rights/actor.py','experiments/0033-owner-rights/qualify.py',
             'experiments/0032-windows-publication/src/native.rs']
    source_root=Path(__file__).resolve().parents[2]
    binding={'binarySha256':sha(binary),'sourceHashes':{name:sha(source_root/name) for name in sources}}
    (root/'source-binding.private.json').write_text(json.dumps(binding,indent=2)+'\n',encoding='utf-8')
    (root/'capture-manifest.private.json').write_text(json.dumps({'readable':manifest,'inaccessible':denied},indent=2)+'\n',encoding='utf-8')
    report.update({'schemaVersion':1,'observedOn':'2026-10-13','capturesAudited':captures,'readableArtifactsHashed':len(manifest),
                   'inaccessibleArtifactsRetained':len(denied),'alternateStreamsHashed':streams,'sourceBindingRetained':True,
                   'existingSourcePropertyGuardQualified':False,'restartCustodyQualified':False,'physicalPowerLossRuns':0,
                   'osCrashRuns':0,'rootProductionUnsafePolicyChanged':False})
    Path(public).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({key:report[key] for key in ['caseCount','capturesAudited','readableArtifactsHashed','inaccessibleArtifactsRetained','alternateStreamsHashed']}))


if __name__=='__main__':
    if not __debug__:raise RuntimeError('Audit assertions require Python without -O')
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['root','binary','public']:parser.add_argument('--'+name,required=True)
    args=parser.parse_args();run(args.root,args.binary,args.public)
