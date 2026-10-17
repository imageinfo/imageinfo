"""Independent #0147 authored output, schedule and resource auditor.

No collector imports. Reconstruct every successful stdout byte from the existing
public authored snapshot and the declared native/session envelopes.
"""
import argparse
import copy
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re

from audit_read_telemetry import audit as audit_telemetry
import check_native_read_json as native
import check_read_session as session

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / 'docs/legacy-compatibility/native-read-json/example.v1.json'
MAX_OUTPUT = 262144
TOKENS = ['metadata', 'read', '--values', 'all', '--', 'authored.cr3']
OUTCOMES = {'exited', 'launch-error', 'timeout', 'output-limit', 'consumer-error', 'cancelled', 'telemetry-limit'}
TOOL_PATHS = {'oracleSha256': SNAPSHOT, 'collectorSha256': ROOT / 'scripts/output_consumers.py',
              'telemetrySha256': ROOT / 'scripts/read_telemetry.py', 'auditorSha256': Path(__file__),
              'sharedCollectorSha256': ROOT / 'scripts/read_benchmark.py',
              'fixtureBuilderSha256': ROOT / 'tests/support/mod.rs'}
VALIDATION_PATHS = [ROOT / path for path in (
    'scripts/check_native_read_json.py', 'scripts/check_read_session.py', 'scripts/audit_read_telemetry.py',
    'docs/metadata-model/metadata-contract.schema.json', 'docs/legacy-compatibility/result.schema.json',
    'docs/legacy-compatibility/read-session/schema.v1.json',
    'docs/legacy-compatibility/native-read-json/snapshot.schema.v1.json')]


def validation_bindings():
    return {path.relative_to(ROOT).as_posix(): digest(path) for path in VALIDATION_PATHS}


@lru_cache(maxsize=1)
def validators():
    # Immutable schema validators may be reused; no output/correctness result is
    # cached. This is outside the process stopwatch and reads no measured input.
    return (*native.validators(), session.validators()[1])


def require_sha(value):
    require(isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None, 'SHA-256 shape')


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(65536), b''):
            result.update(block)
    return result.hexdigest()


def stdin_expected(mode):
    if mode == 'json':
        return b''
    return wire({'protocolVersion': 1, 'kind': 'read', 'id': 'r147', 'tokens': TOKENS}) + wire(
        {'protocolVersion': 1, 'kind': 'close', 'id': 'done147'})


def wire(value, sort=False):
    return (json.dumps(value, ensure_ascii=False, separators=(',', ':'), sort_keys=sort) + '\n').encode()


def envelope(identifier):
    snapshot = json.loads(SNAPSHOT.read_text(encoding='utf-8'))
    snapshot['id'] = identifier + '-snapshot-0'
    return {'schemaVersion': 1, 'requestId': identifier,
            'request': {'schemaVersion': 1, 'kind': 'request', 'requestId': identifier,
                        'operation': 'metadata read', 'mode': 'read', 'issues': []},
            'files': [{'schemaVersion': 1, 'kind': 'file', 'requestId': identifier,
                       'inputId': 'input-0', 'path': 'authored.cr3', 'state': 'read',
                       'snapshot': snapshot, 'transactionId': None,
                       'effects': {'publicationMayHaveOccurred': False, 'changed': False,
                                   'cleanupPending': False, 'recoveryIds': [], 'notes': []},
                       'issues': [{'code': 'COVERAGE_PARTIAL', 'severity': 'warning',
                                   'message': 'Only the declared R5 metadata/preview slice is interpreted. Other fields and embedded metadata are not inspected.',
                                   'inputId': 'input-0', 'path': None, 'occurrenceRef': None}]}],
            'summary': {'schemaVersion': 1, 'kind': 'summary', 'requestId': identifier,
                        'exitStatus': 0, 'selectionComplete': True,
                        'counts': {'discovered': 1, 'excluded': 0, 'deduplicated': 0, 'byState': {'read': 1}},
                        'artifacts': [], 'issues': [], 'interrupted': False, 'outputComplete': True}}


def expected(mode, identifier='r147'):
    result = envelope(identifier)
    if mode == 'json':
        return wire(result)
    if mode != 'jsonl':
        raise ValueError('unknown transport')
    ready = {'protocolVersion': 1, 'kind': 'session-ready', 'limits': session.LIMITS, 'allowApply': False}
    read = {'protocolVersion': 1, 'kind': 'read-result', 'id': identifier, 'result': result}
    close = {'protocolVersion': 1, 'kind': 'session-complete', 'reason': 'close',
             'exitStatus': 0, 'frames': 2, 'results': 1, 'closeId': 'done147'}
    return wire(ready, sort=True) + wire(read) + wire(close, sort=True)


def validate_output(mode, data):
    if not data or len(data) > MAX_OUTPUT or not data.endswith(b'\n'):
        raise ValueError('output extent/framing')
    snapshot_validator, result_validator, session_validator = validators()
    if mode == 'json':
        result = native.strict_load(data.decode('utf-8'))
        identifier = result['requestId']
        if re.fullmatch(r'req-[0-9]+-[0-9]+', identifier) is None:
            raise ValueError('unexpected ordinary invocation ID')
    else:
        frames = [native.strict_load(line.decode('utf-8')) for line in data.splitlines()]
        session.validate_transcript(frames, session_validator)
        if len(frames) != 3 or [f['kind'] for f in frames] != ['session-ready', 'read-result', 'session-complete']:
            raise ValueError('unexpected session frame order/count')
        identifier, result = frames[1]['id'], frames[1]['result']
        if identifier != 'r147':
            raise ValueError('unexpected session ID')
    result_validator.validate(result)
    snapshot_validator.validate(result['files'][0]['snapshot'])
    native.semantic(result['files'][0]['snapshot'])
    if data != expected(mode, identifier):
        raise ValueError('full-byte independent reconstruction differs')
    return True


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit(record, folder, binary, fixture_dir, source_revision, source_freeze_sha256):
    """Bindings come from the independent operator/freeze, never record paths."""
    folder, binary, fixture_dir = Path(folder).resolve(), Path(binary).resolve(), Path(fixture_dir).resolve()
    require(record['revision'] == 'output-consumers-v1', 'revision')
    require(record['warmups'] == 2 and record['repeats'] == 10, 'attempt denominator')
    require(record['timeoutMs'] == 30000 and record['captureBytes'] == MAX_OUTPUT, 'watchdog/capture')
    require(record['sourceUnchanged'] is True and record['binaryUnchanged'] is True, 'source/binary changed')
    require(isinstance(source_revision, str) and re.fullmatch('[0-9a-f]{40}', source_revision) is not None,
            'source revision shape')
    require_sha(source_freeze_sha256)
    require(record['sourceRevision'] == source_revision and record['sourceFreezeSha256'] == source_freeze_sha256,
            'independent frozen source identity')
    require(record['binaryPath'] == str(binary) and record['fixturePath'] == str(fixture_dir / 'authored.cr3'),
            'independent executable/fixture path')
    for field, path in dict(TOOL_PATHS, binarySha256=binary, fixtureSha256=fixture_dir / 'authored.cr3').items():
        require_sha(record[field])
        require(record[field] == digest(path), field + ' binding mismatch')
    require(record['validationBindings'] == validation_bindings(), 'validation tool/schema bindings')
    require(isinstance(record['environment'], dict) and bool(record['environment']), 'declared environment missing')
    require(isinstance(record['python'], str) and bool(record['python']) and
            isinstance(record['platform'], str) and bool(record['platform']), 'runtime environment missing')
    attempts = record['attempts']
    require(len(attempts) == 50, '48 measured/warmup attempts plus two close controls required')
    counts = {}
    valid = 0
    for index, attempt in enumerate(attempts):
        mode, consumer = attempt['mode'], attempt['consumer']
        require(mode in ('json', 'jsonl') and consumer in ('fast', 'slow', 'close'), 'mode/consumer')
        require(type(attempt['index']) is int and attempt['index'] == index, 'global order')
        require(type(attempt['eligible']) is bool and attempt['correctness'] in ('pass', 'fail', 'control'),
                'eligibility/correctness shape')
        argv = [str(binary), *(TOKENS[:2] + ['--output=json'] + TOKENS[2:] if mode == 'json' else ['session', 'read'])]
        require(attempt['argv'] == argv and attempt['cwd'] == str(fixture_dir), 'exact invocation/cwd')
        require(attempt['stdinSha256'] == hashlib.sha256(stdin_expected(mode)).hexdigest(), 'exact session input')
        key = (mode, consumer)
        ordinal = counts.get(key, 0)
        counts[key] = ordinal + 1
        require(attempt['phase'] == ('control' if consumer == 'close' else 'warmup' if ordinal < 2 else 'sample'), 'phase')
        elapsed = attempt['elapsedNs']
        require(type(elapsed) is int and elapsed > 0, 'duration')
        for field in ('firstByteNs', 'firstUsableNs', 'deliveryCompleteNs', 'exitObservedNs', 'consumerClosedNs',
                      'processLaunchBeginNs', 'processSpawnedNs'):
            value = attempt[field]
            require(value is None or type(value) is int and 0 <= value <= elapsed, 'timing alignment')
        outcome = attempt['outcome']
        require(outcome in OUTCOMES, 'unknown outcome')
        require(type(attempt['censored']) is bool and attempt['censored'] == (outcome != 'exited'), 'censor flag')
        require(isinstance(attempt['errors'], list) and all(isinstance(e, str) and e for e in attempt['errors']), 'error records')
        require(all(e.startswith(('launch:', 'stdout:', 'stderr:', 'stdin:', 'oracle:', 'thread did not finish'))
                    for e in attempt['errors']), 'unknown error category')
        launched = outcome != 'launch-error'
        require(type(attempt['processLaunchBeginNs']) is int, 'launch beginning absent')
        if launched:
            require(type(attempt['processSpawnedNs']) is int and type(attempt['exitObservedNs']) is int and
                    attempt['processLaunchBeginNs'] <= attempt['processSpawnedNs'] <= attempt['exitObservedNs'],
                    'launched child missing/contradictory exit endpoint')
            require(type(attempt['exitCode']) is int, 'launched child exit code absent')
        else:
            require(attempt['processSpawnedNs'] is None and attempt['exitObservedNs'] is None and
                    attempt['exitCode'] is None and any(e.startswith('launch:') for e in attempt['errors']),
                    'launch-error semantics')
        telemetry = attempt['telemetry']
        require(type(telemetry['requestedIntervalMs']) is int and telemetry['requestedIntervalMs'] == 10,
                'exact telemetry interval')
        require(telemetry['maxSamples'] == 2048, 'telemetry sample bound')
        require(type(telemetry['valid']) is bool and telemetry['membership'] in
                ('unavailable', 'direct-only-observed', 'invalid-descendants'), 'counter validity/membership')
        require(isinstance(telemetry['errors'], list) and all(isinstance(e, str) and e for e in telemetry['errors']),
                'counter error shape')
        require(telemetry['stopReason'] in (None, 'telemetry-limit'), 'counter stop reason')
        require(type(telemetry['observerWallNs']) is int and telemetry['observerWallNs'] >= 0,
                'counter observer duration')
        require((type(telemetry['pid']) is int and telemetry['pid'] > 0) if launched else telemetry['pid'] is None,
                'direct process identity')
        samples = telemetry['samples']
        if samples:
            require(launched and samples[0]['beginOffsetNs'] >= attempt['processSpawnedNs'] and
                    samples[-1]['final'] is True and samples[-1]['beginOffsetNs'] >= attempt['exitObservedNs'],
                    'counter launch/direct-exit endpoints')
            require(all(type(s['final']) is bool for s in samples), 'counter final flag')
            require(all(type(s['beginOffsetNs']) is int and type(s['endOffsetNs']) is int and
                        isinstance(s['errors'], dict) and all(isinstance(e, str) and e for e in s['errors'].values())
                        for s in samples), 'counter timestamp/error types')
            ordinary = [s['beginOffsetNs'] for s in samples if not s['final']]
            require(all(y - x >= 10_000_000 for x, y in zip(ordinary, ordinary[1:])), 'counter sampling schedule')
        else:
            require(telemetry['valid'] is False and bool(telemetry['errors']), 'counter absence without reason')
        data = []
        for name, cap in (('stdout', MAX_OUTPUT), ('stderr', 8192)):
            require(attempt[name + 'File'] == f'{index:02d}-{mode}-{consumer}.{name}', 'exact capture name')
            require(type(attempt[name + 'Bytes']) is int and 0 <= attempt[name + 'Bytes'] <= cap + 1024 and
                    type(attempt[name + 'CapturedBytes']) is int and
                    attempt[name + 'CapturedBytes'] == min(attempt[name + 'Bytes'], cap), 'capture arithmetic')
            require_sha(attempt[name + 'Sha256'])
            path = folder / attempt[name + 'File']
            require(path.resolve().is_relative_to(folder.resolve()), 'capture outside record folder')
            with path.open('rb') as stream:
                content = stream.read(cap + 1)
            require(len(content) <= cap and len(content) == attempt[name + 'CapturedBytes'], 'capture bound/count')
            require(len(content) <= attempt[name + 'Bytes'], 'capture/total count')
            require(hashlib.sha256(content).hexdigest() == attempt[name + 'Sha256'], 'capture digest')
            data.append(content)
        reads = attempt['reads']
        require(len(reads) <= 4096, 'read-event capture bound')
        total, previous_start, previous_end, first = 0, None, 0, None
        first_usable = None
        for read in reads:
            begin, end, size = read['beginNs'], read['endNs'], read['bytes']
            require(type(size) is int and 0 <= size <= 1024, 'read size')
            require(type(begin) is int and type(end) is int, 'read timestamp types')
            require(0 <= previous_end <= begin <= end <= elapsed, 'read ordering')
            require(launched and begin >= attempt['processSpawnedNs'], 'pipe read before direct spawn')
            if consumer == 'slow' and previous_start is not None:
                require(begin - previous_start >= 5_000_000, 'slow read interval shorter than declared')
            previous_start, previous_end = begin, end
            total += size
            if size and first is None:
                first = end
            if first_usable is None:
                prefix = data[0][:total]
                if mode == 'json' and prefix.endswith(b'\n'):
                    first_usable = end
                elif mode == 'jsonl' and prefix.count(b'\n') >= 2:
                    first_usable = end
        require(total == attempt['stdoutBytes'], 'read/total arithmetic')
        require(all(r['bytes'] > 0 for r in reads[:-1]), 'read after EOF')
        eof = reads[-1]['endNs'] if reads and reads[-1]['bytes'] == 0 else None
        require(attempt['deliveryCompleteNs'] == eof, 'delivery/EOF endpoint')
        if outcome == 'exited' and consumer != 'close':
            require(eof is not None, 'exited ordinary consumer missing EOF')
        require(first == attempt['firstByteNs'], 'first-byte reconstruction')
        require(first_usable == attempt['firstUsableNs'], 'usable-envelope timing reconstruction')
        if outcome == 'launch-error':
            require(not reads and not any(data) and first is None, 'output without launched child')
        if outcome == 'timeout':
            require(elapsed >= 30_000_000_000, 'timeout before research watchdog')
        if outcome == 'telemetry-limit':
            require(telemetry['stopReason'] == 'telemetry-limit', 'telemetry-limit reason')
        if telemetry['stopReason'] is not None:
            require(outcome in ('telemetry-limit', 'cancelled'), 'counter stop reason/outcome')
        if outcome == 'output-limit':
            require(attempt['stdoutBytes'] > MAX_OUTPUT or attempt['stderrBytes'] > 8192 or len(reads) == 4096,
                    'output-limit without exhausted bound')
        if outcome == 'consumer-error':
            require(any(e.startswith(('stdout:', 'stderr:', 'thread did not finish')) for e in attempt['errors']),
                    'consumer-error without consumer failure')
        passed = False
        if consumer == 'close':
            require(not reads and attempt['consumerClosedNs'] is not None and attempt['deliveryCompleteNs'] is None,
                    'close must precede output reads')
            require(attempt['consumerClosedNs'] <= attempt['processLaunchBeginNs'] and not data[0] and
                    attempt['stdoutBytes'] == 0, 'close-before-launch endpoint/output')
            require(attempt['correctness'] == 'control', 'close control label')
        else:
            require(attempt['consumerClosedNs'] is None, 'ordinary drain unexpectedly closed')
        if consumer != 'close' and outcome == 'exited' and attempt['exitCode'] == 0 and not data[1] and not attempt['errors']:
            try:
                passed = validate_output(mode, data[0])
            except Exception:
                passed = False
            if passed:
                require(reads[-1]['bytes'] == 0 and attempt['deliveryCompleteNs'] == reads[-1]['endNs'], 'EOF delivery')
                require(attempt['firstUsableNs'] is not None, 'usable completion absent')
                if mode == 'json':
                    require(json.loads(data[0])['requestId'].startswith('req-' + str(telemetry['pid']) + '-'),
                            'CLI invocation/direct-process ID')
        require(attempt['correctness'] == ('control' if consumer == 'close' else 'pass' if passed else 'fail'), 'correctness')
        control_failure = (consumer == 'close' and outcome == 'exited' and attempt['exitCode'] == 1 and
                           data[1].startswith(b'OUTPUT_INCOMPLETE: Could not finish output ('))
        require(type(attempt['controlOutputFailure']) is bool and attempt['controlOutputFailure'] == control_failure,
                'close-control observed output-failure classification')
        eligible = passed and attempt['phase'] == 'sample' and attempt['telemetry']['valid']
        require(attempt['eligible'] == eligible, 'eligibility')
        # Reuse the independently maintained resource arithmetic auditor without
        # copying its counter logic. The adapter is a noneligible authored cell.
        core = copy.deepcopy(attempt)
        core.update(index=0, phase='sample', eligible=False)
        core['censored'] = core['outcome'] in ('timeout', 'output-limit', 'consumer-error', 'cancelled', 'telemetry-limit')
        audit_telemetry({'schemaVersion': 2, 'purpose': 'authored-child-qualification',
                         'elapsedRecord': {'attempts': [core], 'status': 'cancelled' if outcome == 'cancelled' else 'complete',
                                           'configuration': {'warmups': 0, 'repeats': 1, 'captureBytes': MAX_OUTPUT}},
                         'telemetry': [attempt['telemetry']]})
        valid += int(passed)
    require(counts == {(m, c): 12 for m in ('json', 'jsonl') for c in ('fast', 'slow')} |
            {(m, 'close'): 1 for m in ('json', 'jsonl')}, 'cell denominator')
    return {'attempts': len(attempts), 'completeOutputs': valid,
            'eligibleSamples': sum(a['eligible'] for a in attempts), 'closeControls': 2,
            'closeOutputFailures': sum(a['controlOutputFailure'] for a in attempts)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('record', type=Path)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--fixture-dir', type=Path, required=True)
    parser.add_argument('--source-revision', required=True)
    parser.add_argument('--source-freeze-sha256', required=True)
    args = parser.parse_args()
    with args.record.open('rb') as stream:
        data = stream.read(64 * 1024 * 1024 + 1)
    require(len(data) <= 64 * 1024 * 1024, 'record input bound')
    print(json.dumps(audit(json.loads(data), args.record.parent, args.binary, args.fixture_dir,
                           args.source_revision, args.source_freeze_sha256)))


if __name__ == '__main__':
    main()
