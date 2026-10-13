"""Owned marker source-oplock actors; no media, ACL repair or publication."""
import argparse
import csv
import json
import os
import platform
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import time

HERE = Path(__file__).resolve().parent
ACTOR = HERE / 'actor.py'


class Process:
    def __init__(self, argv, capture):
        self.argv = [str(v) for v in argv]
        self.capture = capture
        self.lines = []
        self.messages = queue.Queue()
        self.stderr = []
        self.controls = []
        self.proc = subprocess.Popen(self.argv, stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     text=True, encoding='utf-8')
        self.timer = threading.Timer(60, self.stop)
        self.timer.start()
        self.reader = threading.Thread(target=self.read, daemon=True)
        self.reader.start()
        self.err_reader = threading.Thread(target=self.read_err, daemon=True)
        self.err_reader.start()

    def read(self):
        for line in self.proc.stdout:
            self.lines.append(line)
            self.messages.put(json.loads(line))
        self.messages.put(None)

    def read_err(self):
        self.stderr.extend(self.proc.stderr)

    def next(self):
        result = self.messages.get(timeout=15)
        if result is None:
            raise RuntimeError('Unexpected process EOF: ' + ''.join(self.stderr))
        return result

    def send(self):
        self.controls.append('continue')
        self.proc.stdin.write('continue\n')
        self.proc.stdin.flush()

    def stop(self):
        if self.proc.poll() is None:
            self.proc.kill()

    def finish(self):
        try:
            code = self.proc.wait(timeout=15)
        finally:
            self.stop()
            self.timer.cancel()
        self.reader.join(timeout=3)
        self.err_reader.join(timeout=3)
        self.capture.mkdir(parents=True, exist_ok=False)
        (self.capture/'argv.private.json').write_text(json.dumps(self.argv), encoding='utf-8')
        (self.capture/'stdout.jsonl').write_text(''.join(self.lines), encoding='utf-8')
        (self.capture/'stderr.jsonl').write_text(''.join(self.stderr), encoding='utf-8')
        (self.capture/'exit.json').write_text(json.dumps({'exitCode': code}), encoding='utf-8')
        (self.capture/'controls.json').write_text(json.dumps(self.controls), encoding='utf-8')
        self.proc.stdin.close()
        self.proc.stdout.close()
        self.proc.stderr.close()
        return code


def invoke(binary, mode, marker, capture):
    p = Process([binary, mode, marker], capture)
    code = p.finish()
    return code, [json.loads(line) for line in p.lines]


def trial(binary, root, mode, actor_name, preopen=False, kill=False):
    case_id = '-'.join([mode, 'preopen' if preopen else 'new',
                        'name', actor_name,
                        'kill' if kill else 'release'])
    case = root/case_id
    case.mkdir()
    marker = case/'source.marker'
    code, prepared = invoke(binary, 'prepare', marker, case/'prepare')
    assert code == 0 and prepared[0]['outcome'] == 'owned-marker-prepared'
    target = marker
    actor = None
    worker = None
    try:
        if preopen:
            actor = Process([sys.executable, ACTOR, 'preopen-'+actor_name, target], case/'actor')
            assert actor.next()['preopened']
        worker = Process([binary, mode, marker], case/'worker')
        first = worker.next()
        if first['outcome'] == 'source-guard-refused':
            assert preopen and actor_name == 'dacl' and mode in ['rw', 'rwh']
            assert first['winError'] == 300
            assert worker.finish() == 0
            actor.send()
            assert actor.finish() == 0
            return {'id': case_id, 'mode': mode, 'actor': actor_name,
                    'preopened': True, 'guardRefused': True, 'winError': 300,
                    'actorResult': [json.loads(line) for line in actor.lines][-1]}
        assert first['outcome'] == 'source-held'
        assert worker.next()['barrier'] == 'held'
        if actor is None:
            actor = Process([sys.executable, ACTOR, actor_name, target], case/'actor')
        else:
            actor.send()
        # Polling observes liveness; it does not promise a native operation
        # deadline. A 1-second quiet interval distinguishes pending actors.
        deadline = time.monotonic()+1
        while actor.proc.poll() is None and time.monotonic() < deadline:
            time.sleep(.01)
        completed_while_held = actor.proc.poll() is not None
        worker.send()
        observed = worker.next()
        assert observed['outcome'] == 'held-source-observed'
        assert worker.next()['barrier'] == 'observed'
        if kill:
            worker.stop()
        else:
            worker.send()
            assert worker.next()['outcome'] == 'holder-released'
        worker_code = worker.finish()
        assert kill or worker_code == 0
        actor_code = actor.finish()
        assert actor_code == 0
        actor_result = [json.loads(line) for line in actor.lines][-1]
        assert observed['contentUnchanged'] and observed['identityUnchanged']
        # Pin independent expected observations, not just successful execution.
        if actor_name in ['mtime', 'readonly', 'ads', 'link', 'link-mtime', 'link-ads']:
            assert completed_while_held and actor_result['allowed']
            assert not observed['oplock']['broken']
        if actor_name in ['mtime', 'link-mtime']:
            assert not observed['mtimeUnchanged']
        if actor_name == 'readonly':
            assert not observed['attributesUnchanged']
        if actor_name in ['ads', 'link-ads']:
            assert not observed['defaultStreamOnly']
        if actor_name.startswith('link'):
            assert observed['linkCount'] == 2
        if actor_name == 'dacl' and mode == 'sharing':
            assert not observed['securityUnchanged']
        if not completed_while_held:
            assert observed['oplock']['broken'] and observed['oplock']['ackRequired']
        return {'id': case_id, 'mode': mode, 'actor': actor_name,
                'preopened': preopen, 'workerKilled': kill,
                'completedWhileHeld': completed_while_held,
                'actorResult': actor_result, 'observed': observed}
    finally:
        for p in [worker, actor]:
            if p is not None:
                p.stop()
                p.timer.cancel()
                if not p.capture.exists():
                    p.finish()


def run(binary, parent, smoke=False):
    binary = Path(binary).resolve()
    parent = Path(parent).resolve()
    parent.mkdir(parents=True, exist_ok=True)
    if os.name != 'nt':
        # The executable must refuse before creating worker artifacts.
        p = subprocess.run([binary, 'admit', 'unused.marker'], capture_output=True,
                           text=True, timeout=15, encoding='utf-8')
        assert p.returncode == 5
        assert json.loads(p.stderr)['diagnostic'] == 'SOURCE_OPLOCK_WINDOWS_UNVERIFIED'
        print(json.dumps({'unsupportedPlatformRefused': True}))
        return
    root = Path(tempfile.mkdtemp(prefix='source-oplocks-', dir=parent))
    # Apply the owner-only capture policy only to this newly created empty root.
    # SID and command output stay private and are never added to public results.
    identity = subprocess.run(['whoami', '/user', '/fo', 'csv', '/nh'],
                              capture_output=True, check=True, timeout=15)
    sid = next(csv.reader(identity.stdout.decode('utf-8', errors='replace').splitlines()))[-1]
    assert sid.startswith('S-1-5-') and all(v.isdigit() for v in sid[2:].split('-'))
    policy = subprocess.run(['icacls', str(root), '/inheritance:r', '/grant:r',
                             '*'+sid+':(OI)(CI)F'], capture_output=True, check=True, timeout=15)
    (root/'root-policy.private.txt').write_bytes(policy.stdout+policy.stderr)
    (root/'environment.private.json').write_text(json.dumps({
        'platform': platform.platform(), 'python': sys.version,
        'rustc': subprocess.run(['rustc', '--version'], capture_output=True, check=True, text=True, timeout=15).stdout.strip(),
        'markerBytes': 65536, 'requestedLevels': {'rh': 3, 'rw': 5, 'rwh': 7},
        'processWatchdogSeconds': 60, 'actorObservationSeconds': 1,
        'osCrashRuns': 0, 'physicalPowerLossRuns': 0}, indent=2), encoding='utf-8')
    cases = []
    try:
        actors = ['read', 'mtime', 'readonly', 'dacl', 'owner-access', 'ads',
                  'write', 'link', 'delete', 'rename']
        for mode in ['sharing', 'rh', 'rw', 'rwh']:
            for actor in (['mtime'] if smoke else actors):
                cases.append(trial(binary, root, mode, actor))
        if not smoke:
            for mode in ['sharing', 'rh', 'rw', 'rwh']:
                for actor in ['link-mtime', 'link-dacl', 'link-ads', 'link-write']:
                    cases.append(trial(binary, root, mode, actor))
            for mode in ['rh', 'rw', 'rwh']:
                for actor in ['mtime', 'dacl']:
                    cases.append(trial(binary, root, mode, actor, preopen=True))
                cases.append(trial(binary, root, mode, 'write', kill=True))
            admit_dir = root/'admit'
            admit_dir.mkdir()
            code, events = invoke(binary, 'admit', admit_dir/'absent.marker', admit_dir/'worker')
            assert code == 0 and events[0]['outcome'] == 'refused-before-effects'
            assert not (admit_dir/'absent.marker').exists()
            cases.append({'id': 'admit', 'refusedBeforeEffects': True})
            for mode in ['sharing', 'rh', 'rw', 'rwh']:
                case = root/(mode+'-preexisting-alias')
                case.mkdir()
                marker = case/'source.marker'
                assert invoke(binary, 'prepare', marker, case/'prepare')[0] == 0
                os.link(marker, case/'alias.marker')
                code, _ = invoke(binary, mode, marker, case/'worker')
                assert code == 5
                diagnostic = json.loads((case/'worker'/'stderr.jsonl').read_text())
                assert diagnostic['diagnostic'] == 'SOURCE_SHAPE_UNVERIFIED'
                cases.append({'id': case.name, 'refusedBeforeGuard': True})
            for suffix in ['../source.marker', 'source.marker:probe', 'CON.marker', 'source.marker.', 'source?.marker']:
                case = root/('path-'+str(len(cases)))
                case.mkdir()
                code, _ = invoke(binary, 'rh', str(case)+'/'+suffix, case/'worker')
                assert code == 5
                diagnostic = json.loads((case/'worker'/'stderr.jsonl').read_text())
                assert diagnostic['diagnostic'] == 'MARKER_PATH_UNVERIFIED'
                assert list(case.iterdir()) == [case/'worker']
                cases.append({'id': case.name, 'refusedBeforeOpen': True})
        report = {'schemaVersion': 1, 'caseCount': len(cases), 'cases': cases,
                  'productionPublicationAllowed': False, 'existingSourcePropertiesSetByHolder': False}
        (root/'report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
        print(json.dumps({'root': str(root), 'caseCount': len(cases)}))
    except BaseException:
        (root/'failed-report.private.json').write_text(json.dumps(cases, indent=2), encoding='utf-8')
        print('Retained failed attempt: '+str(root), file=sys.stderr)
        raise


if __name__ == '__main__':
    if not __debug__:
        raise RuntimeError('Qualification assertions require Python without -O')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', required=True)
    parser.add_argument('--parent', required=True)
    parser.add_argument('--smoke', action='store_true')
    args = parser.parse_args()
    run(args.binary, args.parent, args.smoke)
