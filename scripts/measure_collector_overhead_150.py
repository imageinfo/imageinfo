"""Fixed authored paired elapsed-only/telemetry experiment (#0150)."""
import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
from datetime import datetime, timezone

import read_benchmark as b
import read_telemetry as telemetry
import qualify_batch_read as authored
from audit_read_resources_144 import canonical, wire
from audit_collector_overhead_150 import binding_paths, source_files, validate_bindings

ROOT = Path(__file__).resolve().parents[1]
REVISION = "collector-overhead-v1"


def save(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def schedule():
    return [{"round": r, "index": i, "phase": "warmup" if i < 3 else "sample",
             "arm": arm, "position": position}
            for r in range(3) for i in range(33)
            for position, arm in enumerate(("elapsed", "telemetry") if (r + i) % 2 == 0
                                           else ("telemetry", "elapsed"))]


def prepare(root, binary, revision):
    root, binary = Path(root).resolve(), Path(binary).resolve()
    if not root.is_relative_to(ROOT / ".local"):
        raise ValueError("private collection root required")
    current = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                             capture_output=True, timeout=10).stdout.decode().strip()
    if revision != current:
        raise ValueError("source revision must be the exact current HEAD; source inventory separately binds working tree")
    root.mkdir()
    helper = json.dumps((ROOT / "tests/support/mod.rs").as_posix())
    source = root / "fixture.rs"
    source.write_text(f'#[allow(dead_code)] #[path={helper}] mod support;\n'
        'fn main(){std::fs::write(std::env::args_os().nth(1).unwrap(),support::fixture().bytes).unwrap();}\n',
        encoding="utf-8", newline="\n")
    generator = root / "fixture.exe"
    subprocess.run(["rustc", "--edition=2024", str(source), "-o", str(generator)],
                   check=True, capture_output=True, timeout=60)
    fixture = root / "authored.cr3"
    subprocess.run([str(generator), str(fixture)], check=True, timeout=10)
    save(root / "expected.json", authored.expected_envelope())
    paths = binding_paths(root, {"binary": str(binary), "input": str(fixture)})
    save(root / "protocol.json", {"revision": REVISION, "sourceRevision": revision,
        "fixedUtc": datetime.now(timezone.utc).isoformat(), "fixtureKind": "authored-structural",
        "binary": str(binary), "input": str(fixture), "bindings": {str(p): b.digest(p) for p in sorted(paths)},
        "sourceInventory": source_files(),
        "schedule": schedule(), "timeoutMs": 30000, "captureBytes": 4194304,
        "sampleIntervalMs": 10, "argv": [str(binary), "metadata", "read", "--values", "all",
        "--output", "json", "--max-bytes", "8388608", "--", str(fixture)],
        "conditions": {"cache": "application fresh; preflight hashes expose warm OS cache; OS/device uncontrolled",
        "consumer": "same shared concurrent 4096-byte bounded stdout/stderr drain; correctness outside timing",
        "storage": "same local C: volume; physical topology unknown", "background": "shared developer workstation; uncontrolled",
        "power": "unchanged inherited host; not controlled", "host": platform.platform()},
        "stopping": "198 attempts; no retries, trimming or adaptive stopping; retain failures and censoring",
        "interpretation": "descriptive paired instrumentation/noise; no overhead subtraction or release threshold"})


def collect(root):
    root = Path(root).resolve()
    if not root.is_relative_to(ROOT / ".local"):
        raise ValueError("private collection root required")
    p = b.load(root / "protocol.json", 1048576)
    if p["revision"] != REVISION or p["schedule"] != schedule():
        raise ValueError("fixed schedule changed")
    validate_bindings(root, p)
    expected = canonical(b.load(root / "expected.json", 1048576))
    env = {k: os.environ[k] for k in ("SystemRoot", "WINDIR", "PATH", "TEMP", "TMP") if k in os.environ}
    env.update(LC_ALL="C", LANG="C", TZ="UTC")
    (root / "captures").mkdir()
    before = Path(p["input"]).stat()
    identity = lambda s: [s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns]
    record = {"protocolSha256": b.digest(root / "protocol.json"), "status": "aborted",
              "environment": env, "attempts": [], "sourceBefore": identity(before)}
    try:
        for n, cell in enumerate(p["schedule"]):
            observer = telemetry.Observer(p["sampleIntervalMs"]) if cell["arm"] == "telemetry" else None
            sample, stdout, stderr = b.run_process(p["argv"], str(Path(p["binary"]).parent), env,
                                                   p["timeoutMs"], p["captureBytes"], observer)
            correct = False
            try:
                actual = json.loads(stdout)
                correct = (sample["outcome"] == "exited" and sample["exitCode"] == 0 and not stderr
                    and not sample["censored"] and actual["files"][0]["path"] == p["input"]
                    and wire(canonical(actual)) == wire(expected))
            except (ValueError, KeyError, TypeError, IndexError):
                pass
            captures = {}
            for channel, data in (("stdout", stdout), ("stderr", stderr)):
                name = f"captures/{n:03d}.{channel}"
                (root / name).write_bytes(data)
                captures[channel] = name
            row = dict(cell, ordinal=n, sample=sample, correctness=correct, captures=captures,
                       telemetry=observer.report() if observer else None)
            record["attempts"].append(row)
            save(root / f"attempt-{n:03d}.json", row)
        record["sourceAfter"] = identity(Path(p["input"]).stat())
        record["bindingsUnchanged"] = all(b.digest(path) == digest for path, digest in p["bindings"].items())
        if record["sourceBefore"] != record["sourceAfter"] or not record["bindingsUnchanged"]:
            raise ValueError("binding changed during campaign")
        record["status"] = "completed"
    finally:
        save(root / "record.json", record)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--prepare-binary")
    parser.add_argument("--source-revision")
    args = parser.parse_args()
    if args.prepare_binary:
        prepare(args.run_root, args.prepare_binary, args.source_revision)
    else:
        collect(args.run_root)
