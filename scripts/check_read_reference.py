"""#0122: bounded authored read selection/view observations, not parity.

Requires the already retained lawful reference/runtime manifests; acquires nothing.
Each tool opens an independently bound absolute authored path. Captures stay private.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / 'docs/legacy-compatibility/read-reference.cases.json'
# Authored expectations are explicit input, never learned from observed reports.
CONTRACTS = json.loads(LEDGER.read_bytes())['nativeOccurrenceContracts']
CAP = 1024 * 1024
REV = '2200871d9cef988051d2a99d67df3bda6cbb30a8'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def strict(data):
    def pairs(items):
        result = {}
        for key, value in items:
            assert key not in result, 'duplicate JSON member'
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def execute(argv, cwd, prefix, env, seconds=20):
    paths = [prefix.with_suffix('.stdout'), prefix.with_suffix('.stderr')]
    with paths[0].open('wb') as out, paths[1].open('wb') as err:
        child = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                 stdout=out, stderr=err, shell=False)
        deadline = time.monotonic() + seconds
        failure = None
        while child.poll() is None:
            if time.monotonic() > deadline:
                failure = 'deadline'
            if any(path.stat().st_size > CAP for path in paths):
                failure = 'capture threshold'
            if failure:
                child.kill()
                child.wait(timeout=5)
                raise AssertionError(failure)
            time.sleep(0.01)
    assert all(path.stat().st_size <= CAP for path in paths), 'oversized capture'
    return child.returncode, *(path.read_bytes() for path in paths)


def inventory(folder):
    result = {}
    for path in folder.iterdir():
        assert path.is_file() and not path.is_symlink(), 'unexpected entry'
        stat = path.stat()
        result[path.name] = dict(size=stat.st_size, mtime=stat.st_mtime_ns,
                                creation=stat.st_birthtime_ns if hasattr(stat, 'st_birthtime_ns') else None,
                                device=stat.st_dev, inode=stat.st_ino, links=stat.st_nlink,
                                mode=stat.st_mode, attributes=getattr(stat, 'st_file_attributes', None),
                                sha256=sha(path))
    return result


def tools_check(reference, perl):
    records = {}
    for name, expected_root in [('exiftool-13.59', reference), ('installed-perl', perl.parent),
                                ('json-pp', ROOT / '.local/tools/perl-5.32.1-json-pp')]:
        manifest_path = ROOT / f'.local/tools/manifests/{name}.json'
        manifest = strict(manifest_path.read_bytes())
        assert Path(manifest['root']).resolve() == expected_root.resolve()
        for item in manifest['files']:
            path = expected_root / item['path']
            assert path.resolve().is_relative_to(expected_root.resolve())
            assert str(path.stat().st_size) == item['byteLength'] and sha(path) == item['sha256']
        records[name] = dict(manifestSha256=sha(manifest_path), files=len(manifest['files']))
    observed = subprocess.run(['git', '-C', str(reference), 'rev-parse', 'HEAD'],
                              capture_output=True, check=True, timeout=10)
    assert observed.stdout.decode().strip() == REV
    status = subprocess.run(['git', '-C', str(reference), 'status', '--porcelain'],
                            capture_output=True, check=True, timeout=10)
    assert not status.stdout, 'reference checkout modified'
    pinned = strict((ROOT / 'docs/legacy-compatibility/native-token-inventory.v1.json').read_bytes())
    for name, identity in pinned['upstream']['sources'].items():
        assert sha(reference / name) == identity['sha256']
    return records


def export_fixture(folder, captures, env):
    exporter = folder / 'export.rs'
    exporter.write_text(
        '#[allow(dead_code)] #[path=' + json.dumps((ROOT / 'tests/support/mod.rs').as_posix()) +
        '] mod support;\nfn main(){std::fs::write(std::env::args_os().nth(1).unwrap(),'
        'support::fixture().bytes).unwrap();}\n', encoding='utf-8')
    binary = folder / ('export.exe' if os.name == 'nt' else 'export')
    assert execute(['rustc', '--edition=2024', str(exporter), '-o', str(binary)],
                   ROOT, captures / 'export-build', env, 60)[0] == 0
    source = folder / 'authored.cr3'
    assert execute([str(binary), str(source)], ROOT, captures / 'export', env)[0] == 0
    data = source.read_bytes()
    # Independent TIFF decoding binds known authored semantics before tool output.
    start = data.index(b'CMT2') + 4
    assert data[start:start + 8] == b'II*\x00\x08\x00\x00\x00'
    count = struct.unpack_from('<H', data, start + 8)[0]
    entries = {}
    for index in range(count):
        tag, kind, length, value = struct.unpack_from('<HHII', data, start + 10 + index * 12)
        entries[tag] = (kind, length, value)
    assert entries[0x8827] == (3, 1, 800)
    assert entries[0x829a][:2] == (5, 1)
    assert struct.unpack_from('<II', data, start + entries[0x829a][2]) == (2, 500)
    assert b'Canon EOS R5\0' in data and b'2026:01:02 03:04:05\0' in data
    return data


def native_check(case, result, source, identity):
    status, stdout, stderr = result
    assert status == (2 if 'refusal' in case else 0), 'native status'
    assert bool(stderr) == ('refusal' in case), 'native stderr channel'
    assert b'\x1b' not in stdout + stderr and stdout.endswith(b'\n')
    value = strict(stdout)
    assert value['summary']['exitStatus'] == status
    assert value['summary']['artifacts'] == [] and value['summary']['outputComplete']
    if 'refusal' in case:
        assert value['files'] == []
        assert value['summary']['counts']['discovered'] == 0
        assert value['request']['issues'][0]['code'] == case['refusal']
        return
    assert len(value['files']) == 1
    file = value['files'][0]
    assert file['path'] == str(source) and file['state'] == 'read'
    assert file['effects'] == dict(publicationMayHaveOccurred=False, changed=False,
                                   cleanupPending=False, recoveryIds=[], notes=[])
    assert [issue['code'] for issue in file['issues']] == (
        ['COVERAGE_PARTIAL'] if case['names'] else ['COVERAGE_PARTIAL', 'TAG_UNRESOLVED'])
    snapshot = file['snapshot']
    assert snapshot['sources'][0]['displayPath'] == str(source)
    assert snapshot['sources'][0]['byteLength'] == str(identity['size'])
    assert snapshot['sources'][0]['identity']['kind'] == 'unavailable'
    assert len(snapshot['coverage']) == 1 and snapshot['coverage'][0]['state'] == 'partial'
    assert snapshot['associations'] == [] and snapshot['selections'] == []
    assert snapshot['issues'] == [] and all(r['sha256'] is None for r in snapshot['resources'])
    occurrences = snapshot['occurrences']
    assert [o['tag']['name'] for o in occurrences] == case['names'], 'native names/order'
    expected_occurrences = [CONTRACTS[key] for key in case['nativeOccurrences']]
    assert len(occurrences) == len(expected_occurrences), 'native occurrence multiplicity'
    resources = {r['id']: r for r in snapshot['resources']}
    for occurrence, expected in zip(occurrences, expected_occurrences):
        name, namespace = expected['name'], expected['namespace']
        ordinal = expected['ordinal']
        assert type(occurrence['ordinal']) is int and occurrence['ordinal'] == ordinal
        assert occurrence['id'] == f'occ-{ordinal}' and occurrence['path']
        assert occurrence['documentRef'] == 'doc-raw'
        assert occurrence['tag'] == dict(name=name, namespace=namespace, nativeId=expected['nativeId'],
            definitionRef=f'r5-read-slice-2026-10-11.1:{namespace}:{expected["nativeId"]}'), 'native tag identity'
        assert occurrence['groups'] == [dict(axis='metadata-family', label=namespace)], 'native group identity'
        assert occurrence['origin']['resourceRef'] == f'value-{ordinal}'
        values = occurrence['values']
        raw = expected['value']
        layer = dict(state='present', value=raw)
        assert values['raw'] == layer, 'native exact present raw value'
        assert values['normalized'] == layer, 'native exact present normalized value'
        display = (dict(state='present', text=expected['displayText'], locale='en', timeZone=None,
                        formatterRef='native-r5-display-v1')
                   if case.get('view', 'raw') in ('display', 'all')
                   else dict(state='unavailable', reason='Not requested'))
        assert values['display'] == display, 'native exact typed display'
        resource = resources[occurrence['origin']['resourceRef']]
        span = resource['content']['ranges'][0]
        assert span['ref'] == 'src-raw'
        assert int(span['offset']) + int(span['length']) <= identity['size']
        assert resource['byteLength'] == span['length']
        stored = source.read_bytes()[int(span['offset']):int(span['offset']) + int(span['length'])]
        if name == 'Model':
            assert stored == b'Canon EOS R5\0'
        elif name == 'ISO':
            assert int.from_bytes(stored, 'little') == 800
        elif name == 'ExposureTime':
            fmt = '<II' if namespace == 'exif' else '<HH'
            assert struct.unpack(fmt, stored) == (int(raw['numerator']), int(raw['denominator']))


def reference_check(case, result, source):
    status, stdout, stderr = result
    assert status == 0 and not stderr, 'reference status/channel'
    assert b'\x1b' not in stdout
    if 'referenceText' in case:
        lines = [' '.join(line.split()) for line in stdout.decode('utf-8').splitlines() if line.strip()]
        assert lines == case['referenceText'], 'reference group presentation'
    else:
        result = strict(stdout)
        assert len(result) == 1
        record = result[0]
        assert Path(record.pop('SourceFile')).resolve() == source.resolve(), 'reference wrong input'
        assert record == case['referenceValues'], 'reference semantic values'
        if 'referenceOrder' in case:
            assert list(record) == case['referenceOrder'], 'reference ordering'


def challenge_oracle(case, native_result, reference_result, source, identity):
    """Mutate one dimension at a time; actual passing reports are the controls."""
    def rejects(check):
        try:
            check()
        except AssertionError:
            return
        raise AssertionError('oracle accepted a deliberately false observation')
    value = strict(native_result[1])
    mutations = []

    def change(label, path, replacement):
        mutant = copy.deepcopy(value)
        target = mutant
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = replacement
        mutations.append((case['id'] + ':' + label, mutant))

    snapshot = ['files', 0, 'snapshot']
    first = [*snapshot, 'occurrences', 0]
    layers = [*first, 'values']
    if case['id'] == 'RR-001':
        change('wrong-input', ['files', 0, 'path'], str(source.with_name('unselected-decoy.cr3')))
        change('false-complete', [*snapshot, 'coverage', 0, 'state'], 'complete')
        change('false-effect', ['files', 0, 'effects', 'changed'], True)
        change('wrong-raw-value', [*layers, 'raw', 'value', 'text'], 'Wrong Input!')
        for layer in ('raw', 'normalized'):
            change(layer + '-invalid-state', [*layers, layer, 'state'], 'invalid')
            change(layer + '-wrong-type', [*layers, layer, 'value', 'text'], 37)
        change('wrong-normalized-value', [*layers, 'normalized', 'value', 'text'], 'Wrong Input!')
        invalid = copy.deepcopy(value)
        for layer in ('raw', 'normalized'):
            invalid['files'][0]['snapshot']['occurrences'][0]['values'][layer]['state'] = 'invalid'
        mutations.append((case['id'] + ':both-invalid-states', invalid))
        change('unrequested-display', [*layers, 'display'], dict(state='present', text='Canon EOS R5'))
    elif case['id'] == 'RR-004':
        second = [*snapshot, 'occurrences', 1]
        change('ctmd-as-exif', [*second, 'tag', 'namespace'], 'exif')
        change('wrong-group', [*second, 'groups', 0, 'label'], 'exif')
        change('wrong-native-id', [*second, 'tag', 'nativeId'], '34855')
        change('wrong-definition', [*second, 'tag', 'definitionRef'], 'wrong-definition')
        change('wrong-ordinal', [*second, 'ordinal'], 23)
        change('wrong-occurrence-id', [*second, 'id'], 'occ-23')
        change('duplicated-exif-occurrence', second, value['files'][0]['snapshot']['occurrences'][0])
    else:
        assert case['id'] in ('RR-015', 'RR-025')
        for index in (0, 1):
            display = [*snapshot, 'occurrences', index, 'values', 'display']
            for field, replacement in [('text', 'WRONG'), ('text', 37), ('locale', 37),
                                       ('timeZone', 'UTC'), ('formatterRef', 'WRONG'),
                                       ('state', 'unavailable')]:
                change(f'display-{index}-{field}-{type(replacement).__name__}',
                       [*display, field], replacement)
    for label, mutant in mutations:
        rejects(lambda: native_check(case, (0, json.dumps(mutant).encode() + b'\n', b''), source, identity))
    labels = [label for label, _ in mutations]
    if case['id'] == 'RR-001':
        ref = strict(reference_result[1])
        ref[0]['SourceFile'] = str(source.with_name('unselected-decoy.cr3'))
        rejects(lambda: reference_check(case, (0, json.dumps(ref).encode(), b''), source))
        labels.append(case['id'] + ':reference-wrong-input')
    return labels


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--reference-root', type=Path, required=True)
    parser.add_argument('--perl', type=Path, required=True)
    parser.add_argument('--public-results', type=Path)
    args = parser.parse_args()
    binary, reference, perl = (path.resolve(strict=True) for path in
                               (args.binary, args.reference_root, args.perl))
    tools_before = tools_check(reference, perl)
    cases = strict(LEDGER.read_bytes())['cases']
    assert 0 < len(cases) <= 32 and len({c['id'] for c in cases}) == len(cases)
    scratch = ROOT / '.local/work-wave-20261017a'
    scratch.mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix='122-run-', dir=scratch)).resolve()
    captures = folder / 'captures'
    captures.mkdir()
    env = {key: os.environ[key] for key in ('SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'PATH',
                                           'USERPROFILE', 'CARGO_HOME', 'RUSTUP_HOME') if key in os.environ}
    env.update(LC_ALL='C', LC_CTYPE='C', LANG='C', TZ='UTC0', NO_COLOR='1',
               PERL5LIB=str(ROOT / '.local/tools/perl-5.32.1-json-pp/lib') + os.pathsep + str(perl.parent / 'lib'))
    # Fixture compilation uses the installed compiler's ordinary discovery environment;
    # only media/reference executions use the controlled read environment below.
    data = export_fixture(folder, captures, dict(os.environ))
    base = [str(perl), '-I', str(reference / 'lib'), str(reference / 'exiftool'),
            '-config', '', '-lang', 'en', '-charset', 'filename=UTF8', '-s']
    version = execute([*base, '-ver'], folder, captures / 'reference-version', env)
    assert version[0] == 0 and version[1].strip() == b'13.59' and not version[2]
    report = dict(schemaVersion=1, ticket='#0122', referenceVersion='13.59', referenceRevision=REV,
                  binarySha256=sha(binary), checkerSha256=sha(Path(__file__)), ledgerSha256=sha(LEDGER),
                  fixtureSupportSha256=sha(ROOT / 'tests/support/mod.rs'), fixtureSha256=hashlib.sha256(data).hexdigest(),
                  tools=tools_before, oracleRejectionControls=0, oracleRejectionControlIds=[], sourceSha256={name: sha(ROOT / name) for name in
                     ('Cargo.lock', 'src/cli.rs', 'src/app.rs', 'src/reader/mod.rs', 'src/reader/wire.rs',
                      'src/reader/bmff.rs', 'src/reader/tiff.rs', 'src/reader/tracks.rs')}, cases=[])
    for case in cases:
        work = folder / case['id']
        work.mkdir()
        source = work / 'selected-authored.cr3'
        source.write_bytes(data)
        # Different valid bytes prevent treating another same-shaped path as the selected input.
        decoy = bytearray(data)
        at = decoy.index(b'Canon EOS R5\0')
        decoy[at:at + 12] = b'Wrong Input!'
        (work / 'unselected-decoy.cr3').write_bytes(decoy)
        (work / 'sentinel.txt').write_bytes(b'no metadata operation may change this')
        before = inventory(work)
        assert before[source.name]['sha256'] == report['fixtureSha256']
        (captures / (case['id'] + '-bindings.private.json')).write_text(json.dumps(dict(
            expectedInput=str(source), before=before,
            referenceArgv=[*base, *case['reference'], '--', str(source)],
            nativeArgv=[str(binary), 'metadata', 'read', '--output', 'json', *case['native'], '--', str(source)]), indent=2))
        try:
            reference_result = execute([*base, *case['reference'], '--', str(source)], work,
                                       captures / (case['id'] + '-reference'), env)
            reference_check(case, reference_result, source)
            assert inventory(work) == before, 'reference effects or object replacement'
            native_result = execute([str(binary), 'metadata', 'read', '--output', 'json',
                                     *case['native'], '--', str(source)], work,
                                    captures / (case['id'] + '-native'), env)
            native_check(case, native_result, source, before[source.name])
            assert inventory(work) == before, 'native effects or object replacement'
            (captures / (case['id'] + '-after.private.json')).write_text(json.dumps(inventory(work), indent=2))
            if case['id'] in ('RR-001', 'RR-004', 'RR-015', 'RR-025'):
                report['oracleRejectionControlIds'].extend(challenge_oracle(
                    case, native_result, reference_result, source, before[source.name]))
                report['oracleRejectionControls'] = len(report['oracleRejectionControlIds'])
            row = dict(id=case['id'], passed=True, referenceStatus=reference_result[0],
                       nativeStatus=native_result[0], referenceChannel='stdout', nativeChannel='json+stderr' if 'refusal' in case else 'json',
                       classification='native-refusal' if 'refusal' in case else 'finite-native-difference',
                       effects='unchanged-authored-inventory-and-measured-properties',
                       captures={tool: dict(stdoutBytes=len(result[1]), stderrBytes=len(result[2]),
                                            stdoutSha256=hashlib.sha256(result[1]).hexdigest(),
                                            stderrSha256=hashlib.sha256(result[2]).hexdigest())
                                 for tool, result in [('reference', reference_result), ('native', native_result)]})
        except Exception as error:
            row = dict(id=case['id'], passed=False, failure=str(error))
        report['cases'].append(row)
        (folder / 'results.private.json').write_text(json.dumps(report, indent=2) + '\n')
    assert sha(binary) == report['binarySha256'] and tools_check(reference, perl) == tools_before
    failures = [row for row in report['cases'] if not row['passed']]
    if not failures and args.public_results:
        args.public_results.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(dict(cases=len(cases), failures=failures, retained=str(folder))))
    return bool(failures)


if __name__ == '__main__':
    raise SystemExit(main())
