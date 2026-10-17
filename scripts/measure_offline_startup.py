"""Fixed offline help/version collection (#0143); no media operands or discovery."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import threading
import time

import read_benchmark as b
import read_telemetry as telemetry

ROOT = Path(__file__).resolve().parents[1]
REVISION = "offline-startup-v1"
CASES = (
    ("root-help", ["help"]),
    ("metadata-read-help", ["metadata", "read", "help"]),
    ("session-read-help", ["session", "read", "help"]),
    ("version-text", ["--version"]),
    ("version-json", ["--version", "--output", "json"]),
)
TOOL_FILES = (
    "scripts/measure_offline_startup.py", "scripts/audit_offline_startup.py",
    "scripts/test_offline_startup.py", "scripts/read_benchmark.py",
    "scripts/read_telemetry.py", "scripts/audit_read_telemetry.py",
    "docs/performance/offline-startup.md",
)


def save(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def schedule():
    return [{"case": case, "index": index, "phase": "warmup" if index < 3 else "sample"}
            for case, _ in CASES for index in range(13)]


def source_files():
    files = [ROOT / name for name in ("Cargo.toml", "Cargo.lock", "rust-toolchain.toml")]
    # Embedded include_str!/include_bytes! inputs need not be Rust or manifests.
    # Bind every production-tree file, including future non-code build inputs.
    files += [path for directory in ("src", "crates") for path in (ROOT / directory).rglob("*")
              if path.is_file() and "target" not in path.relative_to(ROOT).parts]
    files += [path for path in (ROOT / ".cargo").rglob("*") if path.is_file()]
    if (ROOT / "build.rs").exists():
        files.append(ROOT / "build.rs")
    return sorted(str(path.resolve()) for path in files)


def binding_paths(root, p):
    return set([str(Path(p[k]).resolve()) for k in ("binary", "pythonExecutable")] +
        [str((ROOT / name).resolve()) for name in TOOL_FILES] + source_files() +
        [str(path.resolve()) for path in (root / "oracle").rglob("*") if path.is_file()])


def validate_bindings(root, p):
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                          capture_output=True, timeout=10).stdout.decode().strip()
    if p["sourceRevision"] != head or p["sourceInventory"] != source_files():
        raise ValueError("frozen source revision/inventory changed")
    if set(p["bindings"]) != binding_paths(root, p):
        raise ValueError("incomplete frozen inventory")
    if any(b.digest(path) != expected for path, expected in p["bindings"].items()):
        raise ValueError("frozen binding changed")


class TimestampedPipe:
    """Read available bytes once per shared drain call; never wait for a full block."""
    def __init__(self, stream, channel, observer):
        self.stream, self.channel, self.observer = stream, channel, observer

    def read(self, size):
        block = self.stream.read1(size)
        now = time.perf_counter_ns() - self.observer.start
        with self.observer.pipe_lock:
            if block:
                self.observer.first.setdefault(self.channel, now)
            else:
                self.observer.eof[self.channel] = now
        return block

    def close(self):
        self.stream.close()


class StartupObserver(telemetry.Observer):
    """Retain shared native counters and timestamp observable pipe/exit endpoints."""
    def __init__(self, interval_ms=10, backend_factory=None):
        super().__init__(interval_ms, backend_factory)
        self.pipe_lock = threading.Lock()
        self.first, self.eof = {}, {}
        self.exit_observed = None

    def attach(self, process, start):
        super().attach(process, start)
        process.stdout = TimestampedPipe(process.stdout, "stdout", self)
        process.stderr = TimestampedPipe(process.stderr, "stderr", self)

    def sample(self, final=False):
        if final:
            # The shared runner calls this only after Popen.wait returns. This is
            # an observed exit upper bound, not the kernel's exact exit instant.
            self.exit_observed = time.perf_counter_ns() - self.start
        super().sample(final)

    def endpoints(self):
        with self.pipe_lock:
            output = max(self.eof.values()) if len(self.eof) == 2 else None
            return {"firstStdoutByteNs": self.first.get("stdout"),
                    "firstStderrByteNs": self.first.get("stderr"),
                    "firstByteNs": min(self.first.values()) if self.first else None,
                    "stdoutEofNs": self.eof.get("stdout"),
                    "stderrEofNs": self.eof.get("stderr"),
                    "completeOutputNs": output, "exitObservedNs": self.exit_observed,
                    "completeOutputExitNs": max(output, self.exit_observed)
                    if output is not None and self.exit_observed is not None else None}


def expected_cases(root):
    manifest = b.load(root / "oracle" / "manifest.json")
    expected = [{"id": case, "argv": argv, "exitCode": 0,
                 "stdout": case + ".stdout", "stderr": case + ".stderr"} for case, argv in CASES]
    if manifest != {"schemaVersion": 1, "cases": expected}:
        raise ValueError("oracle manifest differs from fixed invocation/status matrix")
    outputs = {}
    for case in expected:
        pair = tuple((root / "oracle" / case[channel]).read_bytes() for channel in ("stdout", "stderr"))
        if not pair[0] or pair[1] or any(len(data) > 1048576 for data in pair):
            raise ValueError("expected nonempty bounded stdout and empty stderr")
        outputs[case["id"]] = pair
    return outputs


def prepare(root, binary, revision, expected_root):
    root, binary, expected_root = Path(root).resolve(), Path(binary).resolve(), Path(expected_root).resolve()
    if not root.is_relative_to(ROOT / ".local"):
        raise ValueError("private collection root required")
    current = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                             capture_output=True, timeout=10).stdout.decode().strip()
    if revision != current:
        raise ValueError("source revision must be current exact HEAD")
    root.mkdir()
    (root / "oracle").mkdir()
    for name in ["manifest.json"] + [case + suffix for case, _ in CASES for suffix in (".stdout", ".stderr")]:
        data = (expected_root / name).read_bytes()
        if len(data) > 1048576:
            raise ValueError("oracle exceeds capture bound")
        with (root / "oracle" / name).open("xb") as stream:
            stream.write(data)
    expected_cases(root)
    p = {"schemaVersion": 1, "revision": REVISION, "sourceRevision": revision,
         "fixedUtc": datetime.now(timezone.utc).isoformat(), "binary": str(binary),
         "pythonExecutable": str(Path(sys.executable).resolve()), "pythonVersion": platform.python_version(),
         "sourceInventory": source_files(), "schedule": schedule(), "timeoutMs": 10000,
         "captureBytes": 1048576, "sampleIntervalMs": 10,
         "cases": [{"id": case, "argv": argv} for case, argv in CASES],
         "unsupported": [{"id": "format-discovery", "status": "unsupported-unrun"},
                         {"id": "tag-discovery", "status": "unsupported-unrun"}],
         "conditions": {"cache": "fresh process; hashes warm OS cache; OS/device caches uncontrolled",
             "background": "shared developer workstation; uncontrolled", "power": "unchanged inherited host",
             "storage": "local volume; physical topology unknown", "host": platform.platform(),
             "consumer": "shared concurrent bounded 4096-byte pipe drains with read1 available-byte adapter",
             "counterScope": "Windows direct Popen-owned process handle; sampled descendants, no containment",
             "timing": "perf_counter_ns before Popen; first received byte, two EOFs, exit observed before final counters; no overhead subtraction"},
         "stopping": "65 attempts; case-major 3 warmups then 10 samples; no retries/trimming/adaptive stopping"}
    p["bindings"] = {path: b.digest(path) for path in sorted(binding_paths(root, p))}
    save(root / "protocol.json", p)


def collect(root):
    root = Path(root).resolve()
    if not root.is_relative_to(ROOT / ".local"):
        raise ValueError("private collection root required")
    p = b.load(root / "protocol.json", 1048576)
    if (p["schemaVersion"] != 1 or p["revision"] != REVISION or p["schedule"] != schedule()
            or p["cases"] != [{"id": case, "argv": argv} for case, argv in CASES]
            or (p["timeoutMs"], p["captureBytes"], p["sampleIntervalMs"]) != (10000, 1048576, 10)
            or p["pythonExecutable"] != str(Path(sys.executable).resolve())):
        raise ValueError("fixed protocol changed")
    validate_bindings(root, p)
    expected = expected_cases(root)
    env = {k: os.environ[k] for k in ("SystemRoot", "WINDIR", "PATH", "TEMP", "TMP") if k in os.environ}
    env.update(LC_ALL="C", LANG="C", TZ="UTC")
    (root / "captures").mkdir()  # Fresh campaign: no overwrite/retry.
    record = {"schemaVersion": 1, "protocolSha256": b.digest(root / "protocol.json"),
              "status": "aborted", "environment": env, "attempts": []}
    try:
        for ordinal, cell in enumerate(p["schedule"]):
            observer = StartupObserver(p["sampleIntervalMs"])
            sample, stdout, stderr = b.run_process([p["binary"]] + dict(CASES)[cell["case"]],
                str(Path(p["binary"]).parent), env, p["timeoutMs"], p["captureBytes"], observer)
            sample.update(observer.endpoints())
            correct = (sample["outcome"] == "exited" and sample["exitCode"] == 0
                       and not sample["censored"] and (stdout, stderr) == expected[cell["case"]])
            captures = {}
            for channel, data in (("stdout", stdout), ("stderr", stderr)):
                name = f"captures/{ordinal:03d}.{channel}"
                with (root / name).open("xb") as stream:
                    stream.write(data)
                captures[channel] = name
            row = dict(cell, ordinal=ordinal, sample=sample, correctness=correct,
                       captures=captures, telemetry=observer.report())
            record["attempts"].append(row)
            save(root / f"attempt-{ordinal:03d}.json", row)
            if sample["outcome"] == "cancelled":
                record["status"] = "cancelled"
                break
        validate_bindings(root, p)
        record["bindingsUnchanged"] = True
        if len(record["attempts"]) == 65:
            record["status"] = "completed"
    finally:
        save(root / "record.json", record)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--prepare-binary")
    parser.add_argument("--source-revision")
    parser.add_argument("--expected-root")
    args = parser.parse_args()
    if args.prepare_binary:
        if not args.source_revision or not args.expected_root:
            parser.error("preparation needs --source-revision and --expected-root")
        prepare(args.run_root, args.prepare_binary, args.source_revision, args.expected_root)
    else:
        collect(args.run_root)
