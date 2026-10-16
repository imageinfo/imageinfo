"""#0124 finite executable preview/pair argv checks; authored files only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
from check_read_arguments import run

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / 'docs/legacy-compatibility/preview-pair-arguments.cases.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(folder):
    result = {}
    for path in folder.iterdir():
        assert path.is_file() and not path.is_symlink(), 'unexpected non-file/link'
        stat = path.stat()
        result[path.name] = (stat.st_size, stat.st_mtime_ns, stat.st_mode,
                             stat.st_dev, stat.st_ino, stat.st_nlink,
                             getattr(stat, 'st_file_attributes', None), sha(path))
    return result


def fixture(folder, captures):
    source = folder / 'fixture.rs'
    support = json.dumps((ROOT / 'tests/support/mod.rs').as_posix())
    source.write_text(
        f'#[allow(dead_code)] #[path={support}] mod support;\n'
        'fn main() { let d=std::path::PathBuf::from(std::env::args_os().nth(1).unwrap());'
        'let j=vec![255,216,255,217];'
        'let f=support::fixture_with_previews("Firmware Version 2.2.1",j.clone(),j.clone(),j).bytes;'
        'std::fs::write(d.join("source.cr3"),f).unwrap(); }',
        encoding='utf-8', newline='\n')
    executable = folder / ('fixture.exe' if os.name == 'nt' else 'fixture')
    assert run(['rustc', '--edition=2024', str(source), '-o', str(executable)],
               ROOT, captures / 'fixture-build', 60)[0] == 0
    assert run([str(executable), str(folder)], ROOT, captures / 'fixture-export')[0] == 0
    return (folder / 'source.cr3').read_bytes()


def check(case, status, stdout, stderr, work, data, offset):
    assert status == case['status'], f'status {status}, expected {case["status"]}'
    assert b'\x1b' not in stdout + stderr
    assert bool(stderr) == (status != 0), 'unexpected diagnostic channel'
    kind = case['check']
    if case['channel'] == 'stderr':
        assert stdout == b'' and stderr.startswith(case['code'].encode() + b':')
        return
    if case['channel'] == 'text':
        assert stdout and not stdout.startswith(b'{')
        assert (b'Usage:' in stdout) if kind == 'help' else (b'imageinfo' in stdout)
        return
    value = json.loads(stdout)
    assert value['schemaVersion'] == 1 and value['summary']['exitStatus'] == status
    assert value['summary']['artifacts'] == []
    if kind == 'usage':
        assert value['files'] == [] and value['summary']['counts']['discovered'] == 0
        assert value['request']['issues'][0]['code'] == case['code']
        return
    assert len(value['files']) == 1
    file = value['files'][0]
    assert file['path'] == case['input'], 'result input differs from ledger-selected operand'
    expected_input = work / case['input']
    assert (work / file['path']).samefile(expected_input), 'result input identity differs'
    assert file['transactionId'] is None
    assert file['effects'] == dict(publicationMayHaveOccurred=False, changed=False,
                                    cleanupPending=False, recoveryIds=[], notes=[])
    assert value['summary']['counts']['discovered'] == 1
    if 'code' in case:
        assert case['code'] in [i['code'] for i in file['issues']]
    if kind in ('preview', 'stale-preview'):
        assert value['request']['operation'] == 'preview date-time-original'
        assert file['state'] == 'refused' and file['snapshot']['kind'] == 'date-preview'
        p = file['snapshot']['preview']
        assert p['production_mutation_allowed'] is False and p['status'] == 'refused'
        assert p['source_length'] == len(data)
        if kind == 'stale-preview':
            assert p['expected_occurrence_matches'] is False and p['original_bytes'] is None
        else:
            assert p['field_shape_verified'] and p['expected_occurrence_matches']
            assert p['allocation'] == dict(offset=offset, length=20)
            assert p['original_bytes'] == list(b'2026:01:02 03:04:05\0')
            assert p['proposed_bytes'] == list(b'2000:02:29 23:59:59\0')
            candidate = bytearray(data)
            candidate[offset:offset+20] = bytes(p['proposed_bytes'])
            seen = [0] * len(data)
            for field, changed in [('changed_ranges', True), ('preserved_ranges', False)]:
                for span in p[field]:
                    assert 0 <= span['offset'] <= span['offset'] + span['length'] <= len(data)
                    for at in range(span['offset'], span['offset'] + span['length']):
                        assert (data[at] != candidate[at]) == changed
                        seen[at] += 1
            assert all(n == 1 for n in seen)
            assert p['changed_bytes'] == sum(a != b for a, b in zip(data, candidate)) > 0
            assert p['changed_bytes'] + p['preserved_bytes'] == len(data)
    elif kind == 'pair':
        assert value['request']['operation'] == 'sidecar pair'
        assert file['state'] == 'read' and file['snapshot']['kind'] == 'explicit-pair'
        pair = file['snapshot']['pair']
        assert pair['association'] == 'explicit_paths'
        assert Path(pair['raw_path']).samefile(expected_input), 'pair RAW identity differs from selected operand'
        assert Path(pair['sidecar_path']).samefile(work / case['sidecar']), 'pair sidecar identity differs from selected operand'
    else:
        assert kind == 'file-error' and file['state'] == 'refused' and file['snapshot'] is None


def reject_wrong_inputs(case, status, stdout, stderr, work, data, offset):
    """Negative oracle controls mutate captures; no extra executable argv cases."""
    mutations = []
    if case['id'] == 'PP-010':
        mutations = [('preview-wrong-input', 'source.cr3', None)]
    elif case['id'] == 'PP-026':
        mutations = [('pair-wrong-input', 'opaque.raw', None),
                     ('pair-wrong-raw-identity', None, 'opaque.raw'),
                     ('pair-wrong-input-and-identity', 'opaque.raw', 'opaque.raw')]
    rejected = []
    for name, wrong_input, wrong_raw in mutations:
        value = json.loads(stdout)
        if wrong_input:
            value['files'][0]['path'] = wrong_input
        if wrong_raw:
            value['files'][0]['snapshot']['pair']['raw_path'] = str(work / wrong_raw)
        try:
            check(case, status, json.dumps(value).encode(), stderr, work, data, offset)
        except AssertionError:
            rejected.append(name)
        else:
            raise AssertionError(f'negative oracle control accepted: {name}')
    return rejected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, default=ROOT / 'target/debug' /
                        ('imageinfo.exe' if os.name == 'nt' else 'imageinfo'))
    parser.add_argument('--public-results', type=Path)
    args = parser.parse_args()
    binary = args.binary.resolve(strict=True)
    cases = json.loads(LEDGER.read_text(encoding='utf-8'))['cases']
    assert len(cases) == 32 and len({c['id'] for c in cases}) == 32
    scratch = ROOT / '.local/work-wave-20261016e'
    scratch.mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix='124-run-', dir=scratch)).resolve()
    captures = folder / 'captures'
    captures.mkdir()
    data = fixture(folder, captures)
    needle = b'2026:01:02 03:04:05\0'
    assert data.count(needle) == 1
    offset = data.index(needle)
    report = dict(schemaVersion=1, ticket=124, platform=os.name,
                  binarySha256=sha(binary), ledgerSha256=sha(LEDGER),
                  checkerSha256=sha(Path(__file__)),
                  sourceSha256={p: sha(ROOT / p) for p in (
                      'src/cli.rs', 'src/app.rs', 'src/preview.rs', 'src/pairing.rs',
                      'src/reader/admission.rs', 'tests/support/mod.rs',
                      'scripts/check_read_arguments.py', 'Cargo.lock')}, cases=[], oracleControls=[])
    for case in cases:
        work = folder / case['id']
        work.mkdir()
        for name in ('source.cr3', 'second.cr3', '--output=json'):
            (work / name).write_bytes(data)
        for name in ('opaque.raw', 'help'):
            (work / name).write_bytes(b'authored invalid RAW marker; pairing must not parse')
        (work / 'chosen.xmp').write_bytes(b'\xff\x00not XML; authored explicit sidecar')
        (work / 'source.xmp').write_bytes(b'authored basename decoy')
        os.link(work / 'opaque.raw', work / 'hard-alias.xmp')
        before = inventory(work)
        try:
            argv = [token.replace('{date_offset}', str(offset)) for token in case['argv']]
            status, stdout, stderr = run([str(binary), *argv], work, captures / case['id'])
            check(case, status, stdout, stderr, work, data, offset)
            report['oracleControls'].extend(reject_wrong_inputs(
                case, status, stdout, stderr, work, data, offset))
            assert inventory(work) == before, 'file bytes, properties, identity or names changed'
            result = dict(id=case['id'], status=status, channel=case['channel'],
                          stdoutBytes=len(stdout), stderrBytes=len(stderr),
                          effects='unchanged', passed=True)
        except Exception as error:
            result = dict(id=case['id'], passed=False, failure=str(error))
        report['cases'].append(result)
        (folder / 'results.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8', newline='\n')
    failures = [c for c in report['cases'] if not c['passed']]
    if not failures:
        assert len(report['oracleControls']) == 4, 'missing negative oracle controls'
    print(json.dumps(dict(cases=len(cases), failures=failures, retained=str(folder))))
    if not failures and args.public_results:
        args.public_results.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8', newline='\n')
    return bool(failures)


if __name__ == '__main__':
    raise SystemExit(main())
