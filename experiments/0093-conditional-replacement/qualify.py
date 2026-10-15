"""Finite Windows marker actors and independent refusal-preservation observations."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import queue
import stat
import subprocess
import tempfile
import threading

REPO = Path(__file__).resolve().parents[2]
OLD = b"OLD093\n"
NEW = b"NEW093\n"
FOREIGN = b"BAD093\n"
PROTECTED = b"INPUT093\n"


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def save(path, value):
    with Path(path).open("xb") as stream:
        stream.write((json.dumps(value, indent=2) + "\n").encode("utf-8"))


def sha(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            value.update(block)
    return value.hexdigest()


def snapshot(root, captures, label):
    """Read-only bounded namespace/bytes/security observation, not source authority."""
    paths = [root]
    if root.is_dir():
        for parent, directories, files in os.walk(root, followlinks=False):
            paths += [Path(parent) / name for name in sorted(directories + files)]
            require(len(paths) <= 32, "fixture namespace bound exceeded")
            require(len(Path(parent).relative_to(root).parts) <= 2, "fixture depth bound exceeded")
    records = {}
    for path in paths:
        key = "." if path == root else path.relative_to(root).as_posix()
        if not path.exists():
            records[key] = {"exists": False}
            continue
        s = path.lstat()
        require(not stat.S_ISLNK(s.st_mode), "unexpected fixture symlink")
        item = {"exists": True, "identity": [s.st_dev, s.st_ino],
                "kind": "directory" if path.is_dir() else "file",
                "length": s.st_size, "mtimeNs": s.st_mtime_ns,
                "birthtimeNs": s.st_birthtime_ns, "links": s.st_nlink,
                "attributes": s.st_file_attributes}
        if path.is_file():
            require(s.st_size <= 65536, "fixture byte bound exceeded")
            item["sha256"] = sha(path)
        records[key] = item
    existing = [str(p) for p in paths if p.exists()]
    shell = str(Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe")
    script = """$ErrorActionPreference='Stop';
Import-Module (Join-Path $PSHOME 'Modules/Microsoft.PowerShell.Security/Microsoft.PowerShell.Security.psd1');
Import-Module (Join-Path $PSHOME 'Modules/Microsoft.PowerShell.Management/Microsoft.PowerShell.Management.psd1');
$paths = ConvertFrom-Json $env:IMAGEINFO_0093_PATHS;
$out = @();
foreach ($p in $paths) {
  $acl = Get-Acl -LiteralPath $p;
  $sddl = $acl.GetSecurityDescriptorSddlForm([System.Security.AccessControl.AccessControlSections]'Owner,Access');
  $streams = @();
  if (-not (Get-Item -LiteralPath $p).PSIsContainer) {
    $streams = @(Get-Item -LiteralPath $p -Stream * | ForEach-Object { @{name=$_.Stream; length=$_.Length} });
  }
  $out += @{path=$p; ownerDacl=$sddl; streams=$streams};
}
ConvertTo-Json -InputObject @($out) -Depth 8 -Compress;
"""
    result = subprocess.run([shell, "-NoProfile", "-NonInteractive", "-Command", script],
                            env=dict(os.environ, IMAGEINFO_0093_PATHS=json.dumps(existing)),
                            capture_output=True, timeout=20,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    for channel, data in (("stdout", result.stdout), ("stderr", result.stderr)):
        with (captures / f"observer-{label}.{channel}.private").open("xb") as stream:
            stream.write(data[:65536])
    require(result.returncode == 0 and len(result.stdout) <= 65536,
            "read-only security/stream observer failed or exceeded bound: "
            + result.stderr[:1024].decode(errors="replace"))
    details = json.loads(result.stdout)
    for item in details:
        path = Path(item["path"])
        key = "." if path == root else path.relative_to(root).as_posix()
        records[key]["ownerDacl"] = item["ownerDacl"]
        records[key]["streams"] = sorted(item["streams"], key=lambda x: x["name"])
    return records


def perform(action, root, retained):
    target = root / "target.bin"
    candidate = root / "candidate.bin"
    try:
        if action == "target-swap":
            target.rename(root / "retained-target.bin")
            with target.open("xb") as stream:
                stream.write(FOREIGN)
        elif action == "candidate-swap":
            candidate.rename(root / "retained-candidate.bin")
            with candidate.open("xb") as stream:
                stream.write(FOREIGN)
        elif action == "target-missing":
            target.rename(root / "retained-target.bin")
        elif action == "target-directory":
            target.rename(root / "retained-target.bin")
            target.mkdir()
            (target / "foreign-marker.bin").write_bytes(FOREIGN)
        elif action in ("target-write", "candidate-write"):
            path = target if action == "target-write" else candidate
            with path.open("r+b") as stream:
                stream.write(FOREIGN)
        elif action == "input-write":
            with (root / "input.marker").open("r+b") as stream:
                stream.write(FOREIGN)
        elif action == "input-rename":
            (root / "input.marker").rename(root / "displaced-input.marker")
        elif action == "target-time":
            s = target.stat()
            os.utime(target, ns=(s.st_atime_ns, s.st_mtime_ns + 1_000_000_000))
        elif action == "target-readonly":
            os.chmod(target, stat.S_IREAD)
        elif action == "target-link":
            os.link(target, root / "target-alias.bin")
        elif action == "target-stream":
            with Path(str(target) + ":extra").open("xb") as stream:
                stream.write(b"ADS093\n")
        elif action == "preopened-writer":
            retained.append(target.open("r+b"))
        elif action == "root-rename":
            root.rename(root.with_name(root.name + "-moved"))
        else:
            raise ValueError("unknown fixed actor")
        return {"action": action, "succeeded": True, "osError": None}
    except OSError as error:
        return {"action": action, "succeeded": False,
                "osError": getattr(error, "winerror", None), "errno": error.errno,
                "errorClass": type(error).__name__}


def execute(binary, scratch, case_id, mode, gate=None, action=None):
    root = scratch / case_id
    captures = scratch / (case_id + "-capture")
    captures.mkdir()
    argv = [str(binary), str(root), mode]
    save(captures / "argv.private.json", argv)
    process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
    messages = queue.Queue()
    stderr = bytearray()

    def read_stdout():
        total = 0
        while True:
            line = process.stdout.readline(8193)
            if not line:
                break
            total += len(line)
            if len(line) > 8192 or total > 65536:
                process.kill()
                messages.put(ValueError("worker event bound exceeded"))
                break
            messages.put(line)
        messages.put(None)

    def read_stderr():
        while True:
            data = process.stderr.read(4096)
            if not data:
                break
            if len(stderr) + len(data) > 65536:
                process.kill()
                break
            stderr.extend(data)

    readers = [threading.Thread(target=f, daemon=True) for f in (read_stdout, read_stderr)]
    for reader in readers:
        reader.start()
    timer = threading.Timer(120, lambda: process.kill() if process.poll() is None else None)
    timer.start()
    events, retained, actor, before, after, result = [], [], None, None, None, None
    try:
        while True:
            line = messages.get(timeout=30)
            if line is None:
                break
            if isinstance(line, Exception):
                raise line
            require(len(events) < 8, "worker event count exceeded")
            event = json.loads(line)
            events.append(event)
            if event["event"] in ("ready", "validated"):
                if event["event"] == gate:
                    actor = perform(action, root, retained)
                # This snapshot follows the actor, so preservation means keeping
                # that actual state on refusal, never restoring a stale original.
                before = snapshot(root, captures, f"{event['event']}-{len(events)}")
                process.stdin.write(b"continue\n")
                process.stdin.flush()
            elif event["event"] == "result":
                result = event
                after = snapshot(root, captures, "result")
                process.stdin.write(b"exit\n")
                process.stdin.flush()
            else:
                raise ValueError("unknown worker event")
        code = process.wait(timeout=10)
        for reader in readers:
            reader.join(timeout=2)
        require(code == 0 and result is not None and not stderr, "worker failed unexpectedly")
        require(result["productionReplacementAllowed"] is False and result["committed"] is False
                and result["enabledProfiles"] == 0, "false conditional commitment/profile")
        attempted = result["renameAttempted"]
        succeeded = result["renameSucceeded"]
        require(before.get("input.marker") == after.get("input.marker")
                and (root / "input.marker").read_bytes() == PROTECTED,
                "protected input identity/content/name/security/properties changed")
        require(before.get("unrelated.marker") == after.get("unrelated.marker")
                and before.get("unrelated.marker") is not None,
                "unrelated marker entry changed")
        target_preserved = before.get("target.bin") == after.get("target.bin")
        namespace_preserved = before == after
        if not succeeded:
            require(target_preserved and namespace_preserved,
                    "actual pre-effect refusal changed target bytes/name/security/properties")
        if mode in ("target-guard", "source-guard", "both-guard"):
            require(not succeeded, "guarded standard-library profile unexpectedly replaced target")
        if mode == "unguarded-control" and action is None:
            require(attempted and succeeded and (root / "target.bin").read_bytes() == NEW
                    and not (root / "candidate.bin").exists(), "positive replacement control failed")
        if action in ("target-swap", "target-missing", "target-directory", "candidate-swap") and gate == "ready":
            require(actor["succeeded"] and not attempted and target_preserved,
                    "pre-effect foreign/collision check failed")
        if action in ("target-write", "candidate-write") and gate == "ready":
            require(actor["succeeded"] and not attempted and result["refusalCode"] == "MARKER_BYTES",
                    "pre-effect actual content check failed")
        if action in ("input-write", "input-rename"):
            require(actor["succeeded"] is False, "protected original actor bypassed retained guard")
        if mode == "weak-target-control" and action == "target-swap":
            require(actor["succeeded"] and succeeded and (root / "target.bin").read_bytes() == NEW
                    and (root / "retained-target.bin").read_bytes() == OLD,
                    "weak target race control did not exercise the expected replacement")
        private = {"id": case_id, "mode": mode, "gate": gate, "actor": actor,
                   "events": events, "before": before, "after": after, "exitCode": code}
        save(captures / "observations.private.json", private)
        return {"id": case_id, "mode": mode, "gate": gate, "actor": actor,
                "renameAttempted": attempted, "renameSucceeded": succeeded,
                "osError": result.get("osError"), "refusalCode": result.get("refusalCode"),
                "targetPreservedAcrossWorkerResult": target_preserved,
                "namespacePreservedAcrossWorkerResult": namespace_preserved,
                "protectedInputPreserved": True, "unrelatedEntryPreserved": True,
                "productionReplacementAllowed": False, "committed": False}
    finally:
        timer.cancel()
        if process.poll() is None:
            process.kill()
        process.wait(timeout=10)
        save(captures / "events.private.json", events)
        with (captures / "stderr.private").open("xb") as stream:
            stream.write(stderr)
        for stream in retained:
            stream.close()
        for stream in (process.stdin, process.stdout, process.stderr):
            stream.close()


def run(binary, parent):
    binary = Path(binary).resolve()
    parent = Path(parent).resolve()
    require(parent.is_relative_to(REPO / ".local"), "fresh private fixtures must stay under repository .local")
    require(os.name == "nt", "native Windows qualification required; no simulated success")
    parent.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="replacement-093-", dir=parent))
    identities = {"binarySha256": sha(binary), "qualifierSha256": sha(__file__),
                  "python": platform.python_version()}
    save(scratch / "identities-before.private.json", identities)
    cases = []
    for mode in ("unguarded-control", "target-guard", "source-guard", "both-guard", "weak-target-control"):
        cases.append(execute(binary, scratch, "baseline-" + mode, mode))
    for action in ("target-swap", "target-missing", "target-directory", "candidate-swap",
                   "target-time", "target-readonly", "target-link", "preopened-writer",
                   "target-write", "candidate-write", "input-write", "input-rename"):
        cases.append(execute(binary, scratch, "ready-" + action, "both-guard", "ready", action))
    for action in ("target-swap", "candidate-swap", "target-write", "candidate-write", "root-rename",
                   "target-time", "target-readonly", "target-link", "target-stream"):
        cases.append(execute(binary, scratch, "validated-" + action, "both-guard", "validated", action))
    cases.append(execute(binary, scratch, "weak-target-race", "weak-target-control", "validated", "target-swap"))
    cases.append(execute(binary, scratch, "weak-candidate-race", "weak-target-control", "validated", "candidate-swap"))
    cases.append(execute(binary, scratch, "weak-late-readonly", "weak-target-control", "validated", "target-readonly"))
    summary = {"schemaVersion": 1, "observedOn": "2026-10-15", "platform": platform.platform(),
               "caseCount": len(cases), "cases": cases,
               "conditionalReplacementQualified": False, "productionReplacementAllowed": False,
               "committed": False, "enabledProfiles": 0,
               "scope": "Disposable authored marker calls only; unsupported pinned std replacement profile; no production/source/RAW operation",
               "missing": ["full ancestor binding", "worker security/DACL and stream checkpoints",
                           "conditional expected-target-ID operation", "durability", "original retention/recovery"]}
    save(scratch / "summary.private.json", summary)
    require(sha(binary) == identities["binarySha256"] and sha(__file__) == identities["qualifierSha256"],
            "worker or qualifier changed during actual qualification")
    save(scratch / "identities.private.json", dict(identities, caseCount=len(cases)))
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True)
    parser.add_argument("--parent", required=True)
    parser.add_argument("--output", required=True, help="fresh sanitized derived summary")
    args = parser.parse_args()
    require(not Path(args.output).exists(), "derived summary destination must be fresh")
    save(args.output, run(args.binary, args.parent))
