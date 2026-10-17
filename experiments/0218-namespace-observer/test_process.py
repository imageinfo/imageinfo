"""Actual owned Python-child controls, with no native storage/probe invocation."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import run


CHILD = Path(__file__).with_name("authored_child.py").resolve()


class OwnedProcessTests(unittest.TestCase):
    def setUp(self):
        retained = Path(__file__).resolve().parents[2] / ".local" / "0218-process-controls"
        retained.mkdir(parents=True, exist_ok=True)
        # Keep successful and failed fake-child attempts for independent review.
        self.case_root = Path(tempfile.mkdtemp(prefix="authored-", dir=retained))
        self.root = self.case_root
        (self.case_root / "case.json").write_text(
            json.dumps({"authored_test": self.id()}, sort_keys=True) + "\n",
            encoding="utf-8")

    def execute(self, mode, callback=lambda line: None, **kwargs):
        bounds = kwargs.pop("bounds", run.Bounds(deadline_seconds=3))
        attempt = self.root / "attempt"
        children = []
        real_popen = subprocess.Popen

        def launch(*args, **options):
            child = real_popen(*args, **options)
            children.append(child)
            return child

        with mock.patch.object(run.subprocess, "Popen", side_effect=launch):
            result = run.execute_owned(
                [sys.executable, "-u", str(CHILD), mode], attempt, bounds,
                callback, **kwargs)
        self.assertEqual(len(children), 1)
        self.assertIsNotNone(children[0].poll(), "owned child must have exited")
        self.assertTrue(result["threads_stopped"])
        self.assertTrue(all(pipe.closed for pipe in
                            (children[0].stdin, children[0].stdout, children[0].stderr)),
                        "owned child pipes must close after their threads stop")
        self.assertFalse(result["replayed"])
        self.assertEqual(result, json.loads((attempt / "result.json").read_text()))
        transcript = [json.loads(line) for line in
                      (attempt / "transcript.jsonl").read_text().splitlines()]
        self.assertEqual(transcript[0]["kind"], "start")
        self.assertEqual(transcript[-1]["kind"], "exit")
        self.assertFalse(transcript[-1]["child_alive"])
        self.assertEqual([item["seq"] for item in transcript],
                         list(range(1, len(transcript) + 1)))
        self.assertEqual((attempt / "stdout.bin").stat().st_size, result["stdout_bytes"])
        self.assertEqual((attempt / "stderr.bin").stat().st_size, result["stderr_bytes"])
        return result, attempt, transcript

    @staticmethod
    def valid_release(line):
        return {b"paused 1\n": b"release 1\n",
                b"paused 2\n": b"release 2\n"}.get(line)

    def test_explicit_exchange_and_retained_commands(self):
        sent = []
        result, attempt, transcript = self.execute(
            "exchange", self.valid_release, request=b"request 1\n",
            command_sent=sent.append)
        self.assertEqual(result["status"], "transport_complete")
        self.assertEqual(result["commands"], 3)
        self.assertEqual(sent, [b"request 1\n", b"release 1\n", b"release 2\n"])
        retained = [bytes.fromhex(item["value"]["bytes_hex"]) for item in transcript
                    if item["kind"] == "command_sent"]
        self.assertEqual(retained, sent)
        self.assertEqual((attempt / "stdout.bin").read_bytes(),
                         b"paused 1\npaused 2\ncomplete\n")

    def test_deadline_terminates_owned_child(self):
        result, attempt, _ = self.execute(
            "wait", bounds=run.Bounds(deadline_seconds=0.5))
        self.assertEqual(result["reason"], "deadline")
        self.assertTrue(result["child_killed"])
        self.assertLess(result["elapsed_seconds"], 4)
        self.assertIn(b"waiting\n", (attempt / "stdout.bin").read_bytes())

    def test_partial_stdout_eof_is_retained_failure(self):
        result, attempt, _ = self.execute("partial")
        self.assertEqual(result["reason"], "stdout_unterminated_line")
        self.assertEqual((attempt / "stdout.bin").read_bytes(), b"partial")

    def test_nonzero_exit_is_failure(self):
        result, _, _ = self.execute("nonzero")
        self.assertEqual(result["reason"], "child_nonzero")
        self.assertEqual(result["exit_code"], 7)

    def test_capture_and_line_limits(self):
        for mode, bounds, reason, size in (
            ("stdout_overflow", run.Bounds(stdout_bytes=64), "stdout_overflow", 64),
            ("stderr_overflow", run.Bounds(stderr_bytes=64), "stderr_overflow", 64),
            ("line_overflow", run.Bounds(line_bytes=64), "stdout_line_overflow", None),
        ):
            with self.subTest(mode=mode):
                # Each cell has a fresh retained attempt, never reused or replayed.
                self.root = self.case_root / mode
                self.root.mkdir()
                result, attempt, _ = self.execute(mode, bounds=bounds)
                self.assertEqual(result["reason"], reason)
                if size is not None:
                    capture = "stderr.bin" if mode.startswith("stderr") else "stdout.bin"
                    self.assertEqual((attempt / capture).stat().st_size, size)

    def test_event_limit(self):
        result, _, _ = self.execute("event_overflow", bounds=run.Bounds(events=2))
        self.assertEqual(result["reason"], "event_bound")

    def test_lost_input_does_not_hang(self):
        result, _, _ = self.execute("lost_input", lambda line: b"release 1\n")
        self.assertTrue(result["reason"].startswith("stdin_"), result["reason"])
        self.assertTrue(result["child_killed"])

    def test_stale_ack_refused_by_actual_child(self):
        result, attempt, _ = self.execute(
            "exchange", lambda line: b"release 0\n" if line == b"paused 1\n" else None,
            request=b"request 1\n")
        self.assertEqual(result["reason"], "child_nonzero")
        self.assertEqual(result["exit_code"], 22)
        self.assertIn(b"ack_refused\n", (attempt / "stdout.bin").read_bytes())

    def test_missing_release_times_out_and_retains_pause(self):
        result, attempt, _ = self.execute(
            "exchange", request=b"request 1\n",
            bounds=run.Bounds(deadline_seconds=0.5))
        self.assertEqual(result["reason"], "deadline")
        self.assertTrue(result["child_killed"])
        self.assertEqual(result["commands"], 1)
        self.assertEqual((attempt / "stdout.bin").read_bytes(), b"paused 1\n")

    def test_duplicate_ack_refused_by_actual_child(self):
        result, attempt, _ = self.execute(
            "exchange", lambda line: b"release 1\n" if line.startswith(b"paused") else None,
            request=b"request 1\n")
        self.assertEqual(result["reason"], "child_nonzero")
        self.assertEqual(result["exit_code"], 23)
        self.assertIn(b"ack_refused\n", (attempt / "stdout.bin").read_bytes())

    def test_callback_cancellation_terminates_owned_child(self):
        def cancel(line):
            raise KeyboardInterrupt("authored_cancel")
        result, _, _ = self.execute("wait", cancel)
        self.assertEqual(result["exception_type"], "KeyboardInterrupt")
        self.assertEqual(result["reason"], "authored_cancel")
        self.assertTrue(result["child_killed"])

    def test_invalid_command_is_retained_and_child_terminated(self):
        result, _, _ = self.execute("wait", lambda line: b"two\ncommands\n")
        self.assertEqual(result["reason"], "command_not_single_line")
        self.assertTrue(result["child_killed"])

    def test_dispatch_failure_is_retained(self):
        attempt = self.root / "dispatch"
        result = run.execute_owned([str(self.root / "absent-executable")], attempt,
                                   run.Bounds(), lambda line: None)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["exception_type"], "FileNotFoundError")
        self.assertIsNone(result["exit_code"])
        self.assertFalse(result["child_killed"])
        self.assertEqual(result, json.loads((attempt / "result.json").read_text()))
        self.assertEqual((attempt / "stdout.bin").read_bytes(), b"")

    def test_existing_attempt_preserved(self):
        attempt = self.root / "existing"
        attempt.mkdir()
        marker = attempt / "prior.txt"
        marker.write_bytes(b"prior retained attempt")
        with self.assertRaises(FileExistsError):
            run.execute_owned([sys.executable, "-u", str(CHILD), "wait"],
                              attempt, run.Bounds(), lambda line: None)
        self.assertEqual(list(attempt.iterdir()), [marker])
        self.assertEqual(marker.read_bytes(), b"prior retained attempt")


if __name__ == "__main__":
    unittest.main()
