"""Authored schedule, pipe, retained-failure and refusal controls (#0151)."""
import json
import _thread
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

import measure_comparable_read_151 as measure
import measure_batch_read as batch
import qualify_batch_read as authored


class ComparableCollector(unittest.TestCase):
    def test_batched_verifier_structured_input_and_output_bound(self):
        request = b'{"paths":["authored installed file"]}'
        result, stdout, stderr = measure.run_identity_verifier([sys.executable, "-c",
            "import sys;sys.stdout.buffer.write(sys.stdin.buffer.read())"],
            request, str(measure.ROOT), dict(os.environ))
        self.assertEqual((result["outcome"], result["exitCode"], stdout, stderr),
                         ("exited", 0, request, b""))
        result, stdout, stderr = measure.run_identity_verifier([sys.executable, "-c",
            "import sys;sys.stdin.buffer.read();sys.stdout.buffer.write(b'x'*1048576)"],
            request, str(measure.ROOT), dict(os.environ))
        self.assertEqual(result["outcome"], "output-limit")
        self.assertEqual(len(stdout), 524288)

    def test_batched_identity_mismatch_retains_checkpoint_before_refusal(self):
        root = Path(tempfile.mkdtemp(prefix="151-verifier-refusal-", dir=measure.ROOT / ".local"))
        row = dict(path="/usr/bin/perl", sha256="0" * 64, byteLength="0")
        manifest = root / "manifest.json"
        measure.save(manifest, dict(versionProbe="13.59", configurationSuppressionVerified=True,
            sourceBefore=[row], sourceAfter=[row], runtimeBefore=[row], runtimeAfter=[row]))
        p = dict(priorReferenceEnvironment=str(manifest),
            referenceLibrary="/mnt/c/Projects/imageinfo/.local/tools/exiftool-13.59-source/lib",
            referenceScript="/mnt/c/Projects/imageinfo/.local/tools/exiftool-13.59-source/exiftool",
            referenceLauncher="C:/Windows/System32/wsl.exe", distribution="Ubuntu",
            referenceInput="/mnt/c/authored.cr3", fixture=dict(input="C:/authored.cr3"),
            identityCheckRoot=str(root / "reference-identity"), cwd=str(root), environment=dict(os.environ))
        p["bindings"] = {str(Path(p["referenceLauncher"]).resolve()): "authored binding"}
        original = measure.run_identity_verifier
        def retained_wrong(argv, request, cwd, env):
            script = "import sys;sys.stdin.buffer.read();print('0\\t" + "1" * 64 + "\\t0')"
            return original([sys.executable, "-c", script], request, cwd, env)
        trace = []
        with patch.object(measure, "run_identity_verifier", side_effect=retained_wrong), self.assertRaises(ValueError):
            measure.reference_identity(p, trace)
        checkpoint = root / "reference-identity/checkpoint-00"
        result = measure.b.load(checkpoint / "record.private.json")
        self.assertFalse(result["exactMatch"])
        self.assertEqual(trace, [{"checkpoint": "checkpoint-00",
                                "recordSha256": measure.b.digest(checkpoint / "record.private.json")}])
        self.assertEqual(result["outcome"], "exited")
        self.assertEqual(json.loads((checkpoint / "request.json").read_bytes()), {"paths": ["/usr/bin/perl"]})
        self.assertTrue((checkpoint / "stdout").exists() and (checkpoint / "stderr").exists())

    def test_public_destination_refuses_before_prerequisite_read(self):
        with patch.object(measure.b, "load") as load, self.assertRaises(ValueError):
            measure.collect(measure.ROOT / "docs")
        load.assert_not_called()

    def test_missing_task_authority_refuses_before_identity_or_source(self):
        with patch.object(measure.b, "digest") as digest, self.assertRaises(ValueError):
            measure.rights({"revision": measure.REVISION, "taskAdmission": {}})
        digest.assert_not_called()

    def test_preregistered_orders_balance_each_measured_round(self):
        for round_no in range(3):
            entries = [s for s in measure.schedule() if s["round"] == round_no]
            self.assertEqual(len(entries), 13)
            self.assertEqual(sum(s["phase"] == "warmup" for s in entries), 3)
            self.assertEqual(sum(s["phase"] == "sample" and s["order"][0] == "native" for s in entries), 5)

    def test_reference_keyboard_interrupt_retains_started_capture_and_stops_schedule(self):
        root = Path(tempfile.mkdtemp(prefix="151-authored-cancel-", dir=measure.ROOT / ".local"))
        oracle = root / "oracle.json"
        envelope = authored.expected_envelope()
        oracle.write_text(json.dumps(envelope), encoding="utf-8")
        native_bytes = json.dumps(measure.native.project(envelope, "EXIF:ISO", "raw")).encode()
        p = {"fixture": {"input": "input", "oracle": str(oracle)}, "binary": "authored-native",
             "referenceInput": "input", "cwd": str(root), "environment": dict(os.environ),
             "identityCheckRoot": str(root / "reference-identity")}
        measure.save(root / "protocol.private.json", p)
        direct = measure.b.run_process

        def authored_child(argv, cwd, env, timeout_ms, capture_bytes, observer):
            if argv[0] == "authored-native":
                script = "import sys;sys.stdout.buffer.write(" + repr(native_bytes) + ")"
                return direct([sys.executable, "-c", script], cwd, env, timeout_ms, capture_bytes, observer)
            script = "import sys,time;sys.stdout.write('authored-partial');sys.stdout.flush();time.sleep(30)"
            timer = threading.Timer(0.3, _thread.interrupt_main)
            timer.start()
            try:
                return direct([sys.executable, "-c", script], cwd, env, timeout_ms, capture_bytes, observer)
            finally:
                timer.cancel()

        identity = {"sha256": "authored", "bytes": 0, "mtimeNs": 0, "device": 0, "inode": 0}
        with patch.object(measure, "rights"), patch.object(measure, "source_check", return_value=identity), \
             patch.object(measure, "reference_arguments", return_value=["authored-reference"]), \
             patch.object(measure.b, "run_process", side_effect=authored_child):
            measure.collect(root)
        r = measure.b.load(root / "record.private.json", 16 * 1024 * 1024)
        self.assertEqual((r["status"], r["stopReason"], len(r["pairs"])), ("aborted", "cancelled", 1))
        sample = r["pairs"][0]["attempts"]["reference"]
        self.assertEqual(sample["outcome"], "cancelled")
        self.assertTrue(sample["censored"])
        self.assertFalse(r["pairs"][0]["eligible"])
        self.assertEqual((root / sample["captures"]["stdout"]).read_bytes(), b"authored-partial")

    def test_actual_authored_children_retain_failed_pair_and_all_later_slots(self):
        # This tests orchestration/retention with public authored wire fixtures.
        # No tool/media authority or actual native/reference timing is inferred.
        root = Path(tempfile.mkdtemp(prefix="151-authored-", dir=measure.ROOT / ".local"))
        envelope = authored.expected_envelope()
        for occurrence in envelope["files"][0]["snapshot"]["occurrences"]:
            if occurrence["tag"]["name"] == "ISO":
                self.assertEqual(occurrence["values"]["raw"]["value"]["decimal"], "800")
        envelope["files"][0]["path"] = "input"
        oracle = root / "oracle.json"
        oracle.write_text(json.dumps(envelope), encoding="utf-8")
        native_bytes = json.dumps(measure.native.project(envelope, "EXIF:ISO", "raw")).encode()
        p = {"fixture": {"input": "input", "oracle": str(oracle)}, "binary": "authored-native", "referenceInput": "input",
             "cwd": str(root), "environment": dict(os.environ),
             "identityCheckRoot": str(root / "reference-identity")}
        measure.save(root / "protocol.private.json", p)
        direct = measure.b.run_process
        reference_count = 0

        def authored_child(argv, cwd, env, timeout_ms, capture_bytes, observer):
            nonlocal reference_count
            if argv[0] == "authored-native":
                data = native_bytes
            else:
                # First measured pair is wrong; later slots must still run.
                data = json.dumps([{"SourceFile": "input", "EXIF:ExifIFD:ISO":
                                    801 if reference_count == 3 else 800}]).encode()
                reference_count += 1
            script = "import sys;sys.stdout.buffer.write(" + repr(data) + ")"
            return direct([sys.executable, "-c", script], cwd, env, timeout_ms, capture_bytes, observer)

        identity = {"sha256": "authored", "bytes": 0, "mtimeNs": 0, "device": 0, "inode": 0}
        with patch.object(measure, "rights"), patch.object(measure, "source_check", return_value=identity), \
             patch.object(measure, "reference_arguments", return_value=["authored-reference"]), \
             patch.object(measure.b, "run_process", side_effect=authored_child):
            measure.collect(root)
        record = measure.b.load(root / "record.private.json", 16 * 1024 * 1024)
        self.assertEqual(record["status"], "completed")
        self.assertEqual(len(record["pairs"]), 39)
        self.assertEqual(reference_count, 39)
        self.assertEqual(record["pairs"][3]["correspondence"], "fail")
        self.assertFalse(record["pairs"][3]["eligible"])
        self.assertTrue(record["pairs"][-1]["eligible"])
        self.assertEqual(len(list((root / "captures").iterdir())), 156)
        measure.save(root / "authored-test-only.json", {"privateCameraMediaUsed": False,
            "scope": "Actual authored Python children; rights/source stubs are test-only; no benchmark or native/runtime qualification",
            "wrongReferencePair": [0, 3], "passed": True})
        # Retained location contains only authored data and enables independent QA.
        retained = os.environ.get("IMAGEINFO_151_AUTHORED_POINTER")
        if retained:
            Path(retained).write_text(str(root), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
