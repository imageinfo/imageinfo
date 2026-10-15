"""Independent finite native qualification of the process-owned custody API."""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import sys

from runtime import ProcessCustody

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
native_path = HERE.parent / '0100-receipt-timestamps/native.py'
spec = importlib.util.spec_from_file_location('custody_observer', native_path)
native_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native_module)
WORKER = 'f86918a7fb3880cf8e09590fcc7d58155ef64d98c95cf9c2a6afc541c5b040fa'
CASES = ['stop-prune', 'captured-no-authority', 'released-no-prune', 'original-failure',
         'captured-save-failure', 'stop-save-failure', 'fence-save-failure', 'foreign-extra',
         'candidate-substitution', 'partial-prune', 'existing-root', 'below-budget']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    with Path(path).open('xb') as stream:
        stream.write((json.dumps(value, indent=2) + '\n').encode())


def trial(native, binary, root, name):
    folder = root / name
    folder.mkdir()
    runtime_root = folder / 'runtime.marker'
    transaction = runtime_root / 'transaction.marker'
    custody = runtime_root / 'custody.marker'
    events = []
    controls = []
    operations = []
    actors = []
    injected = False

    def observe(phase, event):
        events.append({'phase': phase, 'event': copy.deepcopy(event)})

    def control(phase, event):
        nonlocal injected
        target = {'original-failure': ('original', 'source-guarded'),
                  'captured-save-failure': ('captured-save', 'custody-before-file-flush'),
                  'stop-save-failure': ('stop-save', 'custody-before-file-flush'),
                  'fence-save-failure': ('fence-save', 'custody-before-file-flush'),
                  'partial-prune': ('prune', 'restart-file-removed')}.get(name)
        choice = 'continue'
        if not injected and target == (phase, event.get('barrier')):
            choice = 'fail'
            injected = True
        controls.append({'phase': phase, 'barrier': event.get('barrier'), 'choice': choice})
        return choice

    if name == 'below-budget':
        try:
            ProcessCustody(runtime_root, binary, byte_limit=655359, observe=observe, control=control)
        except Exception as error:
            return {'id': name, 'events': events, 'controls': controls, 'operations': [], 'actors': [],
                    'injectionApplied': False, 'finalBeforeClose': {'transaction': {}, 'custody': {}},
                    'statusBeforeClose': None, 'beginReturnedNormally': False,
                    'constructorError': {'type': type(error).__name__, 'message': str(error)},
                    'runtimeRootExists': runtime_root.exists()}
        raise RuntimeError('Below-budget constructor unexpectedly admitted operation')
    supervisor = ProcessCustody(runtime_root, binary,
                                byte_limit=655359 if name == 'below-budget' else 655360,
                                observe=observe, control=control)

    def inventory():
        return {'transaction': native.inventory(transaction) if transaction.exists() else {},
                'custody': native.inventory(custody) if custody.exists() else {}}

    def call(label, function):
        before = inventory()
        start = len(events)
        try:
            value = function()
            result = {'returned': copy.deepcopy(value), 'error': None}
        except Exception as error:
            result = {'returned': None, 'error': {'type': type(error).__name__, 'message': str(error)}}
        operations.append({'label': label, 'before': before, 'after': inventory(),
                           'eventStart': start, 'eventEnd': len(events),
                           'result': result, 'status': supervisor.status()})
        return result

    try:
        begin = call('begin', supervisor.begin)
        if name in ['original-failure', 'captured-save-failure', 'below-budget']:
            call('prune-denied-after-begin-failure', supervisor.prune)
        elif name == 'captured-no-authority':
            view = supervisor.status()
            view['ownedChildExited'] = True
            view['state'] = 'stopped'
            actors.append({'action': 'mutate-returned-status-copy', 'value': view})
            call('prune-denied-live-child', supervisor.prune)
            call('arbitrary-context-keyword-denied', lambda: supervisor.prune(context={'stoppedBeforePublication': True}))
        elif name in ['released-no-prune', 'fence-save-failure']:
            call('release', supervisor.release)
            call('prune-denied-after-release-attempt', supervisor.prune)
        elif name == 'existing-root':
            call('existing-root-recreation-denied', lambda: ProcessCustody(runtime_root, binary))
            call('prune-denied-original-still-live', supervisor.prune)
        else:
            call('stop', supervisor.stop)
            if name == 'foreign-extra':
                path = transaction / 'foreign.marker'
                with path.open('xb') as stream:
                    stream.write(b'foreign-owned-fixture-extra')
                actors.append({'action': 'extra-name-created', 'sha256': sha(path)})
            elif name == 'candidate-substitution':
                candidate = transaction / 'candidate.marker'
                prior = native.inventory(transaction)['candidate.marker']
                retained = folder / 'retained-original-candidate.marker'
                candidate.rename(retained)
                with candidate.open('xb') as stream:
                    stream.write(b'3' * 65536)
                replacement = native.inventory(transaction)['candidate.marker']
                actors.append({'action': 'same-byte-candidate-identity-substitution',
                               'before': prior, 'replacement': replacement,
                               'retainedOriginalSha256': sha(retained)})
            call('prune', supervisor.prune)
            if name in ['stop-prune', 'partial-prune']:
                call('second-prune-denied', supervisor.prune)
        return {'id': name, 'events': events, 'controls': controls, 'operations': operations,
                'actors': actors, 'injectionApplied': injected, 'finalBeforeClose': inventory(),
                'statusBeforeClose': supervisor.status(), 'beginReturnedNormally': begin['error'] is None}
    finally:
        supervisor.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    args.binary = args.binary.resolve()
    args.root = args.root.resolve()
    if os.name != 'nt' or sha(args.binary) != WORKER:
        raise RuntimeError('Exact frozen Windows marker worker required')
    args.root.mkdir(parents=True, exist_ok=False)
    files = [HERE / 'runtime.py', HERE / 'qualify.py', HERE / 'audit.py', native_path,
             HERE.parent / '0049-cumulative-budget/supervisor.py']
    save(args.root / 'bindings.private.json', {
        'workerSha256': WORKER, 'sourceRevision': 'b819f54533c495b332c3d4dbb0caccef49923036',
        'host': {'system': platform.system(), 'version': platform.version(), 'machine': platform.machine()},
        'pythonSha256': sha(sys.executable),
        'tooling': {path.relative_to(REPO).as_posix(): sha(path) for path in files},
        'schedule': CASES, 'faults': 'explicit protocol fail controls; not native storage errors'})
    native = native_module.Native()
    results = []
    for name in CASES:
        results.append(trial(native, args.binary, args.root, name))
        save(args.root / f'{name}.private.json', results[-1])
    save(args.root / 'complete.private.json', {'cases': len(results), 'workerUnchanged': sha(args.binary) == WORKER})
    print('Retained twelve native process-owned custody cases; no production admission')


if __name__ == '__main__':
    main()
