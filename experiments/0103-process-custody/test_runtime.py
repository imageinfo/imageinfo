"""Portable synthetic transport/control checks; no F869/native publication evidence."""
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

import runtime


class RuntimeControls(unittest.TestCase):
    def scratch(self):
        parent = Path(__file__).resolve().parents[2]/'.local/0103-control-tests'
        parent.mkdir(parents=True, exist_ok=True)
        return Path(tempfile.mkdtemp(dir=parent))

    def owner_for_transport(self, code):
        # Only a private control-flow harness: no context import/authority and no
        # native worker/profile claim. The actual process object is still real.
        owner = object.__new__(runtime.ProcessCustody)
        owner._state = runtime.State.NEW
        owner._lock = threading.Lock()
        owner._stop_context = None
        owner._uncertain = False
        owner._original = runtime._Child([sys.executable, '-u', '-c', code])
        return owner

    def test_owned_transport_faults_stop_child_and_retain_witness(self):
        programs = {
            'eof': 'pass',
            'malformed': "print('not JSON',flush=True);import time;time.sleep(30)",
            'incomplete': "import sys;sys.stdout.write('{}');sys.stdout.flush()",
            'oversized': f"print('x'*{runtime.BLOCK+1},flush=True);import time;time.sleep(30)",
            'false_admission': "print('{\"committed\":true}',flush=True);import time;time.sleep(30)",
            'timeout': 'import time;time.sleep(30)',
        }
        for name, program in programs.items():
            with self.subTest(name=name):
                folder = self.scratch()
                witness = folder/'unresolved.marker'
                witness.write_bytes(b'retain-authored-witness')
                owner = self.owner_for_transport(program)
                # Deadline injection applies only to this synthetic transport.
                with self.assertRaises((runtime.Refused, json.JSONDecodeError)):
                    with owner._action(runtime.State.NEW):
                        # Restore the normal cleanup wait before _action handles
                        # this injected response deadline on a busy CI host.
                        with patch.object(runtime, 'TIMEOUT', 0.2 if name == 'timeout' else 5):
                            owner._original.next()
                self.assertIsNotNone(owner._original.process.poll())
                self.assertEqual(owner.state, runtime.State.UNCERTAIN)
                self.assertIsNone(owner._stop_context)
                self.assertEqual(witness.read_bytes(), b'retain-authored-witness')
                self.assertEqual([p.name for p in folder.iterdir()], ['unresolved.marker'])

    def test_caller_exception_and_interrupt_stop_owned_child(self):
        for error in (RuntimeError('authored caller failure'), KeyboardInterrupt()):
            with self.subTest(error=type(error).__name__):
                owner = self.owner_for_transport('import time;time.sleep(30)')
                with self.assertRaises(type(error)):
                    with owner._action(runtime.State.NEW):
                        raise error
                self.assertIsNotNone(owner._original.process.poll())
                self.assertEqual(owner.state, runtime.State.UNCERTAIN)

    def test_event_count_is_finite(self):
        child = runtime._Child([sys.executable, '-u', '-c',
                                f"for i in range({runtime.MAX_EVENTS+1}):print('{{}}',flush=True)"])
        try:
            for _ in range(runtime.MAX_EVENTS):
                self.assertEqual(child.next(), {})
            with self.assertRaises(runtime.Refused):
                child.next()
        finally:
            child.stop()

    def test_protocol_request_and_controls_are_bounded(self):
        self.assertEqual(len(runtime.wire('x'*(runtime.BLOCK-3))), runtime.BLOCK)
        with self.assertRaises(runtime.Refused):
            runtime.wire('x'*(runtime.BLOCK-2))
        child = runtime._Child([sys.executable, '-u', '-c',
                                "import sys,json;print(json.dumps({'barrier':'synthetic'}),flush=True);"
                                "print(json.dumps({'outcome':sys.stdin.readline().strip()}),flush=True)"])
        try:
            self.assertEqual(child.next()['barrier'], 'synthetic')
            with self.assertRaises(runtime.Refused):
                child.send('arbitrary-command')
            child.send('continue')
            self.assertEqual(child.next()['outcome'], 'continue')
            self.assertEqual(child.finish(), 0)
        finally:
            child.stop()

    def test_unreviewed_binary_refuses_before_root_creation(self):
        folder = self.scratch()
        root = folder/'not-created'
        with self.assertRaises(runtime.Refused):
            runtime.ProcessCustody(root, sys.executable)
        self.assertFalse(root.exists())

    def test_reader_start_failure_stops_actual_new_child(self):
        spawned = []
        real_popen = runtime.subprocess.Popen

        def create(*args, **kwargs):
            child = real_popen(*args, **kwargs)
            spawned.append(child)
            return child

        with patch.object(runtime.subprocess, 'Popen', side_effect=create):
            with patch.object(runtime.threading.Thread, 'start', side_effect=RuntimeError('authored reader failure')):
                with self.assertRaises(RuntimeError):
                    runtime._Child([sys.executable, '-u', '-c', 'import time;time.sleep(30)'])
        self.assertEqual(len(spawned), 1)
        self.assertIsNotNone(spawned[0].poll())
        self.assertTrue(spawned[0].stdin.closed)
        self.assertTrue(spawned[0].stdout.closed)


if __name__ == '__main__':
    unittest.main()
