"""Authored retained-evidence controls; never run the native worker or probes."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

import audit


def temporary_directory():
    root = Path(__file__).resolve().parents[2] / ".local" / "0218-authored-tests"
    root.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(prefix="audit-", dir=root)


def encoded(value):
    return (json.dumps(value, sort_keys=True, allow_nan=False) + "\n").encode()


def transport_fixture(root):
    bounds = dict(deadline_seconds=30.0, stdout_bytes=4096, stderr_bytes=4096,
                  line_bytes=4096, events=16, command_bytes=4096, commands=16)
    command = ["authored-child-placeholder"]
    raw = encoded({"stage": "authored"})
    result = dict(schema="namespace-observer-run-v1", command=command, bounds=bounds,
                  status="transport_complete", reason="child_exit_zero", exit_code=0,
                  lines=1, commands=1, stdout_bytes=len(raw), stderr_bytes=0,
                  child_killed=False, replayed=False, threads_stopped=True, elapsed_seconds=0.01)
    result.update(exit_confirmed=True, capture_drain_complete=True, cleanup_errors=[], child_pid=218)
    def row(kind, value, alive=True):
        return dict(kind=kind, value=value, child_alive=alive)
    transcript = [row("start", dict(command=command, bounds=bounds), False),
                  row("stdout_line", {"line": 1}),
                  row("command_sent", {"bytes_hex": encoded({"release": "authored"}).hex()}),
                  row("exit", dict(exit_code=0, exit_confirmed=True, status="transport_complete", reason="child_exit_zero"), False)]
    for index, entry in enumerate(transcript, 1):
        entry.update(seq=index, elapsed_ns=index)
    value = dict(result=result, stdout=raw, stderr=b"",
                 events=[dict(line=1, bytes_hex=raw.hex())], transcript=transcript)
    write_transport(root, value)
    return value


def write_transport(root, value):
    (root / "result.json").write_bytes(encoded(value["result"]))
    for key in ("stdout", "stderr"):
        (root / (key + ".bin")).write_bytes(value[key])
    for key in ("events", "transcript"):
        (root / (key + ".jsonl")).write_bytes(b"".join(map(encoded, value[key])))


class TransportControls(unittest.TestCase):
    def test_authored_transport_success_does_not_claim_native_qualification(self):
        with temporary_directory() as directory:
            root = Path(directory)
            transport_fixture(root)
            result = audit.audit_transport(root)
            self.assertEqual(result["result"]["status"], "transport_complete")
            self.assertNotIn("qualified", result)

    def test_retained_transport_tampering_refuses(self):
        def status(value, **changes):
            value["result"].update(changes)
        mutations = {
            "incomplete_zero_exit": lambda v: status(v, status="failed", reason="stdout_unterminated_line"),
            "nonzero_exit": lambda v: status(v, exit_code=7, status="failed", reason="child_nonzero"),
            "killed_zero_exit": lambda v: status(v, child_killed=True),
            "capture_threads_live": lambda v: status(v, threads_stopped=False),
            "replayed": lambda v: status(v, replayed=True),
            "deadline": lambda v: status(v, elapsed_seconds=31),
            "stdout_count": lambda v: status(v, stdout_bytes=0),
            "event_line_number": lambda v: v["events"][0].update(line=2),
            "event_raw_binding": lambda v: v["events"][0].update(bytes_hex=encoded({"stage": "changed"}).hex()),
            "command_count": lambda v: status(v, commands=0),
            "command_after_exit": lambda v: v["transcript"].__setitem__(slice(2, 4), list(reversed(v["transcript"][2:4]))),
            "command_without_child": lambda v: v["transcript"][2].update(child_alive=False),
            "exit_without_stop": lambda v: v["transcript"][-1].update(child_alive=True),
            "time_reversal": lambda v: v["transcript"][2].update(elapsed_ns=0),
            "transcript_sequence": lambda v: v["transcript"][1].update(seq=99),
            "start_binding": lambda v: v["transcript"][0]["value"].update(command=["another-worker"]),
            "boolean_exit_code": lambda v: status(v, exit_code=False),
            "boolean_line_count": lambda v: status(v, lines=True),
            "boolean_command_count": lambda v: status(v, commands=True),
            "boolean_sequence": lambda v: v["transcript"][0].update(seq=True),
            "exit_unconfirmed": lambda v: status(v, exit_confirmed=False),
            "capture_not_drained": lambda v: status(v, capture_drain_complete=False),
            "cleanup_error": lambda v: status(v, cleanup_errors=["authored cleanup failure"]),
            "invalid_pid": lambda v: status(v, child_pid=0),
            "missing_exit": lambda v: v["transcript"].pop(),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name), temporary_directory() as directory:
                root = Path(directory)
                value = transport_fixture(root)
                audit.audit_transport(root)
                mutate(value)
                write_transport(root, value)
                before = {path.name: path.read_bytes() for path in root.iterdir()}
                with self.assertRaises(audit.AuditError):
                    audit.audit_transport(root)
                self.assertEqual({path.name: path.read_bytes() for path in root.iterdir()}, before)

    def test_wrong_top_level_retained_types_raise_audit_error(self):
        for artifact, raw in (("result.json", b"[]\n"), ("events.jsonl", b"[]\n"),
                              ("transcript.jsonl", b"null\n")):
            with self.subTest(artifact=artifact), temporary_directory() as directory:
                root = Path(directory)
                transport_fixture(root)
                (root / artifact).write_bytes(raw)
                with self.assertRaises(audit.AuditError):
                    audit.audit_transport(root)


def collision_protocol_fixture(cell="candidate-collision"):
    """Independent authored transcript for either finite protocol control."""
    normal = cell == "normal"
    stages = (
        "preflight", "create-root", "root-flush", "parent-flush", "create-Candidate",
        "check-CandidateChecked", "file-Candidate", "root-flush", "create-Prepared",
        "check-PreparedChecked", "file-Prepared", "root-flush", "create-Intent", "check-IntentChecked",
        "file-Intent", "root-flush", "release", "check-Prepublication", "publish", "check-Installed",
        "file-Candidate", "root-flush", "check-InstalledRechecked", "create-Observation",
        "check-ObservationChecked", "file-Observation", "root-flush", "create-Receipt", "check-ReceiptChecked",
        "file-Receipt", "check-ReceiptFileChecked", "root-flush", "check-ReceiptParentChecked",
        "checked-context", "check-Final", "terminal",
    ) if normal else ("preflight", "create-root", "root-flush", "parent-flush", "create-Candidate")
    pairs = [("before_operation", stage) if offset == 0 else
             ("candidate_result" if stage == "create-Candidate" else "operation_result", stage)
             for stage in stages
             for offset in (0, 1)]
    pairs.extend((("runtime_result", "runtime"), ("backend_dropped", "backend-drop")))
    raw_lines, received, commands, transcript = [], [], [], []
    position = 0
    for sequence, (kind, stage) in enumerate(pairs, 1):
        result = None
        if kind in ("operation_result", "candidate_result"):
            failed = kind == "candidate_result" and not normal
            result = dict(success=not failed, failure="Conflict" if failed else None,
                          native_error_kind="AlreadyExists" if failed else None,
                          native_os_error=183 if failed else None)
        elif kind == "runtime_result":
            result = dict(status="Refused" if normal else "Conflict", phase="TerminalExport" if normal else "CandidateCreated",
                          failure=None if normal else "Conflict",
                          publication_possible=normal, release_possible=normal, protocol_complete=normal,
                          retained_material=True, pending_cleanup=True, charged_bytes=32)
        event = dict(v=1, unit="authored218", seq=sequence, kind=kind, stage=stage,
                     result=result, bindings=[], **dict.fromkeys(audit.FLAGS, False))
        raw_lines.append(audit.PREFIX + encoded(event))
        position += 1
        row = dict(kind="stdout_line", seq=position, child_alive=True, value={"line": sequence})
        received.append(row)
        transcript.append(row)
        if kind in ("before_operation", "candidate_result"):
            command = dict(v=1, unit="authored218", seq=sequence, stage=stage,
                           command="release" if kind == "candidate_result" else "continue")
            position += 1
            transcript.append(dict(kind="observation_acknowledged", seq=position, child_alive=True,
                                   value={"event_seq": sequence, "command": command["command"]}))
            position += 1
            row = dict(kind="command_sent", seq=position, child_alive=True, value={"bytes_hex": encoded(command).hex()})
            commands.append(row)
            transcript.append(row)
    exit_row = dict(kind="exit", seq=position + 1, child_alive=False, value={"exit_confirmed": True})
    transcript.append(exit_row)
    return dict(raw_lines=raw_lines, received=received, commands=commands, transcript=transcript, exit=exit_row)


class DiagnosticOrderControls(unittest.TestCase):
    def test_authored_collision_protocol_retains_failure_and_release(self):
        events, runtime, candidate = audit._protocol(collision_protocol_fixture(), "candidate-collision", "authored218")
        self.assertEqual(events[9]["result"]["native_os_error"], 183)
        self.assertEqual(runtime["failure"], "Conflict")
        self.assertLess(candidate["receive_seq"], candidate["release_seq"])

    def test_stage_ack_release_and_exit_tamper_refusals(self):
        def event_change(value, index, **changes):
            event = json.loads(value["raw_lines"][index][len(audit.PREFIX):])
            event.update(changes)
            value["raw_lines"][index] = audit.PREFIX + encoded(event)
        def command_change(value, index, **changes):
            command = json.loads(bytes.fromhex(value["commands"][index]["value"]["bytes_hex"]))
            command.update(changes)
            value["commands"][index]["value"]["bytes_hex"] = encoded(command).hex()
        mutations = {
            "operation_order": lambda v: event_change(v, 2, stage="parent-flush"),
            "wrong_unit": lambda v: event_change(v, 9, unit="another-attempt"),
            "missing_candidate_pause": lambda v: v["raw_lines"].pop(9),
            "duplicate_event": lambda v: event_change(v, 9, seq=9),
            "positive_admission": lambda v: event_change(v, 9, committed=True),
            "missing_ack": lambda v: v["commands"].pop(),
            "stale_release": lambda v: command_change(v, -1, seq=9),
            "continue_instead_release": lambda v: command_change(v, -1, command="continue"),
            "release_before_result": lambda v: v["commands"][-1].update(seq=v["received"][9]["seq"] - 1),
            "release_after_runtime": lambda v: v["commands"][-1].update(seq=v["received"][-2]["seq"] + 1),
            "exit_before_backend_drop": lambda v: v["exit"].update(seq=v["received"][-1]["seq"] - 1),
        }
        for name, mutate in mutations.items():
            value = collision_protocol_fixture()
            audit._protocol(value, "candidate-collision", "authored218")
            mutate(value)
            with self.subTest(name=name), self.assertRaises(audit.AuditError):
                audit._protocol(value, "candidate-collision", "authored218")


def postwrite_exit_fixture(cell):
    value = collision_protocol_fixture(cell)
    sent = value["commands"][-1]
    for row in value["transcript"]:
        if row["seq"] >= sent["seq"]:
            row["child_alive"] = False
    return value


class PostwriteExitSampleControls(unittest.TestCase):
    def test_both_final_gate_races_require_and_retain_consumption_proof(self):
        for cell in ("normal", "candidate-collision"):
            value = postwrite_exit_fixture(cell)
            events, runtime, _ = audit._protocol(value, cell, "authored218")
            self.assertFalse(value["commands"][-1]["child_alive"])
            self.assertEqual(events[-1]["kind"], "backend_dropped")
            self.assertEqual(runtime["protocol_complete"], cell == "normal")
            with self.subTest(cell=cell), temporary_directory() as directory:
                root = Path(directory)
                bounds = dict(deadline_seconds=30.0, stdout_bytes=65536, stderr_bytes=4096,
                              line_bytes=4096, events=128, command_bytes=1024, commands=64)
                command = ["authored-placeholder-not-an-executable"]
                for row in value["transcript"]:
                    row["seq"] += 1
                    row["elapsed_ns"] = row["seq"]
                value["exit"]["value"] = dict(exit_code=0, exit_confirmed=True, status="transport_complete", reason="child_exit_zero")
                value["transcript"].insert(0, dict(kind="start", seq=1, elapsed_ns=1, child_alive=False,
                                                  value=dict(command=command, bounds=bounds)))
                stdout = b"".join(value["raw_lines"])
                result = dict(schema="namespace-observer-run-v1", command=command, bounds=bounds,
                              status="transport_complete", reason="child_exit_zero", exit_code=0,
                              lines=len(value["raw_lines"]), commands=len(value["commands"]), stdout_bytes=len(stdout), stderr_bytes=0,
                              child_killed=False, replayed=False, threads_stopped=True, elapsed_seconds=0.01,
                              exit_confirmed=True, capture_drain_complete=True, cleanup_errors=[], child_pid=218)
                write_transport(root, dict(result=result, stdout=stdout, stderr=b"",
                                          events=[dict(line=index, bytes_hex=line.hex()) for index, line in enumerate(value["raw_lines"], 1)],
                                          transcript=value["transcript"]))
                audited = audit.audit_transport(root)
                self.assertFalse(audited["commands"][-1]["child_alive"])

    def test_missing_live_prewrite_or_downstream_evidence_refuses(self):
        def ack(value):
            return next(row for row in value["transcript"] if row["kind"] == "observation_acknowledged"
                        and row["value"]["event_seq"] == (71 if len(value["raw_lines"]) == 74 else 10))
        def runtime(value):
            event = json.loads(value["raw_lines"][-2][len(audit.PREFIX):])
            event["result"]["phase"] = "Preflight"
            value["raw_lines"][-2] = audit.PREFIX + encoded(event)
        mutations = {
            "prewrite_not_alive": lambda v: ack(v).update(child_alive=False),
            "prewrite_wrong_command": lambda v: ack(v)["value"].update(command="cancel"),
            "prewrite_wrong_sequence": lambda v: ack(v)["value"].update(event_seq=1),
            "missing_prewrite": lambda v: v["transcript"].remove(ack(v)),
            "late_prewrite": lambda v: ack(v).update(seq=v["commands"][-1]["seq"] + 1),
            "receive_not_alive": lambda v: v["received"][-4 if len(v["raw_lines"]) == 74 else -3].update(child_alive=False),
            "child_resurrection": lambda v: v["received"][-1].update(child_alive=True),
            "unconfirmed_exit": lambda v: v["exit"]["value"].update(exit_confirmed=False),
            "missing_drop": lambda v: v["raw_lines"].pop(),
            "wrong_runtime": runtime,
            "nonfinal_command_not_alive": lambda v: v["commands"][0].update(child_alive=False),
            "wrong_final_ack": lambda v: v["commands"][-1]["value"].update(bytes_hex=encoded(dict(v=1, unit="authored218", seq=1, stage="preflight", command="continue")).hex()),
        }
        for cell in ("normal", "candidate-collision"):
            for name, mutate in mutations.items():
                value = postwrite_exit_fixture(cell)
                audit._protocol(value, cell, "authored218")
                mutate(value)
                with self.subTest(cell=cell, mutation=name), self.assertRaises(audit.AuditError):
                    audit._protocol(value, cell, "authored218")
            value = collision_protocol_fixture(cell)
            audit._protocol(value, cell, "authored218")
            value["commands"][0]["child_alive"] = False
            with self.subTest(cell=cell, mutation="only_nonfinal_sample_dead"), self.assertRaisesRegex(
                    audit.AuditError, "nonfinal command sampled child exit"):
                audit._protocol(value, cell, "authored218")


def probe_timeline_fixture():
    fixture = dict(source="authored-source-placeholder", sourceSha256="1" * 64, sourceBytes=19,
                   sourceIdentity=dict(device=1, inode=2))
    stat = dict(device=1, inode=2, mode=32768, size=19, mtime_ns=3, ctime_ns=4, birthtime_ns=None)
    snapshot = dict(path=fixture["source"], status="ok", error=None, reason=None,
                    stat_profile="same-fields-v1", observations_match=True, sha256=fixture["sourceSha256"], bytes_read=19,
                    identity_bridge_profile="unavailable-non-windows-v1", bridge_before=None, bridge_after=None,
                    max_bytes=19, **{key: copy.deepcopy(stat) for key in
                                    ("path_before", "handle_before", "handle_after", "path_after")})
    rows = []
    for phase, start, end in (("baseline", 1, 2), ("held", 12, 13), ("after_exit", 31, 32)):
        access = phase != "held"
        probe = dict(path=fixture["source"], expected_access=access, before=copy.deepcopy(snapshot),
                     after=copy.deepcopy(snapshot), source_unchanged=True, expectation_met=True,
                     close_error=None, flags=32769, status="opened" if access else "open_error",
                     opened_stat=copy.deepcopy(stat) if access else None,
                     denial_observation=None if access else "win32_sharing_violation",
                     error=None if access else dict(type="PermissionError", errno=13, winerror=32))
        rows.extend((dict(kind="probe_begin", seq=start, child_alive=not access, value={"phase": phase}),
                     dict(kind="probe_end", seq=end, child_alive=not access, value={"phase": phase, "probe": probe})))
    rows.extend((dict(kind="stdout_line", seq=11, child_alive=True, value={"line": 10}),
                 dict(kind="command_sent", seq=14, child_alive=True, value={})))
    for row in rows:
        row["elapsed_ns"] = row["seq"] * 1000
    rows.sort(key=lambda row: row["seq"])
    transport = dict(transcript=rows, received=[{"seq": 3}], exit={"seq": 30})
    return transport, dict(receive_seq=11, release_seq=14), fixture


class ProbeLifetimeControls(unittest.TestCase):
    def test_authored_three_phase_lifetime_model(self):
        transport, candidate, fixture = probe_timeline_fixture()
        probes = audit._probe_timeline(transport, candidate, fixture)
        self.assertEqual([probe["status"] for probe in probes], ["opened", "open_error", "opened"])

    def test_crt_eacces_and_actual_sharing_error_remain_distinct(self):
        for winerror, observation in ((32, "win32_sharing_violation"),
                                       (None, "crt_eacces_without_native_error")):
            transport, candidate, fixture = probe_timeline_fixture()
            held = next(row["value"]["probe"] for row in transport["transcript"]
                        if row["kind"] == "probe_end" and row["value"]["phase"] == "held")
            held["error"]["winerror"] = winerror
            held["denial_observation"] = observation
            with self.subTest(winerror=winerror):
                self.assertEqual(audit._probe_timeline(transport, candidate, fixture)[1]["denial_observation"], observation)

    def test_probe_errors_identity_flags_and_gate_order_refuse(self):
        def held(value):
            return next(row["value"]["probe"] for row in value["transcript"]
                        if row["kind"] == "probe_end" and row["value"]["phase"] == "held")
        def phase_row(value, phase, kind):
            return next(row for row in value["transcript"] if row["kind"] == kind and row["value"]["phase"] == phase)
        mutations = {
            "missing_phase": lambda v: v["transcript"].pop(),
            "held_probe_after_release": lambda v: phase_row(v, "held", "probe_end").update(seq=15),
            "held_probe_before_candidate_result": lambda v: phase_row(v, "held", "probe_begin").update(seq=10),
            "after_probe_before_exit": lambda v: phase_row(v, "after_exit", "probe_begin").update(seq=29),
            "held_child_dead": lambda v: phase_row(v, "held", "probe_begin").update(child_alive=False),
            "arbitrary_denial": lambda v: held(v)["error"].update(winerror=5),
            "missing_file_is_not_denial": lambda v: held(v)["error"].update(errno=2, winerror=None),
            "wrong_denial_classification": lambda v: held(v).update(denial_observation="crt_eacces_without_native_error"),
            "fabricated_success_flag": lambda v: held(v).update(expectation_met=False),
            "writing_open_flags": lambda v: held(v).update(flags=32769 | 512),
            "changed_source_hash": lambda v: held(v)["after"].update(sha256="2" * 64),
            "changed_source_object": lambda v: held(v)["after"]["path_after"].update(inode=99),
            "wrong_source_path": lambda v: held(v).update(path="other-source"),
            "close_error": lambda v: held(v).update(close_error={"winerror": 6}),
        }
        for name, mutate in mutations.items():
            transport, candidate, fixture = probe_timeline_fixture()
            audit._probe_timeline(transport, candidate, fixture)
            mutate(transport)
            reasons = {
                "missing_phase": "exact three probe phases", "held_probe_after_release": "held probe outside",
                "held_probe_before_candidate_result": "held probe outside", "after_probe_before_exit": "after-exit probe before",
                "held_child_dead": "probe lifetime", "arbitrary_denial": "actual access denial",
                "missing_file_is_not_denial": "actual access denial", "wrong_denial_classification": "classification differs",
                "fabricated_success_flag": "failed expectation", "writing_open_flags": "nonwriting open",
                "changed_source_hash": "snapshot bytes/bound", "changed_source_object": "identity/stat mismatch",
                "wrong_source_path": "probe target/expectation", "close_error": "failed expectation",
            }
            with self.subTest(name=name), self.assertRaisesRegex(audit.AuditError, reasons[name]):
                audit._probe_timeline(transport, candidate, fixture)

    def test_release_deadline_and_original_source_identity_refuse(self):
        transport, candidate, fixture = probe_timeline_fixture()
        audit._probe_timeline(transport, candidate, fixture)
        next(row for row in transport["transcript"] if row["seq"] == candidate["release_seq"])["elapsed_ns"] = 16_000_000_000
        with self.assertRaisesRegex(audit.AuditError, "exceeded worker gate deadline"):
            audit._probe_timeline(transport, candidate, fixture)
        transport, candidate, fixture = probe_timeline_fixture()
        fixture["sourceIdentity"]["inode"] = 99
        with self.assertRaisesRegex(audit.AuditError, "original source identity"):
            audit._probe_timeline(transport, candidate, fixture)


class HeldObjectBindingControls(unittest.TestCase):
    def test_tiny_encoded_identity_size_and_hash(self):
        identity = dict(volume_serial_u32=1, file_index_u64=2)
        digest = hashlib.sha256(b"tiny authored held bytes").hexdigest()
        fields = (1, 2, 24, 1, 32, 3, 4, 0)
        raw = b"imageinfo-held-object-v1\0" + b"".join(value.to_bytes(8, "little") for value in fields) + bytes.fromhex(digest)
        binding = dict(identity=(fields[0].to_bytes(8, "little") + fields[1].to_bytes(8, "little")).hex(), facts=raw.hex())
        audit._held_binding(binding, identity, 24, digest)
        for changed, expected in ((dict(volume_serial_u32=9, file_index_u64=2), "identity/size"),
                                  (dict(volume_serial_u32=1, file_index_u64=9), "identity/size")):
            with self.subTest(changed=changed), self.assertRaisesRegex(audit.AuditError, expected):
                audit._held_binding(binding, changed, 24, digest)
        with self.assertRaisesRegex(audit.AuditError, "identity/size"):
            audit._held_binding(binding, identity, 25, digest)
        with self.assertRaisesRegex(audit.AuditError, "content digest"):
            audit._held_binding(binding, identity, 24, "0" * 64)
        changed = dict(binding, identity="00" * 16)
        with self.assertRaisesRegex(audit.AuditError, "identity/facts"):
            audit._held_binding(changed, identity, 24, digest)
        with self.assertRaisesRegex(audit.AuditError, "held facts encoding"):
            audit._held_binding(dict(binding, facts="00"), identity, 24, digest)


def windows_profile_fixture():
    transport, candidate, fixture = probe_timeline_fixture()
    for row in transport["transcript"]:
        if row["kind"] != "probe_end":
            continue
        probe = row["value"]["probe"]
        for snapshot in (probe["before"], probe["after"]):
            snapshot["stat_profile"] = "cpython-3.14.7-windows-path-creation-handle-change-v1"
            snapshot["identity_bridge_profile"] = "win32-bhfi-same-read-fd-v1"
            snapshot["bridge_before"] = dict(volume_serial_u32=77, file_index_u64=2)
            snapshot["bridge_after"] = dict(volume_serial_u32=77, file_index_u64=2)
            for key in ("path_before", "handle_before", "handle_after", "path_after"):
                snapshot[key]["birthtime_ns"] = 4
                snapshot[key]["ctime_ns"] = 8 if key.startswith("handle") else 4
        if probe["opened_stat"] is not None:
            probe["opened_stat"] = copy.deepcopy(probe["before"]["handle_before"])
    return transport, candidate, fixture


class SnapshotStatProfileControls(unittest.TestCase):
    def test_stat_identity_uint64_and_signed_time_domains_are_separate(self):
        def selected_snapshot():
            transport, _, fixture = probe_timeline_fixture()
            snapshot = copy.deepcopy(next(row["value"]["probe"]["before"] for row in transport["transcript"]
                                          if row["kind"] == "probe_end"))
            return snapshot, fixture
        def set_field(snapshot, field, value):
            for name in ("path_before", "handle_before", "handle_after", "path_after"):
                snapshot[name][field] = value
        def check(snapshot, fixture):
            return audit._snapshot(snapshot, fixture["source"], fixture["sourceSha256"], fixture["sourceBytes"])
        for field in ("device", "inode"):
            for value in (0, 2**63, 10008163935479661397, 2**64 - 1):
                snapshot, fixture = selected_snapshot()
                set_field(snapshot, field, value)
                with self.subTest(field=field, value=value):
                    self.assertEqual(check(snapshot, fixture)[field], value)
            for value in (-1, 2**64, True, False, 1.0, "1"):
                snapshot, fixture = selected_snapshot()
                set_field(snapshot, field, value)
                with self.subTest(field=field, value=value), self.assertRaisesRegex(audit.AuditError, "stat field type"):
                    check(snapshot, fixture)
        for field in ("mtime_ns", "ctime_ns", "birthtime_ns"):
            for value in (-(2**63), -1, 0, 2**63 - 1):
                snapshot, fixture = selected_snapshot()
                set_field(snapshot, field, value)
                with self.subTest(time_field=field, value=value):
                    self.assertEqual(check(snapshot, fixture)[field], value)
            for value in (-(2**63) - 1, 2**63, True, False, 1.0, "1"):
                snapshot, fixture = selected_snapshot()
                set_field(snapshot, field, value)
                with self.subTest(time_field=field, value=value), self.assertRaisesRegex(audit.AuditError, "stat field type"):
                    check(snapshot, fixture)
        for field, value in (("mode", True), ("mode", -1), ("mode", 2**32),
                             ("size", True), ("size", -1), ("size", 16 * 1024 * 1024 + 1)):
            snapshot, fixture = selected_snapshot()
            set_field(snapshot, field, value)
            with self.subTest(other_field=field, value=value), self.assertRaisesRegex(audit.AuditError, "stat field type"):
                check(snapshot, fixture)

    def test_windows_api_semantics_preserve_different_raw_ctimes(self):
        transport, candidate, fixture = windows_profile_fixture()
        probes = audit._probe_timeline(transport, candidate, fixture)
        self.assertEqual(probes[0]["before"]["path_before"]["ctime_ns"], 4)
        self.assertEqual(probes[0]["before"]["handle_before"]["ctime_ns"], 8)
        self.assertEqual(probes[0]["opened_stat"], probes[0]["before"]["handle_before"])

    def test_within_api_shared_and_unknown_profile_drift_refuse(self):
        mutations = {
            "handle_change_time": lambda s: s["handle_after"].update(ctime_ns=9),
            "path_creation_time": lambda s: s["path_after"].update(ctime_ns=9),
            "explicit_birthtime": lambda s: [s[key].update(birthtime_ns=9) for key in ("handle_before", "handle_after")],
            "shared_identity": lambda s: [s[key].update(inode=9) for key in ("handle_before", "handle_after")],
            "missing_birthtime": lambda s: [s[key].pop("birthtime_ns") for key in ("path_before", "path_after")],
            "nullable_birthtime": lambda s: [s[key].update(birthtime_ns=None) for key in ("path_before", "handle_before", "handle_after", "path_after")],
            "unknown_profile": lambda s: s.update(stat_profile="unknown-python-version"),
            "fallback_cannot_ignore_ctime": lambda s: s.update(stat_profile="same-fields-v1"),
            "legacy_schema": lambda s: s.pop("stat_profile"),
        }
        for name, mutate in mutations.items():
            transport, candidate, fixture = windows_profile_fixture()
            audit._probe_timeline(transport, candidate, fixture)
            snapshot = next(row["value"]["probe"]["before"] for row in transport["transcript"] if row["kind"] == "probe_end")
            mutate(snapshot)
            with self.subTest(name=name), self.assertRaises(audit.AuditError):
                audit._probe_timeline(transport, candidate, fixture)

    def test_cross_probe_handle_change_time_and_opened_stat_are_checked(self):
        for mutation in ("across_probes", "within_probe", "opened_stat"):
            transport, candidate, fixture = windows_profile_fixture()
            audit._probe_timeline(transport, candidate, fixture)
            probe = next(row["value"]["probe"] for row in transport["transcript"]
                         if row["kind"] == "probe_end" and row["value"]["phase"] == ("baseline" if mutation == "opened_stat" else "held"))
            if mutation == "opened_stat":
                probe["opened_stat"] = copy.deepcopy(probe["before"]["path_before"])
            else:
                for snapshot in ((probe["before"], probe["after"]) if mutation == "across_probes" else (probe["after"],)):
                    for key in ("handle_before", "handle_after"):
                        snapshot[key]["ctime_ns"] = 9
            with self.subTest(mutation=mutation), self.assertRaises(audit.AuditError):
                audit._probe_timeline(transport, candidate, fixture)

    def test_exact_runtime_profile_and_downgrade_refusals(self):
        observer = dict(implementation="cpython", version="3.14.7 (authored exact runtime)", platform="win32",
                        stat_profile="cpython-3.14.7-windows-path-creation-handle-change-v1")
        plan = dict(observer_python=observer, identity_bridge_profile="win32-bhfi-same-read-fd-v1",
                    root_volume_linkage="source-same-handle-volume-pair-and-equal-python-device-v1")
        native = dict(observer_python=copy.deepcopy(observer))
        profile = audit._observer_profile(plan, native)
        for field, value in (("implementation", "pypy"), ("version", "3.14.8 different"),
                             ("platform", "linux"), ("stat_profile", "same-fields-v1")):
            changed = copy.deepcopy(native)
            changed["observer_python"][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(audit.AuditError, "differs from plan"):
                audit._observer_profile(plan, changed)
        for field, value in (("implementation", "pypy"), ("version", "3.14.8 different"),
                             ("platform", "linux"), ("stat_profile", "same-fields-v1")):
            changed = copy.deepcopy(plan)
            changed["observer_python"][field] = value
            with self.subTest(plan_field=field), self.assertRaisesRegex(audit.AuditError, "reviewed observer"):
                audit._observer_profile(changed, dict(observer_python=copy.deepcopy(changed["observer_python"])))
        audit._require_profile(dict(stat_profile=profile), profile)
        with self.assertRaisesRegex(audit.AuditError, "differs from reviewed observer"):
            audit._require_profile(dict(stat_profile="same-fields-v1"), profile)
        for field in ("identity_bridge_profile", "root_volume_linkage"):
            changed = copy.deepcopy(plan)
            changed.pop(field)
            with self.subTest(missing=field), self.assertRaisesRegex(audit.AuditError, "volume linkage missing"):
                audit._observer_profile(changed, native)


class SameHandleBridgeControls(unittest.TestCase):
    def test_same_python_volume_with_different_captured_legacy_serial_refuses(self):
        transport, _, _ = windows_profile_fixture()
        source = next(row["value"]["probe"]["before"] for row in transport["transcript"] if row["kind"] == "probe_end")
        other = copy.deepcopy(source)
        audit._same_volume_observation(other, source)
        other["bridge_before"]["volume_serial_u32"] = 78
        other["bridge_after"]["volume_serial_u32"] = 78
        with self.assertRaisesRegex(audit.AuditError, "same-volume Python/legacy observations disagree"):
            audit._same_volume_observation(other, source)

    def test_legacy_identity_exact_unsigned_widths(self):
        for volume in (0, 2**32 - 1):
            for inode in (0, 2**63, 2**64 - 1):
                value = dict(volume_serial_u32=volume, file_index_u64=inode)
                self.assertEqual(audit._legacy_identity(value), value)

    def test_captured_legacy_serial_is_not_derived_from_python_device(self):
        transport, _, fixture = windows_profile_fixture()
        snapshot = next(row["value"]["probe"]["before"] for row in transport["transcript"] if row["kind"] == "probe_end")
        for key in ("path_before", "handle_before", "handle_after", "path_after"):
            snapshot[key]["device"] = 2**63 + 123
        audit._snapshot(snapshot, fixture["source"], fixture["sourceSha256"], fixture["sourceBytes"])
        legacy = audit._bridge(snapshot)
        self.assertEqual(legacy, dict(volume_serial_u32=77, file_index_u64=2))
        self.assertNotEqual(legacy["volume_serial_u32"], snapshot["handle_before"]["device"] & 0xffffffff)
        root_identity = dict(device=2**63 + 123, inode=9)
        source_identity = dict(device=2**63 + 123, inode=2)
        encoded_identity = (77).to_bytes(8, "little") + (9).to_bytes(8, "little")
        facts = b"imageinfo-held-object-v1\0" + b"".join(value.to_bytes(8, "little") for value in (77, 9, 0, 1, 32, 3, 4, 0))
        binding = dict(identity=encoded_identity.hex(), facts=facts.hex())
        audit._root_binding(binding, root_identity, source_identity, legacy)
        for root, source, bridge in ((dict(device=123, inode=9), source_identity, legacy),
                                     (root_identity, dict(device=2**63 + 123, inode=3), legacy),
                                     (root_identity, source_identity, dict(volume_serial_u32=123, file_index_u64=2)),
                                     (dict(device=True, inode=9), source_identity, legacy)):
            with self.assertRaises(audit.AuditError):
                audit._root_binding(binding, root, source, bridge)

    def test_bridge_absence_types_bounds_and_stability_refuse(self):
        mutations = {
            "profile": lambda s: s.update(identity_bridge_profile="unavailable-non-windows-v1"),
            "absent": lambda s: s.update(bridge_before=None),
            "serial_drift": lambda s: s["bridge_after"].update(volume_serial_u32=78),
            "index_drift": lambda s: s["bridge_after"].update(file_index_u64=3),
            "index_wrong_both": lambda s: [s[key].update(file_index_u64=3) for key in ("bridge_before", "bridge_after")],
        }
        for field, values in (("volume_serial_u32", (-1, 2**32, True, 1.0)),
                              ("file_index_u64", (-1, 2**64, True, 1.0))):
            for value in values:
                mutations[(field, str(value))] = lambda s, field=field, value=value: [
                    s[key].update({field: value}) for key in ("bridge_before", "bridge_after")]
        for name, mutate in mutations.items():
            transport, _, fixture = windows_profile_fixture()
            snapshot = next(row["value"]["probe"]["before"] for row in transport["transcript"] if row["kind"] == "probe_end")
            audit._snapshot(snapshot, fixture["source"], fixture["sourceSha256"], fixture["sourceBytes"])
            mutate(snapshot)
            with self.subTest(mutation=name), self.assertRaises(audit.AuditError):
                audit._snapshot(snapshot, fixture["source"], fixture["sourceSha256"], fixture["sourceBytes"])

    def test_bridge_changes_within_and_across_probes_refuse(self):
        for across in (False, True):
            transport, candidate, fixture = windows_profile_fixture()
            audit._probe_timeline(transport, candidate, fixture)
            held = next(row["value"]["probe"] for row in transport["transcript"]
                        if row["kind"] == "probe_end" and row["value"]["phase"] == "held")
            for snapshot in ((held["before"], held["after"]) if across else (held["after"],)):
                snapshot["bridge_before"]["volume_serial_u32"] = 78
                snapshot["bridge_after"]["volume_serial_u32"] = 78
            with self.subTest(across=across), self.assertRaises(audit.AuditError):
                audit._probe_timeline(transport, candidate, fixture)


def binding_fixture(root):
    """Tiny identity evidence authored without invoking freeze or collector."""
    source_root = root / "checkout"
    (source_root / "src").mkdir(parents=True)
    observer = source_root / "experiments/0218-namespace-observer"
    observer.mkdir(parents=True)
    contents = {"src/lib.rs": b"// authored source\n", "Cargo.toml": b"# authored\n",
                "Cargo.lock": b"# authored lock\n", ".gitattributes": b"* text eol=lf\n",
                "experiments/0218-namespace-observer/audit.py": b"# authored observer\n"}
    for name in ("src/storage/namespace_diagnostic.rs", "src/storage/windows.rs", "src/storage/runtime.rs",
                 "crates/imageinfo-windows-storage/src/lib.rs", "crates/imageinfo-windows-storage/src/native.rs",
                 "crates/imageinfo-windows-storage/src/windows.rs"):
        contents[name] = b"// tiny authored source binding\n"
    contents["crates/imageinfo-windows-storage/Cargo.toml"] = b"# tiny authored SDK manifest\n"
    for name in ("freeze", "protocol", "controller", "run", "fixtures", "probe"):
        contents["experiments/0218-namespace-observer/" + name + ".py"] = b"# tiny authored observer binding\n"
    for name, raw in contents.items():
        (source_root / name).parent.mkdir(parents=True, exist_ok=True)
        (source_root / name).write_bytes(raw)
    def git(*args):
        completed = subprocess.run(["git", "-c", "core.autocrlf=false", "-c", "commit.gpgsign=false",
                                    "-c", "core.hooksPath=" + str(root / "no-hooks"),
                                    "-c", "user.name=Authored control", "-c", "user.email=authored@example.invalid",
                                    *args], cwd=source_root, capture_output=True, timeout=15, check=True)
        return completed.stdout.decode("ascii").strip()
    # This disposable repository contains tiny controls only, never project code.
    git("init", "--quiet")
    git("add", "--", ".")
    git("commit", "--quiet", "--no-verify", "-m", "Authored binding control")
    commit = git("rev-parse", "HEAD")
    worker = root / "authored-worker-placeholder.bin"
    worker.write_bytes(b"never executable; authored binding only")
    bounds = dict(deadline_seconds=30, stdout_bytes=4096, stderr_bytes=4096,
                  line_bytes=4096, events=16, command_bytes=4096, commands=16)
    plan_path, freeze_path, review_path = [root / name for name in ("plan.json", "freeze.json", "review.json")]
    observer_python = dict(implementation="cpython", version="3.14.7 (authored runtime control)", platform="win32",
                           stat_profile="cpython-3.14.7-windows-path-creation-handle-change-v1")
    plan = dict(schema="namespace-observer-plan-v1", executable=str(worker), argv=[str(worker)],
                cases=["normal", "candidate-collision"], bounds=bounds, observer_python=observer_python,
                identity_bridge_profile="win32-bhfi-same-read-fd-v1",
                root_volume_linkage="source-same-handle-volume-pair-and-equal-python-device-v1")
    plan_path.write_bytes(encoded(plan))
    def binding(path, name=None):
        raw = path.read_bytes()
        return dict(path=str(path) if name is None else name, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    frozen = dict(schema="namespace-observer-freeze-v1", root=str(source_root), git_commit=commit, source_encoding="git-lf-v1",
                  worker=binding(worker), plan=binding(plan_path),
                  sources=[binding(source_root / name, name) for name in sorted(contents)])
    freeze_path.write_bytes(encoded(frozen))
    native = dict(worker_path=str(worker), worker_sha256=binding(worker)["sha256"],
                  plan_sha256=binding(plan_path)["sha256"], freeze_sha256=binding(freeze_path)["sha256"],
                  observer_python=copy.deepcopy(observer_python))
    review = dict(schema="namespace-observer-review-v1", decision="approved", scope="two-native-controls-only",
                  reviewer="authored-control-only", plan_sha256=native["plan_sha256"], freeze_sha256=native["freeze_sha256"])
    review_path.write_bytes(encoded(review))
    native["review_sha256"] = binding(review_path)["sha256"]
    transport = dict(bounds=bounds, result=dict(command=[str(worker)]))
    return native, plan_path, freeze_path, review_path, transport


class SourceAndWorkerBindingControls(unittest.TestCase):
    def test_tiny_authored_exact_inputs_reconcile(self):
        with temporary_directory() as directory:
            args = binding_fixture(Path(directory))
            frozen, plan = audit._input_bindings(*args)
            self.assertEqual(plan["cases"], ["normal", "candidate-collision"])
            self.assertEqual(len(frozen["sources"]), 18)

    def test_source_worker_plan_freeze_review_tampering_refuses_read_only(self):
        def replace(path, raw):
            path.write_bytes(raw)
        def source(args):
            return Path(json.loads(args[2].read_bytes())["root"]) / "src/lib.rs"
        mutations = {
            "changed_source_bytes": lambda a: replace(source(a), b"// changed\n"),
            "source_line_endings": lambda a: replace(source(a), b"// authored source\r\n"),
            "source_inventory_addition": lambda a: replace(source(a).parent / "extra.rs", b"// extra\n"),
            "worker_replaced": lambda a: replace(Path(a[0]["worker_path"]), b"different worker"),
            "worker_claim": lambda a: a[0].update(worker_sha256="0" * 64),
            "plan_changed": lambda a: replace(a[1], b"{}\n"),
            "freeze_changed": lambda a: replace(a[2], b"{}\n"),
            "review_changed": lambda a: replace(a[3], b"{}\n"),
            "plan_claim": lambda a: a[0].update(plan_sha256="0" * 64),
            "freeze_claim": lambda a: a[0].update(freeze_sha256="0" * 64),
            "review_claim": lambda a: a[0].update(review_sha256="0" * 64),
            "executed_argv_changed": lambda a: a[4]["result"].update(command=["other-worker"]),
            "executed_bounds_changed": lambda a: a[4]["bounds"].update(events=1),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name), temporary_directory() as directory:
                root = Path(directory)
                args = binding_fixture(root)
                audit._input_bindings(*args)
                mutate(args)
                before = {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}
                reasons = {
                    "changed_source_bytes": "file binding changed", "source_line_endings": "exact Git LF",
                    "source_inventory_addition": "source omitted/duplicate/inventory changed",
                    "worker_replaced": "file binding changed", "worker_claim": "worker digest mismatch",
                    "plan_changed": "file binding changed", "freeze_changed": "freeze digest mismatch",
                    "review_changed": "review digest mismatch", "plan_claim": "plan digest mismatch",
                    "freeze_claim": "freeze digest mismatch", "review_claim": "review digest mismatch",
                    "executed_argv_changed": "executed argv/bounds", "executed_bounds_changed": "executed argv/bounds",
                }
                with self.assertRaisesRegex(audit.AuditError, reasons[name]):
                    audit._input_bindings(*args)
                self.assertEqual({path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}, before)


class RetainedEncodingControls(unittest.TestCase):
    def test_duplicate_members_and_nonfinite_values_refuse(self):
        for raw in (b'{"exit_code":0,"exit_code":1}',
                    b'{"nested":{"seq":1,"seq":2}}',
                    b'{"elapsed_seconds":NaN}', b'{"elapsed_seconds":Infinity}',
                    b'{"name":"\xff"}'):
            with self.subTest(raw=raw), self.assertRaises(audit.AuditError):
                audit._json(raw)

    def test_jsonl_truncation_blank_and_count_bounds_refuse(self):
        with temporary_directory() as directory:
            path = Path(directory) / "retained.jsonl"
            for raw, count in ((b'{}', 2), (b'{}\n\n', 2), (b'{}\n{}\n', 1)):
                path.write_bytes(raw)
                with self.subTest(raw=raw), self.assertRaises(audit.AuditError):
                    audit._lines(path, count=count)

    def test_oversize_retained_file_refuses_without_rewrite(self):
        with temporary_directory() as directory:
            path = Path(directory) / "oversize.bin"
            raw = b"authored-bound-control"
            path.write_bytes(raw)
            with self.assertRaises(audit.AuditError):
                audit._read(path, 3)
            self.assertEqual(path.read_bytes(), raw)

    def test_relative_paths_cannot_escape_attempt(self):
        with temporary_directory() as directory:
            root = Path(directory)
            for name in ("../outside", "a/../../outside", "C:/outside", "\\outside", "a\\b", "", "."):
                with self.subTest(name=name), self.assertRaises(audit.AuditError):
                    audit._bounded_path(root, name)

    def test_noncanonical_hex_and_overbound_capture_refuse(self):
        for value, maximum in (("AA", 1), ("00 01", 3), ("0", 1), ("zz", 1), ("0001", 1)):
            with self.subTest(value=value), self.assertRaises(audit.AuditError):
                audit._hex(value, maximum)


if __name__ == "__main__":
    unittest.main()
