"""Check #0136's frozen finite evidence inventory; execute no product/shell."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/legacy-compatibility/shell-terminal-baseline'

# Frozen contract values: changing these requires a new, reviewed baseline.
RUNNERS = {'windows': 'windows-2025', 'linux': 'ubuntu-24.04', 'macos': 'macos-15'}
UNRUN = ['Windows PowerShell 5.1 and cmd.exe',
 'zsh, fish, sh and arbitrary shells',
 'interactive shell profiles, editing and completion',
 'guided/cascading menus (optional; guided requests currently refuse)',
 'non-Unicode UTF-8 JSONL wire paths',
 'arbitrary Unicode terminal cell rendering and screen-reader certification',
 'session cancellation/signal and native failing-stdin-handle behavior',
 'all other terminal widths, emulators and platform configurations']
SESSION = {'ticket': 116,
 'kind': 'actual-process-pipe-tests',
 'source': 'tests/cli_read_session.rs',
 'startup': 'tests/cli_session_startup.rs',
 'ciRun': 39043877139,
 'platforms': ['windows-2025', 'ubuntu-24.04', 'macos-15'],
 'scope': 'incremental ready/result flush, isolation, EOF/close, malformed/oversized framing, '
          'broken stdout; no cancellation or native failing-stdin claim'}
SLICES = [{'id': 'ST-REFRESH',
  'state': 'unrun-on-next-source',
  'environments': ['windows-2025', 'ubuntu-24.04', 'macos-15'],
  'commands': ['cargo build --locked --release',
               'python scripts/check_native_paths.py --binary <binary> --public-results '
               '<fresh-report>',
               'python scripts/check_command_shells.py --binary <binary> --public-results '
               '<fresh-report>',
               'python scripts/check_plain_terminals.py --binary <binary> --public-results '
               '<fresh-report>',
               'cargo test --locked --test cli_read_session --test cli_session_startup'],
  'bounds': '94 native-path rows; 32 shell rows; 24 terminal cases at 40/80 columns; exact '
            'existing session tests',
  'oracle': 'Existing checkers require exact applicable IDs, statuses, channels, native '
            'argv/input, fixture bytes and effects. Preserve failures and hashes; refresh only '
            'after all applicable observations pass.'},
 {'id': 'ST-NEW-COMMAND',
  'state': 'unrun',
  'environments': ['Windows PowerShell 7', 'Linux Bash', 'macOS Bash'],
  'commands': ['Extend authored ledgers for the exact newly advertised command before '
               'qualification'],
  'bounds': 'One new command; simple, spaces, Unicode and literal-metacharacter operands; two help '
            'spellings and 40/80 columns',
  'oracle': 'Bind actual shell witness argv/stdin separately from native effects; assert '
            'contextual help inventory, complete visible output, producer plainness and exact '
            'status/channel. Record unsupported operation refusals separately.'}]
REPORT_HASHES = {(137, 'windows'): 'b61baff3758b5932faef90a52758f5235ad618d8372a28bada5e02755513fdfa',
 (138, 'windows'): 'e857c693cf31436357c0a4acfa93f9a29bdea055599e72ca82464e1248fce56b',
 (137, 'linux'): '59c13a3eb80f2bf84cc192a88ca633e07daa289b5c002474bb3f556295fd07ef',
 (138, 'linux'): '09a50c57d2d5001585c3b3c7166601095a723b01ad289b0d28919985077b95cc',
 (137, 'macos'): 'd33eadb77833c66a8e48940cc6f25a956fce21ebcae386891f27f17a776fdf33',
 (138, 'macos'): 'bff4b6c6f063003b4bb6378e9c9b7044e2d16f9955fc75d8d5ff959408a58e88',
 (59, 'windows'): '428a685eef630fbae5a2c0006df658b01aead99bcc63c7b4387d743f156b5df0',
 (59, 'linux'): '3b3b60e59095e96b5e99c1f7a4c53a19ae34d4a8a2bbde1982aca40019ddbf45',
 (59, 'macos'): '65187f34ae14c978632a0af8e65d0f2ddb2832650e886821d87a0db27d00f3f7'}


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def check(ledger):
    assert ledger['schemaVersion'] == 1 and ledger['ticket'] == 136
    assert ledger['kind'] == 'finite-historical-baseline'
    assert ledger['helpMandatory'] is True and ledger['cascadingMenusOptional'] is True
    assert ledger['ciRun'] == 39043877139
    assert ledger['ciUrl'] == 'https://github.com/imageinfo/imageinfo/actions/runs/39043877139'
    assert ledger['sourceCommit'] == '622e39c22e7d6f1cca9d761e3597e149f5007afb'
    rows = ledger['reports']
    assert len(rows) == 9
    assert {(r['ticket'], r['platform']) for r in rows} == {
        (t, p) for t in (59, 137, 138) for p in ('windows', 'linux', 'macos')}
    for row in rows:
        ticket, platform = row['ticket'], row['platform']
        assert row['sha256'] == REPORT_HASHES[ticket, platform]
        if ticket == 59:
            assert 'runner' not in row
            expected_path = f'docs/legacy-compatibility/native-paths/{platform}.results.json'
        else:
            assert row['runner'] == RUNNERS[platform]
            kind = 'command-shells' if ticket == 137 else 'plain-terminals'
            expected_path = f'docs/legacy-compatibility/shell-terminal-baseline/{platform}-{kind}.json'
        assert row['path'] == expected_path
        path = ROOT / row['path']
        assert path.resolve().is_relative_to((ROOT / 'docs').resolve())
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row['sha256']
        result = read(path)
        assert result['binarySha256'] == row['binarySha256']
        assert result['platform'] == (('nt' if platform == 'windows' else 'posix')
                                      if ticket == 138 else platform)
        if ticket == 138:
            assert row['shellVersion'] is None and row['notApplicable'] == 0
        cases = result['cases']
        assert len({c['id'] for c in cases}) == len(cases)
        assert row['passed'] == sum(c.get('state') == 'passed' or c.get('passed') is True for c in cases)
        if row['ticket'] in (59, 137):
            assert result['shellVersion'] == row['shellVersion']
            assert row['notApplicable'] == sum(c['state'] == 'not-applicable' for c in cases)
            directory = 'native-paths' if row['ticket'] == 59 else 'command-shells'
            authored = read(ROOT / 'docs/legacy-compatibility' / directory / 'cases.json')
            assert [c['id'] for c in cases] == [c['id'] for c in authored['cases']]
            assert result['ledgerSha256'] == hashlib.sha256(
                (ROOT / 'docs/legacy-compatibility' / directory / 'cases.json').read_bytes()).hexdigest()
            for actual, expected in zip(cases, authored['cases']):
                applicable = row['platform'] in expected['platforms']
                assert actual['state'] == ('passed' if applicable else 'not-applicable')
                if applicable:
                    expected_status = (expected['expected'][row['platform']]['status']
                                       if row['ticket'] == 59 else expected['status'])
                    assert actual['status'] == expected_status
            expected_count = (70 if row['platform'] == 'windows' else 88) if row['ticket'] == 59 else (28 if row['platform'] == 'windows' else 32)
            assert row['passed'] == expected_count
        else:
            authored = read(ROOT / 'docs/legacy-compatibility/plain-terminals.cases.json')
            assert [c['id'] for c in cases] == [c['id'] for c in authored['cases']]
            assert len(cases) == 24 and result['helpInventoryComplete'] is True
            assert result['ledgerSha256'] == hashlib.sha256(
                (ROOT / 'docs/legacy-compatibility/plain-terminals.cases.json').read_bytes()).hexdigest()
            backend = 'windows-conpty' if row['platform'] == 'windows' else 'posix-pty'
            for actual, expected in zip(cases, authored['cases']):
                assert actual['passed'] is True
                observations = actual['observations']
                assert {(o['spelling'], o['columns']) for o in observations} == {
                    (i, width) for i in range(len(expected['argv'])) for width in (40, 80)}
                assert len(observations) == 2 * len(expected['argv'])
                assert all(o['backend'] == backend and o['status'] == expected['status']
                           and o['exactVisibleNonWhitespace'] is True for o in observations)
            assert sum(len(c['observations']) for c in cases) == 78
    assert ledger['sessionEvidence'] == SESSION
    assert all((ROOT / SESSION[k]).is_file() for k in ('source', 'startup'))
    assert ledger['unrun'] == UNRUN
    assert ledger['nextSlices'] == SLICES



def adversarial_controls(ledger):
    """Reject scope changes without executing any new environment."""
    mutations = [
        ('erased-unrun-limits', lambda v: v.update(unrun=['arbitrary'] * 8)),
        ('lost-menu-limit', lambda v: v['unrun'].__setitem__(3, 'menus qualified')),
        ('lost-wire-limit', lambda v: v['unrun'].__setitem__(4, 'wire paths qualified')),
        ('unknown-refresh-state', lambda v: v['nextSlices'][0].update(state='unrun-anything')),
        ('unknown-command-state', lambda v: v['nextSlices'][1].update(state='unrun-but-passed')),
        ('claimed-run', lambda v: v['nextSlices'][0].update(state='passed')),
        ('wrong-refresh-environment', lambda v: v['nextSlices'][0].update(environments=['fish'])),
        ('wrong-command-environment', lambda v: v['nextSlices'][1].update(environments=['cmd.exe'])),
        ('erased-bounds', lambda v: v['nextSlices'][0].update(bounds='unbounded')),
        ('erased-command-bounds', lambda v: v['nextSlices'][1].update(bounds='anything')),
        ('erased-oracle', lambda v: v['nextSlices'][1].update(oracle='trust output')),
        ('wrong-command', lambda v: v['nextSlices'][0].update(commands=['echo success'])),
        ('wrong-runner', lambda v: v['reports'][0].update(runner='ubuntu-24.04')),
        ('wrong-report-binding', lambda v: v['reports'][0].update(sha256='0' * 64)),
        ('wrong-report-path', lambda v: v['reports'][0].update(path=v['reports'][2]['path'])),
        ('wrong-session-platform', lambda v: v['sessionEvidence'].update(platforms=['fish'])),
        ('wrong-session-source', lambda v: v['sessionEvidence'].update(source='src/main.rs')),
        ('wrong-session-startup', lambda v: v['sessionEvidence'].update(startup='src/main.rs')),
        ('wrong-session-run', lambda v: v['sessionEvidence'].update(ciRun=1)),
        ('invented-session-scope', lambda v: v['sessionEvidence'].update(scope='all platforms')),
        ('wrong-source-revision', lambda v: v.update(sourceCommit='0' * 40)),
        ('wrong-ci-url', lambda v: v.update(ciUrl='https://example.com')),
        ('lost-mandatory-help', lambda v: v.update(helpMandatory=False)),
        ('mandatory-menus', lambda v: v.update(cascadingMenusOptional=False)),
    ]
    for name, mutate in mutations:
        changed = deepcopy(ledger)
        mutate(changed)
        try:
            check(changed)
        except AssertionError:
            continue
        raise AssertionError(f'adversarial control accepted: {name}')
    return len(mutations)


if __name__ == '__main__':
    ledger = read(BASE / 'ledger.v1.json')
    check(ledger)
    controls = adversarial_controls(ledger)
    print(f'0136: nine frozen reports, exact scope/manifests verified; {controls} adversarial controls refused')
