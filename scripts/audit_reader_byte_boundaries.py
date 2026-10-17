"""Independent retained-output byte-range arithmetic and fixed-denominator audit."""
import argparse
import hashlib
import json
from pathlib import Path


def require(value, message):
    if not value:
        raise ValueError(message)


METRICS = {'userCpuNs', 'systemCpuNs', 'workingSetBytes', 'peakWorkingSetBytes',
           'privateCommitBytes', 'readOperations', 'writeOperations', 'otherOperations',
           'readTransferBytes', 'writeTransferBytes', 'otherTransferBytes', 'physicalIoBytes'}
CUMULATIVE = METRICS - {'workingSetBytes', 'privateCommitBytes', 'physicalIoBytes'}
REQUIRED_BINDINGS = {'examples/reader_byte_boundaries.rs', 'tests/support/mod.rs',
    'tests/support/byte_boundaries.rs', 'tests/support/byte_budget_fixtures.rs',
    'scripts/reader_byte_boundary_campaign.py', 'scripts/audit_reader_byte_boundaries.py',
    'scripts/read_benchmark.py', 'scripts/read_telemetry.py', 'Cargo.toml', 'Cargo.lock',
    'src/reader/mod.rs', 'src/reader/bounded.rs', 'src/reader/bmff.rs',
    'src/reader/tiff.rs', 'src/reader/tracks.rs',
    'scripts/check_reader_byte_boundary_tools.py', 'tests/reader_byte_boundaries.rs'}


def integer(value, minimum=0):
    return type(value) is int and minimum <= value <= 2**64 - 1


def sha(value):
    return isinstance(value, str) and len(value) == 64 and all(x in '0123456789abcdef' for x in value)


def resource_audit(telemetry, process_elapsed):
    require(telemetry['valid'] is True and telemetry['membership'] == 'direct-only-observed', 'resource observation')
    require(telemetry['errors'] == [] and telemetry['stopReason'] is None and
            telemetry['observedDescendantPids'] == [], 'telemetry error/stop/membership state')
    require(integer(telemetry['pid'], 1) and telemetry['requestedIntervalMs'] == 1 and
            telemetry['maxSamples'] == 2048, 'telemetry process/configuration')
    samples = telemetry['samples']
    require(isinstance(samples, list) and 2 <= len(samples) <= 2048, 'initial and final samples')
    prior_end, overhead, prior_values = 0, 0, None
    for index, sample in enumerate(samples):
        begin, end = sample['beginOffsetNs'], sample['endOffsetNs']
        require(integer(begin) and integer(end) and prior_end <= begin <= end <= process_elapsed,
                'sample timing alignment')
        require(sample['final'] is (index == len(samples) - 1), 'exact final sample endpoint')
        require(sample['errors'] == {'physicalIoBytes': 'not instrumented; logical transfers are not device traffic'},
                'explicit physical unavailability; no native counter error')
        values = sample['values']
        require(set(values) == METRICS and values['physicalIoBytes'] is None and
                all(integer(values[key]) for key in METRICS - {'physicalIoBytes'}),
                'required CPU memory logical-I/O counters')
        require(values['peakWorkingSetBytes'] >= values['workingSetBytes'], 'working-set high-water')
        if prior_values is not None:
            require(all(values[k] >= prior_values[k] for k in CUMULATIVE), 'cumulative counter monotonicity')
        prior_values = values
        prior_end = end
        overhead += end - begin
    require(integer(telemetry['observerWallNs']) and telemetry['observerWallNs'] == overhead,
            'observer duration sum')
    maxima = {key: max(s['values'][key] for s in samples) for key in ('workingSetBytes', 'privateCommitBytes')}
    require(all(integer(v) for v in telemetry['sampledMaxima'].values()) and telemetry['sampledMaxima'] == maxima, 'independent sampled maxima')


def audit(root, freeze, freeze_sha256):
    root = Path(root)
    campaign = json.loads((root / 'campaign.json').read_text(encoding='utf-8'))
    witness_bytes = Path(freeze).read_bytes()
    require(sha(freeze_sha256) and hashlib.sha256(witness_bytes).hexdigest() == freeze_sha256,
            'independent freeze witness digest')
    witness = json.loads(witness_bytes)
    require(witness['schemaVersion'] == 1 and isinstance(witness['binary'], str) and
            Path(witness['binary']).is_absolute() and sha(witness['binarySha256']), 'freeze executable binding')
    require(REQUIRED_BINDINGS <= set(witness['files']) and all(sha(v) for v in witness['files'].values()),
            'complete source/tool freeze inventory')
    require(campaign['schemaVersion'] == 1 and campaign['scope'] == 'six authored native default-byte-boundary cells'
            and campaign['limits'] == {'metadataBytes': 8388608, 'blockBytes': 1048576}, 'fixed campaign contract')
    require('freezeFailure' not in campaign, 'no changed freeze during campaign')
    require(campaign['freezeSha256'] == freeze_sha256 and campaign['binding'] == witness,
            'exact independently supplied frozen bindings')
    expected = [(axis, delta) for axis in ('metadata', 'block') for delta in (-1, 0, 1)]
    require([(x['axis'], x['delta']) for x in campaign['attempts']] == expected, 'six-cell denominator')
    rows = []
    for attempt in campaign['attempts']:
        process = attempt['process']
        stem = attempt['captureStem']
        axis, delta = attempt['axis'], attempt['delta']
        require(attempt['argv'] == [witness['binary'], axis, str(delta)], 'actual argv binding')
        require(stem == f"{len(rows):02d}-{axis}-{delta}", 'fixed capture binding')
        require(integer(process['elapsedNs'], 1) and process['errorClass'] is None, 'process duration/error')
        raw = (root / (stem + '.stdout')).read_bytes()
        err = (root / (stem + '.stderr')).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == process['stdoutSha256'], 'stdout binding')
        require(hashlib.sha256(err).hexdigest() == process['stderrSha256'], 'stderr binding')
        require(process['outcome'] == 'exited' and process['exitCode'] == 0 and not process['censored'], 'complete attempt')
        require(len(raw) == process['stdoutBytes'] == process['stdoutCapturedBytes'], 'complete capture')
        require(not err and process['stderrBytes'] == process['stderrCapturedBytes'] == 0, 'unexpected stderr')
        result = json.loads(raw)
        require(integer(result['readElapsedNs'], 1) and result['readElapsedNs'] <= process['elapsedNs'], 'native read duration')
        require((result['axis'], result['delta']) == (axis, delta), 'cell binding')
        planned = result['plannedRequests']
        require(all(type(r[k]) is int and r[k] >= 0 for r in planned for k in ('offset', 'requested', 'returned')), 'integer ranges')
        require(all(r['requested'] == r['returned'] and r['offset'] + r['requested'] <= result['sourceBytes'] for r in planned), 'finite source ranges')
        total = sum(r['requested'] for r in planned)
        largest = max(r['requested'] for r in planned)
        require(total == result['plannedRequestedBytes'] and largest == result['largestRequestBytes'], 'independent range sum/max')
        require((total == 8388608 + delta and largest <= 1048576) if axis == 'metadata'
                else (largest == 1048576 + delta and total < 8388608), 'separate-axis consumption')
        prefix, charged = [], 0
        for r in planned:
            if charged + r['requested'] > 8388608 or r['requested'] > 1048576:
                break
            prefix.append(r)
            charged += r['requested']
        require(result['requests'] == prefix and result['underlyingRequestedBytes'] == charged, 'exact request prefix; rejected read absent')
        require(result['sourceUnchanged'] and len(result['sourceSha256']) == 64, 'source audit')
        require(result['complete'] == (delta <= 0) and result['status'] == ('OK' if delta <= 0 else 'LIMIT_EXCEEDED'), 'native named result')
        require(result['reportedChargedBytes'] == (charged if delta <= 0 else None), 'no false complete charged result')
        telemetry = attempt['telemetry']
        resource_audit(telemetry, process['elapsedNs'])
        rows.append({'axis': axis, 'delta': delta, 'status': result['status'], 'plannedBytes': total,
                     'requestedBytes': charged, 'requestCount': len(prefix), 'readElapsedNs': result['readElapsedNs'],
                     'processElapsedNs': process['elapsedNs'], 'sampledMaxima': telemetry['sampledMaxima'],
                     'finalCounters': telemetry['samples'][-1]['values']})
    return {'status': 'passed', 'cells': rows}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('campaign')
    p.add_argument('--freeze', required=True)
    p.add_argument('--freeze-sha256', required=True)
    a = p.parse_args()
    print(json.dumps(audit(a.campaign, a.freeze, a.freeze_sha256), indent=2))
