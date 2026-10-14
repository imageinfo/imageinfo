"""Audit retained guest captures and emit a summary without private identifiers."""
import argparse
import datetime
import hashlib
import json
import pathlib
from guest_qualify import PHASES, assert_reports, fresh_bugcheck, verify_guest_token

SOURCE_HASH = '9e9c1dddb8787259606e29a6fe515a3df88249ed84331d7ac49f51759ba175a5'
# This historical ledger is for the exact static c63e18b worker, not a future
# binary that happens to print compatible JSON.
WORKER_HASH = '2ddc990bee90a5151319440f9f504507f411465cf330ee73137ccb623915f875'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def audit(root, binary, public, actors):
    root = pathlib.Path(root).resolve()
    worker_hash = hashlib.sha256(pathlib.Path(binary).read_bytes()).hexdigest()
    assert worker_hash == WORKER_HASH
    controller_sources = read(root / 'controller-source.private.json')
    for name, expected_hash in controller_sources.items():
        assert hashlib.sha256(pathlib.Path(__file__).with_name(name).read_bytes()).hexdigest() == expected_hash
    summary = read(root / 'summary.json')
    continuity = read(root / 'host-continuity.private.json')
    assert continuity['sameBoot'] and datetime.datetime.fromisoformat(continuity['before']) == datetime.datetime.fromisoformat(continuity['after'])
    assert summary['caseCount'] == 17 and len(summary['cases']) == 17
    expected = {kind + '-' + phase for kind in ['nmi', 'emulator-kill'] for phase in PHASES}
    assert {c['id'] for c in summary['cases']} == expected | {'normal'}
    normal = read(root / 'normal.private.json')
    assert assert_reports(normal['run'])[-1]['installedCheckPassed']
    assert assert_reports(normal['inspect'])[0]['outcome'] == 'matching-output-recovery-required'
    verify_guest_token(read(root / 'initial-hello.private.json')['value'])
    bugchecks = set()
    readable_paths = 0
    cases = []
    for case in summary['cases']:
        if case['id'] == 'normal':
            continue
        folder = root / case['id']
        before, after = read(folder / 'before.private.json'), read(folder / 'after.private.json')
        assert before['barrier']['value']['event']['barrier'] == case['barrier']
        assert after['hello']['at'] > before['barrier']['at']
        assert datetime.datetime.fromisoformat(continuity['recordedUtc'].replace('Z', '+00:00')).timestamp() >= after['hello']['at']
        for value in [before['hello']['value'], after['hello']['value']]:
            verify_guest_token(value)
            assert value['build'] == summary['guestBuild']
            assert 'IgnoreAllFailures' in value['bootPolicy'] and 'recoveryenabled         No' in value['bootPolicy']
        boot_times = [datetime.datetime.fromisoformat(v['hello']['value']['boot']).timestamp() for v in [before, after]]
        assert abs(boot_times[1] - boot_times[0]) > 5
        report = assert_reports(after['inspect'])[0]
        assert report['outcome'] == case['inspection'] and report['outputPresent'] == case['outputPresent']
        prepared_files = {v['name']: v for v in before['prepare']['files']}
        files = {v['name']: v for v in after['inspect']['files']}
        assert prepared_files['source.marker']['sha256'] == SOURCE_HASH
        assert files['source.marker']['sha256'] == SOURCE_HASH and files['source.marker']['size'] == 65536
        for name in ['candidate.marker', 'output.marker']:
            if name in files:
                assert files[name]['sha256'] == SOURCE_HASH and files[name]['size'] == 65536
        assert ('output.marker' in files) == report['outputPresent']
        readable_paths += len(files)
        events = after['osEvents'].get('events') or []
        if isinstance(events, dict):
            events = [events]
        fresh = [v for v in events if fresh_bugcheck(v, before['barrier']['at'])]
        assert bool(fresh) == case['windowsBugcheckEventObserved']
        if case['faultKind'] == 'nmi':
            assert fresh and (folder / 'bugcheck.png').is_file()
            assert case['restartMethod'] == 'controlled-emulator-restart'
            event = fresh[0]
            # Unclean shutdown can lose an event-log tail and reuse RecordId.
            # Require a fresh timestamp/message pair, not durable log numbering.
            event_key = (event['TimeCreated'], event['Message'])
            assert event_key not in bugchecks
            bugchecks.add(event_key)
        else:
            assert not fresh
            assert case['restartMethod'] == 'restart-after-emulator-sigkill'
        assert read(folder / 'relaunch.private.json')['exitCode'] == 0
        cases.append(case)
    assert len(bugchecks) == 8
    actors = pathlib.Path(actors).resolve()
    actor_summary = read(actors / 'summary.json')
    expected_actors = {'source-data': False, 'candidate-data': False, 'source-time-dotnet': False, 'foreign-winner': True, 'owner-edit': True}
    assert {c['id']: c['actorAllowed'] for c in actor_summary['cases']} == expected_actors
    for case in actor_summary['cases']:
        capture = read(actors / (case['id'] + '.private.json'))
        assert capture['actor']['allowed'] == expected_actors[case['id']]
        terminal = assert_reports(capture['run'])[-1]
        report = assert_reports(capture['inspect'])[0]
        assert report['outcome'] == case['inspection']
        if case['id'] == 'foreign-winner':
            assert terminal['publicationAttempted'] and not terminal['publicationCallSucceeded']
            for result in [capture['run'], capture['inspect']]:
                winner = next(f for f in result['files'] if f['name'] == 'output.marker')
                assert winner['sha256'] == hashlib.sha256(b'foreign-winner').hexdigest()
        else:
            assert terminal['publicationCallSucceeded'] and terminal['installedCheckPassed']
    owner = read(actors / 'owner-edit.private.json')
    expected_files = sorted(owner['inspect']['files'], key=lambda f: f['name'])
    for mode in ['ordinary-admit', 'ordinary-finalize', 'ordinary-prune']:
        result = read(actors / (mode + '.private.json'))
        assert assert_reports(result)[0]['outcome'] == 'refused-before-effects'
        assert sorted(result['files'], key=lambda f: f['name']) == expected_files
    actor_captures = [{'path': str(p.relative_to(actors)), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(actors.glob('*.json')) if p.name != 'audit.private.json']
    (actors / 'audit.private.json').write_text(json.dumps(actor_captures, indent=2), encoding='utf-8')
    captures = []
    for path in sorted(root.rglob('*')):
        if path.is_file() and path.name != 'audit.private.json':
            captures.append({'path': str(path.relative_to(root)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    encoded = json.dumps(captures, sort_keys=True, separators=(',', ':')).encode()
    (root / 'audit.private.json').write_text(json.dumps(captures, indent=2), encoding='utf-8')
    result = {
        'schemaVersion': 1, 'observedOn': summary['observedOn'],
        'implementationRevision': 'c63e18b63cb9e06170bce8f15843c2a9017ca40e',
        'guestEdition': 'Windows 11 EnterpriseEval', 'guestBuild': summary['guestBuild'],
        'filesystem': 'guest-local NTFS on QCOW2/SATA, QEMU writeback, WSL KVM',
        'standardMediumIntegrityWorker': True, 'normalRuns': 1,
        'hostBootContinuityVerified': True,
        'windowsNmiBugcheckRuns': 8, 'emulatorTerminationRuns': 8,
        'physicalPowerLossRuns': 0, 'uniqueFreshBugcheckEvents': len(bugchecks),
        'auditedCaptureFiles': len(captures), 'readablePostFaultArtifactPaths': readable_paths,
        'captureManifestSha256': hashlib.sha256(encoded).hexdigest(),
        'workerSha256': worker_hash, 'controllerSourceLocalSha256': controller_sources,
        'cases': cases, 'namespaceAcknowledged': False, 'committed': False,
        'guestActorCases': actor_summary['cases'], 'guestRefusalModes': actor_summary['refusedModes'],
        'guestActorCaptureFiles': len(actor_captures),
        'guestActorCaptureManifestSha256': hashlib.sha256(json.dumps(actor_captures, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
        'repairAllowed': False, 'productionPublicationAllowed': False, 'enabledProfiles': 0,
        'limits': 'NMI bugchecks followed by controlled emulator quit/relaunch; separate SIGKILL/relaunch cases. Host caches remain alive, controlled exit can drain submitted disk work. Not physical power loss or a qualified warm-reset/namespace/receipt protocol. Restart finalize/prune remain refused; no RAW writer is enabled.'
    }
    pathlib.Path(public).write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: result[k] for k in ['windowsNmiBugcheckRuns', 'emulatorTerminationRuns', 'auditedCaptureFiles', 'readablePostFaultArtifactPaths']}))


if __name__ == '__main__':
    if not __debug__:
        raise RuntimeError('Audit requires assertions')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    parser.add_argument('--binary', required=True)
    parser.add_argument('--public', required=True)
    parser.add_argument('--actors', required=True)
    args = parser.parse_args()
    audit(args.root, args.binary, args.public, args.actors)
