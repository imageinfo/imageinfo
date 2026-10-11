"""Disposable primitive observations, not production publication or recovery code.

Runs independently on Windows, WSL-native storage or a supplied disposable mount.
No RAW/media paths are accepted. All content is authored marker data. The caller
retains the scratch directory/report; this probe never deletes by filename pattern.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time


def digest(path):
    with path.open("rb") as stream:
        value = hashlib.sha256()
        for block in iter(lambda: stream.read(65536), b""):
            value.update(block)
        return value.hexdigest()


def worker(directory):
    directory = Path(directory)
    with (directory / "stage").open("xb") as stage:
        stage.write(b"complete-candidate" * 4096)
        stage.flush()
        os.fsync(stage.fileno())
    for phase in ["staged", "before-link", "after-link", "receipt"]:
        if phase == "after-link":
            os.link(directory / "stage", directory / "output")
        if phase == "receipt":
            with (directory / "receipt").open("x", encoding="utf-8") as receipt:
                receipt.write("observed-link; namespace durability unverified\n")
                receipt.flush()
                os.fsync(receipt.fileno())
        print(phase, flush=True)
        sys.stdin.readline()


def run(parent, guard):
    if guard and os.name != "nt":
        raise ValueError("--guard observes the Windows share-mode experiment only")
    scratch = Path(tempfile.mkdtemp(prefix="imageinfo-storage-probe-", dir=parent))
    results = []
    def case(name, observations):
        results.append({"id": name, "observations": observations})

    source = scratch / "hash-then-replace-source"
    source.write_bytes(b"original-version")
    before = digest(source)
    candidate = scratch / "replacement"
    candidate.write_bytes(b"stale-candidate")
    source.write_bytes(b"external-newer-version")
    external = digest(source)
    os.replace(candidate, source)
    case("hash-then-replace", {"preflightHash": before, "externalHash": external,
        "observedHash": digest(source), "externalEditLost": source.read_bytes() == b"stale-candidate"})

    stage = scratch / "complete-stage"
    stage.write_bytes(b"complete-content" * 4096)
    output = scratch / "racing-destination"
    output.write_bytes(b"external-winning-version")
    winner = digest(output)
    try:
        os.link(stage, output)
        collision = "unexpected-publication"
    except OSError as error:
        collision = type(error).__name__
    case("conditional-name-collision", {"result": collision, "winnerRetained": digest(output) == winner})
    fresh = scratch / "new-name"
    os.link(stage, fresh)
    case("fresh-link", {"completeBytes": fresh.read_bytes() == stage.read_bytes(),
        "sharedObject": os.path.samefile(stage, fresh), "durabilityProved": False})

    directory_flush = "not-attempted: Windows Python does not supply directory flush protocol"
    if os.name != "nt":
        try:
            fd = os.open(scratch, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(fd)
                directory_flush = "call-succeeded; no OS-crash/power-loss experiment"
            finally:
                os.close(fd)
        except OSError as error:
            directory_flush = f"call-failed:{error.errno}"
    case("directory-flush", {"result": directory_flush})

    if guard:
        guarded = scratch / "guarded-source"
        guarded.write_bytes(b"guard-original")
        alias = scratch / "guarded-alias"
        os.link(guarded, alias)
        process = subprocess.Popen([guard, str(guarded)], stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            if process.stdout.readline().strip() != "guard-open":
                raise RuntimeError("Native guard did not reach its barrier")
            observed = {}
            for label, action in [("sourceWrite", lambda: guarded.write_bytes(b"external")),
                                  ("aliasWrite", lambda: alias.write_bytes(b"external")),
                                  ("sourceRename", lambda: os.rename(guarded, scratch / "renamed"))]:
                try:
                    action()
                    observed[label] = "allowed"
                except OSError as error:
                    observed[label] = f"refused:{getattr(error, 'winerror', None)}"
            # Sharing denies content/delete opens, not arbitrary metadata changes.
            try:
                os.utime(guarded, (1000000000, 1000000000))
                observed["mtimeChange"] = "allowed"
            except OSError as error:
                observed["mtimeChange"] = f"refused:{getattr(error, 'winerror', None)}"
            observed["contentUnchanged"] = guarded.read_bytes() == b"guard-original"
            case("native-source-share-guard", observed)
        finally:
            process.communicate("release\n", timeout=10)
            if process.returncode:
                raise RuntimeError("Native guard failed")
    if os.name != "nt":
        import fcntl
        locked = scratch / "advisory-source"
        locked.write_bytes(b"advisory-original")
        with locked.open("rb") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            unrelated = subprocess.run([sys.executable, "-c",
                "import pathlib,sys; pathlib.Path(sys.argv[1]).write_bytes(b'unrelated-write')",
                str(locked)], capture_output=True, timeout=10)
            case("advisory-lock", {"unrelatedExit": unrelated.returncode,
                "unrelatedWriteAllowed": locked.read_bytes() == b"unrelated-write"})

    for phase in ["staged", "before-link", "after-link", "receipt"]:
        directory = scratch / ("killed-" + phase)
        directory.mkdir()
        process = subprocess.Popen([sys.executable, __file__, "--worker", str(directory)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for reached in ["staged", "before-link", "after-link", "receipt"]:
            if process.stdout.readline().strip() != reached:
                process.kill()
                process.wait(timeout=10)
                raise RuntimeError("Worker missed its exact barrier")
            if reached == phase:
                process.kill()
                process.communicate(timeout=10)
                break
            process.stdin.write("continue\n")
            process.stdin.flush()
        stage_path = directory / "stage"
        output_path = directory / "output"
        case("process-kill-" + phase, {"termination": process.returncode,
            "stagePresent": stage_path.exists(), "outputPresent": output_path.exists(),
            "outputComplete": output_path.exists() and digest(output_path) == digest(stage_path),
            "receiptPresent": (directory / "receipt").exists(),
            "automaticRepair": False, "OSCrashTest": False, "powerLossTest": False})

    report = {"schemaVersion": 1, "observedAtUnix": time.time(),
        "platform": platform.platform(), "python": sys.version,
        "scratch": str(scratch), "profileVerified": False, "results": results}
    observations = {r["id"]: r["observations"] for r in results}
    assert observations["hash-then-replace"]["externalEditLost"]
    assert observations["conditional-name-collision"]["result"] == "FileExistsError"
    assert observations["conditional-name-collision"]["winnerRetained"]
    assert observations["fresh-link"]["completeBytes"] and observations["fresh-link"]["sharedObject"]
    for phase in ["staged", "before-link", "after-link", "receipt"]:
        observed = observations["process-kill-" + phase]
        assert observed["stagePresent"]
        assert observed["outputPresent"] == (phase in ["after-link", "receipt"])
        assert not observed["outputPresent"] or observed["outputComplete"]
        assert observed["receiptPresent"] == (phase == "receipt")
    if guard:
        observed = observations["native-source-share-guard"]
        assert all(observed[k].startswith("refused:") for k in ["sourceWrite", "aliasWrite", "sourceRename"])
        assert observed["contentUnchanged"]
    if os.name != "nt":
        assert observations["advisory-lock"]["unrelatedWriteAllowed"]
    (scratch / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent")
    parser.add_argument("--guard")
    parser.add_argument("--worker")
    args = parser.parse_args()
    if args.worker:
        worker(args.worker)
    else:
        if not args.parent:
            parser.error("--parent must name an existing disposable scratch parent")
        run(args.parent, args.guard)
