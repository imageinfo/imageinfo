"""Validate emitted native CLI records; optional jsonschema QA dependency only."""
from pathlib import Path
import json
import os
import subprocess
import tempfile
from copy import deepcopy
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
        (["--output=json", "--bogus"], 2, result),
        (["metadata", "wrong", "--output=json"], 2, result),
        (["metadata", "read", "--values=bad", "--output=json"], 2, result),
        (["metadata", "--output=json", "--color=never", "read", "--color=always"], 2, result),
    ]
    for args, status, validator in cases:
        process = subprocess.run([str(EXE), *args], cwd=ROOT, capture_output=True, timeout=10)
        assert process.returncode == status, (args, process.returncode)
        value = json.loads(process.stdout)
        validator.validate(value)
    # Reuse the independently authored public fixture builder without a camera
    # corpus or an additional Cargo target/dependency. The temporary harness has
    # only standard-library dependencies and runs under the pinned toolchain.
    with tempfile.TemporaryDirectory(prefix="imageinfo-schema-") as temporary:
        directory = Path(temporary)
        source = directory / "fixture.rs"
        builder = json.dumps((ROOT / "tests/support/mod.rs").as_posix())
        source.write_text(
            f'#[allow(dead_code)] #[path = {builder}] mod support;\n'
            'fn main() { let fixture = support::fixture_with_previews('
            '"Firmware Version 2.2.1", vec![255,216,255,217], '
            'vec![255,216,255,217], vec![255,216,255,217]); '
            'std::fs::write(std::env::args_os().nth(1).unwrap(), fixture.bytes).unwrap(); }\n',
            encoding="utf-8",
        )
        harness = directory / ("fixture.exe" if os.name == "nt" else "fixture")
        subprocess.run(["rustc", "--edition=2024", str(source), "-o", str(harness)], cwd=ROOT, check=True, capture_output=True, timeout=30)
        raw = directory / "authored.cr3"
        sidecar = directory / "chosen.xmp"
        subprocess.run([str(harness), str(raw)], check=True, timeout=10)
        sidecar.write_bytes(b"authored path-association marker; contents not parsed")
        before = {path.name: path.read_bytes() for path in (raw, sidecar)}
        observations = [
            (["preview", "date-time-original", str(raw), "--value", "2000:02:29 23:59:59", "--output=json"], 1),
            (["preview", "date-time-original", str(raw), "--value", "2000:02:29 23:59:59", "--offset=0", "--output=json"], 1),
            (["sidecar", "pair", str(raw), "--sidecar", str(sidecar), "--output=json"], 0),
            (["sidecar", "pair", str(raw), "--output=json"], 1),
            (["sidecar", "pair", str(raw), "--sidecar", str(directory / "missing.xmp"), "--output=json"], 1),
        ]
        emitted = []
        for args, status in observations:
            process = subprocess.run([str(EXE), *args], cwd=ROOT, capture_output=True, timeout=10)
            assert process.returncode == status, (args, process.returncode)
            value = json.loads(process.stdout)
            result.validate(value)
            emitted.append(value)
        assert before == {path.name: path.read_bytes() for path in (raw, sidecar)}
        assert not (directory / "missing.xmp").exists()
        # Keep observation alternatives closed, including the authority boundary.
        invalid = []
        for source_value in (emitted[0], emitted[2]):
            changed = deepcopy(source_value)
            changed["files"][0]["snapshot"]["unexpected"] = True
            invalid.append(changed)
        changed = deepcopy(emitted[0])
        changed["files"][0]["snapshot"]["preview"]["production_mutation_allowed"] = True
        invalid.append(changed)
        changed = deepcopy(emitted[0])
        changed["files"][0]["snapshot"]["preview"]["proposed_bytes"] = [0]
        invalid.append(changed)
        changed = deepcopy(emitted[2])
        changed["files"][0]["snapshot"]["pair"]["association"] = "inferred_basename"
        invalid.append(changed)
        changed = deepcopy(emitted[0])
        changed["files"][0]["snapshot"] = {"arbitrary": "object"}
        invalid.append(changed)
        assert all(not result.is_valid(value) for value in invalid)
    print(f"{len(cases) + len(observations)} actual native records match their published schemas; {len(invalid)} altered observation records refused")


if __name__ == "__main__":
    main()
