"""Finite, retained subprocess supervision for the separate #0075 experiment.

Limits are logical consumption/capture limits, not OS quotas or containment.
Only the direct child is supervised. No decoder is loaded by importing this file.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import threading
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent

SCHEMA = "imageinfo-0075-process-v1"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value: dict) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")


@dataclass(frozen=True)
class Limits:
    deadline_seconds: float = 120.0
    capture_bytes_per_stream: int = 16384
    poll_seconds: float = 0.01
    drain_seconds: float = 2.0

    def validate(self) -> None:
        for value in (self.deadline_seconds, self.poll_seconds, self.drain_seconds):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError("positive finite process timing required")
        if self.deadline_seconds > 120 or self.drain_seconds > 5 or self.poll_seconds > 0.1:
            raise ValueError("process timing outside finite research envelope")
        if type(self.capture_bytes_per_stream) is not int or not 1 <= self.capture_bytes_per_stream <= 1048576:
            raise ValueError("capture bound outside finite research envelope")


def _cancelled(cancel) -> bool:
    if cancel is None:
        return False
    return bool(cancel() if callable(cancel) else cancel.is_set())


def run_process(command, attempt_root, limits: Limits, *, cancel=None, binding=None):
    """Run once in a fresh root; retain every launched/failed attempt.

    ``cancel`` is a callable or threading.Event. ``binding`` is an already
    admitted JSON record, retained verbatim in request.json. This low-level API
    does not confer permission to invoke a decoder or inspect private inputs.
    """
    limits.validate()
    if not isinstance(command, (list, tuple)) or not command or any(not isinstance(x, str) or "\0" in x for x in command):
        raise ValueError("literal nonempty argument array required")
    # Serialization before effects prevents a caller object being changed while
    # the process runs and refuses non-JSON/nonfinite binding values.
    frozen = json.loads(json.dumps(binding, allow_nan=False))
    root = Path(attempt_root).resolve()
    root.mkdir(parents=False, exist_ok=False)
    started = time.monotonic()
    environment = {key: os.environ[key] for key in ("SystemRoot", "WINDIR", "TEMP", "TMP") if key in os.environ}
    environment.update(PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1", PYTHONHASHSEED="0")
    request = {"schema": SCHEMA, "command": list(command), "limits": asdict(limits),
               "binding": frozen, "cwd": str(root), "environment": environment,
               "supervision": "direct-child-only; logical limits; no OS quota"}
    write_json(root / "request.json", request)
    rows = {name: {"capturedBytes": 0, "observedBytes": 0, "eof": False,
                   "overflow": False, "error": None} for name in ("stdout", "stderr")}
    stop = threading.Event()
    child = None
    readers = []
    outcome, error = "launch-failed", None

    def drain(name, pipe, output):
        row = rows[name]
        try:
            while True:
                block = pipe.read1(16384)
                if not block:
                    row["eof"] = True
                    break
                row["observedBytes"] += len(block)
                room = limits.capture_bytes_per_stream - row["capturedBytes"]
                kept = block[:max(0, room)]
                output.write(kept)
                output.flush()
                row["capturedBytes"] += len(kept)
                if len(block) > room:
                    row["overflow"] = True
                    stop.set()
                    break
        except Exception as exc:
            row["error"] = type(exc).__name__ + ": " + str(exc)
            stop.set()
        finally:
            output.close()
            pipe.close()

    outputs = {name: (root / (name + ".bin")).open("xb") for name in rows}
    try:
        if _cancelled(cancel):
            outcome = "cancelled-before-launch"
        else:
            child = subprocess.Popen(list(command), stdin=subprocess.DEVNULL,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     cwd=root, env=request["environment"], shell=False)
            for name in rows:
                thread = threading.Thread(target=drain, args=(name, getattr(child, name), outputs[name]), daemon=True)
                thread.start()
                readers.append(thread)
            while True:
                if _cancelled(cancel):
                    outcome = "cancelled"
                    break
                if stop.is_set():
                    outcome = "capture-failed"
                    break
                if time.monotonic() - started >= limits.deadline_seconds:
                    outcome = "deadline"
                    break
                if child.poll() is not None:
                    outcome = "exited"
                    break
                time.sleep(limits.poll_seconds)
    except BaseException as exc:
        outcome = "interrupted" if isinstance(exc, KeyboardInterrupt) else "supervisor-failed" if child else "launch-failed"
        error = type(exc).__name__ + ": " + str(exc)
    finally:
        if child is not None:
            if child.poll() is None:
                try:
                    child.kill()
                except OSError as exc:
                    error = "kill: " + str(exc)
            try:
                child.wait(timeout=limits.drain_seconds)
            except subprocess.TimeoutExpired:
                error = "direct child termination not confirmed"
            drain_end = time.monotonic() + limits.drain_seconds
            for thread in readers:
                thread.join(max(0, drain_end - time.monotonic()))
            if any(thread.is_alive() for thread in readers):
                outcome = "drain-incomplete"
            elif any(row["overflow"] or row["error"] for row in rows.values()):
                outcome = "capture-failed"
            if len(readers) != len(rows):
                # Failed thread creation must still release both owned pipes.
                for name in rows:
                    pipe = getattr(child, name)
                    if not rows[name]["eof"] and not any(t.is_alive() for t in readers):
                        pipe.close()
                        outputs[name].close()
        else:
            for output in outputs.values():
                output.close()
        # Open files from still-running drain threads cannot be claimed complete.
        for name, row in rows.items():
            if not any(t.is_alive() for t in readers):
                row["sha256"] = digest((root / (name + ".bin")).read_bytes())
            else:
                row["sha256"] = None
        result = {"schema": SCHEMA, "outcome": outcome, "error": error,
                  "returncode": None if child is None else child.poll(),
                  "terminationConfirmed": child is None or child.poll() is not None,
                  "elapsedSeconds": time.monotonic() - started, "streams": rows,
                  "requestSha256": digest((root / "request.json").read_bytes())}
        write_json(root / "process.json", result)
    return result


def read_bound(binding: dict, *, limit: int = 4 * 1024 * 1024) -> bytes:
    """Read an exact caller-pinned artifact, rejecting overlong files first."""
    if set(binding) != {"path", "sha256", "byteLength"}:
        raise ValueError("exact path/hash/length binding required")
    length = binding["byteLength"]
    if type(length) is not int or not 0 <= length <= limit:
        raise ValueError("binding exceeds logical byte limit")
    path = Path(binding["path"])
    if not path.is_absolute() or path.is_symlink() or not path.is_file() or path.stat().st_size != length:
        raise ValueError("bound regular absolute artifact required")
    with path.open("rb") as stream:
        data = stream.read(length + 1)
    if len(data) != length or digest(data) != binding["sha256"]:
        raise ValueError("bound artifact changed")
    return data


def _stat(path: Path) -> dict:
    value = path.stat()
    return {"st_dev": value.st_dev, "st_ino": value.st_ino,
            "size": value.st_size, "mtime_ns": value.st_mtime_ns,
            "ctime_ns": value.st_ctime_ns}


def _json_bound(binding: dict) -> dict:
    value = json.loads(read_bound(binding))
    if not isinstance(value, dict):
        raise ValueError("bound JSON object required")
    return value


def admit_request(request: dict, *, inspect_input: bool) -> dict:
    """Check trusted parent review and exact frozen artifacts before media read.

    The grant is a trusted orchestration input, not self-authenticating authority.
    Its externally supplied identity must be reviewed by the parent. Replacing
    editable qualification claims cannot silently qualify a different request.
    """
    if request.get("schema") != "imageinfo-0075-cell-v1" or request.get("stage") not in {"authored", "private"}:
        raise ValueError("separate declared authored/private stage required")
    grant = _json_bound(request["parentGrant"])
    core = {key: value for key, value in request.items() if key != "parentGrant"}
    canonical = json.dumps(core, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    if grant.get("schema") != "imageinfo-0075-parent-grant-v1" or grant.get("reviewedRequestSha256") != digest(canonical) or grant.get("stage") != request["stage"]:
        raise ValueError("exact reviewed request grant required")
    if grant.get("authorizedBy") != "parent-after-independent-review":
        raise ValueError("parent review grant required")
    if not request.get("recipeBindings"):
        raise ValueError("frozen recipe bindings required")
    for item in request["recipeBindings"]:
        read_bound(item)
    # Runtime verification must not load the decoder; the native closure is
    # independently checked by runtime.py after actual load/destruction.
    read_bound(request["runtimeManifest"])
    read_bound(request["profile"])
    from runtime import SETTINGS, PROFILE_ID, COMPONENT_PROFILE_CANONICAL_SHA256
    if request.get("limits") != asdict(Limits()):
        raise ValueError("exact declared process profile required")
    profile = _json_bound(request["profile"])
    if profile != {"schemaVersion": 1, "id": PROFILE_ID, "settings": SETTINGS,
                   "componentProfileCanonicalSha256": COMPONENT_PROFILE_CANONICAL_SHA256}:
        raise ValueError("exact generic technical profile required")
    if request["stage"] == "private":
        preflight = _json_bound(request["preflight"])
        authority = _json_bound(preflight["authority"])
        decision = _json_bound(preflight["decision"])
        # The fixed previously answered overlay is read before media access.
        expected_decision = (ROOT / ".local/rfw-decomposition-20261016/corpus.decoder-decision.private.json").resolve()
        if Path(preflight["decision"]["path"]).resolve() != expected_decision:
            raise ValueError("existing exact permission overlay required")
        if decision.get("ticket") != 164 or decision.get("choice") != "A":
            raise ValueError("scoped phase decision required")
        if authority.get("status") != "bound-pending-nondecoding-media-preflight":
            raise ValueError("historical authority bindings required")
        for item in authority["bindings"]:
            if item.get("matches") is not True or item["sha256"] != item["expectedSha256"] or int(item["byteLength"]) != int(item["expectedByteLength"]):
                raise ValueError("historical rights binding mismatch")
            read_bound({"path": item["path"], "sha256": item["sha256"], "byteLength": int(item["byteLength"])})
        if not (preflight.get("immutableObservation") is True and preflight.get("historicalIdentityMatches") is True and preflight.get("syntax", {}).get("accepted") is True):
            raise ValueError("accepted immutable preflight required")
        if preflight["source"] != request["input"]:
            raise ValueError("exact preflight input required")
        accepted = _json_bound(request["acceptedQualification"])
        if accepted.get("schema") != "imageinfo-0075-accepted-qualification-v1" or accepted.get("profile") != request["profile"] or accepted.get("runtimeManifest") != request["runtimeManifest"] or accepted.get("independentReview") != "go":
            raise ValueError("exact independently accepted authored qualification required")
    if inspect_input:
        from syntax import INPUT_LIMIT, PROFILE_ID, inspect_extent
        source = Path(request["input"]["path"])
        before = _stat(source)
        data = read_bound(request["input"], limit=INPUT_LIMIT)
        syntax = inspect_extent(data)
        after = _stat(source)
        if before != after:
            raise ValueError("source changed during bounded read")
        if request["stage"] == "private" and (before != preflight["after"] or not syntax["accepted"] or syntax.get("profileId") != PROFILE_ID or syntax != preflight["syntax"]):
            raise ValueError("fresh exact private profile fit required")
        return {"data": data, "before": before, "syntax": syntax}
    return {}


def run_cell(request: dict, attempt_root, *, cancel=None) -> dict:
    """Execute one reviewed cell. Refusal and all process failures are retained."""
    request = json.loads(json.dumps(request, allow_nan=False))
    root = Path(attempt_root).resolve()
    root.mkdir(parents=False, exist_ok=False)
    write_json(root / "cell-request.json", request)
    terminal = {"schema": "imageinfo-0075-cell-result-v1", "outcome": "not-run",
                "processInvocationAttempted": False}
    try:
        admitted = admit_request(request, inspect_input=True)
        # A single fixed parent-owned sentinel, independent of attempt names,
        # fences private retries before launch, including cancellation/failure.
        if request["stage"] == "private":
            write_json(ROOT / ".local/work-wave-20261017e/0075-private-cell.once.json",
                       {"schema": "imageinfo-0075-once-v1", "request": request,
                        "attemptRoot": str(root)})
        command = [request["interpreter"], str(HERE / "run.py"), "--worker",
                   str(root / "cell-request.json"), digest((root / "cell-request.json").read_bytes())]
        invocation = {"schema": "imageinfo-0075-invocation-v1", "command": command,
                      "cellRequestSha256": digest((root / "cell-request.json").read_bytes())}
        # Record launch uncertainty before crossing the process boundary. If
        # final process-record storage fails after execution, absence of a
        # returned result cannot truthfully mean that no process ran.
        write_json(root / "process-invocation.json", invocation)
        terminal.update(outcome="invalid-experiment", processInvocationAttempted=True)
        process = run_process(command, root / "process", Limits(**request.get("limits", {})),
                              cancel=cancel, binding={"cellRequestSha256": digest((root / "cell-request.json").read_bytes())})
        terminal.update(outcome="invalid-experiment", process=process)
        if process["outcome"] == "exited" and process["returncode"] == 0 and all(row["eof"] and not row["overflow"] and not row["error"] for row in process["streams"].values()):
            worker = json.loads((root / "process/stdout.bin").read_bytes())
            if worker.get("schema") != "imageinfo-0075-worker-v1":
                raise ValueError("invalid worker result schema")
            terminal.update(outcome=worker["decoder"]["outcome"], worker=worker)
        after = _stat(Path(request["input"]["path"]))
        read_bound(request["input"], limit=32 * 1024 * 1024)
        terminal.update(sourceBefore=admitted["before"], sourceAfter=after,
                        immutableObservation=after == admitted["before"])
        for item in request["recipeBindings"] + [request["runtimeManifest"], request["profile"]]:
            read_bound(item)
        if not terminal["immutableObservation"]:
            terminal["outcome"] = "invalid-experiment"
    except BaseException as exc:
        terminal.update(outcome="invalid-experiment" if terminal["processInvocationAttempted"] else "not-run",
                        error=type(exc).__name__ + ": " + str(exc))
        if terminal["processInvocationAttempted"]:
            # These are available artifact observations only, not proof of EOF
            # or termination when the supervisor could not return a record.
            evidence = []
            for name in ("process-invocation.json", "process/request.json", "process/process.json",
                         "process/stdout.bin", "process/stderr.bin"):
                path = root / name
                if path.is_file():
                    evidence.append({"path": name, "byteLength": path.stat().st_size})
            terminal["availableProcessEvidence"] = evidence
    write_json(root / "cell-result.json", terminal)
    return terminal


def worker(request_path: Path, expected_sha256: str) -> dict:
    import runtime
    import decoder
    raw = request_path.read_bytes()
    if len(raw) > 4 * 1024 * 1024 or digest(raw) != expected_sha256:
        raise ValueError("worker request identity mismatch")
    request = json.loads(raw)
    admitted = admit_request(request, inspect_input=True)
    if request["stage"] == "private":
        sentinel = ROOT / ".local/work-wave-20261017e/0075-private-cell.once.json"
        once = json.loads(sentinel.read_bytes())
        if once.get("request") != request or Path(once["attemptRoot"]).resolve() != request_path.parent.resolve():
            raise ValueError("single private attempt binding differs")
        write_json(ROOT / ".local/work-wave-20261017e/0075-private-worker.once.json",
                   {"schema": "imageinfo-0075-worker-once-v1", "requestSha256": expected_sha256})
    verified = runtime.verify_runtime()
    if _json_bound(request["runtimeManifest"]) != verified.identity():
        raise ValueError("runtime manifest differs from installed verified runtime")
    def pixel_sink(view):
        target = request_path.parent / "pixels.rgb"
        if len(view) != admitted["syntax"]["decodedBytes"] or len(view) > 256 * 1024 * 1024:
            raise ValueError("decoded output size differs from admitted bound")
        with target.open("xb") as stream:
            written = stream.write(view)
            if written != len(view):
                raise OSError("short decoded output write")
    # Every successful output is separately retained for independent byte/hash
    # consumption by the auditor. Failed partial derivatives remain untouched.
    result = decoder.decode(admitted["data"], load_library=verified.load_library,
                            verify_loaded=verified.assert_loaded_closure, pixel_sink=pixel_sink)
    actual_closure = verified.assert_loaded_closure() if result.get("nativeInvoked") else None
    read_bound(request["input"], limit=32 * 1024 * 1024)
    if _stat(Path(request["input"]["path"])) != admitted["before"]:
        raise ValueError("worker source changed")
    return {"schema": "imageinfo-0075-worker-v1", "decoder": result,
            "sourceBefore": admitted["before"], "sourceAfter": admitted["before"],
            "runtimeIdentity": verified.identity(), "loadedClosure": actual_closure,
            "pixelArtifact": "pixels.rgb" if result.get("pixelSinkCompleted") else None}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", nargs=2, metavar=("REQUEST", "SHA256"), required=True)
    args = parser.parse_args()
    result = worker(Path(args.worker[0]), args.worker[1])
    print(json.dumps(result, sort_keys=True, allow_nan=False))
