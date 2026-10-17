"""Independent selected EXIF:ISO correspondence and retained-sample audit (#0151).

Numeric outputs from camera runs are restricted evidence: write reports under
.local only. A matched singleton is a bounded correspondence, never JSON or full
producer-work equivalence. This module launches no tool or media reader.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import statistics


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def strict(data, bound=4 * 1024**2):
    require(isinstance(data, bytes) and len(data) <= bound, "bounded byte capture")
    def pairs(items):
        out = {}
        for key, value in items:
            require(key not in out, "duplicate JSON member")
            out[key] = value
        return out
    return json.loads(data.decode("utf-8"), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


def load(path):
    with Path(path).open("rb") as stream:
        data = stream.read(256 * 1024**2 + 1)
    return strict(data, 256 * 1024**2)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def native_iso(data, expected_path=None):
    n = strict(data)
    require(n["schemaVersion"] == 1 and len(n["files"]) == 1, "one native file")
    f = n["files"][0]
    require(f["state"] == "read" and f["transactionId"] is None, "native read outcome")
    require(len(f["issues"]) == 1 and f["issues"][0]["code"] == "COVERAGE_PARTIAL"
            and f["issues"][0]["severity"] == "warning", "declared native partial-coverage warning")
    require(not f["effects"]["changed"], "native no-change outcome")
    if expected_path is not None:
        require(f["path"] == expected_path, "native source operand")
    s = f["snapshot"]
    require(s["basis"] == "observed" and not s["issues"], "native observed issue-free snapshot")
    require(len(s["sources"]) == len(s["documents"]) == 1, "native source/document multiplicity")
    require(s["documents"][0]["format"] == "CR3", "native document format")
    require(len(s["coverage"]) == 1, "native coverage multiplicity")
    c = s["coverage"][0]
    require(c["state"] == "partial" and c["namespace"] == "*" and c["pathPrefix"] == [], "bounded native coverage")
    require(len(s["occurrences"]) == 1, "exact singleton selected occurrence")
    o = s["occurrences"][0]
    require(o["tag"]["namespace"] == "exif" and o["tag"]["name"] == "ISO"
            and o["tag"]["nativeId"] == "34855", "EXIF ISO native identity")
    require(o["documentRef"] == s["documents"][0]["id"] and not o["issueRefs"], "native occurrence document/issues")
    require(sum(p["kind"] == "box" and p["name"] == "CMT2" for p in o["path"]) == 1,
            "CMT2 source allocation identity")
    require(o["path"][-1]["kind"] == "tag" and o["path"][-1]["name"] == "34855", "native tag path")
    v = o["values"]
    require(v["raw"]["state"] == "present" and v["raw"] == v["normalized"], "exact present raw normalization")
    require(v["raw"]["value"]["kind"] == "integer", "native integer kind")
    decimal = v["raw"]["value"]["decimal"]
    require(isinstance(decimal, str) and re.fullmatch(r"0|[1-9][0-9]*", decimal), "canonical unsigned integer")
    require(int(decimal) <= 65535, "stored uint16 ISO range")
    require(v["normalization"] == dict(ruleRef="identity-exact-stored-value", reversibility="exact",
            assumptions=[], dependencies=[], unit=None), "identity normalization declaration")
    require(v["display"] == dict(state="unavailable", reason="Not requested"), "raw-only native view")
    require(o["origin"]["kind"] == "stored" and o["origin"]["encoding"] == "uint16"
            and o["origin"]["byteOrder"] in ("little", "big"), "native stored primitive")
    resources = [r for r in s["resources"] if r["id"] == o["origin"]["resourceRef"]]
    require(len(resources) == 1, "unique native source resource")
    resource = resources[0]
    require(resource["byteLength"] == "2" and resource["content"]["kind"] == "source-ranges", "native uint16 extent")
    spans = resource["content"]["ranges"]
    require(len(spans) == 1 and spans[0]["length"] == "2" and spans[0]["ref"] == s["sources"][0]["id"], "native span binding")
    require(0 <= int(spans[0]["offset"]) <= int(s["sources"][0]["byteLength"]) - 2, "native span bounds")
    return dict(decimal=decimal, occurrenceCount=1, namespace="EXIF", ifd="ExifIFD", tagId="34855",
                nativeCoverage="partial", origin=spans[0], byteOrder=o["origin"]["byteOrder"])


def reference_iso(data, expected_path=None):
    r = strict(data)
    require(isinstance(r, list) and len(r) == 1 and isinstance(r[0], dict), "one reference file")
    record = r[0]
    require(set(record) == {"SourceFile", "EXIF:ExifIFD:ISO"}, "exact reference family/IFD singleton; no duplicate or extra fields")
    require(isinstance(record["SourceFile"], str), "reference source identity")
    if expected_path is not None:
        require(record["SourceFile"] == expected_path, "reference source operand")
    value = record["EXIF:ExifIFD:ISO"]
    require(type(value) is int and 0 <= value <= 65535, "reference numeric uint16 ISO")
    return value


def audit_pair(native_bytes, reference_bytes, expected_path=None, reference_path=None):
    witness = native_iso(native_bytes, expected_path)
    value = reference_iso(reference_bytes, reference_path)
    require(int(witness["decimal"]) == value, "selected exact numeric mismatch")
    return witness


def audit_rights(fixture):
    """Check existing native differential admission and retained provenance scope."""
    m, p = load(fixture["admission"]), load(fixture["provenance"])
    require(m["admission"] == "admitted" and m["media"]["format"] == "CR3"
            and m["media"]["captureMode"] == "full-raw", "existing full RAW admission")
    require("differential" in m["allowedPhases"], "existing native differential phase")
    require(m["rights"]["status"] == "approved" and m["rights"]["analyze"] is True
            and m["rights"]["redistribute"] is False, "private analysis rights")
    require(p["rights"]["permissions"]["analyze"] == "allowed"
            and p["rights"]["permissions"]["publishReports"] == "denied", "provenance private reports")
    require(m["artifact"]["sha256"] == p["artifact"]["sha256"] == fixture["inputSha256"], "grant/source hash binding")
    require(sha(fixture["input"]) == fixture["inputSha256"], "actual source hash")
    require(sha(fixture["oracle"]) == fixture["oracleSha256"], "historical oracle binding")
    return {"status": "private-analysis-only", "admissionSha256": sha(fixture["admission"]),
            "provenanceSha256": sha(fixture["provenance"])}


def paired_statistics(pairs):
    """Each input is (native ns, reference ns); no failed/censored slots allowed."""
    require(len(pairs) == 10, "fixed per-round measured-pair denominator")
    require(all(type(a) is int and type(b) is int and a > 0 and b > 0 for a, b in pairs), "positive complete paired elapsed samples")
    ratios = [b / a for a, b in pairs]
    # Fixed descriptive order-statistic interval; no IID/machine confidence claim.
    ordered = sorted(ratios)
    return dict(statistic="median of per-pair reference/native elapsed-time ratios",
                denominator=10, median=statistics.median(ratios), min=min(ratios), max=max(ratios),
                descriptiveOrderInterval=[ordered[0], ordered[-1]],
                uncertainty="observed range only; adjacent cache-exposed host samples, no population confidence interval")


def audit_identity_checkpoint(folder, rows, expected_argv, manifest_sha, verifier_sha):
    """Verify one retained batch including failed/cancelled bounded prefixes."""
    folder = Path(folder)
    record = load(folder / "record.private.json")
    request = (folder / "request.json").read_bytes()
    stdout, stderr = (folder / "stdout").read_bytes(), (folder / "stderr").read_bytes()
    require(0 < len(rows) <= 4096 and len(request) <= 1048576, "identity request bounds")
    expected_request = json.dumps({"paths": [r["path"] for r in rows]}, ensure_ascii=True).encode("utf-8")
    require(request == expected_request, "exact indexed identity request")
    require(record["argv"] == expected_argv and record["verifierSha256"] == verifier_sha
            and record["priorManifestSha256"] == manifest_sha, "identity verifier/manifest/recipe binding")
    require(record["requestSha256"] == hashlib.sha256(request).hexdigest(), "identity request hash")
    for channel, data in (("stdout", stdout), ("stderr", stderr)):
        require(len(data) <= 524288 and type(record[channel + "Bytes"]) is int
                and len(data) <= record[channel + "Bytes"], "identity capture bound/total")
        require(record[channel + "Sha256"] == hashlib.sha256(data).hexdigest(), "identity retained channel hash")
    require(record["outcome"] in ("exited", "launch-error", "output-limit", "io-error", "timeout", "cancelled"), "identity outcome")
    expected = b"".join(f"{i}\t{row['sha256']}\t{int(row['byteLength'])}\n".encode("ascii")
                        for i, row in enumerate(rows))
    match = (record["outcome"] == "exited" and record["exitCode"] == 0
             and stdout == expected and not stderr)
    require(type(record["exactMatch"]) is bool and record["exactMatch"] == match, "independent identity match classification")
    if match:
        require(record["stdoutBytes"] == len(stdout) and record["stderrBytes"] == 0, "complete identity output totals")
    return dict(checkpoint=folder.name, exactMatch=match, outcome=record["outcome"],
                recordSha256=sha(folder / "record.private.json"), requestSha256=record["requestSha256"],
                stdoutSha256=record["stdoutSha256"], stderrSha256=record["stderrSha256"])


def audit_identity_checkpoints(p):
    """Read all bounded campaign checkpoints; never launch or rehash via UNC."""
    env = load(p["priorReferenceEnvironment"])
    require(env["versionProbe"].strip() == "13.59" and env["configurationSuppressionVerified"] is True,
            "existing reference version/config evidence")
    require(env["runtimeBefore"] == env["runtimeAfter"] and env["sourceBefore"] == env["sourceAfter"],
            "historical reference stable identities")
    require(p["distribution"] == "Ubuntu" and p["referenceLibrary"] == "/mnt/c/Projects/imageinfo/.local/tools/exiftool-13.59-source/lib"
            and p["referenceScript"] == "/mnt/c/Projects/imageinfo/.local/tools/exiftool-13.59-source/exiftool", "existing reference recipe")
    rows = {}
    for row in env["sourceBefore"] + env["runtimeBefore"]:
        path = row["path"]
        require(path.startswith("/") and ".." not in Path(path).parts and not any(c in path for c in "\x00\r\n"), "absolute reference manifest path")
        require(path not in rows or rows[path] == row, "nonconflicting reference manifest")
        rows[path] = row
    verifier = Path(__file__).parent / "check_comparable_reference_151.pl"
    require(str(verifier.resolve()) in p["bindings"], "mandatory batch verifier binding")
    argv = [p["referenceLauncher"], "--distribution", "Ubuntu", "--exec", "/usr/bin/perl",
            "/mnt/c/" + str(verifier.resolve()).replace("\\", "/")[3:]]
    root = Path(p["identityCheckRoot"]).resolve()
    require(".local" in root.parts, "private identity capture root")
    folders = sorted(root.iterdir())
    require(0 < len(folders) <= 16 and all(x.is_dir() and not x.is_symlink() for x in folders), "identity checkpoint bounds")
    require([x.name for x in folders] == [f"checkpoint-{i:02d}" for i in range(len(folders))], "all identity checkpoint positions retained")
    return [audit_identity_checkpoint(folder, list(rows.values()), argv, sha(p["priorReferenceEnvironment"]), sha(verifier)) for folder in folders]


def audit_campaign_identity_links(checkpoints, record):
    links = record["identityCheckpoints"]
    require(isinstance(links, list) and 0 < len(links) <= 6, "campaign identity boundary count")
    require(len(links) == len(checkpoints), "every fresh campaign identity checkpoint must be linked")
    require(record["status"] != "completed" or len(links) == 6, "six completed campaign identity boundaries")
    actual = {x["checkpoint"]: x for x in checkpoints}
    names = [link["checkpoint"] for link in links]
    require(len(set(names)) == len(names) and all(name in actual for name in names), "unique retained campaign identity links")
    indexes = [int(name.removeprefix("checkpoint-")) for name in names]
    require(indexes == list(range(len(checkpoints))), "all indexed campaign identity boundaries in original order")
    for link in links:
        require(set(link) == {"checkpoint", "recordSha256"} and link["recordSha256"] == actual[link["checkpoint"]]["recordSha256"], "campaign identity record hash binding")
        require(record["status"] != "completed" or actual[link["checkpoint"]]["exactMatch"], "failed completed campaign identity boundary")
    return links


def retained_audit(root):
    """Reconstruct every sample/failed capture, semantics and per-round denominator."""
    from audit_read_resources_144 import canonical, oracle_file, wire
    from audit_read_telemetry import audit as resource_audit
    root = Path(root).resolve()
    require(".local" in root.parts, "private evidence root")
    p, r = load(root / "protocol.private.json"), load(root / "record.private.json")
    require(r["protocolSha256"] == sha(root / "protocol.private.json"), "preregistered protocol binding")
    require(p["revision"] == r["revision"] == "comparable-read-151-v1", "protocol revision")
    for path, digest in p["bindings"].items():
        require(sha(path) == digest, "source/executable/tool/config binding")
    for filename in ("audit_comparable_read_151.py", "audit_read_resources_144.py", "audit_read_telemetry.py",
                     "measure_comparable_read_151.py", "read_benchmark.py", "measure_batch_read.py",
                     "measure_read_resources_144.py", "read_telemetry.py", "check_comparable_reference_151.pl"):
        require(str((Path(__file__).parent / filename).resolve()) in p["bindings"], "independent auditor helper binding")
    require(Path(p["identityCheckRoot"]).resolve() == root / "reference-identity", "campaign identity directory binding")
    identity_checks = audit_identity_checkpoints(p)
    identity_links = audit_campaign_identity_links(identity_checks, r)
    require(p["taskAdmission"] == dict(ticket=151, scope="private-read-only-comparable-analysis",
        sourceMutationAllowed=False, reportPublicationAllowed=False), "exact private task admission")
    require(sha(p["priorProtocol"]) == p["priorProtocolSha256"], "prior admission protocol binding")
    prior = load(p["priorProtocol"])
    require(p["fixture"] == prior["fixtureSet"][0], "exact existing admitted first input")
    required_evidence = {prior["primaryGrant"], prior["privacyReview"]}
    required_evidence.update(p["fixture"][key] for key in ("admission", "provenance", "correctness"))
    require(required_evidence <= prior["evidenceSha256"].keys(), "rights evidence completeness")
    for path, digest in prior["evidenceSha256"].items():
        require(sha(path) == digest, "original permission/privacy/admission evidence binding")
    grant, privacy = load(prior["primaryGrant"]), load(prior["privacyReview"])
    require("run metadata tools on copies" in grant["requestedScope"]
            and grant["publicImagesOrIdentifyingMetadata"] == "not authorized", "existing private tool analysis grant")
    require(privacy["status"] == "restricted" and privacy["publicClearance"] is False, "restricted privacy scope")
    rights = audit_rights(p["fixture"])
    reference_argv = [p["referenceLauncher"], "--distribution", p["distribution"], "--exec",
        "/usr/bin/perl", "-I", p["referenceLibrary"], p["referenceScript"], "-config", "", "-j", "-n", "-a",
        "-G0:1:4", "-EXIF:ISO", "--", p["referenceInput"]]
    native_argv = [p["binary"], "metadata", "read", "--values", "raw", "--output", "json",
        "--max-bytes", "8388608", "--tag", "EXIF:ISO", "--", p["fixture"]["input"]]
    require(r["argv"] == dict(native=native_argv, reference=reference_argv), "exact producer work arguments")
    review = load(p["correspondenceReview"])
    require(review["approved"] is True and review["inputSha256"] == p["fixture"]["inputSha256"]
        and review["nativeOracleSha256"] == p["fixture"]["oracleSha256"]
        and review["referenceArguments"] == reference_argv and review["selectedField"] == "EXIF:ISO", "correspondence review binding")
    expected = canonical(load(p["fixture"]["oracle"]))
    expected["files"] = [oracle_file(p["fixture"], "EXIF:ISO", "raw")]
    require(wire(load(root / "expected-native.private.json")) == wire(expected), "independent native oracle projection")
    require(r["status"] in ("completed", "aborted") and r["publicCameraResultsExported"] is False, "retained run scope")
    require(p["timeoutMs"] == 30000 and p["captureBytes"] == 4194304, "fixed collection budgets")
    schedule = [dict(round=round_no, pair=pair_no, phase="warmup" if pair_no < 3 else "sample",
                    order=["native", "reference"] if (round_no * 13 + pair_no) % 2 == 0 else ["reference", "native"])
                for round_no in range(3) for pair_no in range(13)]
    require(p["schedule"] == schedule, "independent fixed counterbalanced schedule")
    require(len(r["pairs"]) <= 39 and (r["status"] != "completed" or len(r["pairs"]) == 39), "fixed total attempt slots")
    require(r["sourceChecks"] and all(x == r["sourceChecks"][0] for x in r["sourceChecks"]), "unchanged source boundaries")
    require(r["status"] != "completed" or len(r["sourceChecks"]) == 4, "all round source boundaries")
    initial = r["sourceChecks"][0]
    stat = Path(p["fixture"]["input"]).stat()
    require(initial == dict(sha256=sha(p["fixture"]["input"]), bytes=stat.st_size, mtimeNs=stat.st_mtime_ns,
                           device=stat.st_dev, inode=stat.st_ino), "current source identity")
    rounds = [dict(round=i, attemptedPairs=0, eligiblePairs=0, failedPairs=0, resourceChecks=[], nativeResources=[], pairs=[]) for i in range(3)]
    for position, pair in enumerate(r["pairs"]):
        entry = schedule[position]
        require(all(pair[k] == v for k, v in entry.items()), "retained attempt ordering/phase")
        report = rounds[entry["round"]]
        report["attemptedPairs"] += 1
        payloads, correct = {}, {}
        require(set(pair["attempts"]) <= {"native", "reference"}, "unknown producer")
        require(r["status"] != "completed" or set(pair["attempts"]) == {"native", "reference"}, "missing producer capture")
        for producer, sample in pair["attempts"].items():
            payloads[producer] = {}
            require(type(sample["elapsedNs"]) is int and sample["elapsedNs"] > 0, "elapsed nanoseconds")
            require(sample["censored"] == (sample["outcome"] in ("timeout", "output-limit", "consumer-error", "cancelled", "telemetry-limit")), "censor classification")
            for channel in ("stdout", "stderr"):
                path = (root / sample["captures"][channel]).resolve()
                require(path.is_relative_to(root / "captures"), "capture confinement")
                data = path.read_bytes()
                require(len(data) == sample[channel + "CapturedBytes"] <= min(sample[channel + "Bytes"], p["captureBytes"]), "retained capture byte denominator")
                digest = hashlib.sha256(data).hexdigest()
                require(digest == sample[channel + "Sha256"] or (sample["outcome"] == "launch-error" and not data and sample[channel + "Sha256"] is None), "retained capture digest")
                payloads[producer][channel] = data
            correct[producer] = (sample["outcome"] == "exited" and sample["exitCode"] == 0
                                 and not sample["censored"] and not payloads[producer]["stderr"])
            if producer == "native":
                try:
                    correct[producer] &= wire(canonical(strict(payloads[producer]["stdout"]))) == wire(expected)
                except (ValueError, KeyError, TypeError, IndexError):
                    correct[producer] = False
                t = sample["telemetry"]
                try:
                    probe = dict(sample, index=0, phase="sample", eligible=False, correctness="pass" if correct[producer] else "fail")
                    resource_audit(dict(schemaVersion=2, purpose="metadata-read", telemetry=[t], elapsedRecord=dict(
                        attempts=[probe], configuration=dict(warmups=0, repeats=1, captureBytes=p["captureBytes"]),
                        status="cancelled" if probe["outcome"] == "cancelled" else "completed", sourceUnchanged=True, binaryUnchanged=True)))
                    resource_result = dict(passed=True, valid=t["valid"], reason=None)
                except (ValueError, KeyError, TypeError, IndexError) as error:
                    resource_result = dict(passed=False, valid=False, reason=str(error))
                report["resourceChecks"].append(resource_result)
                values = dict(t["samples"][-1]["values"]) if resource_result["passed"] and t["samples"] else {}
                report["nativeResources"].append(dict(pair=entry["pair"], phase=entry["phase"],
                    valid=resource_result["valid"], arithmeticAuditPassed=resource_result["passed"],
                    directProcessFinalCounters=values,
                    sampledMaxima=t.get("sampledMaxima") if resource_result["passed"] else None,
                    observerWallNs=t.get("observerWallNs") if resource_result["passed"] else None,
                    reason=resource_result["reason"],
                    observationErrors=t.get("errors"), membership=t.get("membership"), stopReason=t.get("stopReason"),
                    counterErrors=[s.get("errors") for s in t.get("samples", [])],
                    scope="sampled direct process; observed membership is not containment; logical I/O is not device I/O"))
            else:
                require(sample["telemetry"] == dict(available=False, reason="reference-wrapper-descendant-membership-not-qualified",
                    cpuNs=None, memoryBytes=None, logicalIoBytes=None, physicalIoBytes=None), "reference descendants require unavailable counters")
            require(sample["correctness"] == correct[producer], "producer-specific complete-work correctness")
        match = False
        if set(payloads) == {"native", "reference"}:
            try:
                audit_pair(payloads["native"]["stdout"], payloads["reference"]["stdout"], p["fixture"]["input"], p["referenceInput"])
                match = True
            except (ValueError, KeyError, TypeError, IndexError):
                pass
        require(pair["correspondence"] == ("pass" if match else "fail") or
                (r["status"] == "aborted" and len(payloads) < 2 and pair["correspondence"] == "not-checked"),
                "independent semantic correspondence")
        eligible = entry["phase"] == "sample" and match and len(correct) == 2 and all(correct.values()) and r["status"] == "completed"
        require(pair["eligible"] == eligible, "paired eligibility")
        if entry["phase"] == "sample":
            if eligible:
                report["eligiblePairs"] += 1
                report["pairs"].append((pair["attempts"]["native"]["elapsedNs"], pair["attempts"]["reference"]["elapsedNs"]))
            else:
                report["failedPairs"] += 1
    for report in rounds:
        values = report.pop("pairs")
        report["plannedMeasuredPairs"] = 10
        report["ratio"] = paired_statistics(values) if len(values) == 10 else None
        report["ratioUnavailableReason"] = None if len(values) == 10 else "incomplete/failed fixed measured-pair denominator; no selective successful-subset ratio"
    return dict(scope="private singleton EXIF:ISO observations; producer work differs; no broad parity", rights=rights,
                status=r["status"], rounds=rounds, pooledRatio=None,
                referenceResources="unavailable: wrapper descendants not qualified", referenceIdentityCheckpoints=identity_checks,
                campaignIdentityLinks=identity_links)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", required=True)
    root = Path(parser.parse_args().run_root).resolve()
    result = retained_audit(root)
    with (root / "audit.private.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
