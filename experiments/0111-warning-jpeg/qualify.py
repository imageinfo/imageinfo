"""Authored-only warning-aware TurboJPEG qualification; no media path input."""
import argparse
import ctypes as C
from ctypes import wintypes as W
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import threading

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "0107-jpeg-validator" / "qualify.py"
ROOT = Path(sys.executable).parent.parent
NATIVE = ROOT / "native/libheif"
DLL = NATIVE / "libheif/bin/turbojpeg.dll"
CASES = ("complete", "entropy-truncated", "early-eoi", "immediate-eoi",
         "trailing-zeros", "nonzero-suffix", "progressive")
INPUT_LIMIT, DIMENSION_LIMIT, CAPTURE_LIMIT, TIMEOUT_SECONDS = 65536, 128, 8192, 10
STOPONWARNING = 8192
SETTINGS = {"inputBytes": INPUT_LIMIT, "dimension": DIMENSION_LIMIT,
            "captureBytesPerStream": CAPTURE_LIMIT, "childDeadlineSeconds": TIMEOUT_SECONDS,
            "api": "tjDecompress2", "flags": STOPONWARNING, "pixelFormat": "RGB",
            "extentPolicy": "single baseline 8-bit Huffman interleaved scan; no restart; suffix absent or exactly 32 zeros"}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def base_module():
    spec = importlib.util.spec_from_file_location("authored107", BASE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def controls():
    from PIL import Image
    fixtures, offsets = base_module().controls()
    fixtures["immediate-eoi"] = fixtures["complete"][:offsets["scanStart"]] + b"\xff\xd9"
    fixtures["nonzero-suffix"] = fixtures["complete"] + b"\x01"
    pixels = bytes(c for y in range(64) for x in range(64) for c in
                   ((x * 13 + y * 7) % 256, (x * 3 + y * 19) % 256,
                    (x * 23 + y * 11) % 256))
    output = io.BytesIO()
    Image.frombytes("RGB", (64, 64), pixels).save(
        output, "JPEG", quality=90, subsampling=0, optimize=False, progressive=True)
    fixtures["progressive"] = output.getvalue()
    return fixtures, offsets


def library():
    dll = C.CDLL(str(DLL))
    signatures = {
        "tjInitDecompress": ([], C.c_void_p),
        "tjDecompressHeader3": ([C.c_void_p, C.c_void_p, C.c_ulong] +
                                [C.POINTER(C.c_int)] * 4, C.c_int),
        "tjDecompress2": ([C.c_void_p, C.c_void_p, C.c_ulong, C.c_void_p,
                           C.c_int, C.c_int, C.c_int, C.c_int, C.c_int], C.c_int),
        "tjGetErrorCode": ([C.c_void_p], C.c_int),
        "tjGetErrorStr2": ([C.c_void_p], C.c_char_p),
        "tjDestroy": ([C.c_void_p], C.c_int),
    }
    for name, (args, result) in signatures.items():
        function = getattr(dll, name)
        function.argtypes, function.restype = args, result
    if C.sizeof(C.c_ulong) != 4 or C.sizeof(C.c_void_p) != 8:
        raise RuntimeError("reviewed Windows x64 ABI required")
    return dll


def loaded_components():
    # Pin actual loaded non-OS modules rather than guessing the DLL's closure.
    kernel, psapi = C.WinDLL("kernel32", use_last_error=True), C.WinDLL("psapi", use_last_error=True)
    kernel.GetCurrentProcess.restype = W.HANDLE
    psapi.EnumProcessModules.argtypes = [W.HANDLE, C.POINTER(W.HMODULE), W.DWORD, C.POINTER(W.DWORD)]
    psapi.EnumProcessModules.restype = W.BOOL
    psapi.GetModuleFileNameExW.argtypes = [W.HANDLE, W.HMODULE, W.LPWSTR, W.DWORD]
    psapi.GetModuleFileNameExW.restype = W.DWORD
    handles, needed = (W.HMODULE * 2048)(), W.DWORD()
    process = kernel.GetCurrentProcess()
    if not psapi.EnumProcessModules(process, handles, C.sizeof(handles), C.byref(needed)) or needed.value > C.sizeof(handles):
        raise RuntimeError("module inventory failed or exceeded ceiling")
    osroot = Path(os.environ["SystemRoot"]).resolve()
    rows = {}
    for handle in handles[:needed.value // C.sizeof(W.HMODULE)]:
        buffer = C.create_unicode_buffer(32768)
        count = psapi.GetModuleFileNameExW(process, handle, buffer, len(buffer))
        if not count or count >= len(buffer):
            raise RuntimeError("module path inventory failed")
        path = Path(buffer.value).resolve()
        if path.is_relative_to(osroot):
            continue
        if not path.is_relative_to(ROOT):
            raise RuntimeError("unexpected non-OS module outside runtime bundle")
        content = path.read_bytes()
        rows[path.relative_to(ROOT).as_posix()] = {"byteLength": len(content), "sha256": digest(content)}
    return rows


def identity():
    controls()  # Loads the actual authored encoder and its native dependencies.
    library()
    return {"pillowRuntime": base_module().identity(), "loadedNonOsModules": loaded_components(),
            "manifest": {"sha256": digest((NATIVE / "manifest.json").read_bytes()),
                         "package": json.loads((NATIVE / "manifest.json").read_text())},
            "recipeSha256": digest(Path(__file__).read_bytes()),
            "authoredRecipeSha256": digest(BASE.read_bytes())}


def inspect_extent(data):
    """Finite single-scan profile/extent walk, separate from native entropy evidence."""
    if len(data) > INPUT_LIMIT:
        return {"accepted": False, "reason": "input-bound"}
    if data[:2] != b"\xff\xd8":
        return {"accepted": False, "reason": "missing-soi"}
    cursor, frame, scan, component_ids = 2, False, False, set()
    while cursor < len(data):
        if data[cursor] != 255:
            return {"accepted": False, "reason": "expected-marker"}
        while cursor < len(data) and data[cursor] == 255:
            cursor += 1
        if cursor >= len(data):
            break
        marker = data[cursor]
        cursor += 1
        if marker == 217:
            suffix = data[cursor:]
            accepted = frame and scan and suffix in (b"", bytes(32))
            return {"accepted": accepted, "reason": "supported" if accepted else "suffix-or-profile",
                    "eoiEnd": cursor, "suffixBytes": len(suffix)}
        if marker in (0, 216) or 208 <= marker <= 215:
            return {"accepted": False, "reason": "unsupported-marker"}
        if scan or marker not in (192, 196, 218, 219, 254, *range(224, 240)):
            return {"accepted": False, "reason": "unsupported-marker-or-postscan"}
        if cursor + 2 > len(data):
            break
        length = int.from_bytes(data[cursor:cursor + 2], "big")
        if length < 2 or cursor + length > len(data):
            return {"accepted": False, "reason": "segment-length"}
        payload = data[cursor + 2:cursor + length]
        cursor += length
        if marker == 192:
            if frame or len(payload) != 15 or payload[0] != 8 or payload[5] != 3:
                return {"accepted": False, "reason": "unsupported-frame"}
            height, width = int.from_bytes(payload[1:3], "big"), int.from_bytes(payload[3:5], "big")
            if not (0 < width <= DIMENSION_LIMIT and 0 < height <= DIMENSION_LIMIT):
                return {"accepted": False, "reason": "dimension-bound"}
            frame = True
            component_ids = set(payload[6::3])
            if len(component_ids) != 3:
                return {"accepted": False, "reason": "duplicate-component"}
        elif 193 <= marker <= 207 and marker not in (196,):
            return {"accepted": False, "reason": "unsupported-frame-or-coding"}
        elif marker == 218:
            if not frame or scan or len(payload) != 10 or payload[0] != 3 or payload[-3:] != b"\x00\x3f\x00":
                return {"accepted": False, "reason": "unsupported-scan"}
            if len(set(payload[1:7:2])) != 3 or set(payload[1:7:2]) != component_ids:
                return {"accepted": False, "reason": "scan-components"}
            scan = True
            # Stuffed FF00 and restart markers cannot terminate entropy traversal.
            while cursor < len(data):
                if data[cursor] != 255:
                    cursor += 1
                    continue
                start = cursor
                while cursor < len(data) and data[cursor] == 255:
                    cursor += 1
                if cursor >= len(data):
                    break
                if data[cursor] == 0:
                    cursor += 1
                    continue
                cursor = start
                break
    return {"accepted": False, "reason": "incomplete-extent"}


def native_decode(data):
    if len(data) > INPUT_LIMIT:
        return {"outcome": "input-bound"}
    dll, source = library(), C.create_string_buffer(data)
    handle = dll.tjInitDecompress()
    if not handle:
        raise RuntimeError("native initialization failed")
    try:
        width, height, sampling, colorspace = (C.c_int() for _ in range(4))
        header = dll.tjDecompressHeader3(handle, source, len(data), C.byref(width),
                                       C.byref(height), C.byref(sampling), C.byref(colorspace))
        def diagnostic(status):
            message = dll.tjGetErrorStr2(handle)
            if message is None or len(message) > 240:
                raise RuntimeError("native diagnostic absent or exceeds reviewed ceiling")
            return {"returnCode": status, "severityRaw": dll.tjGetErrorCode(handle),
                    "severityMeaningful": status != 0,
                    "diagnosticRaw": message.decode("utf-8", "replace")}
        header_observation = diagnostic(header)
        if header != 0:
            return {"outcome": "header-refused", "header": header_observation}
        if not (0 < width.value <= DIMENSION_LIMIT and 0 < height.value <= DIMENSION_LIMIT):
            return {"outcome": "dimension-bound"}
        pixels = C.create_string_buffer(width.value * height.value * 3)
        status = dll.tjDecompress2(handle, source, len(data), pixels, width.value, 0, height.value, 0, STOPONWARNING)
        row = {"outcome": "warning-free-pixels" if status == 0 else "native-refused",
               "header": header_observation, "dimensions": [width.value, height.value], **diagnostic(status)}
        if not status:
            row.update(decodedBytes=len(pixels), pixelSha256=digest(pixels.raw))
        return row
    finally:
        if dll.tjDestroy(handle) != 0:
            raise RuntimeError("native destroy failed")


def validate(data):
    extent, native = inspect_extent(data), native_decode(data)
    return {"extent": extent, "native": native,
            "accepted": extent["accepted"] and native["outcome"] == "warning-free-pixels"}


def bounded_child(case, attempt_dir):
    child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--worker", case],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    captures, overflow = {"stdout": bytearray(), "stderr": bytearray()}, threading.Event()
    def drain(name, pipe):
        while chunk := pipe.read(1024):
            remaining = CAPTURE_LIMIT - len(captures[name])
            captures[name].extend(chunk[:remaining])
            if len(chunk) > remaining:
                overflow.set()
                child.kill()
        pipe.close()
    readers = [threading.Thread(target=drain, args=(name, pipe)) for name, pipe in
               (("stdout", child.stdout), ("stderr", child.stderr))]
    for reader in readers:
        reader.start()
    timed_out = False
    try:
        child.wait(timeout=TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        timed_out = True
        child.kill()
        child.wait()
    finally:
        for reader in readers:
            reader.join()
    for name, value in captures.items():
        (attempt_dir / (case + "." + name)).write_bytes(value)
    process = {"exitCode": child.returncode, "timedOut": timed_out, "captureOverflow": overflow.is_set(),
               "stdoutBytes": len(captures["stdout"]), "stderrBytes": len(captures["stderr"])}
    (attempt_dir / (case + ".process.json")).write_text(json.dumps(process, sort_keys=True))
    if timed_out or overflow.is_set() or child.returncode:
        raise RuntimeError("child failure retained in attempt directory")
    return {"observed": json.loads(captures["stdout"]), "process": process}


def reviewed_profile():
    profile = json.loads((HERE / "profile.json").read_text())
    if profile["settings"] != SETTINGS:
        raise RuntimeError("profile settings differ from reviewed constants")
    if (digest(Path(__file__).read_bytes()) != profile["runtime"]["recipeSha256"] or
            digest(BASE.read_bytes()) != profile["runtime"]["authoredRecipeSha256"] or
            digest((NATIVE / "manifest.json").read_bytes()) != profile["runtime"]["manifest"]["sha256"]):
        raise RuntimeError("recipe or package manifest identity differs")
    python = Path(sys.executable).parent
    package = python / "Lib/site-packages/PIL"
    distribution = package.parent / "pillow-12.3.0.dist-info"
    component_paths = {
        "python-executable": Path(sys.executable), "python-runtime": python / "python312.dll",
        "python-notices": python / "LICENSE.txt", "pillow-init": package / "__init__.py",
        "pillow-jpeg-plugin": package / "JpegImagePlugin.py", "pillow-image-file": package / "ImageFile.py",
        "pillow-image": package / "Image.py", "pillow-native-decoder": package / "_imaging.cp312-win_amd64.pyd",
        "pillow-metadata": distribution / "METADATA", "pillow-notices": distribution / "licenses/LICENSE",
        "pillow-sbom": distribution / "sboms/pillow-12.3.0.cdx.json",
    }
    expected_components = profile["runtime"]["pillowRuntime"]["components"]
    if component_paths.keys() != expected_components.keys():
        raise RuntimeError("unexpected control encoder component set")
    for name, path in component_paths.items():
        content = path.read_bytes()
        if {"byteLength": len(content), "sha256": digest(content)} != expected_components[name]:
            raise RuntimeError("preload control encoder component identity differs")
    # Verify pinned bytes before loading the native codec or generating controls.
    for name, expected in profile["runtime"]["loadedNonOsModules"].items():
        path = ROOT / name
        if not path.resolve().is_relative_to(ROOT.resolve()):
            raise RuntimeError("component path escapes runtime")
        content = path.read_bytes()
        if {"byteLength": len(content), "sha256": digest(content)} != expected:
            raise RuntimeError("preload component identity differs")
    if identity() != profile["runtime"]:
        raise RuntimeError("runtime or recipe differs from reviewed profile")
    return profile


def qualify(attempt_root):
    attempt_root.mkdir(parents=False, exist_ok=False)
    profile = reviewed_profile()
    (attempt_root / "profile.json").write_bytes((HERE / "profile.json").read_bytes())
    fixtures, offsets = controls()
    rows = []
    for case in CASES:
        observed = bounded_child(case, attempt_root)
        rows.append({"case": case, "inputBytes": len(fixtures[case]),
                     "inputSha256": digest(fixtures[case]), **observed})
        (attempt_root / "partial.json").write_text(json.dumps(rows, indent=2, sort_keys=True))
    by_case = {row["case"]: row["observed"] for row in rows}
    positives = all(by_case[c]["accepted"] for c in ("complete", "trailing-zeros"))
    incomplete = all(by_case[c]["native"]["outcome"] == "native-refused" for c in
                     ("entropy-truncated", "early-eoi", "immediate-eoi"))
    policy = all(not by_case[c]["accepted"] for c in ("nonzero-suffix", "progressive"))
    equal = by_case["complete"]["native"].get("pixelSha256") == by_case["trailing-zeros"]["native"].get("pixelSha256")
    return {"schemaVersion": 1, "ticket": 111, "profile": profile["id"],
            "profileSha256": digest((HERE / "profile.json").read_bytes()), "controlOffsets": offsets,
            "controls": rows, "finiteProfileQualified": positives and incomplete and policy and equal,
            "cameraExecution": False, "productionCapability": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", choices=CASES, help=argparse.SUPPRESS)
    parser.add_argument("--attempt-root", type=Path)
    arguments = parser.parse_args()
    if arguments.worker:
        profile = reviewed_profile()
        result = validate(controls()[0][arguments.worker])
        if loaded_components() != profile["runtime"]["loadedNonOsModules"]:
            raise RuntimeError("loaded module closure changed during decoding")
        print(json.dumps(result, sort_keys=True))
    elif arguments.attempt_root:
        report = qualify(arguments.attempt_root)
        destination = arguments.attempt_root / "report.json"
        destination.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        print(json.dumps({"finiteProfileQualified": report["finiteProfileQualified"], "report": str(destination)}))
    else:
        parser.error("--attempt-root is required")
