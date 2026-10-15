"""Authored permission/boundary vectors; no camera files or media reads."""
import copy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import measure_batch_read as batch


def evidence():
    documents = {"grant": {}, "privacy": {"status": "restricted", "publicClearance": False}}
    fixtures = []
    for n in range(8):
        fixture = {"id": f"AUTHORED-{n}", "input": f"never-read-{n}", "inputSha256": "image-hash",
                   "oracleSha256": "oracle-hash", "admission": f"admission-{n}",
                   "provenance": f"provenance-{n}", "correctness": f"correctness-{n}"}
        documents[fixture["admission"]] = {"id": fixture["id"], "revision": 2, "admission": "admitted",
            "rights": {"analyze": True}, "artifact": {"sha256": "image-hash"}, "media": {"captureMode": "full-raw"}}
        documents[fixture["provenance"]] = {"revision": 2, "purpose": "operational", "review": {"state": "approved"},
            "artifact": {"sha256": "image-hash"}, "rights": {"permissions": {
                "store": "allowed", "analyze": "allowed", "publishReports": "denied"}}}
        documents[fixture["correctness"]] = {"verdict": "pass", "operation": "read",
            "fixtures": [{"id": fixture["id"], "sha256": "image-hash"}],
            "candidate": {"stdout": {"sha256": "oracle-hash"}}}
        fixtures.append(fixture)
    protocol = {"taskAdmission": {"ticket": 63, "scope": "private-read-only-batch-analysis", "sourceMutationAllowed": False},
                "primaryGrant": "grant", "privacyReview": "privacy", "fixtureSet": fixtures,
                "evidenceSha256": {name: "pinned" for name in documents}}
    return protocol, documents


class BatchPermissionTests(unittest.TestCase):
    def test_private_analysis_does_not_expand_report_permission_or_read_media(self):
        protocol, documents = evidence()
        with patch.object(batch.single, "load", side_effect=documents.__getitem__), patch.object(
            batch.single, "digest", return_value="pinned"
        ) as digest:
            rights = batch.rights_before_media(protocol)
        self.assertTrue(rights["analysisAllowed"])
        self.assertFalse(rights["publishReportsAllowed"])
        self.assertFalse(rights["publicCameraResultsExported"])
        self.assertTrue(all(call.args[0] in documents for call in digest.call_args_list))

    def test_denied_analysis_refuses_before_any_media_access(self):
        protocol, documents = evidence()
        documents["provenance-0"]["rights"]["permissions"]["analyze"] = "denied"
        with patch.object(batch.single, "load", side_effect=documents.__getitem__), patch.object(
            batch.single, "digest", return_value="pinned"
        ) as digest, self.assertRaises(ValueError):
            batch.rights_before_media(protocol)
        self.assertTrue(all(call.args[0] in documents for call in digest.call_args_list))

    def test_missing_or_changed_evidence_fails_closed(self):
        protocol, documents = evidence()
        for missing in ("grant", "privacy", "admission-7", "provenance-7", "correctness-7"):
            altered = copy.deepcopy(protocol)
            del altered["evidenceSha256"][missing]
            with self.subTest(missing=missing), patch.object(batch.single, "digest") as digest, self.assertRaises(ValueError):
                batch.rights_before_media(altered)
            digest.assert_not_called()
        with patch.object(batch.single, "digest", return_value="changed"), self.assertRaises(ValueError):
            batch.rights_before_media(protocol)

    def test_initial_reference_only_admission_does_not_enable_native_task(self):
        protocol, documents = evidence()
        documents["provenance-0"]["revision"] = 1
        documents["provenance-0"]["purpose"] = "reference"
        with patch.object(batch.single, "load", side_effect=documents.__getitem__), patch.object(
            batch.single, "digest", return_value="pinned"
        ), self.assertRaises(ValueError):
            batch.rights_before_media(protocol)

    def test_source_byte_bound_precedes_hash_read(self):
        protocol, _ = evidence()
        with patch.object(batch, "rights_before_media"), patch.object(batch.Path, "stat", return_value=SimpleNamespace(
            st_size=1024 * 1024 * 1024 + 1
        )), patch.object(batch.single, "digest") as digest, self.assertRaises(ValueError):
            batch.source_check(protocol, 1, "before", {})
        digest.assert_not_called()

    def test_camera_output_must_remain_private_before_loading_protocol(self):
        with patch.object(batch.single, "load") as load, self.assertRaises(ValueError):
            batch.collect(batch.ROOT / "docs")
        load.assert_not_called()


if __name__ == "__main__":
    unittest.main()
