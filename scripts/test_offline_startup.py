"""Authored controls for independent output/resource and startup capture audits."""
import copy
import io
import json
from pathlib import Path
import shutil
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

import audit_offline_startup as a
import measure_offline_startup as collector


def save(path, value):
    path.write_text(json.dumps(value) + "\n", encoding="utf-8", newline="\n")


def counter():
    values = {name: 10 for name in a.METRICS}
    values["physicalIoBytes"] = None
    return {"maxSamples": 2048, "requestedIntervalMs": 10, "pid": 123,
            "observedDescendantPids": [], "membership": "direct-only-observed", "valid": True,
            "errors": [], "stopReason": None, "observerWallNs": 5,
            "sampledMaxima": {"workingSetBytes": 10, "privateCommitBytes": 10},
            "samples": [{"beginOffsetNs": 60, "endOffsetNs": 65, "final": True,
                         "values": values, "errors": {"physicalIoBytes": "unavailable"}}]}


class Fixture:
    def __init__(self, directory):
        self.repo, self.root = directory / "repo", directory / "run"
        self.repo.mkdir()
        self.root.mkdir()
        for name in (*a.TOOLS, "Cargo.toml", "Cargo.lock", "rust-toolchain.toml", "src/lib.rs",
                     "src/inert_translation_templates.json", "crates/authored/assets/table.dat", "binary.exe", "python.exe"):
            p = self.repo / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"authored-control\n")
        shutil.copytree(a.ROOT / "docs/performance/offline-startup/oracle", self.root / "oracle")
        self.protocol = {"schemaVersion": 1, "revision": "offline-startup-v1", "sourceRevision": "0" * 40,
                         "sourceInventory": a.source_inventory(self.repo),
                         "binary": str(self.repo / "binary.exe"), "pythonExecutable": str(self.repo / "python.exe"),
                         "cases": [{"id": name, "argv": argv} for name, argv in a.CASES],
                         "schedule": [{"case": name, "index": i, "phase": "warmup" if i < 3 else "sample"}
                                      for name, _ in a.CASES for i in range(13)],
                         "timeoutMs": 10000, "captureBytes": 1048576, "sampleIntervalMs": 10,
                         "unsupported": [{"id": name, "status": "unsupported-unrun"}
                                         for name in ("format-discovery", "tag-discovery")]}
        paths = set(self.protocol["sourceInventory"])
        paths.update(str((self.repo / n).resolve()) for n in (*a.TOOLS, "binary.exe", "python.exe"))
        paths.update(str(p.resolve()) for p in (self.root / "oracle").iterdir())
        self.protocol["bindings"] = {p: a.sha(p) for p in paths}
        (self.root / "captures").mkdir()
        self.record = {"schemaVersion": 1, "status": "completed", "bindingsUnchanged": True,
                       "environment": {"LANG": "C", "LC_ALL": "C", "TZ": "UTC"}, "attempts": []}
        outputs = a.oracle(self.root / "oracle")
        import hashlib
        for n, cell in enumerate(self.protocol["schedule"]):
            out, err, code = outputs[cell["case"]]
            sample = {"elapsedNs": 100, "outcome": "exited", "exitCode": code, "censored": False,
                      "firstStdoutByteNs": 20, "firstStderrByteNs": None, "firstByteNs": 20,
                      "stdoutEofNs": 40, "stderrEofNs": 45, "completeOutputNs": 45,
                      "exitObservedNs": 50, "completeOutputExitNs": 50}
            captures = {}
            for channel, data in (("stdout", out), ("stderr", err)):
                captures[channel] = f"captures/{n:03d}.{channel}"
                (self.root / captures[channel]).write_bytes(data)
                sample.update({channel + "Bytes": len(data), channel + "CapturedBytes": len(data),
                               channel + "Sha256": hashlib.sha256(data).hexdigest()})
            self.record["attempts"].append(dict(cell, ordinal=n, sample=sample, captures=captures,
                                                correctness=True, telemetry=counter()))
        self.sync()

    def sync(self):
        save(self.root / "protocol.json", self.protocol)
        self.record["protocolSha256"] = a.sha(self.root / "protocol.json")
        for row in self.record["attempts"]:
            save(self.root / f"attempt-{row['ordinal']:03d}.json", row)
        save(self.root / "record.json", self.record)

    def audit(self):
        return a.audit(self.root, self.repo, "0" * 40)


class RetainedAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.f = Fixture(Path(self.temp.name))

    def test_complete_fixed_denominator(self):
        result = self.f.audit()
        self.assertEqual(result["verdict"], "pass")
        self.assertEqual(result["attempts"], 65)
        self.assertEqual(result["measuredAttempts"], 50)
        self.assertTrue(all(v["warmups"] == 3 and v["samples"] == 10 for v in result["cases"].values()))

    def test_changed_bytes_rejected_even_if_collector_passes(self):
        (self.f.root / "captures/000.stdout").write_bytes(b"wrong\n")
        with self.assertRaises(ValueError):
            self.f.audit()

    def test_consistently_rehashed_wrong_output_fails(self):
        import hashlib
        row = self.f.record["attempts"][0]
        wrong = b"wrong\n"
        (self.f.root / row["captures"]["stdout"]).write_bytes(wrong)
        row["sample"].update(stdoutBytes=len(wrong), stdoutCapturedBytes=len(wrong),
                             stdoutSha256=hashlib.sha256(wrong).hexdigest())
        self.f.sync()
        with self.assertRaisesRegex(ValueError, "correctness"):
            self.f.audit()
        row["correctness"] = False
        self.f.sync()
        self.assertEqual(self.f.audit()["verdict"], "incomplete-or-failed")

    def test_incomplete_retains_missing_denominator(self):
        for row in self.f.record["attempts"][1:]:
            (self.f.root / f"attempt-{row['ordinal']:03d}.json").unlink()
            for name in row["captures"].values():
                (self.f.root / name).unlink()
        self.f.record["attempts"] = self.f.record["attempts"][:1]
        self.f.record["status"] = "aborted"
        self.f.sync()
        result = self.f.audit()
        self.assertEqual(result["missingAttempts"], 64)
        self.assertEqual(result["verdict"], "incomplete-or-failed")

    def test_order_retry_and_unknown_namespace_refuse(self):
        self.f.record["attempts"][1]["index"] = 0
        self.f.sync()
        with self.assertRaisesRegex(ValueError, "order"):
            self.f.audit()
        self.f.record["attempts"][1]["index"] = 1
        self.f.sync()
        (self.f.root / "undeclared-retry.json").write_bytes(b"{}")
        with self.assertRaisesRegex(ValueError, "namespace"):
            self.f.audit()

    def test_source_tool_executable_binding_mutations(self):
        for name in ("src/lib.rs", "src/inert_translation_templates.json", "crates/authored/assets/table.dat",
                     "scripts/read_telemetry.py", "binary.exe", "python.exe"):
            path = self.f.repo / name
            original = path.read_bytes()
            path.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "artifact changed"):
                self.f.audit()
            path.write_bytes(original)

    def test_new_embedded_file_invalidates_frozen_inventory(self):
        for name in ("src/new-template.unfamiliar", "crates/authored/assets/added.unknown"):
            path = self.f.repo / name
            path.write_bytes(b"new production input")
            with self.assertRaisesRegex(ValueError, "source inventory"):
                self.f.audit()
            path.unlink()

    def test_build_target_files_excluded_from_production_inventory(self):
        before = a.source_inventory(self.f.repo)
        for name in ("src/target/irrelevant.json", "crates/authored/target/debug/artifact.exe"):
            path = self.f.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"build output")
        self.assertEqual(a.source_inventory(self.f.repo), before)
        self.assertEqual(self.f.audit()["verdict"], "pass")

    def test_missing_inventory_refused(self):
        self.f.protocol["sourceInventory"] = []
        self.f.sync()
        with self.assertRaisesRegex(ValueError, "source inventory"):
            self.f.audit()

    def test_status_and_timestamp_controls(self):
        row = self.f.record["attempts"][0]
        for field, value in (("exitCode", 2), ("firstByteNs", 21), ("stdoutEofNs", 19),
                             ("completeOutputExitNs", 49), ("exitObservedNs", 61), ("censored", True)):
            original = row["sample"][field]
            row["sample"][field] = value
            self.f.sync()
            with self.assertRaises(ValueError, msg=field):
                self.f.audit()
            row["sample"][field] = original

    def test_counter_failure_null_is_retained_not_zero(self):
        t = self.f.record["attempts"][0]["telemetry"]
        t["samples"][0]["errors"]["cpu"] = "authored inaccessible counter"
        for name in a.GROUPS["cpu"]:
            t["samples"][0]["values"][name] = None
        t["valid"] = False
        self.f.sync()
        result = self.f.audit()
        self.assertEqual(result["resourceValid"], 64)
        self.assertEqual(result["verdict"], "incomplete-or-failed")
        t["samples"][0]["values"]["userCpuNs"] = 0
        self.f.sync()
        with self.assertRaisesRegex(ValueError, "failure/value"):
            self.f.audit()

    def test_counter_arithmetic_endpoint_and_membership_controls(self):
        t = counter()
        for change in (lambda x: x.update(observerWallNs=0),
                       lambda x: x.update(observedDescendantPids=[42]),
                       lambda x: x["sampledMaxima"].update(workingSetBytes=0),
                       lambda x: x["samples"][0]["values"].update(physicalIoBytes=0),
                       lambda x: x["samples"][0].update(final=False)):
            changed = copy.deepcopy(t)
            change(changed)
            with self.assertRaises(ValueError):
                a.telemetry(changed, 100, 50)
        with self.assertRaisesRegex(ValueError, "precedes"):
            a.telemetry(t, 100, 61)

    def test_strict_json_and_relative_paths(self):
        path = self.f.root / "duplicate.json"
        path.write_bytes(b'{"x":1,"x":2}')
        with self.assertRaisesRegex(ValueError, "duplicate"):
            a.load(path)
        path.write_bytes(b'{"x":NaN}')
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            a.load(path)
        with self.assertRaises(ValueError):
            a.retained(self.f.root, "../outside")

    def test_resource_summary_uses_final_endpoint_and_sampled_maxima(self):
        result = self.f.audit()["descriptive"]["root-help"]
        self.assertEqual(result["outputCorrectTimingsNs"]["firstByteNs"],
                         {"count": 10, "min": 20, "median": 20.0, "max": 20})
        self.assertEqual(result["outputCorrectAndResourceValidCounters"]["userCpuNs"]["count"], 10)
        self.assertEqual(result["outputCorrectAndResourceValidCounters"]["sampledMax-workingSetBytes"]["min"], 10)

    def test_censored_failure_retained_and_not_summarized_as_success(self):
        row = self.f.record["attempts"][3]
        row["sample"].update(outcome="timeout", censored=True, exitCode=-1)
        row["correctness"] = False
        self.f.sync()
        result = self.f.audit()
        self.assertEqual(result["censored"], 1)
        self.assertEqual(result["descriptive"]["root-help"]["outputCorrectTimingsNs"]["firstByteNs"]["count"], 9)

    def test_last_counter_failure_never_substitutes_earlier_value(self):
        t = counter()
        early = copy.deepcopy(t["samples"][0])
        early.update(beginOffsetNs=10, endOffsetNs=15, final=False)
        t["samples"].insert(0, early)
        t["observerWallNs"] = 10
        t["samples"][-1]["errors"]["logicalIo"] = "endpoint failure"
        for metric in a.GROUPS["logicalIo"]:
            t["samples"][-1]["values"][metric] = None
        t["valid"] = False
        self.assertFalse(a.telemetry(t, 100, 50))
        t["samples"][-1]["values"]["readTransferBytes"] = 10
        with self.assertRaisesRegex(ValueError, "failure/value"):
            a.telemetry(t, 100, 50)


class EndpointControls(unittest.TestCase):
    def test_available_byte_adapter_records_first_once_and_eof(self):
        observer = collector.StartupObserver()
        observer.start = 100
        pipe = collector.TimestampedPipe(io.BufferedReader(io.BytesIO(b"abc")), "stdout", observer)
        with patch.object(collector.time, "perf_counter_ns", side_effect=[110, 120, 130]):
            self.assertEqual(pipe.read(1), b"a")
            self.assertEqual(pipe.read(9), b"bc")
            self.assertEqual(pipe.read(9), b"")
        self.assertEqual(observer.first, {"stdout": 10})
        self.assertEqual(observer.eof, {"stdout": 30})
        self.assertIsNone(observer.endpoints()["completeOutputNs"])

    def test_combined_endpoint_waits_for_both_eofs_and_exit(self):
        observer = collector.StartupObserver()
        observer.first = {"stdout": 8}
        observer.eof = {"stdout": 20, "stderr": 30}
        self.assertIsNone(observer.endpoints()["completeOutputExitNs"])
        observer.exit_observed = 25
        self.assertEqual(observer.endpoints()["completeOutputExitNs"], 30)

    def test_empty_launch_endpoints(self):
        observer = collector.StartupObserver()
        self.assertTrue(all(v is None for v in observer.endpoints().values()))


class FakeBackend:
    def __init__(self, _process):
        pass

    def read(self):
        sample = counter()["samples"][0]
        return sample["values"], sample["errors"]

    def descendants(self):
        return []


class AuthoredProcessControls(unittest.TestCase):
    """Real pipe lifecycle controls, never a candidate startup measurement."""
    def run_child(self, code, timeout=2000, bound=4096):
        observer = collector.StartupObserver(backend_factory=FakeBackend)
        sample, stdout, stderr = collector.b.run_process([sys.executable, "-c", code],
            str(a.ROOT), os.environ.copy(), timeout, bound, observer)
        sample.update(observer.endpoints())
        a.timing(sample)
        self.assertTrue(a.telemetry(observer.report(), sample["elapsedNs"], sample["exitObservedNs"]))
        return sample, stdout, stderr

    def test_actual_two_pipes_and_first_byte_before_complete(self):
        sample, stdout, stderr = self.run_child("import os,time; os.write(1,b'first\\n'); time.sleep(.03); os.write(1,b'last\\n'); os.write(2,b'error\\n')")
        self.assertEqual((stdout, stderr), (b"first\nlast\n", b"error\n"))
        self.assertEqual(sample["outcome"], "exited")
        self.assertLess(sample["firstStdoutByteNs"], sample["stdoutEofNs"])
        self.assertLessEqual(sample["exitObservedNs"], sample["completeOutputExitNs"])

    def test_actual_timeout_retains_partial_output(self):
        sample, stdout, _ = self.run_child("import os,time; os.write(1,b'partial\\n'); time.sleep(10)", timeout=500)
        self.assertEqual(sample["outcome"], "timeout")
        self.assertTrue(sample["censored"])
        self.assertEqual(stdout, b"partial\n")

    def test_actual_capture_bound_retains_partial(self):
        sample, stdout, _ = self.run_child("import sys; sys.stdout.write('x'*10000)", bound=128)
        self.assertEqual(sample["outcome"], "output-limit")
        self.assertEqual(len(stdout), 128)
        self.assertGreater(sample["stdoutBytes"], sample["stdoutCapturedBytes"])

    def test_actual_launch_failure_endpoints_unavailable(self):
        observer = collector.StartupObserver(backend_factory=FakeBackend)
        sample, out, err = collector.b.run_process([str(a.ROOT / '.local/missing-startup-control.exe')],
            str(a.ROOT), os.environ.copy(), 1000, 128, observer)
        sample.update(observer.endpoints())
        self.assertEqual((out, err), (b"", b""))
        self.assertEqual(sample["outcome"], "launch-error")
        a.timing(sample)
        self.assertFalse(a.telemetry(observer.report(), sample["elapsedNs"], None))


if __name__ == "__main__":
    unittest.main()
