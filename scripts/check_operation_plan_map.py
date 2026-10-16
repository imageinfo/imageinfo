"""Check the finite public #132 requirements inventory; never execute a plan."""
from copy import deepcopy
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "docs/legacy-compatibility/operation-plan-map.v1.json"
DUTIES = {
    "P-READ", "P-WRITE", "P-IDENTITY", "P-PROPERTY", "P-EFFECT", "P-LOSS",
    "P-REVISION", "P-PUBLICATION", "P-RECOVERY", "P-ORDER", "P-AUTHORITY",
}
OWNERS = {
    "existing-date-preview": {55, 76, 77, 23, 78},
    "new-cr3-date-apply": {23, 78, 22, 119},
    "new-xmp-date": {24, 85, 185, 186},
    "paired-date-sync": {24, 86, 78, 85, 179, 180, 181},
    "xmp-owner-removal": {25, 89, 188, 189, 190, 90},
    "fresh-restore": {26, 95, 199, 200, 210},
    "grouped-effects": {26, 96, 24, 86, 179, 180, 181, 200, 208},
}
RESIDUALS = {
    "scalar-assignment", "insertion-block", "list-operations",
    "structure-operations", "language-alternatives", "date-geotag",
    "copy-redirection", "rename-move-cycle", "restore-prune",
    "intent-group-lifetime", "other-format-privacy-repair",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique_members(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON member")
        result[key] = value
    return result


def ids(rows, expected):
    found = [row["id"] for row in rows]
    require(len(found) == len(set(found)), "duplicate inventory ID")
    require(set(found) == expected, "missing or invented inventory ID")


def check(data):
    require(data["schema"] == "imageinfo.operation-plan-map.v1", "wrong inventory version")
    require(data["revision"] == "operation-plan-map-2026-10-16.1", "wrong revision")
    require(data["observed"] == "2026-10-16", "wrong observation date")
    require(data["kind"] == "requirements-inventory", "not an inventory")
    for field in ("executable", "productionMutationAllowed", "importedRecordsAuthorize",
                  "universalPlanSchemaDefined", "lg004Complete"):
        require(data[field] is False, "inventory cannot grant authority or completion")
    ids(data["duties"], DUTIES)
    for row in data["duties"]:
        require(isinstance(row["requirement"], str) and len(row["requirement"]) > 30,
                "empty shared duty")
    ids(data["operations"], set(OWNERS))
    for row in data["operations"]:
        require(set(row["plannerOwners"]) == OWNERS[row["id"]], "owner allocation changed")
        require(len(row["plannerOwners"]) == len(set(row["plannerOwners"])), "duplicate owner")
        require(row["productionMutationAllowed"] is False, "operation admission invented")
        require(set(row["duties"]) == DUTIES, "operation duty missing or invented")
        for value in row["duties"].values():
            require(isinstance(value, str) and len(value) > 30, "empty operation duty")
        expected_wire = (
            "existing-inert-v1" if row["id"] == "existing-date-preview"
            else "undefined-pending-admitted-members-executor"
            if row["id"] in {"paired-date-sync", "grouped-effects"}
            else "undefined-pending-removal-publication"
            if row["id"] == "xmp-owner-removal"
            else "undefined-pending-custody-profile-adapter"
            if row["id"] == "fresh-restore"
            else "undefined-pending-typed-adapter-profile"
        )
        require(row["wireStatus"] == expected_wire, "wire status overstated")
        require(bool(row["evidence"]), "missing evidence")
        for reference in row["evidence"]:
            path = (ROOT / reference).resolve()
            require(path.is_relative_to(ROOT) and path.is_file(), "missing/escaped evidence")
            require(reference.startswith(("docs/", "src/")), "nonpublic evidence")
    schema = json.loads((ROOT / "docs/legacy-compatibility/preview-plan/schema.v1.json")
                        .read_text(encoding="utf-8"), object_pairs_hook=unique_members)
    fields = data["previewFields"]
    require(len(fields) == len(set(fields)), "duplicate preview field")
    require(set(fields) == set(schema["properties"]) == set(schema["required"]),
            "preview field inventory no longer matches actual v1")
    ids(data["residuals"], RESIDUALS)
    for row in data["residuals"]:
        require(row["wireStatus"] == "undefined-until-typed-effects-bindings-known",
                "residual wire invented")
        require(15 in row["owners"] and bool(row["mapFamilies"]), "residual parent lost")
        require(isinstance(row["unmet"], str) and len(row["unmet"]) > 30, "empty residual")


def main():
    data = json.loads(INVENTORY.read_text(encoding="utf-8"), object_pairs_hook=unique_members)
    check(data)
    controls = []
    value = deepcopy(data)
    value["operations"][0]["duties"].pop("P-PROPERTY")
    controls.append(value)
    value = deepcopy(data)
    value["operations"][1]["plannerOwners"].remove(78)
    controls.append(value)
    value = deepcopy(data)
    value["previewFields"].remove("recovery")
    controls.append(value)
    value = deepcopy(data)
    value["residuals"].pop()
    controls.append(value)
    value = deepcopy(data)
    value["operations"][0]["id"] = "universal-executable-plan"
    controls.append(value)
    value = deepcopy(data)
    value["operations"].append(deepcopy(value["operations"][0]))
    controls.append(value)
    value = deepcopy(data)
    value["importedRecordsAuthorize"] = True
    controls.append(value)
    value = deepcopy(data)
    value["operations"][1]["productionMutationAllowed"] = True
    controls.append(value)
    value = deepcopy(data)
    value["operations"][1]["wireStatus"] = "implemented"
    controls.append(value)
    for value in controls:
        try:
            check(value)
        except ValueError:
            continue
        raise ValueError("negative inventory control unexpectedly accepted")
    try:
        json.loads('{"id":1,"id":2}', object_pairs_hook=unique_members)
    except ValueError:
        pass
    else:
        raise ValueError("duplicate JSON member accepted")
    print("operation-plan map: 7 operations, 11 duties each, 11 residuals; "
          "10 negative controls passed; no execution/admission")


if __name__ == "__main__":
    main()
