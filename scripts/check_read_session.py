"""#0058 authored protocol model/schema QA; never a session runtime or media reader.

Uses the existing test-only jsonschema==4.26.0 dependency. Input is retained public
test data; this whole-buffer oracle does not demonstrate bounded runtime I/O.
"""
from copy import deepcopy
import json
from pathlib import Path
import re

from jsonschema import Draft202012Validator, ValidationError
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'docs/legacy-compatibility/read-session'
LIMITS = {
    'maxInputFrameBytes': 524288, 'maxOutputFrameBytes': 16777728,
    'maxFrames': 256, 'maxQueuedRequests': 0, 'maxTokens': 128,
    'maxTokenBytes': 32768, 'maxTotalTokenBytes': 65536,
    'maxInputs': 4, 'maxMetadataBytes': 8388608, 'maxResultBytes': 16777216,
}


class ProtocolError(ValueError):
    pass


def wire(value):
    return (json.dumps(value, ensure_ascii=False, separators=(',', ':')) + '\n').encode('utf-8')


def strict_json(data, max_depth=None):
    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError as error:
        raise ProtocolError('FRAME_ENCODING') from error
    if text.startswith('\ufeff'):
        raise ProtocolError('FRAME_ENCODING')
    # Lexical depth check precedes recursive JSON parsing. Brackets in strings
    # and escaped quotes do not add depth; malformed lexical input still fails.
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
            if max_depth is not None and depth > max_depth:
                raise ProtocolError('FRAME_SCHEMA')
        elif char in ']}':
            depth -= 1

    def members(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ProtocolError('FRAME_JSON')
            result[key] = value
        return result

    def constant(_):
        raise ProtocolError('FRAME_JSON')

    try:
        value = json.loads(text, object_pairs_hook=members, parse_constant=constant)
    except (ValueError, RecursionError) as error:
        raise ProtocolError('FRAME_JSON') from error

    def scalars(item):
        if isinstance(item, str):
            if any(0xD800 <= ord(char) <= 0xDFFF for char in item):
                raise ProtocolError('FRAME_ENCODING')
        elif isinstance(item, dict):
            for key, child in item.items():
                scalars(key)
                scalars(child)
        elif isinstance(item, list):
            for child in item:
                scalars(child)

    scalars(value)
    return value


def validators():
    schemas = [json.loads(path.read_text(encoding='utf-8')) for path in (
        ROOT / 'docs/metadata-model/metadata-contract.schema.json',
        ROOT / 'docs/legacy-compatibility/result.schema.json',
        PACKAGE / 'schema.v1.json',
    )]
    registry = Registry()
    for schema in schemas:
        Draft202012Validator.check_schema(schema)
        registry = registry.with_resource(schema['$id'], Resource.from_contents(schema))
    schema = schemas[-1]
    return tuple(Draft202012Validator({'$ref': schema['$id'] + '#/$defs/' + name},
                                    registry=registry) for name in ('input', 'output'))


def envelope(request_id, code='AUTHORED_REFUSAL', status=2):
    """Schema-shaped fake engine response; status injection is transport-only.

    Non-2 statuses exercise session exit independence, not the native result
    producer's file/count/issue semantics. Native semantics have separate #0053
    and #0057 checks; this model never executes command tokens.
    """
    return {
        'schemaVersion': 1, 'requestId': request_id,
        'request': {'schemaVersion': 1, 'kind': 'request', 'requestId': request_id,
                    'operation': None, 'mode': None, 'issues': [{
                        'code': code, 'severity': 'error', 'message': 'Authored protocol vector.',
                        'inputId': None, 'path': None, 'occurrenceRef': None}]},
        'files': [],
        'summary': {'schemaVersion': 1, 'kind': 'summary', 'requestId': request_id,
                    'exitStatus': status, 'selectionComplete': False,
                    'counts': {'discovered': 0, 'excluded': 0, 'deduplicated': 0, 'byState': {}},
                    'artifacts': [], 'issues': [], 'interrupted': False, 'outputComplete': True},
    }


def input_semantics(value):
    if re.fullmatch(r'[A-Za-z][A-Za-z0-9._:-]{0,127}', value['id']) is None:
        raise ProtocolError('FRAME_SCHEMA')
    if value['kind'] == 'read':
        sizes = [len(token.encode('utf-8')) for token in value['tokens']]
        if (any('\0' in token for token in value['tokens'])
                or any(size > LIMITS['maxTokenBytes'] for size in sizes)
                or sum(sizes) > LIMITS['maxTotalTokenBytes']):
            raise ProtocolError('FRAME_SCHEMA')


def model(data, input_validator, responses=()):
    """Sequential framing oracle with authored fake engine responses only."""
    output = [{'protocolVersion': 1, 'kind': 'session-ready',
               'limits': LIMITS, 'allowApply': False}]
    seen, frames, results, close_id = set(), 0, 0, None
    reason, status, error = 'eof', 0, None
    position = 0
    while position < len(data):
        frames += 1
        end = data.find(b'\n', position)
        try:
            length = (len(data) if end < 0 else end + 1) - position
            if length > LIMITS['maxInputFrameBytes'] or (end < 0 and length == LIMITS['maxInputFrameBytes']):
                raise ProtocolError('FRAME_TOO_LARGE')
            if end < 0:
                raise ProtocolError('FRAME_TRUNCATED')
            value = strict_json(data[position:end], max_depth=8)
            if not input_validator.is_valid(value):
                raise ProtocolError('FRAME_SCHEMA')
            input_semantics(value)
            if value['id'] in seen:
                raise ProtocolError('DUPLICATE_ID')
            seen.add(value['id'])
            if value['kind'] == 'close':
                close_id, reason = value['id'], 'close'
                break
            # No command parser is emulated. Different tokens cannot inherit
            # prior state: each response is a separately authored refusal.
            response = responses[results] if results < len(responses) else {}
            output.append({'protocolVersion': 1, 'kind': 'read-result', 'id': value['id'],
                           'result': envelope(value['id'], **response)})
            results += 1
            if frames == LIMITS['maxFrames']:
                reason = 'limit'
                break
            position = end + 1
        except ProtocolError as failure:
            reason, status, error = 'protocol-error', 2, str(failure)
            output.append({'protocolVersion': 1, 'kind': 'protocol-error',
                           'id': None, 'code': error})
            break
    output.append({'protocolVersion': 1, 'kind': 'session-complete', 'reason': reason,
                   'exitStatus': status, 'frames': frames, 'results': results, 'closeId': close_id})
    return output


def validate_transcript(output, validator):
    assert output[0]['kind'] == 'session-ready'
    assert output[-1]['kind'] == 'session-complete'
    interior = [row['kind'] for row in output[1:-1]]
    assert all(kind == 'read-result' for kind in interior[:-1])
    assert not interior or interior[-1] in ('read-result', 'protocol-error')
    ids, errors = [], []
    for record in output:
        validator.validate(record)
        assert len(wire(record)) <= LIMITS['maxOutputFrameBytes']
        if record['kind'] == 'read-result':
            result = record['result']
            assert len(wire(result)) <= LIMITS['maxResultBytes']
            assert record['id'] == result['requestId'] == result['request']['requestId'] == result['summary']['requestId']
            assert result['request']['mode'] in (None, 'read')
            assert result['request']['operation'] in (None, 'metadata read')
            assert result['summary']['exitStatus'] in (0, 1, 2, 3)
            assert not result['summary']['artifacts'] and not result['summary']['interrupted']
            assert result['summary']['outputComplete']
            for item in result['files']:
                assert item['requestId'] == record['id']
                assert item['state'] in ('read', 'failed', 'refused')
                assert item['transactionId'] is None
                assert item['effects'] == {'publicationMayHaveOccurred': False, 'changed': False,
                                           'cleanupPending': False, 'recoveryIds': [], 'notes': []}
            ids.append(record['id'])
        elif record['kind'] == 'protocol-error':
            errors.append(record)
        if record['kind'] != 'read-result':
            assert len(wire(record)) <= 4096
    complete = output[-1]
    assert len(set(ids)) == len(ids) == complete['results']
    if complete['reason'] == 'input-error':
        assert complete['frames'] in (len(ids), len(ids) + 1)
    else:
        assert complete['frames'] == len(ids) + (complete['closeId'] is not None) + (complete['reason'] == 'protocol-error')
    if complete['reason'] == 'limit':
        assert complete['frames'] == 256
    assert complete['closeId'] is None or complete['closeId'] not in ids
    assert len(errors) == (complete['reason'] in ('protocol-error', 'input-error'))
    if errors:
        assert (errors[0]['code'] == 'INPUT_IO') == (complete['reason'] == 'input-error')
    assert complete['exitStatus'] == {'protocol-error': 2, 'input-error': 1}.get(complete['reason'], 0)
    assert len(b''.join(wire(row) for row in output)) <= 256 * LIMITS['maxOutputFrameBytes'] + 3 * 4096


def expand(case):
    if 'utf8' in case:
        return case['utf8'].encode('utf-8')
    if 'hex' in case:
        return bytes.fromhex(case['hex'])
    recipe = case['recipe']
    kind = recipe['kind']
    if kind == 'count':
        return b''.join(wire({'protocolVersion': 1, 'kind': 'read', 'id': f'r{i}', 'tokens': []})
                        for i in range(recipe['count'])) + recipe.get('tail', '').encode('utf-8')
    if kind == 'padding':
        core = wire({'protocolVersion': 1, 'kind': 'close', 'id': 'done'})
        return core[:-1] + b' ' * (recipe['bytes'] - len(core)) + b'\n'
    if kind == 'unterminated':
        return b' ' * recipe['bytes']
    if kind == 'depth':
        return b'[' * recipe['depth'] + b'0' + b']' * recipe['depth'] + b'\n'
    if kind == 'tokens':
        tokens = [item['text'] * item['repeat'] for item in recipe['tokens']]
        return wire({'protocolVersion': 1, 'kind': 'read', 'id': 'r1', 'tokens': tokens})
    raise AssertionError('unknown vector recipe')


def main():
    input_validator, output_validator = validators()
    vectors = json.loads((PACKAGE / 'vectors.v1.json').read_text(encoding='utf-8'))
    for case in vectors['cases']:
        output = model(expand(case), input_validator, case.get('responses', ()))
        validate_transcript(output, output_validator)
        complete = output[-1]
        actual = {key: complete[key] for key in ('reason', 'exitStatus', 'frames', 'results', 'closeId')}
        actual['error'] = next((row['code'] for row in output if row['kind'] == 'protocol-error'), None)
        assert actual == case['expect'], (case['id'], actual, case['expect'])
    for transcript in vectors['wireTranscripts']:
        data = transcript['outputUtf8'].encode('utf-8')
        assert data.endswith(b'\n')
        output = [strict_json(line) for line in data.split(b'\n')[:-1]]
        validate_transcript(output, output_validator)
        assert output == model(transcript['inputUtf8'].encode('utf-8'), input_validator,
                               transcript.get('responses', ())), transcript['id']
    # Assert client interpretation of authored delivery observations. These
    # explicit status/prefix inputs do not inject an actual pipe/flush failure.
    for case in vectors['transportVectors']:
        data = case['outputUtf8'].encode('utf-8')
        complete = False
        if data.endswith(b'\n'):
            records = [strict_json(line) for line in data.split(b'\n')[:-1]]
            if records and records[-1]['kind'] == 'session-complete':
                validate_transcript(records, output_validator)
                complete = case['processStatus'] == 0 and records[-1]['exitStatus'] == 0
        assert complete == case['completeSession'], case['id']
    # Independent negative output checks: schemas alone cannot bind IDs,
    # terminal counters or completion to transport delivery.
    baseline = model(b'{"protocolVersion":1,"kind":"read","id":"r1","tokens":[]}\n', input_validator)
    mutations = []
    for field, value in [('allowApply', True), ('unexpected', 'field')]:
        altered = deepcopy(baseline)
        altered[0][field] = value
        mutations.append(altered)
    altered = deepcopy(baseline)
    altered[0]['limits']['maxQueuedRequests'] = 1
    mutations.append(altered)
    for field, value in [('id', 'other')]:
        altered = deepcopy(baseline)
        altered[1][field] = value
        mutations.append(altered)
    for field, value in [('results', 0), ('frames', 2), ('exitStatus', 2), ('closeId', 'r1')]:
        altered = deepcopy(baseline)
        altered[-1][field] = value
        mutations.append(altered)
    for field, value in [('mode', 'apply'), ('operation', 'preview date-time-original')]:
        altered = deepcopy(baseline)
        altered[1]['result']['request'][field] = value
        mutations.append(altered)
    for field, value in [('outputComplete', False), ('interrupted', True), ('exitStatus', 130)]:
        altered = deepcopy(baseline)
        altered[1]['result']['summary'][field] = value
        mutations.append(altered)
    mutations.extend([baseline[:-1], baseline[1:]])
    altered = deepcopy(baseline)
    altered.insert(1, deepcopy(altered[0]))
    mutations.append(altered)
    # The largest wrapper ID adds only this fixed ASCII framing overhead to
    # native compact result bytes; its one LF replaces the native result LF.
    wrapper_overhead = len(wire({'protocolVersion': 1, 'kind': 'read-result',
                                 'id': 'r' * 128, 'result': {}})) - len(wire({}))
    assert wrapper_overhead <= 512
    # Every decoded UTF8 byte needs at most six JSON source bytes. Include
    # quotes/commas for all tokens and fixed envelope/ID before comparing caps.
    worst_input = wire({'protocolVersion': 1, 'kind': 'read', 'id': 'r' * 128,
                        'tokens': ['\x01' * 32768, '\x01' * 32768] + [''] * 126})
    assert len(worst_input) <= LIMITS['maxInputFrameBytes']
    for altered in mutations:
        try:
            validate_transcript(altered, output_validator)
        except (AssertionError, ValueError, ValidationError):
            continue
        raise AssertionError('altered output transcript accepted')
    print(f"#0058: {len(vectors['cases'])} authored framing vectors, "
          f"{len(vectors['wireTranscripts'])} complete wire transcripts, "
          f"{len(vectors['transportVectors'])} authored delivery observations, "
          f"{len(mutations)} altered-output refusals; specification model only, no session runtime/media I/O")


if __name__ == '__main__':
    main()
