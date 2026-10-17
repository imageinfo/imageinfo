"""Check #0141's documentation trace without executing reference tools or media.

Only repository text/JSON is read. --self-test also mutates in-memory copies to
check that omissions, stale provenance and unsupported promotion are rejected.
"""
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
BASE = "docs/legacy-compatibility/coverage/"
LEDGER = BASE + "audit.v1.json"
CLASSES = {"finite_current_work", "scope_definition", "permission_guarantee_decision",
           "conditional_alternative", "unknown_planner_scope", "eventual_0012"}
AUTHORITY = {"firstRawAcceptance": False, "fullParity": False, "dropInParity": False,
             "productionMutation": False, "storageProfileAdmission": False}


def read_json(path):
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise ValueError(f"duplicate JSON member: {key}")
            result[key] = value
        return result
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def file_at(path):
    candidate = (ROOT / path).resolve()
    if not candidate.is_relative_to(ROOT) or not candidate.is_file():
        raise ValueError(f"invalid repository evidence path: {path}")
    return candidate


def digest(path):
    return hashlib.sha256(file_at(path).read_bytes()).hexdigest()


def canonical_sources():
    text = file_at("docs/legacy-compatibility/surface-ledger.md").read_text(encoding="utf-8")
    lg = {}
    for line in text.splitlines():
        cells = [part.strip() for part in line.split("|")[1:-1]]
        if cells and re.fullmatch(r"LG-00[1-6]", cells[0]):
            lg[cells[0]] = {"unresolved": cells[1], "requiredClosure": cells[2]}
    gaps = read_json(file_at("docs/inventory/canon-eos-r5-cr3.v1.json"))["gaps"]
    assert len(lg) == 6 and len(gaps) == 12, "original requirement denominator changed"
    return {**lg, **{row["id"]: row for row in gaps}}


def trace_rows(data):
    surface = data["surfaceTrace"]
    return [*data["obligations"], *surface["maps"], *surface["api_methods"],
            *surface["current_native"],
            *(row for denominator in surface["denominators"] for row in denominator["entries"])]


def summarize(obligations, surface=None):
    counts = Counter()
    reverse = defaultdict(list)
    rows = obligations if surface is None else trace_rows({"obligations": obligations, "surfaceTrace": surface})
    for row in rows:
        for residual in row["residuals"]:
            counts[residual["classification"]] += 1
            for owner in residual["owner_tickets"]:
                reverse[str(owner)].append(residual["id"])
    return {
        "originalLg": sum(row["id"].startswith("LG-") for row in obligations),
        "originalGaps": sum(row["id"].startswith("GAP-") for row in obligations),
        "unmetClauses": sum(bool(row["residuals"]) for row in obligations),
        "originalResidualCells": sum(len(row["residuals"]) for row in obligations),
        "residualRecordsAcrossOverlappingViews": sum(counts.values()),
        "byClassification": {key: counts[key] for key in sorted(CLASSES)},
    }, {key: sorted(value) for key, value in sorted(reverse.items(), key=lambda x: int(x[0]))}


def verify(data):
    assert data["schemaVersion"] == 1 and data["ticket"] == 141
    assert data["authority"] == AUTHORITY, "coverage cannot grant acceptance or authority"
    source = canonical_sources()
    obligations = data["obligations"]
    assert len(obligations) == len(source), "missing or duplicate original clause"
    assert {row["id"] for row in obligations} == set(source), "original clause identity mismatch"
    assert data["originalRequirements"] == source, "original requirement text changed"
    slices = []
    for record in data["slices"]:
        assert digest(record["path"]) == record["sha256"], "slice provenance changed"
        loaded = read_json(file_at(record["path"]))
        slices.extend(loaded[record["key"]])
    assert obligations == slices, "merged trace differs from independently authored slices"
    gap_slice = read_json(file_at(BASE + "gap-evidence.v1.json"))
    assert data["surfaceTrace"] == {key: gap_slice[key] for key in
                                     ("maps", "api_methods", "denominators", "current_native")}, "surface trace lost"
    seen = set()
    queue = file_at("docs/remaining-work.md").read_text(encoding="utf-8")
    # Original inventory/corpus owners survive after finite successors leave the
    # current queue. #0012/#0015 retain broader parity/RAW residuals.
    owners = {int(value) for value in re.findall(r"#(\d{4})", queue)} | {2, 12, 13, 15}
    for row in obligations:
        assert row["text"] and row["source"] and row["status"], "empty original trace"
        assert row["original_requirement"] == source[row["id"]], "clause source text changed"
    for row in trace_rows(data):
        assert row["residuals"], "unmet clause lost residual"
        for evidence in row.get("evidence", []):
            file_at(evidence["path"].split("#", 1)[0])
            assert evidence["kind"] and evidence["scope"], "untyped evidence promotion"
        for residual in row["residuals"]:
            assert residual["id"] not in seen, "duplicate residual identity"
            seen.add(residual["id"])
            assert residual["scope"] and residual["classification"] in CLASSES
            assert residual["owner_tickets"] and len(set(residual["owner_tickets"])) == len(residual["owner_tickets"])
            assert all(type(owner) is int and owner in owners for owner in residual["owner_tickets"]), "unknown residual owner"
            if residual["classification"] == "eventual_0012":
                assert 12 in residual["owner_tickets"], "eventual parity owner lost"
    summary, reverse = summarize(obligations, data["surfaceTrace"])
    assert data["summary"] == summary, "unmet residual count changed"
    assert data["reverseOwners"] == reverse, "reverse owner trace incomplete"
    native = read_json(file_at("docs/legacy-compatibility/native-token-inventory.v1.json"))
    matrix = read_json(file_at("docs/legacy-compatibility/delivery-matrix.v1.json"))
    surface = data["surfaceTrace"]
    assert [r["requirement"] for r in surface["maps"]] == [r["requirement"] for r in matrix["maps"]]
    assert [r["id"] for r in surface["api_methods"]] == [r["heading"] for r in native["apiMethods"]]
    method_roles = {r["name"]: r["requiredNativeRole"] for r in matrix["apiMethods"]}
    for row in surface["api_methods"]:
        assert row["required_native_role"] == method_roles[row["id"].split()[0]]
    assert len(surface["current_native"]) == 14
    assert len(surface["denominators"]) == 5
    for denominator in surface["denominators"]:
        source_rows = native[denominator["id"]]
        assert [row["inventory_record"] for row in denominator["entries"]] == source_rows
        assert denominator["expected_count"] == len(source_rows) == len(denominator["ids"])
    assert data["denominators"] == {
        "inventoryCounts": native["counts"],
        "mapIds": [r["id"] for r in native["families"]],
        "cliOptionHeadings": [r["syntax"] for r in native["cliOptionHeadings"]],
        "apiMethods": [r["heading"] for r in native["apiMethods"]],
        "apiOptions": [r["name"] for r in native["apiOptions"]],
        "setNewValueOptions": [r["name"] for r in native["setNewValueOptions"]],
    }, "fixed token/API denominator changed"
    assert data["currentNative"] == native["native"], "current native surface changed"
    assert data["referenceBaseline"] == matrix["referenceBaseline"], "pinned reference changed"
    for path, expected in data["evidenceSha256"].items():
        assert digest(path) == expected, f"evidence changed: {path}"
    required = {e["path"].split("#", 1)[0] for row in trace_rows(data) for e in row.get("evidence", [])}
    assert required <= data["evidenceSha256"].keys(), "evidence binding omitted"
    handles = data["nativeHandleBoundary"]
    assert handles == {
        "ticket": 140, "naturalWindowsCases": 7, "censoredWindowsCases": 1,
        "invalidAndClosedStdin": "EOF-observed-not-input-error",
        "writeOnlyStdin": "INPUT_IO-observed",
        "nullStdin": "watchdog-censored-no-natural-completion",
        "portableFailingHandleGuarantee": False,
        "muslReadonlyStdout": {"naturalStatus": 0, "capturedStdoutBytes": 0,
                              "capturedStderrBytes": 0, "observedOutputIncomplete": False,
                              "successfulDeliveryEstablished": False},
    }, "negative native-handle delivery must remain explicit"
    return summary


def controls(data):
    mutations = {
        "omit-clause": lambda d: d["obligations"].pop(),
        "duplicate-clause": lambda d: d["obligations"].append(deepcopy(d["obligations"][0])),
        "change-source-clause": lambda d: d["originalRequirements"].pop("LG-001"),
        "remove-residual": lambda d: d["obligations"][0].update(residuals=[]),
        "remove-owner": lambda d: d["obligations"][0]["residuals"][0].update(owner_tickets=[]),
        "false-completion": lambda d: d["authority"].update(firstRawAcceptance=True),
        "false-parity": lambda d: d["authority"].update(fullParity=True),
        "wrong-count": lambda d: d["summary"].update(originalResidualCells=0),
        "drop-reverse-trace": lambda d: d.update(reverseOwners={}),
        "stale-slice": lambda d: d["slices"][0].update(sha256="0" * 64),
        "drop-option": lambda d: d["denominators"]["apiOptions"].pop(),
        "native-expansion": lambda d: d["currentNative"]["commands"].append("apply"),
        "promote-censored-handle": lambda d: d["nativeHandleBoundary"].update(censoredWindowsCases=0),
        "promote-musl-no-delivery": lambda d: d["nativeHandleBoundary"]["muslReadonlyStdout"].update(successfulDeliveryEstablished=True),
        "stale-evidence": lambda d: d["evidenceSha256"].update({next(iter(d["evidenceSha256"])): "0" * 64}),
    }
    for name, mutation in mutations.items():
        candidate = deepcopy(data)
        mutation(candidate)
        try:
            verify(candidate)
        except (AssertionError, KeyError, ValueError):
            continue
        raise AssertionError(f"negative control accepted: {name}")
    return len(mutations)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--schema", action="store_true", help="also validate Draft 2020-12 using jsonschema")
    args = parser.parse_args()
    data = read_json(file_at(LEDGER))
    if args.schema:
        from jsonschema import Draft202012Validator
        schema = read_json(file_at(BASE + "audit.schema.v1.json"))
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(data)
    summary = verify(data)
    print(json.dumps({"status": "documentation-trace-valid-not-parity", **summary,
                      "rejectedControls": controls(data) if args.self_test else 0}, indent=2))


if __name__ == "__main__":
    main()
