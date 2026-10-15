"""Finite, live-process marker admission; no restart authority or disk reservation."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

U64_MAX = (1 << 64) - 1
BLOCK = 65536
# Source, candidate, four transaction records, four immutable custody snapshots.
OPERATION_BYTES = 10 * BLOCK
MAX_EVENTS = 128
REVIEWED_WORKER_SHA256 = 'f86918a7fb3880cf8e09590fcc7d58155ef64d98c95cf9c2a6afc541c5b040fa'
MODES = {'ordinary-receipt', 'ordinary-receipt-short-record', 'ordinary-short-source'}


class Refused(ValueError):
    pass


def u64(value):
    if type(value) is not int or not 0 <= value <= U64_MAX:
        raise Refused('u64 required')
    return value


def add(left, right):
    result = u64(left) + u64(right)
    return u64(result)


def wire(value):
    result = json.dumps(value, separators=(',', ':')).encode() + b'\n'
    if len(result) > BLOCK:
        raise Refused('request exceeds worker record bound')
    return result


class Budget:
    """Monotonic charges: neither success nor failure refunds retained work."""
    def __init__(self, byte_limit, operation_limit):
        self.byte_limit = u64(byte_limit)
        self.operation_limit = u64(operation_limit)
        self.charged = 0
        self.operations = 0

    def admit(self):
        charged = add(self.charged, OPERATION_BYTES)
        operations = add(self.operations, 1)
        if charged > self.byte_limit or operations > self.operation_limit:
            raise Refused('cumulative admission exhausted')
        self.charged, self.operations = charged, operations
        return operations


class Supervisor:
    """One trusted caller, fresh namespace, synchronous operations, no ledger reload.

    The full operation is charged before prepare. Each construction is then
    authorized only within that paid finite plan and the unchanged worker's
    checked per-file bounds. No charge release API exists.
    """
    def __init__(self, root, binary, byte_limit, operation_limit):
        self.budget = Budget(byte_limit, operation_limit)
        self.binary = Path(binary).resolve(strict=True)
        self.binary_hash = hashlib.sha256(self.binary.read_bytes()).hexdigest()
        if self.binary_hash != REVIEWED_WORKER_SHA256:
            raise Refused('worker is outside the reviewed finite construction profile')
        self.root = Path(root).resolve()
        # Never adopt an old, empty, foreign, or incomplete supervisor directory.
        self.root.mkdir(exist_ok=False)
        self.poisoned = False
        self.active = False
        self.inventory = {}

    def _inventory(self):
        result = {}

        def visit(folder, depth):
            if depth > 3:
                raise Refused('unexpected directory depth')
            with os.scandir(folder) as entries:
                for entry in entries:
                    if len(result) >= self.budget.operations * 13:
                        raise Refused('unexpected entry count')
                    info = entry.stat(follow_symlinks=False)
                    if entry.is_symlink() or getattr(info, 'st_file_attributes', 0) & 0x400:
                        raise Refused('reparse entry refused')
                    relative = str(Path(entry.path).relative_to(self.root))
                    if entry.is_dir(follow_symlinks=False):
                        result[relative] = None
                        visit(entry.path, depth + 1)
                    else:
                        if info.st_size > BLOCK:
                            raise Refused('entry byte bound')
                        result[relative] = info.st_size

        visit(self.root, 0)
        return result

    def _call(self, root, mode, request=None, callback=None):
        if hashlib.sha256(self.binary.read_bytes()).hexdigest() != self.binary_hash:
            raise Refused('worker changed')
        # All worker modes are fixed by this module; no arbitrary construction.
        with subprocess.Popen([str(self.binary), str(root), mode], stdin=subprocess.PIPE,
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as process:
            try:
                if request is not None:
                    process.stdin.write(wire(request))
                    process.stdin.flush()
                terminal = None
                for _ in range(MAX_EVENTS):
                    line = process.stdout.readline(BLOCK + 1)
                    if not line:
                        break
                    if len(line) > BLOCK or not line.endswith(b'\n'):
                        raise Refused('worker event bound')
                    event = json.loads(line)
                    for flag in ('committed', 'productionPublicationAllowed', 'repairAllowed',
                                 'namespaceAcknowledged'):
                        if event.get(flag, False) is not False:
                            raise Refused('unexpected admission flag')
                    control = callback(event) if callback else 'continue'
                    if 'barrier' in event:
                        if control not in ('continue', 'cancel', 'fail'):
                            raise Refused('invalid control')
                        process.stdin.write(control.encode() + b'\n')
                        process.stdin.flush()
                    if 'outcome' in event:
                        terminal = event
                        break
                else:
                    raise Refused('worker event count bound')
                process.stdin.close()
                code = process.wait(timeout=30)
                if code != 0 or terminal is None:
                    raise Refused('worker failed or omitted result')
                return terminal
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()

    def run(self, mode='ordinary-receipt', control_at=None, control='continue'):
        if self.poisoned or self.active or mode not in MODES:
            raise Refused('supervisor state or mode refused')
        if control not in ('continue', 'cancel', 'fail'):
            raise Refused('control refused')
        try:
            if self._inventory() != self.inventory:
                raise Refused('unknown or changed retained state')
        except BaseException:
            self.poisoned = True
            raise
        number = self.budget.admit()  # Before even creating the operation directory.
        self.active = True
        folder = self.root / str(number)
        state = {'context': None, 'journal': None, 'identity': None, 'snapshots': 0}
        try:
            folder.mkdir(exist_ok=False)
            transaction = folder / 'transaction.marker'
            custody = folder / 'custody.marker'
            prepared = self._call(transaction, 'ordinary-prepare')
            if prepared['outcome'] != 'owned-source-prepared':
                raise Refused('prepare refused')

            def save(event_name, context=None):
                if state['snapshots'] == 4:
                    raise Refused('custody construction count')
                item = {'event': event_name}
                if context is not None:
                    item['context'] = context
                if state['journal'] is None:
                    state['journal'] = {'purpose': 'imageinfo-od11-custody-history-v1', 'events': []}
                state['journal']['events'].append(item)
                request = {'journal': state['journal'], 'expectedCustodyRoot': state['identity']}
                wire(request)  # Check actual serialized input before custody worker creation.
                result = self._call(custody, 'ordinary-custody-save', request)
                if result['outcome'] != 'custody-snapshot-recorded':
                    raise Refused('custody save incomplete')
                state['identity'] = result['custodyRoot']
                state['snapshots'] += 1

            def event(event):
                if 'callerContext' in event:
                    state['context'] = event['callerContext']
                barrier = event.get('barrier')
                if barrier == control_at:
                    return control
                if barrier == 'before-namespace-call':
                    save('captured', state['context'])
                    save('publication-release-fenced')
                elif barrier == 'parent-flushed':
                    save('publication-observed', state['context'])
                elif barrier == 'observation-parent-flushed':
                    save('observation-renewed', state['context'])
                return 'continue'

            terminal = self._call(transaction, mode, callback=event)
            # Observations do not refund even a fully successful operation.
            files = [path for path in folder.rglob('*') if path.is_file()]
            sizes = [path.stat().st_size for path in files]
            total = 0
            for size in sizes:
                total = add(total, size)
            if len(files) > 10 or any(size > BLOCK for size in sizes) or total > OPERATION_BYTES:
                raise Refused('observed artifact bound violated; retained')
            self.inventory = self._inventory()
            return {'outcome': terminal['outcome'], 'chargedBytes': self.budget.charged,
                    'operations': self.budget.operations, 'observedFiles': len(files),
                    'observedLogicalBytes': total, 'custodySnapshots': state['snapshots'],
                    'committed': False, 'productionPublicationAllowed': False,
                    'repairAllowed': False, 'namespaceAcknowledged': False}
        except BaseException:
            # Unknown partial work and namespace conflicts block all further work.
            self.poisoned = True
            raise
        finally:
            self.active = False
