"""Fixed private native/reference ISO timing; no public camera results."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import subprocess
import threading
import time
import hashlib

import measure_batch_read as batch
import measure_read_resources_144 as native
import read_benchmark as b
import read_telemetry as telemetry

ROOT = Path(__file__).resolve().parents[1]
REVISION = "comparable-read-151-v1"
ROUNDS, WARMUPS, PAIRS = 3, 3, 10
TIMEOUT_MS, CAPTURE_BYTES = 30000, 4194304
VERIFIER = ROOT / "scripts/check_comparable_reference_151.pl"


class ReferenceLifecycle:
    """Enable the shared runner's retained cancellation path without counters.

    This hook observes no process membership or resource data. It deliberately
    cannot turn launcher PID counters into reference workload measurements.
    """
    stop_reason = None

    def attach(self, process, start):
        pass

    def launch_failed(self, start):
        pass

    def sample(self, final=False):
        pass


def save(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def schedule():
    """Each round has three warmup pairs then ten measured pairs.

    Measured first-tool order is balanced within every round. Warmup-first order
    alternates globally; no adaptation to observed output or elapsed duration.
    """
    return [{"round": r, "pair": i, "phase": "warmup" if i < WARMUPS else "sample",
             "order": ["native", "reference"] if (r * (WARMUPS + PAIRS) + i) % 2 == 0
             else ["reference", "native"]}
            for r in range(ROUNDS) for i in range(WARMUPS + PAIRS)]


def rights(p, identity_checkpoints=None):
    batch.require(p["revision"] == REVISION, "unsupported protocol")
    batch.require(p["taskAdmission"] == {"ticket": 151,
        "scope": "private-read-only-comparable-analysis", "sourceMutationAllowed": False,
        "reportPublicationAllowed": False}, "exact current private task admission required")
    batch.require(b.digest(p["priorProtocol"]) == p["priorProtocolSha256"], "prior protocol changed")
    prior = b.load(p["priorProtocol"])
    batch.rights_before_media(prior)
    batch.require(p["fixture"] == prior["fixtureSet"][0], "exact admitted existing prefix required")
    batch.require(b.digest(p["fixture"]["oracle"]) == p["fixture"]["oracleSha256"], "oracle changed")
    for path, expected in p["bindings"].items():
        batch.require(b.digest(path) == expected, "pinned prerequisite/tool identity changed")
    required = [__file__, b.__file__, batch.__file__, native.__file__, telemetry.__file__,
                str(ROOT / "scripts/audit_comparable_read_151.py"), p["binary"],
                str(ROOT / "scripts/audit_read_resources_144.py"),
                str(ROOT / "scripts/audit_read_telemetry.py"),
                str(VERIFIER),
                p["priorReferenceEnvironment"], p["priorReferenceLedger"],
                p["correspondenceReview"], p["sourceBuildEvidence"]]
    batch.require(all(str(Path(x).resolve()) in p["bindings"] for x in required),
                  "all prerequisite/build/consumer identities must be bound")
    review = b.load(p["correspondenceReview"])
    batch.require(review["approved"] is True and review["inputSha256"] == p["fixture"]["inputSha256"]
        and review["nativeOracleSha256"] == p["fixture"]["oracleSha256"]
        and review["referenceArguments"] == reference_arguments(p)
        and review["selectedField"] == "EXIF:ISO", "independent exact correspondence approval required")
    batch.require(p["schedule"] == schedule() and p["timeoutMs"] == TIMEOUT_MS
                  and p["captureBytes"] == CAPTURE_BYTES, "fixed schedule/bounds required")
    batch.require(p["environment"] and p["conditions"] and p["nativeSourceRevision"],
                  "declared runtime/storage/cache/load/work conditions required")
    reference_identity(p, identity_checkpoints)


def reference_identity(p, identity_checkpoints=None):
    """Recheck the already admitted installed runtime; never acquire a tool."""
    prior = b.load(p["priorReferenceEnvironment"], 2 * 1024 * 1024)
    batch.require(prior["versionProbe"].strip() == "13.59"
                  and prior["configurationSuppressionVerified"] is True,
                  "existing pinned reference/config evidence required")
    batch.require(prior["runtimeBefore"] == prior["runtimeAfter"]
                  and prior["sourceBefore"] == prior["sourceAfter"], "historical runtime changed")
    source_root = "/mnt/c/Projects/imageinfo/.local/tools/exiftool-13.59-source"
    batch.require(p["referenceLibrary"] == source_root + "/lib"
                  and p["referenceScript"] == source_root + "/exiftool",
                  "only existing reference installation allowed")
    batch.require(Path(p["referenceLauncher"]).name.lower() == "wsl.exe"
                  and str(Path(p["referenceLauncher"]).resolve()) in p["bindings"],
                  "pinned existing WSL launcher required")
    batch.require(p["distribution"] == "Ubuntu", "existing admitted Ubuntu runtime required")
    expected_input = "/mnt/c/" + p["fixture"]["input"].replace("\\", "/")[3:]
    batch.require(p["referenceInput"] == expected_input, "same declared physical input path mapping required")
    seen = {}
    for row in prior["sourceBefore"] + prior["runtimeBefore"]:
        path = row["path"]
        if path in seen:
            batch.require(seen[path] == row, "conflicting historical reference binding")
            continue
        seen[path] = row
        batch.require(path.startswith("/") and ".." not in Path(path).parts
                      and not any(c in path for c in "\x00\r\n"), "absolute existing runtime path required")
    rows = list(seen.values())
    batch.require(0 < len(rows) <= 4096, "installed-file verification row bound")
    request = json.dumps({"paths": [r["path"] for r in rows]}, ensure_ascii=True).encode("utf-8")
    batch.require(len(request) <= 1048576, "installed-file verification input bound")
    verifier_wsl = "/mnt/c/" + str(VERIFIER).replace("\\", "/")[3:]
    argv = [p["referenceLauncher"], "--distribution", p["distribution"], "--exec",
            "/usr/bin/perl", verifier_wsl]
    folder = Path(p["identityCheckRoot"]).resolve()
    batch.require(folder.is_relative_to(ROOT / ".local"), "private verification evidence root required")
    folder.mkdir(exist_ok=True)
    for index in range(16):
        evidence = folder / f"checkpoint-{index:02d}"
        try:
            evidence.mkdir()
            break
        except FileExistsError:
            continue
    else:
        raise ValueError("installed-file verification checkpoint bound")
    result, stdout, stderr = run_identity_verifier(argv, request, p["cwd"], p["environment"])
    for name, data in (("request.json", request), ("stdout", stdout), ("stderr", stderr)):
        with (evidence / name).open("xb") as stream:
            stream.write(data)
    expected = b"".join(f"{i}\t{r['sha256']}\t{int(r['byteLength'])}\n".encode("ascii")
                        for i, r in enumerate(rows))
    result.update(argv=argv, verifierSha256=b.digest(VERIFIER),
                  priorManifestSha256=b.digest(p["priorReferenceEnvironment"]),
                  requestSha256=hashlib.sha256(request).hexdigest(),
                  stdoutSha256=hashlib.sha256(stdout).hexdigest(),
                  stderrSha256=hashlib.sha256(stderr).hexdigest(),
                  exactMatch=result["outcome"] == "exited" and result["exitCode"] == 0
                      and stdout == expected and not stderr)
    checkpoint_record = evidence / "record.private.json"
    save(checkpoint_record, result)
    descriptor = {"checkpoint": evidence.name, "recordSha256": b.digest(checkpoint_record)}
    if identity_checkpoints is not None:
        identity_checkpoints.append(descriptor)
    batch.require(result["exactMatch"], "existing reference runtime/source verification failed; retained checkpoint")
    return descriptor


def run_identity_verifier(argv, request, cwd, env):
    """One fixed verifier with structured stdin and bounded concurrent drains.

    This is outside every measured attempt. It never launches a media reader.
    All byte prefixes and stop/failure outcomes are returned for private retention.
    """
    data = [bytearray(), bytearray()]
    totals = [0, 0]
    overflow, io_error = threading.Event(), threading.Event()
    def drain(pipe, index):
        try:
            while block := pipe.read(8192):
                totals[index] += len(block)
                remaining = 524288 - len(data[index])
                data[index].extend(block[:remaining])
                if len(block) > remaining:
                    overflow.set()
        except OSError:
            io_error.set()
        finally:
            pipe.close()
    def feed(pipe):
        try:
            pipe.write(request)
            pipe.close()
        except OSError:
            io_error.set()
    started = time.monotonic_ns()
    try:
        child = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
    except OSError as error:
        return {"outcome": "launch-error", "exitCode": None, "errorClass": type(error).__name__,
                "stdoutBytes": 0, "stderrBytes": 0}, b"", b""
    threads = [threading.Thread(target=drain, args=(child.stdout, 0), daemon=True),
               threading.Thread(target=drain, args=(child.stderr, 1), daemon=True),
               threading.Thread(target=feed, args=(child.stdin,), daemon=True)]
    outcome = "exited"
    try:
        for thread in threads:
            thread.start()
        while child.poll() is None:
            if overflow.is_set() or io_error.is_set() or time.monotonic_ns() - started >= 60_000_000_000:
                outcome = "output-limit" if overflow.is_set() else "io-error" if io_error.is_set() else "timeout"
                child.kill()
                break
            time.sleep(0.01)
    except KeyboardInterrupt:
        outcome = "cancelled"
        child.kill()
    child.wait()
    for thread in threads:
        thread.join(1)
    if any(t.is_alive() for t in threads) or io_error.is_set():
        outcome = "io-error" if outcome == "exited" else outcome
    if overflow.is_set():
        outcome = "output-limit" if outcome == "exited" else outcome
    return {"outcome": outcome, "exitCode": child.returncode,
            "stdoutBytes": totals[0], "stderrBytes": totals[1]}, bytes(data[0]), bytes(data[1])


def reference_arguments(p):
    return [p["referenceLauncher"], "--distribution", p["distribution"], "--exec",
            "/usr/bin/perl", "-I", p["referenceLibrary"], p["referenceScript"],
            "-config", "", "-j", "-n", "-a", "-G0:1:4", "-EXIF:ISO", "--", p["referenceInput"]]


def source_check(p, identity_checkpoints=None):
    rights(p, identity_checkpoints)  # No source byte access until exact current rights are checked.
    f = p["fixture"]
    stat = Path(f["input"]).stat()
    batch.require(stat.st_size <= 1024 ** 3, "source bound")
    result = {"sha256": b.digest(f["input"]), "bytes": stat.st_size,
              "mtimeNs": stat.st_mtime_ns, "device": stat.st_dev, "inode": stat.st_ino}
    batch.require(result["sha256"] == f["inputSha256"], "source identity changed")
    return result


def classify(sample, stdout, stderr, producer, p, expected):
    if sample["outcome"] != "exited" or sample["exitCode"] != 0 or stderr or sample["censored"]:
        return False
    if producer == "native":
        try:
            actual = batch.strict_json(stdout)
            return (actual["files"][0]["path"] == p["fixture"]["input"]
                    and batch.wire(batch.normalized_envelope(actual)) == batch.wire(expected))
        except (ValueError, TypeError, KeyError, IndexError):
            return False
    return True  # Exact selected-reference semantics are checked by the independent pair consumer.


def collect(root):
    from audit_comparable_read_151 import audit_pair
    root = Path(root).resolve()
    batch.require(root.is_relative_to(ROOT / ".local"), "private root required")
    p = b.load(root / "protocol.private.json")
    batch.require(Path(p["identityCheckRoot"]).resolve() == root / "reference-identity",
                  "campaign-owned identity evidence directory required")
    batch.require(not Path(p["identityCheckRoot"]).exists(), "fresh campaign identity root required")
    batch.require(not (root / "record.private.json").exists(), "fresh campaign record required")
    argv = {"native": [p["binary"], "metadata", "read", "--values", "raw", "--output", "json",
            "--max-bytes", "8388608", "--tag", "EXIF:ISO", "--", p["fixture"]["input"]],
            "reference": reference_arguments(p)}
    # Only preregistered process environment is passed; no inherited tool config.
    env = p["environment"]
    record = {"revision": REVISION, "protocolSha256": b.digest(root / "protocol.private.json"),
        "status": "aborted", "host": {"system": platform.system(), "version": platform.version(),
        "machine": platform.machine(), "pythonVersion": platform.python_version()},
        "argv": argv, "pairs": [], "sourceChecks": [], "identityCheckpoints": [],
        "publicCameraResultsExported": False}
    try:
        rights(p, record["identityCheckpoints"])
        captures = root / "captures"
        captures.mkdir()
        expected = batch.normalized_envelope(native.project(
            b.load(p["fixture"]["oracle"], b.MAX_CAPTURE_BYTES), "EXIF:ISO", "raw"))
        save(root / "expected-native.private.json", expected)
        initial = source_check(p, record["identityCheckpoints"])
        record["sourceChecks"].append(initial)
        for entry in schedule():
            pair = {**entry, "attempts": {}, "correspondence": "not-checked", "eligible": False}
            record["pairs"].append(pair)
            outputs = {}
            stop_reason = None
            for producer in entry["order"]:
                observer = telemetry.Observer(10) if producer == "native" else None
                sample, stdout, stderr = b.run_process(argv[producer], p["cwd"], env,
                    TIMEOUT_MS, CAPTURE_BYTES, observer if observer else ReferenceLifecycle())
                outputs[producer] = stdout
                stem = f"r{entry['round']}-p{entry['pair']}-{producer}"
                paths = {}
                for channel, data in (("stdout", stdout), ("stderr", stderr)):
                    path = captures / f"{stem}.{channel}"
                    with path.open("xb") as stream:
                        stream.write(data)
                    paths[channel] = str(path.relative_to(root))
                sample.update(producer=producer, captures=paths,
                    correctness=classify(sample, stdout, stderr, producer, p, expected),
                    telemetry=observer.report() if observer else {"available": False,
                        "reason": "reference-wrapper-descendant-membership-not-qualified",
                        "cpuNs": None, "memoryBytes": None, "logicalIoBytes": None, "physicalIoBytes": None})
                pair["attempts"][producer] = sample
                save(root / f"{stem}.private.json", sample)
                if sample["outcome"] == "cancelled":
                    stop_reason = "cancelled"
                    break
                if producer == "reference" and sample["censored"]:
                    # Killing the Windows launcher does not establish that its
                    # Linux descendants exited. Never schedule another attempt
                    # against uncertain remaining reference work.
                    stop_reason = "reference-" + sample["outcome"]
                    break
            try:
                pair["witness"] = audit_pair(outputs["native"], outputs["reference"],
                    expected_path=p["fixture"]["input"], reference_path=p["referenceInput"])
                pair["correspondence"] = "pass"
            except (ValueError, KeyError, TypeError, IndexError):
                pair["correspondence"] = "fail"
            pair["eligible"] = (entry["phase"] == "sample" and pair["correspondence"] == "pass"
                and all(a["correctness"] for a in pair["attempts"].values()))
            save(root / f"r{entry['round']}-p{entry['pair']}.private.json", pair)
            if stop_reason:
                record["stopReason"] = stop_reason
                return  # finally retains the incomplete/aborted fixed schedule.
            if entry["pair"] == WARMUPS + PAIRS - 1:
                check = source_check(p, record["identityCheckpoints"])
                record["sourceChecks"].append(check)
                batch.require(check == initial, "source boundary changed")
        rights(p, record["identityCheckpoints"])
        record["status"] = "completed"
    finally:
        if record["status"] != "completed":
            for pair in record["pairs"]:
                pair["eligible"] = False
        record["recordedUtc"] = datetime.now(timezone.utc).isoformat()
        save(root / "record.private.json", record)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", required=True)
    collect(parser.parse_args().run_root)
