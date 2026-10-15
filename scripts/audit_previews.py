"""Independent retained-artifact audit for the authored-only preview experiment.

No measurement-runner imports or camera input support. Elapsed times are observed
process durations; this audit verifies their accounting, not clock authenticity.
"""
import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
TAGS = ('ThumbnailImage', 'PreviewImage', 'JpgFromRaw')
LENGTHS = (4096, 65536, 1048583)


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def decode(data):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'Duplicate JSON member')
            result[key] = value
        return result

    def nonfinite(_):
        raise ValueError('Nonfinite JSON number')

    return json.loads(data, object_pairs_hook=unique, parse_constant=nonfinite)


def load(path, limit=16*1024*1024):
    with Path(path).open('rb') as stream:
        data = stream.read(limit+1)
    require(len(data) <= limit, 'Artifact exceeds audit byte bound')
    return decode(data)


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while block := stream.read(1024*1024):
            result.update(block)
    return result.hexdigest()


def wire(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def bounded(root, relative):
    require(type(relative) is str and not Path(relative).is_absolute(), 'Relative retained path required')
    result = (root/relative).resolve()
    require(result.is_relative_to(root.resolve()), 'Retained path escapes run root')
    return result


def distribution(values):
    if not values:
        return None
    ordered = sorted(values)
    return {'n': len(values), 'minNs': ordered[0], 'medianNs': statistics.median(ordered),
            'p95NearestRankNs': ordered[math.ceil(.95*len(ordered))-1], 'maxNs': ordered[-1],
            'totalNs': sum(values)}


def resource_check(document, source, references):
    """Check named occurrence-to-resource bindings and exact stored source spans."""
    require(len(document['files']) == 1 and document['files'][0]['state'] == 'read',
            'Listing must contain one successful source')
    snapshot = document['files'][0]['snapshot']
    require(snapshot['coverage'] and all(row['state'] == 'partial' for row in snapshot['coverage']),
            'Listing must retain partial coverage')
    occurrences = snapshot['occurrences']
    require([row['tag']['name'] for row in occurrences] == list(TAGS), 'Named resource order/count differs')
    resources = {row['id']: row for row in snapshot['resources']}
    require(len(resources) == len(snapshot['resources']), 'Duplicate resource identity')
    require(source.stat().st_size <= 2*1024*1024, 'Authored source bound exceeded')
    raw = source.read_bytes()
    results = {}
    for occurrence, tag, length in zip(occurrences, TAGS, LENGTHS):
        reference = occurrence['values']['raw']['value']['resourceRef']
        require(occurrence['origin']['resourceRef'] == reference
                and occurrence['values']['normalized']['value']['resourceRef'] == reference,
                'Resource occurrence binding differs')
        resource = resources[reference]
        require(resource['byteLength'] == str(length) and resource['mediaType'] == 'image/jpeg',
                'Resource length/type differs')
        content = resource['content']
        require(content['kind'] == 'source-ranges' and len(content['ranges']) == 1,
                'Expected exactly one stored source range')
        span = content['ranges'][0]
        offset, size = int(span['offset']), int(span['length'])
        require(span['ref'] == 'src-raw' and span['space'] == 'source' and size == length
                and offset >= 0 and offset+size <= len(raw), 'Invalid stored source range')
        stored = raw[offset:offset+size]
        expected = references[tag].read_bytes()
        require(stored == expected and len(expected) == length,
                'Named stored range differs from independent authored resource')
        results[tag] = {'bytes': size, 'sha256': hashlib.sha256(stored).hexdigest(), 'offset': offset}
    return results


def schedule():
    cells = []
    for operation, tag in [('list', None)] + [('extract', tag) for tag in TAGS]:
        for index in range(12):
            cells.append({'operation': operation, 'tag': tag,
                          'phase': 'warmup' if index < 2 else 'sample', 'expected': 'success'})
    for expected in ('collision', 'preview-limit'):
        cells.extend({'operation': 'extract', 'tag': tag, 'phase': 'control', 'expected': expected} for tag in TAGS)
    return cells


def process_check(row, stdout, stderr, cap):
    require(type(row['elapsedNs']) is int and row['elapsedNs'] > 0, 'Invalid actual elapsed duration')
    outcome = row['outcome']
    require(outcome in ('exited', 'launch-error', 'timeout', 'output-limit', 'consumer-error'), 'Unknown outcome')
    require(row['censored'] is (outcome in ('timeout', 'output-limit', 'consumer-error')), 'Censor classification differs')
    require(type(row['exitCode']) is int or outcome == 'launch-error' and row['exitCode'] is None,
            'Invalid process exit status')
    for channel, data in [('stdout', stdout), ('stderr', stderr)]:
        require(len(data) <= cap and type(row[channel+'Bytes']) is int
                and row[channel+'Bytes'] >= len(data)
                and type(row[channel+'CapturedBytes']) is int
                and row[channel+'CapturedBytes'] == len(data), 'Capture byte accounting differs')
        expected = None if outcome == 'launch-error' else hashlib.sha256(data).hexdigest()
        require(row[channel+'Sha256'] == expected, 'Retained capture digest differs')
        if outcome == 'exited':
            require(row[channel+'Bytes'] == len(data), 'Exited sample has incomplete capture')


def envelope_check(document, row, source, target):
    request = document['requestId']
    require(type(document['schemaVersion']) is int and document['schemaVersion'] == 1,
            'Envelope version differs')
    require(document['request']['requestId'] == document['summary']['requestId'] == request,
            'Envelope request identity differs')
    require(document['request']['operation'] == 'binary '+row['operation']
            and document['request']['mode'] == 'read', 'Operation/mode differs')
    files, summary = document['files'], document['summary']
    require(len(files) == 1 and files[0]['path'] == str(source)
            and files[0]['requestId'] == request and files[0]['inputId'] == 'input-0', 'Input identity differs')
    require(wire(files[0]['effects']) == wire({'publicationMayHaveOccurred': False, 'changed': False,
        'cleanupPending': False, 'recoveryIds': [], 'notes': []}), 'Unexpected source effects')
    require(summary['selectionComplete'] is True and summary['outputComplete'] is True
            and summary['interrupted'] is False, 'Incomplete result')
    success = row['expected'] == 'success'
    state, status = ('read', 0) if success else ('failed', 1)
    require(files[0]['state'] == state and type(summary['exitStatus']) is int
            and summary['exitStatus'] == row['exitCode'] == status, 'Observed result differs from scheduled outcome')
    require(wire(summary['counts']) == wire({'discovered': 1, 'excluded': 0, 'deduplicated': 0,
        'byState': {state: 1}}), 'Result denominator differs')
    if success and row['operation'] == 'extract':
        require(summary['artifacts'] == [{'kind': 'extraction', 'path': str(target), 'retainedPath': None,
            'state': 'committed', 'transactionId': None, 'recoveryIds': []}], 'Extraction artifact differs')
    else:
        require(summary['artifacts'] == [], 'Unexpected artifact')
    if not success:
        code = 'DESTINATION_EXISTS' if row['expected'] == 'collision' else 'LIMIT_EXCEEDED'
        require([issue['code'] for issue in files[0]['issues']] == [code], 'Expected refusal code differs')


def file_identity(path):
    stat = path.stat()
    return {'sha256': digest(path), 'bytes': stat.st_size, 'mtimeNs': stat.st_mtime_ns}


def output_inventory(root, attempts, completed):
    expected = {str(root/'outputs'/(row['id']+'.bin')) for row in attempts if row['targetAfter'] is not None}
    actual = {str(path) for path in (root/'outputs').iterdir()}
    require(not completed or actual == expected, 'Completed report omits retained output/temp artifacts')
    return sorted(actual-expected)


def audit(run_root, protocol_path):
    root = Path(run_root).resolve()
    require(root.is_relative_to(ROOT/'.local'), 'Retained measurements must remain private')
    record, p = load(root/'record.json'), load(protocol_path)
    require(wire(record['protocol']) == wire(p) and record['protocolSha256'] == digest(protocol_path),
            'Protocol binding changed')
    require(p['protocolRevision'] == record['collectorRevision'] == 'preview-collector-v1'
            and p['fixtureKind'] == 'authored-structural-no-camera-data'
            and p['warmups'] == 2 and p['repeats'] == 10, 'Authored fixed schedule required')
    require([item['tag'] for item in p['resources']] == list(TAGS)
            and [item['bytes'] for item in p['resources']] == list(LENGTHS), 'Resource denominator changed')
    for name, expected in p['sourcePins'].items():
        require(digest(ROOT/name) == expected, 'Pinned source changed')
    require(digest(record['binary']) == p['binarySha256'], 'Executed binary changed')
    source = Path(record['source'])
    require(source.is_relative_to(ROOT/'.local') and source.stat().st_size <= 2*1024*1024,
            'Only bounded local authored source supported')
    require(digest(source) == p['sourceSha256'] and source.stat().st_size == p['sourceBytes'], 'Source bytes changed')
    require(file_identity(source) == record['sourceBefore'] == record['sourceAfter'], 'Source boundary differs')
    references = {tag: source.parent/(tag+'.bin') for tag in TAGS}
    for expected in p['resources']:
        require(digest(references[expected['tag']]) == expected['sha256'], 'Authored resource changed')
    require(record['status'] in ('completed', 'invalid-measurement', 'aborted'), 'Unknown measurement status')
    complete = record['status'] == 'completed'
    require(record['plannedAttempts'] == 54 and record['remainingAttempts'] == 54-len(record['attempts']),
            'Retained planned/remaining denominator differs')
    require(record['clock']['name'] == 'time.perf_counter_ns'
            and record['clock']['boundary'] == 'before direct Popen through process exit and both pipe drains; no overhead subtraction'
            and type(record['clock']['resolutionSeconds']) in (int, float)
            and 0 < record['clock']['resolutionSeconds'] < 1, 'Clock boundary/resolution differs')
    require(digest(record['python']['path']) == record['python']['sha256'], 'Executed Python identity changed')
    require(set(record['unavailableTelemetry']) == {'cpuNs', 'memoryBytes', 'physicalIoBytes', 'firstResultNs', 'scratchAllocatedBytes'}
            and all(item['value'] is None and item['reason'] for item in record['unavailableTelemetry'].values()),
            'Unavailable telemetry must retain nulls with reasons')
    attempts, planned = record['attempts'], schedule()
    require(len(attempts) <= len(planned) and (not complete or len(attempts) == len(planned)),
            'Missing/excess completed samples')
    used, groups, outcomes = set(), {}, Counter()
    resource_hashes = None
    previous_end = None
    for index, (row, cell) in enumerate(zip(attempts, planned)):
        require(all(wire(row[key]) == wire(value) for key, value in cell.items())
                and row['id'] == f'attempt-{index:03}', 'Missing/reordered/duplicate scheduled attempt')
        target = root/'outputs'/(row['id']+'.bin') if cell['operation'] == 'extract' else None
        require(row['target'] == (str(target) if target else None), 'Destination differs from unique scheduled path')
        argv = [record['binary'], 'binary', cell['operation'], '--output', 'json', '--max-bytes', str(p['maxBytes'])]
        if target:
            argv += ['--tag', cell['tag'], '--output-file', str(target), '--max-preview-bytes',
                     '1' if cell['expected'] == 'preview-limit' else str(p['maxPreviewBytes'])]
        require(row['argv'] == argv+['--', str(source)] and row['cwd'] == str(ROOT), 'Actual command differs')
        captures = []
        for channel in ('stdout', 'stderr'):
            path = root/'captures'/(row['id']+'.'+channel)
            require(row['captures'][channel] == str(path) and str(path) not in used, 'Capture identity differs')
            used.add(str(path))
            with path.open('rb') as stream:
                captures.append(stream.read(p['captureBytes']+1))
        process_check(row, *captures, p['captureBytes'])
        start = datetime.fromisoformat(row['startedUtc'])
        fixed = datetime.fromisoformat(p['fixedUtc'])
        require(start.tzinfo is not None and fixed.tzinfo is not None and start > fixed
                and (previous_end is None or start.timestamp() >= previous_end),
                'Attempt ordering/overlap differs')
        previous_end = start.timestamp()+row['elapsedNs']/1e9
        valid = False
        try:
            require(row['outcome'] == 'exited' and not row['censored'], 'Incomplete process')
            document = decode(captures[0])
            envelope_check(document, row, source, target)
            if cell['expected'] == 'success':
                require(not captures[1], 'Unexpected success stderr')
                if cell['operation'] == 'list':
                    resource_hashes = resource_check(document, source, references)
                    for tag, expected in zip(TAGS, p['resources']):
                        require(resource_hashes[tag]['offset'] == expected['offset'], 'Preregistered source span differs')
                else:
                    expected = next(item for item in p['resources'] if item['tag'] == cell['tag'])
                    require(target.stat().st_size == expected['bytes'] and digest(target) == expected['sha256']
                            and target.read_bytes() == references[cell['tag']].read_bytes(), 'Copied resource differs')
                    require(row['targetBefore'] is None, 'Success target was already present')
            elif cell['expected'] == 'collision':
                require(target.read_bytes() == b'authored-existing-destination\0'
                        and file_identity(target) == row['targetBefore'], 'Collision overwrote destination')
            else:
                require(not target.exists() and row['targetBefore'] is None, 'Refusal created a destination')
            require(row['targetAfter'] == (file_identity(target) if target and target.exists() else None),
                    'Recorded output identity differs')
            valid = True
        except (ValueError, KeyError, TypeError, OSError, IndexError):
            pass
        require((row['validation'] == 'pass') is valid, 'Collector validation disagrees with independent evidence')
        eligible = complete and valid and cell['phase'] == 'sample'
        require(row['eligible'] is eligible, 'Eligibility disagrees with retained evidence')
        attempt_path = root/'captures'/(row['id']+'.attempt.json')
        retained_row = load(attempt_path)
        require(wire({key: value for key, value in retained_row.items() if key != 'eligible'})
                == wire({key: value for key, value in row.items() if key != 'eligible'}),
                'Final attempt differs from immediately retained evidence')
        if complete:
            require(retained_row['eligible'] is eligible, 'Completed eligibility differs from immediate record')
        outcomes[(row['outcome'], row['censored'], valid)] += 1
        key = cell['operation']+(':'+cell['tag'] if cell['tag'] else '')
        groups.setdefault(key, {'attempts': 0, 'eligible': []})['attempts'] += 1
        if eligible:
            groups[key]['eligible'].append(row['elapsedNs'])
    unexpected_outputs = output_inventory(root, attempts, complete)
    require(record['retainedOutputBytes'] == sum(path.stat().st_size for path in (root/'outputs').iterdir()),
            'Retained output accounting differs')
    expected_captures = used | {str(root/'captures'/(row['id']+'.attempt.json')) for row in attempts}
    require(not complete or {str(path) for path in (root/'captures').iterdir()} == expected_captures,
            'Completed record omits captures/attempt records')
    return {'schemaVersion': 1, 'kind': 'authored-preview-independent-audit', 'status': record['status'],
            'auditorSha256': digest(__file__), 'protocolSha256': digest(protocol_path),
            'plannedAttempts': len(planned), 'recordedAttempts': len(attempts), 'unrecordedAttempts': len(planned)-len(attempts),
            'outcomes': [{'outcome': key[0], 'censored': key[1], 'validationPassed': key[2], 'count': count}
                         for key, count in sorted(outcomes.items())],
            'unexpectedRetainedOutputs': unexpected_outputs,
            'groups': {key: {'recordedAttempts': value['attempts'], 'eligibleDistribution': distribution(value['eligible'])}
                       for key, value in groups.items()}, 'resources': resource_hashes,
            'cameraBaseline': False, 'performanceDefaultsSelected': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-root', required=True)
    parser.add_argument('--protocol', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    destination = Path(args.output).resolve()
    require(destination.is_relative_to(ROOT/'.local'), 'Audit output must remain private')
    result = audit(args.run_root, args.protocol)
    with destination.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print('Authored preview audit retained privately')
