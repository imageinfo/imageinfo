"""Compare held-object publication/flush ordering using only disposable markers."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from qualify import trial, invoke, inventory
from guest_qualify import (hello, verify_guest_token, job, assert_reports, queue,
                          wait_event, state, rebooted, relaunch, fresh_bugcheck)
from windows_guest import Qmp

MODES = {'buffered': 'ordinary-persistence-buffered',
         'flush-after-rename': 'ordinary-flush-after-rename',
         'write-through': 'ordinary-write-through'}
PHASES = ['published', 'installed-file-flushed', 'parent-flushed',
          'observation-file-flushed', 'observation-parent-flushed']
SOURCE_HASH = hashlib.sha256(b'3' * 65536).hexdigest()


def native(binary, parent):
    binary, parent = Path(binary).resolve(), Path(parent).resolve()
    parent.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix='persistence-', dir=parent))
    if os.name != 'nt':
        for mode in MODES.values():
            p = subprocess.run([binary, root / 'absent.marker', mode], capture_output=True, text=True, timeout=15)
            assert p.returncode == 5 and json.loads(p.stderr)['diagnostic'] == 'WINDOWS_BACKEND_UNVERIFIED'
            assert not (root / 'absent.marker').exists()
        print(json.dumps({'unsupportedAdapterRefused': True}));return
    cases = []
    for label, mode in MODES.items():
        folder = root / label;folder.mkdir()
        cases.append(trial(binary, folder, 'normal', mode=mode))
        terminal = cases[-1]['terminal']
        assert terminal['persistenceMode'] == label
        assert all(terminal[k] for k in ['installedFileFlushSucceeded', 'parentFlushSucceeded', 'observationFileFlushSucceeded', 'observationParentFlushSucceeded'])
        for name, action, role, phase in [
            ('source-data', 'write', 'source', 'source-guarded'),
            ('candidate-data', 'write', 'candidate', 'candidate-flushed'),
            ('source-time', 'mtime', 'source', 'before-property-check'),
            ('late-output-time', 'mtime', 'output', 'published'),
            ('collision', None, 'source', 'before-namespace-call'),
        ]:
            cases.append(trial(binary, folder, name, action=action, role=role, phase=phase, mode=mode))
        cases.append(trial(binary, folder, 'early-cancel', phase='intent-record-flushed', stop='cancel', mode=mode))
        cases.append(trial(binary, folder, 'owner-edit', post='write', mode=mode))
        for phase in PHASES:
            for stop in ['cancel', 'fail', 'kill']:
                cases.append(trial(binary, folder, stop + '-' + phase, phase=phase, stop=stop, mode=mode))
        # A valid checksum/request label cannot make records from different
        # protocol variants agree. Inspector must reject them read-only.
        transaction = folder / 'normal' / 'transaction.marker'
        path = transaction / 'intent.record'
        envelope = json.loads(path.read_text());body = json.loads(envelope['body'])
        body['persistenceMode'] = 'write-through' if label != 'write-through' else 'flush-after-rename'
        envelope['body'] = json.dumps(body, separators=(',', ':'))
        envelope['sha256'] = hashlib.sha256(envelope['body'].encode()).hexdigest()
        path.write_text(json.dumps(envelope), encoding='utf-8')
        before = inventory(transaction)
        code, reports = invoke(binary, transaction, 'ordinary-inspect', folder / 'mixed-inspect')
        assert code == 0 and reports[0]['outcome'] == 'uninspectable' and reports[0]['diagnostic'] == 'RECORDS_DISAGREE'
        after = inventory(transaction)
        assert after == before
        (folder / 'mixed-inspection-inventory.private.json').write_text(json.dumps({'before': before, 'after': after}, indent=2), encoding='utf-8')
        for case in cases[-23:]:case['mode'] = label
    (root / 'summary.private.json').write_text(json.dumps({'cases': cases, 'caseCount': len(cases), 'mixedRecordRefusals': 3}, indent=2), encoding='utf-8')
    print(json.dumps({'captures': str(root), 'caseCount': len(cases), 'mixedRecordRefusals': 3}))


def guest(root, labels=None, kinds=None, phases=None):
    root = Path(root).resolve()
    manifest = json.loads((root / 'guest.private.json').read_text())
    if manifest['root'] != str(root) or manifest['uid'] != os.getuid():
        raise RuntimeError('Guest root/operator mismatch')
    initial = hello();verify_guest_token(initial['value'])
    captures = root / ('persistence-' + str(int(time.time())));captures.mkdir()
    (captures / 'initial-hello.private.json').write_text(json.dumps(initial, indent=2))
    cases = []
    try:
        for label in labels or list(MODES):
            mode = MODES[label]
            case = label + '-normal-' + str(int(time.time()))
            prepared = job(case + '-prepare', case, 'ordinary-prepare');assert_reports(prepared)
            worker = job(case + '-run', case, mode);terminal = assert_reports(worker)[-1]
            assert terminal['installedCheckPassed'] and terminal['persistenceMode'] == label
            inspection = job(case + '-inspect', case, 'ordinary-inspect')
            assert assert_reports(inspection)[0]['outcome'] == 'matching-output-recovery-required'
            (captures / (label + '-normal.private.json')).write_text(json.dumps({'prepare': prepared, 'run': worker, 'inspect': inspection}, indent=2))
            # Separate checkpoints identify the first observed persistence
            # boundary; a later matching receipt cannot qualify an earlier one.
            for kind in kinds or ['nmi', 'emulator-kill']:
                for phase in phases or PHASES:
                    identifier = label + '-' + kind + '-' + phase
                    # Keep the guest's checked case leaf below its 60-char limit.
                    case = 'persist-' + str(len(cases)) + '-' + str(int(time.time()))
                    before = hello();verify_guest_token(before['value'])
                    prepared = job(case + '-prepare', case, 'ordinary-prepare');assert_reports(prepared)
                    reached = job(case + '-run', case, mode, phase)
                    folder = captures / identifier;folder.mkdir()
                    (folder / 'before.private.json').write_text(json.dumps({'hello': before, 'prepare': prepared, 'barrier': reached, 'mode': mode}, indent=2))
                    fault_time = time.time();q = Qmp(root)
                    if kind == 'nmi':
                        q.call('inject-nmi');time.sleep(12)
                        q.call('screendump', {'filename': str(folder / 'bugcheck.png'), 'format': 'png'})
                        q.call('quit');q.close();time.sleep(2)
                    else:
                        q.close();pid = int((root / 'qemu.pid').read_text());cmd = Path(f'/proc/{pid}/cmdline').read_bytes()
                        if b'qemu-system-x86_64' not in cmd or str(root / 'windows.qcow2').encode() not in cmd:
                            raise RuntimeError('Refuse unrelated process')
                        import signal
                        os.kill(pid, signal.SIGKILL);time.sleep(2)
                    relaunch(root, folder)
                    after = rebooted(before, fault_time);verify_guest_token(after['value'])
                    inspection = job(case + '-inspect', case, 'ordinary-inspect');report = assert_reports(inspection)[0]
                    queue({'id': case + '-events', 'action': 'events'})
                    os_events = wait_event(lambda e: e['path'] == '/result' and e['value'].get('id') == case + '-events')['value']
                    events = os_events.get('events') or []
                    if isinstance(events, dict):events = [events]
                    fresh = [v for v in events if fresh_bugcheck(v, reached['at'])]
                    if kind == 'nmi' and not fresh:raise RuntimeError('Missing fresh NMI bugcheck evidence')
                    (folder / 'after.private.json').write_text(json.dumps({'hello': after, 'inspect': inspection, 'osEvents': os_events}, indent=2))
                    (folder / 'controller-events.private.json').write_text(json.dumps([e for e in state() if e['value'].get('id') == case + '-run'], indent=2))
                    files = {f['name']: f for f in inspection['files']}
                    assert files['source.marker']['sha256'] == SOURCE_HASH
                    for name in ['output.marker', 'candidate.marker']:
                        if name in files:assert files[name]['sha256'] == SOURCE_HASH and files[name]['size'] == 65536
                    row = {'mode': label, 'fault': kind, 'barrier': phase, 'restartMethod': 'controlled-emulator-restart' if kind == 'nmi' else 'restart-after-sigkill', 'inspection': report['outcome'], 'outputPresent': report['outputPresent'], 'records': report['recordCount'], 'windowsBugcheckObserved': bool(fresh), 'committed': False}
                    cases.append(row);print(json.dumps(row), flush=True)
        (captures / 'summary.private.json').write_text(json.dumps({'cases': cases, 'faultCaseCount': len(cases), 'normalRuns': len(labels or MODES)}, indent=2))
        print(json.dumps({'captures': str(captures), 'faultCaseCount': len(cases)}), flush=True)
    except BaseException:
        (captures / 'incomplete.private.json').write_text(json.dumps(cases, indent=2))
        print('Retained incomplete run: ' + str(captures), flush=True);raise


if __name__ == '__main__':
    if not __debug__:raise RuntimeError('Qualification requires assertions')
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=['native', 'guest']);p.add_argument('--binary');p.add_argument('--parent');p.add_argument('--root')
    p.add_argument('--modes', default=','.join(MODES));p.add_argument('--kinds', default='nmi,emulator-kill');p.add_argument('--phases', default=','.join(PHASES))
    args = p.parse_args()
    if args.mode == 'native':native(args.binary, args.parent)
    else:
        labels, kinds, phases = args.modes.split(','), args.kinds.split(','), args.phases.split(',')
        if not set(labels) <= set(MODES) or not set(kinds) <= {'nmi', 'emulator-kill'} or not set(phases) <= set(PHASES):raise ValueError('Unknown comparison cell')
        guest(args.root, labels, kinds, phases)
