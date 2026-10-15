"""Independent #0063 retained batch audit. Camera-derived reports stay private.

Imports no collector/runner code. No media is read before linked private grants.
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
import re
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
ORDERS = [[1, 2, 4, 8], [8, 4, 2, 1], [2, 8, 1, 4]]
SIZES = (1, 2, 4, 8)
WARMUPS, REPEATS = 2, 10
CAPTURE_BYTES = 4194304
TIMEOUT_MS = 30000
MAX_BYTES = 8388608
MAX_JSON_BYTES = 16 * 1024 * 1024


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def decode(data):
    def members(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'Duplicate JSON member')
            result[key] = value
        return result

    def nonfinite(_value):
        raise ValueError('Non-finite JSON constant')

    result = json.loads(data, object_pairs_hook=members, parse_constant=nonfinite)

    def scalar_text(value):
        if isinstance(value, str):
            require(not any(0xD800 <= ord(char) <= 0xDFFF for char in value), 'Invalid Unicode scalar text')
        elif isinstance(value, dict):
            for key, item in value.items():
                scalar_text(key)
                scalar_text(item)
        elif isinstance(value, list):
            for item in value:
                scalar_text(item)

    scalar_text(result)
    return result


def load(path, limit=MAX_JSON_BYTES):
    with Path(path).open('rb') as stream:
        data = stream.read(limit+1)
    require(len(data) <= limit, 'JSON artifact exceeds audit bound')
    return decode(data)


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while block := stream.read(1024 * 1024):
            result.update(block)
    return result.hexdigest()


def wire(value):
    # Strict transport equality distinguishes JSON booleans from numbers.
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(',', ':'), allow_nan=False)


def schedule(orders=ORDERS):
    require(wire(orders) == wire(ORDERS), 'Grid/order differs from fixed preregistration')
    return [(round_index, size, index, 'warmup' if index < WARMUPS else 'sample')
            for round_index, order in enumerate(orders, 1) for size in order
            for index in range(WARMUPS+REPEATS)]


def normalized_file(item, request_id, index):
    require(type(request_id) is str and request_id, 'Missing request identity')
    require(item['requestId'] == request_id and item['inputId'] == f'input-{index}',
            'Incorrect file request/input identity or order')
    value = copy.deepcopy(item)
    value['requestId'] = 'request'
    value['inputId'] = 'input-0'
    value['path'] = 'input'
    for issue in value['issues']:
        require(issue['inputId'] in (None, f'input-{index}'), 'Inconsistent issue input identity')
        if issue['inputId'] is not None:
            issue['inputId'] = 'input-0'
    snapshot = value.get('snapshot')
    if snapshot is not None:
        expected_id = f'{request_id}-snapshot-{index}'
        require(snapshot['id'] == expected_id, 'Incorrect snapshot request/input binding')
        snapshot['id'] = 'snapshot'
        for source in snapshot['sources']:
            require(source['displayPath'] == item['path'], 'Source display path differs from file locator')
            source['displayPath'] = 'input'
        for issue in value['issues']:
            reference = issue['occurrenceRef']
            if reference is not None:
                require(reference['snapshotId'] == expected_id, 'Unbound external occurrence reference')
                reference['snapshotId'] = 'snapshot'
    return value


def normalized_envelope(document):
    value = copy.deepcopy(document)
    request_id = value['requestId']
    require(type(request_id) is str and request_id, 'Missing request identity')
    require(value['request']['requestId'] == request_id
            and value['summary']['requestId'] == request_id, 'Inconsistent envelope request identity')
    for row in (value, value['request'], value['summary']):
        row['requestId'] = 'request'
    value['files'] = [normalized_file(item, request_id, index)
                      for index, item in enumerate(document['files'])]
    return value


def oracle_files(oracles):
    """Retain the entire single-file contract, then derive only batch counts."""
    normalized = [normalized_envelope(document) for document in oracles]
    require(normalized, 'At least one independently bound oracle required')
    for document in normalized:
        require(type(document['schemaVersion']) is int and document['schemaVersion'] == 1 and len(document['files']) == 1
                and document['files'][0]['state'] == 'read', 'Oracle is not one successful file')
        require(wire(document['summary']['counts']) == wire({
            'discovered': 1, 'excluded': 0, 'deduplicated': 0, 'byState': {'read': 1}}),
            'Oracle count semantics are not one read')
        require(document['summary']['exitStatus'] == 0
                and document['summary']['outputComplete'] is True
                and document['summary']['selectionComplete'] is True
                and document['summary']['interrupted'] is False
                and document['summary']['artifacts'] == [], 'Incomplete or unsuccessful oracle')
        require(wire(document['files'][0]['effects']) == wire({
            'publicationMayHaveOccurred': False, 'changed': False,
            'cleanupPending': False, 'recoveryIds': [], 'notes': []}), 'Oracle has effects')
        require(document['files'][0]['snapshot']['coverage']
                and all(row['state'] == 'partial' for row in document['files'][0]['snapshot']['coverage']),
                'Oracle lacks explicit partial coverage')
        shape = {key: value for key, value in document.items() if key != 'files'}
        require(wire(shape) == wire({key: value for key, value in normalized[0].items() if key != 'files'}),
                'Oracle envelopes do not describe equivalent native work')
    return normalized


def classify(stdout, stderr, attempt, fixtures, oracles):
    slots = [{'fixtureId': fixture['id'], 'state': 'not-observed', 'correctness': 'not-checked'}
             for fixture in fixtures]
    if attempt['outcome'] != 'exited':
        return slots, 'not-checked'
    try:
        actual = decode(stdout)
        request_id = actual['requestId']
        for index, slot in enumerate(slots):
            if index >= len(actual['files']):
                continue
            item = actual['files'][index]
            require(item['path'] == fixtures[index]['input'], 'Observed file does not bind scheduled input position')
            normalized = normalized_file(item, request_id, index)
            slot['state'] = item['state'] if item['state'] in ('read', 'failed', 'refused') else 'not-observed'
            slot['correctness'] = ('pass' if wire(normalized)
                                   == wire(oracles[index]['files'][0]) else 'fail')
        expected = copy.deepcopy(oracles[0])
        expected['files'] = [document['files'][0] for document in oracles]
        expected['summary']['counts'] = {'discovered': len(fixtures), 'excluded': 0,
                                         'deduplicated': 0, 'byState': {'read': len(fixtures)}}
        complete = (attempt['exitCode'] == 0 and not stderr
                    and wire(normalized_envelope(actual)) == wire(expected))
        return slots, 'pass' if complete else 'fail'
    except (ValueError, KeyError, TypeError, IndexError, RecursionError):
        return slots, 'fail'


def audit_attempt(attempt, stdout, stderr, fixtures, oracles, slot, measurement_valid=True):
    round_index, size, index, phase = slot
    require(wire([attempt['round'], attempt['size'], attempt['index'], attempt['phase']])
            == wire([round_index, size, index, phase]), 'Missing/reordered/duplicate attempt')
    require(type(attempt['elapsedNs']) is int and attempt['elapsedNs'] > 0, 'Invalid integer elapsed time')
    outcome = attempt['outcome']
    require(outcome in {'exited', 'launch-error', 'timeout', 'output-limit', 'consumer-error'},
            'Unsupported retained attempt outcome')
    require(attempt['censored'] is (outcome in {'timeout', 'output-limit', 'consumer-error'}),
            'Incorrect censor classification')
    for channel, captured in [('stdout', stdout), ('stderr', stderr)]:
        require(len(captured) <= CAPTURE_BYTES, 'Captured bytes exceed preregistered bound')
        require(type(attempt[channel+'Bytes']) is int and attempt[channel+'Bytes'] >= len(captured),
                'Invalid drained byte count')
        require(type(attempt[channel+'CapturedBytes']) is int
                and attempt[channel+'CapturedBytes'] == len(captured), 'Captured byte count mismatch')
        require(attempt[channel+'Sha256'] == hashlib.sha256(captured).hexdigest()
                or outcome == 'launch-error' and not captured and attempt[channel+'Sha256'] is None,
                'Capture digest mismatch')
        if outcome == 'exited':
            require(attempt[channel+'Bytes'] == len(captured), 'Complete exit requires complete capture')
    files, correctness = classify(stdout, stderr, attempt, fixtures, oracles)
    require(wire(attempt['files']) == wire(files), 'Per-file outcomes disagree with actual retained output')
    require(attempt['batchCorrectness'] == correctness, 'Whole-batch correctness claim differs')
    eligible = phase == 'sample' and correctness == 'pass' and measurement_valid
    require(attempt['eligible'] is eligible, 'Eligibility differs from independent correctness/stability gate')
    return {key: copy.deepcopy(attempt[key]) for key in (
        'round', 'size', 'index', 'phase', 'elapsedNs', 'outcome', 'exitCode', 'censored',
        'files', 'batchCorrectness', 'eligible')}


def distribution(values):
    if not values:
        return None
    require(all(type(value) is int and value > 0 for value in values), 'Invalid elapsed distribution input')
    ordered = sorted(values)
    count = len(values)
    median = statistics.median(ordered)
    mean = sum(values)/count
    deviation = statistics.stdev(values) if count > 1 else None
    return {'count': count, 'unit': 'nanoseconds', 'sum': sum(values),
            'minimum': ordered[0], 'maximum': ordered[-1], 'median': median, 'mean': mean,
            'p95NearestRank': ordered[math.ceil(0.95*count)-1],
            'sampleStandardDeviation': deviation,
            'medianAbsoluteDeviation': statistics.median(abs(value-median) for value in values),
            'coefficientOfVariation': deviation/mean if deviation is not None else None}


def derived_rate_distribution(durations, size):
    if not durations:
        return None
    values = [size*1e9/value for value in durations]
    ordered = sorted(values)
    mean = sum(values)/len(values)
    deviation = statistics.stdev(values) if len(values) > 1 else None
    return {'unit': 'files/second', 'definition': 'size / whole-batch elapsed seconds; success-conditional',
            'count': len(values), 'minimum': ordered[0], 'maximum': ordered[-1], 'mean': mean,
            'median': statistics.median(ordered), 'p95NearestRank': ordered[math.ceil(.95*len(values))-1],
            'sampleStandardDeviation': deviation,
            'coefficientOfVariation': deviation/mean if deviation is not None else None}


def summarize(attempts):
    rows = []
    for size in SIZES:
        cells = []
        for round_index in range(1, 4):
            items = [a for a in attempts if a['round'] == round_index and a['size'] == size]
            samples = [a for a in items if a['phase'] == 'sample']
            valid = [a['elapsedNs'] for a in samples if a['eligible']]
            windows = []
            for start, end in ((2, 7), (7, 12)):
                values = [a['elapsedNs'] for a in samples if start <= a['index'] < end and a['eligible']]
                windows.append({'attemptIndexRange': [start, end], 'eligible': len(values),
                                'medianNs': statistics.median(values) if values else None})
            cells.append({'round': round_index, 'plannedAttempts': 12, 'attempted': len(items),
                          'plannedSamples': 10, 'eligibleSamples': len(valid),
                          'successConditionalBatchElapsed': distribution(valid), 'attemptWindows': windows})
        samples = [a for a in attempts if a['size'] == size and a['phase'] == 'sample']
        values = [a['elapsedNs'] for a in samples if a['eligible']]
        medians = [c['successConditionalBatchElapsed']['median'] for c in cells
                   if c['successConditionalBatchElapsed'] is not None]
        rows.append({'size': size, 'plannedBatchSamples': 30, 'attemptedSamples': len(samples),
                     'plannedFileSampleOpportunities': size*30,
                     'eligibleBatchSamples': len(values), 'eligibleFileSampleOpportunities': size*len(values),
                     'successConditionalBatchElapsed': distribution(values),
                     'successConditionalFilesPerSecond': derived_rate_distribution(values, size),
                     'amortizedCostDefinition': 'batch elapsed / size, not measured per-file latency',
                     'amortizedBatchMeanNsPerInput': sum(values)/len(values)/size if values else None,
                     'roundMedianSpanNs': max(medians)-min(medians) if medians else None, 'rounds': cells})
    return {'plannedBatchAttempts': 144, 'plannedWarmups': 24, 'plannedSamples': 120,
            'plannedFileOpportunities': 540, 'plannedWarmupFileOpportunities': 90,
            'plannedSampleFileOpportunities': 450, 'attemptedBatchAttempts': len(attempts),
            'unrecordedBatchOpportunities': 144-len(attempts),
            'attemptedMeasuredBatchSamples': sum(a['phase'] == 'sample' for a in attempts),
            'unrecordedMeasuredBatchOpportunities': 120-sum(a['phase'] == 'sample' for a in attempts),
            'attemptedFileOpportunities': sum(a['size'] for a in attempts),
            'sampleOutcomeCounts': dict(collections.Counter(a['outcome'] for a in attempts if a['phase'] == 'sample')),
            'sampleCorrectnessCounts': dict(collections.Counter(a['batchCorrectness'] for a in attempts if a['phase'] == 'sample')),
            'sampleCensoredAttempts': sum(a['censored'] for a in attempts if a['phase'] == 'sample'),
            'bySize': rows, 'allAttempts': attempts, 'exclusionsOrOutlierTrimming': False,
            'statisticsScope': 'descriptive success-conditional within size; adjacent rounds, not independent hosts',
            'unavailablePerFileLatencyNs': None}


def rights_before_data(protocol):
    """Read permission evidence first; never touch oracle/capture/media here."""
    admission = protocol['taskAdmission']
    require(admission['ticket'] == 63 and admission['scope'] == 'private-read-only-batch-analysis'
            and admission['sourceMutationAllowed'] is False, 'Wrong bounded task admission')
    fixtures = protocol['fixtureSet']
    require([fixture['id'] for fixture in fixtures] == [f'FX-R5-{index:03}' for index in range(1, 9)],
            'Wrong fixed eight-fixture order')
    require(len({str(Path(fixture['input']).resolve()) for fixture in fixtures}) == 8,
            'Fixture paths must be distinct')
    required_paths = {protocol['primaryGrant'], protocol['privacyReview']}
    required_paths.update(fixture[key] for fixture in fixtures for key in ('admission', 'provenance', 'correctness'))
    require(required_paths <= set(protocol['evidenceSha256']), 'Unbound grant/admission/correctness evidence')
    for path, expected in protocol['evidenceSha256'].items():
        require(digest(path) == expected, 'Pinned evidence changed')
    grant = load(protocol['primaryGrant'])
    review = load(protocol['privacyReview'])
    require(grant['originals'] == 'never opened for writing', 'Original-source mutation not authorized')
    require(review['status'] == 'restricted' and review['publicClearance'] is False,
            'This protocol requires restricted private handling')
    report_permissions = []
    for fixture in fixtures:
        admitted = load(fixture['admission'])
        provenance = load(fixture['provenance'])
        correctness = load(fixture['correctness'])
        require(admitted['id'] == fixture['id'] and admitted['admission'] == 'admitted'
                and type(admitted['revision']) is int and admitted['revision'] >= 2
                and admitted['rights']['analyze'] is True
                and admitted['artifact']['sha256'] == fixture['inputSha256']
                and admitted['media']['format'] == 'CR3'
                and admitted['media']['captureMode'] == 'full-raw', 'Wrong admitted full RAW fixture')
        permission = provenance['rights']['permissions']
        require(provenance['review']['state'] == 'approved' and provenance['purpose'] == 'operational'
                and type(provenance['revision']) is int and provenance['revision'] >= 2
                and provenance['artifact']['sha256'] == fixture['inputSha256']
                and permission['store'] == 'allowed' and permission['analyze'] == 'allowed',
                'Private fixture analysis permission is absent')
        links = {item['id']: item for item in provenance['evidence']}
        require(links['EV-GRANT']['sha256'] == protocol['evidenceSha256'][protocol['primaryGrant']]
                and links['EV-PRIVACY']['sha256'] == protocol['evidenceSha256'][protocol['privacyReview']],
                'Fixture does not link the pinned primary permission/privacy evidence')
        require(correctness['execution'] == 'executed' and correctness['verdict'] == 'pass'
                and correctness['operation'] == 'read'
                and {'id': fixture['id'], 'sha256': fixture['inputSha256']} in correctness['fixtures']
                and correctness['candidate']['stdout']['sha256'] == fixture['oracleSha256'],
                'Prior independent oracle is not bound to this exact fixture')
        report_permissions.append(permission['publishReports'] == 'allowed')
    return {'analysisAllowed': True, 'publishReportsAllowed': all(report_permissions),
            'publicCameraResultsExported': False}


def build_binding(protocol):
    require({protocol['buildManifest'], protocol['sourceVerification']} <= set(protocol['evidenceSha256']),
            'Build/source verification evidence must be preregistered')
    build = load(protocol['buildManifest'])
    verified = load(protocol['sourceVerification'])
    revision = protocol['sourceRevision']
    require(type(revision) is str and re.fullmatch(r'[0-9a-f]{40}', revision), 'Exact Git revision required')
    require(build['sourceRevision'] == verified['sourceRevision'] == revision
            and build['binarySha256'] == protocol['binarySha256']
            and build['sourceVerificationSha256'] == digest(protocol['sourceVerification']),
            'Build/source/executable identities disagree')
    source = Path(build['sourcePath']).resolve()
    require(source.is_relative_to(ROOT/'.local'), 'Frozen source must remain in the declared local workspace')
    require(digest(source/'Cargo.lock') == build['cargoLockSha256'], 'Frozen lockfile changed')
    tree = subprocess.check_output(['git', 'ls-tree', '-rz', revision], cwd=ROOT)
    rows = [row for row in tree.split(b'\0') if row]
    require(type(verified['trackedBlobsCompared']) is int and verified['trackedBlobsCompared'] == len(rows)
            and verified['mismatches'] == 0, 'Incomplete original frozen source verification')
    for row in rows:
        details, relative = row.split(b'\t', 1)
        _mode, kind, expected = details.split()
        require(kind == b'blob', 'Unexpected source-tree entry type')
        data = (source/relative.decode('utf-8')).read_bytes()
        actual = hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest().encode()
        require(actual == expected, 'Frozen source differs from exact tracked Git bytes')
    return {'sourceRevision': revision, 'trackedBlobsIndependentlyCompared': len(rows),
            'lockfileBound': True, 'binaryBuildBound': True}


def bounded_path(root, relative):
    require(type(relative) is str and not Path(relative).is_absolute(), 'Relative capture path required')
    path = (root/relative).resolve()
    require(path.is_relative_to(root.resolve()), 'Capture path escapes retained run')
    return path


def source_checks(record, protocol):
    checks = record['sourceChecks']
    expected = [(round_index, boundary) for round_index in range(1, 4) for boundary in ('before', 'after')]
    require(len(checks) <= 6, 'Excess or adaptive source checks')
    if record['status'] == 'completed':
        require(len(checks) == 6, 'A completed grid needs all six source boundaries')
    baseline = None
    all_unchanged = True
    for check, (round_index, boundary) in zip(checks, expected):
        require(check['round'] == round_index and check['boundary'] == boundary,
                'Missing/reordered source boundary')
        rows = check['fixtures']
        require([row['fixtureId'] for row in rows] == [f['id'] for f in protocol['fixtureSet']],
                'Every source boundary must retain all eight fixture slots')
        if baseline is None:
            baseline = rows
        unchanged = wire(rows) == wire(baseline) and all(
            row['sha256'] == fixture['inputSha256'] for row, fixture in zip(rows, protocol['fixtureSet']))
        require(check['unchanged'] is unchanged, 'Source stability flag differs from retained observations')
        require(len({(row['device'], row['inode']) for row in rows}) == 8,
                'Source identities alias; CLI dedup changes the denominator')
        all_unchanged = all_unchanged and unchanged
    for fixture in protocol['fixtureSet']:
        path = Path(fixture['input'])
        stat = path.stat()
        require(stat.st_size <= 1024*1024*1024, 'Source exceeds finite audit bound')
        require(digest(path) == fixture['inputSha256'], 'Current source bytes changed')
        if baseline is not None:
            row = next(item for item in baseline if item['fixtureId'] == fixture['id'])
            require(wire([row['bytes'], row['mtimeNs'], row['device'], row['inode']])
                    == wire([stat.st_size, stat.st_mtime_ns, stat.st_dev, stat.st_ino]),
                    'Current source identity/length/mtime differs from recorded baseline')
    return all_unchanged


def audit(run_root):
    root = Path(run_root).resolve()
    require(root.is_relative_to(ROOT/'.local'), 'Camera records are private local artifacts')
    protocol_path = root/'protocol.private.json'
    protocol = load(protocol_path)
    require(type(protocol['schemaVersion']) is int and protocol['schemaVersion'] == 1
            and protocol['revision'] == 'batch-read-v1', 'Wrong preregistered protocol revision')
    slots = schedule(protocol['orders'])
    require(wire([protocol['warmups'], protocol['repeats'], protocol['timeoutMs'], protocol['captureBytes'], protocol['maxBytes']])
            == wire([WARMUPS, REPEATS, TIMEOUT_MS, CAPTURE_BYTES, MAX_BYTES]), 'Preregistered budgets changed')
    rights = rights_before_data(protocol)
    build = build_binding(protocol)
    record = load(root/'record.private.json')
    require(record['protocolSha256'] == digest(protocol_path), 'Protocol changed after collection')
    require(record['status'] in ('completed', 'aborted'), 'Unknown run completion state')
    require(wire(record['rights']) == wire(rights), 'Recorded grant handling differs from actual rights')
    require(record['elapsedUnit'] == 'nanoseconds' and record['pythonVersion'] == platform.python_version()
            and record['pythonExecutableSha256'] == digest(sys.executable), 'Executed runtime identity mismatch')
    require(record['pythonVersion'] == protocol['pythonVersion']
            and record['pythonExecutableSha256'] == protocol['pythonExecutableSha256'],
            'Executed Python differs from preregistration')
    require(digest(ROOT/'scripts/measure_batch_read.py') == protocol['runnerSha256']
            and digest(ROOT/'scripts/read_benchmark.py') == protocol['collectorSha256'], 'Measurement source identity mismatch')
    current_binary = digest(protocol['binary']) == protocol['binarySha256']
    require(record['binaryUnchanged'] is current_binary or record['status'] == 'aborted', 'Executable stability claim differs')
    require(current_binary, 'Current executed binary binding changed')
    require(record['cwd'] == str(Path(protocol['binary']).parent), 'Command working-directory mismatch')
    require(record['clock']['name'] == 'time.perf_counter_ns'
            and record['clock']['boundary'] == 'before Popen through direct exit and both bounded pipe drains; evidence writes/validation excluded; overhead not subtracted',
            'End-to-end timer boundary changed')
    require(type(record['clock']['resolutionSeconds']) in (int, float)
            and 0 < record['clock']['resolutionSeconds'] < 1, 'Clock resolution unavailable/invalid')
    require(record['cache'] == {
        'process': 'fresh per batch', 'application': 'no persistent session',
        'os': 'warm-exposed/uncontrolled: all eight whole-source hashes before each round',
        'device': 'uncontrolled', 'server': 'not established',
        'conditioning': 'no eviction; fixed grid order and 5-second round gaps'}, 'Cache stratum was mislabeled')
    require(record['unavailableTelemetry'] == dict.fromkeys((
        'perFileLatencyNs', 'firstResultNs', 'cpuNs', 'peakMemoryBytes', 'logicalIoBytes', 'physicalIoBytes')),
        'Unavailable telemetry must be null, not zero or invented per-file phases')
    for key, value in {'LC_ALL': 'C', 'LANG': 'C', 'TZ': 'UTC'}.items():
        require(record['processEnvironment'][key] == value, 'Process environment differs')
    source_stable = source_checks(record, protocol)
    valid_measurement = record['status'] == 'completed' and source_stable and record['binaryUnchanged'] is True
    raw_oracles = []
    for fixture in protocol['fixtureSet']:
        require(digest(fixture['oracle']) == fixture['oracleSha256'], 'Bound prior oracle changed')
        raw_oracles.append(load(fixture['oracle'], CAPTURE_BYTES))
    oracles = oracle_files(raw_oracles)
    attempts = record['attempts']
    require(len(attempts) <= len(slots), 'Excess/retried/adaptive attempts')
    if record['status'] == 'completed':
        require(len(attempts) == len(slots), 'Completed report omitted planned attempts')
    require(record['completedAttempts'] == len(attempts)
            and record['remainingScheduledAttempts'] == len(slots)-len(attempts), 'Attempt denominator claims differ')
    require(record['abortEligibilityInvalidated'] is (record['status'] == 'aborted'), 'Abort eligibility scope differs')
    if record['status'] == 'aborted':
        require(record.get('abortReason'), 'Aborted collection needs an explicit retained reason')
    ledger = (root/'attempts.private.jsonl').read_bytes().splitlines()
    require(len(ledger) == len(attempts), 'Append-only attempt ledger is incomplete')
    checked = []
    capture_paths = set()
    previous_end = None
    previous_round = None
    for attempt, logged, slot in zip(attempts, ledger, slots):
        original = decode(logged)
        require(wire({k: v for k, v in original.items() if k != 'eligible'})
                == wire({k: v for k, v in attempt.items() if k != 'eligible'}), 'Final record differs from retained attempt ledger')
        if record['status'] == 'completed':
            require(original['eligible'] is attempt['eligible'], 'Completed eligibility changed after collection')
        size = slot[1]
        fixtures = protocol['fixtureSet'][:size]
        require(attempt['argv'] == [protocol['binary'], 'metadata', 'read', '--values', 'all', '--output', 'json',
                                    '--max-bytes', str(MAX_BYTES), '--', *[f['input'] for f in fixtures]],
                'Actual invocation differs from preregistered distinct input prefix')
        channels = []
        for channel in ('stdout', 'stderr'):
            expected_capture = f'captures/r{slot[0]}-n{slot[1]}-a{slot[2]:02d}.{channel}'
            require(attempt['captures'][channel] == expected_capture, 'Capture path does not bind exact attempt')
            require(expected_capture not in capture_paths, 'A retained capture was reused')
            capture_paths.add(expected_capture)
            path = bounded_path(root, attempt['captures'][channel])
            with path.open('rb') as stream:
                captured = stream.read(CAPTURE_BYTES+1)
            channels.append(captured)
        checked.append(audit_attempt(attempt, *channels, fixtures, oracles[:size], slot, valid_measurement))
        start = datetime.fromisoformat(attempt['startedUtc'])
        require(start.tzinfo is not None and datetime.fromisoformat(protocol['fixedUtc']) < start,
                'Protocol was not fixed before attempts')
        if previous_end is not None:
            require(start.timestamp() >= previous_end, 'Attempts overlap or reorder')
            if slot[0] != previous_round:
                require(start.timestamp()-previous_end >= 5, 'Declared inter-round gap absent')
        previous_end = start.timestamp()+attempt['elapsedNs']/1e9
        previous_round = slot[0]
    actual_captures = {path.relative_to(root).as_posix() for path in (root/'captures').iterdir()}
    orphan_captures = sorted(actual_captures-capture_paths)
    if record['status'] == 'completed':
        require(actual_captures == capture_paths, 'Completed report omits or invents retained captures')
    result = summarize(checked)
    result.update(schemaVersion=1, kind='private-batch-read-audit', protocolSha256=digest(protocol_path),
                  auditorSha256=digest(__file__), sourceRevision=protocol['sourceRevision'],
                  binarySha256=protocol['binarySha256'], rights=rights, status=record['status'],
                  buildVerification=build, currentSourceChecksPassed=source_stable,
                  sourceBoundaryAgreement=source_stable and bool(record['sourceChecks']),
                  sourceMutationPerformedByAuditor=False,
                  unreconciledCaptureArtifactsRetained=orphan_captures,
                  unrecordedSuffixMeaning='not completed/recorded; orphan captures may identify a started attempt without a terminal record',
                  noPublicCameraResults=True)
    return result


def write_private(path, result):
    destination = Path(path).resolve()
    require(destination.is_relative_to(ROOT/'.local'), 'Camera-derived statistics/reports cannot be published outside .local')
    with destination.open('xb') as stream:
        stream.write((json.dumps(result, indent=2)+'\n').encode('utf-8'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='fresh ignored private .local output only')
    args = parser.parse_args()
    write_private(args.output, audit(args.run_root))
    print('Independent batch audit retained privately; no camera-derived statistics exported')
