"""Live owned staging cleanup, foreign-entry preservation and truthful refusals."""
import argparse,csv,json,os
from importlib.util import spec_from_file_location,module_from_spec
from pathlib import Path
import subprocess,sys,tempfile

HERE=Path(__file__).resolve().parent
spec=spec_from_file_location('capture_process',HERE.parent/'0034-source-oplocks'/'qualify.py')
module=module_from_spec(spec);spec.loader.exec_module(module)
Process=module.Process
def send(p,word):
    p.controls.append(word);p.proc.stdin.write(word+'\n');p.proc.stdin.flush()
def actor(mode,path,capture,reader=False):
    p=Process([sys.executable,HERE/'actor.py',mode,path],capture)
    event=p.next()
    if reader and event.get('opened'):return p,event
    assert p.finish()==0
    return None,event
def trial(binary,scratch,name,mode='abort',action=None,kill=None,cancel_publish=False):
    case=scratch/name;case.mkdir();root=case/'transaction.marker'
    p=Process([binary,mode,root],case/'worker');reader=None;events=[]
    try:
        prepared=p.next();events.append(prepared);assert prepared['barrier']=='prepared'
        if action:reader=action(root,case)
        if kill=='prepared':p.stop()
        else:send(p,'continue' if mode=='publish' and not cancel_publish else 'cancel')
        marked=[];closed=[];terminal=None
        while kill!='prepared':
            event=p.next();events.append(event)
            if 'markedOwnedRole' in event:marked.append(event['markedOwnedRole'])
            if 'closedOwnedRole' in event:
                closed.append(event['closedOwnedRole'])
                if name.startswith('reinsert-'):
                    selected=name[len('reinsert-'):]+'.marker'
                    if event['closedOwnedRole']==selected:(root/selected).write_bytes(b'foreign-reinserted')
            if 'barrier' in event:
                if event['barrier']==kill:p.stop();break
                send(p,'cancel' if event['barrier']=='publication-attempted' else 'continue')
            if 'outcome' in event:terminal=event;break
        code=p.finish();assert kill or code==0
        try:retained=sorted(v.name for v in root.iterdir())
        except PermissionError:retained=None
        if terminal:
            assert not terminal['committed'] and not terminal['productionPublicationAllowed']
            if mode=='publish' and not cancel_publish:assert terminal['outcome']=='cleanup-refused-after-publication-attempt' and not marked
            elif mode=='inject-error':assert terminal['outcome']=='cleanup-partial-injected-error' and terminal['ownedHandlesMarkedAndClosed']==1
            elif mode=='no-delete':assert terminal['outcome']=='cleanup-partial-native-error' and terminal['ownedHandlesMarkedAndClosed']==0
            elif name=='root-dacl':assert terminal['outcome']=='cleanup-refused-live-guard' and not marked
            else:
                assert terminal['outcome']=='cancelled-before-publication' and terminal['ownedHandlesMarkedAndClosed']==2
                if name in ['normal','publish-cancel-before-call']:assert retained==[] and not terminal['cleanupPending']
            if name=='compatible-reader':assert terminal['cleanupPending'] and retained==['stage.marker']
            if mode=='no-delete':assert any(e.get('dispositionErrorCode')==5 for e in events)
        if reader is not None:
            send(reader,'release');assert reader.finish()==0
            assert not (root/'stage.marker').exists()
        if name.startswith('reinsert-'):
            selected=name[len('reinsert-'):]+'.marker';assert (root/selected).read_bytes()==b'foreign-reinserted'
        if name=='extra-entry':assert (root/'unrelated.marker').read_bytes()==b'foreign-extra'
        if name=='collision':assert (root/'output.marker').read_bytes()==b'foreign-winner'
        if name=='published':assert (root/'output.marker').read_bytes()==b'8'*65536
        return {'id':name,'mode':mode,'terminal':terminal,'markedRoles':marked,'closedRoles':closed,'retainedAfterHolderExit':retained,'workerKilled':bool(kill),'rootRetained':root.exists()}
    finally:
        p.stop();p.timer.cancel()
        if not p.capture.exists():p.finish()
        if reader is not None:
            reader.stop();reader.timer.cancel()
            if not reader.capture.exists():reader.finish()
def run(binary,parent):
    binary=Path(binary).resolve();parent=Path(parent).resolve();parent.mkdir(parents=True,exist_ok=True)
    if os.name!='nt':
        p=subprocess.run([binary,'admit',parent/'absent.marker'],capture_output=True,text=True,timeout=15)
        assert p.returncode==5 and json.loads(p.stderr)['diagnostic']=='STAGING_CLEANUP_WINDOWS_UNVERIFIED' and not (parent/'absent.marker').exists()
        print(json.dumps({'unsupportedPlatformRefused':True}));return
    scratch=Path(tempfile.mkdtemp(prefix='staging-cleanup-',dir=parent))
    identity=subprocess.run(['whoami','/user','/fo','csv','/nh'],capture_output=True,check=True,timeout=15)
    sid=next(csv.reader(identity.stdout.decode('utf-8',errors='replace').splitlines()))[-1]
    assert sid.startswith('S-1-5-') and all(part.isdigit() for part in sid[2:].split('-'))
    policy=subprocess.run(['icacls',str(scratch),'/inheritance:r','/grant:r','*'+sid+':(OI)(CI)F'],capture_output=True,check=True,timeout=15)
    (scratch/'root-policy.private.txt').write_bytes(policy.stdout+policy.stderr)
    cases=[]
    try:
        cases.append(trial(binary,scratch,'normal'))
        cases.append(trial(binary,scratch,'publish-cancel-before-call',mode='publish',cancel_publish=True))
        for name in ['stage','record']:cases.append(trial(binary,scratch,'reinsert-'+name))
        def extra(root,case):(root/'unrelated.marker').write_bytes(b'foreign-extra')
        cases.append(trial(binary,scratch,'extra-entry',action=extra))
        def reader(root,case):
            p,event=actor('reader',root/'stage.marker',case/'reader',True);assert event['opened'];return p
        cases.append(trial(binary,scratch,'compatible-reader',action=reader))
        def incompatible(root,case):
            _,event=actor('reader-no-delete-share',root/'stage.marker',case/'actor');assert not event['opened'] and event['winError']==32
        cases.append(trial(binary,scratch,'incompatible-reader',action=incompatible))
        for name in ['mtime','readonly','dacl','owner-access','ads','write','link','delete','rename']:
            def refuse(root,case,name=name):
                _,event=actor(name,root/'stage.marker',case/'actor');assert not event['allowed']
            cases.append(trial(binary,scratch,'actor-'+name,action=refuse))
        def change_root(root,case):actor('root-dacl',root,case/'actor')
        cases.append(trial(binary,scratch,'root-dacl',action=change_root))
        cases.append(trial(binary,scratch,'native-no-delete',mode='no-delete'))
        cases.append(trial(binary,scratch,'injected-after-first-close',mode='inject-error'))
        cases.append(trial(binary,scratch,'published',mode='publish'))
        def winner(root,case):(root/'output.marker').write_bytes(b'foreign-winner')
        cases.append(trial(binary,scratch,'collision',mode='publish',action=winner))
        for phase in ['prepared','delete-marked','owned-handle-closed']:
            cases.append(trial(binary,scratch,'kill-'+phase,kill=phase))
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
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--binary',required=True);p.add_argument('--parent',required=True);args=p.parse_args();run(args.binary,args.parent)
