"""Bind the release qualifier's actual captures/artifacts to a public aggregate."""
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
    assert report['caseCount']==len(report['cases'])==30 and len({c['id'] for c in report['cases']})==30
    actor_count=0
    for case in report['cases']:
        folder=root/case['id'];capture=folder/'worker'
        events=[json.loads(line) for line in (capture/'stdout.jsonl').read_text().splitlines()]
        assert all(not e['committed'] and not e['productionPublicationAllowed'] and not e.get('namespaceAcknowledged',False) and not e.get('restartRepairAllowed',False) for e in events)
        code=json.loads((capture/'exit.json').read_text())['exitCode']
        if case.get('refusedBeforeEffects'):
            assert code==0 and events[0]['outcome']=='refused-before-effects' and not (folder/'absent.marker').exists()
            continue
        assert (folder/'transaction.marker').is_dir()
        release=next((e for e in events if 'releaseOsError' in e),None)
        assert case['release']==release
        terminal=next((e for e in events if 'outcome' in e),None)
        assert terminal==case['terminal']
        if case['stop']=='kill':assert code!=0 and terminal is None
        else:assert code==case['exitCode']
        if release:
            assert not release['releaseExactCreationPolicyMatches'] and release['contentAndIdentityUnchanged']
            if case['mode']!='ordinary-control':assert release['releaseOsError']==5
        transaction=folder/'transaction.marker'
        if case['id']=='post-exit-delete':assert not (transaction/'output.marker').exists()
        elif case['id']=='post-exit-rename':assert (transaction/'moved.marker').read_bytes()==b'3'*65536 and not (transaction/'output.marker').exists()
        elif case['id']=='collision':
            assert (transaction/'output.marker').read_bytes()==b'foreign-winner' and (transaction/'stage.marker').read_bytes()==b'3'*65536
        elif case['stopPhase']=='guarded':assert (transaction/'stage.marker').read_bytes()==b'3'*65536 and not (transaction/'output.marker').exists()
        elif case['mode']=='ordinary-control':assert (transaction/'output.marker').read_bytes()==b'foreign-marker'+b'3'*(65536-14)
        else:assert (transaction/'output.marker').read_bytes()==b'3'*65536 and not (transaction/'stage.marker').exists()
        expected_actors={}
        if case['heldActorResult'] is not None:expected_actors['actor']=case['heldActorResult']
        expected_actors.update({'after-exit-'+name:event for name,event in case['postExitActors'].items()})
        for name,expected in expected_actors.items():
            actor=folder/name
            actual=[json.loads(line) for line in (actor/'stdout.jsonl').read_text().splitlines()]
            assert actual==[expected] and json.loads((actor/'exit.json').read_text())['exitCode']==0
            actor_count+=1
    source_root=Path(__file__).resolve().parents[2]
    sources=list((source_root/'experiments/0039-output-release/src').glob('*.rs'))
    sources+=[source_root/name for name in ['experiments/0039-output-release/Cargo.toml','experiments/0039-output-release/Cargo.lock','experiments/0039-output-release/qualify.py','experiments/0039-output-release/audit.py','experiments/0032-windows-publication/src/native.rs','experiments/0034-source-oplocks/src/path.rs','experiments/0034-source-oplocks/qualify.py','experiments/0033-owner-rights/actor.py']]
    (root/'source-binding.private.json').write_text(json.dumps({'binarySha256':sha(binary),'sourceHashes':{str(p.relative_to(source_root)):sha(p) for p in sources}},indent=2)+'\n',encoding='utf-8')
    manifest={}
    for path in root.rglob('*'):
        if path.is_file() and path.name!='capture-manifest.private.json':manifest[str(path.relative_to(root))]={'sha256':sha(path),'size':path.stat().st_size}
    (root/'capture-manifest.private.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    report.update({'observedOn':'2026-10-13','workerCapturesAudited':30,'actorCapturesAudited':actor_count,'readableArtifactsHashed':len(manifest),
                   'osCrashRuns':0,'physicalPowerLossRuns':0,'productionUnsafePolicyChanged':False,'outputReleaseQualified':False})
    Path(public).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ['caseCount','workerCapturesAudited','actorCapturesAudited','readableArtifactsHashed']}))

if __name__=='__main__':
    if not __debug__:raise RuntimeError('Audit requires Python without -O')
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['root','binary','public']:p.add_argument('--'+name,required=True)
    a=p.parse_args();run(a.root,a.binary,a.public)
