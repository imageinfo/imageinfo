"""#0129 finite authored schema/model QA, not a legacy translator or CLI runtime.

Reads only the fixed public schemas/vectors/inventory/migration document. Pure
validators never open paths carried in documents and never execute suggestions.
Uses the repository's existing test-only jsonschema dependency.
"""
from copy import deepcopy
import json
from pathlib import Path
import re
from unittest.mock import patch

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'docs/legacy-compatibility/inert-translation'
MAX_DOCUMENT_BYTES = 131072
DIAGNOSTIC_CODES = frozenset({
    'APPEND_UNAVAILABLE', 'BLANKET_DELETE_UNSUPPORTED', 'COPY_ALL_UNAVAILABLE',
    'DATE_SHIFT_UNAVAILABLE', 'DELETE_UNAVAILABLE', 'DUPLICATE_OPTION',
    'ENUMERATION_REQUIRED', 'EXECUTABLE_CONFIG_UNSUPPORTED', 'IMPORT_UNAVAILABLE',
    'MALFORMED_INVOCATION', 'ORDER_OUTSIDE_FINITE_PROFILE', 'OVERWRITE_UNAVAILABLE',
    'READ_VIEW_DIFFERENCE', 'REFERENCED_FILES_UNOPENED', 'SESSION_PROTOCOL_REQUIRED',
    'UNKNOWN_TOKEN', 'WRITE_UNAVAILABLE',
})


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique_members(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate-member')
        result[key] = value
    return result


def utf8(value):
    require('\0' not in value, 'nul-string')
    return value.encode('utf-8', errors='strict')


def strict_document(data):
    """Whole-buffer authored oracle only; future runtime must bound its own I/O."""
    require(len(data) <= MAX_DOCUMENT_BYTES, 'document-byte-limit')
    text = data.decode('utf-8', errors='strict')
    require(not text.startswith('\ufeff'), 'bom')
    # Count containers outside strings before decoding: no unbounded recursion.
    depth, quoted, escaped = 0, False, False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in '[{':
            depth += 1
            require(depth <= 8, 'depth-limit')
        elif char in ']}':
            depth -= 1
    return json.loads(text, object_pairs_hook=unique_members,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('constant')))


def validate_request(request, validator):
    validator.validate(request)
    require(type(request['schemaVersion']) is int, 'integer-version')
    require(1 <= len(utf8(request['id'])) <= 128, 'id-byte-limit')
    cwd = request['workingDirectory']
    require(1 <= len(utf8(cwd)) <= 32768, 'cwd-byte-limit')
    if request['pathStyle'] == 'posix':
        require(cwd.startswith('/') and not cwd.startswith('//'), 'absolute-posix-cwd')
    else:
        require(bool(re.fullmatch(r'[A-Za-z]:\\.*|\\\\[^\\/]+\\[^\\/]+(?:\\.*)?', cwd)),
                'absolute-windows-cwd')
    tokens = request['arguments']
    total = 0
    for token in tokens:
        size = len(utf8(token))
        require(1 <= size <= 32768, 'token-byte-limit')
        total += size
    require(total <= 65536, 'total-token-byte-limit')
    # argv[0] is not accepted even as an invented executable path.
    require(tokens[0].startswith('-'), 'arguments-omit-executable')


def validate_report(report, request_validator, report_validator, native):
    require(len(json.dumps(report, ensure_ascii=False, separators=(',', ':')).encode('utf-8')) <= 1048576,
            'report-byte-limit')
    report_validator.validate(report)
    for field in ('findings', 'differences', 'questions', 'prerequisites'):
        require(all(item['code'] in DIAGNOSTIC_CODES for item in report[field]),
                'finite-diagnostic-code')
    if report['status'] == 'malformed':
        require(bool(report['findings']), 'malformed-diagnostic')
        return
    req = report['request']
    validate_request(req, request_validator)
    args = req['arguments']
    accounts = report['accounting']
    require(len(accounts) == len(args), 'account-count')
    findings = {item['id']: item for item in report['findings']}
    require(len(findings) == len(report['findings']), 'unique-findings')
    for finding in findings.values():
        require(all(0 <= i < len(args) for i in finding['tokenIndices']), 'finding-index')
        require(len(set(finding['tokenIndices'])) == len(finding['tokenIndices']), 'finding-duplicate-index')
    for index, account in enumerate(accounts):
        require(type(account['index']) is int and account['index'] == index, 'account-order')
        require(account['token'] == args[index], 'source-token')
        token = args[index]
        separate = index > 0 and args[index - 1] in ('-tagsFromFile', '-stay_open', '-@', '-config', '-if')
        literal_input = (len(args) == 3 and args[:2] == ['-n', '-ISO'] and index == 2)
        after_terminator = '--' in args[:index]
        role = ('operand' if literal_input or after_terminator else
                'option-value' if separate else 'terminator' if token == '--' else
                'unknown' if token == '-unknown' else 'option' if token.startswith('-') else 'operand')
        require(account['role'] == role, 'finite-account-role')
        attached = role == 'option' and ('=' in token or token == '-G1')
        expected_owner = index if attached else index - 1 if separate else None
        require(account['valueOwner'] == expected_owner, 'finite-value-owner')
        cut = token.find('=') + 1 if attached and '=' in token else 2 if token == '-G1' else 0
        expected_parts = ([{'start': 0, 'end': cut, 'kind': 'syntax', 'text': token[:cut]},
                           {'start': cut, 'end': len(token), 'kind': 'value', 'text': token[cut:]}]
                          if attached else [{'start': 0, 'end': len(token),
                                             'kind': 'value' if separate else 'syntax' if role in ('option', 'terminator') else 'literal',
                                             'text': token}])
        require(account['parts'] == expected_parts, 'finite-value-parts')
        for fid in account['findingIds']:
            require(fid in findings and index in findings[fid]['tokenIndices'], 'finding-reference')
        cursor = 0
        has_value = False
        for part in account['parts']:
            require(type(part['start']) is int and type(part['end']) is int, 'part-integer')
            require(part['start'] == cursor and cursor <= part['end'] <= len(args[index]), 'part-coverage')
            require(part['text'] == args[index][cursor:part['end']], 'part-text')
            cursor = part['end']
            has_value |= part['kind'] == 'value'
        require(cursor == len(args[index]), 'part-final-coverage')
        owner = account['valueOwner']
        require((owner is not None) == has_value, 'value-owner-presence')
        if owner is not None:
            require(type(owner) is int and 0 <= owner <= index, 'value-owner-index')
            require(accounts[owner]['role'] == 'option', 'value-owner-option')
            require(owner == index or (owner == index - 1 and account['role'] == 'option-value'), 'value-owner-order')
        if account['role'] == 'option-value':
            require(owner == index - 1, 'separated-value-owner')
    for question in report['questions']:
        require(all(0 <= i < len(args) for i in question['tokenIndices']), 'question-index')
    suggestion = report['suggestion']
    if suggestion['state'] == 'usable':
        require(report['status'] == 'complete-with-differences', 'usable-status')
        require(bool(report['differences']), 'usable-differences')
        require(not report['questions'] and not report['prerequisites'], 'usable-unresolved')
        require(suggestion['workingDirectory'] == req['workingDirectory'], 'suggestion-cwd')
        require(suggestion['operation'] + ' INPUT...' in native['commands'], 'available-command')
        # This specification freezes exactly one usable finite mapping, not a
        # general parser whose accepted flags could accidentally grow at runtime.
        require(len(args) == 3 and args[:2] == ['-n', '-ISO'], 'usable-source-template')
        require(suggestion['arguments'] == ['metadata', 'read', '--tag', 'ISO',
                                          '--values', 'normalized', '--', args[2]], 'usable-native-template')
        require('ISO' in native['selectors'] and 'normalized' in native['leafOptions']['metadata read']['--values'],
                'available-native-selector-view')


def rejected(call):
    try:
        call()
    except (ValueError, UnicodeError, RecursionError, __import__('jsonschema').ValidationError):
        return
    raise AssertionError('negative vector was accepted')


def wire(value):
    return json.dumps(value, ensure_ascii=True, separators=(',', ':')).encode('ascii')


def main():
    invocation = json.loads((PACKAGE / 'invocation.schema.v1.json').read_text(encoding='utf-8'))
    report_schema = json.loads((PACKAGE / 'report.schema.v1.json').read_text(encoding='utf-8'))
    vectors = json.loads((PACKAGE / 'vectors.v1.json').read_text(encoding='utf-8'))
    native = json.loads((PACKAGE.parent / 'native-token-inventory.v1.json').read_text(encoding='utf-8'))['native']
    migration = (PACKAGE.parent / 'migration.md').read_text(encoding='utf-8')
    for schema in (invocation, report_schema):
        Draft202012Validator.check_schema(schema)
    registry = Registry().with_resource(invocation['$id'], Resource.from_contents(invocation))
    iv = Draft202012Validator(invocation, registry=registry)
    rv = Draft202012Validator(report_schema, registry=registry)
    require(report_schema['$defs']['diagnosticCode'] == {'enum': sorted(DIAGNOSTIC_CODES)},
            'schema-diagnostic-vocabulary')
    require(vectors['diagnosticCodes'] == sorted(DIAGNOSTIC_CODES), 'vector-diagnostic-vocabulary')
    for field in ('findings', 'differences', 'questions', 'prerequisites'):
        require(report_schema['properties'][field]['items']['properties']['code'] ==
                {'$ref': '#/$defs/diagnosticCode'}, 'shared-schema-diagnostic-vocabulary')
    reports = vectors['reports']
    require([item['id'] for item in reports[:12]] == [f'MIG-{i:03}' for i in range(1, 13)], 'all-twelve')
    expected_states = ['complete-with-differences', 'unsupported', 'unsupported', 'unsupported',
                       'unsupported', 'unsupported', 'unsupported', 'needs-input', 'unsupported',
                       'needs-input', 'unsupported', 'unsupported', 'unsupported', 'needs-input',
                       'unsupported', 'unsupported', 'unsupported']
    require([item['report']['status'] for item in reports] == expected_states, 'frozen-dispositions')
    for item in reports[:12]:
        match = re.search(r'\| ' + item['id'] + r' \| `exiftool ([^`]+)`', migration)
        require(match is not None and match[1].split(' ') == item['report']['request']['arguments'], 'migration-source-freeze')
    # Catch accidental future file/media/config access in the pure validators.
    def no_open(*_args, **_kwargs):
        raise AssertionError('validator tried to open a referenced file')
    with patch('builtins.open', no_open), patch.object(Path, 'open', no_open):
        for item in reports:
            validate_report(item['report'], iv, rv, native)
        base = reports[0]['report']['request']
        malformed = {
            'invalid-utf8': b'\xff', 'bom': b'\xef\xbb\xbf{}',
            'duplicate-member': b'{"id":"a","id":"b"}',
            'trailing-json': wire(base) + b'{}', 'non-object': b'[]',
            'oversize-document': b' ' * (MAX_DOCUMENT_BYTES + 1),
            'excessive-depth': b'[' * 9 + b'0' + b']' * 9,
        }
        changes = {
            'extra-member': {'executable': 'exiftool'}, 'wrong-version': {'schemaVersion': True},
            'non-string-token': {'arguments': [3]}, 'nul-token': {'arguments': ['-n\0']},
            'surrogate-token': {'arguments': ['-\ud800']}, 'empty-token': {'arguments': ['']},
            'relative-cwd': {'workingDirectory': '.'},
            'windows-drive-relative': {'pathStyle': 'windows', 'workingDirectory': 'C:relative'},
            'cwd-style-mismatch': {'workingDirectory': 'C:\\examples'},
            'oversize-id': {'id': 'x' * 129},
            'oversize-token': {'arguments': ['-' + 'x' * 32768]},
            'oversize-multibyte-token': {'arguments': ['-' + '\u00e9' * 16384]},
            'oversize-total-token-bytes': {'arguments': ['-' + 'x' * 32767, 'x' * 32768, 'x']},
            'oversize-token-count': {'arguments': ['-n'] * 129},
            'argv-zero': {'arguments': ['exiftool', '-ISO']}, 'empty-arguments': {'arguments': []},
        }
        for name, change in changes.items():
            value = deepcopy(base)
            value.update(change)
            malformed[name] = wire(value)
        value = deepcopy(base)
        del value['id']
        malformed['missing-id'] = wire(value)
        require(set(malformed) == set(vectors['malformedCases']), 'malformed-case-coverage')
        for data in malformed.values():
            rejected(lambda data=data: validate_request(strict_document(data), iv))
        # Positive boundary/path/Unicode controls are specification evidence only.
        for change in ({'pathStyle': 'windows', 'workingDirectory': 'C:\\examples\\raw'},
                       {'pathStyle': 'windows', 'workingDirectory': '\\\\server\\share\\raw'},
                       {'arguments': ['-' + 'x' * 32767, 'x' * 32768]},
                       {'arguments': ['-n'] * 128}, {'id': '\u00e9' * 64},
                       {'arguments': ['-n', '$HOME/*.cr3', '$(literal)', ';literal']},
                       {'workingDirectory': '/' + 'x' * 32767}):
            value = deepcopy(base)
            value.update(change)
            validate_request(strict_document(wire(value)), iv)
        mutations = {}
        for name in vectors['rejectionMutations']:
            mutations[name] = deepcopy(reports[0]['report'])
        mutations['drop-account']['accounting'].pop()
        mutations['reorder-account']['accounting'].reverse()
        mutations['change-value']['accounting'][0]['parts'][0]['text'] = '-z'
        mutations['unbound-value']['accounting'][0]['valueOwner'] = 0
        mutations['gap-part']['accounting'][0]['parts'][0]['start'] = 1
        mutations['bad-finding-index']['findings'][0]['tokenIndices'].append(127)
        mutations['missing-finding-reference']['accounting'][0]['findingIds'] = ['absent']
        mutations['forged-usable'] = deepcopy(reports[1]['report'])
        mutations['forged-usable']['suggestion'] = deepcopy(reports[0]['report']['suggestion'])
        mutations['forged-command']['suggestion']['arguments'][1] = 'write'
        mutations['source-mismatch']['request']['arguments'][2] = 'other.cr3'
        mutations['claim-effect']['effects']['mediaOpened'] = True
        mutations['missing-prerequisite'] = deepcopy(reports[1]['report'])
        mutations['missing-prerequisite']['prerequisites'] = []
        mutations['wrong-exit-status']['exitStatus'] = 1
        malformed_report = deepcopy(reports[1]['report'])
        malformed_report.update(request=None, accounting=[], status='malformed', exitStatus=2)
        malformed_report['findings'] = [{'id': 'F1', 'code': 'MALFORMED_INVOCATION',
                                         'tokenIndices': [], 'message': 'Invocation data failed preflight.'}]
        malformed_report.update(differences=[], questions=[], prerequisites=[])
        validate_report(malformed_report, iv, rv, native)
        class NoSchemaChecks:
            """Isolate the companion code invariant from schema enum rejection."""
            @staticmethod
            def validate(_value):
                pass
        for field in ('findings', 'differences', 'questions', 'prerequisites', 'malformed'):
            for kind, code in (('unknown', 'UNREGISTERED_CODE'), ('empty', '')):
                name = f'{field}-{kind}-code'
                value = deepcopy(malformed_report if field == 'malformed' else reports[3]['report'])
                value['findings' if field == 'malformed' else field][0]['code'] = code
                mutations[name] = value
                # Each genuine negative is rejected by both the actual schema
                # and the semantic companion independently, including malformed.
                rejected(lambda value=value: rv.validate(value))
                rejected(lambda value=value: validate_report(value, iv, NoSchemaChecks(), native))
        require(set(mutations) == set(vectors['rejectionMutations']), 'report-mutation-coverage')
        for value in mutations.values():
            rejected(lambda value=value: validate_report(value, iv, rv, native))
    print(f'PASS #0129: {len(reports)} authored reports (all 12 MIG), '
          f'{len(malformed)} malformed, 7 positive boundary/path controls, '
          f'{len(mutations)} rejected report mutations; no referenced-file opens')


if __name__ == '__main__':
    main()
