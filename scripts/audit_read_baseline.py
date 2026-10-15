"""Independently validate retained read captures and descriptive elapsed samples.

Private input paths, image identities and metadata never enter the public output.
This verifier imports no collector or measurement-runner code.
"""
import argparse
import collections
import copy
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import platform
import statistics
import sys


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, 'Duplicate JSON key')
        value[key] = item
    return value


def decode(data):
    def reject_constant(_value):
        raise ValueError('Non-finite JSON number')
    return json.loads(data, object_pairs_hook=unique_object, parse_constant=reject_constant)


def semantic_wire(value):
    # Python equality treats True == 1 and False == 0. Serialized canonical JSON
    # keeps JSON boolean and number types distinct for exact oracle comparisons.
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(',', ':'), allow_nan=False)


def load(path):
    return decode(Path(path).read_bytes())


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while block := stream.read(1024 * 1024):
            value.update(block)
    return value.hexdigest()


def normalized(document):
    """Normalize only invocation IDs and source display paths after checking IDs."""
    value = copy.deepcopy(document)
    request_id = value['requestId']
    require(isinstance(request_id, str) and request_id, 'Missing request ID')
    require(value['request']['requestId'] == request_id
            and value['summary']['requestId'] == request_id, 'Inconsistent request IDs')
    for field in [value, value['request'], value['summary']]:
        field['requestId'] = 'request'
    for item in value['files']:
        require(item['requestId'] == request_id, 'Inconsistent file request ID')
        item['requestId'] = 'request'
        item['path'] = 'input'
        snapshot = item.get('snapshot')
        if snapshot is not None:
            prefix = request_id + '-snapshot-'
            require(snapshot['id'].startswith(prefix), 'Unexpected snapshot ID')
            snapshot['id'] = 'request' + snapshot['id'][len(request_id):]
            for source in snapshot['sources']:
                source['displayPath'] = 'input'
    return value


def successful(document):
    summary = document['summary']
    files = document['files']
    return (document['schemaVersion'] == 1
            and document['request']['operation'] == 'metadata read'
            and summary['exitStatus'] == 0
            and summary['selectionComplete'] is True
            and summary['outputComplete'] is True
            and summary['interrupted'] is False and summary['artifacts'] == []
            and summary['counts'] == {'discovered': 1, 'excluded': 0,
                                      'deduplicated': 0, 'byState': {'read': 1}}
            and len(files) == 1 and files[0]['state'] == 'read'
            and files[0]['effects'] == {'publicationMayHaveOccurred': False,
                                       'changed': False, 'cleanupPending': False,
                                       'recoveryIds': [], 'notes': []}
            and bool(files[0]['snapshot']['coverage'])
            and all(item['state'] == 'partial' for item in files[0]['snapshot']['coverage']))


def distribution(samples):
    """Descriptive, success-conditional statistics; no trimming or inference."""
    if not samples:
        return None
    require(all(type(value) is int and value > 0 for value in samples), 'Invalid elapsed sample')
    ordered = sorted(samples)
    n = len(samples)
    median = statistics.median(ordered)
    mean = sum(samples) / n
    deviation = statistics.stdev(samples) if n > 1 else None
    return {'count': n, 'unit': 'nanoseconds', 'sum': sum(samples),
            'minimum': ordered[0], 'maximum': ordered[-1], 'mean': mean,
            'median': median, 'p95NearestRank': ordered[math.ceil(0.95 * n) - 1],
            'sampleStandardDeviation': deviation,
            'medianAbsoluteDeviation': statistics.median(abs(value - median) for value in samples),
            'coefficientOfVariation': deviation / mean if deviation is not None else None}


def audit_attempt(attempt, stdout, stderr, oracle, warmups, index, capture_bytes,
                  measurement_valid=True):
    require(attempt['index'] == index, 'Missing or reordered attempt')
    phase = 'warmup' if index < warmups else 'sample'
    require(attempt['phase'] == phase, 'Incorrect attempt phase')
    require(type(attempt['elapsedNs']) is int and attempt['elapsedNs'] > 0, 'Invalid elapsed duration')
    for name, wire in [('stdout', stdout), ('stderr', stderr)]:
        require(len(wire) <= capture_bytes, 'Capture exceeds declared retained bound')
        require(attempt[name + 'CapturedBytes'] == len(wire), 'Retained capture length mismatch')
        require(attempt[name + 'Bytes'] >= len(wire), 'Invalid drained byte count')
        expected = hashlib.sha256(wire).hexdigest()
        require(attempt[name + 'Sha256'] == expected
                or (attempt['outcome'] == 'launch-error' and not wire
                    and attempt[name + 'Sha256'] is None), 'Retained capture digest mismatch')
    outcome = attempt['outcome']
    require(outcome in {'exited', 'launch-error', 'timeout', 'output-limit', 'consumer-error'},
            'Unknown attempt outcome')
    require(attempt['censored'] is (outcome in {'timeout', 'output-limit', 'consumer-error'}),
            'Incorrect censor classification')
    valid = False
    if outcome == 'exited':
        require(attempt['stdoutBytes'] == len(stdout) and attempt['stderrBytes'] == len(stderr),
                'Exited process capture must include every drained byte')
        try:
            value = decode(stdout)
            valid = (attempt['exitCode'] == 0 and not stderr
                     and successful(value) and semantic_wire(normalized(value)) == oracle)
        except (ValueError, KeyError, TypeError, IndexError, RecursionError):
            valid = False
    correctness = ('pass' if valid else 'fail') if outcome == 'exited' else 'not-checked'
    require(attempt['correctness'] == correctness, 'Collector correctness claim disagrees with raw output')
    eligible = valid and phase == 'sample' and measurement_valid
    require(attempt['eligible'] is eligible, 'Collector eligibility claim disagrees with independent validation')
    return {key: attempt[key] for key in ['index', 'phase', 'elapsedNs', 'outcome',
                                          'exitCode', 'censored', 'correctness', 'eligible']}


def bounded_path(root, relative):
    path = (root / relative).resolve()
    require(path.is_relative_to(root.resolve()), 'Artifact path escapes run root')
    return path


def audit(run_root):
    root = Path(run_root).resolve()
    protocol_path = root / 'protocol.private.json'
    protocol = load(protocol_path)
    manifest = load(root / 'capture-manifest.private.json')
    require(protocol['schemaVersion'] == 1 and manifest['schemaVersion'] == 1, 'Unsupported schema')
    require(protocol['trialCount'] == 3 and len(protocol['trials']) == 3
            and protocol['interTrialDelaySeconds'] == 5, 'Wrong fixed predeclared schedule')
    require(manifest['status'] == 'completed', 'Aborted experiment is not a completed baseline')
    require(manifest['protocolSha256'] == sha(protocol_path), 'Protocol binding mismatch')
    repo = Path(__file__).resolve().parent.parent
    build = load(root / 'build-manifest.private.json')
    require(sha(root / 'build-manifest.private.json') == protocol['buildManifestSha256'],
            'Pinned build manifest changed')
    require(sha(root / 'source-verification.private.json') == build['sourceVerificationSha256'],
            'Frozen source verification binding changed')
    require(build['sourceRevision'] == protocol['sourceRevision'], 'Source revision mismatch')
    require(sha(root / 'environment-before.private.json') == protocol['beforeEnvironmentSha256'],
            'Pinned before-environment snapshot changed')
    fixed_public_protocol = root / 'public-protocol-as-fixed.private.json'
    published_public_protocol = repo / protocol['publicProtocolPath']
    require(sha(fixed_public_protocol) == protocol['publicProtocolSha256'],
            'Original preregistered public protocol binding changed')
    require(published_public_protocol.read_bytes()
            == fixed_public_protocol.read_bytes().replace(b'\r\n', b'\n'),
            'Published protocol differs beyond canonical LF line endings')
    for field, script in [('runnerSha256', 'measure_single_read.py'),
                          ('collectorSha256', 'read_benchmark.py')]:
        require(protocol[field] == manifest[field] == sha(repo / 'scripts' / script),
                'Actual measurement tooling binding mismatch')
    captures = {}
    for capture in manifest['captures']:
        key = capture['trial'], capture['attempt']
        require(key not in captures, 'Duplicate capture identity')
        captures[key] = capture
    records = {item['trial']: item for item in manifest['records']}
    require(len(records) == len(manifest['records']) == 3, 'Missing/duplicate trial record')
    require(len(captures) == 99, 'Every scheduled attempt must retain both captures')
    rows = []
    previous_end = None
    baseline_config = None
    for trial_index, specification in enumerate(protocol['trials'], 1):
        config_path = bounded_path(root, specification['config'])
        record_path = bounded_path(root, specification['record'])
        require(sha(config_path) == specification['sha256'], 'Pinned configuration changed')
        binding = records[trial_index]
        require(bounded_path(root, binding['path']) == record_path
                and sha(record_path) == binding['sha256'], 'Raw trial record binding mismatch')
        config = load(config_path)
        record = load(record_path)
        require(record['configuration'] == config, 'Collector used a different configuration')
        require(config['binarySha256'] == build['binarySha256'], 'Build/executable binding mismatch')
        require(config['warmups'] == 3 and config['repeats'] == 30
                and config['timeoutMs'] == 10000 and config['captureBytes'] == 1048576
                and config['maxBytes'] == 8388608 and config['fixtureId'] == 'FX-R5-001',
                'Fixed trial policy mismatch')
        comparison_config = copy.deepcopy(config)
        require(comparison_config['environment'].pop('trial') == trial_index,
                'Trial identity mismatch')
        if baseline_config is None:
            baseline_config = comparison_config
        require(comparison_config == baseline_config, 'Trials are not one fixed configuration stratum')
        require(record['driverSha256'] == protocol['collectorSha256'], 'Wrong collector executed')
        require(record['pythonExecutableSha256'] == sha(Path(sys.executable)),
                'Audit requires the same bound Python executable as collection')
        require(record['pythonVersion'] == platform.python_version(), 'Python version mismatch')
        for field in ('binary', 'input', 'oracle'):
            require(sha(config[field]) == config[field + 'Sha256'], 'Current artifact identity mismatch')
        require(record['sourceUnchanged'] is True and record['binaryUnchanged'] is True
                and record['status'] == 'completed', 'Invalid measurement retained but cannot form baseline')
        require(record['inputBytes'] == Path(config['input']).stat().st_size, 'Input length mismatch')
        require(record['argv'] == [config['binary'], 'metadata', 'read', '--values', 'all',
                                   '--output', 'json', '--max-bytes', str(config['maxBytes']),
                                   '--', config['input']], 'Command token mismatch')
        require(record['cwd'] == str(Path(config['binary']).parent), 'Working directory mismatch')
        for field in ('admissionEvidence', 'correctnessEvidence'):
            require(record['evidenceSha256'][field] == sha(config[field]), 'Evidence changed')
        admission = load(config['admissionEvidence'])
        correctness = load(config['correctnessEvidence'])
        require(admission['id'] == config['fixtureId'] and admission['admission'] == 'admitted'
                and admission['rights']['analyze'] is True
                and admission['rights']['redistribute'] is False
                and admission['privacy']['status'] == 'restricted'
                and admission['artifact']['sha256'] == config['inputSha256']
                and int(admission['artifact']['byteLength']) == record['inputBytes']
                and admission['media']['format'] == 'CR3'
                and admission['media']['captureMode'] == 'full-raw', 'Wrong lawful fixture stratum')
        require(correctness['execution'] == 'executed' and correctness['verdict'] == 'pass'
                and correctness['operation'] == 'read'
                and {'id': config['fixtureId'], 'sha256': config['inputSha256']} in correctness['fixtures']
                and correctness['candidate']['stdout']['sha256'] == config['oracleSha256'],
                'Wrong original correctness/oracle binding')
        raw_oracle = load(config['oracle'])
        require(successful(raw_oracle), 'Original oracle is not successful')
        oracle = semantic_wire(normalized(raw_oracle))
        require(len(record['attempts']) == 33, 'Every scheduled attempt must remain present')
        attempts = []
        for index, attempt in enumerate(record['attempts']):
            capture = captures[trial_index, index]
            wire = []
            for channel in ('stdout', 'stderr'):
                artifact = capture[channel]
                path = bounded_path(root, artifact['path'])
                require(sha(path) == artifact['sha256'] and path.stat().st_size == artifact['bytes'],
                        'Runner raw capture binding mismatch')
                wire.append(path.read_bytes())
            attempts.append(audit_attempt(attempt, *wire, oracle, 3, index, 1048576))
            started = datetime.fromisoformat(attempt['startedUtc'])
            require(started.tzinfo is not None, 'Attempt start must be timezone-qualified')
            require(datetime.fromisoformat(protocol['fixedUtc']) < started,
                    'Protocol was not fixed before attempt')
            if previous_end is not None:
                require(started.timestamp() >= previous_end, 'Overlapping/reordered attempts')
                if index == 0:
                    require(started.timestamp() - previous_end >= 5, 'Fixed intertrial gap not observed')
            previous_end = started.timestamp() + attempt['elapsedNs'] / 1e9
        samples = [item for item in attempts if item['phase'] == 'sample']
        eligible = [item['elapsedNs'] for item in samples if item['eligible']]
        first = [item['elapsedNs'] for item in samples[:10] if item['eligible']]
        last = [item['elapsedNs'] for item in samples[-10:] if item['eligible']]
        rows.append({'trial': trial_index, 'attempts': attempts,
                     'eligibleAttemptIndices': [item['index'] for item in samples if item['eligible']],
                     'successConditionalDistribution': distribution(eligible),
                     'firstTenAttemptWindow': {'eligible': len(first), 'medianNs': statistics.median(first) if first else None},
                     'lastTenAttemptWindow': {'eligible': len(last), 'medianNs': statistics.median(last) if last else None},
                     'lastMinusFirstWindowMedianNs': statistics.median(last) - statistics.median(first)
                     if first and last else None})
    all_attempts = [attempt for row in rows for attempt in row['attempts']]
    samples = [item for item in all_attempts if item['phase'] == 'sample']
    eligible = [item['elapsedNs'] for item in samples if item['eligible']]
    medians = [row['successConditionalDistribution']['median'] for row in rows
               if row['successConditionalDistribution'] is not None]
    return {'schemaVersion': 1, 'workload': 'single admitted R5 full RAW, all supported metadata, JSON',
            'auditorSha256': sha(Path(__file__)),
            'protocolSha256': sha(protocol_path),
            'sourceRevision': protocol['sourceRevision'],
            'binarySha256': build['binarySha256'],
            'publicProtocolSha256': protocol['publicProtocolSha256'],
            'publishedProtocolCanonicalLfSha256': sha(published_public_protocol),
            'publicProtocolPublicationTransform': 'original UTF-8 bytes with CRLF replaced by LF only',
            'trialCount': 3, 'scheduledAttempts': 99, 'warmupAttempts': 9, 'sampleAttempts': 90,
            'attemptsAuditedAgainstRetainedRawCaptures': len(all_attempts),
            'correctnessCounts': dict(collections.Counter(item['correctness'] for item in all_attempts)),
            'sampleOutcomeCounts': dict(collections.Counter(item['outcome'] for item in samples)),
            'sampleCorrectnessCounts': dict(collections.Counter(item['correctness'] for item in samples)),
            'sampleCensoredAttempts': sum(item['censored'] for item in samples),
            'eligibleSamples': len(eligible), 'allScheduledAttemptsRetained': True,
            'exclusionsOrOutlierTrimming': False,
            'pooledSuccessConditionalDistribution': distribution(eligible),
            'trialMedianSpanNs': max(medians) - min(medians) if medians else None,
            'trials': rows,
            'statisticsDefinitions': {'median': 'middle sorted value; even n midpoint',
                                      'p95': 'nearest rank ceil(0.95*n), one-based',
                                      'standardDeviation': 'sample standard deviation, denominator n-1',
                                      'MAD': 'median absolute distance from the sample median',
                                      'CV': 'sample standard deviation divided by arithmetic mean',
                                      'drift': 'last ten attempted sample positions median minus first ten; eligible counts reported',
                                      'inference': 'descriptive only; no confidence interval or independent-host replication'},
            'unmeasured': ['cold OS/device cache', 'CPU time', 'memory peak', 'physical I/O',
                           'first result', 'batch scaling', 'sessions', 'writes', 'default limit selection']}


def write_result(path, result):
    """Exclusive creation also refuses symlinks and names inserted after audit."""
    wire = (json.dumps(result, indent=2) + '\n').encode('utf-8')
    with Path(path).open('xb') as stream:
        stream.write(wire)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-root', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = audit(args.run_root)
    write_result(args.output, result)
    print('Independently audited 99 retained attempts; descriptive summary written')


if __name__ == '__main__':
    main()
