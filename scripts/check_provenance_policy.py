"""Finite #0091 abstract policy QA; no media parsing or signature verification."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELECTED = {
    'catalogId': 'AUTH-004',
    'code': 'CANON_ORIGINAL_DECISION_INDICATOR',
    'location': 'cr3-cmt3-canon',
    'tag': '0x0083',
}
CAPABILITIES = {
    'cryptographicValidationPerformed', 'generalAuthenticityAbsenceEstablished',
    'signedCameraEvidenceExecuted', 'mediaParsingPerformed',
    'productionMutationAllowed', 'invalidationImplemented',
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    def unique(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON member')
            result[key] = value
        return result

    def invalid(value):
        raise ValueError('nonfinite JSON constant: ' + value)

    return json.loads(path.read_text(encoding='utf-8'),
                      object_pairs_hook=unique, parse_constant=invalid)


def evaluate(vector):
    """Apply the proposed observation table, never production admission."""
    matched = sum(o['location'] == SELECTED['location'] and o['tag'] == SELECTED['tag']
                  for o in vector['occurrences'])
    if matched:
        observation, decision = 'indicator-present', 'refuse-known-indicator'
    elif not vector['inventoryComplete']:
        observation, decision = 'uninspectable', 'refuse-uninspectable'
    else:
        observation = 'no-match-in-selected-scope'
        decision = ('refuse-invalidation-unimplemented'
                    if vector['request'] == 'explicit-invalidation'
                    else 'continue-other-gates-only')
    return {'matchedOccurrences': matched, 'observation': observation, 'decision': decision}


def main():
    package = read(ROOT / 'docs/privacy/known-provenance-vectors.v1.json')
    require(set(package) == {'schemaVersion', 'revision', 'observedOn', 'status',
                            'catalogRevision', 'selectedIndicator', 'recommendation',
                            'capabilities', 'vectors'}, 'policy package fields changed')
    require(type(package['schemaVersion']) is int and package['schemaVersion'] == 1,
            'unsupported schema version')
    require(package['revision'] == 'canon-original-decision-policy-2026-10-15.1'
            and package['observedOn'] == '2026-10-15'
            and package['status'] == 'proposed-policy-authored-vectors'
            and package['recommendation'] == 'refuse-before-mutation',
            'reviewed proposal identity or disposition changed')
    require(package['selectedIndicator'] == SELECTED, 'selected indicator widened or changed')
    require(set(package['capabilities']) == CAPABILITIES
            and all(value is False for value in package['capabilities'].values()),
            'authored policy cannot claim implementation, media evidence or authority')
    catalog = read(ROOT / 'docs/write-safety/known-authenticity.v1.json')
    require(package['catalogRevision'] == catalog['revision']
            == 'raw-known-provenance-2026-10-12.1', 'catalog revision mismatch')
    entries = [entry for entry in catalog['entries'] if entry['id'] == SELECTED['catalogId']]
    require(len(entries) == 1 and entries[0]['indicator'] == SELECTED['code']
            and entries[0]['identifier'] == SELECTED['tag'], 'existing indicator binding changed')
    require(all(catalog[key] is False for key in ('cryptographicValidationPerformed',
                'generalAuthenticityAbsenceEstablished', 'productionMutationAllowed')),
            'existing catalog gates changed')
    vectors = package['vectors']
    require(type(vectors) is list and len(vectors) == 14, 'expected 14 authored vectors')
    identifiers = []
    for vector in vectors:
        require(set(vector) == {'id', 'purpose', 'request', 'inventoryComplete',
                               'occurrences', 'externalValidityClaim', 'expected'},
                'vector fields changed')
        identifiers.append(vector['id'])
        require(type(vector['purpose']) is str and bool(vector['purpose'].strip()),
                'vector requires reviewable purpose')
        require(vector['request'] in {'metadata-edit-new-output', 'no-op-new-output',
                                     'explicit-invalidation'}, 'unknown operation')
        require(type(vector['inventoryComplete']) is bool, 'inventory completeness is Boolean')
        require(vector['externalValidityClaim'] in {'none', 'valid', 'invalid'},
                'unknown untrusted validity claim')
        require(type(vector['occurrences']) is list, 'occurrences must remain a list')
        for occurrence in vector['occurrences']:
            require(set(occurrence) == {'location', 'tag', 'referenceShape'},
                    'occurrence fields changed')
            require(occurrence['location'] in {'cr3-cmt3-canon', 'cr3-cmt2-exif'}
                    and occurrence['tag'] in {'0x0083', '0x0009'}
                    and occurrence['referenceShape'] in {'zero', 'nonzero', 'uninterpretable'},
                    'unknown abstract occurrence')
        expected = vector['expected']
        require(set(expected) == {'matchedOccurrences', 'observation', 'decision'}
                and type(expected['matchedOccurrences']) is int,
                'expected observation fields changed')
        require(expected == evaluate(vector), 'policy disagreement: ' + vector['id'])
    require(len(set(identifiers)) == 14
            and set(identifiers) == {f'KP-{n:03}' for n in range(1, 15)},
            'vector identities missing or duplicated')

    # Keep each documented boundary represented without freezing explanatory prose.
    require({v['request'] for v in vectors} == {'metadata-edit-new-output',
            'no-op-new-output', 'explicit-invalidation'}, 'operation boundary missing')
    require({v['externalValidityClaim'] for v in vectors} == {'none', 'valid', 'invalid'},
            'untrusted validity boundary missing')
    require({o['referenceShape'] for v in vectors for o in v['occurrences']
             if o['location'] == SELECTED['location'] and o['tag'] == SELECTED['tag']}
            == {'zero', 'nonzero', 'uninterpretable'}, 'reference-shape boundary missing')
    require(any(evaluate(v)['matchedOccurrences'] > 1 for v in vectors),
            'repeated occurrences boundary missing')
    require(any(not v['inventoryComplete'] and evaluate(v)['matchedOccurrences'] for v in vectors),
            'partial inventory with observed indicator boundary missing')
    require(any(not v['inventoryComplete'] and not v['occurrences'] for v in vectors),
            'uninspected inventory boundary missing')
    require(any(v['inventoryComplete'] and v['occurrences']
                and not evaluate(v)['matchedOccurrences'] for v in vectors),
            'out-of-scope identity boundary missing')
    require({evaluate(v)['decision'] for v in vectors} == {'refuse-known-indicator',
            'refuse-uninspectable', 'refuse-invalidation-unimplemented',
            'continue-other-gates-only'}, 'policy decision boundary missing')
    print(json.dumps({'indicator': SELECTED['catalogId'], 'authoredPolicyVectors': len(vectors),
                      'mediaFixturesExecuted': 0, 'signatureVerifications': 0,
                      'productionMutationAllowed': False, 'errors': 0}))


if __name__ == '__main__':
    main()
