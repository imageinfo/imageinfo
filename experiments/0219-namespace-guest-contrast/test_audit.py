"""Independent authored retained-evidence controls; no native or guest actions."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path, PureWindowsPath
import tempfile
import subprocess
import unittest

import audit


def encoded(value):
    return (json.dumps(value, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def temporary_directory():
    parent = Path(__file__).resolve().parents[2] / ".local" / "0219-authored-tests"
    parent.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(prefix="audit-", dir=parent)


def repeated_digest(byte, count):
    digest = hashlib.sha256()
    block = bytes((byte,)) * 65536
    while count:
        piece = block[:min(count, len(block))]
        digest.update(piece)
        count -= len(piece)
    return digest.hexdigest()


def source_snapshot(path, *, inode=2, count=16 * 1024 * 1024):
    """Synthetic raw Python64 and independently captured legacy32 identity."""
    facts = dict(device=2**63 + 123, inode=inode, mode=0o100666, size=count,
                 mtime_ns=4, ctime_ns=3, birthtime_ns=3)
    result = dict(path=path, max_bytes=count, status="ok", error=None, reason=None,
                  stat_profile="cpython-3.14.7-windows-path-creation-handle-change-v1",
                  identity_bridge_profile="win32-bhfi-same-read-fd-v1",
                  bridge_before=dict(volume_serial_u32=77, file_index_u64=inode),
                  bridge_after=dict(volume_serial_u32=77, file_index_u64=inode),
                  bytes_read=count, sha256=repeated_digest(0x53, count),
                  observations_match=True)
    result.update({key: deepcopy(facts) for key in
                   ("path_before", "handle_before", "handle_after", "path_after")})
    return result


NORMAL = (
    "preflight", "create-root", "root-flush", "parent-flush", "create-Candidate",
    "check-CandidateChecked", "file-Candidate", "root-flush", "create-Prepared",
    "check-PreparedChecked", "file-Prepared", "root-flush", "create-Intent",
    "check-IntentChecked", "file-Intent", "root-flush", "release", "check-Prepublication",
    "publish", "check-Installed", "file-Candidate", "root-flush", "check-InstalledRechecked",
    "create-Observation", "check-ObservationChecked", "file-Observation", "root-flush",
    "create-Receipt", "check-ReceiptChecked", "file-Receipt", "check-ReceiptFileChecked",
    "root-flush", "check-ReceiptParentChecked", "checked-context", "check-Final", "terminal")


def held_binding(inode, count=0, digest=None):
    identity = (77).to_bytes(8, "little") + inode.to_bytes(8, "little")
    facts = b"imageinfo-held-object-v1\0" + b"".join(
        number.to_bytes(8, "little") for number in (77, inode, count, 32, 3, 3, 4, 0))
    if digest is not None:
        facts += bytes.fromhex(digest)
    return dict(identity=identity.hex(), facts=facts.hex())


PHASES = (
    "Preflight", "RootCreated", "RootFlushed", "ParentFlushed", "CandidateCreated",
    "CandidateChecked", "CandidateFlushed", "CandidateParentFlushed", "PreparedCreated",
    "PreparedChecked", "PreparedFlushed", "PreparedParentFlushed", "IntentCreated", "IntentChecked",
    "IntentFlushed", "IntentParentFlushed", "CallerRelease", "Prepublication", "Publish", "Installed",
    "InstalledFlushed", "InstalledParentFlushed", "InstalledRechecked", "ObservationCreated",
    "ObservationChecked", "ObservationFlushed", "ObservationParentFlushed", "ReceiptCreated", "ReceiptChecked",
    "ReceiptFlushed", "ReceiptFileChecked", "ReceiptParentFlushed", "ReceiptParentChecked", "CheckedContext",
    "Final", "TerminalExport")


def worker_fixture(root, *, success=False, unit="authored219", identity_offset=0,
                   failure_at=None, failure="BackendIo", native_error=("Other", 1117)):
    """Write raw retained captures from an independently authored finite actor."""
    bounds = dict(deadline_seconds=30, stdout_bytes=1048576, stderr_bytes=4096,
                  line_bytes=32768, events=128, command_bytes=1024, commands=64)
    argv = ["authored-not-an-executable"]
    transcript = [dict(kind="start", value=dict(command=argv, bounds=bounds), child_alive=False)]
    events, captures = [], []
    failed_index = failure_at if failure_at is not None else (None if success else 4)
    completed = failed_index is None
    operations = NORMAL if completed else NORMAL[:failed_index + 1]
    pairs = [(kind, stage) for stage in operations
             for kind in ("before_operation", "candidate_result" if stage == "create-Candidate" else "operation_result")]
    pairs += [("runtime_result", "runtime"), ("backend_dropped", "backend-drop")]
    held = []
    for seq, (kind, stage) in enumerate(pairs, 1):
        result = None
        if kind in ("operation_result", "candidate_result"):
            failed = failed_index is not None and seq == 2 * (failed_index + 1)
            result = dict(success=not failed, failure=failure if failed else None,
                          native_error_kind=native_error[0] if failed else None,
                          native_os_error=native_error[1] if failed else None)
        elif kind == "runtime_result":
            published = completed or failed_index >= 18
            released = completed or failed_index >= 16
            status = ("Refused" if completed else "RecoveryRequired" if published else
                      "FailedBeforePublish" if failure in ("BackendIo", "SourceIo", "Ambiguous") else
                      "Conflict" if failure in ("Conflict", "InvalidBinding") else "Refused")
            result = dict(status=status,
                          phase="TerminalExport" if completed else PHASES[failed_index],
                          failure=None if completed else failure, publication_possible=published,
                          release_possible=released, protocol_complete=completed,
                          retained_material=True, pending_cleanup=True, charged_bytes=4718592)
        if kind in ("operation_result", "candidate_result") and result["success"]:
            if stage == "preflight":
                held.append(held_binding(identity_offset + 2, 16777216, repeated_digest(0x53, 16777216)))
            elif stage == "create-root":
                held.append(held_binding(identity_offset + 1))
            elif stage.startswith("create-"):
                held.append(held_binding(identity_offset + len(held) + 1, 4194304 if stage == "create-Candidate" else 1,
                                         repeated_digest(0x18, 4194304) if stage == "create-Candidate" else hashlib.sha256(b"r").hexdigest()))
        event = dict(v=1, unit=unit, seq=seq, kind=kind, stage=stage, result=result,
                     bindings=[] if kind == "backend_dropped" else deepcopy(held), **dict.fromkeys(audit.FLAGS, False))
        events.append(event)
        captures.append(b"IMAGEINFO218 " + encoded(event))
        transcript.append(dict(kind="stdout_line", value=dict(line=seq), child_alive=True))
        if kind in ("before_operation", "candidate_result"):
            command = {key: event[key] for key in ("v", "unit", "seq", "stage")}
            command["command"] = "release" if kind == "candidate_result" else "continue"
            transcript.append(dict(kind="observation_acknowledged", child_alive=True,
                                   value=dict(event_seq=seq, command=command["command"])))
            transcript.append(dict(kind="command_sent", child_alive=True,
                                   value=dict(bytes_hex=encoded(command).hex())))
    transcript.append(dict(kind="exit", child_alive=False, value=dict(exit_code=0,
                          exit_confirmed=True, status="transport_complete", reason="child_exit_zero")))
    for seq, row in enumerate(transcript, 1):
        row.update(seq=seq, elapsed_ns=seq)
    stdout = b"".join(captures)
    result = dict(schema="namespace-observer-run-v1", command=argv, bounds=bounds,
                  status="transport_complete", reason="child_exit_zero", exit_code=0,
                  lines=len(events), commands=sum(row["kind"] == "command_sent" for row in transcript),
                  stdout_bytes=len(stdout), stderr_bytes=0, child_killed=False, replayed=False,
                  threads_stopped=True, elapsed_seconds=0.01, exit_confirmed=True,
                  capture_drain_complete=True, cleanup_errors=[], child_pid=219)
    value = dict(result=result, stdout=stdout, stderr=b"", transcript=transcript,
                 events=[dict(line=seq, bytes_hex=raw.hex()) for seq, raw in enumerate(captures, 1)])
    write_worker(root, value)
    return value


def write_worker(root, value):
    (root / "result.json").write_bytes(encoded(value["result"]))
    for key in ("stdout", "stderr"):
        (root / (key + ".bin")).write_bytes(value[key])
    for key in ("transcript", "events"):
        (root / (key + ".jsonl")).write_bytes(b"".join(map(encoded, value[key])))


def replace_worker_event(value, index, change):
    raw = bytes.fromhex(value["events"][index]["bytes_hex"])
    event = json.loads(raw[len(b"IMAGEINFO218 "):])
    change(event)
    value["events"][index]["bytes_hex"] = (b"IMAGEINFO218 " + encoded(event)).hex()
    value["stdout"] = b"".join(bytes.fromhex(row["bytes_hex"]) for row in value["events"])
    value["result"]["stdout_bytes"] = len(value["stdout"])


class WorkerCaptureControls(unittest.TestCase):
    def test_final_release_sampled_dead_accepts_backendio_and_success_with_live_prewrite(self):
        for success in (False, True):
            with self.subTest(success=success), temporary_directory() as directory:
                root = Path(directory)
                value = worker_fixture(root, success=success)
                last = max(index for index, row in enumerate(value["transcript"]) if row["kind"] == "command_sent")
                for row in value["transcript"][last:]:
                    row["child_alive"] = False
                write_worker(root, value)
                result = audit.audit_worker(root, "authored219")
                self.assertEqual(result["runtime"]["failure"], None if success else "BackendIo")
                prewrite = value["transcript"][last - 1]
                self.assertEqual(prewrite["kind"], "observation_acknowledged")
                prewrite["child_alive"] = False
                write_worker(root, value)
                with self.assertRaisesRegex(audit.AuditError, "prewrite"):
                    audit.audit_worker(root, "authored219")

    def test_both_authored_candidate_outcomes_keep_actual_native_interface(self):
        for success in (False, True):
            with self.subTest(success=success), temporary_directory() as directory:
                root = Path(directory)
                worker_fixture(root, success=success)
                result = audit.audit_worker(root, "authored219")
                self.assertIs(result["candidate"]["result"]["success"], success)
                self.assertEqual(result["candidate"]["result"]["native_os_error"], None if success else 1117)
                self.assertLess(result["candidate_receive_seq"], result["release_seq"])

    def test_retained_worker_capture_and_actual_error_mutations_refuse(self):
        mutations = {
            "capture_truncated": lambda v: v.update(stdout=v["stdout"][:-1]),
            "exit_unknown": lambda v: v["result"].update(exit_confirmed=False),
            "drain_incomplete": lambda v: v["result"].update(capture_drain_complete=False),
            "native_os_error_without_kind": lambda v: replace_worker_event(v, 9, lambda e: e["result"].update(native_error_kind=None)),
            "injected_error_as_native": lambda v: replace_worker_event(v, 9, lambda e: e["result"].update(controller_injected=True)),
            "positive_admission": lambda v: replace_worker_event(v, 9, lambda e: e.update(committed=True)),
            "wrong_worker_unit": lambda v: replace_worker_event(v, 2, lambda e: e.update(unit="other")),
            "compound_result_omitted": lambda v: replace_worker_event(v, 9, lambda e: e.update(kind="operation_result")),
            "runtime_phase": lambda v: replace_worker_event(v, -2, lambda e: e["result"].update(phase="Preflight")),
            "runtime_charge": lambda v: replace_worker_event(v, -2, lambda e: e["result"].update(charged_bytes=4194304)),
            "runtime_protocol": lambda v: replace_worker_event(v, -2, lambda e: e["result"].update(protocol_complete=True)),
            "candidate_release_wrong": lambda v: next(row for row in reversed(v["transcript"]) if row["kind"] == "command_sent")["value"].update(bytes_hex=encoded(dict(v=1, unit="authored219", seq=10, stage="create-Candidate", command="continue")).hex()),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name), temporary_directory() as directory:
                root = Path(directory)
                value = worker_fixture(root)
                audit.audit_worker(root, "authored219")
                mutate(value)
                write_worker(root, value)
                before = {path.name: path.read_bytes() for path in root.iterdir()}
                with self.assertRaises(audit.AuditError):
                    audit.audit_worker(root, "authored219")
                self.assertEqual({path.name: path.read_bytes() for path in root.iterdir()}, before)


class LaterFailurePrefixControls(unittest.TestCase):
    def test_candidate_success_then_first_later_failure_retains_finite_prefix(self):
        for index in (5, 6, 16, 18, 19, 35):
            for failure, native in (("SourceIo", ("Other", 1117)), ("Unsupported", (None, None))):
                with self.subTest(index=index, failure=failure), temporary_directory() as directory:
                    root = Path(directory)
                    guest_fixture(root, success=True, failure_at=index, failure=failure, native_error=native)
                    result = audit.audit_guest(root)
                    worker = result["worker"]
                    self.assertIs(worker["candidate"]["result"]["success"], True)
                    self.assertEqual(worker["runtime"]["phase"], PHASES[index])
                    self.assertEqual(worker["runtime"]["failure"], failure)
                    self.assertIs(worker["runtime"]["protocol_complete"], False)
                    self.assertEqual(len(worker["events"]), 2 * (index + 1) + 2)
                    last_sdk = worker["events"][-3]["result"]
                    self.assertEqual((last_sdk["native_error_kind"], last_sdk["native_os_error"]), native)
                    self.assertTrue(all(result["guest"][key] is False for key in audit.FLAGS))

    def test_failed_prefix_does_not_authorize_more_operations_or_fabricated_runtime(self):
        mutations = {
            "extra_operations_after_failure": lambda v: replace_worker_event(v, 11, lambda e: e["result"].update(success=False, failure="SourceIo", native_error_kind="Other", native_os_error=1117)),
            "runtime_complete": lambda v: replace_worker_event(v, -2, lambda e: e["result"].update(protocol_complete=True)),
            "runtime_phase": lambda v: replace_worker_event(v, -2, lambda e: e["result"].update(phase="TerminalExport")),
            "runtime_publication": lambda v: replace_worker_event(v, -2, lambda e: e["result"].update(publication_possible=True)),
            "positive_admission": lambda v: replace_worker_event(v, -2, lambda e: e.update(raw_admitted=True)),
            "wrong_later_ack": lambda v: next(row for row in reversed(v["transcript"]) if row["kind"] == "command_sent")["value"].update(bytes_hex=encoded(dict(v=1, unit="authored219", seq=11, stage="check-CandidateChecked", command="cancel")).hex()),
            "missing_explicit_candidate_release": lambda v: next(row for row in v["transcript"] if row["kind"] == "command_sent" and json.loads(bytes.fromhex(row["value"]["bytes_hex"]))["seq"] == 10)["value"].update(bytes_hex=encoded(dict(v=1, unit="authored219", seq=10, stage="create-Candidate", command="continue")).hex()),
            "release_sample_contradicts_later_live_operations": lambda v: next(row for row in v["transcript"] if row["kind"] == "command_sent" and json.loads(bytes.fromhex(row["value"]["bytes_hex"]))["seq"] == 10).update(child_alive=False),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name), temporary_directory() as directory:
                root = Path(directory)
                value = worker_fixture(root, success=True) if name == "extra_operations_after_failure" else worker_fixture(
                    root, success=True, failure_at=5, failure="SourceIo")
                audit.audit_worker(root, "authored219")
                mutate(value)
                write_worker(root, value)
                with self.assertRaises(audit.AuditError):
                    audit.audit_worker(root, "authored219")

    def test_semantic_unsupported_null_pair_is_distinct_from_malformed_native_error(self):
        for native in ((None, None), ("Other", None), ("Unsupported", None)):
            with self.subTest(valid_native=native), temporary_directory() as directory:
                root = Path(directory)
                worker_fixture(root, success=True, failure_at=5, failure="Unsupported", native_error=native)
                result = audit.audit_worker(root, "authored219")
                self.assertEqual((result["events"][-3]["result"]["native_error_kind"],
                                  result["events"][-3]["result"]["native_os_error"]), native)
        for native in ((None, 1117), (True, 1117), ("Other", True)):
            with self.subTest(native=native), temporary_directory() as directory:
                root = Path(directory)
                value = worker_fixture(root, success=True, failure_at=5, failure="Unsupported", native_error=(None, None))
                audit.audit_worker(root, "authored219")
                replace_worker_event(value, 11, lambda event: event["result"].update(native_error_kind=native[0], native_os_error=native[1]))
                write_worker(root, value)
                with self.assertRaises(audit.AuditError):
                    audit.audit_worker(root, "authored219")
        with temporary_directory() as directory:
            root = Path(directory)
            worker_fixture(root, success=True, failure_at=3, failure="SourceIo")
            with self.assertRaises(audit.AuditError):
                audit.audit_worker(root, "authored219")


def snapshot_fixture(phase="prepared", case="persistent-write-error"):
    root = "C:\\authored219\\" + case
    names = dict(source="source.bin", preparedSource="source.bin", candidate="unit\\candidate.bin",
                 output="unit\\output.bin", prepared="unit\\prepared.record", intent="unit\\intent.record",
                 observation="unit\\observation.record", receipt="unit\\receipt.record")
    fixture = dict(root=root, case=case, unit="authored219", sourceBytes=16777216,
                   sourceSha256=repeated_digest(0x53, 16777216),
                   sourceIdentity=dict(device=2**63 + 123, inode=2))
    fixture.update({key: root + "\\" + relative for key, relative in names.items()})
    fixture["old"] = "C:\\authored219\\source.bin"
    fixture["sourceVolumeRoot"] = "C:\\authored219"
    names["old"] = "ignored"
    def absent(path):
        return dict(path=path, status="error", error=dict(type="FileNotFoundError", errno=2, winerror=2))
    def directory(path):
        return dict(path=path, status="ok", stat=dict(device=2**63 + 123, inode=1, mode=0o40777,
                    size=0, mtime_ns=4, ctime_ns=3, birthtime_ns=3),
                    entries=[], error=None, reason=None)
    snapshot = dict(schema="imageinfo-0219-fixture-snapshot-v1", case=case,
                    unit="authored219", phase=phase, root=root, cleanupAuthorized=False,
                    directories=dict(volume=directory(fixture["sourceVolumeRoot"]), root=directory(root), unit=directory(root + "\\unit")),
                    paths={key: absent(fixture[key]) for key in names})
    snapshot["paths"]["source"] = source_snapshot(fixture["source"])
    snapshot["paths"]["preparedSource"] = deepcopy(snapshot["paths"]["source"])
    return snapshot, fixture


class NameAndIdentityControls(unittest.TestCase):
    def test_raw64_identity_remains_distinct_from_independent_legacy32_bridge(self):
        snapshot, fixture = snapshot_fixture()
        audit._snapshot_observation(snapshot, fixture, "prepared")
        raw = snapshot["paths"]["source"]
        self.assertGreater(raw["handle_before"]["device"], 2**63)
        self.assertNotEqual(raw["handle_before"]["device"] & 0xffffffff,
                            raw["bridge_before"]["volume_serial_u32"])

    def test_old_prepared_source_bytes_raw_widths_and_bridge_mutations_refuse(self):
        def both(value, change):
            for key in ("source", "preparedSource"):
                change(value["paths"][key])
        mutations = {
            "source_bytes": lambda s: both(s, lambda p: p.update(sha256="0" * 64)),
            "source_size": lambda s: both(s, lambda p: p.update(bytes_read=16777215)),
            "old_missing": lambda s: s["paths"].pop("old"),
            "old_wrong_path": lambda s: s["paths"]["old"].update(path="C:\\other"),
            "old_error_erased": lambda s: s["paths"]["old"].update(status="error", error=None),
            "prepared_missing": lambda s: s["paths"].pop("prepared"),
            "prepared_error_erased": lambda s: s["paths"]["prepared"].update(error=None),
            "raw_device_over64": lambda s: both(s, lambda p: [p[k].update(device=2**64) for k in ("path_before", "handle_before", "handle_after", "path_after")]),
            "raw_inode_boolean": lambda s: both(s, lambda p: [p[k].update(inode=True) for k in ("path_before", "handle_before", "handle_after", "path_after")]),
            "bridge_over32": lambda s: both(s, lambda p: [p[k].update(volume_serial_u32=2**32) for k in ("bridge_before", "bridge_after")]),
            "bridge_over64": lambda s: both(s, lambda p: [p[k].update(file_index_u64=2**64) for k in ("bridge_before", "bridge_after")]),
            "bridge_different_fd": lambda s: both(s, lambda p: p["bridge_after"].update(file_index_u64=3)),
            "bridge_raw_truncated": lambda s: both(s, lambda p: [p[k].update(file_index_u64=1) for k in ("bridge_before", "bridge_after")]),
            "bridge_missing": lambda s: both(s, lambda p: p.update(bridge_before=None)),
        }
        for name, mutate in mutations.items():
            snapshot, fixture = snapshot_fixture()
            audit._snapshot_observation(snapshot, fixture, "prepared")
            mutate(snapshot)
            with self.subTest(name=name), self.assertRaises(audit.AuditError):
                audit._snapshot_observation(snapshot, fixture, "prepared")

    def test_genuine_postarm_old_lookup_failure_is_retained_not_normalized_away(self):
        snapshot, fixture = snapshot_fixture("candidate_hold")
        error = dict(path=fixture["source"], status="error",
                     error=dict(type="OSError", errno=5, winerror=1117))
        snapshot["paths"]["source"] = deepcopy(error)
        snapshot["paths"]["preparedSource"] = deepcopy(error)
        snapshot["paths"]["old"] = dict(path=fixture["old"], status="error", error=deepcopy(error["error"]))
        result = audit._snapshot_observation(snapshot, fixture, "candidate_hold")
        self.assertEqual(result["paths"]["old"]["error"]["winerror"], 1117)


class PostarmProbeControls(unittest.TestCase):
    def probe(self):
        snapshot, fixture = snapshot_fixture("candidate_hold")
        source = snapshot["paths"]["source"]
        probe = dict(path=fixture["source"], expected_access=False, flags=32769,
                     before=deepcopy(source), after=deepcopy(source), status="open_error",
                     error=dict(type="PermissionError", errno=13, winerror=32), close_error=None,
                     opened_stat=None, denial_observation="win32_sharing_violation",
                     source_unchanged=True, expectation_met=True)
        return probe, fixture

    def test_genuine_not_attempted_handle_stat_close_and_raced_observations_remain_findings(self):
        for finding in ("not_attempted", "handle_stat_error", "close_error", "raced_properties"):
            probe, fixture = self.probe()
            audit._write_probe(probe, fixture, "candidate_hold")
            if finding == "not_attempted":
                probe.update(before=dict(path=fixture["source"], status="error",
                    error=dict(type="OSError", errno=5, winerror=1117)), after=None,
                    status="not_attempted", error=None, denial_observation=None,
                    source_unchanged=False, expectation_met=False)
            elif finding == "handle_stat_error":
                probe.update(status="handle_stat_error", error=dict(type="OSError", errno=5, winerror=1117),
                             denial_observation=None, expectation_met=False)
            elif finding == "close_error":
                probe.update(close_error=dict(type="OSError", errno=5, winerror=1117), expectation_met=False)
            else:
                probe["after"]["handle_after"]["ctime_ns"] = 9
                probe["after"]["observations_match"] = False
                probe.update(source_unchanged=False, expectation_met=False)
            with self.subTest(finding=finding):
                before, after = audit._write_probe(probe, fixture, "candidate_hold")
                self.assertEqual(before["path"], fixture["source"])
                if finding == "not_attempted":
                    self.assertIsNone(after)
                    with self.assertRaises(audit.AuditError):
                        audit._write_probe(probe, fixture, "before_candidate_hold")

    def test_malformed_native_errors_stats_and_false_preservation_refuse(self):
        mutations = {
            "errno_boolean": lambda p: p["error"].update(errno=True),
            "winerror_string": lambda p: p["error"].update(winerror="1117"),
            "winerror_overflow": lambda p: p["error"].update(winerror=2**32),
            "close_error_untyped": lambda p: p.update(close_error="lost"),
            "opened_stat_untyped": lambda p: p.update(status="opened", error=None, denial_observation=None, opened_stat=dict(inode="bad")),
            "raced_stat_untyped": lambda p: (p["after"].update(observations_match=False), p["after"]["handle_after"].update(inode=True)),
            "false_preservation": lambda p: p["after"].update(observations_match=False),
            "false_expectation": lambda p: p.update(expectation_met=False),
        }
        for name, mutate in mutations.items():
            probe, fixture = self.probe()
            audit._write_probe(probe, fixture, "candidate_hold")
            mutate(probe)
            with self.subTest(name=name), self.assertRaises(audit.AuditError):
                audit._write_probe(probe, fixture, "candidate_hold")


def guest_fixture(root, *, success=False, case="persistent-write-error", unit="authored219",
                  failure_at=None, failure="BackendIo", native_error=("Other", 1117)):
    offset = 100 if case == "no-error" else 0
    value = worker_fixture(root, success=success, unit=unit, identity_offset=offset,
                           failure_at=failure_at, failure=failure, native_error=native_error)
    template, fixture = snapshot_fixture(case=case)
    if offset:
        fixture["sourceIdentity"]["inode"] += offset
        for name in ("source", "preparedSource"):
            template["paths"][name] = source_snapshot(fixture[name], inode=offset + 2)
        for directory in template["directories"].values():
            directory["stat"]["inode"] += offset
    fixture.update(unit=unit, schema="imageinfo-0219-fixture-v1", transactionDir="unit",
                   candidateBytes=4194304, sourceByte=0x53, candidateByte=0x18,
                   candidateSha256=repeated_digest(0x18, 4194304), authoredOnly=True,
                   cleanupAuthorized=False, unitInitiallyAbsent=True, outputExpectedAbsent=True,
                   rootIdentity=dict(device=2**63 + 123, inode=offset + 1))
    template["unit"] = unit
    fixture.update(preparationMode="existing_offline_seed", explicitPreparationFlush=False,
                   durablePreparationAcknowledged=False, historicalPayloadByte=0x31, historicalPayloadChanged=True)
    marker = b"imageinfo-0219-disposable-authored-only-v1\n"
    fixture.update(requiredWorkerMarker=dict(path=fixture["root"] + "\\fixture219.marker", bytes=len(marker),
                   sha256=hashlib.sha256(marker).hexdigest()), historicalMetadataPreparationChanged=True,
                   manifestPersistedOnTestVolume=False)
    source_raw = template["paths"]["source"]
    def move_read(path):
        return dict(path=path, pathBefore=deepcopy(source_raw["path_before"]),
                    handleBefore=deepcopy(source_raw["handle_before"]), handleAfter=deepcopy(source_raw["handle_after"]),
                    pathAfter=deepcopy(source_raw["path_after"]), bytesRead=16777216,
                    sha256=fixture["sourceSha256"], identity=fixture["sourceIdentity"])
    fixture["sourceMove"] = dict(before=move_read(fixture["old"]), after=move_read(fixture["source"]),
        identityBefore=fixture["sourceIdentity"], identityAfter=fixture["sourceIdentity"], sameObject=True)
    for phase in ("originalInventory", "preparedInventory"):
        inventory = deepcopy(template["directories"])
        inventory["paths"] = {}
        for name, path in ((name, fixture[name]) for name in template["paths"]):
            exists = name == "old" if phase == "originalInventory" else name in ("source", "preparedSource")
            inventory["paths"][name] = dict(path=path, status="ok" if exists else "error",
                stat=deepcopy(source_raw["path_before"]) if exists else None,
                error=None if exists else dict(type="FileNotFoundError", errno=2, winerror=2), reason=None)
        fixture[phase] = inventory
    timeline = [value["transcript"][0]]
    notes, observations, outer = [], [], []
    alive = False
    def note(kind, content):
        row = dict(seq=len(notes) + 1, elapsed_ns=len(notes) + 1, kind=kind, value=deepcopy(content))
        notes.append(row)
        timeline.append(dict(kind="guest_" + kind, child_alive=alive, value=deepcopy(content)))
    def observe(phase):
        snapshot = deepcopy(template)
        snapshot["phase"] = phase
        permitted = phase in ("prepared", "exited")
        source = snapshot["paths"]["source"]
        probe = dict(path=fixture["source"], expected_access=permitted, flags=32769,
                     before=deepcopy(source), after=deepcopy(source), close_error=None,
                     source_unchanged=True, expectation_met=True,
                     status="opened" if permitted else "open_error",
                     opened_stat=deepcopy(source["handle_before"]) if permitted else None,
                     error=None if permitted else dict(type="PermissionError", errno=13, winerror=32),
                     denial_observation=None if permitted else "win32_sharing_violation")
        result = dict(phase=phase, snapshot=snapshot, write_probe=probe)
        observations.append(result)
        note("observation_begin", dict(phase=phase))
        note("observation_end", result)
        return result
    def emit(stage, worker=None, observation=None):
        event = dict(v=1, unit=unit, case=case, seq=len(outer) + 1, stage=stage,
                     observation=observation or dict(authored=True), worker_event=deepcopy(worker),
                     **dict.fromkeys(audit.FLAGS, False))
        outer.append(event)
        note("event", dict(bytes_hex=(b"IMAGEINFO219 " + encoded(event)).hex()))
        commands = dict(prepared="start", source_reopened_hold="continue", before_candidate_hold="armed", candidate_hold="cleared", cleared_hold="release")
        if stage in commands:
            command = {key: event[key] for key in ("v", "unit", "case", "seq", "stage")}
            command["command"] = commands[stage]
            note("command_received", dict(bytes_hex=encoded(command).hex()))
    prepared = observe("prepared")
    volume = dict(device_serial="SER219", root=fixture["root"], unit=unit,
                  disk_number=2, partition_number=1, filesystem="NTFS", is_boot=False,
                  is_system=False, volume_unique_id="authored-volume", volume_serial="4D")
    (root / "volume-binding.json").write_bytes(encoded(volume))
    emit("prepared", observation=dict(**prepared, volume_binding=volume,
         volume_binding_file_sha256=hashlib.sha256(encoded(volume)).hexdigest()))
    alive = True
    timeline.append(dict(kind="child_started", child_alive=True, value=dict(pid=219)))
    candidate = None
    for row in value["transcript"][1:]:
        if row["kind"] == "exit":
            alive = False
            timeline.append(deepcopy(row))
            exited = observe("exited")
            emit("exited", observation=dict(observation=exited, exit_confirmed=True, exit_code=0))
            final = deepcopy(template)
            final["phase"] = "final"
            if success:
                actual_held = json.loads(bytes.fromhex(value["events"][-2]["bytes_hex"])[len(b"IMAGEINFO218 "):])["bindings"]
                candidate_name = "candidate" if failure_at is not None and failure_at <= 18 else "output"
                final_names = (candidate_name, "prepared", "intent", "observation", "receipt")[:len(actual_held) - 2]
                for inode, name in enumerate(final_names, 3):
                    final["paths"][name] = source_snapshot(fixture[name], inode=offset + inode,
                        count=4194304 if name in ("candidate", "output") else 1)
                    final["paths"][name]["sha256"] = (repeated_digest(0x18, 4194304) if name in ("candidate", "output")
                                                          else hashlib.sha256(b"r").hexdigest())
            emit("final", observation=dict(protocol_complete=True, snapshot=final))
            continue
        timeline.append(deepcopy(row))
        if row["kind"] == "stdout_line":
            event = json.loads(bytes.fromhex(value["events"][row["value"]["line"] - 1]["bytes_hex"])[len(b"IMAGEINFO218 "):])
            note("worker_event", event)
            if event["seq"] == 3:
                observed = observe("source_reopened_hold")
                emit("source_reopened_hold", event, observed)
            if event["seq"] == 9:
                observed = observe("before_candidate_hold")
                emit("before_candidate_hold", event, observed)
            if event["seq"] == 10:
                candidate = event
                observed = observe("candidate_hold")
                emit("candidate_hold", event, observed)
                observed = observe("cleared_hold")
                emit("cleared_hold", event, observed)
            if event["kind"] in ("runtime_result", "backend_dropped"):
                emit(event["kind"], event)
        if row["kind"] == "command_sent":
            note("worker_command_sent", row["value"])
            command = json.loads(bytes.fromhex(row["value"]["bytes_hex"]))
            if command["command"] == "release":
                emit("released", candidate, dict(child_release_write_flush_confirmed=True))
    for seq, row in enumerate(timeline, 1):
        row.update(seq=seq, elapsed_ns=seq)
    value["transcript"] = timeline
    write_worker(root, value)
    guest = dict(schema="imageinfo-0219-guest-v1", unit=unit, case=case, fixture=fixture,
                 status="transport_complete", protocol_complete=True, replayed=False,
                 child_started=True, transport=value["result"], observations=observations, final_snapshot=final,
                 **dict.fromkeys(audit.FLAGS, False))
    (root / "guest.json").write_bytes(encoded(guest))
    (root / "guest-transcript.jsonl").write_bytes(b"".join(map(encoded, notes)))
    return dict(worker=value, guest=guest, notes=notes)


class GuestRetainedControls(unittest.TestCase):
    def test_authored_full_guest_baselines_for_error_and_control(self):
        for success, case in ((False, "persistent-write-error"), (True, "no-error")):
            with self.subTest(case=case), temporary_directory() as directory:
                root = Path(directory)
                guest_fixture(root, success=success, case=case)
                result = audit.audit_guest(root)
                self.assertEqual(result["guest"]["case"], case)

    def test_release_before_clear_and_postexit_before_confirmation_refuse(self):
        for mutation in ("release_before_clear", "postexit_before_exit", "missing_prepared_lookup"):
            with self.subTest(mutation=mutation), temporary_directory() as directory:
                root = Path(directory)
                value = guest_fixture(root)
                audit.audit_guest(root)
                timeline = value["worker"]["transcript"]
                if mutation == "release_before_clear":
                    release = next(row for row in timeline if row["kind"] == "command_sent"
                                   and json.loads(bytes.fromhex(row["value"]["bytes_hex"]))["command"] == "release")
                    timeline.remove(release)
                    before_clear = next(index for index, row in enumerate(timeline)
                                        if row["kind"] == "guest_observation_begin" and row["value"]["phase"] == "cleared_hold")
                    timeline.insert(before_clear, release)
                elif mutation == "postexit_before_exit":
                    exited = next(row for row in timeline if row["kind"] == "exit")
                    timeline.remove(exited)
                    timeline.append(exited)
                else:
                    value["guest"]["observations"][0]["snapshot"]["paths"].pop("prepared")
                for seq, row in enumerate(timeline, 1):
                    row.update(seq=seq, elapsed_ns=seq)
                write_worker(root, value["worker"])
                (root / "guest.json").write_bytes(encoded(value["guest"]))
                before = {path.name: path.read_bytes() for path in root.iterdir()}
                with self.assertRaises(audit.AuditError):
                    audit.audit_guest(root)
                self.assertEqual({path.name: path.read_bytes() for path in root.iterdir()}, before)


def host_fixture(path, cell, *, start_ns=1):
    case, unit = cell["guest"]["case"], cell["guest"]["unit"]
    epoch = ("1" if case == "persistent-write-error" else "2") * 32
    rule = dict(event="write_aio", iotype="write", errno=28, once=False) if case == "persistent-write-error" else None
    binding = dict(unit=unit, case=case, root=cell["fixture"]["root"], raw_node="raw219",
                   file_node="file219", filter_node="filter219-" + case,
                   disk_path="/authored/secondary.raw", device_id="disk219", device_serial="SER219", volume_serial="4D")
    expected = dict(controller_epoch=epoch, code_sha256="1" * 64, python=dict(version="authored-only"))
    plan = dict(resident_expected=dict(controller={case: expected}),
                cases=[dict(case=case, unit=unit, root=binding["root"])],
                identities=dict(disk={key: binding[key] for key in ("raw_node", "file_node", "filter_node", "disk_path", "device_id", "device_serial")},
                                volume=dict(volume_serial="4D")))
    rows, state_epoch = [], 0
    def row(kind, value):
        rows.append(dict(kind=kind, controller_epoch=epoch, state_epoch=state_epoch,
                         monotonic_ns=start_ns + len(rows), value=deepcopy(value)))
    def resident(state):
        value = dict(**expected, binding=binding, rule=rule, state_epoch=state_epoch, state=state, plan_sha256="a" * 64,
                     record_failure_count=0, record_failures=[], clear_outcome=None)
        if state == "cleared":
            value["clear_outcome"] = dict(attempted=True, arguments={"options": [{"driver": "raw", "node-name": binding["raw_node"], "file": binding["file_node"]}]},
                response_received=True, response=None, error=None, graph_verified=True, recording_complete=True, observation_errors=[])
        return value
    def qmp(command, arguments, response=None):
        row("qmp", dict(command=command, arguments=arguments, response=response,
                        success=True, error=None))
    def graph(selected, exists=True):
        nodes = [dict(**{"node-name": binding["file_node"]}, drv="file", image=dict(filename=binding["disk_path"]), children=[]),
                 dict(**{"node-name": binding["raw_node"]}, drv="raw", children=[{"node-name": selected, "child": "file"}])]
        if exists:
            nodes.append(dict(**{"node-name": binding["filter_node"]}, drv="blkdebug",
                              children=[{"node-name": binding["file_node"], "child": "image"}],
                              image=dict(filename="json:" + json.dumps({"driver": "blkdebug", "inject-error": [rule] if rule else []}))))
        qmp("query-named-block-nodes", None, nodes)
        qmp("query-block", None, [dict(qdev="disk219", inserted={"node-name": binding["raw_node"]})])
        qmp("qom-get", {"path": "/machine/peripheral/disk219", "property": "serial"}, "SER219")
        qmp("query-blockstats", None, [])
    row("resident", resident("fresh"))
    graph(binding["file_node"], False)
    qmp("blockdev-add", {"driver": "blkdebug", "node-name": binding["filter_node"],
                         "image": binding["file_node"], "inject-error": [rule] if rule else []})
    graph(binding["file_node"])
    state_epoch = 1
    row("prepared", resident("prepared"))
    for event in cell["events"]:
        row("guest-event", event)
        if event["stage"] == "before_candidate_hold":
            graph(binding["file_node"])
            state_epoch = 2
            qmp("blockdev-reopen", {"options": [{"driver": "raw", "node-name": binding["raw_node"], "file": binding["filter_node"]}]})
            graph(binding["filter_node"])
            row("armed", resident("armed"))
        if event["stage"] == "candidate_hold":
            row("before-clear", resident("armed"))
            graph(binding["filter_node"])
            state_epoch = 3
            qmp("blockdev-reopen", {"options": [{"driver": "raw", "node-name": binding["raw_node"], "file": binding["file_node"]}]})
            graph(binding["file_node"])
            row("cleared", resident("cleared"))
        commands = dict(prepared="start", source_reopened_hold="continue", before_candidate_hold="armed", candidate_hold="cleared", cleared_hold="release")
        if event["stage"] in commands:
            command = {key: event[key] for key in ("v", "unit", "case", "seq", "stage")}
            command["command"] = commands[event["stage"]]
            row("command-prepared", dict(command=command))
            row("command-sent", dict(command=command))
    path.write_bytes(b"".join(map(encoded, rows)))
    return rows, plan


class HostRetainedControls(unittest.TestCase):
    def test_acknowledgement_requires_actual_completed_arm_and_clear(self):
        for stage in ("before_candidate_hold", "candidate_hold"):
            with self.subTest(stage=stage), temporary_directory() as directory:
                root = Path(directory)
                guest_fixture(root)
                cell = audit.audit_guest(root)
                host = root / "host.jsonl"
                rows, plan = host_fixture(host, cell)
                audit.audit_host(host, cell, plan, "a" * 64)
                acknowledgements = [row for row in rows if row["kind"] in ("command-prepared", "command-sent")
                                    and row["value"]["command"]["stage"] == stage]
                for row in acknowledgements:
                    rows.remove(row)
                index = next(index for index, row in enumerate(rows) if row["kind"] == "guest-event" and row["value"]["stage"] == stage)
                epoch = rows[index]["state_epoch"]
                for row in acknowledgements:
                    row["state_epoch"] = epoch
                rows[index + 1:index + 1] = acknowledgements
                for index, row in enumerate(rows, 1):
                    row["monotonic_ns"] = index
                host.write_bytes(b"".join(map(encoded, rows)))
                with self.assertRaisesRegex(audit.AuditError, "acknowledgement precedes"):
                    audit.audit_host(host, cell, plan, "a" * 64)

    def test_two_authored_host_baselines_bind_resident_epoch_and_loaded_graph(self):
        for success, case in ((False, "persistent-write-error"), (True, "no-error")):
            with self.subTest(case=case), temporary_directory() as directory:
                root = Path(directory)
                guest_fixture(root, success=success, case=case)
                cell = audit.audit_guest(root)
                host = root / "host.jsonl"
                _, plan = host_fixture(host, cell)
                result = audit.audit_host(host, cell, plan, "a" * 64)
                self.assertEqual(result["binding"]["volume_serial"], "4D")

    def test_rule_epoch_disk_runtime_and_controller_error_mutations_refuse(self):
        mutations = {
            "controller_epoch": lambda rows: rows[-1].update(controller_epoch="stale"),
            "state_epoch": lambda rows: rows[-1].update(state_epoch=0),
            "disk_identity": lambda rows: rows[0]["value"]["binding"].update(device_serial="foreign"),
            "loaded_code": lambda rows: rows[0]["value"].update(code_sha256="f" * 64),
            "runtime": lambda rows: rows[0]["value"].update(python=dict(version="changed")),
            "rule_once": lambda rows: rows[0]["value"]["rule"].update(once=True),
            "controller_error": lambda rows: next(row for row in rows if row["kind"] == "qmp")["value"].update(success=False, error=dict(desc="authored QMP failure")),
            "graph_loaded_rule": lambda rows: next(row for row in rows if row["kind"] == "qmp" and row["value"]["command"] == "query-named-block-nodes" and len(row["value"]["response"]) == 3)["value"]["response"][2]["image"].update(filename='json:{"driver":"blkdebug","inject-error":[]}'),
            "recording_loss": lambda rows: rows[0]["value"].update(record_failure_count=1, record_failures=["authored loss"]),
            "clear_unverified": lambda rows: next(row for row in rows if row["kind"] == "cleared")["value"]["clear_outcome"].update(graph_verified=False),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name), temporary_directory() as directory:
                root = Path(directory)
                guest_fixture(root)
                cell = audit.audit_guest(root)
                host = root / "host.jsonl"
                rows, plan = host_fixture(host, cell)
                audit.audit_host(host, cell, plan, "a" * 64)
                mutate(rows)
                host.write_bytes(b"".join(map(encoded, rows)))
                before = host.read_bytes()
                with self.assertRaises(audit.AuditError):
                    audit.audit_host(host, cell, plan, "a" * 64)
                self.assertEqual(host.read_bytes(), before)


def update_outer_copies(root, change):
    notes = [json.loads(line) for line in (root / "guest-transcript.jsonl").read_bytes().splitlines()]
    for row in notes:
        if row["kind"] == "event":
            event = json.loads(bytes.fromhex(row["value"]["bytes_hex"])[len(b"IMAGEINFO219 "):])
            change(event)
            row["value"]["bytes_hex"] = (b"IMAGEINFO219 " + encoded(event)).hex()
    (root / "guest-transcript.jsonl").write_bytes(b"".join(map(encoded, notes)))
    events = iter(row["value"] for row in notes if row["kind"] == "event")
    transcript = [json.loads(line) for line in (root / "transcript.jsonl").read_bytes().splitlines()]
    for row in transcript:
        if row["kind"] == "guest_event":
            row["value"] = next(events)
    (root / "transcript.jsonl").write_bytes(b"".join(map(encoded, transcript)))
    if (root / "host.jsonl").exists():
        rows = [json.loads(line) for line in (root / "host.jsonl").read_bytes().splitlines()]
        for row in rows:
            if row["kind"] == "guest-event":
                change(row["value"])
        (root / "host.jsonl").write_bytes(b"".join(map(encoded, rows)))


HTTP_NAMES = ("source.bin", "old-source.bin", "candidate.bin", "output.bin", "prepared.record", "intent.record",
              "observation.record", "receipt.record", "stdout.bin", "stderr.bin", "events.jsonl", "transcript.jsonl",
              "result.json", "guest-transcript.jsonl", "guest.json", "volume-binding.json")
HTTP_REQUIRED = sorted(("stdout.bin", "stderr.bin", "events.jsonl", "transcript.jsonl", "result.json",
                        "guest-transcript.jsonl", "guest.json", "volume-binding.json"))


def http_plan(plan):
    plan.update(parent_transport="bounded-http-current-parent-v1", http_assets={},
                http_export=dict(artifacts={name: 16777216 for name in HTTP_NAMES}, required_files=HTTP_REQUIRED,
                                 require_export=True, export_timeout=30))


def http_fixture(root, cell, rows, plan):
    """Independently author raw HTTP bodies, actual exported bytes and manifest."""
    result = []
    def extra(kind, value, template=None):
        source = template or rows[-1]
        return dict(kind=kind, value=deepcopy(value), controller_epoch=source["controller_epoch"],
                    state_epoch=source["state_epoch"], monotonic_ns=0)
    result.append(deepcopy(rows[0]))
    result.append(extra("http-assets", dict(port=21919, assets=plan["http_assets"], **plan["http_export"]), rows[0]))
    pending = None
    for row in rows[1:]:
        if row["kind"] == "guest-event":
            event = row["value"]
            result.append(extra("http-request", dict(method="POST", path="/event/" + event["unit"],
                                body_hex=(b"IMAGEINFO219 " + encoded(event)).hex()), row))
            result.append(deepcopy(row))
            if event["stage"] in dict(prepared="start", source_reopened_hold="continue", before_candidate_hold="armed", candidate_hold="cleared", cleared_hold="release"):
                pending = event
            else:
                result.append(extra("http-response", dict(status=200, body_hex=b"{}\n".hex()), row))
        elif row["kind"] == "command-sent":
            result.append(extra("http-response", dict(status=200, body_hex=encoded(row["value"]["command"]).hex()), row))
            result.append(deepcopy(row))
            pending = None
        else:
            result.append(deepcopy(row))
    if pending is not None:
        raise AssertionError("authored HTTP pending command")
    files, missing = [], []
    capture_root = cell["guest"]["request"]["attempt_dir"]
    paths = {"source.bin": cell["fixture"]["source"], "old-source.bin": cell["fixture"]["old"]}
    paths.update({name: cell["fixture"][key] for key, name in
                  (("candidate", "candidate.bin"), ("output", "output.bin"), ("prepared", "prepared.record"),
                   ("intent", "intent.record"), ("observation", "observation.record"), ("receipt", "receipt.record"))})
    paths.update({name: capture_root + "\\" + name for name in HTTP_REQUIRED})
    paths["volume-binding.json"] = cell["guest"]["request"]["volume_binding_path"]
    artifact_keys = dict(source="source.bin", candidate="candidate.bin", output="output.bin", prepared="prepared.record",
                         intent="intent.record", observation="observation.record", receipt="receipt.record")
    for key, name in artifact_keys.items():
        if cell["final"]["paths"][key]["status"] == "ok":
            (root / name).write_bytes(b"S" * 16777216 if key == "source" else b"\x18" * 4194304 if key == "output" else b"r")
    for name in sorted(HTTP_NAMES):
        path = root / name
        if path.is_file():
            raw = path.read_bytes()
            row = dict(name=name, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
            result.append(extra("http-artifact", row))
            files.append(dict(**row, guest_path=paths[name]))
        else:
            missing.append(dict(name=name, guest_path=paths[name], status="absent", error=None))
    result.append(extra("http-export", dict(schema="imageinfo-0219-http-export-v1", exit_confirmed=True,
                                           files=files, missing=missing)))
    start = rows[0]["monotonic_ns"]
    for index, row in enumerate(result):
        row["monotonic_ns"] = start + index
    (root / "host.jsonl").write_bytes(b"".join(map(encoded, result)))
    return result


def pair_fixture(root, *, http=False):
    """Two retained synthetic cells plus tiny committed authored input pins."""
    cells, host_values = [], []
    for success, case, unit, start in ((False, "persistent-write-error", "error219", 1),
                                       (True, "no-error", "control219", 1000)):
        folder = root / case
        folder.mkdir()
        guest_fixture(folder, success=success, case=case, unit=unit)
        cell = audit.audit_guest(folder)
        rows, plan = host_fixture(folder / "host.jsonl", cell, start_ns=start)
        cells.append((folder, cell))
        host_values.append((rows, plan))
        entries = []
        for name, snapshot in sorted(cell["final"]["paths"].items()):
            if name in ("old", "preparedSource") or snapshot["status"] != "ok":
                continue
            content = (b"S" * 16777216 if name == "source" else
                       b"\x18" * 4194304 if name == "output" else b"r")
            selected = folder / ("retained-" + name + ".bin")
            selected.write_bytes(content)
            entries.append(dict(guest_path=snapshot["path"], path=selected.name,
                                bytes=len(content), sha256=hashlib.sha256(content).hexdigest()))
        entries.sort(key=lambda row: row["guest_path"])
        (folder / "artifacts.json").write_bytes(encoded(dict(schema="imageinfo-0219-artifacts-v1", entries=entries)))
    checkout = root / "checkout"
    checkout.mkdir()
    sources = {"Cargo.toml": b"# authored\n", "Cargo.lock": b"# authored\n", ".gitattributes": b"* text eol=lf\n"}
    for name in ("src/storage/namespace_diagnostic.rs", "src/storage/namespace_guest_diagnostic.rs", "src/storage/runtime.rs", "src/storage/windows.rs",
                 "crates/imageinfo-windows-storage/src/native.rs", "crates/imageinfo-windows-storage/src/windows.rs"):
        sources[name] = b"// authored\n"
    for name in ("audit", "freeze", "fixtures", "protocol", "guest_collector", "host_controller"):
        sources["experiments/0219-namespace-guest-contrast/" + name + ".py"] = b"# authored\n"
    sources["experiments/0219-namespace-guest-contrast/guest_bootstrap.ps1"] = b"# authored\n"
    for name, content in sources.items():
        selected = checkout / name
        selected.parent.mkdir(parents=True, exist_ok=True)
        selected.write_bytes(content)
    def git(*arguments):
        result = subprocess.run(["git", "-c", "core.autocrlf=false", "-c", "commit.gpgsign=false",
                                 "-c", "core.hooksPath=" + str(root / "no-hooks"), "-c", "user.name=Authored",
                                 "-c", "user.email=authored@example.invalid", *arguments], cwd=checkout,
                                capture_output=True, timeout=15, check=True)
        return result.stdout.decode("ascii").strip()
    git("init", "--quiet")
    git("add", "--", ".")
    git("commit", "--quiet", "--no-verify", "-m", "Authored control")
    commit = git("rev-parse", "HEAD")
    worker_path = root / "worker-placeholder.bin"
    worker_path.write_bytes(b"authored placeholder never executable")
    def binding(path, name=None):
        raw = path.read_bytes()
        return dict(path=str(path.absolute()) if name is None else name, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    worker = binding(worker_path)
    guest_worker_path = "C:\\authored\\worker.exe"
    runtime = dict(implementation="cpython", version="3.14.7 (authored-only)", platform="win32",
                   stat_profile="cpython-3.14.7-windows-path-creation-handle-change-v1", code_sha256="3" * 64,
                   files={guest_worker_path: worker["sha256"], "C:\\authored\\collector.py": "4" * 64, "C:\\authored\\probe.py": "5" * 64})
    plan = deepcopy(host_values[0][1])
    plan.update(schema="namespace-guest-contrast-plan-v1", marker=dict(source_bytes=16777216, source_fill=83, candidate_bytes=4194304, candidate_fill=24),
                fault=dict(event="write_aio", iotype="write", errno=28, once=False, sector=None, arm_stage="create-Candidate", arm_seq=9),
                bounds=cells[0][1]["worker"]["transport"]["bounds"], **dict.fromkeys(audit.FLAGS, False))
    plan["cases"] += host_values[1][1]["cases"]
    for selection, (_, host_plan) in zip(plan["cases"], host_values):
        selection["identities"] = deepcopy(host_plan["identities"])
        selection["identities"]["guest"] = dict(machine="authored-only")
    plan["resident_expected"]["controller"].update(host_values[1][1]["resident_expected"]["controller"])
    plan["resident_expected"]["guest"] = runtime
    if http:
        http_plan(plan)
    argv = [guest_worker_path, "--exact", audit.WORKER_TEST, "--ignored", "--nocapture", "--test-threads=1"]
    plan.update(worker_test_name=audit.WORKER_TEST, argv=argv)
    plan["identities"]["guest"] = dict(machine="authored-only")
    input_paths = {key: root / (key + ".json") for key in ("build_record", "runtime_inventory", "disk_configuration", "controller_source")}
    input_paths["build_record"].write_bytes(encoded(dict(source_commit=commit, worker_sha256=worker["sha256"], argv=["authored-build"], target="authored-target", compiler="authored-compiler")))
    input_paths["runtime_inventory"].write_bytes(encoded(dict(guest=runtime,
        controller_python={case: expected["python"] for case, expected in plan["resident_expected"]["controller"].items()})))
    input_paths["disk_configuration"].write_bytes(encoded(dict(identities=plan["identities"],
        cases={selection["case"]: selection["identities"] for selection in plan["cases"]})))
    input_paths["controller_source"].write_bytes(b"# authored\n")
    plan["freeze_inputs"] = {key: str(path.absolute()) for key, path in input_paths.items()}
    plan_path, freeze_path, review_path = [root / name for name in ("plan.json", "freeze.json", "review.json")]
    plan_path.write_bytes(encoded(plan))
    frozen = dict(schema="namespace-guest-contrast-freeze-v1", root=str(checkout.absolute()), git_commit=commit,
                  source_encoding="git-lf-v1", worker=worker, plan=binding(plan_path),
                  inputs={key: binding(path) for key, path in input_paths.items()},
                  sources=[binding(checkout / name, name) for name in sorted(sources)])
    freeze_path.write_bytes(encoded(frozen))
    plan_sha, freeze_sha = binding(plan_path)["sha256"], binding(freeze_path)["sha256"]
    review_path.write_bytes(encoded(dict(schema="namespace-guest-contrast-review-v1", decision="approved",
                          scope="two-serial-cells-only", reviewer="authored independent control",
                          plan_sha256=plan_sha, freeze_sha256=freeze_sha)))
    for (folder, cell), (rows, _) in zip(cells, host_values):
        guest = cell["guest"]
        guest["bindings"] = dict(plan_sha256=plan_sha, freeze_sha256=freeze_sha, worker_sha256=worker["sha256"])
        guest["observer_python"] = {key: value for key, value in runtime.items() if key != "files"}
        guest["resident_guest"] = deepcopy(runtime)
        guest["request"] = dict(unit=guest["unit"], case=guest["case"], fixture_root=cell["fixture"]["root"],
                                bounds=plan["bounds"], argv=argv, worker_test_name=audit.WORKER_TEST, bindings=guest["bindings"],
                                observer_python=guest["observer_python"], reviewed_files=runtime["files"])
        guest["request"]["volume_binding_path"] = str(folder / "volume-binding.json")
        guest["request"]["attempt_dir"] = "C:\\captures\\" + guest["unit"]
        if http:
            guest["request"]["require_export"] = True
            guest["parent_transport"] = dict(operations=[dict(stage=stage, completed=True, timed_out=False, aborted=False)
                for stage in audit.STAGES], retained_threads=0, poisoned=False, replayed=False)
        (folder / "guest.json").write_bytes(encoded(guest))
        transport = json.loads((folder / "result.json").read_bytes())
        transport["command"] = argv
        guest["transport"] = transport
        (folder / "result.json").write_bytes(encoded(transport))
        transcript = [json.loads(line) for line in (folder / "transcript.jsonl").read_bytes().splitlines()]
        transcript[0]["value"]["command"] = argv
        (folder / "transcript.jsonl").write_bytes(b"".join(map(encoded, transcript)))
        (folder / "guest.json").write_bytes(encoded(guest))
        for row in rows:
            if row["kind"] in ("resident", "prepared", "armed", "before-clear", "cleared"):
                row["value"]["plan_sha256"] = plan_sha
                row["value"].update(source_sha256=binding(input_paths["controller_source"])["sha256"],
                                     source_bytes=binding(input_paths["controller_source"])["bytes"], pid=219)
        (folder / "host.jsonl").write_bytes(b"".join(map(encoded, rows)))
        volume = json.loads((folder / "volume-binding.json").read_bytes())
        volume.update(plan_sha256=plan_sha, drive_root=cell["fixture"]["sourceVolumeRoot"])
        (folder / "volume-binding.json").write_bytes(encoded(volume))
        def prepared_delta(event):
            if event["stage"] == "prepared":
                event["observation"].update(resident_guest=deepcopy(runtime), volume_binding=volume,
                    volume_binding_file_sha256=hashlib.sha256(encoded(volume)).hexdigest())
        update_outer_copies(folder, prepared_delta)
        if http:
            cell = audit.audit_guest(folder)
            current_rows = [json.loads(line) for line in (folder / "host.jsonl").read_bytes().splitlines()]
            http_fixture(folder, cell, current_rows, plan)
    (root / "attempts.jsonl").write_bytes(b"".join(encoded(dict(seq=index, case=cell["guest"]["case"], unit=cell["guest"]["unit"], attempt_dir=folder.name))
                                                for index, (folder, cell) in enumerate(cells, 1)))
    return cells[0][0], cells[1][0], plan_path, freeze_path, review_path


class PairControls(unittest.TestCase):
    def test_actual_resident_and_exact_planned_worker_invocation_are_required(self):
        with temporary_directory() as directory:
            root = Path(directory)
            arguments = pair_fixture(root)
            audit.audit_pair(*arguments)
            folder = arguments[0]
            originals = {path: path.read_bytes() for path in folder.iterdir() if path.is_file()}
            for mutation in ("resident_missing", "resident_actual_changed", "wrong_worker_target", "wrong_test_name", "missing_worker_arg"):
                with self.subTest(mutation=mutation):
                    guest = json.loads((folder / "guest.json").read_bytes())
                    if mutation.startswith("resident"):
                        if mutation == "resident_missing":
                            guest.pop("resident_guest")
                        else:
                            guest["resident_guest"]["code_sha256"] = "f" * 64
                            def wrong_actual(event):
                                if event["stage"] == "prepared":
                                    event["observation"]["resident_guest"]["code_sha256"] = "f" * 64
                            update_outer_copies(folder, wrong_actual)
                    else:
                        argv = guest["request"]["argv"]
                        if mutation == "wrong_worker_target":
                            argv[0] = "C:\\authored\\foreign-worker.exe"
                        elif mutation == "wrong_test_name":
                            argv[2] = "storage::namespace_diagnostic::local_namespace_diagnostic_worker"
                        else:
                            argv.pop()
                        guest["transport"]["command"] = argv
                        result = json.loads((folder / "result.json").read_bytes())
                        result["command"] = argv
                        (folder / "result.json").write_bytes(encoded(result))
                        rows = [json.loads(line) for line in (folder / "transcript.jsonl").read_bytes().splitlines()]
                        rows[0]["value"]["command"] = argv
                        (folder / "transcript.jsonl").write_bytes(b"".join(map(encoded, rows)))
                    (folder / "guest.json").write_bytes(encoded(guest))
                    try:
                        with self.assertRaises(audit.AuditError):
                            audit.audit_pair(*arguments)
                    finally:
                        for path, raw in originals.items():
                            path.write_bytes(raw)

    def test_full_authored_pair_retains_no_positive_admission(self):
        with temporary_directory() as directory:
            arguments = pair_fixture(Path(directory))
            frozen = json.loads(arguments[3].read_bytes())
            plan = json.loads(arguments[2].read_bytes())
            guest_worker_path = plan["argv"][0]
            self.assertEqual(guest_worker_path, "C:\\authored\\worker.exe")
            self.assertTrue(PureWindowsPath(guest_worker_path).is_absolute())
            self.assertNotEqual(frozen["worker"]["path"], guest_worker_path)
            self.assertEqual(Path(frozen["worker"]["path"]).read_bytes(), b"authored placeholder never executable")
            self.assertEqual(plan["resident_expected"]["guest"]["files"][guest_worker_path], frozen["worker"]["sha256"])
            for attempt in arguments[:2]:
                guest = json.loads((attempt / "guest.json").read_bytes())
                self.assertEqual(guest["request"]["argv"], plan["argv"])
                self.assertEqual(guest["transport"]["command"], plan["argv"])
            result = audit.audit_pair(*arguments)
            self.assertEqual(result["attempts"], 2)
            self.assertTrue(all(result[key] is False for key in audit.FLAGS))

    def test_changed_source_artifact_review_and_forgotten_attempt_denominator_refuse(self):
        with temporary_directory() as directory:
            root = Path(directory)
            arguments = pair_fixture(root)
            audit.audit_pair(*arguments)
            selected = (
                (root / "checkout/src/storage/runtime.rs", b"// changed authored source\n"),
                (root / "persistent-write-error/retained-source.bin", b"changed source bytes"),
                (root / "review.json", b"{}\n"),
                (root / "freeze.json", b"{}\n"),
                (root / "attempts.jsonl", b""),
                (root / "attempts.jsonl", (root / "attempts.jsonl").read_bytes() + encoded(dict(seq=3, case="no-error", unit="failed219", attempt_dir="failed-attempt"))),
            )
            for path, changed in selected:
                with self.subTest(path=path.name, changed=changed[:32]):
                    original = path.read_bytes()
                    path.write_bytes(changed)
                    try:
                        with self.assertRaises(audit.AuditError):
                            audit.audit_pair(*arguments)
                        self.assertEqual(path.read_bytes(), changed)
                    finally:
                        path.write_bytes(original)
            failed = root / "failed-attempt"
            failed.mkdir()
            (failed / "result.json").write_bytes(encoded(dict(status="failed", reason="authored only")))
            with self.assertRaises(audit.AuditError):
                audit.audit_pair(*arguments)
            self.assertTrue((failed / "result.json").is_file())


class HttpRetainedControls(unittest.TestCase):
    def test_full_http_pair_baseline_and_raw_export_mutations(self):
        with temporary_directory() as directory:
            root = Path(directory)
            arguments = pair_fixture(root, http=True)
            self.assertEqual(audit.audit_pair(*arguments)["attempts"], 2)
            host = arguments[0] / "host.jsonl"
            original = host.read_bytes()
            def acknowledgement(rows):
                row = next(row for row in rows if row["kind"] == "http-response")
                command = json.loads(bytes.fromhex(row["value"]["body_hex"]))
                command["command"] = "cancel"
                row["value"]["body_hex"] = encoded(command).hex()
            def required_capture(rows):
                uploaded = next(row for row in rows if row["kind"] == "http-artifact" and row["value"]["name"] == "stderr.bin")
                rows.remove(uploaded)
                manifest = next(row for row in rows if row["kind"] == "http-export")["value"]
                entry = next(row for row in manifest["files"] if row["name"] == "stderr.bin")
                manifest["files"].remove(entry)
                manifest["missing"].append(dict(name="stderr.bin", guest_path=entry["guest_path"], status="absent", error=None))
            def lifetime(rows):
                completed = next(row for row in rows if row["kind"] == "http-export")
                rows.remove(completed)
                position = next(index for index, row in enumerate(rows) if row["kind"] == "guest-event" and row["value"]["stage"] == "final")
                rows.insert(position, completed)
                for index, row in enumerate(rows):
                    row["monotonic_ns"] = index + 1
            mutations = {
                "raw_body": lambda rows: next(row for row in rows if row["kind"] == "http-request")["value"].update(body_hex=b"changed".hex()),
                "acknowledgement": acknowledgement,
                "required_capture": required_capture,
                "upload_hash": lambda rows: next(row for row in rows if row["kind"] == "http-artifact")["value"].update(sha256="0" * 64),
                "export_lifetime": lifetime,
                "manifest_path": lambda rows: next(row for row in rows if row["kind"] == "http-export")["value"]["files"][0].update(guest_path="C:\\foreign"),
                "export_exit": lambda rows: next(row for row in rows if row["kind"] == "http-export")["value"].update(exit_confirmed=False),
                "duplicate_manifest": lambda rows: next(row for row in rows if row["kind"] == "http-export")["value"]["files"].append(deepcopy(next(row for row in rows if row["kind"] == "http-export")["value"]["files"][0])),
            }
            for name, mutate in mutations.items():
                rows = [json.loads(line) for line in original.splitlines()]
                mutate(rows)
                host.write_bytes(b"".join(map(encoded, rows)))
                try:
                    with self.subTest(name=name), self.assertRaises(audit.AuditError):
                        audit.audit_pair(*arguments)
                finally:
                    host.write_bytes(original)
            selected = arguments[0] / "source.bin"
            raw = selected.read_bytes()
            selected.write_bytes(b"changed copied artifact")
            try:
                with self.assertRaisesRegex(audit.AuditError, "upload bytes changed"):
                    audit.audit_pair(*arguments)
            finally:
                selected.write_bytes(raw)

    def test_parent_transport_requires_completed_bounded_operations(self):
        value = dict(operations=[dict(stage=stage, completed=True, timed_out=False, aborted=False) for stage in audit.STAGES],
                     retained_threads=0, poisoned=False, replayed=False)
        audit._parent_transport(value)
        changes = {
            "retained_threads": lambda v: v.update(retained_threads=1),
            "poisoned": lambda v: v.update(poisoned=True),
            "replayed": lambda v: v.update(replayed=True),
            "incomplete": lambda v: v["operations"][0].update(completed=False),
            "timed_out": lambda v: v["operations"][0].update(timed_out=True),
            "aborted": lambda v: v["operations"][0].update(aborted=True),
            "stage_order": lambda v: v["operations"].reverse(),
        }
        for name, mutate in changes.items():
            changed = deepcopy(value)
            mutate(changed)
            with self.subTest(name=name), self.assertRaises(audit.AuditError):
                audit._parent_transport(changed)


if __name__ == "__main__":
    unittest.main()
