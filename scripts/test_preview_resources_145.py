"""Authored checks only: no camera reads, resource outcomes or timing baseline."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import audit_preview_resources_145 as audit
import measure_preview_resources_145 as measure


class PreviewResourcesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (measure.ROOT / ".local").mkdir(exist_ok=True)

    def test_fixed_operations(self):
        self.assertEqual(measure.OPERATIONS, [("list", None), ("extract", "ThumbnailImage"),
            ("extract", "PreviewImage"), ("extract", "JpgFromRaw")])
        self.assertEqual(len(measure.OPERATIONS)*12, 48)

    def test_missing_authority_refuses_before_evidence_or_media(self):
        with patch.object(measure.b, "digest", side_effect=AssertionError("must not hash")):
            with self.assertRaises(ValueError):
                measure.rights({"taskAdmission": {}})

    def test_exact_independent_ranges_and_padding(self):
        with tempfile.TemporaryDirectory(dir=measure.ROOT / ".local") as folder:
            root = Path(folder)
            data, rows, occurrences, resources = b"header", [], [], []
            for index, tag in enumerate(("ThumbnailImage", "PreviewImage", "JpgFromRaw")):
                payload = b"\xff\xd8" + bytes([index+50])*9 + b"\xff\xd9\0\0\0"
                path = root / (tag + ".bin")
                path.write_bytes(payload)
                rows.append(dict(tag=tag, bytes=len(payload), offset=len(data), reference=str(path), sha256=hashlib.sha256(payload).hexdigest()))
                ref = "r" + str(index)
                occurrences.append({"tag": {"name": tag}, "origin": {"resourceRef": ref},
                    "values": {"raw": {"value": {"resourceRef": ref}}, "normalized": {"value": {"resourceRef": ref}}}})
                resources.append({"id": ref, "byteLength": str(len(payload)), "mediaType": "image/jpeg",
                    "content": {"kind": "source-ranges", "ranges": [{"offset": str(len(data)), "length": str(len(payload)), "ref": "src-raw", "space": "source"}]}})
                data += payload
            source = root / "source.cr3"
            source.write_bytes(data)
            document = {"files": [{"snapshot": {"occurrences": occurrences, "resources": resources, "coverage": [{"state": "partial"}]}}]}
            audit.resource_check(document, source, rows)
            measure.verify_extents({"fixture": {"input": str(source)}, "resources": rows})
            altered = copy.deepcopy(document)
            altered["files"][0]["snapshot"]["resources"][0]["content"]["ranges"][0]["length"] = "13"
            with self.assertRaises(ValueError):
                audit.resource_check(altered, source, rows)
            source.write_bytes(data[:-1] + b"X")
            with self.assertRaises(ValueError):
                audit.resource_check(document, source, rows)
            with self.assertRaises(ValueError):
                measure.verify_extents({"fixture": {"input": str(source)}, "resources": rows})

    def test_inventory_retains_unexpected_files(self):
        with tempfile.TemporaryDirectory(dir=measure.ROOT / ".local") as folder:
            path = Path(folder) / "retained.tmp"
            path.write_bytes(b"retained-partial")
            self.assertEqual(measure.inventory(Path(folder))[path.name]["bytes"], 16)

    def test_post_process_faults_retain_actual_attempt_and_available_captures(self):
        for fault in ("namespace", "capture"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory(dir=measure.ROOT / ".local") as folder:
                root = Path(folder).resolve()
                (root / "protocol.private.json").write_text(json.dumps({"binary": "authored.exe", "fixture": {"input": "authored"}}))
                sample = {"outcome": "exited", "exitCode": 0}
                original_write = Path.write_bytes
                def write(path, data):
                    if fault == "capture" and path.name.endswith(".stdout"):
                        raise OSError("authored capture failure")
                    return original_write(path, data)
                calls = []
                def inventory(_):
                    calls.append(1)
                    if fault == "namespace" and len(calls) == 2:
                        raise OSError("authored namespace failure")
                    return {}
                with patch.object(measure, "rights"), patch.object(measure, "source_check", return_value={}), \
                     patch.object(measure, "verify_extents"), patch.object(measure, "inventory", side_effect=inventory), \
                     patch.object(measure.preview, "argv_for", return_value=["authored"]), \
                     patch.object(measure.telemetry, "Observer") as observer, \
                     patch.object(measure.b, "run_process", return_value=(sample, b"authored-output", b"")) as run, \
                     patch.object(Path, "write_bytes", write):
                    observer.return_value.report.return_value = {"valid": False}
                    with self.assertRaisesRegex(ValueError, "actual outcome retained"):
                        measure.collect(root)
                record = json.loads((root / "record.private.json").read_text())
                self.assertEqual(run.call_count, 1)
                self.assertEqual(record["remainingAttempts"], 47)
                retained = record["cells"][0]["attempts"][0]
                self.assertEqual(retained["outcome"], "exited")
                self.assertFalse(retained["eligible"])
                self.assertTrue(retained["finalizationErrors"])
                self.assertTrue((root / "captures/c0-a0.stderr").is_file())
                if fault == "namespace":
                    self.assertEqual((root / "captures/c0-a0.stdout").read_bytes(), b"authored-output")
                self.assertEqual(json.loads((root / "attempt-c0-a0.private.json").read_text())["sample"], retained)

    def test_independent_execution_and_consumer_binding_rejects_tampering(self):
        with tempfile.TemporaryDirectory(dir=measure.ROOT / ".local") as folder:
            root = Path(folder).resolve()
            (root / "captures").mkdir()
            p = {"binary": str(root / "authored.exe"), "fixture": {"input": "authored.cr3"}, "fixedUtc": "2026-10-16T00:00:00+00:00"}
            sample = dict(argv=[p["binary"], "binary", "list", "--output", "json", "--max-bytes", "8388608", "--", "authored.cr3"],
                cwd=str(root), operation="list", tag=None, expected="success", index=0, phase="warmup", target=None,
                startOffsetNs=10, endOffsetNs=40, elapsedNs=20, startedUtc="2026-10-17T00:00:00+00:00", outcome="exited", exitCode=0,
                censored=False, finalizationErrors=[], captures={})
            for channel in ("stdout", "stderr"):
                name = f"captures/c0-a0.{channel}"
                (root / name).write_bytes(b"authored" if channel == "stdout" else b"")
                data = (root / name).read_bytes()
                sample["captures"][channel] = name
                sample.update({channel+"Bytes": len(data), channel+"CapturedBytes": len(data), channel+"Sha256": hashlib.sha256(data).hexdigest()})
            path = root / "attempt-c0-a0.private.json"
            path.write_text(json.dumps({"sample": sample, "telemetry": {}}))
            audit.attempt_check(root, p, 0, 0, "list", None, sample, {}, 0)
            for key, value, error in (("argv", ["wrong"], "argv/cwd"), ("cwd", "wrong", "argv/cwd"),
                    ("startOffsetNs", -1, "start/end"), ("elapsedNs", 99, "start/end"),
                    ("stdoutBytes", 99, "capture completeness"), ("censored", True, "censor")):
                changed = copy.deepcopy(sample)
                changed[key] = value
                # Rebind the attempt file: the independent invariant must still fail.
                path.write_text(json.dumps({"sample": changed, "telemetry": {}}))
                with self.assertRaisesRegex(ValueError, error):
                    audit.attempt_check(root, p, 0, 0, "list", None, changed, {}, 0)
            path.write_text(json.dumps({"sample": sample, "telemetry": {"changed": True}}))
            with self.assertRaisesRegex(ValueError, "per-attempt record"):
                audit.attempt_check(root, p, 0, 0, "list", None, sample, {}, 0)
            later = dict(p, fixedUtc="2026-10-18T00:00:00+00:00")
            with self.assertRaisesRegex(ValueError, "preregistration"):
                audit.attempt_check(root, later, 0, 0, "list", None, sample, {}, 0)

    def test_exact_evidence_namespaces_reject_missing_and_extra_entries(self):
        with tempfile.TemporaryDirectory(dir=measure.ROOT / ".local") as folder:
            root = Path(folder)
            (root / "captures").mkdir()
            for ci in range(4):
                for index in range(12):
                    (root / f"attempt-c{ci}-a{index}.private.json").write_text("{}")
                    for channel in ("stdout", "stderr"):
                        (root / f"captures/c{ci}-a{index}.{channel}").write_bytes(b"")
            audit.evidence_namespace_check(root)
            for relative, error in (("captures/extra.stdout", "capture namespace"),
                    ("attempt-c9-a99.private.json", "attempt-record namespace")):
                extra = root / relative
                extra.write_bytes(b"")
                with self.assertRaisesRegex(ValueError, error):
                    audit.evidence_namespace_check(root)
                extra.unlink()
            for relative, error in (("captures/c0-a0.stdout", "capture namespace"),
                    ("attempt-c0-a0.private.json", "attempt-record namespace")):
                missing = root / relative
                data = missing.read_bytes()
                missing.unlink()
                with self.assertRaisesRegex(ValueError, error):
                    audit.evidence_namespace_check(root)
                missing.write_bytes(data)


if __name__ == "__main__":
    unittest.main()
