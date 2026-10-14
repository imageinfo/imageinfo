"""Reconcile private custody guest captures before publishing bounded facts."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '0022-ordinary-output'))
from guest_qualify import fresh_bugcheck, verify_guest_token

FLAGS = ('committed', 'namespaceAcknowledged', 'repairAllowed', 'productionPublicationAllowed')
MARKER_HASH = hashlib.sha256(b'3' * 65536).hexdigest()
SCENARIOS = ('captured-only-nmi', 'stopped-kill', 'fenced-nmi', 'renewed-kill')


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while block := stream.read(65536):
            digest.update(block)
    return digest.hexdigest()


def safe(event):
    assert all(event.get(key) is False for key in FLAGS), event


def reports(result, expected=None):
    assert result['exitCode'] == 0, result.get('stderr')
    events = [json.loads(line) if isinstance(line, str) else line for line in result['stdout']]
    assert events
    for event in events:
        safe(event)
    terminal = next((event for event in reversed(events) if 'outcome' in event), None)
    assert terminal
    if expected is not None:
        assert terminal['outcome'] == expected, terminal
    return terminal


def inventory(result, key='files'):
    entries = result[key]
    assert len(entries) == len({entry['name'] for entry in entries})
    assert all(not entry.get('inaccessible') for entry in entries)
    return {entry['name']: entry for entry in entries}


def markers(entries, output=False):
    for name in ['source.marker'] + (['output.marker'] if output else []):
        assert entries[name]['size'] == 65536 and entries[name]['sha256'] == MARKER_HASH


def fault(folder, kind, phase, bugchecks, postboots, agent_hash):
    value = read(folder / 'reboot.private.json')
    assert value['fault'] == kind
    barrier = value['barrier']
    assert barrier['path'] == '/event' and barrier['value']['event']['custodyCheckpoint'] == phase
    safe(barrier['value']['event'])
    before, after = value['before'], value['after']
    assert before['path'] == after['path'] == '/hello'
    assert before['at'] <= barrier['at'] < after['at']
    for hello in [before, after]:
        verify_guest_token(hello['value'])
        assert hello['value']['build'] == '26300'
        assert hello['value']['scriptSha256'] == agent_hash
    boots = [datetime.datetime.fromisoformat(hello['value']['boot']).timestamp() for hello in [before, after]]
    assert abs(boots[1] - boots[0]) > 5
    assert all(abs(boots[1] - previous) > 5 for previous in postboots)
    postboots.append(boots[1])
    assert read(folder / 'relaunch.private.json')['exitCode'] == 0
    events = value['events'].get('events') or []
    if isinstance(events, dict):
        events = [events]
    fresh = [event for event in events if fresh_bugcheck(event, barrier['at'])]
    if kind == 'nmi':
        assert fresh and (folder / 'bugcheck.png').is_file()
        keys = {(event['TimeCreated'], event['Message']) for event in fresh}
        assert not keys.intersection(bugchecks)
        bugchecks.update(keys)
    else:
        assert not fresh
    target = read(folder / 'fault-target.private.json')
    assert target['verifiedTarget'] is True and target['kind'] == kind and target['checkpoint'] == phase
    assert target['pid'] > 0
    assert Path(target['cmdline'][0]).name == 'qemu-system-x86_64'
    assert target['disk'] == target['guestRoot'] + '/windows.qcow2'
    assert any(argument.split(',')[0] == 'file=' + target['disk'] for argument in target['cmdline'])
    assert target['qmpSocket'].startswith(target['guestRoot'] + '/')
    return barrier


def source_bindings(root, binary, source_root):
    binding = read(root / 'source-binding.private.json')
    original = read(root / 'native-binding.private.json')
    static_native = read(root / 'static-native-binding.private.json')
    assert binding == read(root / 'source-binding-after.private.json')
    assert binding['workerSha256'] == sha(binary)
    assert static_native['binarySha256'] == binding['workerSha256']
    native = {key.replace('\\', '/'): value for key, value in original['sources'].items()}
    frozen = {key.replace('\\', '/'): value for key, value in binding['frozenSources'].items()}
    required = {key for key in native if key.endswith('.rs') or key.endswith('/Cargo.toml') or key.endswith('/Cargo.lock')}
    assert required and required.issubset(frozen)
    assert all(frozen[key] == native[key] for key in required)
    for relative, expected in frozen.items():
        path = (source_root / relative).resolve()
        assert path.is_relative_to(source_root) and sha(path) == expected
    assert any(key.startswith('experiments/0028-recovery-evidence/src/') for key in frozen)
    provenance = read(root / 'frozen-git-blobs.private.json')
    assert provenance['revision'] == binding['sourceRevision']
    for relative in frozen:
        data = (source_root / relative).read_bytes()
        blob = hashlib.sha1(b'blob ' + str(len(data)).encode('ascii') + b'\0' + data).hexdigest()
        assert provenance['blobs'][relative] == blob
    static_sources = {key.replace('\\', '/'): value for key, value in static_native['sources'].items()}
    assert required.issubset(static_sources)
    assert all(static_sources[key] == frozen[key] for key in required)
    repo = Path(__file__).resolve().parents[2]
    for relative, expected in binding['controllerSources'].items():
        path = (repo / relative).resolve()
        assert path.is_relative_to(repo) and sha(path) == expected
        assert sha(root / 'controller-sources.private' / relative) == expected
    assert sha(root / 'driver-source.private.py') == binding['controllerSources']['experiments/0044-custody-guest/qualify.py']
    assert binding['sourceRevision'].startswith('b381576')
    assert len(original['binarySha256']) == 64
    return binding


def checkpoint(folder, plan):
    before = read(folder / 'before.private.json')
    reports(before['prepare'], 'owned-source-prepared')
    envelope = before['checkpoint']
    value = envelope['value']['event']
    safe(value)
    assert value['supervisorObservation'] is True
    assert value['callerAuthorityAuthenticated'] is value['custodyFreshnessProven'] is False
    assert value['custodyCase'] == before['case'] + '-custody'
    assert before['request']['mode'] == 'ordinary-write-through'
    assert before['request']['custodyPlan'] == plan
    assert value['originalExitedBeforeRelease'] is (plan == 'stopped')
    assert value['publicationContinuationSent'] is (plan == 'renewed')
    history = value['journal']
    assert history['purpose'] == 'imageinfo-od11-custody-history-v1'
    names = {
        'captured-only': ['captured'],
        'stopped': ['captured', 'stop-confirmed-before-publication'],
        'fenced': ['captured', 'publication-release-fenced'],
        'renewed': ['captured', 'publication-release-fenced', 'publication-observed', 'observation-renewed'],
    }[plan]
    assert [item['event'] for item in history['events']] == names
    captured = history['events'][0]['context']
    assert captured['stage'] == 'before-publication' and captured['stoppedBeforePublication'] is False
    assert captured['sha256'] == MARKER_HASH and len(captured['records']) == 2
    assert captured['persistenceMode'] == 'write-through'
    saves = value['saves']
    assert len(saves) == len(names)
    previous_root = None
    for index, save in enumerate(saves, 1):
        request = save['request']
        assert request['journal'] == dict(history, events=history['events'][:index])
        assert request['expectedCustodyRoot'] == previous_root
        assert json.loads(save['stdin'][0]) == request
        terminal = reports(save, 'custody-snapshot-recorded')
        assert save['terminal'] == terminal
        assert terminal['journal'] == request['journal']
        assert terminal['callerAuthorityAuthenticated'] is terminal['custodyFreshnessProven'] is False
        assert terminal['transactionMutations'] == 0 and terminal['rootRetained'] is True
        events = [json.loads(line) for line in save['stdout']]
        assert save['stdin'][1:] == ['continue'] * sum('barrier' in event for event in events)
        previous_root = terminal['custodyRoot']
    assert value['custodyRoot'] == previous_root
    controls = value['controls']
    timestamps = [datetime.datetime.fromisoformat(control['guestUtc']) for control in controls]
    assert timestamps == sorted(timestamps)
    successes = [(index, int(control['control'])) for index, control in enumerate(controls)
                 if control['kind'] == 'custody-save-succeeded']
    assert [count for _, count in successes] == list(range(1, len(names) + 1))
    kills = [index for index, control in enumerate(controls) if control['kind'] == 'original-killed-and-waited']
    releases = [index for index, control in enumerate(controls) if control['kind'] == 'original-publication-continuation']
    if plan == 'stopped':
        assert value['originalExitCode'] != 0 and len(kills) == 1
        assert successes[0][0] < kills[0] < successes[1][0] and not releases
    elif plan == 'renewed':
        assert not kills and len(releases) == 1
        assert successes[1][0] < releases[0] < successes[2][0]
    else:
        assert not kills and not releases
    raw = read(folder / 'controller-events.private.json')
    assert envelope in raw
    assert all(entry['value'].get('id') == before['request']['id'] for entry in raw)
    native = [entry['value']['event'] for entry in raw
              if entry['path'] == '/event' and not entry['value']['event'].get('supervisorObservation')]
    for event in native:
        safe(event)
    native_barriers = [event['barrier'] for event in native if 'barrier' in event]
    held = [control['barrier'] for control in controls if control['kind'] == 'original-barrier']
    assert native_barriers == held
    assert held[-1] == ('observation-parent-flushed' if plan == 'renewed' else 'before-namespace-call')
    assert sum(control['kind'] in ['original-continuation', 'original-publication-continuation']
               for control in controls) == len(held) - 1
    assert next(event['callerContext'] for event in native if 'callerContext' in event) == captured
    for index, save in enumerate(saves, 1):
        saved_events = [entry['value']['event']['workerEvent'] for entry in raw
                        if entry['path'] == '/event' and entry['value']['event'].get('custodySave') == index]
        assert saved_events == [json.loads(line) for line in save['stdout']]
    for entry in raw:
        if entry['path'] == '/result':
            assert plan == 'stopped' and entry['value']['exitCode'] == value['originalExitCode']
            assert all('outcome' not in json.loads(line) for line in entry['value']['stdout'])
    if plan == 'renewed':
        observed, renewed = [item['context'] for item in history['events'][2:]]
        for context, count in [(observed, 2), (renewed, 3)]:
            assert context['stage'] == 'after-publication' and context['stoppedBeforePublication'] is False
            assert len(context['records']) == count and context['records'][:2] == captured['records']
            for key in ['purpose', 'root', 'source', 'candidate', 'sha256', 'persistenceMode']:
                assert context[key] == captured[key]
            assert any(event.get('callerContext') == context for event in native)
        assert value['callerContext'] == value['callerContextCandidate'] == renewed
    elif plan == 'stopped':
        assert value['callerContext'] == captured
        assert value['callerContextCandidate'] == dict(captured, stoppedBeforePublication=True)
    else:
        assert value['callerContext'] == captured and value['callerContextCandidate'] is None
    return before, value


def refusal(call):
    terminal = reports(call['result'], 'restart-refused-before-effects')
    assert terminal['effectsAttempted'] is False and terminal['ownedHandlesRemoved'] == 0
    return inventory(call['result'])


def audit(root, binary, source_root, public):
    assert not (root / 'incomplete.private.json').exists()
    summary = read(root / 'summary.private.json')
    assert [case['id'] for case in summary['cases']] == list(SCENARIOS)
    assert summary['caseCount'] == 4 and summary['nmiFaults'] == summary['emulatorTerminationFaults'] == 2
    assert summary['committed'] is summary['productionPublicationAllowed'] is False
    assert summary['enabledProfiles'] == 0
    binding = source_bindings(root, binary, source_root)
    initial = read(root / 'initial-hello.private.json')
    verify_guest_token(initial['value'])
    agent_hash = sha(root / 'served-agent.private.ps1')
    assert initial['value']['scriptSha256'] == agent_hash
    continuity = read(root / 'host-continuity.private.json')
    assert continuity['sameBoot'] is True
    assert datetime.datetime.fromisoformat(continuity['before']) == datetime.datetime.fromisoformat(continuity['after'])
    bugchecks, postboots, save_count = set(), [], 0
    for name, plan, kind, expected_state in zip(SCENARIOS,
            ['captured-only', 'stopped', 'fenced', 'renewed'],
            ['nmi', 'emulator-kill', 'nmi', 'emulator-kill'],
            ['captured-unconfirmed', 'stop-attested-before-publication', 'publication-release-uncertain', 'observation-renewed']):
        folder = root / name
        before, value = checkpoint(folder, plan)
        save_count += len(value['saves'])
        phase = 'custody-' + ('captured' if plan == 'captured-only' else plan)
        assert fault(folder, kind, phase, bugchecks, postboots, agent_hash) == before['checkpoint']
        after = read(folder / 'after.private.json')
        request = after['inspectRequest']
        assert request['mode'] == 'ordinary-custody-inspect'
        assert request['custodyCase'] == value['custodyCase']
        assert request['custodyRequest'] == {'expectedCustodyRoot': value['custodyRoot']}
        terminal = reports(after['inspect'], 'custody-history-observed')
        assert terminal['custodyState'] == expected_state
        assert terminal['journal'] == value['journal']
        current_root, expected_root = terminal['custodyRoot'], value['custodyRoot']
        # Snapshot creation changes directory mtime. Match the worker's stable
        # root contract rather than inventing a stronger Info equality premise.
        assert current_root['identity'] == expected_root['identity']
        assert current_root['creationTime'] == expected_root['creationTime']
        assert current_root['attributes'] & ~32 == expected_root['attributes'] & ~32
        assert terminal['callerContextCandidate'] == value['callerContextCandidate']
        assert terminal['effectsAttempted'] is False and terminal['transactionMutations'] == 0
        assert terminal['callerAuthorityAuthenticated'] is terminal['custodyFreshnessProven'] is False
        candidate, actions = terminal['callerContextCandidate'], after['actions']
        custody_files = inventory(after['inspect'])
        assert sorted(custody_files) == [f'custody-{index}.record' for index in range(1, len(value['saves']) + 1)]
        assert all(0 < entry['size'] <= 65536 for entry in custody_files.values())
        for key in ['transactionBefore', 'transactionAfter']:
            reports(after[key])
            assert after[key + 'Request']['mode'] == 'ordinary-inspect'
        assert inventory(after['transactionBefore']) == inventory(after['transactionAfter'])
        transaction = inventory(after['transactionBefore'])
        markers(transaction, output=(plan == 'renewed'))
        if plan != 'renewed':
            assert sorted(transaction) == ['candidate.marker', 'intent.record', 'prepared.record', 'source.marker']
            assert transaction['candidate.marker']['size'] == 65536 and transaction['candidate.marker']['sha256'] == MARKER_HASH
            for record in value['journal']['events'][0]['context']['records']:
                entry = transaction[record['name'] + '.record']
                assert entry['size'] == record['info']['size'] and entry['sha256'] == record['sha256']
        if plan in ['captured-only', 'fenced']:
            assert len(actions) == 2 and candidate is None
            for call in actions:
                assert call['request']['mode'] == 'ordinary-restart-prune'
                assert call['request']['callerContext'] == value['callerContext']
            leaves = refusal(actions[0])
            assert leaves == refusal(actions[1]) == inventory(after['transactionBefore'])
            assert 'output.marker' not in leaves
            markers(leaves)
        elif plan == 'stopped':
            assert len(actions) == 1 and actions[0]['request']['callerContext'] == candidate
            assert actions[0]['request']['mode'] == 'ordinary-restart-prune'
            pruned = reports(actions[0]['result'], 'owned-unpublished-handles-pruned')
            assert pruned['ownedHandlesRemoved'] == 3 and pruned['cleanupPending'] is False
            leaves = inventory(actions[0]['result'])
            assert sorted(leaves) == ['source.marker']
            markers(leaves)
        else:
            assert len(actions) == 3
            old = value['journal']['events'][2]['context']
            assert actions[0]['request']['callerContext'] == old and actions[0]['request']['mode'] == 'ordinary-restart-observe'
            assert actions[1]['request']['callerContext'] == candidate and actions[1]['request']['mode'] == 'ordinary-restart-observe'
            assert actions[2]['request']['callerContext'] == candidate and actions[2]['request']['mode'] == 'ordinary-restart-prune'
            stale, refused = refusal(actions[0]), refusal(actions[2])
            observed = reports(actions[1]['result'], 'output-observation-already-present')
            assert observed['effectsAttempted'] is False and observed['observationRecordCreated'] is False
            leaves = inventory(actions[1]['result'])
            assert leaves == stale == refused
            assert sorted(leaves) == ['intent.record', 'observation.record', 'output.marker', 'prepared.record', 'source.marker']
            markers(leaves, output=True)
            for record in candidate['records']:
                entry = leaves[record['name'] + '.record']
                assert entry['size'] == record['info']['size'] and entry['sha256'] == record['sha256']
        assert after['inspectAgainRequest']['custodyRequest'] == request['custodyRequest']
        again = reports(after['inspectAgain'], 'custody-history-observed')
        assert again == terminal
        assert inventory(after['inspect']) == inventory(after['inspectAgain'])
    assert len(bugchecks) == 2 and len(postboots) == 4 and save_count == 9
    manifest = {str(path.relative_to(root)): {'sha256': sha(path), 'size': path.stat().st_size}
                for path in sorted(root.rglob('*')) if path.is_file() and path.name != 'custody-audit.private.json'}
    (root / 'custody-audit.private.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    result = {'schemaVersion': 1, 'observedOn': '2026-10-14', 'sourceRevision': binding['sourceRevision'],
              'data': 'authored marker bytes only', 'guestBuild': '26300',
              'scenarioSets': 4, 'faultRuns': 4, 'freshNmiBugchecks': 2, 'emulatorTerminationFaults': 2,
              'distinctPostFaultBootsVerified': 4, 'standardWorkerToken': True, 'hostBootUnchanged': True,
              'nativeCustodySaveCapturesAudited': save_count, 'capturedOnlyNoContext': True,
              'unchangedTransactionInventoryPairsAcrossCustodyInspection': 4,
              'unchangedCustodyInventoryPairsAcrossReadOnlyInspection': 4,
              'stoppedOwnedHandlesPruned': 3, 'fencedNoContext': True,
              'releaseFenceSavedBeforePublicationContinuation': True,
              'staleContextRefused': True, 'renewedContextExistingObservationValidated': True,
              'postpublicationPruneRefused': True, 'auditedCaptureFiles': len(manifest),
              'workerSha256': sha(binary), 'staticCrtRebuildOfAcceptedSource': True,
              'guestBinaryMatchesNativeBaseline': sha(binary) == read(root / 'native-binding.private.json')['binarySha256'],
              'guestBinaryMatchesFreshNativeCustodyRun': True,
              'frozenSourceGitBlobBindingsVerified': True, 'servedAgentBytesBoundAcrossFaults': True,
              'callerAuthorityAuthenticated': False, 'custodyFreshnessProven': False,
              'enabledProfiles': 0, 'physicalPowerLossRuns': 0,
              'limits': 'Four bounded caller-history cells in the standard-user Windows NTFS/QCOW2 guest. Host caches remain alive; NMI faults use controlled emulator exit/relaunch. Restored history cannot prove freshness or nonrelease. No automatic durable custody, namespace commitment, storage-profile admission or production repair is qualified.'}
    result.update({key: False for key in FLAGS})
    public.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: result[key] for key in ['scenarioSets', 'faultRuns', 'freshNmiBugchecks', 'nativeCustodySaveCapturesAudited', 'auditedCaptureFiles']}))


def main():
    if not __debug__:
        raise RuntimeError('Audit requires assertions')
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['root', 'binary', 'source-root', 'public']:
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    audit(Path(args.root).resolve(), Path(args.binary).resolve(), Path(args.source_root).resolve(), Path(args.public))


if __name__ == '__main__':
    main()
