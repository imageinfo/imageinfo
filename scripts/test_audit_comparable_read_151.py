"""Public authored correspondence/adversarial controls, no camera data (#0151)."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import audit_comparable_read_151 as audit


def authored_native(value=800):
    layer = dict(state="present", value=dict(kind="integer", decimal=str(value)))
    occurrence = dict(tag=dict(namespace="exif", name="ISO", nativeId="34855"), documentRef="doc",
        issueRefs=[], path=[dict(kind="box", name="CMT2"), dict(kind="tag", name="34855")],
        origin=dict(kind="stored", encoding="uint16", byteOrder="little", resourceRef="value"),
        values=dict(raw=layer, normalized=copy.deepcopy(layer), display=dict(state="unavailable", reason="Not requested"),
            normalization=dict(ruleRef="identity-exact-stored-value", reversibility="exact", assumptions=[], dependencies=[], unit=None)))
    snapshot = dict(basis="observed", issues=[], sources=[dict(id="src", byteLength="1024")],
        documents=[dict(id="doc", format="CR3")], coverage=[dict(state="partial", namespace="*", pathPrefix=[])],
        occurrences=[occurrence], resources=[dict(id="value", byteLength="2", content=dict(kind="source-ranges",
            ranges=[dict(ref="src", offset="100", length="2")]))])
    return dict(schemaVersion=1, files=[dict(state="read", transactionId=None,
        issues=[dict(code="COVERAGE_PARTIAL", severity="warning")], effects=dict(changed=False),
                                         path="authored.cr3", snapshot=snapshot)])


def wire(value):
    return json.dumps(value).encode()


def authored_reference(value=800):
    return [{"SourceFile": "authored.cr3", "EXIF:ExifIFD:ISO": value}]


class Correspondence(unittest.TestCase):
    def test_campaign_identity_links_cover_all_checks_and_retain_abort(self):
        checkpoints = [dict(checkpoint=f"checkpoint-{i:02d}", recordSha256=f"hash-{i}", exactMatch=True) for i in range(6)]
        links = [dict(checkpoint=x["checkpoint"], recordSha256=x["recordSha256"]) for x in checkpoints]
        record = dict(status="completed", identityCheckpoints=links)
        self.assertEqual(audit.audit_campaign_identity_links(checkpoints, record), links)
        for bad in (links[:-1], links[::-1], links[1:] + links[:1], links[:-1] + links[-2:-1]):
            with self.assertRaises(ValueError):
                audit.audit_campaign_identity_links(checkpoints, dict(status="completed", identityCheckpoints=bad))
        checkpoints[-1]["exactMatch"] = False
        with self.assertRaises(ValueError):
            audit.audit_campaign_identity_links(checkpoints, record)
        self.assertEqual(audit.audit_campaign_identity_links(checkpoints, dict(status="aborted", identityCheckpoints=links)), links)

    def test_earlier_failed_identity_checkpoint_cannot_be_omitted(self):
        checkpoints = [dict(checkpoint=f"checkpoint-{i:02d}", recordSha256=f"hash-{i}", exactMatch=i != 0) for i in range(7)]
        successful_suffix = [dict(checkpoint=x["checkpoint"], recordSha256=x["recordSha256"]) for x in checkpoints[1:]]
        for status in ("completed", "aborted"):
            with self.subTest(status=status), self.assertRaises(ValueError):
                audit.audit_campaign_identity_links(checkpoints, dict(status=status, identityCheckpoints=successful_suffix))

    def test_indexed_identity_checkpoint_and_failed_prefix_controls(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / ".local") as folder:
            root = Path(folder)
            rows = [dict(path="/usr/authored", sha256="a" * 64, byteLength="123"),
                    dict(path="/usr/authored-two", sha256="b" * 64, byteLength="456")]
            argv = ["authored-verifier"]
            request = json.dumps(dict(paths=[x["path"] for x in rows]), ensure_ascii=True).encode()
            expected = b"0\t" + b"a" * 64 + b"\t123\n1\t" + b"b" * 64 + b"\t456\n"
            def save(stdout=expected, stderr=b"", outcome="exited", code=0, match=True):
                (root / "request.json").write_bytes(request)
                (root / "stdout").write_bytes(stdout)
                (root / "stderr").write_bytes(stderr)
                r = dict(argv=argv, verifierSha256="verifier", priorManifestSha256="manifest", outcome=outcome,
                    exitCode=code, exactMatch=match, stdoutBytes=len(stdout), stderrBytes=len(stderr),
                    requestSha256=audit.hashlib.sha256(request).hexdigest(),
                    stdoutSha256=audit.hashlib.sha256(stdout).hexdigest(), stderrSha256=audit.hashlib.sha256(stderr).hexdigest())
                (root / "record.private.json").write_bytes(wire(r))
                return r
            save()
            self.assertTrue(audit.audit_identity_checkpoint(root, rows, argv, "manifest", "verifier")["exactMatch"])
            for data in (expected.replace(b"0\t", b"1\t", 1), expected.replace(b"123", b"124"),
                         expected + b"2\textra\n", expected[:-1]):
                save(stdout=data)
                with self.assertRaises(ValueError):
                    audit.audit_identity_checkpoint(root, rows, argv, "manifest", "verifier")
            save(stdout=expected[:20], stderr=b"authored interruption", outcome="cancelled", code=-1, match=False)
            result = audit.audit_identity_checkpoint(root, rows, argv, "manifest", "verifier")
            self.assertFalse(result["exactMatch"])
            self.assertEqual(result["outcome"], "cancelled")
            for key, value in (("requestSha256", "forged"), ("verifierSha256", "forged"),
                               ("stdoutBytes", 0), ("exactMatch", True), ("argv", ["other"])):
                record = save(stdout=b"partial", outcome="timeout", code=-1, match=False)
                record[key] = value
                (root / "record.private.json").write_bytes(wire(record))
                with self.subTest(key=key), self.assertRaises(ValueError):
                    audit.audit_identity_checkpoint(root, rows, argv, "manifest", "verifier")

    def test_authored_rights_and_exact_hash_controls(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / ".local") as folder:
            root = Path(folder)
            source, oracle = root / "authored.cr3", root / "oracle.json"
            source.write_bytes(b"authored source")
            oracle.write_bytes(wire(authored_native()))
            digest = audit.sha(source)
            m = dict(admission="admitted", media=dict(format="CR3", captureMode="full-raw"),
                allowedPhases=["differential"], artifact=dict(sha256=digest),
                rights=dict(status="approved", analyze=True, redistribute=False))
            p = dict(artifact=dict(sha256=digest), rights=dict(permissions=dict(analyze="allowed", publishReports="denied")))
            admission, provenance = root / "admission.json", root / "provenance.json"
            fixture = dict(input=str(source), oracle=str(oracle), admission=str(admission), provenance=str(provenance),
                inputSha256=digest, oracleSha256=audit.sha(oracle))
            def save():
                admission.write_bytes(wire(m))
                provenance.write_bytes(wire(p))
            save()
            self.assertEqual(audit.audit_rights(fixture)["status"], "private-analysis-only")
            m["allowedPhases"] = ["reference-characterization"]
            save()
            with self.assertRaises(ValueError):
                audit.audit_rights(fixture)
            m["allowedPhases"] = ["differential"]
            p["rights"]["permissions"]["publishReports"] = "allowed"
            save()
            with self.assertRaises(ValueError):
                audit.audit_rights(fixture)
            p["rights"]["permissions"]["publishReports"] = "denied"
            save()
            source.write_bytes(b"changed")
            with self.assertRaises(ValueError):
                audit.audit_rights(fixture)

    def test_exact_value_boundary_controls(self):
        for value in (0, 1, 800, 65535):
            with self.subTest(value=value):
                result = audit.audit_pair(wire(authored_native(value)), wire(authored_reference(value)), "authored.cr3", "authored.cr3")
                self.assertEqual(result["decimal"], str(value))
                self.assertEqual(result["nativeCoverage"], "partial")

    def test_reference_ambiguities_refuse(self):
        cases = []
        for value in (True, "800", 800.0, -1, 65536, [800]):
            cases.append(authored_reference(value))
        cases.extend(([{"SourceFile": "authored.cr3", "ISO": 800}],
                      [{"SourceFile": "authored.cr3", "MakerNotes:Track4:ISO": 800}],
                      [{**authored_reference()[0], "EXIF:ExifIFD:Copy1:ISO": 800}],
                      authored_reference() * 2, authored_reference(801)))
        for value in cases:
            with self.subTest(value=value), self.assertRaises(ValueError):
                audit.audit_pair(wire(authored_native()), wire(value))

    def test_native_identity_coverage_and_occurrence_refuse(self):
        def altered(path, value):
            n = authored_native()
            cursor = n
            for key in path[:-1]:
                cursor = cursor[key]
            cursor[path[-1]] = value
            return n
        s = ["files", 0, "snapshot"]
        o = s + ["occurrences", 0]
        changes = [(s + ["coverage", 0, "state"], "complete"),
            (o + ["tag", "namespace"], "canon:ctmd"), (o + ["tag", "nativeId"], "2"),
            (o + ["path", 0, "name"], "CMT3"), (o + ["values", "raw", "value", "decimal"], "0800"),
            (o + ["values", "normalization", "dependencies"], ["unknown"]),
            (s + ["resources", 0, "content", "ranges", 0, "offset"], "1024"),
            (["files", 0, "effects", "changed"], True), (["files", 0, "path"], "other.cr3")]
        for path, value in changes:
            with self.subTest(path=path), self.assertRaises(ValueError):
                audit.audit_pair(wire(altered(path, value)), wire(authored_reference()), "authored.cr3")
        n = authored_native()
        n["files"][0]["snapshot"]["occurrences"] *= 2
        with self.assertRaises(ValueError):
            audit.audit_pair(wire(n), wire(authored_reference()))

    def test_duplicate_keys_nonfinite_and_utf8_refuse(self):
        for data in (b'[{"SourceFile":"x","EXIF:ExifIFD:ISO":800,"EXIF:ExifIFD:ISO":800}]',
                     b'[{"SourceFile":"x","EXIF:ExifIFD:ISO":NaN}]', b'\xff'):
            with self.subTest(data=data), self.assertRaises(ValueError):
                audit.audit_pair(wire(authored_native()), data)

    def test_statistic_is_median_of_ratios(self):
        pairs = [(1, 1)] * 5 + [(100, 200)] * 5
        result = audit.paired_statistics(pairs)
        self.assertEqual(result["median"], 1.5)
        self.assertIn("per-pair", result["statistic"])
        for bad in (pairs[:-1], pairs + [(1, 1)], [(0, 1)] * 10, [(True, 1)] * 10):
            with self.assertRaises(ValueError):
                audit.paired_statistics(bad)


if __name__ == "__main__":
    unittest.main()
