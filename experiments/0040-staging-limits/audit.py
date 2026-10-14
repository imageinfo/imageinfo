"""Audit exact budget/source failures and the retained owned-cleanup regression."""
import argparse,hashlib,json
from pathlib import Path

STAGE=65536
RECORD=b'owned-prepublication-marker-v1\n'
TOTAL=STAGE+len(RECORD)

def sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as source:
        while block:=source.read(65536):digest.update(block)
    return digest.hexdigest()

def captures(folder):
    capture=folder/'worker'
    events=[json.loads(line) for line in (capture/'stdout.jsonl').read_text().splitlines()]
    errors=[json.loads(line) for line in (capture/'stderr.jsonl').read_text().splitlines()]
    assert all(not e['committed'] and not e['productionPublicationAllowed'] for e in events+errors)
    return events,errors,json.loads((capture/'exit.json').read_text())['exitCode']

def run(root,regression,binary,public):
    root=Path(root).resolve();regression=Path(regression).resolve();binary=Path(binary).resolve()
    report=json.loads((root/'report.json').read_text())
    assert report['caseCount']==len(report['cases'])==len({c['id'] for c in report['cases']})==17
    for case in report['cases']:
        folder=root/case['id'];transaction=folder/'transaction.marker';events,errors,code=captures(folder)
        assert not (transaction/'output.marker').exists()
        assert case['plannedBytes']==TOTAL and case['published'] is False
        assert case['diagnostic']==(errors[-1]['diagnostic'] if errors else None)
        if not case['rootCreated']:
            assert not transaction.exists() and not events and code==5
            assert case['diagnostic'] in ['SCRATCH_BYTE_LIMIT_EXCEEDED','SCRATCH_LIMIT_INVALID']
        elif case['existingRoot']:
            assert code==5 and not events and (transaction/'foreign.marker').read_bytes()==b'foreign-retained'
        elif case['mode'] in ['short-source','long-source']:
            expected=STAGE-1 if case['mode']=='short-source' else STAGE
            assert code==5 and not events and (transaction/'stage.marker').read_bytes()==b'8'*expected
        else:
            observation=json.loads((folder/'held-observation.private.json').read_text())
            assert observation=={'stageLength':STAGE,'recordLength':len(RECORD),'stageSha256':hashlib.sha256(b'8'*STAGE).hexdigest(),'recordSha256':hashlib.sha256(RECORD).hexdigest()}
            if case['workerKilled']:
                assert code!=0 and not errors and not any('outcome' in e for e in events)
                assert (transaction/'stage.marker').read_bytes()==b'8'*STAGE and (transaction/'record.marker').read_bytes()==RECORD
            else:assert code==0 and case['terminal']==events[-1] and not list(transaction.iterdir())
        if case['rootCreated']:assert {v.name:v.stat().st_size for v in transaction.iterdir()}==case['retainedFiles']
    previous=json.loads((regression/'report.json').read_text())
    assert previous['caseCount']==len(previous['cases'])==27
    for case in previous['cases']:
        events,errors,code=captures(regression/case['id'])
        if case.get('terminal'):
            assert code==0 and case['terminal']==events[-1]
            if case['terminal']['publicationAttempted']:assert not case['markedRoles']
        elif case.get('workerKilled'):assert code!=0 and not any('outcome' in e for e in events)
        else:assert code==0 and events[0]['outcome']=='refused-before-effects'
    source_root=Path(__file__).resolve().parents[2]
    sources=list((source_root/'experiments/0038-staging-cleanup/src').glob('*.rs'))
    sources+=[source_root/name for name in ['experiments/0038-staging-cleanup/Cargo.toml','experiments/0038-staging-cleanup/Cargo.lock','experiments/0038-staging-cleanup/qualify.py','experiments/0038-staging-cleanup/actor.py','experiments/0040-staging-limits/qualify.py','experiments/0040-staging-limits/audit.py','experiments/0032-windows-publication/src/native.rs','experiments/0034-source-oplocks/src/path.rs','experiments/0034-source-oplocks/qualify.py','experiments/0033-owner-rights/actor.py']]
    binding={'binarySha256':sha(binary),'sourceHashes':{str(p.relative_to(source_root)):sha(p) for p in sources}}
    (root/'source-binding.private.json').write_text(json.dumps(binding,indent=2)+'\n',encoding='utf-8')
    counts=[];inaccessible=[]
    for selected in [root,regression]:
        manifest={};blocked=[]
        for path in selected.rglob('*'):
            if path.is_dir():
                try:list(path.iterdir())
                except PermissionError:blocked.append(str(path.relative_to(selected)))
            elif path.is_file() and path.name!='limits-manifest.private.json':
                try:manifest[str(path.relative_to(selected))]={'sha256':sha(path),'size':path.stat().st_size}
                except PermissionError:blocked.append(str(path.relative_to(selected)))
        (selected/'limits-manifest.private.json').write_text(json.dumps({'readable':manifest,'inaccessibleRetainedWithoutRepair':blocked},indent=2)+'\n',encoding='utf-8')
        counts.append(len(manifest));inaccessible.append(len(blocked))
    report.update({'observedOn':'2026-10-14','workerCapturesAudited':44,'limitsCaptures':17,'cleanupRegressionCaptures':27,
                   'limitsArtifactsHashed':counts[0],'cleanupRegressionArtifactsHashed':counts[1],
                   'inaccessibleRegressionPathsRetained':inaccessible[1],'portableTests':10,'newPackages':0,'newOsApis':0,
                   'osCrashRuns':0,'physicalPowerLossRuns':0,'productionUnsafePolicyChanged':False,
                   'logicalBytesOnly':True,'diskSpaceReserved':False,'filesystemAllocationBoundQualified':False})
    assert inaccessible==[0,1]
    Path(public).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ['caseCount','workerCapturesAudited','limitsArtifactsHashed','cleanupRegressionArtifactsHashed','inaccessibleRegressionPathsRetained']}))

if __name__=='__main__':
    if not __debug__:raise RuntimeError('Audit requires Python without -O')
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['root','regression','binary','public']:p.add_argument('--'+name,required=True)
    a=p.parse_args();run(a.root,a.regression,a.binary,a.public)
