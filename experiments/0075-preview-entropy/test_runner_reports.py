"""Authored report transport controls; no codec, producer or media access."""
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest import mock
import uuid

import run as runner
from run import (Limits, WORKER_REPORT_LIMIT, read_worker_report,
                 retain_worker_report, run_process)

HERE = Path(__file__).resolve().parent
AUTHORED_REPORT_CHILD = (
    "import json,sys; from pathlib import Path; "
    "sys.path.insert(0,sys.argv[1]); from run import retain_worker_report; "
    "r={'schema':'imageinfo-0075-worker-v1','decoder':"
    "{'outcome':'authored-diagnostic-control','diagnostic':'X'*20000}}; "
    "b=retain_worker_report(r,Path(sys.argv[2])); "
    "print(json.dumps(b,sort_keys=True,separators=(',',':')))"
)


class WorkerReports(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.suite_root = HERE.parent.parent / ".local" / "0075-report-controls" / uuid.uuid4().hex
        cls.suite_root.mkdir(parents=True, exist_ok=False)

    def setUp(self):
        self.root = self.suite_root / self._testMethodName
        self.root.mkdir(exist_ok=False)
        self.report = {"schema": "imageinfo-0075-worker-v1",
                       "decoder": {"outcome": "authored-diagnostic-control",
                                   "diagnostic": "X" * 20000}}

    def test_large_report_actual_subprocess_preserves_fixed_capture(self):
        process_root = self.root / "process"
        result = run_process([sys.executable, "-I", "-c", AUTHORED_REPORT_CHILD,
                              str(HERE), str(self.root)], process_root, Limits())
        self.assertEqual(result["outcome"], "exited")
        self.assertEqual(result["returncode"], 0)
        self.assertTrue(result["terminationConfirmed"])
        for row in result["streams"].values():
            self.assertTrue(row["eof"])
            self.assertFalse(row["overflow"])
        raw = (process_root / "stdout.bin").read_bytes()
        self.assertLess(len(raw), 16384)
        binding = json.loads(raw)
        self.assertEqual(set(binding), {"path", "sha256", "byteLength"})
        self.assertGreater(binding["byteLength"], 16384)
        self.assertEqual(read_worker_report(binding, self.root), self.report)
        report_raw = (self.root / "worker-report.json").read_bytes()
        self.assertEqual(binding["sha256"], hashlib.sha256(report_raw).hexdigest())
        self.assertEqual(binding["byteLength"], len(report_raw))
        self.assertEqual((process_root / "stderr.bin").read_bytes(), b"")

    def test_cell_supervisor_binds_full_report_from_small_capture(self):
        source = self.root / "authored-marker.bin"
        source.write_bytes(b"authored report transport marker")
        binding = {"path": str(source), "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                   "byteLength": source.stat().st_size}
        request = {"stage": "authored", "interpreter": sys.executable,
                   "input": binding, "recipeBindings": [],
                   "runtimeManifest": binding, "profile": binding}
        admitted = {"before": runner._stat(source)}

        def transport_child_only(_command, process_root, limits, **kwargs):
            return run_process([sys.executable, "-I", "-c", AUTHORED_REPORT_CHILD,
                                str(HERE), str(process_root.parent)],
                               process_root, limits, **kwargs)

        # This authored transport seam does not authorize or invoke decoder
        # admission. The real subprocess constructs only the synthetic report.
        with mock.patch.object(runner, "admit_request", return_value=admitted), \
                mock.patch.object(runner, "run_process", side_effect=transport_child_only):
            result = runner.run_cell(request, self.root / "cell")
        self.assertEqual(result["outcome"], "authored-diagnostic-control")
        self.assertEqual(result["worker"], self.report)
        stdout = (self.root / "cell/process/stdout.bin").read_bytes()
        self.assertEqual(result["workerReportBinding"], json.loads(stdout))
        self.assertLess(len(stdout), 16384)
        self.assertGreater(result["workerReportBinding"]["byteLength"], 16384)
        self.assertTrue(result["immutableObservation"])

    def test_exclusive_report_retains_original(self):
        binding = retain_worker_report(self.report, self.root)
        with self.assertRaises(FileExistsError):
            retain_worker_report({"schema": "different"}, self.root)
        self.assertEqual(read_worker_report(binding, self.root), self.report)

    def test_wrong_path_rejected_even_with_same_bytes(self):
        binding = retain_worker_report(self.report, self.root)
        other = self.root / "other.json"
        other.write_bytes((self.root / "worker-report.json").read_bytes())
        with self.assertRaises(ValueError):
            read_worker_report(dict(binding, path=str(other)), self.root)

    def test_changed_report_rejected(self):
        binding = retain_worker_report(self.report, self.root)
        (self.root / "worker-report.json").write_bytes(b"{}")
        with self.assertRaises(ValueError):
            read_worker_report(binding, self.root)

    def test_wrong_hash_or_length_rejected(self):
        binding = retain_worker_report(self.report, self.root)
        for wrong in (dict(binding, sha256="0" * 64),
                      dict(binding, byteLength=binding["byteLength"] + 1),
                      dict(binding, byteLength=WORKER_REPORT_LIMIT + 1)):
            with self.assertRaises(ValueError):
                read_worker_report(wrong, self.root)

    def test_report_bound_refuses_before_creation(self):
        with self.assertRaises(ValueError):
            retain_worker_report({"diagnostic": "X" * WORKER_REPORT_LIMIT}, self.root)
        self.assertFalse((self.root / "worker-report.json").exists())

    def test_missing_report_or_wrong_schema_rejected(self):
        with self.assertRaises((ValueError, FileNotFoundError)):
            read_worker_report({"path": "worker-report.json",
                                "sha256": "0" * 64, "byteLength": 0}, self.root)
        binding = retain_worker_report({"schema": "unexpected"}, self.root)
        with self.assertRaises(ValueError):
            read_worker_report(binding, self.root)


if __name__ == "__main__":
    unittest.main()
