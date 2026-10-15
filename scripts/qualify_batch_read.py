"""Public batch collector controls using authored structural bytes, never cameras."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import measure_batch_read as batch
import read_benchmark as single


def expected_envelope():
    snapshot = single.load(batch.ROOT / "docs/legacy-compatibility/native-read-json/example.v1.json", 1048576)
    snapshot["id"] = "authored-snapshot-0"
    snapshot["sources"][0]["displayPath"] = "input"
    issue = {"code": "COVERAGE_PARTIAL", "severity": "warning",
             "message": "Only the declared R5 metadata/preview slice is interpreted. Other fields and embedded metadata are not inspected.",
             "inputId": "input-0", "path": None, "occurrenceRef": None}
    file = {"schemaVersion": 1, "kind": "file", "requestId": "authored", "inputId": "input-0",
            "path": "input", "state": "read", "snapshot": snapshot, "transactionId": None,
            "effects": {"publicationMayHaveOccurred": False, "changed": False, "cleanupPending": False,
                        "recoveryIds": [], "notes": []}, "issues": [issue]}
    return {"schemaVersion": 1, "requestId": "authored", "request": {
        "schemaVersion": 1, "kind": "request", "requestId": "authored", "operation": "metadata read", "mode": "read", "issues": []},
        "files": [file], "summary": {"schemaVersion": 1, "kind": "summary", "requestId": "authored", "exitStatus": 0,
        "selectionComplete": True, "counts": {"discovered": 1, "excluded": 0, "deduplicated": 0, "byState": {"read": 1}},
        "artifacts": [], "issues": [], "interrupted": False, "outputComplete": True}}


def qualify(binary, source_root, parent):
    binary = Path(binary).resolve()
    source_root = Path(source_root).resolve()
    parent = Path(parent).resolve()
    parent.mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix="batch-authored-", dir=parent))
    source = folder / "fixture.rs"
    helper = json.dumps((source_root / "tests/support/mod.rs").as_posix())
    source.write_bytes((f'#[allow(dead_code)] #[path={helper}] mod support;\n'
        'fn main(){let d=std::path::PathBuf::from(std::env::args_os().nth(1).unwrap());'
        'let f=support::fixture();for n in 1..=8 {std::fs::write(d.join(format!("authored-{n}.cr3")),&f.bytes).unwrap();}}\n').encode())
    generator = folder / ("fixture.exe" if os.name == "nt" else "fixture")
    subprocess.run(["rustc", "--edition=2024", str(source), "-o", str(generator)], check=True, capture_output=True, timeout=45)
    subprocess.run([str(generator), str(folder)], check=True, timeout=10)
    paths = [folder / f"authored-{n}.cr3" for n in range(1, 9)]
    before = {p.name: (single.digest(p), p.stat().st_mtime_ns) for p in paths}
    fixtures = [{"id": f"AUTHORED-{n:03d}", "input": str(paths[n - 1])} for n in range(1, 9)]
    template = expected_envelope()
    expected = [batch.wire(batch.normalized_file(template["files"][0]))] * 8
    env = dict(os.environ, LC_ALL="C", LANG="C", TZ="UTC")
    results = []
    for size in (1, 2, 4, 8):
        for index in range(4):
            argv = [str(binary), "metadata", "read", "--values", "all", "--output", "json", "--", *map(str, paths[:size])]
            names = set(folder.iterdir())
            sample, stdout, stderr = single.run_process(argv, str(folder), env, 30000, 4194304)
            batch.require(set(folder.iterdir()) == names, "read CLI created an unexpected artifact")
            files, correctness = batch.classify(stdout, stderr, sample, fixtures[:size], expected[:size], template)
            batch.require(correctness == "pass", "authored native batch did not match independently published snapshot/contract")
            results.append({"size": size, "index": index, "phase": "warmup" if index == 0 else "sample",
                            "elapsedNs": sample["elapsedNs"], "outcome": sample["outcome"], "exitCode": sample["exitCode"],
                            "censored": sample["censored"], "stdoutBytes": sample["stdoutBytes"], "stderrBytes": sample["stderrBytes"],
                            "files": files, "batchCorrectness": correctness})
            (folder / f"n{size}-a{index}.stdout").write_bytes(stdout)
    controls = []
    for name, operands, code, states, deduplicated in [
        ("duplicate-path", [paths[0], paths[0]], 0, ["read"], 1),
        ("missing-input", [folder / "missing.cr3"], 1, ["failed"], 0),
        ("mixed-read-failure", [paths[0], folder / "missing.cr3"], 3, ["read", "failed"], 0),
    ]:
        argv = [str(binary), "metadata", "read", "--values", "all", "--output", "json", "--", *map(str, operands)]
        names = set(folder.iterdir())
        sample, stdout, stderr = single.run_process(argv, str(folder), env, 30000, 4194304)
        batch.require(set(folder.iterdir()) == names, "failed/read CLI created an unexpected artifact")
        record = batch.strict_json(stdout)
        batch.require(sample["exitCode"] == code and [f["state"] for f in record["files"]] == states
                      and record["summary"]["counts"]["deduplicated"] == deduplicated
                      and record["summary"]["outputComplete"] is True, "authored failure/dedup outcome mismatch")
        controls.append({"id": name, "outcome": sample["outcome"], "exitCode": sample["exitCode"],
                         "fileStates": states, "deduplicated": deduplicated, "passed": True})
    for name, script, timeout, cap, outcome in [
        ("timeout", "import time;time.sleep(5)", 30, 1024, "timeout"),
        ("output-overflow", "import sys;sys.stdout.buffer.write(b'x'*1000000)", 2000, 1024, "output-limit"),
        ("malformed-output", "print('{')", 2000, 1024, "exited"),
    ]:
        sample, stdout, stderr = single.run_process([sys.executable, "-c", script], str(folder), env, timeout, cap)
        files, correctness = batch.classify(stdout, stderr, sample, fixtures[:2], expected[:2], template)
        batch.require(sample["outcome"] == outcome and correctness != "pass"
                      and len(files) == 2 and all(f["state"] == "not-observed" for f in files), "missing/censored slots were invented or dropped")
        controls.append({"id": name, "outcome": sample["outcome"], "censored": sample["censored"],
                         "scheduledFiles": 2, "files": files, "batchCorrectness": correctness, "passed": True})
    batch.require(before == {p.name: (single.digest(p), p.stat().st_mtime_ns) for p in paths}, "authored source changed")
    return {"schemaVersion": 1, "kind": "authored-batch-collector-qualification", "privateCameraMediaUsed": False,
            "scope": "Authored structural fixtures only; these timings are not camera RAW performance evidence",
            "grid": [1, 2, 4, 8], "warmupsPerSize": 1, "samplesPerSize": 3, "attempts": results,
            "controls": controls, "sourcesUnchanged": True, "noMutationArtifacts": True,
            "runnerSha256": single.digest(batch.__file__), "collectorSha256": single.digest(single.__file__),
            "qualifierSha256": single.digest(__file__), "binarySha256": single.digest(binary),
            "oracle": "Committed #0053 authored snapshot plus published result contract, not tested-tool self output",
            "publication": "This artifact contains authored observations only. Actual private-camera measurements and reports are withheld."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True)
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--parent", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    batch.require(not Path(args.output).exists(), "fresh authored qualification destination required")
    batch.save(args.output, qualify(args.binary, args.source_root, args.parent))
