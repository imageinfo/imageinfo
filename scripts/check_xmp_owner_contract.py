"""#0188 authored contract model only; no media/XML parsing or mutation."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG_SHA256 = '2c40f81340730fc169bd5e62b25d20e43ba32b7b37427324c00662d69019b25c'
TARGET = ('http://ns.adobe.com/exif/1.0/aux/', 'OwnerName')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, 'duplicate JSON member')
        result[key] = value
    return result


def load(path):
    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=pairs)


def evaluate(case):
    """Trusted authored observations only, never an operational admission API."""
    require(set(case) == {'id', 'rights', 'inventory', 'occurrences', 'checks', 'expected'},
            'closed authored vector')
    require(case['rights'] in ('authored', 'missing', 'preview-only'), 'rights vocabulary')
    require(case['inventory'] in ('complete', 'unsupported', 'unknown'), 'inventory vocabulary')
    require(case['checks'] in ('pass', 'fail', 'unrun'), 'check vocabulary')
    require(type(case['occurrences']) is list, 'occurrence list')
    matches = []
    for occurrence in case['occurrences']:
        require(type(occurrence) is dict and set(occurrence) == {'uri', 'name', 'form'},
                'closed occurrence')
        require(all(type(value) is str for value in occurrence.values()), 'string identity')
        if (occurrence['uri'], occurrence['name']) == TARGET:
            matches.append(occurrence)
    if case['rights'] != 'authored':
        state = 'refused_rights'
    elif case['inventory'] != 'complete':
        state = 'refused_uninspectable'
    elif len(matches) > 1:
        state = 'refused_duplicate'
    elif not matches:
        state = 'unchanged_absent'
    elif matches[0]['form'] not in ('attribute', 'simple-element'):
        state = 'refused_shape'
    elif case['checks'] == 'unrun':
        state = 'unrun'
    elif case['checks'] != 'pass':
        state = 'refused_preservation'
    else:
        state = 'removed'
    return {'state': state, 'requestedRemovals': 1,
            'actualRemovals': int(state == 'removed'),
            'originalRetained': True, 'otherTemplatesRemoved': 0,
            'productionMutationAllowed': False, 'anonymityEstablished': False}


def main():
    path = ROOT / 'docs/privacy/r5-catalog.v1.json'
    require(hashlib.sha256(path.read_bytes()).hexdigest() == CATALOG_SHA256,
            'frozen catalog changed; review contract revision explicitly')
    catalog = load(path)
    require(catalog['catalogId'] == 'r5-gps-owner-serial-core'
            and type(catalog['revision']) is int and catalog['revision'] == 1,
            'catalog identity')
    entries = catalog['entries']
    require(len(entries) == 31 and sum(len(e['selector']['locations']) for e in entries) == 59,
            '31 selector / 59 template denominator')
    selected = [e for e in entries if e['id'] == 'R5P-026']
    require(len(selected) == 1 and selected[0]['selector'] == {
        'kind': 'xmp', 'namespaceUri': TARGET[0], 'localName': TARGET[1],
        'locations': ['sidecar.xmp', 'preview.xmp']}, 'exact selected catalog identity')
    vectors = load(ROOT / 'docs/privacy/xmp-owner-removal-vectors.v1.json')
    require(set(vectors) == {'contractRevision', 'evidenceKind', 'vectors'}
            and vectors['contractRevision'] == 'xmp-owner-removal-2026-10-16.1'
            and vectors['evidenceKind'] == 'authored-abstract-contract-only', 'vector binding')
    require(type(vectors['vectors']) is list and len(vectors['vectors']) == 14,
            'finite vector denominator')
    ids = set()
    for case in vectors['vectors']:
        require(type(case['id']) is str and case['id'] not in ids, 'unique vector ID')
        ids.add(case['id'])
        actual = evaluate(case)
        require(set(case['expected']) == set(actual), case['id'] + ': effect fields')
        require(all(type(case['expected'][key]) is type(value)
                    and case['expected'][key] == value for key, value in actual.items()),
                case['id'] + ': requested/actual effect mismatch')
    print(json.dumps({'catalogSelectors': 31, 'catalogTemplates': 59,
                      'authoredContractVectors': len(ids), 'mediaFixturesExecuted': 0}))


if __name__ == '__main__':
    main()
