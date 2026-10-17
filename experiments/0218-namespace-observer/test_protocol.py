"""Finite authored wire controls; no worker, fixture or native probe is invoked."""
import copy
import json
import unittest

import protocol as p


def event(seq=1, kind="before_operation", stage="preflight", result=None):
    return {"v": 1, "unit": "authored-218", "seq": seq, "kind": kind,
            "stage": stage, "result": result, "bindings": [],
            "committed": False, "production_profile_admitted": False,
            "raw_admitted": False, "authority_importable": False}


def wire(value):
    return p.PREFIX + json.dumps(value, separators=(",", ":")).encode() + b"\n"


def operation(success=True):
    return {"success": success, "failure": None if success else "BackendIo",
            "native_error_kind": None if success else "AlreadyExists",
            "native_os_error": None if success else 183}


class ProtocolTests(unittest.TestCase):
    def rejects(self, value):
        with self.assertRaises(p.ProtocolError):
            p.parse_event(wire(value))

    def test_authored_success_and_collision_preserve_actual_error(self):
        for success in (True, False):
            value = event(kind="candidate_result", stage="create-Candidate",
                          result=operation(success))
            parsed = p.parse_event(wire(value))
            self.assertEqual(parsed, value)
            self.assertEqual(parsed["result"]["native_os_error"], None if success else 183)
            self.assertTrue(all(parsed[key] is False for key in p.FLAGS))

    def test_exact_shape_and_literal_false_flags(self):
        for field in event():
            value = event()
            del value[field]
            with self.subTest(missing=field):
                self.rejects(value)
        value = event()
        value["qualified"] = False
        self.rejects(value)
        for flag in p.FLAGS:
            for supplied in (True, 0, None, "false"):
                value = event()
                value[flag] = supplied
                with self.subTest(flag=flag, supplied=supplied):
                    self.rejects(value)

    def test_numeric_and_identity_boundaries(self):
        for field, supplied in (("v", True), ("v", 2), ("seq", True),
                                ("seq", 0), ("seq", 129), ("unit", ""),
                                ("unit", "a" * 65), ("unit", "a/b"),
                                ("unit", "é"), ("stage", "future-stage"),
                                ("kind", "future_event")):
            value = event()
            value[field] = supplied
            with self.subTest(field=field, supplied=supplied):
                self.rejects(value)

    def test_malformed_duplicate_nonfinite_and_overlong_lines(self):
        valid = wire(event())
        malformed = [b"", valid[:-1], valid + b"\n", valid.replace(p.PREFIX, b"OTHER ", 1),
                     p.PREFIX + b"\xff\n", p.PREFIX + b"[]\n",
                     p.PREFIX + b'{"v":1,"v":1}\n',
                     valid.replace(b'"result":null', b'"result":NaN'),
                     valid.replace(b'"result":null', b'"result":Infinity'),
                     p.PREFIX + b"[" * 2000 + b"]" * 2000 + b"\n",
                     p.PREFIX + b" " * p.MAX_EVENT_BYTES + b"\n",
                     valid.replace(b'"unit":', b'\r"unit":')]
        for raw in malformed:
            with self.subTest(length=len(raw), prefix=raw[:30]):
                with self.assertRaises(p.ProtocolError):
                    p.parse_event(raw)
        nested = event(kind="candidate_result", stage="create-Candidate", result=operation())
        raw = wire(nested).replace(b'"success":true', b'"success":true,"success":true')
        with self.assertRaises(p.ProtocolError):
            p.parse_event(raw)

    def test_binding_encoding_and_count_limits(self):
        value = event()
        value["bindings"] = [{"identity": "00", "facts": "ff"}]
        self.assertEqual(p.parse_event(wire(value))["bindings"], value["bindings"])
        for binding in ({"identity": "", "facts": "ff"},
                        {"identity": "0", "facts": "ff"},
                        {"identity": "AA", "facts": "ff"},
                        {"identity": "00", "facts": "gg"},
                        {"identity": "00", "facts": "ff", "extra": 1},
                        {"identity": "00" * 257, "facts": "ff"},
                        {"identity": "00", "facts": "ff" * 8193}):
            value["bindings"] = [binding]
            self.rejects(value)
        value["bindings"] = [{"identity": "00", "facts": "ff"}] * 8
        self.rejects(value)

    def test_result_consistency_and_kind_stage_binding(self):
        good = event(kind="candidate_result", stage="create-Candidate", result=operation())
        mutations = [("kind", "operation_result"), ("stage", "create-Prepared")]
        for key, supplied in mutations:
            value = copy.deepcopy(good)
            value[key] = supplied
            self.rejects(value)
        for key, supplied in (("success", 1), ("failure", "BackendIo"),
                              ("native_os_error", True), ("native_os_error", 2**31),
                              ("native_error_kind", "bad\nkind")):
            value = copy.deepcopy(good)
            value["result"][key] = supplied
            self.rejects(value)
        self.rejects(event(result=operation()))
        self.rejects(event(kind="backend_dropped", stage="preflight"))

    def test_command_only_for_matching_pause_kind(self):
        before = event()
        held = event(seq=2, kind="candidate_result", stage="create-Candidate", result=operation(False))
        for value, command in ((before, "continue"), (before, "cancel"),
                               (held, "release"), (held, "cancel")):
            parsed = p.parse_command(p.encode_command(value, command))
            self.assertEqual(parsed, {key: value[key] for key in ("v", "unit", "seq", "stage")} | {"command": command})
        for value, command in ((before, "release"), (held, "continue"), (held, "replay"),
                               (event(kind="operation_result", stage="preflight", result=operation()), "continue")):
            with self.assertRaises(p.ProtocolError):
                p.encode_command(value, command)
        for raw in (b'{"v":1,"unit":"x","seq":1,"stage":"preflight","command":"continue","command":"release"}\n',
                    b" " * (p.MAX_COMMAND_BYTES + 1) + b"\n"):
            with self.assertRaises(p.ProtocolError):
                p.parse_command(raw)

    def test_attempt_stream_rejects_duplicate_gap_stale_and_changed_unit(self):
        for bad in (event(1), event(3), event(2) | {"unit": "foreign"}):
            stream = p.EventStream()
            stream.accept(wire(event(1)))
            with self.assertRaises(p.ProtocolError):
                stream.accept(wire(bad))
            self.assertEqual(stream.sequence, 1)
        stream = p.EventStream("expected")
        with self.assertRaises(p.ProtocolError):
            stream.accept(wire(event()))
        self.assertEqual(stream.sequence, 0)
        stream = p.EventStream()
        for seq in range(1, 129):
            stream.accept(wire(event(seq)))
        with self.assertRaises(p.ProtocolError):
            stream.accept(wire(event(129)))
        self.assertEqual(stream.sequence, 128)

    def test_commands_reject_wrong_current_event_and_unknown_fields(self):
        held = event(seq=5, kind="candidate_result", stage="create-Candidate", result=operation())
        command = p.parse_command(p.encode_command(held, "release"))
        self.assertEqual(p.validate_command(p.encode_command(held, "release"), held), command)
        for key, supplied in (("seq", 4), ("seq", 6), ("unit", "other"),
                              ("stage", "preflight"), ("command", "continue"),
                              ("extra", False)):
            value = command | {key: supplied}
            with self.subTest(key=key):
                with self.assertRaises(p.ProtocolError):
                    p.validate_command(json.dumps(value).encode() + b"\n", held)

    def test_runtime_cannot_claim_committed_or_importable_authority(self):
        result = {"status": "Refused", "phase": "CandidateCreated", "failure": "BackendIo",
                  "publication_possible": False, "release_possible": False,
                  "protocol_complete": False, "retained_material": True,
                  "pending_cleanup": False, "charged_bytes": 17}
        value = event(kind="runtime_result", stage="runtime", result=result)
        self.assertEqual(p.parse_event(wire(value)), value)
        for key, supplied in (("status", "Committed"), ("status", "RecoveredOriginal"),
                              ("charged_bytes", -1), ("charged_bytes", 2**64),
                              ("charged_bytes", True), ("publication_possible", 1),
                              ("phase", "FuturePhase"), ("extra", False)):
            changed = copy.deepcopy(value)
            changed["result"][key] = supplied
            with self.subTest(key=key, supplied=supplied):
                self.rejects(changed)

    def test_gate_error_has_bounded_prior_event_reference(self):
        for reason in p.GATE_ERRORS:
            value = event(seq=2, kind="gate_error", result={
                "error": reason, "rejected_seq": 1, "rejected_stage": "preflight"})
            self.assertEqual(p.parse_event(wire(value)), value)
        value = event(seq=2, kind="gate_error", result={
            "error": next(iter(p.GATE_ERRORS)), "rejected_seq": 1,
            "rejected_stage": "preflight"})
        for key, supplied in (("error", "ignored"), ("rejected_seq", 0),
                              ("rejected_seq", 2), ("rejected_seq", True),
                              ("rejected_stage", "create-Candidate")):
            changed = copy.deepcopy(value)
            changed["result"][key] = supplied
            self.rejects(changed)


if __name__ == "__main__":
    unittest.main()
