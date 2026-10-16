"""Independent retained #0144 output/resource audit; private report only."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import statistics

from audit_read_telemetry import audit as resource_audit


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def load(path):
    data = Path(path).read_bytes()
    require(len(data) <= 256 * 1024**2, "audit input bound")
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON member")
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")))


def wire(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)


def canonical(value):
    value = copy.deepcopy(value)
    identity = value["requestId"]
    require(value["request"]["requestId"] == value["summary"]["requestId"] == identity, "envelope identities")
    value["requestId"] = value["request"]["requestId"] = value["summary"]["requestId"] = "request"
    for index, item in enumerate(value["files"]):
        require(item["requestId"] == identity and item["inputId"] == f"input-{index}", "file identity")
        item["requestId"], item["inputId"], item["path"] = "request", "input-0", "input"
        for issue in item["issues"]:
            if issue["inputId"] is not None:
                require(issue["inputId"] == f"input-{index}", "issue identity")
                issue["inputId"] = "input-0"
        snapshot = item["snapshot"]
        require(snapshot["id"] == f"{identity}-snapshot-{index}", "snapshot identity")
        snapshot["id"] = "snapshot"
        for source in snapshot["sources"]:
            source["displayPath"] = "input"
    return value


def oracle_file(fixture, selection, view):
    raw = load(fixture["oracle"])
    item = canonical(raw)["files"][0]
    snapshot = item["snapshot"]
    selected = snapshot["occurrences"]
    if selection == "EXIF:ISO":
        selected = [o for o in selected if (o["tag"]["namespace"], o["tag"]["name"]) == ("exif", "ISO")]
        allowed_resources = {o["origin"]["resourceRef"] for o in selected}
        snapshot["resources"] = [r for r in snapshot["resources"]
            if r["id"][:6] != "value-" or r["id"] in allowed_resources]
        allowed_issues = {ref for o in selected for ref in o["issueRefs"]}
        snapshot["issues"] = [i for i in snapshot["issues"] if i["id"] in allowed_issues]
    snapshot["occurrences"] = selected
    if view == "raw":
        for o in selected:
            o["values"]["display"] = dict(state="unavailable", reason="Not requested")
    return item


def distribution(values):
    return {"count": len(values), "min": min(values) if values else None,
            "median": statistics.median(values) if values else None,
            "max": max(values) if values else None,
            "mean": statistics.mean(values) if values else None}


def audit(root):
    root = Path(root).resolve()
    p, r = load(root / "protocol.private.json"), load(root / "record.private.json")
    digest = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
    require(r["protocolSha256"] == digest(root / "protocol.private.json"), "protocol binding")
    for path, expected in p["bindings"].items():
        require(digest(path) == expected, "tool/build binding")
    require(r["status"] == "completed" and r["binaryUnchanged"], "incomplete run")
    require(len(r["sourceChecks"]) == 13 and all(x == r["sourceChecks"][0] for x in r["sourceChecks"]), "source boundaries")
    require(len(r["cells"]) == len(p["grid"]) == 12, "grid count")
    reports = []
    for number, (cell, grid) in enumerate(zip(r["cells"], p["grid"])):
        selection, view, shape = grid
        require([cell["selection"], cell["view"], cell["shape"]] == grid, "grid order")
        fixtures = p["fixtureSet"][:4 if shape == "four" else 1]
        expected = canonical(load(fixtures[0]["oracle"]))
        expected["files"] = [oracle_file(f, selection, view) for f in fixtures]
        expected["summary"]["counts"] = {"discovered": len(fixtures), "excluded": 0,
            "deduplicated": 3 if shape == "duplicate" else 0, "byState": {"read": len(fixtures)}}
        require(wire(expected) == wire(load(root / f"expected-{number}.private.json")), "independent oracle projection")
        require(len(cell["attempts"]) == len(cell["telemetry"]) == 12, "attempt count")
        for sample, counters in zip(cell["attempts"], cell["telemetry"]):
            payloads = {}
            for channel in ("stdout", "stderr"):
                path = root / sample["captures"][channel]
                require(path.is_relative_to(root / "captures"), "capture path")
                data = path.read_bytes()
                require(len(data) == sample[channel + "CapturedBytes"] and hashlib.sha256(data).hexdigest() == sample[channel + "Sha256"], "capture identity")
                payloads[channel] = data
            correct = False
            try:
                actual = load(root / sample["captures"]["stdout"])
                require([f["path"] for f in actual["files"]] == [f["input"] for f in fixtures], "operand binding")
                correct = sample["outcome"] == "exited" and sample["exitCode"] == 0 and not payloads["stderr"] and wire(canonical(actual)) == wire(expected)
            except (ValueError, KeyError, TypeError):
                pass
            require(sample["correctness"] == ("pass" if correct else "fail"), "correctness classification")
            require(sample["eligible"] == (sample["index"] >= 2 and correct and counters["valid"]), "eligibility")
        # Audit every retained attempt independently. A counter inconsistency is
        # retained as an audit rejection, never erased or substituted with zero.
        resource_checks = []
        for a, t in zip(cell["attempts"], cell["telemetry"]):
            probe = dict(a, index=0, phase="sample", eligible=False)
            try:
                resource_audit({"schemaVersion": 2, "purpose": "metadata-read", "telemetry": [t],
                    "elapsedRecord": {"attempts": [probe], "configuration": {"warmups": 0, "repeats": 1, "captureBytes": 4194304},
                    "status": "cancelled" if probe["outcome"] == "cancelled" else "completed",
                    "sourceUnchanged": True, "binaryUnchanged": True}})
                resource_checks.append({"passed": True, "reason": None})
            except ValueError as error:
                resource_checks.append({"passed": False, "reason": str(error)})
        rows = []
        for a, t, check in zip(cell["attempts"], cell["telemetry"], resource_checks):
            if a["eligible"] and check["passed"]:
                row = dict(t["samples"][-1]["values"])
                row.update(elapsedNs=a["elapsedNs"], stdoutBytes=a["stdoutBytes"], stderrBytes=a["stderrBytes"],
                    sampledWorkingSetBytes=t["sampledMaxima"]["workingSetBytes"], sampledPrivateCommitBytes=t["sampledMaxima"]["privateCommitBytes"], observerWallNs=t["observerWallNs"])
                rows.append(row)
        reports.append({"grid": grid, "attempted": 12, "eligible": len(rows),
            "operandSlots": cell["operandSlots"] * 12, "physicalFileSlots": len(fixtures) * 12,
            "metrics": {k: distribution([x[k] for x in rows if x[k] is not None]) for k in rows[0]} if rows else {},
            "failures": sum(a["correctness"] != "pass" for a in cell["attempts"]),
            "censors": sum(a["censored"] for a in cell["attempts"]), "resourceAudit": resource_checks})
    return {"scope": "Private descriptive complete-batch resource observations; no per-file latency or policy recommendation", "cells": reports}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", required=True)
    args = parser.parse_args()
    root = Path(args.run_root).resolve()
    require(".local" in root.parts, "private report root")
    result = audit(root)
    with (root / "audit.private.json").open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
