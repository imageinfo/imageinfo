"""Fixed, private batch-read collection with explicit report-publication gates."""
import argparse
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import sys
import time

import read_benchmark as single

ROOT = Path(__file__).resolve().parents[1]
ORDERS = [[1, 2, 4, 8], [8, 4, 2, 1], [2, 8, 1, 4]]


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def save(path, value):
    with Path(path).open("xb") as stream:
        stream.write((json.dumps(value, indent=2) + "\n").encode("utf-8"))


def normalized_file(item):
    item = copy.deepcopy(item)
    request_id = item["requestId"]
    input_id = item["inputId"]
    require(isinstance(request_id, str) and request_id, "missing request identity")
    item["requestId"] = "request"
    item["inputId"] = "input-0"
    item["path"] = "input"
    for issue in item["issues"]:
        if issue["inputId"] is not None:
            require(issue["inputId"] == input_id, "inconsistent issue input identity")
            issue["inputId"] = "input-0"
    snapshot = item.get("snapshot")
    if snapshot is not None:
        require(snapshot["id"].startswith(request_id + "-snapshot-"), "inconsistent snapshot identity")
        snapshot["id"] = "snapshot"
        for source in snapshot["sources"]:
            source["displayPath"] = "input"
    return item


def wire(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def strict_json(data):
    def members(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "duplicate JSON member")
            result[key] = value
        return result
    def invalid(_):
        raise ValueError("nonfinite JSON number")
    result = json.loads(data, object_pairs_hook=members, parse_constant=invalid)
    def strings(value):
        if isinstance(value, str):
            require(not any(0xD800 <= ord(char) <= 0xDFFF for char in value), "invalid Unicode scalar text")
        elif isinstance(value, dict):
            for key, item in value.items():
                strings(key)
                strings(item)
        elif isinstance(value, list):
            for item in value:
                strings(item)
    strings(result)
    return result


def normalized_envelope(envelope):
    result = copy.deepcopy(envelope)
    identity = result["requestId"]
    require(result["request"]["requestId"] == identity and result["summary"]["requestId"] == identity,
            "inconsistent request/summary identity")
    result["requestId"] = result["request"]["requestId"] = result["summary"]["requestId"] = "request"
    for index, item in enumerate(result["files"]):
        require(item["requestId"] == identity and item["inputId"] == f"input-{index}",
                "inconsistent file identity")
        if item.get("snapshot") is not None:
            require(item["snapshot"]["id"] == f"{identity}-snapshot-{index}", "inconsistent snapshot position")
    result["files"] = [normalized_file(item) for item in result["files"]]
    return result


def rights_before_media(protocol):
    """Inspect local grants/manifests only; no media bytes read by this function."""
    require(protocol["taskAdmission"]["ticket"] == 63
            and protocol["taskAdmission"]["scope"] == "private-read-only-batch-analysis"
            and protocol["taskAdmission"]["sourceMutationAllowed"] is False,
            "fresh bounded private task admission required")
    required = {protocol["primaryGrant"], protocol["privacyReview"]}
    required.update(f[key] for f in protocol["fixtureSet"] for key in ("admission", "provenance", "correctness"))
    require(required <= protocol["evidenceSha256"].keys(), "every rights/native-admission evidence path must be pinned")
    for path, expected in protocol["evidenceSha256"].items():
        require(single.digest(path) == expected, "pinned rights/evidence identity changed")
    single.load(protocol["primaryGrant"])
    privacy = single.load(protocol["privacyReview"])
    require(privacy["status"] == "restricted" and privacy["publicClearance"] is False,
            "this private protocol requires the scoped restricted handling review")
    fixtures = protocol["fixtureSet"]
    require(len(fixtures) == 8 and len({f["input"] for f in fixtures}) == 8,
            "eight distinct admitted paths required")
    publications = []
    for fixture in fixtures:
        admission = single.load(fixture["admission"])
        provenance = single.load(fixture["provenance"])
        correctness = single.load(fixture["correctness"])
        require(admission["id"] == fixture["id"] and admission["admission"] == "admitted"
                and admission["revision"] >= 2
                and admission["rights"]["analyze"] is True
                and admission["artifact"]["sha256"] == fixture["inputSha256"]
                and admission["media"]["captureMode"] == "full-raw", "fixture not admitted for full RAW analysis")
        permissions = provenance["rights"]["permissions"]
        require(permissions["store"] == "allowed" and permissions["analyze"] == "allowed"
                and provenance["purpose"] == "operational" and provenance["revision"] >= 2
                and provenance["review"]["state"] == "approved"
                and provenance["artifact"]["sha256"] == fixture["inputSha256"],
                "current private native-analysis provenance required")
        require(correctness["verdict"] == "pass" and correctness["operation"] == "read"
                and {"id": fixture["id"], "sha256": fixture["inputSha256"]} in correctness["fixtures"]
                and correctness["candidate"]["stdout"]["sha256"] == fixture["oracleSha256"],
                "passing native oracle evidence must bind this exact source")
        publications.append(permissions["publishReports"] == "allowed")
    return {"analysisAllowed": True, "publishReportsAllowed": all(publications),
            "publicCameraResultsExported": False}


def classify(stdout, stderr, sample, fixtures, expected, template):
    slots = [{"fixtureId": f["id"], "state": "not-observed", "correctness": "not-checked"} for f in fixtures]
    if sample["outcome"] != "exited":
        return slots, "not-checked"
    try:
        envelope = strict_json(stdout)
        request_id = envelope["requestId"]
        require(envelope["request"]["requestId"] == request_id
                and envelope["summary"]["requestId"] == request_id, "inconsistent envelope identity")
        actual = envelope["files"]
        for index, slot in enumerate(slots):
            if index >= len(actual):
                continue
            item = actual[index]
            require(item["path"] == fixtures[index]["input"], "result path does not bind scheduled input")
            if item.get("snapshot") is not None:
                require(item["snapshot"]["id"] == f"{request_id}-snapshot-{index}"
                        and item["snapshot"]["sources"][0]["displayPath"] == item["path"],
                        "snapshot path/identity does not bind scheduled input")
            valid = (item["requestId"] == request_id and item["inputId"] == f"input-{index}"
                     and wire(normalized_file(item)) == expected[index])
            slot.update(state=item["state"] if item["state"] in ("read", "failed", "refused") else "not-observed",
                        correctness="pass" if valid else "fail")
        n = len(fixtures)
        whole = normalized_envelope(template)
        whole["files"] = [strict_json(item) for item in expected]
        whole["summary"]["counts"] = {"discovered": n, "excluded": 0, "deduplicated": 0, "byState": {"read": n}}
        success = (sample["exitCode"] == 0 and not stderr and len(actual) == n
                   and wire(normalized_envelope(envelope)) == wire(whole)
                   and all(s["correctness"] == "pass" for s in slots))
        return slots, "pass" if success else "fail"
    except (ValueError, KeyError, TypeError, IndexError, RecursionError):
        return slots, "fail"


def source_check(protocol, round_index, boundary, initial):
    rights_before_media(protocol)
    rows = []
    unchanged = True
    for fixture in protocol["fixtureSet"]:
        path = Path(fixture["input"])
        metadata = path.stat()
        require(metadata.st_size <= 1024 * 1024 * 1024, "source fixture byte bound exceeded")
        row = {"fixtureId": fixture["id"], "sha256": single.digest(path), "bytes": metadata.st_size,
               "mtimeNs": metadata.st_mtime_ns, "device": metadata.st_dev, "inode": metadata.st_ino}
        initial.setdefault(fixture["id"], row)
        unchanged = unchanged and row == initial[fixture["id"]] and row["sha256"] == fixture["inputSha256"]
        rows.append(row)
    require(len({(r["device"], r["inode"]) for r in rows}) == 8, "batch fixtures must be distinct physical files")
    return {"round": round_index, "boundary": boundary, "fixtures": rows, "unchanged": unchanged}


def collect(run_root):
    root = Path(run_root).resolve()
    require(root.is_relative_to(ROOT / ".local"), "all camera-derived records/captures must remain private under .local")
    protocol_path = root / "protocol.private.json"
    p = single.load(protocol_path)
    require(p["schemaVersion"] == 1 and p["orders"] == ORDERS and p["warmups"] == 2 and p["repeats"] == 10,
            "fixed declared batch schedule required")
    require(p["timeoutMs"] == 30000 and p["captureBytes"] == 4194304 and p["maxBytes"] == 8388608,
            "fixed declared deadline/capture/read budgets required")
    require(single.digest(__file__) == p["runnerSha256"] and single.digest(single.__file__) == p["collectorSha256"],
            "driver changed after protocol pin")
    rights = rights_before_media(p)
    require(single.digest(p["binary"]) == p["binarySha256"], "binary identity changed")
    captures = root / "captures"
    captures.mkdir()
    expected = []
    template = None
    for fixture in p["fixtureSet"]:
        require(single.digest(fixture["oracle"]) == fixture["oracleSha256"], "oracle identity changed")
        oracle = single.load(fixture["oracle"], single.MAX_CAPTURE_BYTES)
        require(single.successful(oracle), "expected oracle must be complete successful native subset read")
        expected.append(wire(normalized_file(oracle["files"][0])))
        if template is None:
            template = oracle
    env = {k: os.environ[k] for k in ("SystemRoot", "WINDIR", "PATH", "TEMP", "TMP") if k in os.environ}
    env.update(LC_ALL="C", LANG="C", TZ="UTC")
    cwd = str(Path(p["binary"]).parent)
    record = {"schemaVersion": 1, "protocolSha256": single.digest(protocol_path), "status": "aborted",
              "rights": rights, "attempts": [], "sourceChecks": [], "binaryUnchanged": False,
              "elapsedUnit": "nanoseconds", "pythonVersion": platform.python_version(),
              "pythonExecutableSha256": single.digest(sys.executable), "processEnvironment": env, "cwd": cwd,
              "host": {"system": platform.system(), "version": platform.version(), "machine": platform.machine()},
              "clock": {"name": "time.perf_counter_ns", "resolutionSeconds": time.get_clock_info("perf_counter").resolution,
                        "boundary": "before Popen through direct exit and both bounded pipe drains; evidence writes/validation excluded; overhead not subtracted"},
              "cache": {"process": "fresh per batch", "application": "no persistent session",
                        "os": "warm-exposed/uncontrolled: all eight whole-source hashes before each round",
                        "device": "uncontrolled", "server": "not established", "conditioning": "no eviction; fixed grid order and 5-second round gaps"},
              "unavailableTelemetry": {k: None for k in ("perFileLatencyNs", "firstResultNs", "cpuNs", "peakMemoryBytes", "logicalIoBytes", "physicalIoBytes")},
              "unavailableReason": "CLI emits a final batch envelope; stdlib collector does not instrument file phases or resource counters"}
    record["abortEligibilityInvalidated"] = False
    record["ledgerEligibilityScope"] = "per-attempt predicate before final source/binary validation; final aborted record invalidates eligibility"
    initial = {}
    with (root / "attempts.private.jsonl").open("xb") as ledger:
        try:
            for round_index, order in enumerate(ORDERS, 1):
                before = source_check(p, round_index, "before", initial)
                record["sourceChecks"].append(before)
                require(before["unchanged"], "source identity changed before round")
                require(single.digest(p["binary"]) == p["binarySha256"], "binary identity changed before round")
                for size in order:
                    fixtures = p["fixtureSet"][:size]
                    argv = [p["binary"], "metadata", "read", "--values", "all", "--output", "json",
                            "--max-bytes", str(p["maxBytes"]), "--", *[f["input"] for f in fixtures]]
                    for index in range(12):
                        sample, stdout, stderr = single.run_process(argv, cwd, env, p["timeoutMs"], p["captureBytes"])
                        stem = f"r{round_index}-n{size}-a{index:02d}"
                        paths = {}
                        for channel, data in (("stdout", stdout), ("stderr", stderr)):
                            name = f"captures/{stem}.{channel}"
                            with (root / name).open("xb") as stream:
                                stream.write(data)
                            paths[channel] = name
                        files, correctness = classify(stdout, stderr, sample, fixtures, expected[:size], template)
                        sample.update(round=round_index, size=size, index=index,
                                      phase="warmup" if index < 2 else "sample", argv=argv, files=files,
                                      batchCorrectness=correctness, eligible=index >= 2 and correctness == "pass",
                                      captures=paths)
                        record["attempts"].append(sample)
                        ledger.write((json.dumps(sample) + "\n").encode("utf-8"))
                        ledger.flush()
                after = source_check(p, round_index, "after", initial)
                record["sourceChecks"].append(after)
                require(after["unchanged"], "source identity changed during round")
                require(single.digest(p["binary"]) == p["binarySha256"], "binary identity changed during round")
                if round_index < 3:
                    time.sleep(5)
            record["binaryUnchanged"] = True
            require(single.digest(__file__) == p["runnerSha256"] and single.digest(single.__file__) == p["collectorSha256"],
                    "driver changed during collection")
            record["status"] = "completed"
        except Exception as error:
            record["abortReason"] = {"class": type(error).__name__, "message": str(error)[:512]}
            raise
        finally:
            if record["status"] != "completed":
                record["abortEligibilityInvalidated"] = True
                for attempt in record["attempts"]:
                    attempt["eligible"] = False
            record["completedAttempts"] = len(record["attempts"])
            record["remainingScheduledAttempts"] = 144 - len(record["attempts"])
            record["recordedUtc"] = datetime.now(timezone.utc).isoformat()
            save(root / "record.private.json", record)
    print("Private batch collection completed; camera-derived statistics were not exported")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", required=True)
    collect(parser.parse_args().run_root)
