"""Finite #0139 authored contract model; no runtime or native-signal evidence."""
from copy import deepcopy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VECTORS = ROOT / "docs/legacy-compatibility/read-cancellation/vectors.v1.json"


def model(version, events):
    """Single active operation, zero queue; stop at a terminal observation."""
    if type(version) is not int or version not in (1, 2):
        raise ValueError("unsupported model version")
    state, token, frames, results, active = "idle", False, 0, 0, None
    blocked = None
    result = dict(outcome="waiting", exitStatus=None, complete=False,
                  frames=0, results=0, activeId=None, owner="caller-streams")
    for event in events:
        if result["outcome"] != "waiting":
            # A completed observation cannot be withdrawn by a later event.
            if event not in ("cancel", "forced-exit"):
                raise ValueError("event after terminal observation")
            continue
        if blocked:
            returned = {"blocked-input": ("input-error", "interrupted-input"),
                        "blocked-read": (),
                        "blocked-output": ("output-error",)}
            if event not in ("cancel", "forced-exit", "call-returned", *returned[blocked]):
                raise ValueError("blocked call cannot advance before returning")
            if event in returned[blocked]:
                blocked = None
        if event == "cancel":
            if version == 2:
                token = True
        elif event in ("blocked-input", "blocked-read", "blocked-output"):
            allowed = {"blocked-input": ("idle", "partial"),
                       "blocked-read": ("reading",),
                       "blocked-output": ("emitting", "cancelling", "input-error",
                                          "protocol-error", "eof")}
            if state not in allowed[event]:
                raise ValueError("wrong blocking boundary")
            blocked = event  # A token cannot wake a synchronous call.
        elif event == "call-returned":
            if not blocked:
                raise ValueError("no blocked call")
            blocked = None
        elif event == "forced-exit":
            result.update(outcome="forced-exit", owner="invoker-process")
        elif event == "checkpoint":
            if blocked:
                raise ValueError("blocked call cannot poll")
            if version == 2 and token and state in ("idle", "partial", "reading", "prepared"):
                state = "cancelling"
        elif event == "partial-input":
            if state != "idle":
                raise ValueError("input overlaps work")
            frames += 1
            state = "partial"
        elif event == "admit-read":
            if state == "idle":
                frames += 1
            elif state != "partial":
                raise ValueError("read overlaps work")
            state, active = "reading", "read-1"
        elif event == "prepare-result":
            if state != "reading":
                raise ValueError("no active read")
            state = "prepared"
        elif event == "start-result":
            if state != "prepared":
                raise ValueError("no prepared result")
            state = "emitting"
        elif event == "flush-result":
            if state != "emitting":
                raise ValueError("no started frame")
            results += 1
            state, active = "idle", None
        elif event == "interrupted-input":
            # Current v1 retries. Proposed v2 checks cancellation before retry.
            if version == 2 and token:
                state = "cancelling"
        elif event in ("input-error", "output-error", "cancel-frame"):
            blocked = None
            if event == "output-error":
                result.update(outcome="output-error", exitStatus=1)
            else:
                if event == "cancel-frame":
                    if state != "idle":
                        raise ValueError("control cannot bypass active work")
                    frames += 1
                    state = "protocol-error"
                else:
                    state = "input-error"
        elif event == "flush-terminal":
            if state not in ("cancelling", "input-error", "protocol-error", "eof"):
                raise ValueError("no terminal reason")
            outcome = "cancelled" if state == "cancelling" else state
            result.update(outcome=outcome, complete=True,
                          exitStatus={"cancelled": 130, "input-error": 1,
                                      "protocol-error": 2, "eof": 0}[outcome])
        elif event == "eof":
            if state != "idle":
                raise ValueError("model EOF requires frame boundary")
            state = "eof"
        else:
            raise ValueError(f"unknown event {event}")
        result.update(frames=frames, results=results,
                      activeId=active if state == "cancelling" else None)
    return result


def verify_case(case):
    if set(case) != {"id", "version", "events", "expected"}:
        raise ValueError("case shape")
    actual = model(case["version"], case["events"])
    if actual != case["expected"]:
        raise ValueError(f"outcome mismatch: {case['id']}")


def main():
    data = json.loads(VECTORS.read_text(encoding="utf-8"))
    assert data["evidence"] == "authored-specification-only"
    assert data["revision"] == "2026-10-17.1"
    ids = set()
    altered = 0
    for case in data["cases"]:
        assert case["id"] not in ids
        ids.add(case["id"])
        verify_case(case)
        # Every semantic output field is changed independently and must refuse.
        for field, value in case["expected"].items():
            changed = deepcopy(case)
            changed["expected"][field] = (not value if type(value) is bool else
                                          value + 1 if type(value) is int else
                                          "altered")
            try:
                verify_case(changed)
            except ValueError:
                altered += 1
            else:
                raise AssertionError(f"accepted alteration: {case['id']} {field}")
    required = {"v1-token-ignored", "v1-interrupted-retries", "v1-cancel-frame",
                "v2-before-input", "v2-partial-input", "v2-active-read",
                "v2-prepared-result", "v2-started-result", "v2-blocked-read",
                "v2-blocked-output", "v2-input-error-wins", "v2-output-error-wins",
                "v2-interrupted-checkpoint", "v2-terminal-flush-error",
                "v2-cancel-frame", "forced-exit", "completed-before-cancel",
                "v2-blocked-terminal", "v2-unblocked-terminal",
                "v2-unblocked-output", "v2-blocked-input-interrupted",
                "v1-blocked-input-interrupted", "v2-blocked-output-error"}
    assert required <= ids
    invalid = [
        (1, ["admit-read", "cancel-frame"]),
        (2, ["blocked-input", "cancel", "checkpoint"]),
        (2, ["admit-read", "admit-read"]),
        (2, ["flush-result"]),
        (2, ["flush-terminal"]),
        (2, ["admit-read", "blocked-output"]),
        (2, ["admit-read", "prepare-result", "start-result", "blocked-output",
             "cancel", "flush-result"]),
        (2, ["cancel", "checkpoint", "blocked-output", "flush-terminal"]),
        (2, ["admit-read", "blocked-read", "prepare-result"]),
        (2, ["blocked-input", "admit-read"]),
        (2, ["blocked-input", "eof"]),
        (2, ["blocked-input", "output-error"]),
        (2, ["cancel", "checkpoint", "blocked-output", "interrupted-input"]),
    ]
    for version, events in invalid:
        try:
            model(version, events)
        except ValueError:
            pass
        else:
            raise AssertionError(f"accepted impossible transition: {events}")
    print(f"#0139: {len(ids)} authored cases; {altered} altered outcomes refused; "
          f"{len(invalid)} impossible transitions refused; specification only, "
          "no cancellation runtime or OS signals executed")


if __name__ == "__main__":
    main()
