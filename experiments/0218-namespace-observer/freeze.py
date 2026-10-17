"""Exact #0218 source/worker/plan bindings; this file grants no authority.

The owning parent supplies a separate, explicit reviewed decision. Its editable
JSON records that current caller's decision; hashes are ordinary identity checks,
not authentication, custody, build provenance or independently imported authority.
Sources must already contain the repository's Git LF text bytes. Their hashes
describe exact working bytes, with no newline normalization. The parent freezes
only after publication and confirms those bytes against the published Git blobs.
Executable and plan identities likewise describe their exact unmodified bytes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import subprocess


SCHEMA = "namespace-observer-freeze-v1"
PLAN_SCHEMA = "namespace-observer-plan-v1"
REVIEW_SCHEMA = "namespace-observer-review-v1"
EXPERIMENT = "experiments/0218-namespace-observer"
MAX_JSON_BYTES = 262144
MAX_SOURCE_BYTES = 4194304
MAX_WORKER_BYTES = 268435456
MAX_SOURCES = 256


class FreezeError(ValueError):
    """A required exact binding or explicit current review decision is absent."""


def _require(condition, message):
    if not condition:
        raise FreezeError(message)


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        _require(key not in value, "duplicate JSON member")
        value[key] = item
    return value


def _read(path, maximum):
    path = Path(path)
    _require(path.is_file() and not path.is_symlink(), "missing/nonregular binding file")
    with path.open("rb") as handle:
        data = handle.read(maximum + 1)
    _require(len(data) <= maximum, "binding file exceeds byte bound")
    return data


def _json(raw):
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(FreezeError("nonfinite JSON")))
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise FreezeError("invalid bounded UTF-8 JSON") from exc
    _require(type(value) is dict, "JSON object required")
    return value


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _source_bytes(path):
    raw = _read(path, MAX_SOURCE_BYTES)
    _require(b"\r" not in raw, "source contains non-Git-LF line endings")
    return raw


def _absolute(value):
    _require(type(value) is str and value and Path(value).is_absolute(), "absolute binding path required")
    return Path(value).resolve(strict=True)


def _relative(root, value):
    _require(type(value) is str and value and "\\" not in value, "invalid relative source path")
    name = PurePosixPath(value)
    _require(not name.is_absolute() and all(p not in (".", "..") for p in name.parts)
             and str(name) == value and ":" not in value, "source traversal/noncanonical path")
    path = root.joinpath(*name.parts)
    _require(not path.is_symlink() and path.resolve(strict=True).is_relative_to(root), "source escapes root")
    return path


def source_inventory(root):
    """Bind root/local-crate Rust source plus every observer Python component."""
    root = Path(root).resolve(strict=True)
    names = {p.relative_to(root).as_posix() for p in (root / "src").rglob("*.rs") if p.is_file()}
    names.update(p.relative_to(root).as_posix() for p in (root / "crates").rglob("*.rs") if p.is_file())
    names.update(p.relative_to(root).as_posix() for p in (root / "crates").rglob("Cargo.toml") if p.is_file())
    names.update(p.relative_to(root).as_posix() for p in (root / EXPERIMENT).glob("*.py") if p.is_file())
    names.update(("Cargo.toml", "Cargo.lock", ".gitattributes"))
    for name in ("build.rs", ".cargo/config", ".cargo/config.toml", "rust-toolchain", "rust-toolchain.toml"):
        if (root / name).is_file():
            names.add(name)
    _require(0 < len(names) <= MAX_SOURCES, "source inventory count bound")
    required = {"src/storage/namespace_diagnostic.rs", "src/storage/windows.rs", "src/storage/runtime.rs",
                "crates/imageinfo-windows-storage/Cargo.toml", "crates/imageinfo-windows-storage/src/lib.rs",
                "crates/imageinfo-windows-storage/src/native.rs", "crates/imageinfo-windows-storage/src/windows.rs",
                EXPERIMENT + "/freeze.py", EXPERIMENT + "/protocol.py", EXPERIMENT + "/controller.py",
                EXPERIMENT + "/run.py", EXPERIMENT + "/audit.py", EXPERIMENT + "/fixtures.py",
                EXPERIMENT + "/probe.py"}
    _require(required <= names, "incomplete diagnostic source inventory")
    return sorted(names)


def _binding(path, maximum, *, name=None, source=False):
    raw = _source_bytes(path) if source else _read(path, maximum)
    return {"path": str(path) if name is None else name, "bytes": len(raw), "sha256": _sha(raw)}


def _git(root, args):
    try:
        result = subprocess.run(["git", "--no-optional-locks", *args], cwd=root,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise FreezeError("read-only Git identity query failed") from exc
    _require(result.returncode == 0 and len(result.stdout) <= MAX_JSON_BYTES,
             "read-only Git identity query failed or exceeded bound")
    return result.stdout


def _published_sources(root, names, expected_commit=None):
    """Compare raw working bytes with HEAD's exact blobs, without Git filters."""
    commit = _git(root, ["rev-parse", "--verify", "HEAD"]).strip().decode("ascii")
    _require(len(commit) in (40, 64) and all(c in "0123456789abcdef" for c in commit), "invalid Git commit identity")
    if expected_commit is not None:
        _require(commit == expected_commit, "Git HEAD differs from frozen source commit")
    raw = _git(root, ["ls-tree", "-rz", "--full-tree", commit, "--", *names])
    blobs = {}
    try:
        for line in raw.split(b"\0"):
            if not line:
                continue
            metadata, name = line.split(b"\t", 1)
            mode, kind, oid = metadata.split(b" ")
            name = name.decode("utf-8")
            _require(name not in blobs and mode in (b"100644", b"100755") and kind == b"blob",
                     "nonregular or duplicate Git source entry")
            blobs[name] = oid.decode("ascii")
    except (ValueError, UnicodeError) as exc:
        raise FreezeError("malformed Git source inventory") from exc
    _require(set(blobs) == set(names), "source is absent from current committed Git tree")
    for name in names:
        data = _source_bytes(_relative(root, name))
        payload = b"blob " + str(len(data)).encode("ascii") + b"\0" + data
        oid = blobs[name]
        _require(len(oid) in (40, 64), "unsupported Git object identity")
        actual = (hashlib.sha1(payload) if len(oid) == 40 else hashlib.sha256(payload)).hexdigest()
        _require(actual == oid, "working source differs from committed Git blob: " + name)
    return commit


def _check_binding(entry, path, maximum, *, source=False):
    _require(type(entry) is dict and set(entry) == {"path", "bytes", "sha256"}, "invalid binding schema")
    _require(type(entry["bytes"]) is int and 0 <= entry["bytes"] <= maximum, "invalid binding size")
    digest = entry["sha256"]
    _require(type(digest) is str and len(digest) == 64 and all(c in "0123456789abcdef" for c in digest),
             "invalid binding digest")
    actual = _binding(path, maximum, source=source)
    _require(actual["bytes"] == entry["bytes"] and actual["sha256"] == digest, "binding bytes changed: " + str(path))


def _validate_plan(plan, executable):
    _require(plan.get("schema") == PLAN_SCHEMA, "unsupported plan schema")
    _require(_absolute(plan.get("executable")) == executable, "plan executable differs from freeze")
    argv = plan.get("argv")
    _require(type(argv) is list and 1 <= len(argv) <= 32 and all(type(x) is str and x and
             len(x) <= 32768 and "\x00" not in x for x in argv), "invalid exact argv")
    _require(_absolute(argv[0]) == executable, "argv executable differs from freeze")
    _require(plan.get("cases") == ["normal", "candidate-collision"], "exact two native controls required")
    bounds = plan.get("bounds")
    keys = {"deadline_seconds", "stdout_bytes", "stderr_bytes", "line_bytes", "events", "command_bytes", "commands"}
    _require(type(bounds) is dict and set(bounds) == keys, "invalid exact bounds schema")
    deadline = bounds["deadline_seconds"]
    _require(type(deadline) in (int, float) and math.isfinite(deadline) and 0 < deadline <= 120, "deadline bound")
    for key, maximum in (("stdout_bytes", 4194304), ("stderr_bytes", 4194304), ("line_bytes", 32768),
                         ("events", 128), ("command_bytes", 1024), ("commands", 128)):
        _require(type(bounds[key]) is int and 0 < bounds[key] <= maximum, "invalid " + key + " bound")
    return argv


def build_manifest(root, executable, plan_path):
    """Build identity data only. Never creates or approves a review decision."""
    root = Path(root).resolve(strict=True)
    executable = Path(executable).resolve(strict=True)
    plan_path = Path(plan_path).resolve(strict=True)
    plan = _json(_read(plan_path, MAX_JSON_BYTES))
    _validate_plan(plan, executable)
    names = source_inventory(root)
    commit = _published_sources(root, names)
    return {"schema": SCHEMA, "root": str(root), "git_commit": commit, "source_encoding": "git-lf-v1",
            "worker": _binding(executable, MAX_WORKER_BYTES),
            "plan": _binding(plan_path, MAX_JSON_BYTES),
            "sources": [_binding(_relative(root, name), MAX_SOURCE_BYTES, name=name, source=True)
                        for name in names]}


def verify_manifest(manifest, root=None):
    """Re-read exact current inputs; returns the plan and executable identity."""
    _require(type(manifest) is dict and set(manifest) == {"schema", "root", "git_commit", "source_encoding", "worker", "plan", "sources"},
             "invalid manifest schema")
    _require(manifest["schema"] == SCHEMA and manifest["source_encoding"] == "git-lf-v1", "unsupported manifest")
    declared_root = _absolute(manifest["root"])
    if root is not None:
        _require(Path(root).resolve(strict=True) == declared_root, "different source root")
    sources = manifest["sources"]
    _require(type(sources) is list and 0 < len(sources) <= MAX_SOURCES, "source count bound")
    names = [entry.get("path") if type(entry) is dict else None for entry in sources]
    _require(names == source_inventory(declared_root), "source inventory omitted, duplicated or changed")
    _published_sources(declared_root, names, manifest["git_commit"])
    for entry in sources:
        _check_binding(entry, _relative(declared_root, entry["path"]), MAX_SOURCE_BYTES, source=True)
    _require(type(manifest["worker"]) is dict and type(manifest["plan"]) is dict, "missing worker/plan binding")
    executable = _absolute(manifest["worker"].get("path"))
    plan_path = _absolute(manifest["plan"].get("path"))
    _check_binding(manifest["worker"], executable, MAX_WORKER_BYTES)
    _check_binding(manifest["plan"], plan_path, MAX_JSON_BYTES)
    plan = _json(_read(plan_path, MAX_JSON_BYTES))
    argv = _validate_plan(plan, executable)
    return {"plan": plan, "freeze": manifest, "argv": argv, "executable": str(executable)}


def manifest_digest(manifest):
    """Canonical object digest for callers; review binds actual saved file bytes."""
    return _sha(json.dumps(manifest, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8"))


def verify_reviewed(plan_path, freeze_path, review_path):
    """Check a decision supplied by the current owning parent, never infer one.

    Passing a copied or attacker-authored decision here is not an authorization
    mechanism. The caller must already possess the explicit current parent review.
    Recheck immediately before child launch; this is not a continuing file guard.
    """
    freeze_raw = _read(freeze_path, MAX_JSON_BYTES)
    result = verify_manifest(_json(freeze_raw))
    _require(Path(plan_path).resolve(strict=True) == _absolute(result["freeze"]["plan"]["path"]), "different selected plan")
    review = _json(_read(review_path, MAX_JSON_BYTES))
    expected = {"schema", "decision", "scope", "reviewer", "plan_sha256", "freeze_sha256"}
    _require(set(review) == expected and review["schema"] == REVIEW_SCHEMA, "invalid explicit review schema")
    _require(review["decision"] == "approved" and review["scope"] == "two-native-controls-only", "no exact native decision")
    _require(type(review["reviewer"]) is str and 0 < len(review["reviewer"]) <= 128, "missing explicit reviewer")
    _require(review["freeze_sha256"] == _sha(freeze_raw) and
             review["plan_sha256"] == result["freeze"]["plan"]["sha256"], "review binds different exact inputs")
    result.update(plan_sha256=review["plan_sha256"], freeze_sha256=review["freeze_sha256"],
                  worker_sha256=result["freeze"]["worker"]["sha256"], review=review)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    build = sub.add_parser("build", help="write identity manifest only; no decision is created")
    for name in ("root", "executable", "plan", "output"):
        build.add_argument("--" + name, required=True)
    verify = sub.add_parser("verify", help="verify exact inputs and caller-supplied decision")
    for name in ("plan", "freeze", "review"):
        verify.add_argument("--" + name, required=True)
    args = parser.parse_args()
    if args.action == "build":
        manifest = build_manifest(args.root, args.executable, args.plan)
        raw = (json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
        _require(len(raw) <= MAX_JSON_BYTES, "manifest exceeds byte bound")
        with Path(args.output).open("xb") as handle:
            handle.write(raw)
        print("identity manifest written; no execution decision created")
    else:
        verify_reviewed(args.plan, args.freeze, args.review)
        print("current input bindings and caller-supplied decision match")


if __name__ == "__main__":
    main()
