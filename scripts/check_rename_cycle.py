"""Finite #0097 model checks; no filesystem operation is implemented or invoked.

The conditional move and continuing guards below are hypothetical premises. Their
behavior is a specification oracle, never evidence for an operating-system API.
Only the public authored vectors are read. No result grants mutation authority.
"""
from copy import deepcopy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VECTORS = ROOT / 'docs/write-safety/two-name-cycle.v1.json'
STATES = [
    dict(a='alpha', b='beta', temp=None),
    dict(a=None, b='beta', temp='alpha'),
    dict(a='beta', b=None, temp='alpha'),
    dict(a='beta', b='alpha', temp=None),
]
MOVES = [
    dict(id='a-to-temp', source='a', target='temp', object='alpha'),
    dict(id='b-to-a', source='b', target='a', object='beta'),
    dict(id='temp-to-b', source='temp', target='b', object='alpha'),
]


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def strict(text):
    def members(pairs):
        value = {}
        for key, item in pairs:
            require(key not in value, 'duplicate JSON member')
            value[key] = item
        return value

    def nonfinite(value):
        raise ValueError('nonfinite JSON constant: ' + value)

    return json.loads(text, object_pairs_hook=members, parse_constant=nonfinite)


def move(namespace, step):
    """Hypothetical held-source conditional no-replace primitive, not an API."""
    source, target, identity = step['source'], step['target'], step['object']
    if namespace[source] != identity or namespace[target] is not None:
        return False
    namespace[target] = namespace[source]
    namespace[source] = None
    return True


def model(events):
    namespace = deepcopy(STATES[0])
    applied = 0
    uncertain = False
    terminal = False
    verified = False
    for event in events:
        require(not terminal, 'event after terminal refusal/stop/uncertainty')
        require(type(event) is dict and type(event.get('kind')) is str, 'event shape')
        kind = event['kind']
        if kind == 'move':
            require(set(event) == {'kind', 'id', 'outcome'}, 'move event fields')
            require(applied < 3 and event['id'] == MOVES[applied]['id'], 'move order')
            require(event['outcome'] in {'applied', 'not-applied', 'unknown'}, 'outcome')
            if namespace != STATES[applied]:
                # A foreign winner observed before the call ends the attempt.
                require(event['outcome'] == 'not-applied', 'foreign winner overwritten')
                terminal = True
            elif event['outcome'] == 'unknown':
                step = MOVES[applied]
                namespace[step['source']] = 'unknown'
                namespace[step['target']] = 'unknown'
                uncertain = terminal = True
            elif event['outcome'] == 'not-applied':
                terminal = True
            else:
                require(move(namespace, MOVES[applied]), 'conditional move failed')
                applied += 1
        elif kind in {'foreign', 'denied-actor'}:
            require(set(event) == {'kind', 'slot'} and event['slot'] in namespace,
                    'actor event fields')
            slot = event['slot']
            if kind == 'foreign':
                require(namespace[slot] is None, 'foreign insertion into guarded occupied name')
                namespace[slot] = 'foreign'
            else:
                require(namespace[slot] in {'alpha', 'beta'}, 'denied actor lacks held object')
        elif kind == 'stop':
            require(set(event) == {'kind', 'reason'}, 'stop event fields')
            require(event['reason'] in {'cancel', 'guard-lost', 'property-mismatch', 'restart',
                                        'foreign-winner'},
                    'stop reason')
            terminal = True
            uncertain = (event['reason'] in {'guard-lost', 'restart'}
                         or event['reason'] == 'property-mismatch' and applied > 0)
        elif kind == 'verify':
            require(set(event) == {'kind', 'outcome'} and applied == 3, 'final verify fields')
            require(event['outcome'] in {'matched', 'mismatch'}, 'verification outcome')
            require(event['outcome'] != 'matched' or namespace == STATES[3],
                    'foreign final map verified')
            verified = event['outcome'] == 'matched'
            uncertain = not verified
            terminal = True
        else:
            raise ValueError('unknown event kind')
    complete = verified and namespace == STATES[3] and not uncertain
    classification = ('recovery-required' if uncertain else 'complete-observed' if complete
                      else 'no-effect' if applied == 0 else 'partial')
    return dict(classification=classification, bindings=namespace, applied_moves=applied,
                uncertain=uncertain)


def prefix(count):
    return [dict(kind='move', id=step['id'], outcome='applied') for step in MOVES[:count]]


def independent_checks():
    """Exercise primitive late races separately from the vector interpreter."""
    checks = 0
    for index, step in enumerate(MOVES):
        namespace = deepcopy(STATES[index])
        require(move(namespace, step) and namespace == STATES[index + 1], 'exact prefix')
        checks += 1
        # Insert a foreign winner after a hypothetical last check, at the call.
        namespace = deepcopy(STATES[index])
        namespace[step['target']] = 'foreign'
        before = deepcopy(namespace)
        require(not move(namespace, step) and namespace == before, 'late target clobbered')
        checks += 1
        # Equal bytes cannot stand in for held physical identity.
        namespace = deepcopy(STATES[index])
        namespace[step['source']] = 'same-bytes-foreign-object'
        before = deepcopy(namespace)
        require(not move(namespace, step) and namespace == before, 'late source adopted')
        checks += 1
    for count in range(4):
        result = model(prefix(count))
        require(result['bindings'] == STATES[count] and result['applied_moves'] == count,
                'prefix inventory')
        require(sum(value == 'alpha' for value in result['bindings'].values()) == 1
                and sum(value == 'beta' for value in result['bindings'].values()) == 1,
                'original object identity lost')
        checks += 1
        for reason in ('cancel', 'guard-lost', 'property-mismatch', 'restart'):
            result = model(prefix(count) + [dict(kind='stop', reason=reason)])
            expected = ('recovery-required' if reason in {'guard-lost', 'restart'}
                        or reason == 'property-mismatch' and count > 0 else
                        'no-effect' if count == 0 else 'partial')
            require(result['classification'] == expected and result['bindings'] == STATES[count],
                    'stop effects or false completion')
            checks += 1
        vacant = next(slot for slot, obj in STATES[count].items() if obj is None)
        result = model(prefix(count) + [dict(kind='foreign', slot=vacant)])
        require(result['bindings'][vacant] == 'foreign'
                and result['classification'] == ('no-effect' if count == 0 else 'partial'),
                'foreign object lost or false success')
        checks += 1
        if count < 3:
            for outcome in ('not-applied', 'unknown'):
                result = model(prefix(count) + [dict(kind='move', id=MOVES[count]['id'],
                                                    outcome=outcome)])
                require(result['applied_moves'] == count, 'unconfirmed move counted')
                require(result['uncertain'] == (outcome == 'unknown'), 'unknown suppressed')
                require(result['classification'] == ('recovery-required' if outcome == 'unknown'
                        else 'no-effect' if count == 0 else 'partial'), 'failure classification')
                checks += 1
    for outcome in ('matched', 'mismatch'):
        result = model(prefix(3) + [dict(kind='verify', outcome=outcome)])
        require(result['classification'] == ('complete-observed' if outcome == 'matched'
                else 'recovery-required'), 'final verification bypass')
        checks += 1
    malformed = [
        [dict(kind='move', id=MOVES[1]['id'], outcome='applied')],
        [dict(kind='move', id=MOVES[0]['id'], outcome='committed')],
        [dict(kind='foreign', slot='a')],
        [dict(kind='denied-actor', slot='temp')],
        [dict(kind='stop', reason='rollback')],
        [dict(kind='stop', reason='cancel')] + prefix(1),
        [dict(kind='move', id=MOVES[0]['id'], outcome='unknown')] + prefix(1),
        [dict(kind='move', id=MOVES[0]['id'], outcome='not-applied')] + prefix(1),
        [dict(kind='foreign', slot='temp')] + prefix(1),
        prefix(3) + prefix(1),
        [dict(kind='verify', outcome='matched')],
        prefix(3) + [dict(kind='foreign', slot='temp'), dict(kind='verify', outcome='matched')],
        prefix(3) + [dict(kind='verify', outcome='matched')] + prefix(1),
    ]
    for events in malformed:
        try:
            model(events)
        except ValueError:
            checks += 1
        else:
            raise AssertionError('invalid continuation, overwrite or move order accepted')
    return checks


def validate(value):
    require(value['schema'] == 'imageinfo.two-name-cycle.v1', 'schema revision')
    require(value['status'] == 'specification-only', 'specification status')
    require(value['profile']['id'] == 'two-name-local-ntfs-v1'
            and value['profile']['status'] == 'unqualified', 'profile must be unsupported')
    authority = value['authority']
    require(set(authority) == {'filesystem_mutation', 'replay', 'rollback', 'cleanup',
                               'profile_admission', 'raw_admission'}
            and all(type(flag) is bool and flag is False for flag in authority.values()),
            'model cannot grant authority')
    require(value['states'] == dict(zip(('initial', 'after_first', 'after_second', 'complete'),
                                      STATES)), 'exact two-object states')
    require(value['moves'] == MOVES, 'exact three forward moves')
    require(type(value['vectors']) is list and value['vectors'], 'finite vector set')
    identifiers = set()
    for vector in value['vectors']:
        require(type(vector['id']) is str and vector['id'] not in identifiers, 'vector id')
        identifiers.add(vector['id'])
        expected = vector['expected']
        require(set(expected) == {'classification', 'bindings', 'applied_moves', 'uncertain'}
                and type(expected['applied_moves']) is int
                and type(expected['uncertain']) is bool, 'expected result fields/types')
        require(model(vector['events']) == vector['expected'], 'vector mismatch: ' + vector['id'])
    # A finite set must include every applied prefix, unknown call and foreign
    # destination window. Extra prose cannot stand in for these behavioral cells.
    events = [vector['events'] for vector in value['vectors']]
    for count in range(4):
        require(prefix(count) + [dict(kind='stop', reason='cancel')] in events,
                'missing exact-prefix cancellation vector')
        vacant = next(slot for slot, obj in STATES[count].items() if obj is None)
        require(any(row[:count] == prefix(count)
                    and len(row) > count and row[count] == dict(kind='foreign', slot=vacant)
                    for row in events), 'missing foreign-winner window')
        if count < 3:
            for outcome in ('unknown', 'not-applied'):
                require(prefix(count) + [dict(kind='move', id=MOVES[count]['id'], outcome=outcome)]
                        in events, 'missing move-failure vector')
    return len(identifiers)


def negative_checks(value):
    """Ensure altered outcomes cannot quietly manufacture safety or permission."""
    changes = [(['status'], 'native-qualified'), (['profile', 'status'], 'supported'),
               (['moves', 0, 'target'], 'b'), (['states', 'complete', 'temp'], 'alpha'),
               (['vectors', 0, 'expected', 'classification'], 'committed'),
               (['vectors', 0, 'expected', 'applied_moves'], True),
               (['vectors', 0, 'expected', 'uncertain'], 0),
               (['vectors'], value['vectors'][:-1] + [value['vectors'][0]])]
    changes += [(['authority', name], True) for name in value['authority']]
    for path, replacement in changes:
        edited = deepcopy(value)
        parent = edited
        for part in path[:-1]:
            parent = parent[part]
        parent[path[-1]] = replacement
        try:
            validate(edited)
        except (ValueError, KeyError):
            continue
        raise AssertionError('altered protocol accepted: ' + str(path))
    for wire in ('{"x":1,"x":1}', '{"x":NaN}'):
        try:
            strict(wire)
        except ValueError:
            continue
        raise AssertionError('non-strict JSON accepted')
    return len(changes) + 2


def main():
    checks = independent_checks()
    value = strict(VECTORS.read_text(encoding='utf-8'))
    vectors = validate(value)
    negatives = negative_checks(value)
    print(json.dumps(dict(ticket=97, vectors=vectors, independentChecks=checks,
                          negativeChecks=negatives, allPassed=True, nativeOperations=0,
                          productionMutationAllowed=False),
                     indent=2))


if __name__ == '__main__':
    main()
