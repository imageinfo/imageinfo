"""Fresh owned output-policy release attempts; original media/privileges unchanged."""
import argparse,csv,json,os
from importlib.util import spec_from_file_location,module_from_spec
from pathlib import Path
import subprocess,sys,tempfile

HERE=Path(__file__).resolve().parent
spec=spec_from_file_location('capture_process',HERE.parent/'0034-source-oplocks'/'qualify.py')
module=module_from_spec(spec);spec.loader.exec_module(module)
Process=module.Process
ACTOR=HERE.parent/'0033-owner-rights'/'actor.py'
PHASES=['guarded','published-sealed','policy-release-attempted']

def actor(name,path,capture):
    p=Process([sys.executable,ACTOR,name,path],capture)
    try:
        event=p.next();assert p.finish()==0
        return event
    finally:
        p.stop();p.timer.cancel()
        if not p.capture.exists():p.finish()

def trial(binary,scratch,name,mode='release',action=None,action_phase='guarded',stop=None,stop_phase=None,post=None):
    case=scratch/name;case.mkdir();root=case/'transaction.marker'
    p=Process([binary,mode,root],case/'worker');events=[];effect=None
    try:
        for phase in PHASES:
            while True:
                event=p.next();events.append(event)
                if event.get('barrier')==phase:break
            if action and phase==action_phase:
                target=root/('stage.marker' if phase=='guarded' else 'output.marker')
                effect=actor(action,target,case/'actor');assert effect['allowed']==(action=='read')
            if name=='collision' and phase=='guarded':(root/'output.marker').write_bytes(b'foreign-winner')
            if stop_phase==phase:
                if stop=='kill':p.stop()
                else:p.controls.append('cancel');p.proc.stdin.write('cancel\n');p.proc.stdin.flush()
                break
            p.send()
            if name=='collision' or (mode=='inject-before-release' and phase=='published-sealed'):break
        code=p.finish()
        all_events=[json.loads(line) for line in p.lines]
        errors=[json.loads(line) for line in p.stderr]
        assert all(not e['committed'] and not e['productionPublicationAllowed'] and not e['namespaceAcknowledged'] and not e['restartRepairAllowed'] for e in all_events)
        release=next((e for e in all_events if 'releaseOsError' in e),None)
        terminal=next((e for e in all_events if 'outcome' in e),None)
        if stop=='kill':assert code!=0 and not terminal and not errors
        elif stop=='cancel':assert code==5 and errors[-1]['diagnostic']=='CONTROL_STOP' and not terminal
        elif mode.startswith('inject-'):assert code==5 and errors[-1]['diagnostic'].startswith('INJECTED_') and not terminal
        elif name=='collision':assert code==5 and not release and not terminal
        else:
            assert code==0 and terminal['outcome']=='owned-output-policy-release-unverified'
            assert release and not release['releaseExactCreationPolicyMatches'] and release['contentAndIdentityUnchanged']
            if mode=='ordinary-control':assert release['releaseOsError'] is None and release['releaseDiagnostic']=='PRIVATE_OWNER_OR_DACL_CHANGED'
            else:assert release['releaseOsError']==5
        retained=sorted(v.name for v in root.iterdir())
        output=stop_phase!='guarded' and name!='collision'
        if name=='collision':
            assert (root/'output.marker').read_bytes()==b'foreign-winner' and (root/'stage.marker').read_bytes()==b'3'*65536
        elif output:assert (root/'output.marker').read_bytes()==b'3'*65536 and not (root/'stage.marker').exists()
        else:assert (root/'stage.marker').read_bytes()==b'3'*65536 and not (root/'output.marker').exists()
        post_effects={}
        if post:
            for choice in post:
                result=actor(choice,root/'output.marker',case/('after-exit-'+choice));post_effects[choice]=result
                assert result['allowed']==(choice in ['read','delete','rename'] or mode=='ordinary-control')
        return {'id':name,'mode':mode,'heldActor':action,'heldActorPhase':action_phase if action else None,'heldActorResult':effect,
                'stop':stop,'stopPhase':stop_phase,'exitCode':code if stop!='kill' else None,'release':release,'terminal':terminal,
                'retainedBeforePostExitActors':retained,'postExitActors':post_effects,'foreignWinnerRetained':name=='collision'}
    finally:
        p.stop();p.timer.cancel()
        if not p.capture.exists():p.finish()

def run(binary,parent):
    binary=Path(binary).resolve();parent=Path(parent).resolve();parent.mkdir(parents=True,exist_ok=True)
    if os.name!='nt':
        p=subprocess.run([binary,'admit',parent/'absent.marker'],capture_output=True,text=True,timeout=15)
        assert p.returncode==5 and json.loads(p.stderr)['diagnostic']=='OUTPUT_RELEASE_WINDOWS_UNVERIFIED' and not (parent/'absent.marker').exists()
        print(json.dumps({'unsupportedPlatformRefused':True}));return
    scratch=Path(tempfile.mkdtemp(prefix='output-release-',dir=parent))
    identity=subprocess.run(['whoami','/user','/fo','csv','/nh'],capture_output=True,check=True,timeout=15)
    sid=next(csv.reader(identity.stdout.decode('utf-8',errors='replace').splitlines()))[-1]
    assert sid.startswith('S-1-5-') and all(part.isdigit() for part in sid[2:].split('-'))
    policy=subprocess.run(['icacls',str(scratch),'/inheritance:r','/grant:r','*'+sid+':(OI)(CI)F'],capture_output=True,check=True,timeout=15)
    (scratch/'root-policy.private.txt').write_bytes(policy.stdout+policy.stderr)
    cases=[]
    try:
        for mode in ['release','full-control','no-write-dac']:
            cases.append(trial(binary,scratch,mode,mode=mode,post=['read','write','ads','mtime','dacl','owner-access','link','readonly']))
        cases.append(trial(binary,scratch,'ordinary-control',mode='ordinary-control',post=['read','write']))
        for name in ['read','mtime','readonly','dacl','owner-access','ads','write','link']:
            cases.append(trial(binary,scratch,'guarded-'+name,action=name))
        for name in ['mtime','dacl','ads','write']:
            cases.append(trial(binary,scratch,'post-attempt-'+name,action=name,action_phase='policy-release-attempted'))
        for phase in PHASES:
            for stop in ['kill','cancel']:cases.append(trial(binary,scratch,stop+'-'+phase,stop=stop,stop_phase=phase))
        for mode in ['inject-before-release','inject-after-release']:cases.append(trial(binary,scratch,mode,mode=mode))
        cases.append(trial(binary,scratch,'collision'))
        for name in ['delete','rename']:cases.append(trial(binary,scratch,'post-exit-'+name,post=[name]))
        for mode in ['admit','finalize','prune']:
            case=scratch/mode;case.mkdir();p=Process([binary,mode,case/'absent.marker'],case/'worker')
            assert p.finish()==0;report=json.loads(''.join(p.lines));assert report['outcome']=='refused-before-effects' and not (case/'absent.marker').exists()
            cases.append({'id':mode,'refusedBeforeEffects':True})
        report={'schemaVersion':1,'caseCount':len(cases),'cases':cases,'productionPublicationAllowed':False,'enabledProfiles':0}
        (scratch/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps({'root':str(scratch),'caseCount':len(cases)}))
    except BaseException:
        (scratch/'failed-report.private.json').write_text(json.dumps(cases,indent=2),encoding='utf-8');print('Retained attempt: '+str(scratch),file=sys.stderr);raise
if __name__=='__main__':
    if not __debug__:raise RuntimeError('Qualification requires Python without -O')
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--binary',required=True);p.add_argument('--parent',required=True);a=p.parse_args();run(a.binary,a.parent)
