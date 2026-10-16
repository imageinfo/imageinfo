"""Bounded authored-only reference serialization research; no media input API."""
import argparse
import hashlib
import itertools
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import time

ORIGINAL = b"2001:02:03 04:05:06\0"
CHANGED = b"2007:08:09 10:11:12\0"
REACHABLE = b"AUTHORED-0109\0"
TAIL = bytes(range(1, 25))
UUID = bytes.fromhex("85c0b687820f11e08111f4ce462b6a48")
MAX_BYTES = 65536
PINS = {
    "exiftool-13.59.json": "b55345e4b02d221ffa4cc7c444858337329b433d2d4877ce7a6dc03cce2827ed",
    "installed-perl.json": "6f4eb552f97a25039ba1c786765a61cd6a1419f5837e75e25da0191f9e91e691",
    "json-pp.json": "dcb168d2cb67fe46d6de6c540e23b0f97ac3fa7b7a6d04b8f0c0f28d6ecb1fb2",
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def box(kind, body):
    return struct.pack(">I4s", len(body) + 8, kind) + body


def tiff(order, entries, tail=b""):
    endian = "<" if order == "II" else ">"
    start = 8 + 2 + 12 * len(entries) + 4
    directory, values = b"", b""
    for tag, kind, count, value in entries:
        if len(value) <= 4:
            slot = value.ljust(4, b"\0")
        else:
            slot = struct.pack(endian + "I", start + len(values))
            values += value
            if len(values) % 2:
                values += b"\0"
        directory += struct.pack(endian + "HHI", tag, kind, count) + slot
    return (order.encode("ascii") + struct.pack(endian + "HIH", 42, 8, len(entries))
            + directory + b"\0" * 4 + values + tail)


def fixture(order, storage):
    date = tiff(order, [(0x9003, 2, len(ORIGINAL), ORIGINAL)])
    entries = [(0, 1, 4, bytes((2, 3, 0, 0)))]
    if storage == "reachable":
        entries.append((18, 2, len(REACHABLE), REACHABLE))
    tail = {"absent": b"", "zero": b"\0" * 24,
            "nonzero": TAIL, "reachable": b""}[storage]
    companion = tiff(order, entries, tail)
    atoms = box(b"CNCV", b"CanonCR3_0109\0") + box(b"CMT2", date) + box(b"CMT4", companion)
    data = box(b"ftyp", b"crx \0\0\0\0crx ") + box(b"moov", box(b"uuid", UUID + atoms))
    if len(data) > MAX_BYTES:
        raise ValueError("Authored input exceeds bound")
    return data


def matrix():
    return [{"id": f"{order}-{storage}-{assignment}-{'pad' if pad else 'default'}",
             "order": order, "storage": storage, "assignment": assignment, "pad": pad}
            for order, storage, assignment, pad in itertools.product(
                ("II", "MM"), ("absent", "zero", "nonzero", "reachable"),
                ("same", "changed"), (False, True))]


def verify_tools(repository):
    closures = []
    for name, digest in PINS.items():
        manifest_path = repository / ".local/tools/manifests" / name
        if sha(manifest_path) != digest:
            raise ValueError("Pinned distribution manifest changed")
        definition = json.loads(manifest_path.read_text(encoding="utf-8"))
        root = Path(definition["root"]).resolve()
        for item in definition["files"]:
            path = (root / item["path"]).resolve()
            if (not path.is_relative_to(root) or sha(path) != item["sha256"]
                    or path.stat().st_size != int(item["byteLength"])):
                raise ValueError("Pinned distribution component changed")
        closures.append({"manifestPath": str(manifest_path), "sha256": digest,
                         "root": str(root), "files": definition["files"]})
    return closures


def artifact(root, path):
    return {"path": path.relative_to(root).as_posix(), "sha256": sha(path),
            "size": path.stat().st_size, "mtimeNs": path.stat().st_mtime_ns}


def execute(root, cell, perl, reference, env):
    source = root / (cell["id"] + ".input.cr3")
    destination = root / (cell["id"] + ".output.cr3")
    source.write_bytes(fixture(cell["order"], cell["storage"]))
    before = artifact(root, source)
    date = ORIGINAL if cell["assignment"] == "same" else CHANGED
    argv = [str(perl), str(reference), "-config", "", "-ExifIFD:DateTimeOriginal=" + date[:-1].decode("ascii")]
    if cell["pad"]:
        argv += ["-api", "QuickTimePad=1"]
    argv += ["-o", str(destination), str(source)]
    started = time.monotonic_ns()
    launch_error = None
    try:
        process = subprocess.run(argv, env=env, cwd=root, capture_output=True, timeout=120, check=False)
        stdout, stderr = process.stdout, process.stderr
        exit_code, timed_out = process.returncode, False
    except subprocess.TimeoutExpired as error:
        stdout, stderr = error.stdout or b"", error.stderr or b""
        exit_code, timed_out = None, True
    except OSError as error:
        stdout, stderr = b"", str(error).encode("utf-8")
        exit_code, timed_out, launch_error = None, False, str(error)
    captures = []
    for label, data in (("stdout", stdout), ("stderr", stderr)):
        path = root / (cell["id"] + "." + label + ".bin")
        path.write_bytes(data)
        captures.append(artifact(root, path))
    after = artifact(root, source)
    result = {**cell, "input": before, "inputAfter": after,
              "output": artifact(root, destination) if destination.is_file() else None,
              "command": {"argv": argv, "exitCode": exit_code, "timedOut": timed_out,
                          "launchError": launch_error,
                          "elapsedNs": time.monotonic_ns() - started,
                          "stdout": captures[0], "stderr": captures[1]}}
    dump(root / (cell["id"] + ".result.json"), result)
    return result


def run(root, repository):
    closures = verify_tools(repository)
    root.mkdir(parents=False, exist_ok=False)
    source_dir = root / "sources"
    source_dir.mkdir()
    sources = []
    for path in sorted(Path(__file__).parent.glob("*.py")):
        destination = source_dir / path.name
        shutil.copyfile(path, destination)
        sources.append({"currentPath": str(path.resolve()), "archive": artifact(root, destination)})
    dump(root / "source-manifest.json", {"sources": sources})
    perl = Path(closures[1]["root"]) / "perl.exe"
    reference = Path(closures[0]["root"]) / "exiftool"
    env = {key: os.environ[key] for key in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP") if key in os.environ}
    env.update(PATH=str(perl.parent) + os.pathsep + str(Path(os.environ["SYSTEMROOT"]) / "System32"),
               PERL5LIB=str(Path(closures[2]["root"]) / "lib"), LC_ALL="C", LANG="C", TZ="UTC0")
    plan = matrix()
    dump(root / "scope.json", {"schemaVersion": 1, "authoredOnly": True,
         "productionMutationAllowed": False, "maxInputBytes": MAX_BYTES,
         "timeoutSeconds": 120, "matrix": plan, "toolClosures": closures,
         "driver": {"path": str(Path(__file__).resolve()), "sha256": sha(__file__)},
         "sources": sources,
         "environment": env})
    results = []
    try:
        for cell in plan:
            results.append(execute(root, cell, perl, reference, env))
    finally:
        dump(root / "manifest.json", {"schemaVersion": 1, "cells": results,
             "complete": len(results) == 32, "toolClosuresAfter": verify_tools(repository)})
        dump(root / "capture-manifest.json", {"files": [artifact(root, path)
             for path in sorted(root.rglob("*")) if path.is_file()]})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    run(args.root.resolve(), Path(__file__).resolve().parents[2])
