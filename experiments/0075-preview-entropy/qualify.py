"""Fixed authored qualification orchestration, with external parent review gates.

Import and freeze() are preparation only. No function creates a grant. Encoding
and decoding are separate explicit operations, each consuming caller-pinned
review artifacts outside the fresh evidence root. No private media entry exists.
"""
from dataclasses import asdict
import argparse
import hashlib
import json
from pathlib import Path
import sys

import controls
import corruption
import run

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MODULES = ("qualify.py", "controls.py", "corruption.py", "run.py", "audit.py",
           "decoder.py", "syntax.py", "runtime.py", "component-profile.json", "profile.json")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def binding(path):
    path = Path(path).resolve(strict=True)
    data = path.read_bytes()
    return {"path": str(path), "byteLength": len(data), "sha256": sha(data)}


def read_json(bound):
    return json.loads(run.read_bound(bound, limit=16 * 1024 * 1024))


def write(path, value):
    run.write_json(Path(path), value)
    return binding(path)


def private_root(path, *, fresh=False):
    path = Path(path).resolve()
    if not path.is_relative_to((ROOT / ".local").resolve()):
        raise ValueError("operational paths and outputs must remain ignored under .local")
    if fresh:
        path.mkdir(parents=False, exist_ok=False)
    elif not path.is_dir() or path.is_symlink() or path.is_junction():
        raise ValueError("existing unaliased evidence root required")
    return path


def checked_freeze(bound):
    proposal = read_json(bound)
    if proposal.get("schema") != "imageinfo-0075-authored-freeze-v1":
        raise ValueError("authored source freeze required")
    root = private_root(proposal["root"])
    if Path(bound["path"]).resolve() != root / "freeze.json":
        raise ValueError("freeze location differs")
    if proposal["recipeBindings"] != [binding(HERE / name) for name in MODULES]:
        raise ValueError("frozen source closure differs")
    if proposal["controls"] != controls.declaration() or proposal["corruptions"] != corruption.declaration():
        raise ValueError("fixed authored declarations differ")
    run.read_bound(proposal["runtimeManifest"])
    run.read_bound(proposal["interpreter"], limit=32 * 1024 * 1024)
    return proposal, root


def parent_grant(bound, *, purpose, reviewed, root):
    # The trusted caller must pin this binding after independent review. A JSON
    # authorizedBy string is never cryptographic authentication or self-authority.
    grant_path = Path(bound["path"]).resolve()
    if grant_path.is_relative_to(root):
        raise ValueError("parent grant must be external to editable evidence root")
    grant = read_json(bound)
    if grant != {"schema": "imageinfo-0075-orchestration-grant-v1",
                 "authorizedBy": "parent-after-independent-review",
                 "purpose": purpose, "reviewedArtifact": reviewed}:
        raise ValueError("exact externally pinned orchestration grant required")


def freeze(root, *, interpreter, runtime_manifest):
    """Record public declarations and exact sources; never import native codec.

    interpreter and runtime_manifest are caller-supplied exact file bindings.
    This output is a proposal requiring external review, not execution authority.
    """
    run.read_bound(interpreter, limit=32 * 1024 * 1024)
    read_json(runtime_manifest)
    declarations = list(controls.specs()) + list(corruption.specs())
    if len(declarations) != 59 or len({item["id"] for item in declarations}) != 59:
        raise ValueError("fixed 43 positive and 16 negative cells required")
    root = private_root(root, fresh=True)
    value = {"schema": "imageinfo-0075-authored-freeze-v1", "root": str(root),
             "interpreter": interpreter, "runtimeManifest": runtime_manifest,
             "recipeBindings": [binding(HERE / name) for name in MODULES],
             "controls": controls.declaration(), "corruptions": corruption.declaration(),
             "limits": asdict(run.Limits()), "nativeExecutionPerformed": False}
    return write(root / "freeze.json", value)


def _encode_with_verified_closure(case_id, verified):
    """Bind the separate encoder closure before any image operation.

    prepare_encoder performs only verified module loading. Closure equality is
    exact on both sides of construction; decoder closure remains independent.
    """
    before = verified.prepare_encoder()
    expected = verified.profile["loadedEncoderNonOsModules"]
    if before != expected:
        raise ValueError("encoder pre-operation closure differs")
    source_hash = controls.source_pixel_digest(case_id)
    data = controls.build_control(case_id, verified.assert_encoder_closure)
    after = verified.assert_encoder_closure()
    if after != expected or after != before:
        raise ValueError("encoder post-operation closure differs")
    return data, source_hash, before, after


def _encoder_worker(request_binding):
    """One exact formula base, invoked only by a reviewed six-base campaign."""
    request = read_json(request_binding)
    proposal, root = checked_freeze(request["freeze"])
    parent_grant(request["parentGrant"], purpose="encode-six-authored-bases",
                 reviewed=request["freeze"], root=root)
    case_id = request["baseId"]
    bases = [item["id"] for item in controls.specs() if item["suffixBytes"] == 0]
    if case_id not in bases:
        raise ValueError("fixed unsuffixed authored base required")
    target = root / "bases" / (case_id + ".jpg")
    if request["output"] != str(target) or Path(sys.executable).resolve() != Path(proposal["interpreter"]["path"]).resolve():
        raise ValueError("exact pinned encoder process required")
    # Exclusive marker fences direct worker replay, even after encoding fails.
    write(root / "bases" / (case_id + ".once.json"), {"request": request_binding})
    import runtime
    verified = runtime.verify_runtime()
    identity_before = verified.identity()
    if read_json(proposal["runtimeManifest"]) != identity_before:
        raise ValueError("reviewed encoder runtime differs")
    specification = controls.control_spec(case_id)
    data, source_hash, closure_before, closure_after = _encode_with_verified_closure(case_id, verified)
    identity_after = runtime.verify_runtime().identity()
    if identity_before != identity_after:
        raise ValueError("encoder components changed")
    with target.open("xb") as stream:
        if stream.write(data) != len(data):
            raise OSError("short authored base write")
    provenance = {"schema": "imageinfo-0075-encoder-result-v1", "baseId": case_id,
            "input": binding(target), "specification": specification,
            "sourceRgb": {"formula": specification["formula"],
                          "byteLength": specification["width"] * specification["height"] * 3,
                          "sha256": source_hash},
            "invocation": {"api": "PIL.Image.frombytes/save", "mode": "RGB", "format": "JPEG",
                           "dimensions": [specification["width"], specification["height"]],
                           "subsampling": specification["subsampling"],
                           "options": specification["encoderOptions"]},
            "componentIdentityBefore": identity_before, "componentIdentityAfter": identity_after,
            "loadedEncoderClosureBefore": closure_before,
            "loadedEncoderClosureAfter": closure_after,
            "loadedEncoderClosure": closure_after}
    # Component identities are larger than the bounded process capture. Retain
    # them separately and emit only their exact binding on the worker pipe.
    return {"provenance": write(root / "encoding" / (case_id + ".provenance.json"), provenance)}


def encode(freeze_binding, grant_binding):
    """Attempt all six fixed encodings once; retain every failure, no retry."""
    proposal, root = checked_freeze(freeze_binding)
    parent_grant(grant_binding, purpose="encode-six-authored-bases", reviewed=freeze_binding, root=root)
    write(root / "encoding.once.json", {"freeze": freeze_binding, "parentGrant": grant_binding})
    (root / "bases").mkdir(exist_ok=False)
    (root / "encoding").mkdir(exist_ok=False)
    results = []
    for spec in controls.specs():
        if spec["suffixBytes"]:
            continue
        case_id = spec["id"]
        request = {"freeze": freeze_binding, "parentGrant": grant_binding,
                   "baseId": case_id, "output": str(root / "bases" / (case_id + ".jpg"))}
        request_binding = write(root / "encoding" / (case_id + ".json"), request)
        command = [proposal["interpreter"]["path"], str(HERE / "qualify.py"),
                   "--encoder-worker", json.dumps(request_binding)]
        try:
            process = run.run_process(command, root / "encoding" / case_id,
                                      run.Limits(), binding={"encoderRequest": request_binding})
            result = {"baseId": case_id, "process": process}
            if (process["outcome"] == "exited" and process["returncode"] == 0 and
                    all(row["eof"] and not row["overflow"] and not row["error"]
                        for row in process["streams"].values())):
                emitted = json.loads((root / "encoding" / case_id / "stdout.bin").read_bytes())
                result["provenanceBinding"] = emitted["provenance"]
                result["provenance"] = read_json(emitted["provenance"])
        except Exception as error:
            result = {"baseId": case_id, "failure": type(error).__name__}
        results.append(result)
        write(root / "encoding" / (case_id + ".result.json"), result)
    checked_freeze(freeze_binding)
    return write(root / "encoding-results.json", {"schema": "imageinfo-0075-encoding-results-v1", "bases": results})


def prepare_cells(freeze_binding, encoding_binding):
    """Derive exact bytes and request-core proposals after encoding; no decode."""
    proposal, root = checked_freeze(freeze_binding)
    if Path(encoding_binding["path"]).resolve() != root / "encoding-results.json":
        raise ValueError("exact retained encoding report required")
    encoded = read_json(encoding_binding)
    bases = {}
    for row in encoded["bases"]:
        provenance = row.get("provenance", {})
        if provenance.get("schema") != "imageinfo-0075-encoder-result-v1":
            raise ValueError("all six authored encodings must have retained provenance")
        bases[row["baseId"]] = run.read_bound(provenance["input"], limit=controls.INPUT_LIMIT)
    expected_bases = {item["id"] for item in controls.specs() if item["suffixBytes"] == 0}
    if set(bases) != expected_bases or len(encoded["bases"]) != 6:
        raise ValueError("exact six encoded bases required")
    (root / "inputs").mkdir(exist_ok=False)
    (root / "requests").mkdir(exist_ok=False)
    (root / "runs").mkdir(exist_ok=False)
    cells = []
    positive_ids = {item["id"] for item in controls.specs()}
    for spec in (*controls.specs(), *corruption.specs()):
        case_id = spec["id"]
        data = (bases[spec["baseId"]] + bytes(spec["suffixBytes"]) if case_id in positive_ids
                else corruption.build_corruption(case_id, bases[spec["baseId"]]))
        input_path = root / "inputs" / (case_id + ".jpg")
        with input_path.open("xb") as stream:
            if stream.write(data) != len(data):
                raise OSError("short authored input write")
        outcome = ("pass" if case_id in positive_ids else
                   "fail" if case_id in ("early-eoi", "immediate-eoi") else "unsupported")
        core = {"schema": "imageinfo-0075-cell-v1", "stage": "authored",
                "interpreter": proposal["interpreter"]["path"], "input": binding(input_path),
                "runtimeManifest": proposal["runtimeManifest"], "profile": binding(HERE / "profile.json"),
                "recipeBindings": proposal["recipeBindings"], "limits": proposal["limits"]}
        cells.append({"id": case_id, "core": core, "reviewedRequestSha256": sha(canonical(core)),
                      "runRoot": str(root / "runs" / case_id), "expectedAssertionOutcome": outcome})
    return write(root / "cell-proposals.json", {"schema": "imageinfo-0075-cell-proposals-v1",
                 "freeze": freeze_binding, "encoding": encoding_binding, "cells": cells})


def prepare_requests(proposals_binding, cell_grants):
    """Bind the parent's external per-cell grants; produce reviewable audit plan.

    cell_grants is exactly {case_id: parentGrant file binding}; grants use the
    runner's imageinfo-0075-parent-grant-v1 schema. No process runs here.
    """
    proposals = read_json(proposals_binding)
    _, root = checked_freeze(proposals["freeze"])
    if Path(proposals_binding["path"]).resolve() != root / "cell-proposals.json":
        raise ValueError("exact cell proposals required")
    if set(cell_grants) != {cell["id"] for cell in proposals["cells"]}:
        raise ValueError("one external grant per fixed cell required")
    cells = []
    for cell in proposals["cells"]:
        grant_binding = cell_grants[cell["id"]]
        if Path(grant_binding["path"]).resolve().is_relative_to(root):
            raise ValueError("cell grants must be external to evidence root")
        request = dict(cell["core"], parentGrant=grant_binding)
        run.admit_request(request, inspect_input=False)
        request_binding = write(root / "requests" / (cell["id"] + ".json"), request)
        # run_cell exclusively creates the identical request bytes in runRoot.
        expected_binding = dict(request_binding, path=str(Path(cell["runRoot"]) / "cell-request.json"))
        expectation = write(root / "requests" / (cell["id"] + ".expectations.json"),
                            {"schema": "imageinfo-0075-audit-expectations-v1", "cellRequest": expected_binding,
                             "expectedAssertionOutcome": cell["expectedAssertionOutcome"]})
        cells.append({"id": cell["id"], "request": request_binding, "runRoot": cell["runRoot"],
                      "expectations": expectation, "expectedAssertionOutcome": cell["expectedAssertionOutcome"]})
    return write(root / "audit-plan.json", {"schema": "imageinfo-0075-authored-audit-plan-v1",
                 "freeze": proposals["freeze"], "proposals": proposals_binding, "cells": cells})


def execute(plan_binding, grant_binding):
    """Run all fixed cells once, then independently audit all, retaining failures."""
    plan = read_json(plan_binding)
    _, root = checked_freeze(plan["freeze"])
    parent_grant(grant_binding, purpose="execute-59-authored-cells", reviewed=plan_binding, root=root)
    if Path(plan_binding["path"]).resolve() != root / "audit-plan.json" or len(plan["cells"]) != 59:
        raise ValueError("exact externally pinned authored plan required")
    write(root / "execution.once.json", {"plan": plan_binding, "parentGrant": grant_binding})
    results = []
    for cell in plan["cells"]:
        try:
            result = run.run_cell(read_json(cell["request"]), cell["runRoot"])
            results.append({"id": cell["id"], "outcome": result["outcome"]})
        except Exception as error:
            results.append({"id": cell["id"], "failure": type(error).__name__})
    write(root / "execution-results.json", {"cells": results})
    # This module never interprets outputs as qualification: the independent
    # auditor evaluates raw retained evidence without codec/producer replay.
    import audit
    audits = []
    for cell in plan["cells"]:
        try:
            value = audit.audit_run(Path(cell["runRoot"]), Path(cell["expectations"]["path"]))
        except Exception as error:
            value = {"auditOutcome": "invalid-experiment", "reason": type(error).__name__}
        audits.append({"id": cell["id"], "audit": value})
    try:
        aggregate = audit.audit_plan(plan_binding)
    except Exception as error:
        aggregate = {"auditOutcome": "invalid-experiment", "reason": type(error).__name__}
    checked_freeze(plan["freeze"])
    return write(root / "audit-results.json", {"cells": audits, "aggregate": aggregate})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--encoder-worker", required=True)
    args = parser.parse_args()
    print(json.dumps(_encoder_worker(json.loads(args.encoder_worker)), sort_keys=True, allow_nan=False))
