"""Read-only #0175 retained-artifact reconciliation, independent of its collector.

No actor/controller imports, process invocation, mutation, cleanup, VM operation,
authority decoder or admission capability. Diagnostic reports stay private.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import struct

SOURCE = b"imageinfo-0175 protected authored source v1\n"
CANDIDATE = b"imageinfo-0175 authored output candidate v1\n"
PREFIX = b"imageinfo-held-object-v1\0"
PARENT = b"held-containing-parent-v1\0"
FIELDS = ("volume", "file_index", "size", "links", "attributes",
          "creation_time", "last_write_time")
RECORDS = ("prepared.record", "intent.record", "observation.record", "receipt.record")
PHASES = ("RootFlushed", "ParentFlushed", "CandidateChecked", "CandidateFlushed",
          "CandidateParentFlushed", "PreparedCreated", "PreparedChecked",
          "PreparedFlushed", "PreparedParentFlushed", "IntentCreated", "IntentChecked",
          "IntentFlushed", "IntentParentFlushed", "CallerRelease", "Prepublication",
          "Publish", "Installed", "InstalledFlushed", "InstalledParentFlushed",
          "InstalledRechecked", "ObservationCreated", "ObservationChecked",
          "ObservationFlushed", "ObservationParentFlushed")
MATRIX = (
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


def require(condition, message):
    if not condition:
        raise ValueError(message)


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def decode(raw):
    def reject(_value):
        raise ValueError("nonfinite JSON number")
    return json.loads(raw, object_pairs_hook=strict_object, parse_constant=reject)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def reference(root, ref):
    require(isinstance(ref, dict) and set(ref) == {"path", "sha256"}, "reference schema")
    path = Path(ref["path"])
    require(not path.is_absolute() and path.parts and not any(
        part in ("..", ".") for part in path.parts), "reference must stay below manifest")
    target = (root / path).resolve()
    require(target.is_relative_to(root.resolve()) and target.is_file(), "reference outside root or missing")
    require(target.stat().st_size <= 16 * 1024 * 1024, "reference bound")
    raw = target.read_bytes()
    require(digest(raw) == ref["sha256"], "reference hash mismatch")
    return raw


def integer(value, message):
    require(type(value) is int and 0 <= value < 2**64, message)
    return value


def snapshot_binding(row, include_digest=False):
    security = row["owner_dacl"].encode("utf-8")
    require(0 < len(security) <= 8192, "security text bound")
    values = [integer(row[key], "native property type/range") for key in FIELDS]
    result = PREFIX + struct.pack("<8Q", *values, len(security)) + security
    if include_digest:
        result += bytes.fromhex(row["sha256"])
    return result


def parse_snapshot(raw):
    require(raw.startswith(PREFIX) and len(raw) >= len(PREFIX) + 64, "binding snapshot prefix/extent")
    values = struct.unpack_from("<8Q", raw, len(PREFIX))
    n = values[-1]
    end = len(PREFIX) + 64 + n
    require(0 < n <= 8192 and end <= len(raw), "binding security extent")
    security = raw[len(PREFIX) + 64:end].decode("utf-8")
    return dict(zip(FIELDS, values[:-1]), owner_dacl=security), raw[end:]


def file_bytes(row):
    require(isinstance(row["content_base64"], str) and len(row["content_base64"]) <= 87384,
            "base64 content bound")
    raw = base64.b64decode(row["content_base64"], validate=True)
    require(len(raw) <= 65536 and len(raw) == integer(row["size"], "size type/range"), "content size")
    require(digest(raw) == row["sha256"], "content hash")
    return raw


def read_snapshot(value):
    require(value["schema"] == "imageinfo-0175-independent-snapshot-v1", "snapshot schema")
    require(value["read_only"] is True and value["authority"] == "none", "observer authority")
    require(isinstance(value["errors"], list), "observer errors shape")
    rows = value["files"]
    require(isinstance(rows, list) and len(rows) <= 7, "snapshot inventory bound")
    files = {}
    for row in rows:
        name = row["path"].replace("\\", "/")
        require(name == "source.bin" or name in {"unit/" + v for v in (
            "candidate.bin", "output.bin", *RECORDS)}, "unexpected namespace member")
        require(name not in files and row["directory"] is False, "duplicate/wrong-kind member")
        require(row["attributes"] & (16 | 1024) == 0, "file attributes/reparse")
        require(row["links"] == 1 and row["streams"] == ["::$DATA"], "file links/streams")
        snapshot_binding(row, True)
        file_bytes(row)
        files[name] = row
    require("source.bin" in files and file_bytes(files["source.bin"]) == SOURCE, "source bytes changed/missing")
    for name in ("unit/candidate.bin", "unit/output.bin"):
        if name in files:
            require(file_bytes(files[name]) == CANDIDATE, "candidate/output bytes changed")
    require(not {"unit/candidate.bin", "unit/output.bin"} <= files.keys(), "candidate and output both named")
    for row in value["directories"].values():
        require(row["directory"] is True and row["attributes"] & 16 and not row["attributes"] & 1024,
                "directory kind/reparse")
        require(row["streams"] in ([], ["::$DATA"]), "directory streams")
        snapshot_binding(row)
    return files


def parse_record(raw, name, implementation):
    """Independent fixed wire decoder; never constructs a current-caller proof."""
    require(name in RECORDS and 0 < len(raw) <= 65536, "record name/size")
    at = 0

    def field(bound):
        nonlocal at
        require(at + 4 <= len(raw), "record truncated length")
        n = struct.unpack_from("<I", raw, at)[0]
        at += 4
        require(n <= bound and at + n <= len(raw), "record field bound/extent")
        value = raw[at:at + n]
        at += n
        return value

    expected = ("windows-new-output-contract-v1", "windows-ntfs-unqualified-internal-v1",
                implementation, "0175-authored-single-output-v1", "0175-marker-only-v1",
                "output.bin", name)
    for text in expected:
        require(field(256) == text.encode("utf-8"), "record identifier")
    require(field(8) == struct.pack("<Q", len(CANDIDATE)), "record planned length")
    index = RECORDS.index(name)
    bindings = []
    for _ in range(3 + index):
        identity, facts = field(256), field(8192)
        require(len(identity) == 16 and 0 < len(facts) <= 8192, "record binding")
        require(identity not in [b[0] for b in bindings], "duplicate binding identity")
        parsed, _ = parse_snapshot(facts)
        require(identity == struct.pack("<2Q", parsed["volume"], parsed["file_index"]), "binding identity disagrees with facts")
        bindings.append((identity, facts))
    for phase in PHASES[:(5, 9, 20, 24)[index]]:
        require(field(256) == phase.encode("ascii"), "record phase/order")
    require(at == len(raw), "record trailing bytes")
    return bindings


def stable_snapshot(value):
    # Observation timestamp, boot and diagnostic paths are separate evidence.
    directories = {name: dict(row) for name, row in value["directories"].items()}
    # inspect-events.jsonl is a declared fresh diagnostic in the containing cell,
    # outside transaction root. Its creation changes parent size/time/archive;
    # retain raw observations, compare all other parent properties exactly.
    if "parent" in directories:
        parent = directories["parent"]
        parent.pop("size", None)
        parent.pop("last_write_time", None)
        parent["attributes"] &= ~32
    return {"files": sorted(value["files"], key=lambda row: row["path"]),
            "directories": directories, "errors": value["errors"]}


def inventory_matches(event, files):
    inventory = event["inventory"]
    require(len(inventory) == len(files), "event/reopened inventory count differs")
    seen = set()
    for old in inventory:
        name = old["path"].replace("\\", "/")
        require(name in files and name not in seen, "event/reopened name differs")
        seen.add(name)
        for key in ("size", "sha256", "attributes", "creation_time", "last_write_time"):
            require(type(old[key]) is type(files[name][key]) and old[key] == files[name][key],
                    "event/reopened " + name + " " + key + " differs")


def compare_binding(identity, facts, row, directory=False):
    require(identity == struct.pack("<2Q", row["volume"], row["file_index"]), "reopened identity differs")
    old, tail = parse_snapshot(facts)
    for key in (*FIELDS, "owner_dacl"):
        if directory and key in ("size", "last_write_time"):
            continue
        actual, expected = row[key], old[key]
        if directory and key == "attributes":
            actual, expected = actual & ~32, expected & ~32
        require(actual == expected, "reopened binding " + key + " differs")
    if directory:
        return tail
    require(tail == bytes.fromhex(row["sha256"]), "reopened binding content hash differs")
    return b""


def reconcile_records(files, snapshot, implementation):
    chains = []
    for name in RECORDS:
        if "unit/" + name in files:
            chains.append((name, parse_record(file_bytes(files["unit/" + name]), name, implementation)))
    prior = None
    for _name, chain in chains:
        if prior:
            require(chain[:len(prior)] == prior, "record binding chain disagreement")
        prior = chain
    if not chains:
        return []
    chain = chains[-1][1]
    compare_binding(*chain[0], files["source.bin"])
    require("root" in snapshot["directories"] and "parent" in snapshot["directories"], "directory facts missing")
    tail = compare_binding(*chain[1], snapshot["directories"]["root"], directory=True)
    require(tail.startswith(PARENT), "containing parent tag missing")
    parent_facts = tail[len(PARENT):]
    parent = snapshot["directories"]["parent"]
    parent_id = struct.pack("<2Q", parent["volume"], parent["file_index"])
    require(compare_binding(parent_id, parent_facts, parent, directory=True) == b"", "parent trailing facts")
    candidate = files.get("unit/output.bin", files.get("unit/candidate.bin"))
    require(candidate is not None, "bound candidate/output missing")
    compare_binding(*chain[2], candidate)
    missing = []
    for index, binding in enumerate(chain[3:]):
        name = "unit/" + RECORDS[index]
        if name not in files:
            missing.append(name)
        else:
            compare_binding(*binding, files[name])
    return missing


def reconcile_exported_bindings(events, files, snapshot, partial_cleanup):
    exports = [event["facts"]["bindings"] for event in events if "bindings" in event["facts"]]
    if not exports:
        return False
    chain = [(bytes.fromhex(item["identity"]), bytes.fromhex(item["facts"])) for item in exports[-1]]
    if not chain:
        return False
    require(1 <= len(chain) <= 7 and len(set(b[0] for b in chain)) == len(chain), "export binding count/identity")
    compare_binding(*chain[0], files["source.bin"])
    if len(chain) >= 2:
        root = snapshot["directories"]["root"]
        tail = compare_binding(*chain[1], root, directory=True)
        require(tail.startswith(PARENT), "export parent missing")
        parent = snapshot["directories"]["parent"]
        require(compare_binding(struct.pack("<2Q", parent["volume"], parent["file_index"]),
                                tail[len(PARENT):], parent, directory=True) == b"", "export parent trailing bytes")
    if len(chain) >= 3:
        compare_binding(*chain[2], files.get("unit/output.bin", files.get("unit/candidate.bin")))
    for index, binding in enumerate(chain[3:]):
        name = "unit/" + RECORDS[index]
        if partial_cleanup and name == "unit/prepared.record":
            require(name not in files, "partial cleanup kept first record")
        else:
            require(name in files, "exported record missing")
            compare_binding(*binding, files[name])
    return True


def expected_names(checkpoint):
    names = {"source.bin"}
    if checkpoint == "candidate-ready":
        return names | {"unit/candidate.bin"}
    records = set(RECORDS[:2])
    if checkpoint not in ("intent-ready", "possible-publication", "publication-api-response", "installed-ack"):
        records = set(RECORDS)
    if checkpoint == "cleanup-one-removed":
        records.remove("prepared.record")
    data = "candidate.bin" if checkpoint in ("intent-ready", "possible-publication") else "output.bin"
    return names | {"unit/" + name for name in records | {data}}


def parse_events(raw):
    require(0 < len(raw) <= 4 * 1024 * 1024 and raw.endswith(b"\n"), "event file bound/framing")
    lines = raw.splitlines(keepends=True)
    require(len(lines) <= 128, "event count bound")
    events = [decode(line) for line in lines]
    pids = set()
    for n, event in enumerate(events, 1):
        require(event["schema"] == "imageinfo-0175-event-v1" and type(event["sequence"]) is int
                and event["sequence"] == n, "event schema/sequence")
        pids.add(integer(event["pid"], "event pid"))
        require(type(event["gate"]) is bool, "gate boolean")
        facts = event["facts"]
        for key in ("production_profile_admitted", "raw_admitted", "imported_authority", "mutation_attempted"):
            if key in facts:
                require(facts[key] is False, "diagnostic claims forbidden authority/admission")
        require(facts.get("status") != "Committed", "unqualified actor claims Committed")
    require(len(pids) == 1, "mixed actor pids")
    return events, lines


def profile_binding(profile, binding):
    """Independently decode fixed live launch/QMP facts, no collector imports."""
    args = binding["argv"]
    require(isinstance(args, list) and args and Path(args[0]).name == "qemu-system-x86_64", "emulator executable")
    root = binding["root"]
    require(root.startswith("/var/tmp/imageinfo-windows-eval-20261014/production-0175-")
            and "/../" not in root and root.count("/") == 4, "disposable root scope")
    require(root == profile["emulator"]["root"], "live disposable root differs")
    require(binding["emulator_sha256"] == profile["hypervisor_executable_sha256"], "live emulator build differs")
    require(args == profile["hypervisor_arguments"] == profile["launch"]["argv"], "live launcher argv differs")
    require(args.count("-machine") == 1 and args[args.index("-machine") + 1] == "q35,accel=kvm,smm=on", "machine profile")
    require(args.count("-drive") == 3, "unexpected drive denominator")
    drives = [args[index + 1] for index, arg in enumerate(args[:-1]) if arg == "-drive"]
    require(drives[2] == f"file={root}/windows.qcow2,if=ide,format=qcow2,cache=writeback", "system drive/cache profile")
    require(drives[0].startswith("if=pflash,format=raw,unit=0,readonly=on,file=")
            and drives[0].endswith("/usr/share/OVMF/OVMF_CODE_4M.ms.fd")
            and drives[1] == f"if=pflash,format=raw,unit=1,file={root}/vars.fd", "firmware drive profile")
    require(f"unix:{root}/qmp,server=on,wait=off" in args, "QMP root differs")
    require(not any(arg in ("-blockdev", "-hda", "-hdb", "-hdc", "-hdd", "-fda", "-fdb", "-cdrom",
                            "-virtfs", "-fsdev", "-readconfig", "-chroot")
                    or "hostfwd" in arg or "media=cdrom" in arg or "/dev/" in arg for arg in args), "unexpected host/disk path")
    selected = [item["inserted"] for item in binding["blocks"]
                if item.get("inserted", {}).get("file") == root + "/windows.qcow2"]
    require(len(selected) == 1, "actual system block ambiguous")
    image = selected[0]["image"]
    base = "/var/tmp/imageinfo-windows-eval-20261014/windows.qcow2"
    require(image["filename"] == root + "/windows.qcow2" and image["format"] == "qcow2"
            and image["full-backing-filename"] == base, "system image/backing differs")
    backing = image["backing-image"]
    require(backing["filename"] == base and backing["format"] == "qcow2"
            and not backing.get("backing-image") and not backing.get("backing-filename"), "backing chain differs")


def validate_profile(profile, frozen):
    require(profile["schema"] == "imageinfo-0175-profile-v1", "profile schema")
    require(profile["filesystem"] == "NTFS" and profile["cache"] == "writeback"
            and profile["host_caches_survive_vmoff"] is True and profile["host_caches_alive"] is True
            and profile["physical_power_tested"] is False, "declared profile/cache scope")
    require(profile["actor_executable_sha256"] == frozen["executable"]["sha256"]
            and profile["actor_source_sha256"] == frozen["actor_source"]["sha256"]
            and profile["controller_sha256"] == frozen["controller"]["sha256"]
            and profile["auditor_sha256"] == frozen["audit_storage_vmoff_175_py"]["sha256"], "profile tooling hashes")
    for field in ("actor_toolchain", "actor_build_command", "native_baseline_evidence_sha256", "freeze_review_evidence_sha256"):
        require(isinstance(profile[field], str) and profile[field], "missing exact build/review baseline")
    raw = profile["guest"]["raw"]
    require(profile["guest_os_version"] == raw["version"] == "10.0.26300"
            and profile["guest_os_build"] == raw["build"] == "26300", "declared guest build differs")
    require(profile["guest_os_servicing_revision"] == raw["servicingRevision"], "servicing revision differs")
    require(raw["filesystem"] == "NTFS" and raw["driveType"] == 3 and raw["clusterBytes"] > 0
            and raw["volumeSizeBytes"] > 0 and raw["controllers"] and raw["controllerDrivers"] and raw["disks"], "guest storage facts missing")
    groups = "\n".join(raw["groups"])
    require("S-1-16-8192" in groups and "S-1-5-32-544" not in groups, "ordinary guest token differs")
    cache = raw["guestCachePolicy"]
    encoded = base64.b64decode(cache["rawBase64"], validate=True)
    require(27 <= len(encoded) <= 64 and cache["querySucceeded"] is True and cache["settingChanged"] is False, "cache observation extent/effect")
    values = struct.unpack_from("<6I", encoded)
    require(values[0] >= 27 and 27 <= values[1] <= len(encoded), "cache descriptor extent")
    for key, value in zip(("version", "size", "type", "enabled", "changeable", "writeThrough"), values):
        require(type(cache[key]) is int and cache[key] == value, "cache native descriptor disagrees")
    require(cache["type"] in (1, 2, 3) and cache["enabled"] in (1, 2) and cache["writeThrough"] in (1, 2), "unknown guest cache policy")
    for key, value in zip(("flushSupported", "userPowerProtection", "nonvolatileCacheEnabled"), encoded[24:27]):
        require(type(cache[key]) is bool and cache[key] == bool(value), "cache native Boolean disagrees")
    profile_binding(profile, profile["emulator"])


def audit_cell(root, cell, frozen, implementation, profile_hash, profile):
    report = {"id": cell["id"], "status": cell["status"], "requested_checkpoint": cell["requested_checkpoint"],
              "observed_checkpoint": None, "discrepancies": [], "refusals": []}
    if cell["status"] == "not-run":
        report["refusals"].append("declared cell not run")
        return report
    refs = cell["references"]

    def raw(name):
        require(name in refs, "missing reference " + name)
        return reference(root, refs[name])

    def load(name):
        return decode(raw(name))

    try:
        require(cell["status"] in ("actual", "refused"), "cell status")
        request, run = load("request"), load("run_result")
        for key, expected in (("cell_id", cell["id"]), ("mode", cell["mode"]),
                              ("fault", cell["fault"]), ("requested_checkpoint", cell["requested_checkpoint"]),
                              ("executable_sha256", frozen["executable"]["sha256"]),
                              ("reader_sha256", frozen["reader"]["sha256"])):
            require(request[key] == expected, "request differs " + key)
        require(run["exit_confirmed"] is True, "actor exit not confirmed")
        events, lines = parse_events(raw("events"))
        require(all(event["pid"] == run["actor_pid"] for event in events), "actor pid mismatch")
        gated = [event for event in events if event["gate"]]
        if cell["fault"] != "none" and cell["status"] == "actual":
            require(len(gated) == 1 and gated[0]["event"] == cell["requested_checkpoint"], "requested checkpoint not actually gated")
            gate = load("gate")
            event = gated[0]
            for key, expected in (("observed_checkpoint", event["event"]), ("actor_pid", event["pid"]),
                                  ("event_sequence", event["sequence"]), ("gate_armed", True),
                                  ("event_sha256", digest(lines[event["sequence"] - 1]))):
                require(type(gate[key]) is type(expected) and gate[key] == expected, "gate mismatch " + key)
            require(events[-1] == event, "actor continued after interrupted gate")
            require(run["fault_confirmed"] is True and run["observed_checkpoint"] == event["event"], "fault/checkpoint unconfirmed")
            report["observed_checkpoint"] = event["event"]
        elif cell["status"] == "refused":
            require(run["fault_confirmed"] is False and isinstance(run["reason"], str) and run["reason"], "refusal provenance missing")
            report["refusals"].append(run["reason"])
            report["observed_checkpoint"] = run["observed_checkpoint"]
        else:
            require(not gated and run["fault_confirmed"] is False, "normal cell fault/gate")
            require(any(event["event"] == "completed-predicate" for event in events), "normal protocol completion missing")
        before, after = load("snapshot_before"), load("snapshot_after")
        files, files_after = read_snapshot(before), read_snapshot(after)
        require(not before["errors"] and not after["errors"], "independent observer retained errors")
        require(stable_snapshot(before) == stable_snapshot(after), "read-only inspection changed artifacts/properties")
        inventory_matches(events[-1], files)
        if cell["status"] == "actual":
            require(set(files) == expected_names(cell["requested_checkpoint"]), "checkpoint namespace predicate differs")
        exported = reconcile_exported_bindings(events, files, after, cell["requested_checkpoint"] == "cleanup-one-removed")
        if cell["status"] == "actual":
            require(exported, "actual checkpoint has no original held bindings")
            if cell["requested_checkpoint"] == "finalize-receipt-created":
                require(events[-1]["facts"]["fresh_receipt_binding_exported"] is True
                        and len(events[-1]["facts"]["bindings"]) == 7, "fresh finalize receipt identity not retained")
        missing = reconcile_records(files_after, after, implementation)
        if cell["requested_checkpoint"] == "cleanup-one-removed":
            require(len(missing) <= 1 and "unit/output.bin" in files, "partial cleanup unexpected survivor set")
            removed = set("unit/" + name for name in RECORDS) - files.keys()
            require(len(removed) == 1, "partial cleanup did not retain exact one-removal state")
            report["removed_records"] = sorted(removed)
        else:
            require(not missing, "record chain refers to missing prior objects")
        if cell["status"] == "actual" and cell["requested_checkpoint"] in (
                "none", "final-success-response", "completed-predicate"):
            terminal = [event for event in events if event["event"] in (
                "final-success-response", "completed-predicate")]
            require(terminal and all(event["facts"]["protocol_complete"] is True
                    and event["facts"]["status"] == "Refused"
                    and event["facts"]["publication_possible"] is True for event in terminal),
                    "completed predicate absent or optimistic")
        inspected, _ = parse_events(raw("inspect_events"))
        require(len(inspected) == 1 and inspected[0]["event"] == "read-only-inspection", "inspect event shape")
        facts = inspected[0]["facts"]
        require(facts["authority"] == "MissingAuthority" and facts["survivor"] == "RecoveryRequired"
                and facts["mutation_attempted"] is False, "new process imported recovery authority")
        inventory_matches(inspected[0], files_after)
        result = load("inspect_result")
        require(result["authority_imported"] is False and result["mutation_requested"] is False, "inspect invoked action")
        report["inspection"] = {"exit_code": result["exit_code"], "collected": facts["collected"], "refusal": facts["refusal"],
                                "authority": facts["authority"]}
        if result["exit_code"] != 0 or not facts["collected"]:
            report["refusals"].append("read-only inspection refused; no imported authority")
        hello_before, hello_after = load("before_hello"), load("after_hello")
        for hello in (hello_before, hello_after):
            require(hello["executable_sha256"] == frozen["executable"]["sha256"]
                    and hello["reader_sha256"] == frozen["reader"]["sha256"], "guest tool freeze differs")
            for key in ("version", "build", "servicingRevision", "architecture", "filesystem", "volumeSerial", "driveType",
                        "clusterBytes", "volumeSizeBytes", "volumeDeviceId", "controllers", "controllerDrivers", "disks", "guestCachePolicy", "groups",
                        "workerSha256", "readerSha256", "scriptSha256"):
                require(hello["raw"][key] == profile["guest"]["raw"][key], "guest profile observation differs " + key)
        serial = profile["guest"]["raw"]["volumeSerial"]
        require(isinstance(serial, str) and int(serial, 16) == files["source.bin"]["volume"], "native source/guest volume differs")
        require(hello_before["host_boot_utc"] == hello_after["host_boot_utc"], "host boot changed")
        require(hello_after["boot_utc"] == before["boot_utc"] == after["boot_utc"], "snapshot/guest boot mismatch")
        require(hello_after["os_build"] == after["os_build"] and hello_after["os_version"] == after["os_version"], "guest OS mismatch")
        changed = hello_before["boot_utc"] != hello_after["boot_utc"]
        require(changed == (cell["fault"] == "vm-off" and cell["status"] == "actual"), "actual guest restart mismatch")
        if cell["fault"] == "vm-off" and cell["status"] == "actual":
            off, target, launch = load("off_completed"), load("off_target"), load("restart_launch")
            require(off["vm_process_exit_confirmed"] is True and off["requested_cell_id"] == cell["id"], "VM exit confirmation missing")
            require(target["profile_sha256"] == launch["profile_sha256"] == profile_hash, "VM target profile mismatch")
            require(launch["exit_code"] == 0 and off["host_boot_utc"] == hello_before["host_boot_utc"]
                    and off["host_caches_alive"] is True, "VM restart/host receipt differs")
            profile_binding(profile, target)
            profile_binding(profile, launch["live_binding"])
        report["guest_restarted"] = changed
        report["source_preserved"] = True
        report["file_count"] = len(files)
    except (KeyError, TypeError, ValueError, OSError, UnicodeError, struct.error) as error:
        report["discrepancies"].append(str(error))
    return report


def audit(manifest, root):
    require(manifest["schema"] == "imageinfo-0175-audit-manifest-v1", "manifest schema")
    frozen = manifest["frozen"]
    require({"executable", "actor_source", "reader", "controller", "source_manifest", "audit_storage_vmoff_175_py",
             "test_audit_storage_vmoff_175_py", "test_read_storage_artifacts_175_py"} <= frozen.keys(), "freeze incomplete")
    for ref in frozen.values():
        reference(root, ref)
    source_manifest = decode(reference(root, frozen["source_manifest"]))
    require(source_manifest["workerSha256"] == frozen["executable"]["sha256"]
            and source_manifest["implementation"] == manifest["implementation"], "source/executable revision differs")
    sources = source_manifest["sources"]
    require({"Cargo.toml", "Cargo.lock", "rust-toolchain.toml", "src/lib.rs", "src/storage/mod.rs",
             "src/storage/runtime.rs", "src/storage/windows.rs", "src/storage/qualification.rs",
             "src/storage/inspection.rs", "src/storage/finalization.rs", "src/storage/cleanup.rs",
             "src/storage/custody.rs", "src/storage/resources.rs", "crates/imageinfo-windows-storage/src/lib.rs",
             "crates/imageinfo-windows-storage/src/native.rs", "crates/imageinfo-windows-storage/src/windows.rs"} <= sources.keys(),
            "production source freeze incomplete")
    for relative, expected in sources.items():
        require("\\" not in relative and not relative.startswith("/"), "source path syntax")
        require(frozen["source_" + relative.replace("/", "_")]["sha256"] == expected, "frozen source manifest disagreement")
    require(frozen["source_src_storage_qualification.rs"]["sha256"] == frozen["actor_source"]["sha256"], "actor source freeze disagreement")
    profile_raw = reference(root, manifest["profile"])
    profile = decode(profile_raw)
    validate_profile(profile, frozen)
    for key in ("actor_toolchain", "actor_build_command", "native_baseline_evidence_sha256", "freeze_review_evidence_sha256"):
        require(profile[key] == source_manifest[key], "profile/source build evidence differs")
    choice = manifest["possible_publication_checkpoint"]
    require(choice in ("possible-publication", "publication-api-response"), "undeclared publication checkpoint")
    cells = manifest["cells"]
    require(len(cells) == len(MATRIX), "fixed twelve-cell denominator")
    for cell, expected in zip(cells, MATRIX):
        checkpoint = choice if expected[3] == "possible-publication" else expected[3]
        require((cell["id"], cell["mode"], cell["fault"], cell["requested_checkpoint"]) == (*expected[:3], checkpoint), "fixed matrix/order mismatch")
    reports = [audit_cell(root, cell, frozen, manifest["implementation"], digest(profile_raw), profile) for cell in cells]
    return {"schema": "imageinfo-0175-retained-audit-v1",
            "ok": all(not row["discrepancies"] for row in reports),
            "campaign_complete": all(row["status"] == "actual" and not row["discrepancies"] for row in reports),
            "cells": reports, "evidence_sha256": digest(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()),
            "production_profile_admitted": False, "raw_admitted": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    require(not args.output.exists(), "fresh audit output required")
    manifest = decode(args.manifest.read_bytes())
    try:
        require(digest(Path(__file__).read_bytes()) == manifest["frozen"]["audit_storage_vmoff_175_py"]["sha256"],
                "executed auditor differs from frozen source")
        report = audit(manifest, args.manifest.resolve().parent)
    except (KeyError, TypeError, ValueError, OSError, UnicodeError, struct.error) as error:
        report = {"schema": "imageinfo-0175-retained-audit-v1", "ok": False, "campaign_complete": False,
                  "discrepancies": [str(error)], "production_profile_admitted": False, "raw_admitted": False}
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"ok": report["ok"], "campaign_complete": report["campaign_complete"]}))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
