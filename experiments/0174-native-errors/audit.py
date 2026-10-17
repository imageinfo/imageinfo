"""Read-only reconciliation of retained #0174 captures; never repairs artifacts."""
import argparse
import hashlib
import json
import pathlib


def audit(root):
    root = pathlib.Path(root)
    binding = json.loads((root / "bindings.private.json").read_text())
    retained = json.loads((root.parent / "retained-audit-final.private/audit.private.json").read_text())
    retained_rows = {row["cell"]: row for row in retained["rows"]}
    records = [json.loads(line) for line in (root / "controller.private.jsonl").read_text().splitlines()]
    rows = []
    for cell in binding["cells"]:
        path = root / (cell["cell"] + ".private.json")
        if not path.exists():
            partial = json.loads((root / (cell["cell"] + ".partial.private.json")).read_text())
            assert cell["cell"] == "candidate-flush" and partial["workerSha256"] == binding["workerSha256"]
            assert not any(event.get("terminal") or event.get("operation") == "publish" for event in partial["events"])
            flushes = [event for event in partial["events"] if event.get("operation") == "file-Candidate"]
            assert len(flushes) == 1 and flushes[0]["success"] and flushes[0]["nativeOsError"] is None
            offline = retained_rows[cell["cell"]]
            candidate = offline["files"]["unit/candidate.bin"]
            assert candidate["readable"] and candidate["bytes"] == 4194304
            assert candidate["sha256"] == hashlib.sha256(b"\x74" * 4194304).hexdigest()
            assert offline["preparedSourceNameAndBytesPreserved"]
            rows.append({"cell": cell["cell"], "disposition": "native-flush-unproduced-harness-interruption",
                         "runtimeTerminalCaptured": False, "publicationOperationCalled": False,
                         "preparedSourceNameAndBytesPreserved": True, "candidateBytes": candidate["bytes"],
                         "sourcePropertyPreservationQualified": False})
            continue
        value = json.loads(path.read_text())
        assert value["workerSha256"] == binding["workerSha256"]
        assert value["exitCode"] == 0 and not value["timedOut"]
        terminals = [event for event in value["events"] if event.get("terminal")]
        assert len(terminals) == 1
        terminal = terminals[0]
        assert not terminal["committed"] and not terminal["productionProfileAdmitted"] and not terminal["rawAdmission"]
        assert terminal["ownedHandlesRemoved"] == 0
        before = {file["name"]: file for file in value["before"]}
        after = {file["name"]: file for file in value["after"]}
        assert set(before) == {"source.bin"}
        offline = retained_rows[cell["cell"]]
        if cell["cell"] == "staged-write":
            # Preserve the contrary result. The guest's inventory was empty and
            # independent stopped-image reads could not resolve the prepared
            # source name; bytes survive only at the pre-move fixture name.
            assert not after and not offline["preparedSourceNameAndBytesPreserved"]
            assert offline["sourceBytesRetainedAtOriginalFixtureName"]
        else:
            assert set(after) == {"source.bin"} and offline["preparedSourceNameAndBytesPreserved"]
            left, right = before["source.bin"], after["source.bin"]
            assert right["sha256"] == cell["sourceSha256"]
            assert right["bytes"] == cell["sourceBytes"]
            for key in ("name", "bytes", "creation", "write", "attributes", "sddl", "identity", "streams"):
                assert left[key] == right[key], (cell["cell"], key)
        failures = [event for event in value["events"] if event.get("operation") and not event["success"]]
        assert len(failures) <= 1
        unit = {file["name"]: file for file in value["unit"]}
        assert len(unit) <= 5
        assert all(file["bytes"] <= (4 * 1024 * 1024 if name in ("candidate.bin", "output.bin") else 65536) for name, file in unit.items())
        operations = [event["operation"] for event in value["events"] if event.get("operation")]
        assert operations.count("publish") <= 1
        if "output.bin" in unit:
            assert unit["output.bin"]["bytes"] == 4 * 1024 * 1024
            assert unit["output.bin"]["sha256"] == hashlib.sha256(b"\x74" * (4 * 1024 * 1024)).hexdigest()
        if terminal["publicationPossible"]:
            assert terminal["status"] == ("Refused" if terminal["protocolComplete"] else "RecoveryRequired")
        else:
            assert "output.bin" not in unit
        arms = [r["value"] for r in records if r["kind"] == "fault-armed" and r["value"]["cell"] == cell["cell"]]
        if cell["cell"] == "control":
            assert not arms and terminal["protocolComplete"] and not failures
            assert set(unit) == {"output.bin", "prepared.record", "intent.record", "observation.record", "receipt.record"}
            disposition = "normal-unqualified-control"
        elif failures and failures[0].get("nativeOsError") is not None:
            assert arms
            disposition = "actual-native-error-preservation-refused" if cell["cell"] == "staged-write" else "actual-source-data-read-error"
        else:
            disposition = "requested-class-unproduced"
        rows.append({"cell": cell["cell"], "disposition": disposition, "terminal": terminal,
                     "nativeFailures": failures, "faultsArmed": len(arms),
                     "preparedSourceNameAndBytesPreserved": offline["preparedSourceNameAndBytesPreserved"],
                     "sourceBytesRetainedAtOriginalFixtureName": offline["sourceBytesRetainedAtOriginalFixtureName"],
                     "retained": {name: file["bytes"] for name, file in unit.items()}})
    return {"schema": "imageinfo-0174-retained-capture-audit-v1", "rows": rows,
            "workerSha256": binding["workerSha256"], "profileAdmitted": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("captures")
    args = parser.parse_args()
    print(json.dumps(audit(args.captures), indent=2))
