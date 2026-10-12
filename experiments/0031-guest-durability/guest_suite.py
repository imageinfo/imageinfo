"""Isolated QEMU marker guests. Only regular image files, no host shares/network."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import shutil
import socket
import subprocess
import threading
import time

BARRIERS = ['staged','prepared','intent','validated-before-link','linked','output-flushed',
            'namespace-flushed','observation-file-flushed','observation-namespace-flushed']
FAULTS = ['recovery.bin','candidate','staged-namespace','prepared.record','prepared-namespace',
          'intent.record','intent-namespace','output','output-namespace','observation.record','observation-namespace']
ACTORS = {
    'missing-intent':'candidate-object-observed',
    'missing-records':'invalid-or-uninspectable-evidence',
    'corrupt-intent':'invalid-or-uninspectable-evidence',
    'oversized-intent':'invalid-or-uninspectable-evidence',
    'inaccessible-intent':'invalid-or-uninspectable-evidence',
    'symlink-intent':'invalid-or-uninspectable-evidence',
    'fifo-intent':'invalid-or-uninspectable-evidence',
    'corrupt-observation':'invalid-or-uninspectable-evidence',
    'missing-recovery':'invalid-or-uninspectable-evidence',
    'corrupt-recovery':'invalid-or-uninspectable-evidence',
    'inaccessible-root':'invalid-or-uninspectable-evidence',
    'missing-output':'expected-absence-observed',
    'foreign-output':'foreign-or-uninspectable-target',
    'corrupt-output':'foreign-or-uninspectable-target',
    'inaccessible-output':'foreign-or-uninspectable-target',
    'symlink-output':'foreign-or-uninspectable-target',
    'fifo-output':'foreign-or-uninspectable-target',
    'directory-output':'foreign-or-uninspectable-target',
    'extra-alias':'invalid-or-uninspectable-evidence',
}

def inventory(raw):
    parts = raw.split('IMAGEINFO_SNAPSHOT_BEGIN\n')[1:]
    assert len(parts) == 2
    # Kernel console messages can arrive between serial inventory lines. Exclude
    # only timestamped kernel lines; retain every artifact/shell diagnostic line.
    return [[line for line in part.split('IMAGEINFO_SNAPSHOT_END')[0].splitlines()
             if not re.match(r'^\[\s*\d+\.\d+\]',line)] for part in parts]

def retain_result(case, result):
    # Preserve completed case verdicts even if a later case or the host stops.
    temporary = case/'result.tmp'
    with temporary.open('w') as output:
        output.write(json.dumps(result,indent=2)+'\n')
        output.flush()
        os.fsync(output.fileno())
    temporary.replace(case/'result.json')
    print(json.dumps(result),flush=True)

class Guest:
    def __init__(self, build, disk, mode, capture, block_fault=False):
        if not __debug__:
            raise RuntimeError('Qualification assertions require Python without -O')
        self.capture = capture
        self.lines = []
        self.events = []
        self.queue = queue.Queue()
        self.controls = []
        self.qmp_path = str(capture.parent.parent/('q-'+hashlib.sha256(str(capture).encode()).hexdigest()[:12]+'.sock'))
        assert len(self.qmp_path) < 100 and disk.is_file() and not disk.is_symlink()
        disk_argument = str(disk)
        if block_fault:
            config = capture/'blkdebug.conf'
            # The measured first flush belongs to guest mount. Let it complete;
            # subsequent flushes fail in the worker's native storage path.
            config.write_text('[set-state]\nevent = "flush_to_disk"\nstate = "1"\nnew_state = "2"\n'
                              '[inject-error]\nevent = "flush_to_disk"\nstate = "2"\nerrno = "5"\nonce = "off"\n')
            disk_argument = f'blkdebug:{config}:{disk}'
        argv = ['qemu-system-x86_64','-nodefaults','-no-user-config','-machine','q35,accel=tcg',
                '-m','256','-smp','1','-display','none','-serial','stdio','-monitor','none',
                '-net','none','-qmp',f'unix:{self.qmp_path},server=on,wait=off',
                '-kernel',str(build/'kernel'),'-initrd',str(build/'initramfs.cpio.gz'),
                '-append',f'console=ttyS0 panic=-1 rdinit=/init-imageinfo imageinfo_disposable_guest=owned-marker-v1 imageinfo_mode={mode}',
                '-drive',f'file={disk_argument},format=raw,if=virtio,cache=writeback,werror=report,rerror=report','-no-reboot']
        (capture/'argv.json').write_text(json.dumps(argv))
        self.process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT, text=True)
        # A stalled/broken guest cannot keep an unbounded emulator alive.
        self.timer = threading.Timer(180, self.process.kill)
        self.timer.daemon = True
        self.timer.start()
        def read():
            for line in self.process.stdout:
                self.queue.put(line)
            self.queue.put(None)
        self.reader = threading.Thread(target=read,daemon=True)
        self.reader.start()
        deadline = time.monotonic()+20
        while not Path(self.qmp_path).exists():
            assert self.process.poll() is None and time.monotonic() < deadline
            time.sleep(0.01)
        self.qmp = socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        self.qmp.settimeout(20)
        self.qmp.connect(self.qmp_path)
        self.qmp_stream = self.qmp.makefile('rwb', buffering=0)
        assert 'QMP' in json.loads(self.qmp_stream.readline())
        self.command('qmp_capabilities')

    def command(self, name):
        self.qmp_stream.write((json.dumps({'execute':name})+'\n').encode())
        while True:
            reply = json.loads(self.qmp_stream.readline())
            if 'return' in reply:
                return reply
            if 'error' in reply:
                raise RuntimeError(reply)

    def send(self, word):
        self.controls.append(word)
        self.process.stdin.write(word+'\n')
        self.process.stdin.flush()

    def next(self, timeout=30):
        line = self.queue.get(timeout=timeout)
        if line is None:
            return None
        self.lines.append(line)
        if line.startswith('{'):
            event = json.loads(line)
            self.events.append(event)
            assert not event.get('committed',False) and not event.get('productionPublicationAllowed',False)
            return event
        return line

    def close(self, abrupt=False):
        if self.process.poll() is None:
            if abrupt:
                self.process.kill()
            else:
                # Emulator quit may add host/device cleanup flushes; distinct from
                # SIGKILL's guest power interruption, never called physical loss.
                try:
                    self.command('quit')
                except (OSError,ValueError):
                    pass
            self.process.wait(timeout=30)
        self.reader.join(timeout=5)
        while not self.queue.empty():
            line = self.queue.get_nowait()
            if line is not None:
                self.lines.append(line)
        self.qmp_stream.close()
        self.qmp.close()
        self.timer.cancel()
        (self.capture/'serial.log').write_text(''.join(self.lines))
        (self.capture/'controls.json').write_text(json.dumps(self.controls))
        (self.capture/'events.json').write_text(json.dumps(self.events))

def inspect(build,disk,capture,mode='inspect'):
    guest = Guest(build,disk,mode,capture)
    observation = None
    try:
        while True:
            item = guest.next(timeout=60)
            assert item is not None
            if isinstance(item,dict) and 'classification' in item:
                observation = item
            elif 'IMAGEINFO_INSPECTION_DONE' in item:
                break
        assert observation and not observation['committed']
        refusals = [event for event in guest.events if event.get('outcome') == 'refused-before-mutation']
        assert len(refusals) == 3 and all(event['authorizedActions'] == [] for event in refusals)
        snapshots = inventory(''.join(guest.lines))
        assert snapshots[0] == snapshots[1]
        return observation
    finally:
        guest.close()

def run(build,parent):
    import tempfile
    build = Path(build).resolve()
    parent = Path(parent).resolve()
    parent.mkdir(parents=True,exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix='vm-',dir=parent))
    results = []
    for event in ['normal','worker-kill','guest-kernel-panic','guest-abrupt-power-cut','cooperative-cancel']:
        phases = [BARRIERS[-1]] if event == 'normal' else BARRIERS
        for phase in phases:
            case = root/(event+'-'+phase)
            case.mkdir()
            disk = case/'data.raw'
            shutil.copyfile(build/'blank.raw',disk)
            work = case/'worker';work.mkdir()
            guest = Guest(build,disk,'worker',work)
            reached = False
            panic_observed = False
            try:
                while True:
                    item = guest.next(timeout=60)
                    assert item is not None
                    if not isinstance(item,dict):
                        continue
                    if 'barrier' in item:
                        if item['barrier'] == phase and event != 'normal':
                            reached = True
                            if event == 'guest-abrupt-power-cut':
                                guest.close(abrupt=True)
                            elif event == 'guest-kernel-panic':
                                guest.command('inject-nmi')
                                while True:
                                    text = guest.next(timeout=30)
                                    assert text is not None
                                    if isinstance(text,str) and 'Kernel panic' in text:
                                        panic_observed = True
                                        break
                            else:
                                guest.send('kill-worker' if event == 'worker-kill' else 'cancel')
                                # Wait for actual kill acknowledgement or bounded
                                # cooperative worker exit; never count a sent word.
                                while True:
                                    stopped = guest.next(timeout=30)
                                    assert stopped is not None
                                    if (isinstance(stopped,str) and 'IMAGEINFO_WORKER_KILLED' in stopped) or (isinstance(stopped,dict) and stopped.get('issue') == 'CONTROL_STOP'):
                                        break
                            break
                        guest.send('continue')
                    elif item.get('outcome') == 'marker-publication-observed':
                        reached = True
                        break
                assert reached
            finally:
                if guest.process.poll() is None:
                    guest.close()
            restart = case/'restart';restart.mkdir()
            observation = inspect(build,disk,restart)
            expected_output = BARRIERS.index(phase) >= BARRIERS.index('namespace-flushed')
            if phase == 'staged' and event != 'normal':
                assert observation['classification'] == 'invalid-or-uninspectable-evidence'
            elif expected_output:
                assert observation['classification'] == 'candidate-object-observed', observation
            elif phase in ['linked','output-flushed']:
                # Visibility is not namespace persistence. Without the directory
                # acknowledgement, either complete candidate or absence is valid.
                assert observation['classification'] in ['candidate-object-observed','expected-absence-observed'], observation
            else:
                assert observation['classification'] == 'expected-absence-observed', observation
            assert observation['authorizedActions'] == [] and not observation['profileVerified']
            if phase == BARRIERS[-1]:
                assert observation['observationPresent']
            result = {'id':case.name,'interruption':event,'phase':phase,'classification':observation['classification'],
                      'observationPresent':observation.get('observationPresent',False),'guestPanicObserved':panic_observed,
                      'committed':False,'authorizedActions':[],'physicalPowerLossTested':False}
            results.append(result)
            retain_result(case,result)
    normal_disk = root/'normal-observation-namespace-flushed'/'data.raw'
    for actor, expected in ACTORS.items():
        case = root/actor; case.mkdir()
        disk = case/'data.raw'; shutil.copyfile(normal_disk,disk)
        capture = case/'actor'; capture.mkdir()
        observation = inspect(build,disk,capture,actor)
        assert observation['classification'] == expected, observation
        result = {'id':actor,'classification':expected,'repairAndPruneRefused':True,'artifactInventoryUnchanged':True,'committed':False}
        results.append(result); retain_result(case,result)
    for fault in FAULTS + ['full-disk','device-flush-eio']:
        case = root/('fault-'+fault); case.mkdir()
        disk = case/'data.raw'; shutil.copyfile(build/'blank.raw',disk)
        capture = case/'worker'; capture.mkdir()
        mode = 'full-disk' if fault == 'full-disk' else ('worker' if fault == 'device-flush-eio' else 'worker-fail-'+fault)
        guest = Guest(build,disk,mode,capture,block_fault=fault == 'device-flush-eio')
        try:
            while True:
                item = guest.next(timeout=60)
                assert item is not None
                if isinstance(item,dict):
                    if 'barrier' in item:
                        guest.send('continue')
                    elif 'issue' in item:
                        issue = item['issue']
                        if fault == 'full-disk':
                            assert 'No space left on device' in issue
                        elif fault == 'device-flush-eio':
                            assert 'I/O error' in issue or 'Input/output error' in issue or 'Read-only file system' in issue
                            statistics = guest.command('query-blockstats')
                            (capture/'blockstats.json').write_text(json.dumps(statistics,indent=2)+'\n')
                            assert any(drive['stats']['failed_flush_operations'] > 0 for drive in statistics['return'])
                        else:
                            assert issue == 'INJECTED_FLUSH_FAILURE:'+fault
                        break
        finally:
            guest.close()
        restart = case/'restart'; restart.mkdir()
        observation = inspect(build,disk,restart)
        assert observation['authorizedActions'] == [] and not observation['committed']
        if fault in FAULTS[:7] + ['full-disk','device-flush-eio']:
            assert observation['classification'] in ['expected-absence-observed','invalid-or-uninspectable-evidence']
        elif fault in ['output','output-namespace']:
            # Linking did occur, but without namespace acknowledgement it can
            # disappear on reboot. Retain uncertainty; never infer no effects.
            assert observation['classification'] in ['expected-absence-observed','candidate-object-observed']
        else:
            assert observation['classification'] == 'candidate-object-observed'
        kind = {'full-disk':'actual-ENOSPC','device-flush-eio':'emulated-device-flush-error'}.get(fault,'protocol-injected-flush-refusal')
        result = {'id':'fault-'+fault,'faultKind':kind,
                  'issue':issue,'classification':observation['classification'],'committed':False,'authorizedActions':[]}
        results.append(result); retain_result(case,result)
    report = {'cases':results,'caseCount':len(results),'kernel':'6.18.52-0-virt','qemu':'10.2.1','machine':'q35/TCG','memoryMiB':256,
              'dataDiskMiB':64,'filesystem':'ext4','mount':'data=ordered,errors=remount-ro','qemuCache':'writeback',
              'hostCacheSurvivesAbruptEmulatorExit':True,'physicalPowerLossRuns':0,'productionPublicationAllowed':False,'enabledProfiles':0}
    report['buildHashes'] = {name:hashlib.sha256((build/name).read_bytes()).hexdigest() for name in ['kernel','initramfs.cpio.gz','blank.raw']}
    report['probeSha256'] = hashlib.sha256((build/'root'/'probe').read_bytes()).hexdigest()
    report['sourceHashes'] = {name:hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest() for name in ['guest_suite.py','build_guest.py','guest-init.sh','src/main.rs','src/linux.rs','Cargo.toml','Cargo.lock']}
    (root/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build',required=True)
    parser.add_argument('--parent',required=True)
    args=parser.parse_args()
    print(json.dumps(run(args.build,args.parent),indent=2))
