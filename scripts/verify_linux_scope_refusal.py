"""Bounded #0177 refusal checks only; never invoke a research worker or VM."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import tempfile


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def snapshot(root):
    result = {}
    for path in sorted(root.iterdir()):
        stat = path.lstat()
        require(path.is_file() and not path.is_symlink(), "unexpected artifact")
        result[path.name] = (stat.st_dev, stat.st_ino, stat.st_mode,
                             stat.st_uid, stat.st_gid, stat.st_nlink,
                             stat.st_size, stat.st_mtime_ns,
                             hashlib.sha256(path.read_bytes()).hexdigest())
    return result


def run(args):
    require(platform.system() == "Linux", "run this check in Linux")
    binary = args.binary.resolve(strict=True)
    digest = hashlib.sha256(binary.read_bytes()).hexdigest()
    require(digest == args.expected_sha256, "binary provenance mismatch")
    parents = [args.native_parent.resolve(strict=True),
               args.mounted_parent.resolve(strict=True)]
    require(parents[0].stat().st_dev != parents[1].stat().st_dev,
            "native and mounted locations must be distinct filesystems")
    filesystems = []
    for parent in parents:
        query = subprocess.run(["findmnt", "-n", "-T", str(parent), "-o", "FSTYPE"],
                               capture_output=True, text=True, timeout=20, check=True)
        filesystems.append(query.stdout.strip())
    require(filesystems == ["ext4", "9p"],
            "this bounded check requires WSL-native ext4 and Windows-mounted 9p")
    cases = []
    for label, parent in zip(("wsl-native", "windows-mounted"), parents):
        # The harness creates fixtures; the tested commands must change none.
        root = Path(tempfile.mkdtemp(prefix="177-refusal-", dir=parent))
        existing = root / "foreign"
        existing.mkdir(mode=0o700)
        (existing / "output.bin").write_bytes(b"authored foreign output retained\n")
        (existing / "intent.record").write_bytes(b"authored invalid record retained\n")
        before = snapshot(existing)
        for mode in ("admit", "finalize", "prune"):
            for state, operand in (("absent", root / "must-remain-absent"),
                                   ("foreign", existing)):
                proc = subprocess.run([str(binary), mode, str(operand)],
                                      capture_output=True, text=True, timeout=20)
                require(proc.returncode == 0, "research refusal command failed")
                value = json.loads(proc.stdout)
                require(value.get("outcome") == "refused-before-mutation"
                        and value.get("authorizedActions") == []
                        and value.get("committed") is False
                        and value.get("productionPublicationAllowed") is False,
                        "unexpected capability or refusal result")
                require(not (root / "must-remain-absent").exists(),
                        "absent operand was created")
                require(snapshot(existing) == before, "foreign artifacts changed")
                require(sorted(p.name for p in root.iterdir()) == ["foreign"],
                        "transaction artifacts created")
                cases.append({"location": label, "mode": mode, "state": state,
                              "refusedBeforeMutation": True})
    report = {"caseCount": len(cases), "cases": cases,
              "binarySha256": digest, "kernel": platform.release(),
              "filesystems": filesystems,
              "newGuardProbes": 0, "workerRuns": 0, "vmOperations": 0,
              "positiveLinuxProfileQualified": False,
              "limits": "Frozen research action dispatch only; no production backend or guard qualification."}
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"caseCount": len(cases), "passed": True}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--native-parent", type=Path, required=True)
    parser.add_argument("--mounted-parent", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    run(parser.parse_args())
