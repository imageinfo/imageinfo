"""Bounded #0218 diagnostic transport. Records confer no ownership or admission.

The current owning parent controls an owned child's stdin/stdout. This module
validates syntax and sequence; controller.py owns operation/lifetime ordering.
"""
import json
import re

PREFIX = b"IMAGEINFO218 "
MAX_EVENT_BYTES = 32768
MAX_COMMAND_BYTES = 1024
MAX_EVENTS = 128
GATE_TIMEOUT_SECONDS = 15
MAX_BINDINGS = 7
FLAGS = ("committed", "production_profile_admitted", "raw_admitted", "authority_importable")
PHASES = frozenset("Preflight SourceRead RootCreated RootFlushed ParentFlushed CandidateCreated CandidateChecked CandidateFlushed CandidateParentFlushed PreparedCreated PreparedChecked PreparedFlushed PreparedParentFlushed IntentCreated IntentChecked IntentFlushed IntentParentFlushed CallerRelease Prepublication Publish Installed InstalledFlushed InstalledParentFlushed InstalledRechecked ObservationCreated ObservationChecked ObservationFlushed ObservationParentFlushed ReceiptCreated ReceiptChecked ReceiptFlushed ReceiptFileChecked ReceiptParentFlushed ReceiptParentChecked CheckedContext Final TerminalExport".split())
ARTIFACTS = ("Candidate", "Prepared", "Intent", "Observation", "Receipt")
STAGES = frozenset(("preflight", "create-root", "root-flush", "parent-flush", "publish", "release", "checked-context", "terminal", "runtime", "backend-drop")) | frozenset("create-" + a for a in ARTIFACTS) | frozenset("file-" + a for a in ARTIFACTS) | frozenset("check-" + p for p in PHASES)
KINDS = frozenset(("before_operation", "operation_result", "candidate_result", "runtime_result", "backend_dropped", "gate_error"))
GATE_ERRORS = frozenset("Eof TooLong Malformed Mismatch Cancelled Timeout Io EventBound Output".split())
FAILURES = frozenset("LengthOverflow CandidateTooLarge BudgetExhausted StorageUnavailable ShortSource OverlongSource SourceIo Cancelled BackendIo Unsupported Conflict Ambiguous InvalidBinding RecordTooLarge CallerHistory".split())
STATUSES = frozenset("Unchanged Refused Conflict FailedBeforePublish CancelledBeforePublish RecoveryRequired".split())
_UNIT = re.compile(r"[A-Za-z0-9_-]{1,64}\Z", re.ASCII)
_HEX = re.compile(r"(?:[0-9a-f]{2})+\Z", re.ASCII)


class ProtocolError(ValueError):
    """Untrusted or unsupported diagnostic record."""


def _require(condition, message):
    if not condition:
        raise ProtocolError(message)


def _keys(value, expected):
    _require(type(value) is dict and set(value) == set(expected), "unknown or missing keys")


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def _decode(raw, limit, prefix=b""):
    _require(type(raw) is bytes, "line must be bytes")
    _require(0 < len(raw) <= limit and raw.endswith(b"\n"), "line length or missing LF")
    _require(raw.startswith(prefix), "wrong prefix")
    payload = raw[len(prefix):-1]
    _require(b"\n" not in payload and b"\r" not in payload, "embedded line break")
    try:
        return json.loads(payload.decode("utf-8"), object_pairs_hook=_pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(ProtocolError("nonfinite JSON")))
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ProtocolError("invalid JSON line") from exc


def _envelope(value):
    _require(type(value["v"]) is int and value["v"] == 1, "unsupported version")
    _require(type(value["unit"]) is str and _UNIT.fullmatch(value["unit"]), "invalid unit")
    _require(type(value["seq"]) is int and 1 <= value["seq"] <= MAX_EVENTS, "invalid sequence")
    _require(type(value["stage"]) is str and value["stage"] in STAGES, "unknown stage")


def _nullable_text(value, maximum=128):
    return value is None or (type(value) is str and 0 < len(value) <= maximum and all(32 <= ord(c) <= 126 for c in value))


def validate_event(event):
    """Return the same dictionary after exact shape/type validation."""
    _keys(event, ("v", "unit", "seq", "kind", "stage", "result", "bindings", *FLAGS))
    _envelope(event)
    _require(type(event["kind"]) is str and event["kind"] in KINDS, "unknown event kind")
    _require(all(event[f] is False for f in FLAGS), "positive authority/admission flag")
    bindings = event["bindings"]
    _require(type(bindings) is list and len(bindings) <= MAX_BINDINGS, "invalid bindings")
    for binding in bindings:
        _keys(binding, ("identity", "facts"))
        for key, limit in (("identity", 512), ("facts", 16384)):
            value = binding[key]
            _require(type(value) is str and len(value) <= limit and _HEX.fullmatch(value), "invalid binding hex")
    result, kind, stage = event["result"], event["kind"], event["stage"]
    _require((kind == "runtime_result") == (stage == "runtime"), "runtime stage mismatch")
    _require((kind == "backend_dropped") == (stage == "backend-drop"), "drop stage mismatch")
    if kind in ("before_operation", "backend_dropped"):
        _require(result is None, "unexpected result")
    elif kind == "gate_error":
        _keys(result, ("error", "rejected_seq", "rejected_stage"))
        _require(type(result["error"]) is str and result["error"] in GATE_ERRORS, "invalid gate error")
        _require(type(result["rejected_seq"]) is int and 1 <= result["rejected_seq"] < event["seq"], "invalid rejected sequence")
        _require(result["rejected_stage"] == stage, "invalid rejected stage")
    elif kind in ("operation_result", "candidate_result"):
        _require((kind == "candidate_result") == (stage == "create-Candidate"), "candidate event mismatch")
        _keys(result, ("success", "failure", "native_error_kind", "native_os_error"))
        _require(type(result["success"]) is bool, "invalid success")
        _require(result["failure"] is None or (type(result["failure"]) is str and result["failure"] in FAILURES), "invalid failure")
        _require(result["success"] == (result["failure"] is None), "inconsistent result")
        _require(_nullable_text(result["native_error_kind"]), "invalid native error kind")
        code = result["native_os_error"]
        _require(code is None or (type(code) is int and -(2**31) <= code < 2**31), "invalid OS error")
    else:
        _keys(result, ("status", "phase", "failure", "publication_possible", "release_possible", "protocol_complete", "retained_material", "pending_cleanup", "charged_bytes"))
        _require(type(result["status"]) is str and result["status"] in STATUSES, "invalid status")
        _require(type(result["phase"]) is str and result["phase"] in PHASES, "invalid phase")
        _require(result["failure"] is None or (type(result["failure"]) is str and result["failure"] in FAILURES), "invalid runtime failure")
        for key in ("publication_possible", "release_possible", "protocol_complete", "retained_material", "pending_cleanup"):
            _require(type(result[key]) is bool, "invalid result boolean")
        _require(type(result["charged_bytes"]) is int and 0 <= result["charged_bytes"] < 2**64, "invalid charge")
    return event


def parse_event(raw):
    return validate_event(_decode(raw, MAX_EVENT_BYTES, PREFIX))


def parse_command(raw):
    command = _decode(raw, MAX_COMMAND_BYTES)
    _keys(command, ("v", "unit", "seq", "stage", "command"))
    _envelope(command)
    _require(type(command["command"]) is str and command["command"] in ("continue", "release", "cancel"), "unknown command")
    return command


def encode_command(event, command):
    """Bind an explicit parent command to its exact pause event."""
    validate_event(event)
    expected = {"before_operation": "continue", "candidate_result": "release"}.get(event["kind"])
    _require(expected is not None and command in (expected, "cancel"), "command not permitted at event")
    value = {key: event[key] for key in ("v", "unit", "seq", "stage")}
    value["command"] = command
    raw = json.dumps(value, separators=(",", ":"), allow_nan=False).encode("utf-8") + b"\n"
    parse_command(raw)
    return raw


def validate_command(raw, event):
    """Check command correspondence without inferring that it was delivered."""
    validate_event(event)
    command = parse_command(raw)
    _require(all(command[key] == event[key] for key in ("v", "unit", "seq", "stage")), "command event mismatch")
    expected = {"before_operation": "continue", "candidate_result": "release"}.get(event["kind"])
    _require(expected is not None and command["command"] in (expected, "cancel"), "wrong command for event")
    return command


class EventStream:
    """Contiguous attempt-local sequence validation; no authority is imported."""
    def __init__(self, unit=None):
        self.unit = unit
        self.sequence = 0

    def accept(self, raw):
        event = parse_event(raw)
        _require(event["seq"] == self.sequence + 1, "stale, duplicate or skipped event")
        _require(self.unit is None or event["unit"] == self.unit, "changed unit")
        self.unit = event["unit"]
        self.sequence = event["seq"]
        return event
