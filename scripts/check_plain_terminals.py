"""#0138: authored plain-terminal/process observations; no shell or desktop input.

Captures bounded fresh owned PTYs at 40/80 columns and separate redirected
streams. Windows ConPTY's host VT is rendered, never attributed to the producer.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from plain_terminal_pty import capture, LIMIT

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / 'docs/legacy-compatibility/plain-terminals.cases.json'


def plain(data):
    text = data.decode('utf-8')
    assert all(ord(ch) >= 32 and not 127 <= ord(ch) <= 159 or ch in '\r\n\t' for ch in text), \
        'producer emitted a terminal control'
    assert not any(ch in text for ch in ('\u0085', '\u009b', '\u2028', '\u2029')), \
        'producer emitted a non-ASCII line/control separator'
    return text


def screen(data, columns):
    """Finite VT renderer for captured ConPTY host output, not a general emulator.

    Unknown commands fail qualification. Plain POSIX output follows the same
    cell model. Wide-character screen input is outside these authored cases.
    """
    text = data.decode('utf-8')
    cells = [[' '] * columns for _ in range(100)]
    row = col = 0
    pending_wrap = False
    i = 0
    controls = set()
    while i < len(text):
        if text.startswith('\x1b]', i):
            end = text.find('\x07', i)
            assert end >= 0 and text[i + 2:end].startswith('0;'), 'unknown host OSC'
            controls.add('OSC-title')
            i = end + 1
            continue
        if text.startswith('\x1b[', i):
            match = re.match(r'\x1b\[([?0-9;]*)([A-Za-z])', text[i:])
            assert match, 'unknown host escape'
            param, command = match.groups()
            controls.add('CSI-' + param + command)
            if param.startswith('?'):
                assert param in ('?25', '?9001', '?1004') and command in 'hl', \
                    'unexpected terminal mode (including mouse tracking)'
            elif command == 'm':
                assert param in ('', '0'), 'unexpected color/style command'
            elif command in 'Hf':
                values = [int(x or '1') for x in param.split(';')]
                row = values[0] - 1
                col = (values[1] if len(values) > 1 else 1) - 1
                pending_wrap = False
            elif command == 'J':
                assert param == '2', 'unsupported host erase'
                cells = [[' '] * columns for _ in range(100)]
            elif command == 'K':
                assert param in ('', '0'), 'unsupported host line erase'
                cells[row][col:] = [' '] * (columns - col)
            else:
                raise AssertionError('unsupported host cursor command: ' + command)
            i += len(match.group())
            continue
        ch = text[i]
        i += 1
        if ch == '\r':
            col = 0
            pending_wrap = False
        elif ch == '\n':
            row += 1
            pending_wrap = False
        elif ch == '\t':
            col = min(columns - 1, (col // 8 + 1) * 8)
        else:
            assert 32 <= ord(ch) < 127, 'unexpected screen character/control'
            if pending_wrap:
                row += 1
                col = 0
                pending_wrap = False
            assert row < len(cells) and col < columns, 'screen overflow'
            cells[row][col] = ch
            col += 1
            if col == columns:
                col -= 1
                pending_wrap = True
        assert row < len(cells), 'screen scroll exceeds authored bound'
    return '\n'.join(''.join(line).rstrip() for line in cells).rstrip(), sorted(controls)


def compact(text):
    return re.sub(r'req-[0-9]+-[0-9]+', 'req-ID', re.sub(r'\s+', '', text))


def redirect(argv, cwd, env):
    # Known finite help/refusal requests only. A tempfile sink plus polling keeps
    # unexpected producer output from allocating unbounded parent memory.
    import time
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        process = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                   stdout=out, stderr=err, shell=False)
        deadline = time.monotonic() + 10
        try:
            while process.poll() is None:
                assert time.monotonic() < deadline, 'redirected child deadline exceeded'
                assert os.fstat(out.fileno()).st_size <= LIMIT and \
                    os.fstat(err.fileno()).st_size <= LIMIT, 'redirected capture limit exceeded'
                time.sleep(.01)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=2)
        assert os.fstat(out.fileno()).st_size <= LIMIT and \
            os.fstat(err.fileno()).st_size <= LIMIT, 'redirected capture limit exceeded'
        out.seek(0)
        err.seek(0)
        return process.returncode, out.read(), err.read()


def check(case, status, out, err):
    assert status == case['status'], f'unexpected status {status}'
    stdout, stderr = plain(out), plain(err)
    channel = case['channel']
    if channel == 'help':
        assert stdout and 'Usage:' in stdout and '--help' in stdout and not stderr
    elif channel == 'json':
        value = json.loads(stdout)
        assert isinstance(value, dict) and value['schemaVersion'] == 1
        assert value['summary']['exitStatus'] == status
        assert case['contains'] in stdout
        assert stderr and not stderr.lstrip().startswith('{')
    else:
        assert not stdout and case['contains'] in stderr
    if case['id'].startswith('control-path'):
        assert '\\u{1b}' in stderr and '\\r\\n\\t' in stderr, \
            'control-bearing path must remain one escaped diagnostic operand'
    return stdout, stderr


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--public-results', type=Path)
    args = parser.parse_args()
    binary = args.binary.resolve(strict=True)
    ledger = json.loads(LEDGER.read_text(encoding='utf-8'))
    cases = ledger['cases']
    assert 1 <= len(cases) <= 24 and len({c['id'] for c in cases}) == len(cases)
    help_nodes = {tuple(case['argv'][0][:-1]) for case in cases if case['channel'] == 'help'
                  and case['id'] != 'forced-color-help'}
    discovered = {()}
    scratch = ROOT / '.local/plain-terminals'
    scratch.mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix='run-', dir=scratch))
    env = {**os.environ, 'TERM': 'dumb',
           'PAGER': 'imageinfo-must-not-launch-pager', 'CLICOLOR_FORCE': '0'}
    env.pop('NO_COLOR', None)
    report = {'schemaVersion': 1, 'platform': os.name,
              'binarySha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
              'ledgerSha256': hashlib.sha256(LEDGER.read_bytes()).hexdigest(),
              'sourceSha256': {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                               for path in ('src/cli.rs', 'src/main.rs', 'src/app.rs',
                                            'src/read_request.rs', 'src/output.rs',
                                            'src/inert_translation.rs', 'Cargo.lock',
                                            'scripts/check_plain_terminals.py',
                                            'scripts/plain_terminal_pty.py')}, 'cases': []}
    for case in cases:
        observations = []
        try:
            for spelling_index, tokens in enumerate(case['argv']):
                # A literal missing operand; Windows forbids creating such names,
                # but argv and the diagnostic path still contain the controls.
                argv = [str(binary), *[t.replace('$CONTROL', 'missing\x1b[31m\r\n\t.cr3') for t in tokens]]
                status, out, err = redirect(argv, folder, env)
                stdout, stderr = check(case, status, out, err)
                if case['id'].startswith('help-') and spelling_index == 0:
                    node = tuple(tokens[:-1])
                    section = re.search(r'(?ms)^Commands:\r?\n(.*?)(?:\r?\n\r?\n|\Z)', stdout)
                    if section:
                        for line in section.group(1).splitlines():
                            match = re.match(r'  ([a-z][a-z-]*)\s', line)
                            assert match, 'unexpected command-list layout'
                            if match.group(1) != 'help':
                                discovered.add((*node, match.group(1)))
                stem = folder / (case['id'] + '-' + str(spelling_index))
                stem.with_suffix('.stdout').write_bytes(out)
                stem.with_suffix('.stderr').write_bytes(err)
                for width in (40, 80):
                    status2, raw, backend = capture(argv, folder, width, env)
                    stem.with_suffix(f'.{width}.pty').write_bytes(raw)
                    rendered, controls = screen(raw, width)
                    stem.with_suffix(f'.{width}.screen.txt').write_text(rendered + '\n', encoding='utf-8')
                    # stderr/stdout ordering under the merged PTY is not a
                    # machine-channel promise. Both must be complete in order
                    # for these sequentially emitted finite cases.
                    expected = stdout + stderr
                    exact = compact(rendered) == compact(expected)
                    observations.append({'spelling': spelling_index, 'columns': width,
                                         'backend': backend, 'status': status2,
                                         'ptyBytes': len(raw), 'hostControls': controls,
                                         'exactVisibleNonWhitespace': exact})
                    assert status2 == status, 'PTY child status differs from redirected status'
                    assert exact, 'PTY display lost/changed output'
            result = {'id': case['id'], 'passed': True, 'observations': observations}
        except Exception as error:
            result = {'id': case['id'], 'passed': False, 'failure': str(error),
                      'observations': observations}
        report['cases'].append(result)
        (folder / 'results.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    failures = [c for c in report['cases'] if not c['passed']]
    report['helpInventoryComplete'] = help_nodes == discovered
    if help_nodes != discovered:
        failures.append({'failure': 'authored help cases differ from actual command inventory'})
    (folder / 'results.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    if args.public_results:
        args.public_results.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'cases': len(cases), 'failures': failures, 'retained': str(folder)}))
    return bool(failures)


if __name__ == '__main__':
    raise SystemExit(main())
