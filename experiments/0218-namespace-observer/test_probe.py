"""Mocked access-interface controls; these never open a native source."""

import errno
from copy import deepcopy
from io import BytesIO
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

import probe


class ProbeTests(unittest.TestCase):
    def snapshot(self, profile=probe.WINDOWS_3147):
        path_stat = {
            "device": 7, "inode": 11, "mode": 0o100666, "size": 3,
            "mtime_ns": 30, "ctime_ns": 10, "birthtime_ns": 10,
        }
        handle_stat = dict(path_stat, ctime_ns=20)
        if profile == probe.SAME_FIELDS:
            handle_stat = dict(path_stat)
        return {
            "status": "ok", "observations_match": True,
            "sha256": "a" * 64, "stat_profile": profile,
            "path_before": path_stat, "path_after": dict(path_stat),
            "handle_before": handle_stat, "handle_after": dict(handle_stat),
        }

    def simulate(self, failure=None, expected_access=False, *, before=None, after=None, opened_stat=None):
        before = self.snapshot() if before is None else before
        after = deepcopy(before) if after is None else after
        opened_stat = before["handle_before"] if opened_stat is None else opened_stat
        with (
            patch.object(probe, "read_snapshot", side_effect=[before, after]),
            patch.object(probe.os, "open", return_value=123, side_effect=failure) as opened,
            patch.object(probe.os, "fstat"),
            patch.object(probe, "_stat", return_value=opened_stat),
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

    def test_pinned_windows_profile_preserves_both_ctime_observations(self):
        snapshot = self.snapshot()
        unchanged = deepcopy(snapshot)
        self.assertNotEqual(snapshot["path_before"]["ctime_ns"], snapshot["handle_before"]["ctime_ns"])
        self.assertTrue(probe._observations_match(snapshot))
        self.assertEqual(snapshot, unchanged)

    def test_all_raw_within_api_fields_still_require_stability(self):
        for name in ("path_after", "handle_after"):
            for field in self.snapshot()[name]:
                snapshot = self.snapshot()
                snapshot[name][field] += 1
                with self.subTest(name=name, field=field):
                    self.assertFalse(probe._observations_match(snapshot))

    def test_every_shared_field_is_compared_between_apis(self):
        for field in probe.SHARED_FIELDS:
            snapshot = self.snapshot()
            snapshot["handle_before"][field] += 1
            snapshot["handle_after"][field] += 1
            with self.subTest(field=field):
                self.assertFalse(probe._observations_match(snapshot))

    def test_windows_requires_explicit_creation_time_and_path_semantics(self):
        for invalid in (None, 10.0, True):
            snapshot = self.snapshot()
            for name in probe.STAT_NAMES:
                snapshot[name]["birthtime_ns"] = invalid
            self.assertFalse(probe._observations_match(snapshot))
        snapshot = self.snapshot()
        snapshot["path_before"]["ctime_ns"] = 11
        snapshot["path_after"]["ctime_ns"] = 11
        self.assertFalse(probe._observations_match(snapshot))

    def test_unknown_or_other_interpreter_profiles_cannot_ignore_ctime(self):
        snapshot = self.snapshot()
        snapshot["stat_profile"] = probe.SAME_FIELDS
        self.assertFalse(probe._observations_match(snapshot))
        snapshot["stat_profile"] = "unsupported"
        self.assertFalse(probe._observations_match(snapshot))
        self.assertTrue(probe._observations_match(self.snapshot(probe.SAME_FIELDS)))

    def test_exact_interpreter_profile_selection(self):
        with (
            patch.object(probe.os, "name", "nt"),
            patch.object(probe.sys, "implementation", SimpleNamespace(name="cpython")),
            patch.object(probe.sys, "version_info", (3, 14, 7)),
        ):
            self.assertEqual(probe._stat_profile(), probe.WINDOWS_3147)
            with patch.object(probe.sys, "version_info", (3, 14, 8)):
                self.assertEqual(probe._stat_profile(), probe.SAME_FIELDS)
            with patch.object(probe.os, "name", "posix"):
                self.assertEqual(probe._stat_profile(), probe.SAME_FIELDS)

    def test_cross_probe_handle_change_is_not_hidden_by_stable_path_stats(self):
        before = self.snapshot()
        after = deepcopy(before)
        for name in ("handle_before", "handle_after"):
            after[name]["ctime_ns"] += 1
        self.assertTrue(probe._observations_match(after))
        result = self.simulate(expected_access=True, before=before, after=after)
        self.assertFalse(result["source_unchanged"])
        self.assertFalse(result["expectation_met"])

    def test_opened_write_handle_is_compared_to_read_handle_properties(self):
        snapshot = self.snapshot()
        self.assertTrue(self.simulate(expected_access=True)["expectation_met"])
        # Comparing to the path's creation-time alias would incorrectly pass.
        result = self.simulate(expected_access=True, opened_stat=snapshot["path_before"])
        self.assertFalse(result["expectation_met"])

    def test_read_snapshot_retains_raw_semantics_without_native_source(self):
        snapshot = self.snapshot()
        path_stat = SimpleNamespace(**{
            "st_dev": 7, "st_ino": 11, "st_mode": 0o100666, "st_size": 3,
            "st_mtime_ns": 30, "st_ctime_ns": 10, "st_birthtime_ns": 10,
        })
        handle_stat = SimpleNamespace(**dict(vars(path_stat), st_ctime_ns=20))
        selected = MagicMock()
        selected.lstat.return_value = path_stat
        selected.is_symlink.return_value = False
        source = MagicMock()
        source.read.side_effect = BytesIO(b"abc").read
        selected.open.return_value.__enter__.return_value = source
        with (
            patch.object(probe, "Path", return_value=selected),
            patch.object(probe.os, "fstat", return_value=handle_stat),
            patch.object(probe, "_stat_profile", return_value=probe.WINDOWS_3147),
        ):
            result = probe.read_snapshot("authored", max_bytes=3)
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["observations_match"])
        for name in probe.STAT_NAMES:
            self.assertEqual(result[name], snapshot[name])


if __name__ == "__main__":
    unittest.main()
