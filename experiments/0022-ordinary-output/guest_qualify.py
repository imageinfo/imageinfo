"""Exercise only the private Windows guest; never signal/reboot the Windows host."""
import argparse,datetime,json,os,pathlib,re,signal,subprocess,time,urllib.request
from windows_guest import Qmp, start_agent
BASE='http://127.0.0.1:18722'
PHASES=['source-guarded','candidate-flushed','prepared-record-flushed','intent-record-flushed','before-property-check','before-namespace-call','published','observed-record-flushed']
def state():return json.load(urllib.request.urlopen(BASE+'/state',timeout=10))
def queue(job):
    request=urllib.request.Request(BASE+'/queue',data=json.dumps(job).encode(),headers={'Content-Type':'application/json'})
    return json.load(urllib.request.urlopen(request,timeout=10))
def wait_event(predicate,timeout=240):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        for entry in reversed(state()):
            if predicate(entry):return entry
        time.sleep(1)
    raise TimeoutError('Guest event deadline')
def job(identifier,case,mode,stop=None):
    value={'id':identifier,'action':'run','case':case,'mode':mode}
    if stop:value['stopAt']=stop
    queue(value)
    if stop:return wait_event(lambda e:e['path']=='/event' and e['value'].get('id')==identifier and e['value']['event'].get('barrier')==stop)
    return wait_event(lambda e:e['path']=='/result' and e['value'].get('id')==identifier)['value']
def hello():
    return next(e for e in reversed(state()) if e['path']=='/hello')
def rebooted(previous,fault_time):
    # Searching historical hello messages can otherwise return an older boot.
    return wait_event(lambda e:e['path']=='/hello' and e['at']>fault_time and abs(datetime.datetime.fromisoformat(e['value']['boot']).timestamp()-datetime.datetime.fromisoformat(previous['value']['boot']).timestamp())>5)
def verify_guest_token(value):
    groups='\n'.join(value['groups']) if isinstance(value['groups'],list) else value['groups']
    if 'S-1-5-32-544' in groups or 'S-1-16-8192' not in groups:raise RuntimeError('Guest worker is not an ordinary medium-integrity user')
def assert_reports(result):
    if result['exitCode']!=0:raise RuntimeError(result.get('stderr'))
    events=[json.loads(v) for v in result['stdout']]
    assert all(not v['committed'] and not v['namespaceAcknowledged'] and not v['productionPublicationAllowed'] and not v['repairAllowed'] for v in events)
    return events
def fresh_bugcheck(event,barrier_time):
    if event.get('Id')!=1001 or not re.search(r'0x0*80\b',event.get('Message',''),re.I):return False
    stamp=str(event.get('TimeCreated',''));match=re.search(r'Date\((\d+)',stamp)
    when=int(match[1])/1000 if match else datetime.datetime.fromisoformat(stamp.replace('Z','+00:00')).timestamp()
    return when>=barrier_time-5
def relaunch(root,folder):
    launcher=pathlib.Path(__file__).with_name('windows_guest.py').resolve()
    p=subprocess.run(['/mnt/c/Windows/System32/wsl.exe','-u','root','-e','python3',str(launcher),'launch','--root',str(root)],capture_output=True,timeout=40)
    (folder/'relaunch.private.json').write_text(json.dumps({'exitCode':p.returncode,'stdout':p.stdout.decode('utf-8',errors='replace'),'stderr':p.stderr.decode('utf-8',errors='replace')}))
    if p.returncode:raise RuntimeError('Guest relaunch failed')
    # This fixture's ordinary logon Run item can be delayed after a crash. Start
    # the same mutex-protected user agent through QMP after the boot interval.
    time.sleep(30);start_agent(root)
def run(root,kinds,phases):
    root=pathlib.Path(root).resolve();manifest=json.loads((root/'guest.private.json').read_text())
    if manifest['root']!=str(root) or manifest['uid']!=os.getuid():raise RuntimeError('Guest root/operator mismatch')
    initial=hello();verify_guest_token(initial['value']);captures=root/('qualification-'+str(int(time.time())));captures.mkdir();cases=[]
    (captures/'initial-hello.private.json').write_text(json.dumps(initial,indent=2))
    # Normal exit verifies this exact guest binary/kernel/owner policy before faults.
    case='normal-'+str(int(time.time()));prepared=job(case+'-prepare',case,'ordinary-prepare');assert_reports(prepared)
    result=job(case+'-run',case,'ordinary');events=assert_reports(result);assert events[-1]['outcome']=='recovery-required' and events[-1]['installedCheckPassed']
    inspection=job(case+'-inspect',case,'ordinary-inspect');assert assert_reports(inspection)[0]['outcome']=='matching-output-recovery-required'
    (captures/'normal.private.json').write_text(json.dumps({'prepare':prepared,'run':result,'inspect':inspection},indent=2));cases.append({'id':'normal','outcome':'matching-output-recovery-required','committed':False})
    print(json.dumps({'guest':'normal-passed','build':initial['value']['build']}),flush=True)
    try:
        for kind in kinds:
            for phase in phases:
                identifier=kind+'-'+phase;case=identifier+'-'+str(int(time.time()));before=hello();verify_guest_token(before['value'])
                prepared=job(case+'-prepare',case,'ordinary-prepare');assert_reports(prepared)
                reached=job(case+'-run',case,'ordinary',phase)
                # Serialize the reached barrier before any fault is injected.
                folder=captures/identifier;folder.mkdir();(folder/'before.private.json').write_text(json.dumps({'hello':before,'prepare':prepared,'barrier':reached},indent=2))
                fault_time=time.time();q=Qmp(root)
                if kind=='nmi':
                    q.call('inject-nmi');time.sleep(12)
                    q.call('screendump',{'filename':str(folder/'bugcheck.png'),'format':'png'})
                    (folder/'qmp-status.private.json').write_text(json.dumps(q.call('query-status')))
                    # Nested KVM warm reset stalled a retained preliminary run.
                    # Capture the actual Windows bugcheck, then perform a separate
                    # controlled emulator restart; host caches remain alive.
                    q.call('quit');q.close();time.sleep(2);relaunch(root,folder)
                elif kind=='emulator-kill':
                    q.close();pid=int((root/'qemu.pid').read_text());cmd=pathlib.Path(f'/proc/{pid}/cmdline').read_bytes()
                    if b'qemu-system-x86_64' not in cmd or str(root/'windows.qcow2').encode() not in cmd:raise RuntimeError('Refuse to signal unrelated PID')
                    os.kill(pid,signal.SIGKILL);time.sleep(2)
                    relaunch(root,folder)
                else:raise ValueError('Unsupported guest fault kind')
                after=rebooted(before,fault_time);verify_guest_token(after['value'])
                inspection=job(case+'-inspect',case,'ordinary-inspect');report=assert_reports(inspection)[0]
                queue({'id':case+'-events','action':'events'});os_events=wait_event(lambda e:e['path']=='/result' and e['value'].get('id')==case+'-events')['value']
                (folder/'after.private.json').write_text(json.dumps({'hello':after,'inspect':inspection,'osEvents':os_events},indent=2))
                captured=state();(folder/'controller-events.private.json').write_text(json.dumps([v for v in captured if v['value'].get('id') in [case+'-run',case+'-inspect']],indent=2))
                # No source/record phase authorizes repair, even on exact matches.
                assert report['outcome'] in ['unattributed-artifacts','candidate-retained-output-absent','matching-output-recovery-required','candidate-missing-or-conflicting','source-conflict','uninspectable']
                event_list=os_events.get('events') or []
                if isinstance(event_list,dict):event_list=[event_list]
                bugcheck=any(fresh_bugcheck(v,reached['at']) for v in event_list)
                if kind=='nmi' and not bugcheck:raise RuntimeError('NMI lacks Windows bugcheck event evidence')
                record={'id':identifier,'faultKind':kind,'restartMethod':'controlled-emulator-restart' if kind=='nmi' else 'restart-after-emulator-sigkill','barrier':phase,'bootChanged':True,'windowsBugcheckEventObserved':bugcheck,'inspection':report['outcome'],'outputPresent':report.get('outputPresent'),'committed':False}
                cases.append(record);print(json.dumps(record),flush=True)
        summary={'schemaVersion':1,'observedOn':'2026-10-14','cases':cases,'caseCount':len(cases),'guestBuild':initial['value']['build'],'guestVersion':initial['value']['version'],'standardWorkerToken':True,'physicalPowerLossRuns':0,'hostCrashed':False,'committed':False,'productionPublicationAllowed':False,'enabledProfiles':0}
        (captures/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps({'captures':str(captures),'caseCount':len(cases)}),flush=True)
    except BaseException:
        (captures/'failed-summary.private.json').write_text(json.dumps(cases,indent=2));print('Retained guest attempt: '+str(captures),flush=True);raise

if __name__=='__main__':
    if not __debug__:raise RuntimeError('Qualification requires assertions')
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True);p.add_argument('--kinds',default='nmi,emulator-kill');p.add_argument('--phases',default=','.join(PHASES));a=p.parse_args();run(a.root,a.kinds.split(','),a.phases.split(','))
