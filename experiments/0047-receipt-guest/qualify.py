"""Observe 33 interrupted receipt cells in the retained disposable Windows guest.

No observation here grants namespace, durability, repair, or production authority.
Receipt context is captured from actual worker output outside transaction records.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import urllib.request

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent / '0022-ordinary-output'
sys.path.insert(0, str(TOOLS))
from guest_qualify import (assert_reports, hello, job, queue, state,
                          verify_guest_token, wait_event)
from restart_guest import faults
from windows_guest import AGENT

SOURCE_COMMIT = 'b819f54533c495b332c3d4dbb0caccef49923036'
MARKER_HASH = hashlib.sha256(b'3' * 65536).hexdigest()
PHASES = ['before-namespace-call', 'published', 'installed-file-flushed',
          'parent-flushed', 'observation-file-flushed', 'observation-parent-flushed',
          'observed-record-flushed', 'receipt-written', 'receipt-file-flushed',
          'receipt-parent-flushed', 'final-checked']
KINDS = ['process-kill', 'emulator-kill', 'nmi']
FLAGS = ('committed', 'namespaceAcknowledged', 'productionPublicationAllowed', 'repairAllowed')
PROPERTY_FIELDS = {'attributes', 'creationTimeUtc', 'lastWriteTimeUtc', 'sddl'}
SUCCESS = 'observed-receipt-recovery-required'


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_binding(binary, source_root):
    frozen = list((source_root / 'experiments/0032-windows-publication/src').glob('*.rs'))
    frozen += list((source_root / 'experiments/0028-recovery-evidence/src').glob('*.rs'))
    frozen += [source_root / name for name in [
        'rust-toolchain.toml', 'experiments/0028-recovery-evidence/Cargo.toml',
        'experiments/0028-recovery-evidence/Cargo.lock',
        'experiments/0032-windows-publication/Cargo.toml',
        'experiments/0032-windows-publication/Cargo.lock',
        'experiments/0038-staging-cleanup/src/staging.rs',
        'experiments/0038-staging-cleanup/src/disposition.rs']]
    if len(frozen) < 10 or not all(path.is_file() for path in frozen):
        raise RuntimeError('Complete frozen #0046 sources are required')
    checkout = HERE.parents[1]
    current = [Path(__file__).resolve(), HERE / 'audit.py'] + [TOOLS / name for name in [
        'windows_guest.py', 'guest_qualify.py', 'restart_guest.py']]
    return {'sourceRevision': SOURCE_COMMIT, 'workerSha256': digest(binary),
            'frozenSources': {p.relative_to(source_root).as_posix(): digest(p) for p in sorted(frozen)},
            'controllerSources': {p.relative_to(checkout).as_posix(): digest(p) for p in sorted(current)}}


def served_agent(captures, expected_worker):
    payload = urllib.request.urlopen('http://127.0.0.1:18722/agent.ps1', timeout=10).read()
    if payload != AGENT.encode('utf-8'):
        raise RuntimeError('HTTP server is serving a different guest agent')
    metadata = json.load(urllib.request.urlopen('http://127.0.0.1:18722/meta', timeout=10))
    if metadata['sha256'] != expected_worker:
        raise RuntimeError('HTTP server is serving a different worker')
    (captures / 'served-agent.private.ps1').write_bytes(payload)
    write(captures / 'server-meta.private.json', metadata)
    return hashlib.sha256(payload).hexdigest()


def fault_target(root, folder, kind, checkpoint):
    pid = int((root / 'qemu.pid').read_text())
    args = [item.decode() for item in Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0') if item]
    disk, qmp = root / 'windows.qcow2', root / 'qmp'
    if (not args or Path(args[0]).name != 'qemu-system-x86_64'
            or not any(argument.split(',')[0] == 'file=' + str(disk) for argument in args)
            or not any(argument == f'unix:{qmp},server=on,wait=off' for argument in args)
            or not qmp.is_socket()):
        raise RuntimeError('Refuse unrelated or unverified emulator target')
    write(folder / 'fault-target.private.json', {
        'pid': pid, 'cmdline': args, 'guestRoot': str(root), 'disk': str(disk),
        'qmpSocket': str(qmp), 'kind': kind,
        'checkpoint': checkpoint['value']['event']['barrier'], 'verifiedTarget': True})


def invoke(request):
    queue(request)
    return wait_event(lambda e: e['path'] == '/result'
                      and e['value'].get('id') == request['id'])['value']


def reports(result):
    events = [json.loads(line) for line in result['stdout']]
    for event in events:
        assert all(event.get(flag) is False for flag in FLAGS), event
    return events


def terminal(result):
    return next((event for event in reversed(reports(result)) if 'outcome' in event), None)


def live_events(identifier):
    return [entry for entry in state() if entry['value'].get('id') == identifier]


def receipt_context(entries):
    contexts = [entry['value']['event']['receiptContext'] for entry in entries
                if entry['path'] == '/event' and 'receiptContext' in entry['value']['event']]
    assert not contexts or all(context == contexts[0] for context in contexts)
    return contexts[-1] if contexts else None


def inventory(result):
    assert result['exitCode'] == 0
    files = {item['name']: item for item in result['files']}
    assert len(files) == len(result['files']) and not any(item.get('inaccessible') for item in files.values())
    assert result['rootInfo']['exists']
    assert files['source.marker']['sha256'] == MARKER_HASH
    assert files['source.marker']['size'] == 65536
    return files


def flat_inventory(result):
    files = inventory(result)
    assert result['inventoryComplete'] and not result['inventoryErrors']
    assert all(item['kind'] == 'file' for item in files.values())
    assert result['rootInfo']['kind'] == 'directory'
    return files


def compare_inventories(before, after):
    """Keep exact byte/name checks separate from property observations.

    Property observations can differ across a read-only inspection interval;
    their cause is not established. Retain both raw snapshots and field names without treating
    observational equality as a continuous property-exclusion guarantee.
    """
    before_files, after_files = flat_inventory(before), flat_inventory(after)
    assert before_files.keys() == after_files.keys()
    changed = []
    pairs = [(name, before_files[name], after_files[name]) for name in sorted(before_files)]
    pairs.append(('root', before['rootInfo'], after['rootInfo']))
    for name, left, right in pairs:
        # This includes kinds, names, sizes, hashes, stream lists and captured
        # record bytes. Unknown non-property fields also require exact equality.
        assert {key: value for key, value in left.items() if key not in PROPERTY_FIELDS} == {
            key: value for key, value in right.items() if key not in PROPERTY_FIELDS}
        for key in sorted(PROPERTY_FIELDS):
            if (key in left) != (key in right) or left.get(key) != right.get(key):
                changed.append(name + '.' + key)
    return sorted(changed)


def run(root, binary, source_root, output=None):
    root, binary, source_root = (Path(p).resolve() for p in (root, binary, source_root))
    manifest = json.loads((root / 'guest.private.json').read_text())
    if manifest['root'] != str(root) or manifest['uid'] != os.getuid():
        raise RuntimeError('Guest root/operator mismatch')
    captures = Path(output).resolve() if output else root / ('receipt-' + str(int(time.time())))
    captures.mkdir(exist_ok=False)
    initial = hello()
    verify_guest_token(initial['value'])
    assert initial['value']['build'] == '26300'
    write(captures / 'initial-hello.private.json', initial)
    binding = source_binding(binary, source_root)
    write(captures / 'source-binding.private.json', binding)
    (captures / 'driver-source.private.py').write_bytes(Path(__file__).read_bytes())
    checkout = HERE.parents[1]
    for relative, expected in binding['controllerSources'].items():
        target = captures / 'controller-sources.private' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((checkout / relative).read_bytes())
        assert digest(target) == expected
    agent_hash = served_agent(captures, binding['workerSha256'])
    assert initial['value']['scriptSha256'] == agent_hash
    rows, postboots, bugchecks = [], set(), set()
    print(json.dumps({'captures': str(captures), 'sourceCommit': SOURCE_COMMIT}), flush=True)
    try:
        matrix = [('normal', None, None)] + [(kind + '-' + phase, kind, phase)
                                              for kind in KINDS for phase in PHASES]
        for name, kind, phase in matrix:
            folder = captures / name
            folder.mkdir()
            case = 'c47-' + name + '-' + str(int(time.time()))
            before = hello()
            verify_guest_token(before['value'])
            assert before['value']['build'] == '26300'
            assert before['value']['scriptSha256'] == agent_hash
            prepared = job(case + '-prepare', case, 'ordinary-prepare')
            assert_reports(prepared)
            prepared_files = inventory(prepared)
            request = {'id': case + '-live', 'action': 'run', 'case': case, 'mode': 'ordinary-receipt'}
            if phase:
                request['stopAt'] = phase
            if kind == 'process-kill':
                request['control'] = 'terminate'
            queue(request)
            live_result = None
            checkpoint = None
            if phase:
                checkpoint = wait_event(lambda e: e['path'] == '/event'
                                        and e['value'].get('id') == request['id']
                                        and e['value']['event'].get('barrier') == phase)
                # The native event precedes supervisor export. Wait until the
                # no-continuation hold is captured before interrupting the guest.
                wait_event(lambda e: e['path'] == '/event'
                           and e['value'].get('id') == request['id']
                           and e['value']['event'].get('supervisorControl', {}).get('barrier') == phase
                           and e['value']['event'].get('supervisorControl', {}).get('control') == 'held')
            else:
                live_result = wait_event(lambda e: e['path'] == '/result'
                                         and e['value'].get('id') == request['id'])['value']
                assert live_result['exitCode'] == 0 and terminal(live_result)['outcome'] == SUCCESS
            context = receipt_context(live_events(request['id']))
            write(folder / 'before.private.json', {'case': case, 'prepare': prepared, 'hello': before,
                  'request': request, 'checkpoint': checkpoint, 'receiptContext': context})
            print(json.dumps({'case': name, 'barrier': phase, 'fault': kind}), flush=True)
            after_boot = before
            if kind == 'process-kill':
                live_result = wait_event(lambda e: e['path'] == '/result'
                                         and e['value'].get('id') == request['id'])['value']
                termination = live_result['processTermination']
                assert termination['barrier'] == phase and termination['control'] == 'terminate'
                assert termination['killCalled'] and termination['exitWaitCompleted']
                assert not termination['barrierContinuationSent'] and live_result['exitCode'] != 0
                assert terminal(live_result) is None
                after_boot = hello()
                assert after_boot['value']['boot'] == before['value']['boot']
            elif kind:
                fault_target(root, folder, kind, checkpoint)
                after_boot = faults(root, folder, kind, before, checkpoint)
                boot = after_boot['value']['boot']
                assert boot not in postboots
                postboots.add(boot)
                reboot = json.loads((folder / 'reboot.private.json').read_text())
                if kind == 'nmi':
                    from guest_qualify import fresh_bugcheck
                    os_events = reboot['events'].get('events') or []
                    if isinstance(os_events, dict):
                        os_events = [os_events]
                    keys = {(str(e['TimeCreated']), e['Message']) for e in os_events
                            if fresh_bugcheck(e, checkpoint['at'])}
                    assert keys and not keys.intersection(bugchecks)
                    bugchecks.update(keys)
            verify_guest_token(after_boot['value'])
            assert after_boot['value']['build'] == '26300'
            assert after_boot['value']['scriptSha256'] == agent_hash
            before_request = {'id': case + '-inventory-before', 'action': 'run',
                              'case': case, 'mode': 'ordinary-inventory'}
            before_inventory = invoke(before_request)
            files = flat_inventory(before_inventory)
            for key in ('name', 'size', 'sha256'):
                assert files['source.marker'][key] == prepared_files['source.marker'][key]
            inspect_request = {'id': case + '-inspect', 'action': 'run', 'case': case,
                               'mode': 'ordinary-receipt-inspect', 'receiptContext': context}
            inspection = invoke(inspect_request)
            after_request = dict(before_request, id=case + '-inventory-after')
            after_inventory = invoke(after_request)
            write(folder / 'after.private.json', {'hello': after_boot, 'liveResult': live_result,
                  'inventoryBeforeRequest': before_request, 'inventoryBefore': before_inventory,
                  'inspectRequest': inspect_request, 'inspect': inspection,
                  'inventoryAfterRequest': after_request, 'inventoryAfter': after_inventory})
            write(folder / 'controller-events.private.json', live_events(request['id']))
            changed_properties = compare_inventories(before_inventory, after_inventory)
            inspection_unchanged = (files == flat_inventory(after_inventory)
                                    and before_inventory['rootInfo'] == after_inventory['rootInfo'])
            report = terminal(inspection)
            assert inspection['exitCode'] in (0, 5)
            if report:
                assert report['outcome'] in (SUCCESS, 'receipt-inspection-refused')
                assert not report['effectsAttempted'] and report['ownedHandlesRemoved'] == 0
            if context is None:
                assert report is None or report['outcome'] != SUCCESS
            if kind is None:
                assert context is not None and report and report['outcome'] == SUCCESS
            row = {'id': name, 'faultKind': kind, 'barrier': phase,
                   'receiptContextCaptured': context is not None,
                   'inspection': report['outcome'] if report else 'input-refused',
                   'inspectionExitCode': inspection['exitCode'], 'sourceRetained': True,
                   'rootRetained': True, 'inspectionUnchanged': inspection_unchanged,
                   'byteNameInventoryUnchanged': True,
                   'propertyObservationsUnchanged': not changed_properties,
                   'changedPropertyFields': changed_properties,
                   'outputPresent': 'output.marker' in files, 'receiptPresent': 'receipt.record' in files,
                   'bootChanged': bool(kind and kind != 'process-kill'),
                   **dict.fromkeys(FLAGS, False)}
            rows.append(row)
            write(captures / 'progress.private.json', {'cases': rows})
            print(json.dumps(row), flush=True)
        final_binding = source_binding(binary, source_root)
        write(captures / 'source-binding-after.private.json', final_binding)
        assert final_binding == binding
        write(captures / 'summary.private.json', {'sourceCommit': SOURCE_COMMIT, 'cases': rows,
              'caseCount': 34, 'processTerminationFaults': 11, 'nmiFaults': 11,
              'emulatorTerminationFaults': 11, 'physicalPowerLossRuns': 0, 'hostCrashed': False,
              'enabledProfiles': 0, **dict.fromkeys(FLAGS, False)})
        print(json.dumps({'captures': str(captures), 'caseCount': len(rows), 'complete': True}), flush=True)
    except BaseException:
        write(captures / 'incomplete.private.json', {'cases': rows})
        print('Retained incomplete run ' + str(captures), flush=True)
        raise


if __name__ == '__main__':
    if not __debug__:
        raise RuntimeError('Qualification requires assertions')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    parser.add_argument('--binary', required=True)
    parser.add_argument('--source-root', required=True)
    parser.add_argument('--output')
    args = parser.parse_args()
    run(args.root, args.binary, args.source_root, args.output)
