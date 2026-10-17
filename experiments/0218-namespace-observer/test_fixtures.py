"""Tiny authored fixture controls; no native worker or hold probe is invoked."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import fixtures
import protocol


def pause(**changes):
    event = dict(v=1, unit="unit", seq=9, kind="before_operation", stage="create-Candidate",
                 result=None, bindings=[], **dict.fromkeys(protocol.FLAGS, False))
    event.update(changes)
    return event


class FixtureControls(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[2] / ".local" / "0218-authored-tests"
        root.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="fixtures-", dir=root)
        self.addCleanup(self.temporary.cleanup)
        self.parent = Path(self.temporary.name)
        source_patch = patch.object(fixtures, "SOURCE_BYTES", 19)
        candidate_patch = patch.object(fixtures, "CANDIDATE_BYTES", 7)
        source_patch.start()
        candidate_patch.start()
        self.addCleanup(source_patch.stop)
        self.addCleanup(candidate_patch.stop)

    def prepare(self, case="normal", name="new", **kwargs):
        return fixtures.prepare_fixture(self.parent / name, case, **kwargs)

    def test_fresh_fixture_exact_bytes_and_no_candidate_or_output(self):
        manifest = self.prepare()
        source = Path(manifest["source"])
        self.assertEqual(source.read_bytes(), b"S" * 19)
        self.assertEqual(manifest["sourceSha256"], hashlib.sha256(b"S" * 19).hexdigest())
        self.assertEqual(manifest["candidateSha256"], hashlib.sha256(b"\x18" * 7).hexdigest())
        self.assertEqual(json.loads((source.parent / "fixture.private.json").read_bytes()), manifest)
        self.assertFalse(Path(manifest["candidate"]).exists())
        self.assertFalse(Path(manifest["output"]).exists())
        self.assertFalse((source.parent / manifest["unit"]).exists())
        self.assertFalse(manifest["cleanupAuthorized"])

    def test_attempt_token_does_not_select_transaction_directory(self):
        manifest = self.prepare(unit="attempt_218")
        self.assertEqual(manifest["unit"], "attempt_218")
        self.assertEqual(manifest["transactionDir"], "unit")
        self.assertEqual(Path(manifest["candidate"]), Path(manifest["root"]) / "unit" / "candidate.bin")

    def test_existing_root_preserves_all_existing_bytes(self):
        root = self.parent / "existing"
        root.mkdir()
        source = root / "source.bin"
        source.write_bytes(b"unrelated source")
        foreign = root / "foreign.bin"
        foreign.write_bytes(b"unrelated foreign")
        with self.assertRaises(FileExistsError):
            fixtures.prepare_fixture(root, "normal")
        self.assertEqual(source.read_bytes(), b"unrelated source")
        self.assertEqual(foreign.read_bytes(), b"unrelated foreign")
        self.assertEqual({item.name for item in root.iterdir()}, {"source.bin", "foreign.bin"})

    def test_outside_relative_traversing_and_ignored_root_refuse(self):
        forbidden = [Path("relative-fixture"), self.parent / ".." / "traversal",
                     fixtures._IGNORED, Path(__file__).resolve().parent / "outside-fixture"]
        for root in forbidden:
            with self.subTest(root=root), self.assertRaises(ValueError):
                fixtures.prepare_fixture(root, "normal")

    def test_case_unit_alias_and_overbound_refusals_create_nothing(self):
        for case, unit in (("undeclared", "unit"), ("normal", "../alias"),
                           ("normal", "a/b"), ("normal", "a\\b"),
                           ("normal", ""), ("normal", "x" * 65), ("normal", "ユニット")):
            root = self.parent / "must-remain-absent"
            with self.subTest(case=case, unit=unit), self.assertRaises(ValueError):
                fixtures.prepare_fixture(root, case, unit=unit)
            self.assertFalse(root.exists())

    def test_collision_requires_exact_pause_and_preserves_source(self):
        manifest = self.prepare("candidate-collision")
        root = Path(manifest["root"])
        (root / manifest["unit"]).mkdir()
        source = Path(manifest["source"]).read_bytes()
        for changes in ({"seq": 8}, {"unit": "different"}, {"stage": "create-Prepared"},
                        {"kind": "backend_dropped", "stage": "backend-drop"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                fixtures.inject_candidate_collision(manifest, pause(**changes))
            self.assertFalse(Path(manifest["candidate"]).exists())
        record = fixtures.inject_candidate_collision(manifest, pause())
        self.assertTrue(record["preserveForeign"])
        self.assertEqual(Path(manifest["candidate"]).read_bytes(), fixtures.FOREIGN)
        with self.assertRaises(ValueError):
            fixtures.inject_candidate_collision(manifest, pause())
        self.assertEqual(Path(manifest["source"]).read_bytes(), source)
        self.assertEqual(Path(manifest["candidate"]).read_bytes(), fixtures.FOREIGN)

    def test_existing_foreign_candidate_never_overwritten(self):
        manifest = self.prepare("candidate-collision")
        candidate = Path(manifest["candidate"])
        candidate.parent.mkdir()
        candidate.write_bytes(b"earlier foreign bytes")
        source = Path(manifest["source"]).read_bytes()
        with self.assertRaises(FileExistsError):
            fixtures.inject_candidate_collision(manifest, pause())
        self.assertEqual(candidate.read_bytes(), b"earlier foreign bytes")
        self.assertEqual(Path(manifest["source"]).read_bytes(), source)
        self.assertFalse((Path(manifest["root"]) / "collision.private.json").exists())

    def test_changed_marker_or_manifest_refuses_before_foreign_creation(self):
        for artifact in ("fixture218.marker", "fixture.private.json"):
            manifest = self.prepare("candidate-collision", name=artifact.replace(".", "-"))
            root = Path(manifest["root"])
            (root / manifest["unit"]).mkdir()
            (root / artifact).write_bytes(b"changed")
            with self.subTest(artifact=artifact), self.assertRaises(ValueError):
                fixtures.inject_candidate_collision(manifest, pause())
            self.assertFalse(Path(manifest["candidate"]).exists())

    def test_observed_reparse_ancestor_refuses_before_creation(self):
        # Model the lstat reparse observation; creating native links may require privileges.
        original = fixtures._plain
        alias = self.parent / "alias"
        alias.mkdir()
        def observed(path, *, directory):
            if path == alias:
                raise ValueError("symlink/reparse fixture path refused")
            return original(path, directory=directory)
        with patch.object(fixtures, "_plain", side_effect=observed):
            with self.assertRaises(ValueError):
                fixtures.prepare_fixture(alias / "fresh", "normal")
        self.assertFalse((alias / "fresh").exists())


if __name__ == "__main__":
    unittest.main()
