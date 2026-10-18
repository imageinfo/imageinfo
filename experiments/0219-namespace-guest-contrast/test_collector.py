"""Actual authored subprocess controls; no guest, native worker or probes.

All attempts, including deliberately failed attempts, remain below .local for
independent inspection. The fake observations make no storage claims.
"""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import guest_collector as collector
import protocol

CHILD = Path(__file__).with_name("authored_child.py").resolve()


class OwnedTransportControls(unittest.TestCase):
    def setUp(self):
        parent = Path(__file__).resolve().parents[2] / ".local" / "0219-collector-controls"
        parent.mkdir(parents=True, exist_ok=True)
        self.root = Path(tempfile.mkdtemp(prefix="authored-", dir=parent))
        (self.root / "case.json").write_text(json.dumps({"test": self.id()}) + "\n")
        self.observer = collector.load_observer218()

    def execute(self, mode, callback=lambda raw: None, **kwargs):
        run = self.observer.run
        bounds = kwargs.pop("bounds", run.Bounds(deadline_seconds=2))
        children = []
        actual = subprocess.Popen
        def launch(*args, **options):
            child = actual(*args, **options)
            children.append(child)
            return child
        with mock.patch.object(run.subprocess, "Popen", side_effect=launch):
            result = run.execute_owned([sys.executable, "-u", str(CHILD), mode, "authored219"],
                                       self.root / "transport", bounds, callback, **kwargs)
        self.assertEqual(len(children), 1)
        self.assertIsNotNone(children[0].poll())
        self.assertTrue(result["exit_confirmed"])
        self.assertTrue(result["threads_stopped"])
        self.assertFalse(result["replayed"])
        self.assertEqual(json.loads((self.root / "transport/result.json").read_text()), result)
        return result

    def test_deadline_retained_and_postexit_observer_runs_only_after_exit(self):
        observed = []
        def after_exit(record):
            transcript = [json.loads(line) for line in
                          (self.root / "transport/transcript.jsonl").read_text().splitlines()]
            self.assertEqual(transcript[-1]["kind"], "exit")
            self.assertFalse(transcript[-1]["child_alive"])
            self.assertTrue(transcript[-1]["value"]["exit_confirmed"])
            observed.append("confirmed")
        result = self.execute("wait", bounds=self.observer.run.Bounds(deadline_seconds=.3),
                              after_exit=after_exit)
        self.assertEqual(result["reason"], "deadline")
        self.assertEqual(observed, ["confirmed"])
        self.assertTrue(result["child_killed"])

    def test_partial_eof_capture_and_nonzero_are_retained(self):
        for mode, reason in (("partial", "stdout_unterminated_line"),
                             ("nonzero", "child_nonzero")):
            with self.subTest(mode=mode):
                self.root = self.root / mode
                self.root.mkdir()
                result = self.execute(mode)
                self.assertEqual(result["reason"], reason)
                self.assertEqual(result["status"], "failed")

    def test_capture_bounds_are_enforced(self):
        for mode, key in (("stdout_overflow", "stdout_bytes"),
                          ("stderr_overflow", "stderr_bytes")):
            with self.subTest(mode=mode):
                self.root = self.root / mode
                self.root.mkdir()
                result = self.execute(mode, bounds=self.observer.run.Bounds(**{key: 128}))
                self.assertEqual(result["reason"], mode)
                self.assertEqual(result[key], 128)

    def test_callback_cancel_does_not_send_future_commands(self):
        def cancel(raw):
            raise KeyboardInterrupt("authored_cancel")
        result = self.execute("exchange", cancel)
        self.assertEqual(result["exception_type"], "KeyboardInterrupt")
        self.assertEqual(result["commands"], 0)
        self.assertTrue(result["child_killed"])

    def test_lost_child_ack_waits_only_to_deadline(self):
        p = self.observer.protocol
        def release(raw):
            value = p.parse_event(raw)
            if value["kind"] not in ("before_operation", "candidate_result"):
                return None
            command = "release" if value["kind"] == "candidate_result" else "continue"
            return p.encode_command(value, command)
        result = self.execute("lost_ack", release,
                              bounds=self.observer.run.Bounds(deadline_seconds=.4))
        self.assertEqual(result["reason"], "deadline")
        self.assertEqual(result["commands"], 5)

    def test_postexit_observer_failure_is_retained(self):
        def fail(record):
            raise OSError("authored_postexit")
        result = self.execute("early_eof", after_exit=fail)
        self.assertEqual(result["reason"], "after_exit_OSError")
        self.assertEqual(result["status"], "failed")



class FaultingPipe:
    def __init__(self, pipe):
        self.pipe = pipe
    def write(self, data):
        return 0
    def __getattr__(self, key):
        return getattr(self.pipe, key)


class FaultingCapture:
    def __init__(self, handle):
        self.handle = handle
    def __enter__(self):
        self.handle.__enter__()
        return self
    def __exit__(self, *args):
        return self.handle.__exit__(*args)
    def write(self, data):
        raise OSError("authored_capture_failure")
    def __getattr__(self, key):
        return getattr(self.handle, key)


class CaptureFailureControls(unittest.TestCase):
    setUp = OwnedTransportControls.setUp
    execute = OwnedTransportControls.execute
    def test_capture_write_failure_remains_failed(self):
        original = Path.open
        def fault(path, *args, **kwargs):
            handle = original(path, *args, **kwargs)
            return FaultingCapture(handle) if path.name == "stdout.bin" and args == ("xb",) else handle
        with mock.patch.object(Path, "open", fault):
            result = self.execute("partial")
        self.assertEqual(result["reason"], "stdout_capture_OSError")
        self.assertEqual(result["status"], "failed")

    def test_short_child_stdin_write_is_retained(self):
        run = self.observer.run
        original = subprocess.Popen
        def launch(*args, **kwargs):
            child = original(*args, **kwargs)
            child.stdin = FaultingPipe(child.stdin)
            return child
        with mock.patch.object(run.subprocess, "Popen", side_effect=launch):
            result = run.execute_owned([sys.executable, "-u", str(CHILD), "wait", "authored219"],
                                       self.root / "short-write", run.Bounds(deadline_seconds=1),
                                       lambda raw: None, request=b"command\n")
        self.assertEqual(result["reason"], "stdin_OSError")
        self.assertTrue(result["exit_confirmed"])
        self.assertEqual(json.loads((self.root / "short-write/result.json").read_text()), result)




class CollectedControls(unittest.TestCase):
    def setUp(self):
        OwnedTransportControls.setUp(self)
        from types import SimpleNamespace
        self.phases = []
        self.events = []
        def snapshot(fixture, phase, **kwargs):
            self.phases.append(phase)
            if phase == "exited":
                trace = [json.loads(line) for line in
                         (self.root / "attempt/transcript.jsonl").read_text().splitlines()]
                exit_record = next(item for item in trace if item["kind"] == "exit")
                self.assertFalse(exit_record["child_alive"])
                self.assertTrue(exit_record["value"]["exit_confirmed"])
            return {"authored": True, "phase": phase}
        def prepare(root, case, unit):
            return {"source": str(self.root / "source.bin")}
        self.fixtures = SimpleNamespace(prepare_fixture=prepare, snapshot_fixture=snapshot)
        self.observer.probe = SimpleNamespace(
            _stat_profile=lambda: {"authored": True},
            read_snapshot=lambda *a, **kw: {"authored": True},
            write_open_probe=lambda *a, **kw: {"expectation_met": True, "authored": True})

    def collect(self, mode="exchange", fail_stage=None, command_failure=None, parent_channel=None, **kwargs):
        test = self
        class Parent:
            def notify(self, event, raw, deadline):
                test.events.append(deepcopy(event))
            def exchange(self, event, raw, deadline):
                self.notify(event, raw, deadline)
                if event["stage"] == fail_stage:
                    if command_failure == "lost":
                        raise TimeoutError("authored_lost_parent")
                    if command_failure == "cancel":
                        return protocol.encode_command(event, "cancel")
                    if command_failure == "stale":
                        value = json.loads(protocol.encode_command(event, protocol.COMMANDS[event["stage"]]))
                        value["seq"] -= 1
                        return json.dumps(value).encode() + b"\n"
                return protocol.encode_command(event, protocol.COMMANDS[event["stage"]])
        request = {"argv": [sys.executable, "-u", str(CHILD), mode, "authored219"],
                   "fixture_root": str(self.root / "fixture"),
                   "attempt_dir": str(self.root / "attempt"), "unit": "authored219",
                   "case": "persistent-write-error", "bounds": {"deadline_seconds": 2},
                   "bindings": {"authored": True}}
        request.update(kwargs)
        result = collector.execute_collected(request, parent_channel=parent_channel or Parent(), observer=self.observer,
                                             fixture_api=self.fixtures, verify=lambda request: None)
        self.assertFalse(result["guest"]["replayed"])
        self.assertEqual(json.loads((self.root / "attempt/guest.json").read_text()), result["guest"])
        return result

    def test_complete_outer_exchange_retains_live_then_postexit_order(self):
        result = self.collect()
        self.assertTrue(result["guest"]["protocol_complete"])
        self.assertEqual([event["stage"] for event in self.events], list(protocol.STAGES))
        self.assertLess(self.phases.index("cleared_hold"), self.phases.index("exited"))
        self.assertEqual(self.phases[-1], "final")
        trace = [json.loads(line) for line in
                 (self.root / "attempt/guest-transcript.jsonl").read_text().splitlines()]
        sent = [json.loads(bytes.fromhex(item["value"]["bytes_hex"])) for item in trace
                if item["kind"] == "worker_command_sent"]
        self.assertEqual([item["command"] for item in sent], ["continue"] * 5 + ["release"])

    def test_lost_parent_candidate_ack_never_releases_child(self):
        result = self.collect(fail_stage="candidate_hold", command_failure="lost")
        self.assertFalse(result["guest"]["protocol_complete"])
        self.assertTrue(result["transport"]["exit_confirmed"])
        self.assertNotIn("cleared_hold", self.phases)
        self.assertNotIn("final", self.phases)
        self.assertEqual(self.events[-1]["stage"], "failure")
        self.assertEqual(result["transport"]["commands"], 5)

    def test_cancel_at_release_gate_stops_owned_child(self):
        result = self.collect(fail_stage="cleared_hold", command_failure="cancel")
        self.assertFalse(result["guest"]["protocol_complete"])
        self.assertTrue(result["transport"]["child_killed"])
        self.assertNotIn("released", [event["stage"] for event in self.events])

    def test_stale_parent_command_refuses_without_child_release(self):
        result = self.collect(fail_stage="cleared_hold", command_failure="stale")
        self.assertFalse(result["guest"]["protocol_complete"])
        self.assertNotIn("released", [event["stage"] for event in self.events])
        self.assertEqual(result["transport"]["commands"], 5)

    def test_exit_zero_before_runtime_is_not_protocol_success(self):
        result = self.collect("exit_race")
        self.assertEqual(result["transport"]["exit_code"], 0)
        self.assertFalse(result["guest"]["protocol_complete"])
        self.assertNotIn("final", self.phases)

    def test_early_clean_eof_is_failed_attempt(self):
        result = self.collect("early_eof")
        self.assertFalse(result["guest"]["protocol_complete"])
        self.assertEqual(self.events[-1]["stage"], "failure")


    def test_late_stderr_capture_failure_cannot_become_complete(self):
        result = self.collect("late_stderr", bounds={"deadline_seconds": 2, "stderr_bytes": 128})
        self.assertFalse(result["guest"]["protocol_complete"])
        self.assertEqual(result["transport"]["reason"], "stderr_overflow")
        self.assertNotIn("final", self.phases)

    def test_preparation_failure_retained_before_child_launch(self):
        self.fixtures.prepare_fixture = mock.Mock(side_effect=OSError("authored_prepare_failure"))
        with mock.patch.object(self.observer.run.subprocess, "Popen") as launch:
            result = self.collect()
        launch.assert_not_called()
        self.assertFalse(result["guest"]["child_started"])
        self.assertIsNone(result["transport"])
        self.assertEqual(result["guest"]["reason"], "authored_prepare_failure")

    def test_existing_attempt_cannot_be_replayed(self):
        self.collect("early_eof")
        retained = {path.name: path.read_bytes() for path in (self.root / "attempt").iterdir()}
        with self.assertRaises(FileExistsError):
            self.collect()
        self.assertEqual({path.name: path.read_bytes() for path in (self.root / "attempt").iterdir()}, retained)


class MailboxControls(unittest.TestCase):
    setUp = OwnedTransportControls.setUp

    def channel(self, **kwargs):
        command = self.root / "commands"
        command.write_bytes(b"")
        channel = collector.MailboxChannel(self.root / "events", command, **kwargs)
        self.addCleanup(channel.close)
        return channel, command

    def test_single_bound_command_roundtrip(self):
        import time
        channel, command = self.channel()
        command.write_bytes(b"authored\n")
        self.assertEqual(channel.exchange({}, b"event\n", time.monotonic() + .2), b"authored\n")
        self.assertEqual((self.root / "events").read_bytes(), b"event\n")

    def test_lost_parent_expires_instead_of_accepting_mailbox_eof(self):
        import time
        channel, _ = self.channel()
        with self.assertRaises(TimeoutError):
            channel.exchange({}, b"event\n", time.monotonic() + .03)
        self.assertEqual(channel.count, 0)

    def test_duplicate_batch_is_retained_and_refused(self):
        import time
        channel, command = self.channel()
        command.write_bytes(b"one\ntwo\n")
        with self.assertRaisesRegex(ValueError, "unsolicited_command_batch"):
            channel.exchange({}, b"event\n", time.monotonic() + .2)
        self.assertEqual(command.read_bytes(), b"one\ntwo\n")

    def test_oversized_command_refuses(self):
        import time
        channel, command = self.channel(command_bytes=8)
        command.write_bytes(b"123456789\n")
        with self.assertRaisesRegex(ValueError, "parent_command_(line_)?bound"):
            channel.exchange({}, b"event\n", time.monotonic() + .2)

    def test_replacement_refused_preserving_both_files(self):
        import time
        channel, command = self.channel()
        prior = self.root / "retained-commands"
        # Windows CRT sharing prevents replacement while this FD is open.
        # Close only in this authored seam to test the stored identity check.
        channel.commands.close()
        command.rename(prior)
        command.write_bytes(b"replacement\n")
        with self.assertRaisesRegex(ValueError, "command_mailbox_changed"):
            channel.exchange({}, b"event\n", time.monotonic() + .2)
        self.assertEqual(prior.read_bytes(), b"")
        self.assertEqual(command.read_bytes(), b"replacement\n")

    def test_event_write_failure_refuses_without_command_read(self):
        import time
        channel, command = self.channel()
        channel.events = FaultingCapture(channel.events)
        command.write_bytes(b"authored\n")
        with self.assertRaisesRegex(OSError, "authored_capture_failure"):
            channel.exchange({}, b"event\n", time.monotonic() + .2)
        self.assertEqual(channel.count, 0)





class ExitUncertaintyControl(unittest.TestCase):
    setUp = OwnedTransportControls.setUp

    def test_unconfirmed_exit_never_calls_postexit_observer(self):
        import io
        child = mock.Mock(pid=219, returncode=None)
        child.stdin, child.stdout, child.stderr = io.BytesIO(), io.BytesIO(), io.BytesIO()
        child.poll.return_value = None
        child.wait.side_effect = subprocess.TimeoutExpired("authored", 2)
        after_exit = mock.Mock()
        run = self.observer.run
        with mock.patch.object(run.subprocess, "Popen", return_value=child):
            result = run.execute_owned(["authored-model-only"], self.root / "uncertain-exit",
                                       run.Bounds(deadline_seconds=.05), lambda raw: None,
                                       after_exit=after_exit)
        after_exit.assert_not_called()
        self.assertFalse(result["exit_confirmed"])
        self.assertEqual(result["reason"], "owned_child_cleanup_uncertain")
        self.assertEqual(json.loads((self.root / "uncertain-exit/result.json").read_text()), result)




class FiniteCountControls(unittest.TestCase):
    setUp = OwnedTransportControls.setUp
    execute = OwnedTransportControls.execute

    def reply(self, raw):
        p = self.observer.protocol
        value = p.parse_event(raw)
        if value["kind"] in ("before_operation", "candidate_result"):
            return p.encode_command(value, "release" if value["kind"] == "candidate_result" else "continue")
        return None

    def test_line_bound_before_decoding_large_stdout(self):
        result = self.execute("stdout_overflow", bounds=self.observer.run.Bounds(line_bytes=64))
        self.assertEqual(result["reason"], "stdout_line_overflow")

    def test_event_count_bound_stops_later_child_commands(self):
        result = self.execute("exchange", self.reply, bounds=self.observer.run.Bounds(events=1))
        self.assertEqual(result["reason"], "event_bound")
        self.assertEqual(result["commands"], 1)

    def test_command_count_bound_stops_later_child_commands(self):
        result = self.execute("exchange", self.reply, bounds=self.observer.run.Bounds(commands=1))
        self.assertEqual(result["reason"], "command_bound")
        self.assertEqual(result["commands"], 1)




class HttpControls(unittest.TestCase):
    """Injected fake HTTP connections only; never opens a socket."""
    def channel(self, body=b"command\n", *, status=200, headers=None):
        response = mock.Mock(status=status)
        values = {"Content-Length": str(len(body)), "Transfer-Encoding": None}
        values.update(headers or {})
        response.getheader.side_effect = values.get
        response.read.return_value = body
        connection = mock.Mock()
        connection.getresponse.return_value = response
        factory = mock.Mock(return_value=connection)
        channel = collector.HttpChannel("http://10.0.2.2:42319/event/authored219",
                                        connection_factory=factory)
        return channel, factory, connection, response

    def test_exact_unit_post_is_single_bounded_request(self):
        import time
        channel, factory, connection, response = self.channel()
        self.assertEqual(channel.exchange({"unit": "authored219"}, b"event\n", time.monotonic() + 1), b"command\n")
        factory.assert_called_once()
        self.assertEqual(factory.call_args.args, ("10.0.2.2", 42319))
        self.assertGreater(factory.call_args.kwargs["timeout"], 0)
        connection.request.assert_called_once_with("POST", "/event/authored219", body=b"event\n",
            headers={"Content-Type": "application/x-ndjson", "Content-Length": "6", "Connection": "close",
                     "X-Imageinfo-Sha256": __import__("hashlib").sha256(b"event\n").hexdigest()})
        response.read.assert_called_once_with(9)
        connection.close.assert_called_once()

    def test_unapproved_endpoint_shapes_refuse_before_connection(self):
        for endpoint in ("http://127.0.0.1:42319/event/authored219",
                         "https://10.0.2.2:42319/event/authored219",
                         "http://name@10.0.2.2:42319/event/authored219",
                         "http://10.0.2.2:42319/event/authored219?x=1",
                         "http://10.0.2.2:80/event/authored219",
                         "http://10.0.2.2:42319/event/../other"):
            factory = mock.Mock()
            with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                collector.HttpChannel(endpoint, connection_factory=factory)
            factory.assert_not_called()

    def test_response_status_length_transfer_and_actual_body_bounds(self):
        import time
        for body, status, headers in ((b"x", 302, {}), (b"x", 200, {"Content-Length": None}),
                (b"x", 200, {"Content-Length": "1025"}), (b"x", 200, {"Content-Length": "0"}),
                (b"x", 200, {"Transfer-Encoding": "chunked"}),
                (b"x", 200, {"Content-Length": "2"}), (b"xx", 200, {"Content-Length": "1"})):
            with self.subTest(body=body, status=status, headers=headers):
                channel, factory, connection, _ = self.channel(body, status=status, headers=headers)
                with self.assertRaises(ValueError):
                    channel.exchange({"unit": "authored219"}, b"event\n", time.monotonic() + 1)
                factory.assert_called_once()
                connection.close.assert_called_once()

    def test_expired_or_wrong_unit_request_never_connects(self):
        import time
        for unit, deadline, error in (("authored219", time.monotonic() - 1, TimeoutError),
                                      ("foreign", time.monotonic() + 1, ValueError)):
            channel, factory, _, _ = self.channel()
            with self.assertRaises(error):
                channel.exchange({"unit": unit}, b"event\n", deadline)
            factory.assert_not_called()

    def test_connection_failure_closes_without_retry(self):
        import time
        channel, factory, connection, _ = self.channel()
        connection.request.side_effect = OSError("authored_http_write_failure")
        with self.assertRaises(OSError):
            channel.exchange({"unit": "authored219"}, b"event\n", time.monotonic() + 1)
        factory.assert_called_once()
        connection.request.assert_called_once()
        connection.close.assert_called_once()

    def test_late_response_refuses_even_valid_bytes(self):
        import time
        channel, factory, connection, _ = self.channel()
        original = collector.time.monotonic
        deadline = original() + .02
        connection.getresponse.side_effect = lambda: (time.sleep(.04) or mock.Mock())
        with self.assertRaises(TimeoutError):
            channel.exchange({"unit": "authored219"}, b"event\n", deadline)
        factory.assert_called_once()
        self.assertTrue(channel.transport_state()["poisoned"])
        for thread in channel.threads:
            thread.join(timeout=.2)
        connection.close.assert_called_once()

    def test_notification_ack_is_exact(self):
        import time
        for body, accepted in ((b"{}\n", True), (b"{}", False), (b"command\n", False)):
            channel, _, connection, _ = self.channel(body)
            if accepted:
                channel.notify({"unit": "authored219"}, b"event\n", time.monotonic() + 1)
            else:
                with self.assertRaises(ValueError):
                    channel.notify({"unit": "authored219"}, b"event\n", time.monotonic() + 1)
            connection.close.assert_called_once()



class HttpDeadlineControls(unittest.TestCase):
    channel = HttpControls.channel

    def test_blocked_each_http_phase_returns_at_absolute_deadline_and_never_retries(self):
        import threading
        import time
        for phase in ("request", "getresponse", "read"):
            with self.subTest(phase=phase):
                release = threading.Event()
                entered = threading.Event()
                channel, factory, connection, response = self.channel()
                target = response if phase == "read" else connection
                original = getattr(target, phase)
                result = original.return_value
                def blocked(*args, **kwargs):
                    entered.set()
                    release.wait(2)
                    return result
                original.side_effect = blocked
                started = time.monotonic()
                try:
                    with self.assertRaises(TimeoutError):
                        channel.exchange({"unit": "authored219", "stage": "candidate_hold"},
                                         b"event\n", time.monotonic() + .05)
                    self.assertLess(time.monotonic() - started, .5)
                    self.assertTrue(entered.is_set())
                    retained = channel.transport_state()
                    self.assertTrue(retained["poisoned"])
                    self.assertTrue(retained["operations"][0]["timed_out"])
                    self.assertEqual(retained["retained_threads"], 1)
                    with self.assertRaisesRegex(RuntimeError, "poisoned"):
                        channel.notify({"unit": "authored219"}, b"failure\n", time.monotonic() + .2)
                    factory.assert_called_once()
                finally:
                    release.set()
                    for thread in channel.threads:
                        thread.join(timeout=1)
                self.assertTrue(channel.transport_state()["operations"][0]["completed"])
                self.assertTrue(channel.transport_state()["poisoned"])
                factory.assert_called_once()
                connection.close.assert_called_once()

    def test_interrupted_owner_wait_poison_prevents_later_dispatch(self):
        import threading
        import time
        channel, factory, connection, _ = self.channel()
        release, entered = threading.Event(), threading.Event()
        def block(*args, **kwargs):
            entered.set()
            release.wait(2)
        connection.request.side_effect = block
        actual_queue = collector.queue.Queue
        class InterruptQueue(actual_queue):
            def get(self, *args, **kwargs):
                entered.wait(.5)
                raise KeyboardInterrupt("authored_wait_cancel")
        try:
            with mock.patch.object(collector.queue, "Queue", InterruptQueue):
                with self.assertRaises(KeyboardInterrupt):
                    channel.exchange({"unit": "authored219"}, b"event\n", time.monotonic() + 1)
            state = channel.transport_state()
            self.assertTrue(state["poisoned"])
            self.assertTrue(state["operations"][0]["aborted"])
            with self.assertRaisesRegex(RuntimeError, "poisoned"):
                channel.notify({"unit": "authored219"}, b"failure\n", time.monotonic() + 1)
            factory.assert_called_once()
        finally:
            release.set()
            for thread in channel.threads:
                thread.join(timeout=1)
        self.assertTrue(channel.transport_state()["operations"][0]["completed"])


class HttpCollectedDeadlineControls(unittest.TestCase):
    setUp = CollectedControls.setUp
    collect = CollectedControls.collect

    def blocking_channel(self, blocked_stage):
        import threading
        release, entered = threading.Event(), threading.Event()
        connections = []
        def factory(*args, **kwargs):
            connection = mock.Mock()
            state = {}
            def request(method, path, body, headers):
                event = protocol.parse_event(body)
                state["event"] = event
                if event["stage"] == blocked_stage:
                    entered.set()
                    release.wait(2)
            def getresponse():
                event = state["event"]
                value = (protocol.encode_command(event, protocol.COMMANDS[event["stage"]])
                         if event["stage"] in protocol.COMMANDS else b"{}\n")
                response = mock.Mock(status=200)
                response.getheader.side_effect = {"Content-Length": str(len(value))}.get
                response.read.return_value = value
                return response
            connection.request.side_effect = request
            connection.getresponse.side_effect = getresponse
            connections.append(connection)
            return connection
        channel = collector.HttpChannel("http://10.0.2.2:42319/event/authored219", connection_factory=factory)
        def cleanup():
            release.set()
            for thread in channel.threads:
                thread.join(timeout=1)
        self.addCleanup(cleanup)
        return channel, release, entered, connections

    def test_late_candidate_ack_never_releases_child_or_changes_saved_session(self):
        channel, release, entered, connections = self.blocking_channel("candidate_hold")
        result = self.collect(parent_channel=channel, parent_gate_seconds=.05)
        self.assertTrue(entered.is_set())
        self.assertFalse(result["guest"]["protocol_complete"])
        self.assertTrue(result["transport"]["exit_confirmed"])
        self.assertEqual(result["transport"]["commands"], 5)
        self.assertTrue(result["guest"]["parent_transport"]["poisoned"])
        self.assertNotIn("cleared_hold", self.phases)
        saved = (self.root / "attempt/guest.json").read_bytes()
        count = len(connections)
        release.set()
        for thread in channel.threads:
            thread.join(timeout=1)
        self.assertEqual((self.root / "attempt/guest.json").read_bytes(), saved)
        self.assertEqual(len(connections), count)
        self.assertNotIn("final", self.phases)

    def test_final_notification_timeout_retains_latest_transport_uncertainty(self):
        channel, _, entered, _ = self.blocking_channel("final")
        result = self.collect(parent_channel=channel, parent_gate_seconds=.05)
        self.assertTrue(entered.is_set())
        self.assertFalse(result["guest"]["protocol_complete"])
        state = result["guest"]["parent_transport"]
        self.assertTrue(state["poisoned"])
        self.assertEqual(state["operations"][-1]["stage"], "final")
        self.assertTrue(state["operations"][-1]["timed_out"])
        self.assertEqual(state["retained_threads"], 1)



class ExportControls(unittest.TestCase):
    def setUp(self):
        OwnedTransportControls.setUp(self)
        self.fixture = self.root / "fixture"
        self.fixture.mkdir()
        (self.fixture / "unit").mkdir()
        self.attempt = self.root / "attempt"
        self.attempt.mkdir()
        self.volume = self.root / "volume-binding.json"
        self.volume.write_bytes(b"authored-volume\n")
        for name in collector.REQUIRED_EXPORT_NAMES - {"volume-binding.json"}:
            (self.attempt / name).write_bytes(("authored-" + name).encode())
        self.source = self.fixture / "source.bin"
        self.source.write_bytes(b"authored-source")
        self.channel = mock.Mock()
        self.request = {"volume_binding_path": str(self.volume)}
        self.manifest = {"root": str(self.fixture), "source": str(self.source),
                         "old": str(self.root / "absent-old-source.bin")}

    def export(self, **kwargs):
        return collector.export_closed(self.request, self.manifest, self.attempt,
                                       self.channel, exit_confirmed=kwargs.get("exit_confirmed", True))

    def test_no_confirmed_exit_refuses_before_io_or_upload(self):
        with mock.patch.object(Path, "lstat") as inspect:
            with self.assertRaisesRegex(ValueError, "actual confirmed child exit"):
                self.export(exit_confirmed=False)
        inspect.assert_not_called()
        self.channel.upload.assert_not_called()
        self.channel.export_complete.assert_not_called()

    def test_fixed_names_hashes_and_optional_absences_preserve_files(self):
        import hashlib
        foreign = self.fixture / "unit/foreign.bin"
        foreign.write_bytes(b"preserve")
        before = {path: path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        manifest = self.export()
        self.assertEqual({item["name"] for item in manifest["files"]},
                         collector.REQUIRED_EXPORT_NAMES | {"source.bin"})
        self.assertEqual({item["name"] for item in manifest["missing"]},
                         collector.EXPORT_NAMES - collector.REQUIRED_EXPORT_NAMES - {"source.bin"})
        self.assertTrue(all(item["status"] == "absent" for item in manifest["missing"]))
        for call in self.channel.upload.call_args_list:
            name, body, deadline = call.args
            item = next(item for item in manifest["files"] if item["name"] == name)
            self.assertEqual(item["bytes"], len(body))
            self.assertEqual(item["sha256"], hashlib.sha256(body).hexdigest())
        self.assertEqual({path: path.read_bytes() for path in before}, before)
        self.channel.export_complete.assert_called_once()
        self.assertEqual(self.channel.export_complete.call_args.args[0], manifest)

    def test_required_capture_missing_prevents_completion(self):
        (self.attempt / "events.jsonl").unlink()
        with self.assertRaisesRegex(RuntimeError, "required_export_capture_unavailable_events.jsonl"):
            self.export()
        self.channel.export_complete.assert_not_called()

    def test_oversized_optional_artifact_is_error_not_uploaded(self):
        oversized = self.fixture / "unit/candidate.bin"
        with oversized.open("wb") as handle:
            handle.truncate(16 * 1024 * 1024 + 1)
        manifest = self.export()
        item = next(item for item in manifest["missing"] if item["name"] == "candidate.bin")
        self.assertEqual(item["status"], "error")
        self.assertNotIn("candidate.bin", [call.args[0] for call in self.channel.upload.call_args_list])
        self.assertEqual(oversized.stat().st_size, 16 * 1024 * 1024 + 1)

    def test_partial_upload_failure_has_no_retry_or_completion(self):
        self.channel.upload.side_effect = OSError("authored_upload_failure")
        with self.assertRaisesRegex(OSError, "authored_upload_failure"):
            self.export()
        self.channel.upload.assert_called_once()
        self.channel.export_complete.assert_not_called()
        self.assertEqual(self.source.read_bytes(), b"authored-source")
        self.assertEqual(len(list(self.attempt.iterdir())), 7)

    def test_http_export_name_and_body_bounds_before_request(self):
        channel, factory, _, _ = HttpControls.channel(self, b"{}\n")
        for name, body in (("foreign.bin", b"x"), ("source.bin", b"x" * (16 * 1024 * 1024 + 1))):
            with self.assertRaisesRegex(ValueError, "fixed bounded export artifact"):
                channel.upload(name, body, 1)
        factory.assert_not_called()



class GuestEntryBindingControls(unittest.TestCase):
    setUp = CollectedControls.setUp
    collect = CollectedControls.collect

    def test_selected_guest_entry_uses_actual_captured_root_unit_drive(self):
        binding = self.root / "volume.json"
        capture = {"unit": "authored219", "root": str(self.root / "fixture"), "drive_root": "E:\\"}
        binding.write_text(json.dumps(capture))
        original = subprocess.Popen
        environments = []
        def launch(*args, **kwargs):
            environments.append(deepcopy(kwargs["env"]))
            return original(*args, **kwargs)
        with mock.patch.object(self.observer.run.subprocess, "Popen", side_effect=launch):
            result = self.collect(worker_test_name=collector.GUEST_TEST_NAME, volume_binding_path=str(binding))
        self.assertTrue(result["guest"]["protocol_complete"])
        self.assertEqual(len(environments), 1)
        selected = environments[0]
        self.assertEqual(selected["IMAGEINFO_219_ROOT"], capture["root"])
        self.assertEqual(selected["IMAGEINFO_219_UNIT"], capture["unit"])
        self.assertEqual(selected["IMAGEINFO_219_GUEST_DRIVE"], "E:")
        self.assertEqual(selected["IMAGEINFO_219_GUEST_APPROVAL"], "explicit-parent-disposable-guest-v1")
        prepared = self.events[0]["observation"]
        self.assertEqual(prepared["volume_binding"], capture)

    def test_guest_entry_without_volume_capture_refuses_before_launch(self):
        with mock.patch.object(self.observer.run.subprocess, "Popen") as launch:
            result = self.collect(worker_test_name=collector.GUEST_TEST_NAME)
        launch.assert_not_called()
        self.assertFalse(result["guest"]["child_started"])
        self.assertFalse(result["guest"]["protocol_complete"])
        self.assertIn("actual bootstrap volume observation", result["transport"]["reason"])

    def test_wrong_captured_root_unit_or_drive_refuses_before_launch(self):
        baseline = {"unit": "authored219", "root": str(self.root / "fixture"), "drive_root": "E:\\"}
        initial_root = self.root
        for key, value in (("unit", "foreign"), ("root", "foreign-root"), ("drive_root", "E:/")):
            with self.subTest(key=key):
                self.root = initial_root / key
                self.root.mkdir()
                capture = dict(baseline, root=str(self.root / "fixture"))
                capture[key] = value
                binding = self.root / "volume.json"
                binding.write_text(json.dumps(capture))
                with mock.patch.object(self.observer.run.subprocess, "Popen") as launch:
                    result = self.collect(worker_test_name=collector.GUEST_TEST_NAME, volume_binding_path=str(binding))
                launch.assert_not_called()
                self.assertFalse(result["guest"]["child_started"])
                self.assertFalse(result["guest"]["protocol_complete"])


if __name__ == "__main__":
    unittest.main()
