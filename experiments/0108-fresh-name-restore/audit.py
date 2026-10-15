"""Read-only independent comparison of actual retained #0108 artifacts.

Fresh observer captures are written outside each marker root. Evidence never
authorizes restore, cleanup, publication or replay.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("restore_qualifier", HERE / "qualify.py")
qualifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qualifier)


def audit(scratch):
    scratch = Path(scratch).resolve()
    qualifier.require(scratch.is_relative_to(qualifier.REPO / ".local"), "private scratch required")
    summary = json.loads((scratch / "summary.private.json").read_text())
    identities = json.loads((scratch / "identities-before.private.json").read_text())
    qualifier.require(summary["identities"] == identities, "source identities differ")
    expected = {p.relative_to(qualifier.REPO).as_posix() for p in qualifier.source_paths()}
    qualifier.require(set(identities["sources"]) == expected, "unexpected source manifest")
    for name, digest in identities["sources"].items():
        qualifier.require(qualifier.sha(qualifier.REPO / name) == digest, "source differs from actual run")
    cases = summary["cases"]
    qualifier.require(len(cases) == summary["caseCount"], "case count differs")
    seen = set()
    restored = killed = refusals = 0
    for case in cases:
        name = case["id"]
        qualifier.require(re.fullmatch(r"[a-z-]+", name) and name not in seen, "invalid case identity")
        seen.add(name)
        root, captures = scratch / name, scratch / (name + "-capture")
        evidence = json.loads((captures / "observations.private.json").read_text())
        qualifier.require(evidence["id"] == name and evidence["mode"] == case["mode"], "case binding differs")
        current = qualifier.snapshot(root, captures, "independent-audit")
        qualifier.require(qualifier.files_only(current) == qualifier.files_only(evidence["after"]),
                          "actual retained artifacts changed since completed run")
        qualifier.require(current["."]["identity"] == evidence["baseline"]["."]["identity"],
                          "actual root identity differs")
        qualifier.require(current[qualifier.UNRELATED] == evidence["baseline"][qualifier.UNRELATED],
                          "actual unrelated marker changed")
        if case["restoredCopyObserved"]:
            restored += 1
            qualifier.require((root / qualifier.DESTINATION).read_bytes() == qualifier.ORIGINAL
                              and (root / qualifier.CURRENT).read_bytes() == qualifier.LATER
                              and (root / qualifier.ORIGINAL_NAME).read_bytes() == qualifier.ORIGINAL,
                              "actual fresh restore or current/original bytes differ")
            qualifier.require(current[qualifier.DESTINATION]["identity"] == evidence["candidateIdentity"],
                              "actual installed object is not captured candidate")
        else:
            refusals += 1
        if case["ownedProcessKilled"]:
            killed += 1
            qualifier.require(qualifier.files_only(current) == qualifier.files_only(evidence["beforeStop"]),
                              "owned process termination changed retained artifacts")
        for event in evidence["events"]:
            qualifier.require(all(event.get(flag, False) is False for flag in qualifier.FLAGS),
                              "saved worker event claimed authority")
    qualifier.require(restored > 0 and killed == len(qualifier.GATES), "missing positive/owned interruption cells")
    admissions = summary["admissionRefusals"]
    qualifier.require(len(admissions) == summary["admissionRefusalCount"] == 3, "admission count differs")
    for case in admissions:
        name = case["id"]
        root, captures = scratch / name, scratch / (name + "-capture")
        if name == "saved-context-existing-root":
            evidence = json.loads((captures / "observations.private.json").read_text())
            current = qualifier.snapshot(root, captures, "independent-audit")
            qualifier.require(current == evidence["before"] == evidence["after"], "saved context artifacts changed")
        else:
            qualifier.require(not root.exists(), "invalid mode created marker artifacts")
    return {"schemaVersion": 1, "caseCount": len(cases), "restoredCopyObservedCount": restored,
            "otherOutcomes": refusals, "ownedProcessKills": killed,
            "admissionRefusalCount": len(admissions),
            "allActualRetainedArtifactsMatchCompletedRun": True, "currentTargetsRetained": True,
            "auditChangedMarkerArtifacts": False, "committed": False,
            "productionPublicationAllowed": False, "enabledProfiles": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scratch", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    qualifier.require(not Path(args.output).exists(), "fresh audit output required")
    qualifier.save(args.output, audit(args.scratch))
