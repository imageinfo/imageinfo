"""Collector and versioned record QA; jsonschema is a test-only dependency."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

from jsonschema import Draft202012Validator

import read_benchmark as b

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs/performance/read-collector"


class CollectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = b.load(DATA / "record.schema.json", 100000)
        Draft202012Validator.check_schema(cls.schema)
        cls.validator = Draft202012Validator(cls.schema)
        cls.vector = b.load(DATA / "synthetic-record.v1.json")

    def test_schema_positive_vector(self):
        self.validator.validate(self.vector)

    def test_schema_rejects_bad_records(self):
        mutations = [
            lambda v: v.update(schemaVersion=2),
            lambda v: v.update(unreviewed=True),
            lambda v: v.update(driverSha256="not-a-sha"),
            lambda v: v["attempts"][0].update(elapsedNs=-1),
            lambda v: v["attempts"][0].update(phase="warmup", eligible=True),
            lambda v: v["attempts"][0].update(outcome="timeout", censored=False),
            lambda v: v["attempts"][0].update(outcome="timeout", correctness="pass"),
            lambda v: v["unavailableTelemetry"].update(peakMemoryBytes=0),
            lambda v: v["configuration"].update(repeats=101),
            lambda v: v["configuration"].update(captureBytes=4194305),
            lambda v: v.pop("cache"),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                value = copy.deepcopy(self.vector)
                mutate(value)
                self.assertTrue(list(self.validator.iter_errors(value)))

    def test_config_refuses_unbounded_and_unknown(self):
        for field, value in (("repeats", 0), ("timeoutMs", True),
                             ("timeoutMs", 60001), ("captureBytes", 0),
                             ("warmups", 11), ("binarySha256", "x")):
            c = copy.deepcopy(self.vector["configuration"])
            c[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                b.check_config(c)
        c["unknown"] = 1
        with self.assertRaises(ValueError):
            b.check_config(c)

    def test_existing_record_never_overwrites_source(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".local") as directory:
            source = Path(directory) / "source"
            source.write_bytes(b"source bytes")
            with self.assertRaisesRegex(ValueError, "fresh"):
                b.collect(self.vector["configuration"], source)
            self.assertEqual(source.read_bytes(), b"source bytes")

    def run_child(self, script, deadline=2000, cap=8192):
        return b.run_process([sys.executable, "-c", script], str(ROOT),
                             dict(os.environ), deadline, cap)

    def test_actual_drain_nonzero_and_invalid_output(self):
        r, stdout, stderr = self.run_child("import sys; print('invalid json'); print('error',file=sys.stderr); sys.exit(7)")
        self.assertEqual((r["outcome"], r["exitCode"], r["censored"]), ("exited", 7, False))
        self.assertEqual(r["stdoutBytes"], len(stdout))
        self.assertEqual(r["stderrBytes"], len(stderr))
        self.assertGreater(r["elapsedNs"], 0)
        with self.assertRaises(ValueError):
            json.loads(stdout)

    def test_actual_timeout_retains_censoring(self):
        r, _, _ = self.run_child("import time; time.sleep(10)", deadline=30)
        self.assertEqual(r["outcome"], "timeout")
        self.assertTrue(r["censored"])
        self.assertGreaterEqual(r["elapsedNs"], 30_000_000)
        self.assertLess(r["elapsedNs"], 3_000_000_000)

    def test_actual_output_limit_is_bounded(self):
        r, stdout, stderr = self.run_child("import sys; sys.stdout.buffer.write(b'x'*1000000); sys.stdout.flush()", cap=1024)
        self.assertEqual(r["outcome"], "output-limit")
        self.assertTrue(r["censored"])
        self.assertLessEqual(len(stdout), 1024)
        self.assertLessEqual(len(stderr), 1024)
        self.assertGreater(r["stdoutBytes"], len(stdout))

    def test_actual_launch_error(self):
        r, _, _ = b.run_process([str(ROOT / "does-not-exist-benchmark-tool")], str(ROOT), {}, 100, 1024)
        self.assertEqual(r["outcome"], "launch-error")
        self.assertIsNone(r["exitCode"])
        self.assertFalse(r["censored"])

    def test_bounded_json_load(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".local") as directory:
            path = Path(directory) / "large.json"
            path.write_bytes(b" " * 100)
            with self.assertRaisesRegex(ValueError, "bound"):
                b.load(path, 10)


if __name__ == "__main__":
    unittest.main()
