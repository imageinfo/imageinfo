"""Pure retained-evidence rejection tests: no producer, process or codec calls.

Run with ``python -m unittest discover -s experiments/0075-preview-entropy
-p test_audit.py``. Every file and native-result record below is synthetic.
"""

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys

import audit


def temporary_directory():
    # Keep synthetic files in the caller's writable workspace, including inside
    # restricted Windows test sandboxes whose default Temp permits mkdir only.
    return tempfile.TemporaryDirectory(prefix="0075-audit-test-", dir=Path.cwd())


class CaptureAccountingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = temporary_directory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        request = {
            "schema": "imageinfo-0075-process-v1", "command": ["synthetic-never-executed"],
            "limits": {"deadline_seconds": 120, "capture_bytes_per_stream": 16,
                       "poll_seconds": .01, "drain_seconds": 2},
            "binding": {}, "cwd": str(self.root.resolve()), "environment": {},
            "supervision": "direct-child-only; logical limits; no OS quota",
        }
        raw = json.dumps(request).encode("utf-8")
        (self.root / "request.json").write_bytes(raw)
        self.result = {
            "schema": request["schema"], "outcome": "exited", "error": None,
            "returncode": 0, "terminationConfirmed": True, "elapsedSeconds": .1,
            "requestSha256": audit.sha(raw), "streams": {},
        }
        for name in ("stdout", "stderr"):
            self.capture(name, b"", observed=0)

    def capture(self, name, content, *, observed, eof=True, overflow=False, error=None):
        (self.root / (name + ".bin")).write_bytes(content)
        self.result["streams"][name] = {
            "capturedBytes": len(content), "observedBytes": observed,
            "eof": eof, "overflow": overflow, "error": error,
            "sha256": audit.sha(content),
        }

    def evaluate(self):
        (self.root / "process.json").write_text(json.dumps(self.result), encoding="utf-8")
        return audit.audit_process(self.root)

    def test_complete_capture_accounts_for_both_streams(self):
        self.capture("stdout", b"result", observed=6)
        self.capture("stderr", b"diagnostic", observed=10)
        result = self.evaluate()
        self.assertTrue(result["completeSuccess"])
        for name in ("stdout", "stderr"):
            self.assertEqual(result["streams"][name]["captureDisposition"], "complete")

    def test_unclassified_lost_observed_bytes_refuse_for_both_streams(self):
        for name in ("stdout", "stderr"):
            for content in (b"", b"abc"):
                with self.subTest(stream=name, retained=len(content)):
                    self.capture(name, content, observed=9)
                    with self.assertRaisesRegex(audit.InvalidEvidence, "unclassified-capture-loss"):
                        self.evaluate()
                    self.capture(name, b"", observed=0)

    def test_non_eof_and_deadline_do_not_explain_lost_observed_bytes(self):
        self.result["outcome"] = "deadline"
        self.capture("stderr", b"", observed=9, eof=False)
        with self.assertRaisesRegex(audit.InvalidEvidence, "unclassified-capture-loss"):
            self.evaluate()

    def test_failed_write_retained_prefixes_are_auditable_but_cannot_pass(self):
        self.result["outcome"] = "capture-failed"
        for name in ("stdout", "stderr"):
            with self.subTest(stream=name):
                self.capture(name, b"abc", observed=9, eof=False, error="OSError: synthetic write failure")
                result = self.evaluate()
                self.assertFalse(result["completeSuccess"])
                self.assertEqual(result["streams"][name]["captureDisposition"], "failed-prefix")
                self.assertEqual(result["streams"][name]["byteLength"], 3)
                self.assertEqual((self.root / (name + ".bin")).read_bytes(), b"abc")
                self.capture(name, b"", observed=0)

    def test_overflow_prefix_is_classified_and_cannot_pass(self):
        self.result["outcome"] = "capture-failed"
        self.capture("stdout", b"x" * 16, observed=17, eof=False, overflow=True)
        result = self.evaluate()
        self.assertFalse(result["completeSuccess"])
        self.assertEqual(result["streams"]["stdout"]["captureDisposition"], "overflow-prefix")

    def test_unconfirmed_drain_cannot_claim_complete_consumption(self):
        self.result["outcome"] = "drain-incomplete"
        for name in ("stdout", "stderr"):
            self.capture(name, b"abc", observed=9, eof=False)
            self.result["streams"][name]["sha256"] = None
        result = self.evaluate()
        self.assertFalse(result["completeSuccess"])
        self.assertEqual(result["streams"]["stderr"]["captureDisposition"], "unconfirmed-drain")

    def test_failed_prefix_still_requires_exact_retained_size_and_hash(self):
        self.result["outcome"] = "capture-failed"
        self.capture("stderr", b"abc", observed=9, eof=False, error="OSError: synthetic")
        (self.root / "stderr.bin").write_bytes(b"ab")
        with self.assertRaisesRegex(audit.InvalidEvidence, "artifact-size"):
            self.evaluate()

    def test_empty_error_does_not_classify_capture_loss(self):
        self.capture("stderr", b"", observed=9, error="")
        with self.assertRaisesRegex(audit.InvalidEvidence, "process-stream-error"):
            self.evaluate()

    def test_nonzero_exit_cannot_pass(self):
        self.result["returncode"] = 7
        self.assertFalse(self.evaluate()["completeSuccess"])


def synthetic_extent():
    def segment(marker, payload):
        return bytes((255, marker)) + (len(payload) + 2).to_bytes(2, "big") + payload
    quantization = segment(219, b"\x00" + b"\x01" * 64)
    one_symbol = b"\x01" + bytes(15) + b"\x00"
    huffman = segment(196, b"\x00" + one_symbol + b"\x10" + one_symbol)
    frame = segment(192, b"\x08\x00\x01\x00\x01\x03\x01\x11\x00\x02\x11\x00\x03\x11\x00")
    scan = segment(218, b"\x03\x01\x00\x02\x00\x03\x00\x00\x3f\x00")
    # This is only a marker-policy fixture; no entropy-validity claim is made.
    return b"\xff\xd8" + quantization + huffman + frame + scan + b"\x01" * 10 + b"\xff\xd9"


class IndependentReconstructionTests(unittest.TestCase):
    def test_all_zero_suffix_lengths_and_nonzero_positions(self):
        data = synthetic_extent()
        for count in range(33):
            self.assertEqual(audit.independent_extent(data + bytes(count))["suffixBytes"], count)
        for position in range(32):
            self.assertIsNone(audit.independent_extent(data + bytes(position) + b"\x01" + bytes(31 - position)))
        self.assertIsNone(audit.independent_extent(data + bytes(33)))

    def test_independent_corruptions_separate_native_from_syntax_failures(self):
        corruptions = audit.independent_corruptions(synthetic_extent())
        self.assertEqual(set(corruptions), set(audit.NEGATIVE_CASES))
        syntax_fits = {name for name, data in corruptions.items() if audit.independent_extent(data)}
        self.assertEqual(syntax_fits, {"early-eoi", "immediate-eoi"})

    def test_full_synthetic_rgb_derivative_rehash_and_failure(self):
        data = synthetic_extent()
        extent = audit.independent_extent(data)
        status = {"returnCode": 0, "severityRaw": 0, "severityMeaningful": False,
                  "severity": "not-meaningful-on-success", "diagnosticRaw": "synthetic"}
        row = {"api": "tjDecompress2", "flags": 8192, "pixelFormat": "RGB", "pitch": 0,
               "storedExtentBytes": len(data), "syntax": dict(extent, accepted=True,
                   profileId="0075-baseline-interleaved-rgb-zero-padding-v2"),
               "nativeInvoked": True, "destroy": {"returnCode": 0, "succeeded": True},
               "header": status, "headerDimensions": [1, 1], "decode": status,
               "dimensions": [1, 1], "accepted": True, "outcome": "warning-free-pixels",
               "decodedBytes": 3, "pixelSha256": audit.sha(b"abc"),
               "consumption": "sha256-all-packed-rgb-bytes"}
        with temporary_directory() as directory:
            pixels = Path(directory) / "pixels.rgb"
            pixels.write_bytes(b"abc")
            self.assertEqual(audit.audit_decoder(row, data, pixels)["assertionOutcome"], "pass")
            pixels.write_bytes(b"abd")
            with self.assertRaisesRegex(audit.InvalidEvidence, "artifact-content"):
                audit.audit_decoder(row, data, pixels)
            mutated = copy.deepcopy(row)
            mutated["decode"]["severityMeaningful"] = True
            with self.assertRaisesRegex(audit.InvalidEvidence, "native-severity-meaning"):
                audit.audit_decoder(mutated, data, pixels)

    def test_missing_extra_and_duplicate_authored_cells_refuse(self):
        positives = (set(audit.POSITIVE_BASES) | {name + "-zero32" for name in audit.POSITIVE_BASES} |
                     {"formula-64-444-zero" + str(count) for count in range(1, 32)})
        identifiers = positives | set(audit.NEGATIVE_CASES)
        self.assertEqual((len(positives), len(identifiers)), (43, 59))
        with temporary_directory() as directory:
            root = Path(directory)
            cells = [{"id": name, "runRoot": str(root / name)} for name in sorted(identifiers)]
            for altered, reason in ((cells[:-1], "authored-plan-denominator"),
                                    (cells + [{"id": "extra", "runRoot": str(root / "extra")}],
                                     "authored-plan-denominator"),
                                    (cells + [cells[0]], "authored-plan-cell-set")):
                raw = json.dumps({"schema": "imageinfo-0075-authored-audit-plan-v1", "cells": altered}).encode()
                path = root / "plan.json"
                path.write_bytes(raw)
                with self.assertRaisesRegex(audit.InvalidEvidence, reason):
                    audit.audit_plan({"path": str(path), "byteLength": len(raw), "sha256": audit.sha(raw)})

    def test_independent_source_formula_and_encoder_recipe(self):
        formula = "rgb-mod256-x13y7-x3y19-x23y11"
        small = {"formula": formula, "width": 2, "height": 2}
        self.assertEqual(audit.source_rgb_binding(small)["sha256"],
                         audit.sha(bytes((0, 0, 0, 13, 3, 23, 7, 19, 11, 20, 22, 34))))
        self.assertEqual(audit.source_rgb_binding(dict(small, formula="solid-rgb-64-128-192"))["sha256"],
                         audit.sha(bytes((64, 128, 192)) * 4))
        specification = audit.positive_specification("formula-64-444")
        # Independent formula construction, with no encoder/producer import.
        pixels = bytes(value for y in range(64) for x in range(64) for value in
                       ((x * 13 + y * 7) % 256, (x * 3 + y * 19) % 256,
                        (x * 23 + y * 11) % 256))
        manifest = {"syntheticComponentIdentity": True}
        provenance = {"schema": "imageinfo-0075-encoder-result-v1", "baseId": "formula-64-444",
                      "specification": specification,
                      "sourceRgb": {"formula": formula, "byteLength": len(pixels), "sha256": audit.sha(pixels)},
                      "invocation": {"api": "PIL.Image.frombytes/save", "mode": "RGB", "format": "JPEG",
                                     "dimensions": [64, 64], "subsampling": 0,
                                     "options": {"quality": 90, "optimize": False, "progressive": False}},
                      "componentIdentityBefore": manifest, "componentIdentityAfter": manifest}
        audit.audit_encoder_recipe(provenance, "formula-64-444", manifest)
        for mutate, reason in ((lambda row: row["sourceRgb"].update(sha256="0" * 64), "encoder-source-rgb"),
                               (lambda row: row["sourceRgb"].update(formula="other"), "encoder-source-rgb"),
                               (lambda row: row["invocation"]["options"].update(quality=89), "encoder-invocation"),
                               (lambda row: row.update(componentIdentityAfter={}), "encoder-component-identities")):
            altered = copy.deepcopy(provenance)
            mutate(altered)
            with self.assertRaisesRegex(audit.InvalidEvidence, reason):
                audit.audit_encoder_recipe(altered, "formula-64-444", manifest)


class SyntheticPositivePlanTests(unittest.TestCase):
    """Exercise actual audit_run -> audit_plan return propagation, without native I/O.

    Only runtime validation and the separate six-base provenance audit are
    replaced. A tiny synthetic declaration exercises all33 suffix branches;
    the ordinary denominator test separately enforces the real59 declarations.
    None of these synthetic reports is actual native qualification evidence.
    """

    def test_full_positive_return_preserves_consumption_and_suffix_comparison(self):
        with temporary_directory() as directory:
            root = Path(directory)
            evidence, grants = root / "evidence", root / "grants"
            for path in (evidence, grants, evidence / "runs", evidence / "requests", evidence / "inputs"):
                path.mkdir()

            def binding(path):
                raw = path.read_bytes()
                return {"path": str(path.resolve()), "byteLength": len(raw), "sha256": audit.sha(raw)}

            def write(path, value):
                path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
                return binding(path)

            manifest = write(root / "manifest.json", {"syntheticRuntimeOnly": True})
            profile = write(root / "profile.json", {"syntheticProfileOnly": True})
            here = Path(audit.__file__).resolve().parent
            recipes = [binding(here / name) for name in
                       ("qualify.py", "controls.py", "corruption.py", "run.py", "audit.py",
                        "decoder.py", "syntax.py", "runtime.py", "component-profile.json", "profile.json")]
            limits = {"deadline_seconds": 120, "capture_bytes_per_stream": 16384,
                      "poll_seconds": .01, "drain_seconds": 2}
            frozen = {"recipeBindings": recipes, "runtimeManifest": manifest, "limits": limits,
                      "interpreter": {"path": sys.executable}}
            cells, proposals, expectations = [], [], {}
            base = synthetic_extent()
            for count in range(33):
                identifier = "formula-64-444" + ("-zero" + str(count) if count else "")
                run_root = evidence / "runs" / identifier
                run_root.mkdir()
                process_root = run_root / "process"
                process_root.mkdir()
                source = evidence / "inputs" / (identifier + ".jpg")
                source.write_bytes(base + bytes(count))
                before = audit.stat_identity(source)
                core = {"schema": "imageinfo-0075-cell-v1", "stage": "authored", "interpreter": sys.executable,
                        "input": binding(source), "runtimeManifest": manifest, "profile": profile,
                        "recipeBindings": recipes, "limits": limits}
                grant = write(grants / (identifier + ".json"), {"schema": "imageinfo-0075-parent-grant-v1",
                    "stage": "authored", "authorizedBy": "parent-after-independent-review",
                    "reviewedRequestSha256": audit.canonical_sha(core)})
                request = dict(core, parentGrant=grant)
                prepared = write(evidence / "requests" / (identifier + ".json"), request)
                request_bound = write(run_root / "cell-request.json", request)
                expected = write(evidence / "requests" / (identifier + ".expectations.json"), {
                    "schema": "imageinfo-0075-audit-expectations-v1", "cellRequest": request_bound,
                    "expectedAssertionOutcome": "pass"})
                expectations[identifier] = Path(expected["path"])
                command = [sys.executable, str(here / "run.py"), "--worker",
                           str(run_root / "cell-request.json"), request_bound["sha256"]]
                write(run_root / "process-invocation.json", {"schema": "imageinfo-0075-invocation-v1",
                    "command": command, "cellRequestSha256": request_bound["sha256"]})
                process_request = write(process_root / "request.json", {
                    "schema": "imageinfo-0075-process-v1", "command": command, "limits": limits,
                    "binding": {"cellRequestSha256": request_bound["sha256"]}, "cwd": str(process_root),
                    "environment": {}, "supervision": "direct-child-only; logical limits; no OS quota"})
                status = {"returnCode": 0, "severityRaw": 0, "severityMeaningful": False,
                          "severity": "not-meaningful-on-success", "diagnosticRaw": "synthetic"}
                decoder = {"api": "tjDecompress2", "flags": 8192, "pixelFormat": "RGB", "pitch": 0,
                    "storedExtentBytes": len(base) + count, "syntax": dict(audit.independent_extent(base + bytes(count)),
                        accepted=True, profileId="0075-baseline-interleaved-rgb-zero-padding-v2"),
                    "nativeInvoked": True, "destroy": {"returnCode": 0, "succeeded": True},
                    "header": status, "headerDimensions": [1, 1], "decode": status, "dimensions": [1, 1],
                    "accepted": True, "outcome": "warning-free-pixels", "decodedBytes": 3,
                    "pixelSha256": audit.sha(b"abc"), "consumption": "sha256-all-packed-rgb-bytes",
                    "pixelSinkCompleted": True, "subsamplingRaw": 0}
                worker = {"schema": "imageinfo-0075-worker-v1", "decoder": decoder,
                          "sourceBefore": before, "sourceAfter": before, "pixelArtifact": "pixels.rgb"}
                (run_root / "pixels.rgb").write_bytes(b"abc")
                stdout = (json.dumps(worker) + "\n").encode()
                (process_root / "stdout.bin").write_bytes(stdout)
                (process_root / "stderr.bin").write_bytes(b"")
                streams = {name: {"capturedBytes": len(content), "observedBytes": len(content),
                    "eof": True, "overflow": False, "error": None, "sha256": audit.sha(content)}
                    for name, content in (("stdout", stdout), ("stderr", b""))}
                process = {"schema": "imageinfo-0075-process-v1", "outcome": "exited", "error": None,
                    "returncode": 0, "terminationConfirmed": True, "elapsedSeconds": .1,
                    "streams": streams, "requestSha256": process_request["sha256"]}
                write(process_root / "process.json", process)
                write(run_root / "cell-result.json", {"schema": "imageinfo-0075-cell-result-v1",
                    "outcome": "warning-free-pixels", "processInvocationAttempted": True, "process": process,
                    "worker": worker, "sourceBefore": before, "sourceAfter": before, "immutableObservation": True})
                cells.append({"id": identifier, "runRoot": str(run_root), "request": prepared,
                              "expectations": expected, "expectedAssertionOutcome": "pass"})
                proposals.append({"id": identifier, "core": core, "reviewedRequestSha256": audit.canonical_sha(core),
                                  "runRoot": str(run_root), "expectedAssertionOutcome": "pass"})
            plan = write(evidence / "audit-plan.json", {"schema": "imageinfo-0075-authored-audit-plan-v1", "cells": cells})
            execution_grant = write(grants / "execute.json", {"schema": "imageinfo-0075-orchestration-grant-v1",
                "authorizedBy": "parent-after-independent-review", "purpose": "execute-59-authored-cells", "reviewedArtifact": plan})
            write(evidence / "execution.once.json", {"plan": plan, "parentGrant": execution_grant})
            context = {"freeze": frozen, "proposals": {"cells": proposals}, "root": evidence,
                       "baseInputs": {"formula-64-444": binding(evidence / "inputs/formula-64-444.jpg")}}
            with patch.object(audit, "audit_runtime", return_value={"syntheticOnly": True}), \
                 patch.object(audit, "audit_encoder_provenance", return_value=context), \
                 patch.object(audit, "POSITIVE_BASES", {"formula-64-444": (1, 1, 0)}), \
                 patch.object(audit, "NEGATIVE_CASES", ()):
                single = audit.audit_run(evidence / "runs/formula-64-444", expectations["formula-64-444"])
                self.assertEqual(single["decodedConsumption"], {"byteLength": 3, "sha256": audit.sha(b"abc")})
                result = audit.audit_plan(plan)
                self.assertTrue(result["finiteAuthoredProfileQualified"])
                self.assertTrue(all(row["decodedConsumption"] == single["decodedConsumption"] for row in result["cells"]))


if __name__ == "__main__":
    unittest.main()
