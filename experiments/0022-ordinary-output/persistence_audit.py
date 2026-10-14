"""Audit the exact persistence captures; publish no private paths or identities."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
from persistence_qualify import MODES, PHASES, SOURCE_HASH
from guest_qualify import assert_reports, fresh_bugcheck, verify_guest_token


def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def safe(events):
    assert all(not e.get(k, False) for e in events for k in ['committed', 'namespaceAcknowledged', 'productionPublicationAllowed', 'repairAllowed'])


def audit_native(root, binary, public):
    root = Path(root).resolve();summary = read(root / 'summary.private.json')
    assert summary['caseCount'] == len(summary['cases']) == 69
    assert len({(c['mode'], c['id']) for c in summary['cases']}) == 69
    unchanged = 0
    for case in summary['cases']:
        folder = root / case['mode'] / case['id']
        events = [json.loads(v) for v in (folder / 'worker/stdout.jsonl').read_text().splitlines()]
        safe(events);code = read(folder / 'worker/exit.json')['exitCode']
        terminal = next((e for e in events if 'outcome' in e), None)
        assert terminal == case['terminal']
        if case['stop'] == 'kill':assert code != 0 and terminal is None
        else:assert code == 0 and terminal['persistenceMode'] == case['mode']
        snapshot = read(folder / 'inspection-inventory.private.json')
        assert snapshot['before'] == snapshot['after'];unchanged += 1
        report = json.loads((folder / 'inspect/stdout.jsonl').read_text())
        safe([report]);assert report == case['inspection']
        if case['id'].startswith(('cancel-', 'fail-')):
            phase = case['phase'];index = PHASES.index(phase)
            actual = [terminal[k] for k in ['installedFileFlushSucceeded', 'parentFlushSucceeded', 'observationFileFlushSucceeded', 'observationParentFlushSucceeded']]
            assert actual == [index >= n for n in range(1, 5)]
            assert terminal['ownedHandlesRemoved'] == 0 and terminal['cleanupPending']
    for mode in MODES:
        folder = root / mode
        report = json.loads((folder / 'mixed-inspect/stdout.jsonl').read_text())
        assert report['diagnostic'] == 'RECORDS_DISAGREE';safe([report])
        snapshot = read(folder / 'mixed-inspection-inventory.private.json')
        assert snapshot['before'] == snapshot['after'];unchanged += 1
    manifest = {};inaccessible = 0
    for p in sorted(root.rglob('*')):
        if not p.is_file() or p.name == 'audit.private.json':continue
        try:manifest[str(p.relative_to(root))] = {'sha256': sha(p), 'size': p.stat().st_size}
        except PermissionError:inaccessible += 1
    (root / 'audit.private.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    result = {'schemaVersion': 1, 'observedOn': '2026-10-14', 'nativeCaseCount': 69,
              'mixedModeRecordRefusals': 3, 'unchangedInspectionInventories': unchanged,
              'readableArtifactPathsHashed': len(manifest), 'inaccessibleRetained': inaccessible,
              'workerSha256': sha(Path(binary)), 'modes': list(MODES),
              'postpublicationBoundaries': PHASES, 'namespaceAcknowledged': False,
              'committed': False, 'repairAllowed': False, 'productionPublicationAllowed': False,
              'limits': 'Injected protocol failures and process kills, not native failed flush/device errors or physical power loss. Request labels and call returns do not admit a profile.'}
    Path(public).write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8');print(json.dumps(result))


def audit_guest(roots, binary, public):
    all_rows = [];event_keys = set();artifact_paths = 0;captures = 0;normal_runs = 0
    expected = {(m, k, p) for m in MODES for k in ['nmi', 'emulator-kill'] for p in PHASES}
    full_set = False
    for root in [Path(r).resolve() for r in roots]:
        summary = read(root / 'summary.private.json');normal_runs += summary['normalRuns']
        cells = {(c['mode'], c['fault'], c['barrier']) for c in summary['cases']}
        if cells == expected:full_set = True
        assert summary['faultCaseCount'] == len(summary['cases']) == len(cells)
        header = read(root / 'source-binding.private.json')
        assert header['workerSha256'] == sha(Path(binary))
        # Preserve the exact loaded driver when later native-only edits occur.
        assert sha(root / 'driver-source.private.py') == header['sources']['experiments/0022-ordinary-output/persistence_qualify.py']
        continuity = read(root / 'host-continuity.private.json')
        assert continuity['sameBoot'] and datetime.datetime.fromisoformat(continuity['before']) == datetime.datetime.fromisoformat(continuity['after'])
        for label in {c['mode'] for c in summary['cases']}:
            normal = read(root / (label + '-normal.private.json'))
            terminal = assert_reports(normal['run'])[-1]
            assert terminal['persistenceMode'] == label and terminal['installedCheckPassed']
            assert all(terminal[k] for k in ['installedFileFlushSucceeded', 'parentFlushSucceeded', 'observationFileFlushSucceeded', 'observationParentFlushSucceeded'])
            assert assert_reports(normal['inspect'])[0]['outcome'] == 'matching-output-recovery-required'
        for case in summary['cases']:
            folder = root / (case['mode'] + '-' + case['fault'] + '-' + case['barrier'])
            before, after = read(folder / 'before.private.json'), read(folder / 'after.private.json')
            assert before['mode'] == MODES[case['mode']] and before['barrier']['value']['event']['barrier'] == case['barrier']
            assert after['hello']['at'] > before['barrier']['at']
            for value in [before['hello']['value'], after['hello']['value']]:verify_guest_token(value);assert value['build'] == '26300'
            boots = [datetime.datetime.fromisoformat(v['hello']['value']['boot']).timestamp() for v in [before, after]]
            assert abs(boots[1] - boots[0]) > 5
            assert read(folder / 'relaunch.private.json')['exitCode'] == 0
            report = assert_reports(after['inspect'])[0]
            assert report['outcome'] == case['inspection'] and report['outputPresent'] == case['outputPresent'] and report['persistenceMode'] == case['mode']
            assert report['recordCount'] == case['records']
            files = {f['name']: f for f in after['inspect']['files']}
            assert files['source.marker']['sha256'] == SOURCE_HASH
            for name in ['candidate.marker', 'output.marker']:
                if name in files:assert files[name]['sha256'] == SOURCE_HASH and files[name]['size'] == 65536
            artifact_paths += len(files)
            events = after['osEvents'].get('events') or []
            if isinstance(events, dict):events = [events]
            fresh = [e for e in events if fresh_bugcheck(e, before['barrier']['at'])]
            if case['fault'] == 'nmi':
                assert fresh and (folder / 'bugcheck.png').is_file()
                key = (fresh[0]['TimeCreated'], fresh[0]['Message']);assert key not in event_keys;event_keys.add(key)
            else:assert not fresh
            all_rows.append(case)
        manifest = {str(p.relative_to(root)): sha(p) for p in sorted(root.rglob('*')) if p.is_file() and p.name != 'audit.private.json'}
        captures += len(manifest)
        (root / 'audit.private.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    assert full_set
    result = {'schemaVersion': 1, 'observedOn': '2026-10-14', 'guestBuild': '26300',
              'normalRuns': normal_runs, 'faultRuns': len(all_rows), 'freshNmiBugchecks': len(event_keys),
              'auditedCaptureFiles': captures, 'postFaultArtifactPaths': artifact_paths,
              'workerSha256': sha(Path(binary)), 'cases': all_rows,
              'namespaceAcknowledged': False, 'committed': False, 'repairAllowed': False,
              'productionPublicationAllowed': False, 'physicalPowerLossRuns': 0,
              'limits': 'Standard-user NTFS/QCOW2 guest. NMI then controlled emulator exit/relaunch, or SIGKILL/relaunch. Host caches remain alive. This finite comparison does not qualify physical power loss, namespace/receipt commitment or restart repair.'}
    Path(public).write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: result[k] for k in ['faultRuns', 'freshNmiBugchecks', 'auditedCaptureFiles', 'postFaultArtifactPaths']}))


if __name__ == '__main__':
    if not __debug__:raise RuntimeError('Audit requires assertions')
    p = argparse.ArgumentParser(description=__doc__);p.add_argument('mode', choices=['native', 'guest'])
    p.add_argument('--root', required=True, action='append');p.add_argument('--binary', required=True);p.add_argument('--public', required=True)
    a = p.parse_args()
    if a.mode == 'native':audit_native(a.root[0], a.binary, a.public)
    else:audit_guest(a.root, a.binary, a.public)
