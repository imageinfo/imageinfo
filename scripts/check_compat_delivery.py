"""Check finite delivery assignments against the complete public requirements.

This is a documentation coverage check, not runtime or media qualification.
"""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "docs/legacy-compatibility"


def main():
    inventory = json.loads((ROOT / "docs/inventory/canon-eos-r5-cr3.v1.json").read_text(encoding="utf-8"))
    matrix = json.loads((BASE / "delivery-matrix.v1.json").read_text(encoding="utf-8"))
    ledger = (BASE / "surface-ledger.md").read_text(encoding="utf-8")
    document = (BASE / "delivery-matrix.md").read_text(encoding="utf-8")
    queue = (ROOT / "docs/remaining-work.md").read_text(encoding="utf-8")
    errors = []

    def require(condition, message):
        if not condition:
            errors.append(message)

    def index(rows, key):
        result = {row[key]: row for row in rows}
        require(len(result) == len(rows), f"duplicate {key}")
        return result

    maps = index(matrix["maps"], "id")
    require(len(maps) == 32, "MAP denominator must be 32")
    require(set(maps) == {r["id"] for r in inventory["mappings"]}, "MAP identities differ")
    for original in inventory["mappings"]:
        require(maps.get(original["id"], {}).get("requirement") == original,
                f"{original['id']}: original full requirement changed or omitted")

    expected_methods = {}
    expected_gaps = {}
    roles = {"Request settings", "Extraction/query", "Values/identity", "Intent lifetime",
             "Copy/context", "Filesystem effects", "Discovery", "Extension/ordering"}
    for line in ledger.splitlines():
        if not line.startswith("| "):
            continue
        cells = [c.strip() for c in line.split("|")[1:-1]]
        if len(cells) != 3:
            continue
        if cells[0] in roles:
            for name in re.findall(r"`([^`]+)`", cells[1]):
                require(name not in expected_methods, f"duplicate source method {name}")
                expected_methods[name] = (cells[0], cells[2])
        if re.fullmatch(r"LG-00[1-6]", cells[0]):
            expected_gaps[cells[0]] = {"unresolved": cells[1], "requiredClosure": cells[2]}
    methods = index(matrix["apiMethods"], "name")
    require(len(expected_methods) == len(methods) == 39, "API denominator must be 39")
    require(set(methods) == set(expected_methods), "API heading identities differ")
    for name, (role, contract) in expected_methods.items():
        row = methods.get(name, {})
        require(row.get("role") == role and row.get("requiredNativeRole") == contract,
                f"{name}: native role requirement changed or omitted")
        require(bool(row.get("mapRefs")) and all(ref in maps for ref in row.get("mapRefs", [])),
                f"{name}: missing MAP assignment")
        require(f"`{name}`" in document, f"{name}: missing document heading row")
    for gap in inventory["gaps"]:
        if gap["id"] in {"GAP-006", "GAP-012"}:
            expected_gaps[gap["id"]] = gap
    gaps = index(matrix["gaps"], "id")
    require(len(gaps) == 8 and set(gaps) == set(expected_gaps), "gap denominator differs")
    for key, original in expected_gaps.items():
        require(gaps.get(key, {}).get("requirement") == original,
                f"{key}: full gap clause changed or omitted")
    queue_tickets = {int(n) for n in re.findall(r"#(\d{4})", queue)}
    for row in [*maps.values(), *methods.values(), *gaps.values()]:
        label = row.get("id", row.get("name"))
        require(row.get("complete") is False, f"{label}: cannot claim full-family completion")
        require(row.get("residualOwner") == 15 and bool(row.get("residual")),
                f"{label}: missing full residual owner")
        require(bool(row.get("nextTickets")) and all(n in queue_tickets for n in row["nextTickets"]),
                f"{label}: next work not assigned to existing queue")
        require(bool(row.get("evidenceRefs")), f"{label}: missing scoped evidence")
        for ref in row.get("evidenceRefs", []):
            path = (ROOT / ref).resolve()
            require(path.is_relative_to(ROOT) and path.is_file(), f"{label}: invalid evidence path {ref}")
        if "id" in row:
            require(row["id"] in document, f"{label}: missing document row")
    require(matrix["referenceBaseline"] == inventory["reference"], "pinned baseline changed")
    require(matrix["authority"] == {"parityEstablished": False, "reducedRequirementsAccepted": False,
                                    "productionMutationAllowed": False, "storageProfileAdmitted": False},
            "matrix must confer no parity/mutation/profile authority")
    require(bool(matrix.get("engineeringOrder")), "missing engineering order")
    print(json.dumps({"mapFamilies": len(maps), "apiHeadings": len(methods),
                      "retainedGaps": len(gaps), "errors": errors}, indent=2))
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
