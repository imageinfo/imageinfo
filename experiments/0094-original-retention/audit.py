"""Read-only independent audit of a retained private #0094 native run.

Saved observations are evidence to compare, never restore or cleanup authority.
Only newly created observer capture files are written; marker entries are read.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
spec = importlib.util.spec_from_file_location("retention_qualifier", HERE / "qualify.py")
qualifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qualifier)


def audit(scratch):
    scratch = Path(scratch).resolve()
    qualifier.require(scratch.is_relative_to(REPO / ".local"), "private run must stay under .local")
    summary = json.loads((scratch / "summary.private.json").read_text())
    identities = json.loads((scratch / "identities-before.private.json").read_text())
    qualifier.require(summary["identities"] == identities, "source identities disagree")
    for name, digest in identities["sources"].items():
        source = (REPO / name).resolve()
        qualifier.require(source.is_relative_to(HERE) or source == qualifier.OBSERVER,
                          "unexpected source manifest path")
        qualifier.require(qualifier.sha(source) == digest, "source differs from actual-run source")
    cases = summary["cases"]
    qualifier.require(len(cases) == summary["caseCount"] == 32, "unexpected finite suite count")
    names = set()
    killed = complete = incomplete = absent = foreign = 0
    for case in cases:
        name = case["id"]
        qualifier.require(re.fullmatch(r"[a-z-]+", name) and name not in names, "invalid/duplicate case")
        names.add(name)
        root, captures = scratch / name, scratch / (name + "-capture")
        evidence = json.loads((captures / "observations.private.json").read_text())
        current = qualifier.snapshot(root, captures, "independent-audit")
        qualifier.require(qualifier.files_only(current) == qualifier.files_only(evidence["postExit"]),
                          "actual retained entries differ from completed-run observation")
        qualifier.require(evidence["id"] == name and evidence["mode"] == case["mode"],
                          "case identity differs")
        baseline = evidence["baseline"]
        qualifier.require(current["."]["identity"] == baseline["."]["identity"],
                          "actual fresh root identity changed")
        qualifier.require(current["target.bin"]["identity"] == baseline["target.bin"]["identity"]
                          and (root / "target.bin").read_bytes() == qualifier.OLD,
                          "actual current original identity/default bytes lost")
        qualifier.require(current["candidate.bin"]["identity"] == baseline["candidate.bin"]["identity"]
                          and (root / "candidate.bin").read_bytes() == qualifier.NEW,
                          "actual staged candidate identity/default bytes lost")
        qualifier.require(current["unrelated.marker"] == baseline["unrelated.marker"],
                          "actual unrelated entry changed")
        if case["ownedProcessKilled"]:
            killed += 1
            qualifier.require(qualifier.files_only(evidence["before"]) == qualifier.files_only(current),
                              "interrupted namespace changed")
        for event in evidence["events"]:
            qualifier.require(all(event.get(flag) is False for flag in qualifier.AUTHORITY_FLAGS)
                              and event.get("enabledProfiles") == 0, "saved worker claimed authority")
        retained = current.get("retained-original.bin")
        state = "absent"
        if retained:
            if retained["kind"] == "directory":
                state = "directory"
            else:
                data = (root / "retained-original.bin").read_bytes()
                state = "complete-original-bytes" if data == qualifier.OLD else \
                    "incomplete-empty" if data == b"" else "foreign-bytes"
        qualifier.require(state == case["retainedOriginalState"], "derived retained state differs")
        if state == "complete-original-bytes":
            complete += 1
        elif state == "incomplete-empty":
            incomplete += 1
        elif state == "absent":
            absent += 1
        else:
            foreign += 1
    admissions = summary["admissionRefusals"]
    qualifier.require(len(admissions) == summary["admissionRefusalCount"] == 3,
                      "unexpected admission refusal count")
    for case in admissions:
        name = case["id"]
        qualifier.require(name in ("unknown-mode", "json-authority-mode", "reused-stale-context"),
                          "unknown admission refusal")
        root = scratch / ("negative-" + name)
        captures = scratch / ("negative-" + name + "-capture")
        evidence = json.loads((captures / "observations.private.json").read_text())
        if name == "reused-stale-context":
            current = qualifier.snapshot(root, captures, "independent-audit")
            qualifier.require(current == evidence["before"] == evidence["after"],
                              "reused stale-context artifacts changed")
        else:
            qualifier.require(not root.exists(), "invalid input created marker root")
    return {"schemaVersion": 1, "caseCount": len(cases), "ownedProcessKills": killed,
            "admissionRefusalCount": len(admissions),
            "completeOriginalBytesAtRetainedName": complete, "incompleteEmptyCopies": incomplete,
            "absentRetainedName": absent, "foreignOrDirectoryRetainedNames": foreign,
            "actualCurrentOriginalAndCandidateRetained": True, "allActualEntriesUnchangedByAudit": True,
            "allWorkerAuthorityFlagsFalse": True, "conditionalReplacementQualified": False,
            "restoreAllowed": False, "productionReplacementAllowed": False, "committed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scratch", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    qualifier.require(not Path(args.output).exists(), "audit output must be fresh")
    qualifier.save(args.output, audit(args.scratch))
