"""Finite authored-only Pillow decoder qualification; never accepts media paths."""

import argparse
import hashlib
import importlib.metadata
import io
import json
from pathlib import Path
import platform
import subprocess
import sys
import threading

HERE = Path(__file__).resolve().parent
INPUT_LIMIT = 65536
DIMENSION_LIMIT = 128
CAPTURE_LIMIT = 8192
TIMEOUT_SECONDS = 10
CASES = ("complete", "entropy-truncated", "trailing-zeros", "early-eoi")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def identity():
    import PIL
    from PIL import JpegImagePlugin, _imaging, features

    package = Path(PIL.__file__).parent
    distribution = Path(importlib.metadata.distribution("Pillow")._path)
    paths = {
        "python-executable": Path(sys.executable),
        "python-runtime": Path(sys.executable).parent / "python312.dll",
        "python-notices": Path(sys.executable).parent / "LICENSE.txt",
        "pillow-init": Path(PIL.__file__),
        "pillow-jpeg-plugin": Path(JpegImagePlugin.__file__),
        "pillow-image-file": package / "ImageFile.py",
        "pillow-image": package / "Image.py",
        "pillow-native-decoder": Path(_imaging.__file__),
        "pillow-metadata": distribution / "METADATA",
        "pillow-notices": distribution / "licenses" / "LICENSE",
        "pillow-sbom": distribution / "sboms" / "pillow-12.3.0.cdx.json",
    }
    return {
        "python": platform.python_version(),
        "platform": platform.system(),
        "machine": platform.machine(),
        "pillow": PIL.__version__,
        "jpegApi": features.version("jpg"),
        "libjpegTurbo": features.version("libjpeg_turbo"),
        "licenseExpression": importlib.metadata.metadata("Pillow")["License-Expression"],
        "components": {
            name: {"sha256": digest(path.read_bytes()), "byteLength": path.stat().st_size}
            for name, path in paths.items()
        },
    }


def controls():
    from PIL import Image

    # Formula-authored pixels avoid imported photographs and upstream fixtures.
    pixels = bytes(
        component
        for y in range(64)
        for x in range(64)
        for component in ((x * 13 + y * 7) % 256, (x * 3 + y * 19) % 256,
                          (x * 23 + y * 11) % 256)
    )
    image = Image.frombytes("RGB", (64, 64), pixels)
    encoded = io.BytesIO()
    image.save(encoded, "JPEG", quality=90, subsampling=0, optimize=False,
               progressive=False)
    complete = encoded.getvalue()
    # Parse marker lengths up to the single baseline scan; never search entropy
    # for marker-looking bytes to infer its start.
    cursor = 2
    assert complete[:2] == b"\xff\xd8"
    while True:
        assert complete[cursor] == 255
        marker = complete[cursor + 1]
        length = int.from_bytes(complete[cursor + 2:cursor + 4], "big")
        assert length >= 2
        cursor += 2 + length
        if marker == 218:
            break
        assert cursor < len(complete)
    assert complete[-2:] == b"\xff\xd9"
    cut = cursor + (len(complete) - 2 - cursor) // 2
    return {
        "complete": complete,
        "entropy-truncated": complete[:cut],
        "trailing-zeros": complete + bytes(32),
        "early-eoi": complete[:cut] + b"\xff\xd9",
    }, {"scanStart": cursor, "cutOffset": cut, "originalEoiOffset": len(complete) - 2}


def worker(case):
    from PIL import Image, ImageFile

    ImageFile.LOAD_TRUNCATED_IMAGES = False
    Image.MAX_IMAGE_PIXELS = DIMENSION_LIMIT * DIMENSION_LIMIT
    data = controls()[0][case]
    assert len(data) <= INPUT_LIMIT
    try:
        with Image.open(io.BytesIO(data), formats=("JPEG",)) as image:
            if not (0 < image.width <= DIMENSION_LIMIT and
                    0 < image.height <= DIMENSION_LIMIT):
                raise ValueError("dimension ceiling")
            image.load()  # verify()/header recognition does not consume entropy.
            pixels = image.tobytes()
            result = {"outcome": "pixels-returned", "mode": image.mode,
                      "dimensions": list(image.size), "decodedBytes": len(pixels),
                      "pixelSha256": digest(pixels)}
    except (OSError, ValueError) as error:
        result = {"outcome": "decode-error", "errorType": type(error).__name__,
                  "message": str(error)[:240]}
    print(json.dumps(result, sort_keys=True))


def bounded_child(case):
    child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()),
                              "--worker", case], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
    captures = {"stdout": bytearray(), "stderr": bytearray()}
    overflow = threading.Event()

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
    try:
        child.wait(timeout=TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        child.kill()
        child.wait()
        raise RuntimeError("authored decoder child exceeded deadline") from None
    finally:
        for reader in readers:
            reader.join()
    if overflow.is_set() or child.returncode != 0:
        raise RuntimeError("authored child failed or exceeded capture ceiling")
    return json.loads(captures["stdout"]), {
        "exitCode": child.returncode,
        "stdoutBytes": len(captures["stdout"]),
        "stderrBytes": len(captures["stderr"]),
        "stderrSha256": digest(captures["stderr"]),
    }


def qualify():
    profile = json.loads((HERE / "profile.json").read_text(encoding="utf-8"))
    actual = identity()
    if actual != profile["runtime"]:
        raise RuntimeError("runtime identity differs from reviewed profile")
    assert profile["settings"] == {
        "loadTruncatedImages": False, "inputByteCeiling": INPUT_LIMIT,
        "dimensionCeiling": DIMENSION_LIMIT, "captureBytesPerStream": CAPTURE_LIMIT,
        "childDeadlineSeconds": TIMEOUT_SECONDS,
        "extentPolicy": "Pass the complete authored stored extent unchanged; accept exactly 32 appended zero bytes only as a measured control. Never trim extraction bytes.",
    }
    fixtures, offsets = controls()
    rows = []
    for case in CASES:
        data = fixtures[case]
        assert len(data) <= INPUT_LIMIT
        observed, process = bounded_child(case)
        expected = "decode-error" if case == "entropy-truncated" else "pixels-returned"
        assert observed["outcome"] == expected, (case, observed["outcome"])
        if expected == "pixels-returned":
            assert observed["mode"] == "RGB"
            assert observed["dimensions"] == [64, 64]
            assert observed["decodedBytes"] == 64 * 64 * 3
        rows.append({"case": case, "inputBytes": len(data), "inputSha256": digest(data),
                     "expectedObservedOutcome": expected, "observed": observed,
                     "process": process})
    assert rows[0]["observed"] == rows[2]["observed"]
    assert rows[0]["observed"]["pixelSha256"] != rows[3]["observed"]["pixelSha256"]
    return {"schemaVersion": 1, "ticket": 107, "profile": profile["id"],
            "runtime": actual, "controlOffsets": offsets, "controls": rows,
            "strictEntropyValidatorQualified": False,
            "reason": "Early EOI returns substituted pixels despite disabled truncation tolerance.",
            "cameraExecution": False, "productionCapability": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", choices=CASES, help=argparse.SUPPRESS)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if arguments.worker:
        worker(arguments.worker)
    else:
        report = json.dumps(qualify(), indent=2, sort_keys=True) + "\n"
        if arguments.output:
            arguments.output.write_text(report, encoding="utf-8", newline="\n")
        else:
            print(report, end="")
