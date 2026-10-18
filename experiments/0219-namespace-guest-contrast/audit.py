"""Independent bounded audit of retained #0219 two-cell guest evidence.

No worker, probe, guest or controller is invoked. The accepted #0218 auditor
supplies bounded decoding and same-read-FD identity decoders only. Historical
custody rests on the explicit current-parent transcript, not file hashes.
"""
from __future__ import annotations

import argparse
import base64
import binascii
from functools import wraps
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re

_path = Path(__file__).resolve().parents[1] / "0218-namespace-observer" / "audit.py"
_spec = importlib.util.spec_from_file_location("namespace_218_audit_for_219", _path)
accepted = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(accepted)
AuditError = accepted.AuditError
require = accepted.require
_read, _load, _json, _lines = accepted._read, accepted._load, accepted._json, accepted._lines
_exact, _integer, _hex, _sha = accepted._exact, accepted._integer, accepted._hex, accepted._sha
FLAGS = accepted.FLAGS
CASES = ("persistent-write-error", "no-error")
STAGES = ("prepared", "source_reopened_hold", "before_candidate_hold", "candidate_hold", "cleared_hold", "released",
          "runtime_result", "backend_dropped", "exited", "final")
GATES = {"prepared": "start", "source_reopened_hold": "continue", "before_candidate_hold": "armed", "candidate_hold": "cleared",
         "cleared_hold": "release"}
PREFIX = b"IMAGEINFO219 "
RULE = {"event": "write_aio", "iotype": "write", "errno": 28, "once": False}
WORKER_TEST = "storage::namespace_guest_diagnostic::guest_namespace_diagnostic_worker"
# Positional phases matter where operation names such as root-flush repeat.
# This is the fixed production runtime order, not permission for other runs.
PHASES = (
    "Preflight", "RootCreated", "RootFlushed", "ParentFlushed", "CandidateCreated",
    "CandidateChecked", "CandidateFlushed", "CandidateParentFlushed",
    "PreparedCreated", "PreparedChecked", "PreparedFlushed", "PreparedParentFlushed",
    "IntentCreated", "IntentChecked", "IntentFlushed", "IntentParentFlushed",
    "CallerRelease", "Prepublication", "Publish", "Installed", "InstalledFlushed",
    "InstalledParentFlushed", "InstalledRechecked", "ObservationCreated", "ObservationChecked",
    "ObservationFlushed", "ObservationParentFlushed", "ReceiptCreated", "ReceiptChecked",
    "ReceiptFlushed", "ReceiptFileChecked", "ReceiptParentFlushed", "ReceiptParentChecked",
    "CheckedContext", "Final", "TerminalExport",
)
FAILURES = frozenset(("LengthOverflow", "CandidateTooLarge", "BudgetExhausted", "StorageUnavailable",
    "ShortSource", "OverlongSource", "SourceIo", "Cancelled", "BackendIo", "Unsupported", "Conflict",
    "Ambiguous", "InvalidBinding", "RecordTooLarge", "CallerHistory"))
EXPORT_NAMES = frozenset(("source.bin", "old-source.bin", "candidate.bin", "output.bin",
    "prepared.record", "intent.record", "observation.record", "receipt.record", "stdout.bin", "stderr.bin",
    "events.jsonl", "transcript.jsonl", "result.json", "guest-transcript.jsonl", "guest.json", "volume-binding.json"))
REQUIRED_EXPORT_NAMES = frozenset(("stdout.bin", "stderr.bin", "events.jsonl", "transcript.jsonl",
    "result.json", "guest-transcript.jsonl", "guest.json", "volume-binding.json"))


def _digest(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _guest_path(value):
    return (type(value) is str and 0 < len(value) <= 32768 and "\0" not in value
            and PureWindowsPath(value).is_absolute() and ".." not in PureWindowsPath(value).parts)


def _identities(value):
    require(type(value) is dict and set(value) == {"guest", "disk", "volume"}
            and all(type(v) is dict and v for v in value.values()), "guest/disk/volume identities missing")
    require(set(value["disk"]) == {"disk_path", "raw_node", "file_node", "filter_node", "device_id", "device_serial"}
            and set(value["volume"]) == {"volume_serial"}
            and all(type(v) is str and 0 < len(v) <= 32768 and "\0" not in v
                    for group in ("disk", "volume") for v in value[group].values()), "exact disk/volume binding incomplete")


def _false_flags(value):
    require(type(value) is dict and all(value.get(key) is False for key in FLAGS),
            "missing or positive admission flag")


def _outer_event(raw, index, unit, case):
    require(type(raw) is bytes and len(raw) <= 262144 and raw.startswith(PREFIX)
            and raw.endswith(b"\n") and b"\n" not in raw[:-1] and b"\r" not in raw,
            "outer event framing")
    event = _json(raw[len(PREFIX):-1])
    require(type(event) is dict and set(event) == {
        "v", "unit", "case", "seq", "stage", "observation", "worker_event", *FLAGS}, "outer event schema")
    require(type(event["v"]) is int and event["v"] == 1 and type(event["seq"]) is int
            and event["seq"] == index and event["unit"] == unit and event["case"] == case,
            "outer attempt/sequence mismatch")
    _false_flags(event)
    require(event["stage"] == STAGES[index - 1] and type(event["observation"]) is dict
            and bool(event["observation"]), "outer phase/order mismatch")
    expected = {"source_reopened_hold": ("before_operation", "create-root", 3),
                "before_candidate_hold": ("before_operation", "create-Candidate", 9),
                "candidate_hold": ("candidate_result", "create-Candidate", 10),
                "cleared_hold": ("candidate_result", "create-Candidate", 10),
                "released": ("candidate_result", "create-Candidate", 10),
                "runtime_result": ("runtime_result", "runtime", None),
                "backend_dropped": ("backend_dropped", "backend-drop", None)}.get(event["stage"])
    worker = event["worker_event"]
    if expected is None:
        require(worker is None, "unexpected worker event")
    else:
        require(type(worker) is dict and worker.get("unit") == unit
                and (worker.get("kind"), worker.get("stage")) == expected[:2]
                and (expected[2] is None or worker.get("seq") == expected[2]), "outer worker phase mismatch")
        _false_flags(worker)
    return event


def _transport(root):
    """Same bounded #0218 raw encoding, with #0219 protocol checked later.

    The accepted auditor's dead-after-write fallback assumes its old libtest
    test name. Reconstruct transport here so that a valid guest test exit race
    is checked against this auditor's complete worker protocol instead.
    """
    root = Path(root)
    result = _load(root / "result.json")
    require(type(result) is dict and result.get("schema") == "namespace-observer-run-v1", "worker run schema")
    bounds = accepted._bounds(result.get("bounds"))
    stdout, stderr = (_read(root / (name + ".bin"), bounds[name + "_bytes"]) for name in ("stdout", "stderr"))
    events = _lines(root / "events.jsonl", maximum=2 * bounds["stdout_bytes"] + 65536, count=bounds["events"])
    transcript = _lines(root / "transcript.jsonl", maximum=16 * 1048576, count=2048)
    require(result.get("status") == "transport_complete" and result.get("reason") == "child_exit_zero"
            and type(result.get("exit_code")) is int and result["exit_code"] == 0
            and result.get("child_killed") is False and result.get("replayed") is False
            and result.get("threads_stopped") is True and result.get("exit_confirmed") is True
            and result.get("capture_drain_complete") is True and result.get("cleanup_errors") == []
            and _integer(result.get("child_pid"), 1, 2**32 - 1), "worker capture/lifecycle incomplete")
    elapsed = result.get("elapsed_seconds")
    require(type(elapsed) in (int, float) and 0 <= elapsed <= bounds["deadline_seconds"], "worker elapsed deadline")
    require(type(result.get("stdout_bytes")) is int and type(result.get("stderr_bytes")) is int
            and result["stdout_bytes"] == len(stdout) and result["stderr_bytes"] == len(stderr), "worker raw capture lengths")
    raw_lines = []
    for index, event in enumerate(events, 1):
        require(type(event) is dict and set(event) == {"line", "bytes_hex"}
                and type(event["line"]) is int and event["line"] == index, "worker event line sequence")
        raw = _hex(event["bytes_hex"], bounds["line_bytes"])
        require(raw.endswith(b"\n") and b"\n" not in raw[:-1], "worker raw line framing")
        raw_lines.append(raw)
    require(b"".join(raw_lines) == stdout and type(result.get("lines")) is int
            and result["lines"] == len(raw_lines), "worker raw line/capture mismatch")
    require(transcript and transcript[0].get("kind") == "start", "worker transcript start missing")
    last_time = -1
    for index, row in enumerate(transcript, 1):
        require(type(row) is dict and set(row) == {"kind", "seq", "elapsed_ns", "child_alive", "value"}
                and type(row["seq"]) is int and row["seq"] == index and _integer(row["elapsed_ns"])
                and row["elapsed_ns"] >= last_time and type(row["child_alive"]) is bool, "worker transcript order/time")
        last_time = row["elapsed_ns"]
    require(_exact(transcript[0]["value"], {"command": result.get("command"), "bounds": bounds}), "worker start/result mismatch")
    received = [row for row in transcript if row["kind"] == "stdout_line"]
    require(_exact([row["value"] for row in received], [{"line": n} for n in range(1, len(events) + 1)]), "worker receive/capture mismatch")
    commands = [row for row in transcript if row["kind"] == "command_sent"]
    require(type(result.get("commands")) is int and len(commands) == result["commands"] <= bounds["commands"], "worker command count")
    for row in commands:
        require(type(row["value"]) is dict and set(row["value"]) == {"bytes_hex"}, "worker raw command schema")
        raw = _hex(row["value"]["bytes_hex"], bounds["command_bytes"])
        require(raw.endswith(b"\n") and b"\n" not in raw[:-1], "worker raw command framing")
    exits = [row for row in transcript if row["kind"] == "exit"]
    require(len(exits) == 1 and exits[0]["child_alive"] is False
            and _exact(exits[0]["value"], {"exit_code": 0, "exit_confirmed": True,
                "status": "transport_complete", "reason": "child_exit_zero"})
            and all(row["seq"] < exits[0]["seq"] for row in received + commands), "actual worker exit ordering/status")
    return {"root": root, "result": result, "bounds": bounds, "stdout": stdout, "stderr": stderr,
            "raw_lines": raw_lines, "transcript": transcript, "commands": commands, "received": received, "exit": exits[0]}


def audit_worker(attempt_dir, unit):
    """Reconstruct actual raw #0218 transport without assuming an error outcome."""
    transport = _transport(attempt_dir)
    require(not transport["stderr"], "unexpected worker stderr")
    events, positions = [], []
    harnesses = (b"test storage::namespace_diagnostic::local_namespace_diagnostic_worker ... ",
                 b"test storage::namespace_guest_diagnostic::guest_namespace_diagnostic_worker ... ")
    for raw, receive in zip(transport["raw_lines"], transport["received"]):
        for harness in harnesses:
            if raw.startswith(harness + accepted.PREFIX):
                raw = raw[len(harness):]
                break
        if not raw.startswith(accepted.PREFIX):
            require(raw in (b"\n", b"running 1 test\n", b"ok\n", *(harness + b"\n" for harness in harnesses)) or re.fullmatch(
                rb"test result: ok\. 1 passed; 0 failed; 0 ignored; 0 measured; [0-9]+ filtered out; finished in [0-9.]+s\n", raw),
                "unrecognized worker harness output")
            continue
        require(len(raw) <= 32768 and b"\r" not in raw and raw.endswith(b"\n"), "worker framing")
        event = _json(raw[len(accepted.PREFIX):-1])
        require(type(event) is dict and set(event) == {
            "v", "unit", "seq", "kind", "stage", "result", "bindings", *FLAGS}, "worker event schema")
        require(type(event["v"]) is int and event["v"] == 1 and event["unit"] == unit
                and type(event["seq"]) is int and event["seq"] == len(events) + 1, "worker sequence/unit")
        _false_flags(event)
        require(type(event["bindings"]) is list and len(event["bindings"]) <= 7, "worker binding bound")
        for binding in event["bindings"]:
            require(type(binding) is dict and set(binding) == {"identity", "facts"}, "worker binding schema")
            for key, limit in (("identity", 512), ("facts", 16384)):
                require(type(binding[key]) is str and re.fullmatch(r"(?:[0-9a-f]{2})+", binding[key])
                        and len(binding[key]) <= limit, "worker binding encoding")
        events.append(event)
        positions.append(receive["seq"])
    require(len(events) >= 12 and len(events) <= 128, "incomplete worker event sequence")
    candidate = events[9]
    require((candidate["kind"], candidate["stage"]) == ("candidate_result", "create-Candidate"),
            "missing actual compound candidate result")
    success = candidate["result"].get("success") if type(candidate["result"]) is dict else None
    require(type(success) is bool, "candidate success missing")
    require((len(events) - 2) % 2 == 0, "incomplete worker operation pair")
    operation_count = (len(events) - 2) // 2
    require(5 <= operation_count <= len(accepted.NORMAL_STAGES), "worker prefix outside candidate-to-terminal scope")
    stages = accepted.NORMAL_STAGES[:operation_count]
    expected = [(kind, stage) for stage in stages for kind in (
        "before_operation", "candidate_result" if stage == "create-Candidate" else "operation_result")]
    expected.extend((("runtime_result", "runtime"), ("backend_dropped", "backend-drop")))
    require([(e["kind"], e["stage"]) for e in events] == expected, "worker operation order differs")
    commands = []
    failed_index = None
    for index, event in enumerate(events):
        result, kind = event["result"], event["kind"]
        if kind in ("before_operation", "backend_dropped"):
            require(result is None, "unexpected worker result")
        elif kind in ("candidate_result", "operation_result"):
            require(type(result) is dict and set(result) == {
                "success", "failure", "native_error_kind", "native_os_error"}, "SDK result schema")
            require(type(result["success"]) is bool, "SDK success type")
            if result["success"]:
                require(all(result[key] is None for key in ("failure", "native_error_kind", "native_os_error")),
                        "success carries SDK error")
            else:
                operation_index = index // 2
                require(operation_index >= 4 and operation_index == operation_count - 1 and failed_index is None
                        and type(result["failure"]) is str and result["failure"] in FAILURES,
                        "failure before candidate checkpoint or operations after first failure")
                failed_index = operation_index
                native_kind, native_code = result["native_error_kind"], result["native_os_error"]
                require(native_kind is None or (type(native_kind) is str and 0 < len(native_kind) <= 128
                        and all(32 <= ord(char) <= 126 for char in native_kind)), "invalid SDK error kind")
                require(native_code is None or _integer(native_code, -(2**31), 2**31 - 1), "invalid native OS error")
                require(native_code is None or native_kind is not None, "native OS error lacks captured error kind")
        if kind in ("before_operation", "candidate_result"):
            command = {key: event[key] for key in ("v", "unit", "seq", "stage")}
            command["command"] = "release" if kind == "candidate_result" else "continue"
            commands.append((command, positions[index], positions[index + 1]))
    require(failed_index is not None or operation_count == len(accepted.NORMAL_STAGES),
            "successful prefix is missing later operations")
    require(len(commands) == len(transport["commands"]), "worker acknowledgement count")
    for sent, (wanted, lower, upper) in zip(transport["commands"], commands):
        require(_exact(_json(_hex(sent["value"]["bytes_hex"], 1024)), wanted)
                and lower < sent["seq"] < upper, "worker stale/wrong/out-of-gate command")
    runtime = events[-2]["result"]
    require(type(runtime) is dict and set(runtime) == {
        "status", "phase", "failure", "publication_possible", "release_possible", "protocol_complete",
        "retained_material", "pending_cleanup", "charged_bytes"}, "runtime schema")
    require(all(type(runtime[k]) is bool for k in ("publication_possible", "release_possible", "protocol_complete",
                                                  "retained_material", "pending_cleanup"))
            and _integer(runtime["charged_bytes"], 0, 2**64 - 1), "runtime field type")
    complete = failed_index is None
    last_index = operation_count - 1
    failure = None if complete else events[-3]["result"]["failure"]
    publication_possible = last_index >= 18
    release_possible = last_index >= 16
    failed_status = ("RecoveryRequired" if publication_possible else
                     "CancelledBeforePublish" if failure == "Cancelled" else
                     "Conflict" if failure in ("Conflict", "InvalidBinding") else
                     "FailedBeforePublish" if failure in ("BackendIo", "SourceIo", "ShortSource", "OverlongSource", "Ambiguous") else
                     "Refused")
    require(_exact(runtime, {"status": "Refused" if complete else failed_status,
        "phase": PHASES[last_index], "failure": failure,
        "publication_possible": publication_possible, "release_possible": release_possible, "protocol_complete": complete,
        "retained_material": True, "pending_cleanup": True, "charged_bytes": 4718592}),
        "runtime outcome contradicts actual candidate/protocol")
    require(positions[-2] < positions[-1] < transport["exit"]["seq"], "runtime/drop/confirmed exit order")
    _postwrite_exit_samples(transport, last_index, events, positions, commands)
    return {"transport": transport, "events": events, "positions": positions, "candidate": candidate,
            "candidate_receive_seq": positions[9], "release_seq": next(sent["seq"] for sent, (wanted, _, _) in
                zip(transport["commands"], commands) if wanted["command"] == "release"), "runtime": runtime,
            "first_failed_operation": None if complete else {"index": failed_index,
                "stage": accepted.NORMAL_STAGES[failed_index], "result": events[-3]["result"]}}


def _postwrite_exit_samples(transport, last_index, events, positions, commands):
    dead = [row for row in transport["commands"] if row["child_alive"] is False]
    if not dead:
        return
    require(len(dead) == 1 and dead[0] is transport["commands"][-1], "nonfinal command sampled worker exit")
    sent = dead[0]
    wanted, lower, upper = commands[-1]
    candidate_release = last_index == 4
    require((wanted["command"], wanted["stage"], wanted["seq"]) == (
        ("release", "create-Candidate", 10) if candidate_release else
        ("continue", accepted.NORMAL_STAGES[last_index], 2 * last_index + 1)), "dead-after-write lacks final finite gate")
    prewrite = [row for row in transport["transcript"] if row["kind"] == "observation_acknowledged"
                and _exact(row["value"], {"event_seq": wanted["seq"], "command": wanted["command"]})]
    received = next(row for row in transport["received"] if row["seq"] == lower)
    require(len(prewrite) == 1 and lower < prewrite[0]["seq"] < sent["seq"] < upper
            and received["child_alive"] is True and prewrite[0]["child_alive"] is True
            and not any(row["child_alive"] for row in transport["transcript"] if row["seq"] > sent["seq"]),
            "dead-after-write lacks live prewrite proof or contradicts later samples")
    if candidate_release:
        require(positions[-2] == upper and events[-2]["result"]["failure"] == events[9]["result"]["failure"],
                "candidate release consumption absent")
    else:
        require(events[-3]["kind"] == "operation_result" and events[-3]["stage"] == accepted.NORMAL_STAGES[last_index]
                and positions[-3] == upper, "final continue consumption absent")


def _error(value):
    require(type(value) is dict and set(value) == {"type", "errno", "winerror"}
            and type(value["type"]) is str and 0 < len(value["type"]) <= 128
            and all(32 <= ord(char) <= 126 for char in value["type"])
            and all(value[key] is None or _integer(value[key], -(2**31), 2**32 - 1)
                    for key in ("errno", "winerror")), "raw error schema/type/range")


def _lookup(snapshot, path, maximum):
    """Validate a raw read observation, retaining errors as observations."""
    require(type(snapshot) is dict and snapshot.get("path") == path, "pathname observation target")
    if snapshot.get("status") == "ok":
        require(type(snapshot.get("sha256")) is str and re.fullmatch(r"[0-9a-f]{64}", snapshot["sha256"])
                and _integer(snapshot.get("bytes_read"), 0, maximum)
                and _integer(snapshot.get("max_bytes"), snapshot["bytes_read"], maximum)
                and type(snapshot.get("observations_match")) is bool, "pathname digest/size")
        if snapshot["observations_match"]:
            accepted._snapshot(snapshot, path, snapshot["sha256"], snapshot["bytes_read"])
            accepted._bridge(snapshot)
        else:
            # Retain a raced property/identity observation without converting
            # it into successful preservation or a final name binding.
            require(snapshot.get("stat_profile") == "cpython-3.14.7-windows-path-creation-handle-change-v1"
                    and snapshot.get("identity_bridge_profile") == accepted.BRIDGE_PROFILE,
                    "unsupported raw snapshot profile")
            for key in ("path_before", "handle_before", "handle_after", "path_after"):
                _stat(snapshot.get(key))
            accepted._legacy_identity(snapshot.get("bridge_before"))
            accepted._legacy_identity(snapshot.get("bridge_after"))
    elif snapshot.get("status") == "error":
        _error(snapshot.get("error"))
    else:
        require(snapshot.get("status") == "refused" and type(snapshot.get("reason")) is str
                and 0 < len(snapshot["reason"]) <= 512, "pathname observation unclassified")
    return snapshot


def _stat(value):
    require(type(value) is dict and set(value) == {
        "device", "inode", "mode", "size", "mtime_ns", "ctime_ns", "birthtime_ns"}
        and all(_integer(value[key], 0, 2**64 - 1) for key in ("device", "inode", "size"))
        and _integer(value["mode"], 0, 2**32 - 1)
        and all(_integer(value[key], -(2**63), 2**63 - 1) for key in ("mtime_ns", "ctime_ns"))
        and (value["birthtime_ns"] is None or _integer(value["birthtime_ns"], -(2**63), 2**63 - 1)), "raw stat schema/type")


def _directory(value, path):
    require(type(value) is dict and set(value) == {"path", "status", "stat", "entries", "error", "reason"}
            and value["path"] == path and type(value["entries"]) is list and len(value["entries"]) <= 32,
            "directory inventory schema/bound")
    if value["status"] == "ok":
        require(type(value["stat"]) is dict and value["error"] is None and value["reason"] is None,
                "directory success fields")
        _stat(value["stat"])
        names = []
        for item in value["entries"]:
            require(type(item) is dict and set(item) == {"name", "stat", "error"}
                    and type(item["name"]) is str and item["name"] not in ("", ".", "..")
                    and not any(c in item["name"] for c in ("/", "\\", ":"))
                    and ((type(item["stat"]) is dict and item["error"] is None)
                         or (item["stat"] is None and type(item["error"]) is dict)), "directory entry schema")
            names.append(item["name"])
            if item["stat"] is not None:
                _stat(item["stat"])
        require(names == sorted(set(names)), "duplicate/unordered directory inventory")
    else:
        require(value["status"] in ("error", "refused")
                and (type(value["error"]) is dict or type(value["reason"]) is str),
                "directory observation failure missing")


def _snapshot_observation(snapshot, fixture, phase):
    """Independently validate full names including explicit old/prepared lookups."""
    require(type(snapshot) is dict and set(snapshot) == {
        "schema", "case", "unit", "phase", "root", "directories", "paths", "cleanupAuthorized"}, "fixture snapshot schema")
    require(snapshot["schema"] == "imageinfo-0219-fixture-snapshot-v1" and snapshot["case"] == fixture["case"]
            and snapshot["unit"] == fixture["unit"] and snapshot["phase"] == phase
            and snapshot["root"] == fixture["root"] and snapshot["cleanupAuthorized"] is False, "fixture snapshot selection")
    require(type(snapshot["directories"]) is dict and set(snapshot["directories"]) == {"volume", "root", "unit"},
            "directory inventory missing")
    root = fixture["root"].rstrip("/\\")
    # Preserve guest path spelling; audit may run on a different host OS.
    separator = "\\" if "\\" in fixture["candidate"] else "/"
    _directory(snapshot["directories"]["root"], fixture["root"])
    _directory(snapshot["directories"]["unit"], root + separator + "unit")
    _directory(snapshot["directories"]["volume"], fixture["sourceVolumeRoot"])
    require(type(snapshot["paths"]) is dict and set(snapshot["paths"]) == {
        "source", "old", "preparedSource", "candidate", "output", "prepared", "intent", "observation", "receipt"}, "pathname inventory missing")
    for name, value in snapshot["paths"].items():
        _lookup(value, fixture[name], 16 * 1048576 if name in ("source", "old", "preparedSource") else 4 * 1048576)
    require(_exact(snapshot["paths"]["preparedSource"], snapshot["paths"]["source"]), "prepared/source lookup differs")
    if phase in ("prepared", "source_reopened_hold", "before_candidate_hold"):
        source = snapshot["paths"]["source"]
        stat = accepted._snapshot(source, fixture["source"], fixture["sourceSha256"], fixture["sourceBytes"])
        require({"device": stat["device"], "inode": stat["inode"]} == fixture["sourceIdentity"], "source identity differs before arm")
    return snapshot


def _fixture(fixture, unit, case):
    require(type(fixture) is dict and fixture.get("schema") == "imageinfo-0219-fixture-v1"
            and fixture.get("unit") == unit and fixture.get("case") == case
            and fixture.get("transactionDir") == "unit", "fixture declaration")
    require(fixture.get("sourceBytes") == 16 * 1048576 and type(fixture["sourceBytes"]) is int
            and fixture.get("candidateBytes") == 4 * 1048576 and type(fixture["candidateBytes"]) is int
            and fixture.get("sourceByte") == 0x53 and type(fixture["sourceByte"]) is int
            and fixture.get("candidateByte") == 0x18 and type(fixture["candidateByte"]) is int,
            "authored marker dimensions changed")
    require(fixture.get("sourceSha256") == accepted._repeated_hash(0x53, 16 * 1048576)
            and fixture.get("candidateSha256") == accepted._repeated_hash(0x18, 4 * 1048576), "marker digest differs")
    require(fixture.get("authoredOnly") is True and fixture.get("cleanupAuthorized") is False
            and fixture.get("unitInitiallyAbsent") is True and fixture.get("outputExpectedAbsent") is True,
            "fixture authority/name premise")
    require(type(fixture.get("root")) is str and 0 < len(fixture["root"]) <= 4096, "fixture root bound")
    separator = "\\" if "\\" in fixture["root"] else "/"
    names = {"source": "source.bin", "candidate": "unit/candidate.bin", "output": "unit/output.bin",
             "prepared": "unit/prepared.record", "intent": "unit/intent.record",
             "observation": "unit/observation.record", "receipt": "unit/receipt.record"}
    for name, relative in names.items():
        require(fixture.get(name) == fixture["root"].rstrip("/\\") + separator + relative.replace("/", separator),
                "fixture name changed")
    parent = str((PureWindowsPath if separator == "\\" else PurePosixPath)(fixture["root"]).parent)
    require(fixture.get("sourceVolumeRoot") == parent and fixture.get("old") == parent.rstrip("/\\") + separator + "source.bin"
            and fixture.get("preparedSource") == fixture["source"], "old/prepared source name binding changed")
    require(fixture.get("preparationMode") == "existing_offline_seed" and fixture.get("explicitPreparationFlush") is False
            and fixture.get("durablePreparationAcknowledged") is False and type(fixture.get("historicalPayloadByte")) is int
            and fixture["historicalPayloadByte"] == 0x31 and fixture.get("historicalPayloadChanged") is True,
            "historical preparation method changed or model-only fixture")
    marker = b"imageinfo-0219-disposable-authored-only-v1\n"
    require(_exact(fixture.get("requiredWorkerMarker"), {"path": fixture["root"].rstrip("/\\") + separator + "fixture219.marker",
                "bytes": len(marker), "sha256": _sha(marker)})
            and fixture.get("historicalMetadataPreparationChanged") is True
            and fixture.get("manifestPersistedOnTestVolume") is False, "required guest marker/preparation metadata differs")
    for key in ("sourceIdentity", "rootIdentity"):
        identity = fixture.get(key)
        require(type(identity) is dict and set(identity) == {"device", "inode"}
                and all(_integer(v, 0, 2**64 - 1) for v in identity.values()), "fixture raw identity")
    move = fixture.get("sourceMove")
    require(type(move) is dict and set(move) == {"before", "after", "identityBefore", "identityAfter", "sameObject"}
            and move["sameObject"] is True and _exact(move["identityBefore"], move["identityAfter"])
            and _exact(move["identityAfter"], fixture["sourceIdentity"]), "source move object identity differs")
    for key, path in (("before", fixture["old"]), ("after", fixture["source"])):
        observed = move[key]
        require(type(observed) is dict and set(observed) == {"path", "pathBefore", "handleBefore", "handleAfter", "pathAfter",
                "bytesRead", "sha256", "identity"} and observed["path"] == path
                and type(observed["bytesRead"]) is int and observed["bytesRead"] == fixture["sourceBytes"]
                and observed["sha256"] == fixture["sourceSha256"] and _exact(observed["identity"], fixture["sourceIdentity"]),
                "source move bytes/identity evidence differs")
        for stat_key in ("pathBefore", "handleBefore", "handleAfter", "pathAfter"):
            _stat(observed[stat_key])
            require({k: observed[stat_key][k] for k in ("device", "inode")} == fixture["sourceIdentity"]
                    and observed[stat_key]["size"] == fixture["sourceBytes"], "source move raw stat differs")
        require(_exact(observed["pathBefore"], observed["pathAfter"])
                and _exact(observed["handleBefore"], observed["handleAfter"]), "source changed during move read")
    for phase in ("originalInventory", "preparedInventory"):
        inventory = fixture.get(phase)
        require(type(inventory) is dict and set(inventory) == {"volume", "root", "unit", "paths"}, "preparation inventory missing")
        for name, path in (("volume", parent), ("root", fixture["root"]),
                           ("unit", fixture["root"].rstrip("/\\") + separator + "unit")):
            _directory(inventory[name], path)
        require(type(inventory["paths"]) is dict and set(inventory["paths"]) == set(names) | {"old", "preparedSource"},
                "preparation names missing")
        for name, snapshot in inventory["paths"].items():
            require(type(snapshot) is dict and set(snapshot) == {"path", "status", "stat", "error", "reason"}
                    and snapshot["path"] == fixture[name], "preparation lookup schema/target")
            exists = name == "old" if phase == "originalInventory" else name in ("source", "preparedSource")
            if exists:
                require(snapshot["status"] == "ok" and snapshot["error"] is None and snapshot["reason"] is None, "preparation source absent")
                _stat(snapshot["stat"])
                require({k: snapshot["stat"][k] for k in ("device", "inode")} == fixture["sourceIdentity"]
                        and snapshot["stat"]["size"] == fixture["sourceBytes"], "preparation source identity differs")
            else:
                require(snapshot["status"] == "error" and snapshot["stat"] is None
                        and type(snapshot["error"]) is dict and snapshot["error"].get("errno") == 2,
                        "preparation absent name lacks raw lookup failure")
    return fixture


def _write_probe(value, fixture, phase):
    require(type(value) is dict and value.get("path") == fixture["source"]
            and value.get("expected_access") is (phase in ("prepared", "exited"))
            and type(value.get("flags")) is int and value["flags"] == 32769, "probe target/mode")
    before = _lookup(value.get("before"), fixture["source"], 16 * 1048576)
    require(type(value.get("expectation_met")) is bool and type(value.get("source_unchanged")) is bool,
            "probe raw boolean type")
    if value.get("status") == "not_attempted":
        require(phase not in ("prepared", "source_reopened_hold", "before_candidate_hold")
                and (before["status"] != "ok" or before.get("observations_match") is False)
                and value.get("after") is None and value.get("error") is None and value.get("opened_stat") is None
                and value.get("denial_observation") is None and value["source_unchanged"] is False
                and value["expectation_met"] is False and value.get("close_error") is None,
                "unattempted probe contradicts source observation")
        return before, None
    require(before["status"] == "ok" and before.get("observations_match") is True,
            "probe attempted despite failed prior source snapshot")
    after = _lookup(value.get("after"), fixture["source"], 16 * 1048576)
    if phase in ("prepared", "source_reopened_hold", "before_candidate_hold"):
        accepted._probe(value, phase == "prepared", fixture["source"], fixture["sourceSha256"], fixture["sourceBytes"])
    else:
        # A lookup/open failure under the filter is a finding, not fabricated
        # preservation. Keep all raw outcomes rather than declaring success.
        require(value.get("status") in ("opened", "open_error", "handle_stat_error"), "probe status unknown")
        if value.get("close_error") is not None:
            _error(value["close_error"])
        if value["status"] == "opened":
            require(value.get("error") is None and value.get("denial_observation") is None, "opened probe fields")
            _stat(value.get("opened_stat"))
        else:
            _error(value.get("error"))
            require(value.get("opened_stat") is None, "failed open/stat retained unexpected opened stat")
            error = value["error"]
            expected_denial = ("win32_sharing_violation" if error["winerror"] == 32 else
                               "crt_eacces_without_native_error" if error["winerror"] is None and error["errno"] == 13 else None)
            require(value.get("denial_observation") == (expected_denial if value["status"] == "open_error" else None),
                    "probe denial classification differs from raw fields")
        unchanged = (after["status"] == "ok" and after.get("observations_match") is True
                     and before["sha256"] == after["sha256"] and accepted._same_snapshot_properties(before, after))
        access = value["status"] == "opened" if value["expected_access"] else (
            value["status"] == "open_error" and value["denial_observation"] is not None)
        met = bool(access and value.get("close_error") is None and unchanged
                   and (value.get("opened_stat") is None or _exact(value["opened_stat"], before["handle_before"])))
        require(value["source_unchanged"] is unchanged and value["expectation_met"] is met,
                "probe derived booleans contradict raw observations")
    return before, after


def audit_guest(attempt_dir):
    """Validate a retained guest cell, independent of host fault assertions."""
    root = Path(attempt_dir)
    guest = _load(root / "guest.json", 8 * 1048576)
    require(type(guest) is dict and guest.get("schema") == "imageinfo-0219-guest-v1", "guest schema")
    _false_flags(guest)
    unit, case = guest.get("unit"), guest.get("case")
    require(type(unit) is str and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", unit) and case in CASES, "guest attempt identity")
    require(guest.get("status") == "transport_complete" and guest.get("protocol_complete") is True
            and guest.get("replayed") is False and guest.get("child_started") is True, "failed/incomplete guest attempt retained")
    fixture = _fixture(guest.get("fixture"), unit, case)
    worker = audit_worker(root, unit)
    require(_exact(guest.get("transport"), worker["transport"]["result"]), "guest worker result differs")
    notes = _lines(root / "guest-transcript.jsonl", 16 * 1048576, 1024)
    previous = -1
    for index, row in enumerate(notes, 1):
        require(type(row) is dict and set(row) == {"seq", "kind", "elapsed_ns", "value"}
                and type(row["seq"]) is int and row["seq"] == index
                and _integer(row["elapsed_ns"]) and row["elapsed_ns"] >= previous, "guest transcript order/time")
        previous = row["elapsed_ns"]
    event_notes = [row for row in notes if row["kind"] == "event"]
    require(len(event_notes) == len(STAGES), "missing/extra outer event")
    events = []
    for index, row in enumerate(event_notes, 1):
        require(type(row["value"]) is dict and set(row["value"]) == {"bytes_hex"}, "outer raw event schema")
        events.append(_outer_event(_hex(row["value"]["bytes_hex"], 262144), index, unit, case))
    commands = [row for row in notes if row["kind"] == "command_received"]
    gated = [(index, event) for index, event in enumerate(events) if event["stage"] in GATES]
    require(len(commands) == len(gated), "missing/extra outer command")
    for row, (index, event) in zip(commands, gated):
        require(type(row["value"]) is dict and set(row["value"]) == {"bytes_hex"}, "outer raw command schema")
        raw = _hex(row["value"]["bytes_hex"], 1024)
        require(raw.endswith(b"\n") and b"\r" not in raw and b"\n" not in raw[:-1], "outer command framing")
        wanted = {key: event[key] for key in ("v", "unit", "case", "seq", "stage")}
        wanted["command"] = GATES[event["stage"]]
        require(_exact(_json(raw), wanted) and event_notes[index]["seq"] < row["seq"] < event_notes[index + 1]["seq"],
                "outer stale/duplicate/out-of-gate command")
    require(_exact([r["value"] for r in notes if r["kind"] == "worker_event"], worker["events"]),
            "guest worker event copies differ from raw")
    require(_exact([r["value"] for r in notes if r["kind"] == "worker_command_sent"],
                   [r["value"] for r in worker["transport"]["commands"]]), "guest worker command copies differ")
    copied = [r for r in worker["transport"]["transcript"] if r["kind"].startswith("guest_")]
    require(len(copied) == len(notes) and all(r["kind"] == "guest_" + n["kind"]
            and _exact(r["value"], n["value"]) for r, n in zip(copied, notes)), "worker/guest transcript mismatch")
    note_positions = {n["seq"]: r for n, r in zip(notes, copied)}
    by_stage = {event["stage"]: event for event in events}
    outer_positions = {event["stage"]: note_positions[note["seq"]]["seq"] for event, note in zip(events, event_notes)}
    core_keys = ("phase", "snapshot", "write_probe")
    for event in events:
        if event["worker_event"] is not None:
            sequence = event["worker_event"]["seq"]
            require(_exact(event["worker_event"], worker["events"][sequence - 1]), "outer/raw worker event differs")
    require(_exact(by_stage["candidate_hold"]["worker_event"], by_stage["cleared_hold"]["worker_event"])
            and _exact(by_stage["candidate_hold"]["worker_event"], by_stage["released"]["worker_event"]), "held candidate event changed")
    observations = guest.get("observations")
    phases = ("prepared", "source_reopened_hold", "before_candidate_hold", "candidate_hold", "cleared_hold", "exited")
    require(type(observations) is list and len(observations) == len(phases), "observation denominator")
    for observation, phase in zip(observations, phases):
        require(type(observation) is dict and observation.get("phase") == phase, "observation phase order")
        _snapshot_observation(observation.get("snapshot"), fixture, phase)
        _write_probe(observation.get("write_probe"), fixture, phase)
        begins = [r for r in notes if r["kind"] == "observation_begin" and r["value"] == {"phase": phase}]
        ends = [r for r in notes if r["kind"] == "observation_end" and type(r["value"]) is dict
                and _exact({k: r["value"].get(k) for k in core_keys}, {k: observation.get(k) for k in core_keys})]
        require(len(begins) == len(ends) == 1 and begins[0]["seq"] < ends[0]["seq"], "observation raw timeline missing")
        begin, end = note_positions[begins[0]["seq"]], note_positions[ends[0]["seq"]]
        emitted = by_stage[phase]["observation"]
        if phase == "exited":
            emitted = emitted.get("observation")
        require(type(emitted) is dict and _exact({k: emitted.get(k) for k in core_keys},
                {k: observation.get(k) for k in core_keys}) and end["seq"] < outer_positions[phase],
                "outer phase differs from actual observation/order")
        if phase == "prepared":
            spawned = [r for r in worker["transport"]["transcript"] if r["kind"] == "child_started"]
            require(len(spawned) == 1 and end["seq"] < spawned[0]["seq"], "prepared observation after spawn")
        elif phase == "exited":
            require(worker["transport"]["exit"]["seq"] < begin["seq"] and not begin["child_alive"]
                    and not end["child_alive"], "postexit observation before confirmed exit")
        else:
            lower = {"source_reopened_hold": worker["positions"][2], "before_candidate_hold": worker["positions"][8],
                     "candidate_hold": worker["candidate_receive_seq"], "cleared_hold": worker["candidate_receive_seq"]}[phase]
            upper = worker["release_seq"] if phase in ("candidate_hold", "cleared_hold") else next(
                r["seq"] for r in worker["transport"]["commands"] if _json(_hex(r["value"]["bytes_hex"], 1024))["seq"] ==
                (3 if phase == "source_reopened_hold" else 9))
            require(lower < begin["seq"] < end["seq"] < upper and begin["child_alive"] and end["child_alive"],
                    "held observation outside actual worker gate")
            prior_gate = {"source_reopened_hold": "prepared", "before_candidate_hold": "source_reopened_hold",
                          "candidate_hold": "before_candidate_hold", "cleared_hold": "candidate_hold"}[phase]
            prior_command = next(r for r in commands if _json(_hex(r["value"]["bytes_hex"], 1024))["stage"] == prior_gate)
            require(note_positions[prior_command["seq"]]["seq"] < begin["seq"], "observation precedes current parent phase command")
    require(by_stage["exited"]["observation"].get("exit_confirmed") is True
            and type(by_stage["exited"]["observation"].get("exit_code")) is int
            and by_stage["exited"]["observation"]["exit_code"] == 0, "outer confirmed exit missing")
    final = by_stage["final"]["observation"].get("snapshot")
    _snapshot_observation(final, fixture, "final")
    require(_exact(guest.get("final_snapshot"), final), "guest final snapshot differs from raw outer event")
    require(worker["release_seq"] < outer_positions["released"] < worker["positions"][-2],
            "released event not after actual send/flush before runtime")
    release_command = next(r for r in commands if _json(_hex(r["value"]["bytes_hex"], 1024))["stage"] == "cleared_hold")
    require(note_positions[release_command["seq"]]["seq"] < worker["release_seq"], "child release before explicit parent release")
    require(by_stage["released"]["observation"].get("child_release_write_flush_confirmed") is True
            and by_stage["final"]["observation"].get("protocol_complete") is True, "release/final status missing")
    held = []
    for event in worker["events"]:
        if event["kind"] == "backend_dropped":
            require(event["bindings"] == [], "backend drop retained bindings")
            continue
        growing = event["kind"] in ("operation_result", "candidate_result") and event["result"]["success"] and (
            event["stage"] in ("preflight", "create-root") or event["stage"].startswith("create-"))
        require(event["bindings"][:len(held)] == held and len(event["bindings"]) == len(held) + int(growing),
                "held source/object binding history changed")
        held = event["bindings"]
    prepared_source = observations[0]["snapshot"]["paths"]["source"]
    accepted._held_binding(held[0], accepted._bridge(prepared_source), fixture["sourceBytes"], fixture["sourceSha256"])
    unit_stat = observations[2]["snapshot"]["directories"]["unit"]["stat"]
    require(type(unit_stat) is dict and all(_integer(unit_stat.get(k), 0, 2**64 - 1) for k in ("device", "inode")),
            "live transaction root identity missing")
    accepted._root_binding(held[1], {k: unit_stat[k] for k in ("device", "inode")},
                           fixture["sourceIdentity"], accepted._bridge(prepared_source))
    held_candidate_final_name = None
    names = ("output", "prepared", "intent", "observation", "receipt")
    for binding, name in zip(held[2:], names):
        snapshot = final["paths"][name]
        if name == "output":
            # A refused prepublication continuation retains candidate.bin.
            # A failed publish can leave either name; select only an actual
            # stable snapshot with the held identity, never infer the rename.
            snapshot = None
            for candidate_name in ("candidate", "output"):
                observed = final["paths"][candidate_name]
                if observed["status"] == "ok" and observed.get("observations_match") is True:
                    legacy = accepted._bridge(observed)
                    identity = legacy["volume_serial_u32"].to_bytes(8, "little") + legacy["file_index_u64"].to_bytes(8, "little")
                    if bytes.fromhex(binding["identity"]) == identity:
                        snapshot, held_candidate_final_name = observed, candidate_name
                        break
            if snapshot is None:
                snapshot = {"status": "unbound-observed-names"}
        if snapshot["status"] == "ok" and snapshot.get("observations_match") is True:
            accepted._held_binding(binding, accepted._bridge(snapshot), snapshot["bytes_read"], snapshot["sha256"])
        else:
            # Namespace failure is precisely an investigated outcome. Retain
            # it without inventing a final name-to-handle binding.
            raw = bytes.fromhex(binding["facts"])
            header = b"imageinfo-held-object-v1\0"
            require(raw.startswith(header) and len(raw) >= len(header) + 96, "held artifact encoding incomplete")
            values = [int.from_bytes(raw[len(header) + n * 8:len(header) + (n + 1) * 8], "little") for n in range(8)]
            end = len(header) + 64 + values[7]
            require(values[0] <= 2**32 - 1 and len(raw) == end + 32, "held artifact facts/digest extent")
            accepted._held_binding(binding, {"volume_serial_u32": values[0], "file_index_u64": values[1]}, values[2], raw[end:].hex())
            if name == "output":
                require(values[2] == fixture["candidateBytes"] and raw[end:].hex() == fixture["candidateSha256"],
                        "held candidate authored bytes differ")
    return {"guest": guest, "worker": worker, "events": events, "notes": notes, "fixture": fixture, "final": final,
            "held_candidate_final_name": held_candidate_final_name}


def _graph(nodes, blocks, binding, selected, rule, *, filter_exists=True):
    require(type(nodes) is list and 2 <= len(nodes) <= 256 and type(blocks) is list and len(blocks) <= 256,
            "QMP graph bounds")
    lookup = {}
    for node in nodes:
        require(type(node) is dict and type(node.get("node-name")) is str and node["node-name"] not in lookup,
                "QMP duplicate/malformed node")
        lookup[node["node-name"]] = node
    require(binding["raw_node"] in lookup and binding["file_node"] in lookup, "QMP disk nodes missing")
    raw, file = lookup[binding["raw_node"]], lookup[binding["file_node"]]
    require(file.get("drv") == "file" and file.get("image", {}).get("filename") == binding["disk_path"]
            and file.get("children", []) == [], "QMP file/disk changed")
    require(raw.get("drv") == "raw" and raw.get("children") == [{"node-name": selected, "child": "file"}],
            "QMP active raw child differs")
    if filter_exists:
        filt = lookup.get(binding["filter_node"], {})
        require(filt.get("drv") == "blkdebug" and filt.get("children") == [
            {"node-name": binding["file_node"], "child": "image"}], "QMP filter child differs")
        filename = filt.get("image", {}).get("filename")
        require(type(filename) is str and filename.startswith("json:") and len(filename) <= 65536,
                "QMP loaded rule configuration missing")
        config = _json(filename[5:].encode("utf-8"))
        require(config.get("driver") == "blkdebug" and _exact(config.get("inject-error"), [rule] if rule else []),
                "QMP loaded rule is not exact persistent whole-volume rule/control")
    else:
        require(binding["filter_node"] not in lookup, "existing filter adopted")
    matches = [block for block in blocks if type(block) is dict
               and block.get("inserted", {}).get("node-name") == binding["raw_node"]]
    require(len(matches) == 1 and matches[0].get("qdev") in (
        binding["device_id"], "/machine/peripheral/" + binding["device_id"] + "/" + binding["device_id"] + ".0",
        "/machine/peripheral/" + binding["device_id"] + "/" + binding["device_id"] + ".0/legacy[0]"),
        "QMP attached device differs")


def audit_host(host_path, cell, plan, plan_sha256):
    """Audit exact retained QMP graph/rule actions and guest command ordering."""
    rows = _lines(host_path, 32 * 1048576, 2048)
    require(rows and rows[0].get("kind") == "resident", "host resident start missing")
    case = cell["guest"]["case"]
    expected = plan["resident_expected"]["controller"][case]
    epoch = expected["controller_epoch"]
    previous_time, previous_state = -1, -1
    for row in rows:
        require(type(row) is dict and set(row) == {"kind", "controller_epoch", "state_epoch", "monotonic_ns", "value"}
                and row["controller_epoch"] == epoch and _integer(row["state_epoch"], 0, 3)
                and row["state_epoch"] >= previous_state and _integer(row["monotonic_ns"])
                and row["monotonic_ns"] >= previous_time, "controller epoch/order mismatch")
        previous_time, previous_state = row["monotonic_ns"], row["state_epoch"]
        require(row["kind"] in {"resident", "plan-bound", "qmp", "prepared", "armed", "before-clear", "cleared",
                                "guest-event", "command-prepared", "command-sent", "http-assets", "http-request", "http-response",
                                "http-artifact", "http-export"},
                "failed/unknown host ledger row")
    resident = rows[0]["value"]
    require(type(resident) is dict and all(_exact(resident.get(k), value) for k, value in expected.items()),
            "loaded controller code/runtime/epoch differs")
    binding = resident.get("binding")
    require(type(binding) is dict and set(binding) == {"unit", "case", "raw_node", "file_node", "filter_node",
            "disk_path", "device_id", "device_serial", "volume_serial", "root"}, "controller binding schema")
    selection = next(row for row in plan["cases"] if row["case"] == case)
    require(binding["unit"] == selection["unit"] == cell["guest"]["unit"]
            and binding["root"] == selection["root"] == cell["fixture"]["root"] and binding["case"] == case,
            "controller case/root/unit differs")
    identities = selection.get("identities", plan["identities"])
    require(all(binding.get(k) == value for k, value in identities["disk"].items())
            and all(binding.get(k) == value for k, value in identities["volume"].items()),
            "controller disk/volume profile differs")
    rule = RULE if case == CASES[0] else None
    require(_exact(resident.get("rule"), rule), "resident requested rule differs")
    for row in rows:
        if row["kind"] in ("resident", "plan-bound", "prepared", "armed", "before-clear", "cleared"):
            value = row["value"]
            require(type(value) is dict and all(_exact(value.get(k), v) for k, v in expected.items())
                    and _exact(value.get("binding"), binding) and _exact(value.get("rule"), rule)
                    and value.get("state_epoch") == row["state_epoch"]
                    and type(value.get("record_failure_count")) is int and value["record_failure_count"] == 0
                    and value.get("record_failures") == [], "resident epoch/code/config changed or recording loss")
            if row["kind"] != "cleared":
                require(value.get("clear_outcome") is None, "premature clear outcome")
            if row["kind"] != "resident" or value.get("plan_sha256") is not None:
                require(value.get("plan_sha256") == plan_sha256, "resident loaded plan changed")
    bound = [r for r in rows if r["kind"] == "plan-bound"]
    require(resident.get("plan_sha256") == plan_sha256 or len(bound) == 1, "loaded plan never bound")
    # Exact finite QMP operation sequence: prepare, arm, pre-clear observation,
    # clear. Every successful query retains its unwrapped actual response.
    qmp = [(index, row) for index, row in enumerate(rows) if row["kind"] == "qmp"]
    cursor = 0
    graph_indices = []
    def call(command, arguments):
        nonlocal cursor
        require(cursor < len(qmp), "missing QMP operation")
        index, row = qmp[cursor]
        cursor += 1
        value = row["value"]
        require(type(value) is dict and set(value) == {"command", "arguments", "success", "response", "error"}
                and value["command"] == command and _exact(value["arguments"], arguments)
                and value["success"] is True and value["error"] is None, "QMP operation failed/changed/replayed")
        return index, value["response"]
    def graph(selected, exists=True):
        index, nodes = call("query-named-block-nodes", None)
        _, blocks = call("query-block", None)
        _, serial = call("qom-get", {"path": "/machine/peripheral/" + binding["device_id"], "property": "serial"})
        require(serial == binding["device_serial"], "actual QMP device serial differs")
        _, stats = call("query-blockstats", None)
        require(type(stats) is list and len(stats) <= 256, "QMP raw block statistics missing")
        _graph(nodes, blocks, binding, selected, rule, filter_exists=exists)
        graph_indices.append(index)
    graph(binding["file_node"], False)
    call("blockdev-add", {"driver": "blkdebug", "node-name": binding["filter_node"],
                         "image": binding["file_node"], "inject-error": [rule] if rule else []})
    graph(binding["file_node"])
    graph(binding["file_node"])
    arm_index, _ = call("blockdev-reopen", {"options": [{"driver": "raw", "node-name": binding["raw_node"],
                                                       "file": binding["filter_node"]}]})
    graph(binding["filter_node"])
    graph(binding["filter_node"])
    clear_index, clear_response = call("blockdev-reopen", {"options": [{"driver": "raw", "node-name": binding["raw_node"],
                                                         "file": binding["file_node"]}]})
    graph(binding["file_node"])
    require(cursor == len(qmp), "extra QMP operation/replay")
    host_events = [(i, r["value"]) for i, r in enumerate(rows) if r["kind"] == "guest-event"]
    require(_exact([value for _, value in host_events], cell["events"]), "host/guest outer raw events differ")
    indexes = {value["stage"]: i for i, value in host_events}
    require(indexes["source_reopened_hold"] < indexes["before_candidate_hold"] < graph_indices[2]
            < arm_index < graph_indices[3] < indexes["candidate_hold"] < graph_indices[4]
            < clear_index < graph_indices[5] < indexes["cleared_hold"] < indexes["released"],
            "QMP arm/clear outside exact live worker gates")
    prepared = [(i, r["value"]) for i, r in enumerate(rows) if r["kind"] == "command-prepared"]
    sent = [(i, r["value"]) for i, r in enumerate(rows) if r["kind"] == "command-sent"]
    require(len(prepared) == len(sent) == len(GATES), "host command denominator")
    for (i, value), (j, sent_value), event in zip(prepared, sent, (e for e in cell["events"] if e["stage"] in GATES)):
        wanted = {key: event[key] for key in ("v", "unit", "case", "seq", "stage")}
        wanted["command"] = GATES[event["stage"]]
        require(_exact(value, {"command": wanted}) and _exact(sent_value, value)
                and indexes[event["stage"]] < i < j < host_events[event["seq"]][0], "host send out of gate/mismatched")
    state_positions = {}
    for kind, state, number in (("prepared", "prepared", 1), ("armed", "armed", 2),
                                ("before-clear", "armed", 2), ("cleared", "cleared", 3)):
        matched = [(i, r) for i, r in enumerate(rows) if r["kind"] == kind]
        require(len(matched) == 1 and matched[0][1]["value"].get("state") == state
                and matched[0][1]["state_epoch"] == number, "host state epoch transition missing")
        state_positions[kind] = matched[0][0]
    require(graph_indices[1] < state_positions["prepared"] < indexes["prepared"]
            and graph_indices[3] < state_positions["armed"] < indexes["candidate_hold"]
            and indexes["candidate_hold"] < state_positions["before-clear"] < graph_indices[4]
            and graph_indices[5] < state_positions["cleared"] < indexes["cleared_hold"],
            "resident state observation outside corresponding actual QMP transition")
    prepared_positions = {value["command"]["stage"]: position for position, value in prepared}
    require(state_positions["armed"] < prepared_positions["before_candidate_hold"]
            and state_positions["cleared"] < prepared_positions["candidate_hold"],
            "host acknowledgement precedes actual completed arm/clear observation")
    outcome = rows[state_positions["cleared"]]["value"].get("clear_outcome")
    require(_exact(outcome, {"attempted": True, "arguments": {
        "options": [{"driver": "raw", "node-name": binding["raw_node"], "file": binding["file_node"]}]},
        "response_received": True, "response": clear_response, "error": None, "graph_verified": True,
        "recording_complete": True, "observation_errors": []}), "cleared state lacks exact successful restoration/recording proof")
    observation = cell["events"][0]["observation"]
    actual = observation.get("volume_binding")
    require(type(actual) is dict and actual.get("device_serial") == binding["device_serial"]
            and actual.get("root") == binding["root"] and actual.get("unit") == binding["unit"]
            and all(_integer(actual.get(key), 0, 2**32 - 1) for key in ("disk_number", "partition_number"))
            and actual.get("filesystem") == "NTFS" and actual.get("is_boot") is False and actual.get("is_system") is False
            and type(actual.get("volume_unique_id")) is str and actual["volume_unique_id"], "actual guest volume inventory differs")
    serials = []
    for value in (actual.get("volume_serial"), binding["volume_serial"]):
        require(type(value) is str and re.fullmatch(r"[0-9A-Fa-f]{1,8}", value.replace("-", "")), "native volume serial format")
        serials.append(int(value.replace("-", ""), 16))
    require(serials[0] == serials[1] == accepted._bridge(observation["write_probe"]["before"])["volume_serial_u32"]
            and _digest(observation.get("volume_binding_file_sha256")), "same-FD volume bridge/inventory differs")
    requests = [(i, row["value"]) for i, row in enumerate(rows) if row["kind"] == "http-request"]
    responses = [(i, row["value"]) for i, row in enumerate(rows) if row["kind"] == "http-response"]
    if requests or responses or plan.get("parent_transport") == "bounded-http-current-parent-v1":
        require(len(requests) == len(responses) == len(cell["events"]), "HTTP raw event/response denominator")
        for (lower, request), (upper, response), (position, event) in zip(requests, responses, host_events):
            require(type(request) is dict and set(request) == {"method", "path", "body_hex"}
                    and request["method"] == "POST" and request["path"] == "/event/" + binding["unit"]
                    and _exact(_outer_event(_hex(request["body_hex"], 262144), event["seq"], binding["unit"], case), event)
                    and lower < position < upper, "HTTP raw event binding/order")
            require(type(response) is dict and set(response) == {"status", "body_hex"}
                    and type(response["status"]) is int and response["status"] == 200, "HTTP raw response status")
            raw = _hex(response["body_hex"], 1024)
            if event["stage"] in GATES:
                wanted = {key: event[key] for key in ("v", "unit", "case", "seq", "stage")}
                wanted["command"] = GATES[event["stage"]]
                require(raw.endswith(b"\n") and _exact(_json(raw), wanted), "HTTP acknowledgement bytes differ")
                sent_position = next(i for i, value in sent if value["command"]["stage"] == event["stage"])
                prepared_position = next(i for i, value in prepared if value["command"]["stage"] == event["stage"])
                require(prepared_position < upper < sent_position, "HTTP sent claimed before actual response write/flush")
            else:
                require(raw == b"{}\n", "HTTP noncommand response changed")
        assets = [row["value"] for row in rows if row["kind"] == "http-assets"]
        require(len(assets) == 1 and type(assets[0]) is dict and set(assets[0]) == {
            "port", "assets", "artifacts", "required_files", "require_export", "export_timeout"}
                and _integer(assets[0]["port"], 1, 65535) and _exact(assets[0]["assets"], plan.get("http_assets"))
                and _exact({k: assets[0][k] for k in ("artifacts", "required_files", "require_export", "export_timeout")},
                           plan.get("http_export")),
                "HTTP served assets differ from exact plan")
        export = assets[0]
        require(export["require_export"] is True and type(export["artifacts"]) is dict
                and set(export["artifacts"]) == EXPORT_NAMES and type(export["required_files"]) is list
                and export["required_files"] == sorted(REQUIRED_EXPORT_NAMES)
                and all(_integer(bound, 0, 16 * 1048576) for bound in export["artifacts"].values()),
                "HTTP actual export not required/bounded")
        uploaded = [(i, row["value"]) for i, row in enumerate(rows) if row["kind"] == "http-artifact"]
        completed = [(i, row["value"]) for i, row in enumerate(rows) if row["kind"] == "http-export"]
        require(len(completed) == 1, "HTTP export completion missing/duplicate")
        completion_index, manifest = completed[0]
        require(type(manifest) is dict and set(manifest) == {"schema", "exit_confirmed", "files", "missing"}
                and manifest["schema"] == "imageinfo-0219-http-export-v1" and manifest["exit_confirmed"] is True
                and type(manifest["files"]) is list and type(manifest["missing"]) is list
                and len(manifest["files"]) + len(manifest["missing"]) == len(export["artifacts"])
                and indexes["final"] < completion_index, "HTTP completed export denominator/lifetime")
        received = {}
        total = 0
        for position, value in uploaded:
            require(type(value) is dict and set(value) == {"name", "bytes", "sha256"}
                    and type(value["name"]) is str and value["name"] in export["artifacts"] and value["name"] not in received
                    and _integer(value["bytes"], 0, export["artifacts"][value["name"]]) and _digest(value["sha256"])
                    and indexes["exited"] < position < completion_index, "HTTP artifact transfer binding/lifetime")
            raw = _read(accepted._bounded_path(Path(host_path).parent, value["name"]), 16 * 1048576)
            require(len(raw) == value["bytes"] and _sha(raw) == value["sha256"], "HTTP retained upload bytes changed")
            total += len(raw)
            received[value["name"]] = value
        require(total <= 64 * 1048576, "HTTP cumulative retained upload bound")
        names = []
        for item in manifest["files"]:
            require(type(item) is dict and set(item) == {"name", "bytes", "sha256", "guest_path"}
                    and type(item["guest_path"]) is str and item["guest_path"]
                    and _exact({k: item[k] for k in ("name", "bytes", "sha256")}, received.get(item["name"])),
                    "HTTP export manifest differs from actual received bytes")
            names.append(item["name"])
        require(set(names) >= set(export["required_files"]), "HTTP required raw captures absent")
        for item in manifest["missing"]:
            require(type(item) is dict and set(item) == {"name", "status", "error", "guest_path"}
                    and item["name"] in export["artifacts"] and item["name"] not in received
                    and item["status"] in ("absent", "error") and type(item["guest_path"]) is str
                    and (item["error"] is None or type(item["error"]) is dict), "HTTP missing artifact classification")
            names.append(item["name"])
        require(len(names) == len(set(names)) and set(names) == set(export["artifacts"]), "HTTP omitted/duplicate artifact")
        fixture = cell["fixture"]
        path_type = PureWindowsPath if "\\" in fixture["root"] else PurePosixPath
        guest_paths = {"source.bin": fixture["source"], "old-source.bin": fixture["old"],
                       **{name: str(path_type(fixture["root"]) / "unit" / name) for name in (
                           "candidate.bin", "output.bin", "prepared.record", "intent.record", "observation.record", "receipt.record")}}
        request = cell["guest"].get("request", {})
        attempt = request.get("attempt_dir")
        require(type(attempt) is str and attempt, "actual guest capture directory missing")
        guest_paths.update({name: str(path_type(attempt) / name) for name in REQUIRED_EXPORT_NAMES if name != "volume-binding.json"})
        guest_paths["volume-binding.json"] = request.get("volume_binding_path")
        for item in manifest["files"] + manifest["missing"]:
            require(item["guest_path"] == guest_paths[item["name"]], "HTTP export guest path differs from executed request/fixture")
    return {"rows": rows, "controller_epoch": epoch, "binding": binding, "rule": rule,
            "first_ns": rows[0]["monotonic_ns"], "last_ns": rows[-1]["monotonic_ns"]}


def audit_inputs(plan_path, freeze_path, review_path):
    """Recheck immutable source/build/runtime/config pins; no saved authority."""
    plan_raw, freeze_raw, review_raw = (_read(path, 1048576) for path in (plan_path, freeze_path, review_path))
    plan, frozen, review = map(_json, (plan_raw, freeze_raw, review_raw))
    require(type(frozen) is dict and set(frozen) == {"schema", "root", "git_commit", "source_encoding",
            "worker", "plan", "inputs", "sources"} and frozen["schema"] == "namespace-guest-contrast-freeze-v1"
            and frozen["source_encoding"] == "git-lf-v1", "freeze schema")
    root = Path(frozen["root"])
    require(root.is_absolute() and root.is_dir(), "source root unavailable")
    expected = {p.relative_to(root).as_posix() for folder in ("src", "crates")
                for p in (root / folder).rglob("*.rs") if p.is_file()}
    expected.update(p.relative_to(root).as_posix() for p in (root / "crates").rglob("Cargo.toml") if p.is_file())
    expected.update(("Cargo.toml", "Cargo.lock", ".gitattributes"))
    expected.update(name for name in ("build.rs", ".cargo/config", ".cargo/config.toml", "rust-toolchain", "rust-toolchain.toml")
                    if (root / name).is_file())
    for folder in ("experiments/0218-namespace-observer", "experiments/0219-namespace-guest-contrast"):
        expected.update(p.relative_to(root).as_posix() for p in (root / folder).glob("*.py") if p.is_file())
    expected.update(p.relative_to(root).as_posix() for pattern in ("*.ps1", "*.sh")
                    for p in (root / "experiments/0219-namespace-guest-contrast").glob(pattern) if p.is_file())
    required = {"src/storage/namespace_diagnostic.rs", "src/storage/namespace_guest_diagnostic.rs", "src/storage/runtime.rs", "src/storage/windows.rs",
                "crates/imageinfo-windows-storage/src/native.rs", "crates/imageinfo-windows-storage/src/windows.rs"}
    required.add("experiments/0219-namespace-guest-contrast/guest_bootstrap.ps1")
    required.update("experiments/0219-namespace-guest-contrast/" + name + ".py" for name in (
        "audit", "freeze", "fixtures", "protocol", "guest_collector", "host_controller"))
    require(required <= expected, "required source/runtime/SDK missing")
    sources = frozen["sources"]
    require(type(sources) is list and 0 < len(sources) <= 512
            and [row.get("path") if type(row) is dict else None for row in sources] == sorted(expected),
            "source omitted/duplicate/inventory changed")
    for entry in sources:
        accepted._file_binding(entry, accepted._bounded_path(root, entry["path"]), 4194304, source=True)
    accepted._committed_sources(root, sorted(expected), frozen["git_commit"])
    accepted._file_binding(frozen["worker"], frozen["worker"]["path"], 268435456)
    require(Path(frozen["plan"]["path"]).resolve() == Path(plan_path).resolve(), "selected plan changed")
    accepted._file_binding(frozen["plan"], plan_path, 1048576)
    require(type(plan) is dict and plan.get("schema") == "namespace-guest-contrast-plan-v1", "plan schema")
    _false_flags(plan)
    argv = plan.get("argv")
    require(plan.get("worker_test_name") == WORKER_TEST and type(argv) is list and len(argv) == 6
            and all(type(arg) is str and 0 < len(arg) <= 32768 for arg in argv)
            and set(argv[1:]) == {"--exact", WORKER_TEST, "--ignored", "--nocapture", "--test-threads=1"},
            "exact reviewed guest worker invocation missing/changed")
    require(_exact(plan.get("marker"), {"source_bytes": 16777216, "source_fill": 83,
                                        "candidate_bytes": 4194304, "candidate_fill": 24})
            and _exact(plan.get("fault"), {**RULE, "sector": None, "arm_stage": "create-Candidate", "arm_seq": 9}),
            "markers/historical fault plan changed")
    cases = plan.get("cases")
    require(type(cases) is list and len(cases) == 2 and [row.get("case") for row in cases] == list(CASES)
            and all(type(row.get("unit")) is str and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", row["unit"])
                    and _guest_path(row.get("root")) for row in cases)
            and cases[0]["unit"] != cases[1]["unit"] and cases[0]["root"].casefold() != cases[1]["root"].casefold(),
            "two fresh serial cases required")
    accepted._bounds(plan.get("bounds"))
    inputs = frozen.get("inputs")
    require(type(inputs) is dict and set(inputs) == {"build_record", "runtime_inventory", "disk_configuration", "controller_source"}
            and type(plan.get("freeze_inputs")) is dict and set(plan["freeze_inputs"]) == set(inputs), "input pins missing")
    loaded = {}
    for key, entry in inputs.items():
        require(type(entry) is dict and entry.get("path") == plan["freeze_inputs"][key], "pinned input selection changed")
        raw = accepted._file_binding(entry, entry["path"], 1048576)
        if key != "controller_source":
            loaded[key] = _json(raw)
    build = loaded["build_record"]
    require(type(build) is dict and build.get("source_commit") == frozen["git_commit"]
            and build.get("worker_sha256") == frozen["worker"]["sha256"]
            and type(build.get("argv")) is list and 0 < len(build["argv"]) <= 64
            and all(type(arg) is str and 0 < len(arg) <= 32768 for arg in build["argv"])
            and all(type(build.get(k)) is str and build[k] for k in ("target", "compiler")), "source/worker/build linkage")
    require(type(plan.get("identities")) is dict and set(plan["identities"]) == {"guest", "disk", "volume"}
            and _exact(loaded["disk_configuration"].get("identities"), plan["identities"]), "disk configuration identity differs")
    _identities(plan["identities"])
    for row in cases:
        _identities(row.get("identities", plan["identities"]))
        _planned_volume(row, row.get("identities", plan["identities"]))
    if any("identities" in row for row in cases):
        require(_exact(loaded["disk_configuration"].get("cases"), {
            row["case"]: row.get("identities", plan["identities"]) for row in cases}), "per-cell disk configuration differs")
    resident = plan.get("resident_expected")
    require(type(resident) is dict and set(resident) == {"controller", "guest"}
            and type(resident["controller"]) is dict and set(resident["controller"]) == set(CASES), "resident per-cell expectations missing")
    epochs = []
    for value in resident["controller"].values():
        require(type(value) is dict and set(value) == {"controller_epoch", "code_sha256", "python"}
                and type(value["controller_epoch"]) is str and re.fullmatch(r"[0-9a-f]{32}", value["controller_epoch"])
                and _digest(value["code_sha256"]) and type(value["python"]) is dict and value["python"],
                "resident controller expected fields")
        epochs.append(value["controller_epoch"])
    require(len(set(epochs)) == 2, "controller epoch reused across cells")
    guest = resident["guest"]
    require(type(guest) is dict and set(guest) == {"implementation", "version", "platform", "stat_profile", "code_sha256", "files"}
            and guest.get("implementation") == "cpython" and guest.get("platform") == "win32"
            and guest.get("stat_profile") == "cpython-3.14.7-windows-path-creation-handle-change-v1"
            and _digest(guest.get("code_sha256")) and type(guest.get("files")) is dict
            and 3 <= len(guest["files"]) <= 512 and all(_guest_path(k) and _digest(v) for k, v in guest["files"].items())
            and len({str(PureWindowsPath(k)).casefold() for k in guest["files"]}) == len(guest["files"]),
            "guest resident runtime/bridge fields")
    require(guest["files"].get(argv[0]) == frozen["worker"]["sha256"], "planned guest worker path/digest differs")
    inventory = loaded["runtime_inventory"]
    require(type(inventory) is dict and _exact(inventory.get("guest"), guest)
            and _exact(inventory.get("controller_python"), {case: resident["controller"][case]["python"] for case in CASES}),
            "runtime inventory differs from actual reviewed expectations")
    controller_source = next(row for row in sources if row["path"] == "experiments/0219-namespace-guest-contrast/host_controller.py")
    require(frozen["inputs"]["controller_source"]["sha256"] == controller_source["sha256"]
            and frozen["inputs"]["controller_source"]["bytes"] == controller_source["bytes"],
            "controller input differs from immutable published source")
    require(type(review) is dict and set(review) == {"schema", "decision", "scope", "reviewer", "plan_sha256", "freeze_sha256"}
            and review["schema"] == "namespace-guest-contrast-review-v1" and review["decision"] == "approved"
            and review["scope"] == "two-serial-cells-only" and type(review["reviewer"]) is str and review["reviewer"]
            and review["plan_sha256"] == _sha(plan_raw) and review["freeze_sha256"] == _sha(freeze_raw),
            "documentary independent review does not bind exact inputs")
    return {"plan": plan, "freeze": frozen, "plan_sha256": _sha(plan_raw), "freeze_sha256": _sha(freeze_raw),
            "review_sha256": _sha(review_raw), "runtime_inventory": loaded["runtime_inventory"]}


def audit_artifacts(artifact_path, cell):
    """Hash retained guest copies without converting guest identities to host IDs."""
    manifest = _load(artifact_path, 1048576)
    require(type(manifest) is dict and set(manifest) == {"schema", "entries"}
            and manifest["schema"] == "imageinfo-0219-artifacts-v1" and type(manifest["entries"]) is list
            and len(manifest["entries"]) <= 32, "artifact transfer manifest")
    root, final = Path(artifact_path).parent, cell["final"]
    expected = {snapshot["path"]: snapshot for name, snapshot in final["paths"].items()
                if name != "preparedSource" and snapshot["status"] == "ok"}
    require([entry.get("guest_path") for entry in manifest["entries"]] == sorted(expected),
            "retained final artifact denominator differs")
    paths = []
    for entry in manifest["entries"]:
        require(type(entry) is dict and set(entry) == {"guest_path", "path", "bytes", "sha256"}, "artifact transfer fields")
        target = accepted._bounded_path(root, entry["path"])
        require(target != Path(artifact_path).resolve(), "artifact manifest aliases itself")
        paths.append(str(target))
        snapshot = expected[entry["guest_path"]]
        require(type(entry["bytes"]) is int and entry["bytes"] == snapshot["bytes_read"]
                and entry["sha256"] == snapshot["sha256"], "artifact copy differs from guest snapshot")
        raw = _read(target, 16 * 1048576)
        require(len(raw) == entry["bytes"] and _sha(raw) == entry["sha256"], "retained artifact bytes changed")
    require(len(paths) == len(set(paths)), "artifact copy alias reused")
    return manifest


def _parent_transport(value):
    require(type(value) is dict and set(value) == {"operations", "retained_threads", "poisoned", "replayed"}
            and type(value["retained_threads"]) is int and value["retained_threads"] == 0
            and value["poisoned"] is False and value["replayed"] is False
            and _exact(value["operations"], [{"stage": stage, "completed": True, "timed_out": False, "aborted": False}
                                             for stage in STAGES]), "guest parent HTTP state incomplete/poisoned/replayed")


def _planned_volume(selection, identities):
    """The reviewed cell owns both exact selection content and its byte digest."""
    value = selection.get("volume_plan")
    keys = {"unit", "fixture_relative", "min_disk_bytes", "max_disk_bytes", "label", "bus_type",
            "device_serial", "volume_serial", "volume_unique_id", "disk_number", "partition_number", "root"}
    require(type(value) is dict and set(value) == keys and _digest(selection.get("volume_plan_sha256")),
            "reviewed exact volume selection missing")
    require(value["unit"] == selection["unit"] and value["root"] == selection["root"]
            and value["device_serial"] == identities["disk"]["device_serial"]
            and value["volume_serial"] == identities["volume"]["volume_serial"],
            "reviewed volume selection differs from cell/controller")
    require(all(type(value[k]) is str and value[k] for k in ("fixture_relative", "label", "volume_unique_id"))
            and type(value["min_disk_bytes"]) is int and type(value["max_disk_bytes"]) is int
            and 33554432 <= value["min_disk_bytes"] <= value["max_disk_bytes"] <= 1073741824
            and _integer(value["disk_number"], 0, 2**32-1) and _integer(value["partition_number"], 1, 2**32-1)
            and value["bus_type"] == "USB", "reviewed volume selection geometry/identity missing")
    return value


def _volume_selection(actual, request, selection, identities, diagnostic_sha256):
    """Check actual captured bytes, both independent digests, and planned facts."""
    planned = _planned_volume(selection, identities)
    require(actual.get("plan_sha256") == diagnostic_sha256 and _digest(diagnostic_sha256),
            "actual volume capture selects another diagnostic plan")
    expected_sha = selection["volume_plan_sha256"]
    require(actual.get("volume_plan_sha256") == request.get("volume_plan_sha256") == expected_sha
            and _exact(request.get("volume_plan"), planned), "volume selection request/digests differ")
    encoded = actual.get("volume_plan_bytes_base64")
    require(type(encoded) is str and 0 < len(encoded) <= 21848, "actual volume selection bytes missing/bounded")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise AuditError("actual volume selection encoding invalid") from exc
    require(0 < len(raw) <= 16384 and _sha(raw) == expected_sha and _exact(_json(raw), planned),
            "actual volume selection bytes/hash/content differ from review")
    require(all(_exact(actual.get(key), planned[key]) for key in
                ("unit", "root", "device_serial", "volume_serial", "volume_unique_id", "disk_number", "partition_number")),
            "actual volume facts differ from reviewed selection")
    return raw


def _audit_cell(attempt_dir, inputs):
    root = Path(attempt_dir)
    cell = audit_guest(root)
    plan, frozen = inputs["plan"], inputs["freeze"]
    guest, worker = cell["guest"], cell["worker"]
    selected = next(row for row in plan["cases"] if row["case"] == guest["case"])
    require(guest["unit"] == selected["unit"] and cell["fixture"]["root"] == selected["root"], "cell differs from plan")
    request = guest.get("request")
    require(type(request) is dict and request.get("unit") == guest["unit"] and request.get("case") == guest["case"]
            and request.get("fixture_root") == selected["root"] and _exact(request.get("bounds"), plan["bounds"])
            and _exact(request.get("argv"), worker["transport"]["result"]["command"])
            and _exact(request.get("argv"), plan["argv"]) and request.get("worker_test_name") == plan["worker_test_name"],
            "guest request/transport differs from exact planned invocation")
    if plan.get("parent_transport") == "bounded-http-current-parent-v1":
        require(request.get("require_export") is True, "actual HTTP attempt did not require postexit export")
        _parent_transport(guest.get("parent_transport"))
    bindings = guest.get("bindings")
    require(type(bindings) is dict and all(bindings.get(key) == expected for key, expected in {
        "plan_sha256": inputs["plan_sha256"], "freeze_sha256": inputs["freeze_sha256"],
        "worker_sha256": frozen["worker"]["sha256"]}.items()) and _exact(request.get("bindings"), bindings), "cell exact input pins missing")
    runtime = plan["resident_expected"]["guest"]
    require(_exact(guest.get("observer_python"), {k: v for k, v in runtime.items() if k != "files"})
            and _exact(request.get("reviewed_files"), runtime["files"])
            and _exact(request.get("observer_python"), guest["observer_python"]), "actual resident guest code/runtime/file pins differ")
    require(_exact(guest.get("resident_guest"), runtime)
            and _exact(cell["events"][0]["observation"].get("resident_guest"), runtime),
            "actual captured resident guest code/runtime/files differ or are absent")
    require(type(request.get("argv")) is list and request["argv"] and runtime["files"].get(request["argv"][0]) == frozen["worker"]["sha256"],
            "guest selected worker differs from frozen worker")
    host = audit_host(root / "host.jsonl", cell, plan, inputs["plan_sha256"])
    controller_input = frozen["inputs"]["controller_source"]
    for row in host["rows"]:
        if row["kind"] in ("resident", "plan-bound", "prepared", "armed", "before-clear", "cleared"):
            resident = row["value"]
            require(resident.get("source_sha256") == controller_input["sha256"]
                    and type(resident.get("source_bytes")) is int and resident["source_bytes"] == controller_input["bytes"]
                    and _integer(resident.get("pid"), 1, 2**32 - 1)
                    and resident["pid"] == host["rows"][0]["value"]["pid"], "loaded controller source/process pin differs")
    volume_raw = _read(root / "volume-binding.json", 65536)
    prepared = cell["events"][0]["observation"]
    require(_sha(volume_raw) == prepared["volume_binding_file_sha256"]
            and _exact(_json(volume_raw), prepared["volume_binding"]), "retained actual volume capture differs")
    actual_volume = prepared["volume_binding"]
    _volume_selection(actual_volume, request, selected, selected.get("identities", plan["identities"]), inputs["plan_sha256"])
    require(actual_volume.get("drive_root") == cell["fixture"]["sourceVolumeRoot"],
            "actual bootstrap volume capture selects another drive root")
    artifacts = audit_artifacts(root / "artifacts.json", cell)
    return cell, host, artifacts


def audit(attempt_dir, plan_path, freeze_path, review_path):
    """Audit one retained cell; only audit_pair can accept the two-cell scope."""
    try:
        inputs = audit_inputs(plan_path, freeze_path, review_path)
        cell, host, _ = _audit_cell(attempt_dir, inputs)
        return _summary(cell, host, inputs)
    except AuditError:
        raise
    except (AttributeError, KeyError, TypeError, IndexError, OSError, OverflowError, RecursionError, ValueError) as exc:
        raise AuditError("malformed, changed or unavailable retained cell") from exc


def _summary(cell, host, inputs):
    candidate = cell["worker"]["candidate"]["result"]
    source = cell["final"]["paths"]["source"]
    failed = cell["worker"]["first_failed_operation"]
    return {"schema": "imageinfo-0219-independent-audit-v1", "passed": True,
            "case": cell["guest"]["case"], "unit": cell["guest"]["unit"],
            "controller_epoch": host["controller_epoch"], "plan_sha256": inputs["plan_sha256"],
            "freeze_sha256": inputs["freeze_sha256"], "review_sha256": inputs["review_sha256"],
            "worker_sha256": inputs["freeze"]["worker"]["sha256"],
            "candidate_sdk_result": candidate, "controller_injected_rule": host["rule"],
            "first_failed_operation": failed,
            "first_failed_operation_native_os_error_observed": failed is not None and failed["result"]["native_os_error"] is not None,
            "held_candidate_final_name": cell["held_candidate_final_name"],
            "sdk_error_is_controller_injection_record": False,
            "runtime": cell["worker"]["runtime"], "source_final_lookup_status": source["status"],
            "source_final_authored_bytes_match": source.get("sha256") == cell["fixture"]["sourceSha256"],
            "explicit_release_after_filter_clear_before_runtime_drop_exit": True,
            "causal_claim": "finite-ordered-observations-only; underlying cause unresolved",
            "candidate_sdk_native_error_433_observed": candidate.get("native_os_error") == 433,
            "three_native_flush_error_classes_qualified": False,
            "identity_bridge_profile": accepted.BRIDGE_PROFILE,
            "custody_basis": "explicit-current-owning-parent-transcript; hashes-alone-are-not-custody",
            **{flag: False for flag in FLAGS}}


def audit_pair(error_dir, control_dir, plan_path, freeze_path, review_path):
    """Require both serial fresh cells; never infer a missing or failed cell."""
    try:
        first_path, second_path = Path(error_dir).resolve(), Path(control_dir).resolve()
        require(first_path != second_path and first_path.parent == second_path.parent, "paired attempt directory reused/unbounded")
        inputs = audit_inputs(plan_path, freeze_path, review_path)
        pair_root = first_path.parent
        attempts = _lines(pair_root / "attempts.jsonl", 65536, 32)
        wanted = [{"seq": index, "case": case["case"], "unit": case["unit"], "attempt_dir": path.name}
                  for index, (case, path) in enumerate(zip(inputs["plan"]["cases"], (first_path, second_path)), 1)]
        require(_exact(attempts, wanted), "failed/extra/forgotten attempted cell denominator")
        directories = list(pair_root.iterdir())
        require(len(directories) <= 64, "pair directory inventory bound")
        retained = {path.resolve() for path in directories if path.is_dir()
                    and ((path / "guest.json").exists() or (path / "result.json").exists())}
        require(retained == {first_path, second_path}, "unlisted retained attempt omitted")
        first, first_host, _ = _audit_cell(error_dir, inputs)
        second, second_host, _ = _audit_cell(control_dir, inputs)
        require((first["guest"]["case"], second["guest"]["case"]) == CASES, "pair order differs")
        require(first_host["last_ns"] < second_host["first_ns"], "matched cells not serial")
        require(first_host["controller_epoch"] != second_host["controller_epoch"], "controller epoch reused")
        if (first_host["binding"]["disk_path"], first_host["binding"]["device_serial"]) == (
                second_host["binding"]["disk_path"], second_host["binding"]["device_serial"]):
            require(first["fixture"]["sourceIdentity"] != second["fixture"]["sourceIdentity"]
                    and first["fixture"]["rootIdentity"] != second["fixture"]["rootIdentity"], "fresh cell object identity reused on same disk")
        return {"schema": "imageinfo-0219-independent-pair-audit-v1", "passed": True,
                "cells": [_summary(first, first_host, inputs), _summary(second, second_host, inputs)],
                "attempts": 2, "serial": True, "underlying_cause_resolved": False,
                **{flag: False for flag in FLAGS}}
    except AuditError:
        raise
    except (AttributeError, KeyError, TypeError, IndexError, OSError, OverflowError, RecursionError, ValueError) as exc:
        raise AuditError("malformed, changed or unavailable retained pair") from exc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("error_dir")
    parser.add_argument("control_dir")
    parser.add_argument("--plan", required=True)
    parser.add_argument("--freeze", required=True)
    parser.add_argument("--review", required=True)
    args = parser.parse_args()
    try:
        result = audit_pair(args.error_dir, args.control_dir, args.plan, args.freeze, args.review)
    except AuditError as exc:
        print(json.dumps({"schema": "imageinfo-0219-independent-pair-audit-v1", "passed": False, "reason": str(exc)}))
        return 1
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


def _checked(function):
    @wraps(function)
    def bounded(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except AuditError:
            raise
        except (AttributeError, KeyError, TypeError, IndexError, OSError, OverflowError, RecursionError, ValueError) as exc:
            raise AuditError("malformed, changed or unavailable retained evidence") from exc
    return bounded


audit_worker = _checked(audit_worker)
audit_guest = _checked(audit_guest)
audit_host = _checked(audit_host)
audit_inputs = _checked(audit_inputs)
audit_artifacts = _checked(audit_artifacts)


if __name__ == "__main__":
    raise SystemExit(main())
