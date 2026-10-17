"""#0147 bounded authored JSON/JSONL consumer experiment; no product timeout.

Prepare first. Run only with the parent's frozen executable and serialized slot.
Private captures retain every attempted cell, including failures and censoring.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import threading
import time

import read_benchmark as common
import read_telemetry

ROOT = Path(__file__).resolve().parents[1]
CAPTURE = 262144
STDERR = 8192
MAX_READS = 4096
WATCHDOG_MS = 30000
REVISION = 'output-consumers-v1'
TOKENS = ['metadata', 'read', '--values', 'all', '--', 'authored.cr3']


def prepare(folder):
    """Compile the existing public authored fixture builder; no media or imageinfo."""
    folder.mkdir(parents=True, exist_ok=False)
    builder = json.dumps((ROOT / 'tests/support/mod.rs').as_posix())
    source = folder / 'fixture.rs'
    source.write_text(f'#[allow(dead_code)] #[path={builder}] mod support;\n'
                      'fn main(){std::fs::write(std::env::args_os().nth(1).unwrap(),'
                      'support::fixture().bytes).unwrap();}\n', encoding='utf-8', newline='\n')
    exe = folder / ('fixture.exe' if os.name == 'nt' else 'fixture')
    subprocess.run(['rustc', '--edition=2024', str(source.resolve()), '-o', str(exe.resolve())],
                   cwd=ROOT, check=True, capture_output=True, timeout=45)
    subprocess.run([str(exe.resolve()), str((folder / 'authored.cr3').resolve())], check=True, timeout=10)


def input_bytes(mode):
    if mode == 'json':
        return b''
    return b''.join((json.dumps(v, separators=(',', ':')) + '\n').encode() for v in (
        {'protocolVersion': 1, 'kind': 'read', 'id': 'r147', 'tokens': TOKENS},
        {'protocolVersion': 1, 'kind': 'close', 'id': 'done147'}))


def run_process(argv, cwd, mode, consumer, timeout_ms=WATCHDOG_MS, capture=CAPTURE,
                observer=None, cancel_event=None):
    """Unbuffered 1024-byte OS-pipe reads, with 5ms minimum start spacing if slow.

    No queue, sink thread behind the declared consumer, or text wrapper. The
    separate stderr drainer has an 8192-byte retained cap. This direct-process
    research watchdog does not implement a timeout or final-frame guarantee.
    """
    if mode not in ('json', 'jsonl') or consumer not in ('fast', 'slow', 'close'):
        raise ValueError('mode/consumer')
    common.integer(timeout_ms, 1, WATCHDOG_MS)
    common.integer(capture, 1, CAPTURE)
    payload = input_bytes(mode)
    assert len(payload) <= 2048
    result = {'outcome': 'exited', 'exitCode': None, 'censored': False,
              'firstByteNs': None, 'firstUsableNs': None, 'deliveryCompleteNs': None,
              'exitObservedNs': None, 'consumerClosedNs': None, 'processSpawnedNs': None,
              'processLaunchBeginNs': None, 'reads': [], 'errors': [],
              'argv': list(argv), 'cwd': str(Path(cwd).resolve()),
              'stdinSha256': hashlib.sha256(payload).hexdigest()}
    retained = [bytearray(), bytearray()]
    totals = [0, 0]
    stop = threading.Event()
    failure = []
    start = time.perf_counter_ns()
    stamp = lambda: time.perf_counter_ns() - start
    result['startedUtc'] = datetime.now(timezone.utc).isoformat()
    broken_write = None
    out = subprocess.PIPE
    if consumer == 'close':
        read_fd, broken_write = os.pipe()
        os.close(read_fd)
        out = broken_write
        result['consumerClosedNs'] = stamp()
    try:
        result['processLaunchBeginNs'] = stamp()
        p = subprocess.Popen(argv, cwd=cwd, env=dict(os.environ, NO_COLOR='1'),
                             stdin=subprocess.PIPE if payload else subprocess.DEVNULL,
                             stdout=out, stderr=subprocess.PIPE, shell=False, bufsize=0)
        result['processSpawnedNs'] = stamp()
    except OSError as error:
        result['outcome'] = 'launch-error'
        result['errors'].append('launch:' + type(error).__name__)
        p = None
        if observer is not None:
            observer.launch_failed(start)
    finally:
        if broken_write is not None:
            os.close(broken_write)

    def stderr_drain():
        try:
            while True:
                block = p.stderr.read(1024)
                if not block:
                    break
                totals[1] += len(block)
                available = STDERR - len(retained[1])
                retained[1].extend(block[:available])
                if len(block) > available:
                    failure.append('output-limit')
                    stop.set()
                    break
        except OSError as error:
            result['errors'].append('stderr:' + type(error).__name__)
            failure.append('consumer-error')
            stop.set()
        finally:
            p.stderr.close()

    def stdout_drain():
        previous_start = None
        try:
            while not stop.is_set():
                if len(result['reads']) >= MAX_READS:
                    failure.append('output-limit')
                    stop.set()
                    break
                if consumer == 'slow' and previous_start is not None:
                    due = start + previous_start + 5_000_000
                    while time.perf_counter_ns() < due:
                        if stop.wait((due - time.perf_counter_ns()) / 1e9 if due > time.perf_counter_ns() else 0):
                            return
                begin = stamp()
                previous_start = begin
                block = p.stdout.read(1024)
                end = stamp()
                result['reads'].append({'beginNs': begin, 'endNs': end, 'bytes': len(block)})
                if not block:
                    result['deliveryCompleteNs'] = end
                    break
                if result['firstByteNs'] is None:
                    result['firstByteNs'] = end
                totals[0] += len(block)
                available = capture - len(retained[0])
                retained[0].extend(block[:available])
                if result['firstUsableNs'] is None:
                    # Framing timestamp only; the independent full-byte/schema
                    # audit subsequently decides whether this was usable output.
                    if ((mode == 'json' and retained[0].endswith(b'\n')) or
                            (mode == 'jsonl' and retained[0].count(b'\n') >= 2)):
                        result['firstUsableNs'] = end
                if len(block) > available:
                    failure.append('output-limit')
                    stop.set()
                    break
        except OSError as error:
            result['errors'].append('stdout:' + type(error).__name__)
            failure.append('consumer-error')
            stop.set()
        finally:
            p.stdout.close()

    def write_input():
        try:
            view = memoryview(payload)
            while view:
                written = p.stdin.write(view)
                if not written:
                    raise OSError('no input progress')
                view = view[written:]
        except OSError as error:
            result['errors'].append('stdin:' + type(error).__name__)
        finally:
            p.stdin.close()

    threads = []
    if p is not None:
        if observer is not None:
            observer.attach(p, start)
        threads.append(threading.Thread(target=stderr_drain, daemon=True))
        if consumer != 'close':
            threads.append(threading.Thread(target=stdout_drain, daemon=True))
        if payload:
            threads.append(threading.Thread(target=write_input, daemon=True))
        for thread in threads:
            thread.start()
        exited = False
        try:
            while True:
                if not exited and p.poll() is not None:
                    exited = True
                    result['exitObservedNs'] = stamp()
                    if observer is not None:
                        observer.sample(final=True)
                if exited and not any(t.is_alive() for t in threads):
                    break
                if observer is not None and not exited:
                    observer.sample()
                reason = ('cancelled' if cancel_event is not None and cancel_event.is_set() else
                          failure[0] if failure else
                          observer.stop_reason if observer is not None and observer.stop_reason else
                          'timeout' if stamp() >= timeout_ms * 1_000_000 else None)
                if reason:
                    result['outcome'] = reason
                    stop.set()
                    if not exited:
                        p.kill()
                    break
                time.sleep(.001)
        except KeyboardInterrupt:
            result['outcome'] = 'cancelled'
            stop.set()
            if not exited:
                p.kill()
        p.wait()
        if not exited:
            result['exitObservedNs'] = stamp()
            if observer is not None:
                observer.sample(final=True)
        for thread in threads:
            thread.join(1)
        if any(t.is_alive() for t in threads):
            result['outcome'] = 'consumer-error'
            result['errors'].append('thread did not finish after direct exit')
        elif failure and result['outcome'] == 'exited':
            result['outcome'] = failure[0]
        result['exitCode'] = p.returncode
    result['elapsedNs'] = stamp()
    result['censored'] = result['outcome'] != 'exited'
    for index, name in enumerate(('stdout', 'stderr')):
        result[name + 'Bytes'] = totals[index]
        result[name + 'CapturedBytes'] = len(retained[index])
        result[name + 'Sha256'] = hashlib.sha256(retained[index]).hexdigest()
    if observer is not None:
        result['telemetry'] = observer.report()
    return result, bytes(retained[0]), bytes(retained[1])


def collect(binary, folder, output, environment, source_revision, source_freeze_sha256):
    import audit_output_consumers as oracle
    from audit_output_consumers import SNAPSHOT, expected, validate_output
    oracle.require_sha(source_freeze_sha256)
    if not isinstance(source_revision, str) or re.fullmatch('[0-9a-f]{40}', source_revision) is None:
        raise ValueError('explicit frozen source revision required')
    binary, folder, output = binary.resolve(), folder.resolve(), output.resolve()
    if output.exists():
        raise ValueError('fresh output directory required')
    source = folder / 'authored.cr3'
    before = common.digest(source)
    binary_hash = common.digest(binary)
    require_size = max(len(expected(m, 'req-9999999999-9999999999999999999' if m == 'json' else 'r147'))
                       for m in ('json', 'jsonl'))
    if require_size > CAPTURE:
        raise ValueError('independent expected output exceeds experiment bound')
    output.mkdir(parents=True)
    record = {'revision': REVISION, 'observedUtc': datetime.now(timezone.utc).isoformat(),
              'sourceRevision': source_revision, 'sourceFreezeSha256': source_freeze_sha256,
              'binaryPath': str(binary), 'fixturePath': str(source),
              'binarySha256': binary_hash, 'fixtureSha256': before,
              'collectorSha256': common.digest(__file__), 'telemetrySha256': common.digest(read_telemetry.__file__),
              'auditorSha256': common.digest(oracle.__file__), 'sharedCollectorSha256': common.digest(common.__file__),
              'fixtureBuilderSha256': common.digest(ROOT / 'tests/support/mod.rs'),
              'validationBindings': oracle.validation_bindings(),
              'oracleSha256': common.digest(SNAPSHOT), 'environment': environment,
              'python': platform.python_version(), 'platform': platform.platform(),
              'warmups': 2, 'repeats': 10, 'timeoutMs': WATCHDOG_MS, 'captureBytes': CAPTURE,
              'sourceUnchanged': True, 'binaryUnchanged': True, 'attempts': []}
    for mode in ('json', 'jsonl'):
        argv = [str(binary), *(TOKENS[:2] + ['--output=json'] + TOKENS[2:] if mode == 'json' else ['session', 'read'])]
        for consumer in ('fast', 'slow', 'close'):
            for ordinal in range(1 if consumer == 'close' else 12):
                observer = read_telemetry.Observer(interval_ms=10)
                attempt, stdout, stderr = run_process(argv, str(folder), mode, consumer, observer=observer)
                index = len(record['attempts'])
                attempt.update(index=index, mode=mode, consumer=consumer,
                               phase='control' if consumer == 'close' else 'warmup' if ordinal < 2 else 'sample')
                passed = False
                if consumer == 'close':
                    attempt['correctness'] = 'control'
                else:
                    try:
                        passed = (attempt['outcome'] == 'exited' and attempt['exitCode'] == 0 and not stderr and not attempt['errors']
                                  and validate_output(mode, stdout))
                    except Exception as error:
                        # Schema/semantic/framing failures are observations too;
                        # retain the cell before proceeding. Interrupts propagate.
                        attempt['errors'].append('oracle:' + type(error).__name__)
                    attempt['correctness'] = 'pass' if passed else 'fail'
                attempt['eligible'] = passed and attempt['phase'] == 'sample' and observer.report()['valid']
                attempt['controlOutputFailure'] = (consumer == 'close' and attempt['outcome'] == 'exited' and
                                                   attempt['exitCode'] == 1 and
                                                   stderr.startswith(b'OUTPUT_INCOMPLETE: Could not finish output ('))
                for name, data in (('stdout', stdout), ('stderr', stderr)):
                    filename = f'{index:02d}-{mode}-{consumer}.{name}'
                    (output / filename).write_bytes(data)
                    attempt[name + 'File'] = filename
                record['attempts'].append(attempt)
                record['sourceUnchanged'] = common.digest(source) == before
                record['binaryUnchanged'] = common.digest(binary) == binary_hash
                (output / 'record.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8', newline='\n')
                if attempt['outcome'] == 'cancelled' or not record['sourceUnchanged'] or not record['binaryUnchanged']:
                    return record
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', type=Path)
    parser.add_argument('--binary', type=Path)
    parser.add_argument('--fixture-dir', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--environment', type=Path, help='bounded JSON file declaring hardware/storage/cache/load facts')
    parser.add_argument('--source-revision', help='parent frozen source commit, 40 lowercase hexadecimal digits')
    parser.add_argument('--source-freeze-sha256', help='parent retained source-freeze manifest SHA-256')
    args = parser.parse_args()
    if args.prepare:
        prepare(args.prepare.resolve())
        print('authored fixture prepared; no imageinfo campaign run')
    else:
        if None in (args.binary, args.fixture_dir, args.output, args.environment, args.source_revision, args.source_freeze_sha256):
            parser.error('--binary --fixture-dir --output --environment --source-revision --source-freeze-sha256 are required')
        environment = common.load(args.environment)
        if not isinstance(environment, dict) or not environment:
            raise ValueError('explicit environment facts/unknowns required')
        record = collect(args.binary, args.fixture_dir, args.output, environment, args.source_revision, args.source_freeze_sha256)
        print(json.dumps({'attempts': len(record['attempts']), 'eligible': sum(a['eligible'] for a in record['attempts'])}))


if __name__ == '__main__':
    main()
