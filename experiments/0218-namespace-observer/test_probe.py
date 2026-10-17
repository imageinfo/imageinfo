"""Mocked access-interface controls; these never open a native source."""

import errno
import unittest
from unittest.mock import patch

import probe


class ProbeTests(unittest.TestCase):
    def simulate(self, failure=None, expected_access=False):
        snapshot = {
            "status": "ok", "observations_match": True,
            "sha256": "a" * 64, "path_before": {"authored": True},
        }
        with (
            patch.object(probe, "read_snapshot", return_value=snapshot),
            patch.object(probe.os, "open", return_value=123, side_effect=failure) as opened,
            patch.object(probe.os, "fstat"),
            patch.object(probe, "_stat", return_value={"authored": True}),
            patch.object(probe.os, "close") as closed,
        ):
            result = probe.write_open_probe("authored", expected_access=expected_access)
            self.assertFalse(opened.call_args.args[1] & (
                probe.os.O_CREAT | probe.os.O_TRUNC | probe.os.O_APPEND
            ))
            self.assertEqual(closed.call_count, 0 if failure else 1)
            return result

    def test_crt_eacces_is_accurately_labeled_without_invented_winerror(self):
        result = self.simulate(PermissionError(errno.EACCES, "authored CRT denial"))
        self.assertTrue(result["expectation_met"])
        self.assertEqual(result["error"]["errno"], errno.EACCES)
        self.assertIsNone(result["error"]["winerror"])
        self.assertEqual(result["denial_observation"], "crt_eacces_without_native_error")

    def test_native_sharing_error_retained(self):
        failure = PermissionError(errno.EACCES, "authored native denial")
        failure.winerror = 32
        result = self.simulate(failure)
        self.assertTrue(result["expectation_met"])
        self.assertEqual(result["error"]["winerror"], 32)
        self.assertEqual(result["denial_observation"], "win32_sharing_violation")

    def test_other_native_denial_not_reclassified(self):
        failure = PermissionError(errno.EACCES, "authored other denial")
        failure.winerror = 5
        result = self.simulate(failure)
        self.assertFalse(result["expectation_met"])
        self.assertIsNone(result["denial_observation"])

    def test_missing_source_not_held_evidence(self):
        self.assertFalse(self.simulate(FileNotFoundError(errno.ENOENT, "missing"))["expectation_met"])

    def test_opened_baseline(self):
        result = self.simulate(expected_access=True)
        self.assertTrue(result["expectation_met"])
        self.assertIsNone(result["denial_observation"])

    def test_opened_source_not_held_evidence(self):
        self.assertFalse(self.simulate()["expectation_met"])


if __name__ == "__main__":
    unittest.main()
