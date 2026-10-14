"""Caller-held restart contexts across faults in the existing disposable guest."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import time
from guest_qualify import (hello, verify_guest_token, job, queue, wait_event, state,
                          assert_reports, rebooted, relaunch, fresh_bugcheck)
from windows_guest import Qmp

HASH = hashlib.sha256(b'3' * 65536).hexdigest()


def faults(root, capture, kind, before, barrier):
    started = time.time();q = Qmp(root)
    if kind == 'nmi':
        q.call('inject-nmi');time.sleep(12)
        q.call('screendump', {'filename': str(capture/'bugcheck.png'), 'format': 'png'})
        q.call('quit');q.close();time.sleep(2)
    else:
        q.close();pid = int((root/'qemu.pid').read_text());cmd = Path(f'/proc/{pid}/cmdline').read_bytes()
        if b'qemu-system-x86_64' not in cmd or str(root/'windows.qcow2').encode() not in cmd:
            raise RuntimeError('Refuse unrelated process')
        os.kill(pid, signal.SIGKILL);time.sleep(2)
    relaunch(root, capture);after = rebooted(before, started);verify_guest_token(after['value'])
    identifier = 'events-' + str(int(time.time()))
    queue({'id': identifier, 'action': 'events'})
    events = wait_event(lambda e:e['path']=='/result' and e['value'].get('id')==identifier)['value']
    items = events.get('events') or []
    if isinstance(items, dict):items = [items]
    fresh = [e for e in items if fresh_bugcheck(e, barrier['at'])]
    assert bool(fresh) == (kind == 'nmi')
    (capture/'reboot.private.json').write_text(json.dumps({'before':before,'after':after,'events':events,'fault':kind,'barrier':barrier}, indent=2))
    return after


def context(identifier):
    return next(e['value']['event']['callerContext'] for e in reversed(state()) if e['path']=='/event' and e['value'].get('id')==identifier and 'callerContext' in e['value']['event'])


def action(case, mode, caller, stop=None):
    identifier = case+'-'+mode+'-'+str(int(time.time()))
    request = {'id':identifier,'action':'run','case':case,'mode':mode,'callerContext':caller}
    if stop:request['stopAt'] = stop
    queue(request)
    if stop:
        reached = wait_event(lambda e:e['path']=='/event' and e['value'].get('id')==identifier and e['value']['event'].get('barrier')==stop)
        return identifier, reached
    result = wait_event(lambda e:e['path']=='/result' and e['value'].get('id')==identifier)['value']
    assert_reports(result)
    return identifier, result


def prepare(root, captures, name, live_phase, kind):
    case = name+'-'+str(int(time.time()));folder = captures/name;folder.mkdir()
    before = hello();verify_guest_token(before['value'])
    prepared = job(case+'-prepare', case, 'ordinary-prepare');assert_reports(prepared)
    identifier = case+'-live'
    barrier = job(identifier, case, 'ordinary-write-through', live_phase)
    caller = context(identifier)
    assert not caller['stoppedBeforePublication']
    (folder/'live.private.json').write_text(json.dumps({'case':case,'prepare':prepared,'barrier':barrier,'callerContext':caller}, indent=2))
    faults(root, folder, kind, before, barrier)
    # This assertion is supplied by the supervisor only after the live child
    # is gone, and only when no publication-barrier continuation was ever sent.
    if live_phase == 'before-namespace-call':caller['stoppedBeforePublication'] = True
    return case, folder, caller


def run(root):
    root = Path(root).resolve();manifest=json.loads((root/'guest.private.json').read_text())
    if manifest['root']!=str(root) or manifest['uid']!=os.getuid():raise RuntimeError('Guest root/operator mismatch')
    captures=root/('restart-'+str(int(time.time())));captures.mkdir();rows=[]
    (captures/'initial-hello.private.json').write_text(json.dumps(hello(),indent=2))
    try:
        case, folder, caller=prepare(root,captures,'unpublished-nmi','before-namespace-call','nmi')
        _, result=action(case,'ordinary-restart-prune',caller)
        terminal=assert_reports(result)[-1]
        assert terminal['outcome']=='owned-unpublished-handles-pruned' and terminal['ownedHandlesRemoved']==3
        assert [f['name'] for f in result['files']]==['source.marker'] and result['files'][0]['sha256']==HASH
        (folder/'action.private.json').write_text(json.dumps({'caller':caller,'result':result},indent=2));rows.append({'id':'unpublished-nmi','outcome':terminal['outcome'],'removed':3})

        case, folder, caller=prepare(root,captures,'published-nmi','parent-flushed','nmi')
        before=hello();identifier, barrier=action(case,'ordinary-restart-observe',caller,'restart-record-file-flushed')
        renewed=context(identifier)
        assert renewed['stage']=='after-publication' and len(renewed['records'])==3 and not renewed['stoppedBeforePublication']
        (folder/'recovery-context.private.json').write_text(json.dumps({'caller':caller,'renewed':renewed,'barrier':barrier},indent=2))
        recovery=folder/'recovery-fault';recovery.mkdir();faults(root,recovery,'emulator-kill',before,barrier)
        _, stale=action(case,'ordinary-restart-observe',caller)
        assert assert_reports(stale)[-1]['outcome']=='restart-refused-before-effects'
        _, existing=action(case,'ordinary-restart-observe',renewed)
        assert assert_reports(existing)[-1]['outcome']=='output-observation-already-present'
        assert stale['files']==existing['files']
        _, prune=action(case,'ordinary-restart-prune',renewed)
        assert assert_reports(prune)[-1]['outcome']=='restart-refused-before-effects' and prune['files']==existing['files']
        files={f['name']:f for f in existing['files']};assert files['source.marker']['sha256']==files['output.marker']['sha256']==HASH
        (folder/'action.private.json').write_text(json.dumps({'stale':stale,'existing':existing,'prune':prune},indent=2));rows.append({'id':'published-nmi-recovery-kill','outcome':'output-observation-already-present','staleContextRefused':True,'postpublicationPruneRefused':True})

        case, folder, caller=prepare(root,captures,'unpublished-kill','before-namespace-call','emulator-kill')
        before=hello();_, barrier=action(case,'ordinary-restart-prune',caller,'restart-file-removed')
        recovery=folder/'recovery-fault';recovery.mkdir();faults(root,recovery,'nmi',before,barrier)
        _, retry=action(case,'ordinary-restart-prune',caller)
        report=assert_reports(retry)[-1]
        assert report['outcome'] in ['restart-refused-before-effects','owned-unpublished-handles-pruned']
        files={f['name']:f for f in retry['files']};assert files['source.marker']['sha256']==HASH and 'output.marker' not in files
        if report['outcome']=='restart-refused-before-effects':assert report['ownedHandlesRemoved']==0 and not report['effectsAttempted']
        else:assert sorted(files)==['source.marker']
        (folder/'action.private.json').write_text(json.dumps({'caller':caller,'retry':retry},indent=2));rows.append({'id':'unpublished-kill-recovery-nmi','outcome':report['outcome'],'sourceRetained':True})
        (captures/'summary.private.json').write_text(json.dumps({'cases':rows,'liveFaults':3,'recoveryFaults':2,'nmiFaults':3,'emulatorTerminationFaults':2,'committed':False,'productionPublicationAllowed':False},indent=2))
        print(json.dumps({'captures':str(captures),'cases':rows}),flush=True)
    except BaseException:
        (captures/'incomplete.private.json').write_text(json.dumps(rows,indent=2));print('Retained incomplete run '+str(captures),flush=True);raise


if __name__=='__main__':
    if not __debug__:raise RuntimeError('Qualification requires assertions')
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True);a=p.parse_args();run(a.root)
