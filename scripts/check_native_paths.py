"""#0059: finite native argv and declared shell path qualification.

Only authored structural fixtures are used. Raw captures remain under .local.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import sys
import tempfile

from check_read_arguments import fixture, run

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / 'docs/legacy-compatibility/native-paths/cases.json'
PLATFORM = {'win32': 'windows', 'linux': 'linux', 'darwin': 'macos'}.get(sys.platform)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def native(value):
    if isinstance(value, str):
        return value
    if 'unixHex' in value:
        return os.fsdecode(bytes.fromhex(value['unixHex']))
    return bytes.fromhex(value['windowsUtf16LeHex']).decode('utf-16-le', 'surrogatepass')


def display(value):
    if os.name == 'nt':
        return value.encode('utf-16-le', 'surrogatepass').decode('utf-16-le', 'replace')
    return os.fsencode(value).decode('utf-8', 'replace')


def inventory(folder):
    """Keep native names distinct even when two paths have the same JSON label."""
    result = {}
    for path in folder.iterdir():
        assert path.is_file() and not path.is_symlink(), 'unexpected fixture entry'
        name = (path.name.encode('utf-16-le', 'surrogatepass') if os.name == 'nt'
                else os.fsencode(path.name))
        stat = path.stat()
        result[name.hex()] = [stat.st_size, stat.st_mtime_ns, digest(path)]
    return result


def quote(value, shell):
    if shell == 'powershell':
        return "'" + value.replace("'", "''") + "'"
    # ANSI-C quoting is used only for native invalid-byte tokens, not Unicode.
    if any(0xdc80 <= ord(char) <= 0xdcff for char in value):
        return "$'" + ''.join(f'\\x{byte:02x}' for byte in os.fsencode(value)) + "'"
    return "'" + value.replace("'", "'\\''") + "'"


def shell_source(binary, argv, shell):
    command = ' '.join(quote(token, shell) for token in [str(binary), *argv])
    if shell == 'powershell':
        return ("$ErrorActionPreference = 'Stop'\n"
                "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)\n"
                f'& {command}\nexit $LASTEXITCODE\n')
    return 'exec ' + command + '\n'


def check(case, status, stdout, stderr, paths):
    expected = case['expected'][PLATFORM]
    assert status == expected['status'], f'status {status}, expected {expected["status"]}'
    assert b'\x1b' not in stdout + stderr, 'terminal escape in capture'
    value = json.loads(stdout)
    assert value['schemaVersion'] == 1
    assert value['summary']['exitStatus'] == status
    assert value['summary']['artifacts'] == []
    assert bool(stderr) == (status != 0), 'unexpected stderr presence'
    if expected['kind'] == 'syntax-refusal':
        assert value['files'] == []
        assert value['request']['issues'][0]['code'] == expected['code']
        assert value['summary']['counts']['discovered'] == 0
        return
    assert [file['path'] for file in value['files']] == [display(path) for path in paths]
    assert value['summary']['counts']['discovered'] == len(paths)
    for file in value['files']:
        assert file['state'] == ('read' if status == 0 else 'failed')
        codes = [issue['code'] for issue in file['issues']]
        if expected['kind'] == 'file-refusal':
            assert expected['code'] in codes and file['snapshot'] is None
        else:
            names = [item['tag']['name'] for item in file['snapshot']['occurrences']]
            assert names == (['Model'] if case['operation'] == 'metadata-read' else
                             ['ThumbnailImage', 'PreviewImage', 'JpgFromRaw']), names
            assert ('PATH_DISPLAY_LOSSY' in codes) == case.get('lossy', False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, default=ROOT / 'target/debug' /
                        ('imageinfo.exe' if os.name == 'nt' else 'imageinfo'))
    parser.add_argument('--shell', type=Path, help='Explicit pwsh (Windows) or bash (Unix) executable')
    parser.add_argument('--public-results', type=Path)
    args = parser.parse_args()
    assert PLATFORM, 'only Windows, Linux and macOS are declared'
    binary = args.binary.resolve(strict=True)
    shell_kind = 'powershell' if PLATFORM == 'windows' else 'bash'
    shell = str(args.shell.resolve(strict=True)) if args.shell else shutil.which(
        'pwsh' if PLATFORM == 'windows' else 'bash')
    assert shell, f'declared shell {shell_kind} unavailable'
    ledger = json.loads(LEDGER.read_text(encoding='utf-8'))
    cases = ledger['cases']
    assert len({case['id'] for case in cases}) == len(cases), 'duplicate case ID'
    scratch = ROOT / '.local/native-paths'
    scratch.mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix='run-', dir=scratch)).resolve()
    captures = folder / 'captures'
    captures.mkdir()
    version_argv = ([shell, '-NoLogo', '-NoProfile', '-NonInteractive', '-Command',
                     '$PSVersionTable.PSVersion.ToString()'] if os.name == 'nt'
                    else [shell, '--version'])
    status, out, err = run(version_argv, ROOT, captures / 'shell-version')
    assert status == 0 and not err, 'shell version query failed'
    shell_version = out.decode('utf-8').splitlines()[0]
    if shell_kind == 'powershell':
        assert shell_version.startswith('7.'), 'the declared PowerShell shell is version 7'
    else:
        assert shell_version.startswith('GNU bash, version '), 'the declared Unix shell is Bash'
    fixture(folder, captures)
    data = (folder / 'source.cr3').read_bytes()
    report = {
        'schemaVersion': 1, 'platform': PLATFORM, 'osRelease': platform.release(),
        'observedAtUtc': datetime.now(timezone.utc).isoformat(),
        'shell': shell_kind, 'shellVersion': shell_version,
        'shellInvocation': (['pwsh', '-NoLogo', '-NoProfile', '-NonInteractive', '-File', '<script>']
                            if os.name == 'nt' else ['bash', '--noprofile', '--norc', '<script>']),
        'ledgerSha256': digest(LEDGER), 'binarySha256': digest(binary),
        'checkerSha256': digest(Path(__file__)),
        'sourceSha256': {name: digest(ROOT / name) for name in
                         ('src/cli.rs', 'src/app.rs', 'src/read_request.rs',
                          'src/reader/wire.rs', 'Cargo.lock', 'tests/support/mod.rs',
                          'scripts/check_read_arguments.py')},
        'fixtureSha256': hashlib.sha256(data).hexdigest(), 'cases': []}
    for case in cases:
        if PLATFORM not in case['platforms']:
            report['cases'].append({'id': case['id'], 'state': 'not-applicable'})
            continue
        work = folder / case['id']
        work.mkdir()
        try:
            for item in case['files']:
                (work / native(item['path'])).write_bytes(
                    data if item['content'] == 'fixture' else b'not-a-CR3-lossy-neighbor')
            before = inventory(work)
            argv = [native(token) for token in case['argv']]
            paths = [native(token) for token in case['paths']]
            if case['transport'] == 'native-argv':
                command = [str(binary), *argv]
                command_hash = None
                public_script = None
            else:
                source = shell_source(binary, argv, shell_kind)
                public_script = shell_source('<binary>', argv, shell_kind)
                script = captures / (case['id'] + ('.ps1' if os.name == 'nt' else '.bash'))
                script.write_text(source, encoding='utf-8', newline='\n')
                command_hash = digest(script)
                command = ([shell, '-NoLogo', '-NoProfile', '-NonInteractive', '-File', str(script)]
                           if os.name == 'nt' else [shell, '--noprofile', '--norc', str(script)])
            status, stdout, stderr = run(command, work, captures / case['id'])
            check(case, status, stdout, stderr, paths)
            assert inventory(work) == before, 'input bytes, mtime or namespace changed'
            result = {'id': case['id'], 'state': 'passed', 'status': status,
                      'channel': 'json', 'stdoutBytes': len(stdout), 'stderrBytes': len(stderr),
                      'effects': 'unchanged-bytes-mtime-native-names',
                      'classification': case['expected'][PLATFORM]['kind'],
                      'shellScriptSha256': command_hash, 'shellScriptTemplate': public_script}
        except Exception as error:
            # Path labels may contain native non-Unicode units: escape public text.
            result = {'id': case['id'], 'state': 'failed', 'failure': ascii(str(error))}
        report['cases'].append(result)
        (folder / 'results.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    failures = [case for case in report['cases'] if case['state'] == 'failed']
    print(json.dumps({'platform': PLATFORM, 'passed': sum(case['state'] == 'passed'
                      for case in report['cases']), 'failures': failures, 'retained': str(folder)}))
    if not failures and args.public_results:
        args.public_results.parent.mkdir(parents=True, exist_ok=True)
        args.public_results.write_text(json.dumps(report, indent=2, ensure_ascii=True) + '\n',
                                       encoding='utf-8', newline='\n')
    return bool(failures)


if __name__ == '__main__':
    raise SystemExit(main())
