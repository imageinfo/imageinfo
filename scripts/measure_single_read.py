"""Run the fixed #0061 protocol and retain bounded private correctness captures."""
import argparse
import json
from pathlib import Path
import time

import read_benchmark as collector


def measure(run_root):
    root = Path(run_root).resolve()
    protocol_path = root / "protocol.private.json"
    protocol = collector.load(protocol_path)
    if protocol["schemaVersion"] != 1 or protocol["trialCount"] != 3:
        raise ValueError("unsupported fixed protocol")
    if protocol["interTrialDelaySeconds"] != 5:
        raise ValueError("fixed intertrial delay required")
    if collector.digest(__file__) != protocol["runnerSha256"]:
        raise ValueError("runner identity changed after protocol pin")
    if collector.digest(collector.__file__) != protocol["collectorSha256"]:
        raise ValueError("collector identity changed after protocol pin")
    trials = protocol["trials"]
    if len(trials) != 3:
        raise ValueError("three trial configurations required")
    configurations = []
    for index, trial in enumerate(trials, 1):
        if trial["config"] != f"trial-{index}.config.private.json":
            raise ValueError("unexpected configuration name")
        if trial["record"] != f"trial-{index}.record.private.json":
            raise ValueError("unexpected record name")
        path = root / trial["config"]
        if collector.digest(path) != trial["sha256"]:
            raise ValueError("configuration identity changed after protocol pin")
        c = collector.load(path)
        collector.check_config(c)
        if any(c[k] != v for k, v in {
            "repeats": 30, "warmups": 3, "timeoutMs": 10000,
            "captureBytes": 1048576, "maxBytes": 8388608,
        }.items()):
            raise ValueError("configuration differs from fixed sample/budget protocol")
        if (root / trial["record"]).exists():
            raise ValueError("trial record destination must be fresh")
        configurations.append(c)
    captures = root / "captures"
    captures.mkdir()  # Exclusive directory creation prevents capture replacement.
    original = collector.run_process
    manifest = {"schemaVersion": 1, "protocolSha256": collector.digest(protocol_path),
                "runnerSha256": protocol["runnerSha256"],
                "collectorSha256": protocol["collectorSha256"],
                "status": "aborted", "captures": [], "records": []}
    try:
        for trial_number, (trial, config) in enumerate(zip(trials, configurations), 1):
            attempt_number = 0

            def capture(*args, **kwargs):
                nonlocal attempt_number
                result = original(*args, **kwargs)
                # Keep the accepted collector's timing boundary unchanged. The
                # wrapper saves its already bounded returned bytes only after
                # timing ends, enabling a separate verifier to check every output.
                stem = f"trial-{trial_number}-attempt-{attempt_number:02d}"
                entry = {"trial": trial_number, "attempt": attempt_number}
                for name, data in zip(("stdout", "stderr"), result[1:]):
                    path = captures / f"{stem}.{name}"
                    with path.open("xb") as stream:
                        stream.write(data)
                    entry[name] = {"path": f"captures/{path.name}",
                                   "sha256": collector.digest(path), "bytes": len(data)}
                manifest["captures"].append(entry)
                attempt_number += 1
                return result

            collector.run_process = capture
            record_path = root / trial["record"]
            record = collector.collect(config, record_path)
            manifest["records"].append({"trial": trial_number, "path": trial["record"],
                                        "sha256": collector.digest(record_path),
                                        "status": record["status"]})
            if attempt_number != 33:
                raise ValueError("attempt count differs from declared protocol")
            if trial_number < 3:
                time.sleep(5)
        manifest["status"] = "completed"
    finally:
        collector.run_process = original
        with (root / "capture-manifest.private.json").open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(manifest, indent=2) + "\n")
    print(f"Retained {len(manifest['captures'])} bounded private output pairs; {manifest['status']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", required=True, help="private pinned protocol/configuration directory")
    measure(parser.parse_args().run_root)
