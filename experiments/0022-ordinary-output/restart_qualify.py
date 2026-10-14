"""Caller-bound restart marker actions; captures remain private and no RAW is used."""
import argparse
import csv
import json
import mmap
import os
from pathlib import Path
import subprocess
import tempfile

from qualify import Process, actor, inventory, invoke

MODES = ['ordinary-persistence-buffered', 'ordinary-flush-after-rename', 'ordinary-write-through']
FLAGS = ['committed', 'namespaceAcknowledged', 'repairAllowed', 'productionPublicationAllowed']
PRE = 'before-namespace-call'
POST = 'parent-flushed'
OBSERVED = 'observation-parent-flushed'


def flags(events):
    for event in events:
        assert all(not event.get(key, False) for key in FLAGS)


def close(p):
    p.stop()
    p.timer.cancel()
    if not p.capture.exists():
        p.finish()


def capture_context(binary, root, folder, mode, phase):
    """Capture authority from the live caller channel, never reconstruct from disk."""
    code, _ = invoke(binary, root, 'ordinary-prepare', folder/'prepare')
    assert code == 0
    p = Process([binary, root, mode], folder/'live')
    context = None
    try:
        while True:
            event = p.next()
            flags([event])
            if 'callerContext' in event:
                context = event['callerContext']
            if event.get('barrier') == phase:
                assert context is not None
                assert context['stage'] == ('before-publication' if phase == PRE else 'after-publication')
                assert len(context['records']) == (3 if phase == OBSERVED else 2)
                p.stop()
                assert p.finish() != 0
                # The caller adds this premise only after its own live child has
                # exited without receiving the publication-barrier continuation.
                assert not context.get('stoppedBeforePublication', False)
                if phase == PRE:
                    context['stoppedBeforePublication'] = True
                break
            if 'barrier' in event:
                p.send()
            assert 'outcome' not in event
        (folder/'caller-context.private.json').write_text(json.dumps(context, indent=2), encoding='utf-8')
        return context
    finally:
        close(p)


def restart(binary, root, mode, context, folder, *, stop=None, phase=None,
            held_actor=None, reinsert=False, late_extra=None):
    p = Process([binary, root, mode], folder)
    wire = context if isinstance(context, str) else json.dumps(context, separators=(',', ':'))
    p.proc.stdin.write(wire+'\n')
    p.proc.stdin.flush()
    (folder.parent/(folder.name+'-input.private.json')).write_text(wire+'\n', encoding='utf-8')
    actors = []
    removal = None
    try:
        while True:
            try:
                event = p.next()
            except RuntimeError:
                # Malformed/missing caller input may use the command's status-5 channel.
                if p.proc.poll() is None:
                    raise
                break
            flags([event])
            if 'ownedLeaf' in event:
                removal = event['ownedLeaf']
            barrier = event.get('barrier')
            if late_extra and barrier == late_extra:
                (root/'foreign.marker').write_bytes(b'foreign-after-record')
                late_extra = None
            if barrier == 'restart-guarded' and held_actor:
                name, role = held_actor
                target = root if role == 'root' else root/(role+'.marker')
                result = actor('rename' if role == 'root' else name, target, folder.parent/'actor')
                assert not result['allowed']
                actors.append({'action': name, 'role': role, 'allowed': False, 'winError': result['winError']})
            if barrier == 'restart-file-removed' and reinsert:
                assert removal in ['prepared.record', 'intent.record', 'candidate.marker']
                assert not (root/removal).exists()
                (root/removal).write_bytes(b'foreign-reinserted')
                reinsert = False
            if barrier == phase and stop:
                if stop == 'kill':
                    p.stop()
                    break
                p.controls.append(stop)
                p.proc.stdin.write(stop+'\n')
                p.proc.stdin.flush()
                continue
            if barrier:
                p.send()
            if 'outcome' in event:
                break
        code = p.finish()
        events = [json.loads(line) for line in p.lines]
        flags(events)
        terminal = next((event for event in reversed(events) if 'outcome' in event), None)
        if stop == 'kill':
            assert code != 0 and terminal is None
        else:
            assert terminal is not None or code == 5
        return {'exitCode': code, 'outcome': terminal['outcome'] if terminal else None,
                'terminal': terminal, 'actors': actors, 'barriers': [e['barrier'] for e in events if 'barrier' in e]}
    finally:
        close(p)


def trial(binary, parent, name, phase=PRE, mode=MODES[1], change=None,
          stop=None, stop_phase=None, held_actor=None, reinsert=False, reader=False,
          preexisting=None, late_extra=None):
    folder = parent/name
    folder.mkdir()
    root = folder/'transaction.marker'
    context = capture_context(binary, root, folder, mode, phase)
    action = 'ordinary-restart-prune' if phase == PRE else 'ordinary-restart-observe'
    if change == 'missing-context':
        context = ''
    elif change == 'malformed-context':
        context = '{'
    elif change == 'context-identity':
        context['candidate']['identity'] = '0:0'
    elif change == 'context-digest':
        context['sha256'] = '0'*64
    elif change == 'context-record-digest':
        context['records'][0]['sha256'] = '0'*64
    elif change == 'context-stage':
        context['stage'] = 'after-publication' if phase == PRE else 'before-publication'
    elif change == 'context-purpose':
        context['purpose'] = 'untrusted-record-derived-context'
    elif change == 'context-unknown':
        context['repairAllowed'] = True
    elif change == 'context-unattested':
        context['stoppedBeforePublication'] = False
    elif change == 'context-false-stop':
        context['stoppedBeforePublication'] = True
    elif change == 'record-corrupt':
        (root/'intent.record').write_bytes(b'corrupt-record')
    elif change == 'record-replaced':
        path = root/'prepared.record'
        data = path.read_bytes()
        # Retain the old object under a different name: ID reuse cannot explain success.
        path.rename(folder/'retained-old-record.private.bin')
        path.write_bytes(data)
    elif change == 'record-missing':
        (root/'intent.record').unlink()
    elif change == 'candidate-replaced':
        path = root/'candidate.marker'
        path.rename(folder/'retained-old-candidate.private.bin')
        path.write_bytes(b'3'*65536)
    elif change == 'source-edit':
        (root/'source.marker').write_bytes(b'4'*65536)
    elif change == 'output-edit':
        (root/'output.marker').write_bytes(b'4'*65536)
    elif change == 'candidate-property':
        assert actor('mtime', root/'candidate.marker', folder/'property-actor')['allowed']
    elif change == 'source-property':
        assert actor('mtime', root/'source.marker', folder/'property-actor')['allowed']
    elif change == 'output-property':
        assert actor('mtime', root/'output.marker', folder/'property-actor')['allowed']
    elif change == 'collision':
        (root/'output.marker').write_bytes(b'foreign-output')
    elif change == 'extra':
        (root/'foreign.marker').write_bytes(b'foreign-extra')
    elif change == 'observation-collision':
        (root/'observation.record').write_bytes(b'foreign-record')
    elif change in ['record-ads', 'record-link', 'record-dacl']:
        # The CLI actor intentionally limits its public entry point to marker
        # leaves. This explicit private fixture uses the same reviewed actor on
        # the caller-bound authored intent record, never a caller-supplied path.
        record_actor = load_actor()
        record_actor.act(change[7:], root/'intent.record')
        (folder/'record-actor.private.json').write_text(json.dumps({'action': change, 'allowed': True}), encoding='utf-8')
    before = inventory(root)
    reader_handle = None
    writable_handle = None
    writable_map = None
    if reader:
        # An independent compatible reader can postpone actual deletion despite
        # creator-held disposition. Leave this handle open through terminal output.
        reader_actor = load_actor()
        reader_handle = reader_actor.open(root/'candidate.marker', 1)
    if preexisting:
        writable_handle = (root/('candidate.marker' if phase == PRE else 'output.marker')).open('r+b')
        if preexisting == 'writable-map':
            writable_map = mmap.mmap(writable_handle.fileno(), 0, access=mmap.ACCESS_WRITE)
            writable_handle.close()
    try:
        result = restart(binary, root, action, context, folder/'restart', stop=stop,
                         phase=stop_phase, held_actor=held_actor, reinsert=reinsert, late_extra=late_extra)
        after = inventory(root)
    finally:
        if reader_handle is not None:
            reader_actor.k.CloseHandle(reader_handle)
        if writable_map is not None:
            writable_map.close()
        if writable_handle is not None and not writable_handle.closed:
            writable_handle.close()
    after_release = inventory(root)
    assert (root/'source.marker').exists()
    if phase != PRE:
        assert (root/'output.marker').exists()
        assert before['output.marker'] == after['output.marker'] == after_release['output.marker']
    if change or preexisting:
        assert result['outcome'] == 'restart-refused-before-effects' or result['exitCode'] == 5
        assert before == after == after_release
    elif late_extra:
        assert result['outcome'] == 'restart-partial-or-uncertain'
        assert (root/'foreign.marker').read_bytes() == b'foreign-after-record'
        assert (root/'observation.record').exists()
        assert all(after[key] == value for key, value in before.items())
        assert sorted(after) == sorted([*before, 'observation.record', 'foreign.marker'])
    elif not stop and not reinsert and not reader:
        expected = 'owned-unpublished-handles-pruned' if phase == PRE else (
            'output-observation-already-present' if phase == OBSERVED else 'output-observation-recorded-recovery-required')
        assert result['outcome'] == expected
        if phase == PRE:
            assert sorted(after) == ['source.marker']
        elif phase == OBSERVED:
            assert before == after
        else:
            assert sorted(after) == sorted([*before, 'observation.record'])
            assert all(after[key] == value for key, value in before.items())
    elif reinsert:
        assert result['outcome'] == 'restart-partial-or-uncertain'
        assert any(path.read_bytes() == b'foreign-reinserted' for path in root.iterdir() if path.is_file())
    elif stop and stop_phase in ['restart-guarded', 'restart-before-remove', 'restart-before-record']:
        assert before == after
    elif stop and stop_phase == 'restart-file-removed':
        assert len(after) == len(before)-1
        assert all(before[key] == value for key, value in after.items())
        if stop != 'kill':
            assert result['outcome'] == 'restart-partial-or-uncertain'
    elif stop and stop_phase == 'restart-record-file-flushed':
        assert sorted(after) == sorted([*before, 'observation.record'])
        assert all(after[key] == value for key, value in before.items())
        if stop != 'kill':
            assert result['outcome'] == 'restart-partial-or-uncertain'
    elif reader:
        assert result['outcome'] == 'owned-unpublished-handles-pruned'
        assert result['terminal']['cleanupPending'] == ('candidate.marker' in after)
        assert result['terminal']['ownedHandlesRemoved'] == 3
        assert 'candidate.marker' not in after_release
        assert sorted(after_release) == ['source.marker']
    assert before['source.marker'] == after['source.marker'] == after_release['source.marker']
    snapshots = {'before': before, 'after': after, 'afterReaderRelease': after_release}
    (folder/'inventories.private.json').write_text(json.dumps(snapshots, indent=2), encoding='utf-8')
    result.update({'id': name, 'liveMode': mode, 'liveStop': phase, 'change': change,
                   'stop': stop, 'stopPhase': stop_phase, 'foreignReinsertion': reinsert,
                   'readerDeferral': reader, 'sourceRetained': True, 'outputRetained': phase != PRE,
                   'preexisting': preexisting, 'lateExtraAt': late_extra,
                   'unchanged': before == after, 'remainingLeaves': sorted(after_release),
                   'remainingDirectoryEntries': sorted(path.name for path in root.iterdir())})
    return result


def load_actor():
    from importlib.util import spec_from_file_location, module_from_spec
    path = Path(__file__).resolve().parent.parent/'0033-owner-rights'/'actor.py'
    spec = spec_from_file_location('explicit_fixture_actor', path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Actor()


def run(binary, parent):
    binary = Path(binary).resolve()
    parent = Path(parent).resolve()
    parent.mkdir(parents=True, exist_ok=True)
    if os.name != 'nt':
        p = subprocess.run([binary, parent/'absent.marker', 'ordinary-restart-prune'],
                           input='{}\n', capture_output=True, text=True, timeout=15)
        assert p.returncode == 5 and not (parent/'absent.marker').exists()
        print(json.dumps({'unsupportedPlatformRefused': True}))
        return
    root = Path(tempfile.mkdtemp(prefix='ordinary-restart-', dir=parent))
    who = subprocess.run(['whoami', '/user', '/fo', 'csv', '/nh'], capture_output=True, check=True, timeout=15)
    sid = next(csv.reader(who.stdout.decode('utf-8', errors='replace').splitlines()))[-1]
    assert sid.startswith('S-1-5-') and all(v.isdigit() for v in sid[2:].split('-'))
    policy = subprocess.run(['icacls', str(root), '/inheritance:r', '/grant:r', '*'+sid+':(OI)(CI)F'],
                            capture_output=True, check=True, timeout=15)
    (root/'root-policy.private.txt').write_bytes(policy.stdout+policy.stderr)
    cases = []
    try:
        for mode in MODES:
            for phase in [PRE, POST, OBSERVED]:
                cases.append(trial(binary, root, mode+'-'+phase, phase, mode))
        for change in ['missing-context', 'malformed-context', 'context-identity', 'context-digest',
                       'context-record-digest', 'context-stage', 'context-purpose', 'context-unknown',
                       'context-unattested',
                       'record-corrupt', 'record-replaced', 'record-missing', 'candidate-replaced',
                       'source-edit', 'candidate-property', 'source-property', 'collision', 'extra']:
            cases.append(trial(binary, root, 'prune-'+change, change=change))
        for change in ['context-stage', 'context-false-stop', 'record-corrupt', 'source-edit', 'output-edit',
                       'output-property', 'observation-collision', 'extra']:
            cases.append(trial(binary, root, 'observe-'+change, POST, change=change))
        for phase, role in [(PRE, 'candidate'), (POST, 'output')]:
            for action in ['write', 'rename']:
                cases.append(trial(binary, root, 'held-'+role+'-'+action, phase, held_actor=(action, role)))
        cases.append(trial(binary, root, 'held-root-rename', held_actor=('rename', 'root')))
        for phase, barrier in [(PRE, 'restart-before-remove'), (PRE, 'restart-file-removed'),
                               (POST, 'restart-before-record'), (POST, 'restart-record-file-flushed')]:
            for stop in ['cancel', 'fail', 'kill']:
                cases.append(trial(binary, root, stop+'-'+barrier, phase, stop=stop, stop_phase=barrier))
        cases.append(trial(binary, root, 'foreign-reinsertion', reinsert=True))
        cases.append(trial(binary, root, 'reader-deferral', reader=True))
        for kind in ['writable-handle', 'writable-map']:
            cases.append(trial(binary, root, 'preexisting-'+kind, preexisting=kind))
        for change in ['record-ads', 'record-link', 'record-dacl']:
            cases.append(trial(binary, root, 'prune-'+change, change=change))
        for barrier in ['restart-record-file-flushed', 'restart-record-parent-flushed']:
            cases.append(trial(binary, root, 'foreign-extra-'+barrier, POST, late_extra=barrier))
        report = {'schemaVersion': 1, 'caseCount': len(cases), 'cases': cases,
                  'productionPublicationAllowed': False, 'enabledProfiles': 0}
        (root/'report.private.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
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
