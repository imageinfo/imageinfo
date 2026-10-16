"""Independent finite native replay; accepts authored controls only, never media."""

import argparse
import ctypes as c
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
from contextlib import contextmanager

HERE = Path(__file__).resolve().parent
DLL = (Path(sys.executable).parent.parent / "native/libheif/libheif/bin/turbojpeg.dll")
EXPECTED_DLL = "fb734a4abb87c07eb78a7292facf0944d7331d55573cd9afd0f242dd0c573245"
CASES = ("complete", "entropy-truncated", "early-eoi", "immediate-eoi",
         "trailing-zeros", "nonzero-suffix", "progressive")


@contextmanager
def replace_attribute(target, name, value):
    previous = getattr(target, name)
    setattr(target, name, value)
    try:
        yield
    finally:
        setattr(target, name, previous)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def authored_controls():
    # Reuse only the already public formula/encoding, not validator decisions.
    spec = importlib.util.spec_from_file_location(
        "authored_0107", HERE.parent / "0107-jpeg-validator/qualify.py")
    old = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old)
    data, offsets = old.controls()
    from PIL import Image
    pixels = bytes(v for y in range(64) for x in range(64) for v in
                   ((x * 13 + y * 7) % 256, (x * 3 + y * 19) % 256,
                    (x * 23 + y * 11) % 256))
    output = io.BytesIO()
    Image.frombytes("RGB", (64, 64), pixels).save(
        output, "JPEG", quality=90, subsampling=0, optimize=False, progressive=True)
    data["immediate-eoi"] = data["complete"][:offsets["scanStart"]] + b"\xff\xd9"
    data["nonzero-suffix"] = data["complete"] + b"\x01"
    data["progressive"] = output.getvalue()
    assert set(data) == set(CASES)
    return data


def native(case):
    assert sys.platform == "win32" and c.sizeof(c.c_ulong) == 4 and c.sizeof(c.c_void_p) == 8
    assert sha(DLL.read_bytes()) == EXPECTED_DLL
    data = authored_controls()[case]
    assert 0 < len(data) <= 65536
    # Legacy API uses unsigned long (Windows LLP64), not size_t.
    lib = c.CDLL(str(DLL.resolve()))
    ptr = c.POINTER(c.c_ubyte)
    lib.tjInitDecompress.argtypes, lib.tjInitDecompress.restype = [], c.c_void_p
    lib.tjDecompressHeader3.argtypes = [c.c_void_p, ptr, c.c_ulong] + [c.POINTER(c.c_int)] * 4
    lib.tjDecompressHeader3.restype = c.c_int
    lib.tjDecompress2.argtypes = [c.c_void_p, ptr, c.c_ulong, ptr] + [c.c_int] * 5
    lib.tjDecompress2.restype = c.c_int
    lib.tjGetErrorCode.argtypes, lib.tjGetErrorCode.restype = [c.c_void_p], c.c_int
    lib.tjGetErrorStr2.argtypes, lib.tjGetErrorStr2.restype = [c.c_void_p], c.c_char_p
    lib.tjDestroy.argtypes, lib.tjDestroy.restype = [c.c_void_p], c.c_int
    handle = lib.tjInitDecompress()
    assert handle
    source = (c.c_ubyte * len(data)).from_buffer_copy(data)

    def result(status):
        severity = lib.tjGetErrorCode(handle)
        diagnostic = lib.tjGetErrorStr2(handle).decode("utf-8", "replace")
        assert len(diagnostic.encode()) <= 4096
        return {"returnCode": status, "severityRaw": severity,
                "severityMeaningful": status == -1, "diagnosticRaw": diagnostic}

    try:
        width, height, subsamp, colorspace = [c.c_int() for _ in range(4)]
        header = result(lib.tjDecompressHeader3(handle, source, len(data),
                        c.byref(width), c.byref(height), c.byref(subsamp), c.byref(colorspace)))
        assert header["returnCode"] == 0
        assert 0 < width.value <= 128 and 0 < height.value <= 128
        output = (c.c_ubyte * (width.value * height.value * 3))()
        decoded = result(lib.tjDecompress2(handle, source, len(data), output,
                         width.value, width.value * 3, height.value, 0, 8192))
        return {"case": case, "inputBytes": len(data), "inputSha256": sha(data),
                "dimensions": [width.value, height.value], "header": header,
                "decode": decoded, "outputBufferBytes": len(output),
                "outputBufferSha256": sha(bytes(output))}
    finally:
        assert lib.tjDestroy(handle) == 0


def replay():
    rows = []
    for case in CASES:
        # This audit's native children return one tiny fixed record. The production
        # candidate harness separately exercises streaming capture overflow.
        completed = subprocess.run([sys.executable, str(Path(__file__).resolve()),
                                    "--native-worker", case], capture_output=True,
                                   timeout=10, check=True)
        assert len(completed.stdout) <= 8192 and len(completed.stderr) <= 8192
        assert not completed.stderr
        row = json.loads(completed.stdout)
        expected_failure = case in ("entropy-truncated", "early-eoi", "immediate-eoi")
        if expected_failure:
            assert row["decode"]["returnCode"] == -1
            assert row["decode"]["severityRaw"] == 0
            assert row["decode"]["diagnosticRaw"]
        else:
            assert row["decode"]["returnCode"] == 0
        assert row["dimensions"] == [64, 64]
        rows.append(row)
    assert rows[0]["outputBufferSha256"] == rows[4]["outputBufferSha256"]
    return {"schemaVersion": 1, "ticket": 111, "independentNativeReplay": rows,
            "nativeOnlySuffixAndProgressiveSuccessDoesNotAuthorizeWrapperAcceptance": True,
            "cameraExecution": False, "productionCapability": False}


def wrapper_audit(attempt_root):
    """Probe real bounded subprocesses and refusal paths separately from JPEGs."""
    attempt_root.mkdir(parents=False, exist_ok=False)
    spec = importlib.util.spec_from_file_location("candidate111", HERE / "qualify.py")
    candidate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(candidate)
    profile = candidate.reviewed_profile()
    fixtures, _ = candidate.controls()
    independent = authored_controls()
    assert fixtures == independent
    curated = json.loads((HERE / "observations.json").read_text(encoding="utf-8"))
    assert curated["finiteProfileQualified"] and not curated["cameraExecution"]
    assert curated["profileSha256"] == sha((HERE / "profile.json").read_bytes())
    stored_rows = {row["case"]: row for row in curated["controls"]}
    assert set(stored_rows) == set(CASES)
    expected_accepts = {"complete", "trailing-zeros"}
    for case in CASES:
        observed = candidate.validate(fixtures[case])
        assert observed["accepted"] == (case in expected_accepts)
        assert observed == stored_rows[case]["observed"]
        assert sha(fixtures[case]) == stored_rows[case]["inputSha256"]
        assert len(fixtures[case]) == stored_rows[case]["inputBytes"]
    checks = ["seven-whole-extent-wrapper-decisions", "independent-authored-bytes-match",
              "curated-observations-match-fresh-native-results"]
    assert candidate.inspect_extent(bytes(65537))["reason"] == "input-bound"
    assert candidate.native_decode(bytes(65537))["outcome"] == "input-bound"
    # SOF dimensions are parsed independently from fixed authored marker lengths.
    data = bytearray(fixtures["complete"])
    cursor = 2
    while data[cursor + 1] != 192:
        cursor += 2 + int.from_bytes(data[cursor + 2:cursor + 4], "big")
    data[cursor + 5:cursor + 7] = (129).to_bytes(2, "big")
    assert candidate.inspect_extent(data)["reason"] == "dimension-bound"
    assert candidate.native_decode(bytes(data))["outcome"] == "dimension-bound"
    checks.extend(["input-bound", "dimension-bound"])
    # Stuffing traversal must skip FF00 inside entropy. APP payload markers must
    # likewise not terminate the walk; neither check claims entropy validity.
    complete = fixtures["complete"]
    assert candidate.inspect_extent(complete[:2] + b"\xff\xee\x00\x06\xff\xd9\x00\x00" + complete[2:])["accepted"]
    assert candidate.inspect_extent(complete[:-2] + b"\xff\x00\xd9" + complete[-2:])["eoiEnd"] == len(complete) + 3
    assert not candidate.inspect_extent(complete + bytes(31))["accepted"]
    assert not candidate.inspect_extent(complete + bytes(33))["accepted"]
    checks.extend(["marker-in-app-payload", "stuffing-aware-extent", "non32-zero-suffix-refused"])
    for mutation in ("settings", "runtime"):
        directory = attempt_root / mutation
        directory.mkdir()
        changed = json.loads(json.dumps(profile))
        if mutation == "settings":
            changed["settings"]["inputBytes"] += 1
        else:
            components = changed["runtime"]["loadedNonOsModules"]
            components[next(iter(components))]["sha256"] = "0" * 64
        (directory / "profile.json").write_text(json.dumps(changed), encoding="utf-8", newline="\n")
        with replace_attribute(candidate, "HERE", directory):
            try:
                candidate.reviewed_profile()
            except RuntimeError:
                checks.append(mutation + "-mismatch-refused")
            else:
                raise AssertionError(mutation + " mismatch accepted")
    original_popen = subprocess.Popen
    injected = {
        "stdout-overflow": "import sys;sys.stdout.buffer.write(b'x'*9000);sys.stdout.flush()",
        "stderr-overflow": "import sys;sys.stderr.buffer.write(b'x'*9000);sys.stderr.flush()",
        "deadline": "import time;time.sleep(12)",
        "nonzero-exit": "raise SystemExit(7)",
    }
    process_checks = {}
    for name, code in injected.items():
        directory = attempt_root / name
        directory.mkdir()
        def substitute(_args, **kwargs):
            return original_popen([sys.executable, "-c", code], **kwargs)
        with replace_attribute(candidate.subprocess, "Popen", substitute):
            try:
                candidate.bounded_child("complete", directory)
            except RuntimeError:
                pass
            else:
                raise AssertionError(name + " was accepted")
        process = json.loads((directory / "complete.process.json").read_text())
        assert process["stdoutBytes"] <= 8192 and process["stderrBytes"] <= 8192
        assert (directory / "complete.stdout").stat().st_size == process["stdoutBytes"]
        assert (directory / "complete.stderr").stat().st_size == process["stderrBytes"]
        if name.endswith("overflow"):
            assert process["captureOverflow"]
        elif name == "deadline":
            assert process["timedOut"]
        else:
            assert process["exitCode"] == 7
        process_checks[name] = process
    return {"checks": checks, "processRefusals": process_checks,
            "candidateSourceSha256": sha((HERE / "qualify.py").read_bytes()),
            "profileSha256": sha((HERE / "profile.json").read_bytes()),
            "auditSourceSha256": sha(Path(__file__).read_bytes())}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-worker", choices=CASES, help=argparse.SUPPRESS)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--candidate-attempt-root", type=Path)
    args = parser.parse_args()
    report = native(args.native_worker) if args.native_worker else replay()
    if args.candidate_attempt_root:
        assert not args.native_worker
        report["independentWrapperAudit"] = wrapper_audit(args.candidate_attempt_root)
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8", newline="\n")
    else:
        print(encoded, end="")
