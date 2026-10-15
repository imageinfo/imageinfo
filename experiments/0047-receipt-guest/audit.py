"""Independently reconcile the finite receipt guest captures before publication."""
import argparse
import base64
import datetime
import hashlib
import json
from pathlib import Path
import sys

if not __debug__:
    raise RuntimeError('Audit requires enabled assertions')

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '0022-ordinary-output'))
from guest_qualify import fresh_bugcheck, verify_guest_token

REVISION = 'b819f54533c495b332c3d4dbb0caccef49923036'
FLAGS = ('committed', 'namespaceAcknowledged', 'repairAllowed', 'productionPublicationAllowed')
MARKER_HASH = hashlib.sha256(b'3' * 65536).hexdigest()
PHASES = ['before-namespace-call', 'published', 'installed-file-flushed', 'parent-flushed',
          'observation-file-flushed', 'observation-parent-flushed', 'observed-record-flushed',
          'receipt-written', 'receipt-file-flushed', 'receipt-parent-flushed', 'final-checked']
PREFIX = ['source-guarded', 'candidate-flushed', 'prepared-record-flushed',
          'intent-record-flushed', 'before-property-check']
KINDS = ['process-kill', 'emulator-kill', 'nmi']
SUCCESS = 'observed-receipt-recovery-required'
PROPERTY_FIELDS = {'attributes', 'creationTimeUtc', 'lastWriteTimeUtc', 'sddl'}


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        while block := stream.read(65536):
            result.update(block)
    return result.hexdigest()


def safe(event):
    assert all(event.get(key) is False for key in FLAGS), event


def events(result):
    result = [json.loads(line) if isinstance(line, str) else line for line in result['stdout']]
    for event in result:
        safe(event)
    return result


def terminal(result, expected=None):
    assert result['exitCode'] == 0, result.get('stderr')
    found = next((event for event in reversed(events(result)) if 'outcome' in event), None)
    assert found is not None
    if expected is not None:
        assert found['outcome'] == expected, found
    return found


def inventory(result):
    assert result['exitCode'] == 0
    entries = result['files']
    assert len(entries) == len({entry['name'] for entry in entries})
    assert all(not entry.get('inaccessible') and not entry.get('directory') for entry in entries)
    return {entry['name']: entry for entry in entries}


def hello(envelope, agent_hash):
    assert envelope['path'] == '/hello'
    value = envelope['value']
    verify_guest_token(value)
    assert value['build'] == '26300'
    assert value['scriptSha256'] == agent_hash
    return datetime.datetime.fromisoformat(value['boot']).timestamp()


def source_bindings(root, binary, source_root):
    binding = read(root / 'source-binding.private.json')
    assert binding == read(root / 'source-binding-after.private.json')
    assert binding['sourceRevision'] == REVISION
    assert binding['workerSha256'] == sha(binary)
    frozen = {key.replace('\\', '/'): value for key, value in binding['frozenSources'].items()}
    provenance = read(root / 'frozen-git-blobs.private.json')
    assert provenance['revision'] == REVISION
    assert any(key.endswith('/receipt_record.rs') for key in frozen)
    assert any(key.startswith('experiments/0028-recovery-evidence/src/') for key in frozen)
    assert len(frozen) >= 10
    for relative, expected in frozen.items():
        path = (source_root / relative).resolve()
        assert path.is_relative_to(source_root) and sha(path) == expected
        data = path.read_bytes()
        blob = hashlib.sha1(b'blob ' + str(len(data)).encode('ascii') + b'\0' + data).hexdigest()
        assert provenance['blobs'][relative] == blob
    for name in ['native-binding.private.json', 'static-native-binding.private.json']:
        native = read(root / name)
        sources = {key.replace('\\', '/'): value for key, value in native['sources'].items()}
        required = {key for key in sources if key.endswith('.rs') or key.endswith('/Cargo.toml') or key.endswith('/Cargo.lock')}
        assert required and required.issubset(frozen)
        assert all(sources[key] == frozen[key] for key in required)
        assert len(native.get('workerSha256', native.get('binarySha256', ''))) == 64
        if name.startswith('static-'):
            assert native.get('workerSha256', native.get('binarySha256')) == sha(binary)
    repo = Path(__file__).resolve().parents[2]
    required_controllers = {'experiments/0047-receipt-guest/audit.py',
                           'experiments/0047-receipt-guest/qualify.py',
                           'experiments/0022-ordinary-output/windows_guest.py',
                           'experiments/0022-ordinary-output/guest_qualify.py',
                           'experiments/0022-ordinary-output/restart_guest.py'}
    assert required_controllers.issubset(binding['controllerSources'])
    for relative, expected in binding['controllerSources'].items():
        path = (repo / relative).resolve()
        assert path.is_relative_to(repo) and sha(path) == expected
        assert sha(root / 'controller-sources.private' / relative) == expected
    assert sha(root / 'driver-source.private.py') == binding['controllerSources']['experiments/0047-receipt-guest/qualify.py']
    assert read(root / 'server-meta.private.json')['sha256'] == sha(binary)
    native_audit = read(root / 'static-native-audit.private.json')
    assert native_audit['caseCount'] == 93
    assert all(native_audit.get(key) is False for key in FLAGS)
    assert native_audit['enabledProfiles'] == 0
    assert read(root / 'static-native-artifact-manifest.private.json')
    return binding


def reboot(folder, before, after, kind, phase, agent_hash, bugchecks, postboots):
    proof = read(folder / 'reboot.private.json')
    assert proof['fault'] == kind and proof['before'] == before['hello'] and proof['after'] == after['hello']
    checkpoint = before['checkpoint']
    assert proof['barrier'] == checkpoint
    assert before['hello']['at'] <= checkpoint['at'] < after['hello']['at']
    first, second = hello(before['hello'], agent_hash), hello(after['hello'], agent_hash)
    assert abs(second - first) > 5
    assert all(abs(second - other) > 5 for other in postboots)
    postboots.append(second)
    assert read(folder / 'relaunch.private.json')['exitCode'] == 0
    os_events = proof['events'].get('events') or []
    if isinstance(os_events, dict):
        os_events = [os_events]
    fresh = [event for event in os_events if fresh_bugcheck(event, checkpoint['at'])]
    if kind == 'nmi':
        assert fresh and (folder / 'bugcheck.png').stat().st_size > 0
        identities = {(event['TimeCreated'], event['Message']) for event in fresh}
        assert not identities.intersection(bugchecks)
        bugchecks.update(identities)
    else:
        assert not fresh
    target = read(folder / 'fault-target.private.json')
    assert target['verifiedTarget'] is True and target['kind'] == kind and target['checkpoint'] == phase
    assert target['pid'] > 0 and Path(target['cmdline'][0]).name == 'qemu-system-x86_64'
    assert target['disk'] == target['guestRoot'] + '/windows.qcow2'
    assert any(argument.split(',')[0] == 'file=' + target['disk'] for argument in target['cmdline'])
    assert target['qmpSocket'].startswith(target['guestRoot'] + '/')
    assert 'unix:' + target['qmpSocket'] + ',server=on,wait=off' in target['cmdline']


def live_capture(folder, before, after, phase, kind):
    request = before['request']
    assert request['action'] == 'run' and request['case'] == before['case']
    assert request['mode'] == 'ordinary-receipt'
    raw = read(folder / 'controller-events.private.json')
    assert all(entry['value'].get('id') == request['id'] for entry in raw)
    assert [entry['at'] for entry in raw] == sorted(entry['at'] for entry in raw)
    native = [entry['value']['event'] for entry in raw if entry['path'] == '/event'
              and not entry['value']['event'].get('supervisorObservation')]
    for event in native:
        safe(event)
    barriers = [event['barrier'] for event in native if 'barrier' in event]
    expected = PREFIX + (PHASES if phase is None else PHASES[:PHASES.index(phase) + 1])
    assert barriers == expected, barriers
    controls = [entry['value']['event']['supervisorControl'] for entry in raw
                if entry['path'] == '/event' and 'supervisorControl' in entry['value']['event']]
    assert [control['barrier'] for control in controls] == expected
    assert [control['control'] for control in controls] == (['continue'] * len(expected)
            if phase is None else ['continue'] * (len(expected) - 1) + ['held'])
    assert len({control['processId'] for control in controls}) == 1 and controls[0]['processId'] > 0
    assert [control['guestUtc'] for control in controls] == sorted(control['guestUtc'] for control in controls)
    contexts = [event['receiptContext'] for event in native if 'receiptContext' in event]
    context = contexts[-1] if contexts else None
    assert before['receiptContext'] == context
    assert bool(context) == (phase is None or PHASES.index(phase) >= PHASES.index('receipt-written'))
    if context:
        assert context['purpose'] == 'imageinfo-od11-receipt-context-v1'
        assert context['prior']['stage'] == 'after-publication'
        assert context['prior']['persistenceMode'] == 'write-through'
        assert context['prior']['sha256'] == MARKER_HASH and len(context['prior']['records']) == 3
        assert len(context['receipt']['sha256']) == 64
    if phase is not None:
        assert before['checkpoint'] in raw
        assert before['checkpoint']['value']['event']['barrier'] == phase
        assert native[-1].get('barrier') == phase
        assert request['stopAt'] == phase
    results = [entry['value'] for entry in raw if entry['path'] == '/result']
    if kind in ['process-kill', None]:
        result = after['liveResult']
        assert results == [result]
        assert events(result) == native
        if kind is None:
            observed = terminal(result, SUCCESS)
            assert all(observed[key] is True for key in ['receiptWritten', 'receiptFileFlushSucceeded',
                'receiptParentFlushSucceeded', 'finalCheckPassed'])
        else:
            assert result['exitCode'] != 0 and not any('outcome' in event for event in native)
            termination = result['processTermination']
            assert termination['barrier'] == phase and termination['control'] == 'terminate'
            assert termination['killCalled'] is termination['exitWaitCompleted'] is True
            assert termination['barrierContinuationSent'] is False and termination['exitCode'] == result['exitCode']
            assert termination['processId'] > 0
            assert termination['processId'] == controls[0]['processId']
            assert datetime.datetime.fromisoformat(termination['processStartUtc']) <= datetime.datetime.fromisoformat(termination['guestUtc'])
            kills = [entry['value']['event'] for entry in raw if entry['path'] == '/event'
                     and 'processTermination' in entry['value']['event']]
            assert len(kills) == 1 and kills[0]['processTermination'] == termination
            assert [json.loads(line) for line in kills[0]['capturedStdout']] == native
    else:
        assert not results and not any('outcome' in event for event in native)
    return context


def inspect(before, after, context):
    request = after['inspectRequest']
    assert request['mode'] == 'ordinary-receipt-inspect' and request['case'] == before['case']
    assert 'receiptContext' in request and request['receiptContext'] == context
    for key in ['inventoryBefore', 'inventoryAfter']:
        assert after[key + 'Request']['mode'] == 'ordinary-inventory'
        assert after[key + 'Request']['case'] == before['case']
    leaves = inventory(after['inventoryBefore'])
    later = inventory(after['inventoryAfter'])
    assert set(leaves) == set(later)
    changed = []
    for name in sorted(leaves):
        first, second = leaves[name], later[name]
        assert {key: value for key, value in first.items() if key not in PROPERTY_FIELDS} == {
            key: value for key, value in second.items() if key not in PROPERTY_FIELDS}
        changed.extend(name + '.' + key for key in sorted(PROPERTY_FIELDS)
                       if first.get(key) != second.get(key))
    first_root, second_root = after['inventoryBefore']['rootInfo'], after['inventoryAfter']['rootInfo']
    assert {key: value for key, value in first_root.items() if key not in PROPERTY_FIELDS} == {
        key: value for key, value in second_root.items() if key not in PROPERTY_FIELDS}
    changed.extend('root.' + key for key in sorted(PROPERTY_FIELDS)
                   if first_root.get(key) != second_root.get(key))
    changed.sort()
    for capture in [after['inventoryBefore'], after['inventoryAfter']]:
        assert capture['inventoryComplete'] is True and capture['inventoryErrors'] == []
        assert capture['rootInfo']['kind'] == 'directory' and capture['rootInfo']['sddl']
    for entry in leaves.values():
        assert entry['kind'] == 'file' and entry['sddl'] and entry['streamsSupported'] is True
        assert len(entry['streams']) == 1 and entry['streams'][0] == {'name': ':$DATA', 'length': entry['size']}
        if entry['name'].endswith('.record'):
            wire = base64.b64decode(entry['recordBytesBase64'], validate=True)
            assert len(wire) == entry['size'] <= 65536
            assert hashlib.sha256(wire).hexdigest() == entry['sha256']
    assert after['inventoryAfter']['rootInfo']['exists'] is True
    source = leaves['source.marker']
    assert source['size'] == 65536 and source['sha256'] == MARKER_HASH
    result = after['inspect']
    observed = terminal(result)
    assert observed['outcome'] in [SUCCESS, 'receipt-inspection-refused']
    assert observed['effectsAttempted'] is False and observed['ownedHandlesRemoved'] == 0
    assert observed['sourceRetained'] is observed['rootRetained'] is observed['observationOnly'] is True
    basic = inventory(result)
    assert set(basic) == set(leaves)
    for name, entry in basic.items():
        assert all(entry[key] == leaves[name][key] for key in ['name', 'size', 'sha256'])
    assert all(value == first_root[key] for key, value in result['rootInfo'].items() if key not in PROPERTY_FIELDS)
    if context is None:
        assert observed['outcome'] == 'receipt-inspection-refused'
    if observed['outcome'] == SUCCESS:
        assert context is not None
        for name in ['output.marker', 'receipt.record', 'prepared.record', 'intent.record', 'observation.record']:
            assert name in leaves
        assert leaves['output.marker']['sha256'] == MARKER_HASH and leaves['output.marker']['size'] == 65536
        assert leaves['receipt.record']['sha256'] == context['receipt']['sha256']
        assert leaves['receipt.record']['size'] == context['receipt']['info']['size']
        receipt = decoded_record(leaves['receipt.record'])
        assert receipt == {'purpose': 'imageinfo-od11-receipt-v1',
                           'protocol': 'imageinfo-new-output-protocol-v1',
                           'profile': 'unqualified-windows-marker-v1', 'prior': context['prior']}
        for record in context['prior']['records']:
            actual = leaves[record['name'] + '.record']
            assert actual['sha256'] == record['sha256'] and actual['size'] == record['info']['size']
            value = decoded_record(actual)
            assert value['purpose'] == 'imageinfo-od11-marker-v1'
            assert value['phase'] == {'prepared': 'prepared', 'intent': 'publication-intent', 'observation': 'recovery-required'}[record['name']]
            assert value['committed'] is value['namespaceAcknowledged'] is False
            assert value['expectedAbsence'] is value['observationOnly'] is True
            for key in ['root', 'source', 'candidate', 'sha256', 'persistenceMode']:
                assert value[key] == context['prior'][key]
    observations = {'byteNameInventoryUnchanged': True,
                    'propertyObservationsUnchanged': not changed,
                    'changedPropertyFields': changed,
                    'inspectionUnchanged': leaves == later and first_root == second_root}
    return observed, leaves, observations


def decoded_record(entry):
    wire = base64.b64decode(entry['recordBytesBase64'], validate=True)
    envelope = json.loads(wire)
    assert set(envelope) == {'body', 'sha256'}
    assert isinstance(envelope['body'], str)
    assert hashlib.sha256(envelope['body'].encode('utf-8')).hexdigest() == envelope['sha256']
    return json.loads(envelope['body'])


def survivor_classes(leaves, context):
    """Keep crash disagreements as observations rather than assuming survival."""
    marker_states = {}
    for name in ['source.marker', 'candidate.marker', 'output.marker']:
        entry = leaves.get(name)
        marker_states[name] = ('absent' if entry is None else 'matching-marker'
            if entry['size'] == 65536 and entry['sha256'] == MARKER_HASH else 'conflicting-marker')
    records = []
    for name, entry in sorted(leaves.items()):
        if not name.endswith('.record'):
            continue
        state = 'corrupt-or-out-of-scope'
        try:
            value = decoded_record(entry)
            if name == 'receipt.record':
                assert set(value) == {'purpose', 'protocol', 'profile', 'prior'}
                assert value['purpose'] == 'imageinfo-od11-receipt-v1'
                assert value['protocol'] == 'imageinfo-new-output-protocol-v1'
                assert value['profile'] == 'unqualified-windows-marker-v1'
                prior = value['prior']
                assert prior['purpose'] == 'imageinfo-od11-caller-context-v1'
                assert prior['stage'] == 'after-publication' and prior['stoppedBeforePublication'] is False
                assert prior['persistenceMode'] == 'write-through' and prior['sha256'] == MARKER_HASH
                assert [record['name'] for record in prior['records']] == ['prepared', 'intent', 'observation']
                state = 'valid-unattributed'
                if context is not None:
                    state = ('matching-context' if prior == context['prior']
                        and entry['sha256'] == context['receipt']['sha256']
                        and entry['size'] == context['receipt']['info']['size'] else 'conflicting-context')
            else:
                expected_phase = {'prepared.record': 'prepared', 'intent.record': 'publication-intent',
                                  'observation.record': 'recovery-required'}[name]
                assert value['purpose'] == 'imageinfo-od11-marker-v1' and value['phase'] == expected_phase
                assert value['target'] == 'output.marker'
                assert value['committed'] is value['namespaceAcknowledged'] is False
                assert value['observationOnly'] is value['expectedAbsence'] is True
                assert value['sha256'] == MARKER_HASH and value['persistenceMode'] == 'write-through'
                state = 'valid-unattributed'
                if context is not None:
                    bound = next(record for record in context['prior']['records'] if record['name'] + '.record' == name)
                    matches = entry['size'] == bound['info']['size'] and entry['sha256'] == bound['sha256']
                    matches = matches and all(value[key] == context['prior'][key]
                        for key in ['root', 'source', 'candidate', 'sha256', 'persistenceMode'])
                    state = 'matching-context' if matches else 'conflicting-context'
        except (AssertionError, KeyError, TypeError, ValueError, StopIteration):
            pass
        records.append({'name': name, 'size': entry['size'], 'sha256': entry['sha256'], 'classification': state})
    receipt = next((record['classification'] for record in records if record['name'] == 'receipt.record'), 'absent')
    return {'markerBytes': marker_states, 'receiptClassification': receipt, 'recordSurvivors': records}


def audit(root, binary, source_root, public):
    assert not (root / 'incomplete.private.json').exists()
    binding = source_bindings(root, binary, source_root)
    agent_hash = sha(root / 'served-agent.private.ps1')
    hello(read(root / 'initial-hello.private.json'), agent_hash)
    continuity = read(root / 'host-continuity.private.json')
    assert continuity['sameBoot'] is True
    assert datetime.datetime.fromisoformat(continuity['before']) == datetime.datetime.fromisoformat(continuity['after'])
    expected = [('normal', None, None)] + [(kind + '-' + phase, kind, phase) for kind in KINDS for phase in PHASES]
    summary = read(root / 'summary.private.json')
    assert [row['id'] for row in summary['cases']] == [name for name, _, _ in expected]
    assert summary['caseCount'] == 34
    rows, bugchecks, postboots = [], set(), []
    for name, kind, phase in expected:
        folder = root / name
        before, after = read(folder / 'before.private.json'), read(folder / 'after.private.json')
        terminal(before['prepare'], 'owned-source-prepared')
        context = live_capture(folder, before, after, phase, kind)
        first, second = hello(before['hello'], agent_hash), hello(after['hello'], agent_hash)
        if kind in ['nmi', 'emulator-kill']:
            reboot(folder, before, after, kind, phase, agent_hash, bugchecks, postboots)
        else:
            assert first == second
            assert not (folder / 'reboot.private.json').exists()
        observed, leaves, observations = inspect(before, after, context)
        if kind is None:
            assert observed['outcome'] == SUCCESS
        row = {'id': name, 'faultKind': kind, 'barrier': phase,
               'receiptContextCaptured': context is not None, 'inspection': observed['outcome'],
               'inspectionExitCode': after['inspect']['exitCode'],
               'outputPresent': 'output.marker' in leaves, 'receiptPresent': 'receipt.record' in leaves,
               'bootChanged': first != second,
               'sourceRetained': True, 'rootRetained': True}
        row.update({key: False for key in FLAGS})
        row.update(observations)
        row.update(survivor_classes(leaves, context))
        rows.append(row)
        reported = summary['cases'][len(rows) - 1]
        for key in ['id', 'barrier', 'receiptContextCaptured', 'inspection', 'inspectionExitCode', 'outputPresent', 'receiptPresent', 'bootChanged',
                    'byteNameInventoryUnchanged', 'propertyObservationsUnchanged', 'changedPropertyFields', 'inspectionUnchanged']:
            assert reported[key] == row[key], (key, reported, row)
    assert len(bugchecks) == 11 and len(postboots) == 22
    manifest = {path.relative_to(root).as_posix(): {'sha256': sha(path), 'size': path.stat().st_size}
                for path in sorted(root.rglob('*')) if path.is_file() and path.name != 'receipt-audit.private.json'}
    (root / 'receipt-audit.private.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    result = {'schemaVersion': 1, 'observedOn': datetime.date.today().isoformat(),
              'sourceRevision': binding['sourceRevision'], 'data': 'authored marker bytes only',
              'workerSha256': sha(binary), 'guestBuild': '26300', 'caseCount': 34,
              'faultRuns': 33, 'processTerminationFaults': 11, 'emulatorTerminationFaults': 11,
              'freshNmiBugchecks': 11, 'distinctPostFaultBootsVerified': 22,
              'unchangedByteNameInventoryPairs': 34,
              'unchangedPropertyObservationPairs': sum(row['propertyObservationsUnchanged'] for row in rows),
              'unchangedReceiptInspectionInventories': sum(row['inspectionUnchanged'] for row in rows),
              'propertyObservationDriftPairs': sum(not row['propertyObservationsUnchanged'] for row in rows),
              'standardWorkerToken': True,
              'hostBootUnchanged': True, 'frozenSourceGitBlobBindingsVerified': True,
              'servedAgentBytesBoundAcrossFaults': True, 'controllerSourceCopiesVerified': True,
              'auditedCaptureFiles': len(manifest), 'cases': rows,
              'enabledProfiles': 0, 'physicalPowerLossRuns': 0,
              'callerAuthorityAuthenticated': False, 'custodyFreshnessProven': False,
              'limits': 'Finite NTFS/QCOW2 marker observations. Host caches remain alive; guest OS I/O shares the test volume. NMI bugchecks use controlled emulator exit/relaunch. Metadata differences between inventory observations do not establish that inspection caused a change; observation-source uncertainty remains. Flush returns and surviving names are observations, not qualified namespace persistence, durable receipt authentication, automatic custody, repair, production or RAW admission.'}
    result.update({key: False for key in FLAGS})
    public.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: result[key] for key in ['caseCount', 'faultRuns', 'freshNmiBugchecks', 'auditedCaptureFiles']}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['root', 'binary', 'source-root', 'public']:
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    audit(Path(args.root).resolve(), Path(args.binary).resolve(), Path(args.source_root).resolve(), Path(args.public))


if __name__ == '__main__':
    main()
