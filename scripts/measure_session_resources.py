"""#0146 authored sequential OS-pipe session observations; no product deadline."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
import time

import read_benchmark as base
from read_telemetry import Observer

ROOT = Path(__file__).resolve().parents[1]
CAP = 32 * 1024 * 1024
FRAME_CAP = 524288
TOOLS = ('scripts/measure_session_resources.py', 'scripts/audit_session_resources.py',
         'scripts/read_telemetry.py', 'scripts/audit_read_telemetry.py',
         'scripts/read_benchmark.py', 'scripts/check_read_arguments.py', 'tests/support/mod.rs')


def source_binding():
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    paths = [ROOT/'Cargo.toml', ROOT/'Cargo.lock', ROOT/'rust-toolchain.toml']
    paths += [p for p in (ROOT/'src').rglob('*') if p.is_file()]
    return dict(revision=revision, files={str(p.relative_to(ROOT)).replace('\\','/'):base.digest(p) for p in sorted(paths)})


def save(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def frame(kind, identity, tokens=None):
    value = dict(protocolVersion=1, kind=kind, id=identity)
    if tokens is not None:
        value['tokens'] = tokens
    return json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8') + b'\n'


def tokens(case):
    common = ['metadata', 'read', '--max-bytes', '8388608']
    if case == 'usage':
        return common + ['--bogus']
    if case == 'missing':
        return common + ['--', 'missing.cr3']
    if case == 'invalid':
        return common + ['--', 'invalid.cr3']
    if case == 'selected':
        return common + ['--tag', 'ISO', '--values', 'raw', '--', 's\u00e9ssion.cr3']
    return common + ['--values', 'all', '--', 's\u00e9ssion.cr3']


def plan():
    rows = []
    pattern = ('usage', 'selected', 'missing', 'all', 'invalid', 'selected', 'all')
    for count in (1, 64, 255):
        for repeat in range(3):
            cases = ['selected'] if count == 1 else [pattern[i % len(pattern)] for i in range(count)]
            rows.append(dict(name=f'reads-{count}-{repeat}', cases=cases, control=None))
    for control in ('id-128', 'id-129', 'duplicate-id', 'frame-lf-cap', 'frame-crlf-cap', 'frame-over', 'auto-256'):
        rows.append(dict(name=control, cases=[], control=control))
    return rows


def requests(cell):
    control = cell['control']
    if control is None:
        return [(frame('read', f'r{i}', tokens(case)), case) for i, case in enumerate(cell['cases'])] + [(frame('close', 'done'), None)]
    if control == 'auto-256':
        return [(frame('read', f'r{i:03}'+'a'*124, tokens('selected' if i % 2 == 0 else 'all')), 'selected' if i % 2 == 0 else 'all') for i in range(256)]
    if control.startswith('id-'):
        return [(frame('close', 'a' * int(control.split('-')[1])), None)]
    if control == 'duplicate-id':
        return [(frame('read', 'same', tokens('selected')), 'selected'), (frame('close', 'same'), None)]
    wire = frame('close', 'cap')
    if control == 'frame-over':
        return [(b' ' * FRAME_CAP, None)]
    ending = b'\r\n' if control == 'frame-crlf-cap' else b'\n'
    return [(wire[:-1] + b' ' * (FRAME_CAP - len(wire[:-1]) - len(ending)) + ending, None)]


def snapshot(work):
    return {p.name: dict(bytes=p.stat().st_size, mtimeNs=p.stat().st_mtime_ns,
                        sha256=base.digest(p), device=p.stat().st_dev, inode=p.stat().st_ino)
            for p in sorted(work.iterdir())}


def prepare(root, binary):
    from check_read_arguments import fixture
    root.mkdir()
    work = root / 'fixtures'
    work.mkdir()
    captures = root / 'fixture-build'
    captures.mkdir()
    fixture(work, captures)
    (work/'source.cr3').rename(work/'s\u00e9ssion.cr3')
    (work / 'invalid.cr3').write_bytes(b'authored invalid CR3\n')
    oracles = {}
    for case in ('usage', 'missing', 'invalid', 'selected', 'all'):
        done = subprocess.run([str(binary), *tokens(case), '--output=json'] if case == 'usage' else
                              [str(binary), *tokens(case)[:4], '--output=json', *tokens(case)[4:]],
                              cwd=work, capture_output=True, timeout=30, check=False)
        (captures / f'oracle-{case}.stdout').write_bytes(done.stdout)
        (captures / f'oracle-{case}.stderr').write_bytes(done.stderr)
        oracles[case] = json.loads(done.stdout)
    save(root / 'oracles.private.json', oracles)
    save(root / 'prepared.private.json', dict(binary=str(binary), binarySha256=base.digest(binary), sourceBinding=source_binding(), fixtureBefore=snapshot(work),
                                             plan=plan(), oracleSha256=base.digest(root / 'oracles.private.json')))


def run_cell(binary, work, cell, output, watchdog_ms=30000):
    """Bounded harness: reader timestamps LF before JSON parsing; writer cannot block supervision."""
    start = time.perf_counter_ns()
    observer = Observer(10)
    received = queue.Queue(maxsize=1024)
    outgoing = queue.Queue(maxsize=1)
    captures = [bytearray(), bytearray()]
    counts = [0, 0]
    faults = []
    row = dict(name=cell['name'], requests=[], received=[], outcome='exited', censored=False,
               readyLatencyNs=None, readyCheckpoint=None, readyCheckpointUnavailable=None,
               checkpointLiveness={}, exitCode=None)
    process = None

    def drain(stream, index):
        try:
            while True:
                data = stream.readline(16 * 1024 * 1024 + 513) if index == 0 else stream.read(4096)
                stamp = time.perf_counter_ns() - start
                if not data:
                    break
                counts[index] += len(data)
                captures[index].extend(data[:max(0, CAP - len(captures[index]))])
                if counts[index] > CAP:
                    faults.append('output-limit')
                    break
                if index == 0:
                    received.put_nowait((stamp, data))
        except Exception as error:
            faults.append('consumer-error:' + type(error).__name__)

    def write():
        try:
            while True:
                wire = outgoing.get()
                if wire is None:
                    return
                pending = memoryview(wire)
                while pending:
                    written = process.stdin.write(pending)
                    if not written:
                        raise OSError('short pipe write')
                    pending = pending[written:]
                process.stdin.flush()
        except (OSError, ValueError) as error:
            faults.append('writer-error:' + type(error).__name__)

    def checkpoint():
        before = time.perf_counter_ns() - start
        if process.poll() is not None:
            return None, 'process-exited'
        count = len(observer.samples)
        observer.next_sample = 0
        observer.sample()
        live = process.poll() is None
        after = time.perf_counter_ns() - start
        if not live:
            return None, 'process-exited'
        if len(observer.samples) != count+1:
            return None, 'sample-unavailable'
        row['checkpointLiveness'][str(count)] = dict(beforeOffsetNs=before, afterOffsetNs=after,
                                                    liveBefore=True, liveAfter=True)
        return count, None

    def receive():
        while True:
            observer.sample()
            if observer.stop_reason:
                raise RuntimeError(observer.stop_reason)
            if faults:
                raise RuntimeError(faults[0])
            if time.perf_counter_ns() - start > watchdog_ms * 1000000:
                raise RuntimeError('timeout')
            try:
                stamp, data = received.get(timeout=0.002)
                row['received'].append(dict(completeLf=data.endswith(b'\n'), endOffsetNs=stamp,
                                            bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
                return stamp, json.loads(data)
            except queue.Empty:
                if process.poll() is not None and not threads[0].is_alive():
                    raise RuntimeError('no-final-frame')

    threads = []
    try:
        process = subprocess.Popen([str(binary), 'session', 'read'], cwd=work, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
        observer.attach(process, start)
        threads = [threading.Thread(target=drain, args=(process.stdout, 0), daemon=True),
                   threading.Thread(target=drain, args=(process.stderr, 1), daemon=True),
                   threading.Thread(target=write, daemon=True)]
        for thread in threads:
            thread.start()
        stamp, ready = receive()
        row['readyLatencyNs'], row['ready'] = stamp, ready
        row['readyCheckpoint'], row['readyCheckpointUnavailable'] = checkpoint()
        for wire, case in requests(cell):
            request = dict(sendOffsetNs=time.perf_counter_ns() - start, inputBytes=len(wire),
                           inputSha256=hashlib.sha256(wire).hexdigest(), case=case,
                           completeOffsetNs=None, latencyNs=None, checkpoint=None, checkpointUnavailable='request-incomplete')
            row['requests'].append(request)
            outgoing.put_nowait(wire)
            stamp, value = receive()
            point, unavailable = checkpoint()
            request.update(completeOffsetNs=stamp, latencyNs=stamp-request['sendOffsetNs'],
                           checkpoint=point, checkpointUnavailable=unavailable)
            if value['kind'] == 'protocol-error':
                receive()
                break
        if row['received'] and value['kind'] == 'read-result':
            receive()
        while process.poll() is None:
            observer.sample()
            if faults or observer.stop_reason or time.perf_counter_ns() - start > watchdog_ms*1000000:
                raise RuntimeError(observer.stop_reason or (faults[0] if faults else 'timeout'))
            time.sleep(0.002)
    except (OSError, RuntimeError, ValueError, KeyError, KeyboardInterrupt) as error:
        row['outcome'] = 'cancelled' if isinstance(error, KeyboardInterrupt) else str(error)
        row['censored'] = True
    finally:
        if process is not None:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
            row['exitCode'] = process.returncode
            process.stdin.close()
            try:
                outgoing.put_nowait(None)
            except queue.Full:
                pass
            for thread in threads:
                thread.join(timeout=5)
            process.stdout.close()
            process.stderr.close()
            observer.sample(final=True)
        else:
            observer.launch_failed(start)
        row['elapsedNs'] = time.perf_counter_ns() - start
        row['telemetry'] = observer.report()
        row['faults'] = faults
        for index, channel in enumerate(('stdout', 'stderr')):
            data = bytes(captures[index])
            (output / f'{cell["name"]}.{channel}').write_bytes(data)
            row[channel+'Bytes'] = counts[index]
            row[channel+'CapturedBytes'] = len(data)
            row[channel+'Sha256'] = hashlib.sha256(data).hexdigest()
    return row


def collect(root):
    p = base.load(root / 'prepared.private.json')
    binary = Path(p['binary'])
    bindings = {str(path): base.digest(path) for path in (binary, *(ROOT/name for name in TOOLS))}
    before = snapshot(root/'fixtures')
    if before != p['fixtureBefore'] or base.digest(root/'oracles.private.json') != p['oracleSha256'] or base.digest(binary) != p['binarySha256'] or source_binding() != p['sourceBinding']:
        raise ValueError('prepared inputs changed')
    capture = root/'captures'
    capture.mkdir()
    record = dict(revision='session-resources-146-v1', bindings=bindings, sourceBinding=p['sourceBinding'], cells=[], sourceBefore=before,
                  status='aborted', clock='perf_counter_ns before Popen; LF timestamp before parse',
                  watchdogMs=30000, captureBytes=CAP, cache='uncontrolled; repeatedly read authored fixture')
    try:
        for cell in plan():
            row = run_cell(binary, root/'fixtures', cell, capture)
            record['cells'].append(row)
            save(root/f'{cell["name"]}.private.json', row)
            if row['outcome'] == 'cancelled':
                break
        record['status'] = 'completed' if len(record['cells']) == len(plan()) else 'cancelled'
    finally:
        record['sourceAfter'] = snapshot(root/'fixtures')
        record['bindingsUnchanged'] = all(base.digest(path) == value for path, value in bindings.items())
        record['sourceBindingUnchanged'] = source_binding() == p['sourceBinding']
        save(root/'record.private.json', record)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-root', type=Path, required=True)
    parser.add_argument('--prepare', type=Path, metavar='BINARY')
    args = parser.parse_args()
    root = args.run_root.resolve()
    if not root.is_relative_to(ROOT/'.local'):
        raise ValueError('private .local run root required')
    if args.prepare:
        prepare(root, args.prepare.resolve())
    else:
        collect(root)
