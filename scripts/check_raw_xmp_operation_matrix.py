"""Check #0117's inert requirements inventory, not format/storage admission."""
from copy import deepcopy
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "docs/write-safety/raw-xmp-operation-matrix.v1.json"
OWNERS = {
    "cr3-date-new": {23, 78, 80, 119, 22, 176},
    "xmp-date-new": {24, 85, 185, 186},
    "pair-date": {24, 86, 179, 180, 181},
    "xmp-owner-delete": {25, 89, 90, 188, 189, 190},
    "xmp-label": {24}, "caption": {24, 23}, "list": {24},
    "language": {24}, "structure": {24}, "snapshot-copy": {24, 23},
    "rational": {23}, "null": {23, 24}, "growth-shrink": {23, 119},
    "insert-delete-block": {23, 24, 25}, "date-transform": {23, 24, 133},
    "preview-variant": {23, 25}, "file-rename": {26, 212, 213, 201, 202},
    "replacement-restore-prune": {26, 209, 210, 211, 95, 199, 200},
    "group": {26, 96, 179, 214}, "privacy-other": {25, 91, 92, 191, 192},
}
VALUE_OPERATIONS = dict(zip(
    (f"VAL-{n:03}" for n in range(1, 13)),
    ["list"] * 4 + ["language"] * 2 + ["structure"] * 2
    + ["snapshot-copy", "rational", "rational", "null"],
))
SHARED_OPERATIONS = {"cr3-date-new", "xmp-date-new", "replacement-restore-prune", "group"}
SAF_OPERATIONS = {
    "SAF-001": {"caption"}, "SAF-002": {"xmp-label"},
    "SAF-003": {"cr3-date-new", "growth-shrink"},
    "SAF-004": {"cr3-date-new", "preview-variant"},
    **{f"SAF-{i:03}": SHARED_OPERATIONS for i in (5, 6, 7, 8, 9, 15)},
    "SAF-010": {"pair-date", "group"}, "SAF-011": {"file-rename"},
    "SAF-012": {"replacement-restore-prune"},
    "SAF-013": {"xmp-owner-delete", "privacy-other"},
    "SAF-014": {"cr3-date-new", "xmp-owner-delete", "privacy-other"},
    "SAF-016": {"cr3-date-new", "replacement-restore-prune"},
}
PROPOSAL_OPERATIONS = {
    "proposal:canon:ctmd/ISO@1": "preview-variant",
    "proposal:canon:opaque/UnknownRecord@1": "growth-shrink",
    "proposal:cr3-container-utc-v1": "date-transform",
    "proposal:exif-capture-time-v1": "date-transform",
    "proposal:exif/Artist@1": "snapshot-copy",
    "proposal:exif/DateTimeOriginal@1": "cr3-date-new",
    "proposal:exif/ExposureTime@1": "rational",
    "proposal:exif/ISO@1": "preview-variant",
    "proposal:exif/SubSecTimeOriginal@1": "date-transform",
    "proposal:exposure-display-v1": "rational",
    "proposal:http://ns.adobe.com/xap/1.0//Label@1": "xmp-label",
    "proposal:http://purl.org/dc/elements/1.1//Rights@1": "language",
    "proposal:http://purl.org/dc/elements/1.1//Subject@1": "list",
    "proposal:imageinfo:derived/ShutterSpeed@1": "rational",
    "proposal:iso-bmff/CreateDate@1": "date-transform",
    "proposal:iso-bmff:canon/PreviewImage@1": "preview-variant",
    "proposal:local-date-display-v1": "date-transform",
    "proposal:reduce-rational-v1": "rational",
    "proposal:shutter-from-exposure-v1": "rational",
    "proposal:string-to-creator-sequence-v1": "snapshot-copy",
    "proposal:synthetic-decoder-not-executable": "growth-shrink",
    "proposal:xmp-dc/creator@1": "snapshot-copy",
}
SELECTION_FIELDS = {
    "operationId", "documentIdentity", "occurrenceOrInsertionIdentity", "containerPath",
    "rawTypeAndEncoding", "inputView", "originalReadSet", "exactProposedValue",
    "allocationAndDependencyMap", "preservedComplements", "expectedEffectsAndLosses",
    "equalityAndNoopRule", "refusalCases", "independentOracle", "owner", "evidenceRefs",
}
# Frozen original seven acceptance paragraphs, independent of private board state.
ORIGINAL_ACCEPTANCE = [
    "Exercise docs/write-safety/acceptance-scenarios.md and the transaction/value cases against actual implementations and admitted media.",
    "Declare each OS/filesystem/storage profile and exclusions. Prove publication, collision/concurrency, properties, persistence, cancellation and recovery.",
    "Validate sensor samples, references, calibration/CFA interpretation, opaque data, previews and known signatures for each supported CR3 operation/layout.",
    "Finish exact pairing/mappings and named privacy field catalogs; measure removed/residual/uninspectable data and retained copies.",
    "Record independent validators, RAW usability checks and bounded failure injection through the fixture-plan records.",
    "Separate process kill, OS crash and power loss. Separate supported/refused/failed/unverified combinations. Full RAW does not enable C-RAW/DPRAW.",
    "Close GAP-004/GAP-009 only when their specified evidence exists. Logical deletion never establishes secure erasure.",
]


def require(value, message):
    if not value:
        raise ValueError(message)


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON member")
        result[key] = value
    return result


def read(path):
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique)


def indexed(rows):
    result = {row["id"]: row for row in rows}
    require(len(result) == len(rows), "duplicate ID")
    return result


def evidence(path):
    target = (ROOT / path).resolve()
    require(path.startswith("docs/") and target.is_relative_to(ROOT)
            and target.is_file(), "missing/nonpublic/escaped evidence")


def check(data):
    require(data["schema"] == "imageinfo.raw-xmp-operation-matrix.v1"
            and data["revision"] == "2026-10-17.1"
            and data["kind"] == "inert-requirements-inventory", "inventory version")
    for field in ("productionMutationAllowed", "parentAcceptanceComplete",
                  "gap004Complete", "gap009Complete"):
        require(data[field] is False, "inventory cannot grant admission/completion")
    require(data["firstOperation"] == "cr3-date-new"
            and data["firstOperationAdmission"] == "refused", "first slice/admission")
    require(data["familyCardinality"] == "unknown-outside-exact-selected-rows",
            "undefined family count invented")
    operations = indexed(data["operations"])
    require(set(operations) == set(OWNERS), "missing/invented operation or residual")
    for oid, row in operations.items():
        require(set(row["owners"]) == OWNERS[oid]
                and len(row["owners"]) == len(set(row["owners"])), "owner drift")
        require(row["productionMutationAllowed"] is False, "operation grants mutation")
        expected = "refused" if oid in {"cr3-date-new", "growth-shrink",
                   "preview-variant", "replacement-restore-prune"} else "unverified"
        require(row["outcome"] == expected, "operation outcome overstated")
        for field in ("operation", "identity", "location", "inputView",
                      "preservationBasis", "nextFinishLine"):
            require(isinstance(row[field], str) and len(row[field]) > 25,
                    "missing operation-specific contract")
        require(row["evidence"], "missing operation evidence")
        for ref in row["evidence"]:
            evidence(ref)
    cases = indexed(data["criteria"])
    source = read(ROOT / "docs/write-safety/scenarios.v1.json")
    expected_ids = set()
    for section, count in (("traces", 34), ("valueCases", 12),
                           ("recoveryCases", 8), ("retentionCases", 4), ("groups", 6)):
        require(len(source[section]) == count, "source denominator changed")
        for original in source[section]:
            cid = original["id"]
            expected_ids.add(cid)
            row = cases[cid]
            require(row["source"] == "docs/write-safety/scenarios.v1.json"
                    and row["sourceSection"] == section, "wrong criterion source")
            require(row["rules"] == original["ruleRefs"]
                    and row["required"] == original["expected"]
                    and row["title"] == original.get("title", original["expected"]),
                    "original case weakened or changed")
            if cid in VALUE_OPERATIONS:
                require(row["operations"] == [VALUE_OPERATIONS[cid]],
                        "value residual mapped to wrong operation")
    text = (ROOT / "docs/write-safety/acceptance-scenarios.md").read_text(encoding="utf-8")
    saf = [line for line in text.splitlines() if line.startswith("| SAF-")]
    require(len(saf) == 16, "SAF denominator changed")
    for line in saf:
        columns = [s.strip() for s in line.split("|")[1:-1]]
        cid, title, required, rules, fixtures = columns
        expected_ids.add(cid)
        row = cases[cid]
        require(row["source"] == "docs/write-safety/acceptance-scenarios.md"
                and row["sourceSection"] == "SAF"
                and row["title"] == title and row["required"] == required
                and row["rules"] == rules.split(", ")
                and row["fixtureFamilies"] == fixtures.split(", "),
                "original SAF criterion weakened or changed")
    require(set(cases) == expected_ids and len(cases) == 80, "criterion omitted/invented")
    for row in cases.values():
        require(row["status"] == "unverified-for-full-parent-acceptance",
                "criterion claimed complete")
        require(row["operations"] and set(row["operations"]) <= set(operations)
                and row["owners"] and len(row["evidenceBoundary"]) > 30,
                "unallocated criterion")
        section = row["sourceSection"]
        if section == "SAF":
            expected_operations = SAF_OPERATIONS[row["id"]]
            expected_owners = set().union(*(OWNERS[oid] for oid in expected_operations))
        elif section == "valueCases":
            oid = VALUE_OPERATIONS[row["id"]]
            expected_operations = {oid}
            expected_owners = {24} if oid in {"list", "language", "structure", "snapshot-copy"} else {23}
        elif section == "groups":
            expected_operations = {"pair-date", "group"}
            expected_owners = {24, 26, 179, 180, 181, 214}
        elif section == "retentionCases":
            expected_operations = {"replacement-restore-prune"}
            expected_owners = {26, 198, 203, 211}
        elif section == "recoveryCases":
            expected_operations = SHARED_OPERATIONS
            expected_owners = {22, 26, 169, 170, 171, 172}
        else:
            expected_operations = SHARED_OPERATIONS
            expected_owners = {22, 23, 26, 167, 168, 176}
        require(set(row["operations"]) == expected_operations
                and len(row["operations"]) == len(expected_operations),
                "criterion operation allocation changed/duplicated")
        require(set(row["owners"]) == expected_owners
                and len(row["owners"]) == len(expected_owners),
                "criterion owner allocation changed/duplicated")
    for row in operations.values():
        expected = {cid for cid, case in cases.items() if row["id"] in case["operations"]}
        require(set(row["criteria"]) == expected
                and len(row["criteria"]) == len(expected),
                "operation/criterion links missing, invented or duplicated")
    parent = indexed(data["parentAcceptance"])
    require(set(parent) == {f"A14-{i:02}" for i in range(1, 8)}, "parent clause omitted")
    for i, original in enumerate(ORIGINAL_ACCEPTANCE, 1):
        row = parent[f"A14-{i:02}"]
        require(row["original"] == original and row["status"] == "unmet"
                and row["operations"] and set(row["operations"]) <= set(operations),
                "original parent acceptance weakened/completed")
    require("VM-off" in parent["A14-06"]["currentRefinement"]
            and "no physical-power" in parent["A14-06"]["currentRefinement"],
            "current power policy lost")
    expected_keys = {}
    for path in (ROOT / "docs/metadata-model/examples").glob("*.json"):
        for key in re.findall(r'"(proposal:[^"]+)"', path.read_text(encoding="utf-8")):
            expected_keys.setdefault(key, set()).add(path.relative_to(ROOT).as_posix())
    keys = data["proposalKeys"]
    require(len(keys) == len({row["key"] for row in keys})
            and {row["key"] for row in keys} == set(expected_keys)
            and set(expected_keys) == set(PROPOSAL_OPERATIONS), "proposal key omitted/invented")
    for row in keys:
        require(set(row["sources"]) == expected_keys[row["key"]]
                and row["operation"] == PROPOSAL_OPERATIONS[row["key"]]
                and "not an executable or admitted" in row["meaning"], "proposal identity promoted")
    contract = data["nextContract"]
    require(contract["kind"] == "inert-operation-specific-selection-record-not-runtime-wire"
            and set(contract["requiredFields"]) == SELECTION_FIELDS
            and len(contract["requiredFields"]) == len(SELECTION_FIELDS)
            and len(contract["invariants"]) == 4, "selection contract weakened")
    for ref in data["sharedEvidence"]:
        evidence(ref)


def main():
    data = read(PATH)
    check(data)
    controls = []
    for field in ("productionMutationAllowed", "parentAcceptanceComplete",
                  "gap004Complete", "gap009Complete"):
        changed = deepcopy(data)
        changed[field] = True
        controls.append(changed)
    for field in ("operations", "criteria", "parentAcceptance", "proposalKeys"):
        changed = deepcopy(data)
        changed[field].pop()
        controls.append(changed)
    changed = deepcopy(data)
    changed["operations"][0]["outcome"] = "supported"
    controls.append(changed)
    changed = deepcopy(data)
    changed["operations"][0]["owners"].remove(119)
    controls.append(changed)
    changed = deepcopy(data)
    changed["operations"].append(deepcopy(changed["operations"][0]))
    controls.append(changed)
    changed = deepcopy(data)
    changed["parentAcceptance"][0]["original"] = "Fixed date only"
    controls.append(changed)
    changed = deepcopy(data)
    changed["criteria"][0]["required"] = "No check needed"
    controls.append(changed)
    changed = deepcopy(data)
    next(row for row in changed["criteria"] if row["id"] == "VAL-012")["operations"] = ["cr3-date-new"]
    controls.append(changed)
    # Remove each restored case family from the operation side only.
    for prefix in ("SAF", "TX", "VAL", "REC", "BKP", "GRP"):
        changed = deepcopy(data)
        operation = next(row for row in changed["operations"]
                         if any(cid.startswith(prefix + "-") for cid in row["criteria"]))
        operation["criteria"].remove(next(cid for cid in operation["criteria"]
                                          if cid.startswith(prefix + "-")))
        controls.append(changed)
    changed = deepcopy(data)
    changed["operations"][0]["criteria"].append("VAL-012")
    controls.append(changed)
    changed = deepcopy(data)
    next(row for row in changed["criteria"] if row["id"] == "TX-001")["operations"].remove("cr3-date-new")
    controls.append(changed)
    changed = deepcopy(data)
    next(row for row in changed["criteria"] if row["id"] == "TX-001")["operations"].append("caption")
    controls.append(changed)
    changed = deepcopy(data)
    changed["operations"][0]["criteria"].append(changed["operations"][0]["criteria"][0])
    controls.append(changed)
    changed = deepcopy(data)
    next(row for row in changed["criteria"] if row["id"] == "TX-001")["owners"] = [99999]
    controls.append(changed)
    changed = deepcopy(data)
    next(row for row in changed["proposalKeys"]
         if row["key"] == "proposal:exif/ExposureTime@1")["operation"] = "null"
    controls.append(changed)
    for changed in controls:
        try:
            check(changed)
        except (ValueError, KeyError):
            continue
        raise ValueError("negative control accepted")
    try:
        json.loads('{"id":1,"id":2}', object_pairs_hook=unique)
    except ValueError:
        pass
    else:
        raise ValueError("duplicate JSON member accepted")
    print(f"RAW/XMP matrix: {len(data['operations'])} finite rows; 80 criteria; "
          f"7 original clauses; {len(data['proposalKeys'])} proposal keys; "
          f"{len(controls) + 1} negative controls passed; no admission")


if __name__ == "__main__":
    main()
