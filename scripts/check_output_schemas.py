"""Validate emitted foundation records; optional jsonschema QA dependency only."""
from pathlib import Path
import json
import os
import subprocess
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / "target" / "debug" / ("imageinfo.exe" if os.name == "nt" else "imageinfo")


def read(relative):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def main():
    metadata = read("docs/metadata-model/metadata-contract.schema.json")
    registry = Registry().with_resource(metadata["$id"], Resource.from_contents(metadata))
    result = Draft202012Validator(read("docs/legacy-compatibility/result.schema.json"), registry=registry)
    version = Draft202012Validator(read("docs/foundation/version.schema.json"))
    cases = [
        (["version", "--output", "json"], 0, version),
        (["metadata", "read", "--output", "json", "invented-not-a-fixture.cr3"], 1, result),
        (["metadata", "read", "--output", "json"], 2, result),
    ]
    for args, status, validator in cases:
        process = subprocess.run([str(EXE), *args], cwd=ROOT, capture_output=True, timeout=10)
        assert process.returncode == status, (args, process.returncode)
        value = json.loads(process.stdout)
        validator.validate(value)
    print(f"{len(cases)} actual foundation records match their published schemas")


if __name__ == "__main__":
    main()
