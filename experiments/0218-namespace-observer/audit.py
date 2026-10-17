"""Independent, read-only audit of retained #0218 observer attempts.

This auditor never imports or invokes the producer, worker, controller or probe.
The retained owning-parent transcript is evidence from an explicit trusted caller;
hash agreement alone supplies no live custody or historical authenticity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import subprocess


class AuditError(ValueError):
    """Retained evidence is incomplete, inconsistent or outside declared bounds."""


def require(condition, message):
    if not condition:
        raise AuditError(message)


def _object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON member")
        result[key] = value
    return result


def _json(raw):
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_object,
                          parse_constant=lambda _: (_ for _ in ()).throw(AuditError("nonfinite JSON")))
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise AuditError("invalid UTF-8 JSON") from exc


def _read(path, maximum):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), "missing/nonregular retained file")
    require(not getattr(path.lstat(), "st_file_attributes", 0) & 0x400, "retained reparse file refused")
    with path.open("rb") as handle:
        raw = handle.read(maximum + 1)
    require(len(raw) <= maximum, "retained file exceeds audit bound")
    return raw


def _load(path, maximum=1048576):
    return _json(_read(path, maximum))


def _lines(path, maximum=1048576, count=512):
    raw = _read(path, maximum)
    require(not raw or raw.endswith(b"\n"), "unterminated retained JSONL")
    lines = raw.splitlines()
    require(len(lines) <= count and all(lines), "JSONL line/count bound")
    return [_json(line) for line in lines]


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _integer(value, low=0, high=2**63 - 1):
    return type(value) is int and low <= value <= high


def _exact(left, right):
    """JSON equality that never equates booleans, numbers or their containers."""
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return set(left) == set(right) and all(_exact(left[key], right[key]) for key in left)
    if type(left) is list:
        return len(left) == len(right) and all(_exact(a, b) for a, b in zip(left, right))
    return left == right


def _hex(value, maximum):
    require(isinstance(value, str) and len(value) <= maximum * 2,
            "invalid hex capture bound")
    try:
        raw = bytes.fromhex(value)
    except ValueError as exc:
        raise AuditError("invalid hex capture") from exc
    require(raw.hex() == value, "noncanonical hex capture")
    return raw


def _bounded_path(root, name):
    require(isinstance(name, str) and name and "\\" not in name and ":" not in name,
            "invalid retained relative path")
    path = PurePosixPath(name)
    require(bool(path.parts) and not path.is_absolute() and str(path) == name
            and all(p not in (".", "..") for p in path.parts),
            "retained path escapes attempt")
    selected = root.joinpath(*path.parts)
    require(not selected.is_symlink(), "retained source alias refused")
    result = selected.resolve()
    require(result.is_relative_to(root.resolve()), "retained path escapes attempt")
    return result


def _bounds(value):
    require(isinstance(value, dict), "missing declared bounds")
    expected = {"deadline_seconds", "stdout_bytes", "stderr_bytes", "line_bytes", "events",
                "command_bytes", "commands"}
    require(set(value) == expected, "unexpected bounds schema")
    deadline = value["deadline_seconds"]
    require(type(deadline) in (int, float) and math.isfinite(deadline) and 0 < deadline <= 120,
            "deadline bound")
    for key in ("stdout_bytes", "stderr_bytes"):
        require(_integer(value[key], 1, 4194304), "capture bound")
    require(_integer(value["line_bytes"], 1, 32768), "line bound")
    require(_integer(value["command_bytes"], 1, 4096), "command byte bound")
    require(_integer(value["events"], 1, 256), "record count bound")
    require(_integer(value["commands"], 1, 128), "record count bound")
    return value


def _audit_transport(attempt_dir):
    """Reconcile raw transport, without treating success as native qualification."""
    root = Path(attempt_dir)
    result = _load(root / "result.json")
    require(result.get("schema") == "namespace-observer-run-v1", "run schema")
    bounds = _bounds(result.get("bounds"))
    stdout = _read(root / "stdout.bin", bounds["stdout_bytes"])
    stderr = _read(root / "stderr.bin", bounds["stderr_bytes"])
    events = _lines(root / "events.jsonl", count=bounds["events"])
    transcript = _lines(root / "transcript.jsonl", maximum=4 * 1048576, count=1024)
    require(result.get("status") == "transport_complete" and result.get("reason") == "child_exit_zero",
            "failed/incomplete transport is retained, never a qualified observation")
    require(type(result.get("exit_code")) is int and result["exit_code"] == 0 and result.get("child_killed") is False
            and result.get("replayed") is False and result.get("threads_stopped") is True,
            "child exit/lifecycle mismatch")
    require(result.get("exit_confirmed") is True and result.get("capture_drain_complete") is True
            and result.get("cleanup_errors") == [] and _integer(result.get("child_pid"), 1, 2**32 - 1),
            "child exit/capture/cleanup incomplete")
    elapsed = result.get("elapsed_seconds")
    require(type(elapsed) in (int, float) and math.isfinite(elapsed)
            and 0 <= elapsed <= bounds["deadline_seconds"], "elapsed deadline")
    require(type(result.get("stdout_bytes")) is int and type(result.get("stderr_bytes")) is int
            and result["stdout_bytes"] == len(stdout) and result["stderr_bytes"] == len(stderr),
            "raw capture length mismatch")
    raw_lines = []
    for index, event in enumerate(events, 1):
        require(set(event) == {"line", "bytes_hex"} and type(event["line"]) is int and event["line"] == index, "event line sequence")
        raw = _hex(event["bytes_hex"], bounds["line_bytes"])
        require(raw.endswith(b"\n") and b"\n" not in raw[:-1], "event line framing")
        raw_lines.append(raw)
    require(b"".join(raw_lines) == stdout and type(result.get("lines")) is int and result["lines"] == len(raw_lines),
            "raw stdout/event mismatch")
    require(transcript and transcript[0].get("kind") == "start", "missing transcript start")
    last_time = -1
    for index, row in enumerate(transcript, 1):
        require(set(row) == {"kind", "seq", "elapsed_ns", "child_alive", "value"}, "transcript schema")
        require(type(row["seq"]) is int and row["seq"] == index and _integer(row["elapsed_ns"]) and row["elapsed_ns"] >= last_time,
                "transcript order/time")
        require(type(row["child_alive"]) is bool, "invalid child alive observation")
        last_time = row["elapsed_ns"]
    require(_exact(transcript[0]["value"], {"command": result["command"], "bounds": bounds}),
            "start/result mismatch")
    received = [row for row in transcript if row["kind"] == "stdout_line"]
    require(_exact([row["value"] for row in received], [{"line": n} for n in range(1, len(events) + 1)]),
            "transcript/event receive mismatch")
    commands = [row for row in transcript if row["kind"] == "command_sent"]
    require(type(result.get("commands")) is int and len(commands) == result["commands"] <= bounds["commands"], "command count")
    for row in commands:
        require(set(row["value"]) == {"bytes_hex"}, "command transcript schema")
        raw = _hex(row["value"]["bytes_hex"], bounds["command_bytes"])
        require(raw.endswith(b"\n") and b"\n" not in raw[:-1] and row["child_alive"],
                "command framing/lifetime")
    exits = [row for row in transcript if row["kind"] == "exit"]
    require(len(exits) == 1 and exits[0]["child_alive"] is False, "actual child exit required")
    require(_exact(exits[0]["value"], {"exit_code": 0, "exit_confirmed": True,
                                     "status": "transport_complete", "reason": "child_exit_zero"}),
            "exit/result mismatch")
    require(all(row["seq"] < exits[0]["seq"] for row in received + commands), "post-exit transport event")
    return {"root": root, "result": result, "bounds": bounds, "stdout": stdout,
            "stderr": stderr, "raw_lines": raw_lines, "transcript": transcript,
            "commands": commands, "received": received, "exit": exits[0]}


def audit_transport(attempt_dir):
    try:
        return _audit_transport(attempt_dir)
    except AuditError:
        raise
    except (AttributeError, KeyError, TypeError, IndexError, OSError, RecursionError, ValueError) as exc:
        raise AuditError("malformed or unavailable retained transport") from exc


PREFIX = b"IMAGEINFO218 "
FLAGS = ("committed", "production_profile_admitted", "raw_admitted", "authority_importable")
NORMAL_STAGES = (
    "preflight", "create-root", "root-flush", "parent-flush", "create-Candidate",
    "check-CandidateChecked", "file-Candidate", "root-flush",
    "create-Prepared", "check-PreparedChecked", "file-Prepared", "root-flush",
    "create-Intent", "check-IntentChecked", "file-Intent", "root-flush",
    "release", "check-Prepublication", "publish", "check-Installed", "file-Candidate",
    "root-flush", "check-InstalledRechecked", "create-Observation", "check-ObservationChecked",
    "file-Observation", "root-flush", "create-Receipt", "check-ReceiptChecked", "file-Receipt",
    "check-ReceiptFileChecked", "root-flush", "check-ReceiptParentChecked", "checked-context",
    "check-Final", "terminal",
)


def _protocol(transport, cell, unit):
    """Independent exact finite two-cell event/command/order reconciliation."""
    stages = NORMAL_STAGES if cell == "normal" else NORMAL_STAGES[:5]
    expected = []
    for stage in stages:
        expected.extend((("before_operation", stage),
                         ("candidate_result" if stage == "create-Candidate" else "operation_result", stage)))
    expected.extend((("runtime_result", "runtime"), ("backend_dropped", "backend-drop")))
    events, positions = [], []
    for line, receive in zip(transport["raw_lines"], transport["received"]):
        harness_prefix = b"test storage::namespace_diagnostic::local_namespace_diagnostic_worker ... "
        if line.startswith(harness_prefix + PREFIX):
            line = line[len(harness_prefix):]
        if not line.startswith(PREFIX):
            require(line in (b"\n", b"running 1 test\n", b"ok\n", harness_prefix + b"\n") or re.fullmatch(
                rb"test result: ok\. 1 passed; 0 failed; 0 ignored; 0 measured; [0-9]+ filtered out; finished in [0-9.]+s\n", line),
                "unrecognized harness output")
            continue  # libtest output has no protocol authority.
        require(len(line) <= 32768 and b"\r" not in line and b"\n" not in line[:-1], "event framing/bound")
        event = _json(line[len(PREFIX):-1])
        require(isinstance(event, dict) and set(event) == {
            "v", "unit", "seq", "kind", "stage", "result", "bindings", *FLAGS}, "event schema")
        require(type(event["v"]) is int and event["v"] == 1
                and type(event["seq"]) is int and event["seq"] == len(events) + 1,
                "diagnostic version/sequence")
        require(event["unit"] == unit and all(event[f] is False for f in FLAGS), "unit/admission mismatch")
        bindings = event["bindings"]
        require(type(bindings) is list and len(bindings) <= 7, "binding bound")
        for binding in bindings:
            require(type(binding) is dict and set(binding) == {"identity", "facts"}, "binding schema")
            for key, maximum in (("identity", 512), ("facts", 16384)):
                value = binding[key]
                require(isinstance(value, str) and 0 < len(value) <= maximum
                        and re.fullmatch(r"(?:[0-9a-f]{2})+", value), "binding encoding")
        events.append(event)
        positions.append(receive["seq"])
    require(len(events) == len(expected) <= 128, "missing/extra diagnostic events")
    require([(e["kind"], e["stage"]) for e in events] == expected, "operation order differs")
    required_commands = []
    candidate = None
    for index, event in enumerate(events):
        kind, result = event["kind"], event["result"]
        if kind in ("before_operation", "backend_dropped"):
            require(result is None, "nonresult event has result")
        elif kind in ("operation_result", "candidate_result"):
            require(type(result) is dict and set(result) == {
                "success", "failure", "native_error_kind", "native_os_error"}, "operation result schema")
            failed = cell == "candidate-collision" and kind == "candidate_result"
            require(result["success"] is (not failed), "unexpected operation outcome")
            if failed:
                require(result["failure"] == "Conflict" and type(result["native_os_error"]) is int
                        and -(2**31) <= result["native_os_error"] < 2**31,
                        "collision must retain actual native error")
                require(type(result["native_error_kind"]) is str and 0 < len(result["native_error_kind"]) <= 128
                        and all(32 <= ord(char) <= 126 for char in result["native_error_kind"]),
                        "collision missing actual error kind")
            else:
                require(result["failure"] is None and result["native_error_kind"] is None
                        and result["native_os_error"] is None, "unexpected success error fields")
        if kind in ("before_operation", "candidate_result"):
            command = {key: event[key] for key in ("v", "unit", "seq", "stage")}
            command["command"] = "release" if kind == "candidate_result" else "continue"
            required_commands.append((command, positions[index], positions[index + 1]))
        if kind == "candidate_result":
            candidate = {"event": event, "receive_seq": positions[index], "before_receive_seq": positions[index - 1]}
    require(len(transport["commands"]) == len(required_commands), "missing/extra acknowledgements")
    for sent, (wanted, lower, upper) in zip(transport["commands"], required_commands):
        raw = _hex(sent["value"]["bytes_hex"], 1024)
        require(b"\r" not in raw and _exact(_json(raw[:-1]), wanted), "stale/duplicate/wrong acknowledgement")
        require(lower < sent["seq"] < upper, "acknowledgement outside its actual event gate")
        if wanted["command"] == "release":
            candidate["release_seq"] = sent["seq"]
    runtime = events[-2]["result"]
    require(type(runtime) is dict and set(runtime) == {
        "status", "phase", "failure", "publication_possible", "release_possible", "protocol_complete",
        "retained_material", "pending_cleanup", "charged_bytes"}, "runtime result schema")
    for key in ("publication_possible", "release_possible", "protocol_complete", "retained_material", "pending_cleanup"):
        require(type(runtime[key]) is bool, "runtime boolean type")
    require(_integer(runtime["charged_bytes"], 0, 2**64 - 1), "runtime charge bound")
    require(positions[-2] < positions[-1] < transport["exit"]["seq"], "runtime/drop/exit order")
    return events, runtime, candidate


def _snapshot(snapshot, source, source_hash, source_bytes):
    require(type(snapshot) is dict and snapshot.get("path") == source
            and snapshot.get("status") == "ok" and snapshot.get("error") is None
            and snapshot.get("reason") is None and snapshot.get("observations_match") is True,
            "source snapshot unsuccessful")
    require(snapshot.get("sha256") == source_hash and snapshot.get("bytes_read") == source_bytes
            and _integer(snapshot.get("max_bytes"), source_bytes, 16 * 1024 * 1024),
            "source snapshot bytes/bound mismatch")
    stats = [snapshot.get(key) for key in ("path_before", "handle_before", "handle_after", "path_after")]
    require(all(type(value) is dict and set(value) == {
        "device", "inode", "mode", "size", "mtime_ns", "ctime_ns"} for value in stats),
        "snapshot stat schema")
    require(all(value == stats[0] for value in stats) and stats[0]["size"] == source_bytes,
            "source snapshot identity/stat mismatch")
    require(all(_integer(value) for value in stats[0].values()), "source stat field type")
    return stats[0]


def _probe(probe, expected_access, source, source_hash, source_bytes):
    require(type(probe) is dict and probe.get("path") == source
            and probe.get("expected_access") is expected_access, "probe target/expectation mismatch")
    before = _snapshot(probe.get("before"), source, source_hash, source_bytes)
    after = _snapshot(probe.get("after"), source, source_hash, source_bytes)
    require(before == after and probe.get("source_unchanged") is True
            and probe.get("expectation_met") is True and probe.get("close_error") is None,
            "probe changed source or failed expectation")
    flags = probe.get("flags")
    # MSVCRT O_WRONLY=1, O_BINARY=32768. Create/truncate/append are forbidden.
    require(type(flags) is int and flags == 32769, "probe is not the reviewed nonwriting open")
    if expected_access:
        require(probe.get("status") == "opened" and probe.get("error") is None
                and probe.get("opened_stat") == before and probe.get("denial_observation") is None,
                "access-open evidence missing")
    else:
        error = probe.get("error")
        require(probe.get("status") == "open_error" and probe.get("opened_stat") is None
                and type(error) is dict and set(error) == {"type", "errno", "winerror"}
                and ((type(error["winerror"]) is int and error["winerror"] == 32)
                     or (error["winerror"] is None and type(error["errno"]) is int and error["errno"] == 13)),
                "held observation lacks actual access denial")
        expected_denial = "win32_sharing_violation" if error["winerror"] == 32 else "crt_eacces_without_native_error"
        require(probe.get("denial_observation") == expected_denial, "probe error classification differs from raw fields")
    return before


def _probe_timeline(transport, candidate, fixture):
    starts = [row for row in transport["transcript"] if row["kind"] == "probe_begin"]
    ends = [row for row in transport["transcript"] if row["kind"] == "probe_end"]
    phases = ("baseline", "held", "after_exit")
    require(len(starts) == len(ends) == 3, "exact three probe phases required")
    stats, probes = [], []
    for phase, begin, end in zip(phases, starts, ends):
        require(begin["value"] == {"phase": phase} and type(end["value"]) is dict
                and set(end["value"]) == {"phase", "probe"} and end["value"]["phase"] == phase,
                "probe phase schema/order")
        require(begin["seq"] < end["seq"], "probe begin/end order")
        require(begin["child_alive"] is (phase == "held")
                and end["child_alive"] is (phase == "held"), "probe lifetime observation mismatch")
        probe = end["value"]["probe"]
        stats.append(_probe(probe, phase != "held", fixture["source"], fixture["sourceSha256"], fixture["sourceBytes"]))
        probes.append(probe)
    require(ends[0]["seq"] < transport["received"][0]["seq"], "baseline probe after worker event")
    require(candidate["receive_seq"] < starts[1]["seq"] < ends[1]["seq"] < candidate["release_seq"],
            "held probe outside actual candidate-result gate")
    by_seq = {row["seq"]: row for row in transport["transcript"]}
    require(by_seq[candidate["release_seq"]]["elapsed_ns"] - by_seq[candidate["receive_seq"]]["elapsed_ns"]
            <= 15_000_000_000, "candidate-result release exceeded worker gate deadline")
    require(transport["exit"]["seq"] < starts[2]["seq"], "after-exit probe before actual exit")
    require(all(value == stats[0] for value in stats), "source identity/properties changed across probes")
    require({"device": stats[0]["device"], "inode": stats[0]["inode"]}
            == fixture["sourceIdentity"], "probes differ from original source identity")
    return probes


def _absent(snapshot, path):
    require(type(snapshot) is dict and snapshot.get("path") == path and snapshot.get("status") == "error"
            and type(snapshot.get("error")) is dict and snapshot["error"].get("errno") == 2
            and snapshot.get("bytes_read") == 0 and snapshot.get("sha256") is None,
            "absent artifact snapshot lacks actual missing-file result")


def _collision_binding(collision, fixture, unit_identity, candidate_identity):
    require(type(collision) is dict and set(collision) == {
        "schema", "case", "root", "unitIdentity", "candidate", "bytes", "sha256", "identity", "event", "preserveForeign"}
        and collision["schema"] == "imageinfo-0218-collision-v1" and collision["case"] == "candidate-collision"
        and collision["root"] == fixture["root"] and collision["candidate"] == fixture["candidate"]
        and _exact(collision["unitIdentity"], unit_identity) and _exact(collision["identity"], candidate_identity),
        "collision declaration contradicts actual fixture/unit/candidate")
    foreign = b"imageinfo-0218 foreign candidate collision v1\n"
    require(collision["sha256"] == _sha(foreign) and type(collision["bytes"]) is int
            and collision["bytes"] == len(foreign) and collision["preserveForeign"] is True,
            "foreign collision declaration bytes changed")


def _file_binding(entry, path, maximum, *, source=False):
    require(type(entry) is dict and set(entry) == {"path", "bytes", "sha256"}, "file binding schema")
    require(_integer(entry["bytes"], 0, maximum), "file binding size")
    raw = _read(path, maximum)
    require(not source or b"\r" not in raw, "source differs from exact Git LF bytes")
    require(entry["bytes"] == len(raw) and entry["sha256"] == _sha(raw), "file binding changed")
    return raw


def _input_bindings(native, plan_path, freeze_path, review_path, transport):
    freeze_raw = _read(freeze_path, 262144)
    require(_sha(freeze_raw) == native.get("freeze_sha256"), "freeze digest mismatch")
    frozen = _json(freeze_raw)
    require(type(frozen) is dict and set(frozen) == {
        "schema", "root", "git_commit", "source_encoding", "worker", "plan", "sources"}, "freeze schema")
    require(frozen["schema"] == "namespace-observer-freeze-v1"
            and frozen["source_encoding"] == "git-lf-v1", "freeze version")
    source_root = Path(frozen["root"])
    require(source_root.is_absolute() and source_root.is_dir(), "source root missing")
    sources = frozen["sources"]
    require(type(sources) is list and 0 < len(sources) <= 256, "source inventory bound")
    expected = {p.relative_to(source_root).as_posix() for p in (source_root / "src").rglob("*.rs") if p.is_file()}
    expected.update(p.relative_to(source_root).as_posix() for p in (source_root / "crates").rglob("*.rs") if p.is_file())
    expected.update(p.relative_to(source_root).as_posix() for p in (source_root / "crates").rglob("Cargo.toml") if p.is_file())
    observer = source_root / "experiments/0218-namespace-observer"
    expected.update(p.relative_to(source_root).as_posix() for p in observer.glob("*.py") if p.is_file())
    expected.update(("Cargo.toml", "Cargo.lock", ".gitattributes"))
    expected.update(name for name in ("build.rs", ".cargo/config", ".cargo/config.toml", "rust-toolchain", "rust-toolchain.toml") if (source_root / name).is_file())
    required = {"src/storage/namespace_diagnostic.rs", "src/storage/windows.rs", "src/storage/runtime.rs",
                "crates/imageinfo-windows-storage/Cargo.toml", "crates/imageinfo-windows-storage/src/lib.rs",
                "crates/imageinfo-windows-storage/src/native.rs", "crates/imageinfo-windows-storage/src/windows.rs"}
    required.update("experiments/0218-namespace-observer/" + name + ".py"
                    for name in ("freeze", "protocol", "controller", "run", "audit", "fixtures", "probe"))
    require(required <= expected, "required diagnostic/runtime/SDK source absent")
    names = [entry.get("path") if type(entry) is dict else None for entry in sources]
    require(names == sorted(expected), "source omitted/duplicate/inventory changed")
    for entry in sources:
        _file_binding(entry, _bounded_path(source_root, entry["path"]), 4194304, source=True)
    _committed_sources(source_root, names, frozen["git_commit"])
    require(Path(frozen["worker"]["path"]).resolve() == Path(native["worker_path"]).resolve(), "worker selection changed")
    _file_binding(frozen["worker"], native["worker_path"], 268435456)
    require(frozen["worker"]["sha256"] == native["worker_sha256"], "worker digest mismatch")
    require(Path(frozen["plan"]["path"]).resolve() == Path(plan_path).resolve(), "plan selection changed")
    plan_raw = _file_binding(frozen["plan"], plan_path, 262144)
    require(_sha(plan_raw) == native["plan_sha256"], "plan digest mismatch")
    plan = _json(plan_raw)
    require(plan.get("schema") == "namespace-observer-plan-v1"
            and plan.get("cases") == ["normal", "candidate-collision"], "exact two-cell plan required")
    require(_exact(plan.get("bounds"), transport["bounds"]) and _exact(plan.get("argv"), transport["result"]["command"]),
            "executed argv/bounds differ from plan")
    require(Path(plan["argv"][0]).resolve() == Path(native["worker_path"]).resolve()
            and Path(plan["executable"]).resolve() == Path(native["worker_path"]).resolve(), "plan worker mismatch")
    review_raw = _read(review_path, 262144)
    require(_sha(review_raw) == native["review_sha256"], "review digest mismatch")
    review = _json(review_raw)
    require(type(review) is dict and set(review) == {
        "schema", "decision", "scope", "reviewer", "plan_sha256", "freeze_sha256"}, "review schema")
    require(review["schema"] == "namespace-observer-review-v1" and review["decision"] == "approved"
            and review["scope"] == "two-native-controls-only" and type(review["reviewer"]) is str
            and 0 < len(review["reviewer"]) <= 128, "missing explicit current caller review record")
    require(review["plan_sha256"] == native["plan_sha256"]
            and review["freeze_sha256"] == native["freeze_sha256"], "review targets different inputs")
    return frozen, plan


def _committed_sources(root, names, commit):
    require(type(commit) is str and re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", commit), "invalid source commit")
    def query(arguments):
        try:
            result = subprocess.run(["git", "--no-optional-locks", *arguments], cwd=root,
                                    capture_output=True, timeout=15, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise AuditError("read-only source identity query failed") from exc
        require(result.returncode == 0 and len(result.stdout) <= 262144, "source identity query failed/bounded")
        return result.stdout
    require(query(["rev-parse", "--verify", commit + "^{commit}"]).strip().decode("ascii") == commit,
            "frozen source commit unavailable")
    raw = query(["ls-tree", "-rz", "--full-tree", commit, "--", *names])
    entries = {}
    for line in raw.split(b"\0"):
        if not line:
            continue
        meta, name = line.split(b"\t", 1)
        mode, kind, oid = meta.split(b" ")
        name = name.decode("utf-8")
        require(name not in entries and mode in (b"100644", b"100755") and kind == b"blob", "nonregular/duplicate source blob")
        entries[name] = oid.decode("ascii")
    require(set(entries) == set(names), "committed source inventory mismatch")
    for name in names:
        raw = _read(_bounded_path(root, name), 4194304)
        blob = b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw
        oid = entries[name]
        require(len(oid) in (40, 64), "source object algorithm unsupported")
        actual = hashlib.sha1(blob).hexdigest() if len(oid) == 40 else hashlib.sha256(blob).hexdigest()
        require(oid == actual, "source differs from committed raw blob")


def _repeated_hash(byte, count):
    digest = hashlib.sha256()
    block = bytes((byte,)) * 65536
    while count:
        piece = block[:min(count, len(block))]
        digest.update(piece)
        count -= len(piece)
    return digest.hexdigest()


def _artifacts(native, transport):
    fixture = native["fixture_before"]
    require(type(fixture) is dict and fixture.get("schema") == "imageinfo-0218-fixture-v1"
            and fixture.get("case") == native["cell"] and fixture.get("unit") == native["request"]["unit"],
            "fixture declaration mismatch")
    root = Path(fixture["root"])
    require(root.is_absolute() and root == Path(native["request"]["fixture_root"]), "fixture root mismatch")
    require(fixture.get("authoredOnly") is True and fixture.get("cleanupAuthorized") is False
            and fixture.get("unitInitiallyAbsent") is True and fixture.get("outputExpectedAbsent") is True,
            "fixture scope/effect declaration mismatch")
    require(fixture.get("sourceBytes") == 16 * 1024 * 1024 and fixture.get("candidateBytes") == 4 * 1024 * 1024
            and fixture.get("sourceByte") == 0x53 and fixture.get("candidateByte") == 0x18,
            "fixture content parameters changed")
    source_hash = _repeated_hash(0x53, fixture["sourceBytes"])
    candidate_hash = _repeated_hash(0x18, fixture["candidateBytes"])
    require(fixture.get("sourceSha256") == source_hash and fixture.get("candidateSha256") == candidate_hash,
            "fixture authored byte digest mismatch")
    require(Path(fixture["source"]) == root / "source.bin" and Path(fixture["candidate"]) == root / "unit/candidate.bin"
            and Path(fixture["output"]) == root / "unit/output.bin", "fixture artifact names changed")
    require(_read(root / "fixture218.marker", 128) == b"imageinfo-0218-disposable-authored-only-v1\n", "fixture marker changed")
    require(_load(root / "fixture.private.json", 8192) == fixture, "fixture declaration changed")
    expected_root = {"source.bin", "fixture218.marker", "fixture.private.json", "unit"}
    if native["cell"] == "candidate-collision":
        expected_root.add("collision.private.json")
    require({path.name for path in root.iterdir()} == expected_root and not (root / "unit").is_symlink(),
            "unexpected fixture root artifacts/alias")
    source = _read(fixture["source"], fixture["sourceBytes"])
    require(len(source) == fixture["sourceBytes"] and _sha(source) == source_hash, "current source bytes changed")
    info = root.stat()
    require(fixture.get("rootIdentity") == {"device": info.st_dev, "inode": info.st_ino}, "fixture root identity changed")
    info = Path(fixture["source"]).stat()
    require(fixture.get("sourceIdentity") == {"device": info.st_dev, "inode": info.st_ino}, "source identity changed")
    after = native["fixture_after"]
    require(type(after) is dict and set(after) == {"source", "candidate", "output", "unit_files"}, "artifact snapshot schema")
    checkpoints = [row for row in transport["transcript"] if row["kind"] == "artifact_checkpoint"]
    require(len(checkpoints) == 1 and checkpoints[0]["value"] == after
            and checkpoints[0]["seq"] > transport["exit"]["seq"] and not checkpoints[0]["child_alive"],
            "artifact checkpoint not after actual exit")
    _snapshot(after["source"], fixture["source"], source_hash, fixture["sourceBytes"])
    if native["cell"] == "normal":
        _absent(after["candidate"], fixture["candidate"])
        _snapshot(after["output"], fixture["output"], candidate_hash, fixture["candidateBytes"])
    else:
        foreign = b"imageinfo-0218 foreign candidate collision v1\n"
        _absent(after["output"], fixture["output"])
        _snapshot(after["candidate"], fixture["candidate"], _sha(foreign), len(foreign))
    files = after["unit_files"]
    require(type(files) is list and len(files) <= 6, "unit inventory bound")
    names = [entry.get("name") if type(entry) is dict else None for entry in files]
    wanted = ["intent.record", "observation.record", "output.bin", "prepared.record", "receipt.record"] if native["cell"] == "normal" else ["candidate.bin"]
    require(names == wanted and sorted(p.name for p in (root / "unit").iterdir()) == wanted,
            "actual unit artifact names differ from finite outcome")
    for entry in files:
        require(set(entry) == {"name", "bytes", "sha256", "identity"}, "artifact inventory schema")
        maximum = 4194304 if entry["name"].endswith(".bin") else 65536
        path = root / "unit" / entry["name"]
        raw = _read(path, maximum)
        info = path.stat()
        require(len(raw) == entry["bytes"] and _sha(raw) == entry["sha256"]
                and entry["identity"] == {"device": info.st_dev, "inode": info.st_ino}, "current artifact binding changed")
        if entry["name"] == "output.bin":
            require(len(raw) == fixture["candidateBytes"] and _sha(raw) == candidate_hash, "output authored bytes mismatch")
    if native["cell"] == "candidate-collision":
        collision = native.get("collision")
        require(type(collision) is dict and _load(root / "collision.private.json", 65536) == collision,
                "missing/changed collision declaration")
        unit_info = (root / "unit").stat()
        _collision_binding(collision, fixture, {"device": unit_info.st_dev, "inode": unit_info.st_ino}, files[0]["identity"])
        foreign = b"imageinfo-0218 foreign candidate collision v1\n"
        require(_read(fixture["candidate"], 65536) == foreign,
                "foreign collision bytes changed")
    else:
        require(native.get("collision") is None and not (root / "collision.private.json").exists(), "unexpected collision")
    return fixture, files


def _held_binding(binding, identity, size, sha256=None):
    """Decode only the documented finite in-process observation encoding."""
    raw = bytes.fromhex(binding["facts"])
    header = b"imageinfo-held-object-v1\0"
    require(raw.startswith(header) and len(raw) >= len(header) + 64, "held facts encoding")
    values = [int.from_bytes(raw[len(header) + n * 8:len(header) + (n + 1) * 8], "little") for n in range(8)]
    require(values[0] == identity["device"] and values[1] == identity["inode"] and values[2] == size,
            "held observation identity/size differs from artifact")
    require(bytes.fromhex(binding["identity"]) == raw[len(header):len(header) + 16], "binding identity/facts differ")
    end = len(header) + 64 + values[7]
    require(end <= len(raw), "held security text bound")
    if sha256 is not None:
        require(raw[end:] == bytes.fromhex(sha256), "held observation content digest differs")


def _bindings(events, fixture, files):
    held = []
    for event in events:
        if event["kind"] == "backend_dropped":
            require(event["bindings"] == [], "drop retained unexpected bindings")
            continue
        growing = event["kind"] in ("operation_result", "candidate_result") and event["result"]["success"] and (
            event["stage"] in ("preflight", "create-root") or event["stage"].startswith("create-"))
        current = event["bindings"]
        require(current[:len(held)] == held and len(current) == len(held) + int(growing),
                "held binding history changed or unexpected binding count")
        held = current
    _held_binding(held[0], fixture["sourceIdentity"], fixture["sourceBytes"], fixture["sourceSha256"])
    unit_info = Path(fixture["candidate"]).parent.stat()
    # Directory size/properties can change during protocol operations; identity
    # linkage is historical, while native backend checks own live exclusions.
    root_binding = held[1]
    raw_identity = bytes.fromhex(root_binding["identity"])
    require(raw_identity == unit_info.st_dev.to_bytes(8, "little") + unit_info.st_ino.to_bytes(8, "little"),
            "held transaction root identity differs")
    if len(held) > 2:
        entries = {entry["name"]: entry for entry in files}
        for binding, name in zip(held[2:], ("output.bin", "prepared.record", "intent.record", "observation.record", "receipt.record")):
            entry = entries[name]
            _held_binding(binding, entry["identity"], entry["bytes"], entry["sha256"])


def _audit(attempt_dir, plan_path=None, freeze_path=None, review_path=None):
    transport = audit_transport(attempt_dir)
    native = _load(Path(attempt_dir) / "native.json", 4 * 1048576)
    require(type(native) is dict and native.get("schema") == "imageinfo-0218-native-v1", "native schema")
    require(native.get("cell") in ("normal", "candidate-collision")
            and all(native.get(flag) is False for flag in FLAGS), "native cell/admission mismatch")
    require(native.get("protocol_complete") is True and native.get("transport_status") == "transport_complete",
            "observer protocol incomplete")
    require(type(native.get("request")) is dict and set(native["request"]) == {"unit", "fixture_root"}, "request schema")
    spawned = [row for row in transport["transcript"] if row["kind"] == "child_started"]
    require(len(spawned) == 1 and spawned[0]["child_alive"]
            and type(spawned[0]["value"]) is dict and set(spawned[0]["value"]) == {"pid"}
            and _integer(spawned[0]["value"]["pid"], 1, 2**32 - 1)
            and spawned[0]["value"]["pid"] == transport["result"]["child_pid"]
            and spawned[0]["seq"] < transport["received"][0]["seq"], "actual owned child identity missing")
    unit = native["request"]["unit"]
    require(type(unit) is str and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", unit), "invalid event unit")
    frozen, plan = _input_bindings(native, plan_path or native["plan_path"],
                                   freeze_path or native["freeze_path"], review_path or native["review_path"], transport)
    require(not transport["stderr"], "unexpected worker stderr")
    events, runtime, candidate = _protocol(transport, native["cell"], unit)
    require(type(native.get("protocol_events")) is int and native["protocol_events"] == len(events), "protocol event count mismatch")
    normal = native["cell"] == "normal"
    expected_runtime = {
        "status": "Refused" if normal else "Conflict",
        "phase": "TerminalExport" if normal else "CandidateCreated",
        "failure": None if normal else "Conflict",
        "publication_possible": normal, "release_possible": normal, "protocol_complete": normal,
        "retained_material": True, "pending_cleanup": True, "charged_bytes": 4718592,
    }
    require(runtime == expected_runtime, "runtime outcome differs from predeclared finite control")
    fixture, files = _artifacts(native, transport)
    probes = _probe_timeline(transport, candidate, fixture)
    baseline_end = next(row for row in transport["transcript"] if row["kind"] == "probe_end"
                        and row["value"]["phase"] == "baseline")
    require(baseline_end["seq"] < spawned[0]["seq"], "baseline probe after actual child spawn")
    require(native["fixture_after"]["source"]["path_before"] == probes[-1]["after"]["path_before"],
            "final source snapshot changed after postexit probe")
    require(native["observations"] == [{"phase": phase, "probe": probe} for phase, probe in zip(
        ("baseline", "held", "after_exit"), probes)], "native/transcript probe mismatch")
    _bindings(events, fixture, files)
    copies = [row["value"] for row in transport["transcript"] if row["kind"] == "protocol_event"]
    require(copies == events, "retained protocol event copies differ from raw bytes")
    checkpoints = [row for row in transport["transcript"] if row["kind"] == "candidate_checkpoint"]
    require(len(checkpoints) == 1 and checkpoints[0]["value"] == candidate["event"]
            and candidate["receive_seq"] < checkpoints[0]["seq"] < candidate["release_seq"]
            and checkpoints[0]["child_alive"], "candidate checkpoint mismatch")
    held_artifacts = [row for row in transport["transcript"] if row["kind"] == "held_artifact_checkpoint"]
    require(len(held_artifacts) == 1 and held_artifacts[0]["value"] == native.get("held_candidate")
            and candidate["receive_seq"] < held_artifacts[0]["seq"] < candidate["release_seq"]
            and held_artifacts[0]["child_alive"], "held artifact observation outside candidate gate")
    held_candidate = native["held_candidate"]
    require(type(held_candidate) is dict and held_candidate.get("path") == fixture["candidate"],
            "held artifact target differs")
    if held_candidate.get("status") == "ok":
        held_hash = fixture["candidateSha256"] if normal else _sha(b"imageinfo-0218 foreign candidate collision v1\n")
        held_size = fixture["candidateBytes"] if normal else len(b"imageinfo-0218 foreign candidate collision v1\n")
        observed_stat = _snapshot(held_candidate, fixture["candidate"], held_hash, held_size)
        expected_file = next(entry for entry in files if entry["name"] == ("output.bin" if normal else "candidate.bin"))
        require({"device": observed_stat["device"], "inode": observed_stat["inode"]} == expected_file["identity"],
                "held candidate identity differs from final actual artifact")
    else:
        require(held_candidate.get("status") in ("error", "refused")
                and (type(held_candidate.get("error")) is dict or type(held_candidate.get("reason")) is str),
                "held artifact failure lacks actual error/refusal")
    collision_rows = [row for row in transport["transcript"] if row["kind"] in ("collision_begin", "collision_end")]
    if normal:
        require(not collision_rows, "normal control injected collision")
    else:
        require(len(collision_rows) == 2 and collision_rows[0]["kind"] == "collision_begin"
                and collision_rows[0]["value"] == {"event_seq": 9}
                and collision_rows[1]["kind"] == "collision_end" and collision_rows[1]["value"] == native["collision"]
                and native["collision"].get("event") == events[8]
                and all(row["child_alive"] for row in collision_rows), "collision observation missing")
        sent_before = next(row for row in transport["commands"] if _json(bytes.fromhex(row["value"]["bytes_hex"]))["seq"] == 9)
        require(candidate["receive_seq"] > sent_before["seq"] > collision_rows[1]["seq"]
                > collision_rows[0]["seq"] > candidate["before_receive_seq"], "collision injection outside pre-call gate")
    return {
        "schema": "imageinfo-0218-independent-audit-v1", "passed": True, "cell": native["cell"],
        "disposition": "normal-unqualified-protocol-complete" if normal else "native-candidate-collision-before-publication",
        "runtime": runtime, "candidate_result": candidate["event"]["result"], "protocol_events": len(events),
        "worker_sha256": native["worker_sha256"], "plan_sha256": native["plan_sha256"],
        "freeze_sha256": native["freeze_sha256"], "review_sha256": native["review_sha256"],
        "source_name_and_bytes_preserved": True, "foreign_bytes_preserved": True if not normal else None,
        "source_write_open_denied_while_paused": True, "held_probe_error": probes[1]["error"],
        "held_candidate_observation_status": held_candidate["status"],
        "explicit_release_before_runtime_drop_and_exit": True,
        "custody_basis": "explicit-current-owning-parent-stdio-transcript; hashes-alone-are-not-custody",
        "failed_temporary_sdk_handles_claimed_live": False,
        "historical_433_or_storage_full_qualified": False, **{flag: False for flag in FLAGS},
    }


def audit(attempt_dir, plan_path=None, freeze_path=None, review_path=None):
    """Return the finite result or refuse; preserve all input and partial files."""
    try:
        return _audit(attempt_dir, plan_path, freeze_path, review_path)
    except AuditError:
        raise
    except (AttributeError, KeyError, TypeError, IndexError, OSError, OverflowError, RecursionError, ValueError) as exc:
        raise AuditError("malformed, changed or unavailable retained evidence") from exc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("attempt_dir")
    parser.add_argument("--plan")
    parser.add_argument("--freeze")
    parser.add_argument("--review")
    args = parser.parse_args()
    try:
        result = audit(args.attempt_dir, args.plan, args.freeze, args.review)
    except AuditError as error:
        print(json.dumps({"schema": "imageinfo-0218-independent-audit-v1", "passed": False, "reason": str(error)}))
        return 1
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
