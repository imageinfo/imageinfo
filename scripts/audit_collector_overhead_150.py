"""Independent fixed-denominator retained-output and statistics audit (#0150)."""
import argparse
import hashlib
import math
from pathlib import Path
import statistics
import re
import subprocess

from audit_read_resources_144 import load, require, canonical, wire
from audit_read_telemetry import audit as telemetry_audit
from qualify_batch_read import expected_envelope

ROOT = Path(__file__).resolve().parents[1]
TOOL_FILES = ("scripts/read_benchmark.py", "scripts/read_telemetry.py",
    "scripts/measure_collector_overhead_150.py", "scripts/audit_collector_overhead_150.py",
    "scripts/qualify_batch_read.py", "scripts/measure_batch_read.py",
    "scripts/audit_read_resources_144.py", "scripts/audit_read_telemetry.py",
    "docs/legacy-compatibility/native-read-json/example.v1.json", "tests/support/mod.rs")


def source_files():
    files = [ROOT / name for name in ("Cargo.toml", "Cargo.lock", "rust-toolchain.toml")]
    files += [path for directory in ("src", "crates") for path in (ROOT / directory).rglob("*")
              if path.is_file() and path.suffix in (".rs", ".toml", ".lock") and "target" not in path.parts]
    files += [path for path in (ROOT / ".cargo").rglob("*") if path.is_file()]
    if (ROOT / "build.rs").exists():
        files.append(ROOT / "build.rs")
    return sorted(str(path.resolve()) for path in files)


def binding_paths(root, p):
    return set([str(Path(p[k]).resolve()) for k in ("binary", "input")] +
        [str((root / name).resolve()) for name in ("fixture.rs", "expected.json")] +
        [str((ROOT / name).resolve()) for name in TOOL_FILES] + source_files())


def validate_bindings(root, p):
    require(isinstance(p.get("sourceRevision"), str) and
            re.fullmatch("[0-9a-f]{40}", p["sourceRevision"]) is not None, "exact source revision required")
    probe = subprocess.run(["git", "cat-file", "-t", p["sourceRevision"]], cwd=ROOT,
                           capture_output=True, timeout=10)
    require(probe.returncode == 0 and probe.stdout.strip() == b"commit", "source revision is not a commit")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                          capture_output=True, timeout=10).stdout.decode().strip()
    require(p["sourceRevision"] == head, "source revision differs from frozen HEAD")
    require(set(p["bindings"]) == binding_paths(root, p), "incomplete frozen inventory")
    require(p["sourceInventory"] == source_files(), "source inventory changed")
    for path, expected in p["bindings"].items():
        require(hashlib.sha256(Path(path).read_bytes()).hexdigest() == expected, "frozen binding changed")


def validate_sample(sample, capture_bytes):
    require(type(sample["elapsedNs"]) is int and sample["elapsedNs"] > 0, "invalid elapsed duration")
    outcome = sample["outcome"]
    require(outcome in {"exited", "launch-error", "timeout", "output-limit", "consumer-error", "cancelled", "telemetry-limit"},
            "unsupported sample outcome")
    require(type(sample["censored"]) is bool and sample["censored"] is
            (outcome in {"timeout", "output-limit", "consumer-error", "cancelled", "telemetry-limit"}), "censor mismatch")
    require(sample["exitCode"] is None if outcome == "launch-error" else type(sample["exitCode"]) is int,
            "invalid exit code")
    for channel in ("stdout", "stderr"):
        total, captured = sample[channel + "Bytes"], sample[channel + "CapturedBytes"]
        require(type(total) is int and type(captured) is int and 0 <= captured <= capture_bytes
                and total >= captured, "invalid byte counts")
        if outcome in {"exited", "launch-error"}:
            require(total == captured, "uncensored capture incomplete")


def distribution(values):
    if not values:
        return dict(count=0, medianNs=None, madNs=None, p95Ns=None, cv=None, windowDriftNs=None)
    median = statistics.median(values)
    mean = statistics.mean(values)
    return {"count": len(values), "medianNs": median,
        "madNs": statistics.median(abs(x - median) for x in values),
        "p95Ns": sorted(values)[math.ceil(.95 * len(values)) - 1],
        "cv": statistics.stdev(values) / mean if len(values) > 1 and mean > 0 else None,
        "windowDriftNs": statistics.median(values[-10:]) - statistics.median(values[:10])
                         if len(values) >= 20 else None}


def summarize(rows):
    """Failure/censor/missing measurements stay in denominator; no latency imputation."""
    reports = []
    for trial in range(3):
        arms = {}
        for arm in ("elapsed", "telemetry"):
            selected = [x for x in rows if x["round"] == trial and x["arm"] == arm and x["phase"] == "sample"]
            values = [x["sample"]["elapsedNs"] for x in selected if x["valid"]]
            arms[arm] = {"planned": 30, "attempted": len(selected), "missing": 30 - len(selected),
                "failed": sum(not x["valid"] for x in selected),
                "censored": sum(x["sample"]["censored"] for x in selected),
                "distribution": distribution(values), "driftRequiresCompleteSeries": True}
            if len(values) != 30:
                arms[arm]["distribution"]["windowDriftNs"] = None
        pairs = []
        for index in range(3, 33):
            pair = {x["arm"]: x for x in rows if x["round"] == trial and x["index"] == index}
            if len(pair) == 2 and all(x["valid"] for x in pair.values()):
                pairs.append(pair["telemetry"]["sample"]["elapsedNs"] - pair["elapsed"]["sample"]["elapsedNs"])
        paired = distribution(pairs)
        paired["cv"] = None  # Signed differences have no useful relative variability denominator.
        if len(pairs) != 30:
            paired["windowDriftNs"] = None
        reports.append({"round": trial, "arms": arms, "pairedTelemetryMinusElapsed": paired,
                        "pairedPlanned": 30, "pairedExcluded": 30 - len(pairs)})
    return reports


def audit(root):
    root = Path(root).resolve()
    p, r = load(root / "protocol.json"), load(root / "record.json")
    digest = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
    require(r["protocolSha256"] == digest(root / "protocol.json"), "protocol binding")
    require(p["revision"] == "collector-overhead-v1", "protocol revision")
    require(p["argv"] == [p["binary"], "metadata", "read", "--values", "all", "--output", "json",
            "--max-bytes", "8388608", "--", p["input"]], "workload changed")
    require((p["timeoutMs"], p["captureBytes"], p["sampleIntervalMs"]) == (30000, 4194304, 10),
            "collection configuration changed")
    require(r["status"] == "completed" and r["bindingsUnchanged"], "incomplete campaign")
    require(r["sourceBefore"] == r["sourceAfter"], "source identity boundary")
    validate_bindings(root, p)
    expected = canonical(expected_envelope())
    require(wire(expected) == wire(canonical(load(root / "expected.json"))), "authored oracle changed")
    require(len(r["attempts"]) == 198 and len(p["schedule"]) == 198, "fixed stopping")
    audited = []
    for n, row in enumerate(r["attempts"]):
        trial, within = divmod(n, 66)
        index, position = divmod(within, 2)
        first = "elapsed" if (trial + index) % 2 == 0 else "telemetry"
        arm = first if position == 0 else ("telemetry" if first == "elapsed" else "elapsed")
        cell = dict(round=trial, index=index, position=position, arm=arm,
                    phase="warmup" if index < 3 else "sample")
        require(all(row[k] == v for k, v in cell.items()) and p["schedule"][n] == cell,
                "paired counterbalance/order changed")
        require(row["ordinal"] == n and row == load(root / f"attempt-{n:03d}.json"), "attempt retention")
        sample = row["sample"]
        validate_sample(sample, p["captureBytes"])
        payloads = {}
        for channel in ("stdout", "stderr"):
            name = f"captures/{n:03d}.{channel}"
            require(row["captures"][channel] == name, "capture path")
            payloads[channel] = data = (root / name).read_bytes()
            require(len(data) == sample[channel + "CapturedBytes"], "capture length")
            expected_hash = hashlib.sha256(data).hexdigest()
            require(sample[channel + "Sha256"] == expected_hash or
                    (sample["outcome"] == "launch-error" and not data and sample[channel + "Sha256"] is None),
                    "capture hash")
        correct = False
        try:
            actual = load(root / row["captures"]["stdout"])
            correct = (sample["outcome"] == "exited" and sample["exitCode"] == 0
                and not sample["censored"] and not payloads["stderr"]
                and actual["files"][0]["path"] == p["input"] and wire(canonical(actual)) == wire(expected))
        except (ValueError, KeyError, TypeError, IndexError):
            pass
        require(row["correctness"] == correct, "correctness classification")
        counters_valid = True
        if arm == "telemetry":
            try:
                probe = dict(sample, index=0, phase="sample", eligible=False)
                telemetry_audit({"schemaVersion": 2, "purpose": "metadata-read", "telemetry": [row["telemetry"]],
                    "elapsedRecord": {"attempts": [probe], "configuration": {"warmups": 0, "repeats": 1,
                    "captureBytes": p["captureBytes"]}, "status": "completed", "sourceUnchanged": True,
                    "binaryUnchanged": True}})
                counters_valid = row["telemetry"]["valid"]
            except ValueError:
                counters_valid = False
        else:
            require(row["telemetry"] is None, "elapsed arm instrumented")
        audited.append(dict(row, valid=correct and counters_valid))
    return {"schemaVersion": 1, "attempted": 198, "warmups": 18, "measured": 180,
        "trials": summarize(audited), "allCorrect": all(x["correctness"] for x in audited),
        "allTelemetryValid": all(x["valid"] for x in audited if x["arm"] == "telemetry"),
        "limits": "success-conditional descriptive ns; failed/censored/missing retained; no subtraction, release gate or cross-host inference"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", required=True)
    args = parser.parse_args()
    import json
    root = Path(args.run_root)
    with (root / "audit.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(audit(root), stream, indent=2, allow_nan=False)
        stream.write("\n")
