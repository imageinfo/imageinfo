"""Five native integration observations of process-owned checked receipt custody.

Only authored markers in an exclusively fresh caller root are used. Captures are
private evidence, outside the runtime's fixed logical construction budget.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import sys

from runtime import CheckedReceiptCustody

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ACTOR = 'e378d436ed478cc4fe31ec84ff0ab91f27a459d8c6b636fcb55d0c700c11f941'
INSPECTOR = 'f86918a7fb3880cf8e09590fcc7d58155ef64d98c95cf9c2a6afc541c5b040fa'
MODE = 'ordinary-receipt-checked-flush'
CASES = ['normal', 'terminate-pre-context', 'receipt-property-pre-context',
         'later-output-edit', 'stop-prune']
TOOLING = [
    'experiments/0114-checked-receipt-custody/runtime.py',
    'experiments/0114-checked-receipt-custody/qualify.py',
    'experiments/0114-checked-receipt-custody/audit.py',
    'experiments/0103-process-custody/runtime.py',
    'experiments/0049-cumulative-budget/supervisor.py',
    'experiments/0100-receipt-timestamps/native.py',
    'experiments/0033-owner-rights/actor.py',
    'experiments/0110-receipt-context/audit.py',
    'experiments/0106-receipt-properties/audit_final.py',
]


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, REPO/relative)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    with Path(path).open('xb') as stream:
        stream.write((json.dumps(value, indent=2)+'\n').encode('utf-8'))


class QualificationStop(RuntimeError):
    """An authored caller interruption, causing the runtime to kill/wait its child."""


def trial(native, property_actor, actor, inspector, parent, name):
    folder = parent/name
    folder.mkdir()
    root = folder/'runtime.marker'
    transaction = root/'transaction.marker'
    custody = root/'custody.marker'
    events, controls, actors, operations, admissions = [], [], [], [], []
    stopped = False

    def observe(phase, event):
        events.append({'phase': phase, 'event': copy.deepcopy(event)})

    def control(phase, event):
        nonlocal stopped
        item = {'phase': phase, 'barrier': event['barrier'], 'choice': 'continue'}
        controls.append(item)
        if phase == 'original' and event['barrier'] == 'receipt-written':
            if name == 'terminate-pre-context':
                stopped = True
                item['choice'] = 'caller-exception-kill-wait'
                actors.append({'action': 'caller-exception', 'barrier': 'receipt-written',
                               'eventOrdinal': len(events)-1})
                raise QualificationStop('Authored caller interruption at receipt-written')
            if name == 'receipt-property-pre-context':
                before = native.inventory(transaction)['receipt.record']
                property_actor.act('mtime', transaction/'receipt.record')
                after = native.inventory(transaction)['receipt.record']
                actors.append({'action': 'receipt-last-write', 'barrier': 'receipt-written',
                               'eventOrdinal': len(events)-1, 'before': before, 'after': after})
        return 'continue'

    if name == 'normal':
        for label, options in [('wrong-actor', {'actor': inspector, 'inspector': inspector}),
                               ('wrong-inspector', {'actor': actor, 'inspector': actor}),
                               ('below-budget', {'actor': actor, 'inspector': inspector,
                                                 'byte_limit': 655359})]:
            refused_root = folder/(label+'.marker')
            try:
                CheckedReceiptCustody(refused_root, **options)
                result = {'error': None}
            except Exception as error:
                result = {'error': {'type': type(error).__name__, 'message': str(error)}}
            admissions.append({'label': label, **result, 'rootExists': refused_root.exists()})

    supervisor = CheckedReceiptCustody(root, actor, inspector, observe=observe, control=control)

    def inventory():
        return {'transaction': native.inventory(transaction) if transaction.exists() else {},
                'custody': native.inventory(custody) if custody.exists() else {}}

    def child():
        # Evidence observes the exact runtime-owned object; it supplies no PID or
        # process/context authority to the runtime and never controls another child.
        value = supervisor._original
        if value is None:
            return None
        return {'pid': value.process.pid, 'exitCode': value.process.poll()}

    def call(label, function):
        before, start = inventory(), len(events)
        try:
            result = {'returned': copy.deepcopy(function()), 'error': None}
        except Exception as error:
            result = {'returned': None, 'error': {'type': type(error).__name__, 'message': str(error)}}
        operations.append({'label': label, 'before': before, 'after': inventory(),
                           'eventStart': start, 'eventEnd': len(events), 'result': result,
                           'status': supervisor.status(), 'ownedChild': child()})
        return result

    try:
        if name == 'normal':
            call('inspect-before-begin', supervisor.inspect_receipt)
            call('existing-root', lambda: CheckedReceiptCustody(root, actor, inspector))
        call('begin', supervisor.begin)
        if name == 'stop-prune':
            call('inspect-before-release', supervisor.inspect_receipt)
            call('stop', supervisor.stop)
            call('prune', supervisor.prune)
            call('prune-again', supervisor.prune)
            call('inspect-after-prune', supervisor.inspect_receipt)
        else:
            call('release', supervisor.release)
            if name == 'later-output-edit':
                output = transaction/'output.marker'
                before = native.inventory(transaction)['output.marker']
                with output.open('r+b') as stream:
                    stream.write(b'ordinary-owner-edit')
                    stream.flush()
                    os.fsync(stream.fileno())
                after = native.inventory(transaction)['output.marker']
                actors.append({'action': 'ordinary-owner-output-edit', 'before': before, 'after': after})
            call('inspect', supervisor.inspect_receipt)
            call('prune-after-release', supervisor.prune)
        final = inventory()
        status = supervisor.status()
    finally:
        call('close', supervisor.close)
    call('inspect-after-close', supervisor.inspect_receipt)
    return {'id': name, 'events': events, 'controls': controls, 'actors': actors,
            'admissionRefusals': admissions, 'operations': operations,
            'callerInterruptionApplied': stopped, 'finalBeforeClose': final,
            'statusBeforeClose': status, 'finalAfterClose': inventory(),
            'statusAfterClose': supervisor.status(), 'ownedChildAfterClose': child()}


def run(actor, inspector, root):
    if os.name != 'nt' or sha(actor) != ACTOR or sha(inspector) != INSPECTOR:
        raise RuntimeError('Exact reviewed Windows actor and frozen inspector required')
    root.mkdir(parents=True, exist_ok=False)
    bindings = {'schema': 'imageinfo-checked-custody-qualification-v1',
        'actorPath': str(actor), 'actorSha256': sha(actor), 'inspectorPath': str(inspector),
        'inspectorSha256': sha(inspector), 'mode': MODE, 'schedule': CASES,
        'host': {'system': platform.system(), 'version': platform.version(), 'machine': platform.machine()},
        'pythonSha256': sha(sys.executable),
        'tooling': {relative: sha(REPO/relative) for relative in TOOLING},
        'faultScope': 'caller exception/owned-process termination and native marker property/edit actors; no storage-error or VM fault'}
    save(root/'bindings.private.json', bindings)
    for relative in TOOLING:
        target = root/'tooling.private'/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((REPO/relative).read_bytes())
    native = module('checked114_native', 'experiments/0100-receipt-timestamps/native.py').Native()
    property_actor = module('checked114_property', 'experiments/0033-owner-rights/actor.py').Actor()
    completed = []
    try:
        for name in CASES:
            result = trial(native, property_actor, actor, inspector, root, name)
            save(root/(name+'.private.json'), result)
            completed.append(name)
        after = {'actorSha256': sha(actor), 'inspectorSha256': sha(inspector),
                 'tooling': {relative: sha(REPO/relative) for relative in TOOLING}}
        save(root/'complete.private.json', {'cases': completed, 'after': after})
    except BaseException as error:
        save(root/'failed.private.json', {'completed': completed, 'error': str(error)})
        raise
    print('Retained five checked-custody native integration scenarios; no profile admitted')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--actor', required=True, type=Path)
    parser.add_argument('--inspector', required=True, type=Path)
    parser.add_argument('--root', required=True, type=Path)
    args = parser.parse_args()
    run(args.actor.resolve(), args.inspector.resolve(), args.root.resolve())
