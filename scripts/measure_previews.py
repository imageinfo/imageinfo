"""Finite authored stored-preview smoke measurements; no camera baseline claims."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import time
from datetime import datetime, timezone

import read_benchmark as bounded

ROOT = Path(__file__).resolve().parents[1]
REVISION = "preview-collector-v1"
TAGS = ("ThumbnailImage", "PreviewImage", "JpgFromRaw")


def require(value, message):
    if not value:
        raise ValueError(message)


def save(path, value):
    with Path(path).open("xb") as stream:
        stream.write((json.dumps(value, indent=2, allow_nan=False) + "\n").encode())


def identity(path):
    stat = Path(path).stat()
    return {"sha256": bounded.digest(path), "bytes": stat.st_size, "mtimeNs": stat.st_mtime_ns}


def schedule(p):
    result = []
    for operation, tag in [("list", None)] + [("extract", t) for t in TAGS]:
        for phase, count in [("warmup", p["warmups"]), ("sample", p["repeats"])]:
            for _ in range(count):
                result.append({"operation": operation, "tag": tag, "phase": phase, "expected": "success"})
    for expected in ("collision", "preview-limit"):
        for tag in TAGS:
            result.append({"operation": "extract", "tag": tag, "phase": "control", "expected": expected})
    return result


def validate_protocol(p):
    require(p["protocolRevision"] == REVISION and p["schemaVersion"] == 1, "wrong protocol revision")
    bounded.integer(p["warmups"], 0, 10)
    bounded.integer(p["repeats"], 1, 100)
    bounded.integer(p["timeoutMs"], 1, 60000)
    bounded.integer(p["captureBytes"], 1, 4194304)
    bounded.integer(p["maxBytes"], 1, 268435456)
    bounded.integer(p["maxPreviewBytes"], 1048583, 1073741824)
    require(p["status"] == "fixed-before-collection", "protocol must be frozen")
    require([r["tag"] for r in p["resources"]] == list(TAGS), "exact authored resources required")
    require([r["bytes"] for r in p["resources"]] == [4096, 65536, 1048583], "fixed authored sizes required")
    require(p["fixtureKind"] == "authored-structural-no-camera-data", "authored fixture required")


def argv_for(p, binary, source, target, cell):
    argv = [str(binary), "binary", cell["operation"], "--output", "json", "--max-bytes", str(p["maxBytes"])]
    if cell["operation"] == "extract":
        argv += ["--tag", cell["tag"], "--output-file", str(target), "--max-preview-bytes",
                 "1" if cell["expected"] == "preview-limit" else str(p["maxPreviewBytes"])]
    return argv + ["--", str(source)]


def check_envelope(data, sample, cell, p, source, target):
    """Assert advertised outcome and independently authored exact source extents."""
    value = json.loads(data)
    summary = value["summary"]
    files = value["files"]
    require(sample["outcome"] == "exited" and not sample["censored"], "unfinished process")
    require(value["schemaVersion"] == 1 and value["request"]["operation"] == "binary " + cell["operation"], "operation mismatch")
    require(summary["outputComplete"] is True and summary["selectionComplete"] is True
            and summary["interrupted"] is False, "incomplete summary")
    require(len(files) == 1 and files[0]["path"] == str(source), "source selection mismatch")
    require(files[0]["effects"] == {"publicationMayHaveOccurred": False, "changed": False,
            "cleanupPending": False, "recoveryIds": [], "notes": []}, "source effects")
    expected = cell["expected"]
    if expected == "success":
        require(sample["exitCode"] == summary["exitStatus"] == 0 and sample["stderrBytes"] == 0
                and files[0]["state"] == "read", "unsuccessful operation")
        if cell["operation"] == "list":
            require(summary["artifacts"] == [], "listing artifact")
            snapshot = files[0]["snapshot"]
            require(snapshot["coverage"] and all(c["state"] == "partial" for c in snapshot["coverage"]), "coverage mismatch")
            resources = {r["id"]: r for r in snapshot["resources"]}
            occurrences = snapshot["occurrences"]
            require([o["tag"]["name"] for o in occurrences] == list(TAGS), "preview names/order mismatch")
            for occurrence, expected_resource in zip(occurrences, p["resources"]):
                resource = resources[occurrence["origin"]["resourceRef"]]
                require(resource["byteLength"] == str(expected_resource["bytes"]) and resource["sha256"] is None
                        and resource["mediaType"] == "image/jpeg", "preview identity mismatch")
                require(resource["content"] == {"kind": "source-ranges", "ranges": [{"length": str(expected_resource["bytes"]),
                        "offset": str(expected_resource["offset"]), "ref": "src-raw", "space": "source"}]}, "extent mismatch")
        else:
            require(summary["artifacts"] == [{"kind": "extraction", "path": str(target), "retainedPath": None,
                    "state": "committed", "transactionId": None, "recoveryIds": []}], "artifact mismatch")
    else:
        code = "DESTINATION_EXISTS" if expected == "collision" else "LIMIT_EXCEEDED"
        require(sample["exitCode"] == summary["exitStatus"] == 1 and files[0]["state"] == "failed"
                and summary["artifacts"] == [] and [i["code"] for i in files[0]["issues"]] == [code], "refusal mismatch")
    return value


def collect(protocol_path, binary, fixture, output):
    protocol_path, binary, fixture, output = map(lambda x: Path(x).resolve(), (protocol_path, binary, fixture, output))
    p = bounded.load(protocol_path)
    validate_protocol(p)
    require(output.is_relative_to(ROOT / ".local") and not output.exists(), "fresh private output directory required")
    require(bounded.digest(binary) == p["binarySha256"], "binary mismatch")
    for name, expected in p["sourcePins"].items():
        require(bounded.digest(ROOT / name) == expected, "source pin mismatch: " + name)
    source = fixture / "source.cr3"
    require(datetime.fromisoformat(p["fixedUtc"]) <= datetime.now(timezone.utc), "future protocol timestamp")
    source_before = identity(source)
    require(source_before["sha256"] == p["sourceSha256"] and source_before["bytes"] == p["sourceBytes"], "fixture mismatch")
    source_bytes = source.read_bytes()
    for resource in p["resources"]:
        data = (fixture / (resource["tag"] + ".bin")).read_bytes()
        require(len(data) == resource["bytes"] and hashlib.sha256(data).hexdigest() == resource["sha256"], "expected resource mismatch")
        require(source_bytes[resource["offset"]:resource["offset"] + resource["bytes"]] == data, "authored extent mismatch")
    output.mkdir()
    (output / "captures").mkdir()
    (output / "outputs").mkdir()
    env = {k: v for k, v in os.environ.items() if k.upper() in {"SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP", "LANG", "LC_ALL", "TZ"}}
    attempts = []
    started = datetime.now(timezone.utc).isoformat()
    abort = None
    try:
        for number, cell in enumerate(schedule(p)):
            sample_id = f"attempt-{number:03}"
            target = output / "outputs" / (sample_id + ".bin") if cell["operation"] == "extract" else None
            if cell["expected"] == "collision":
                with target.open("xb") as stream:
                    stream.write(b"authored-existing-destination\x00")
            target_before = identity(target) if target and target.exists() else None
            argv = argv_for(p, binary, source, target, cell)
            sample, stdout, stderr = bounded.run_process(argv, ROOT, env, p["timeoutMs"], p["captureBytes"])
            sample.update(cell, id=sample_id, argv=argv, cwd=str(ROOT), captures={},
                          target=str(target) if target else None, targetBefore=target_before,
                          targetAfter=None, validation="attempt finalization incomplete", eligible=False)
            attempts.append(sample)
            paths = {}
            for channel, data in [("stdout", stdout), ("stderr", stderr)]:
                path = output / "captures" / (sample_id + "." + channel)
                with path.open("xb") as stream:
                    stream.write(data)
                paths[channel] = str(path)
            validation = "pass"
            try:
                check_envelope(stdout, sample, cell, p, source, target)
                expected_resource = next((r for r in p["resources"] if r["tag"] == cell["tag"]), None)
                if cell["operation"] == "extract":
                    if cell["expected"] == "success":
                        require(target.is_file() and target.stat().st_size == expected_resource["bytes"]
                                and bounded.digest(target) == expected_resource["sha256"], "stored output mismatch")
                    elif cell["expected"] == "collision":
                        require(identity(target) == target_before, "existing destination changed")
                    else:
                        require(not target.exists(), "refusal created destination")
                require(not list((output / "outputs").glob("*.tmp")), "temporary artifact retained")
            except (ValueError, KeyError, TypeError, OSError) as exc:
                validation = type(exc).__name__ + ": " + str(exc)
            sample.update(cell, id=sample_id, argv=argv, cwd=str(ROOT), captures=paths,
                          target=str(target) if target else None, targetBefore=target_before,
                          targetAfter=identity(target) if target and target.exists() else None,
                          validation=validation, eligible=validation == "pass" and cell["phase"] == "sample")
            save(output / "captures" / (sample_id + ".attempt.json"), sample)
    except BaseException as exc:
        abort = type(exc).__name__ + ": " + str(exc)
    try:
        source_after = identity(source)
        unchanged = source_before == source_after and bounded.digest(binary) == p["binarySha256"]
        unchanged = unchanged and all(bounded.digest(ROOT / n) == h for n, h in p["sourcePins"].items())
    except OSError as exc:
        source_after, unchanged = None, False
        abort = abort or type(exc).__name__ + ": " + str(exc)
    unchanged = unchanged and abort is None
    if not unchanged:
        for sample in attempts:
            sample["eligible"] = False
    record = {"schemaVersion": 1, "collectorRevision": REVISION, "status": "aborted" if abort else "completed" if unchanged else "invalid-measurement",
              "abortReason": abort, "plannedAttempts": len(schedule(p)), "remainingAttempts": len(schedule(p)) - len(attempts),
              "protocol": p, "protocolSha256": bounded.digest(protocol_path), "startedUtc": started,
              "finishedUtc": datetime.now(timezone.utc).isoformat(), "source": str(source),
              "sourceBefore": source_before, "sourceAfter": source_after, "binary": str(binary),
              "python": {"path": sys.executable, "sha256": bounded.digest(sys.executable), "version": sys.version},
              "environment": {"os": platform.platform(), "machine": platform.machine(), "allowlistedEnvironment": env},
              "clock": {"name": "time.perf_counter_ns", "resolutionSeconds": time.get_clock_info("perf_counter").resolution,
                        "boundary": "before direct Popen through process exit and both pipe drains; no overhead subtraction"},
              "unavailableTelemetry": {k: {"value": None, "reason": "not instrumented by bounded direct-process collector"}
                                       for k in ("cpuNs", "memoryBytes", "physicalIoBytes", "firstResultNs", "scratchAllocatedBytes")},
              "attempts": attempts, "retainedOutputBytes": sum(x.stat().st_size for x in (output / "outputs").iterdir())}
    save(output / "record.json", record)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("protocol", "binary", "fixture", "output"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    record = collect(args.protocol, args.binary, args.fixture, args.output)
    print(json.dumps({"status": record["status"], "attempts": len(record["attempts"]),
                      "validationsPassed": sum(a["validation"] == "pass" for a in record["attempts"])}))
    return 0 if record["status"] == "completed" and all(a["validation"] == "pass" for a in record["attempts"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
