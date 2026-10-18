"""One explicitly owned #0219 guest attempt; no import-time native effects.

The unchanged #0218 runner owns the actual worker pipes.  This adapter pauses
that owner for bounded, current-parent commands.  Mailboxes are transport only:
their contents cannot confer imported custody, replay or storage admission.
"""
from __future__ import annotations

import argparse
import hashlib
import http.client
import importlib.util
import json
import os
from pathlib import Path
import queue
import marshal
import re
import stat
import sys
import threading
import time
from types import SimpleNamespace
from types import CodeType, FunctionType
from urllib.parse import urlsplit


HERE = Path(__file__).absolute().parent
FLAGS = ("committed", "production_profile_admitted", "raw_admitted", "authority_importable")
EXPORT_NAMES = frozenset(("source.bin", "old-source.bin", "candidate.bin", "output.bin",
                          "prepared.record", "intent.record", "observation.record", "receipt.record",
                          "stdout.bin", "stderr.bin", "events.jsonl", "transcript.jsonl",
                          "result.json", "guest-transcript.jsonl", "guest.json", "volume-binding.json"))
REQUIRED_EXPORT_NAMES = frozenset(("stdout.bin", "stderr.bin", "events.jsonl", "transcript.jsonl",
                                  "result.json", "guest-transcript.jsonl", "guest.json", "volume-binding.json"))
GUEST_TEST_NAME = "storage::namespace_guest_diagnostic::guest_namespace_diagnostic_worker"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_observer218():
    """Load frozen sibling modules under private names, without native calls."""
    directory = HERE.parent / "0218-namespace-observer"
    protocol = _load("_collector219_worker_protocol", directory / "protocol.py")
    previous = sys.modules.get("protocol")
    try:
        sys.modules["protocol"] = protocol
        controller = _load("_collector219_worker_controller", directory / "controller.py")
    finally:
        if previous is None:
            sys.modules.pop("protocol", None)
        else:
            sys.modules["protocol"] = previous
    return SimpleNamespace(protocol=protocol, controller=controller,
                           run=_load("_collector219_worker_run", directory / "run.py"),
                           probe=_load("_collector219_worker_probe", directory / "probe.py"))


def _loaded_code_hash(observer):
    """Hash resident Python code, retaining disk hashes as a separate fact."""
    digest = hashlib.sha256()
    def normalized(code):
        return code.replace(co_filename="<reviewed-resident>", co_consts=tuple(
            normalized(value) if isinstance(value, CodeType) else value
            for value in code.co_consts))
    for label, module in sorted({"collector": sys.modules[__name__],
                                "worker_run": observer.run,
                                "worker_controller": observer.controller,
                                "worker_protocol": observer.protocol,
                                "worker_probe": observer.probe}.items()):
        for name, value in sorted(vars(module).items()):
            values = vars(value).items() if isinstance(value, type) else (("", value),)
            for member, function in sorted(values):
                if isinstance(function, (staticmethod, classmethod)):
                    function = function.__func__
                if (isinstance(function, FunctionType)
                        and function.__module__ == getattr(module, "__name__", None)):
                    digest.update((label + "." + name + "." + member + "\0").encode())
                    digest.update(marshal.dumps(normalized(function.__code__)))
    return digest.hexdigest()


def observer_runtime(observer=None):
    observer = observer or load_observer218()
    return {"implementation": sys.implementation.name, "version": sys.version,
            "platform": sys.platform, "stat_profile": observer.probe._stat_profile(),
            "code_sha256": _loaded_code_hash(observer)}


def _new_json(path, value):
    with Path(path).open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def _sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_request(request):
    """Check exact declared bytes/runtime, not a persisted execution approval."""
    pins = request.get("reviewed_files")
    if type(pins) is not dict or not pins:
        raise ValueError("reviewed file pins required")
    sibling = HERE.parent / "0218-namespace-observer"
    required = {str(Path(sys.executable).absolute()), str(Path(__file__).absolute()),
                str(HERE / "protocol.py"), str(HERE / "fixtures.py"),
                *(str(sibling / name) for name in
                  ("run.py", "controller.py", "protocol.py", "probe.py"))}
    if not required.issubset(pins):
        raise ValueError("runtime and collector source pins required")
    for path, expected in pins.items():
        if (not Path(path).is_absolute() or type(expected) is not str
                or re.fullmatch(r"[0-9a-f]{64}", expected) is None
                or _sha(path) != expected):
            raise ValueError("reviewed file changed")
    if request["argv"][0] not in pins:
        raise ValueError("worker executable pin required")
    if observer_runtime() != request.get("observer_python"):
        raise ValueError("observer runtime differs from request")


class MailboxChannel:
    """Fresh event file and retained, initially empty append-only command FD.

    An EOF is a temporary lack of data, never a release.  Replacement,
    truncation, overflow or a lost parent expires the current attempt.
    """
    def __init__(self, event_file, command_file, *, command_bytes=1024,
                 max_commands=8):
        self.event_path, self.command_path = Path(event_file), Path(command_file)
        if (not self.event_path.is_absolute() or not self.command_path.is_absolute()
                or self.event_path == self.command_path):
            raise ValueError("distinct absolute mailbox paths required")
        self.limit, self.maximum = command_bytes, max_commands
        self.count = self.total = 0
        self.pending = bytearray()
        self.commands = self.command_path.open("rb", buffering=0)
        self.identity = os.fstat(self.commands.fileno())
        if self.identity.st_size or self.command_path.is_symlink():
            self.commands.close()
            raise ValueError("fresh empty command mailbox required")
        try:
            self.events = self.event_path.open("xb", buffering=0)
        except BaseException:
            self.commands.close()
            raise

    def notify(self, event, encoded, deadline):
        if time.monotonic() >= deadline:
            raise TimeoutError("parent_deadline")
        if self.events.write(encoded) != len(encoded):
            raise OSError("parent_event_short_write")
        self.events.flush()
        if time.monotonic() >= deadline:
            raise TimeoutError("parent_deadline")

    def exchange(self, event, encoded, deadline):
        self.notify(event, encoded, deadline)
        while time.monotonic() < deadline:
            info = self.command_path.lstat()
            if (self.command_path.is_symlink()
                    or (info.st_dev, info.st_ino) != (self.identity.st_dev, self.identity.st_ino)
                    or info.st_size < self.total or info.st_size > self.limit * self.maximum):
                raise ValueError("command_mailbox_changed_or_overflow")
            block = self.commands.read(self.limit + 1)
            if block:
                self.total += len(block)
                self.pending.extend(block)
                # More than one queued line is an unsolicited/duplicate command.
                if self.pending.count(b"\n") > 1:
                    raise ValueError("unsolicited_command_batch")
                if b"\n" in self.pending:
                    line, _, rest = self.pending.partition(b"\n")
                    self.pending = bytearray(rest)
                    self.count += 1
                    if self.pending or len(line) + 1 > self.limit or self.count > self.maximum:
                        raise ValueError("parent_command_bound")
                    return bytes(line) + b"\n"
                if len(self.pending) >= self.limit:
                    raise ValueError("parent_command_line_bound")
            time.sleep(0.01)
        raise TimeoutError("parent_deadline")

    def close(self):
        self.commands.close()
        self.events.close()


class HttpChannel:
    """Single-attempt private NAT bridge, with no redirects or retries."""
    def __init__(self, endpoint, *, connection_factory=None):
        parsed = urlsplit(endpoint)
        try:
            port = parsed.port
        except ValueError as exc:
            raise ValueError("invalid parent endpoint port") from exc
        if (parsed.scheme != "http" or parsed.hostname != "10.0.2.2"
                or port is None or not 1024 <= port <= 65535
                or parsed.username is not None or parsed.password is not None
                or parsed.query or parsed.fragment
                or re.fullmatch(r"/event/[A-Za-z0-9_-]{1,64}", parsed.path) is None):
            raise ValueError("exact private NAT unit endpoint required")
        self.port, self.path = port, parsed.path
        self.unit = parsed.path.rsplit("/", 1)[1]
        self.factory = connection_factory or http.client.HTTPConnection
        self.operations = []
        self.threads = []
        self.poisoned = False

    def _request(self, event, encoded, deadline, *, path=None, body_limit=262144):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("parent_deadline")
        if self.poisoned:
            raise RuntimeError("parent_http_attempt_poisoned")
        if event.get("unit") != self.unit or len(encoded) > body_limit:
            raise ValueError("parent_endpoint_unit_or_body_mismatch")
        connection = self.factory("10.0.2.2", self.port, timeout=remaining)
        try:
            connection.request("POST", self.path if path is None else path, body=encoded,
                               headers={"Content-Type": "application/x-ndjson",
                                        "Content-Length": str(len(encoded)),
                                        "X-Imageinfo-Sha256": hashlib.sha256(encoded).hexdigest(),
                                        "Connection": "close"})
            response = connection.getresponse()
            length = response.getheader("Content-Length")
            if (response.status != 200 or response.getheader("Transfer-Encoding") is not None
                    or length is None or re.fullmatch(r"[0-9]{1,4}", length) is None
                    or not 0 < int(length) <= 1024):
                raise ValueError("parent_http_response_refused")
            raw = response.read(int(length) + 1)
            if len(raw) != int(length):
                raise ValueError("parent_http_response_length")
            if time.monotonic() >= deadline:
                raise TimeoutError("parent_deadline")
            return raw
        finally:
            connection.close()

    def _post(self, event, encoded, deadline, *, path=None, body_limit=262144):
        """Bound the complete callback, including trickled HTTP responses.

        A timed-out daemon may still hold its HTTP connection. Its eventual
        response is discarded and cannot release a child. Preserve that
        uncertainty rather than waiting beyond the owned-child deadline.
        """
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("parent_deadline")
        if self.poisoned:
            raise RuntimeError("parent_http_attempt_poisoned")
        if len(self.operations) >= 32:
            raise ValueError("parent_http_operation_bound")
        outcome = queue.Queue(maxsize=1)
        state = {"stage": event.get("stage"), "completed": False,
                 "timed_out": False, "aborted": False}
        self.operations.append(state)
        def work():
            try:
                value = (self._request(event, encoded, deadline) if path is None else
                         self._request(event, encoded, deadline, path=path, body_limit=body_limit))
                result = (True, value)
            except BaseException as exc:
                result = (False, exc)
            # Publish completion only after _request's connection-close finally.
            state["completed"] = True
            outcome.put(result)
        thread = threading.Thread(target=work, daemon=True)
        self.threads.append(thread)
        try:
            thread.start()
            success, value = outcome.get(timeout=max(0, deadline - time.monotonic()))
            thread.join(timeout=max(0, deadline - time.monotonic()))
            if thread.is_alive():
                raise TimeoutError("parent_deadline_http_thread_uncertain")
        except queue.Empty as exc:
            state["timed_out"] = True
            self.poisoned = True
            raise TimeoutError("parent_deadline_http_outcome_uncertain") from exc
        except BaseException:
            state["aborted"] = True
            self.poisoned = True
            raise
        if time.monotonic() >= deadline:
            state["timed_out"] = True
            self.poisoned = True
            raise TimeoutError("parent_deadline")
        if not success:
            raise value
        return value

    def transport_state(self):
        return {"operations": [dict(state) for state in self.operations],
                "retained_threads": sum(thread.is_alive() for thread in self.threads),
                "poisoned": self.poisoned,
                "replayed": False}

    def exchange(self, event, encoded, deadline):
        return self._post(event, encoded, deadline)

    def notify(self, event, encoded, deadline):
        if self._post(event, encoded, deadline) != b"{}\n":
            raise ValueError("parent_http_notification_ack")

    def close(self):
        pass


    def upload(self, name, content, deadline):
        if name not in EXPORT_NAMES or type(content) is not bytes or len(content) > 16 * 1024 * 1024:
            raise ValueError("fixed bounded export artifact required")
        raw = self._post({"unit": self.unit, "stage": "export-" + name}, content, deadline,
                         path="/artifact/" + self.unit + "/" + name, body_limit=16 * 1024 * 1024)
        if raw != b"{}\n":
            raise ValueError("parent_http_artifact_ack")

    def export_complete(self, manifest, deadline):
        body = (json.dumps(manifest, sort_keys=True, allow_nan=False) + "\n").encode()
        if len(body) > 65536:
            raise ValueError("export manifest bound")
        raw = self._post({"unit": self.unit, "stage": "export-complete"}, body, deadline,
                         path="/export-complete/" + self.unit, body_limit=65536)
        if raw != b"{}\n":
            raise ValueError("parent_http_export_ack")


def export_closed(request, fixture, attempt, channel, *, exit_confirmed):
    """Export only fixed names after confirmed exit; all failures remain local."""
    if exit_confirmed is not True:
        raise ValueError("artifact export requires actual confirmed child exit")
    if not hasattr(channel, "upload") or not hasattr(channel, "export_complete"):
        raise ValueError("reviewed export channel required")
    root = Path(fixture["root"])
    paths = {name: root / "unit" / name for name in
             ("candidate.bin", "output.bin", "prepared.record", "intent.record",
              "observation.record", "receipt.record")}
    paths.update({name: Path(attempt) / name for name in
                  ("stdout.bin", "stderr.bin", "events.jsonl", "transcript.jsonl",
                   "result.json", "guest-transcript.jsonl", "guest.json")})
    paths.update({"source.bin": Path(fixture["source"]),
                  "old-source.bin": Path(fixture.get("old", root.parent / "source.bin")),
                  "volume-binding.json": Path(request["volume_binding_path"])})
    manifest = {"schema": "imageinfo-0219-http-export-v1", "exit_confirmed": True,
                "files": [], "missing": []}
    deadline = time.monotonic() + 120
    total = 0
    for name in sorted(EXPORT_NAMES):
        path = paths[name]
        limit = 16 * 1024 * 1024 if name.endswith(".bin") else 4 * 1024 * 1024
        try:
            if time.monotonic() >= deadline:
                raise TimeoutError("export_deadline")
            info = path.lstat()
            if (not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode)
                    or getattr(info, "st_file_attributes", 0) & 0x400 or info.st_size > limit):
                raise ValueError("export_not_bounded_plain_file")
            with path.open("rb") as handle:
                content = handle.read(limit + 1)
            if len(content) > limit or total + len(content) > 64 * 1024 * 1024:
                raise ValueError("export_logical_byte_bound")
        except (OSError, ValueError) as exc:
            manifest["missing"].append({"name": name, "guest_path": str(path),
                                        "status": "absent" if isinstance(exc, FileNotFoundError) else "error",
                                        "error": {"type": type(exc).__name__, "errno": getattr(exc, "errno", None),
                                                  "winerror": getattr(exc, "winerror", None)}})
            if name in REQUIRED_EXPORT_NAMES:
                raise RuntimeError("required_export_capture_unavailable_" + name) from exc
            continue
        total += len(content)
        channel.upload(name, content, min(deadline, time.monotonic() + 10))
        manifest["files"].append({"name": name, "bytes": len(content),
                                   "sha256": hashlib.sha256(content).hexdigest(), "guest_path": str(path)})
    channel.export_complete(manifest, min(deadline, time.monotonic() + 10))
    return manifest


def execute_collected(request, *, parent_channel, observer=None, fixture_api=None,
                      verify=None):
    """Run exactly once; injections are authored-test seams, not wire options.

    The caller owns this invocation now.  A request and its hashes describe
    bytes; neither grants future authority.  Every failed child attempt stays.
    """
    outer = _load("_collector219_protocol", HERE / "protocol.py")
    observer = observer or load_observer218()
    fixture_api = fixture_api or _load("_collector219_fixtures", HERE / "fixtures.py")
    verify = verify or verify_request
    attempt = Path(request["attempt_dir"])
    if attempt.exists():
        raise FileExistsError(attempt)
    summary = {"schema": "imageinfo-0219-guest-v1", "unit": request["unit"],
               "case": request["case"], "bindings": request.get("bindings", {}),
               "observer_python": observer_runtime(observer), "observations": [],
               "request": request,
               "protocol_complete": False, "replayed": False,
               **{flag: False for flag in FLAGS}}
    try:
        bounds = observer.run.Bounds(**request.get("bounds", {}))
        bounds.validate()
        gate_seconds = request.get("parent_gate_seconds", 4.0)
        if (type(gate_seconds) not in (int, float) or not 0 < gate_seconds <= 5):
            raise ValueError("parent gate bound outside 0..5 seconds")
        session = outer.Session(request["unit"], request["case"])
        worker_name = request.get("worker_test_name", observer.run.TEST_NAME)
        if worker_name not in (observer.run.TEST_NAME, GUEST_TEST_NAME):
            raise ValueError("undeclared native worker entry")
        # Validate identity/case before any preparation effects.
        outer.encode_event({"v": 1, "unit": request["unit"], "case": request["case"],
                            "seq": 1, "stage": "prepared", "observation": {"validation": True},
                            "worker_event": None, **{flag: False for flag in FLAGS}})
        verify(request)
        fixture = fixture_api.prepare_fixture(request["fixture_root"], request["case"],
                                              unit=request["unit"])
    except (Exception, KeyboardInterrupt) as exc:
        attempt.mkdir(parents=False, exist_ok=False)
        summary.update(status="failed", reason=str(exc)[:512],
                       exception_type=type(exc).__name__, child_started=False)
        if hasattr(parent_channel, "transport_state"):
            summary["parent_transport"] = parent_channel.transport_state()
        _new_json(attempt / "guest.json", summary)
        return {"transport": None, "guest": summary}
    summary["fixture"] = fixture
    stream = observer.protocol.EventStream(unit=request["unit"])
    machine = observer.controller.Controller(unit=request["unit"])
    recorder = None
    transcript = None
    number = 0
    started = time.monotonic()
    deadline = started + bounds.deadline_seconds
    pending = None
    candidate = None
    exited = None

    def note(kind, value):
        nonlocal number
        number += 1
        transcript.write(json.dumps({"seq": number, "kind": kind,
                                    "elapsed_ns": int((time.monotonic() - started) * 1e9),
                                    "value": value}, sort_keys=True, allow_nan=False) + "\n")
        transcript.flush()
        if recorder is not None:
            recorder("guest_" + kind, value)

    def emit(stage, observation, worker=None, gate=False):
        event = session.emit(stage, observation, worker)
        raw = outer.encode_event(event)
        note("event", {"bytes_hex": raw.hex()})
        parent_deadline = min(deadline, time.monotonic() + gate_seconds)
        if gate:
            command = parent_channel.exchange(event, raw, parent_deadline)
            note("command_received", {"bytes_hex": command.hex()})
            accepted = session.accept_command(command)
            if accepted["command"] == "cancel":
                raise RuntimeError("current_parent_cancelled")
        else:
            parent_channel.notify(event, raw, parent_deadline)
        return event

    def observe(phase, access):
        note("observation_begin", {"phase": phase})
        snapshot = fixture_api.snapshot_fixture(fixture, phase,
                                               read_snapshot=observer.probe.read_snapshot)
        value = observer.probe.write_open_probe(fixture["source"], expected_access=access,
                                                max_bytes=16 * 1024 * 1024)
        observation = {"phase": phase, "snapshot": snapshot, "write_probe": value}
        summary["observations"].append(observation)
        note("observation_end", observation)
        # A missing/refused pathname after arming is the observation sought by
        # this contrast. Preserve its raw error and continue to the clear gate.
        if phase == "prepared" and not value.get("expectation_met"):
            raise RuntimeError("source_probe_expectation_" + phase)
        return observation

    def ready(record):
        nonlocal recorder, transcript
        recorder = record
        transcript = (attempt / "guest-transcript.jsonl").open("x", encoding="utf-8")
        verify(request)
        baseline = dict(observe("prepared", True))
        resident = {**observer_runtime(observer),
                    "files": {path: _sha(path) for path in request.get("reviewed_files", {})}}
        summary["resident_guest"] = resident
        baseline["bindings"] = summary["bindings"]
        baseline["observer_python"] = summary["observer_python"]
        baseline["resident_guest"] = resident
        if request.get("volume_binding_path") is not None:
            selected = Path(request["volume_binding_path"])
            if not selected.is_absolute() or selected.stat().st_size > 65536:
                raise ValueError("bounded absolute bootstrap volume observation required")
            captured = json.loads(selected.read_bytes())
            if (type(captured) is not dict or captured.get("unit") != request["unit"]
                    or captured.get("root") != str(request["fixture_root"])):
                raise ValueError("bootstrap volume observation root/unit mismatch")
            baseline["volume_binding"] = captured
            baseline["volume_binding_file_sha256"] = _sha(selected)
            if worker_name == GUEST_TEST_NAME:
                drive = captured.get("drive_root")
                if type(drive) is not str or re.fullmatch(r"[A-Za-z]:\\", drive) is None:
                    raise ValueError("actual bootstrap drive binding required")
                environment.update(IMAGEINFO_219_ROOT=str(request["fixture_root"]),
                                   IMAGEINFO_219_UNIT=request["unit"],
                                   IMAGEINFO_219_GUEST_APPROVAL="explicit-parent-disposable-guest-v1",
                                   IMAGEINFO_219_GUEST_DRIVE=drive[:2])
        elif worker_name == GUEST_TEST_NAME:
            raise ValueError("guest entry requires actual bootstrap volume observation")
        emit("prepared", baseline, gate=True)

    def after_exit(record):
        nonlocal recorder, exited
        recorder = record
        # #0218 invokes this callback only after actual owned-child exit.
        exited = observe("exited", True)

    def line(raw):
        nonlocal pending, candidate
        prefix = ("test " + worker_name + " ... ").encode("ascii")
        if raw.startswith(prefix + observer.protocol.PREFIX):
            raw = raw[len(prefix):]
        if not raw.startswith(observer.protocol.PREFIX):
            if raw in (b"\n", b"running 1 test\n", b"ok\n", prefix + b"\n") or re.fullmatch(
                    rb"test result: ok\. 1 passed; 0 failed; 0 ignored; 0 measured; [0-9]+ filtered out; finished in [0-9.]+s\n", raw):
                note("harness_line", {"bytes_hex": raw.hex()})
                return None
            raise ValueError("unexpected libtest stdout")
        event = stream.accept(raw)
        action = machine.accept(event)
        note("worker_event", event)
        if action.kind == "observe_before":
            if event["stage"] == "create-root":
                emit("source_reopened_hold", observe("source_reopened_hold", False), event, True)
            elif event["stage"] == "create-Candidate":
                emit("before_candidate_hold", observe("before_candidate_hold", False), event, True)
        elif action.kind == "observe_held":
            candidate = event
            emit("candidate_hold", observe("candidate_hold", False), event, True)
            emit("cleared_hold", observe("cleared_hold", False), event, True)
        elif event["kind"] in ("runtime_result", "backend_dropped"):
            emit(event["kind"], {"worker_event_retained": True}, event)
        if action.kind not in ("observe_before", "observe_held"):
            return None
        command = machine.acknowledge_observation(event["seq"], event["stage"])
        pending = (event["seq"], event["stage"], command.command)
        recorder("observation_acknowledged", {"event_seq": event["seq"],
                                               "command": command.command})
        return observer.protocol.encode_command(event, command.command)

    def sent(raw):
        nonlocal pending
        if pending is None:
            raise ValueError("child command without pending gate")
        machine.command_sent(*pending)
        note("worker_command_sent", {"bytes_hex": raw.hex()})
        if pending[2] == "release":
            emit("released", {"child_release_write_flush_confirmed": True}, candidate)
        pending = None

    environment = dict(os.environ)
    environment.update(IMAGEINFO_218_ROOT=str(request["fixture_root"]),
                       IMAGEINFO_218_UNIT=request["unit"])
    result = observer.run.execute_owned(request["argv"], attempt, bounds, line,
                                       cwd=request.get("cwd"), env=environment,
                                       on_ready=ready, after_exit=after_exit, command_sent=sent)
    recorder = None  # The retained #0218 transcript is closed after this call.
    summary["transport"] = result
    if hasattr(parent_channel, "transport_state"):
        summary["parent_transport"] = parent_channel.transport_state()
    summary["child_started"] = result["child_pid"] is not None
    try:
        if result["status"] != "transport_complete":
            raise RuntimeError(result["reason"])
        machine.eof()
        machine.mark_exit(result["exit_code"])
        if exited is None:
            raise RuntimeError("confirmed_exit_observation_missing")
        emit("exited", {"exit_confirmed": result["exit_confirmed"],
                        "exit_code": result["exit_code"], "observation": exited})
        final = fixture_api.snapshot_fixture(fixture, "final",
                                             read_snapshot=observer.probe.read_snapshot)
        summary["final_snapshot"] = final
        emit("final", {"snapshot": final, "protocol_complete": machine.complete})
        summary.update(status="transport_complete", protocol_complete=machine.complete and session.complete)
    except (Exception, KeyboardInterrupt) as exc:
        summary.update(status="failed", reason=str(exc)[:512], exception_type=type(exc).__name__)
        if transcript is not None and not session.complete:
            failure = session.fail({"reason": summary["reason"],
                                    "exit_confirmed": result["exit_confirmed"],
                                    "exit_code": result["exit_code"]})
            raw = outer.encode_event(failure)
            note("event", {"bytes_hex": raw.hex()})
            try:
                parent_channel.notify(failure, raw, time.monotonic() + gate_seconds)
            except (Exception, KeyboardInterrupt) as notify_error:
                note("failure_notify_failed", {"exception_type": type(notify_error).__name__})
    finally:
        if transcript is not None:
            transcript.close()
        if hasattr(parent_channel, "transport_state"):
            summary["parent_transport"] = parent_channel.transport_state()
    _new_json(attempt / "guest.json", summary)
    answer = {"transport": result, "guest": summary}
    if request.get("require_export") is True:
        export_result = {"schema": "imageinfo-0219-export-result-v1", "complete": False,
                         "replayed": False}
        try:
            export_result["manifest"] = export_closed(request, fixture, attempt, parent_channel,
                                                       exit_confirmed=result["exit_confirmed"])
            export_result["complete"] = True
        except (Exception, KeyboardInterrupt) as exc:
            export_result.update(reason=str(exc)[:512], exception_type=type(exc).__name__)
        if hasattr(parent_channel, "transport_state"):
            export_result["parent_transport"] = parent_channel.transport_state()
        _new_json(attempt / "export.json", export_result)
        answer["export"] = export_result
    return answer


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True)
    parser.add_argument("--current-owning-parent", action="store_true", required=True)
    parser.add_argument("--event-file")
    parser.add_argument("--command-file")
    parser.add_argument("--endpoint")
    options = parser.parse_args(argv)
    path = Path(options.request)
    if not path.is_absolute() or path.stat().st_size > 262144:
        raise ValueError("bounded absolute current-parent request required")
    request = json.loads(path.read_bytes())
    if options.endpoint:
        if options.event_file or options.command_file:
            raise ValueError("one explicit parent transport required")
        channel = HttpChannel(options.endpoint)
    else:
        if not options.event_file or not options.command_file:
            raise ValueError("paired mailbox paths required")
        channel = MailboxChannel(options.event_file, options.command_file)
    try:
        result = execute_collected(request, parent_channel=channel)
    finally:
        channel.close()
    return 0 if (result["guest"]["protocol_complete"] and
                 (not request.get("require_export") or result.get("export", {}).get("complete"))) else 1


if __name__ == "__main__":
    raise SystemExit(main())
