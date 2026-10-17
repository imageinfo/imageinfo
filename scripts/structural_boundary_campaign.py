"""Finite authored #149 process campaign; run only in a serialized frozen slot."""
import argparse
import json
import os
from pathlib import Path
import sys

import read_benchmark as shared
from read_telemetry import Observer


def sha(path):
    return shared.digest(path)


def collect(binary, corpus, output, repeats):
    binary, corpus, output = (Path(p).resolve() for p in (binary, corpus, output))
    if not 1 <= repeats <= 10:
        raise ValueError("repeats must be within 1..10")
    output.mkdir(exist_ok=False)
    manifest_path = corpus / "structural-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if len(manifest) != 15 or len({c["id"] for c in manifest}) != 15:
        raise ValueError("expected exact 15-cell authored corpus")
    record = {"schemaVersion": 1, "ticket": 149, "binary": str(binary),
              "binarySha256": sha(binary), "manifest": str(manifest_path),
              "manifestSha256": sha(manifest_path), "driverSha256": sha(__file__),
              "sharedDriverSha256": sha(shared.__file__), "pythonExecutable":sys.executable, "pythonSha256": sha(sys.executable),
              "telemetryDriverSha256": sha(Path(__file__).with_name("read_telemetry.py")),
              "scope": "authored default structural boundaries, fresh direct child; process lifetime and bounded pipe drain",
              "cache": "uncontrolled OS/device cache; fixture hash preflight warms bytes; no eviction",
              "environment": {"platform": sys.platform, "parallelism": "caller must supply exclusive measurement slot", "physicalIoBytes": None},
              "limits": {"timeoutMs": 10000, "captureBytesPerPipe": 4194304, "telemetryIntervalMs": 1},
              "repeats": repeats, "cases": [], "complete": False}
    env = {k: os.environ[k] for k in ("SystemRoot", "WINDIR", "PATH", "TEMP", "TMP") if k in os.environ}
    env.update({"LC_ALL": "C", "LANG": "C", "TZ": "UTC"})
    try:
        for cell in manifest:
            path = corpus / (cell["id"] + ".cr3")
            if sha(path) != cell["sha256"] or path.stat().st_size != cell["length"]:
                raise ValueError("corpus identity mismatch")
            before = path.stat()
            argv = [str(binary), "metadata", "read", "--tag", "Make", "--output", "json", "--", str(path)]
            case = {"id": cell["id"], "input": str(path), "inputSha256": cell["sha256"],
                    "expectation": cell, "argv": argv, "attempts": [], "sourceUnchanged": False}
            record["cases"].append(case)
            for i in range(repeats):
                observer = Observer(1)
                attempt, stdout, stderr = shared.run_process(argv, str(binary.parent), env, 10000, 4194304, observer)
                stem = f"{cell['id']}-{i}"
                (output / (stem + ".stdout")).write_bytes(stdout)
                (output / (stem + ".stderr")).write_bytes(stderr)
                attempt.update({"index": i, "stdoutFile": stem + ".stdout", "stderrFile": stem + ".stderr", "telemetry": observer.report()})
                case["attempts"].append(attempt)
                (output / "record.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            after = path.stat()
            case["sourceUnchanged"] = sha(path) == cell["sha256"] and (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
        record["complete"] = True
    finally:
        record["binaryUnchanged"] = sha(binary) == record["binarySha256"]
        (output / "record.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True)
    parser.add_argument("--corpus", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    collect(args.binary, args.corpus, args.output, args.repeats)


if __name__ == "__main__":
    main()
