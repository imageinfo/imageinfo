"""Authored order/statistics/failure controls for #0150."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import subprocess
import os
import sys
import unittest
from unittest.mock import patch

import audit_collector_overhead_150 as audit
import measure_collector_overhead_150 as measure


class OverheadTests(unittest.TestCase):
    def test_known_statistics_and_signed_differences(self):
        result = audit.distribution(list(range(1, 31)))
        self.assertEqual((result["count"], result["medianNs"], result["madNs"],
                          result["p95Ns"], result["windowDriftNs"]), (30, 15.5, 7.5, 29, 20))
        self.assertAlmostEqual(result["cv"], 0.5679618342470648)
        self.assertIsNone(audit.distribution([])["medianNs"])
        self.assertIsNone(audit.distribution([-3, -2, -1])["cv"])

    def test_complete_paired_order_and_balance(self):
        rows = measure.schedule()
        self.assertEqual(len(rows), 198)
        for trial in range(3):
            measured = [r for r in rows if r["round"] == trial and r["phase"] == "sample"]
            self.assertEqual(sum(r["arm"] == "elapsed" and r["position"] == 0 for r in measured), 15)
            self.assertEqual(sum(r["arm"] == "telemetry" and r["position"] == 0 for r in measured), 15)
            for index in range(33):
                pair = [r for r in rows if r["round"] == trial and r["index"] == index]
                self.assertEqual({r["arm"] for r in pair}, {"elapsed", "telemetry"})

    def test_failed_censored_missing_series_preserve_denominator(self):
        rows = [dict(cell, valid=True, sample={"elapsedNs": 100 + cell["index"] +
                    (10 if cell["arm"] == "telemetry" else 0), "censored": False})
                for cell in measure.schedule()]
        full = audit.summarize(rows)
        self.assertEqual(full[0]["pairedTelemetryMinusElapsed"]["medianNs"], 10)
        self.assertEqual(full[0]["pairedTelemetryMinusElapsed"]["madNs"], 0)
        broken = copy.deepcopy(rows)
        broken[6]["valid"] = False
        broken[6]["sample"]["censored"] = True
        del broken[8]
        result = audit.summarize(broken)[0]
        self.assertEqual(sum(x["attempted"] for x in result["arms"].values()), 59)
        self.assertEqual(sum(x["missing"] for x in result["arms"].values()), 1)
        self.assertEqual(sum(x["failed"] for x in result["arms"].values()), 1)
        self.assertEqual(sum(x["censored"] for x in result["arms"].values()), 1)
        self.assertEqual(result["pairedExcluded"], 2)
        self.assertIsNone(result["pairedTelemetryMinusElapsed"]["windowDriftNs"])

    def test_public_collection_refuses(self):
        with self.assertRaises(ValueError):
            measure.collect(measure.ROOT / "docs")

    def test_both_arm_samples_reject_invalid_semantics(self):
        valid = {"elapsedNs": 100, "outcome": "exited", "exitCode": 0, "censored": False,
                 "stdoutBytes": 10, "stdoutCapturedBytes": 10, "stderrBytes": 0, "stderrCapturedBytes": 0}
        for arm in ("elapsed", "telemetry"):
            for field, value in (("elapsedNs", -123), ("elapsedNs", True), ("stdoutBytes", -1),
                                 ("stdoutBytes", True), ("stdoutCapturedBytes", -1),
                                 ("censored", True), ("outcome", "invented"), ("exitCode", False)):
                with self.subTest(arm=arm, field=field, value=value), self.assertRaises(ValueError):
                    audit.validate_sample(dict(valid, **{field: value}), 100)
        for outcome in ("timeout", "cancelled", "consumer-error", "output-limit", "telemetry-limit"):
            audit.validate_sample(dict(valid, outcome=outcome, censored=True), 100)
        audit.validate_sample(dict(valid, outcome="launch-error", exitCode=None,
            stdoutBytes=0, stdoutCapturedBytes=0), 100)

    def test_actual_shared_runner_telemetry_limit_is_censored_and_retained(self):
        class Backend:
            def __init__(self, process):
                pass

            def read(self):
                return {key: None for key in measure.telemetry.METRICS}, {}

            def descendants(self):
                return []

        observer = measure.telemetry.Observer(10, backend_factory=Backend)
        with patch.object(measure.telemetry, "MAX_SAMPLES", 1):
            sample, stdout, stderr = measure.b.run_process(
                [sys.executable, "-c", "import time; time.sleep(10)"], str(measure.ROOT),
                dict(os.environ), 3000, 1024, observer)
        self.assertEqual(sample["outcome"], "telemetry-limit")
        self.assertTrue(sample["censored"])
        audit.validate_sample(sample, 1024)
        rows = [dict(cell, valid=False, sample=sample) for cell in measure.schedule()]
        report = audit.summarize(rows)[0]
        for arm in ("elapsed", "telemetry"):
            self.assertEqual((report["arms"][arm]["planned"], report["arms"][arm]["attempted"],
                report["arms"][arm]["failed"], report["arms"][arm]["censored"]), (30, 30, 30, 30))
            self.assertIsNone(report["arms"][arm]["distribution"]["medianNs"])

    def test_frozen_inventory_dependencies_and_source_revision(self):
        with tempfile.TemporaryDirectory(dir=measure.ROOT / ".local", prefix="150-binding-") as temporary:
            root = Path(temporary)
            for name in ("binary.exe", "input.cr3", "fixture.rs", "expected.json"):
                (root / name).write_bytes(b"authored")
            p = {"binary": str(root / "binary.exe"), "input": str(root / "input.cr3"),
                 "sourceInventory": audit.source_files(), "sourceRevision": subprocess.run(
                    ["git", "rev-parse", "HEAD"], cwd=measure.ROOT, check=True, capture_output=True).stdout.decode().strip()}
            p["bindings"] = {path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
                             for path in audit.binding_paths(root, p)}
            audit.validate_bindings(root, p)
            for dependency in ("scripts/qualify_batch_read.py", "scripts/audit_read_resources_144.py",
                               "scripts/audit_read_telemetry.py", "src/lib.rs"):
                path = str((measure.ROOT / dependency).resolve())
                missing = copy.deepcopy(p)
                del missing["bindings"][path]
                with self.assertRaisesRegex(ValueError, "inventory"):
                    audit.validate_bindings(root, missing)
                changed = copy.deepcopy(p)
                changed["bindings"][path] = "0" * 64
                with self.assertRaisesRegex(ValueError, "binding changed"):
                    audit.validate_bindings(root, changed)
            for revision in (None, "arbitrary", "0" * 40):
                with self.assertRaisesRegex(ValueError, "revision"):
                    audit.validate_bindings(root, dict(p, sourceRevision=revision))
            real_run = subprocess.run
            different_head = p["sourceRevision"][:-1] + ("0" if p["sourceRevision"][-1] != "0" else "1")

            def changed_head(args, **kwargs):
                if args == ["git", "rev-parse", "HEAD"]:
                    return subprocess.CompletedProcess(args, 0, (different_head + "\n").encode(), b"")
                return real_run(args, **kwargs)

            with patch.object(audit.subprocess, "run", side_effect=changed_head), \
                    self.assertRaisesRegex(ValueError, "frozen HEAD"):
                audit.validate_bindings(root, p)
            changed = copy.deepcopy(p)
            changed["sourceInventory"] = []
            with self.assertRaisesRegex(ValueError, "source inventory"):
                audit.validate_bindings(root, changed)

    def test_retained_raw_audit_rejects_missing_reorder_and_capture_change(self):
        with tempfile.TemporaryDirectory(dir=measure.ROOT / ".local", prefix="150-controls-") as temporary:
            root = Path(temporary)
            (root / "captures").mkdir()
            expected = measure.authored.expected_envelope()
            expected["files"][0]["path"] = "fixture.cr3"
            stdout = json.dumps(expected).encode()
            (root / "expected.json").write_bytes(stdout)
            protocol = {"revision": measure.REVISION, "binary": "imageinfo.exe", "input": "fixture.cr3",
                "schedule": measure.schedule(), "bindings": {}, "timeoutMs": 30000,
                "captureBytes": 4194304, "sampleIntervalMs": 10,
                "argv": ["imageinfo.exe", "metadata", "read", "--values", "all", "--output", "json",
                         "--max-bytes", "8388608", "--", "fixture.cr3"]}
            measure.save(root / "protocol.json", protocol)
            rows = []
            for n, cell in enumerate(protocol["schedule"]):
                sample = {"outcome": "exited", "exitCode": 0, "censored": False, "elapsedNs": 100 + n,
                          "stdoutCapturedBytes": len(stdout), "stderrCapturedBytes": 0,
                          "stdoutBytes": len(stdout), "stderrBytes": 0,
                          "stdoutSha256": hashlib.sha256(stdout).hexdigest(),
                          "stderrSha256": hashlib.sha256(b"").hexdigest()}
                captures = {k: f"captures/{n:03d}.{k}" for k in ("stdout", "stderr")}
                (root / captures["stdout"]).write_bytes(stdout)
                (root / captures["stderr"]).write_bytes(b"")
                row = dict(cell, ordinal=n, sample=sample, captures=captures, correctness=True,
                           telemetry={"valid": True} if cell["arm"] == "telemetry" else None)
                measure.save(root / f"attempt-{n:03d}.json", row)
                rows.append(row)
            record = {"protocolSha256": hashlib.sha256((root / "protocol.json").read_bytes()).hexdigest(),
                "status": "completed", "bindingsUnchanged": True, "sourceBefore": [1], "sourceAfter": [1],
                "attempts": rows}
            def write_record(value):
                (root / "record.json").write_text(json.dumps(value), encoding="utf-8")
            write_record(record)
            with patch.object(audit, "telemetry_audit"), patch.object(audit, "validate_bindings"):
                self.assertTrue(audit.audit(root)["allCorrect"])
                for arm in ("elapsed", "telemetry"):
                    for field, value in (("elapsedNs", -123), ("stdoutBytes", -1), ("censored", True)):
                        bad = copy.deepcopy(record)
                        index = next(i for i, x in enumerate(bad["attempts"]) if x["arm"] == arm)
                        bad["attempts"][index]["sample"][field] = value
                        path = root / f"attempt-{index:03d}.json"
                        path.write_text(json.dumps(bad["attempts"][index]), encoding="utf-8")
                        write_record(bad)
                        with self.subTest(arm=arm, field=field), self.assertRaises(ValueError):
                            audit.audit(root)
                        path.write_text(json.dumps(record["attempts"][index]), encoding="utf-8")
                missing = copy.deepcopy(record)
                missing["attempts"].pop()
                write_record(missing)
                with self.assertRaisesRegex(ValueError, "fixed stopping"):
                    audit.audit(root)
                reordered = copy.deepcopy(record)
                reordered["attempts"][0], reordered["attempts"][1] = reordered["attempts"][1], reordered["attempts"][0]
                write_record(reordered)
                with self.assertRaisesRegex(ValueError, "counterbalance"):
                    audit.audit(root)
                write_record(record)
                (root / rows[0]["captures"]["stdout"]).write_bytes(b"bad")
                with self.assertRaisesRegex(ValueError, "capture length"):
                    audit.audit(root)


if __name__ == "__main__":
    unittest.main()
