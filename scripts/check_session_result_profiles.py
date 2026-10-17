"""#0128 actual process frames and separately labeled caller-owned trait faults.

Test-only jsonschema dependency; no camera media or producer changes.
"""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch

from jsonschema import Draft202012Validator, ValidationError
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'docs/legacy-compatibility/session-result-profiles'
LIMITS = dict(maxInputFrameBytes=524288, maxOutputFrameBytes=16777728,
              maxFrames=256, maxQueuedRequests=0, maxTokens=128,
              maxTokenBytes=32768, maxTotalTokenBytes=65536, maxInputs=4,
              maxMetadataBytes=8388608, maxResultBytes=16777216)


class Rejected(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise Rejected(message)


def wire(value):
    return (json.dumps(value, separators=(',', ':'), ensure_ascii=False) + '\n').encode()


def unique_members(items):
    out = {}
    for key, value in items:
        require(key not in out, 'duplicate member')
        out[key] = value
    return out


def finite_number(_):
    raise Rejected('nonfinite number')


def scalar_text(item):
    if isinstance(item, str):
        require(not any(0xd800 <= ord(c) <= 0xdfff for c in item), 'surrogate')
    elif isinstance(item, dict):
        for key, child in item.items():
            scalar_text(key)
            scalar_text(child)
    elif isinstance(item, list):
        for child in item:
            scalar_text(child)


def utf8_text(data):
    text = data.decode('utf-8')
    require(not text.startswith('\ufeff'), 'BOM')
    return text


def strict_json(data):
    value = json.loads(utf8_text(data), object_pairs_hook=unique_members, parse_constant=finite_number)
    scalar_text(value)
    return value


def validator():
    registry = Registry()
    for path in (ROOT/'docs/metadata-model/metadata-contract.schema.json',
                 ROOT/'docs/legacy-compatibility/result.schema.json', PACKAGE/'schema.v1.json'):
        schema = json.loads(path.read_text(encoding='utf-8'))
        Draft202012Validator.check_schema(schema)
        registry = registry.with_resource(schema['$id'], Resource.from_contents(schema))
    return Draft202012Validator(schema, registry=registry)


def integer(value, lo=0, hi=256):
    require(type(value) is int and lo <= value <= hi, 'integer type/bound')


def result_semantics(frame):
    """Independent current native envelope oracle, not producer helper calls."""
    result = frame['result']
    rid = frame['id']
    require(all(record['requestId'] == rid for record in
                [result, result['request'], result['summary'], *result['files']]), 'inner ID mismatch')
    for record in [result, result['request'], result['summary'], *result['files']]:
        integer(record['schemaVersion'], 1, 1)
    summary, request, files = result['summary'], result['request'], result['files']
    integer(summary['exitStatus'], 0, 3)
    counts = summary['counts']
    for value in [counts['discovered'], counts['excluded'], counts['deduplicated'], *counts['byState'].values()]:
        integer(value, 0, 4)
    require(counts['discovered'] == len(files) and counts['excluded'] == 0, 'file counts')
    require(counts['discovered'] + counts['deduplicated'] <= 4, 'input budget')
    require(counts['byState'] == dict(Counter(file['state'] for file in files)), 'state counts')
    require(summary['outputComplete'] is True and summary['interrupted'] is False,
            'inner completion flags')
    require(summary['artifacts'] == [] and summary['issues'] == [], 'unexpected summary effects')
    if files:
        require(request['operation'] == 'metadata read' and request['mode'] == 'read', 'operation')
        require(request['issues'] == [] and summary['selectionComplete'] is True, 'selected result')
        successes = sum(file['state'] == 'read' for file in files)
        expected = 0 if successes == len(files) else 3 if successes else 1
        require(summary['exitStatus'] == expected, 'native status precedence')
    else:
        require(summary['selectionComplete'] is False and counts['deduplicated'] == 0,
                'refusal selection')
        require(bool(request['issues']) and summary['exitStatus'] in (1, 2), 'request refusal')
        require((request['operation'], request['mode']) in ((None, None), ('metadata read', 'read')), 'refusal mode')
    for index, file in enumerate(files):
        require(file['inputId'] == f'input-{index}', 'input identity')
        require(file['effects'] == dict(publicationMayHaveOccurred=False, changed=False,
                cleanupPending=False, recoveryIds=[], notes=[]) and file['transactionId'] is None,
                'mutation effects')
        require(file['state'] != 'read' or file['snapshot'] is not None, 'read snapshot missing')
        if file['snapshot'] is not None:
            require(file['snapshot']['id'] == f'{rid}-snapshot-{index}', 'snapshot identity')
            require(len(file['snapshot']['sources']) == 1 and
                    file['snapshot']['sources'][0]['displayPath'] == file['path'], 'snapshot source path')
        for issue in file['issues']:
            require(issue['inputId'] == file['inputId'] and issue['path'] is None and
                    issue['occurrenceRef'] is None, 'file issue binding')
            require(issue['severity'] == ('warning' if issue['code'] in
                    ('COVERAGE_PARTIAL', 'TAG_UNRESOLVED', 'PATH_DISPLAY_LOSSY') else 'error'), 'file issue severity')
        require((file['state'] == 'read') == all(issue['severity'] != 'error' for issue in file['issues']), 'file issue/state')


def expected_result(frame, expected):
    """Bind finite authored request intent, not merely self-consistent output."""
    envelope = frame['result']
    files, request, summary = envelope['files'], envelope['request'], envelope['summary']
    require(summary['exitStatus'] == expected['status'], 'authored request status')
    require(summary['counts']['deduplicated'] == 0, 'authored input deduplication')
    require([(f['path'], f['state']) for f in files] == expected['files'], 'authored input paths/outcomes')
    if not expected['files']:
        require(request['operation'] is None and request['mode'] is None and
                [(i['code'], i['severity'], i['inputId'], i['path'], i['occurrenceRef']) for i in request['issues']] ==
                [('REQUEST_OPERATION_UNSUPPORTED', 'error', None, None, None)], 'authored empty-token refusal')
        return
    for file, (_, state) in zip(files, expected['files']):
        require([(i['code'], i['severity']) for i in file['issues']] ==
                ([('COVERAGE_PARTIAL', 'warning')] if state == 'read' else [('INPUT_IO', 'error')]), 'authored issues')
        if state != 'read':
            require(file['snapshot'] is None, 'authored failed snapshot')
            continue
        snapshot = file['snapshot']
        require(snapshot['sources'][0]['byteLength'] == str(expected['sourceBytes']), 'authored source length')
        # Independent fixture intent: CMT2 ISO and CTMD ISO are authored as 800.
        observations = snapshot['occurrences']
        require([(o['id'], o['ordinal'], o['tag']['namespace'], o['tag']['nativeId'], o['tag']['name']) for o in observations] ==
                [('occ-6', 6, 'exif', '34855', 'ISO'), ('occ-22', 22, 'canon:ctmd', '5/8', 'ISO')], 'authored ISO selection')
        for observation in observations:
            values = observation['values']
            require(values['raw'] == values['normalized'] ==
                    dict(state='present', value=dict(decimal='800', kind='integer')), 'authored ISO values')
            require(values['display'] == dict(state='unavailable', reason='Not requested'), 'authored default view')


def canonical_lf(data):
    require(data.endswith(b'\n'), 'missing final LF')
    require(b'\r' not in data, 'output must use LF')


def decode_frames(data, check):
    canonical_lf(data)
    frames = []
    for line in data.splitlines(keepends=True):
        require(len(line) <= LIMITS['maxOutputFrameBytes'], 'outer frame limit')
        value = strict_json(line)
        check.validate(value)
        integer(value['protocolVersion'], 1, 1)
        if value['kind'] == 'read-result':
            result_semantics(value)
        if value['kind'] == 'session-ready':
            require(value['limits'] == LIMITS and value['allowApply'] is False, 'ready limits')
            for number in value['limits'].values():
                integer(number, 0, 16777728)
        if value['kind'] == 'session-complete':
            for field in ('frames', 'results', 'exitStatus'):
                integer(value[field])
        frames.append(value)
    return frames


def transcript(data, check, *, ids, reason, attempts, status, close_id=None, code=None, expected=None):
    """Expected IDs/attempts/status come from authored input intent, not output."""
    frames = decode_frames(data, check)
    kinds = ['session-ready'] + ['read-result'] * len(ids)
    if code:
        kinds.append('protocol-error')
    kinds.append('session-complete')
    require([f['kind'] for f in frames] == kinds, 'frame order/completeness')
    require([f['id'] for f in frames if f['kind'] == 'read-result'] == ids, 'request ID sequence')
    require(len(ids) == len(set(ids)), 'duplicate result ID')
    if expected is not None:
        require(set(expected) == set(ids), 'complete authored expectations required')
        for frame in frames[1:1+len(ids)]:
            expected_result(frame, expected[frame['id']])
    if code:
        require(frames[-2]['code'] == code and frames[-2]['id'] is None, 'error code/id')
    require(frames[-1] == dict(protocolVersion=1, kind='session-complete', reason=reason,
            frames=attempts, results=len(ids), exitStatus=status, closeId=close_id), 'completion contradiction')
    if close_id:
        require(close_id not in ids, 'reused close ID')
    return frames


def request(rid, tokens):
    return wire(dict(protocolVersion=1, kind='read', id=rid, tokens=tokens))


def rejected(call):
    try:
        call()
    except (Rejected, ValidationError, ValueError, UnicodeError, TypeError, KeyError):
        return
    raise AssertionError('negative vector unexpectedly accepted')


def lexical_negatives(baseline, check, specs):
    """Each detector's removal must admit its otherwise valid actual control.

    NaN is tested at the strict JSON layer: no current closed numeric field can
    contain NaN and remain schema-valid. No schema rejection counts for it.
    """
    ready = wire(baseline[0])
    issue = deepcopy(baseline[3])  # actual empty-token refusal; message is free text
    issue['result']['request']['issues'][0]['message'] = 'lexical-control'
    control = wire(issue)
    decode_frames(ready, check)
    decode_frames(control, check)
    for spec in specs:
        name = spec['name']
        if name == 'duplicate':
            data = ready.replace(b'"protocolVersion":1', b'"protocolVersion":1,"protocolVersion":1')
            target, bypass = 'unique_members', dict
        elif name == 'surrogate':
            data = control.replace(b'lexical-control', b'\\ud800')
            target, bypass = 'scalar_text', lambda _: None
        elif name == 'crlf':
            data = ready[:-1] + b'\r\n'
            target, bypass = 'canonical_lf', lambda _: None
        elif name == 'no-lf':
            data = ready[:-1]
            target, bypass = 'canonical_lf', lambda _: None
        elif name == 'bom':
            data = b'\xef\xbb\xbf' + ready
            target, bypass = 'utf8_text', lambda b: b.decode('utf-8-sig')
        elif name == 'bad-utf8':
            data = control.replace(b'lexical-control', b'\xff')
            target, bypass = 'utf8_text', lambda b: b.decode('utf-8', errors='replace')
        elif name == 'nan':
            data = ready.replace(b'"protocolVersion":1', b'"protocolVersion":NaN')
            try:
                strict_json(data)
            except Rejected as error:
                require(str(error) == 'nonfinite number', 'wrong NaN rejection layer')
            else:
                raise AssertionError('NaN strict detector absent')
            with patch.dict(globals(), finite_number=float):
                require(math.isnan(strict_json(data)['protocolVersion']), 'NaN detector sensitivity')
            continue
        else:
            raise AssertionError('unknown lexical control')
        rejected(lambda: decode_frames(data, check))
        with patch.dict(globals(), {target: bypass}):
            # Schema and all remaining strict/semantic checks must still pass.
            decode_frames(data, check)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--binary', type=Path, default=ROOT/'target/debug'/('imageinfo.exe' if os.name == 'nt' else 'imageinfo'))
    parser.add_argument('--library', type=Path)
    parser.add_argument('--public', type=Path, help='Write sanitized source/binary-bound evidence')
    parser.add_argument('--write-examples', action='store_true')
    args = parser.parse_args()
    binary = args.binary.resolve()
    library = (args.library or binary.parent/'libimageinfo.rlib').resolve()
    check = validator()
    evidence = []
    with tempfile.TemporaryDirectory(prefix='imageinfo-session-schema-') as tmp:
        folder = Path(tmp)
        # Reuse only authored fixture construction, never its result oracle.
        from check_native_read_json import fixture_harness
        fixture_harness(folder)
        raw, missing = folder/'authored.cr3', folder/'missing.cr3'
        before = {p.name: p.read_bytes() for p in folder.glob('*.cr3')}
        read = lambda rid, paths: request(rid, ['metadata', 'read', '--tag', 'ISO', '--', *map(str, paths)])
        close = wire(dict(protocolVersion=1, kind='close', id='done'))
        authored = {
            'good': dict(files=[(str(raw), 'read')], status=0, sourceBytes=raw.stat().st_size),
            'bad': dict(files=[(str(missing), 'failed')], status=1),
            'mixed': dict(files=[(str(raw), 'read'), (str(missing), 'failed')], status=3, sourceBytes=raw.stat().st_size),
            'one': dict(files=[(str(raw), 'read')], status=0, sourceBytes=raw.stat().st_size),
        }
        def intent(ids):
            return {rid: authored.get(rid, dict(files=[], status=2)) for rid in ids}
        cases = [
            ('eof-empty', b'', [], 'eof', 0, 0, None, None),
            ('close-empty', close + request('never', []), [], 'close', 1, 0, 'done', None),
            ('read-statuses-close', read('good', [raw]) + read('bad', [missing]) + request('usage', []) + read('mixed', [raw, missing]) + close,
             ['good', 'bad', 'usage', 'mixed'], 'close', 5, 0, 'done', None),
            ('read-eof', read('one', [raw]), ['one'], 'eof', 1, 0, None, None),
            ('limit', b''.join(request(f'r{i}', []) for i in range(257)), [f'r{i}' for i in range(256)], 'limit', 256, 0, None, None),
            ('invalid-json', b'{\n' + close, [], 'protocol-error', 1, 2, None, 'FRAME_JSON'),
            ('truncated', b'{', [], 'protocol-error', 1, 2, None, 'FRAME_TRUNCATED'),
            ('encoding', b'\xff\n', [], 'protocol-error', 1, 2, None, 'FRAME_ENCODING'),
            ('schema', wire(dict(protocolVersion=1, kind='apply', id='x')), [], 'protocol-error', 1, 2, None, 'FRAME_SCHEMA'),
            ('oversized', b' '*524288, [], 'protocol-error', 1, 2, None, 'FRAME_TOO_LARGE'),
            ('duplicate-id', request('same', []) + request('same', []), ['same'], 'protocol-error', 2, 2, None, 'DUPLICATE_ID'),
            ('close-at-limit', b''.join(request(f'r{i}', []) for i in range(255)) + close + request('never', []),
             [f'r{i}' for i in range(255)], 'close', 256, 0, 'done', None),
            ('error-at-limit', b''.join(request(f'r{i}', []) for i in range(255)) + b'{\n' + close,
             [f'r{i}' for i in range(255)], 'protocol-error', 256, 2, None, 'FRAME_JSON'),
            ('reused-close-id', request('done', []) + close, ['done'], 'protocol-error', 2, 2, None, 'DUPLICATE_ID'),
        ]
        captured = {}
        for name, data, ids, reason, attempts, status, cid, code in cases:
            proc = subprocess.run([str(binary), 'session', 'read'], input=data, capture_output=True, cwd=folder, timeout=20)
            require(proc.returncode == status and not proc.stderr, 'process exit/stderr mismatch')
            frames = transcript(proc.stdout, check, ids=ids, reason=reason, attempts=attempts, status=proc.returncode, close_id=cid, code=code, expected=intent(ids))
            captured[name] = frames
            evidence.append(dict(name=name, category='actual-process', frames=len(frames), attempts=attempts, results=len(ids), exitStatus=status))
        require([f['result']['summary']['exitStatus'] for f in captured['read-statuses-close'][1:-1]] == [0, 1, 2, 3], 'request statuses')
        require(before == {p.name:p.read_bytes() for p in folder.glob('*.cr3')} and not missing.exists(), 'source effects')
        harness = folder/('traits.exe' if os.name == 'nt' else 'traits')
        deps = library.parent if library.parent.name == 'deps' else library.parent/'deps'
        subprocess.run(['rustc', '--edition=2024', str(PACKAGE/'trait-harness.rs'), '--extern', f'imageinfo={library}', '-L', f'dependency={deps}', '-o', str(harness)], check=True, capture_output=True, timeout=45)
        for mode, attempts, results, visible in [('flush-1',0,0,1), ('flush-2',1,0,2), ('flush-3',1,1,3), ('write-broken',0,0,0), ('write-zero',0,0,0), ('input-empty',0,0,3), ('input-partial',1,0,3), ('short-write',1,1,3)]:
            output = folder/'trait.jsonl'
            proc = subprocess.run([str(harness),mode,str(output)], check=True, capture_output=True, timeout=10)
            report = strict_json(proc.stdout)
            require(report['frames'] == attempts and report['results'] == results, 'trait counts')
            data = output.read_bytes()
            if mode.startswith('flush-'):
                frames = decode_frames(data, check)
                for frame in frames:
                    if frame['kind'] == 'read-result':
                        expected_result(frame, dict(files=[], status=2))
                require(len(frames) == visible and report['outcome'] == 'output-incomplete' and report['exitStatus'] == 1, 'trait flush semantics')
                require(report['consumed'] == (0 if mode == 'flush-1' else len(request('r1', []))), 'post-failure input')
                # Even a visible completion whose flush failed is not delivered.
                require(report['errorKind'] == 'BrokenPipe', 'flush error kind')
            elif mode.startswith('write-'):
                require(report['outcome'] == 'output-incomplete' and report['consumed'] == 0 and report['exitStatus'] == 1, 'trait write semantics')
                require(report['errorKind'] == ('WriteZero' if mode == 'write-zero' else 'BrokenPipe'), 'write error kind')
                rejected(lambda: decode_frames(data, check))
            else:
                trait_ids = [] if mode.startswith('input-') else ['r1']
                transcript(data, check, ids=trait_ids, reason='input-error' if mode.startswith('input-') else 'eof', attempts=attempts, status=1 if mode.startswith('input-') else 0, code='INPUT_IO' if mode.startswith('input-') else None, expected=intent(trait_ids))
                require(report['outcome'] == 'complete', 'trait completion')
            evidence.append(dict(name=mode, category='actual-caller-owned-traits', **report))
        baseline = captured['read-statuses-close']
        vector_spec = json.loads((PACKAGE/'negative-vectors.v1.json').read_text())
        for vector in vector_spec['mutations']:
            frames = deepcopy(baseline)
            for edit in vector.get('edits', [vector]):
                cursor = frames
                for key in edit['path'][:-1]:
                    cursor = cursor[key]
                cursor[edit['path'][-1]] = edit['value']
            rejected(lambda: transcript(b''.join(map(wire, frames)), check, ids=['good','bad','usage','mixed'], reason='close', attempts=5, status=0, close_id='done', expected=intent(['good','bad','usage','mixed'])))
        lexical_negatives(baseline, check, vector_spec['lexicalControls'])
        for vector in vector_spec['malformed']:
            rejected(lambda: decode_frames(bytes.fromhex(vector['hex']), check))
        for vector in vector_spec['errorMutations']:
            frames = deepcopy(captured['invalid-json'])
            cursor = frames
            for key in vector['path'][:-1]:
                cursor = cursor[key]
            cursor[vector['path'][-1]] = vector['value']
            rejected(lambda: transcript(b''.join(map(wire, frames)), check, ids=[], reason='protocol-error', attempts=1, status=2, code='FRAME_JSON'))
        for name, value in [('missing-completion', baseline[:-1]), ('duplicate-ready', [baseline[0],*baseline]), ('result-after-completion', [*baseline,baseline[1]]), ('missing-result', baseline[:1]+baseline[2:])]:
            rejected(lambda: transcript(b''.join(map(wire, value)), check, ids=['good','bad','usage','mixed'], reason='close', attempts=5, status=0, close_id='done'))
        for bad_status in (1, 2):
            rejected(lambda: transcript(b''.join(map(wire, baseline)), check, ids=['good','bad','usage','mixed'], reason='close', attempts=5, status=bad_status, close_id='done'))
        if args.write_examples:
            # Only authored, path-independent control frames are published.
            for name in ('eof-empty', 'close-empty', 'invalid-json', 'duplicate-id'):
                (PACKAGE/(name+'.example.json')).write_text(json.dumps(captured[name], indent=2)+'\n', encoding='utf-8', newline='\n')
    count = len(vector_spec['mutations']) + len(vector_spec['malformed']) + len(vector_spec['lexicalControls']) + len(vector_spec['errorMutations']) + 6
    bound_sources = sorted((ROOT/'src').rglob('*.rs')) + sorted((ROOT/'crates').rglob('*.rs'))
    bound_sources += sorted((ROOT/'tests/support').rglob('*.rs'))
    bound_sources += [ROOT/name for name in ('Cargo.toml', 'Cargo.lock', 'rust-toolchain.toml')]
    bound_sources += [Path(__file__).resolve(), PACKAGE/'schema.v1.json', PACKAGE/'negative-vectors.v1.json', PACKAGE/'trait-harness.rs', ROOT/'docs/metadata-model/metadata-contract.schema.json', ROOT/'docs/legacy-compatibility/result.schema.json', ROOT/'scripts/check_native_read_json.py']
    report = dict(ticket=128, scope='authored actual session-v1 results only', observations=evidence, negativeVectors=count, lexicalDetectorSensitivityChecks=len(vector_spec['lexicalControls']),
                  sourceSha256={str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in bound_sources},
                  binarySha256=hashlib.sha256(binary.read_bytes()).hexdigest(), librarySha256=hashlib.sha256(library.read_bytes()).hexdigest(),
                  limits=['Trait failures are not native failing-input or flush-only OS-pipe evidence.', 'Inner outputComplete never proves outer delivery.', 'No queue/cancellation/apply, performance policy, storage or RAW admission.'])
    if args.public:
        args.public.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(f'{len(cases)} actual process sessions; 8 separately labeled trait cases; {count} negative vectors passed')


if __name__ == '__main__':
    main()
