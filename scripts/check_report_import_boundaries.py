"""#0126 test-only finite report/intent contract; never opens media or applies edits."""
import csv
import hashlib
import io
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'docs/legacy-compatibility/report-import'
HEADER = ['sourceKey', 'snapshotId', 'occurrenceId', 'namespace', 'nativeId',
          'valueKind', 'decimal', 'numerator', 'denominator', 'text']
IDENTITY = HEADER[:5]
DIMENSIONS = {'duplicates', 'groups', 'lists', 'language', 'binary', 'encoding',
              'omission', 'empty', 'null', 'missing', 'matching', 'loss'}
PROFILES = {'native-json', 'native-plain', 'legacy-json', 'legacy-csv', 'legacy-xml',
            'legacy-short', 'legacy-plain', 'legacy-args', 'legacy-php', 'legacy-plot',
            'templates', 'filename-placeholders', 'inert-json', 'inert-csv',
            'legacy-json-import', 'legacy-csv-import'}


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def members(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate-member')
        result[key] = value
    return result


def scalar_text(text):
    require(type(text) is str, 'text-type')
    require(not any(0xd800 <= ord(c) <= 0xdfff for c in text), 'unicode-scalar')
    return text


def parse_json(text):
    def nonfinite(_):
        raise ValueError('nonfinite')
    return json.loads(text, object_pairs_hook=members, parse_constant=nonfinite)


def load(path):
    return parse_json(path.read_text(encoding='utf-8'))


def uint(value, maximum):
    require(type(value) is str and re.fullmatch(r'0|[1-9][0-9]{0,19}', value),
            'decimal-spelling')
    require(int(value) <= maximum, 'decimal-range')


def csv_rows(text):
    """Check a strict finite CSV lexical grammar before the stdlib field decoder."""
    require(text.endswith('\r\n'), 'csv-final-crlf')
    state = 'start'
    i = 0
    while i < len(text):
        c = text[i]
        if state == 'quoted':
            if c == '"':
                if i + 1 < len(text) and text[i + 1] == '"':
                    i += 2
                    continue
                state = 'closed'
            i += 1
            continue
        if c == '\r':
            require(text[i:i + 2] == '\r\n', 'csv-record-crlf')
            state = 'start'
            i += 2
            continue
        require(c != '\n', 'csv-record-crlf')
        if c == ',':
            state = 'start'
        elif c == '"':
            require(state == 'start', 'csv-quote')
            state = 'quoted'
        else:
            require(state != 'closed', 'csv-after-quote')
            state = 'unquoted'
        i += 1
    require(state != 'quoted', 'csv-unclosed-quote')
    return list(csv.reader(io.StringIO(text, newline=''), strict=True))


def decode_csv(text):
    rows = csv_rows(text)
    require(rows and rows[0] == HEADER, 'csv-header')
    edits = []
    for row in rows[1:]:
        require(len(row) == len(HEADER), 'csv-width')
        cells = dict(zip(HEADER, row))
        kind = cells['valueKind']
        fields = {'integer': ['decimal'], 'rational': ['numerator', 'denominator'],
                  'string': ['text']}.get(kind)
        require(fields is not None, 'value-kind')
        require(all(cells[k] == '' for k in ['decimal', 'numerator', 'denominator', 'text']
                    if k not in fields), 'csv-unused-cell')
        edits.append({**{k: cells[k] for k in IDENTITY}, 'operation': 'set',
                      'value': {'kind': kind, **{k: cells[k] for k in fields}}})
    return {'schemaVersion': 1, 'kind': 'inert-scalar-intents', 'edits': edits}


def validate(document, bindings):
    require(type(document) is dict and set(document) == {'schemaVersion', 'kind', 'edits'},
            'root-shape')
    require(type(document['schemaVersion']) is int and document['schemaVersion'] == 1
            and document['kind'] == 'inert-scalar-intents', 'profile-version')
    edits = document['edits']
    require(type(edits) is list and 1 <= len(edits) <= 64, 'edit-bound')
    require(type(bindings) is list and 1 <= len(bindings) <= 16, 'binding-bound')
    # Bindings are trusted authored observation-table fixtures, never file authority.
    source_keys = [b['sourceKey'] for b in bindings]
    require(len(source_keys) == len(set(source_keys)), 'ambiguous-binding')
    snapshot_ids = [b['snapshotId'] for b in bindings]
    require(len(snapshot_ids) == len(set(snapshot_ids)), 'aliased-snapshot-binding')
    for binding in bindings:
        occurrence_ids = [o['occurrenceId'] for o in binding['occurrences']]
        require(len(occurrence_ids) == len(set(occurrence_ids)), 'occurrence-match')
    seen = set()
    for edit in edits:
        require(type(edit) is dict and set(edit) == set(IDENTITY) | {'operation', 'value'},
                'edit-shape')
        require(edit['operation'] == 'set', 'operation')
        for k in IDENTITY:
            scalar_text(edit[k])
            require(1 <= len(edit[k]) <= 256, 'identity-bound')
        require(re.fullmatch(r'[A-Za-z0-9_-]{1,64}', edit['sourceKey']), 'source-key')
        key = tuple(edit[k] for k in IDENTITY[:3])
        require(key not in seen, 'duplicate-target')
        seen.add(key)
        matches = [b for b in bindings if b['sourceKey'] == edit['sourceKey']]
        require(len(matches) == 1, 'unmatched-source')
        binding = matches[0]
        require(binding['snapshotId'] == edit['snapshotId'], 'snapshot-mismatch')
        occurrences = [o for o in binding['occurrences']
                       if o['occurrenceId'] == edit['occurrenceId']]
        require(len(occurrences) == 1, 'occurrence-match')
        require(all(occurrences[0][k] == edit[k] for k in ['namespace', 'nativeId']),
                'identity-mismatch')
        value = edit['value']
        require(type(value) is dict and type(value.get('kind')) is str, 'value-shape')
        kind = value['kind']
        if kind == 'integer':
            require(set(value) == {'kind', 'decimal'}, 'value-shape')
            uint(value['decimal'], 2**64 - 1)
        elif kind == 'rational':
            require(set(value) == {'kind', 'numerator', 'denominator'}, 'value-shape')
            uint(value['numerator'], 2**32 - 1)
            uint(value['denominator'], 2**32 - 1)
            require(value['denominator'] != '0', 'zero-denominator')
        elif kind == 'string':
            require(set(value) == {'kind', 'text'}, 'value-shape')
            require(len(scalar_text(value['text']).encode('utf-8')) <= 4096, 'text-byte-bound')
        else:
            raise ValueError('value-kind')
    return document


def evaluate(case):
    text = case['input']
    try:
        scalar_text(text)
        if 'padInputToBytes' in case:
            # Fixed authored bound probe without a megabyte of checked-in whitespace.
            n = case['padInputToBytes']
            require(type(n) is int and 0 <= n <= 1048577, 'fixture-padding-bound')
            text += ' ' * max(0, n - len(text.encode('utf-8')))
        require(not text.startswith('\ufeff'), 'bom')
        require(len(text.encode('utf-8')) <= 1048576, 'input-byte-bound')
        require(case['transport'] in ('json', 'csv'), 'transport')
        document = parse_json(text) if case['transport'] == 'json' else decode_csv(text)
        return {'state': 'modeled-intents', 'document': validate(document, case['bindings'])}
    except (ValueError, csv.Error) as error:
        # JSON parser messages vary by Python release; vector expectations name refusal,
        # not a new product error-code grammar.
        return {'state': 'refused', 'reason': str(error)}


def main():
    matrix = load(PACKAGE / 'profiles.v1.json')
    require(matrix['schemaVersion'] == 1 and matrix['ticket'] == '#0126', 'matrix identity')
    require(matrix['evidenceKind'] == 'specification-and-authored-model-only', 'evidence kind')
    require(matrix['authority'] == {k: False for k in [
        'runtimeImporter', 'newRenderer', 'legacyParity', 'mutationAllowed',
        'storageAdmission', 'losslessStandaloneExport']}, 'authority flags')
    require(set(matrix['ruleSets']) == {'native-exact', 'native-display',
                                      'legacy-open', 'inert-scalar'}, 'rule sets')
    for rules in matrix['ruleSets'].values():
        require(set(rules) == DIMENSIONS and all(type(v) is str and v for v in rules.values()),
                'rule dimension coverage')
    profiles = matrix['profiles']
    require(len(profiles) == len(PROFILES) and {p['id'] for p in profiles} == PROFILES,
            '16-profile denominator')
    for profile in profiles:
        require(profile['ruleSet'] in matrix['ruleSets'], 'rule reference')
        require(profile['status'] == ('supported' if profile['id'] in
                                     {'native-json', 'native-plain'} else 'unimplemented'),
                'runtime status')
        require(profile['contract'] and profile['nextOutcome'] and profile['residual'],
                'concrete profile outcome')
        require(profile['residualOwner'] == '#0015', 'residual owner')
        require(profile['evidence'] and all((ROOT / p).is_file() for p in profile['evidence']),
                'local evidence paths')
    schema = load(PACKAGE / 'intent.schema.v1.json')
    require(schema['additionalProperties'] is False
            and schema['properties']['edits']['maxItems'] == 64
            and schema['$defs']['edit']['additionalProperties'] is False
            and len(schema['$defs']['value']['oneOf']) == 3, 'closed scalar schema')
    package = load(PACKAGE / 'vectors.v1.json')
    require(package['contract'] == matrix['revision'], 'vector binding')
    require(package['schemaSha256'] == hashlib.sha256(
        (PACKAGE / 'intent.schema.v1.json').read_bytes()).hexdigest(), 'schema vector binding')
    ids = set()
    dimensions = set()
    accepted = 0
    groups = {}
    for case in package['vectors']:
        require(case['id'] not in ids, 'unique vector')
        ids.add(case['id'])
        require(set(case['dimensions']) <= DIMENSIONS, 'vector dimension vocabulary')
        dimensions.update(case['dimensions'])
        result = evaluate(case)
        require(result['state'] == case['expectedState'], case['id'] + ': outcome')
        if case.get('expectedReason'):
            require(result.get('reason') == case['expectedReason'], case['id'] + ': reason')
        if result['state'] == 'modeled-intents':
            accepted += 1
            require(result['document'] == case['expectedDocument'], case['id'] + ': exact intent')
            if case.get('equivalenceGroup'):
                groups.setdefault(case['equivalenceGroup'], []).append(result['document'])
    require(len(ids) == package['vectorCount'] and accepted == package['acceptedCount'],
            'vector denominator')
    require(len(groups) >= 4 and all(len(v) == 2 and v[0] == v[1] for v in groups.values()),
            'JSON/CSV equivalence groups')
    require(set(package['coveredDimensions']) == dimensions == DIMENSIONS,
            'vector dimension coverage')
    print(json.dumps({'profiles': len(profiles), 'ruleDimensions': len(DIMENSIONS),
                      'authoredVectors': len(ids), 'modeledIntents': accepted,
                      'equivalentTransportPairs': len(groups), 'runtimeImports': 0,
                      'mediaOperations': 0}))


if __name__ == '__main__':
    main()
