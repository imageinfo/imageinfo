"""#0140 finite actual session child faults, separate from library I/O traits.

No media read requests are submitted. Results and raw captures are retained even
on an oracle failure; caller-owned artifacts must use a fresh output directory.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import sys

from native_session_handles import launch, LIMIT, SECONDS


READY = {'allowApply': False, 'kind': 'session-ready', 'protocolVersion': 1,
         'limits': {'maxFrames': 256, 'maxInputFrameBytes': 524288, 'maxInputs': 4,
                    'maxMetadataBytes': 8388608, 'maxOutputFrameBytes': 16777728,
                    'maxQueuedRequests': 0, 'maxResultBytes': 16777216,
                    'maxTokenBytes': 32768, 'maxTokens': 128, 'maxTotalTokenBytes': 65536}}
WINDOWS = ['eof-file', 'eof-pipe', 'stdin-null', 'stdin-invalid', 'stdin-closed',
           'stdin-write-only', 'stdout-read-only', 'stdout-broken-pipe']
POSIX = ['eof-file', 'eof-pipe', 'stdin-closed', 'stdin-write-only',
         'stdin-directory', 'stdout-read-only', 'stdout-broken-pipe']


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(root):
    result = {}
    for path in sorted(root.iterdir()):
        assert path.is_file() and not path.is_symlink(), 'unexpected fixture entry'
        stat = path.stat()
        result[path.name] = {'bytes': stat.st_size, 'mtimeNs': stat.st_mtime_ns,
                             'sha256': digest(path), 'mode': stat.st_mode}
    return result


def complete(reason, status):
    return {'closeId': None, 'exitStatus': status, 'frames': 0,
            'kind': 'session-complete', 'protocolVersion': 1, 'reason': reason, 'results': 0}


def wire(frames):
    return b''.join((json.dumps(frame, sort_keys=True, separators=(',', ':')) + '\n').encode()
                    for frame in frames)


def check(case, status, out, err):
    """Independent exact-byte oracle for the declared pinned runtime profile."""
    expected_error = None
    if case.startswith('stdout-'):
        kind = ('PermissionDenied' if os.name == 'nt' else 'Uncategorized') \
            if case == 'stdout-read-only' else 'BrokenPipe'
        expected_error = kind
        expected_status, frames = 1, []
        expected_stderr = f'OUTPUT_INCOMPLETE: Could not finish output ({kind}).\n'.encode()
    elif case == 'stdin-null':
        expected_status, frames, expected_stderr = None, [READY], b''
    elif case in ('stdin-write-only', 'stdin-directory'):
        expected_status, expected_stderr = 1, b''
        frames = [READY, {'code': 'INPUT_IO', 'id': None, 'kind': 'protocol-error', 'protocolVersion': 1},
                  complete('input-error', 1)]
    else:
        expected_status, frames, expected_stderr = 0, [READY, complete('eof', 0)], b''
    assert status == expected_status, f'exit status {status!r}, expected {expected_status!r}'
    assert out == wire(frames), 'stdout differs from exact canonical LF frames'
    assert err == expected_stderr, 'stderr differs from exact diagnostic'
    return frames, expected_error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    binary = args.binary.resolve(strict=True)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    fixture = output / 'fixture'
    fixture.mkdir()
    (fixture / 'empty').write_bytes(b'')
    (fixture / 'guard').write_bytes(b'authored protected handle-fault guard\n')
    before = inventory(fixture)
    report = {'ticket': 140, 'createdUtc': datetime.now(timezone.utc).isoformat(),
              'platform': sys.platform, 'osRelease': platform.release(),
              'python': platform.python_version(), 'binarySha256': digest(binary),
              'binaryBytes': binary.stat().st_size,
              'toolSha256': {path.name: digest(path) for path in
                             (Path(__file__), Path(__file__).with_name('native_session_handles.py'))},
              'watchdogSeconds': SECONDS, 'captureValidationBytes': LIMIT,
              'inventoryBefore': before, 'cases': [],
              'nativeFlushOnlyInjection': 'unavailable; no write-success/flush-only-failure claim',
              'limits': ['No read frames or media parsing; transport-only authored files.',
                         'Parent-side handle setup does not prove unmodified child runtime handle identity.',
                         'Inventories exclude ordinary access-time accounting and capture artifacts.',
                         'Watchdog termination has no natural process status or final-frame guarantee.']}
    failed = False
    for case in WINDOWS if os.name == 'nt' else POSIX:
        record = {'case': case}
        report['cases'].append(record)
        try:
            status, out, err, injection = launch(binary, case, fixture, output / case)
            record.update(status=status, stdoutHex=out.hex(), stderrHex=err.hex(), injection=injection)
            frames, error_kind = check(case, status, out, err)
            record.update(frames=frames, outputErrorKind=error_kind,
                          disposition='censored-watchdog' if status is None else 'natural-exact',
                          oraclePassed=True)
        except Exception as error:
            record.update(oraclePassed=False, failure=f'{type(error).__name__}: {error}')
            failed = True
        record['inventoryAfter'] = inventory(fixture)
        record['inventoryUnchanged'] = record['inventoryAfter'] == before
        failed |= not record['inventoryUnchanged']
        report['binaryUnchanged'] = digest(binary) == report['binarySha256']
        failed |= not report['binaryUnchanged']
        (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    report['passed'] = not failed
    (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(f'native session handles: {len(report["cases"])} retained cases; '
          f'{"PASS" if not failed else "FAIL"}; {output / "report.json"}')
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
