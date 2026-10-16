"""Fixed #0144 private resource grid; camera evidence never leaves .local."""
import argparse
import copy
import json
import os
from pathlib import Path
import platform
import sys
from datetime import datetime, timezone

import measure_batch_read as batch
import read_benchmark as b
import read_telemetry as telemetry

REVISION = "98a658e1857ee7f220c6c11bc87f5dd83499dd9d"
GRID = [(selection, view, shape) for selection in ("EXIF:ISO", "full")
        for view in ("raw", "all") for shape in ("one", "four", "duplicate")]


def save(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def project(oracle, selection, view):
    """Project prior all-values oracle; preserve every unselected structure."""
    result = copy.deepcopy(oracle)
    for item in result["files"]:
        snapshot = item["snapshot"]
        if selection != "full":
            snapshot["occurrences"] = [o for o in snapshot["occurrences"]
                if o["tag"]["namespace"] == "exif" and o["tag"]["name"] == "ISO"]
            keep = {o["origin"]["resourceRef"] for o in snapshot["occurrences"]}
            snapshot["resources"] = [r for r in snapshot["resources"]
                if not r["id"].startswith("value-") or r["id"] in keep]
            issues = {i for o in snapshot["occurrences"] for i in o["issueRefs"]}
            snapshot["issues"] = [i for i in snapshot["issues"] if i["id"] in issues]
        if view == "raw":
            for occurrence in snapshot["occurrences"]:
                occurrence["values"]["display"] = {"state": "unavailable", "reason": "Not requested"}
    return result


def expected_envelope(fixtures, selection, view, duplicate):
    oracles = [project(b.load(f["oracle"], b.MAX_CAPTURE_BYTES), selection, view) for f in fixtures]
    result = batch.normalized_envelope(oracles[0])
    result["files"] = [batch.normalized_file(o["files"][0]) for o in oracles]
    result["summary"]["counts"] = {"discovered": len(fixtures), "excluded": 0,
        "deduplicated": 3 if duplicate else 0, "byState": {"read": len(fixtures)}}
    return result


def rights(p):
    batch.require(p["taskAdmission"] == {"ticket": 144, "scope": "private-read-only-resource-analysis",
        "sourceMutationAllowed": False, "reportPublicationAllowed": False}, "task admission")
    batch.require(b.digest(p["priorProtocol"]) == p["priorProtocolSha256"], "prior evidence changed")
    prior = b.load(p["priorProtocol"])
    batch.rights_before_media(prior)
    batch.require(p["fixtureSet"] == prior["fixtureSet"][:4], "fixed admitted prefix")
    for fixture in p["fixtureSet"]:
        batch.require(b.digest(fixture["oracle"]) == fixture["oracleSha256"], "oracle changed")
    for path, digest in p["bindings"].items():
        batch.require(b.digest(path) == digest, "tool/build binding changed")


def source_check(p):
    rights(p)  # Rights/evidence rechecked before every media hashing boundary.
    rows = []
    for f in p["fixtureSet"]:
        stat = Path(f["input"]).stat()
        batch.require(stat.st_size <= 1024**3, "source bound")
        row = {"sha256": b.digest(f["input"]), "bytes": stat.st_size,
               "mtimeNs": stat.st_mtime_ns, "device": stat.st_dev, "inode": stat.st_ino}
        batch.require(row["sha256"] == f["inputSha256"], "source hash changed")
        rows.append(row)
    batch.require(len({(r["device"], r["inode"]) for r in rows}) == 4, "distinct physical sources required")
    return rows


def collect(root):
    root = Path(root).resolve()
    batch.require(root.is_relative_to(batch.ROOT / ".local"), "private root required")
    p = b.load(root / "protocol.private.json")
    batch.require(p["revision"] == REVISION and p["grid"] == [list(x) for x in GRID]
                  and p["warmups"] == 2 and p["repeats"] == 10, "fixed protocol")
    rights(p)
    captures = root / "captures"
    captures.mkdir()
    env = {k: os.environ[k] for k in ("SystemRoot", "WINDIR", "PATH", "TEMP", "TMP") if k in os.environ}
    env.update(LC_ALL="C", LANG="C", TZ="UTC")
    record = {"protocolSha256": b.digest(root / "protocol.private.json"), "status": "aborted",
        "environment": env, "host": {"system": platform.system(), "version": platform.version(),
        "machine": platform.machine()}, "pythonVersion": platform.python_version(),
        "cells": [], "sourceChecks": [], "binaryUnchanged": False}
    try:
        initial = source_check(p)
        record["sourceChecks"].append(initial)
        for cell_index, (selection, view, shape) in enumerate(GRID):
            fixtures = p["fixtureSet"][:4 if shape == "four" else 1]
            operands = [f["input"] for f in fixtures]
            if shape == "duplicate":
                operands *= 4
            expected = expected_envelope(fixtures, selection, view, shape == "duplicate")
            save(root / f"expected-{cell_index}.private.json", expected)
            argv = [p["binary"], "metadata", "read", "--values", view, "--output", "json",
                    "--max-bytes", "8388608"]
            if selection != "full":
                argv += ["--tag", selection]
            argv += ["--", *operands]
            cell = {"selection": selection, "view": view, "shape": shape, "argv": argv,
                    "operandSlots": len(operands), "physicalFiles": len(fixtures), "attempts": [], "telemetry": []}
            record["cells"].append(cell)
            for index in range(12):
                observer = telemetry.Observer(10)
                sample, stdout, stderr = b.run_process(argv, str(Path(p["binary"]).parent), env,
                                                       30000, 4194304, observer)
                correct = False
                try:
                    actual = batch.strict_json(stdout)
                    batch.require([f["path"] for f in actual["files"]] == [f["input"] for f in fixtures], "path binding")
                    correct = (sample["outcome"] == "exited" and sample["exitCode"] == 0 and not stderr
                        and batch.wire(batch.normalized_envelope(actual)) == batch.wire(expected))
                except (ValueError, KeyError, IndexError, TypeError):
                    pass
                paths = {}
                for channel, data in (("stdout", stdout), ("stderr", stderr)):
                    name = f"captures/c{cell_index}-a{index}.{channel}"
                    (root / name).write_bytes(data)
                    paths[channel] = name
                report = observer.report()
                sample.update(index=index, phase="warmup" if index < 2 else "sample",
                    correctness="pass" if correct else "fail", eligible=index >= 2 and correct and report["valid"],
                    captures=paths)
                cell["attempts"].append(sample)
                cell["telemetry"].append(report)
                save(root / f"attempt-c{cell_index}-a{index}.private.json", {"sample": sample, "telemetry": report})
            after = source_check(p)
            record["sourceChecks"].append(after)
            batch.require(after == initial, "source stat/identity changed")
        record["binaryUnchanged"] = b.digest(p["binary"]) == p["bindings"][p["binary"]]
        batch.require(record["binaryUnchanged"], "binary changed")
        record["status"] = "completed"
    finally:
        if record["status"] != "completed":
            for cell in record["cells"]:
                for attempt in cell["attempts"]:
                    attempt["eligible"] = False
        record["recordedUtc"] = datetime.now(timezone.utc).isoformat()
        save(root / "record.private.json", record)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", required=True)
    collect(parser.parse_args().run_root)
