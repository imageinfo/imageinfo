"""Independent finite #0056 ledger checks; reads public source/specification only.

This checks declared mapping identity and reference closure, not media semantics,
write admission, or a complete date catalog. Existing Rust tests exercise the
actual reader/admission/preview/source-binding paths independently.
"""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / 'docs/legacy-compatibility/r5-date-mapping.v1.json'
FIELDS = {
    'dto': ('DateTimeOriginal', 0x9003),
    'offset-original': ('OffsetTimeOriginal', 0x9011),
    'subsec-original': ('SubSecTimeOriginal', 0x9291),
    'digitized-alias': ('DateTimeDigitized', 0x9004),
}
OPERATIONS = {'named-read', 'changed-intent-preview', 'identical-intent-preview',
              'repair', 'dependency-absence-proof'}


class Rejected(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise Rejected(message)


def strict(text):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON member')
            result[key] = value
        return result

    def invalid(value):
        raise Rejected('nonfinite JSON constant: ' + value)

    return json.loads(text, object_pairs_hook=pairs, parse_constant=invalid)


def closed(value, keys, label):
    require(type(value) is dict and set(value) == set(keys.split()), label + ' keys')


def nonempty(value):
    return type(value) is str and bool(value.strip())


def references(value, source_ids):
    require(type(value) is list and value and all(type(ref) is str for ref in value)
            and len(value) == len(set(value)) and set(value) <= source_ids,
            'missing, duplicate or unresolved source reference')


def validate(value):
    closed(value, 'schemaVersion catalogId revision observedOn sourceRevision requirements '
           'authority statusMeaning sources fields operationRows denominators evidenceCounts '
           'exclusions', 'ledger')
    require(type(value['schemaVersion']) is int and value['schemaVersion'] == 1
            and value['catalogId'] == 'r5-date-family-bounded'
            and value['revision'] == '2026-10-15.1'
            and value['observedOn'] == '2026-10-15', 'ledger version')
    require(value['sourceRevision'] == '211f395e62c2dc35f396c1d40336d87344e4b4d1',
            'reviewed source revision')
    require(value['requirements'] == ['LG-005'], 'bounded requirement references')
    closed(value['authority'], 'productionMutationAllowed repairEnabled runtimeRegistry '
           'completeDateFamily', 'authority')
    require(all(type(item) is bool and item is False for item in value['authority'].values()),
            'ledger cannot grant capability or complete coverage')
    closed(value['statusMeaning'], 'supported refused unverified', 'status meanings')
    require(all(nonempty(item) for item in value['statusMeaning'].values()), 'status meanings')
    require(type(value['sources']) is list, 'sources array')
    source_ids = set()
    for source in value['sources']:
        closed(source, 'id path purpose observedOn', 'source')
        require(nonempty(source['id']) and source['id'] not in source_ids, 'source identity')
        source_ids.add(source['id'])
        require(nonempty(source['purpose']) and source['observedOn'] in
                {'2026-10-11', '2026-10-12', '2026-10-15'}, 'source description/date')
        require(type(source['path']) is str, 'source path')
        path = (ROOT / source['path']).resolve()
        require(path.is_relative_to(ROOT) and path.is_file()
                and source['path'].startswith(('src/', 'tests/', 'docs/')),
                'source must be an existing public repository file')
    required_paths = {'reader': 'src/reader/mod.rs', 'selector': 'src/reader/wire.rs',
                      'tiff': 'src/reader/tiff.rs', 'admission': 'src/reader/admission.rs',
                      'preview': 'src/preview.rs',
                      'plan': 'src/plan.rs', 'binding': 'src/source_binding.rs',
                      'authored-binding': 'tests/source_binding.rs',
                      'authored-alias': 'tests/admission_contract.rs',
                      'authored-preview': 'tests/date_preview.rs',
                      'admission-observations': 'docs/write-safety/admission-observations.json'}
    actual_paths = {source['id']: source['path'] for source in value['sources']}
    require(all(actual_paths.get(key) == path for key, path in required_paths.items()),
            'primary implementation/evidence references changed')

    require(type(value['fields']) is list and len(value['fields']) == len(FIELDS), 'field count')
    seen_fields = set()
    # Extract the actual root CMT2 date decoder arms. This independently catches
    # drift between the implemented named read subset and the documented ledger.
    reader = (ROOT / 'src/reader/mod.rs').read_text(encoding='utf-8')
    decoded = {name: int(tag, 16) for tag, name in re.findall(
        r'\(b"CMT2", (0x[0-9a-f]+)\) => "(DateTimeOriginal|OffsetTimeOriginal|SubSecTimeOriginal|DateTimeDigitized)"',
        reader)}
    require(decoded == {name: tag for key, (name, tag) in FIELDS.items()
                        if key != 'digitized-alias'}, 'actual root date decoder subset changed')
    wire = (ROOT / 'src/reader/wire.rs').read_text(encoding='utf-8')
    names = set(re.findall(r'"([A-Za-z]+)"', wire.split('pub const NAMES:')[1].split('];')[0]))
    for field in value['fields']:
        closed(field, 'id name namespace nativeId tagHex container parentUuid pathRule selectors '
               'evidenceKind storage sourceRefs', 'field')
        key = field['id']
        require(key in FIELDS and key not in seen_fields, 'field identity')
        seen_fields.add(key)
        name, tag = FIELDS[key]
        require((field['name'], field['nativeId'], field['tagHex']) ==
                (name, str(tag), f'0x{tag:04x}'), 'native field identity')
        require(field['namespace'] == 'exif' and field['container'] == 'CMT2'
                and field['parentUuid'] == '85c0b687820f11e08111f4ce462b6a48',
                'exact native namespace/container')
        require(nonempty(field['pathRule']) and nonempty(field['storage']), 'field policy')
        opaque = key == 'digitized-alias'
        expected_selectors = [] if opaque else [name, 'EXIF:' + name, 'exif:' + name]
        require(field['selectors'] == expected_selectors
                and (name not in names if opaque else name in names), 'named selector subset')
        require(field['evidenceKind'] == ('opaque-alias-witness' if opaque else
                                         'decoded-stored-string'), 'evidence kind')
        references(field['sourceRefs'], source_ids)

    require(type(value['operationRows']) is list, 'operation array')
    cells = set()
    counts = Counter()
    for row in value['operationRows']:
        closed(row, 'id fieldId operation status reason runtimeCode sourceRefs', 'operation')
        key, operation = row['fieldId'], row['operation']
        require(key in FIELDS and operation in OPERATIONS and (key, operation) not in cells,
                'unknown or repeated operation cell')
        cells.add((key, operation))
        require(row['id'] == key + ':' + operation, 'operation identity')
        expected = 'refused'
        if operation == 'dependency-absence-proof':
            expected = 'unverified'
        elif operation == 'named-read' and key != 'digitized-alias':
            expected = 'supported'
        elif key == 'dto' and operation in {'changed-intent-preview', 'identical-intent-preview'}:
            expected = 'supported'
        require(row['status'] == expected, 'observation/refusal/proof distinction')
        code = 'TAG_UNSUPPORTED' if (key, operation) == ('digitized-alias', 'named-read') else None
        require(row['runtimeCode'] == code, 'ledger must not invent runtime codes')
        require(nonempty(row['reason']), 'operation reason')
        references(row['sourceRefs'], source_ids)
        needed = {'reader', 'selector', 'tiff'} if operation == 'named-read' else (
            {'preview', 'admission', 'authored-preview'} if operation.endswith('preview') else
            {'admission', 'admission-method'})
        require(needed <= set(row['sourceRefs']), 'operation missing primary implementation trace')
        counts[row['status']] += 1
    require(cells == {(key, operation) for key in FIELDS for operation in OPERATIONS},
            'finite operation matrix incomplete')
    expected_counts = dict(fieldRows=4, decodedFieldRows=3, opaqueWitnessRows=1,
                           operationsPerField=5, operationRows=len(cells), **counts)
    require(value['denominators'] == expected_counts
            and all(type(item) is int for item in value['denominators'].values()),
            'denominators must derive from the complete finite matrix')

    observed = strict((ROOT / required_paths['admission-observations']).read_text(encoding='utf-8'))
    cases = observed['cases']
    alias_cases = [case for case in cases if case['expectedRefusal'] == 'FIELD_ALLOCATION_ALIAS']
    evidence = dict(readSourceCount=8, readDeclaredScalarRationalChecks=160,
                    readAllPrimitiveSpanChecks=184, admissionSourceCount=observed['sourceCount'],
                    admissionRows=len(cases), admissionCaseKindsPerSource=7,
                    admissionMutationRefusals=sum(case['productionMutationAllowed'] is False
                                                 for case in cases),
                    admissionAliasKindsPerSource=2, admissionAliasRefusals=len(alias_cases),
                    privateAliasCandidates=observed['candidateAliasDerivatives'],
                    privateAliasDecodedPairsEqual=observed['decodedPairsEqual'],
                    realCameraNewMutationAdmissions=0)
    require(value['evidenceCounts'] == evidence
            and all(type(item) is int for item in value['evidenceCounts'].values()),
            'historical evidence denominators drifted')
    require(type(value['exclusions']) is list and len(value['exclusions']) >= 6
            and all(nonempty(item) for item in value['exclusions']), 'explicit exclusions')
    return counts


def negative_vectors(value):
    """Independent edits test identity, closure and authority, not prose keywords."""
    edits = [
        (['schemaVersion'], True), (['catalogId'], 'all-date-tags'),
        (['sourceRevision'], '0' * 40), (['requirements'], ['LG-005', 'DATE']),
        (['authority', 'productionMutationAllowed'], True),
        (['authority', 'repairEnabled'], True), (['authority', 'runtimeRegistry'], 0),
        (['authority', 'completeDateFamily'], True),
        (['fields', 0, 'nativeId'], '36868'), (['fields', 0, 'namespace'], 'tiff-exif'),
        (['fields', 0, 'container'], 'CMT1'), (['fields', 0, 'parentUuid'], '0' * 32),
        (['fields', 0, 'selectors'], ['CreateDate']),
        (['fields', 3, 'selectors'], ['DateTimeDigitized']),
        (['fields', 3, 'evidenceKind'], 'decoded-stored-string'),
        (['fields', 0, 'sourceRefs'], ['missing']),
        (['fields', 0, 'sourceRefs'], ['reader', 'reader']),
        (['operationRows', 0, 'status'], 'unverified'),
        (['operationRows', 0, 'runtimeCode'], 'NEW_REFUSAL'),
        (['operationRows', 0, 'sourceRefs'], ['reader']),
        (['operationRows', 3, 'status'], 'supported'),
        (['operationRows', 4, 'status'], 'refused'),
        (['denominators', 'supported'], 6), (['evidenceCounts', 'admissionRows'], 55),
        (['evidenceCounts', 'realCameraNewMutationAdmissions'], 1),
        (['sources', 0, 'path'], '../private.json'),
        (['operationRows'], value['operationRows'][:-1]),
        (['operationRows'], value['operationRows'] + [value['operationRows'][0]]),
        (['fields'], value['fields'][:-1] + [value['fields'][0]]),
    ]
    for path, replacement in edits:
        changed = deepcopy(value)
        parent = changed
        for part in path[:-1]:
            parent = parent[part]
        parent[path[-1]] = replacement
        try:
            validate(changed)
        except Rejected:
            continue
        raise AssertionError(f'negative mutation accepted: {path}')
    for wire in ['{"schemaVersion":1,"schemaVersion":1}', '{"value":NaN}']:
        try:
            strict(wire)
        except Rejected:
            continue
        raise AssertionError('non-strict JSON accepted')
    return len(edits) + 2


def main():
    value = strict(LEDGER.read_text(encoding='utf-8'))
    counts = validate(value)
    vectors = negative_vectors(value)
    print(json.dumps({'ticket': 56, 'fields': len(value['fields']),
                      'operationRows': len(value['operationRows']), 'statuses': dict(counts),
                      'negativeVectors': vectors, 'allPassed': True,
                      'mediaExecuted': 0, 'productionMutationAllowed': False}, indent=2))


if __name__ == '__main__':
    main()
