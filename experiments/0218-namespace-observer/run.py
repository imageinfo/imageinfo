"""Bounded direct-stdio owner for the #0218 diagnostic child.

This module has no import-time effects. It never retries, removes an attempt,
or interprets an exit-zero child as observation qualification.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading
import time
from typing import Callable


@dataclass(frozen=True)
class Bounds:
    deadline_seconds: float = 30.0
    stdout_bytes: int = 1048576
    stderr_bytes: int = 65536
    line_bytes: int = 32768
    events: int = 256
    command_bytes: int = 4096
    commands: int = 128

    def validate(self):
        if not 0 < self.deadline_seconds <= 120:
            raise ValueError("deadline outside diagnostic ceiling")
        for name in ("stdout_bytes", "stderr_bytes"):
            if not 0 < getattr(self, name) <= 4194304:
                raise ValueError("capture outside diagnostic ceiling")
        if not 0 < self.line_bytes <= 32768 or not 0 < self.command_bytes <= 4096:
            raise ValueError("line/command outside diagnostic ceiling")
        if not 0 < self.events <= 256 or not 0 < self.commands <= 128:
            raise ValueError("event/command count outside diagnostic ceiling")


def _json_line(handle, value):
    handle.write(json.dumps(value, sort_keys=True, allow_nan=False) + "\n")
    handle.flush()


def execute_owned(command: list[str], attempt_dir, bounds: Bounds,
                  on_line: Callable[[bytes], bytes | None], *,
                  request: bytes | None = None, cwd=None,
                  env=None,
                  command_sent: Callable[[bytes], None] | None = None,
                  on_ready: Callable | None = None,
                  after_exit: Callable | None = None) -> dict:
    """Run one owned child; on_line returns the explicit next command or None.

    on_line and command_sent are trusted, quick in-process code. Their runtime
    is charged to the deadline but Python cannot preempt them. Fake-child tests
    exercise this seam; native callers must use the reviewed protocol adapter.
    Captures are logical byte limits, not OS resource or descendant containment.
    """
    bounds.validate()
    if not command or any(not isinstance(x, str) or not x for x in command):
        raise ValueError("explicit nonempty argv required")
    attempt = Path(attempt_dir)
    attempt.mkdir(parents=False, exist_ok=False)
    start = time.monotonic()
    deadline = start + bounds.deadline_seconds
    result = {"schema": "namespace-observer-run-v1", "command": command,
              "bounds": asdict(bounds), "status": "failed", "reason": "not_started",
              "exit_code": None, "lines": 0, "commands": 0,
              "stdout_bytes": 0, "stderr_bytes": 0,
              "child_killed": False, "child_pid": None, "exit_confirmed": False,
              "cleanup_errors": [], "capture_drain_complete": False,
              "replayed": False}
    incoming = queue.Queue(maxsize=16)
    outgoing = queue.Queue(maxsize=1)
    failures = queue.Queue(maxsize=8)
    stop = threading.Event()
    threads = []
    child = None

    def fail(reason):
        try:
            failures.put_nowait(reason)
        except queue.Full:
            pass

    def enqueue(item):
        while not stop.is_set():
            try:
                incoming.put(item, timeout=0.02)
                return
            except queue.Full:
                pass

    def capture(pipe, name, limit, handle):
        total = 0
        pending = bytearray()
        try:
            while not stop.is_set():
                data = pipe.read(1024)
                if not data:
                    if name == "stdout":
                        if pending:
                            fail("stdout_unterminated_line")
                        enqueue(("eof", None))
                    return
                kept = data[:max(0, limit - total)]
                handle.write(kept)
                handle.flush()
                total += len(kept)
                result[name + "_bytes"] = total
                if len(kept) != len(data):
                    fail(name + "_overflow")
                    return
                if name == "stdout":
                    pending.extend(data)
                    while b"\n" in pending:
                        line, _, rest = pending.partition(b"\n")
                        pending = bytearray(rest)
                        if len(line) + 1 > bounds.line_bytes:
                            fail("stdout_line_overflow")
                            return
                        enqueue(("line", bytes(line) + b"\n"))
                    if len(pending) >= bounds.line_bytes:
                        fail("stdout_line_overflow")
                        return
        except Exception as exc:
            fail(name + "_capture_" + type(exc).__name__)

    def writer():
        while not stop.is_set():
            try:
                data, complete = outgoing.get(timeout=0.02)
            except queue.Empty:
                continue
            try:
                written = child.stdin.write(data)
                if written != len(data):
                    raise OSError("short_stdin_write")
                child.stdin.flush()
                complete.append(None)
            except Exception as exc:
                complete.append(type(exc).__name__)

    def check():
        if time.monotonic() >= deadline:
            raise RuntimeError("deadline")
        try:
            raise RuntimeError(failures.get_nowait())
        except queue.Empty:
            pass

    with (attempt / "stdout.bin").open("xb") as stdout_file, \
            (attempt / "stderr.bin").open("xb") as stderr_file, \
            (attempt / "events.jsonl").open("x", encoding="utf-8") as events_file, \
            (attempt / "transcript.jsonl").open("x", encoding="utf-8") as transcript:
        record_number = 0

        def record(kind, value=None):
            nonlocal record_number
            record_number += 1
            try:
                alive = child is not None and child.poll() is None
            except OSError as exc:
                alive = None
                result["cleanup_errors"].append("record_poll_" + type(exc).__name__)
            _json_line(transcript, {"kind": kind, "seq": record_number,
                                    "elapsed_ns": int((time.monotonic() - start) * 1e9),
                                    "child_alive": alive,
                                    "value": value})

        record("start", {"command": command, "bounds": asdict(bounds)})

        def send(data):
            if not isinstance(data, bytes) or not data.endswith(b"\n") or b"\n" in data[:-1]:
                raise RuntimeError("command_not_single_line")
            if len(data) > bounds.command_bytes or result["commands"] >= bounds.commands:
                raise RuntimeError("command_bound")
            check()
            done = []
            outgoing.put_nowait((data, done))
            while not done:
                check()
                time.sleep(0.005)
            if done[0] is not None:
                raise RuntimeError("stdin_" + done[0])
            result["commands"] += 1
            record("command_sent", {"bytes_hex": data.hex()})
            if command_sent is not None:
                command_sent(data)

        try:
            if on_ready is not None:
                on_ready(record)
            check()
            child = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     bufsize=0, shell=False)
            result["child_pid"] = child.pid
            record("child_started", {"pid": child.pid})
            for args in ((child.stdout, "stdout", bounds.stdout_bytes, stdout_file),
                         (child.stderr, "stderr", bounds.stderr_bytes, stderr_file)):
                thread = threading.Thread(target=capture, args=args, daemon=True)
                thread.start()
                threads.append(thread)
            thread = threading.Thread(target=writer, daemon=True)
            thread.start()
            threads.append(thread)
            if request is not None:
                send(request)
            eof = False
            while not eof:
                check()
                try:
                    kind, data = incoming.get(timeout=0.02)
                except queue.Empty:
                    continue
                if kind == "eof":
                    eof = True
                    continue
                result["lines"] += 1
                if result["lines"] > bounds.events:
                    raise RuntimeError("event_bound")
                _json_line(events_file, {"line": result["lines"], "bytes_hex": data.hex()})
                record("stdout_line", {"line": result["lines"]})
                reply = on_line(data)
                check()
                if reply is not None:
                    send(reply)
            while child.poll() is None:
                check()
                time.sleep(0.005)
            # Drain capture threads before accepting exit; late stderr overflow
            # and unterminated stdout are failures even when exit status is zero.
            for thread in threads[:2]:
                while thread.is_alive():
                    check()
                    thread.join(timeout=0.02)
            check()
            result["exit_code"] = child.returncode
            if child.returncode != 0:
                raise RuntimeError("child_nonzero")
            result.update(status="transport_complete", reason="child_exit_zero")
        except (Exception, KeyboardInterrupt) as exc:
            result["reason"] = str(exc)[:512]
            result["exception_type"] = type(exc).__name__
        finally:
            if child is not None:
                try:
                    if child.poll() is None:
                        try:
                            child.kill()
                            result["child_killed"] = True
                        except OSError as exc:
                            result["cleanup_errors"].append("kill_" + type(exc).__name__)
                        try:
                            child.wait(timeout=2)
                        except (OSError, subprocess.TimeoutExpired) as exc:
                            result["cleanup_errors"].append("wait_" + type(exc).__name__)
                    result["exit_code"] = child.poll()
                    result["exit_confirmed"] = result["exit_code"] is not None
                except OSError as exc:
                    result["cleanup_errors"].append("poll_" + type(exc).__name__)
                # After confirmed exit, retain remaining available pipe bytes up
                # to the capture limits. Drain queued lines without executing
                # callbacks: failed histories must never send a later release.
                drain_deadline = time.monotonic() + 2
                while result["exit_confirmed"] and any(t.is_alive() for t in threads[:2]) \
                        and time.monotonic() < drain_deadline:
                    try:
                        incoming.get_nowait()
                    except queue.Empty:
                        pass
                    for thread in threads[:2]:
                        thread.join(timeout=0.01)
                result["capture_drain_complete"] = all(not t.is_alive() for t in threads[:2])
            stop.set()
            for thread in threads:
                thread.join(timeout=0.2)
            result["threads_stopped"] = all(not t.is_alive() for t in threads)
            if child is not None and result["threads_stopped"]:
                for pipe in (child.stdin, child.stdout, child.stderr):
                    try:
                        pipe.close()
                    except OSError as exc:
                        result["cleanup_errors"].append("close_" + type(exc).__name__)
            if not result["threads_stopped"]:
                result.update(status="failed", reason="capture_or_writer_thread_retained")
            if result["cleanup_errors"] or (child is not None and not result["exit_confirmed"]):
                result.update(status="failed", reason="owned_child_cleanup_uncertain")
            result["elapsed_seconds"] = time.monotonic() - start
            record("exit", {"exit_code": result["exit_code"],
                            "exit_confirmed": result["exit_confirmed"],
                            "status": result["status"], "reason": result["reason"]})
            if after_exit is not None and result["exit_confirmed"]:
                try:
                    after_exit(record)
                except (Exception, KeyboardInterrupt) as exc:
                    result.update(status="failed", reason="after_exit_" + type(exc).__name__)
                    record("after_exit_failed", {"exception_type": type(exc).__name__})
    with (attempt / "result.json").open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
    return result


def sha256_file(path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for data in iter(lambda: handle.read(65536), b""):
            digest.update(data)
    return digest.hexdigest()


TEST_NAME = "storage::namespace_diagnostic::local_namespace_diagnostic_worker"


def run_reviewed(plan_path, freeze_path, review_path, *, case, fixture_root,
                 attempt_dir, unit="unit"):
    """Execute one exact parent-reviewed local control; never retries.

    Verification binds the current source, plan and executable; the caller is
    still the explicit owning parent. Neither those files nor this collector
    can grant imported custody or a storage admission.
    """
    import controller
    import fixtures
    import freeze
    import probe
    import protocol

    if Path(attempt_dir).exists():
        raise FileExistsError(attempt_dir)

    def prelaunch_failure(exc, stage):
        Path(attempt_dir).mkdir(parents=False, exist_ok=False)
        with (Path(attempt_dir) / "preparation_failure.json").open("x", encoding="utf-8") as handle:
            json.dump({"schema": "imageinfo-0218-preparation-failure-v1",
                       "stage": stage, "case": case, "fixture_root": str(fixture_root),
                       "exception_type": type(exc).__name__, "reason": str(exc)[:512],
                       "child_started": False, "replayed": False}, handle, indent=2)
            handle.write("\n")

    def observer_runtime():
        return {"implementation": sys.implementation.name, "version": sys.version,
                "platform": sys.platform, "stat_profile": probe._stat_profile()}

    try:
        verified = freeze.verify_reviewed(plan_path, freeze_path, review_path)
        plan = verified["plan"]
        observer_python = observer_runtime()
        if observer_python != plan.get("observer_python"):
            raise ValueError("observer Python runtime differs from reviewed plan")
        if case not in plan["cases"] or case not in fixtures.CASES:
            raise ValueError("cell outside exact reviewed plan")
        bounds = Bounds(**plan["bounds"])
        bounds.validate()
    except (Exception, KeyboardInterrupt) as exc:
        prelaunch_failure(exc, "review_or_plan")
        raise
    try:
        fixture = fixtures.prepare_fixture(fixture_root, case, unit=unit)
    except (Exception, KeyboardInterrupt) as exc:
        # Even preparation-only attempts receive a permanent failure marker;
        # any partially created authored fixture is deliberately left intact.
        prelaunch_failure(exc, "fixture_preparation")
        raise
    machine = controller.Controller(unit=unit)
    stream = protocol.EventStream(unit=unit)
    observations = []
    recorder = None
    pending_command = None
    candidate_seen = False
    native = {"schema": "imageinfo-0218-native-v1", "cell": case,
              "observer_python": observer_python,
              "request": {"unit": unit, "fixture_root": str(fixture_root)},
              "plan_sha256": verified["plan_sha256"],
              "plan_path": str(Path(plan_path).absolute()),
              "freeze_sha256": verified["freeze_sha256"],
              "freeze_path": str(Path(freeze_path).absolute()),
              "review_path": str(Path(review_path).absolute()),
              "review_sha256": sha256_file(review_path),
              "worker_sha256": verified["worker_sha256"],
              "worker_path": plan["argv"][0], "fixture_before": fixture,
              "observations": observations, "fixture_after": None,
              "protocol_complete": False, "protocol_events": 0,
              "committed": False, "production_profile_admitted": False,
              "raw_admitted": False, "authority_importable": False}

    def observe(phase, access):
        recorder("probe_begin", {"phase": phase})
        value = probe.write_open_probe(fixture["source"], expected_access=access,
                                       max_bytes=fixtures.SOURCE_BYTES)
        entry = {"phase": phase, "probe": value}
        observations.append(entry)
        recorder("probe_end", entry)
        if not value.get("expectation_met"):
            raise RuntimeError("source_probe_expectation_" + phase)

    def ready(record):
        nonlocal recorder
        recorder = record
        # Revalidate after preparation and immediately before child launch.
        freeze.verify_reviewed(plan_path, freeze_path, review_path)
        if observer_runtime() != plan["observer_python"]:
            raise ValueError("observer Python runtime changed before child launch")
        observe("baseline", True)

    def after_exit(record):
        nonlocal recorder
        recorder = record
        observe("after_exit", True)
        native["fixture_after"] = {
            name: probe.read_snapshot(fixture[name], max_bytes=fixtures.SOURCE_BYTES)
            for name in ("source", "candidate", "output")}
        unit_path = Path(fixture["candidate"]).parent
        allowed = {"candidate.bin", "output.bin", "prepared.record", "intent.record",
                   "observation.record", "receipt.record"}
        inventory = []
        if unit_path.exists():
            for index, path in enumerate(unit_path.iterdir()):
                if index >= 6 or path.name not in allowed:
                    raise ValueError("unexpected unit inventory")
                snapshot = probe.read_snapshot(path, max_bytes=(fixtures.CANDIDATE_BYTES
                                               if path.suffix == ".bin" else 65536))
                if snapshot.get("status") != "ok":
                    raise ValueError("unreadable retained artifact")
                info = path.stat()
                inventory.append({"name": path.name, "bytes": info.st_size,
                                  "sha256": snapshot["sha256"],
                                  "identity": {"device": info.st_dev, "inode": info.st_ino},
                                  "snapshot": snapshot})
        native["fixture_after"]["unit_files"] = sorted(inventory, key=lambda entry: entry["name"])
        record("artifact_checkpoint", native["fixture_after"])

    def line(raw):
        nonlocal pending_command, candidate_seen
        prefix = ("test " + TEST_NAME + " ... ").encode("ascii")
        if raw.startswith(prefix + protocol.PREFIX):
            raw = raw[len(prefix):]
        if not raw.startswith(protocol.PREFIX):
            # Only the fixed single-test libtest framing is accepted. No free
            # form stdout is silently promoted to an event or ignored.
            if raw in (b"\n", b"running 1 test\n", b"ok\n", prefix + b"\n") or re.fullmatch(
                    rb"test result: ok\. 1 passed; 0 failed; 0 ignored; 0 measured; [0-9]+ filtered out; finished in [0-9.]+s\n", raw):
                recorder("harness_line", {"bytes_hex": raw.hex()})
                return None
            raise ValueError("unexpected libtest stdout")
        event = stream.accept(raw)
        native["protocol_events"] += 1
        recorder("protocol_event", event)
        action = machine.accept(event)
        if action.kind == "observe_before":
            if case == "candidate-collision" and event["stage"] == "create-Candidate":
                recorder("collision_begin", {"event_seq": event["seq"]})
                collision = fixtures.inject_candidate_collision(fixture, event)
                native["collision"] = collision
                recorder("collision_end", collision)
        elif action.kind == "observe_held":
            candidate_seen = True
            recorder("candidate_checkpoint", event)
            observe("held", False)
            native["held_candidate"] = probe.read_snapshot(fixture["candidate"],
                                                           max_bytes=fixtures.CANDIDATE_BYTES)
            recorder("held_artifact_checkpoint", native["held_candidate"])
        else:
            return None
        command_action = machine.acknowledge_observation(event["seq"], event["stage"])
        pending_command = (event["seq"], event["stage"], command_action.command)
        recorder("observation_acknowledged", {"event_seq": event["seq"],
                                               "command": command_action.command})
        return protocol.encode_command(event, command_action.command)

    def sent(raw):
        nonlocal pending_command
        if pending_command is None:
            raise ValueError("command without pending observation")
        machine.command_sent(*pending_command)
        pending_command = None

    environment = dict(os.environ)
    environment.update(IMAGEINFO_218_ROOT=str(fixture_root), IMAGEINFO_218_UNIT=unit)
    result = execute_owned(plan["argv"], attempt_dir, bounds, line,
                           cwd=verified["freeze"]["root"], env=environment,
                           on_ready=ready, after_exit=after_exit, command_sent=sent)
    if result["status"] == "transport_complete":
        try:
            machine.eof()
            machine.mark_exit(result["exit_code"])
            native["protocol_complete"] = machine.complete and candidate_seen
        except ValueError as exc:
            native["protocol_error"] = str(exc)[:512]
    native["transport_status"] = result["status"]
    with (Path(attempt_dir) / "native.json").open("x", encoding="utf-8") as handle:
        json.dump(native, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
    return {"transport": result, "native": native}
