"""Assemble a local, unsigned source rehearsal; never create tags or releases.

Reads objects from one frozen Git commit, not the mutable working tree. The
external manifest deliberately lives outside that tree to avoid self-reference.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import subprocess
import tarfile
import tomllib


VERSION = "0.2.0-alpha.1"
MATRIX = {"windows-2025", "ubuntu-24.04", "macos-15"}
ROOT = Path(__file__).resolve().parents[1]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout


def validate_ci(record, commit):
    if (record.get("headSha") != commit or record.get("status") != "completed"
            or record.get("conclusion") != "success"
            or record.get("workflowName") != "Rust foundation"):
        raise ValueError("CI must be successful completed Rust foundation at the exact commit")
    jobs = record.get("jobs", [])
    for name in MATRIX:
        matches = [job for job in jobs if job.get("name") == name]
        if len(matches) != 1 or matches[0].get("conclusion") != "success":
            raise ValueError(f"Missing unique successful exact-source CI matrix job: {name}")
    return {key: record[key] for key in
            ("headSha", "status", "conclusion", "workflowName", "url", "databaseId", "jobs")}


def inspect_archive(data, expected, object_format="sha1"):
    """Reject links, path traversal, Git metadata and archive substitutions."""
    files = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as archive:
        for member in archive:
            path = PurePosixPath(member.name)
            if (path.is_absolute() or ".." in path.parts or "\\" in member.name or ":" in member.name
                    or any(part in {".git", ".local", "target", "__pycache__"}
                           for part in path.parts)):
                raise ValueError(f"Forbidden archive path: {member.name}")
            if member.isdir():
                continue
            if not member.isfile() or member.name in files:
                raise ValueError(f"Non-file/duplicate archive entry: {member.name}")
            if path.suffix.lower() in {".exe", ".dll", ".pdb", ".msi", ".cr3", ".cr2", ".nef"}:
                raise ValueError(f"Binary/media packaging needs separate review: {member.name}")
            payload = archive.extractfile(member).read()
            blob_id = hashlib.new(object_format, b"blob " + str(len(payload)).encode()
                                  + b"\0" + payload).hexdigest()
            if member.name not in expected or blob_id != expected[member.name]:
                raise ValueError(f"Archive content differs from Git object: {member.name}")
            files[member.name] = payload
    if set(files) != set(expected):
        raise ValueError("Archive file set differs from the full frozen Git tree")
    return files


def inventory(files):
    manifest = tomllib.loads(files["Cargo.toml"].decode())
    if manifest["package"]["version"] != VERSION or manifest["package"]["publish"] is not False:
        raise ValueError("Candidate must have adopted version and publish=false")
    if manifest["package"]["license"] != "MIT":
        raise ValueError("Candidate project license differs from the adopted MIT basis")
    locked = tomllib.loads(files["Cargo.lock"].decode())["package"]
    admission = json.loads(files["docs/foundation/dependencies.json"])
    external = {(p["name"], p["version"]): p for p in locked if "source" in p}
    reviewed = {(p["name"], p["version"]): p for p in admission["packages"]}
    if set(external) != set(reviewed):
        raise ValueError("Root locked external graph differs from reviewed dependency inventory")
    for identity, package in external.items():
        record = reviewed[identity]
        if package.get("checksum") != record["packageSha256"]:
            raise ValueError(f"Dependency checksum mismatch: {identity}")
        for notice in record["publishedNotices"]:
            if digest(files[notice["path"]]) != notice["sha256"]:
                raise ValueError(f"Dependency notice mismatch: {notice['path']}")
    required = ["Cargo.toml", "Cargo.lock", "rust-toolchain.toml", "LICENSE",
                "THIRD_PARTY_NOTICES.md", "docs/foundation/dependencies.json"]
    notices = sorted(path for path in files if path.startswith("licenses/"))
    return {"identityFiles": {path: digest(files[path]) for path in required + notices},
            "rootLockedPackages": locked, "reviewedExternalPackages": admission["packages"],
            "researchManifests": sorted(path for path in files
                                        if path.startswith("experiments/") and path.endswith("Cargo.toml")),
            "dependencySourcesVendored": False}


def assemble(commit_ref, output, ci_path=None):
    commit = git("rev-parse", "--verify", f"{commit_ref}^{{commit}}").decode().strip()
    tree = git("rev-parse", f"{commit}^{{tree}}").decode().strip()
    object_format = git("rev-parse", "--show-object-format").decode().strip()
    expected = {}
    for entry in git("ls-tree", "-rz", "--full-tree", commit).split(b"\0"):
        if not entry:
            continue
        meta, raw_path = entry.split(b"\t", 1)
        mode, kind, object_id = meta.decode().split()
        if kind != "blob" or mode not in {"100644", "100755"}:
            raise ValueError("Only ordinary tracked files are allowed in this source candidate")
        expected[raw_path.decode("utf-8")] = object_id
    data = git("archive", "--format=tar", commit)
    files = inspect_archive(data, expected, object_format)
    dependencies = inventory(files)
    ci = validate_ci(json.loads(ci_path.read_text(encoding="utf-8")), commit) if ci_path else None
    output.mkdir(parents=True, exist_ok=False)
    archive_name = f"imageinfo-{VERSION}-source-rehearsal.tar"
    (output / archive_name).write_bytes(data)
    source = output / "source"
    source.mkdir()
    for name, payload in files.items():
        destination = source.joinpath(*PurePosixPath(name).parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
    record = {"schemaVersion": 1, "kind": "local-source-reader-candidate",
              "version": VERSION, "sourceCommit": commit, "sourceTree": tree,
              "archive": {"path": archive_name, "bytes": len(data), "sha256": digest(data)},
              "files": [{"path": path, "sha256": digest(files[path])} for path in sorted(expected)],
              "inventory": dependencies, "exactSourceCi": ci,
              "automatedAssembly": "passed", "sourceFileComparison": "passed",
              "unpackedBuild": "not-run-by-assembler", "agentReview": "record-separately",
              "candidateApproval": "pending-terry", "publicationPerformed": False,
              "signed": False, "reproducibleBinaries": "not-claimed",
              "excluded": ["Git metadata", "untracked/ignored working files", "Cargo dependency source"],
              "limits": ["Full tracked research source is included but not production capability",
                         "License/hash checks do not replace assembled-artifact provenance review",
                         "GitHub-generated compression bytes may differ; compare extracted content",
                         "No independent human verifier or backup operator is claimed"]}
    (output / "candidate.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"commit": commit, "archiveSha256": digest(data),
                      "fileCount": len(files), "exactSourceCiAttached": ci is not None,
                      "output": str(output.resolve())}))
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--output", required=True, type=Path,
                        help="New private local directory; never commit generated evidence")
    parser.add_argument("--ci-json", type=Path,
                        help="gh run view --json headSha,status,conclusion,workflowName,url,databaseId,jobs")
    args = parser.parse_args()
    assemble(args.commit, args.output, args.ci_json)


if __name__ == "__main__":
    main()
