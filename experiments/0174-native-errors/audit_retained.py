"""Read-only NTFS artifact audit after the exact disposable guest is stopped.

Writes new bounded partition copies and reports beside the private fixture. It
never mounts, repairs, replays, prunes, or writes the retained original images.
"""
import argparse
import hashlib
import json
import os
import pathlib
import shutil
import subprocess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=pathlib.Path)
    parser.add_argument("--output-name", default="retained-audit.private")
    args = parser.parse_args()
    root = args.root.resolve()
    expected = pathlib.Path("/var/tmp/imageinfo-windows-eval-20261014/native-errors-0174-20261017")
    if root != expected:
        raise ValueError("Only the exact disposable #0174 fixture is supported")
    # QEMU removes its pidfile on a normal guest shutdown. Inspect live process
    # bindings as well, rather than treating a missing pidfile as stop evidence.
    for entry in pathlib.Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            command = (entry / "cmdline").read_bytes().split(b"\0")
        except OSError:
            continue
        if command and b"qemu-system-x86" in command[0] and any(str(root).encode() in part for part in command):
            raise ValueError("Guest must be stopped; active images are never audited")
    manifest = json.loads((root / "preflight.private.json").read_text())
    tools = root.parent / "native-errors-0048-tools/extracted"
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = str(tools / "usr/lib/x86_64-linux-gnu")
    if not args.output_name.endswith(".private") or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-." for c in args.output_name):
        raise ValueError("Audit output must be a fresh private child name")
    output = root / args.output_name
    output.mkdir(exist_ok=False)
    leaves = ["source.bin", "unit/candidate.bin", "unit/output.bin", "unit/prepared.record", "unit/intent.record", "unit/observation.record", "unit/receipt.record"]
    rows = []
    for cell in manifest["cells"]:
        raw = pathlib.Path(cell["disk"]).resolve()
        if raw.parent != root or raw.stat().st_size != 134217728:
            raise ValueError("Unexpected retained image")
        part = output / (cell["cell"] + ".ntfs")
        before = hashlib.sha256(raw.read_bytes()).hexdigest()
        with raw.open("rb") as src, part.open("xb") as dst:
            src.seek(1048576)
            shutil.copyfileobj(src, dst, 1048576)
        files = {}
        for leaf in leaves:
            result = subprocess.run([str(tools / "usr/bin/ntfscat"), str(part), "/case/" + leaf], env=env, capture_output=True, timeout=30)
            (output / (cell["cell"] + "-" + leaf.replace("/", "-") + "-read.private.log")).write_bytes(result.stderr)
            if result.returncode:
                files[leaf] = {"readable": False, "exitCode": result.returncode}
                continue
            data = result.stdout
            bound = 16777216 if leaf == "source.bin" else 4194304 if leaf.endswith(".bin") else 65536
            if len(data) > bound:
                raise ValueError("Retained artifact exceeds its admitted bound")
            files[leaf] = {"readable": True, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            info = subprocess.run([str(tools / "usr/bin/ntfsinfo"), "-F", "/case/" + leaf, str(part)], env=env, capture_output=True, timeout=30)
            (output / (cell["cell"] + "-" + leaf.replace("/", "-") + ".private.log")).write_bytes(info.stdout + info.stderr)
        if hashlib.sha256(raw.read_bytes()).hexdigest() != before:
            raise ValueError("Retained original image changed during read-only audit")
        source = files["source.bin"]
        preserved = source["readable"] and source["bytes"] == cell["sourceBytes"] and source["sha256"] == cell["sourceSha256"]
        original = subprocess.run([str(tools / "usr/bin/ntfscat"), str(part), "/source.bin"], env=env, capture_output=True, timeout=30)
        original_matches = original.returncode == 0 and len(original.stdout) == cell["sourceBytes"] and hashlib.sha256(original.stdout).hexdigest() == cell["sourceSha256"]
        listing = subprocess.run([str(tools / "usr/bin/ntfsls"), "-l", "-p", "/", str(part)], env=env, capture_output=True, timeout=30)
        (output / (cell["cell"] + "-root-listing.private.log")).write_bytes(listing.stdout + listing.stderr)
        rows.append({"cell": cell["cell"], "retainedImageSha256": before, "preparedSourceNameAndBytesPreserved": preserved,
                     "sourceBytesRetainedAtOriginalFixtureName": original_matches, "files": files})
    value = {"schema": "imageinfo-0174-independent-offline-artifact-audit-v1", "readOnlyOriginalImages": True, "rows": rows, "profileAdmitted": False}
    (output / "audit.private.json").write_text(json.dumps(value, indent=2))
    print(json.dumps({"auditedCells": len(rows), "allPreparedSourceNamesPreserved": all(row["preparedSourceNameAndBytesPreserved"] for row in rows), "report": str(output / "audit.private.json")}))


if __name__ == "__main__":
    main()
