"""Process-owned marker custody. Trusted caller API, not a Python security boundary."""
from contextlib import contextmanager
from copy import deepcopy
from enum import Enum
import hashlib
import importlib.util
import json
from pathlib import Path
import queue
import subprocess
import threading

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('marker_budget49', HERE.parent/'0049-cumulative-budget/supervisor.py')
_budget49 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_budget49)
Budget, Refused = _budget49.Budget, _budget49.Refused
BLOCK, MAX_EVENTS, OPERATION_BYTES = _budget49.BLOCK, _budget49.MAX_EVENTS, _budget49.OPERATION_BYTES
REVIEWED_WORKER_SHA256 = _budget49.REVIEWED_WORKER_SHA256
TIMEOUT = 30


class State(Enum):
    NEW = 'new'
    CAPTURED = 'captured-unreleased'
    STOP_ATTESTED = 'owned-child-stopped-and-saved'
    RELEASE_ATTEMPTED = 'release-fence-attempted'
    RECEIPT_OBSERVED = 'receipt-observed-unqualified'
    PRUNE_ATTEMPTED = 'prune-attempted'
    PRUNED = 'owned-unpublished-handles-pruned'
    UNCERTAIN = 'uncertain-retained'
    CLOSED = 'closed-retained'


def wire(value):
    result = json.dumps(value, separators=(',', ':')).encode('utf-8')+b'\n'
    if len(result) > BLOCK:
        raise Refused('bounded worker request exceeded')
    return result


def checked_event(line):
    if len(line) > BLOCK or not line.endswith(b'\n'):
        raise Refused('bounded worker line exceeded or incomplete')
    event = json.loads(line)
    if type(event) is not dict:
        raise Refused('worker event must be an object')
    for flag in ('committed', 'namespaceAcknowledged', 'repairAllowed', 'productionPublicationAllowed'):
        if event.get(flag, False) is not False:
            raise Refused('worker unexpectedly claims admission')
    return event


class _Child:
    """Own the actual process object, bounded pipe reader and its exit wait."""
    def __init__(self, argv):
        self.process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL)
        try:
            self.events = queue.Queue(maxsize=MAX_EVENTS+1)
            self.count = 0
            self.reader = threading.Thread(target=self._read, daemon=True)
            self.reader.start()
        except BaseException:
            # Popen already owns a child even if the reader cannot start. Do not
            # leave that process waiting at a barrier without a returned owner.
            if self.process.poll() is None:
                self.process.kill()
            self.process.wait(timeout=TIMEOUT)
            reader = getattr(self, 'reader', None)
            if reader is not None and reader.is_alive():
                reader.join(timeout=TIMEOUT)
            self.process.stdin.close()
            self.process.stdout.close()
            raise

    def _read(self):
        try:
            for _ in range(MAX_EVENTS):
                line = self.process.stdout.readline(BLOCK+1)
                if not line:
                    self.events.put(('eof', None))
                    return
                self.events.put(('event', checked_event(line)))
            self.events.put(('error', Refused('worker event count exceeded')))
        except BaseException as error:
            self.events.put(('error', error))

    def next(self):
        try:
            kind, item = self.events.get(timeout=TIMEOUT)
        except queue.Empty as error:
            raise Refused('worker response timeout; retained') from error
        if kind == 'error':
            raise item
        if kind == 'eof':
            raise Refused('worker exited before a required result')
        self.count += 1
        return item

    def send(self, control):
        if control not in ('continue', 'cancel', 'fail'):
            raise Refused('unsupported control')
        self.process.stdin.write(control.encode('ascii')+b'\n')
        self.process.stdin.flush()

    def request(self, value):
        self.process.stdin.write(wire(value))
        self.process.stdin.flush()

    def finish(self):
        close_error = None
        try:
            if not self.process.stdin.closed:
                self.process.stdin.close()
        except OSError as error:
            close_error = error
        code = self.process.wait(timeout=TIMEOUT)
        self.reader.join(timeout=TIMEOUT)
        if self.reader.is_alive():
            raise Refused('worker reader did not stop after process exit')
        self.process.stdout.close()
        if close_error is not None:
            raise close_error
        return code

    def stop(self):
        if self.process.poll() is None:
            self.process.kill()
        return self.finish()


class ProcessCustody:
    """One fresh operation, one live trusted caller, no context import or adoption.

    Observe/control hooks are for authored qualification and receive copies. They
    cannot replace stored context through the public API. Callers in this Python
    process remain trusted; object privacy is not an adversarial sandbox.
    """
    def __init__(self, root, binary, byte_limit=OPERATION_BYTES, observe=None, control=None):
        self._budget = Budget(byte_limit, 1)
        self._binary = Path(binary).resolve(strict=True)
        self._check_binary()
        self._budget.admit()  # Full source/candidate/record/custody plan before creation.
        self.root = Path(root).resolve()
        self.root.mkdir(exist_ok=False)
        self.transaction = self.root/'transaction.marker'
        self.custody = self.root/'custody.marker'
        self._state = State.NEW
        self._lock = threading.Lock()
        self._observe = observe
        self._control = control
        self._original = None
        self._captured = None
        self._stop_context = None
        self._journal = None
        self._custody_root = None
        self._snapshots = 0
        self._release_attempted = False
        self._release_possible = False
        self._release_sent = False
        self._prune_attempted = False
        self._uncertain = False

    @property
    def state(self):
        return self._state

    def status(self):
        return {'state': self._state.value, 'chargedBytes': self._budget.charged,
                'operationCount': self._budget.operations, 'custodySnapshots': self._snapshots,
                'originalProcessStarted': self._original is not None,
                'ownedChildExited': self._original is not None and self._original.process.poll() is not None,
                'releaseAttempted': self._release_attempted,
                'publicationReleasePossible': self._release_possible,
                'releaseContinuationSent': self._release_sent, 'pruneAttempted': self._prune_attempted,
                'uncertain': self._uncertain, 'committed': False, 'namespaceAcknowledged': False,
                'repairAllowed': False, 'productionPublicationAllowed': False,
                'automaticDurableCustody': False}

    def _check_binary(self):
        if hashlib.sha256(self._binary.read_bytes()).hexdigest() != REVIEWED_WORKER_SHA256:
            raise Refused('worker is outside the reviewed fixed marker profile')

    def _spawn(self, root, mode):
        self._check_binary()
        return _Child([str(self._binary), str(root), mode])

    def _notice(self, name):
        if self._observe:
            self._observe('runtime', {'runtimeEvent': name, **self.status()})

    def _event(self, phase, event):
        if self._observe:
            self._observe(phase, deepcopy(event))
        command = self._control(phase, deepcopy(event)) if self._control and 'barrier' in event else 'continue'
        if command not in ('continue', 'cancel', 'fail'):
            raise Refused('unsupported qualification control')
        return command

    @contextmanager
    def _action(self, expected):
        if not self._lock.acquire(blocking=False):
            raise Refused('another caller action is active')
        try:
            if self._state != expected:
                raise Refused('caller lifecycle disallows action')
            try:
                yield
            except BaseException:
                self._state = State.UNCERTAIN
                self._uncertain = True
                self._stop_context = None
                self._shutdown()
                raise
        finally:
            self._lock.release()

    def _shutdown(self):
        if self._original is not None:
            try:
                self._original.stop()
            except (OSError, subprocess.TimeoutExpired):
                self._uncertain = True

    def _call(self, root, mode, phase, request=None):
        child = self._spawn(root, mode)
        try:
            if request is not None:
                child.request(request)
            while True:
                event = child.next()
                command = self._event(phase, event)
                if 'outcome' in event:
                    if child.finish() != 0:
                        raise Refused('worker exited unsuccessfully')
                    return event
                if 'barrier' in event:
                    child.send(command)
        finally:
            child.stop()

    def _save(self, phase, event_name, context=None):
        if self._snapshots >= 4:
            raise Refused('custody snapshot construction count exceeded')
        proposed = deepcopy(self._journal) if self._journal is not None else {
            'purpose': 'imageinfo-od11-custody-history-v1', 'events': []}
        item = {'event': event_name}
        if context is not None:
            item['context'] = deepcopy(context)
        proposed['events'].append(item)
        request = {'journal': proposed, 'expectedCustodyRoot': self._custody_root}
        wire(request)  # Before starting a construction worker.
        terminal = self._call(self.custody, 'ordinary-custody-save', phase, request)
        if terminal['outcome'] != 'custody-snapshot-recorded' or terminal.get('journal') != proposed:
            raise Refused('custody save did not complete; no authority retained')
        self._journal = proposed
        self._custody_root = deepcopy(terminal['custodyRoot'])
        self._snapshots += 1
        self._notice(phase+'-complete')

    def begin(self):
        with self._action(State.NEW):
            prepared = self._call(self.transaction, 'ordinary-prepare', 'prepare')
            if prepared['outcome'] != 'owned-source-prepared':
                raise Refused('marker preparation refused')
            self._original = self._spawn(self.transaction, 'ordinary-receipt')
            while True:
                event = self._original.next()
                command = self._event('original', event)
                if 'callerContext' in event:
                    self._captured = deepcopy(event['callerContext'])
                if event.get('barrier') == 'before-namespace-call':
                    if (not self._captured or self._captured['stage'] != 'before-publication'
                            or self._captured['stoppedBeforePublication']):
                        raise Refused('actual before-publication caller context required')
                    self._save('captured-save', 'captured', self._captured)
                    self._state = State.CAPTURED
                    return self.status()  # Deliberately withhold this barrier's continuation.
                if 'outcome' in event:
                    raise Refused('worker finished before caller capture')
                if 'barrier' in event:
                    self._original.send(command)

    def stop(self):
        with self._action(State.CAPTURED):
            if self._release_attempted or self._release_possible or self._original is None:
                raise Refused('release history disallows stop attestation')
            self._original.stop()  # Wait on this owned process object, never a supplied PID.
            if self._original.process.poll() is None:
                raise Refused('owned child exit unconfirmed')
            self._notice('owned-child-exit-confirmed-before-release')
            self._save('stop-save', 'stop-confirmed-before-publication')
            self._stop_context = deepcopy(self._captured)
            self._stop_context['stoppedBeforePublication'] = True
            self._state = State.STOP_ATTESTED
            return self.status()

    def prune(self):
        with self._action(State.STOP_ATTESTED):
            self._prune_attempted = True
            self._state = State.PRUNE_ATTEMPTED  # One invocation even after partial/refused work.
            self._notice('prune-invocation-started')
            terminal = self._call(self.transaction, 'ordinary-restart-prune', 'prune', self._stop_context)
            self._stop_context = None
            if terminal['outcome'] == 'owned-unpublished-handles-pruned':
                self._state = State.PRUNED
            else:
                self._state = State.UNCERTAIN
                self._uncertain = True
            return {**terminal, 'runtime': self.status()}

    def release(self):
        with self._action(State.CAPTURED):
            self._release_attempted = True
            self._state = State.RELEASE_ATTEMPTED
            self._save('fence-save', 'publication-release-fenced')
            self._release_possible = True  # A failed pipe write can have an ambiguous effect.
            self._original.send('continue')
            self._release_sent = True
            self._notice('publication-continuation-sent')
            context = None
            while True:
                event = self._original.next()
                command = self._event('original', event)
                if 'callerContext' in event:
                    context = deepcopy(event['callerContext'])
                barrier = event.get('barrier')
                if barrier == 'parent-flushed':
                    self._save('observed-save', 'publication-observed', context)
                elif barrier == 'observation-parent-flushed':
                    self._save('renewed-save', 'observation-renewed', context)
                if 'outcome' in event:
                    if self._original.finish() != 0:
                        raise Refused('original worker failed after release')
                    if event['outcome'] == 'observed-receipt-recovery-required':
                        self._state = State.RECEIPT_OBSERVED
                    else:
                        self._state = State.UNCERTAIN
                        self._uncertain = True
                    return {**event, 'runtime': self.status()}
                if barrier:
                    self._original.send(command)

    def close(self):
        if not self._lock.acquire(blocking=False):
            raise Refused('another caller action is active')
        try:
            if self._state not in (State.PRUNED, State.RECEIPT_OBSERVED, State.NEW, State.CLOSED):
                self._uncertain = True
            self._shutdown()
            self._stop_context = None
            self._state = State.CLOSED
            return self.status()
        finally:
            self._lock.release()
