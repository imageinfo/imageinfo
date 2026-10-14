"""Interrupt the existing disposable Windows guest at four custody checkpoints.

The supervisor in windows_guest.py owns the original live process and saves each
whole history before the controller is permitted to fault the isolated guest.
The caller histories are observations of this test run, not authenticated custody.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import urllib.request

TOOLS = Path(__file__).resolve().parents[1] / '0022-ordinary-output'
sys.path.insert(0, str(TOOLS))
from guest_qualify import (assert_reports, hello, job, queue, state,
                          verify_guest_token, wait_event)
from restart_guest import faults
from windows_guest import AGENT

SOURCE_COMMIT = 'b3815765d5230bec979e8a38b1cf9c6f384d1682'
MARKER_HASH = hashlib.sha256(b'3' * 65536).hexdigest()
CELLS = [
    ('captured-only-nmi', 'captured-only', 'nmi', 'captured-unconfirmed'),
    ('stopped-kill', 'stopped', 'emulator-kill', 'stop-attested-before-publication'),
    ('fenced-nmi', 'fenced', 'nmi', 'publication-release-uncertain'),
    ('renewed-kill', 'renewed', 'emulator-kill', 'observation-renewed'),
]


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_binding(binary, source_root):
    """Bind Rust to the frozen #0043 archive, and orchestration to this checkout."""
    frozen = list((source_root / 'experiments/0032-windows-publication/src').glob('*.rs'))
    frozen += list((source_root / 'experiments/0028-recovery-evidence/src').glob('*.rs'))
    frozen += [source_root / name for name in [
        'rust-toolchain.toml',
        'experiments/0028-recovery-evidence/Cargo.toml',
        'experiments/0028-recovery-evidence/Cargo.lock',
        'experiments/0032-windows-publication/Cargo.toml',
        'experiments/0032-windows-publication/Cargo.lock',
        'experiments/0038-staging-cleanup/src/staging.rs',
        'experiments/0038-staging-cleanup/src/disposition.rs',
    ]]
    if len(frozen) < 10 or not all(path.is_file() for path in frozen):
        raise RuntimeError('Complete frozen #0043 sources are required')
    checkout = Path(__file__).resolve().parents[2]
    current = [Path(__file__).resolve(), Path(__file__).with_name('audit.py')] + [TOOLS / name for name in [
        'windows_guest.py', 'guest_qualify.py', 'restart_guest.py',
    ]]
    return {
        'sourceRevision': SOURCE_COMMIT,
        'workerSha256': digest(binary),
        'frozenSources': {path.relative_to(source_root).as_posix(): digest(path)
                          for path in sorted(frozen)},
        'controllerSources': {path.relative_to(checkout).as_posix(): digest(path)
                          for path in sorted(current)},
    }


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
    disk = root / 'windows.qcow2'
    qmp = root / 'qmp'
    if (not args or Path(args[0]).name != 'qemu-system-x86_64'
            or not any(argument.split(',')[0] == 'file=' + str(disk) for argument in args)
            or not qmp.is_socket()):
        raise RuntimeError('Refuse unrelated or unverified emulator target')
    write(folder / 'fault-target.private.json', {
        'pid': pid, 'cmdline': args, 'guestRoot': str(root), 'disk': str(disk),
        'qmpSocket': str(qmp), 'kind': kind,
        'checkpoint': checkpoint['value']['event']['custodyCheckpoint'],
        'verifiedTarget': True,
    })


def terminal(result):
    reports = assert_reports(result)
    return next(report for report in reversed(reports) if 'outcome' in report)


def invoke(request):
    queue(request)
    return wait_event(lambda entry: entry['path'] == '/result'
                      and entry['value'].get('id') == request['id'])['value']


def action(case, mode, context, suffix):
    request = {'id': case + '-' + suffix, 'action': 'run', 'case': case,
               'mode': mode, 'callerContext': context}
    return {'request': request, 'result': invoke(request)}


def assert_refusal(call):
    report = terminal(call['result'])
    assert report['outcome'] == 'restart-refused-before-effects'
    assert not report['effectsAttempted'] and report['ownedHandlesRemoved'] == 0


def assert_source(result, *, output):
    files = {item['name']: item for item in result['files']}
    assert files['source.marker']['sha256'] == MARKER_HASH
    assert ('output.marker' in files) == output
    if output:
        assert files['output.marker']['sha256'] == MARKER_HASH


def run(root, binary, source_root, output=None):
    root = Path(root).resolve()
    binary = Path(binary).resolve()
    source_root = Path(source_root).resolve()
    manifest = json.loads((root / 'guest.private.json').read_text())
    if manifest['root'] != str(root) or manifest['uid'] != os.getuid():
        raise RuntimeError('Guest root/operator mismatch')
    captures = Path(output).resolve() if output else root / ('custody-' + str(int(time.time())))
    captures.mkdir(exist_ok=False)
    initial = hello()
    verify_guest_token(initial['value'])
    write(captures / 'initial-hello.private.json', initial)
    binding = source_binding(binary, source_root)
    write(captures / 'source-binding.private.json', binding)
    (captures / 'driver-source.private.py').write_bytes(Path(__file__).read_bytes())
    checkout = Path(__file__).resolve().parents[2]
    for relative, expected in binding['controllerSources'].items():
        target = captures / 'controller-sources.private' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((checkout / relative).read_bytes())
        assert digest(target) == expected
    agent_hash = served_agent(captures, binding['workerSha256'])
    assert initial['value']['scriptSha256'] == agent_hash
    rows = []
    print(json.dumps({'captures': str(captures), 'sourceCommit': SOURCE_COMMIT}), flush=True)
    try:
        for name, plan, kind, expected_state in CELLS:
            folder = captures / name
            folder.mkdir()
            case = 'c44-' + name + '-' + str(int(time.time()))
            before = hello()
            verify_guest_token(before['value'])
            assert before['value']['scriptSha256'] == agent_hash
            prepared = job(case + '-prepare', case, 'ordinary-prepare')
            assert_reports(prepared)
            request = {'id': case + '-live', 'action': 'run', 'case': case,
                       'mode': 'ordinary-write-through', 'custodyPlan': plan}
            queue(request)
            expected_checkpoint = 'custody-' + ('captured' if plan == 'captured-only' else plan)
            checkpoint = wait_event(lambda entry: entry['path'] == '/event'
                                    and entry['value'].get('id') == request['id']
                                    and entry['value']['event'].get('custodyCheckpoint') == expected_checkpoint)
            observation = checkpoint['value']['event']
            assert observation['supervisorObservation']
            assert observation['custodyCase'] == case + '-custody'
            assert observation['originalExitedBeforeRelease'] == (plan == 'stopped')
            assert observation['publicationContinuationSent'] == (plan == 'renewed')
            assert observation['callerContext']['stoppedBeforePublication'] is False
            assert len(observation['journal']['events']) == {'captured-only': 1, 'stopped': 2, 'fenced': 2, 'renewed': 4}[plan]
            write(folder / 'before.private.json', {'case': case, 'prepare': prepared,
                  'hello': before, 'request': request, 'checkpoint': checkpoint})
            # Persist the complete supervisor observation before the guest fault.
            print(json.dumps({'case': name, 'checkpoint': expected_checkpoint, 'fault': kind}), flush=True)
            fault_target(root, folder, kind, checkpoint)
            after_boot = faults(root, folder, kind, before, checkpoint)
            assert after_boot['value']['scriptSha256'] == agent_hash
            inspection_request = {'id': case + '-custody-inspect', 'action': 'run',
                                  'case': case, 'mode': 'ordinary-custody-inspect',
                                  'custodyCase': observation['custodyCase'],
                                  'custodyRequest': {'expectedCustodyRoot': observation['custodyRoot']}}
            transaction_before_request = {'id': case + '-transaction-before', 'action': 'run',
                                          'case': case, 'mode': 'ordinary-inspect'}
            transaction_before = invoke(transaction_before_request)
            assert_reports(transaction_before)
            inspection = invoke(inspection_request)
            transaction_after_request = dict(transaction_before_request, id=case + '-transaction-after')
            transaction_after = invoke(transaction_after_request)
            assert_reports(transaction_after)
            after = {'inspectRequest': inspection_request, 'inspect': inspection, 'actions': [],
                     'transactionBeforeRequest': transaction_before_request,
                     'transactionBefore': transaction_before,
                     'transactionAfterRequest': transaction_after_request,
                     'transactionAfter': transaction_after}
            write(folder / 'after.private.json', after)
            assert transaction_before['files'] == transaction_after['files']
            report = terminal(inspection)
            assert report['outcome'] == 'custody-history-observed'
            assert report['custodyState'] == expected_state
            assert report['journal'] == observation['journal']
            current_root, expected_root = report['custodyRoot'], observation['custodyRoot']
            # Creating a snapshot can change directory mtime; the worker binds
            # identity, creation time and non-archive attributes for this root.
            assert current_root['identity'] == expected_root['identity']
            assert current_root['creationTime'] == expected_root['creationTime']
            assert current_root['attributes'] & ~32 == expected_root['attributes'] & ~32
            assert not report['effectsAttempted'] and report['transactionMutations'] == 0
            assert not report['callerAuthorityAuthenticated'] and not report['custodyFreshnessProven']
            candidate = report.get('callerContextCandidate')
            assert candidate == observation.get('callerContextCandidate')

            def record(call):
                after['actions'].append(call)
                write(folder / 'after.private.json', after)
                return call

            if plan in ('captured-only', 'fenced'):
                assert candidate is None
                refused = record(action(case, 'ordinary-restart-prune', observation['callerContext'], 'unattested-prune'))
                assert_refusal(refused)
                assert_source(refused['result'], output=False)
                repeated = record(action(case, 'ordinary-restart-prune', observation['callerContext'], 'unattested-prune-again'))
                assert_refusal(repeated)
                assert repeated['result']['files'] == refused['result']['files']
                outcome = 'unattested-prune-refused'
            elif plan == 'stopped':
                assert candidate['stage'] == 'before-publication' and candidate['stoppedBeforePublication']
                pruned = record(action(case, 'ordinary-restart-prune', candidate, 'attested-prune'))
                result = terminal(pruned['result'])
                assert result['outcome'] == 'owned-unpublished-handles-pruned'
                assert result['ownedHandlesRemoved'] == 3
                assert_source(pruned['result'], output=False)
                assert [item['name'] for item in pruned['result']['files']] == ['source.marker']
                outcome = result['outcome']
            else:
                assert candidate['stage'] == 'after-publication' and not candidate['stoppedBeforePublication']
                assert len(candidate['records']) == 3
                stale_context = observation['journal']['events'][2]['context']
                assert len(stale_context['records']) == 2
                stale = record(action(case, 'ordinary-restart-observe', stale_context, 'stale-observe'))
                assert_refusal(stale)
                observed = record(action(case, 'ordinary-restart-observe', candidate, 'renewed-observe'))
                result = terminal(observed['result'])
                assert result['outcome'] == 'output-observation-already-present'
                assert not result['effectsAttempted'] and result['ownedHandlesRemoved'] == 0
                assert not result['observationRecordCreated']
                refused = record(action(case, 'ordinary-restart-prune', candidate, 'postpublication-prune'))
                assert_refusal(refused)
                assert stale['result']['files'] == observed['result']['files'] == refused['result']['files']
                assert_source(observed['result'], output=True)
                outcome = result['outcome']
            repeated_inspection_request = dict(inspection_request, id=case + '-custody-inspect-again')
            after['inspectAgainRequest'] = repeated_inspection_request
            after['inspectAgain'] = invoke(repeated_inspection_request)
            write(folder / 'after.private.json', after)
            assert terminal(after['inspectAgain']) == report
            assert after['inspectAgain']['files'] == inspection['files']
            write(folder / 'controller-events.private.json',
                  [entry for entry in state() if entry['value'].get('id') == request['id']])
            rows.append({'id': name, 'fault': kind, 'custodyState': report['custodyState'],
                         'outcome': outcome, 'committed': False})
            print(json.dumps(rows[-1]), flush=True)
        final_binding = source_binding(binary, source_root)
        write(captures / 'source-binding-after.private.json', final_binding)
        assert final_binding == binding
        write(captures / 'summary.private.json', {'sourceCommit': SOURCE_COMMIT,
              'cases': rows, 'caseCount': 4, 'nmiFaults': 2, 'emulatorTerminationFaults': 2,
              'committed': False, 'productionPublicationAllowed': False, 'enabledProfiles': 0})
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
