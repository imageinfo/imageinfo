"""Actual authored direct-child controls; captures remain under ignored .local.

No media, native decoder, OS resource quota or descendant containment is tested.
Timeout/cancellation assert the child handshake, rather than assuming a sleep
means that the child reached the intended state. Failed attempts are retained.
"""
import hashlib
import json
from pathlib import Path
import sys
import threading
import unittest
from unittest import mock
import uuid

import authored_process_child as child_helper
import run as runner
from authored_process_child import ERR, OUT, PARTIAL
from run import Limits, run_process


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


class ProcessControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = REPO / ".local" / "0075-process-controls" / uuid.uuid4().hex
        cls.root.mkdir(parents=True, exist_ok=False)

    def launch(self, mode, *, cancel=None, deadline=10, capture=4096):
        attempt = self.root / self._testMethodName
        handshake = self.root / (self._testMethodName + ".handshake.json")
        command = [sys.executable, "-I", str(HERE / "authored_process_child.py"),
                   mode, str(handshake)]
        if cancel == "handshake":
            cancel = handshake.exists
        elif cancel in {"callback-failure", "callback-interruption"}:
            failure = cancel

            def cancel():
                if handshake.exists():
                    if failure == "callback-interruption":
                        raise KeyboardInterrupt("authored interruption")
                    raise RuntimeError("authored supervisor callback failure")
                return False
        result = run_process(command, attempt,
                             Limits(deadline_seconds=deadline,
                                    capture_bytes_per_stream=capture),
                             cancel=cancel,
                             binding={"phase": "authored-process-controls-v1",
                                      "mode": mode, "descendantsCreated": False})
        self.assertEqual(result, json.loads((attempt / "process.json").read_text("utf-8")))
        self.assertTrue(result["terminationConfirmed"])
        self.assertIsNotNone(result["returncode"])
        self.assertEqual(result["requestSha256"],
                         hashlib.sha256((attempt / "request.json").read_bytes()).hexdigest())
        self.assertTrue(handshake.is_file(), "child did not reach its declared handshake")
        marker = json.loads(handshake.read_text("utf-8"))
        self.assertEqual(marker["mode"], mode)
        self.assertTrue(marker["prefixesFlushed"])
        for name, row in result["streams"].items():
            stored = (attempt / (name + ".bin")).read_bytes()
            self.assertEqual(row["capturedBytes"], len(stored))
            self.assertLessEqual(len(stored), capture)
            self.assertGreaterEqual(row["observedBytes"], len(stored))
            self.assertEqual(row["sha256"], hashlib.sha256(stored).hexdigest())
            self.assertIsNone(row["error"])
        return result, attempt

    def exact_prefixes(self, result, attempt, stdout=OUT):
        self.assertEqual((attempt / "stdout.bin").read_bytes(), stdout)
        self.assertEqual((attempt / "stderr.bin").read_bytes(), ERR)
        for row in result["streams"].values():
            self.assertTrue(row["eof"])
            self.assertFalse(row["overflow"])

    def test_normal_exit(self):
        result, attempt = self.launch("normal")
        self.assertEqual(result["outcome"], "exited")
        self.assertEqual(result["returncode"], 0)
        self.exact_prefixes(result, attempt)

    def test_nonzero_exit_retained(self):
        result, attempt = self.launch("nonzero")
        self.assertEqual(result["outcome"], "exited")
        self.assertEqual(result["returncode"], 23)
        self.exact_prefixes(result, attempt)

    def test_partial_capture_nonzero_retained(self):
        result, attempt = self.launch("partial")
        self.assertEqual(result["outcome"], "exited")
        self.assertEqual(result["returncode"], 24)
        self.exact_prefixes(result, attempt, PARTIAL)
        with self.assertRaises(json.JSONDecodeError):
            json.loads((attempt / "stdout.bin").read_bytes())

    def test_deadline_kills_and_drains_waiting_child(self):
        result, attempt = self.launch("wait")
        self.assertEqual(result["outcome"], "deadline")
        self.assertGreaterEqual(result["elapsedSeconds"], 10)
        self.assertNotEqual(result["returncode"], 0)
        self.exact_prefixes(result, attempt)

    def test_cancel_after_child_handshake(self):
        result, attempt = self.launch("wait", cancel="handshake")
        self.assertEqual(result["outcome"], "cancelled")
        self.assertNotEqual(result["returncode"], 0)
        self.exact_prefixes(result, attempt)

    def test_callback_failure_reaps_child(self):
        result, attempt = self.launch("wait", cancel="callback-failure")
        self.assertEqual(result["outcome"], "supervisor-failed")
        self.assertIn("authored supervisor callback failure", result["error"])
        self.exact_prefixes(result, attempt)

    def test_interruption_reaps_child(self):
        result, attempt = self.launch("wait", cancel="callback-interruption")
        self.assertEqual(result["outcome"], "interrupted")
        self.assertIn("authored interruption", result["error"])
        self.exact_prefixes(result, attempt)

    def overflow(self, mode, stream, prefix):
        result, attempt = self.launch(mode, capture=1024)
        self.assertEqual(result["outcome"], "capture-failed")
        row = result["streams"][stream]
        self.assertTrue(row["overflow"])
        self.assertEqual(row["capturedBytes"], 1024)
        self.assertGreater(row["observedBytes"], 1024)
        self.assertEqual((attempt / (stream + ".bin")).read_bytes(),
                         prefix + b"X" * (1024 - len(prefix)))

    def test_stdout_overflow(self):
        self.overflow("overflow", "stdout", OUT)

    def test_stderr_overflow(self):
        self.overflow("stderr-overflow", "stderr", ERR)

    def test_launch_failure_retained(self):
        attempt = self.root / self._testMethodName
        result = run_process([str(self.root / "nonexistent-authored-child.exe")],
                             attempt, Limits(), binding={"phase": "authored"})
        self.assertEqual(result["outcome"], "launch-failed")
        self.assertIsNone(result["returncode"])
        self.assertTrue(result["terminationConfirmed"])
        self.assertIsNotNone(result["error"])
        self.assertEqual(result, json.loads((attempt / "process.json").read_text("utf-8")))
        for name, row in result["streams"].items():
            self.assertEqual((attempt / (name + ".bin")).read_bytes(), b"")
            self.assertEqual(row["capturedBytes"], 0)

    def test_cancel_before_launch_retained(self):
        event = threading.Event()
        event.set()
        attempt = self.root / self._testMethodName
        result = run_process([str(self.root / "must-not-launch.exe")], attempt,
                             Limits(), cancel=event)
        self.assertEqual(result["outcome"], "cancelled-before-launch")
        self.assertIsNone(result["returncode"])
        self.assertTrue(result["terminationConfirmed"])
        self.assertIsNone(result["error"])
        self.assertEqual(result, json.loads((attempt / "process.json").read_text("utf-8")))

    def test_existing_attempt_refuses_before_launch(self):
        attempt = self.root / self._testMethodName
        attempt.mkdir()
        sentinel = attempt / "retain.txt"
        sentinel.write_bytes(b"retained original")
        with self.assertRaises(FileExistsError):
            run_process([str(self.root / "must-not-launch.exe")], attempt, Limits())
        self.assertEqual(list(attempt.iterdir()), [sentinel])
        self.assertEqual(sentinel.read_bytes(), b"retained original")

    def test_handshake_hidden_until_complete_closed_json(self):
        handshake = self.root / (self._testMethodName + ".json")
        original_dump = json.dump
        original_rename = Path.rename
        seen = []

        def writing(value, stream):
            self.assertFalse(handshake.exists())
            stream.write(" ")
            stream.flush()
            self.assertFalse(handshake.exists(), "partial JSON must remain private")
            seen.append(stream)
            return original_dump(value, stream)

        def publishing(staged, target):
            self.assertTrue(seen[0].closed)
            self.assertFalse(handshake.exists())
            self.assertEqual(json.loads(staged.read_text("utf-8"))["mode"], "authored")
            return original_rename(staged, target)

        with mock.patch.object(child_helper.json, "dump", side_effect=writing), \
                mock.patch.object(Path, "rename", autospec=True, side_effect=publishing):
            child_helper.publish_handshake(handshake, "authored")
        self.assertTrue(json.loads(handshake.read_text("utf-8"))["prefixesFlushed"])
        self.assertFalse(handshake.with_name(handshake.name + ".staged").exists())

    def test_postlaunch_process_record_failure_is_invalid_experiment(self):
        attempt = self.root / self._testMethodName
        handshake = self.root / (self._testMethodName + ".handshake.json")
        original_write = runner.write_json
        original_run = runner.run_process
        command = [sys.executable, "-I", str(HERE / "authored_process_child.py"),
                   "normal", str(handshake)]

        def fail_final_record(path, value):
            if path.name == "process.json":
                raise OSError("authored final process record failure")
            return original_write(path, value)

        def authored_child_only(_command, root, limits, **kwargs):
            return original_run(command, root, limits, **kwargs)

        # Admission/worker substitution is only a fault-injection seam. The
        # actual launched child is the authored helper, never a native decoder.
        with mock.patch.object(runner, "admit_request", return_value={}), \
                mock.patch.object(runner, "run_process", side_effect=authored_child_only), \
                mock.patch.object(runner, "write_json", side_effect=fail_final_record):
            result = runner.run_cell({"stage": "authored", "interpreter": sys.executable},
                                     attempt)
        self.assertTrue(handshake.is_file())
        self.assertEqual(result["outcome"], "invalid-experiment")
        self.assertTrue(result["processInvocationAttempted"])
        self.assertIn("authored final process record failure", result["error"])
        self.assertEqual((attempt / "process/stdout.bin").read_bytes(), OUT)
        self.assertEqual((attempt / "process/stderr.bin").read_bytes(), ERR)
        self.assertFalse((attempt / "process/process.json").exists())
        evidence = {row["path"]: row["byteLength"]
                    for row in result["availableProcessEvidence"]}
        self.assertEqual(evidence["process/stdout.bin"], len(OUT))
        self.assertEqual(evidence["process/stderr.bin"], len(ERR))
        self.assertIn("process-invocation.json", evidence)
        self.assertEqual(result, json.loads((attempt / "cell-result.json").read_text("utf-8")))


if __name__ == "__main__":
    unittest.main()
