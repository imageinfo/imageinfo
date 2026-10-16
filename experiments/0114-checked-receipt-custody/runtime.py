"""Live checked-receipt custody; authored-marker research, no restart adoption."""
from copy import deepcopy
import hashlib
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('process_custody103', HERE.parent/'0103-process-custody/runtime.py')
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)
Refused, State = base.Refused, base.State
ACTOR_SHA256 = 'e378d436ed478cc4fe31ec84ff0ab91f27a459d8c6b636fcb55d0c700c11f941'
INSPECTOR_SHA256 = base.REVIEWED_WORKER_SHA256
MODE = 'ordinary-receipt-checked-flush'


class _CheckedSequence:
    """Bound the live export order; native inspection validates context contents."""
    def __init__(self):
        self.step = 0
        self.context = None
        self.exports = 0
        self.prior = None

    def accept(self, event):
        relevant = [name for name in ('checkedReceiptBoundary', 'receiptContext', 'barrier', 'outcome')
                    if name in event]
        if 'callerContext' in event:
            if self.step:
                raise Refused('caller context after receipt sequence began')
            self.prior = deepcopy(event['callerContext'])
        if self.step == 0:
            if 'receiptContext' in event or 'checkedReceiptBoundary' in event:
                raise Refused('receipt context or check before receipt-written')
            if event.get('barrier') == 'receipt-written':
                self.step = 1
            elif event.get('barrier') in ('receipt-file-flushed', 'receipt-parent-flushed', 'final-checked'):
                raise Refused('receipt sequence began out of order')
            elif event.get('outcome') == 'observed-receipt-recovery-required':
                raise Refused('receipt success without checked sequence')
            return
        expected = {
            1: ('checkedReceiptBoundary', 'receipt-file-flushed'),
            2: ('receiptContext', None),
            3: ('barrier', 'receipt-file-flushed'),
            4: ('checkedReceiptBoundary', 'receipt-parent-flushed'),
            5: ('receiptContext', None),
            6: ('barrier', 'receipt-parent-flushed'),
            7: ('barrier', 'final-checked'),
            8: ('outcome', 'observed-receipt-recovery-required'),
        }.get(self.step)
        if expected is None:
            raise Refused('event after completed receipt sequence')
        key, value = expected
        if relevant != [key] or (value is not None and event[key] != value):
            raise Refused('missing, duplicate or reordered checked receipt event')
        if key == 'checkedReceiptBoundary':
            if (event.get('receiptFileFlushSucceeded') is not True
                    or event.get('originalPropertiesMatch') is not True):
                raise Refused('checked receipt boundary lacks successful original checks')
        elif key == 'receiptContext':
            context = event[key]
            base.wire(context)
            if (event.get('observationOnly') is not True or type(context) is not dict
                    or context.get('purpose') != 'imageinfo-od11-receipt-context-v1'
                    or self.prior is None or context.get('prior') != self.prior
                    or type(context.get('receipt')) is not dict):
                raise Refused('receipt export does not bind the actual prior context')
            if self.context is not None and context != self.context:
                raise Refused('checked receipt binding changed between exports')
            self.context = deepcopy(context)
            self.exports += 1
        elif key == 'outcome':
            for flag in ('receiptFileFlushSucceeded', 'receiptParentFlushSucceeded', 'finalCheckPassed'):
                if event.get(flag) is not True:
                    raise Refused('terminal receipt observation lacks completed checks')
        self.step += 1

    def complete(self):
        return self.step == 9 and self.exports == 2 and self.context is not None


class CheckedReceiptCustody(base.ProcessCustody):
    """One owned checked actor and fixed helper; trusted in-process callers only.

    Four existing caller-history snapshots remain unchanged. Receipt provenance
    and events stay in bounded process memory and cannot be imported or adopted.
    """
    def __init__(self, root, actor, inspector, byte_limit=base.OPERATION_BYTES,
                 observe=None, control=None):
        self._actor = Path(actor).resolve(strict=True)
        self._sequence = _CheckedSequence()
        self._original_events = []
        self._checked_complete = False
        self._inspection_count = 0
        super().__init__(root, inspector, byte_limit, observe, control)

    @staticmethod
    def _hash_check(path, expected):
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise Refused('binary is outside the reviewed checked custody profile')

    def _check_binary(self):
        self._hash_check(self._actor, ACTOR_SHA256)
        self._hash_check(self._binary, INSPECTOR_SHA256)

    def _spawn(self, root, mode):
        if mode == 'ordinary-receipt':
            binary, selected, expected = self._actor, MODE, ACTOR_SHA256
        else:
            binary, selected, expected = self._binary, mode, INSPECTOR_SHA256
        self._hash_check(binary, expected)
        return base._Child([str(binary), str(root), selected])

    def _event(self, phase, event):
        if phase == 'original':
            if len(self._original_events) >= base.MAX_EVENTS:
                raise Refused('original event history exceeded')
            self._original_events.append(deepcopy(event))
            try:
                self._sequence.accept(event)
            except Refused:
                # Retain/report the actual rejected native event as evidence;
                # never offer its barrier to the control hook or continue it.
                if self._observe:
                    self._observe(phase, deepcopy(event))
                raise
        return super()._event(phase, event)

    def status(self):
        return {**super().status(), 'actorSha256': ACTOR_SHA256,
                'inspectorSha256': INSPECTOR_SHA256, 'receiptMode': MODE,
                'originalEventCount': len(self._original_events),
                'checkedReceiptExports': self._sequence.exports,
                'checkedReceiptContextEligible': (self._checked_complete
                    and self._state == State.RECEIPT_OBSERVED and not self._uncertain),
                'inspectionCount': self._inspection_count}

    def release(self):
        # Keep readiness and exit confirmation inside the same serialized action.
        # Calling super().release() then setting readiness would race with close.
        with self._action(State.CAPTURED):
            self._release_attempted = True
            self._state = State.RELEASE_ATTEMPTED
            self._save('fence-save', 'publication-release-fenced')
            self._release_possible = True
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
                    if self._original.finish() != 0 or not self._sequence.complete():
                        raise Refused('owned checked receipt child did not complete')
                    self._state = State.RECEIPT_OBSERVED
                    self._checked_complete = True
                    self._notice('checked-receipt-owned-child-exit-confirmed')
                    return {**event, 'runtime': self.status()}
                if barrier:
                    self._original.send(command)

    def inspect_receipt(self):
        with self._action(State.RECEIPT_OBSERVED):
            if not self._checked_complete or self._uncertain or not self._sequence.complete():
                raise Refused('completed owned checked receipt sequence required')
            self._inspection_count += 1
            self._notice('receipt-inspection-started')
            terminal = self._call(self.transaction, 'ordinary-receipt-inspect',
                                  'receipt-inspect', deepcopy(self._sequence.context))
            return {**terminal, 'runtime': self.status()}

    def close(self):
        result = super().close()
        self._checked_complete = False
        self._sequence.context = None
        return {**result, 'checkedReceiptContextEligible': False}
