"""Check #0064's scalar proposal and descriptive noise arithmetic, without media.

These are specification-model checks, not native parser saturation, memory, I/O,
deadline or cancellation tests. Imports no benchmark collector or auditor code.
"""
import copy
from fractions import Fraction
import json
from pathlib import Path
import statistics


ROOT = Path(__file__).resolve().parent.parent
PROPOSAL = ROOT / 'docs/performance/read-limits/proposal.v1.json'
BASELINE = ROOT / 'docs/performance/single-read/results.v1.json'
U64_MAX = 2**64 - 1
# Independently reviewed implemented values; this checker does not execute Rust.
LIMITS = {'metadata_bytes': (8388608, 268435456),
          'block_bytes': (1048576, 8388608), 'boxes': (4096, 65536),
          'depth': (16, 64), 'entries': (4096, 65536), 'records': (4096, 65536)}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate JSON key')
        result[key] = value
    return result


def decode(wire):
    def nonfinite(_value):
        raise ValueError('Nonfinite JSON value')
    return json.loads(wire, object_pairs_hook=unique, parse_constant=nonfinite)


def integer(value):
    return type(value) is int and 0 <= value <= U64_MAX


def validate(proposal, baseline):
    require(proposal['schemaVersion'] == 1
            and proposal['status'] == 'proposed-not-adopted', 'Proposal status/version')
    rows = proposal['limits']
    require(len(rows) == len(LIMITS)
            and {row['name'] for row in rows} == set(LIMITS), 'Limit inventory')
    by_name = {row['name']: row for row in rows}
    for name, (default, ceiling) in LIMITS.items():
        row = by_name[name]
        for field, expected in [('implementedDefault', default), ('proposedDefault', default),
                                ('proposedOperatingCeiling', default),
                                ('implementedHardCeiling', ceiling)]:
            require(integer(row[field]) and row[field] == expected, 'Limit value: ' + name)
    expected_vectors = set()
    for name, row in by_name.items():
        for boundary in ['proposedOperatingCeiling', 'implementedHardCeiling']:
            ceiling = row[boundary]
            expected_vectors.update((name, boundary, value, outcome)
                                    for value, outcome in [(ceiling - 1, 'within'),
                                                           (ceiling, 'within'),
                                                           (ceiling + 1, 'exceeds')])
    actual_vectors = []
    for item in proposal['boundaryVectors']:
        require(integer(item['value']), 'Boundary value must be an unsigned integer')
        actual_vectors.append((item['limit'], item['boundary'], item['value'], item['expected']))
    require(len(actual_vectors) == 36 and set(actual_vectors) == expected_vectors,
            'Boundary vectors missing, duplicated or incorrect')

    # Recompute from ordered public attempts, not the stored aggregate fields.
    require(baseline['scheduledAttempts'] == 99 and baseline['warmupAttempts'] == 9
            and baseline['sampleAttempts'] == 90, 'Baseline denominators')
    trials = baseline['trials']
    require(len(trials) == 3, 'Baseline trial count')
    samples, medians, shifts = [], [], []
    for index, trial in enumerate(trials, 1):
        require(trial['trial'] == index and len(trial['attempts']) == 33, 'Trial schedule')
        measured = []
        for at, attempt in enumerate(trial['attempts']):
            require(attempt['index'] == at
                    and attempt['phase'] == ('warmup' if at < 3 else 'sample'), 'Attempt order')
            require(integer(attempt['elapsedNs']) and attempt['elapsedNs'] > 0,
                    'Elapsed duration')
            require(attempt['outcome'] == 'exited' and attempt['exitCode'] == 0
                    and attempt['correctness'] == 'pass' and attempt['censored'] is False,
                    'Historical success denominator changed')
            require(attempt['eligible'] is (at >= 3), 'Eligibility changed')
            if at >= 3:
                measured.append(attempt['elapsedNs'])
        samples.extend(measured)
        medians.append(statistics.median(measured))
        shifts.append(abs(statistics.median(measured[-10:])
                          - statistics.median(measured[:10])))
    median = statistics.median(samples)
    span = max(medians) - min(medians)
    shift = max(shifts)
    noise = proposal['noise']
    require(noise['source'] == '../single-read/results.v1.json'
            and noise['unit'] == 'nanoseconds'
            and noise['status'] == 'proposed-advisory-not-release-gate'
            and noise['batchBudget'] is None, 'Noise scope/status')
    for name, value in [('baselineMedianNs', median), ('trialMedianSpanNs', span),
                        ('maximumAbsoluteWindowShiftNs', shift), ('noiseScaleNs', max(span, shift))]:
        require(integer(noise[name]) and noise[name] == value, 'Noise arithmetic: ' + name)
    require(type(noise['relativeFloorNumerator']) is int
            and type(noise['relativeFloorDenominator']) is int
            and type(noise['noiseMultiplier']) is int
            and (noise['relativeFloorNumerator'], noise['relativeFloorDenominator'],
                 noise['noiseMultiplier']) == (1, 10, 3), 'Proposed policy margins')
    budget = max(Fraction(int(median), 10), 3 * max(span, shift))
    require(integer(noise['advisoryBudgetNs']) and noise['advisoryBudgetNs'] == budget,
            'Advisory budget arithmetic')


def arithmetic_controls():
    """Finite unsigned arithmetic model; no claim these execute native branches."""
    range_vectors = [(0, 0, 0, True), (0, 1, 1, True), (1, 0, 1, True),
                     (1, 1, 1, False), (U64_MAX, 0, U64_MAX, True),
                     (U64_MAX, 1, U64_MAX, False), (U64_MAX - 1, 1, U64_MAX, True),
                     (0, U64_MAX, U64_MAX, True)]
    for offset, length, end, expected in range_vectors:
        require((offset + length <= U64_MAX and offset + length <= end) is expected,
                'Range model control')
    charge_vectors = [(0, 0, 0, 0, 'within'), (0, 1, 1, 1, 'within'),
                      (1, 1, 2, 1, 'within'), (2, 1, 2, 1, 'limit'),
                      (0, 2, 10, 1, 'limit'),
                      (U64_MAX, 1, U64_MAX, U64_MAX, 'overflow'),
                      (U64_MAX - 1, 1, U64_MAX, U64_MAX, 'within')]
    for charged, length, total, block, expected in charge_vectors:
        next_charge = charged + length
        outcome = ('overflow' if next_charge > U64_MAX else
                   'limit' if next_charge > total or length > block else 'within')
        require(outcome == expected, 'Charge model control')
    return len(range_vectors) + len(charge_vectors)


def rejection_controls(proposal, baseline):
    cases = []
    for change in ['duplicate', 'boolean', 'outcome', 'default', 'budget']:
        altered = copy.deepcopy(proposal)
        if change == 'duplicate':
            altered['boundaryVectors'][-1] = altered['boundaryVectors'][0]
        elif change == 'boolean':
            altered['boundaryVectors'][0]['value'] = True
        elif change == 'outcome':
            altered['boundaryVectors'][0]['expected'] = 'exceeds'
        elif change == 'default':
            altered['limits'][0]['proposedDefault'] += 1
        else:
            altered['noise']['advisoryBudgetNs'] += 1
        cases.append((altered, baseline))
    for change in ['denominator', 'eligibility']:
        altered = copy.deepcopy(baseline)
        if change == 'denominator':
            altered['sampleAttempts'] -= 1
        else:
            altered['trials'][0]['attempts'][3]['eligible'] = False
        cases.append((proposal, altered))
    for altered_proposal, altered_baseline in cases:
        try:
            validate(altered_proposal, altered_baseline)
        except ValueError:
            continue
        raise ValueError('Invalid model input was accepted')
    for malformed in ['{"x":1,"x":2}', '{"x":NaN}']:
        try:
            decode(malformed)
        except ValueError:
            continue
        raise ValueError('Invalid JSON was accepted')
    return len(cases) + 2


def main():
    proposal = decode(PROPOSAL.read_bytes())
    baseline = decode(BASELINE.read_bytes())
    validate(proposal, baseline)
    arithmetic = arithmetic_controls()
    rejections = rejection_controls(proposal, baseline)
    print(f'Read-limit proposal: 36 scalar vectors, {arithmetic} arithmetic model controls, '
          f'{rejections} rejection controls; 99 public attempts/90 samples rechecked. '
          'No native saturation or resource qualification.')


if __name__ == '__main__':
    main()
