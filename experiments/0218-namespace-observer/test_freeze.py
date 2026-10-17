"""Authored byte-only freeze controls; no worker, native probe or fixture run.

Manifest controls mock the read-only Git inventory query against an authored tree.
Separate Git-blob controls exercise exact raw-byte identity from authored replies.
No operational records, source media or native backend are used.
"""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import freeze


class FreezeControls(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="imageinfo218-freeze-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        names = ["Cargo.toml", "Cargo.lock", ".gitattributes", "src/storage/namespace_diagnostic.rs",
                 "src/storage/windows.rs", "src/storage/runtime.rs"]
        names += ["crates/imageinfo-windows-storage/Cargo.toml", "crates/imageinfo-windows-storage/src/lib.rs",
                  "crates/imageinfo-windows-storage/src/native.rs", "crates/imageinfo-windows-storage/src/windows.rs"]
        names += [freeze.EXPERIMENT + "/" + name + ".py" for name in
                  ("freeze", "protocol", "controller", "run", "audit", "fixtures", "probe")]
        for name in names:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"authored source\n")
        self.worker = self.root / "not-executed-worker.exe"
        self.worker.write_bytes(b"authored inert bytes")
        self.plan_path = self.root / "plan.json"
        self.plan = {"schema": freeze.PLAN_SCHEMA, "executable": str(self.worker), "argv": [str(self.worker)],
                     "cases": ["normal", "candidate-collision"], "bounds": {"deadline_seconds": 30,
                     "stdout_bytes": 1048576, "stderr_bytes": 65536, "line_bytes": 32768,
                     "events": 128, "command_bytes": 1024, "commands": 128}}
        self.plan_path.write_bytes(json.dumps(self.plan).encode())
        self.git_patch = patch.object(freeze, "_published_sources", return_value="a" * 40)
        self.git_patch.start()
        self.addCleanup(self.git_patch.stop)
        self.manifest = freeze.build_manifest(self.root, self.worker, self.plan_path)
        self.freeze_path = self.root / "freeze.json"
        self.freeze_path.write_bytes(json.dumps(self.manifest).encode())
        self.review_path = self.root / "review.json"
        self.review = {"schema": freeze.REVIEW_SCHEMA, "decision": "approved", "scope": "two-native-controls-only",
                       "reviewer": "authored control only", "plan_sha256": self.manifest["plan"]["sha256"],
                       "freeze_sha256": freeze._sha(self.freeze_path.read_bytes())}
        self.review_path.write_bytes(json.dumps(self.review).encode())
        # Every tamper control starts from a demonstrably accepted baseline.
        self.verify()

    def verify(self):
        return freeze.verify_reviewed(self.plan_path, self.freeze_path, self.review_path)

    def test_positive_exact_and_no_implicit_review(self):
        self.assertEqual(self.verify()["worker_sha256"], self.manifest["worker"]["sha256"])
        self.assertNotIn("approved", self.manifest)
        before = set(self.root.rglob("*"))
        freeze.build_manifest(self.root, self.worker, self.plan_path)
        self.assertEqual(before, set(self.root.rglob("*")))

    def test_worker_changes_refuse(self):
        self.worker.write_bytes(b"changed inert bytes")
        with self.assertRaises(freeze.FreezeError):
            self.verify()

    def test_plan_changes_refuse(self):
        self.plan_path.write_bytes(self.plan_path.read_bytes() + b" ")
        with self.assertRaises(freeze.FreezeError):
            self.verify()

    def test_raw_crlf_refuses(self):
        (self.root / "Cargo.toml").write_bytes(b"authored source\r\n")
        with self.assertRaises(freeze.FreezeError):
            self.verify()

    def test_source_changes_refuse(self):
        (self.root / "Cargo.toml").write_bytes(b"changed source\n")
        with self.assertRaises(freeze.FreezeError):
            self.verify()

    def test_inventory_omission_duplicate_extra_refuses(self):
        for mutate in (lambda x: x.pop(), lambda x: x.append(x[0]),
                       lambda x: x.append({"path": "../escape", "bytes": 0, "sha256": "0" * 64})):
            manifest = copy.deepcopy(self.manifest)
            mutate(manifest["sources"])
            with self.assertRaises(freeze.FreezeError):
                freeze.verify_manifest(manifest)

    def test_new_source_refuses(self):
        (self.root / freeze.EXPERIMENT / "new.py").write_bytes(b"added source\n")
        with self.assertRaises(freeze.FreezeError):
            self.verify()

    def test_changed_exact_review_refuses(self):
        for key, value in (("decision", "pending"), ("scope", "anything"), ("freeze_sha256", "0" * 64)):
            review = dict(self.review, **{key: value})
            self.review_path.write_bytes(json.dumps(review).encode())
            with self.assertRaises(freeze.FreezeError):
                self.verify()

    def test_malformed_json_refuses(self):
        for raw in (b'{"duplicate":1,"duplicate":2}', b'{"value":NaN}', b'[]'):
            with self.assertRaises(freeze.FreezeError):
                freeze._json(raw)

    def test_bound_bool_nan_and_extra_case_refuse(self):
        for key, value in (("events", True), ("deadline_seconds", float("nan")), ("line_bytes", 32769)):
            plan = copy.deepcopy(self.plan)
            plan["bounds"][key] = value
            with self.assertRaises(freeze.FreezeError):
                freeze._validate_plan(plan, self.worker)
        plan = copy.deepcopy(self.plan)
        plan["cases"].append("undeclared")
        with self.assertRaises(freeze.FreezeError):
            freeze._validate_plan(plan, self.worker)


class GitBlobControls(unittest.TestCase):
    def test_exact_blob_modified_untracked_and_head_mismatch(self):
        with tempfile.TemporaryDirectory(prefix="imageinfo218-freeze-") as directory:
            root = Path(directory).resolve(strict=True)
            data = b"authored raw LF source\n"
            (root / "sample.rs").write_bytes(data)
            oid = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
            commit = "b" * 40
            records = b"100644 blob " + oid.encode() + b"\tsample.rs\0"
            def git(_root, args):
                return (commit + "\n").encode() if args[0] == "rev-parse" else records
            with patch.object(freeze, "_git", side_effect=git):
                self.assertEqual(freeze._published_sources(root, ["sample.rs"]), commit)
                with self.assertRaises(freeze.FreezeError):
                    freeze._published_sources(root, ["sample.rs"], "c" * 40)
                with self.assertRaises(freeze.FreezeError):
                    freeze._published_sources(root, ["sample.rs", "missing.rs"])
                (root / "sample.rs").write_bytes(b"changed source\n")
                with self.assertRaises(freeze.FreezeError):
                    freeze._published_sources(root, ["sample.rs"])

    def test_sha256_git_blob_and_nonregular(self):
        with tempfile.TemporaryDirectory(prefix="imageinfo218-freeze-") as directory:
            root = Path(directory).resolve(strict=True)
            data = b"source\n"
            (root / "sample.rs").write_bytes(data)
            oid = hashlib.sha256(b"blob 7\0" + data).hexdigest()
            commit = "b" * 64
            def git(_root, args):
                return ((commit + "\n").encode() if args[0] == "rev-parse" else
                        b"100644 blob " + oid.encode() + b"\tsample.rs\0")
            with patch.object(freeze, "_git", side_effect=git):
                self.assertEqual(freeze._published_sources(root, ["sample.rs"]), commit)
            with patch.object(freeze, "_git", side_effect=[(commit + "\n").encode(),
                 b"120000 blob " + oid.encode() + b"\tsample.rs\0"]):
                with self.assertRaises(freeze.FreezeError):
                    freeze._published_sources(root, ["sample.rs"])


if __name__ == "__main__":
    unittest.main()
