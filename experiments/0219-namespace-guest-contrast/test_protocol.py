"""Authored exchange controls; these tests never launch a worker or controller."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest


_spec = importlib.util.spec_from_file_location(
    "namespace_219_protocol_tests", Path(__file__).with_name("protocol.py"))
p = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(p)


UNIT = "authored219"


def worker(kind, stage, seq, result=None):
    return {"v": 1, "unit": UNIT, "seq": seq, "kind": kind,
            "stage": stage, "result": result,
            "bindings": [{"identity": "00", "facts": "ff"}],
            **{flag: False for flag in p.FLAGS}}


def candidate(success=False):
    return worker("candidate_result", "create-Candidate", 10,
                  {"success": success, "failure": None if success else "BackendIo",
                   "native_error_kind": None if success else "Other",
                   "native_os_error": None if success else 1117})


def runtime():
    return worker("runtime_result", "runtime", 11,
                  {"status": "FailedBeforePublish", "phase": "CandidateCreated",
                   "failure": "BackendIo", "publication_possible": False,
                   "release_possible": False, "protocol_complete": False,
                   "retained_material": True, "pending_cleanup": False,
                   "charged_bytes": 4194304})


def event(stage="prepared", seq=1, case="persistent-write-error", success=False):
    nested = None
    if stage == "source_reopened_hold":
        nested = worker("before_operation", "create-root", 3)
    elif stage == "before_candidate_hold":
        nested = worker("before_operation", "create-Candidate", 9)
    elif stage in ("candidate_hold", "cleared_hold", "released"):
        nested = candidate(success)
    elif stage == "runtime_result":
        nested = runtime()
    elif stage == "backend_dropped":
        nested = worker("backend_dropped", "backend-drop", 12)
    observation = {"authored": True}
    if stage == "exited":
        observation = {"exit_confirmed": True, "exit_code": 0}
    return {"v": 1, "unit": UNIT, "case": case, "seq": seq,
            "stage": stage, "observation": observation, "worker_event": nested,
            **{flag: False for flag in p.FLAGS}}


def raw(value):
    return p.PREFIX + json.dumps(value, separators=(",", ":")).encode() + b"\n"


def advance(session, through, success=False):
    """Deliver every gate command through the specified stage, inclusively."""
    values = []
    for stage in p.STAGES[session.index:]:
        value = event(stage, session.sequence + 1, session.case, success)
        session.accept_event(value)
        values.append(value)
        if session.pending is not None:
            session.accept_command(p.encode_command(value, p.COMMANDS[stage]))
        if stage == through:
            break
    return values


class CodecTests(unittest.TestCase):
    def rejects(self, value):
        with self.assertRaises(p.ProtocolError):
            p.parse_event(raw(value))

    def test_every_stage_round_trips_for_both_authored_cells(self):
        for case, success in (("persistent-write-error", False), ("no-error", True)):
            for seq, stage in enumerate(p.STAGES, 1):
                with self.subTest(case=case, stage=stage):
                    value = event(stage, seq, case, success)
                    self.assertEqual(p.parse_event(p.encode_event(value)), value)
                    self.assertTrue(all(value[key] is False for key in p.FLAGS))
                    if value["worker_event"]:
                        self.assertTrue(all(value["worker_event"][key] is False for key in p.FLAGS))

    def test_envelope_exact_types_shapes_and_false_flags(self):
        original = event()
        for field in original:
            value = copy.deepcopy(original)
            del value[field]
            self.rejects(value)
        for key, supplied in (("v", True), ("v", 2), ("unit", ""),
                              ("unit", "a/b"), ("unit", "x" * 65),
                              ("case", "other"), ("seq", True), ("seq", 0),
                              ("seq", p.MAX_EVENTS + 1), ("stage", "unknown"),
                              ("observation", {}), ("observation", []),
                              ("extra", False)):
            with self.subTest(key=key, value=supplied):
                self.rejects(original | {key: supplied})
        for flag in p.FLAGS:
            for supplied in (True, 0, None, "false"):
                self.rejects(original | {flag: supplied})
                nested = event("candidate_hold", 3)
                nested["worker_event"][flag] = supplied
                self.rejects(nested)

    def test_bounded_strict_json_and_frame(self):
        valid = raw(event())
        malformed = (b"", valid[:-1], valid + b"\n", valid.replace(p.PREFIX, b"OTHER ", 1),
                     p.PREFIX + b"\xff\n", p.PREFIX + b"[]\n",
                     valid.replace(b'"v":1', b'"v":1,"v":1'),
                     valid.replace(b'"authored":true', b'"authored":NaN'),
                     valid.replace(b'"authored":true', b'"authored":Infinity'),
                     valid.replace(b'"unit":', b'\r"unit":'),
                     p.PREFIX + b" " * p.MAX_EVENT_BYTES + b"\n")
        for data in malformed:
            with self.subTest(size=len(data)):
                with self.assertRaises(p.ProtocolError):
                    p.parse_event(data)
        oversized = event()
        oversized["observation"] = {"bytes": "x" * p.MAX_EVENT_BYTES}
        with self.assertRaises(p.ProtocolError):
            p.encode_event(oversized)

    def test_nested_worker_phase_sequence_unit_and_binding_are_required(self):
        for stage, seq in (("source_reopened_hold", 2), ("before_candidate_hold", 3), ("candidate_hold", 4),
                           ("cleared_hold", 4), ("released", 5)):
            for key, supplied in (("unit", "foreign"), ("seq", 1), ("bindings", [])):
                value = event(stage, seq)
                value["worker_event"][key] = supplied
                self.rejects(value)
        for stage in ("runtime_result", "backend_dropped", "before_candidate_hold"):
            value = event(stage, 6)
            value["worker_event"] = candidate()
            self.rejects(value)
        self.rejects(event() | {"worker_event": candidate()})

    def test_postexit_requires_actual_confirmation_and_integer_code(self):
        for observation in ({"exit_confirmed": False, "exit_code": 0},
                            {"exit_confirmed": 1, "exit_code": 0},
                            {"exit_confirmed": True, "exit_code": True},
                            {"exit_confirmed": True}):
            self.rejects(event("exited", 8) | {"observation": observation})

    def test_gate_command_exact_binding_and_allowed_verbs(self):
        for seq, (stage, verb) in enumerate(p.COMMANDS.items(), 1):
            value = event(stage, seq)
            for command in (verb, "cancel"):
                encoded = p.encode_command(value, command)
                self.assertEqual(p.validate_command(encoded, value)["command"], command)
            original = p.parse_command(p.encode_command(value, verb))
            for key, supplied in (("unit", "stale"), ("case", "no-error"),
                                  ("seq", seq + 1), ("stage", "final"),
                                  ("command", "replay"), ("extra", False)):
                changed = original | {key: supplied}
                with self.assertRaises(p.ProtocolError):
                    p.validate_command(json.dumps(changed).encode() + b"\n", value)
        for data in (b"", b"x" * (p.MAX_COMMAND_BYTES + 1) + b"\n"):
            with self.assertRaises(p.ProtocolError):
                p.parse_command(data)
        with self.assertRaises(p.ProtocolError):
            p.encode_command(event("final", 9), "release")
        gate = event()
        encoded = p.encode_command(gate, "start")
        with self.assertRaises(p.ProtocolError):
            p.parse_command(encoded.replace(b'"command":"start"',
                                            b'"command":"start","command":"start"'))


class SessionTests(unittest.TestCase):
    def test_two_complete_cells_keep_all_admission_flags_false(self):
        for case, success in (("persistent-write-error", False), ("no-error", True)):
            session = p.Session(UNIT, case)
            values = advance(session, "final", success)
            self.assertEqual([value["stage"] for value in values], list(p.STAGES))
            self.assertTrue(session.complete)
            self.assertFalse(session.refused)
            self.assertEqual(session.sequence, len(p.STAGES))
            self.assertIsNone(session.pending)
            self.assertTrue(all(value[flag] is False for value in values for flag in p.FLAGS))
            with self.assertRaises(p.ProtocolError):
                session.accept_event(event("failure", 10, case))

    def test_stale_duplicate_gap_foreign_unit_and_case_poison_attempt(self):
        for replacement in ({"seq": 1}, {"seq": 3}, {"unit": "foreign"},
                            {"case": "no-error"}, {"stage": "candidate_hold"}):
            session = p.Session(UNIT, "persistent-write-error")
            advance(session, "prepared")
            with self.assertRaises(p.ProtocolError):
                session.accept_event(event("source_reopened_hold", 2) | replacement)
            self.assertTrue(session.refused)
            self.assertEqual(session.sequence, 1)
            with self.assertRaises(p.ProtocolError):
                session.accept_event(event("source_reopened_hold", 2))

    def test_lost_ack_never_advances_or_allows_release(self):
        for stage in p.COMMANDS:
            session = p.Session(UNIT, "persistent-write-error")
            if stage != "prepared":
                preceding = p.STAGES[p.STAGES.index(stage) - 1]
                advance(session, preceding)
            held = event(stage, session.sequence + 1)
            session.accept_event(held)
            self.assertEqual(session.pending, held)
            next_stage = p.STAGES[p.STAGES.index(stage) + 1]
            with self.assertRaises(p.ProtocolError):
                session.accept_event(event(next_stage, session.sequence + 1))
            self.assertTrue(session.refused)

    def test_duplicate_ack_wrong_verb_and_premature_release_refuse(self):
        for verb in ("release", "cleared", "wrong-rule"):
            session = p.Session(UNIT, "persistent-write-error")
            held = session.accept_event(event())
            command = {key: held[key] for key in ("v", "unit", "case", "seq", "stage")}
            command["command"] = verb
            with self.assertRaises(p.ProtocolError):
                session.accept_command(json.dumps(command).encode() + b"\n")
            self.assertTrue(session.refused)
        session = p.Session(UNIT, "persistent-write-error")
        held = session.accept_event(event())
        ack = p.encode_command(held, "start")
        session.accept_command(ack)
        with self.assertRaises(p.ProtocolError):
            session.accept_command(ack)
        self.assertTrue(session.refused)

    def test_arm_requires_pre_candidate_gate_after_source_reopen(self):
        session = p.Session(UNIT, "persistent-write-error")
        advance(session, "prepared")
        source = session.accept_event(event("source_reopened_hold", 2))
        command = {key: source[key] for key in ("v", "unit", "case", "seq", "stage")}
        command["command"] = "armed"
        with self.assertRaises(p.ProtocolError):
            session.accept_command(json.dumps(command).encode() + b"\n")
        self.assertTrue(session.refused)
        session = p.Session(UNIT, "persistent-write-error")
        advance(session, "source_reopened_hold")
        gate = session.accept_event(event("before_candidate_hold", 3))
        session.accept_command(p.encode_command(gate, "armed"))
        self.assertEqual(session.accept_event(event("candidate_hold", 4))["stage"], "candidate_hold")

    def test_cancel_and_eof_at_each_live_gate_are_terminal(self):
        for stage in p.COMMANDS:
            for cancel in (True, False):
                session = p.Session(UNIT, "persistent-write-error")
                if stage != "prepared":
                    advance(session, p.STAGES[p.STAGES.index(stage) - 1])
                held = session.accept_event(event(stage, session.sequence + 1))
                if cancel:
                    session.accept_command(p.encode_command(held, "cancel"))
                else:
                    with self.assertRaises(p.ProtocolError):
                        session.accept_command(b"")
                self.assertTrue(session.refused)
                with self.assertRaises(p.ProtocolError):
                    session.accept_command(p.encode_command(held, p.COMMANDS[stage]))

    def test_clear_observation_and_release_preserve_exact_held_result(self):
        for target in ("cleared_hold", "released"):
            for key, supplied in (("native_os_error", 5), ("native_error_kind", "PermissionDenied")):
                session = p.Session(UNIT, "persistent-write-error")
                advance(session, p.STAGES[p.STAGES.index(target) - 1])
                changed = event(target, session.sequence + 1)
                changed["worker_event"]["result"][key] = supplied
                with self.assertRaises(p.ProtocolError):
                    session.accept_event(changed)
                self.assertTrue(session.refused)
        session = p.Session(UNIT, "persistent-write-error")
        advance(session, "candidate_hold")
        with self.assertRaises(p.ProtocolError):
            session.accept_event(event("released", session.sequence + 1))

    def test_final_inventory_cannot_precede_confirmed_exit(self):
        session = p.Session(UNIT, "persistent-write-error")
        advance(session, "backend_dropped")
        with self.assertRaises(p.ProtocolError):
            session.accept_event(event("final", session.sequence + 1))
        self.assertTrue(session.refused)

    def test_failure_record_is_retained_and_does_not_complete(self):
        session = p.Session(UNIT, "persistent-write-error")
        advance(session, "prepared")
        failure = event("failure", 2)
        self.assertEqual(session.accept_event(failure), failure)
        self.assertTrue(session.refused)
        self.assertFalse(session.complete)
        self.assertEqual(session.sequence, 2)

    def test_failure_can_be_retained_once_after_pending_cancel_eof_or_poison(self):
        for condition in ("pending", "cancel", "eof", "poison"):
            session = p.Session(UNIT, "persistent-write-error")
            gate = session.accept_event(event())
            if condition == "cancel":
                session.accept_command(p.encode_command(gate, "cancel"))
            elif condition == "eof":
                with self.assertRaises(p.ProtocolError):
                    session.accept_command(b"")
            elif condition == "poison":
                with self.assertRaises(p.ProtocolError):
                    session.accept_event(event("final", 2))
            retained = session.fail({"reason": condition})
            self.assertEqual(retained["seq"], 2)
            self.assertEqual(retained["stage"], "failure")
            self.assertTrue(session.refused)
            self.assertFalse(session.complete)
            self.assertIsNone(session.pending)
            self.assertTrue(all(retained[key] is False for key in p.FLAGS))
            with self.assertRaises(p.ProtocolError):
                session.fail({"reason": "duplicate"})

    def test_emit_uses_same_state_machine_and_failure_cannot_follow_final(self):
        session = p.Session(UNIT, "persistent-write-error")
        value = session.emit("prepared", {"authored": True})
        self.assertEqual(value, event())
        session.accept_command(p.encode_command(value, "start"))
        advance(session, "final")
        with self.assertRaises(p.ProtocolError):
            session.fail({"reason": "postfinal"})

    def test_peer_failure_after_cancel_or_refusal_is_retained_once(self):
        for cancel in (True, False):
            session = p.Session(UNIT, "persistent-write-error")
            gate = session.accept_event(event())
            if cancel:
                session.accept_command(p.encode_command(gate, "cancel"))
            else:
                with self.assertRaises(p.ProtocolError):
                    session.accept_command(b"")
            failure = event("failure", 2)
            self.assertEqual(session.accept_event(failure), failure)
            self.assertEqual(session.sequence, 2)
            self.assertFalse(session.complete)
            self.assertTrue(session.refused)
            with self.assertRaises(p.ProtocolError):
                session.accept_event(event("failure", 3))
            self.assertEqual(session.sequence, 2)

    def test_received_records_and_saved_candidate_are_copied(self):
        session = p.Session(UNIT, "persistent-write-error")
        held = session.accept_event(event())
        held["observation"]["authored"] = False
        self.assertTrue(session.pending["observation"]["authored"])
        session.accept_command(p.encode_command(event(), "start"))
        advance(session, "before_candidate_hold")
        candidate_event = event("candidate_hold", 4)
        returned = session.accept_event(candidate_event)
        candidate_event["worker_event"]["result"]["native_os_error"] = 5
        returned["worker_event"]["result"]["native_os_error"] = 6
        session.accept_command(p.encode_command(session.pending, "cleared"))
        self.assertEqual(session.accept_event(event("cleared_hold", 5))["worker_event"], candidate())


if __name__ == "__main__":
    unittest.main()
