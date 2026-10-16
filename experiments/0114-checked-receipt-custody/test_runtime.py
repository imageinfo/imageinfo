"""Authored protocol controls; no native storage or durability evidence."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

import runtime


def sequence():
    prior = {'stage': 'after-publication', 'records': ['authored-prior']}
    context = {'purpose': 'imageinfo-od11-receipt-context-v1', 'prior': prior,
               'receipt': {'info': {'identity': '1:2'}, 'sha256': 'a'*64}}
    return [
        {'callerContext': prior, 'observationOnly': True},
        {'barrier': 'receipt-written'},
        {'checkedReceiptBoundary': 'receipt-file-flushed',
         'receiptFileFlushSucceeded': True, 'originalPropertiesMatch': True},
        {'receiptContext': context, 'observationOnly': True},
        {'barrier': 'receipt-file-flushed'},
        {'checkedReceiptBoundary': 'receipt-parent-flushed',
         'receiptFileFlushSucceeded': True, 'originalPropertiesMatch': True},
        {'receiptContext': deepcopy(context), 'observationOnly': True},
        {'barrier': 'receipt-parent-flushed'}, {'barrier': 'final-checked'},
        {'outcome': 'observed-receipt-recovery-required', 'receiptFileFlushSucceeded': True,
         'receiptParentFlushSucceeded': True, 'finalCheckPassed': True},
    ]


class CheckedControls(unittest.TestCase):
    def validate(self, events):
        validator = runtime._CheckedSequence()
        for event in events:
            validator.accept(event)
        return validator

    def test_exact_sequence_and_copy(self):
        events = sequence()
        validator = self.validate(events)
        self.assertTrue(validator.complete())
        events[3]['receiptContext']['receipt']['sha256'] = 'b'*64
        self.assertEqual(validator.context['receipt']['sha256'], 'a'*64)

    def test_early_missing_false_reordered_duplicate_changed_and_terminal_only(self):
        cases = []
        events = sequence(); events.insert(1, deepcopy(events[3])); cases.append(events)
        for index in (1, 2, 3, 4, 5, 6, 7, 8):
            events = sequence(); del events[index]; cases.append(events)
        for field in ('receiptFileFlushSucceeded', 'originalPropertiesMatch'):
            events = sequence(); events[2][field] = False; cases.append(events)
        events = sequence(); events[2], events[3] = events[3], events[2]; cases.append(events)
        events = sequence(); events.insert(4, deepcopy(events[3])); cases.append(events)
        events = sequence(); events[6]['receiptContext']['receipt']['info']['identity'] = '1:3'; cases.append(events)
        events = sequence(); events[3]['receiptContext']['prior'] = {}; cases.append(events)
        for field in ('receiptFileFlushSucceeded', 'receiptParentFlushSucceeded', 'finalCheckPassed'):
            events = sequence(); events[-1][field] = False; cases.append(events)
        cases.append([sequence()[-1]])
        for events in cases:
            with self.subTest(events=events):
                with self.assertRaises(runtime.Refused):
                    self.validate(events)

    def owner(self, events, observe=None):
        owner = object.__new__(runtime.CheckedReceiptCustody)
        owner._sequence = runtime._CheckedSequence()
        owner._original_events = []
        owner._checked_complete = False
        owner._inspection_count = 0
        owner._state = runtime.State.CAPTURED
        owner._lock = threading.Lock()
        owner._observe = observe
        owner._control = None
        owner._uncertain = False
        owner._stop_context = None
        owner._release_attempted = owner._release_possible = owner._release_sent = False
        # Real owned synthetic process, with the same bounded transport. No native
        # marker files or F869/E378 claims are supplied by this control harness.
        code = ('import sys,json\n'
                'sys.stdin.readline()\n'
                f'events=json.loads({json.dumps(json.dumps(events))})\n'
                'for event in events:\n'
                ' print(json.dumps(event),flush=True)\n'
                ' if "barrier" in event: sys.stdin.readline()\n')
        owner._original = runtime.base._Child([sys.executable, '-u', '-c', code])
        owner._save = lambda *args: None
        owner._notice = lambda *args: None
        owner.status = lambda: {'ready': owner._checked_complete and
                                owner._state == runtime.State.RECEIPT_OBSERVED and not owner._uncertain}
        return owner

    def test_owned_exit_and_hook_copy_and_invalid_sequence(self):
        def mutate(phase, event):
            if 'receiptContext' in event:
                event['receiptContext']['receipt']['sha256'] = 'b'*64
        owner = self.owner(sequence(), mutate)
        try:
            self.assertTrue(owner.release()['runtime']['ready'])
            self.assertIsNotNone(owner._original.process.poll())
            self.assertEqual(owner._sequence.context['receipt']['sha256'], 'a'*64)
            self.assertEqual(owner._original_events[3]['receiptContext']['receipt']['sha256'], 'a'*64)
            owner.close()
            with self.assertRaises(runtime.Refused):
                owner.inspect_receipt()
        finally:
            owner._original.stop()
        owner = self.owner([sequence()[-1]])
        with self.assertRaises(runtime.Refused):
            owner.release()
        self.assertIsNotNone(owner._original.process.poll())
        self.assertFalse(owner.status()['ready'])

    def test_inspection_requires_readiness_and_no_import(self):
        owner = self.owner(sequence())
        try:
            with self.assertRaises(runtime.Refused):
                owner.inspect_receipt()
            with self.assertRaises(TypeError):
                owner.inspect_receipt(context={})
        finally:
            owner._original.stop()

    def test_reentrant_hook_cannot_close_or_inspect_active_release(self):
        refused = []
        owner = self.owner(sequence())
        def observe(phase, event):
            for action in (owner.close, owner.inspect_receipt):
                try:
                    action()
                except runtime.Refused:
                    refused.append(True)
                else:
                    self.fail('reentrant caller action accepted')
        owner._observe = observe
        try:
            self.assertTrue(owner.release()['runtime']['ready'])
            self.assertEqual(len(refused), 2*len(sequence()))
        finally:
            owner._original.stop()

    def test_hashes_and_budget_refuse_before_root_effects(self):
        parent = Path(__file__).resolve().parents[2]/'.local/0114-control-tests'
        parent.mkdir(parents=True, exist_ok=True)
        folder = Path(tempfile.mkdtemp(dir=parent))
        for actor, inspector in ((sys.executable, sys.executable),):
            with self.assertRaises(runtime.Refused):
                runtime.CheckedReceiptCustody(folder/'wrong-binaries', actor, inspector)
        self.assertFalse((folder/'wrong-binaries').exists())
        # Independently test each hash gate without claiming these synthetic files
        # are reviewed executables, then test admission after both gates pass.
        for failed in ('actor', 'inspector'):
            calls = []
            def gate(path, expected):
                calls.append(expected)
                if expected == (runtime.ACTOR_SHA256 if failed == 'actor' else runtime.INSPECTOR_SHA256):
                    raise runtime.Refused('authored mismatch')
            root = folder/failed
            with patch.object(runtime.CheckedReceiptCustody, '_hash_check', side_effect=gate):
                with self.assertRaises(runtime.Refused):
                    runtime.CheckedReceiptCustody(root, sys.executable, sys.executable)
            self.assertFalse(root.exists())
        with patch.object(runtime.CheckedReceiptCustody, '_check_binary'):
            with self.assertRaises(runtime.Refused):
                runtime.CheckedReceiptCustody(folder/'budget', sys.executable, sys.executable,
                                             byte_limit=runtime.base.OPERATION_BYTES-1)
        self.assertFalse((folder/'budget').exists())


if __name__ == '__main__':
    unittest.main()
