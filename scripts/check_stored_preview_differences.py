"""#0123: 18 pinned reference/native preview comparisons; authored bytes only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import struct
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / 'docs/legacy-compatibility/stored-preview-differences.cases.json'
PIN = '2200871d9cef988051d2a99d67df3bda6cbb30a8'
EXPECTED = {tag: bytes.fromhex(code) for tag, code in {
    'ThumbnailImage': 'ffd8fffe000341ffd900',
    'PreviewImage': 'ffd8fffe000342ffd90000',
    'JpgFromRaw': 'ffd8fffe000343ffd9000000'}.items()}
LIMIT = 1024 * 1024


def sha(data):
    return hashlib.sha256(data).hexdigest()


def dump(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def execute(argv, cwd, capture, env, seconds=15):
    paths = [capture.with_suffix('.stdout'), capture.with_suffix('.stderr')]
    with paths[0].open('wb') as out, paths[1].open('wb') as err:
        child = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                 stdout=out, stderr=err, shell=False)
        end = time.monotonic() + seconds
        failure = None
        while child.poll() is None:
            if time.monotonic() >= end:
                failure = 'deadline exceeded'
            if any(p.stat().st_size > LIMIT for p in paths):
                failure = 'capture limit exceeded'
            if failure:
                child.kill()
                child.wait(timeout=5)
                raise AssertionError(failure)
            time.sleep(.01)
    assert all(p.stat().st_size <= LIMIT for p in paths), 'oversized capture'
    return child.returncode, *(p.read_bytes() for p in paths)


def verify_tools(tool, perl, manifests):
    result = {}
    for name, base in [('exiftool-13.59', tool), ('installed-perl', perl.parent),
                       ('json-pp', ROOT / '.local/tools/perl-5.32.1-json-pp')]:
        path = manifests / (name + '.json')
        manifest = json.loads(path.read_text(encoding='utf-8'))
        for row in manifest['files']:
            p = base / row['path']
            assert not p.is_symlink() and p.is_file()
            assert len(p.read_bytes()) == int(row['byteLength'])
            assert sha(p.read_bytes()) == row['sha256'], p
        if name != 'installed-perl':
            actual = {p.relative_to(base).as_posix() for p in base.rglob('*')
                      if p.is_file() and '.git' not in p.relative_to(base).parts}
            assert actual == {r['path'] for r in manifest['files']}, 'tool file set drift'
        if name == 'installed-perl':
            actual = {p.relative_to(base).as_posix() for p in base.rglob('*')
                      if p.is_file() and (p.suffix.lower() in ('.pm', '.dll', '.exe')
                      and ('lib' in p.relative_to(base).parts or p.name == 'perl.exe'
                           or p.suffix.lower() == '.dll'))}
            assert actual == {r['path'] for r in manifest['files']}, 'runtime file set drift'
        result[name] = {'manifestSha256': sha(path.read_bytes()),
                        'checkedFiles': len(manifest['files'])}
    assert subprocess.check_output(['git', '-C', str(tool), 'rev-parse', 'HEAD'], text=True).strip() == PIN
    assert not subprocess.check_output(['git', '-C', str(tool), 'status', '--porcelain'])
    pin = json.loads((ROOT / 'docs/legacy-compatibility/native-token-inventory.v1.json').read_text())
    for name, item in pin['upstream']['sources'].items():
        assert sha((tool / name).read_bytes()) == item['sha256']
    return result


def fixture(folder, captures, env):
    # The repo's independently authored CR3 structure is reused, never camera bytes.
    # Only this fixture adds four authored handler atoms; every sample offset moves
    # by the independently computed 4 * 32 bytes. No reference source is imported.
    support = json.dumps((ROOT / 'tests/support/mod.rs').as_posix())
    source = folder / 'fixture.rs'
    arrays = ','.join('vec![' + ','.join(map(str, b)) + ']' for b in EXPECTED.values())
    source.write_text(f'#[allow(dead_code)] #[path={support}] mod support;\n'
                      'fn main(){let f=support::fixture_with_previews("Firmware Version test",'
                      + arrays + ');std::fs::write(std::env::args_os().nth(1).unwrap(),f.bytes).unwrap();}\n')
    exe = folder / ('fixture.exe' if os.name == 'nt' else 'fixture')
    assert execute(['rustc', '--edition=2024', str(source), '-o', str(exe)], ROOT,
                   captures / 'fixture-build', env, 60)[0] == 0
    original = folder / 'authored.cr3'
    assert execute([str(exe), str(original)], ROOT, captures / 'fixture-export', env)[0] == 0

    def atom(kind, data):
        return struct.pack('>I', len(data) + 8) + kind + data

    def rebuild(data):
        output = b''
        offset = 0
        while offset < len(data):
            size = struct.unpack('>I', data[offset:offset + 4])[0]
            assert 8 <= size <= len(data) - offset
            kind, value = data[offset + 4:offset + 8], data[offset + 8:offset + size]
            if kind in (b'moov', b'trak', b'mdia', b'minf', b'stbl'):
                value = rebuild(value)
            if kind == b'mdia':
                value = atom(b'hdlr', bytes(8) + b'vide' + bytes(12)) + value
            if kind == b'co64':
                assert len(value) == 16
                value = value[:8] + struct.pack('>Q', struct.unpack('>Q', value[8:])[0] + 128)
            output += atom(kind, value)
            offset += size
        return output

    data = rebuild(original.read_bytes())
    original.write_bytes(data)
    for value in EXPECTED.values():
        assert data.count(value) == 1
    return data


def inventory(folder):
    result = {}
    for p in folder.iterdir():
        s = p.lstat()
        assert stat.S_ISREG(s.st_mode) and not p.is_symlink(), 'unexpected namespace entry'
        result[p.name] = {'sha256': sha(p.read_bytes()), 'byteLength': s.st_size,
                          'device': s.st_dev, 'fileId': s.st_ino, 'mode': s.st_mode,
                          'mtimeNs': s.st_mtime_ns, 'ctimeNs': s.st_ctime_ns,
                          'birthtimeNs': getattr(s, 'st_birthtime_ns', None), 'links': s.st_nlink,
                          'fileAttributes': getattr(s, 'st_file_attributes', None)}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', required=True, type=Path)
    parser.add_argument('--reference-root', required=True, type=Path)
    parser.add_argument('--perl', required=True, type=Path)
    parser.add_argument('--manifests', type=Path, default=ROOT / '.local/tools/manifests')
    parser.add_argument('--public-results', type=Path)
    args = parser.parse_args()
    binary, tool, perl = (p.resolve(strict=True) for p in (args.binary, args.reference_root, args.perl))
    tools_before = verify_tools(tool, perl, args.manifests)
    env = {k: os.environ[k] for k in ('SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP') if k in os.environ}
    env.update(PATH=str(perl.parent) + os.pathsep + str(Path(os.environ['SYSTEMROOT']) / 'System32'),
               LC_ALL='C', LC_CTYPE='C', LANG='C', TZ='UTC0',
               PERL5LIB=str(ROOT / '.local/tools/perl-5.32.1-json-pp/lib') + os.pathsep + str(perl.parent / 'lib'))
    native_env = {**os.environ, 'NO_COLOR': '1'}
    base = ROOT / '.local/work-wave-20261017a'
    folder = Path(tempfile.mkdtemp(prefix='123-run-', dir=base))
    captures = folder / 'captures'
    captures.mkdir()
    print(folder, flush=True)
    data = fixture(folder, captures, native_env)
    prefix = [str(perl), '-I', str(tool / 'lib'), str(tool / 'exiftool'), '-config', '']
    version = execute(prefix + ['-ver'], folder, captures / 'reference-version', env)
    assert version == (0, b'13.59\r\n', b'') or version == (0, b'13.59\n', b'')
    ledger = json.loads(LEDGER.read_text())
    assert len(ledger['cases']) == 18
    source_files = sorted({p.relative_to(ROOT).as_posix()
                           for directory in ('src', 'crates')
                           for p in (ROOT / directory).rglob('*.rs')}
                          | {'tests/support/mod.rs', 'Cargo.lock', 'Cargo.toml', 'rust-toolchain.toml'}
                          | {p.relative_to(ROOT).as_posix() for p in (ROOT / 'crates').rglob('Cargo.toml')})
    frozen = {name: sha((ROOT / name).read_bytes()) for name in source_files}
    binary_hash = sha(binary.read_bytes())
    report = {'schemaVersion': 1, 'ticket': '#0123', 'referenceVersion': '13.59',
              'referenceRevision': PIN, 'tools': tools_before,
              'referenceConfig': 'explicit empty -config; isolated Perl environment; C locale; UTC0',
              'binarySha256': binary_hash, 'sourceSha256': frozen,
              'checkerSha256': sha(Path(__file__).read_bytes()), 'ledgerSha256': sha(LEDGER.read_bytes()),
              'fixture': {'sha256': sha(data), 'byteLength': len(data),
                          'previews': {t: {'byteLength': len(v), 'sha256': sha(v),
                                            'sourceOffset': data.index(v)} for t, v in EXPECTED.items()}},
              'cases': []}
    for case in ledger['cases']:
        row = {'id': case['id'], 'passed': False, 'observations': {}}
        report['cases'].append(row)
        for side in ('reference', 'native'):
            work = folder / (case['id'] + '-' + side)
            work.mkdir()
            source_name = '-photo.cr3' if case['id'] == 'SP-013' else ('space name.cr3' if case['id'] == 'SP-014' else 'source.cr3')
            (work / source_name).write_bytes(data)
            occupied = 'source.jpg' if case['kind'] == 'occupied-w' else ('PreviewImage.jpg' if case['kind'] == 'occupied-W' else None)
            if occupied:
                (work / occupied).write_bytes(b'authored occupied destination sentinel\n')
            before = inventory(work)
            status, out, err = execute((prefix if side == 'reference' else [str(binary)]) + case[side],
                                       work, captures / (case['id'] + '-' + side), env if side == 'reference' else native_env)
            after = inventory(work)
            dump(folder / (case['id'] + '-' + side + '.inventory.private.json'), {'before': before, 'after': after})
            observation = {'status': status, 'stdoutBytes': len(out), 'stdoutSha256': sha(out),
                           'stderrBytes': len(err), 'stderrSha256': sha(err),
                           'inputPath': source_name, 'inputBefore': before[source_name],
                           'inputAfter': after[source_name],
                           'occupiedBefore': before.get(occupied), 'occupiedAfter': after.get(occupied),
                           'newFileCount': len(after.keys() - before.keys()),
                           'namespaceBefore': sorted(before), 'namespaceAfter': sorted(after),
                           'outputFiles': {n: after[n] for n in sorted(after.keys() - before.keys())}}
            row['observations'][side] = observation
            dump(folder / 'results.private.json', report)
            assert status == case[side + 'Status'], (case['id'], side, status)
            outputs = case[side + 'Outputs']
            assert after.keys() == before.keys() | outputs.keys(), (case['id'], side, 'namespace')
            for name, value in before.items():
                assert after[name] == value, (case['id'], side, name, 'input/sentinel changed')
            for name, tag in outputs.items():
                assert (work / name).read_bytes() == EXPECTED[tag], (case['id'], side, 'wrong bytes')
            if side == 'reference':
                assert bool(err) == (status != 0), (case['id'], 'reference diagnostics')
                if case['referenceStdoutPreview']:
                    assert out == EXPECTED[case['referenceStdoutPreview']] * case.get('referenceStdoutCopies', 1), (case['id'], 'stdout bytes')
                if case['kind'] == 'list':
                    assert all(t.encode() in out for t in EXPECTED)
            else:
                obj = json.loads(out)
                observation['summaryArtifactCount'] = len(obj['summary']['artifacts'])
                assert obj['summary']['exitStatus'] == status
                if obj['files']:
                    assert obj['files'][0]['path'] == source_name
                assert len(obj['summary']['artifacts']) == len(outputs)
                if outputs:
                    assert obj['files'][0]['path'] == source_name
                    assert {a['path'] for a in obj['summary']['artifacts']} == set(outputs)
                if case['kind'] == 'list':
                    snap = obj['files'][0]['snapshot']
                    assert [o['tag']['name'] for o in snap['occurrences']] == list(EXPECTED)
                    for o in snap['occurrences']:
                        resource = next(r for r in snap['resources'] if r['id'] == o['origin']['resourceRef'])
                        ranges = resource['content']['ranges']
                        assert len(ranges) == 1
                        value = EXPECTED[o['tag']['name']]
                        assert ranges[0]['offset'] == str(data.index(value)) and ranges[0]['length'] == str(len(value))
                if case['kind'] == 'dry-run':
                    assert obj['files'][0]['state'] == 'previewed'
                if status == 1:
                    assert obj['files'][0]['issues'][0]['code'] == 'DESTINATION_EXISTS'
        row['passed'] = True
        dump(folder / 'results.private.json', report)
    assert tools_before == verify_tools(tool, perl, args.manifests)
    assert frozen == {n: sha((ROOT / n).read_bytes()) for n in source_files}, 'source changed during run'
    assert binary_hash == sha(binary.read_bytes()), 'binary changed during run'
    report['toolsUnchangedAfter'] = True
    report['passedCases'] = len(report['cases'])
    dump(folder / 'results.private.json', report)
    if args.public_results:
        dump(args.public_results, report)
    print('18/18 authored reference/native cases passed')


if __name__ == '__main__':
    main()
