"""Independent retained-evidence audit; never imports or runs the producer/codec.

The caller supplies an externally reviewed expectation document. Editable run
reports are evidence, never phase authority or a source of accepted bindings.
Camera-capable invocations must keep both the expectation and output private.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

INPUT_LIMIT = 32 * 1024 * 1024
DIMENSION_LIMIT = 8192
PIXEL_LIMIT = 256 * 1024 * 1024
JSON_LIMIT = 16 * 1024 * 1024
WORKER_REPORT_LIMIT = 65536
POSITIVE_BASES = {
    "formula-64-444": (64, 64, 0), "odd-19x17-420": (19, 17, 2),
    "formula-256-422": (256, 256, 1), "wide-8192x1-444": (8192, 1, 0),
    "tall-1x8192-444": (1, 8192, 0), "square-8192-420": (8192, 8192, 2),
}
NEGATIVE_CASES = (
    "entropy-truncated", "early-eoi", "immediate-eoi", "suffix-nonzero-middle", "suffix-nonzero-last",
    "suffix-zero33", "suffix-nonzero", "suffix-second-jpeg", "segment-length-one",
    "segment-length-overrun", "quant-table-selector", "huffman-table-selector",
    "scan-nonbaseline", "entropy-restart-marker", "entropy-tem-marker", "duplicate-soi",
)


class InvalidEvidence(ValueError):
    """Evidence cannot support a valid experiment; messages contain no input data."""


def require(condition, reason):
    if not condition:
        raise InvalidEvidence(reason)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def _unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate-json-key")
        result[key] = value
    return result


def read_json(path):
    require(path.stat().st_size <= JSON_LIMIT, "json-bound")
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique,
                          parse_constant=lambda _: require(False, "nonfinite-json"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise InvalidEvidence("malformed-json") from error


def file_binding(path, bound, *, limit=None):
    """Hash every retained byte without allocating the entire output file."""
    require(type(bound) is dict and type(bound.get("byteLength")) is int,
            "missing-file-binding")
    size = bound["byteLength"]
    require(size >= 0 and (limit is None or size <= limit), "artifact-bound")
    require(path.is_file() and path.stat().st_size == size, "artifact-size")
    digest = hashlib.sha256()
    consumed = 0
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
            consumed += len(block)
            require(consumed <= size, "artifact-grew")
    require(consumed == size and digest.hexdigest() == bound.get("sha256"),
            "artifact-content")
    return {"byteLength": consumed, "sha256": digest.hexdigest()}


def local_path(root, name):
    require(type(name) is str and name and not Path(name).is_absolute(),
            "artifact-path")
    require(".." not in Path(name).parts, "artifact-parent-traversal")
    unresolved = root / name
    path = unresolved.resolve()
    require(path.is_relative_to(root.resolve()), "artifact-outside-run")
    # Reject links/reparse aliases at every existing path component.
    for component in (unresolved, *unresolved.parents):
        if component == root.resolve().parent:
            break
        require(not component.is_symlink() and not component.is_junction(),
                "artifact-alias")
    return path


def independent_extent(data):
    """A second marker/table/scan walk, separate from entropy/native results.

    Returns None outside the finite syntax policy. This walk does not establish
    entropy correctness, decoded usability, or support for arbitrary JPEGs.
    """
    if type(data) is not bytes or not 0 < len(data) <= INPUT_LIMIT or data[:2] != b"\xff\xd8":
        return None
    at, frame, scan, quant, huffman = 2, None, None, set(), set()
    while at < len(data):
        if data[at] != 255:
            return None
        while at < len(data) and data[at] == 255:
            at += 1
        if at == len(data):
            return None
        marker, at = data[at], at + 1
        if marker == 217:
            suffix = data[at:]
            if frame is None or scan is None or len(suffix) > 32 or any(suffix):
                return None
            return {"width": frame[0], "height": frame[1],
                    "decodedBytes": frame[0] * frame[1] * 3,
                    "scanStart": scan, "eoiEnd": at,
                    "suffixBytes": len(data) - at, "inputBytes": len(data)}
        if scan is not None or marker not in (192, 196, 218, 219, 254, *range(224, 240)):
            return None
        if at + 2 > len(data):
            return None
        count = int.from_bytes(data[at:at + 2], "big")
        if count < 2 or at + count > len(data):
            return None
        payload = memoryview(data)[at + 2:at + count]
        at += count
        if marker == 219:
            if not payload or len(payload) % 65:
                return None
            for offset in range(0, len(payload), 65):
                if payload[offset] > 3 or 0 in payload[offset + 1:offset + 65]:
                    return None
                quant.add(payload[offset])
        elif marker == 196:
            cursor = 0
            if not payload:
                return None
            while cursor < len(payload):
                if len(payload) - cursor < 17:
                    return None
                selector = payload[cursor]
                symbols = sum(payload[cursor + 1:cursor + 17])
                if selector not in (*range(4), *range(16, 20)) or not 1 <= symbols <= 256:
                    return None
                cursor += 17 + symbols
                if cursor > len(payload):
                    return None
                huffman.add(selector)
        elif marker == 192:
            if frame or len(payload) != 15 or payload[0] != 8 or payload[5] != 3:
                return None
            height = int.from_bytes(payload[1:3], "big")
            width = int.from_bytes(payload[3:5], "big")
            if not 1 <= width <= DIMENSION_LIMIT or not 1 <= height <= DIMENSION_LIMIT:
                return None
            if width * height * 3 > PIXEL_LIMIT:
                return None
            components, blocks = {}, 0
            for offset in (6, 9, 12):
                identifier, sampling, table = payload[offset:offset + 3]
                horizontal, vertical = sampling >> 4, sampling & 15
                if identifier in components or table > 3 or not 1 <= horizontal <= 4 or not 1 <= vertical <= 4:
                    return None
                components[identifier] = table
                blocks += horizontal * vertical
            if blocks > 10:
                return None
            frame = (width, height, components)
        elif marker == 218:
            if frame is None or len(payload) != 10 or payload[0] != 3 or bytes(payload[-3:]) != b"\x00\x3f\x00":
                return None
            ids = list(payload[1:7:2])
            if len(set(ids)) != 3 or set(ids) != set(frame[2]) or not set(frame[2].values()) <= quant:
                return None
            for selector in payload[2:7:2]:
                if selector >> 4 not in range(4) or selector & 15 not in range(4):
                    return None
                if selector >> 4 not in huffman or (16 | (selector & 15)) not in huffman:
                    return None
            scan = at
            while at < len(data):
                if data[at] != 255:
                    at += 1
                elif at + 1 < len(data) and data[at + 1] == 0:
                    at += 2
                else:
                    break
    return None


def native_diagnostic(row):
    require(type(row) is dict and type(row.get("returnCode")) is int,
            "missing-native-status")
    code = row["returnCode"]
    require(code in (0, -1), "unknown-native-status")
    require(row.get("severityMeaningful") is (code != 0), "native-severity-meaning")
    require(type(row.get("severityRaw")) is int, "missing-native-severity")
    diagnostic = row.get("diagnosticRaw")
    require(type(diagnostic) is str and len(diagnostic.encode("utf-8")) <= 720,
            "native-diagnostic-bound")
    if code:
        require(row["severityRaw"] in (0, 1) and diagnostic, "native-failure-diagnostic")
        require(row.get("severity") == ("warning" if row["severityRaw"] == 0 else "fatal"),
                "native-severity")
    else:
        require(row.get("severity") == "not-meaningful-on-success", "success-severity")
    return code


def audit_decoder(row, data, pixel_path=None):
    """Reconstruct syntax/native/output distinctions from retained evidence."""
    extent = independent_extent(data)
    require(row.get("storedExtentBytes") == len(data), "native-input-extent")
    require(row.get("api") == "tjDecompress2" and row.get("flags") == 8192 and
            row.get("pixelFormat") == "RGB" and row.get("pitch") == 0,
            "native-settings")
    require(type(row.get("syntax")) is dict and row["syntax"].get("accepted") is (extent is not None),
            "syntax-disagreement")
    require(row["syntax"].get("profileId") == "0075-baseline-interleaved-rgb-zero-padding-v2",
            "syntax-profile")
    if extent is None:
        require(row.get("nativeInvoked") is False and row.get("accepted") is False and
                row.get("outcome") == "syntax-refused", "unsupported-native-invocation")
        require("header" not in row and "decode" not in row and "pixelSha256" not in row,
                "refusal-has-native-results")
        return {"assertionOutcome": "unsupported", "nativeEvaluated": False}
    require(all(row["syntax"].get(key) == value for key, value in extent.items()),
            "extent-fields-disagree")
    require(row.get("nativeInvoked") is True, "missing-native-invocation")
    require(row.get("destroy") == {"returnCode": 0, "succeeded": True}, "native-destroy")
    header = native_diagnostic(row.get("header"))
    require(row.get("headerDimensions") == [extent["width"], extent["height"]] or header != 0,
            "native-header-dimensions")
    if header != 0:
        require(row.get("accepted") is False and row.get("outcome") == "header-refused" and
                "decode" not in row and "pixelSha256" not in row, "header-failure-classification")
        return {"assertionOutcome": "fail", "nativeEvaluated": True}
    code = native_diagnostic(row.get("decode"))
    require(row.get("dimensions") == [extent["width"], extent["height"]], "decode-dimensions")
    if code:
        require(row.get("accepted") is False and row.get("outcome") == "native-refused" and
                "pixelSha256" not in row, "native-failure-classification")
        return {"assertionOutcome": "fail", "nativeEvaluated": True}
    require(row.get("accepted") is True and row.get("outcome") == "warning-free-pixels" and
            row.get("decodedBytes") == extent["decodedBytes"] and
            row.get("consumption") == "sha256-all-packed-rgb-bytes", "pixel-consumption")
    require(pixel_path is not None, "decoded-derivative-not-retained")
    observed = file_binding(pixel_path, {"byteLength": extent["decodedBytes"],
                                        "sha256": row.get("pixelSha256")}, limit=PIXEL_LIMIT)
    return {"assertionOutcome": "pass", "nativeEvaluated": True,
            "decodedConsumption": observed}


def audit_process(root, expected_command=None, expected_binding=None):
    """Audit the retained direct-child record, including failed attempts.

    A bounded failure is a valid process observation, not a passed assertion.
    Capture counts describe bytes actually observed/retained, not all bytes the
    child may have attempted to write after overflow caused termination.
    """
    request_path = root / "request.json"
    request, result = read_json(request_path), read_json(root / "process.json")
    require(request.get("schema") == result.get("schema") == "imageinfo-0075-process-v1",
            "process-schema")
    require(result.get("requestSha256") == sha(request_path.read_bytes()), "request-binding")
    command, limits = request.get("command"), request.get("limits")
    require(type(command) is list and command and
            all(type(value) is str and "\0" not in value for value in command), "process-command")
    if expected_command is not None:
        require(command == expected_command, "process-command-binding")
    if expected_binding is not None:
        require(request.get("binding") == expected_binding, "process-input-binding")
    require(request.get("cwd") == str(root.resolve()) and
            request.get("supervision") == "direct-child-only; logical limits; no OS quota",
            "process-supervision")
    require(type(request.get("environment")) is dict and
            all(type(key) is str and type(value) is str for key, value in request["environment"].items()),
            "process-environment")
    require(type(limits) is dict, "process-limits")
    for key, ceiling in (("deadline_seconds", 120), ("poll_seconds", .1), ("drain_seconds", 5)):
        value = limits.get(key)
        require(type(value) in (int, float) and math.isfinite(value) and 0 < value <= ceiling,
                "process-time-bound")
    capture = limits.get("capture_bytes_per_stream")
    require(type(capture) is int and 1 <= capture <= 1048576, "process-capture-bound")
    elapsed = result.get("elapsedSeconds")
    require(type(elapsed) in (int, float) and math.isfinite(elapsed) and elapsed >= 0,
            "process-elapsed")
    outcome = result.get("outcome")
    require(outcome in ("launch-failed", "cancelled-before-launch", "cancelled", "capture-failed",
                        "deadline", "exited", "interrupted", "supervisor-failed", "drain-incomplete"),
            "process-outcome")
    require(type(result.get("terminationConfirmed")) is bool, "process-termination")
    require(type(result.get("streams")) is dict and set(result["streams"]) == {"stdout", "stderr"},
            "process-stream-set")
    streams = {}
    for name, row in result["streams"].items():
        retained, observed = row.get("capturedBytes"), row.get("observedBytes")
        require(type(retained) is int and type(observed) is int and
                0 <= retained <= capture and observed >= retained, "process-stream-counts")
        require(type(row.get("eof")) is bool and type(row.get("overflow")) is bool,
                "process-stream-status")
        require(row["overflow"] is (observed > capture), "process-overflow")
        stream_error = row.get("error")
        require(stream_error is None or (type(stream_error) is str and bool(stream_error)),
                "process-stream-error")
        # A completed, error-free stream must account for every observed byte.
        # A failed write may truthfully retain only a prefix; overflow and an
        # unconfirmed drain likewise cannot establish complete consumption.
        censored = row["overflow"] or stream_error is not None or outcome == "drain-incomplete"
        require(retained == observed or censored, "unclassified-capture-loss")
        disposition = ("overflow-prefix" if row["overflow"] else
                       "failed-prefix" if stream_error is not None else
                       "unconfirmed-drain" if outcome == "drain-incomplete" else
                       "complete" if row["eof"] else "incomplete-eof")
        if outcome == "drain-incomplete":
            require(row.get("sha256") is None, "incomplete-capture-claimed-hash")
            streams[name] = {"captureDisposition": disposition}
        else:
            streams[name] = file_binding(root / (name + ".bin"),
                                         {"byteLength": retained, "sha256": row.get("sha256")},
                                         limit=capture)
            streams[name]["captureDisposition"] = disposition
    complete = (outcome == "exited" and result.get("returncode") == 0 and
                result["terminationConfirmed"] and result.get("error") is None and
                all(row["eof"] and not row["overflow"] and row.get("error") is None and
                    row["capturedBytes"] == row["observedBytes"]
                    for row in result["streams"].values()))
    if outcome == "exited":
        require(type(result.get("returncode")) is int and result["terminationConfirmed"],
                "exited-without-termination")
    return {"processOutcome": outcome, "completeSuccess": complete, "streams": streams,
            "request": request, "process": result}


def canonical_sha(value):
    return sha(json.dumps(value, sort_keys=True, separators=(",", ":"),
                          allow_nan=False).encode("utf-8"))


def absolute_binding(bound, *, limit=JSON_LIMIT):
    require(type(bound) is dict and set(bound) == {"path", "sha256", "byteLength"},
            "absolute-binding-schema")
    path = Path(bound["path"])
    require(path.is_absolute() and not path.is_symlink() and not path.is_junction(),
            "absolute-binding-path")
    file_binding(path, bound, limit=limit)
    return path


def stat_identity(path):
    info = path.stat()
    return {"st_dev": info.st_dev, "st_ino": info.st_ino, "size": info.st_size,
            "mtime_ns": info.st_mtime_ns, "ctime_ns": info.st_ctime_ns}


def audit_private_authority(request):
    """Rebind the existing decision, original grants, extraction and preflight.

    This routine reads only already bound text records. Its caller must finish
    it before opening either the selected media or a decoded derivative.
    """
    preflight = read_json(absolute_binding(request["preflight"]))
    authority = read_json(absolute_binding(preflight["authority"]))
    repository = Path(__file__).resolve().parents[2]
    require(Path(preflight["decision"]["path"]).resolve() == repository /
            ".local/rfw-decomposition-20261016/corpus.decoder-decision.private.json",
            "exact-existing-phase-decision")
    decision = read_json(absolute_binding(preflight["decision"]))
    require(decision.get("recordKind") == "scoped-user-permission-decision" and
            decision.get("ticket") == 164 and decision.get("choice") == "A" and
            decision.get("actor") == "Terry", "phase-decision")
    require(decision.get("allowedUse", {}).get("assertion") == "P0A-002" and
            decision.get("phaseReconciliation", {}).get("additionalPhase") == "differential",
            "phase-scope")
    require(authority.get("status") == "bound-pending-nondecoding-media-preflight" and
            authority.get("mediaOpened") is False and authority.get("decoderRun") is False,
            "authority-stage")
    require(authority.get("decision") == preflight["decision"], "authority-decision-binding")
    bindings = [decision["readinessPacket"], *decision["underlyingTextBindings"]]
    fixture, provenance = None, None
    for item in bindings:
        path = Path(item["path"])
        if not path.is_absolute():
            path = repository / path
        file_binding(path, item, limit=JSON_LIMIT)
        if path.name == decision["selectedFixture"]["id"] + ".json":
            fixture = read_json(path)
        if path.name == "PV-" + decision["selectedFixture"]["id"] + ".json":
            provenance = read_json(path)
    require(fixture is not None and provenance is not None, "fixture-provenance-binding")
    selected = decision["selectedFixture"]
    require(fixture.get("id") == selected["id"] and fixture.get("revision") == selected["fixtureRevision"] and
            fixture.get("artifact") == selected["recordedArtifact"] and
            fixture.get("lineage") == selected["lineage"], "fixture-lineage")
    require(fixture.get("rights", {}).get("analyze") is True and
            fixture.get("rights", {}).get("modify") is True and
            fixture.get("rights", {}).get("redistribute") is False and
            fixture.get("storageAccess") == "restricted", "fixture-rights")
    rights = provenance.get("rights", {}).get("permissions", {})
    require(rights.get("analyze") == rights.get("modify") == "allowed" and
            all(rights.get(key) == "denied" for key in
                ("redistribute", "includeInSource", "includeInRelease", "publishReports")),
            "provenance-rights")
    recipe_path = absolute_binding(authority["recipe"])
    require(authority["recipe"]["sha256"] == selected["lineage"]["recipeSha256"] and
            read_json(recipe_path) == authority.get("recipeRecord"), "extraction-recipe")
    recorded = selected["recordedArtifact"]
    require(request["input"]["sha256"] == recorded["sha256"] and
            request["input"]["byteLength"] == int(recorded["byteLength"]) and
            Path(request["input"]["path"]).resolve() ==
            Path(authority["selectedInput"]["absolutePath"]).resolve(), "selected-input-binding")
    require(preflight.get("source") == request["input"] and
            preflight.get("immutableObservation") is True and
            preflight.get("historicalIdentityMatches") is True and
            preflight.get("decoderRun") is False and
            preflight.get("before") == preflight.get("after") and
            preflight.get("syntax", {}).get("accepted") is True, "private-preflight")
    accepted = read_json(absolute_binding(request["acceptedQualification"]))
    require(accepted.get("schema") == "imageinfo-0075-accepted-qualification-v1" and
            accepted.get("profile") == request["profile"] and
            accepted.get("runtimeManifest") == request["runtimeManifest"] and
            accepted.get("independentReview") == "go", "authored-qualification-acceptance")
    return preflight


def audit_runtime(request, worker):
    manifest = read_json(absolute_binding(request["runtimeManifest"]))
    profile = manifest["componentProfile"]
    observed = worker.get("runtimeIdentity")
    require(type(observed) is dict and observed == manifest and
            observed.get("componentProfileCanonicalSha256") == canonical_sha(profile),
            "runtime-identity")
    require(observed.get("abi") == profile.get("abi") == "Windows-x64-LLP64-CPython-3.12.14" and
            (worker.get("loadedClosure") == profile.get("loadedNonOsModules")
             if worker["decoder"].get("nativeInvoked") else worker.get("loadedClosure") is None),
            "runtime-abi-or-loaded-closure")
    return rebind_runtime_files(request, manifest)


def rebind_runtime_files(request, manifest):
    """Read-only component/notices/ABI reconstruction, without a codec import."""
    profile = manifest["componentProfile"]
    require(manifest.get("componentProfileCanonicalSha256") == canonical_sha(profile) and
            manifest.get("abi") == profile.get("abi") == "Windows-x64-LLP64-CPython-3.12.14" and
            read_json(Path(__file__).resolve().parent / "component-profile.json") == profile,
            "component-profile-binding")
    settings = {"inputBytes": INPUT_LIMIT, "dimension": DIMENSION_LIMIT,
                "packedRgbBytes": PIXEL_LIMIT, "captureBytesPerStream": 16384,
                "childDeadlineSeconds": 120, "api": "tjDecompress2", "flags": 8192,
                "pixelFormat": "RGB", "extentPolicy": "single baseline 8-bit Huffman interleaved scan; no restart; all-zero suffix length 0 through 32 bytes inclusive"}
    admitted_profile = read_json(absolute_binding(request["profile"]))
    require(admitted_profile == {"schemaVersion": 1,
                                 "id": "0075-baseline-interleaved-rgb-zero-padding-v2",
                                 "settings": settings,
                                 "componentProfileCanonicalSha256": canonical_sha(profile)},
            "technical-profile")
    require(request.get("limits") == {"deadline_seconds": 120, "capture_bytes_per_stream": 16384,
                                      "poll_seconds": .01, "drain_seconds": 2},
            "qualified-process-limits")
    historical_root = Path(__file__).resolve().parent.parent / "0111-warning-jpeg"
    historical = read_json(historical_root / "profile.json")
    require(canonical_sha(historical) == "885ae7003d6272ac4527b23b5471467f2546beeaa87bf5877f73214c7997011e",
            "historical-profile-preserved")
    require(sha((historical_root / "qualify.py").read_bytes()) == historical["runtime"]["recipeSha256"] and
            sha((historical_root.parent / "0107-jpeg-validator/qualify.py").read_bytes()) ==
            historical["runtime"]["authoredRecipeSha256"], "historical-recipes-preserved")
    interpreter = Path(request["interpreter"]).resolve()
    python, root = interpreter.parent, interpreter.parent.parent
    package = python / "Lib/site-packages/PIL"
    distribution = package.parent / "pillow-12.3.0.dist-info"
    paths = {
        "python-executable": interpreter, "python-runtime": python / "python312.dll",
        "python-notices": python / "LICENSE.txt", "pillow-init": package / "__init__.py",
        "pillow-jpeg-plugin": package / "JpegImagePlugin.py", "pillow-image-file": package / "ImageFile.py",
        "pillow-image": package / "Image.py", "pillow-native-decoder": package / "_imaging.cp312-win_amd64.pyd",
        "pillow-metadata": distribution / "METADATA", "pillow-notices": distribution / "licenses/LICENSE",
        "pillow-sbom": distribution / "sboms/pillow-12.3.0.cdx.json",
    }
    require(set(paths) == set(profile["components"]), "component-set")
    for key, path in paths.items():
        file_binding(path, profile["components"][key])
    for name, binding in profile["loadedNonOsModules"].items():
        file_binding(local_path(root, name), binding)
    # The encoder's plugin preparation has a separately reviewed closure. It
    # neither widens nor replaces the exact decoder closure above.
    for field in ("loadedEncoderNonOsModules", "encoderSourceModules"):
        require(type(profile.get(field)) is dict and bool(profile[field]), "encoder-component-map")
        for name, binding in profile[field].items():
            file_binding(local_path(root, name), binding)
    manifest_path = root / "native/libheif/manifest.json"
    require(sha(manifest_path.read_bytes()) == profile["manifest"]["sha256"] and
            read_json(manifest_path) == profile["manifest"]["package"], "package-manifest")
    return {"componentProfileCanonicalSha256": canonical_sha(profile),
            "loadedNonOsModulesRebound": True, "encoderComponentsRebound": True,
            "encoderSourcesRebound": True, "noticesRebound": True}


def rebind_worker_report(root, terminal=None):
    """Bind the compact raw capture to its full, fixed-root retained report."""
    reference = read_json(root / "process/stdout.bin")
    require(type(reference) is dict and set(reference) == {"path", "sha256", "byteLength"},
            "worker-report-reference-schema")
    path = local_path(root, "worker-report.json")
    require(reference["path"] == "worker-report.json", "worker-report-fixed-path")
    file_binding(path, reference, limit=WORKER_REPORT_LIMIT)
    report = read_json(path)
    require(type(report) is dict and report.get("schema") == "imageinfo-0075-worker-v1", "worker-report-schema")
    if terminal is not None:
        require(terminal.get("workerReportBinding") == reference and
                terminal.get("worker") == report, "worker-capture-binding")
    return report


def audit_run(run_root, expectations_path):
    """Audit exactly one externally pinned retained cell without replay."""
    root = Path(run_root).resolve()
    expected = read_json(Path(expectations_path))
    require(expected.get("schema") == "imageinfo-0075-audit-expectations-v1", "expectations-schema")
    request_path = absolute_binding(expected["cellRequest"])
    require(request_path.resolve() == root / "cell-request.json", "expected-cell-request")
    request = read_json(request_path)
    require(request.get("schema") == "imageinfo-0075-cell-v1" and
            request.get("stage") in ("authored", "private"), "cell-schema")
    grant = read_json(absolute_binding(request["parentGrant"]))
    core = {key: value for key, value in request.items() if key != "parentGrant"}
    require(grant.get("schema") == "imageinfo-0075-parent-grant-v1" and
            grant.get("stage") == request["stage"] and
            grant.get("reviewedRequestSha256") == canonical_sha(core) and
            grant.get("authorizedBy") == "parent-after-independent-review", "parent-reviewed-request")
    required = {"run.py", "decoder.py", "syntax.py", "runtime.py", "controls.py", "corruption.py",
                "component-profile.json", "profile.json"}
    recipes = request.get("recipeBindings")
    require(type(recipes) is list and required <= {Path(row["path"]).name for row in recipes},
            "recipe-module-closure")
    require(len({row["path"] for row in recipes}) == len(recipes), "duplicate-recipe-binding")
    here = Path(__file__).resolve().parent
    require({here / name for name in required} <= {Path(row["path"]).resolve() for row in recipes},
            "actual-recipe-module-paths")
    for binding in recipes:
        absolute_binding(binding)
    absolute_binding(request["profile"])
    absolute_binding(request["runtimeManifest"])
    preflight = audit_private_authority(request) if request["stage"] == "private" else None
    result = read_json(root / "cell-result.json")
    require(result.get("schema") == "imageinfo-0075-cell-result-v1", "cell-result-schema")
    command = [request["interpreter"], str(Path(__file__).resolve().parent / "run.py"), "--worker",
               str(request_path.resolve()), sha(request_path.read_bytes())]
    invocation_path = root / "process-invocation.json"
    invoked = invocation_path.exists()
    require(result.get("processInvocationAttempted") is invoked, "process-invocation-marker")
    if invoked:
        require(read_json(invocation_path) == {"schema": "imageinfo-0075-invocation-v1",
                                              "command": command,
                                              "cellRequestSha256": sha(request_path.read_bytes())},
                "process-invocation-binding")
    if not (root / "process").exists():
        require(result.get("outcome") == ("invalid-experiment" if invoked else "not-run") and
                "worker" not in result, "not-run-classification")
        return {"schemaVersion": 1, "ticket": 75, "auditOutcome": "valid",
                "assertionOutcome": "invalid-experiment" if invoked else "not-run",
                "cameraAcceptanceSatisfied": False}
    require(invoked, "unrecorded-process-invocation")
    process = audit_process(root / "process", command,
                            {"cellRequestSha256": sha(request_path.read_bytes())})
    require(process["request"]["limits"] == request["limits"] and
            process["process"] == result.get("process"), "cell-process-binding")
    if not process["completeSuccess"]:
        require(result.get("outcome") == "invalid-experiment", "failed-process-classification")
        return {"schemaVersion": 1, "ticket": 75, "auditOutcome": "valid",
                "assertionOutcome": "invalid-experiment", "cameraAcceptanceSatisfied": False,
                "processOutcome": process["processOutcome"]}
    require(process["streams"]["stderr"]["byteLength"] == 0, "unexpected-worker-stderr")
    worker = rebind_worker_report(root, result)
    runtime = audit_runtime(request, worker)
    input_path = absolute_binding(request["input"], limit=INPUT_LIMIT)
    before = stat_identity(input_path)
    data = input_path.read_bytes()
    require(sha(data) == request["input"]["sha256"] and stat_identity(input_path) == before,
            "fresh-source-binding")
    require(result.get("sourceBefore") == result.get("sourceAfter") == before and
            result.get("immutableObservation") is True and
            worker.get("sourceBefore") == worker.get("sourceAfter") == before,
            "source-immutability")
    if preflight is not None:
        require(preflight["after"] == before and preflight["syntax"] == worker["decoder"]["syntax"],
                "preflight-source-binding")
        sentinel = read_json(Path(__file__).resolve().parents[2] /
                             ".local/work-wave-20261017e/0075-private-cell.once.json")
        require(sentinel.get("schema") == "imageinfo-0075-once-v1" and
                sentinel.get("request") == request and sentinel.get("attemptRoot") == str(root),
                "private-once-only-sentinel")
        worker_once = read_json(Path(__file__).resolve().parents[2] /
                                ".local/work-wave-20261017e/0075-private-worker.once.json")
        require(worker_once == {"schema": "imageinfo-0075-worker-once-v1",
                                "requestSha256": sha(request_path.read_bytes())},
                "private-worker-once-only-sentinel")
    artifact = worker.get("pixelArtifact")
    require(artifact in (None, "pixels.rgb"), "pixel-artifact-path")
    pixels = local_path(root, artifact) if artifact is not None else None
    require(worker["decoder"].get("pixelSinkCompleted") is (pixels is not None),
            "pixel-sink-completion")
    assertion = audit_decoder(worker["decoder"], data, pixels)
    require(result.get("outcome") == worker["decoder"].get("outcome"), "terminal-native-classification")
    wanted = expected.get("expectedAssertionOutcome")
    require(wanted in ("pass", "fail", "unsupported", "any"), "expected-assertion")
    require(wanted == "any" or assertion["assertionOutcome"] == wanted, "assertion-expectation")
    return {"schemaVersion": 1, "ticket": 75, "auditOutcome": "valid", **assertion,
            "runtime": runtime, "sourceImmutabilityObserved": True,
            "cameraAcceptanceSatisfied": request["stage"] == "private" and
            assertion["nativeEvaluated"] and assertion["assertionOutcome"] == "pass",
            "limits": "finite observations; no universal JPEG proof or OS quota"}


def positive_specification(case_id):
    """Reconstruct public formula/options without importing the encoder recipe."""
    base, separator, suffix_text = case_id.partition("-zero")
    require(base in POSITIVE_BASES, "authored-positive-identity")
    suffix = int(suffix_text) if separator else 0
    require((base == "formula-64-444" and 0 <= suffix <= 32) or suffix in (0, 32),
            "authored-positive-suffix")
    width, height, sampling = POSITIVE_BASES[base]
    formula = ("rgb-mod256-x13y7-x3y19-x23y11" if base in
               ("formula-64-444", "odd-19x17-420", "formula-256-422") else "solid-rgb-64-128-192")
    return {"id": case_id, "baseId": base, "width": width, "height": height,
            "formula": formula, "subsampling": sampling,
            "encoderOptions": {"quality": 90, "optimize": False, "progressive": False},
            "suffixBytes": suffix,
            "expected": {"syntaxAccepted": True, "nativeInvoked": True, "decodeAccepted": True,
                         "width": width, "height": height, "decodedBytes": width * height * 3,
                         "pixelFormat": "packed-RGB", "pixelEqualityToSourceAsserted": False,
                         "samePixelsAsBase": bool(suffix), "sameRgbBytesAsBase": bool(suffix),
                         "nativeInput": "full-stored-input-including-suffix"}}


def source_rgb_binding(specification):
    """Hash authored source RGB a row at a time, never allocate the full image."""
    width, height = specification["width"], specification["height"]
    require(type(width) is int and type(height) is int and
            0 < width <= DIMENSION_LIMIT and 0 < height <= DIMENSION_LIMIT and
            width * height * 3 <= PIXEL_LIMIT, "authored-source-rgb-bound")
    formula = specification["formula"]
    require(formula in ("rgb-mod256-x13y7-x3y19-x23y11", "solid-rgb-64-128-192"),
            "authored-source-rgb-formula")
    digest = hashlib.sha256()
    if formula == "solid-rgb-64-128-192":
        row = bytes((64, 128, 192)) * width
        for _ in range(height):
            digest.update(row)
    else:
        for y in range(height):
            row = bytearray(width * 3)
            for x in range(width):
                at = x * 3
                row[at:at + 3] = bytes(((x * 13 + y * 7) % 256,
                                         (x * 3 + y * 19) % 256,
                                         (x * 23 + y * 11) % 256))
            digest.update(row)
    return {"formula": formula, "byteLength": width * height * 3, "sha256": digest.hexdigest()}


def external_orchestration_grant(bound, purpose, reviewed, root):
    path = absolute_binding(bound)
    require(not path.resolve().is_relative_to(root), "external-orchestration-grant")
    require(read_json(path) == {"schema": "imageinfo-0075-orchestration-grant-v1",
                               "authorizedBy": "parent-after-independent-review",
                               "purpose": purpose, "reviewedArtifact": reviewed},
            "orchestration-grant-binding")


def audit_encoder_recipe(provenance, base_id, manifest):
    """Independently establish source formula and exact retained encoder recipe."""
    specification = positive_specification(base_id)
    require(provenance.get("schema") == "imageinfo-0075-encoder-result-v1" and
            provenance.get("baseId") == base_id and provenance.get("specification") == specification and
            provenance.get("sourceRgb") == source_rgb_binding(specification), "encoder-source-rgb")
    require(provenance.get("invocation") == {"api": "PIL.Image.frombytes/save", "mode": "RGB", "format": "JPEG",
                "dimensions": [specification["width"], specification["height"]],
                "subsampling": specification["subsampling"], "options": specification["encoderOptions"]},
            "encoder-invocation")
    require(provenance.get("componentIdentityBefore") == provenance.get("componentIdentityAfter") == manifest,
            "encoder-component-identities")


def audit_encoder_closure(provenance, manifest):
    """Both actual encoder observations must equal its separate exact pin."""
    pins = manifest["componentProfile"]["loadedEncoderNonOsModules"]
    mandatory = {"python/python.exe", "python/python312.dll",
                 "python/Lib/site-packages/PIL/_imaging.cp312-win_amd64.pyd"}
    require(type(pins) is dict and mandatory <= set(pins), "encoder-closure-pin")
    require(provenance.get("loadedEncoderClosureBefore") ==
            provenance.get("loadedEncoderClosureAfter") ==
            provenance.get("loadedEncoderClosure") == pins, "encoder-loaded-closure")
    return pins


def audit_encoder_provenance(plan):
    """Rebind six retained encodings, source formulas and their actual processes.

    No encoding is repeated. Formula hashes identify the lossless source RGB;
    they are not an oracle for equality to a lossy decoded image.
    """
    freeze_path = absolute_binding(plan["freeze"])
    frozen = read_json(freeze_path)
    require(frozen.get("schema") == "imageinfo-0075-authored-freeze-v1", "authored-freeze-schema")
    root = Path(frozen["root"]).resolve()
    require(freeze_path.resolve() == root / "freeze.json", "authored-freeze-location")
    here = Path(__file__).resolve().parent
    required = ("qualify.py", "controls.py", "corruption.py", "run.py", "audit.py",
                "decoder.py", "syntax.py", "runtime.py", "component-profile.json", "profile.json")
    require([Path(row["path"]).resolve() for row in frozen["recipeBindings"]] ==
            [here / name for name in required], "encoder-source-closure")
    for bound in frozen["recipeBindings"]:
        absolute_binding(bound)
    interpreter_path = absolute_binding(frozen["interpreter"], limit=INPUT_LIMIT)
    manifest = read_json(absolute_binding(frozen["runtimeManifest"]))
    require(frozen.get("nativeExecutionPerformed") is False and
            frozen.get("limits") == {"deadline_seconds": 120, "capture_bytes_per_stream": 16384,
                                      "poll_seconds": .01, "drain_seconds": 2}, "encoder-freeze-settings")
    technical_profile = next(bound for bound in frozen["recipeBindings"] if Path(bound["path"]).name == "profile.json")
    rebind_runtime_files({"interpreter": str(interpreter_path), "profile": technical_profile,
                          "limits": frozen["limits"]}, manifest)
    declared = frozen["controls"]["cases"]
    positive_ids = (set(POSITIVE_BASES) | {name + "-zero32" for name in POSITIVE_BASES} |
                    {"formula-64-444-zero" + str(count) for count in range(1, 32)})
    require(len(declared) == 43 and {row["id"] for row in declared} == positive_ids and
            all(row == positive_specification(row["id"]) for row in declared), "encoder-positive-declarations")
    declared_negative = frozen["corruptions"]["cases"]
    require(len(declared_negative) == 16 and {row["id"] for row in declared_negative} == set(NEGATIVE_CASES),
            "encoder-negative-declarations")
    for row in declared_negative:
        native = row["id"] in ("early-eoi", "immediate-eoi")
        require(row["baseId"] == "formula-64-444" and row["expected"] == {
                    "syntaxAccepted": native, "decodeAccepted": False if native else None,
                    "nativeInvoked": native, "nativeWarningOrErrorRequired": native,
                    "combinedAccepted": False}, "encoder-negative-expectations")
    proposals_path = absolute_binding(plan["proposals"])
    proposals = read_json(proposals_path)
    require(proposals_path.resolve() == root / "cell-proposals.json" and
            proposals.get("schema") == "imageinfo-0075-cell-proposals-v1" and
            proposals.get("freeze") == plan["freeze"], "encoder-proposal-binding")
    encoded_path = absolute_binding(proposals["encoding"])
    encoded = read_json(encoded_path)
    bases = encoded.get("bases")
    require(encoded_path.resolve() == root / "encoding-results.json" and
            encoded.get("schema") == "imageinfo-0075-encoding-results-v1" and
            type(bases) is list and len(bases) == 6 and
            {row["baseId"] for row in bases} == set(POSITIVE_BASES), "encoder-base-denominator")
    campaign = read_json(root / "encoding.once.json")
    require(campaign.get("freeze") == plan["freeze"], "encoder-campaign-binding")
    external_orchestration_grant(campaign["parentGrant"], "encode-six-authored-bases", plan["freeze"], root)
    base_inputs = {}
    for row in bases:
        base_id = row["baseId"]
        request_path = root / "encoding" / (base_id + ".json")
        request_binding = {"path": str(request_path), "byteLength": request_path.stat().st_size,
                           "sha256": sha(request_path.read_bytes())}
        encoder_request = read_json(request_path)
        expected_input = root / "bases" / (base_id + ".jpg")
        require(encoder_request == {"freeze": plan["freeze"], "parentGrant": campaign["parentGrant"],
                                    "baseId": base_id, "output": str(expected_input)}, "encoder-request")
        require(read_json(root / "bases" / (base_id + ".once.json")) == {"request": request_binding},
                "encoder-worker-once")
        observed = audit_process(root / "encoding" / base_id,
                                 expected_binding={"encoderRequest": request_binding})
        command = observed["request"]["command"]
        require(len(command) == 4 and command[:3] == [str(interpreter_path), str(here / "qualify.py"),
                                                     "--encoder-worker"] and
                json.loads(command[3], object_pairs_hook=_unique) == request_binding,
                "encoder-command")
        require(observed["completeSuccess"] and observed["streams"]["stderr"]["byteLength"] == 0 and
                observed["process"] == row.get("process") and
                observed["request"]["limits"] == frozen["limits"], "encoder-process-success")
        emitted = read_json(root / "encoding" / base_id / "stdout.bin")
        require(emitted == {"provenance": row["provenanceBinding"]}, "encoder-captured-provenance")
        provenance_path = absolute_binding(row["provenanceBinding"])
        provenance = read_json(provenance_path)
        require(provenance_path.resolve() == root / "encoding" / (base_id + ".provenance.json") and
                provenance == row.get("provenance") and
                read_json(root / "encoding" / (base_id + ".result.json")) == row,
                "encoder-provenance-binding")
        audit_encoder_recipe(provenance, base_id, manifest)
        closure = audit_encoder_closure(provenance, manifest)
        bundle = interpreter_path.parent.parent
        for name, bound in closure.items():
            file_binding(local_path(bundle, name), bound)
        input_path = absolute_binding(provenance["input"], limit=INPUT_LIMIT)
        require(input_path.resolve() == expected_input, "encoder-output-location")
        base_inputs[base_id] = provenance["input"]
    return {"freeze": frozen, "proposals": proposals, "baseInputs": base_inputs, "root": root}


def audit_plan(plan_binding):
    """Evaluate every externally preregistered retained authored cell once.

    The plan's identities and expected outcomes come from caller review, never
    from collected output. No assertion may be silently omitted or retried.
    """
    plan = read_json(absolute_binding(plan_binding))
    require(plan.get("schema") == "imageinfo-0075-authored-audit-plan-v1", "audit-plan-schema")
    cells = plan.get("cells")
    require(type(cells) is list and cells and
            len({cell["id"] for cell in cells}) == len(cells) and
            len({str(Path(cell["runRoot"]).resolve()) for cell in cells}) == len(cells),
            "authored-plan-cell-set")
    positive_ids = (set(POSITIVE_BASES) | {name + "-zero32" for name in POSITIVE_BASES} |
                    {"formula-64-444-zero" + str(count) for count in range(1, 32)})
    require({cell["id"] for cell in cells} == positive_ids | set(NEGATIVE_CASES),
            "authored-plan-denominator")
    encoding = audit_encoder_provenance(plan)
    execution = read_json(encoding["root"] / "execution.once.json")
    require(execution.get("plan") == plan_binding, "authored-execution-campaign")
    external_orchestration_grant(execution["parentGrant"], "execute-59-authored-cells",
                                 plan_binding, encoding["root"])
    proposed = encoding["proposals"]["cells"]
    require(len(proposed) == len(cells) and {cell["id"] for cell in proposed} == {cell["id"] for cell in cells},
            "authored-proposal-denominator")
    proposals = {cell["id"]: cell for cell in proposed}
    results, pixels, inputs = [], {}, {}
    for cell in cells:
        expectations = absolute_binding(cell["expectations"])
        expected = read_json(expectations)
        require(expected.get("expectedAssertionOutcome") == cell.get("expectedAssertionOutcome") and
                cell.get("expectedAssertionOutcome") in ("pass", "fail", "unsupported"),
                "authored-plan-expectation")
        request = read_json(absolute_binding(expected["cellRequest"]))
        require(request.get("stage") == "authored", "authored-plan-private-input")
        proposal = proposals[cell["id"]]
        core = {key: value for key, value in request.items() if key != "parentGrant"}
        frozen = encoding["freeze"]
        require(core == proposal["core"] and canonical_sha(core) == proposal["reviewedRequestSha256"] and
                proposal["runRoot"] == cell["runRoot"] == str(encoding["root"] / "runs" / cell["id"]) and
                proposal["expectedAssertionOutcome"] == cell["expectedAssertionOutcome"], "authored-cell-proposal")
        original_request = absolute_binding(cell["request"])
        require(original_request == encoding["root"] / "requests" / (cell["id"] + ".json") and
                read_json(original_request) == request and
                all(cell["request"][key] == expected["cellRequest"][key] for key in ("sha256", "byteLength")),
                "authored-prepared-request-binding")
        require(request["recipeBindings"] == frozen["recipeBindings"] and
                request["runtimeManifest"] == frozen["runtimeManifest"] and
                request["limits"] == frozen["limits"] and request["interpreter"] == frozen["interpreter"]["path"],
                "authored-cell-freeze")
        outcome = ("pass" if cell["id"] in positive_ids else
                   "fail" if cell["id"] in ("early-eoi", "immediate-eoi") else "unsupported")
        require(cell["expectedAssertionOutcome"] == outcome, "authored-preregistered-expectation")
        result = audit_run(Path(cell["runRoot"]), expectations)
        require(result.get("auditOutcome") == "valid" and
                result.get("assertionOutcome") == cell["expectedAssertionOutcome"],
                "authored-plan-unmet-cell")
        if result["assertionOutcome"] == "pass":
            consumption = result.get("decodedConsumption")
            specification = positive_specification(cell["id"])
            require(type(consumption) is dict and consumption.get("byteLength") ==
                    specification["width"] * specification["height"] * 3 and
                    type(consumption.get("sha256")) is str and len(consumption["sha256"]) == 64,
                    "authored-decoded-consumption-return")
            pixels[cell["id"]] = consumption
        # audit_run already bound/grant-checked these authored bytes. Retain them
        # only to independently compare exact suffix/corruption constructions.
        inputs[cell["id"]] = absolute_binding(request["input"], limit=INPUT_LIMIT)
        if cell["id"] in positive_ids:
            base_id = cell["id"].split("-zero", 1)[0]
            width, height, sampling = POSITIVE_BASES[base_id]
            extent = independent_extent(inputs[cell["id"]].read_bytes())
            worker = rebind_worker_report(Path(cell["runRoot"]))
            require((extent["width"], extent["height"]) == (width, height) and
                    worker["decoder"].get("subsamplingRaw") == sampling,
                    "authored-control-dimensions-or-sampling")
        results.append({"id": cell["id"], "assertionOutcome": result["assertionOutcome"],
                        **({"decodedConsumption": result["decodedConsumption"]}
                           if result["assertionOutcome"] == "pass" else {})})
    for base in POSITIVE_BASES:
        base_path = absolute_binding(encoding["baseInputs"][base], limit=INPUT_LIMIT)
        require(base_path.read_bytes() == inputs[base].read_bytes(), "authored-encoded-base-binding")
        for count in (range(1, 33) if base == "formula-64-444" else (32,)):
            suffixed = base + "-zero" + str(count)
            require(inputs[suffixed].read_bytes() == inputs[base].read_bytes() + bytes(count) and pixels[base] == pixels[suffixed],
                    "authored-suffix-byte-or-pixel-disagreement")
    mutations = independent_corruptions(inputs["formula-64-444"].read_bytes())
    require(all(inputs[name].read_bytes() == mutations[name] for name in NEGATIVE_CASES),
            "authored-corruption-construction")
    return {"schemaVersion": 1, "ticket": 75, "auditOutcome": "valid",
            "finiteAuthoredProfileQualified": True, "cells": results,
            "cameraAcceptanceSatisfied": False,
            "limits": "only the exact preregistered authored cells; no universal JPEG proof"}


def independent_corruptions(base):
    """Reconstruct the fixed public fault recipes without importing their code."""
    extent = independent_extent(base)
    require(extent is not None and extent["suffixBytes"] == 0, "authored-corruption-base")
    scan, end = extent["scanStart"], extent["eoiEnd"] - 2
    cut = scan + (end - scan) // 2
    require(end - scan >= 4, "authored-corruption-entropy")
    markers, offset = {}, 2
    while offset < scan:
        marker = base[offset + 1]
        markers.setdefault(marker, offset)
        offset += 2 + int.from_bytes(base[offset + 2:offset + 4], "big")
    rows = {
        "entropy-truncated": base[:cut], "early-eoi": base[:cut] + b"\xff\xd9",
        "immediate-eoi": base[:scan] + b"\xff\xd9",
        "suffix-second-jpeg": base + base,
        "entropy-restart-marker": base[:scan] + b"\xff\xd0" + base[scan:],
        "entropy-tem-marker": base[:scan] + b"\xff\x01" + base[scan:],
        "duplicate-soi": base[:2] + b"\xff\xd8" + base[2:],
    }
    rows["suffix-zero33"] = base + bytes(33)
    for name, position in (("suffix-nonzero", 0), ("suffix-nonzero-middle", 16),
                           ("suffix-nonzero-last", 31)):
        rows[name] = base + bytes(position) + b"\x01" + bytes(31 - position)
    replacements = {
        "segment-length-one": (markers[219] + 2, b"\x00\x01"),
        "segment-length-overrun": (markers[219] + 2, b"\xff\xff"),
        "quant-table-selector": (markers[192] + 12, b"\x04"),
        "huffman-table-selector": (markers[218] + 6, b"\x44"),
        "scan-nonbaseline": (scan - 3, b"\x01"),
    }
    for name, (offset, replacement) in replacements.items():
        rows[name] = base[:offset] + replacement + base[offset + len(replacement):]
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--expectations", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        expectation = read_json(args.expectations)
        request = read_json(absolute_binding(expectation["cellRequest"]))
        if request.get("stage") == "private":
            private_root = Path(__file__).resolve().parents[2] / ".local"
            require(all(path.resolve().is_relative_to(private_root.resolve()) for path in
                        (args.output, args.expectations, args.run_root)), "private-report-destination")
        result = audit_run(args.run_root, args.expectations)
    except (InvalidEvidence, KeyError, TypeError, ValueError, OSError) as error:
        result = {"schemaVersion": 1, "ticket": 75, "auditOutcome": "invalid-experiment",
                  "reason": str(error) if isinstance(error, InvalidEvidence) else "unreadable-evidence"}
        private_root = Path(__file__).resolve().parents[2] / ".local"
        if not args.output.resolve().is_relative_to(private_root.resolve()):
            return 1
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    # No result, path, hash or camera-derived Boolean leaks onto stdout/stderr.
    return 0 if result.get("auditOutcome") == "valid" else 1


if __name__ == "__main__":
    sys.exit(main())
