"""Private pinned-reference replay in an existing Linux environment.

No corpus, runtime, source distribution, or captured result is redistributed.
Invoke from Linux; the existing private baseline is an input, never a work area.
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import platform
import re
import subprocess
import sys


PIN = "2200871d9cef988051d2a99d67df3bda6cbb30a8"


def strict_load(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON member")
            result[key] = value
        return result
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def descriptor(path):
    path = Path(path).resolve()
    return {"path": str(path), "sha256": digest(path), "byteLength": str(path.stat().st_size)}


def dump(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def windows_path(value):
    if re.match(r"^[A-Za-z]:[\\/]", value):
        return Path("/mnt") / value[0].lower() / value[3:].replace("\\", "/")
    return Path(value)


def checked_artifact(artifact, roots):
    path = roots[artifact["root"]] / artifact["path"]
    actual = descriptor(path)
    if actual["sha256"] != artifact["sha256"] or actual["byteLength"] != artifact["byteLength"]:
        raise ValueError("baseline artifact integrity mismatch")
    return actual


def tree_files(paths):
    files = set()
    for path in paths:
        path = Path(path)
        if path.is_file():
            files.add(path.resolve())
        elif path.is_dir():
            files.update(p.resolve() for p in path.rglob("*") if p.is_file() and ".git" not in p.parts)
    return [descriptor(p) for p in sorted(files)]


def reproduce(repository, output):
    if sys.platform != "linux":
        raise ValueError("A native Linux Python and Perl runtime is required")
    repository, output = repository.resolve(), output.resolve()
    # A fresh private directory makes output substitution reviewable and prevents replay overwrite.
    if output.exists() or not output.is_relative_to(repository / ".local"):
        raise ValueError("Supply a new directory under the repository's ignored .local root")
    output.mkdir(parents=True)
    (output / "captures").mkdir()
    (output / "derived").mkdir()
    (output / "probes").mkdir()
    # Retain the executed runner bytes even if the working tree changes after this run.
    executed_runner = output / "reproduce.executed.py"
    executed_runner.write_bytes(Path(__file__).read_bytes())
    index_path = repository / ".local/corpus/records/artifact-index.private.json"
    index = strict_load(index_path)
    roots = {key: windows_path(value) for key, value in index["roots"].items()}
    records_root = repository / ".local/corpus/records"
    oracle_path = records_root / "oracle-13.59.json"
    oracle = strict_load(oracle_path)
    if oracle["source"]["commit"] != PIN or oracle["source"]["version"] != "13.59":
        raise ValueError("Wrong baseline reference")
    source_manifest = checked_artifact(oracle["tool"]["distributionManifest"], roots)
    manifest = strict_load(source_manifest["path"])
    source = windows_path(manifest["root"])
    for entry in manifest["files"]:
        checked_artifact({**entry, "root": "source"}, {"source": source})
    source_before = tree_files([source])
    expected_source = {str((source / entry["path"]).resolve()) for entry in manifest["files"]}
    if {entry["path"] for entry in source_before} != expected_source:
        raise ValueError("Pinned source tree membership differs")
    driver = roots["tool-cache"] / "drivers/reference_api.pl"
    # Bind the historical observer, not a reimplementation of its value semantics.
    driver_manifest = strict_load(roots["tool-cache"] / "manifests/drivers.json")
    driver_entry = next(entry for entry in driver_manifest["files"] if entry["path"] == "reference_api.pl")
    checked_artifact({**driver_entry, "root": "drivers"}, {"drivers": driver.parent})
    perl = Path("/usr/bin/perl").resolve()
    env = {"PATH": "/usr/bin:/bin", "LC_ALL": "C", "LC_CTYPE": "C", "LANG": "C", "TZ": "UTC0",
           "HOME": str(output), "PERL5LIB": str(source / "lib")}
    probes = []
    def capture_probe(argv):
        item = {"arguments": argv, "startedAt": now()}
        try:
            result = subprocess.run(argv, env=env, cwd=output, capture_output=True, timeout=180)
            stdout, stderr = result.stdout, result.stderr
            item["termination"] = {"kind": "exit", "code": result.returncode}
        except subprocess.TimeoutExpired as error:
            stdout, stderr = error.stdout or b"", error.stderr or b""
            item["termination"] = {"kind": "timeout"}
        item["finishedAt"] = now()
        for name, content in (("stdout", stdout), ("stderr", stderr)):
            path = output / "probes" / (str(len(probes)) + "." + name)
            path.write_bytes(content)
            item[name] = descriptor(path)
        probes.append(item)
        dump(output / "probes.private.json", probes)
        return item, stdout
    def probe(argv):
        item, stdout = capture_probe(argv)
        if item["termination"] != {"kind": "exit", "code": 0}:
            raise ValueError("Setup probe failed; captures retained")
        return stdout.decode("utf-8", errors="strict")
    version = probe([str(perl), "-I", str(source / "lib"), str(source / "exiftool"), "-config", "", "-ver"]).strip()
    if version != "13.59":
        raise ValueError("Reference version probe mismatch")
    inc = probe([str(perl), "-e", 'print join("\\n", @INC)']).splitlines()
    linked = probe(["/usr/bin/ldd", str(perl)])
    libraries = re.findall(r"(?:=>\s+)?(/[^\s()]+)", linked)
    runtime_inputs = [perl, *inc, *libraries, "/etc/os-release", "/usr/share/doc/perl/copyright", "/usr/share/doc/libc6/copyright"]
    runtime_before = tree_files(runtime_inputs)
    # This deliberately hostile sentinel must be suppressed by the original CLI/API controls.
    sentinel = output / ".ExifTool_config"
    sentinel.write_text('die "imageinfo_config_sentinel\\n";\n', encoding="ascii")
    hostile, hostile_stdout = capture_probe([str(perl), str(source / "exiftool"), "-ver"])
    hostile_stderr = Path(hostile["stderr"]["path"]).read_bytes()
    if b"imageinfo_config_sentinel" not in hostile_stderr:
        raise ValueError("Configuration sentinel was not observed")
    suppressed = probe([str(perl), str(source / "exiftool"), "-config", "", "-ver"]).strip()
    if suppressed != "13.59":
        raise ValueError("CLI configuration suppression failed")
    environment = {"declaredAt": now(), "platform": platform.platform(), "uname": list(platform.uname()),
                   "osRelease": Path("/etc/os-release").read_text(), "perlConfig": probe([str(perl), "-V"]),
                   "linkedLibraries": linked, "filesystem": probe(["/usr/bin/stat", "-f", "-c", "%T", str(output)]),
                   "runtimePackages": probe(["/usr/bin/dpkg-query", "-W", "perl", "perl-base", "perl-modules-5.40", "libc6"]),
                   "environment": env, "versionProbe": version, "runtimeBefore": runtime_before,
                   "runtimeProvenance": "Existing Ubuntu distribution packages; hashed installed files, not rebuilt or installer authenticated.",
                   "sourceBefore": source_before, "driver": descriptor(driver),
                   "clockProbe": probe([str(perl), "-e", 'print scalar(localtime(0)),"\\n",scalar(gmtime(0)),"\\n"']),
                   "configurationSentinel": descriptor(sentinel), "configurationSuppressionVerified": True}
    dump(output / "environment.private.json", environment)
    policy = {"schemaVersion": 1, "declaredAt": now(), "jsonComparison": "strict typed structural comparison; array order retained",
              "exclusions": [], "binaryComparison": "exact bytes", "stderrComparison": "exact bytes",
              "limits": {"wallTimeSeconds": 180, "memoryBytes": None, "decodedBytes": None, "depth": None, "records": None},
              "unconfiguredLimitsReason": "Trusted admitted private fixtures; only the external process wall timeout is configured.",
              "scope": "Pinned 13.59 operations only; original 13.55 comparison is outside this replay."}
    dump(output / "policy.private.json", policy)
    selected = []
    for path in records_root.joinpath("experiments").glob("*.json"):
        record = strict_load(path)
        if record["reference"]["tool"]["reportedVersion"] == "13.59":
            selected.append((path, record))
    selected.sort(key=lambda item: (item[1]["reference"]["startedAt"], item[1]["id"]))
    fixtures = {}
    for path in sorted(records_root.joinpath("fixtures").glob("*.json")):
        fixture = strict_load(path)
        provenance_path = records_root / "provenance" / ("PV-" + fixture["id"] + ".json")
        provenance = strict_load(provenance_path)
        permissions = provenance["rights"]["permissions"]
        if provenance["review"]["state"] != "approved" or any(permissions[key] != "allowed" for key in ("store", "analyze", "modify")):
            raise ValueError("Fixture not admitted for private analysis")
        if permissions["publishReports"] != "denied":
            raise ValueError("Review expected historical restricted-report grant")
        artifact = checked_artifact(fixture["artifact"], roots)
        fixtures[fixture["id"]] = {"id": fixture["id"], **artifact, "before": artifact["sha256"],
                                     "manifest": descriptor(path), "provenance": descriptor(provenance_path)}
    selected_path = repository / ".local/corpus-intake/selected.private.json"
    originals = []
    for item in strict_load(selected_path):
        path = windows_path(item["privateSource"])
        binding = {"fixtureId": item["id"], **descriptor(path), "mtimeNs": str(path.stat().st_mtime_ns)}
        if binding["sha256"] != item["sha256"] or binding["mtimeNs"] != item["sourceMtimeNs"]:
            raise ValueError("Original source differs from acquisition binding")
        originals.append(binding)
    ledger = {"schemaVersion": 1, "startedAt": now(), "environment": descriptor(output / "environment.private.json"),
              "policy": descriptor(output / "policy.private.json"), "sourceManifest": source_manifest,
              "baselineOracle": descriptor(oracle_path), "baselineIndex": descriptor(index_path),
              "runner": descriptor(executed_runner), "fixtures": list(fixtures.values()), "attempts": [], "completed": False,
              "originalsBefore": originals, "selectionManifest": descriptor(selected_path)}
    dump(output / "ledger.private.json", ledger)
    path_map = {}
    # Redirect every historical produced media path to fresh output; baseline inputs stay immutable.
    for _, record in selected:
        ref = record["reference"]
        if "-o" in ref["arguments"]:
            old = ref["arguments"][ref["arguments"].index("-o") + 1]
            path_map[str(windows_path(old))] = output / "derived" / windows_path(old).name
        if "-b" in ref["arguments"]:
            old = checked_artifact(ref["stdout"], roots)["path"]
            path_map[old] = output / "captures" / (record["id"] + ".stdout")
    def remap(value):
        if re.match(r"^[A-Za-z]:[\\/]", value):
            path = windows_path(value)
            return str(path_map.get(str(path), path))
        return value
    for baseline_path, record in selected:
        ref = record["reference"]
        argv = [str(perl), *[remap(value) for value in ref["arguments"][1:]]]
        inputs = []
        for input_record in ref["inputHashesBefore"]:
            fixture = fixtures[input_record["fixtureId"]]
            active = path_map.get(fixture["path"], Path(fixture["path"]))
            inputs.append({"fixtureId": fixture["id"], **descriptor(active)})
        for entry, original in zip(inputs, ref["inputHashesBefore"]):
            entry["baselineSha256"] = original["sha256"]
            entry["matchesBaseline"] = entry["sha256"] == original["sha256"]
            entry["regenerated"] = entry["path"] != fixtures[entry["fixtureId"]]["path"]
            if not entry["regenerated"] and not entry["matchesBaseline"]:
                raise ValueError("Immutable baseline input differs")
        attempt = {"id": record["id"], "baselineRecord": descriptor(baseline_path),
                   "kind": "api-json" if Path(argv[3]).name == "reference_api.pl" else
                           "binary" if "-b" in argv else "write-status" if "-o" in argv else "cli-json",
                   "arguments": argv, "startedAt": now(), "inputHashesBefore": inputs,
                   "baselineStdout": checked_artifact(ref["stdout"], roots),
                   "baselineStderr": checked_artifact(ref["stderr"], roots)}
        try:
            result = subprocess.run(argv, env=env, cwd=output, capture_output=True, timeout=180)
            stdout, stderr = result.stdout, result.stderr
            attempt["termination"] = {"kind": "exit", "code": result.returncode}
        except subprocess.TimeoutExpired as error:
            stdout, stderr = error.stdout or b"", error.stderr or b""
            attempt["termination"] = {"kind": "timeout"}
        attempt["finishedAt"] = now()
        for name, content in (("stdout", stdout), ("stderr", stderr)):
            capture = output / "captures" / (record["id"] + "." + name)
            capture.write_bytes(content)
            attempt[name] = descriptor(capture)
        attempt["inputHashesAfter"] = [{"fixtureId": item["fixtureId"], **descriptor(item["path"])} for item in inputs]
        attempt["outputs"] = [descriptor(Path(argv[argv.index("-o") + 1]))] if "-o" in argv and Path(argv[argv.index("-o") + 1]).exists() else []
        ledger["attempts"].append(attempt)
        dump(output / "ledger.private.json", ledger)
        if attempt["termination"] != {"kind": "exit", "code": 0}:
            raise ValueError("Reference invocation failed; attempt retained privately")
        if any(before["sha256"] != after["sha256"] for before, after in zip(inputs, attempt["inputHashesAfter"])):
            raise ValueError("Reference input changed")
    for fixture in ledger["fixtures"]:
        fixture["after"] = digest(fixture["path"])
        if fixture["before"] != fixture["after"]:
            raise ValueError("Baseline fixture changed")
    ledger["originalsAfter"] = [{"fixtureId": item["fixtureId"], **descriptor(item["path"]),
                                 "mtimeNs": str(Path(item["path"]).stat().st_mtime_ns)} for item in originals]
    if ledger["originalsBefore"] != ledger["originalsAfter"]:
        raise ValueError("Original source changed during replay")
    environment["runtimeAfter"] = tree_files(runtime_inputs)
    environment["sourceAfter"] = tree_files([source])
    environment["driverAfter"] = descriptor(driver)
    if environment["driver"] != environment["driverAfter"]:
        raise ValueError("Observer driver changed")
    if environment["runtimeBefore"] != environment["runtimeAfter"] or source_before != environment["sourceAfter"]:
        raise ValueError("Source/runtime inventory changed")
    dump(output / "environment.private.json", environment)
    ledger["environment"] = descriptor(output / "environment.private.json")
    ledger["probes"] = descriptor(output / "probes.private.json")
    ledger["finishedAt"], ledger["completed"] = now(), True
    dump(output / "ledger.private.json", ledger)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    fresh_private_output = (not args.output.exists() and
                            args.output.resolve().is_relative_to(args.repository.resolve() / ".local"))
    try:
        reproduce(args.repository, args.output)
    except Exception as error:
        if fresh_private_output and args.output.is_dir() and (args.output / "reproduce.executed.py").is_file():
            dump(args.output / "failure.private.json", {"time": now(), "type": type(error).__name__, "reason": str(error)})
        raise
