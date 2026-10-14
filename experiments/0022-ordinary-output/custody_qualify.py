"""Bounded external caller-history snapshots and publication release ordering."""
import argparse
import copy
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

from qualify import Process, inventory, invoke
from restart_qualify import close, flags, load_actor, restart

PURPOSE = 'imageinfo-od11-custody-history-v1'
PRE = 'before-namespace-call'


def source_binding(binary):
    source_root = Path(__file__).resolve().parents[2]
    sources = list((source_root/'experiments/0032-windows-publication/src').glob('*.rs'))
    sources += [source_root/name for name in [
        'experiments/0032-windows-publication/Cargo.toml', 'experiments/0032-windows-publication/Cargo.lock',
        'experiments/0038-staging-cleanup/src/staging.rs', 'experiments/0038-staging-cleanup/src/disposition.rs',
        'experiments/0033-owner-rights/actor.py', 'experiments/0034-source-oplocks/qualify.py',
        'experiments/0022-ordinary-output/qualify.py', 'experiments/0022-ordinary-output/restart_qualify.py',
        'experiments/0022-ordinary-output/custody_qualify.py', 'experiments/0022-ordinary-output/custody_audit.py']]
    return {'binarySha256': hashlib.sha256(Path(binary).read_bytes()).hexdigest(),
            'sources': {str(p.relative_to(source_root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}}


def captured(context):
    return {'purpose': PURPOSE, 'events': [{'event': 'captured', 'context': context}]}


def extended(journal, event, context=None):
    result = copy.deepcopy(journal)
    item = {'event': event}
    if context is not None:
        item['context'] = context
    result['events'].append(item)
    return result


def call(binary, root, mode, request, folder, *, stop=None, at=None, late_extra=None, held_actor=None):
    p = Process([binary, root, mode], folder)
    wire = request if isinstance(request, str) else json.dumps(request, separators=(',', ':'))
    p.proc.stdin.write(wire+'\n')
    p.proc.stdin.flush()
    (folder.parent/(folder.name+'-request.private.json')).write_text(wire+'\n', encoding='utf-8')
    actors = []
    try:
        while True:
            try:
                event = p.next()
            except RuntimeError:
                if p.proc.poll() is None:
                    raise
                break
            flags([event])
            barrier = event.get('barrier')
            if held_actor and barrier == 'custody-before-write':
                name = 'rename' if held_actor == 'root-rename' else held_actor
                target = root if held_actor == 'root-rename' else root/'custody-1.record'
                try:
                    load_actor().act(name, target)
                    allowed = True
                    error = None
                except OSError as exception:
                    allowed = False
                    error = exception.winerror
                assert not allowed
                actors.append({'action': held_actor, 'allowed': allowed, 'winError': error})
                held_actor = None
            if late_extra and barrier == late_extra:
                (root/'foreign.marker').write_bytes(b'foreign-custody-extra')
                late_extra = None
            if stop and barrier == at:
                if stop == 'kill':
                    p.stop()
                    break
                p.controls.append(stop)
                p.proc.stdin.write(stop+'\n')
                p.proc.stdin.flush()
            elif barrier:
                p.send()
            if 'outcome' in event:
                break
        code = p.finish()
        events = [json.loads(line) for line in p.lines]
        flags(events)
        terminal = next((e for e in reversed(events) if 'outcome' in e), None)
        if stop == 'kill':
            assert code != 0 and terminal is None
        else:
            assert terminal is not None or code == 5
        return {'exitCode': code, 'terminal': terminal,
                'actors': actors,
                'barriers': [e['barrier'] for e in events if 'barrier' in e]}
    finally:
        close(p)


def save(binary, root, journal, identity, folder, **kw):
    return call(binary, root, 'ordinary-custody-save',
                {'journal': journal, 'expectedCustodyRoot': identity}, folder, **kw)


def inspect(binary, root, identity, folder):
    return call(binary, root, 'ordinary-custody-inspect',
                {'expectedCustodyRoot': identity}, folder)


def live_start(binary, root, folder):
    code, _ = invoke(binary, root, 'ordinary-prepare', folder/'prepare')
    assert code == 0
    worker = Process([binary, root, 'ordinary-write-through'], folder/'live')
    context = None
    while True:
        event = worker.next()
        flags([event])
        if 'callerContext' in event:
            context = event['callerContext']
        if event.get('barrier') == PRE:
            assert context and context['stage'] == 'before-publication'
            assert not context['stoppedBeforePublication']
            return worker, context
        assert 'outcome' not in event
        if 'barrier' in event:
            worker.send()


def save_ok(result):
    terminal = result['terminal']
    assert result['exitCode'] == 0 and terminal['outcome'] == 'custody-snapshot-recorded'
    return terminal['custodyRoot']


def inspect_ok(result, state):
    terminal = result['terminal']
    assert result['exitCode'] == 0 and terminal['outcome'] == 'custody-history-observed'
    assert terminal['custodyState'] == state
    return terminal.get('callerContextCandidate')


def rejected(result):
    assert result['exitCode'] == 5 or result['terminal']['outcome'] not in (
        'custody-snapshot-recorded', 'custody-history-observed')
    assert not (result['terminal'] or {}).get('callerContextCandidate')


def trial(binary, parent, name, *, branch='captured', change=None,
          stop=None, stop_at=None, late_extra=None, malformed=None, held_actor=None):
    folder = parent/name
    folder.mkdir()
    transaction = folder/'transaction.marker'
    custody = folder/'custody.marker'
    worker, context = live_start(binary, transaction, folder)
    journal = captured(context)
    # Ordinary Python opens do not share DELETE, so inventory while the worker
    # holds DELETE-capable candidate/record handles marks them inaccessible. Take
    # the comparable full snapshot only after this exact child exits.
    original = None
    calls = []
    identity = None
    released = False
    candidate = None
    history = ['original-blocked-before-publication']
    owned_action = None
    try:
        first = save(binary, custody, journal, None, folder/'save-1')
        calls.append(first)
        identity = save_ok(first)
        history.append('captured-snapshot-save-complete')
        assert transaction != custody and not custody.is_relative_to(transaction)
        if branch == 'stopped':
            worker.stop()
            assert worker.finish() != 0
            history.append('original-process-exit-confirmed-without-publication-release')
            # A held process object and wait establish this controller's own stop;
            # no publication continuation was sent after receiving PRE.
            journal = extended(journal, 'stop-confirmed-before-publication')
            result = save(binary, custody, journal, identity, folder/'save-2',
                          stop=stop, at=stop_at, late_extra=late_extra, held_actor=held_actor)
            calls.append(result)
            if not stop and not late_extra:
                save_ok(result)
                history.append('stop-attestation-snapshot-save-complete')
        elif branch in ['fenced', 'observed', 'renewed']:
            journal = extended(journal, 'publication-release-fenced')
            result = save(binary, custody, journal, identity, folder/'save-2',
                          stop=stop, at=stop_at, late_extra=late_extra, held_actor=held_actor)
            calls.append(result)
            if held_actor:
                assert len(result['actors']) == 1 and result['actors'][0]['action'] == held_actor
            if not stop and not late_extra:
                save_ok(result)
                history.append('release-fence-snapshot-save-complete')
            if branch in ['observed', 'renewed']:
                # Only the complete fence save success permits this one continue.
                save_ok(result)
                worker.send()
                released = True
                history.append('original-publication-continuation-sent')
                while True:
                    event = worker.next()
                    flags([event])
                    if 'callerContext' in event:
                        context = event['callerContext']
                    barrier = event.get('barrier')
                    if barrier == 'parent-flushed':
                        journal = extended(journal, 'publication-observed', context)
                        result = save(binary, custody, journal, identity, folder/'save-3')
                        calls.append(result)
                        save_ok(result)
                        if branch == 'observed':
                            break
                    elif barrier == 'observation-parent-flushed':
                        journal = extended(journal, 'observation-renewed', context)
                        result = save(binary, custody, journal, identity, folder/'save-4')
                        calls.append(result)
                        save_ok(result)
                        break
                    assert 'outcome' not in event
                    if barrier:
                        worker.send()
        if not worker.capture.exists():
            worker.stop()
            assert worker.finish() != 0
        assert (transaction/'output.marker').exists() == released
        original = inventory(transaction)
        assert original['source.marker']['sha256'] == context['sha256']
        before = inventory(custody)
        if change:
            target = custody/'custody-1.record'
            if change == 'truncated':
                target.write_bytes(target.read_bytes()[:-1])
            elif change == 'corrupt':
                target.write_bytes(b'{')
            elif change == 'replaced':
                data = target.read_bytes()
                target.rename(folder/'retained-old-custody.private.bin')
                # Ask the same admitted creation boundary to author matching bytes
                # with the exact private descriptor in a separate fixture root.
                # Moving that fresh leaf preserves its protected descriptor; no
                # ACL repair is attempted on the retained original or transaction.
                replacement_root = folder/'replacement-custody.marker'
                replacement = save(binary, replacement_root, journal, None, folder/'replacement-save')
                calls.append(replacement)
                save_ok(replacement)
                fresh_leaf = replacement_root/'custody-1.record'
                assert fresh_leaf.read_bytes() == data
                fresh_leaf.rename(target)
            elif change == 'extra':
                (custody/'foreign.marker').write_bytes(b'foreign-extra')
            elif change == 'missing-first':
                target.unlink()
            elif change == 'missing-latest':
                (custody/f'custody-{len(journal["events"])}.record').unlink()
            elif change in ['ads', 'link', 'readonly', 'dacl']:
                load_actor().act(change, target)
            elif change == 'wrong-root':
                identity = copy.deepcopy(identity)
                identity['identity'] = '0:0'
            elif change == 'stale-prefix':
                calls.append(save(binary, custody, captured(journal['events'][0]['context']),
                                  identity, folder/'save-stale'))
                rejected(calls[-1])
            else:
                raise AssertionError(change)
        if malformed:
            invalid = copy.deepcopy(journal)
            if malformed == 'stop-after-fence':
                invalid = extended(extended(captured(journal['events'][0]['context']),
                                            'publication-release-fenced'), 'stop-confirmed-before-publication')
            elif malformed == 'release-after-stop':
                invalid = extended(extended(captured(journal['events'][0]['context']),
                                            'stop-confirmed-before-publication'), 'publication-release-fenced')
            elif malformed == 'duplicate-capture':
                invalid['events'].append(copy.deepcopy(invalid['events'][0]))
            elif malformed == 'unknown-field':
                invalid['permission'] = True
            elif malformed == 'mismatched-context':
                invalid = extended(captured(journal['events'][0]['context']), 'publication-release-fenced')
                observed = copy.deepcopy(journal['events'][0]['context'])
                observed['stage'] = 'after-publication'
                observed['sha256'] = '0'*64
                invalid = extended(invalid, 'publication-observed', observed)
            result = save(binary, custody, invalid, identity, folder/'save-invalid')
            calls.append(result)
            rejected(result)
        before_inspect = inventory(custody)
        result = inspect(binary, custody, identity, folder/'inspect')
        calls.append(result)
        after = inventory(custody)
        assert before_inspect == after
        if change in ['truncated', 'corrupt', 'extra', 'missing-first', 'ads', 'link', 'readonly', 'dacl', 'wrong-root'] or late_extra:
            rejected(result)
        elif change == 'missing-latest':
            candidate = inspect_ok(result, 'captured-unconfirmed' if branch == 'stopped' else 'publication-release-uncertain')
            assert candidate is None
        elif stop:
            # A stopped snapshot writer never permits publication. A complete
            # fenced snapshot can still be observed, but grants no prune context.
            if result['terminal'] and result['terminal']['outcome'] == 'custody-history-observed':
                candidate = result['terminal'].get('callerContextCandidate')
                assert candidate is None
            else:
                rejected(result)
        else:
            states = {'captured': 'captured-unconfirmed', 'stopped': 'stop-attested-before-publication',
                      'fenced': 'publication-release-uncertain', 'observed': 'publication-observed',
                      'renewed': 'observation-renewed'}
            candidate = inspect_ok(result, states[branch])
            if branch in ['captured', 'fenced']:
                assert candidate is None
            elif branch == 'stopped':
                assert candidate['stage'] == 'before-publication' and candidate['stoppedBeforePublication']
            else:
                assert candidate['stage'] == 'after-publication' and not candidate['stoppedBeforePublication']
        # Storage inspection never mutates the editable transaction or repairs
        # custody files. A valid representation is still a caller trust premise.
        final_transaction = inventory(transaction)
        if not released:
            assert original == final_transaction
        assert original['source.marker'] == final_transaction['source.marker']
        if branch in ['stopped', 'renewed'] and not (change or stop or late_extra or malformed):
            action_mode = 'ordinary-restart-prune' if branch == 'stopped' else 'ordinary-restart-observe'
            owned_action = restart(binary, transaction, action_mode, candidate, folder/'owned-action')
            expected = 'owned-unpublished-handles-pruned' if branch == 'stopped' else 'output-observation-already-present'
            assert owned_action['outcome'] == expected
            after_owned_action = inventory(transaction)
            assert original['source.marker'] == after_owned_action['source.marker']
            if branch == 'stopped':
                assert sorted(after_owned_action) == ['source.marker']
            else:
                assert final_transaction == after_owned_action
        else:
            after_owned_action = final_transaction
        (folder/'inventories.private.json').write_text(json.dumps({
            'custodyBeforeChange': before, 'custodyBeforeInspect': before_inspect, 'custodyAfterInspect': after,
            'transactionBefore': original, 'transactionAfter': final_transaction,
            'afterOwnedAction': after_owned_action}, indent=2), encoding='utf-8')
        return {'id': name, 'branch': branch, 'change': change, 'malformed': malformed,
                'stop': stop, 'stopAt': stop_at, 'lateExtraAt': late_extra,
                'heldActor': held_actor,
                'publicationReleased': released, 'sourceRetained': True,
                'custodyInspectUnchanged': True, 'calls': calls,
                'supervisorHistory': history, 'ownedAction': owned_action,
                'candidateStage': candidate.get('stage') if candidate else None,
                'remainingCustodyLeaves': sorted(after), 'transactionLeaves': sorted(final_transaction)}
    finally:
        close(worker)


def run(binary, parent):
    binary = Path(binary).resolve()
    parent = Path(parent).resolve()
    parent.mkdir(parents=True, exist_ok=True)
    if os.name != 'nt':
        p = subprocess.run([binary, parent/'absent.marker', 'ordinary-custody-inspect'],
                           input='{}\n', capture_output=True, text=True, timeout=15)
        assert p.returncode == 5 and not (parent/'absent.marker').exists()
        print(json.dumps({'unsupportedPlatformRefused': True}))
        return
    root = Path(tempfile.mkdtemp(prefix='ordinary-custody-', dir=parent))
    (root/'source-binding.private.json').write_text(json.dumps(source_binding(binary), indent=2), encoding='utf-8')
    who = subprocess.run(['whoami', '/user', '/fo', 'csv', '/nh'], capture_output=True, check=True, timeout=15)
    sid = next(csv.reader(who.stdout.decode('utf-8', errors='replace').splitlines()))[-1]
    policy = subprocess.run(['icacls', str(root), '/inheritance:r', '/grant:r', '*'+sid+':(OI)(CI)F'],
                            capture_output=True, check=True, timeout=15)
    (root/'root-policy.private.txt').write_bytes(policy.stdout+policy.stderr)
    cases = []
    try:
        for branch in ['captured', 'stopped', 'fenced', 'observed', 'renewed']:
            cases.append(trial(binary, root, branch, branch=branch))
        for change in ['truncated', 'corrupt', 'replaced', 'extra', 'missing-first', 'ads', 'link',
                       'readonly', 'dacl', 'wrong-root', 'stale-prefix']:
            cases.append(trial(binary, root, 'change-'+change, change=change))
        for branch in ['stopped', 'observed']:
            cases.append(trial(binary, root, branch+'-missing-latest', branch=branch, change='missing-latest'))
        for malformed in ['stop-after-fence', 'release-after-stop', 'duplicate-capture', 'unknown-field', 'mismatched-context']:
            cases.append(trial(binary, root, 'history-'+malformed, malformed=malformed))
        for at in ['custody-before-write', 'custody-before-file-flush', 'custody-file-flushed', 'custody-parent-flushed']:
            for stop in ['cancel', 'fail', 'kill']:
                cases.append(trial(binary, root, stop+'-'+at, branch='fenced', stop=stop, stop_at=at))
        for at in ['custody-file-flushed', 'custody-parent-flushed']:
            cases.append(trial(binary, root, 'foreign-'+at, branch='fenced', late_extra=at))
        for action in ['write', 'delete', 'rename', 'root-rename']:
            cases.append(trial(binary, root, 'held-'+action, branch='fenced', held_actor=action))
        report = {'schemaVersion': 1, 'caseCount': len(cases), 'cases': cases,
                  'productionPublicationAllowed': False, 'enabledProfiles': 0}
        (root/'report.private.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps({'root': str(root), 'caseCount': len(cases)}))
    except BaseException:
        (root/'failed-report.private.json').write_text(json.dumps(cases, indent=2), encoding='utf-8')
        print('Retained attempt: '+str(root), file=__import__('sys').stderr)
        raise


if __name__ == '__main__':
    if not __debug__:
        raise RuntimeError('Qualification requires assertions')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', required=True)
    parser.add_argument('--parent', required=True)
    args = parser.parse_args()
    run(args.binary, args.parent)
