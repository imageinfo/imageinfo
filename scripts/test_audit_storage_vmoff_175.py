"""Authored oracles/mutations only; invented fixtures are never guest evidence."""
import base64
import copy
import json
from pathlib import Path
import struct
import tempfile
import unittest

import audit_storage_vmoff_175 as audit

IMPLEMENTATION = "imageinfo-storage-live-ack-v1-0.2.0-alpha.1"
# Fixed oracle literals are transcribed from the approved wire/cell contracts,
# never generated from the parser's field order, phase table or matrix.
ORACLE_RECORDS = ("prepared.record", "intent.record", "observation.record", "receipt.record")
ORACLE_PHASES = ("RootFlushed", "ParentFlushed", "CandidateChecked", "CandidateFlushed", "CandidateParentFlushed",
                 "PreparedCreated", "PreparedChecked", "PreparedFlushed", "PreparedParentFlushed", "IntentCreated",
                 "IntentChecked", "IntentFlushed", "IntentParentFlushed", "CallerRelease", "Prepublication", "Publish",
                 "Installed", "InstalledFlushed", "InstalledParentFlushed", "InstalledRechecked", "ObservationCreated",
                 "ObservationChecked", "ObservationFlushed", "ObservationParentFlushed")
ORACLE_MATRIX = (
    ("normal", "run", "none", "none"),
    ("kill-candidate-ready", "run", "process-kill", "candidate-ready"),
    ("kill-intent-ready", "run", "process-kill", "intent-ready"),
    ("kill-possible-publication", "run", "process-kill", "possible-publication"),
    ("kill-installed-ack", "run", "process-kill", "installed-ack"),
    ("kill-receipt-before-ack", "run", "process-kill", "receipt-before-ack"),
    ("kill-final-success-response", "run", "process-kill", "final-success-response"),
    ("vmoff-possible-publication", "run", "vm-off", "possible-publication"),
    ("vmoff-receipt-before-ack", "run", "vm-off", "receipt-before-ack"),
    ("vmoff-completed-predicate", "run", "vm-off", "completed-predicate"),
    ("kill-restart-finalize", "finalize", "process-kill", "finalize-receipt-created"),
    ("kill-partial-cleanup", "cleanup", "process-kill", "cleanup-one-removed"),
)


def wire(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode() + b"\n"


def row(name, number, data=None, directory=False):
    value = dict(path=name, volume=7, file_index=number, size=len(data or b""), links=1,
                 attributes=16 if directory else 32, creation_time=100, last_write_time=200,
                 owner_dacl="O:SYD:(A;;FA;;;SY)", directory=directory,
                 streams=[] if directory else ["::$DATA"])
    if data is not None:
        value.update(content_base64=base64.b64encode(data).decode(), sha256=audit.digest(data))
    return value


def binding(value, parent=None):
    def native(item):
        security = item["owner_dacl"].encode("utf-8")
        return b"imageinfo-held-object-v1\0" + struct.pack("<8Q", item["volume"], item["file_index"], item["size"],
                    item["links"], item["attributes"], item["creation_time"], item["last_write_time"], len(security)) + security
    facts = native(value)
    if not value["directory"]:
        facts += bytes.fromhex(value["sha256"])
    if parent:
        facts += b"held-containing-parent-v1\0" + native(parent)
    return struct.pack("<2Q", value["volume"], value["file_index"]), facts


def record(name, bindings):
    def field(data):
        return struct.pack("<I", len(data)) + data
    headers = ("windows-new-output-contract-v1", "windows-ntfs-unqualified-internal-v1",
               IMPLEMENTATION, "0175-authored-single-output-v1", "0175-marker-only-v1", "output.bin", name)
    out = b"".join(field(text.encode()) for text in headers)
    out += field(struct.pack("<Q", len(audit.CANDIDATE)))
    for identity, facts in bindings:
        out += field(identity) + field(facts)
    count = (5, 9, 20, 24)[ORACLE_RECORDS.index(name)]
    return out + b"".join(field(text.encode()) for text in ORACLE_PHASES[:count])


def authored_fixture(root):
    """Independently construct valid finite wire bytes from authored constants."""
    def save(name, value, raw=False):
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        data = value if raw else wire(value)
        target.write_bytes(data)
        return {"path": name, "sha256": audit.digest(data)}

    frozen = {name: save("frozen/" + name, b"authored-" + name.encode(), True)
              for name in ("executable", "actor_source", "reader", "controller", "source_manifest", "audit_storage_vmoff_175_py",
                           "test_audit_storage_vmoff_175_py", "test_read_storage_artifacts_175_py")}
    cache_bytes = struct.pack("<6I", 28, 28, 1, 1, 1, 1) + bytes((1, 0, 0, 0))
    cache = dict(version=28, size=28, type=1, enabled=1, changeable=1, writeThrough=1,
                 flushSupported=True, userPowerProtection=False, nonvolatileCacheEnabled=False,
                 querySucceeded=True, settingChanged=False, rawBase64=base64.b64encode(cache_bytes).decode())
    raw_guest = dict(version="10.0.26300", build="26300", servicingRevision=123, architecture="64-bit", filesystem="NTFS",
                     volumeSerial="00000007", driveType=3, clusterBytes=4096, volumeSizeBytes=1024**3,
                     volumeDeviceId="authored-volume", controllers=[{"Name": "authored-SATA"}], controllerDrivers=[{"DriverVersion": "1"}],
                     disks=[{"Model": "authored-disk"}], guestCachePolicy=cache, groups=["S-1-16-8192"],
                     workerSha256=frozen["executable"]["sha256"], readerSha256=frozen["reader"]["sha256"], scriptSha256="a" * 64)
    vm_root = "/var/tmp/imageinfo-windows-eval-20261014/production-0175-authored"
    args = ["/authored/qemu-system-x86_64", "-machine", "q35,accel=kvm,smm=on", "-drive",
            "if=pflash,format=raw,unit=0,readonly=on,file=/authored/usr/share/OVMF/OVMF_CODE_4M.ms.fd", "-drive",
            f"if=pflash,format=raw,unit=1,file={vm_root}/vars.fd", "-drive",
            f"file={vm_root}/windows.qcow2,if=ide,format=qcow2,cache=writeback", "-qmp", f"unix:{vm_root}/qmp,server=on,wait=off"]
    base = "/var/tmp/imageinfo-windows-eval-20261014/windows.qcow2"
    emulator = dict(argv=args, root=vm_root, emulator_sha256="b" * 64,
                    blocks=[{"inserted": {"file": vm_root + "/windows.qcow2", "image": {
                        "filename": vm_root + "/windows.qcow2", "format": "qcow2", "full-backing-filename": base,
                        "backing-image": {"filename": base, "format": "qcow2"}}}}])
    profile_value = dict(schema="imageinfo-0175-profile-v1", filesystem="NTFS", cache="writeback", host_caches_survive_vmoff=True,
                         host_caches_alive=True, physical_power_tested=False, actor_executable_sha256=frozen["executable"]["sha256"],
                         actor_source_sha256=frozen["actor_source"]["sha256"], controller_sha256=frozen["controller"]["sha256"],
                         auditor_sha256=frozen["audit_storage_vmoff_175_py"]["sha256"], actor_toolchain="authored-toolchain",
                         actor_build_command="authored build", native_baseline_evidence_sha256="c" * 64, freeze_review_evidence_sha256="d" * 64,
                         guest={"raw": raw_guest}, guest_os_version="10.0.26300", guest_os_build="26300", guest_os_servicing_revision=123,
                         emulator=emulator, hypervisor_executable_sha256="b" * 64, hypervisor_arguments=args, launch={"argv": args})
    sources = {}
    for relative in ("Cargo.toml", "Cargo.lock", "rust-toolchain.toml", "src/lib.rs", "src/storage/mod.rs",
                     "src/storage/runtime.rs", "src/storage/windows.rs", "src/storage/qualification.rs",
                     "src/storage/inspection.rs", "src/storage/finalization.rs", "src/storage/cleanup.rs",
                     "src/storage/custody.rs", "src/storage/resources.rs", "crates/imageinfo-windows-storage/src/lib.rs",
                     "crates/imageinfo-windows-storage/src/native.rs", "crates/imageinfo-windows-storage/src/windows.rs"):
        label = "source_" + relative.replace("/", "_")
        frozen[label] = frozen["actor_source"] if relative == "src/storage/qualification.rs" else save("frozen/" + label, relative.encode(), True)
        sources[relative] = frozen[label]["sha256"]
    spec = {key: profile_value[key] for key in ("actor_toolchain", "actor_build_command", "native_baseline_evidence_sha256", "freeze_review_evidence_sha256")}
    spec.update(sources=sources, workerSha256=frozen["executable"]["sha256"], implementation=IMPLEMENTATION)
    frozen["source_manifest"] = save("frozen/source_manifest", spec)
    profile = save("profile.json", profile_value)
    cells = []
    for index, (cell_id, mode, fault, checkpoint) in enumerate(ORACLE_MATRIX):
        parent = row("parent", 2, directory=True)
        directory = row("root", 3, directory=True)
        source = row("source.bin", 1, audit.SOURCE)
        candidate = row("unit/candidate.bin", 4, audit.CANDIDATE)
        bindings = [binding(source), binding(directory, parent), binding(candidate)]
        all_files = {"source.bin": source, "unit/candidate.bin": candidate}
        for n, name in enumerate(ORACLE_RECORDS, 5):
            current = row("unit/" + name, n, record(name, bindings))
            all_files["unit/" + name] = current
            bindings.append(binding(current))
        if checkpoint not in ("candidate-ready", "intent-ready", "possible-publication"):
            candidate["path"] = "unit/output.bin"
            all_files["unit/output.bin"] = all_files.pop("unit/candidate.bin")
        required = {"source.bin", "unit/candidate.bin"} if checkpoint == "candidate-ready" else {
            "source.bin", "unit/" + ("candidate.bin" if checkpoint in ("intent-ready", "possible-publication") else "output.bin"),
            "unit/prepared.record", "unit/intent.record"}
        if checkpoint not in ("candidate-ready", "intent-ready", "possible-publication", "installed-ack"):
            required |= {"unit/observation.record", "unit/receipt.record"}
        if checkpoint == "cleanup-one-removed":
            required.remove("unit/prepared.record")
        files = {key: value for key, value in all_files.items() if key in required}
        count = 3 if checkpoint == "candidate-ready" else 5 if checkpoint in (
            "intent-ready", "possible-publication", "publication-api-response", "installed-ack") else 7
        facts = {"bindings": [{"identity": a.hex(), "facts": b.hex()} for a, b in bindings[:count]],
                 "production_profile_admitted": False, "raw_admitted": False}
        if checkpoint in ("none", "final-success-response", "completed-predicate"):
            facts.update(protocol_complete=True, status="Refused", publication_possible=True)
        if checkpoint == "finalize-receipt-created":
            facts["fresh_receipt_binding_exported"] = True
        inventory = [{key: value[key] for key in ("path", "size", "sha256", "attributes", "creation_time", "last_write_time")}
                     for value in files.values()]
        event = {"schema": "imageinfo-0175-event-v1", "sequence": 1, "pid": 42,
                 "event": checkpoint if checkpoint != "none" else "completed-predicate",
                 "gate": fault != "none", "facts": facts, "inventory": inventory}
        inspect_event = dict(event, pid=43, event="read-only-inspection", gate=False,
                             facts={"collected": checkpoint != "cleanup-one-removed", "refusal": None,
                                    "authority": "MissingAuthority", "survivor": "RecoveryRequired", "mutation_attempted": False})
        boot_after = "guest-boot-2" if fault == "vm-off" else "guest-boot-1"
        snapshot = {"schema": "imageinfo-0175-independent-snapshot-v1", "files": list(files.values()),
                    "directories": {"root": directory, "parent": parent}, "errors": [],
                    "boot_utc": boot_after, "os_version": "10.0.26300", "os_build": "26300",
                    "read_only": True, "authority": "none"}
        request = {"cell_id": cell_id, "mode": mode, "fault": fault, "requested_checkpoint": checkpoint,
                   "executable_sha256": frozen["executable"]["sha256"], "reader_sha256": frozen["reader"]["sha256"]}
        hello = {"boot_utc": "guest-boot-1", "host_boot_utc": "host-boot-1", "os_version": "10.0.26300", "os_build": "26300",
                 "executable_sha256": frozen["executable"]["sha256"], "reader_sha256": frozen["reader"]["sha256"], "raw": raw_guest}
        docs = {"request": request, "run_result": {"actor_pid": 42, "exit_confirmed": True, "fault_confirmed": fault != "none",
                                                    "observed_checkpoint": checkpoint if fault != "none" else None, "reason": None},
                "events": wire(event), "snapshot_before": snapshot, "snapshot_after": snapshot,
                "inspect_events": wire(inspect_event), "inspect_result": {"exit_code": 0, "authority_imported": False, "mutation_requested": False},
                "before_hello": hello, "after_hello": dict(hello, boot_utc=boot_after)}
        if fault != "none":
            docs["gate"] = {"observed_checkpoint": checkpoint, "actor_pid": 42, "event_sequence": 1,
                            "event_sha256": audit.digest(wire(event)), "gate_armed": True}
        if fault == "vm-off":
            docs.update(off_completed={"vm_process_exit_confirmed": True, "requested_cell_id": cell_id, "host_boot_utc": "host-boot-1", "host_caches_alive": True},
                        off_target=dict(emulator, profile_sha256=profile["sha256"]),
                        restart_launch={"profile_sha256": profile["sha256"], "exit_code": 0, "live_binding": emulator})
        refs = {name: save(f"cells/{index}/{name}.json", data, isinstance(data, bytes)) for name, data in docs.items()}
        cells.append(dict(id=cell_id, mode=mode, fault=fault, requested_checkpoint=checkpoint, status="actual", references=refs))
    return {"schema": "imageinfo-0175-audit-manifest-v1", "implementation": IMPLEMENTATION,
            "possible_publication_checkpoint": "possible-publication", "frozen": frozen, "profile": profile, "cells": cells}


class AuditorTests(unittest.TestCase):
    def setUp(self):
        test_parent = Path(__file__).resolve().parents[1] / ".local" / "175-auditor-tests"
        test_parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=test_parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = authored_fixture(self.root)

    def change(self, cell_index, ref_name, transform, jsonl=False):
        ref = self.manifest["cells"][cell_index]["references"][ref_name]
        path = self.root / ref["path"]
        value = audit.decode(path.read_bytes())
        transform(value)
        raw = wire(value)
        path.write_bytes(raw)
        ref["sha256"] = audit.digest(raw)
        if ref_name == "events" and "gate" in self.manifest["cells"][cell_index]["references"]:
            gate_ref = self.manifest["cells"][cell_index]["references"]["gate"]
            gate_path = self.root / gate_ref["path"]
            gate = audit.decode(gate_path.read_bytes())
            gate["event_sha256"] = audit.digest(raw)
            gate_raw = wire(gate)
            gate_path.write_bytes(gate_raw)
            gate_ref["sha256"] = audit.digest(gate_raw)

    def report(self):
        return audit.audit(self.manifest, self.root)

    def test_authored_positive_and_no_authority(self):
        result = self.report()
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["campaign_complete"])
        self.assertFalse(result["production_profile_admitted"])
        self.assertFalse(result["raw_admitted"])
        self.assertEqual(len(result["cells"]), 12)

    def test_mutation_controls(self):
        mutations = (
            ("gate-label", 1, "gate", lambda v: v.update(observed_checkpoint="intent-ready")),
            ("gate-hash", 1, "gate", lambda v: v.update(event_sha256="0" * 64)),
            ("fault-confirmation", 1, "run_result", lambda v: v.update(fault_confirmed=False)),
            ("source-content", 1, "snapshot_before", lambda v: v["files"][0].update(content_base64="eA==")),
            ("native-identity", 1, "snapshot_before", lambda v: v["files"][0].update(file_index=999)),
            ("native-dacl", 1, "snapshot_before", lambda v: v["files"][0].update(owner_dacl="O:BAD:")),
            ("native-link", 1, "snapshot_before", lambda v: v["files"][0].update(links=2)),
            ("alternate-stream", 1, "snapshot_before", lambda v: v["files"][0].update(streams=["::$DATA", ":extra:$DATA"])),
            ("drift", 1, "snapshot_before", lambda v: v["files"][0].update(last_write_time=201)),
            ("observer-error", 1, "snapshot_before", lambda v: v["errors"].append({"error": "unavailable"})),
            ("missing-file", 1, "snapshot_before", lambda v: v["files"].pop()),
            ("inspection-mutation", 1, "inspect_result", lambda v: v.update(mutation_requested=True)),
            ("imported-authority", 1, "inspect_events", lambda v: v["facts"].update(authority="Imported")),
            ("false-commit", 0, "events", lambda v: v["facts"].update(status="Committed")),
            ("false-admission", 0, "events", lambda v: v["facts"].update(production_profile_admitted=True)),
            ("unchanged-guest-boot", 7, "after_hello", lambda v: v.update(boot_utc="guest-boot-1")),
            ("changed-host-boot", 7, "after_hello", lambda v: v.update(host_boot_utc="host-boot-2")),
            ("wrong-vm-profile", 7, "restart_launch", lambda v: v.update(profile_sha256="0" * 64)),
            ("unconfirmed-vm-exit", 7, "off_completed", lambda v: v.update(vm_process_exit_confirmed=False)),
            ("servicing-drift", 1, "after_hello", lambda v: v["raw"].update(servicingRevision=124)),
            ("cache-drift", 1, "after_hello", lambda v: v["raw"]["guestCachePolicy"].update(enabled=2)),
            ("controller-drift", 1, "after_hello", lambda v: v["raw"].update(controllers=[{"Name": "changed"}])),
            ("backing-drift", 7, "off_target", lambda v: v["blocks"][0]["inserted"]["image"]["backing-image"].update(filename="/changed")),
            ("finalize-receipt-not-exported", 10, "events", lambda v: v["facts"].update(fresh_receipt_binding_exported=False)),
        )
        original = copy.deepcopy(self.manifest)
        saved = {ref["path"]: (self.root / ref["path"]).read_bytes() for cell in original["cells"] for ref in cell["references"].values()}
        for name, index, ref_name, change in mutations:
            with self.subTest(name=name):
                self.manifest = copy.deepcopy(original)
                for path, raw in saved.items():
                    (self.root / path).write_bytes(raw)
                self.change(index, ref_name, change)
                self.assertFalse(self.report()["ok"], name)

    def test_record_independent_decoder_rejects_mutations(self):
        ref = self.manifest["cells"][0]["references"]["snapshot_before"]
        snapshot = audit.decode((self.root / ref["path"]).read_bytes())
        files = audit.read_snapshot(snapshot)
        raw = audit.file_bytes(files["unit/receipt.record"])
        self.assertEqual(len(audit.parse_record(raw, "receipt.record", IMPLEMENTATION)), 6)
        for changed in (raw + b"x", raw[:-1], b"\xff\xff\xff\xff" + raw[4:],
                        raw.replace(b"windows-new-output-contract-v1", b"windows-new-output-contract-v2"),
                        raw.replace(b"Receipt", b"x" * 7)):
            if changed == raw:
                continue
            with self.assertRaises(ValueError):
                audit.parse_record(changed, "receipt.record", IMPLEMENTATION)

    def test_same_byte_receipt_replacement_and_property_change_after_finalization(self):
        for key, changed in (("file_index", 999), ("owner_dacl", "O:BAD:"), ("last_write_time", 201)):
            with self.subTest(key=key):
                self.manifest = authored_fixture(self.root)
                def alter(value):
                    receipt = next(row for row in value["files"] if row["path"] == "unit/receipt.record")
                    receipt[key] = changed
                # Both independent post-loss observations agree; only comparison
                # with the original creator-held receipt catches substitution.
                self.change(10, "snapshot_before", alter)
                self.change(10, "snapshot_after", alter)
                result = self.report()
                self.assertFalse(result["ok"])
                self.assertIn("reopened", result["cells"][10]["discrepancies"][0])

    def test_binding_properties_survive_directory_diagnostic_changes(self):
        self.change(0, "snapshot_after", lambda value: value["directories"]["parent"].update(size=99, last_write_time=999, attributes=48))
        self.assertTrue(self.report()["ok"])
        self.change(0, "snapshot_after", lambda value: value["directories"]["root"].update(last_write_time=999))
        self.assertFalse(self.report()["ok"])

    def test_fixed_denominator_and_reference_integrity(self):
        self.manifest["cells"].pop()
        with self.assertRaises(ValueError):
            self.report()

    def test_native_profile_cache_and_source_freeze_disagreement_refuse(self):
        ref = self.manifest["profile"]
        path = self.root / ref["path"]
        value = audit.decode(path.read_bytes())
        value["guest"]["raw"]["guestCachePolicy"]["enabled"] = 2
        changed = wire(value)
        path.write_bytes(changed)
        ref["sha256"] = audit.digest(changed)
        with self.assertRaisesRegex(ValueError, "cache native descriptor"):
            self.report()
        self.manifest = authored_fixture(self.root)
        source_ref = self.manifest["frozen"]["source_manifest"]
        source_path = self.root / source_ref["path"]
        source = audit.decode(source_path.read_bytes())
        source["sources"]["src/storage/runtime.rs"] = "0" * 64
        changed = wire(source)
        source_path.write_bytes(changed)
        source_ref["sha256"] = audit.digest(changed)
        with self.assertRaisesRegex(ValueError, "frozen source manifest disagreement"):
            self.report()
        self.manifest = authored_fixture(self.root)
        self.manifest["frozen"]["reader"]["path"] = "../reader"
        with self.assertRaises(ValueError):
            self.report()

    def test_duplicate_json_and_boolean_not_integer(self):
        with self.assertRaises(ValueError):
            audit.decode('{"x":1,"x":2}')
        with self.assertRaises(ValueError):
            audit.integer(True, "boolean is not integer")


if __name__ == "__main__":
    unittest.main()
