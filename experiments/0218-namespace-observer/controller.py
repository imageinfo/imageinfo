"""Pure owned-child event/ack controller for the #0218 diagnostic.

An action is a request to the caller, never an effect. In particular, observing
the candidate result does not release its gate. The caller must finish its
observation, send and flush the matching command, then report that send here.
This state machine grants no ownership or storage admission authority.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from protocol import ProtocolError, validate_event


class ControllerError(ValueError):
    """The current attempt cannot form a complete ordered observation."""


# Repeated operation names are positional. This is the unchanged runtime order,
# not a new execution protocol or a claim that any operation must succeed.
OPERATIONS = (
    "preflight", "create-root", "root-flush", "parent-flush",
    "create-Candidate", "check-CandidateChecked", "file-Candidate", "root-flush",
    "create-Prepared", "check-PreparedChecked", "file-Prepared", "root-flush",
    "create-Intent", "check-IntentChecked", "file-Intent", "root-flush",
    "release", "check-Prepublication", "publish", "check-Installed",
    "file-Candidate", "root-flush", "check-InstalledRechecked",
    "create-Observation", "check-ObservationChecked", "file-Observation", "root-flush",
    "create-Receipt", "check-ReceiptChecked", "file-Receipt",
    "check-ReceiptFileChecked", "root-flush", "check-ReceiptParentChecked",
    "checked-context", "check-Final", "terminal",
)


@dataclass(frozen=True)
class Action:
    kind: str
    event: dict
    command: str | None = None


class Controller:
    """One finite attempt, with no I/O, clocks, child creation or cleanup.

    ``accept`` takes protocol-validated event dictionaries. It also checks the
    fields used for ordering, so accidental direct callers cannot skip gates.
    Any rejected transition poisons the attempt; instantiate a new controller
    for a separately identified attempt rather than repairing this history.
    """

    def __init__(self, unit: str | None = None):
        self.unit = unit
        self._phase = "event"
        self._next_seq = 1
        self._operation = 0
        self._active_stage = None
        self._pending = None
        self._pending_command = None
        self._released = False
        self._failed_operation = False
        self._last_failure = None
        self._runtime_seen = False
        self._eof_seen = False
        self._exit_seen = False

    @property
    def phase(self) -> str:
        return self._phase

    @property
    def released(self) -> bool:
        return self._released

    @property
    def complete(self) -> bool:
        return self._phase == "exited" and self._eof_seen and self._exit_seen

    def _refuse(self, reason):
        self._phase = "refused"
        raise ControllerError(reason)

    def _require(self, condition, reason):
        if not condition:
            self._refuse(reason)

    def accept(self, event: dict) -> Action:
        self._require(self._phase in ("event", "result"), "event outside receiving state")
        self._require(type(event) is dict, "event must be a dictionary")
        try:
            validate_event(event)
        except ProtocolError as exc:
            self._refuse("invalid event: " + str(exc))
        event = deepcopy(event)
        seq, stage, kind = event.get("seq"), event.get("stage"), event.get("kind")
        self._require(type(seq) is int and seq == self._next_seq, "stale, duplicate or missing event")
        self._require(isinstance(event.get("unit"), str) and bool(event["unit"]), "missing unit")
        if self.unit is None:
            self.unit = event["unit"]
        self._require(event["unit"] == self.unit, "unit changed")
        self._require(isinstance(stage, str), "missing stage")
        for flag in ("committed", "production_profile_admitted", "raw_admitted", "authority_importable"):
            self._require(event.get(flag) is False, "missing or positive authority flag")

        if kind == "before_operation":
            self._require(self._phase == "event" and not self._runtime_seen, "operation before prior result")
            self._require(not self._failed_operation, "operation after failed operation")
            self._require(self._operation < len(OPERATIONS) and stage == OPERATIONS[self._operation],
                          "operation outside declared runtime order")
            self._require(event.get("result") is None, "before-operation result must be null")
            self._active_stage = stage
            self._pending = event
            self._phase = "observe"
            action = Action("observe_before", deepcopy(event))
        elif kind in ("operation_result", "candidate_result"):
            self._require(self._phase == "result" and stage == self._active_stage,
                          "result without matching continued operation")
            self._require((kind == "candidate_result") == (stage == "create-Candidate"),
                          "candidate result kind/stage mismatch")
            result = event.get("result")
            self._require(isinstance(result, dict) and type(result.get("success")) is bool,
                          "operation result lacks actual success state")
            self._failed_operation = not result["success"]
            self._last_failure = result["failure"]
            self._active_stage = None
            self._operation += 1
            if kind == "candidate_result":
                self._require(not self._released, "duplicate candidate checkpoint")
                self._pending = event
                self._phase = "observe"
                action = Action("observe_held", deepcopy(event))
            else:
                self._phase = "event"
                action = Action("record", deepcopy(event))
        elif kind == "runtime_result":
            self._require(self._phase == "event" and self._released and not self._runtime_seen,
                          "runtime terminal before explicit candidate release")
            self._require(stage == "runtime", "runtime result stage mismatch")
            self._require(self._failed_operation or self._operation == len(OPERATIONS),
                          "runtime terminal before operation outcome")
            result = event["result"]
            self._require(result["failure"] == self._last_failure,
                          "runtime failure disagrees with operation result")
            self._require(result["protocol_complete"] is (not self._failed_operation),
                          "runtime completion disagrees with operation history")
            self._runtime_seen = True
            action = Action("record", deepcopy(event))
        elif kind == "backend_dropped":
            self._require(self._phase == "event" and self._released and self._runtime_seen,
                          "backend drop before runtime result and release")
            self._require(stage == "backend-drop", "backend drop stage mismatch")
            self._phase = "terminal"
            action = Action("terminal", deepcopy(event))
        else:
            self._refuse("unknown or failed-gate event")
        self._next_seq += 1
        return action

    def acknowledge_observation(self, seq: int, stage: str) -> Action:
        self._require(self._phase == "observe" and self._pending is not None,
                      "no pending observation")
        self._require(type(seq) is int and seq == self._pending["seq"] and stage == self._pending["stage"],
                      "stale or mismatched observation")
        command = "release" if self._pending["kind"] == "candidate_result" else "continue"
        self._pending_command = command
        self._phase = "send"
        return Action("command", deepcopy(self._pending), command)

    def command_sent(self, seq: int, stage: str, command: str) -> None:
        self._require(self._phase == "send" and self._pending is not None,
                      "no prepared command")
        self._require(type(seq) is int and seq == self._pending["seq"]
                      and stage == self._pending["stage"] and command == self._pending_command,
                      "stale, duplicate or mismatched command")
        if command == "release":
            self._released = True
            self._phase = "event"
        else:
            self._phase = "result"
        self._pending = None
        self._pending_command = None

    def eof(self) -> None:
        """Record stdout EOF; it is not proof of child exit."""
        self._require(self._phase == "terminal" and not self._eof_seen,
                      "EOF before ordered terminal or duplicate EOF")
        self._eof_seen = True

    def mark_exit(self, returncode: int) -> None:
        """Record actual owned-child exit only after ordered terminal and EOF."""
        self._require(self._phase == "terminal" and self._eof_seen and not self._exit_seen,
                      "exit before terminal/EOF or duplicate exit")
        self._require(type(returncode) is int and returncode == 0, "child did not exit zero")
        self._exit_seen = True
        self._phase = "exited"
