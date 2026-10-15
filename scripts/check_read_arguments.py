"""#0052: finite real-argv qualification, using only authored structural fixtures.

No shell, token splitting, camera media or third-party Python package is used.
Captures and fixtures remain in an owned fresh directory under ignored .local.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / 'docs/legacy-compatibility/read-argument-order.cases.json'
CAPTURE_LIMIT = 1024 * 1024


def run(argv, cwd, capture, seconds=15):
    """Apply deadlines and capture thresholds; file sinks may overshoot a poll."""
    paths = [capture.with_suffix('.stdout'), capture.with_suffix('.stderr')]
    failure = None
    with paths[0].open('wb') as out, paths[1].open('wb') as err:
        process = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.DEVNULL,
                                   stdout=out, stderr=err, shell=False,
                                   env={**os.environ, 'NO_COLOR': '1',
                                        'PAGER': 'imageinfo-must-not-launch-pager'})
        deadline = time.monotonic() + seconds
        while process.poll() is None:
            if time.monotonic() >= deadline:
                failure = 'deadline exceeded'
            elif any(path.stat().st_size > CAPTURE_LIMIT for path in paths):
                failure = 'capture limit exceeded'
            if failure:
                process.kill()
                process.wait(timeout=5)
                break
            time.sleep(0.01)
    if any(path.stat().st_size > CAPTURE_LIMIT for path in paths):
        failure = 'capture limit exceeded'
    if failure:
        raise AssertionError(failure)
    return process.returncode, *(path.read_bytes() for path in paths)


def fixture(folder, captures):
    source = folder / 'fixture.rs'
    support = json.dumps((ROOT / 'tests/support/mod.rs').as_posix())
    source.write_text(
        f'#[allow(dead_code)] #[path={support}] mod support;\n'
        'fn main() { let d=std::path::PathBuf::from(std::env::args_os().nth(1).unwrap());'
        'let f=support::fixture();'
        'std::fs::write(d.join("source.cr3"),f.bytes).unwrap();'
        'std::fs::write(d.join("ThumbnailImage.expected"),f.thumbnail).unwrap();'
        'std::fs::write(d.join("PreviewImage.expected"),f.preview).unwrap();'
        'std::fs::write(d.join("JpgFromRaw.expected"),f.jpeg).unwrap(); }',
        encoding='utf-8')
    executable = folder / ('fixture.exe' if os.name == 'nt' else 'fixture')
    status, _, _ = run(['rustc', '--edition=2024', str(source), '-o', str(executable)],
                       ROOT, captures / 'fixture-build', 60)
    assert status == 0, 'fixture compilation failed'
    status, _, _ = run([str(executable), str(folder)], ROOT, captures / 'fixture-export')
    assert status == 0, 'fixture export failed'


def inventory(folder):
    paths = list(folder.iterdir())
    assert all(path.is_file() and not path.is_symlink() for path in paths), \
        'unexpected directory, link or non-file fixture entry'
    return {path.name: (path.stat().st_size, path.stat().st_mtime_ns,
                        hashlib.sha256(path.read_bytes()).hexdigest())
            for path in paths}


def check(case, status, stdout, stderr, work, before, expected):
    assert status == case['status'], f'status {status}, expected {case["status"]}'
    assert b'\x1b' not in stdout + stderr, 'terminal escape in output'
    kind = case['check']
    value = None
    if case['channel'] == 'json':
        value = json.loads(stdout)
        assert value['schemaVersion'] == 1
        assert value['summary']['exitStatus'] == status
        assert value['summary']['artifacts'] == ([] if kind != 'extract' else [
            {'kind': 'extraction', 'path': case['destination'], 'retainedPath': None,
             'state': 'committed', 'transactionId': None, 'recoveryIds': []}])
        if kind == 'usage':
            assert value['files'] == []
            assert value['summary']['counts']['discovered'] == 0
            assert value['request']['issues'][0]['code'] == case['code']
        elif kind in ('read', 'list'):
            assert [file['path'] for file in value['files']] == case['paths']
            assert all(file['state'] == 'read' for file in value['files'])
            for file in value['files']:
                names = [item['tag']['name'] for item in file['snapshot']['occurrences']]
                if 'names' in case:
                    assert names == case['names'], names
                if 'view' in case:
                    for item in file['snapshot']['occurrences']:
                        vals = item['values']
                        present = {'raw': vals['raw']['state'] != 'unavailable',
                                   'normalized': vals['normalized']['state'] != 'unavailable',
                                   'display': vals['display']['state'] != 'unavailable'}
                        # The current JSON snapshot retains both exact typed views;
                        # --values selects text presentation and optional display JSON.
                        assert present == {'raw': True, 'normalized': True,
                                           'display': case['view'] in ('display', 'all')}, present
        elif kind in ('extract', 'dry-run'):
            assert len(value['files']) == 1
            assert value['files'][0]['state'] == ('previewed' if kind == 'dry-run' else 'read')
        elif kind == 'file-error':
            assert len(value['files']) == 1 and value['files'][0]['state'] == 'failed'
            assert value['files'][0]['issues'][0]['code'] == case['code']
    elif case['channel'] == 'empty':
        assert not stdout
    elif kind == 'help':
        assert stdout.startswith(case['prefix'].encode())
    else:
        assert stdout and not stdout.startswith(b'{')
    assert bool(stderr) == (status != 0), 'unexpected stderr presence'
    after = inventory(work)
    if kind == 'extract':
        destination = case['destination']
        assert after.keys() == before.keys() | {destination}, 'unexpected namespace effects'
        assert (work / destination).read_bytes() == expected[case['preview']]
        after.pop(destination)
    assert after == before, 'source or sentinel bytes, mtime, or names changed'
    return {'id': case['id'], 'status': status, 'channel': case['channel'],
            'stdoutBytes': len(stdout), 'stderrBytes': len(stderr),
            'effects': 'exact-new-preview-only' if kind == 'extract' else 'unchanged',
            'classification': case['classification'], 'passed': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, default=ROOT / 'target/debug' /
                        ('imageinfo.exe' if os.name == 'nt' else 'imageinfo'))
    parser.add_argument('--public-results', type=Path)
    args = parser.parse_args()
    binary = args.binary.resolve(strict=True)
    ledger = json.loads(LEDGER.read_text(encoding='utf-8'))
    cases = ledger['cases']
    assert len({case['id'] for case in cases}) == len(cases)
    scratch = ROOT / '.local/read-arguments'
    scratch.mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix='run-', dir=scratch)).resolve()
    captures = folder / 'captures'
    captures.mkdir()
    fixture(folder, captures)
    data = (folder / 'source.cr3').read_bytes()
    expected = {tag: (folder / (tag + '.expected')).read_bytes()
                for tag in ('ThumbnailImage', 'PreviewImage', 'JpgFromRaw')}
    report = {'schemaVersion': 1, 'ledgerSha256': hashlib.sha256(LEDGER.read_bytes()).hexdigest(),
              'binarySha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
              'checkerSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'sourceSha256': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                               for name in ('src/cli.rs', 'src/app.rs', 'src/read_request.rs',
                                            'src/reader/wire.rs', 'Cargo.lock')},
              'supportSha256': hashlib.sha256((ROOT / 'tests/support/mod.rs').read_bytes()).hexdigest(),
              'cases': []}
    for case in cases:
        work = folder / case['id']
        work.mkdir()
        # Include real literal operands, spaces, Unicode and option-looking names.
        for name in ('source.cr3', 'second.cr3', 'help', '-photo.cr3', '--output=json',
                     'space name.cr3', '写真 🦆.cr3'):
            (work / name).write_bytes(data)
        (work / 'occupied.jpg').write_bytes(b'owned-existing-destination-sentinel')
        before = inventory(work)
        try:
            status, stdout, stderr = run([str(binary), *case['argv']], work,
                                         captures / case['id'])
            result = check(case, status, stdout, stderr, work, before, expected)
        except Exception as error:
            result = {'id': case['id'], 'passed': False, 'failure': str(error)}
        report['cases'].append(result)
        (folder / 'results.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    failures = [case for case in report['cases'] if not case['passed']]
    print(json.dumps({'cases': len(cases), 'failures': failures, 'retained': str(folder)}))
    if not failures and args.public_results:
        args.public_results.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')
    return bool(failures)


if __name__ == '__main__':
    raise SystemExit(main())
