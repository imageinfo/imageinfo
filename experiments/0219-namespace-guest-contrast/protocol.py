"""Pure finite #0219 outer exchange; decoded records import no authority.

The current parent owns actual controller effects and pipe delivery. This module
reuses #0218 framing and worker validation without changing its accepted wire.
"""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path

_path = Path(__file__).resolve().parents[1] / "0218-namespace-observer" / "protocol.py"
_spec = importlib.util.spec_from_file_location("namespace_218_protocol_for_219", _path)
worker_protocol = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(worker_protocol)
ProtocolError = worker_protocol.ProtocolError
FLAGS = worker_protocol.FLAGS
PREFIX = b"IMAGEINFO219 "
MAX_EVENT_BYTES = 262144
MAX_COMMAND_BYTES = 1024
MAX_EVENTS = 12
CASES = frozenset(("persistent-write-error", "no-error"))
STAGES = ("prepared", "source_reopened_hold", "before_candidate_hold", "candidate_hold", "cleared_hold",
          "released", "runtime_result", "backend_dropped", "exited", "final")
COMMANDS = {"prepared": "start", "source_reopened_hold": "continue", "before_candidate_hold": "armed",
            "candidate_hold": "cleared", "cleared_hold": "release"}
_require = worker_protocol._require
_keys = worker_protocol._keys


def _envelope(value):
    _require(type(value["v"]) is int and value["v"] == 1, "unsupported version")
    _require(type(value["unit"]) is str and worker_protocol._UNIT.fullmatch(value["unit"]), "invalid unit")
    _require(type(value["case"]) is str and value["case"] in CASES, "invalid case")
    _require(type(value["seq"]) is int and 1 <= value["seq"] <= MAX_EVENTS, "invalid sequence")
    _require(type(value["stage"]) is str and value["stage"] in (*STAGES, "failure"), "invalid stage")


def validate_event(event):
    _keys(event, ("v", "unit", "case", "seq", "stage", "observation", "worker_event", *FLAGS))
    _envelope(event)
    _require(all(event[key] is False for key in FLAGS), "positive or missing admission flag")
    _require(type(event["observation"]) is dict and bool(event["observation"]), "missing raw observation")
    try:
        size = len(json.dumps(event, allow_nan=False, ensure_ascii=True).encode("ascii"))
    except (TypeError, ValueError, RecursionError) as exc:
        raise ProtocolError("invalid observation JSON") from exc
    _require(size + len(PREFIX) + 1 <= MAX_EVENT_BYTES, "observation exceeds bound")
    stage, worker = event["stage"], event["worker_event"]
    expected = {"source_reopened_hold": ("before_operation", "create-root"),
                "before_candidate_hold": ("before_operation", "create-Candidate"),
                "candidate_hold": ("candidate_result", "create-Candidate"),
                "cleared_hold": ("candidate_result", "create-Candidate"),
                "released": ("candidate_result", "create-Candidate"),
                "runtime_result": ("runtime_result", "runtime"),
                "backend_dropped": ("backend_dropped", "backend-drop")}.get(stage)
    if expected:
        worker_protocol.validate_event(worker)
        _require(worker["unit"] == event["unit"], "worker unit mismatch")
        _require((worker["kind"], worker["stage"]) == expected, "wrong worker phase")
        if stage == "source_reopened_hold":
            _require(worker["seq"] == 3 and bool(worker["bindings"]), "missing reopened source binding")
        if stage == "before_candidate_hold":
            _require(worker["seq"] == 9 and bool(worker["bindings"]), "missing held pre-candidate binding")
        if stage in ("candidate_hold", "cleared_hold", "released"):
            _require(worker["seq"] == 10 and bool(worker["bindings"]), "missing candidate held binding")
    else:
        _require(worker is None, "unexpected worker event")
    if stage == "exited":
        _require(event["observation"].get("exit_confirmed") is True, "exit not confirmed")
        _require(type(event["observation"].get("exit_code")) is int, "missing actual exit code")
    return event


def parse_event(raw):
    return validate_event(worker_protocol._decode(raw, MAX_EVENT_BYTES, PREFIX))


def encode_event(event):
    validate_event(event)
    raw = PREFIX + json.dumps(event, separators=(",", ":"), allow_nan=False).encode("utf-8") + b"\n"
    parse_event(raw)
    return raw


def parse_command(raw):
    value = worker_protocol._decode(raw, MAX_COMMAND_BYTES)
    _keys(value, ("v", "unit", "case", "seq", "stage", "command"))
    _envelope(value)
    expected = COMMANDS.get(value["stage"])
    _require(expected is not None and value["command"] in (expected, "cancel"), "command outside gate")
    return value


def encode_command(event, command):
    validate_event(event)
    value = {key: event[key] for key in ("v", "unit", "case", "seq", "stage")}
    value["command"] = command
    raw = json.dumps(value, separators=(",", ":"), allow_nan=False).encode("utf-8") + b"\n"
    parse_command(raw)
    return raw


def validate_command(raw, event):
    validate_event(event)
    value = parse_command(raw)
    _require(all(value[key] == event[key] for key in ("v", "unit", "case", "seq", "stage")), "command binding mismatch")
    return value


class Session:
    """One attempt. Call accept_command only after actual send/receive.

    This checks claimed order, not QMP effects, live handles, probe meanings or
    delivery. Auditing separately binds those raw observations and operations.
    Any malformed/out-of-order input permanently refuses this session.
    """
    def __init__(self, unit, case):
        self.unit, self.case = unit, case
        self.sequence = 0
        self.index = 0
        self.pending = None
        self.refused = False
        self.complete = False
        self._candidate = None
        self._failure_reported = False

    def _check(self, action, *, allow_failure=False):
        try:
            _require(not self.complete and (not self.refused or
                     (allow_failure and not self._failure_reported)), "terminal session")
            return action()
        except (ProtocolError, TypeError, KeyError, ValueError) as exc:
            self.refused = True
            raise ProtocolError(str(exc)) from exc

    def accept_event(self, event):
        def accept():
            validate_event(event)
            _require(event["unit"] == self.unit and event["case"] == self.case, "changed attempt identity")
            _require(event["seq"] == self.sequence + 1, "stale duplicate or skipped event")
            stage = event["stage"]
            if stage == "failure":
                self.refused = True
                self.pending = None
                self._failure_reported = True
                self.sequence += 1
                return deepcopy(event)
            _require(self.pending is None, "event before gate command")
            _require(self.index < len(STAGES) and stage == STAGES[self.index], "out-of-order phase")
            if stage == "candidate_hold":
                self._candidate = deepcopy(event["worker_event"])
            if stage in ("cleared_hold", "released"):
                _require(event["worker_event"] == self._candidate, "changed held candidate event")
            self.sequence += 1
            self.index += 1
            if stage in COMMANDS:
                self.pending = deepcopy(event)
            self.complete = stage == "final"
            return deepcopy(event)
        failure = type(event) is dict and event.get("stage") == "failure"
        return self._check(accept, allow_failure=failure)

    def emit(self, stage, observation, worker_event=None):
        event = {"v": 1, "unit": self.unit, "case": self.case, "seq": self.sequence + 1,
                 "stage": stage, "observation": observation, "worker_event": worker_event,
                 **{key: False for key in FLAGS}}
        return self.accept_event(event)

    def accept_command(self, raw):
        def accept():
            _require(self.pending is not None, "command without live gate")
            value = validate_command(raw, self.pending)
            self.pending = None
            if value["command"] == "cancel":
                self.refused = True
            return value
        return self._check(accept)

    def fail(self, observation):
        """Retain one terminal failure even after a refusal/cancelled gate."""
        _require(not self.complete and not self._failure_reported, "failure already terminal")
        event = {"v": 1, "unit": self.unit, "case": self.case, "seq": self.sequence + 1,
                 "stage": "failure", "observation": observation, "worker_event": None,
                 **{key: False for key in FLAGS}}
        validate_event(event)
        self.sequence += 1
        self.pending = None
        self.refused = True
        self._failure_reported = True
        return deepcopy(event)
