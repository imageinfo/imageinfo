"""#0127 exact finite CLI result profiles; authored inputs only.

Requires the existing test-only jsonschema==4.26.0, never a product dependency.
"""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import tempfile

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from check_native_read_json import Rejected, strict_load, semantic as native_semantic
from check_preview_pair_arguments import inventory
from check_read_arguments import run

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'docs/legacy-compatibility/result-profiles'
OPERATIONS = {'read': 'metadata read', 'list': 'binary list',
              'extract': 'binary extract', 'date-preview': 'preview date-time-original',
              'pair': 'sidecar pair'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validators():
    assert version('jsonschema') == '4.26.0', 'use the pinned QA dependency'
    paths = [ROOT / 'docs/metadata-model/metadata-contract.schema.json',
             ROOT / 'docs/legacy-compatibility/result.schema.json',
             ROOT / 'docs/legacy-compatibility/native-read-json/snapshot.schema.v1.json',
             *sorted(PACKAGE.glob('*.schema.v1.json'))]
    registry = Registry()
    schemas = {}
    for path in paths:
        schema = strict_load(path.read_text(encoding='utf-8'))
        Draft202012Validator.check_schema(schema)
        registry = registry.with_resource(schema['$id'], Resource.from_contents(schema))
        schemas[path.name] = schema
    return {name: Draft202012Validator(schemas[name+'.schema.v1.json'], registry=registry)
            for name in OPERATIONS}


def cases():
    rows = []
    for profile, command in [('read', ['metadata', 'read']), ('list', ['binary', 'list'])]:
        for label, paths, states, status in [
            ('success', ['source.cr3'], ['read'], 0),
            ('refusal', ['opaque.raw'], ['refused'], 1),
            ('partial', ['source.cr3', 'opaque.raw'], ['read', 'refused'], 3),
            ('deduplicated', ['source.cr3', 'source.cr3'], ['read'], 0)]:
            rows.append(dict(id=f'{profile}-{label}', profile=profile,
                             argv=command+paths, inputs=paths, states=states, status=status))
    rows.append(dict(id='read-invalid-value', profile='read', argv=['metadata', 'read', 'invalid.cr3'],
                     inputs=['invalid.cr3'], states=['failed'], status=1))
    for label, source, extra, state, status in [
        ('success', 'source.cr3', [], 'read', 0),
        ('dry-run', 'source.cr3', ['--dry-run'], 'previewed', 0),
        ('refusal', 'opaque.raw', [], 'failed', 1),
        ('occupied', 'source.cr3', [], 'failed', 1)]:
        rows.append(dict(id='extract-'+label, profile='extract', inputs=[source],
                         argv=['binary', 'extract', '--tag=PreviewImage', '--output-file=out.jpg', source]+extra,
                         states=[state], status=status))
    for label, source, extra in [('advisory', 'source.cr3', []),
                                  ('stale', 'source.cr3', ['--offset=0']),
                                  ('missing', 'missing.cr3', [])]:
        rows.append(dict(id='date-preview-'+label, profile='date-preview', inputs=[source],
                         argv=['preview', 'date-time-original', '--value=2000:02:29 23:59:59', source]+extra,
                         states=['refused'], status=1))
    for label, extra, state, status in [('success', ['--sidecar=chosen.xmp'], 'read', 0),
                                       ('omitted', [], 'refused', 1),
                                       ('same-object', ['--sidecar=opaque.raw'], 'refused', 1)]:
        rows.append(dict(id='pair-'+label, profile='pair', inputs=['opaque.raw'],
                         argv=['sidecar', 'pair', 'opaque.raw']+extra, states=[state], status=status))
    return rows


def fixture(folder, captures):
    source = folder / 'fixture.rs'
    support = json.dumps((ROOT / 'tests/support/mod.rs').as_posix())
    source.write_text(f'#[allow(dead_code)] #[path={support}] mod support;\n'
                      'fn main(){let d=std::path::PathBuf::from(std::env::args_os().nth(1).unwrap());'
                      'let j=vec![255,216,255,217];'
                      'let f=support::fixture_with_previews("Firmware Version 2.2.1",j.clone(),j.clone(),j).bytes;'
                      'std::fs::write(d.join("source.cr3"),&f).unwrap();'
                      'let mut invalid=f;let at=support::field_offset(&invalid,b"CMT2",0x829a);'
                      'invalid[at+4..at+8].copy_from_slice(&0u32.to_le_bytes());'
                      'std::fs::write(d.join("invalid.cr3"),invalid).unwrap();}', encoding='utf-8')
    binary = folder / ('fixture.exe' if os.name == 'nt' else 'fixture')
    assert run(['rustc', '--edition=2024', str(source), '-o', str(binary)], ROOT,
               captures / 'fixture-build', 60)[0] == 0
    assert run([str(binary), str(folder)], ROOT, captures / 'fixture-export')[0] == 0


def semantic(value, case, work):
    """Independent ledger/object assertions, never deriving expectations from output."""
    request, summary, files = value['request'], value['summary'], value['files']
    assert request['operation'] == OPERATIONS[case['profile']]
    assert request['mode'] == ('preview' if case['profile'] == 'date-preview' or
                               case['id'] == 'extract-dry-run' else 'read')
    assert summary['exitStatus'] == case['status']
    assert [f['state'] for f in files] == case['states']
    inputs = list(dict.fromkeys(case['inputs']))
    assert [f['path'] for f in files] == inputs
    assert summary['counts'] == dict(discovered=len(inputs), excluded=0,
                                      deduplicated=len(case['inputs'])-len(inputs),
                                      byState=dict(Counter(case['states'])))
    for record in [request, summary, *files]:
        assert record['requestId'] == value['requestId']
    for index, (file, expected) in enumerate(zip(files, inputs)):
        assert file['inputId'] == f'input-{index}'
        if (work / expected).exists():
            assert (work / file['path']).samefile(work / expected)
        for issue in file['issues']:
            assert issue['inputId'] == file['inputId']
            assert issue['path'] is None and issue['occurrenceRef'] is None
        codes = [i['code'] for i in file['issues']]
        assert len(codes) == len(set(codes))
        if case['profile'] in ('read', 'list'):
            expected_codes = (['CAPABILITY_UNSUPPORTED'] if expected == 'opaque.raw' else
                              ['INVALID_VALUE', 'COVERAGE_PARTIAL'] if expected == 'invalid.cr3' else
                              ['COVERAGE_PARTIAL'])
        else:
            expected_codes = {
                'extract-success': [], 'extract-dry-run': [],
                'extract-refusal': ['CAPABILITY_UNSUPPORTED'],
                'extract-occupied': ['DESTINATION_EXISTS'],
                'date-preview-advisory': ['OPAQUE_DEPENDENCY_UNPROVEN'],
                'date-preview-stale': ['OCCURRENCE_CHANGED', 'OPAQUE_DEPENDENCY_UNPROVEN'],
                'date-preview-missing': ['INPUT_IO'], 'pair-success': [],
                'pair-omitted': ['EXPLICIT_SIDECAR_REQUIRED'],
                'pair-same-object': ['PAIRING_SAME_FILE']}[case['id']]
        assert codes == expected_codes
        assert all(i['severity'] == ('warning' if i['code'] == 'COVERAGE_PARTIAL' else 'error')
                   for i in file['issues'])
        errors = [i for i in file['issues'] if i['severity'] == 'error']
        assert bool(errors) == (file['state'] in ('refused', 'failed'))
        snapshot = file['snapshot']
        expected_snapshot = ((case['profile'] in ('read', 'list') and expected != 'opaque.raw') or
                             case['id'] in ('date-preview-advisory', 'date-preview-stale', 'pair-success'))
        assert (snapshot is not None) == expected_snapshot
        if case['profile'] in ('read', 'list') and snapshot is not None:
            native_semantic(snapshot)
            assert snapshot['id'] == value['requestId']+f'-snapshot-{index}'
            assert snapshot['sources'][0]['displayPath'] == expected
            assert int(snapshot['sources'][0]['byteLength']) == (work / expected).stat().st_size
            assert 'COVERAGE_PARTIAL' in codes
            if case['profile'] == 'list':
                assert all(o['values']['raw']['value']['kind'] == 'binary' for o in snapshot['occurrences'])
            if case['id'] == 'read-invalid-value':
                assert 'INVALID_VALUE' in codes
                assert any(o['values']['raw']['state'] == 'invalid' for o in snapshot['occurrences'])
        elif case['profile'] == 'date-preview' and snapshot is not None:
            preview = snapshot['preview']
            assert [r['code'] for r in preview['refusals']] == codes
            assert preview['status'] == file['state']
            data = (work / expected).read_bytes()
            assert preview['source_length'] == len(data)
            assert preview['proposed_bytes'] == list(b'2000:02:29 23:59:59\0')
            if case['id'].endswith('advisory'):
                needle = b'2026:01:02 03:04:05\0'
                assert data.count(needle) == 1
                offset = data.index(needle)
                assert preview['allocation'] == dict(offset=offset, length=20)
                assert preview['original_bytes'] == list(needle)
                assert preview['field_shape_verified'] and preview['expected_occurrence_matches']
                candidate = data[:offset]+bytes(preview['proposed_bytes'])+data[offset+20:]
                seen = [0]*len(data)
                for key, changed in [('changed_ranges', True), ('preserved_ranges', False)]:
                    for span in preview[key]:
                        assert span['length'] > 0
                        assert 0 <= span['offset'] < span['offset']+span['length'] <= len(data)
                        for at in range(span['offset'], span['offset']+span['length']):
                            assert (data[at] != candidate[at]) == changed
                            seen[at] += 1
                assert all(n == 1 for n in seen)
                assert preview['changed_bytes'] == sum(a != b for a, b in zip(data, candidate))
                assert preview['preserved_bytes'] == len(data)-preview['changed_bytes']
                assert not preview['value_already_matches']
            else:
                assert not preview['expected_occurrence_matches']
                assert preview['original_bytes'] is None
                assert preview['changed_ranges'] == preview['preserved_ranges'] == []
                assert 'OCCURRENCE_CHANGED' in codes
        elif case['profile'] == 'pair' and snapshot is not None:
            pair = snapshot['pair']
            assert Path(pair['raw_path']).samefile(work / 'opaque.raw')
            assert Path(pair['sidecar_path']).samefile(work / 'chosen.xmp')
            assert not Path(pair['raw_path']).samefile(Path(pair['sidecar_path']))
    artifacts = summary['artifacts']
    if case['id'] == 'extract-success':
        assert artifacts == [dict(kind='extraction', path='out.jpg', retainedPath=None,
                                  state='committed', transactionId=None, recoveryIds=[])]
        assert (work / artifacts[0]['path']).read_bytes() == bytes([255,216,255,217])
    else:
        assert artifacts == []


def negative_vectors(value, case, validator, work):
    """Each mutation has exactly one declared validation layer."""
    mutations = [('unknown-member', 'schema', ['unexpected'], True),
                 ('wrong-type-mode', 'schema', ['request', 'mode'], False),
                 ('wrong-type-discovered', 'schema', ['summary', 'counts', 'discovered'], '1'),
                 ('wrong-type-files', 'schema', ['files'], {}),
                 ('wrong-operation', 'schema', ['request', 'operation'], 'metadata apply'),
                 ('transaction-authority', 'schema', ['files', 0, 'transactionId'], 'txn-forged'),
                 ('count-mismatch', 'semantic', ['summary', 'counts', 'byState'], {}),
                 ('request-mismatch', 'semantic', ['files', 0, 'requestId'], 'wrong-id'),
                 ('wrong-input-label', 'semantic', ['files', 0, 'path'], 'chosen.xmp'),
                 ('wrong-exit-status', 'semantic', ['summary', 'exitStatus'], 0 if case['status'] else 1),
                 ('mutation-effect', 'schema', ['files', 0, 'effects', 'changed'], True)]
    if value['files'][0]['issues']:
        mutations.append(('wrong-issue-code', 'semantic', ['files', 0, 'issues', 0, 'code'], 'FORGED_ERROR'))
    if value['files'][0]['snapshot']:
        mutations.append(('missing-observation', 'semantic', ['files', 0, 'snapshot'], None))
    profile = case['profile']
    if profile in ('read', 'list') and value['files'][0]['snapshot']:
        mutations.append(('complete-coverage', 'schema', ['files', 0, 'snapshot', 'coverage', 0, 'state'], 'complete'))
    if profile == 'date-preview' and value['files'][0]['snapshot']:
        mutations.append(('mutation-authority', 'schema', ['files', 0, 'snapshot', 'preview', 'production_mutation_allowed'], True))
        if case['id'] == 'date-preview-advisory':
            mutations.append(('wrong-difference-count', 'semantic', ['files', 0, 'snapshot', 'preview', 'changed_bytes'], 0))
    if profile == 'pair' and value['files'][0]['snapshot']:
        mutations.append(('wrong-sidecar-object', 'semantic', ['files', 0, 'snapshot', 'pair', 'sidecar_path'], str(work / 'opaque.raw')))
    if case['id'] == 'extract-success':
        mutations.append(('wrong-artifact-label', 'semantic', ['summary', 'artifacts', 0, 'path'], 'chosen.xmp'))
    accepted = []
    for name, layer, path, replacement in mutations:
        changed = deepcopy(value)
        at = changed
        for part in path[:-1]:
            at = at[part]
        at[path[-1]] = replacement
        if layer == 'schema':
            assert not validator.is_valid(changed), name
        else:
            validator.validate(changed)
            try:
                semantic(changed, case, work)
            except (AssertionError, KeyError, ValueError):
                pass
            else:
                raise AssertionError('negative semantic vector accepted: '+name)
        public_replacement = replacement.replace(str(work), '{work}') if isinstance(replacement, str) else replacement
        accepted.append(dict(case=case['id'], name=name, layer=layer, path=path,
                             replacement=public_replacement, rejected=True))
    return accepted


def public_example(value, work):
    # Preserve parsed actual values, substituting only volatile locator prefixes.
    text = json.dumps(value).replace(json.dumps(str(work))[1:-1], '{work}')
    return json.loads(text)


def without_request_id(value):
    identity = value['envelope']['requestId']
    return json.loads(json.dumps(value).replace(identity, '{requestId}'))


def lexical_vectors():
    rows = [('duplicate-member', '{"x":1,"x":2}'),
            ('nonfinite', '{"x":NaN}'), ('trailing-document', '{} {}'),
            ('unpaired-surrogate', '{"x":"\\ud800"}')]
    for name, text in rows:
        try:
            strict_load(text)
        except (Rejected, ValueError):
            pass
        else:
            raise AssertionError('lexical negative accepted: '+name)
    return [dict(case='all-profiles', name=name, layer='lexical', input=text, rejected=True)
            for name, text in rows]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path,
                        default=ROOT / 'target/debug' / ('imageinfo.exe' if os.name == 'nt' else 'imageinfo'))
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--refresh', action='store_true',
                      help='replace the public frozen authored evidence')
    mode.add_argument('--check-current', action='store_true',
                      help='validate current execution without comparing frozen platform examples')
    args = parser.parse_args()
    binary = args.binary.resolve(strict=True)
    checks = validators()
    scratch = ROOT / '.local/work-wave-20261017a'
    scratch.mkdir(exist_ok=True, parents=True)
    folder = Path(tempfile.mkdtemp(prefix='127-run-', dir=scratch)).resolve()
    captures = folder / 'captures'
    captures.mkdir()
    fixture(folder, captures)
    results, examples, vectors = [], [], lexical_vectors()
    for case in cases():
        work = folder / case['id']
        work.mkdir()
        for name in ('source.cr3', 'invalid.cr3'):
            (work / name).write_bytes((folder / name).read_bytes())
        (work / 'opaque.raw').write_bytes(b'\x00\x00\x00\x08free')
        (work / 'chosen.xmp').write_bytes(b'\xff\x00authored non-XML marker')
        if case['id'] == 'extract-occupied':
            (work / 'out.jpg').write_bytes(b'preserve occupied authored target')
        before = inventory(work)
        status, stdout, stderr = run([str(binary), '--output=json', *case['argv']], work, captures / case['id'])
        assert status == case['status'], case['id']
        assert stdout.endswith(b'\n') and not stdout.endswith(b'\n\n')
        assert b'\x1b' not in stdout+stderr
        value = strict_load(stdout.decode('utf-8', errors='strict'))
        checks[case['profile']].validate(value)
        semantic(value, case, work)
        after = inventory(work)
        if case['id'] == 'extract-success':
            assert set(after)-set(before) == {'out.jpg'}
            del after['out.jpg']
        assert after == before, case['id']+' source/name/property effect'
        vectors.extend(negative_vectors(value, case, checks[case['profile']], work))
        examples.append(dict(case=case, envelope=public_example(value, work)))
        results.append(dict(id=case['id'], exitStatus=status, stdoutBytes=len(stdout),
                            stderrBytes=len(stderr), sourceEffects='unchanged',
                            inputSha256={name: sha(work / name) for name in dict.fromkeys(case['inputs'])
                                         if (work / name).exists()},
                            output='exact authored preview copy' if case['id']=='extract-success' else 'none', passed=True))
    source_paths = ['src/main.rs', 'src/lib.rs', 'src/app.rs', 'src/output.rs', 'src/cli.rs', 'src/read_request.rs',
                    'src/preview.rs', 'src/pairing.rs', 'tests/support/mod.rs', 'Cargo.toml', 'Cargo.lock',
                    'scripts/check_result_profiles.py', 'scripts/check_read_arguments.py',
                    'scripts/check_preview_pair_arguments.py', 'scripts/check_native_read_json.py']
    source_paths += [p.relative_to(ROOT).as_posix() for p in sorted((ROOT / 'src/reader').rglob('*.rs'))]
    source_paths += [p.relative_to(ROOT).as_posix() for p in sorted(PACKAGE.glob('*.schema.v1.json'))]
    source_paths += ['docs/legacy-compatibility/result.schema.json',
                     'docs/legacy-compatibility/native-read-json/snapshot.schema.v1.json',
                     'docs/metadata-model/metadata-contract.schema.json']
    report = dict(schemaVersion=1, ticket=127, platform=os.name, binarySha256=sha(binary),
                  sourceSha256={p: sha(ROOT / p) for p in source_paths}, cases=results,
                  negativeVectors=len(vectors), limits='finite authored current profiles; no importer or mutation authority')
    (folder / 'results.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    if args.refresh:
        for name, data in [('qualification.v1.json', report), ('examples.v1.json', examples), ('vectors.v1.json', vectors)]:
            (PACKAGE / name).write_text(json.dumps(data, indent=2)+'\n', encoding='utf-8', newline='\n')
    elif not args.check_current:
        saved = strict_load((PACKAGE / 'examples.v1.json').read_text(encoding='utf-8'))
        assert [without_request_id(v) for v in examples] == [without_request_id(v) for v in saved]
        assert vectors == strict_load((PACKAGE / 'vectors.v1.json').read_text(encoding='utf-8'))
    print(json.dumps(dict(cases=len(results), negativeVectors=len(vectors), retained=str(folder))))


if __name__ == '__main__':
    main()
