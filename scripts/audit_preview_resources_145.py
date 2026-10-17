"""Independent retained stored-preview/resource audit, private output only."""
import argparse
import copy
from datetime import datetime
import hashlib
import json
from pathlib import Path
import statistics

import audit_previews as a
from audit_read_telemetry import audit as counters_audit


def identity(path):
    stat = path.stat()
    return dict(bytes=stat.st_size, mtimeNs=stat.st_mtime_ns, device=stat.st_dev,
                inode=stat.st_ino, sha256=a.digest(path))


def resource_check(document, source, rows):
    snapshot = document["files"][0]["snapshot"]
    a.require([o["tag"]["name"] for o in snapshot["occurrences"]] == list(a.TAGS), "named extent order")
    resources = {r["id"]: r for r in snapshot["resources"]}
    a.require(len(resources) == len(snapshot["resources"]), "duplicate resource identity")
    a.require(snapshot["coverage"] and all(c["state"] == "partial" for c in snapshot["coverage"]), "partial coverage")
    with source.open("rb") as stream:
        for occurrence, row in zip(snapshot["occurrences"], rows):
            ref = occurrence["origin"]["resourceRef"]
            a.require(occurrence["values"]["raw"]["value"]["resourceRef"] == occurrence["values"]["normalized"]["value"]["resourceRef"] == ref, "resource references")
            resource = resources[ref]
            a.require(resource["byteLength"] == str(row["bytes"]) and resource["mediaType"] == "image/jpeg"
                and resource["content"] == {"kind": "source-ranges", "ranges": [{"offset": str(row["offset"]), "length": str(row["bytes"]), "ref": "src-raw", "space": "source"}]}, "exact source range")
            a.require(0 <= row["offset"] and 0 < row["bytes"] <= 64*1024**2 and row["offset"] + row["bytes"] <= source.stat().st_size, "range bounds")
            stream.seek(row["offset"])
            stored = stream.read(row["bytes"])
            reference = Path(row["reference"]).read_bytes()
            a.require(stored == reference and len(reference) == row["bytes"] and hashlib.sha256(reference).hexdigest() == row["sha256"], "independent exact bytes including padding")


def attempt_check(root, p, ci, index, op, tag, sample, counters, previous_end):
    """Check execution/consumer evidence independently of advertised correctness."""
    target = root / "outputs" / f"c{ci}-a{index}.bin" if tag else None
    argv = [p["binary"], "binary", op, "--output", "json", "--max-bytes", "8388608"]
    if tag:
        argv += ["--tag", tag, "--output-file", str(target), "--max-preview-bytes", "67108864"]
    argv += ["--", p["fixture"]["input"]]
    a.require(sample["argv"] == argv and sample["cwd"] == str(Path(p["binary"]).parent), "argv/cwd binding")
    a.require(sample["operation"] == op and sample["tag"] == tag and sample["expected"] == "success", "scheduled operation")
    a.require(sample["index"] == index and sample["phase"] == ("warmup" if index < 2 else "sample"), "phase/index")
    a.require(sample["target"] == (str(target) if target else None), "fresh owned target")
    a.require(type(sample["startOffsetNs"]) is int and type(sample["endOffsetNs"]) is int
        and previous_end <= sample["startOffsetNs"] < sample["endOffsetNs"]
        and type(sample["elapsedNs"]) is int and 0 < sample["elapsedNs"] <= sample["endOffsetNs"] - sample["startOffsetNs"], "serialized start/end order")
    started = datetime.fromisoformat(sample["startedUtc"])
    a.require(started.utcoffset() is not None and started.utcoffset().total_seconds() == 0, "UTC start timestamp")
    fixed = datetime.fromisoformat(p["fixedUtc"])
    a.require(fixed.utcoffset() is not None and fixed.utcoffset().total_seconds() == 0 and started >= fixed, "preregistration before attempt")
    a.require(sample["outcome"] in ("exited", "launch-error", "timeout", "output-limit", "consumer-error", "cancelled", "telemetry-limit"), "outcome")
    a.require(sample["censored"] is (sample["outcome"] in ("timeout", "output-limit", "consumer-error", "cancelled", "telemetry-limit")), "censor accounting")
    a.require((sample["outcome"] == "launch-error" and sample["exitCode"] is None)
        or (sample["outcome"] != "launch-error" and type(sample["exitCode"]) is int), "exit accounting")
    a.require(sample["finalizationErrors"] == [], "completed finalization")
    retained = a.load(root / f"attempt-c{ci}-a{index}.private.json", 16*1024**2)
    a.require(a.wire(retained) == a.wire(dict(sample=sample, telemetry=counters)), "per-attempt record binding")
    payloads = []
    for channel in ("stdout", "stderr"):
        a.require(sample["captures"][channel] == f"captures/c{ci}-a{index}.{channel}", "capture position binding")
        data = a.bounded(root, sample["captures"][channel]).read_bytes()
        a.require(type(sample[channel+"Bytes"]) is int and type(sample[channel+"CapturedBytes"]) is int
            and len(data) == sample[channel+"CapturedBytes"] <= min(sample[channel+"Bytes"], 4194304), "capture byte accounting")
        a.require(sample[channel+"Sha256"] == (None if sample["outcome"] == "launch-error" else hashlib.sha256(data).hexdigest()), "capture digest")
        a.require(sample["outcome"] != "exited" or sample[channel+"Bytes"] == len(data), "exited capture completeness")
        payloads.append(data)
    return target, payloads


def evidence_namespace_check(root):
    captures = {f"c{ci}-a{index}.{channel}" for ci in range(4) for index in range(12)
        for channel in ("stdout", "stderr")}
    attempts = {f"attempt-c{ci}-a{index}.private.json" for ci in range(4) for index in range(12)}
    a.require({path.name for path in (root / "captures").iterdir()} == captures
        and all(path.is_file() for path in (root / "captures").iterdir()), "exact capture namespace")
    a.require({path.name for path in root.glob("attempt-c*-a*.private.json")} == attempts
        and all((root / name).is_file() for name in attempts), "exact attempt-record namespace")


def audit(root):
    root = Path(root).resolve()
    a.require(root.is_relative_to(a.ROOT / ".local"), "private run root")
    p, r = a.load(root / "protocol.private.json"), a.load(root / "record.private.json", 256*1024**2)
    a.require(r["protocolSha256"] == a.digest(root / "protocol.private.json"), "protocol binding")
    for path, digest in p["bindings"].items():
        a.require(a.digest(path) == digest, "tool/evidence binding")
    a.require(p["taskAdmission"] == {"ticket": 145, "scope": "private-stored-preview-resource-analysis",
        "sourceMutationAllowed": False, "reportPublicationAllowed": False, "decodingAllowed": False}, "private authority")
    a.require(a.digest(p["priorProtocol"]) == p["priorProtocolSha256"], "prior evidence")
    prior = a.load(p["priorProtocol"])
    a.require(p["fixture"] == prior["fixtureSet"][0], "admitted prefix fixture")
    a.require(a.digest(prior["priorProtocol"]) == prior["priorProtocolSha256"], "grant protocol binding")
    base = a.load(prior["priorProtocol"])
    for path, digest in base["evidenceSha256"].items():
        a.require(a.digest(path) == digest, "grant/admission evidence")
    admission = a.load(p["fixture"]["admission"])
    provenance = a.load(p["fixture"]["provenance"])
    a.require(admission["admission"] == "admitted" and admission["revision"] >= 2
        and admission["artifact"]["sha256"] == p["fixture"]["inputSha256"]
        and admission["media"]["captureMode"] == "full-raw" and admission["rights"]["analyze"] is True, "source admission")
    a.require(provenance["rights"]["permissions"]["analyze"] == provenance["rights"]["permissions"]["modify"] == "allowed"
        and a.load(base["privacyReview"])["publicClearance"] is False, "private derivative rights")
    source = Path(p["fixture"]["input"])
    a.require(r["status"] == "completed" and r["plannedAttempts"] == 48 and r["remainingAttempts"] == 0, "complete denominator")
    a.require(len(r["sourceChecks"]) == 5 and all(row == r["sourceChecks"][0] for row in r["sourceChecks"]), "unchanged source boundaries")
    a.require(identity(source) == r["sourceChecks"][0] and a.digest(source) == p["fixture"]["inputSha256"], "current source")
    a.require(len(r["cells"]) == 4 and p["warmups"] == 2 and p["repeats"] == 10, "fixed configuration")
    evidence_namespace_check(root)
    reports, names, known_targets, previous_end, previous_start = [], set(), set(), 0, None
    for ci, ((op, tag), cell) in enumerate(zip([("list", None)] + [("extract", t) for t in a.TAGS], r["cells"])):
        a.require((cell["operation"], cell["tag"]) == (op, tag) and len(cell["attempts"]) == len(cell["telemetry"]) == 12, "operation/attempt order")
        metrics, dispositions = [], []
        for index, (sample, counters) in enumerate(zip(cell["attempts"], cell["telemetry"])):
            target, (stdout, stderr) = attempt_check(root, p, ci, index, op, tag, sample, counters, previous_end)
            if target:
                known_targets.add(target.name)
            previous_end = sample["endOffsetNs"]
            current_start = datetime.fromisoformat(sample["startedUtc"])
            a.require(previous_start is None or previous_start <= current_start, "start timestamp order")
            previous_start = current_start
            correct = False
            try:
                document = a.decode(stdout)
                a.envelope_check(document, sample, source, target)
                a.require(sample["outcome"] == "exited" and not sample["censored"] and not stderr, "finished process")
                before, after = sample["namespaceBefore"], sample["namespaceAfter"]
                a.require(set(before) == names and set(after) == names | ({target.name} if target else set()), "namespace set")
                a.require(all(after[name] == row for name, row in before.items()), "earlier artifacts changed")
                if tag:
                    resource = next(row for row in p["resources"] if row["tag"] == tag)
                    a.require(identity(target) == after[target.name] and target.read_bytes() == Path(resource["reference"]).read_bytes(), "exact output bytes")
                else:
                    resource_check(document, source, p["resources"])
                correct = True
            except (ValueError, KeyError, TypeError, OSError):
                pass
            names = set(sample["namespaceAfter"])
            a.require(sample["correctness"] == ("pass" if correct else "fail") and sample["eligible"] == (index >= 2 and correct and counters["valid"]), "eligibility")
            probe = copy.deepcopy(sample)
            probe.update(index=0, phase="sample", eligible=False)
            disposition = {"passed": True, "reason": None}
            try:
                counters_audit({"schemaVersion": 2, "purpose": "metadata-read", "telemetry": [counters],
                    "elapsedRecord": {"attempts": [probe], "configuration": {"warmups": 0, "repeats": 1, "captureBytes": 4194304},
                    "status": "cancelled" if probe["outcome"] == "cancelled" else "completed", "sourceUnchanged": True, "binaryUnchanged": True}})
            except ValueError as error:
                disposition = {"passed": False, "reason": str(error)}
            dispositions.append(disposition)
            if sample["eligible"] and disposition["passed"]:
                row = dict(counters["samples"][-1]["values"], elapsedNs=sample["elapsedNs"],
                    stdoutBytes=sample["stdoutBytes"], stderrBytes=sample["stderrBytes"], observerWallNs=counters["observerWallNs"],
                    sampledWorkingSetBytes=counters["sampledMaxima"]["workingSetBytes"], sampledPrivateCommitBytes=counters["sampledMaxima"]["privateCommitBytes"],
                    finalOutputBytes=sample["namespaceAfter"].get(target.name, {}).get("bytes", 0) if target else 0,
                    inputStoredBytes=r["sourceChecks"][0]["bytes"],
                    observedTemporaryBoundaryBytes=sum(v["bytes"] for name, v in sample["namespaceAfter"].items()
                        if name not in known_targets) if all("bytes" in v for v in sample["namespaceAfter"].values()) else None,
                    retainedArtifactBytes=sum(v.get("bytes", 0) for v in sample["namespaceAfter"].values()))
                metrics.append(row)
        reports.append(dict(operation=op, tag=tag, attempts=12, eligible=len(metrics), resourceAudit=dispositions,
            failures=sum(s["correctness"] != "pass" for s in cell["attempts"]), censors=sum(s["censored"] for s in cell["attempts"]),
            metrics={key: {"count": len(values := [m[key] for m in metrics if m[key] is not None]),
            "min": min(values) if values else None, "median": statistics.median(values) if values else None,
            "max": max(values) if values else None, "mean": statistics.mean(values) if values else None} for key in metrics[0]} if metrics else {}))
    a.require({path.name for path in (root / "outputs").iterdir()} == names, "unrecorded namespace artifacts")
    return {"scope": "Private stored bytes; no decode, physical peak or device-I/O claim", "cells": reports}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", required=True)
    root = Path(parser.parse_args().run_root).resolve()
    result = audit(root)
    with (root / "audit.private.json").open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
