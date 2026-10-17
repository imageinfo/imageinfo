"""Validate the finite retained-policy record offline; never queries or changes GitHub."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "docs/governance/retained-review-policy.v1.json"
REPO = "https://github.com/imageinfo/imageinfo"
EXPECTED_CASES = {
    "RP-01": "observed-no-new-enforcement",
    "RP-02": "observed-allowed-route",
    "RP-03": "observed-procedural-route",
    "RP-04": "no-adopted-machine-denial",
    "RP-05": "no-adopted-machine-denial",
    "RP-06": "not-executed-outside-retained-scope",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate(value):
    require(value["schemaVersion"] == 1 and value["ticket"] == 158, "record identity")
    require(value["policy"] == "retained-0157-option-a", "selected policy")
    require(value["repository"] == "imageinfo/imageinfo" and value["branch"] == "main", "target")
    require(value["requirements"] == {
        "authorizedDirectPush": True, "projectChecks": True,
        "practicalAgentReview": True, "terryBoardAcceptance": True,
        "mandatoryPullRequest": False, "mandatoryHumanApproval": False,
        "codeownersRequired": False, "newProtectionRequired": False,
    }, "procedural and adopted enforcement requirements")
    observation = value["observation"]
    sha = observation["sha"]
    require(re.fullmatch(r"[0-9a-f]{40}", sha) is not None, "exact observation SHA")
    require(observation["status"] == "observed", "actual repository observation")
    require(observation["rulesets"] == 0 and observation["mainProtected"] is False
            and observation["trackedCodeowners"] == [], "bounded current configuration")
    require(observation["dedicatedProtectionEndpoint"] == "403-unknown"
            and observation["collaboratorPermissionEndpoint"] == "403-unknown", "endpoint limits")
    require(len(observation["sources"]) == 3 and all(
        source.startswith("https://api.github.com/repos/imageinfo/imageinfo/")
        for source in observation["sources"]), "read-only source references")
    push = value["directPush"]
    require(push["status"] == "observed" and push["sha"] == sha, "exact allowed-route source")
    require(push["url"] == f"{REPO}/commit/{sha}", "source link")
    require(re.fullmatch(re.escape(REPO) + r"/actions/runs/[0-9]+", push["runUrl"])
            is not None, "actual CI run reference")
    require(push["event"] == "parent-retained-direct-push-operation", "operation provenance")
    require(len(push["checks"]) == 3 and {item["name"] for item in push["checks"]}
            == {"windows-2025", "ubuntu-24.04", "macos-15"}, "finite check denominator")
    require(all(item["conclusion"] == "success" for item in push["checks"]), "exact-source CI success")
    cases = value["cases"]
    require(len(cases) == 6 and {case["id"]: case["result"] for case in cases}
            == EXPECTED_CASES, "actual versus procedural/unexecuted case dispositions")
    require(all(case["basis"] for case in cases), "case evidence limits")
    require(value["boardAcceptance"]["actor"] == "terry"
            and value["boardAcceptance"]["state"] == "completed"
            and value["boardAcceptance"]["ticket"] == 160, "bounded owner acceptance")
    require(value["agentReview"]["result"] == "independent-agent-review-retained", "agent review")
    for field in ("settingsChanged", "reviewersContacted", "permissionsChanged",
                  "independentHumanVerificationClaimed", "historical18CaseRehearsalExecuted"):
        require(value[field] is False, field)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", type=Path, default=LEDGER)
    args = parser.parse_args()
    validate(json.loads(args.record.read_text(encoding="utf-8")))
    print("Retained policy: six dispositions consistent; offline record check only.")


if __name__ == "__main__":
    main()
