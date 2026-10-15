"""Bounded single-file metadata-read collector. Private records; no speed claims."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone

REVISION = "read-collector-v1"
MAX_CONFIG_BYTES = 65536
MAX_CAPTURE_BYTES = 4 * 1024 * 1024


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load(path, limit=MAX_CONFIG_BYTES):
    with Path(path).open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError("JSON input exceeds declared bound")
    return json.loads(data)


def integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"expected integer within {low}..{high}")


def check_config(c):
    required = {"binary", "binarySha256", "input", "inputSha256", "fixtureId",
                "oracle", "oracleSha256", "admissionEvidence", "correctnessEvidence",
                "environment", "repeats", "warmups", "timeoutMs", "captureBytes", "maxBytes"}
    if set(c) != required:
        raise ValueError("configuration has missing or unknown fields")
    for field in ("binarySha256", "inputSha256", "oracleSha256"):
        if not isinstance(c[field], str) or len(c[field]) != 64 or any(x not in "0123456789abcdef" for x in c[field]):
            raise ValueError("expected lowercase SHA-256")
    for field in required - {"environment", "repeats", "warmups", "timeoutMs", "captureBytes", "maxBytes"}:
        if not isinstance(c[field], str) or not c[field]:
            raise ValueError("expected nonempty identity/path/evidence string")
    if not isinstance(c["environment"], dict) or not c["environment"]:
        raise ValueError("environment must declare storage/hardware/power/load facts and unknowns")
    integer(c["repeats"], 1, 100)
    integer(c["warmups"], 0, 10)
    integer(c["timeoutMs"], 1, 60000)
    integer(c["captureBytes"], 1, MAX_CAPTURE_BYTES)
    integer(c["maxBytes"], 1, 256 * 1024 * 1024)


def canonical(value):
    """Ignore only invocation IDs and source display path, never values/coverage."""
    value = json.loads(json.dumps(value))
    request_id = value["requestId"]
    value["requestId"] = "request"
    value["request"]["requestId"] = "request"
    value["summary"]["requestId"] = "request"
    for f in value["files"]:
        f["requestId"] = "request"
        f["path"] = "input"
        snapshot = f.get("snapshot")
        if snapshot:
            if snapshot["id"].startswith(request_id + "-snapshot-"):
                snapshot["id"] = "request" + snapshot["id"][len(request_id):]
            for source in snapshot["sources"]:
                source["displayPath"] = "input"
    return value


def successful(value):
    s = value["summary"]
    return (value["schemaVersion"] == 1 and value["request"]["operation"] == "metadata read"
            and s["exitStatus"] == 0 and s["outputComplete"] is True
            and s["selectionComplete"] is True and s["interrupted"] is False
            and s["artifacts"] == [] and s["counts"] == {
                "discovered": 1, "excluded": 0, "deduplicated": 0, "byState": {"read": 1}}
            and len(value["files"]) == 1 and value["files"][0]["state"] == "read"
            and value["files"][0]["effects"] == {
                "publicationMayHaveOccurred": False, "changed": False,
                "cleanupPending": False, "recoveryIds": [], "notes": []}
            and value["files"][0]["snapshot"]["coverage"]
            and all(x["state"] == "partial" for x in value["files"][0]["snapshot"]["coverage"]))


def run_process(argv, cwd, env, timeout_ms, capture_bytes):
    """Drain both pipes with fixed retained bounds; stop on deadline/overflow.

    Scope is the current direct imageinfo executable, which spawns no helpers.
    This is not a process-tree sandbox or an OS CPU/memory/disk quota.
    """
    data = [bytearray(), bytearray()]
    totals = [0, 0]
    overflow = threading.Event()
    consumer_error = threading.Event()

    def drain(stream, index):
        try:
            while True:
                block = stream.read(4096)
                if not block:
                    break
                totals[index] += len(block)
                available = capture_bytes - len(data[index])
                data[index].extend(block[:available])
                if len(block) > available:
                    overflow.set()
        except OSError:
            consumer_error.set()
        finally:
            stream.close()

    started_utc = datetime.now(timezone.utc).isoformat()
    start = time.perf_counter_ns()
    try:
        p = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
    except OSError as error:
        return {"startedUtc": started_utc, "elapsedNs": time.perf_counter_ns() - start,
                "outcome": "launch-error", "exitCode": None, "censored": False,
                "errorClass": type(error).__name__, "stdoutBytes": 0, "stderrBytes": 0,
                "stdoutCapturedBytes": 0, "stderrCapturedBytes": 0,
                "stdoutSha256": None, "stderrSha256": None}, b"", b""
    threads = [threading.Thread(target=drain, args=(s, i), daemon=True)
               for i, s in enumerate((p.stdout, p.stderr))]
    for thread in threads:
        thread.start()
    outcome = "exited"
    while p.poll() is None:
        if overflow.is_set():
            outcome = "output-limit"
            p.kill()
            break
        if time.perf_counter_ns() - start >= timeout_ms * 1_000_000:
            outcome = "timeout"
            p.kill()
            break
        time.sleep(0.001)
    p.wait()
    for thread in threads:
        thread.join(1)
    if any(t.is_alive() for t in threads) or consumer_error.is_set():
        outcome = "consumer-error"
    elif overflow.is_set() and outcome == "exited":
        outcome = "output-limit"
    elapsed = time.perf_counter_ns() - start
    record = {"startedUtc": started_utc, "elapsedNs": elapsed, "outcome": outcome,
              "exitCode": p.returncode, "censored": outcome in ("timeout", "output-limit", "consumer-error"),
              "errorClass": None, "stdoutBytes": totals[0], "stderrBytes": totals[1],
              "stdoutCapturedBytes": len(data[0]), "stderrCapturedBytes": len(data[1]),
              "stdoutSha256": hashlib.sha256(data[0]).hexdigest(),
              "stderrSha256": hashlib.sha256(data[1]).hexdigest()}
    return record, bytes(data[0]), bytes(data[1])


def collect(c, output):
    check_config(c)
    if Path(output).exists() or Path(output).is_symlink():
        raise ValueError("derived record destination must be fresh")
    for field in ("binary", "input", "oracle"):
        if not Path(c[field]).is_absolute() or digest(c[field]) != c[field + "Sha256"]:
            raise ValueError("absolute artifact path and matching identity required")
    admission = load(c["admissionEvidence"])
    correctness = load(c["correctnessEvidence"])
    if not (admission["id"] == c["fixtureId"] and admission["admission"] == "admitted"
            and admission["rights"]["analyze"] is True
            and admission["artifact"]["sha256"] == c["inputSha256"]
            and admission["media"]["format"] == "CR3"
            and admission["media"]["captureMode"] == "full-raw"):
        raise ValueError("matching admitted lawful full RAW fixture required")
    if not (correctness["verdict"] == "pass" and correctness["operation"] == "read"
            and {"id": c["fixtureId"], "sha256": c["inputSha256"]} in correctness["fixtures"]
            and correctness["candidate"]["stdout"]["sha256"] == c["oracleSha256"]):
        raise ValueError("linked passing read evidence must bind fixture and exact oracle")
    oracle = load(c["oracle"], MAX_CAPTURE_BYTES)
    if not successful(oracle):
        raise ValueError("oracle is not a complete successful partial-slice read")
    expected = canonical(oracle)
    cwd = str(Path(c["binary"]).parent)
    env = {k: os.environ[k] for k in ("SystemRoot", "WINDIR", "PATH", "TEMP", "TMP") if k in os.environ}
    env.update({"LC_ALL": "C", "LANG": "C", "TZ": "UTC"})
    argv = [c["binary"], "metadata", "read", "--values", "all", "--output", "json",
            "--max-bytes", str(c["maxBytes"]), "--", c["input"]]
    before = Path(c["input"]).stat()
    record = {"schemaVersion": 1, "collectorRevision": REVISION,
              "driverSha256": digest(__file__), "pythonExecutableSha256": digest(sys.executable),
              "pythonVersion": platform.python_version(), "configuration": c,
              "evidenceSha256": {k: digest(c[k]) for k in ("admissionEvidence", "correctnessEvidence")},
              "argv": argv, "cwd": cwd, "processEnvironment": env,
              "host": {"system": platform.system(), "release": platform.release(),
                       "version": platform.version(), "machine": platform.machine()},
              "inputBytes": before.st_size, "cache": {
                  "process": "fresh per attempt", "application": "no persistent session",
                  "os": "uncontrolled; preflight SHA-256 reads may warm caches",
                  "device": "uncontrolled", "server": "unknown/not established",
                  "conditioning": "none; sequential warmups then repeats, no eviction"},
              "consumer": "two bounded in-memory pipe drains; complete JSON validation after timed drain/exit",
              "clock": {"name": "time.perf_counter_ns", "resolutionSeconds": time.get_clock_info("perf_counter").resolution,
                        "unit": "nanoseconds", "boundary": "before Popen through direct exit and pipe drains; validation excluded; overhead not subtracted"},
              "unavailableTelemetry": {k: None for k in ("cpuNs", "peakMemoryBytes", "logicalIoBytes", "physicalIoBytes", "firstResultNs", "queueDepth", "scratchBytes")},
              "unavailableReason": "not instrumented by this stdlib direct-process collector; not zero",
              "attempts": [], "sourceUnchanged": False, "binaryUnchanged": False,
              "status": "completed", "aggregates": None}
    for index in range(c["warmups"] + c["repeats"]):
        attempt, stdout, stderr = run_process(argv, cwd, env, c["timeoutMs"], c["captureBytes"])
        attempt.update({"index": index, "phase": "warmup" if index < c["warmups"] else "sample",
                        "correctness": "not-checked", "eligible": False})
        if attempt["outcome"] == "exited":
            try:
                actual = json.loads(stdout)
                valid = (attempt["exitCode"] == 0 and not stderr and successful(actual)
                         and canonical(actual) == expected)
            except (ValueError, KeyError, TypeError, IndexError, RecursionError):
                valid = False
            attempt["correctness"] = "pass" if valid else "fail"
            attempt["eligible"] = valid and attempt["phase"] == "sample"
        record["attempts"].append(attempt)
    after = Path(c["input"]).stat()
    record["sourceUnchanged"] = (digest(c["input"]) == c["inputSha256"]
                                  and (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns))
    record["binaryUnchanged"] = digest(c["binary"]) == c["binarySha256"]
    if not record["sourceUnchanged"] or not record["binaryUnchanged"]:
        record["status"] = "invalid-measurement"
        for attempt in record["attempts"]:
            attempt["eligible"] = False
    # Exclusive creation also rejects a name inserted after preflight, including
    # an alias of corpus media. Never overwrite a caller-selected existing file.
    with Path(output).open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(record, indent=2) + "\n")
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="private JSON configuration")
    parser.add_argument("--output", required=True, help="private derived record; never stdout/media")
    args = parser.parse_args()
    record = collect(load(args.config), args.output)
    print(f"Retained {len(record['attempts'])} attempts; {record['status']}; private record written")
    return 0 if record["status"] == "completed" and all(
        x["correctness"] == "pass" for x in record["attempts"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
