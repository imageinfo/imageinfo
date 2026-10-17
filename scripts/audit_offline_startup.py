"""Read-only independent audit of retained offline startup captures.

Imports no collector or counter implementation. Hashes bind retained observations;
they do not authenticate arbitrary imported records or prove cold caches.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import statistics
import subprocess

CASES = (("root-help", ["help"]),
         ("metadata-read-help", ["metadata", "read", "help"]),
         ("session-read-help", ["session", "read", "help"]),
         ("version-text", ["--version"]),
         ("version-json", ["--version", "--output", "json"]))
GROUPS = {"cpu": ("userCpuNs", "systemCpuNs"),
          "memory": ("workingSetBytes", "peakWorkingSetBytes", "privateCommitBytes"),
          "logicalIo": ("readOperations", "writeOperations", "otherOperations",
                        "readTransferBytes", "writeTransferBytes", "otherTransferBytes")}
METRICS = set(sum(GROUPS.values(), ())) | {"physicalIoBytes"}
CUMULATIVE = METRICS - {"workingSetBytes", "privateCommitBytes", "physicalIoBytes"}
CENSORED = {"timeout", "output-limit", "consumer-error", "cancelled", "telemetry-limit"}
ROOT = Path(__file__).resolve().parents[1]
TOOLS = ("scripts/measure_offline_startup.py", "scripts/audit_offline_startup.py",
         "scripts/test_offline_startup.py", "scripts/read_benchmark.py", "scripts/read_telemetry.py",
         "scripts/audit_read_telemetry.py", "docs/performance/offline-startup.md")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def load(path, limit=32 * 1024 * 1024):
    with Path(path).open("rb") as stream:
        raw = stream.read(limit + 1)
    require(len(raw) <= limit, "record too large")
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


def capture(path):
    with Path(path).open("rb") as stream:
        data = stream.read(1048577)
    require(len(data) <= 1048576, "capture exceeds retained bound")
    return data


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def retained(root, relative):
    require(isinstance(relative, str) and relative, "missing retained path")
    path = Path(relative)
    require(not path.is_absolute() and ".." not in path.parts, "retained path escapes root")
    resolved = (root / path).resolve()
    require(resolved.is_relative_to(root.resolve()), "retained symlink escapes root")
    return resolved


def integer(value):
    return type(value) is int and value >= 0


def oracle(root, expected_version="0.2.0-alpha.1", expected_revision="2026-10-12.1"):
    names = {"manifest.json"} | {name + suffix for name, _ in CASES for suffix in (".stdout", ".stderr")}
    require({str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()} == names, "oracle namespace")
    manifest = load(root / "manifest.json")
    require(type(manifest["schemaVersion"]) is int and manifest["schemaVersion"] == 1, "oracle version")
    require([(x["id"], x["argv"]) for x in manifest["cases"]] == list(CASES), "oracle case identities")
    outputs = {}
    for entry in manifest["cases"]:
        name = entry["id"]
        require(entry["stdout"] == name + ".stdout" and entry["stderr"] == name + ".stderr", "oracle channel identity")
        stdout = capture(retained(root, entry["stdout"]))
        stderr = capture(retained(root, entry["stderr"]))
        require(type(entry["exitCode"]) is int and entry["exitCode"] == 0 and not stderr and stdout.endswith(b"\n"), "oracle status/channel")
        require(b"\x1b" not in stdout and b"\r" not in stdout, "oracle plain canonical LF")
        text = stdout.decode("utf-8", errors="strict")
        if name.endswith("help"):
            usage, description, tail = {
                "root-help": ("Usage: imageinfo [OPTIONS] [COMMAND]", "Camera RAW metadata tooling",
                              "metadata writes are not supported yet."),
                "metadata-read-help": ("Usage: imageinfo metadata read [OPTIONS] [INPUT]...",
                                       "Read the declared R5 metadata subset", "--tag selects every matching implemented occurrence."),
                "session-read-help": ("Usage: imageinfo session read [OPTIONS]",
                                      "Read metadata requests from stdin using session protocol v1",
                                      "No queue, cancellation, metadata writes or elapsed-time guarantee.")}[name]
            require(text.startswith(description + "\n\n") and usage in text and tail in text,
                    "oracle help identity")
            require(all(option in text for option in ("--help", "--version", "--output", "--color",
                                                       "--no-interactive", "--interactive")), "oracle common options")
            require("session-ready" not in text, "help entered session")
            if name == "root-help":
                require(all("  " + command in text for command in
                            ("help", "compat", "version", "session", "metadata", "binary", "preview", "sidecar")),
                        "root commands")
            if name == "metadata-read-help":
                require(all(token in text for token in ("--tag", "--values", "--max-bytes", "--max-preview-bytes")),
                        "metadata help options")
        elif name == "version-text":
            require(text == f"imageinfo {expected_version}\nCanon EOS R5 full RAW metadata/preview slice; coverage is partial.\n",
                    "version text identity")
        else:
            expected = {"schemaVersion": 1, "kind": "version", "version": expected_version,
                        "capabilityDataRevision": expected_revision, "mediaReadingImplemented": True}
            actual = json.loads(text, object_pairs_hook=unique)
            require(json.dumps(actual, sort_keys=True) == json.dumps(expected, sort_keys=True), "version JSON identity")
            require(type(json.loads(text)["schemaVersion"]) is int, "version schema integer")
        outputs[name] = (stdout, stderr, entry["exitCode"])
    return outputs


def telemetry(record, elapsed, exit_ns):
    """Audit actual bracketed endpoints; never replace a failed endpoint with zero."""
    samples = record["samples"]
    require(record["maxSamples"] == 2048 and len(samples) <= 2048, "counter sample bound")
    require(record["requestedIntervalMs"] == 10, "counter interval")
    require(record["membership"] in {"unavailable", "direct-only-observed", "invalid-descendants"}, "counter membership")
    require(isinstance(record["errors"], list) and all(isinstance(e, str) and e for e in record["errors"]), "counter setup errors")
    require(not samples or type(record["pid"]) is int and record["pid"] > 0, "direct child PID")
    require(bool(samples) or bool(record["errors"]), "missing counters without reason")
    require(record["observedDescendantPids"] == sorted(set(record["observedDescendantPids"])), "descendant identities")
    require(not record["observedDescendantPids"] or record["membership"] == "invalid-descendants", "descendant membership")
    total, last, previous = 0, -1, {}
    for position, sample in enumerate(samples):
        begin, end = sample["beginOffsetNs"], sample["endOffsetNs"]
        require(integer(begin) and integer(end) and last <= begin <= end <= elapsed, "counter timing")
        last = end
        total += end - begin
        require(type(sample["final"]) is bool and sample["final"] == (position == len(samples) - 1), "counter final endpoint")
        if sample["final"]:
            require(exit_ns is not None and begin >= exit_ns, "final sample precedes observed exit")
        values, errors = sample["values"], sample["errors"]
        require(set(values) == METRICS and isinstance(errors, dict), "counter metric set")
        require(values["physicalIoBytes"] is None and bool(errors.get("physicalIoBytes")), "fabricated physical I/O")
        for group, names in GROUPS.items():
            failed = group in errors or "counterRead" in errors
            require(all(values[n] is None for n in names) if failed else all(integer(values[n]) for n in names),
                    "counter failure/value mismatch")
        require(all(isinstance(v, str) and bool(v) for v in errors.values()), "counter error reason")
        for name in CUMULATIVE:
            if values[name] is not None:
                require(values[name] >= previous.get(name, 0), "counter decreased")
                previous[name] = values[name]
        if values["workingSetBytes"] is not None:
            require(values["workingSetBytes"] <= values["peakWorkingSetBytes"], "RSS exceeds high water")
    require(integer(record["observerWallNs"]) and total == record["observerWallNs"], "observer arithmetic")
    for name in ("workingSetBytes", "privateCommitBytes"):
        maximum = max((s["values"][name] for s in samples if s["values"][name] is not None), default=None)
        require(record["sampledMaxima"][name] == maximum, "sampled memory maximum")
    valid = bool(samples) and record["membership"] == "direct-only-observed" and not record["errors"] \
        and record["stopReason"] is None and all(not (set(s["errors"]) - {"physicalIoBytes"}) for s in samples)
    require(type(record["valid"]) is bool and record["valid"] == valid, "counter validity")
    return valid


def timing(sample):
    elapsed = sample["elapsedNs"]
    require(integer(elapsed) and elapsed > 0, "elapsed duration")
    fields = ("firstStdoutByteNs", "firstStderrByteNs", "firstByteNs", "stdoutEofNs", "stderrEofNs",
              "completeOutputNs", "exitObservedNs", "completeOutputExitNs")
    require(all(sample[k] is None or integer(sample[k]) and sample[k] <= elapsed for k in fields), "endpoint range")
    first = []
    for channel in ("stdout", "stderr"):
        begin, end = sample["first" + channel.title() + "ByteNs"], sample[channel + "EofNs"]
        require((sample[channel + "Bytes"] > 0) == (begin is not None), "first-byte presence")
        if begin is not None:
            first.append(begin)
            require(end is None or begin <= end, "first byte after EOF")
    require(sample["firstByteNs"] == (min(first) if first else None), "first-byte minimum")
    eof = [sample[k] for k in ("stdoutEofNs", "stderrEofNs")]
    complete = max(eof) if all(x is not None for x in eof) else None
    require(sample["completeOutputNs"] == complete, "complete output endpoint")
    exit_ns = sample["exitObservedNs"]
    require(sample["completeOutputExitNs"] == (max(complete, exit_ns)
            if complete is not None and exit_ns is not None else None), "combined output/exit endpoint")
    if sample["outcome"] == "exited":
        require(complete is not None and exit_ns is not None, "successful endpoints missing")
    if sample["outcome"] == "launch-error":
        require(all(sample[k] is None for k in fields), "launch failure fabricated endpoint")


def source_inventory(repo):
    files = {repo / name for name in ("Cargo.toml", "Cargo.lock", "rust-toolchain.toml")}
    for directory in ("src", "crates"):
        source_root = repo / directory
        # Embedded data (include_str!/include_bytes!) is a build input too.
        # Inventory every production-tree file instead of guessing extensions.
        files.update(p for p in source_root.rglob("*") if p.is_file()
                     and "target" not in p.relative_to(source_root).parts)
    files.update(p for p in (repo / ".cargo").rglob("*") if p.is_file())
    if (repo / "build.rs").exists():
        files.add(repo / "build.rs")
    return sorted(str(p.resolve()) for p in files)


def distribution(values):
    return {"count": len(values), "min": min(values) if values else None,
            "median": statistics.median(values) if values else None,
            "max": max(values) if values else None}


def summaries(attempts):
    """Finite descriptive observations only, with explicit success-conditional pools."""
    result = {}
    time_fields = ("firstByteNs", "completeOutputNs", "exitObservedNs", "completeOutputExitNs", "elapsedNs")
    resource_fields = tuple(sorted(METRICS - {"physicalIoBytes", "workingSetBytes", "privateCommitBytes"}))
    for case, _ in CASES:
        rows = [r for r in attempts if r["case"] == case and r["phase"] == "sample"]
        output_rows = [r for r in rows if r["correctness"]]
        resource_rows = [r for r in output_rows if r["telemetry"]["valid"]]
        endpoints = {metric: distribution([r["telemetry"]["samples"][-1]["values"][metric]
                                          for r in resource_rows]) for metric in resource_fields}
        for metric in ("workingSetBytes", "privateCommitBytes"):
            endpoints["sampledMax-" + metric] = distribution([r["telemetry"]["sampledMaxima"][metric]
                                                            for r in resource_rows])
        result[case] = {"planned": 10, "retained": len(rows), "missing": 10 - len(rows),
                        "failedOutput": sum(not r["correctness"] for r in rows),
                        "censored": sum(r["sample"]["censored"] for r in rows),
                        "resourceUnavailableOrInvalid": sum(not r["telemetry"]["valid"] for r in rows),
                        "outputCorrectTimingsNs": {k: distribution([r["sample"][k] for r in output_rows
                                                                    if r["sample"][k] is not None]) for k in time_fields},
                        "outputCorrectAndResourceValidCounters": endpoints}
    return result


def audit(root, repo=ROOT, source_revision=None):
    root, repo = Path(root).resolve(), Path(repo).resolve()
    protocol, record = load(root / "protocol.json"), load(root / "record.json", 256 * 1024 * 1024)
    require(type(protocol["schemaVersion"]) is int and type(record["schemaVersion"]) is int
            and protocol["schemaVersion"] == record["schemaVersion"] == 1, "record schema")
    require(protocol["revision"] == "offline-startup-v1", "protocol revision")
    require(record["protocolSha256"] == sha(root / "protocol.json"), "protocol identity")
    require(isinstance(protocol["sourceRevision"], str) and re.fullmatch("[0-9a-f]{40}", protocol["sourceRevision"]), "source revision syntax")
    if source_revision is None:
        source_revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True,
                                         capture_output=True, timeout=10).stdout.decode("ascii").strip()
    require(protocol["sourceRevision"] == source_revision, "source revision")
    require(protocol["sourceInventory"] == source_inventory(repo), "source inventory")
    expected_paths = set(protocol["sourceInventory"])
    expected_paths.update(str((repo / p).resolve()) for p in TOOLS)
    expected_paths.update(str(Path(protocol[k]).resolve()) for k in ("binary", "pythonExecutable"))
    expected_paths.update(str(p.resolve()) for p in (root / "oracle").rglob("*") if p.is_file())
    require(set(protocol["bindings"]) == expected_paths, "binding inventory")
    require(all(Path(p).is_absolute() and sha(p) == digest for p, digest in protocol["bindings"].items()), "frozen artifact changed")
    require([(x["id"], x["argv"]) for x in protocol["cases"]] == list(CASES), "fixed cases")
    schedule = [{"case": case, "index": index, "phase": "warmup" if index < 3 else "sample"}
                for case, _ in CASES for index in range(13)]
    require(protocol["schedule"] == schedule, "fixed denominator/order")
    require((protocol["timeoutMs"], protocol["captureBytes"], protocol["sampleIntervalMs"]) == (10000, 1048576, 10), "fixed limits")
    require(protocol["unsupported"] == [{"id": "format-discovery", "status": "unsupported-unrun"},
                                        {"id": "tag-discovery", "status": "unsupported-unrun"}], "unsupported discovery matrix")
    outputs = oracle(root / "oracle")
    attempts = record["attempts"]
    require(len(attempts) <= 65, "excess attempts/retry")
    require(record["status"] in {"completed", "aborted", "cancelled"}, "campaign status")
    require(record["status"] != "completed" or len(attempts) == 65 and record.get("bindingsUnchanged") is True,
            "incomplete campaign marked complete")
    require(record["environment"].get("LC_ALL") == "C" and record["environment"].get("LANG") == "C"
            and record["environment"].get("TZ") == "UTC", "environment")
    expected_names = {"protocol.json", "record.json"}
    expected_names.update("oracle/" + p.name for p in (root / "oracle").iterdir() if p.is_file())
    correct_count, resource_count, measured = 0, 0, 0
    cases = {name: {"warmups": 0, "samples": 0, "correctSamples": 0, "resourceSamples": 0} for name, _ in CASES}
    for ordinal, row in enumerate(attempts):
        require(type(row["ordinal"]) is int and type(row["index"]) is int and row["ordinal"] == ordinal
                and all(row[k] == v for k, v in schedule[ordinal].items()), "attempt order")
        expected_names.add(f"attempt-{ordinal:03d}.json")
        require(load(root / f"attempt-{ordinal:03d}.json") == row, "attempt copy identity")
        sample = row["sample"]
        require(sample["outcome"] in {"exited", "launch-error"} | CENSORED, "unknown outcome")
        require(sample["exitCode"] is None if sample["outcome"] == "launch-error"
                else type(sample["exitCode"]) is int, "exit status type")
        require(type(sample["censored"]) is bool and sample["censored"] == (sample["outcome"] in CENSORED), "censor status")
        actual = []
        for channel in ("stdout", "stderr"):
            name = f"captures/{ordinal:03d}.{channel}"
            require(row["captures"][channel] == name, "capture namespace")
            expected_names.add(name)
            data = capture(retained(root, name))
            actual.append(data)
            require(integer(sample[channel + "Bytes"]) and integer(sample[channel + "CapturedBytes"])
                    and len(data) == sample[channel + "CapturedBytes"]
                    and len(data) <= min(sample[channel + "Bytes"], protocol["captureBytes"]), "capture length")
            digest = hashlib.sha256(data).hexdigest()
            require(sample[channel + "Sha256"] == (None if sample["outcome"] == "launch-error" else digest), "capture identity")
        timing(sample)
        resource = telemetry(row["telemetry"], sample["elapsedNs"], sample["exitObservedNs"])
        expected = outputs[row["case"]]
        correct = sample["outcome"] == "exited" and sample["exitCode"] == expected[2] \
            and not sample["censored"] and tuple(actual) == expected[:2]
        require(type(row["correctness"]) is bool and row["correctness"] == correct, "collector correctness contradicted by retained bytes/status")
        correct_count += correct
        resource_count += resource
        summary = cases[row["case"]]
        summary["warmups" if row["phase"] == "warmup" else "samples"] += 1
        if row["phase"] == "sample":
            measured += 1
            summary["correctSamples"] += correct
            summary["resourceSamples"] += resource
    actual_names = {str(p.relative_to(root)).replace("\\", "/") for p in root.rglob("*") if p.is_file()}
    require(actual_names == expected_names, "unexpected/missing retained namespace entries")
    complete = len(attempts) == 65 and record["status"] == "completed"
    return {"verdict": "pass" if complete and correct_count == resource_count == 65 else "incomplete-or-failed",
            "attempts": len(attempts), "requiredAttempts": 65, "missingAttempts": 65 - len(attempts),
            "measuredAttempts": measured, "outputCorrect": correct_count, "resourceValid": resource_count,
            "censored": sum(r["sample"]["censored"] for r in attempts), "cases": cases,
            "descriptive": summaries(attempts),
            "limits": "retained identity/consistency; source-reviewed shared-implementation oracle; uncontrolled caches; direct-process logical I/O"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--source-revision")
    args = parser.parse_args()
    result = audit(args.run_root, source_revision=args.source_revision)
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if result["verdict"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
