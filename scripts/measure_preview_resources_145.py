"""Private stored-preview resource observations; never publishes camera results."""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import platform
import sys
import time

import read_benchmark as b
import read_telemetry as telemetry
import measure_batch_read as batch
import measure_read_resources_144 as prior
import measure_previews as preview

REVISION = "preview-resources-145-v1"
OPERATIONS = [("list", None)] + [("extract", tag) for tag in preview.TAGS]
ROOT = Path(__file__).resolve().parents[1]


def rights(p):
    batch.require(p["taskAdmission"] == {"ticket": 145, "scope": "private-stored-preview-resource-analysis",
        "sourceMutationAllowed": False, "reportPublicationAllowed": False, "decodingAllowed": False}, "task admission")
    fixed = datetime.fromisoformat(p["fixedUtc"])
    batch.require(fixed.utcoffset() is not None and fixed.utcoffset().total_seconds() == 0
        and fixed <= datetime.now(timezone.utc), "valid prior UTC preregistration")
    batch.require(b.digest(p["priorProtocol"]) == p["priorProtocolSha256"], "prior protocol changed")
    old = b.load(p["priorProtocol"])
    prior.rights(old)
    batch.require(p["fixture"] == old["fixtureSet"][0], "exact admitted fixture required")
    for path, digest in p["bindings"].items():
        batch.require(b.digest(path) == digest, "frozen evidence/tool changed")
    required = {str(Path(path).resolve()) for path in (p["binary"], p["buildManifest"], sys.executable,
        __file__, b.__file__, telemetry.__file__, batch.__file__, prior.__file__, preview.__file__,
        ROOT / "scripts/audit_preview_resources_145.py", ROOT / "scripts/audit_previews.py", ROOT / "scripts/audit_read_telemetry.py")}
    batch.require(required <= p["bindings"].keys(), "all runtime/tool/build pins required")
    batch.require(p["referenceManifest"] in p["bindings"], "independent reference manifest pin")
    references = b.load(p["referenceManifest"])
    oracle = b.load(p["fixture"]["oracle"], b.MAX_CAPTURE_BYTES)["files"][0]["snapshot"]
    for resource in p["resources"]:
        batch.require({resource["correctness"], resource["reference"]} <= p["bindings"].keys(), "resource evidence pins")
        evidence = b.load(resource["correctness"])
        batch.require(evidence["verdict"] == "pass" and evidence["operation"] == "read" and evidence["caseRef"] == "FXP-007"
            and {"id": p["fixture"]["id"], "sha256": p["fixture"]["inputSha256"]} in evidence["fixtures"], "prior extraction correctness")
        reference = next(r for r in references if r["parentFixtureId"] == p["fixture"]["id"] and r["tag"] == resource["tag"])
        batch.require(reference["sha256"] == resource["sha256"] and int(reference["byteLength"]) == resource["bytes"]
            and Path(resource["reference"]).resolve() == (ROOT / ".local" / reference["received"]).resolve(), "independent reference binding")
        occurrence = next(o for o in oracle["occurrences"] if o["tag"]["name"] == resource["tag"])
        observed = next(r for r in oracle["resources"] if r["id"] == occurrence["origin"]["resourceRef"])
        batch.require(observed["content"]["ranges"] == [{"offset": str(resource["offset"]), "length": str(resource["bytes"]), "ref": "src-raw", "space": "source"}], "historical extent binding")
    batch.require([r["tag"] for r in p["resources"]] == list(preview.TAGS), "three named extents")
    provenance = b.load(p["fixture"]["provenance"])
    batch.require(provenance["rights"]["permissions"]["modify"] == "allowed", "private derivative grant")
    batch.require(p["warmups"] == 2 and p["repeats"] == 10 and p["revision"] == REVISION, "fixed workload")
    batch.require(p["maxBytes"] == 8388608 and p["maxPreviewBytes"] == 67108864, "fixed read/copy limits")


def identity(path):
    stat = Path(path).stat()
    return dict(bytes=stat.st_size, mtimeNs=stat.st_mtime_ns, device=stat.st_dev,
                inode=stat.st_ino, sha256=b.digest(path))


def source_check(p):
    rights(p)  # Recheck grants/evidence before opening media.
    batch.require(Path(p["fixture"]["input"]).stat().st_size <= 1024**3, "source length bound")
    row = identity(p["fixture"]["input"])
    batch.require(row["bytes"] <= 1024**3 and row["sha256"] == p["fixture"]["inputSha256"], "source binding")
    return row


def verify_extents(p):
    with Path(p["fixture"]["input"]).open("rb") as stream:
        for r in p["resources"]:
            batch.require(0 <= r["offset"] and 0 < r["bytes"] <= 64*1024**2, "extent bounds")
            stream.seek(r["offset"])
            expected = Path(r["reference"]).read_bytes()
            batch.require(len(expected) == r["bytes"] and b.digest(r["reference"]) == r["sha256"]
                and stream.read(r["bytes"]) == expected, "independent stored extent differs")


def inventory(folder):
    return {p.name: identity(p) if p.is_file() else {"kind": "directory"} for p in folder.iterdir()}


def collect(root):
    root = Path(root).resolve()
    batch.require(root.is_relative_to(ROOT / ".local"), "private root required")
    p = b.load(root / "protocol.private.json")
    rights(p)
    (root / "captures").mkdir()
    (root / "outputs").mkdir()
    env = {k: v for k, v in os.environ.items() if k.upper() in {"SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP"}}
    env.update(LC_ALL="C", LANG="C", TZ="UTC")
    record = dict(protocolSha256=b.digest(root / "protocol.private.json"), status="aborted", cells=[],
        sourceChecks=[], abortReason=None, environment=env, host=dict(system=platform.system(), version=platform.version(),
        machine=platform.machine()), pythonVersion=platform.python_version(), plannedAttempts=48,
        unavailable={"physicalAllocationBytes": "not instrumented", "temporaryPeakBytes": "no continuous namespace observer",
        "physicalIoBytes": "logical counters are not physical device traffic"})
    epoch = time.perf_counter_ns()
    try:
        initial = source_check(p)
        record["sourceChecks"].append(initial)
        verify_extents(p)
        for ci, (operation, tag) in enumerate(OPERATIONS):
            cell = dict(operation=operation, tag=tag, attempts=[], telemetry=[])
            record["cells"].append(cell)
            for index in range(12):
                target = root / "outputs" / f"c{ci}-a{index}.bin" if tag else None
                before = inventory(root / "outputs")
                batch.require(target is None or not target.exists(), "fresh output name required")
                selection = dict(operation=operation, tag=tag, expected="success")
                argv = preview.argv_for(p, Path(p["binary"]), Path(p["fixture"]["input"]), target, selection)
                observer = telemetry.Observer(10)
                cwd = str(Path(p["binary"]).parent)
                start_offset = time.perf_counter_ns() - epoch
                sample, stdout, stderr = b.run_process(argv, cwd, env, 30000, 4194304, observer)
                sample.update(index=index, phase="warmup" if index < 2 else "sample", argv=argv,
                    cwd=cwd, startOffsetNs=start_offset, endOffsetNs=time.perf_counter_ns() - epoch,
                    operation=operation, tag=tag, expected="success", target=str(target) if target else None,
                    namespaceBefore=before, namespaceAfter=None, captures={}, correctness="fail", eligible=False,
                    finalizationErrors=[])
                # Retain the process outcome before any fallible artifact finalization.
                cell["attempts"].append(sample)
                cell["telemetry"].append(None)
                try:
                    cell["telemetry"][-1] = observer.report()
                except BaseException as error:
                    sample["finalizationErrors"].append("telemetry: " + type(error).__name__)
                for channel, data in (("stdout", stdout), ("stderr", stderr)):
                    name = f"captures/c{ci}-a{index}.{channel}"
                    try:
                        (root / name).write_bytes(data)
                        sample["captures"][channel] = name
                    except BaseException as error:
                        sample["finalizationErrors"].append(channel + ": " + type(error).__name__)
                try:
                    sample["namespaceAfter"] = inventory(root / "outputs")
                except BaseException as error:
                    sample["finalizationErrors"].append("namespace: " + type(error).__name__)
                if sample["finalizationErrors"]:
                    prior.save(root / f"attempt-c{ci}-a{index}.private.json", dict(sample=sample, telemetry=cell["telemetry"][-1]))
                    raise ValueError("attempt finalization failed; actual outcome retained")
                correct = False
                try:
                    preview.check_envelope(stdout, sample, selection, p, Path(p["fixture"]["input"]), target)
                    after = sample["namespaceAfter"]
                    expected_names = set(before) | ({target.name} if target else set())
                    batch.require(set(after) == expected_names and all(after[n] == v for n, v in before.items()), "namespace effects")
                    if tag:
                        resource = next(r for r in p["resources"] if r["tag"] == tag)
                        batch.require(after[target.name]["bytes"] == resource["bytes"] and after[target.name]["sha256"] == resource["sha256"], "exact stored bytes")
                    correct = True
                except (ValueError, KeyError, TypeError, OSError):
                    pass
                report = cell["telemetry"][-1]
                sample.update(correctness="pass" if correct else "fail", eligible=index >= 2 and correct and report["valid"])
                prior.save(root / f"attempt-c{ci}-a{index}.private.json", dict(sample=sample, telemetry=report))
            after = source_check(p)
            record["sourceChecks"].append(after)
            batch.require(after == initial, "source changed")
        rights(p)
        record["status"] = "completed"
    except BaseException as error:
        record["abortReason"] = type(error).__name__ + ": " + str(error)
        raise
    finally:
        if record["status"] != "completed":
            for cell in record["cells"]:
                for sample in cell["attempts"]:
                    sample["eligible"] = False
            # Keep individual evidence and the final ledger in agreement after abort.
            for ci, cell in enumerate(record["cells"]):
                for sample, report in zip(cell["attempts"], cell["telemetry"]):
                    try:
                        path = root / f"attempt-c{ci}-a{sample['index']}.private.json"
                        with path.open("w", encoding="utf-8", newline="\n") as stream:
                            import json
                            json.dump(dict(sample=sample, telemetry=report), stream, indent=2, allow_nan=False)
                    except OSError as error:
                        record["abortReason"] += "; attempt record: " + type(error).__name__
        record["recordedUtc"] = datetime.now(timezone.utc).isoformat()
        record["remainingAttempts"] = 48 - sum(len(c["attempts"]) for c in record["cells"])
        prior.save(root / "record.private.json", record)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", required=True)
    collect(parser.parse_args().run_root)
