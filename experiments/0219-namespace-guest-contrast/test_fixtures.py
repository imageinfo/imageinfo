"""Tiny authored preparation/snapshot controls; no native bridge or worker."""
from __future__ import annotations

from copy import deepcopy
import errno
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import fixtures


class FixtureControls(unittest.TestCase):
    def setUp(self):
        parent = Path(__file__).resolve().parents[2] / ".local" / "0219-authored-tests"
        parent.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="fixtures-", dir=parent)
        self.addCleanup(self.temporary.cleanup)
        self.parent = Path(self.temporary.name)
        for name, count in (("SOURCE_BYTES", 19), ("CANDIDATE_BYTES", 7)):
            selected = patch.object(fixtures, name, count)
            selected.start()
            self.addCleanup(selected.stop)

    def prepare(self, case="persistent-write-error", name="fresh", **kwargs):
        kwargs.setdefault("preparation_mode", "authored_model_seed")
        return fixtures.prepare_fixture(self.parent / name, case, **kwargs)

    def test_fresh_exact_source_and_candidate_extent_hash(self):
        for case in ("persistent-write-error", "no-error"):
            with self.subTest(case=case):
                with patch.object(fixtures.os, "fsync", side_effect=AssertionError("preparation fsync forbidden")):
                    manifest = self.prepare(case, name=case, unit="attempt_219")
                source = Path(manifest["source"])
                self.assertEqual(source.read_bytes(), b"S" * 19)
                self.assertEqual(manifest["sourceBytes"], 19)
                self.assertEqual(manifest["candidateBytes"], 7)
                self.assertEqual(manifest["sourceSha256"], hashlib.sha256(b"S" * 19).hexdigest())
                self.assertEqual(manifest["candidateSha256"], hashlib.sha256(b"\x18" * 7).hexdigest())
                self.assertFalse((source.parent / "fixture.private.json").exists())
                self.assertEqual({entry.name for entry in source.parent.iterdir()},
                                 {"source.bin", "fixture219.marker"})
                self.assertFalse(manifest["manifestPersistedOnTestVolume"])
                self.assertTrue(manifest["historicalMetadataPreparationChanged"])
                self.assertEqual(manifest["requiredWorkerMarker"], {
                    "path": str(source.parent / "fixture219.marker"),
                    "bytes": len(fixtures.MARKER),
                    "sha256": hashlib.sha256(fixtures.MARKER).hexdigest(),
                })
                self.assertEqual((source.parent / "fixture219.marker").read_bytes(),
                                 b"imageinfo-0219-disposable-authored-only-v1\n")
                self.assertEqual(manifest["unit"], "attempt_219")
                self.assertEqual(manifest["transactionDir"], "unit")
                self.assertFalse(Path(manifest["candidate"]).exists())
                self.assertFalse(Path(manifest["output"]).exists())
                self.assertFalse((source.parent / "unit").exists())
                self.assertFalse(manifest["cleanupAuthorized"])
                original = manifest["originalInventory"]
                self.assertEqual(original["root"]["status"], "error")
                self.assertEqual(original["volume"]["status"], "ok")
                self.assertEqual(original["unit"]["status"], "error")
                self.assertNotEqual(manifest["old"], manifest["source"])
                self.assertEqual(Path(manifest["old"]), source.parent.parent / "source.bin")
                for name in fixtures.NAMES:
                    lookup = original["paths"][name]
                    self.assertEqual(lookup["status"], "error")
                    self.assertEqual(lookup["error"]["errno"], errno.ENOENT)
                    self.assertEqual(lookup["path"], manifest[name])
                self.assertEqual(original["paths"]["old"]["status"], "ok")
                self.assertEqual(manifest["sourceMove"]["identityBefore"], manifest["sourceMove"]["identityAfter"])
                self.assertTrue(manifest["sourceMove"]["sameObject"])
                self.assertFalse(Path(manifest["old"]).exists())
                prepared = manifest["preparedInventory"]
                self.assertEqual(prepared["volume"]["status"], "ok")
                self.assertEqual(prepared["root"]["status"], "ok")
                self.assertEqual(prepared["paths"]["old"]["status"], "error")
                self.assertEqual(prepared["paths"]["old"]["error"]["errno"], errno.ENOENT)
                self.assertEqual(prepared["paths"]["source"]["status"], "ok")
                self.assertEqual(prepared["paths"]["preparedSource"], prepared["paths"]["source"])
                self.assertEqual(manifest["sourceMove"]["before"]["sha256"], manifest["sourceSha256"])
                self.assertEqual(manifest["sourceMove"]["after"]["sha256"], manifest["sourceSha256"])
                self.assertFalse(manifest["explicitPreparationFlush"])
                self.assertFalse(manifest["durablePreparationAcknowledged"])

    def test_existing_root_preserves_source_and_foreign_bytes(self):
        root = self.parent / "occupied"
        root.mkdir()
        (root / "source.bin").write_bytes(b"unrelated source")
        (root / "foreign.bin").write_bytes(b"unrelated foreign")
        before = {path.name: path.read_bytes() for path in root.iterdir()}
        with self.assertRaises(FileExistsError):
            fixtures.prepare_fixture(root, "no-error")
        self.assertEqual({path.name: path.read_bytes() for path in root.iterdir()}, before)

    def test_relative_and_traversing_roots_refuse_without_effects(self):
        for root in (Path("relative-219"), self.parent / ".." / "traversal-219"):
            with self.subTest(root=root), self.assertRaises(ValueError):
                fixtures.prepare_fixture(root, "no-error")
        self.assertFalse((self.parent.parent / "traversal-219").exists())

    def test_invalid_case_and_attempt_tokens_create_nothing(self):
        invalid = (("undeclared", "unit"), ("no-error", "../alias"),
                   ("no-error", "a/b"), ("no-error", "a\\b"),
                   ("no-error", ""), ("no-error", "x" * 65),
                   ("no-error", "ユニット"))
        for case, unit in invalid:
            root = self.parent / "refused"
            with self.subTest(case=case, unit=unit), self.assertRaises(ValueError):
                fixtures.prepare_fixture(root, case, unit=unit)
            self.assertFalse(root.exists())

    def test_observed_alias_ancestor_refuses_before_creation(self):
        alias = self.parent / "alias"
        alias.mkdir()
        original = fixtures._plain

        def plain(path, *, directory):
            if path == alias:
                raise ValueError("symlink/reparse fixture path refused")
            return original(path, directory=directory)

        with patch.object(fixtures, "_plain", side_effect=plain):
            with self.assertRaises(ValueError):
                fixtures.prepare_fixture(alias / "fresh", "no-error")
        self.assertFalse((alias / "fresh").exists())

    def test_extent_bounds_refuse_before_creating_root(self):
        for name, values in (("SOURCE_BYTES", (0, True, 16 * 1024 * 1024 + 1)),
                             ("CANDIDATE_BYTES", (0, True, 4 * 1024 * 1024 + 1))):
            for value in values:
                with self.subTest(name=name, value=value), patch.object(fixtures, name, value):
                    with self.assertRaises(ValueError):
                        self.prepare()
                    self.assertFalse((self.parent / "fresh").exists())

    def test_postmove_observation_failure_retains_prepared_source(self):
        observe = fixtures._seed_observation

        def fail_moved_observation(path):
            if path == self.parent / "fresh" / "source.bin":
                raise OSError(errno.ENOSPC, "authored preparation failure")
            return observe(path)

        with patch.object(fixtures, "_seed_observation", side_effect=fail_moved_observation):
            with self.assertRaises(OSError):
                self.prepare()
        root = self.parent / "fresh"
        self.assertEqual((root / "fixture219.marker").read_bytes(), fixtures.MARKER)
        self.assertEqual((root / "source.bin").read_bytes(), b"S" * 19)
        self.assertFalse((self.parent / "source.bin").exists())
        self.assertFalse((root / "fixture.private.json").exists())
        self.assertFalse((root / "unit").exists())

    def test_marker_write_failure_retains_original_source_and_partial_case(self):
        with patch.object(fixtures, "_write_new", side_effect=OSError(errno.ENOSPC, "authored marker failure")):
            with self.assertRaises(OSError):
                self.prepare()
        self.assertEqual((self.parent / "source.bin").read_bytes(), b"S" * 19)
        root = self.parent / "fresh"
        self.assertTrue(root.is_dir())
        self.assertEqual(list(root.iterdir()), [])

    def test_existing_offline_seed_moves_same_object_without_durability_call(self):
        old = self.parent / "source.bin"
        old.write_bytes(b"S" * 19)
        original = old.stat()
        foreign = self.parent / "foreign.bin"
        foreign.write_bytes(b"retain unrelated foreign")
        with patch.object(fixtures.os, "fsync", side_effect=AssertionError("preparation fsync forbidden")):
            manifest = self.prepare(preparation_mode="existing_offline_seed")
        source = Path(manifest["source"])
        self.assertEqual(source.read_bytes(), b"S" * 19)
        self.assertEqual((source.stat().st_dev, source.stat().st_ino), (original.st_dev, original.st_ino))
        self.assertFalse(old.exists())
        self.assertEqual(foreign.read_bytes(), b"retain unrelated foreign")
        self.assertEqual(manifest["old"], str(old))
        self.assertEqual(manifest["preparedSource"], str(source))
        self.assertEqual(manifest["preparationMode"], "existing_offline_seed")

    def test_default_requires_existing_seed_and_preserves_foreign_seed(self):
        root = self.parent / "fresh"
        with self.assertRaises((ValueError, FileNotFoundError)):
            fixtures.prepare_fixture(root, "no-error")
        self.assertFalse(root.exists())
        old = self.parent / "source.bin"
        old.write_bytes(b"foreign seed")
        with self.assertRaises(ValueError):
            fixtures.prepare_fixture(root, "no-error")
        self.assertEqual(old.read_bytes(), b"foreign seed")
        self.assertFalse(root.exists())
        with self.assertRaises(FileExistsError):
            self.prepare()
        self.assertEqual(old.read_bytes(), b"foreign seed")
        self.assertFalse(root.exists())

    def test_model_seed_and_move_failure_retain_original_and_partial_root(self):
        old = self.parent / "source.bin"
        with patch.object(fixtures.os, "rename", side_effect=OSError(errno.EACCES, "authored move failure")):
            with self.assertRaises(OSError):
                self.prepare()
        self.assertEqual(old.read_bytes(), b"S" * 19)
        self.assertTrue((self.parent / "fresh").is_dir())
        self.assertFalse((self.parent / "fresh" / "source.bin").exists())
        self.assertFalse((self.parent / "fresh" / "fixture.private.json").exists())

    def test_mocked_snapshot_preserves_uint64_nanoseconds_and_bridge_fields(self):
        manifest = self.prepare()
        (Path(manifest["root"]) / "unit").mkdir()
        raw = {
            "status": "ok", "observations_match": True,
            "sha256": hashlib.sha256(b"S" * 19).hexdigest(),
            "path_before": {"device": 2**63 + 17, "inode": 2**64 - 1,
                            "mtime_ns": 1_798_478_400_123_456_789,
                            "ctime_ns": 1_798_478_401_987_654_321,
                            "birthtime_ns": 1_798_478_399_222_333_444},
            "bridge_before": {"volume_serial_u32": 2**32 - 1,
                              "file_index_u64": 2**64 - 1},
            "identity_bridge_profile": "win32-bhfi-same-read-fd-v1",
        }
        expected = deepcopy(raw)
        calls = []

        def reader(path, *, max_bytes):
            calls.append((Path(path), max_bytes))
            return deepcopy(raw)

        with patch.object(fixtures, "_reader", side_effect=AssertionError("native reader forbidden")):
            snapshot = fixtures.snapshot_fixture(manifest, "candidate_hold", read_snapshot=reader)
        self.assertEqual(snapshot["paths"]["source"], expected)
        self.assertEqual(snapshot["paths"]["old"], expected)
        self.assertEqual(raw, expected)
        self.assertEqual(dict(calls)[Path(manifest["source"])], 19)
        self.assertEqual(len(calls), len(fixtures.NAMES) + 1)
        self.assertFalse(snapshot["cleanupAuthorized"])

    def test_old_and_prepared_native_lookup_errors_are_distinct(self):
        manifest = self.prepare()
        (Path(manifest["root"]) / "unit").mkdir()

        def reader(path, *, max_bytes):
            if path == Path(manifest["old"]):
                error = FileNotFoundError(errno.ENOENT, "authored old-name failure")
                error.winerror = 2
            elif path == Path(manifest["source"]):
                error = PermissionError(errno.EACCES, "authored prepared-name failure")
                error.winerror = 32
            else:
                return {"status": "authored-unused"}
            raise error

        snapshot = fixtures.snapshot_fixture(manifest, "cleared_hold", read_snapshot=reader)
        old = snapshot["paths"]["old"]
        prepared = snapshot["paths"]["source"]
        self.assertEqual(old["status"], "error")
        self.assertEqual(old["error"], {"type": "FileNotFoundError", "errno": errno.ENOENT, "winerror": 2})
        self.assertEqual(prepared["status"], "error")
        self.assertEqual(prepared["error"], {"type": "PermissionError", "errno": errno.EACCES, "winerror": 32})
        self.assertEqual(old["path"], manifest["old"])
        self.assertEqual(prepared["path"], manifest["source"])

    def test_missing_unit_lookup_remains_explicit_and_source_foreign_unchanged(self):
        manifest = self.prepare()
        root = Path(manifest["root"])
        foreign = root / "foreign.bin"
        foreign.write_bytes(b"foreign must survive")
        before = {path.name: path.read_bytes() for path in root.iterdir()}
        calls = []

        def reader(path, *, max_bytes):
            calls.append(Path(path))
            return {"status": "ok", "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

        snapshot = fixtures.snapshot_fixture(manifest, "prepared", read_snapshot=reader)
        self.assertEqual(set(calls), {Path(manifest["source"]), Path(manifest["old"])})
        self.assertEqual(snapshot["paths"]["old"]["status"], "error")
        self.assertEqual(snapshot["paths"]["old"]["error"]["errno"], errno.ENOENT)
        self.assertEqual(snapshot["paths"]["source"]["status"], "ok")
        self.assertEqual(snapshot["paths"]["source"]["sha256"], manifest["sourceSha256"])
        for name in ("candidate", "output", "prepared", "intent", "observation", "receipt"):
            with self.subTest(name=name):
                self.assertEqual(snapshot["paths"][name]["status"], "error")
                self.assertEqual(snapshot["paths"][name]["error"]["errno"], errno.ENOENT)
        self.assertEqual(snapshot["directories"]["unit"]["status"], "error")
        self.assertEqual({path.name: path.read_bytes() for path in root.iterdir()}, before)

    def test_snapshot_path_or_phase_refusal_never_calls_reader(self):
        manifest = self.prepare()
        for changes, phase in (({"source": str(self.parent / "foreign")}, "prepared"),
                               ({"old": str(self.parent / "foreign")}, "prepared"),
                               ({}, "unknown")):
            with self.subTest(changes=changes, phase=phase):
                with patch.object(fixtures, "_reader", side_effect=AssertionError("reader forbidden")):
                    with self.assertRaises(ValueError):
                        fixtures.snapshot_fixture(dict(manifest, **changes), phase)

    def test_directory_inventory_bound_is_explicit_and_retains_foreign_entries(self):
        manifest = self.prepare()
        unit = Path(manifest["root"]) / "unit"
        unit.mkdir()
        for index in range(4):
            (unit / f"foreign-{index}").write_bytes(bytes((index,)))
        before = {path.name: path.read_bytes() for path in unit.iterdir()}
        with patch.object(fixtures, "MAX_ENTRIES", 3):
            snapshot = fixtures.snapshot_fixture(manifest, "final", read_snapshot=lambda path, **kw: {"status": "mock"})
        self.assertEqual(snapshot["directories"]["unit"]["status"], "refused")
        self.assertEqual(snapshot["directories"]["unit"]["reason"], "directory_entry_bound")
        self.assertEqual(len(snapshot["directories"]["unit"]["entries"]), 3)
        self.assertEqual({path.name: path.read_bytes() for path in unit.iterdir()}, before)


if __name__ == "__main__":
    unittest.main()
