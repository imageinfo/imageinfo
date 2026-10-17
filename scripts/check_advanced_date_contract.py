"""#0133 public contract and authored arithmetic oracle; never opens media.

This test-only model is deliberately not imported by imageinfo. Positive vectors
are proposed semantics, not native capability, dataset qualification or repair.
"""
from copy import deepcopy
from datetime import datetime, timedelta
from fractions import Fraction
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / 'docs/legacy-compatibility/advanced-date-contract.v1.json'
OPS = {'calendar-months', 'elapsed-seconds', 'offset-convert', 'named-zone',
       'clock-correction', 'track-interpolate', 'geolocation', 'inverse-export',
       'validate', 'repair'}


def require(ok):
    if not ok:
        raise ValueError('contract rejected')


def strict(text):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result)
            result[key] = value
        return result
    return json.loads(text, object_pairs_hook=pairs,
                      parse_constant=lambda _: require(False))


def keys(value, names):
    require(type(value) is dict and set(value) == set(names.split()))


def integer(value, low, high):
    require(type(value) is int and low <= value <= high)
    return value


def date(value):
    require(type(value) is str and re.fullmatch(r'[0-9]{4}:[0-9]{2}:[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}', value))
    return datetime.strptime(value, '%Y:%m:%d %H:%M:%S')


def offset(value):
    require(type(value) is str and re.fullmatch(r'[+-][0-9]{2}:[0-9]{2}', value))
    hours, minutes = int(value[1:3]), int(value[4:6])
    require(hours <= 14 and minutes < 60 and (hours != 14 or minutes == 0)
            and value != '-00:00')
    return (1 if value[0] == '+' else -1) * (hours * 60 + minutes)


def stamp(value):
    return f'{value.year:04}:{value.month:02}:{value.day:02} {value.hour:02}:{value.minute:02}:{value.second:02}'


def model(request):
    """All numeric times are authored UTC integer seconds; no parser/OS clock."""
    try:
        keys(request, 'operation arguments')
        op, a = request['operation'], request['arguments']
        require(op in OPS)
        if op == 'calendar-months':
            keys(a, 'date months')
            old = date(a['date'])
            total = (old.year - 1) * 12 + old.month - 1 + integer(a['months'], -120000, 120000)
            year, month = divmod(total, 12)
            result = stamp(old.replace(year=year + 1, month=month + 1))
        elif op == 'elapsed-seconds':
            keys(a, 'date offset seconds')
            # Explicit offset is mandatory even though a fixed offset cancels in
            # this bounded result. Zone-less elapsed arithmetic is undefined.
            offset(a['offset'])
            result = stamp(date(a['date']) + timedelta(seconds=integer(a['seconds'], -86400, 86400)))
        elif op == 'offset-convert':
            keys(a, 'date sourceOffset targetOffset')
            delta = offset(a['targetOffset']) - offset(a['sourceOffset'])
            result = stamp(date(a['date']) + timedelta(minutes=delta))
        elif op == 'clock-correction':
            keys(a, 'camera anchors')
            t = integer(a['camera'], 0, 1000000)
            anchors = a['anchors']
            require(type(anchors) is list and len(anchors) in (1, 2))
            for pair in anchors:
                require(type(pair) is list and len(pair) == 2)
                for item in pair:
                    integer(item, 0, 1000000)
            c0, u0 = anchors[0]
            if len(anchors) == 1:
                require(abs(t - c0) <= 86400)
                result = u0 + t - c0
            else:
                c1, u1 = anchors[1]
                require(c0 < c1 and u0 < u1 and c0 <= t <= c1 and c1 - c0 <= 86400)
                result = Fraction(u0) + Fraction((t - c0) * (u1 - u0), c1 - c0)
                require(result.denominator == 1)
                result = int(result)
            integer(result, 0, 1000000)
        elif op == 'track-interpolate':
            keys(a, 'time samples')
            t = integer(a['time'], 0, 1000000)
            samples = a['samples']
            require(type(samples) is list and len(samples) == 2)
            for sample in samples:
                require(type(sample) is list and len(sample) == 3)
                integer(sample[0], 0, 1000000)
                integer(sample[1], -90000000, 90000000)
                integer(sample[2], -180000000, 180000000)
            p, q = samples
            require(p[0] < q[0] and q[0] - p[0] <= 300 and p[0] <= t <= q[0]
                    and abs(q[2] - p[2]) <= 180000000)
            result = [Fraction(p[i]) + Fraction((t - p[0]) * (q[i] - p[i]), q[0] - p[0]) for i in (1, 2)]
            require(all(v.denominator == 1 for v in result))
            result = list(map(int, result))
        elif op == 'geolocation':
            keys(a, 'dataset latitude longitude offline')
            require(a['dataset'] == 'authored-rectangle-v1' and a['offline'] is True)
            lat = integer(a['latitude'], -90000000, 90000000)
            lon = integer(a['longitude'], -180000000, 180000000)
            # Invented half-open rectangle: no claims about a real place.
            require(0 <= lat < 1000000 and 0 <= lon < 1000000)
            result = 'authored-cell-A'
        elif op == 'validate':
            keys(a, 'date suppressWarnings')
            require(type(a['suppressWarnings']) is bool)
            date(a['date'])
            result = 'calendar-shape-only'
        else:
            # Unknown named-zone data, inverse export and all repair refuse.
            return {'status': 'refused'}
        return {'status': 'proposed', 'value': result}
    except (ValueError, TypeError, KeyError, OverflowError):
        return {'status': 'refused'}


def validate(value):
    keys(value, 'schemaVersion id requirements authority baseline sources operations dataRights vectors residuals')
    require(type(value['schemaVersion']) is int and value['schemaVersion'] == 1
            and value['id'] == 'r5-advanced-date-contract/1')
    require(value['requirements'] == ['MAP-018', 'MAP-019', 'MAP-020', 'MAP-022'])
    keys(value['authority'], 'runtimeEnabled productionMutationAllowed repairEnabled datasetQualified parityComplete')
    require(all(type(v) is bool and v is False for v in value['authority'].values()))
    require(value['baseline'] == {'catalog': 'r5-date-family-bounded', 'fields': 4, 'cells': 20,
                                 'supported': 5, 'refused': 11, 'unverified': 4})
    baseline = strict((ROOT / 'docs/legacy-compatibility/r5-date-mapping.v1.json').read_text(encoding='utf-8'))
    for key, recorded in {'fieldRows': 4, 'operationRows': 20, 'supported': 5,
                          'refused': 11, 'unverified': 4}.items():
        require(baseline['denominators'][key] == recorded)
    require(baseline['authority']['repairEnabled'] is False)
    require(type(value['sources']) is list and len(value['sources']) >= 5)
    for path in value['sources']:
        require(type(path) is str and path.startswith('docs/'))
        resolved = (ROOT / path).resolve()
        require(resolved.is_relative_to(ROOT) and resolved.is_file())
    rows = value['operations']
    require(type(rows) is list and len(rows) == len(OPS) and {r['operation'] for r in rows} == OPS)
    for row in rows:
        keys(row, 'operation requirement destination data coverage refusal nextCell runtime')
        family = ('MAP-018' if row['operation'] in {'calendar-months', 'elapsed-seconds', 'offset-convert', 'named-zone'}
                  else 'MAP-019' if row['operation'] in {'clock-correction', 'track-interpolate'}
                  else 'MAP-020' if row['operation'] in {'geolocation', 'inverse-export'} else 'MAP-022')
        require(row['requirement'] == family and row['runtime'] == 'unavailable')
        require(all(type(row[k]) is str and row[k].strip() for k in ('destination', 'data', 'coverage', 'refusal', 'nextCell')))
    require(value['dataRights'] == {
        'authored-rectangle-v1': 'Invented public test coordinates and label; no real geographic coverage.',
        'realGeography': 'unselected', 'timeZoneDatabase': 'unselected',
        'network': 'disabled', 'paidServices': 'not-authorized',
        'requiredManifest': ['provider', 'version', 'digest', 'license', 'attribution', 'redistribution', 'derivative-export', 'coverage', 'accuracy', 'privacy']})
    require(type(value['residuals']) is list and len(value['residuals']) >= 4 and all(type(r) is str and r for r in value['residuals']))
    ids = set()
    seen = set()
    require(type(value['vectors']) is list and len(value['vectors']) >= 30)
    for vector in value['vectors']:
        keys(vector, 'id request expected')
        require(type(vector['id']) is str and vector['id'] not in ids)
        ids.add(vector['id'])
        # Python equality conflates True with 1 and 1.0 with 1; the contract
        # expects exact JSON value kinds as well as equal numeric values.
        require(json.dumps(model(vector['request']), sort_keys=True)
                == json.dumps(vector['expected'], sort_keys=True))
        seen.add(vector['request']['operation'])
    require(seen == OPS)


def main():
    value = strict(PATH.read_text(encoding='utf-8'))
    validate(value)
    mutations = []
    for key in value['authority']:
        changed = deepcopy(value)
        changed['authority'][key] = True
        mutations.append(changed)
    for key in ('fields', 'cells', 'supported', 'refused', 'unverified'):
        changed = deepcopy(value)
        changed['baseline'][key] += 1
        mutations.append(changed)
    for key in ('network', 'realGeography', 'timeZoneDatabase'):
        changed = deepcopy(value)
        changed['dataRights'][key] = 'enabled'
        mutations.append(changed)
    for index in range(len(value['operations'])):
        changed = deepcopy(value)
        changed['operations'][index]['runtime'] = 'supported'
        mutations.append(changed)
    changed = deepcopy(value)
    changed['vectors'][0]['expected'] = {'status': 'admitted'}
    mutations.append(changed)
    for changed in mutations:
        try:
            validate(changed)
        except ValueError:
            continue
        raise AssertionError('unsafe alteration accepted')
    for text in ('{"x":1,"x":2}', '{"x":NaN}'):
        try:
            strict(text)
        except ValueError:
            continue
        raise AssertionError('invalid JSON accepted')
    print(f'advanced date contract: {len(value["operations"])} operation rows, {len(value["vectors"])} authored vectors, {len(mutations) + 2} rejected alterations/JSON inputs')


if __name__ == '__main__':
    main()
