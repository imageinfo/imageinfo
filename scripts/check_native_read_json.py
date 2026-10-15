"""#0053 finite schema/semantic QA using authored bytes, never private RAW media.

Requires the test-only jsonschema==4.26.0 package, not a product dependency.
"""
import argparse
from copy import deepcopy
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT/'docs/legacy-compatibility/native-read-json'
U64_MAX = (1 << 64) - 1
U32_MAX = (1 << 32) - 1


class Rejected(ValueError):
    pass


def strict_load(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise Rejected('duplicate JSON member')
            result[key] = value
        return result

    def invalid_constant(value):
        raise Rejected('nonfinite JSON number: '+value)

    result = json.loads(text, object_pairs_hook=pairs, parse_constant=invalid_constant)

    def strings(value):
        if isinstance(value, str):
            if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
                raise Rejected('unpaired UTF-16 surrogate')
        elif isinstance(value, dict):
            for key, item in value.items():
                strings(key)
                strings(item)
        elif isinstance(value, list):
            for item in value:
                strings(item)

    strings(result)
    return result


def uint(value, maximum=U64_MAX):
    if type(value) is not str or re.fullmatch(r'0|[1-9][0-9]*', value) is None:
        raise Rejected('canonical unsigned decimal string required')
    if len(value) > len(str(maximum)) or int(value) > maximum:
        raise Rejected('unsigned bound exceeded')
    return int(value)


def semantic(snapshot):
    """Finite NRJ cross-reference/value rules; schema validation runs first."""
    tables = {}
    for name in ('sources', 'documents', 'resources', 'occurrences', 'coverage', 'issues'):
        rows = snapshot[name]
        ids = [row['id'] for row in rows]
        if len(ids) != len(set(ids)):
            raise Rejected('duplicate identity in '+name)
        tables[name] = dict(zip(ids, rows))
    source = snapshot['sources'][0]
    source_length = uint(source['byteLength'])
    if source['identity']['kind'] != 'unavailable' or snapshot['associations'] or snapshot['selections']:
        raise Rejected('bounded read is partial and nonauthoritative')
    for document in snapshot['documents']:
        if document['sourceRef'] not in tables['sources']:
            raise Rejected('unresolved source')
    for resource in snapshot['resources']:
        if resource['sha256'] is not None:
            raise Rejected('bounded read does not compute full resource hashes')
        length = uint(resource['byteLength'])
        spans = resource['content']['ranges']
        if len(spans) != 1:
            raise Rejected('native resource has one source span')
        span = spans[0]
        if span['space'] != 'source' or span['ref'] not in tables['sources']:
            raise Rejected('unresolved native resource source')
        offset, span_length = uint(span['offset']), uint(span['length'])
        if offset + span_length > U64_MAX or offset + span_length > source_length or span_length != length:
            raise Rejected('out-of-bounds or mismatching resource span')
    last_ordinal = -1
    occurrence_keys = set()
    for occurrence in snapshot['occurrences']:
        ordinal = occurrence['ordinal']
        if type(ordinal) is not int or ordinal <= last_ordinal or occurrence['id'] != f'occ-{ordinal}':
            raise Rejected('occurrence ordinal/identity/order mismatch')
        last_ordinal = ordinal
        if occurrence['documentRef'] not in tables['documents']:
            raise Rejected('unresolved occurrence document')
        if occurrence['origin']['resourceRef'] not in tables['resources']:
            raise Rejected('unresolved origin resource')
        tag = occurrence['tag']
        key = (occurrence['documentRef'], tag['namespace'], tag['nativeId'],
               json.dumps(occurrence['path'], sort_keys=True, separators=(',', ':')))
        if key in occurrence_keys:
            raise Rejected('duplicate exact native occurrence key')
        occurrence_keys.add(key)
        if tag['definitionRef'] != f"{snapshot['producer']['readerRevision']}:{tag['namespace']}:{tag['nativeId']}":
            raise Rejected('tag definition revision/key mismatch')
        if occurrence['groups'] != [{'axis': 'metadata-family', 'label': tag['namespace']}]:
            raise Rejected('metadata-family group differs from native namespace')
        for part in occurrence['path']:
            if type(part['index']) is not int or part['index'] < 0:
                raise Rejected('path index required')
        values = occurrence['values']
        raw, normalized = values['raw'], values['normalized']
        rule = values['normalization']
        units = {'ExposureTime': 'seconds', 'FNumber': 'f-number', 'FocalLength': 'mm',
                 'ImageWidth': 'pixels', 'ImageHeight': 'pixels',
                 'PixelXDimension': 'pixels', 'PixelYDimension': 'pixels'}
        if rule['unit'] != units.get(tag['name']):
            raise Rejected('native normalization unit mismatch')
        if (rule['ruleRef'] != 'identity-exact-stored-value' or rule['assumptions']
                or rule['dependencies'] or raw != normalized):
            raise Rejected('native identity normalization changed/lost information')
        refs = occurrence['issueRefs']
        if any(ref not in tables['issues'] for ref in refs):
            raise Rejected('unresolved occurrence issue')
        if raw['state'] == 'invalid':
            if (raw['code'] != 'ZERO_DENOMINATOR' or rule['reversibility'] != 'not-applicable'
                    or values['display'] != {'state': 'unavailable', 'reason': 'Invalid stored rational'}
                    or refs != [f'invalid-{ordinal}']
                    or occurrence['origin']['resourceRef'] != f'value-{ordinal}'):
                raise Rejected('invalid rational state/link contract')
            issue = tables['issues'][refs[0]]
            if issue['code'] != 'ZERO_DENOMINATOR' or issue['occurrenceRefs'] != [occurrence['id']]:
                raise Rejected('invalid rational issue binding')
        elif raw['state'] == 'present':
            if rule['reversibility'] != 'exact' or refs:
                raise Rejected('native valid identity conversion is exact')
            value = raw['value']
            if value['kind'] == 'binary':
                if value['resourceRef'] != occurrence['origin']['resourceRef']:
                    raise Rejected('binary value/origin resource mismatch')
            elif occurrence['origin']['resourceRef'] != f'value-{ordinal}':
                raise Rejected('scalar origin identity mismatch')
            if value['kind'] == 'integer':
                uint(value['decimal'])
            elif value['kind'] == 'rational':
                uint(value['numerator'], U32_MAX)
                if uint(value['denominator'], U32_MAX) == 0:
                    raise Rejected('zero denominator is invalid, never a present rational')
            elif value['kind'] == 'binary' and value['resourceRef'] not in tables['resources']:
                raise Rejected('unresolved binary value resource')
            if values['display']['state'] == 'unavailable' and values['display']['reason'] != 'Not requested':
                raise Rejected('native unrequested display reason mismatch')
        else:
            raise Rejected('unsupported native raw state')
    for coverage in snapshot['coverage']:
        if coverage['state'] != 'partial' or coverage['documentRef'] not in tables['documents']:
            raise Rejected('native coverage is partial and bound')
    for issue in snapshot['issues']:
        if any(ref not in tables['occurrences'] for ref in issue['occurrenceRefs']):
            raise Rejected('unresolved issue occurrence')
        if any(ref not in tables['documents'] for ref in issue['documentRefs']):
            raise Rejected('unresolved issue document')
        occurrence = tables['occurrences'][issue['occurrenceRefs'][0]]
        if (occurrence['values']['raw']['state'] != 'invalid'
                or occurrence['issueRefs'] != [issue['id']]):
            raise Rejected('issue lacks reverse invalid occurrence binding')


def validators():
    metadata = strict_load((ROOT/'docs/metadata-model/metadata-contract.schema.json').read_text(encoding='utf-8'))
    native = strict_load((PACKAGE/'snapshot.schema.v1.json').read_text(encoding='utf-8'))
    result = strict_load((ROOT/'docs/legacy-compatibility/result.schema.json').read_text(encoding='utf-8'))
    registry = Registry().with_resource(metadata['$id'], Resource.from_contents(metadata))
    registry = registry.with_resource(native['$id'], Resource.from_contents(native))
    for schema in (metadata, native, result):
        Draft202012Validator.check_schema(schema)
    return Draft202012Validator(native, registry=registry), Draft202012Validator(result, registry=registry)


def fixture_harness(folder):
    source = folder/'fixture.rs'
    builder = json.dumps((ROOT/'tests/support/mod.rs').as_posix())
    source.write_text(
        f'#[allow(dead_code)] #[path = {builder}] mod support;\n'
        'fn main() { let dir = std::path::PathBuf::from(std::env::args_os().nth(1).unwrap());\n'
        'let normal = support::fixture(); std::fs::write(dir.join("authored.cr3"), &normal.bytes).unwrap();\n'
        'let mut escaped=normal.bytes.clone(); let at=support::field_offset(&escaped,b"CMT3",7);'
        'escaped[at..at+5].copy_from_slice(&[67,34,97,92,110]);'
        'std::fs::write(dir.join("escaping.cr3"),escaped).unwrap();\n'
        'let mut invalid=normal.bytes.clone(); let at=support::field_offset(&invalid,b"CMT2",0x829a);'
        'invalid[at+4..at+8].copy_from_slice(&0u32.to_le_bytes());'
        'std::fs::write(dir.join("invalid.cr3"),invalid).unwrap();\n'
        'let mut endian=normal.bytes.clone(); support::big_endian_tiff_boxes(&mut endian);'
        'std::fs::write(dir.join("endian.cr3"),endian).unwrap();\n'
        'let mut duplicate=normal.bytes; let base=duplicate.windows(4).position(|w|w==b"CMT2").unwrap()+4;'
        'let n=u16::from_le_bytes(duplicate[base+8..base+10].try_into().unwrap()) as usize;'
        'for i in 0..n { let at=base+10+i*12;'
        'if duplicate[at..at+2]==0xa002u16.to_le_bytes() {'
        'duplicate[at..at+2].copy_from_slice(&0x8827u16.to_le_bytes()); }}'
        'std::fs::write(dir.join("duplicates.cr3"),duplicate).unwrap(); }\n',
        encoding='utf-8', newline='\n')
    binary = folder/('fixture.exe' if os.name == 'nt' else 'fixture')
    subprocess.run(['rustc', '--edition=2024', str(source), '-o', str(binary)], cwd=ROOT,
                   check=True, capture_output=True, timeout=45)
    subprocess.run([str(binary), str(folder)], check=True, timeout=10)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--binary', type=Path, default=ROOT/'target/debug'/('imageinfo.exe' if os.name == 'nt' else 'imageinfo'))
    parser.add_argument('--write-examples', action='store_true')
    parser.add_argument('--public', type=Path)
    args = parser.parse_args()
    native, result = validators()
    scratch = ROOT/'.local/native-read-json-qa'
    scratch.mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(dir=scratch)).resolve()
    fixture_harness(folder)
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.glob('*.cr3')}
    cases = [
        ('normal-all', ['--values', 'all', 'authored.cr3'], 0),
        ('raw-mode', ['--values', 'raw', 'authored.cr3'], 0),
        ('normalized-mode', ['--values', 'normalized', 'authored.cr3'], 0),
        ('display-mode', ['--values', 'display', 'authored.cr3'], 0),
        ('ascii-json-escaping', ['--values', 'all', 'escaping.cr3'], 0),
        ('iso-selection', ['--tag', 'ISO', 'authored.cr3'], 0),
        ('empty-selection', ['--tag', 'CTMD:OffsetTimeOriginal', 'authored.cr3'], 0),
        ('invalid-rational', ['--values', 'all', 'invalid.cr3'], 1),
        ('big-endian', ['--values', 'all', 'endian.cr3'], 0),
        ('duplicate-native-tag', ['--values', 'all', '--tag', 'ISO', 'duplicates.cr3'], 0),
    ]
    emitted = {}
    for identifier, options, status in cases:
        process = subprocess.run([str(args.binary.resolve()), 'metadata', 'read', '--output=json', *options],
                                 cwd=folder, capture_output=True, timeout=15)
        assert process.returncode == status, (identifier, process.returncode, process.stderr)
        envelope = strict_load(process.stdout.decode('utf-8'))
        result.validate(envelope)
        snapshot = envelope['files'][0]['snapshot']
        native.validate(snapshot)
        semantic(snapshot)
        emitted[identifier] = snapshot
    assert before == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.glob('*.cr3')}
    assert emitted['empty-selection']['occurrences'] == []
    non_unicode = {'method': 'native Unix filename bytes', 'status': 'not-run-on-Windows'}
    if os.name != 'nt':
        filename = b'authored-\xff.cr3'
        source = (folder/'authored.cr3').read_bytes()
        try:
            target = open(os.fsencode(folder)+b'/'+filename, 'xb')
        except OSError as error:
            if error.errno not in (errno.EINVAL, errno.EILSEQ, errno.ENOTSUP):
                raise
            non_unicode.update(status='not-run-filesystem-rejected-fixture', errno=error.errno)
        else:
            with target:
                target.write(source)
            process = subprocess.run([os.fsencode(args.binary.resolve()), b'metadata', b'read',
                                      b'--output=json', filename], cwd=folder,
                                     capture_output=True, timeout=15)
            assert process.returncode == 0, process.stderr
            envelope = strict_load(process.stdout.decode('utf-8'))
            result.validate(envelope)
            snapshot = envelope['files'][0]['snapshot']
            native.validate(snapshot)
            semantic(snapshot)
            assert any(issue['code'] == 'PATH_DISPLAY_LOSSY' for issue in envelope['files'][0]['issues'])
            assert '\ufffd' in snapshot['sources'][0]['displayPath']
            with open(os.fsencode(folder)+b'/'+filename, 'rb') as target:
                assert target.read() == source
            non_unicode['status'] = 'passed'
    normal = emitted['normal-all']
    exposure = next(o for o in normal['occurrences'] if o['tag']['name'] == 'ExposureTime' and o['tag']['namespace'] == 'exif')
    assert exposure['values']['raw']['value'] == {'kind': 'rational', 'numerator': '2', 'denominator': '500'}
    for mode in ('raw-mode', 'normalized-mode'):
        assert all(o['values']['display'] == {'state': 'unavailable', 'reason': 'Not requested'}
                   for o in emitted[mode]['occurrences'])
    for mode in ('normal-all', 'display-mode'):
        assert all(o['values']['display']['state'] == 'present' for o in emitted[mode]['occurrences'])
    escaped = next(o for o in emitted['ascii-json-escaping']['occurrences'] if o['tag']['name'] == 'CanonFirmwareVersion')
    assert escaped['values']['raw']['value']['text'] == r'C"a\nare Version test'
    duplicates = emitted['duplicate-native-tag']['occurrences']
    assert len(duplicates) == 3 and len({o['id'] for o in duplicates}) == 3
    assert len([o for o in duplicates if o['tag']['namespace'] == 'exif']) == 2
    invalid = next(o for o in emitted['invalid-rational']['occurrences'] if o['tag']['name'] == 'ExposureTime' and o['tag']['namespace'] == 'exif')
    assert invalid['values']['raw']['state'] == 'invalid'
    if args.write_examples:
        for name, value in [('example.v1.json', normal), ('zero-denominator.v1.json', emitted['invalid-rational'])]:
            (PACKAGE/name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
    else:
        for current, name in [(normal, 'example.v1.json'), (emitted['invalid-rational'], 'zero-denominator.v1.json')]:
            published = strict_load((PACKAGE/name).read_text(encoding='utf-8'))
            # Snapshot IDs are explicitly scoped to a parse, and the CLI embeds
            # its per-run request ID. The captured examples remain unmodified.
            assert {k: v for k, v in current.items() if k != 'id'} == {
                k: v for k, v in published.items() if k != 'id'}
    vector_results = check_vectors(native)
    artifact_paths = [Path(__file__), ROOT/'src/reader/wire.rs', ROOT/'tests/support/mod.rs',
                      ROOT/'tests/native_read_json_contract.rs',
                      ROOT/'docs/metadata-model/metadata-contract.schema.json',
                      ROOT/'docs/legacy-compatibility/result.schema.json']
    artifact_paths += [PACKAGE/name for name in ('snapshot.schema.v1.json', 'example.v1.json',
                                                'zero-denominator.v1.json', 'vectors.v1.json')]
    summary = {'ticket': 53, 'kind': 'authored-native-cli-json-qualification',
               'observed': '2026-10-15',
               'actualCliRecords': len(cases), 'vectors': vector_results, 'allPassed': True,
               'actualCases': [{'id': identifier, 'exitStatus': status} for identifier, _, status in cases],
               'authoredFixtureSha256': before, 'privateMediaUsed': False,
               'nonUnicodePath': non_unicode,
               'artifactSha256': {str(path.relative_to(ROOT)).replace('\\', '/'):
                                  hashlib.sha256(path.read_bytes()).hexdigest()
                                  for path in sorted(artifact_paths)},
               'schemaValidationDoesNotAuthorizeMutation': True}
    if args.public:
        args.public.write_text(json.dumps(summary, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps({'actualCliRecords': len(cases), 'vectors': len(vector_results), 'allPassed': True}))


def check_vectors(native):
    package = strict_load((PACKAGE/'vectors.v1.json').read_text(encoding='utf-8'))
    baseline = strict_load((PACKAGE/'example.v1.json').read_text(encoding='utf-8'))
    results = []
    for case in package['cases']:
        if 'wire' in case:
            try:
                strict_load(case['wire'])
            except (Rejected, json.JSONDecodeError):
                valid = False
            else:
                valid = True
            assert valid == case['lexicallyValid'], case['id']
        else:
            changed = deepcopy(baseline)
            for edit in case['changes']:
                target = changed
                for key in edit['path'][:-1]:
                    target = target[key]
                if edit.get('delete'):
                    del target[edit['path'][-1]]
                else:
                    target[edit['path'][-1]] = deepcopy(edit['value'])
            schema_valid = native.is_valid(changed)
            assert schema_valid == case['schemaValid'], case['id']
            try:
                if not schema_valid:
                    raise Rejected('schema invalid')
                semantic(changed)
            except Rejected:
                semantically_valid = False
            else:
                semantically_valid = True
            assert semantically_valid == case['semanticValid'], case['id']
        results.append({'id': case['id'], 'passed': True})
    return results


if __name__ == '__main__':
    main()
