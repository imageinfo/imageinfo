"""Audit caller-directed guest restart captures without publishing private identities."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path

from guest_qualify import assert_reports, fresh_bugcheck, verify_guest_token

FLAGS = ['committed', 'namespaceAcknowledged', 'repairAllowed', 'productionPublicationAllowed']
MARKER_HASH = hashlib.sha256(b'3' * 65536).hexdigest()
SCENARIOS = ['unpublished-nmi', 'published-nmi', 'unpublished-kill']


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while block := stream.read(65536):
            digest.update(block)
    return digest.hexdigest()


def safe(event):
    assert all(event[key] is False for key in FLAGS)


def files(result):
    entries = result['files']
    assert len(entries) == len({entry['name'] for entry in entries})
    assert all(not entry.get('inaccessible') for entry in entries)
    return {entry['name']: entry for entry in entries}


def terminal(result, expected):
    events = assert_reports(result)
    assert events and events[-1]['outcome'] == expected
    return events[-1]


def marker(entry):
    assert entry['size'] == 65536 and entry['sha256'] == MARKER_HASH


def fault(folder, kind, phase, bugchecks):
    value = read(folder / 'reboot.private.json')
    assert value['fault'] == kind
    barrier = value['barrier']
    assert barrier['path'] == '/event' and barrier['value']['event']['barrier'] == phase
    safe(barrier['value']['event'])
    before, after = value['before'], value['after']
    assert before['path'] == after['path'] == '/hello'
    assert before['at'] <= barrier['at'] < after['at']
    for hello in [before, after]:
        verify_guest_token(hello['value'])
        assert hello['value']['build'] == '26300'
    boots = [datetime.datetime.fromisoformat(h['value']['boot']).timestamp() for h in [before, after]]
    assert abs(boots[1] - boots[0]) > 5
    assert read(folder / 'relaunch.private.json')['exitCode'] == 0
    events = value['events'].get('events') or []
    if isinstance(events, dict):
        events = [events]
    fresh = [event for event in events if fresh_bugcheck(event, barrier['at'])]
    if kind == 'nmi':
        assert fresh and (folder / 'bugcheck.png').is_file()
        # Historical bugcheck events cannot satisfy more than one injected fault.
        keys = {(event['TimeCreated'], event['Message']) for event in fresh}
        assert not keys.intersection(bugchecks)
        bugchecks.update(keys)
    else:
        assert not fresh
    return barrier


def audit(root, binary, public):
    root = Path(root).resolve()
    binary = Path(binary).resolve()
    assert not (root / 'incomplete.private.json').exists()
    summary = read(root / 'summary.private.json')
    assert [case['id'] for case in summary['cases']] == [
        'unpublished-nmi', 'published-nmi-recovery-kill', 'unpublished-kill-recovery-nmi']
    assert [summary[key] for key in ['liveFaults', 'recoveryFaults', 'nmiFaults', 'emulatorTerminationFaults']] == [3, 2, 3, 2]
    assert summary['committed'] is False and summary['productionPublicationAllowed'] is False
    initial = read(root / 'initial-hello.private.json')
    verify_guest_token(initial['value'])
    binding = read(root / 'source-binding.private.json')
    assert binding['workerSha256'] == sha(binary)
    source_root = Path(__file__).resolve().parents[2]
    required = {
        'experiments/0032-windows-publication/src/ordinary.rs',
        'experiments/0032-windows-publication/src/restart_context.rs',
        'experiments/0032-windows-publication/src/ordinary_record.rs',
        'experiments/0038-staging-cleanup/src/disposition.rs',
        'experiments/0022-ordinary-output/restart_guest.py',
        'experiments/0022-ordinary-output/windows_guest.py',
        'experiments/0022-ordinary-output/guest_qualify.py',
    }
    assert required.issubset(binding['sources'])
    assert sha(root / 'driver-source.private.py') == binding['sources']['experiments/0022-ordinary-output/restart_guest.py']
    for relative, expected in binding['sources'].items():
        path = (source_root / relative).resolve()
        assert path.is_relative_to(source_root) and sha(path) == expected
    continuity = read(root / 'host-continuity.private.json')
    assert continuity['sameBoot'] is True
    assert datetime.datetime.fromisoformat(continuity['before']) == datetime.datetime.fromisoformat(continuity['after'])
    bugchecks = set()
    callers = {}
    for name, kind, phase in zip(SCENARIOS, ['nmi', 'nmi', 'emulator-kill'],
                                  ['before-namespace-call', 'parent-flushed', 'before-namespace-call']):
        folder = root / name
        live = read(folder / 'live.private.json')
        terminal(live['prepare'], 'owned-source-prepared')
        caller = live['callerContext']
        assert caller['stage'] == ('after-publication' if name == 'published-nmi' else 'before-publication')
        assert caller['stoppedBeforePublication'] is False and len(caller['records']) == 2
        assert caller['sha256'] == MARKER_HASH
        assert fault(folder, kind, phase, bugchecks) == live['barrier']
        callers[name] = caller

    first = read(root / 'unpublished-nmi/action.private.json')
    attested = dict(callers['unpublished-nmi'], stoppedBeforePublication=True)
    assert first['caller'] == attested
    result = terminal(first['result'], 'owned-unpublished-handles-pruned')
    assert result['ownedHandlesRemoved'] == 3 and not result['cleanupPending']
    leaves = files(first['result'])
    assert sorted(leaves) == ['source.marker']
    marker(leaves['source.marker'])

    folder = root / 'published-nmi'
    renewed = read(folder / 'recovery-context.private.json')
    assert renewed['caller'] == callers['published-nmi']
    assert fault(folder / 'recovery-fault', 'emulator-kill', 'restart-record-file-flushed', bugchecks) == renewed['barrier']
    context = renewed['renewed']
    assert context['stage'] == 'after-publication' and context['stoppedBeforePublication'] is False
    assert len(context['records']) == 3 and context['records'][:2] == renewed['caller']['records']
    for key in ['purpose', 'root', 'source', 'candidate', 'sha256', 'persistenceMode']:
        assert context[key] == renewed['caller'][key]
    published = read(folder / 'action.private.json')
    for key in ['stale', 'prune']:
        refused = terminal(published[key], 'restart-refused-before-effects')
        assert refused['effectsAttempted'] is False and refused['ownedHandlesRemoved'] == 0
    terminal(published['existing'], 'output-observation-already-present')
    assert files(published['stale']) == files(published['existing']) == files(published['prune'])
    leaves = files(published['existing'])
    assert sorted(leaves) == ['intent.record', 'observation.record', 'output.marker', 'prepared.record', 'source.marker']
    marker(leaves['source.marker']);marker(leaves['output.marker'])
    for record in context['records']:
        leaf = record['name'] + '.record'
        assert leaves[leaf]['sha256'] == record['sha256'] and leaves[leaf]['size'] == record['info']['size']

    folder = root / 'unpublished-kill'
    fault(folder / 'recovery-fault', 'nmi', 'restart-file-removed', bugchecks)
    partial = read(folder / 'action.private.json')
    assert partial['caller'] == dict(callers['unpublished-kill'], stoppedBeforePublication=True)
    outcome = assert_reports(partial['retry'])[-1]
    assert outcome['outcome'] in ['restart-refused-before-effects', 'owned-unpublished-handles-pruned']
    assert summary['cases'][2]['outcome'] == outcome['outcome']
    leaves = files(partial['retry'])
    assert 'output.marker' not in leaves and set(leaves).issubset({'source.marker', 'candidate.marker', 'prepared.record', 'intent.record'})
    marker(leaves['source.marker'])
    if 'candidate.marker' in leaves:
        marker(leaves['candidate.marker'])
    for record in partial['caller']['records']:
        leaf = record['name'] + '.record'
        if leaf in leaves:
            assert leaves[leaf]['sha256'] == record['sha256'] and leaves[leaf]['size'] == record['info']['size']
    if outcome['outcome'] == 'restart-refused-before-effects':
        assert outcome['ownedHandlesRemoved'] == 0 and outcome['effectsAttempted'] is False
    else:
        assert sorted(leaves) == ['source.marker'] and outcome['ownedHandlesRemoved'] == 3
    assert len(bugchecks) == 3
    manifest = {str(path.relative_to(root)): {'sha256': sha(path), 'size': path.stat().st_size}
                for path in sorted(root.rglob('*')) if path.is_file() and path.name != 'restart-audit.private.json'}
    (root / 'restart-audit.private.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    result = {'schemaVersion': 1, 'observedOn': '2026-10-14', 'guestBuild': '26300',
              'scenarioSets': 3, 'liveFaults': 3, 'recoveryFaults': 2, 'faultRuns': 5,
              'freshNmiBugchecks': 3, 'emulatorTerminationFaults': 2,
              'distinctPostFaultBootsVerified': 5, 'standardWorkerToken': True,
              'hostBootUnchanged': True, 'unpublishedOwnedHandlesPruned': 3,
              'staleContextRefused': True, 'renewedContextExistingObservationValidated': True,
              'postpublicationPruneRefused': True, 'partialPruneRetryOutcome': outcome['outcome'],
              'auditedCaptureFiles': len(manifest), 'workerSha256': sha(binary),
              'enabledProfiles': 0, 'physicalPowerLossRuns': 0,
              'limits': 'Caller-directed marker research in the standard-user NTFS/QCOW2 guest. Host caches remain alive. NMI faults use controlled emulator exit/relaunch. No durable context custody, namespace commitment or production repair is qualified.'}
    result.update({key: False for key in FLAGS})
    Path(public).write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: result[key] for key in ['scenarioSets', 'faultRuns', 'freshNmiBugchecks', 'auditedCaptureFiles', 'partialPruneRetryOutcome']}))


if __name__ == '__main__':
    if not __debug__:
        raise RuntimeError('Audit requires assertions')
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['root', 'binary', 'public']:
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    audit(args.root, args.binary, args.public)
