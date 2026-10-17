"""Authored state histories only: importing/running these tests opens no markers."""
import unittest

from controller import Controller, ControllerError
from test_protocol import event, operation


# Explicit expected protocol history; do not derive the test oracle from the
# controller's operation table. Repeated flushes have distinct positions.
NORMAL = (
    "preflight", "create-root", "root-flush", "parent-flush", "create-Candidate",
    "check-CandidateChecked", "file-Candidate", "root-flush", "create-Prepared",
    "check-PreparedChecked", "file-Prepared", "root-flush", "create-Intent",
    "check-IntentChecked", "file-Intent", "root-flush", "release",
    "check-Prepublication", "publish", "check-Installed", "file-Candidate",
    "root-flush", "check-InstalledRechecked", "create-Observation",
    "check-ObservationChecked", "file-Observation", "root-flush", "create-Receipt",
    "check-ReceiptChecked", "file-Receipt", "check-ReceiptFileChecked", "root-flush",
    "check-ReceiptParentChecked", "checked-context", "check-Final", "terminal",
)


def runtime(seq, failed=False):
    return event(seq, "runtime_result", "runtime", {
        "status": "FailedBeforePublish" if failed else "Unchanged",
        "phase": "CandidateCreated" if failed else "Final",
        "failure": "BackendIo" if failed else None,
        "publication_possible": False, "release_possible": False,
        "protocol_complete": not failed, "retained_material": True,
        "pending_cleanup": False, "charged_bytes": 123})


class History:
    def __init__(self):
        self.controller = Controller("authored-218")
        self.seq = 1

    def begin(self, stage):
        value = event(self.seq, stage=stage)
        self.seq += 1
        return self.controller.accept(value)

    def acknowledge(self, action):
        value = action.event
        command = self.controller.acknowledge_observation(value["seq"], value["stage"])
        self.controller.command_sent(value["seq"], value["stage"], command.command)
        return command

    def result(self, stage, success=True):
        kind = "candidate_result" if stage == "create-Candidate" else "operation_result"
        action = self.controller.accept(event(self.seq, kind, stage, operation(success)))
        self.seq += 1
        return action

    def step(self, stage, success=True):
        self.acknowledge(self.begin(stage))
        action = self.result(stage, success)
        if action.kind == "observe_held":
            self.acknowledge(action)
        return action

    def held(self):
        for stage in NORMAL[:4]:
            self.step(stage)
        self.acknowledge(self.begin("create-Candidate"))
        return self.result("create-Candidate")

    def terminal(self, failed=False):
        self.controller.accept(runtime(self.seq, failed))
        self.seq += 1
        action = self.controller.accept(event(self.seq, "backend_dropped", "backend-drop"))
        self.seq += 1
        return action


class ControllerTests(unittest.TestCase):
    def refused(self, controller, callback):
        with self.assertRaises(ControllerError):
            callback()
        self.assertEqual(controller.phase, "refused")
        self.assertFalse(controller.complete)
        with self.assertRaises(ControllerError):
            controller.accept(event())

    def test_normal_and_collision_complete_only_after_drop_eof_and_exit(self):
        for collision in (False, True):
            with self.subTest(collision=collision):
                h = History()
                stages = NORMAL[:5] if collision else NORMAL
                for stage in stages:
                    h.step(stage, success=not (collision and stage == "create-Candidate"))
                self.assertTrue(h.controller.released)
                self.assertFalse(h.controller.complete)
                action = h.terminal(collision)
                self.assertEqual(action.kind, "terminal")
                self.assertTrue(all(action.event[key] is False for key in (
                    "committed", "production_profile_admitted", "raw_admitted", "authority_importable")))
                self.assertFalse(h.controller.complete)
                h.controller.eof()
                self.assertFalse(h.controller.complete)
                h.controller.mark_exit(0)
                self.assertTrue(h.controller.complete)

    def test_before_and_held_observations_do_not_implicitly_send(self):
        for held in (False, True):
            h = History()
            action = h.held() if held else h.begin("preflight")
            self.assertEqual(action.kind, "observe_held" if held else "observe_before")
            self.assertFalse(h.controller.released)
            self.refused(h.controller, lambda: h.controller.command_sent(
                action.event["seq"], action.event["stage"], "release" if held else "continue"))

    def test_lost_command_after_observation_cannot_advance_or_complete(self):
        for held in (False, True):
            h = History()
            action = h.held() if held else h.begin("preflight")
            command = h.controller.acknowledge_observation(action.event["seq"], action.event["stage"])
            self.assertEqual(command.command, "release" if held else "continue")
            self.assertFalse(h.controller.released)
            self.refused(h.controller, h.controller.eof)

    def test_duplicate_observation_or_send_is_terminal_refusal(self):
        for duplicate in ("observation", "send"):
            h = History()
            action = h.begin("preflight")
            h.acknowledge(action)
            if duplicate == "observation":
                callback = lambda: h.controller.acknowledge_observation(1, "preflight")
            else:
                callback = lambda: h.controller.command_sent(1, "preflight", "continue")
            self.refused(h.controller, callback)

    def test_stale_sequence_stage_and_wrong_release_refuse(self):
        for seq, stage, command in ((2, "preflight", "continue"),
                                     (1, "create-root", "continue"),
                                     (True, "preflight", "continue"),
                                     (1, "preflight", "release")):
            h = History()
            action = h.begin("preflight")
            h.controller.acknowledge_observation(action.event["seq"], action.event["stage"])
            self.refused(h.controller, lambda: h.controller.command_sent(seq, stage, command))
        h = History()
        h.held()
        self.refused(h.controller, lambda: h.controller.acknowledge_observation(1, "create-Candidate"))

    def test_result_or_next_operation_before_command_delivery_refuses(self):
        for next_event in (event(2, "operation_result", "preflight", operation()),
                           event(2, stage="create-root")):
            h = History()
            h.begin("preflight")
            h.controller.acknowledge_observation(1, "preflight")
            self.refused(h.controller, lambda: h.controller.accept(next_event))

    def test_out_of_order_missing_stale_and_foreign_events_refuse(self):
        bad_events = [event(stage="create-root"), event(2), event() | {"unit": "foreign"},
                      event(kind="operation_result", result=operation()),
                      event(kind="backend_dropped", stage="backend-drop")]
        for value in bad_events:
            h = History()
            self.refused(h.controller, lambda: h.controller.accept(value))
        h = History()
        h.step("preflight")
        self.refused(h.controller, lambda: h.controller.accept(event(1, stage="create-root")))

    def test_failed_candidate_release_still_requires_runtime_then_drop(self):
        for followup in ("operation", "drop"):
            h = History()
            for stage in NORMAL[:4]:
                h.step(stage)
            h.step("create-Candidate", False)
            value = (event(h.seq, stage="check-CandidateChecked") if followup == "operation"
                     else event(h.seq, "backend_dropped", "backend-drop"))
            self.refused(h.controller, lambda: h.controller.accept(value))

    def test_eof_and_exit_at_incomplete_or_nonzero_boundaries_refuse(self):
        for where in ("empty", "held", "runtime", "drop", "nonzero", "bool_exit"):
            h = History()
            if where != "empty":
                if where == "held":
                    h.held()
                else:
                    for stage in NORMAL[:4]:
                        h.step(stage)
                    h.step("create-Candidate", False)
                    if where == "runtime":
                        h.controller.accept(runtime(h.seq, True))
                    else:
                        h.terminal(True)
            if where in ("empty", "held", "runtime"):
                callback = h.controller.eof
            elif where == "drop":
                callback = lambda: h.controller.mark_exit(0)
            else:
                h.controller.eof()
                callback = lambda: h.controller.mark_exit(True if where == "bool_exit" else 1)
            self.refused(h.controller, callback)

    def test_positive_flags_and_early_runtime_cannot_bypass_gates(self):
        for flag in ("committed", "production_profile_admitted", "raw_admitted", "authority_importable"):
            h = History()
            self.refused(h.controller, lambda: h.controller.accept(event() | {flag: True}))
        h = History()
        held = h.held()
        h.acknowledge(held)
        self.refused(h.controller, lambda: h.controller.accept(runtime(h.seq)))

    def test_returned_action_is_detached_from_pending_state(self):
        h = History()
        action = h.begin("preflight")
        action.event["seq"] = 99
        command = h.controller.acknowledge_observation(1, "preflight")
        command.event["stage"] = "publish"
        h.controller.command_sent(1, "preflight", "continue")
        self.assertEqual(h.result("preflight").kind, "record")

    def test_runtime_cannot_relabel_actual_operation_outcome(self):
        for failed in (False, True):
            for field, supplied in (("failure", None if failed else "BackendIo"),
                                    ("protocol_complete", failed)):
                h = History()
                for stage in (NORMAL[:5] if failed else NORMAL):
                    h.step(stage, not (failed and stage == "create-Candidate"))
                value = runtime(h.seq, failed)
                value["result"][field] = supplied
                self.refused(h.controller, lambda: h.controller.accept(value))

    def test_failed_gate_event_preserves_refusal_instead_of_resuming(self):
        h = History()
        h.begin("preflight")
        value = event(2, "gate_error", "preflight", {
            "error": "Eof", "rejected_seq": 1, "rejected_stage": "preflight"})
        self.refused(h.controller, lambda: h.controller.accept(value))


if __name__ == "__main__":
    unittest.main()
