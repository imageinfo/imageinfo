"""Option A live source/output guards, ordinary editing and restart observations."""
import argparse,csv,hashlib,json,mmap,os,subprocess,sys,tempfile
from pathlib import Path
from importlib.util import spec_from_file_location,module_from_spec
HERE=Path(__file__).resolve().parent
spec=spec_from_file_location('capture_process',HERE.parent/'0034-source-oplocks'/'qualify.py');capture=module_from_spec(spec);spec.loader.exec_module(capture)
Process=capture.Process
ACTOR=HERE.parent/'0033-owner-rights'/'actor.py'
PHASES=['source-guarded','candidate-flushed','prepared-record-flushed','intent-record-flushed','before-property-check','before-namespace-call','published','observed-record-flushed']

def inventory(root):
    result={}
    for path in root.iterdir():
        if not path.is_file():continue
        try:
            s=path.stat();result[path.name]={'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'size':s.st_size,'mtime':s.st_mtime_ns,'identity':s.st_ino,'links':s.st_nlink,'attributes':s.st_file_attributes}
        except PermissionError:result[path.name]={'inaccessible':True}
        for stream in [':probe']:
            try:result[path.name+stream]={'sha256':hashlib.sha256(Path(str(path)+stream).read_bytes()).hexdigest()}
            except FileNotFoundError:pass
            except PermissionError:result[path.name+stream]={'inaccessible':True}
    return result

def invoke(binary,root,mode,folder):
    p=Process([binary,root,mode],folder)
    code=p.finish();events=[json.loads(v) for v in p.lines]
    assert all(not e.get('committed',False) and not e.get('productionPublicationAllowed',False) for e in events)
    return code,events

def actor(name,path,folder):
    helper=HERE.parent/'0034-source-oplocks'/'actor.py' if name.startswith('link-') else ACTOR
    p=Process([sys.executable,helper,name,path],folder)
    assert p.finish()==0
    return json.loads(''.join(p.lines))

def trial(binary,parent,name,action=None,role='source',phase='before-property-check',stop=None,post=None,inspect_change=None):
    case=parent/name;case.mkdir();root=case/'transaction.marker'
    code,events=invoke(binary,root,'ordinary-prepare',case/'prepare');assert code==0 and events[0]['outcome']=='owned-source-prepared'
    p=Process([binary,root,'ordinary'],case/'worker');observed=[];action_result=None
    try:
        while True:
            event=p.next();observed.append(event)
            if event.get('barrier')==phase:
                target=root/(role+'.marker')
                if action:
                    action_result=actor('rename' if action=='root-rename' else action,root if action=='root-rename' else target,case/'actor')
                    if action in ['write','delete','rename','root-rename','link-write']:assert not action_result['allowed']
                    else:assert action_result['allowed']
                if name=='collision':(root/'output.marker').write_bytes(b'foreign-winner')
                if stop=='kill':p.stop();break
                if stop in ['cancel','fail']:
                    p.controls.append(stop);p.proc.stdin.write(stop+'\n');p.proc.stdin.flush();continue
            if 'barrier' in event:p.send()
            if 'outcome' in event:break
        code=p.finish();events=[json.loads(v) for v in p.lines];terminal=next((v for v in events if 'outcome' in v),None)
        assert all(not e['committed'] and not e['namespaceAcknowledged'] and not e['productionPublicationAllowed'] and not e['repairAllowed'] for e in events)
        if stop=='kill':assert code!=0 and terminal is None
        else:assert code==0 and terminal
        attempted=any(v.get('barrier')=='before-namespace-call' for v in events) and not (stop in ['cancel','fail','kill'] and phase=='before-namespace-call')
        output=(root/'output.marker').exists()
        if name=='collision':assert (root/'output.marker').read_bytes()==b'foreign-winner' and terminal['publicationAttempted'] and not terminal['publicationCallSucceeded'] and not terminal['installedCheckPassed']
        elif action in ['mtime','readonly','ads','link','dacl','link-write']:
            assert terminal['diagnostic'] is not None
            assert output==(phase in ['before-namespace-call','published','observed-record-flushed'])
        elif stop=='cancel' and phase not in ['published','observed-record-flushed']:
            assert not output and terminal['outcome']=='cancelled-before-publication' and not terminal['cleanupPending']
            assert sorted(v.name for v in root.iterdir())==['source.marker']
        elif stop in ['kill','fail']:
            assert output==(phase in ['published','observed-record-flushed'])
        else:assert output and (root/'output.marker').read_bytes()==b'3'*65536 and terminal['outcome']=='recovery-required'
        if post:
            result=actor(post,root/'output.marker',case/'post-actor');assert result['allowed']
        if inspect_change:
            if inspect_change=='record-corrupt':(root/'intent.record').write_bytes(b'bad-record')
            elif inspect_change=='extra':(root/'foreign.marker').write_bytes(b'foreign-extra')
            elif inspect_change=='remove-record':(root/'prepared.record').unlink()
        before=inventory(root)
        code,inspection=invoke(binary,root,'ordinary-inspect',case/'inspect');assert code==0
        after=inventory(root);assert before==after
        (case/'inspection-inventory.private.json').write_text(json.dumps({'before':before,'after':after},indent=2),encoding='utf-8')
        assert inspection and not inspection[0]['repairAllowed'] and not inspection[0]['committed']
        if name=='normal':assert inspection[0]['outcome']=='matching-output-recovery-required'
        if post=='write':assert inspection[0]['outcome']=='output-conflict'
        if inspect_change:assert inspection[0]['outcome']=='uninspectable'
        return {'id':name,'action':action,'role':role,'phase':phase,'actionResult':action_result,'stop':stop,'postActor':post,'terminal':terminal,'inspection':inspection[0],'outputPresent':output,'sourceRetained':(root/'source.marker').exists()}
    finally:
        p.stop();p.timer.cancel()
        if not p.capture.exists():p.finish()

def run(binary,parent):
    binary=Path(binary).resolve();parent=Path(parent).resolve();parent.mkdir(parents=True,exist_ok=True)
    if os.name!='nt':
        p=subprocess.run([binary,parent/'absent.marker','ordinary-admit'],capture_output=True,text=True,timeout=15)
        assert p.returncode==5 and json.loads(p.stderr)['diagnostic']=='WINDOWS_BACKEND_UNVERIFIED' and not (parent/'absent.marker').exists()
        print(json.dumps({'unsupportedPlatformRefused':True}));return
    root=Path(tempfile.mkdtemp(prefix='ordinary-output-',dir=parent));cases=[]
    who=subprocess.run(['whoami','/user','/fo','csv','/nh'],capture_output=True,check=True,timeout=15)
    sid=next(csv.reader(who.stdout.decode('utf-8',errors='replace').splitlines()))[-1]
    assert sid.startswith('S-1-5-') and all(v.isdigit() for v in sid[2:].split('-'))
    p=subprocess.run(['icacls',str(root),'/inheritance:r','/grant:r','*'+sid+':(OI)(CI)F'],capture_output=True,check=True,timeout=15);(root/'root-policy.private.txt').write_bytes(p.stdout+p.stderr)
    try:
        cases.append(trial(binary,root,'normal'))
        for role,phase in [('source','source-guarded'),('candidate','candidate-flushed')]:
            for action in ['read','write','delete','rename']:
                cases.append(trial(binary,root,role+'-held-'+action,action,role,phase))
            for action in ['mtime','readonly','ads','link','dacl']:
                cases.append(trial(binary,root,role+'-property-'+action,action,role))
        for role in ['source','candidate']:
            # Candidate is now named output at the installed observation barrier.
            cases.append(trial(binary,root,role+'-late-mtime','mtime',role if role=='source' else 'output','published'))
            cases.append(trial(binary,root,role+'-alias-write','link-write',role))
        cases.append(trial(binary,root,'held-root-rename','root-rename'))
        cases.append(trial(binary,root,'between-checks-mtime','mtime','source','before-namespace-call'))
        cases.append(trial(binary,root,'collision',phase='before-namespace-call'))
        for phase in PHASES:
            for stop in ['cancel','fail','kill']:cases.append(trial(binary,root,stop+'-'+phase,phase=phase,stop=stop))
        for post in ['read','write','mtime']:
            cases.append(trial(binary,root,'post-exit-'+post,post=post))
        for change in ['record-corrupt','extra','remove-record']:
            cases.append(trial(binary,root,change,inspect_change=change))
        for kind in ['writable-handle','writable-map','readonly-map']:
            case=root/('preexisting-'+kind);case.mkdir();transaction=case/'transaction.marker'
            code,_=invoke(binary,transaction,'ordinary-prepare',case/'prepare');assert code==0
            handle=(transaction/'source.marker').open('rb' if kind=='readonly-map' else 'r+b');mapping=None
            try:
                if kind.endswith('map'):
                    mapping=mmap.mmap(handle.fileno(),0,access=mmap.ACCESS_READ if kind=='readonly-map' else mmap.ACCESS_WRITE);handle.close()
                p=Process([binary,transaction,'ordinary'],case/'worker')
                try:
                    if kind=='readonly-map':
                        assert p.next()['barrier']=='source-guarded';p.controls.append('cancel');p.proc.stdin.write('cancel\n');p.proc.stdin.flush()
                    code=p.finish();events=[json.loads(v) for v in p.lines]
                    if kind=='readonly-map':assert code==0 and events[-1]['outcome']=='cancelled-before-publication'
                    else:assert code==5 and not events
                    assert sorted(v.name for v in transaction.iterdir())==['source.marker']
                    cases.append({'id':'preexisting-'+kind,'guardRefused':kind!='readonly-map','compatibleReadMap':kind=='readonly-map','sourceRetained':True,'outputPresent':False})
                finally:
                    p.stop();p.timer.cancel()
                    if not p.capture.exists():p.finish()
            finally:
                if mapping is not None:mapping.close()
                if not handle.closed:handle.close()
        for kind,size in [('short',65535),('long',65536)]:
            case=root/('injected-'+kind+'-stream');case.mkdir();transaction=case/'transaction.marker'
            code,_=invoke(binary,transaction,'ordinary-prepare',case/'prepare');assert code==0
            p=Process([binary,transaction,'ordinary-'+kind+'-source'],case/'worker')
            assert p.next()['barrier']=='source-guarded';p.send();assert p.finish()==0
            terminal=json.loads(p.lines[-1]);assert terminal['cleanupPending'] and not terminal['publicationAttempted']
            assert (transaction/'candidate.marker').read_bytes()==b'3'*size and not (transaction/'prepared.record').exists() and not (transaction/'output.marker').exists()
            cases.append({'id':case.name,'terminal':terminal,'partialStageBytes':size,'sourceRetained':True,'outputPresent':False,'injection':'producer-stream-shape-not-OS-error'})
        for mode in ['ordinary-admit','ordinary-finalize','ordinary-prune']:
            case=root/mode;case.mkdir();code,events=invoke(binary,case/'absent.marker',mode,case/'worker');assert code==0 and events[0]['outcome']=='refused-before-effects' and not (case/'absent.marker').exists()
            cases.append({'id':mode,'refusedBeforeEffects':True})
        report={'schemaVersion':1,'caseCount':len(cases),'cases':cases,'productionPublicationAllowed':False,'enabledProfiles':0}
        (root/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps({'root':str(root),'caseCount':len(cases)}))
    except BaseException:
        (root/'failed-report.private.json').write_text(json.dumps(cases,indent=2),encoding='utf-8');print('Retained attempt: '+str(root),file=sys.stderr);raise
if __name__=='__main__':
    if not __debug__:raise RuntimeError('Qualification requires assertions')
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--binary',required=True);p.add_argument('--parent',required=True);a=p.parse_args();run(a.binary,a.parent)
