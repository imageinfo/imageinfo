"""Audit option A captures and readable artifacts; inaccessible markers stay untouched."""
import argparse,hashlib,json
from pathlib import Path

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        while block:=f.read(65536):h.update(block)
    return h.hexdigest()

def run(root,binary,public):
    root=Path(root).resolve();binary=Path(binary).resolve();report=json.loads((root/'report.json').read_text())
    assert report['caseCount']==len(report['cases'])==len({c['id'] for c in report['cases']})==64
    captures=0;inventories=0
    for case in report['cases']:
        folder=root/case['id']
        for capture in folder.iterdir():
            if not capture.is_dir() or not (capture/'stdout.jsonl').exists():continue
            stdout=[json.loads(line) for line in (capture/'stdout.jsonl').read_text().splitlines()]
            for event in stdout:assert not event.get('committed',False) and not event.get('productionPublicationAllowed',False) and not event.get('repairAllowed',False)
            code=json.loads((capture/'exit.json').read_text())['exitCode']
            if capture.name=='worker':
                terminal=next((e for e in stdout if 'outcome' in e),None)
                if case.get('terminal'):assert code==0 and terminal==case['terminal']
                elif case.get('stop')=='kill':assert code!=0 and terminal is None
                elif case.get('refusedBeforeEffects'):assert code==0 and terminal['outcome']=='refused-before-effects'
                elif case.get('guardRefused'):assert code==5 and not stdout
                else:assert case.get('compatibleReadMap') and code==0
                captures+=1
        if case.get('inspection'):
            actual=json.loads((folder/'inspect/stdout.jsonl').read_text())
            assert actual==case['inspection']
            snapshot=json.loads((folder/'inspection-inventory.private.json').read_text());assert snapshot['before']==snapshot['after'];inventories+=1
            if case['id']=='normal':assert actual['outcome']=='matching-output-recovery-required'
        transaction=folder/'transaction.marker'
        if case.get('sourceRetained'):assert (transaction/'source.marker').exists()
        if case['id']=='collision':assert (transaction/'output.marker').read_bytes()==b'foreign-winner'
        if case['id']=='post-exit-write':assert (transaction/'output.marker').read_bytes()==b'foreign-marker'+b'3'*(65536-14)
    assert captures==64 and inventories==56
    source_root=Path(__file__).resolve().parents[2]
    paths=list((source_root/'experiments/0032-windows-publication/src').glob('*.rs'))
    paths += [source_root/name for name in ['experiments/0032-windows-publication/Cargo.toml','experiments/0032-windows-publication/Cargo.lock','experiments/0038-staging-cleanup/src/staging.rs','experiments/0038-staging-cleanup/src/disposition.rs','experiments/0033-owner-rights/actor.py','experiments/0034-source-oplocks/actor.py','experiments/0034-source-oplocks/qualify.py','experiments/0022-ordinary-output/qualify.py','experiments/0022-ordinary-output/audit.py']]
    (root/'source-binding.private.json').write_text(json.dumps({'binarySha256':sha(binary),'sources':{str(p.relative_to(source_root)):sha(p) for p in paths}},indent=2),encoding='utf-8')
    manifest={};inaccessible=[]
    for path in root.rglob('*'):
        if not path.is_file() or path.name=='artifact-manifest.private.json':continue
        try:manifest[str(path.relative_to(root))]={'sha256':sha(path),'size':path.stat().st_size}
        except PermissionError:inaccessible.append(str(path.relative_to(root)))
        for stream in [':probe']:
            try:manifest[str(path.relative_to(root))+stream]={'sha256':sha(Path(str(path)+stream))}
            except FileNotFoundError:pass
            except PermissionError:pass
    (root/'artifact-manifest.private.json').write_text(json.dumps({'readablePaths':manifest,'inaccessibleRetainedWithoutRepair':inaccessible},indent=2),encoding='utf-8')
    report.update({'observedOn':'2026-10-14','workerCapturesAudited':captures,'unchangedInspectionInventories':inventories,'readableArtifactPathsHashed':len(manifest),'inaccessiblePathsRetained':len(inaccessible),'data':'authored marker bytes only','logicalScratchCap':262144,'committed':False,'namespaceAcknowledged':False,'physicalPowerLossRuns':0})
    Path(public).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ['caseCount','workerCapturesAudited','unchangedInspectionInventories','readableArtifactPathsHashed','inaccessiblePathsRetained']}))

if __name__=='__main__':
    if not __debug__:raise RuntimeError('Audit requires assertions')
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['root','binary','public']:p.add_argument('--'+name,required=True)
    a=p.parse_args();run(a.root,a.binary,a.public)
