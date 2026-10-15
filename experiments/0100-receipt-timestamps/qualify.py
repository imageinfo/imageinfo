"""Twelve predeclared native timestamp lifecycle cells; frozen worker unchanged."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

from native import Native

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / '0034-source-oplocks'))
from qualify import Process

WORKER = 'f86918a7fb3880cf8e09590fcc7d58155ef64d98c95cf9c2a6afc541c5b040fa'
PHASES = ['receipt-written', 'receipt-file-flushed', 'final-checked']
FLAGS = ['committed', 'namespaceAcknowledged', 'repairAllowed', 'productionPublicationAllowed']


def save(path, value):
    with Path(path).open('xb') as stream:
        stream.write((json.dumps(value, indent=2) + '\n').encode())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def finish(process):
    code = process.finish()
    events = [json.loads(line) for line in process.lines]
    if any(event.get(flag) is not False for event in events for flag in FLAGS):
        raise RuntimeError('False worker flags required')
    return {'exitCode': code, 'events': events, 'controls': process.controls,
            'stderr': ''.join(process.stderr)}


def inspect(binary, transaction, context, folder):
    process = Process([binary, transaction, 'ordinary-receipt-inspect'], folder)
    try:
        process.proc.stdin.write(json.dumps(context, separators=(',', ':')) + '\n')
        process.proc.stdin.flush()
        while True:
            event = process.next()
            if 'barrier' in event:
                process.send()
            if 'outcome' in event:
                break
        return finish(process)
    finally:
        process.stop()
        process.timer.cancel()


def worker_cell(native, binary, root, phase, completion):
    folder = root / f'worker-{phase}-{completion}'
    folder.mkdir()
    transaction = folder / 'transaction.marker'
    prepare = Process([binary, transaction, 'ordinary-prepare'], folder / 'prepare')
    prepared = finish(prepare)
    if prepared['exitCode'] != 0:
        raise RuntimeError('Worker preparation failed')
    process = Process([binary, transaction, 'ordinary-receipt'], folder / 'worker')
    context = phase_context = None
    observer = None
    observations = []
    try:
        while True:
            event = process.next()
            if 'receiptContext' in event:
                context = event['receiptContext']
            if event.get('barrier') == phase:
                if context is None:
                    raise RuntimeError('Actual emitted receipt context required')
                phase_context = copy.deepcopy(context)
                observer = native.open(transaction / 'receipt.record')
                observations.append({'stage': 'at-worker-barrier',
                                     'value': native.observe(transaction / 'receipt.record', observer)})
                if completion == 'terminate':
                    process.stop()
                    break
            if 'barrier' in event:
                process.send()
            if 'outcome' in event:
                break
        result = finish(process)
        if observer is None:
            raise RuntimeError('Selected barrier was not reached')
        observations.append({'stage': 'worker-exited-observer-retained',
                             'value': native.observe(transaction / 'receipt.record', observer)})
        inspections = []
        for name, value in [('phase-context', phase_context), ('latest-context', context)]:
            before = native.inventory(transaction)
            inspected = inspect(binary, transaction, value, folder / ('inspect-' + name))
            after = native.inventory(transaction)
            inspections.append({'contextKind': name, 'actualEmittedContext': value,
                                'before': before, 'result': inspected, 'after': after})
        native.close(observer)
        observer = None
        fresh = native.open(transaction / 'receipt.record')
        try:
            observations.append({'stage': 'original-observer-closed-fresh-readonly',
                                 'value': native.observe(transaction / 'receipt.record', fresh)})
        finally:
            native.close(fresh)
        return {'kind': 'frozen-worker', 'phase': phase, 'completion': completion,
                'prepare': prepared, 'worker': result, 'phaseContext': phase_context,
                'latestContext': context, 'observations': observations, 'inspections': inspections}
    finally:
        process.stop()
        process.timer.cancel()
        if observer is not None:
            native.close(observer)


def actor_cell(native, root, write_through, boundary):
    folder = root / f'actor-{write_through}-{boundary}'
    folder.mkdir()
    path = folder / 'authored.marker'
    writer = native.open(path, writer=True, write_through=write_through)
    observer = None
    try:
        created = native.info(writer)
        time.sleep(0.02)  # Declared separation of create/write, not a performance sample.
        native.write_marker(writer)
        observer = native.open(path)
        observations = [{'stage': 'after-write-before-explicit-flush', 'value': native.observe(path, observer)}]
        if boundary in ['flush', 'close']:
            native.flush(writer)
            observations.append({'stage': 'after-explicit-flush', 'value': native.observe(path, observer)})
        if boundary == 'close':
            native.close(writer)
            writer = None
            observations.append({'stage': 'after-writer-close-observer-retained', 'value': native.observe(path, observer)})
        phase_binding = copy.deepcopy(observations[-1]['value'])
        if writer is not None:
            native.close(writer)
            writer = None
        observations.append({'stage': 'all-writer-handles-closed', 'value': native.observe(path, observer)})
        native.close(observer)
        observer = None
        fresh = native.open(path)
        try:
            post_close_binding = native.observe(path, fresh)
            time.sleep(0.02)
            repeated = native.observe(path, fresh)
        finally:
            native.close(fresh)
        return {'kind': 'authored-actor', 'writeThrough': write_through, 'bindingBoundary': boundary,
                'created': created, 'observations': observations, 'phaseBinding': phase_binding,
                'freshPostCloseBinding': post_close_binding, 'repeatedPostCloseObservation': repeated,
                'namespace': [item.name for item in folder.iterdir()]}
    finally:
        if observer is not None:
            native.close(observer)
        if writer is not None:
            native.close(writer)


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
    bindings = {'workerSha256': WORKER, 'sourceRevision': 'b819f54533c495b332c3d4dbb0caccef49923036',
                'host': {'system': platform.system(), 'version': platform.version(), 'machine': platform.machine()},
                'pythonSha256': sha(sys.executable), 'pythonVersion': platform.python_version(),
                'whoami': subprocess.check_output(['whoami', '/user'], text=True),
                'tooling': {p.relative_to(HERE.parents[1]).as_posix(): sha(p) for p in [HERE / 'native.py', HERE / 'qualify.py', HERE / 'audit.py',
                                                    HERE.parent / '0034-source-oplocks/qualify.py']},
                'observer': {'access': 0x80020000, 'sharing': 7, 'creation': 3, 'flags': 0x00200000,
                             'lifetime': 'retained across writer exit/close; then replaced with fresh readonly observer'},
                'schedule': {'workerPhases': PHASES, 'completion': ['continue', 'terminate'],
                             'actorWriteThrough': [False, True], 'actorBindingBoundaries': ['write', 'flush', 'close']}}
    save(args.root / 'bindings.private.json', bindings)
    native = Native()
    cells = []
    for phase in PHASES:
        for completion in ['continue', 'terminate']:
            cells.append(worker_cell(native, args.binary, args.root, phase, completion))
    for write_through in [False, True]:
        for boundary in ['write', 'flush', 'close']:
            cells.append(actor_cell(native, args.root, write_through, boundary))
    save(args.root / 'cells.private.json', cells)
    save(args.root / 'complete.private.json', {'cells': len(cells), 'workerUnchanged': sha(args.binary) == WORKER})
    print('Retained twelve native marker timestamp lifecycle cells; no profile admitted')


if __name__ == '__main__':
    main()
