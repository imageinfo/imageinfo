"""Finite native marker receipt observations; no profile or production authority."""
import argparse
import copy
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/'0022-ordinary-output'))
from qualify import Process, inventory, invoke
from restart_qualify import close, flags, load_actor, restart
from custody_qualify import captured, extended, save, save_ok

PHASES = ['installed-file-flushed', 'parent-flushed', 'observation-parent-flushed',
          'receipt-written', 'receipt-file-flushed', 'receipt-parent-flushed', 'final-checked']
SUCCESS = 'observed-receipt-recovery-required'


def binding(binary):
    repo = HERE.parents[1]
    paths = list((repo/'experiments/0032-windows-publication/src').glob('*.rs'))
    for relative in ['experiments/0032-windows-publication/Cargo.toml',
                     'experiments/0032-windows-publication/Cargo.lock',
                     'experiments/0038-staging-cleanup/src/staging.rs',
                     'experiments/0038-staging-cleanup/src/disposition.rs',
                     'experiments/0033-owner-rights/actor.py',
                     'experiments/0034-source-oplocks/qualify.py',
                     'experiments/0022-ordinary-output/qualify.py',
                     'experiments/0022-ordinary-output/restart_qualify.py',
                     'experiments/0022-ordinary-output/custody_qualify.py',
                     'experiments/0046-namespace-receipt/qualify.py',
                     'experiments/0046-namespace-receipt/audit.py']:
        paths.append(repo/relative)
    return {'workerSha256': hashlib.sha256(Path(binary).read_bytes()).hexdigest(),
            'sources': {str(p.relative_to(repo)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}


def perform_actor(action, target):
    try:
        load_actor().act(action, target)
        return {'action': action, 'allowed': True, 'winError': None}
    except OSError as error:
        return {'action': action, 'allowed': False, 'winError': error.winerror}


def inspect(binary, transaction, context, folder, *, action=None, role=None):
    process = Process([binary, transaction, 'ordinary-receipt-inspect'], folder)
    wire = context if isinstance(context, str) else json.dumps(context, separators=(',', ':'))
    (folder.parent/(folder.name+'-input.private.json')).write_text(wire+'\n', encoding='utf-8')
    process.proc.stdin.write(wire+'\n')
    process.proc.stdin.flush()
    actors = []
    try:
        while True:
            try:
                event = process.next()
            except RuntimeError:
                if process.proc.poll() is None:
                    raise
                break
            flags([event])
            if event.get('barrier') == 'receipt-inspect-guarded' and action:
                target = transaction if role == 'root' else transaction/role
                result = perform_actor(action, target)
                assert result['allowed'] == (action not in ['write', 'delete', 'rename'])
                actors.append(result)
            if 'barrier' in event:
                process.send()
            if 'outcome' in event:
                break
        code = process.finish()
        events = [json.loads(line) for line in process.lines]
        terminal = next((e for e in reversed(events) if 'outcome' in e), None)
        flags(events)
        assert terminal or code == 5
        return {'exitCode': code, 'terminal': terminal, 'actors': actors}
    finally:
        close(process)


def trial(binary, parent, name, *, phase=None, stop=None, change=None,
          action=None, role=None, inspect_change=None, inspect_action=None,
          mode='ordinary-receipt'):
    folder = parent/name
    folder.mkdir()
    transaction = folder/'transaction.marker'
    custody = folder/'custody.marker'
    code, _ = invoke(binary, transaction, 'ordinary-prepare', folder/'prepare')
    assert code == 0
    source_before = inventory(transaction)['source.marker']
    worker = Process([binary, transaction, mode], folder/'worker')
    context = None
    before_context = None
    receipt_context = None
    journal = None
    custody_root = None
    history = []
    actors = []
    mutated = False
    try:
        while True:
            event = worker.next()
            flags([event])
            if 'callerContext' in event:
                context = event['callerContext']
            if 'receiptContext' in event:
                receipt_context = event['receiptContext']
            barrier = event.get('barrier')
            if barrier == 'before-namespace-call':
                assert context and context['stage'] == 'before-publication'
                before_context = copy.deepcopy(context)
                history.append('original-blocked-before-publication')
                journal = captured(context)
                custody_root = save_ok(save(binary, custody, journal, None, folder/'save-captured'))
                history.append('captured-snapshot-save-complete')
                journal = extended(journal, 'publication-release-fenced')
                save_ok(save(binary, custody, journal, custody_root, folder/'save-fence'))
                history.append('release-fence-snapshot-save-complete')
                history.append('original-publication-continuation-sent')
            if barrier == 'parent-flushed':
                assert context and context['stage'] == 'after-publication'
                journal = extended(journal, 'publication-observed', context)
                save_ok(save(binary, custody, journal, custody_root, folder/'save-observed'))
                history.append('publication-observed-snapshot-save-complete')
            if barrier == 'observation-parent-flushed':
                assert len(context['records']) == 3
                journal = extended(journal, 'observation-renewed', context)
                save_ok(save(binary, custody, journal, custody_root, folder/'save-renewed'))
                history.append('observation-renewed-snapshot-save-complete')
            if barrier == phase and not mutated:
                mutated = True
                if change in ['receipt-winner', 'extra']:
                    leaf = 'receipt.record' if change == 'receipt-winner' else 'foreign.marker'
                    (transaction/leaf).write_bytes(b'foreign-receipt-winner')
                if action:
                    target = transaction if role == 'root' else transaction/role
                    result = perform_actor(action, target)
                    if action in ['write', 'delete', 'rename']:
                        assert not result['allowed']
                    else:
                        assert result['allowed']
                    actors.append(result)
                if stop == 'kill':
                    worker.stop()
                    break
                if stop:
                    worker.controls.append(stop)
                    worker.proc.stdin.write(stop+'\n')
                    worker.proc.stdin.flush()
                    continue
            if barrier:
                worker.send()
            if 'outcome' in event:
                break
        code = worker.finish()
        events = [json.loads(line) for line in worker.lines]
        flags(events)
        terminal = next((e for e in reversed(events) if 'outcome' in e), None)
        if stop == 'kill':
            assert code != 0 and terminal is None
        else:
            assert code == 0 and terminal
        if phase:
            assert mutated
        if mode == 'ordinary-receipt-short-record':
            assert terminal['outcome'] != SUCCESS
            assert receipt_context is None
            assert (transaction/'receipt.record').exists()
            try:
                json.loads((transaction/'receipt.record').read_text(encoding='utf-8'))
            except json.JSONDecodeError:
                pass
            else:
                raise AssertionError('Producer fault must leave a malformed partial record')
        elif not stop and not change and not (action and action not in ['write', 'delete', 'rename']):
            assert terminal['outcome'] == SUCCESS, terminal
        elif terminal:
            assert terminal['outcome'] != SUCCESS, terminal
        try:
            assert (transaction/'source.marker').read_bytes() == b'3'*65536
        except PermissionError:
            assert role == 'source.marker' and action == 'dacl'
        assert source_before == inventory(transaction)['source.marker'] or role == 'source.marker' and action in ['mtime', 'readonly', 'ads', 'link', 'dacl']
        assert (transaction/'output.marker').read_bytes() == b'3'*65536
        if change == 'receipt-winner':
            assert (transaction/'receipt.record').read_bytes() == b'foreign-receipt-winner'
        if change == 'extra':
            assert (transaction/'foreign.marker').read_bytes() == b'foreign-receipt-winner'
        legacy_before = inventory(transaction)
        legacy_code, legacy_events = invoke(binary, transaction, 'ordinary-inspect', folder/'legacy-inspect')
        assert legacy_code == 0 and inventory(transaction) == legacy_before
        if (transaction/'receipt.record').exists():
            assert legacy_events[-1]['outcome'] != 'matching-output-recovery-required'
        legacy_restart = None
        if receipt_context:
            legacy_restart = restart(binary, transaction, 'ordinary-restart-observe',
                                     receipt_context['prior'], folder/'legacy-restart')
            assert legacy_restart['outcome'] not in ['output-observation-recorded-recovery-required',
                                                      'output-observation-already-present']
            assert inventory(transaction) == legacy_before
        inspection = None
        before = after = None
        if receipt_context:
            external = copy.deepcopy(receipt_context)
            if inspect_change == 'missing':
                external = ''
            elif inspect_change == 'malformed':
                external = '{'
            elif inspect_change == 'stale':
                external['prior'] = before_context
            elif inspect_change == 'identity':
                external['receipt']['info']['identity'] = '0:0'
            elif inspect_change == 'digest':
                external['receipt']['sha256'] = '0'*64
            elif inspect_change == 'prior-digest':
                external['prior']['sha256'] = '0'*64
            elif inspect_change == 'unknown-authority':
                external['committed'] = True
            elif inspect_change == 'receipt-corrupt':
                (transaction/'receipt.record').write_bytes(b'{')
            elif inspect_change == 'receipt-replaced':
                leaf = transaction/'receipt.record'
                data = leaf.read_bytes()
                leaf.rename(folder/'retained-old-receipt.private.bin')
                leaf.write_bytes(data)
            elif inspect_change == 'receipt-missing':
                (transaction/'receipt.record').unlink()
            elif inspect_change == 'intent-corrupt':
                (transaction/'intent.record').write_bytes(b'{')
            elif inspect_change == 'source-edit':
                (transaction/'source.marker').write_bytes(b'4'*65536)
            elif inspect_change == 'output-edit':
                (transaction/'output.marker').write_bytes(b'4'*65536)
            elif inspect_change == 'extra':
                (transaction/'foreign.marker').write_bytes(b'foreign')
            elif inspect_change in ['mtime', 'readonly', 'ads', 'link', 'dacl']:
                assert perform_actor(inspect_change, transaction/'receipt.record')['allowed']
            before = inventory(transaction)
            inspection = inspect(binary, transaction, external, folder/'inspect',
                                 action=inspect_action, role=role)
            after = inventory(transaction)
            if inspect_action == 'mtime':
                expected = copy.deepcopy(before)
                assert before[role]['mtime'] != after[role]['mtime']
                expected[role]['mtime'] = after[role]['mtime']
                assert expected == after
            else:
                assert before == after
            accepted = (inspection['terminal'] or {}).get('outcome') == SUCCESS
            if inspect_change or change or (action or inspect_action) and (action or inspect_action) not in ['write', 'delete', 'rename']:
                assert not accepted
            elif not stop:
                assert accepted, inspection
        (folder/'inventories.private.json').write_text(json.dumps({'sourceBefore': source_before,
            'beforeInspect': before, 'afterInspect': after}, indent=2), encoding='utf-8')
        (folder/'receipt-context.private.json').write_text(json.dumps(receipt_context, indent=2), encoding='utf-8')
        return {'id': name, 'phase': phase, 'stop': stop, 'change': change, 'action': action,
                'role': role, 'mode': mode, 'inspectChange': inspect_change, 'inspectAction': inspect_action,
                'supervisorHistory': history, 'terminal': terminal, 'exitCode': code,
                'actors': actors, 'inspection': inspection, 'legacyInspection': legacy_events[-1],
                'legacyRestart': legacy_restart, 'sourceRetained': True,
                'rootRetained': transaction.is_dir(), 'inspectionUnchanged': before == after,
                'receiptContextCaptured': receipt_context is not None,
                'transactionLeaves': sorted(p.name for p in transaction.iterdir())}
    finally:
        close(worker)


def run(binary, parent):
    binary = Path(binary).resolve()
    parent = Path(parent).resolve()
    parent.mkdir(parents=True, exist_ok=True)
    if os.name != 'nt':
        for mode in ['ordinary-receipt', 'ordinary-receipt-inspect']:
            absent = parent/(mode+'.marker')
            result = subprocess.run([binary, absent, mode], input='\n', capture_output=True,
                                    text=True, timeout=15)
            assert result.returncode == 5 and not absent.exists()
            assert json.loads(result.stderr)['diagnostic'] == 'WINDOWS_BACKEND_UNVERIFIED'
        print(json.dumps({'unsupportedPlatformRefused': True, 'artifactsCreated': 0}))
        return
    root = Path(tempfile.mkdtemp(prefix='namespace-receipt-', dir=parent))
    who = subprocess.run(['whoami', '/user', '/fo', 'csv', '/nh'], capture_output=True, check=True, timeout=15)
    sid = next(csv.reader(who.stdout.decode('utf-8', errors='replace').splitlines()))[-1]
    assert sid.startswith('S-1-5-') and all(v.isdigit() for v in sid[2:].split('-'))
    policy = subprocess.run(['icacls', str(root), '/inheritance:r', '/grant:r', '*'+sid+':(OI)(CI)F'],
                            capture_output=True, check=True, timeout=15)
    (root/'root-policy.private.txt').write_bytes(policy.stdout+policy.stderr)
    (root/'source-binding.private.json').write_text(json.dumps(binding(binary), indent=2), encoding='utf-8')
    cases = []
    try:
        cases.append(trial(binary, root, 'success'))
        cases.append(trial(binary, root, 'short-record-producer', mode='ordinary-receipt-short-record'))
        for phase in PHASES:
            for stop in ['cancel', 'fail', 'kill']:
                cases.append(trial(binary, root, stop+'-'+phase, phase=phase, stop=stop))
        for phase in ['observation-parent-flushed', 'receipt-written', 'receipt-file-flushed', 'receipt-parent-flushed', 'final-checked']:
            cases.append(trial(binary, root, 'extra-'+phase, phase=phase, change='extra'))
        cases.append(trial(binary, root, 'foreign-receipt-winner', phase='observation-parent-flushed', change='receipt-winner'))
        for role in ['source.marker', 'output.marker', 'receipt.record', 'root']:
            for action in ['write', 'delete', 'rename'] if role != 'root' else ['rename']:
                cases.append(trial(binary, root, 'held-'+role+'-'+action, phase='receipt-written', action=action, role=role))
        for phase in ['observation-parent-flushed', 'receipt-written', 'receipt-file-flushed', 'receipt-parent-flushed']:
            for action in ['mtime', 'ads', 'link']:
                cases.append(trial(binary, root, action+'-'+phase, phase=phase, action=action, role='output.marker'))
        for role in ['source.marker', 'receipt.record']:
            for action in ['mtime', 'readonly', 'ads', 'link', 'dacl']:
                cases.append(trial(binary, root, role+'-property-'+action,
                                   phase='receipt-written', action=action, role=role))
        for change in ['missing', 'malformed', 'stale', 'identity', 'digest', 'prior-digest',
                       'unknown-authority', 'receipt-corrupt', 'receipt-replaced', 'receipt-missing',
                       'intent-corrupt', 'source-edit', 'output-edit', 'extra',
                       'mtime', 'readonly', 'ads', 'link', 'dacl']:
            cases.append(trial(binary, root, 'inspect-'+change, inspect_change=change))
        for role in ['source.marker', 'output.marker', 'receipt.record', 'root']:
            for action in ['write', 'delete', 'rename'] if role != 'root' else ['rename']:
                cases.append(trial(binary, root, 'inspect-held-'+role+'-'+action,
                                   inspect_action=action, role=role))
        for role in ['source.marker', 'output.marker', 'receipt.record']:
            cases.append(trial(binary, root, 'inspect-late-mtime-'+role,
                               inspect_action='mtime', role=role))
        assert binding(binary) == json.loads((root/'source-binding.private.json').read_text(encoding='utf-8'))
        (root/'report.private.json').write_text(json.dumps({'caseCount': len(cases), 'cases': cases}, indent=2), encoding='utf-8')
        print(json.dumps({'root': str(root), 'caseCount': len(cases)}))
    except BaseException:
        (root/'failed-report.private.json').write_text(json.dumps(cases, indent=2), encoding='utf-8')
        print('Retained attempt: '+str(root), file=sys.stderr)
        raise


if __name__ == '__main__':
    if not __debug__:
        raise RuntimeError('Qualification requires assertions')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', required=True)
    parser.add_argument('--parent', required=True)
    args = parser.parse_args()
    run(args.binary, args.parent)
