"""Authored fake-channel controls; never connect to a guest or native worker."""
import base64
import copy
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import http.client
import hashlib
import json
import socket


_spec = importlib.util.spec_from_file_location(
    "namespace_219_host_tests", Path(__file__).with_name("host_controller.py"))
h = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = h
_spec.loader.exec_module(h)


class FakeQga:
    """In-memory QGA file service with observable handle ownership."""
    def __init__(self, data=b"authored", read_response=None, write_response=None):
        self.data = data
        self.position = 0
        self.calls = []
        self.opened = False
        self.read_response = read_response
        self.write_response = write_response

    def __call__(self, command, arguments):
        self.calls.append((command, copy.deepcopy(arguments)))
        if command == "guest-file-open":
            self.opened = True
            self.position = 0
            return 41
        if command == "guest-file-close":
            self.opened = False
            return {}
        if command == "guest-file-flush":
            return {}
        if command == "guest-file-read":
            if self.read_response is not None:
                return copy.deepcopy(self.read_response)
            raw = self.data[self.position:self.position + arguments["count"]]
            self.position += len(raw)
            return {"count": len(raw), "buf-b64": base64.b64encode(raw).decode(),
                    "eof": self.position == len(self.data)}
        if command == "guest-file-write":
            if self.write_response is not None:
                return copy.deepcopy(self.write_response)
            raw = base64.b64decode(arguments["buf-b64"], validate=True)
            self.data += raw
            return {"count": len(raw), "eof": False}
        if command == "guest-exec":
            return {"pid": 123}
        if command == "guest-exec-status":
            return {"exited": True, "exitcode": 0}
        raise AssertionError("unmodeled QGA command: " + command)


class QgaTransferTests(unittest.TestCase):
    def test_exact_bounded_read_retains_all_bytes_and_closes(self):
        raw = bytes(range(256)) * 300
        fake = FakeQga(raw)
        self.assertEqual(h.QgaChannel(fake).read_file("authored.bin", len(raw)), raw)
        self.assertFalse(fake.opened)
        self.assertEqual(fake.calls[-1][0], "guest-file-close")

    def test_authored_sixteen_mib_optional_transfer_does_not_truncate(self):
        raw = b"S" * (16 * 1024 * 1024)
        fake = FakeQga(raw)
        self.assertEqual(h.QgaChannel(fake).read_file("authored-source.bin", len(raw)), raw)
        self.assertFalse(fake.opened)

    def test_over_limit_read_refuses_and_closes_without_reopen(self):
        fake = FakeQga(b"12345")
        with self.assertRaises(h.HostError):
            h.QgaChannel(fake).read_file("authored.bin", 4)
        self.assertFalse(fake.opened)
        self.assertEqual(sum(name == "guest-file-open" for name, _ in fake.calls), 1)

    def test_read_truncation_corrupt_base64_and_invalid_counts_refuse(self):
        for response in (
            {"count": 2, "buf-b64": "YQ==", "eof": True},
            {"count": 1, "buf-b64": "!invalid!", "eof": True},
            {"count": -1, "buf-b64": "", "eof": True},
            {"count": True, "buf-b64": "YQ==", "eof": True},
            {"count": 0, "buf-b64": "", "eof": False},
        ):
            with self.subTest(response=response):
                fake = FakeQga(read_response=response)
                with self.assertRaises(h.HostError):
                    h.QgaChannel(fake).read_file("authored.bin", 100)
                self.assertFalse(fake.opened)

    def test_short_write_is_failure_not_success_or_retry(self):
        fake = FakeQga(write_response={"count": 1, "eof": False})
        with self.assertRaises(h.HostError):
            h.QgaChannel(fake).write_new("authored.bin", b"not-complete")
        self.assertFalse(fake.opened)
        self.assertEqual(sum(name == "guest-file-write" for name, _ in fake.calls), 1)

    def test_cancelled_read_has_no_transfer_or_replay(self):
        fake = FakeQga()
        with self.assertRaises(h.HostError):
            h.QgaChannel(fake, cancel=lambda: True).read_file("authored.bin", 100)
        self.assertFalse(fake.opened)
        self.assertFalse(any(name == "guest-file-read" for name, _ in fake.calls))

    def test_qga_exception_closes_handle_and_does_not_retry(self):
        fake = FakeQga()
        original = fake.__call__
        def failed(command, arguments):
            if command == "guest-file-read":
                fake.calls.append((command, copy.deepcopy(arguments)))
                raise OSError("authored transport loss")
            return original(command, arguments)
        with self.assertRaises(OSError):
            h.QgaChannel(failed).read_file("authored.bin", 100)
        self.assertFalse(fake.opened)
        self.assertEqual(sum(name == "guest-file-read" for name, _ in fake.calls), 1)

    def test_confirmed_exit_retains_actual_code(self):
        fake = FakeQga()
        channel = h.QgaChannel(fake)
        self.assertEqual(channel.launch("authored.exe", ["literal"]), 123)
        self.assertEqual(channel.wait_exit(123, 1)["exitcode"], 0)


class QmpChannelTests(unittest.TestCase):
    def test_raw_return_is_preserved_and_request_is_not_replayed(self):
        calls = []
        raw = [{"node-name": "authored-node", "drv": "raw"}]
        def call(command, arguments):
            calls.append((command, copy.deepcopy(arguments)))
            return copy.deepcopy(raw)
        channel = h.QmpChannel(call)
        self.assertEqual(channel.call("query-named-block-nodes"), raw)
        self.assertEqual(len(calls), 1)

    def test_transport_error_is_bounded_failure_without_retry(self):
        calls = []
        def call(command, arguments):
            calls.append(command)
            raise OSError("authored QMP failure")
        with self.assertRaises(OSError):
            h.QmpChannel(call).call("query-block")
        self.assertEqual(calls, ["query-block"])

    def test_oversized_return_refuses(self):
        channel = h.QmpChannel(lambda command, arguments: {"oversize": "x" * (h.MAX_REPLY_BYTES + 1)})
        with self.assertRaises(h.HostError):
            channel.call("query-block")


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class FakeJsonSocket:
    """Deterministic partial send/receive with honored socket idle ceilings."""
    def __init__(self, clock):
        self.clock = clock
        self.incoming = [(b'{"QMP":{}}\n', 0), (b'{"return":{},"id":1}\n', 0)]
        self.sent = bytearray()
        self.timeouts = []
        self.timeout = 1
        self.send_bound = 100000
        self.send_delay = 0
        self.recv_count = 0
        self.closed = False

    def settimeout(self, value):
        self.timeout = value
        self.timeouts.append(value)

    def connect(self, path):
        self.path = path

    def delay(self, delay):
        if delay >= self.timeout:
            self.clock.now += self.timeout
            raise TimeoutError("authored socket deadline")
        self.clock.now += delay

    def recv(self, count):
        self.recv_count += 1
        if not self.incoming:
            self.delay(self.timeout)
        chunk, delay = self.incoming.pop(0)
        self.delay(delay)
        if len(chunk) > count:
            self.incoming.insert(0, (chunk[count:], 0))
        return chunk[:count]

    def send(self, raw):
        self.delay(self.send_delay)
        count = min(len(raw), self.send_bound)
        self.sent.extend(raw[:count])
        return count

    def shutdown(self, how):
        self.closed = True

    def close(self):
        self.closed = True


class JsonSocketDeadlineTests(unittest.TestCase):
    def channel(self, timeout=.1):
        clock = FakeClock()
        fake = FakeJsonSocket(clock)
        with patch.object(h.socket, "AF_UNIX", 1, create=True), patch.object(h.socket, "socket", return_value=fake):
            channel = h.JsonSocketChannel("authored.sock", timeout=timeout, clock=clock)
        self.addCleanup(channel.close)
        return channel, fake, clock

    def test_fragmented_send_and_reply_preserve_exact_single_request(self):
        channel, fake, _ = self.channel()
        fake.send_bound = 2
        fake.incoming = [(bytes([byte]), 0) for byte in b'{"return":{"authored":true},"id":2}\n']
        self.assertEqual(channel.call("query-block"), {"authored": True})
        requests = [json.loads(line) for line in fake.sent.splitlines()]
        self.assertEqual([request["execute"] for request in requests], ["qmp_capabilities", "query-block"])

    def test_trickled_reply_has_absolute_deadline_and_poisoned_channel(self):
        channel, fake, clock = self.channel()
        fake.incoming = [(bytes([byte]), .025) for byte in b'{"return":{},"id":2}\n']
        with self.assertRaises((h.HostError, TimeoutError)):
            channel.call("query-block")
        self.assertLessEqual(clock.now, .101)
        self.assertTrue(fake.closed)
        sends = bytes(fake.sent)
        with self.assertRaises(h.HostError):
            channel.call("query-block")
        self.assertEqual(bytes(fake.sent), sends)

    def test_partial_send_shares_aggregate_call_deadline_and_is_not_replayed(self):
        channel, fake, clock = self.channel()
        fake.send_bound, fake.send_delay = 1, .025
        with self.assertRaises((h.HostError, TimeoutError)):
            channel.call("query-block")
        self.assertLessEqual(clock.now, .101)
        self.assertTrue(fake.closed)
        self.assertNotIn(b'"execute": "query-block"', bytes(fake.sent).splitlines()[-1])

    def test_async_events_cannot_reset_whole_call_deadline(self):
        channel, fake, clock = self.channel()
        fake.incoming = [(b'{"event":"AUTHORED"}\n', .025)] * 8 + [(b'{"return":{},"id":2}\n', 0)]
        with self.assertRaises((h.HostError, TimeoutError)):
            channel.call("query-block")
        self.assertLessEqual(clock.now, .101)
        self.assertTrue(fake.closed)

    def test_stale_response_is_refusal_without_second_request(self):
        channel, fake, _ = self.channel()
        fake.incoming = [(b'{"return":{},"id":1}\n', 0)]
        with self.assertRaises(h.HostError):
            channel.call("query-block")
        self.assertTrue(fake.closed)
        self.assertEqual(len(fake.sent.splitlines()), 2)

    def test_zero_byte_send_is_failure_not_retry_loop(self):
        channel, fake, _ = self.channel()
        fake.send_bound = 0
        with self.assertRaises(h.HostError):
            channel.call("query-block")
        self.assertTrue(fake.closed)

    def test_eof_and_oversized_unterminated_reply_poison_without_replay(self):
        for raw in (b"", b"x" * 129):
            with self.subTest(bytes=len(raw)):
                channel, fake, _ = self.channel()
                fake.incoming = [(raw, 0)]
                with patch.object(h, "MAX_REPLY_BYTES", 128):
                    with self.assertRaises(h.HostError):
                        channel.call("query-block")
                self.assertTrue(fake.closed)
                self.assertEqual(len(fake.sent.splitlines()), 2)

    def test_greeting_trickle_is_bounded_before_capabilities_request(self):
        clock = FakeClock()
        fake = FakeJsonSocket(clock)
        fake.incoming = [(bytes([byte]), .025) for byte in b'{"QMP":{}}\n']
        with patch.object(h.socket, "AF_UNIX", 1, create=True), patch.object(h.socket, "socket", return_value=fake):
            with self.assertRaises((h.HostError, TimeoutError)):
                h.JsonSocketChannel("authored.sock", timeout=.1, clock=clock)
        self.assertLessEqual(clock.now, .101)
        self.assertTrue(fake.closed)
        self.assertFalse(fake.sent)


def binding(case="persistent-write-error"):
    return h.Binding("authored219", case, "raw219", "file219", "filter219",
                     "/authored/disposable.qcow2", "disk219", "serial219", "A219", "D:\\authored219")


class FakeQmp:
    def __init__(self, bound):
        self.binding = bound
        self.selected = bound.file_node
        self.config = None
        self.calls = []
        self.disk_path = bound.disk_path
        self.device = bound.device_id
        self.fail_arm = False

    def __call__(self, command, arguments):
        self.calls.append((command, copy.deepcopy(arguments)))
        b = self.binding
        if command == "query-named-block-nodes":
            nodes = [{"node-name": b.file_node, "drv": "file", "children": [],
                      "image": {"filename": self.disk_path}},
                     {"node-name": b.raw_node, "drv": "raw",
                      "children": [{"node-name": self.selected, "child": "file"}]}]
            if self.config is not None:
                import json
                nodes.append({"node-name": b.filter_node, "drv": "blkdebug",
                              "children": [{"node-name": b.file_node, "child": "image"}],
                              "image": {"filename": "json:" + json.dumps(self.config)}})
            return nodes
        if command == "query-block":
            return [{"qdev": self.device, "inserted": {"node-name": b.raw_node}}]
        if command == "query-blockstats":
            return [{"device": b.device_id, "stats": {"failed_wr_operations": 0}}]
        if command == "qom-get":
            return b.device_serial
        if command == "blockdev-add":
            self.config = copy.deepcopy(arguments)
            return {}
        if command == "blockdev-reopen":
            self.selected = arguments["options"][0]["file"]
            if self.fail_arm and self.selected == b.filter_node:
                raise OSError("authored arm applied but response lost")
            return {}
        raise AssertionError("unmodeled QMP command: " + command)


def outer(stage="prepared", seq=1, bound=None):
    b = bound or binding()
    obs = {"volume_binding": {"device_serial": b.device_serial, "volume_serial": b.volume_serial,
                              "root": b.root, "unit": b.unit, "disk_number": 1,
                              "partition_number": 1, "filesystem": "NTFS", "is_boot": False,
                              "is_system": False, "volume_unique_id": "authored-volume"},
           "volume_binding_file_sha256": "a" * 64,
           "write_probe": {"before": {"bridge_before": {"volume_serial_u32": int(b.volume_serial, 16)}}}}
    nested = None
    worker_kind = {"source_reopened_hold": ("before_operation", "create-root", 3),
                   "before_candidate_hold": ("before_operation", "create-Candidate", 9),
                   "candidate_hold": ("candidate_result", "create-Candidate", 10),
                   "cleared_hold": ("candidate_result", "create-Candidate", 10),
                   "released": ("candidate_result", "create-Candidate", 10),
                   "runtime_result": ("runtime_result", "runtime", 11),
                   "backend_dropped": ("backend_dropped", "backend-drop", 12)}.get(stage)
    if worker_kind:
        kind, worker_stage, worker_seq = worker_kind
        result = None
        if kind == "candidate_result":
            result = {"success": False, "failure": "BackendIo", "native_error_kind": "Other", "native_os_error": 1117}
        elif kind == "runtime_result":
            result = {"status": "FailedBeforePublish", "phase": "CandidateCreated", "failure": "BackendIo",
                      "publication_possible": False, "release_possible": False, "protocol_complete": False,
                      "retained_material": True, "pending_cleanup": False, "charged_bytes": 4194304}
        nested = {"v": 1, "unit": b.unit, "seq": worker_seq, "kind": kind, "stage": worker_stage,
                  "result": result, "bindings": [{"identity": "00", "facts": "ff"}],
                  **{flag: False for flag in h.protocol.FLAGS}}
    if stage == "exited":
        obs = {"exit_confirmed": True, "exit_code": 0}
    return {"v": 1, "unit": b.unit, "case": b.case, "seq": seq,
            "stage": stage, "observation": obs, "worker_event": nested,
            **{flag: False for flag in h.protocol.FLAGS}}


class ControllerTests(unittest.TestCase):
    def make(self, case="persistent-write-error"):
        b = binding(case)
        fake, records = FakeQmp(b), []
        return h.Controller(h.QmpChannel(fake), b, records.append), fake, records

    def test_exact_persistent_whole_volume_rule_and_control_are_serialized(self):
        for case, expected in (("persistent-write-error", [{"event": "write_aio", "iotype": "write",
                                 "errno": 28, "once": False}]), ("no-error", [])):
            with self.subTest(case=case):
                controller, fake, records = self.make(case)
                controller.prepare()
                self.assertEqual(fake.config["inject-error"], expected)
                self.assertTrue(all("sector" not in rule for rule in expected))
                controller.arm()
                self.assertEqual(fake.selected, binding(case).filter_node)
                controller.clear()
                self.assertEqual(fake.selected, binding(case).file_node)
                self.assertEqual(controller.state, "cleared")
                self.assertEqual([r["kind"] for r in records].count("armed"), 1)
                with self.assertRaises(h.HostError):
                    controller.arm()

    def test_wrong_disk_or_device_refuses_before_any_mutation(self):
        for field in ("disk_path", "device"):
            with self.subTest(field=field):
                controller, fake, _ = self.make()
                setattr(fake, field, "foreign")
                with self.assertRaises(h.HostError):
                    controller.prepare()
                self.assertFalse(any(name.startswith("blockdev-") for name, _ in fake.calls))

    def test_wrong_guest_fixture_binding_has_no_ack(self):
        for field in ("device_serial", "volume_serial", "root", "unit"):
            with self.subTest(field=field):
                controller, _, records = self.make()
                controller.prepare()
                value = outer()
                value["observation"]["volume_binding"][field] = "foreign"
                with self.assertRaises(h.HostError):
                    controller.accept(value)
                self.assertFalse(any(r["kind"] == "command-prepared" for r in records))

    def test_ack_is_current_stage_bound_and_never_sent_twice(self):
        controller, _, _ = self.make()
        controller.prepare()
        ack = controller.accept(outer())
        with self.assertRaises(h.HostError):
            controller.sent(ack.replace(b"authored219", b"foreign219"))
        controller.sent(ack)
        with self.assertRaises(h.HostError):
            controller.sent(ack)

    def test_cancel_clears_uncertain_applied_arm_once_and_never_releases(self):
        controller, fake, records = self.make()
        controller.prepare()
        fake.fail_arm = True
        with self.assertRaises(OSError):
            controller.arm()
        self.assertEqual(controller.state, "arm-uncertain")
        controller.cancel("authored transport loss")
        self.assertEqual(controller.state, "refused")
        self.assertEqual(fake.selected, binding().file_node)
        self.assertEqual(sum(name == "blockdev-reopen" for name, _ in fake.calls), 2)
        controller.cancel("duplicate cancellation")
        self.assertEqual(sum(name == "blockdev-reopen" for name, _ in fake.calls), 2)
        self.assertFalse(any(r["kind"] == "command-sent" for r in records))

    def test_resident_epoch_and_code_bind_loaded_state_without_source_read(self):
        with patch.object(Path, "read_bytes", side_effect=AssertionError("disk source is not resident code")):
            first, _, _ = self.make()
            second, _, _ = self.make()
            self.assertNotEqual(first.resident()["controller_epoch"], second.resident()["controller_epoch"])
            self.assertEqual(first.resident()["code_sha256"], second.resident()["code_sha256"])
        with patch.dict(h.RULE, {"once": True}):
            with self.assertRaises(h.HostError):
                first.prepare()

    def test_plan_can_only_bind_once_before_any_effect(self):
        controller, fake, _ = self.make()
        controller.bind_plan("a" * 64)
        self.assertEqual(controller.resident()["plan_sha256"], "a" * 64)
        self.assertEqual(fake.calls, [])
        with self.assertRaises(h.HostError):
            controller.bind_plan("b" * 64)
        controller.prepare()
        with self.assertRaises(h.HostError):
            controller.bind_plan("c" * 64)

    def test_default_epoch_remains_fresh_and_explicit_parent_epoch_is_exact(self):
        first, first_fake, _ = self.make()
        second, second_fake, _ = self.make()
        self.assertRegex(first.controller_epoch, r"^[0-9a-f]{32}$")
        self.assertRegex(second.controller_epoch, r"^[0-9a-f]{32}$")
        self.assertNotEqual(first.controller_epoch, second.controller_epoch)
        self.assertEqual(first_fake.calls, [])
        self.assertEqual(second_fake.calls, [])
        b, records = binding(), []
        fake = FakeQmp(b)
        explicit = "0123456789abcdef0123456789abcdef"
        controller = h.Controller(h.QmpChannel(fake), b, records.append, controller_epoch=explicit)
        self.assertEqual(controller.controller_epoch, explicit)
        self.assertEqual(controller.resident()["controller_epoch"], explicit)
        self.assertEqual(records[0]["controller_epoch"], explicit)
        self.assertEqual(records[0]["value"]["controller_epoch"], explicit)
        self.assertEqual(controller.state, "new")
        self.assertEqual(fake.calls, [])
        self.assertFalse(controller.session.complete)

    def test_invalid_preregistered_epoch_refuses_before_record_or_channel_call(self):
        for epoch in (True, False, 32, 1.5, b"a" * 32, {"controller_epoch": "a" * 32},
                      [], "", "a" * 31, "a" * 33, "A" * 32, "g" * 32, "a" * 31 + "\n"):
            with self.subTest(epoch=repr(epoch)):
                b, records = binding(), []
                fake = FakeQmp(b)
                with self.assertRaises(h.HostError):
                    h.Controller(h.QmpChannel(fake), b, records.append, controller_epoch=epoch)
                self.assertEqual(records, [])
                self.assertEqual(fake.calls, [])

    def test_recording_failure_during_clear_still_restores_once_without_success_claim(self):
        for point in ("before-clear", "pre-query", "restore-result", "post-query", "cleared", "all"):
            with self.subTest(point=point):
                controller, fake, records = self.make()
                controller.prepare()
                controller.arm()
                saved = controller.record
                fired = []
                def record(value):
                    kind, detail = value["kind"], value["value"]
                    selected = fake.selected
                    fail = (point == "all" or point == kind or
                            (kind == "qmp" and (
                                (point == "pre-query" and detail["command"] == "query-named-block-nodes" and selected == binding().filter_node) or
                                (point == "restore-result" and detail["command"] == "blockdev-reopen") or
                                (point == "post-query" and detail["command"] == "query-named-block-nodes" and selected == binding().file_node))))
                    if fail and (not fired or point == "all"):
                        fired.append(kind)
                        raise OSError("authored recorder failure at " + point)
                    saved(value)
                controller.record = record
                before = len(fake.calls)
                with self.assertRaises((h.HostError, OSError)):
                    controller.clear()
                self.assertTrue(fired)
                self.assertEqual(fake.selected, binding().file_node)
                restored = [(name, args) for name, args in fake.calls[before:] if name == "blockdev-reopen"]
                self.assertEqual(len(restored), 1)
                self.assertNotEqual(controller.state, "cleared")
                self.assertFalse(any(r["kind"] == "cleared" for r in records))
                controller.record = saved
                controller.cancel("authored follow-up after partial clear")
                self.assertEqual(sum(name == "blockdev-reopen" for name, _ in fake.calls[before:]), 1)

    def test_cancel_recorder_failure_cannot_prevent_one_actual_restore(self):
        for fail_all in (False, True):
            with self.subTest(fail_all=fail_all):
                controller, fake, records = self.make()
                controller.prepare()
                controller.arm()
                saved = controller.record
                def record(value):
                    if fail_all or value["kind"] == "cancelled":
                        raise OSError("authored unavailable recorder")
                    saved(value)
                controller.record = record
                before = len(fake.calls)
                with self.assertRaises((h.HostError, OSError)):
                    controller.cancel("authored cancel while recording unavailable")
                self.assertEqual(fake.selected, binding().file_node)
                self.assertEqual(controller.state, "refused")
                self.assertEqual(sum(name == "blockdev-reopen" for name, _ in fake.calls[before:]), 1)
                controller.record = saved
                controller.cancel("duplicate cancellation after logging failure")
                self.assertEqual(sum(name == "blockdev-reopen" for name, _ in fake.calls[before:]), 1)


class MailboxTests(unittest.TestCase):
    def make(self):
        bound = binding()
        fake = FakeQmp(bound)
        controller = h.Controller(h.QmpChannel(fake), bound, lambda record: None)
        controller.prepare()
        return controller, fake

    def test_truncated_mailbox_refuses_and_does_not_replay_ack(self):
        controller, _ = self.make()
        raw = h.protocol.encode_event(outer())
        class Mailbox:
            reads = 0
            acks = []
            def read_file(self, path):
                self.reads += 1
                return raw if self.reads == 1 else raw[:-1]
            def append(self, path, ack):
                self.acks.append(ack)
        mailbox = Mailbox()
        with self.assertRaises(h.HostError):
            h.drive_mailbox(controller, mailbox, "events", "commands", sleep=lambda _: None)
        self.assertEqual(len(mailbox.acks), 1)
        self.assertEqual(controller.state, "refused")

    def test_lost_ack_response_is_not_resent_or_marked_sent(self):
        controller, _ = self.make()
        raw = h.protocol.encode_event(outer())
        class Mailbox:
            attempts = 0
            def read_file(self, path):
                return raw
            def append(self, path, ack):
                self.attempts += 1
                raise OSError("authored response lost after possible append")
        mailbox = Mailbox()
        with self.assertRaises(OSError):
            h.drive_mailbox(controller, mailbox, "events", "commands", sleep=lambda _: None)
        self.assertEqual(mailbox.attempts, 1)
        self.assertIsNotNone(controller.session.pending)
        self.assertEqual(controller.state, "refused")

    def test_cancelled_mailbox_clears_armed_filter_without_guest_release(self):
        controller, fake = self.make()
        controller.arm()
        class NoGuestEffects:
            def read_file(self, path):
                raise AssertionError("cancel must precede guest read")
            def append(self, path, ack):
                raise AssertionError("cancel must not send child release")
        with self.assertRaises(h.HostError):
            h.drive_mailbox(controller, NoGuestEffects(), "events", "commands", cancel=lambda: True)
        self.assertEqual(fake.selected, binding().file_node)
        self.assertEqual(controller.state, "refused")

    def test_unterminated_oversized_record_stops_at_bound(self):
        controller, _ = self.make()
        class Mailbox:
            def read_file(self, path):
                return b"x" * (h.protocol.MAX_EVENT_BYTES + 1)
            def append(self, path, ack):
                raise AssertionError("oversized event cannot be acknowledged")
        with self.assertRaises(h.HostError):
            h.drive_mailbox(controller, Mailbox(), "events", "commands")
        self.assertEqual(controller.state, "refused")


class FakeHttpController:
    """Finite authored Session adapter: no emulator, child or marker effects."""
    def __init__(self):
        self.binding = binding()
        self.session = h.protocol.Session(self.binding.unit, self.binding.case)
        self.records, self.sent_commands, self.cancellations = [], [], []

    def _emit(self, kind, value):
        self.records.append((kind, copy.deepcopy(value)))

    def accept(self, value):
        self.session.accept_event(value)
        command = h.protocol.COMMANDS.get(value["stage"])
        return h.protocol.encode_command(value, command) if command else None

    def sent(self, raw):
        self.session.accept_command(raw)
        self.sent_commands.append(raw)

    def cancel(self, reason):
        self.cancellations.append(str(reason))

    def resident(self):
        return {"authored": True}


class HttpEndpointTests(unittest.TestCase):
    def endpoint(self, *, controller=None, assets=None, timeout=5, **kwargs):
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        controller = controller or FakeHttpController()
        endpoint = h.HttpEndpoint(controller, assets or {"/asset.py": b"original-authored-bytes"},
                                  port=port, timeout=timeout, **kwargs)
        self.addCleanup(endpoint.close)
        endpoint.start()
        return endpoint, controller, port

    def request(self, port, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
        try:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            return response.status, response.read()
        finally:
            connection.close()

    def raw_request(self, port, raw):
        with socket.create_connection(("127.0.0.1", port), timeout=2) as connection:
            connection.sendall(raw)
            connection.shutdown(socket.SHUT_WR)
            chunks = []
            while True:
                value = connection.recv(65536)
                if not value:
                    return b"".join(chunks)
                chunks.append(value)

    def test_assets_are_loaded_immutable_bytes_and_routes_are_exact(self):
        assets = {"/asset.py": b"authored-original"}
        endpoint, controller, port = self.endpoint(assets=assets)
        assets["/asset.py"] = b"changed-on-disk-equivalent"
        self.assertEqual(endpoint.server.server_address[0], "127.0.0.1")
        self.assertEqual(self.request(port, "GET", "/asset.py"), (200, b"authored-original"))
        for path in ("/../asset.py", "/asset.py?query=1", "/%61sset.py", "/missing"):
            self.assertEqual(self.request(port, "GET", path)[0], 404)
        self.assertFalse(controller.sent_commands)
        self.assertFalse(controller.cancellations)

    def test_exact_current_event_returns_one_raw_command_after_send(self):
        endpoint, controller, port = self.endpoint()
        value = outer()
        expected = h.protocol.encode_command(value, "start")
        self.assertEqual(self.request(port, "POST", "/event/authored219", h.protocol.encode_event(value)),
                         (200, expected))
        self.assertEqual(controller.sent_commands, [expected])
        kinds = [kind for kind, _ in controller.records]
        self.assertIn("http-request", kinds)
        self.assertIn("http-response", kinds)
        self.assertEqual(self.request(port, "POST", "/event/authored219", h.protocol.encode_event(value))[0], 400)
        self.assertEqual(controller.sent_commands, [expected])
        self.assertTrue(endpoint.stop.is_set())

    def test_whole_authored_exchange_returns_gate_commands_and_notification_bytes(self):
        endpoint, controller, port = self.endpoint()
        expected_commands = []
        for seq, stage in enumerate(h.protocol.STAGES, 1):
            value = outer(stage, seq)
            command = h.protocol.COMMANDS.get(stage)
            expected = h.protocol.encode_command(value, command) if command else b"{}\n"
            if command:
                expected_commands.append(expected)
            self.assertEqual(self.request(port, "POST", "/event/authored219", h.protocol.encode_event(value)),
                             (200, expected))
        self.assertTrue(controller.session.complete)
        self.assertEqual(controller.sent_commands, expected_commands)
        self.assertTrue(endpoint.stop.is_set())

    def test_foreign_current_path_refuses_without_acceptance(self):
        endpoint, controller, port = self.endpoint()
        self.assertEqual(self.request(port, "POST", "/event/foreign", h.protocol.encode_event(outer()))[0], 400)
        self.assertEqual(controller.session.sequence, 0)
        self.assertFalse(controller.sent_commands)
        self.assertTrue(endpoint.stop.is_set())

    def test_forbidden_methods_do_not_run_controller(self):
        _, controller, port = self.endpoint()
        for method in ("PUT", "DELETE", "PATCH", "HEAD", "CONNECT", "OPTIONS"):
            self.assertEqual(self.request(port, method, "/event/authored219")[0], 501)
        self.assertEqual(controller.session.sequence, 0)
        self.assertFalse(controller.sent_commands)

    def test_invalid_asset_allowlists_refuse_before_serving(self):
        for assets in ({"/../escape": b"bytes"}, {"/file?query": b"bytes"},
                       {"/ok": bytearray(b"mutable")}, {"not-absolute": b"bytes"}):
            with self.subTest(assets=list(assets)):
                with self.assertRaises(h.HostError):
                    h.HttpEndpoint(FakeHttpController(), assets, port=12345)

    def test_duplicate_length_and_transfer_encoding_are_not_accepted(self):
        for framing in (b"Content-Length: 1\r\nContent-Length: 1\r\n",
                        b"Content-Length: 1\r\nTransfer-Encoding: chunked\r\n",
                        b"Content-Length: -1\r\n", b"",
                        b"Content-Length: " + str(h.protocol.MAX_EVENT_BYTES + 1).encode() + b"\r\n"):
            with self.subTest(framing=framing):
                endpoint, controller, port = self.endpoint()
                response = self.raw_request(port, b"POST /event/authored219 HTTP/1.1\r\nHost: localhost\r\n" + framing + b"\r\nx")
                self.assertIn(b" 400 ", response.split(b"\r\n")[0])
                self.assertEqual(controller.session.sequence, 0)
                self.assertFalse(controller.sent_commands)
                self.assertTrue(endpoint.stop.is_set())

    def test_truncated_body_refuses_and_does_not_retry(self):
        endpoint, controller, port = self.endpoint()
        response = self.raw_request(port, b"POST /event/authored219 HTTP/1.1\r\nHost: localhost\r\nContent-Length: 10\r\n\r\nx")
        self.assertIn(b" 400 ", response.split(b"\r\n")[0])
        self.assertEqual(controller.session.sequence, 0)
        self.assertFalse(controller.sent_commands)
        self.assertTrue(endpoint.stop.is_set())

    def test_explicit_cancel_refuses_later_event_and_sends_no_command(self):
        endpoint, controller, port = self.endpoint()
        endpoint.cancel("authored operator cancellation")
        self.assertEqual(self.request(port, "POST", "/event/authored219", h.protocol.encode_event(outer()))[0], 400)
        self.assertEqual(controller.session.sequence, 0)
        self.assertFalse(controller.sent_commands)

    def test_idle_absolute_deadline_cancels_without_any_guest_request(self):
        endpoint, controller, _ = self.endpoint(timeout=.05)
        self.assertTrue(endpoint.stop.wait(1))
        self.assertTrue(controller.cancellations)
        with self.assertRaises(h.HostError):
            endpoint.wait()
        self.assertFalse(controller.sent_commands)

    def test_incomplete_body_cannot_hold_current_deadline_or_delay_clear(self):
        bound = binding()
        fake = FakeQmp(bound)
        controller = h.Controller(h.QmpChannel(fake), bound, lambda record: None)
        controller.prepare()
        controller.arm()
        endpoint, _, port = self.endpoint(controller=controller, timeout=.15)
        with socket.create_connection(("127.0.0.1", port), timeout=2) as connection:
            connection.sendall(b"POST /event/authored219 HTTP/1.1\r\nHost: localhost\r\nContent-Length: 100\r\n\r\nx")
            self.assertTrue(endpoint.stop.wait(1.5), "body receive must not defeat current-parent deadline")
        self.assertEqual(fake.selected, bound.file_node)
        self.assertEqual(controller.state, "refused")

    def test_arm_response_lost_at_new_gate_clears_and_does_not_send_armed(self):
        bound = binding()
        fake, records = FakeQmp(bound), []
        controller = h.Controller(h.QmpChannel(fake), bound, records.append)
        controller.prepare()
        _, _, port = self.endpoint(controller=controller)
        for seq, stage in enumerate(("prepared", "source_reopened_hold"), 1):
            self.assertEqual(self.request(port, "POST", "/event/authored219",
                                          h.protocol.encode_event(outer(stage, seq)))[0], 200)
        fake.fail_arm = True
        self.assertEqual(self.request(port, "POST", "/event/authored219",
                                      h.protocol.encode_event(outer("before_candidate_hold", 3)))[0], 400)
        self.assertEqual(controller.state, "refused")
        self.assertEqual(fake.selected, bound.file_node)
        self.assertEqual([r["value"]["command"]["command"] for r in records if r["kind"] == "command-sent"],
                         ["start", "continue"])

    def advance_http(self, port, through="final"):
        for seq, stage in enumerate(h.protocol.STAGES, 1):
            self.assertEqual(self.request(port, "POST", "/event/authored219",
                                          h.protocol.encode_event(outer(stage, seq)))[0], 200)
            if stage == through:
                break

    def export_endpoint(self, **kwargs):
        sink = []
        endpoint, controller, port = self.endpoint(artifacts={"capture.bin": 1024, "optional.bin": 1024},
                                                  artifact_sink=lambda name, data: sink.append((name, data)),
                                                  required_files=("capture.bin",), require_export=True, **kwargs)
        return endpoint, controller, port, sink

    def upload(self, port, data=b"authored-capture", name="capture.bin", sha=None):
        return self.request(port, "POST", "/artifact/authored219/" + name, data,
                            {"X-Imageinfo-Sha256": sha or hashlib.sha256(data).hexdigest()})

    def manifest(self, data=b"authored-capture"):
        return {"schema": "imageinfo-0219-http-export-v1", "exit_confirmed": True,
                "files": [{"name": "capture.bin", "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                           "guest_path": "D:\\authored219\\capture.bin"}],
                "missing": [{"name": "optional.bin", "status": "absent", "error": None,
                             "guest_path": "D:\\authored219\\optional.bin"}]}

    def test_export_requires_confirmed_exit_and_preserves_fixed_bytes_and_missing_denominator(self):
        endpoint, controller, port, sink = self.export_endpoint()
        self.advance_http(port)
        self.assertTrue(endpoint.exit_confirmed)
        self.assertTrue(controller.session.complete)
        self.assertFalse(endpoint.stop.is_set())
        self.assertEqual(self.upload(port), (200, b"{}\n"))
        self.assertEqual(sink, [("capture.bin", b"authored-capture")])
        self.assertEqual(self.request(port, "POST", "/export-complete/authored219", json.dumps(self.manifest()).encode()),
                         (200, b"{}\n"))
        self.assertTrue(endpoint.export_complete)
        self.assertEqual(endpoint.wait(), {"authored": True})

    def test_artifact_before_exit_refuses_without_sink_effect(self):
        endpoint, _, port, sink = self.export_endpoint()
        self.assertEqual(self.upload(port)[0], 400)
        self.assertEqual(sink, [])
        self.assertTrue(endpoint.stop.is_set())

    def test_artifact_unknown_name_oversize_or_bad_hash_refuses(self):
        for options in ({"name": "../capture.bin"}, {"data": b"x" * 1025}, {"sha": "0" * 64}):
            with self.subTest(options=list(options)):
                endpoint, _, port, sink = self.export_endpoint()
                self.advance_http(port)
                self.assertEqual(self.upload(port, **options)[0], 400)
                self.assertEqual(sink, [])
                self.assertTrue(endpoint.stop.is_set())

    def test_duplicate_upload_is_not_replayed_to_sink(self):
        endpoint, _, port, sink = self.export_endpoint()
        self.advance_http(port)
        self.assertEqual(self.upload(port)[0], 200)
        self.assertEqual(self.upload(port)[0], 400)
        self.assertEqual(len(sink), 1)
        self.assertTrue(endpoint.stop.is_set())

    def test_partial_sink_failure_retains_failure_without_retry(self):
        effects = []
        def fail(name, data):
            effects.append((name, data[:2]))
            raise OSError("authored partial exclusive destination write")
        endpoint, _, port = self.endpoint(artifacts={"capture.bin": 1024}, artifact_sink=fail,
                                          required_files=("capture.bin",), require_export=True)
        self.advance_http(port)
        self.assertEqual(self.upload(port)[0], 400)
        self.assertEqual(effects, [("capture.bin", b"au")])
        self.assertFalse(endpoint.uploaded)
        self.assertTrue(endpoint.stop.is_set())

    def test_export_missing_required_or_wrong_hash_denominator_refuses(self):
        for change in ("required-missing", "wrong-hash", "duplicate-name", "missing-denominator"):
            with self.subTest(change=change):
                endpoint, _, port, _ = self.export_endpoint()
                self.advance_http(port)
                manifest = self.manifest()
                if change == "required-missing":
                    manifest["files"] = []
                    manifest["missing"].append({"name": "capture.bin", "status": "absent", "error": None,
                                                "guest_path": "D:\\authored219\\capture.bin"})
                else:
                    self.assertEqual(self.upload(port)[0], 200)
                    if change == "wrong-hash":
                        manifest["files"][0]["sha256"] = "0" * 64
                    elif change == "duplicate-name":
                        manifest["missing"][0]["name"] = "capture.bin"
                    else:
                        manifest["missing"] = []
                self.assertEqual(self.request(port, "POST", "/export-complete/authored219", json.dumps(manifest).encode())[0], 400)
                self.assertFalse(endpoint.export_complete)
                self.assertTrue(endpoint.stop.is_set())

    def test_confirmed_exit_failure_can_export_retained_attempt_but_never_complete_cell(self):
        bound = binding()
        fake, records, sink = FakeQmp(bound), [], []
        controller = h.Controller(h.QmpChannel(fake), bound, records.append)
        controller.prepare()
        controller.arm()
        endpoint, _, port = self.endpoint(controller=controller, artifacts={"capture.bin": 1024, "optional.bin": 1024},
                                          artifact_sink=lambda name, data: sink.append((name, data)),
                                          required_files=("capture.bin",), require_export=True)
        event = outer("failure")
        event["observation"] = {"exit_confirmed": True, "exit_code": 1, "error": "authored child failure"}
        self.assertEqual(self.request(port, "POST", "/event/authored219", h.protocol.encode_event(event)), (200, b"{}\n"))
        self.assertEqual(fake.selected, bound.file_node)
        self.assertFalse(controller.session.complete)
        self.assertFalse(endpoint.stop.is_set())
        self.assertEqual(self.upload(port)[0], 200)
        self.assertEqual(self.request(port, "POST", "/export-complete/authored219", json.dumps(self.manifest()).encode())[0], 200)
        self.assertEqual(sink, [("capture.bin", b"authored-capture")])
        with self.assertRaises(h.HostError):
            endpoint.wait()

    def test_failure_without_confirmed_exit_does_not_permit_artifact_postwork(self):
        endpoint, _, port, sink = self.export_endpoint()
        event = outer("failure")
        event["observation"] = {"exit_confirmed": False, "error": "authored child stop uncertain"}
        self.assertEqual(self.request(port, "POST", "/event/authored219", h.protocol.encode_event(event))[0], 200)
        self.assertTrue(endpoint.stop.is_set())
        self.assertEqual(self.upload(port)[0], 400)
        self.assertEqual(sink, [])


if __name__ == "__main__":
    unittest.main()
