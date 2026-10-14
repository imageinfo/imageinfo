"""Actual staging byte preflight, bounded-copy failures and cancellation."""
import argparse,csv,ctypes,hashlib,json,os
from importlib.util import spec_from_file_location,module_from_spec
from pathlib import Path
import subprocess,tempfile,sys

HERE=Path(__file__).resolve().parent
spec=spec_from_file_location('capture_process',HERE.parent/'0034-source-oplocks'/'qualify.py')
module=module_from_spec(spec);spec.loader.exec_module(module)
Process=module.Process
spec=spec_from_file_location('owner_actor',HERE.parent/'0033-owner-rights'/'actor.py')
owner_module=module_from_spec(spec);spec.loader.exec_module(owner_module)
STAGE=65536
RECORD=b'owned-prepublication-marker-v1\n'
TOTAL=STAGE+len(RECORD)

def held_bytes(path):
    # Reuse the reviewed actor declarations and compatible READ|WRITE|DELETE
    # sharing. Python's ordinary open omits DELETE sharing and cannot coexist
    # with the creator's retained DELETE right.
    actor=owner_module.Actor();handle=actor.open(path,1)
    try:
        data=ctypes.create_string_buffer(STAGE+1);count=owner_module.w.DWORD()
        if not actor.k.ReadFile(handle,data,STAGE+1,ctypes.byref(count),None):raise ctypes.WinError(ctypes.get_last_error())
        return data.raw[:count.value]
    finally:actor.k.CloseHandle(handle)

def trial(binary,scratch,name,limit=None,mode='abort',stop=None,existing=False):
    case=scratch/name;case.mkdir();root=case/'transaction.marker'
    if existing:
        root.mkdir();(root/'foreign.marker').write_bytes(b'foreign-retained')
    argv=[binary,mode,root]
    if limit is not None:argv.append(str(limit))
    p=Process(argv,case/'worker');terminal=None;events=[]
    refused=limit is not None and (not str(limit).isascii() or not str(limit).isdigit() or int(limit)>2**64-1 or int(limit)<TOTAL)
    try:
        if not refused and not existing and mode not in ['short-source','long-source']:
            event=p.next();events.append(event);assert event['barrier']=='prepared'
            stage=held_bytes(root/'stage.marker');record=held_bytes(root/'record.marker')
            assert stage==b'8'*STAGE and record==RECORD
            assert sum(v.stat().st_size for v in root.iterdir())==TOTAL
            (case/'held-observation.private.json').write_text(json.dumps({'stageLength':len(stage),'recordLength':len(record),'stageSha256':hashlib.sha256(stage).hexdigest(),'recordSha256':hashlib.sha256(record).hexdigest()}),encoding='utf-8')
            if stop=='kill':p.stop()
            elif stop=='cancel' or stop is None:
                p.controls.append('cancel');p.proc.stdin.write('cancel\n');p.proc.stdin.flush()
                while True:
                    event=p.next();events.append(event)
                    if 'barrier' in event:p.send()
                    if 'outcome' in event:terminal=event;break
        code=p.finish()
        captured=[json.loads(line) for line in p.lines]
        errors=[json.loads(line) for line in p.stderr]
        assert all(not e['committed'] and not e['productionPublicationAllowed'] for e in captured+errors)
        diagnostic=errors[-1]['diagnostic'] if errors else None
        if refused:
            assert code==5 and not root.exists() and not captured
            assert diagnostic==('SCRATCH_BYTE_LIMIT_EXCEEDED' if str(limit).isascii() and str(limit).isdigit() and int(limit)<=2**64-1 else 'SCRATCH_LIMIT_INVALID')
        elif existing:
            assert code==5 and not captured and sorted(v.name for v in root.iterdir())==['foreign.marker']
            assert (root/'foreign.marker').read_bytes()==b'foreign-retained'
        elif mode in ['short-source','long-source']:
            expected=65535 if mode=='short-source' else 65536
            assert code==5 and diagnostic==('STAGE_SOURCE_SHORT' if mode=='short-source' else 'STAGE_SOURCE_LONG') and not captured
            assert sorted(v.name for v in root.iterdir())==['stage.marker'] and (root/'stage.marker').read_bytes()==b'8'*expected
        elif stop=='kill':
            assert code!=0 and not terminal and not errors
            assert sorted(v.name for v in root.iterdir())==['record.marker','stage.marker']
        else:
            assert code==0 and terminal['outcome']=='cancelled-before-publication'
            assert terminal['ownedHandlesMarkedAndClosed']==2 and not terminal['cleanupPending'] and not list(root.iterdir())
        assert not (root/'output.marker').exists()
        retained={v.name:v.stat().st_size for v in root.iterdir()} if root.exists() else None
        return {'id':name,'mode':mode,'limit':str(limit) if limit is not None else 'default-131072','rootCreated':root.exists(),
                'retainedFiles':retained,'terminal':terminal,'diagnostic':diagnostic,'workerKilled':stop=='kill','existingRoot':existing,
                'plannedBytes':TOTAL,'published':False}
    finally:
        p.stop();p.timer.cancel()
        if not p.capture.exists():p.finish()

def run(binary,parent):
    binary=Path(binary).resolve();parent=Path(parent).resolve();parent.mkdir(parents=True,exist_ok=True)
    if os.name!='nt':
        p=subprocess.run([binary,'abort',parent/'absent.marker',str(TOTAL)],capture_output=True,text=True,timeout=15)
        assert p.returncode==5 and json.loads(p.stderr)['diagnostic']=='STAGING_CLEANUP_WINDOWS_UNVERIFIED' and not (parent/'absent.marker').exists()
        print(json.dumps({'unsupportedPlatformRefused':True}));return
    scratch=Path(tempfile.mkdtemp(prefix='staging-limits-',dir=parent))
    identity=subprocess.run(['whoami','/user','/fo','csv','/nh'],capture_output=True,check=True,timeout=15)
    sid=next(csv.reader(identity.stdout.decode('utf-8',errors='replace').splitlines()))[-1]
    assert sid.startswith('S-1-5-') and all(part.isdigit() for part in sid[2:].split('-'))
    policy=subprocess.run(['icacls',str(scratch),'/inheritance:r','/grant:r','*'+sid+':(OI)(CI)F'],capture_output=True,check=True,timeout=15)
    (scratch/'root-policy.private.txt').write_bytes(policy.stdout+policy.stderr)
    cases=[]
    try:
        for limit in [0,1,STAGE-1,STAGE,TOTAL-1,TOTAL,TOTAL+1,2**64-1]:
            cases.append(trial(binary,scratch,'budget-'+str(limit),limit))
        for name,value in [('negative','-1'),('text','no'),('overflow',str(2**64))]:
            cases.append(trial(binary,scratch,'invalid-'+name,value))
        cases.append(trial(binary,scratch,'default-limit'))
        cases.append(trial(binary,scratch,'exact-limit-kill',TOTAL,stop='kill'))
        cases.append(trial(binary,scratch,'publish-mode-cancel',TOTAL,mode='publish',stop='cancel'))
        for mode in ['short-source','long-source']:
            cases.append(trial(binary,scratch,mode,TOTAL,mode=mode))
        cases.append(trial(binary,scratch,'foreign-existing-root',TOTAL,existing=True))
        report={'schemaVersion':1,'caseCount':len(cases),'cases':cases,'productionPublicationAllowed':False,'enabledProfiles':0}
        (scratch/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'root':str(scratch),'caseCount':len(cases)}))
    except BaseException:
        (scratch/'failed-report.private.json').write_text(json.dumps(cases,indent=2),encoding='utf-8');print('Retained attempt: '+str(scratch),file=sys.stderr);raise

if __name__=='__main__':
    if not __debug__:raise RuntimeError('Qualification requires Python without -O')
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--binary',required=True);p.add_argument('--parent',required=True);a=p.parse_args();run(a.binary,a.parent)
