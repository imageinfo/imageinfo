"""Exact #0219 identities, without imported execution authority.

Host source is pinned to immutable Git blobs and exact LF working bytes. That
pin says nothing about a resident controller or guest: those independently
reported identities must match ``resident_expected`` and the loaded plan hash.
All hashes are byte comparisons, not authentication, custody or provenance.
Only the current owning parent's in-memory decision permits verify_current.
This module performs no native, guest, QMP, build or worker operation.
"""
from __future__ import annotations

from dataclasses import dataclass
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path, PureWindowsPath
import re
import sys
import types
import uuid

_path = Path(__file__).resolve().parents[1] / "0218-namespace-observer" / "freeze.py"
_spec = importlib.util.spec_from_file_location("namespace_218_freeze_for_219", _path)
previous = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(previous)
FreezeError = previous.FreezeError
_require = previous._require
_read = previous._read
_json = previous._json
_sha = previous._sha
_relative = previous._relative
_absolute = previous._absolute
_source_bytes = previous._source_bytes
_binding = previous._binding
_check_binding = previous._check_binding
_git = previous._git
MAX_JSON_BYTES = previous.MAX_JSON_BYTES
MAX_SOURCE_BYTES = previous.MAX_SOURCE_BYTES
MAX_WORKER_BYTES = previous.MAX_WORKER_BYTES
MAX_SOURCES = 512
EXPERIMENT = "experiments/0219-namespace-guest-contrast"
SCHEMA = "namespace-guest-contrast-freeze-v1"
PLAN_SCHEMA = "namespace-guest-contrast-plan-v1"
WORKER_TEST = "storage::namespace_guest_diagnostic::guest_namespace_diagnostic_worker"
FLAGS = ("committed", "production_profile_admitted", "raw_admitted", "authority_importable")
CASES = ("persistent-write-error", "no-error")
INPUTS = ("build_record", "runtime_inventory", "disk_configuration", "controller_source")
FAULT = {"event": "write_aio", "iotype": "write", "errno": 28, "once": False,
         "sector": None, "arm_stage": "create-Candidate", "arm_seq": 9}
MARKER = {"source_bytes": 16777216, "source_fill": 83,
          "candidate_bytes": 4194304, "candidate_fill": 24}
_HEX = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_UNIT = re.compile(r"[A-Za-z0-9_-]{1,64}\Z", re.ASCII)


def _digest(value):
    return type(value) is str and _HEX.fullmatch(value) is not None


def _text(value, maximum=32768):
    return type(value) is str and 0 < len(value) <= maximum and "\x00" not in value


def _guest_path(value):
    return _text(value) and PureWindowsPath(value).is_absolute() and ".." not in PureWindowsPath(value).parts


def _plain_json(value):
    """Require bounded finite JSON even for direct in-process API callers."""
    try:
        raw = json.dumps(value, allow_nan=False, ensure_ascii=True).encode("ascii")
    except (ValueError, TypeError, RecursionError) as exc:
        raise FreezeError("invalid finite JSON binding") from exc
    _require(len(raw) <= MAX_JSON_BYTES, "JSON binding exceeds byte bound")


def source_inventory(root):
    root = Path(root).resolve(strict=True)
    names = set(previous.source_inventory(root))
    names.update(p.relative_to(root).as_posix() for p in (root / EXPERIMENT).glob("*.py") if p.is_file())
    names.update(p.relative_to(root).as_posix() for p in (root / EXPERIMENT).glob("*.ps1") if p.is_file())
    names.update(p.relative_to(root).as_posix() for p in (root / EXPERIMENT).glob("*.sh") if p.is_file())
    required = {EXPERIMENT + "/" + name + ".py" for name in
                ("freeze", "protocol", "host_controller", "guest_collector", "fixtures", "audit")}
    required.add(EXPERIMENT + "/guest_bootstrap.ps1")
    required.add("src/storage/namespace_guest_diagnostic.rs")
    _require(required <= names and len(names) <= MAX_SOURCES, "incomplete contrast source inventory")
    return sorted(names)


def _published_sources(root, names, expected_commit=None):
    """Raw LF/Git-blob check; a later HEAD alone does not invalidate the pin."""
    commit = expected_commit
    if commit is None:
        commit = _git(root, ["rev-parse", "--verify", "HEAD"]).strip().decode("ascii")
    _require(type(commit) is str and len(commit) in (40, 64) and
             all(c in "0123456789abcdef" for c in commit), "invalid immutable Git commit")
    resolved = _git(root, ["rev-parse", "--verify", commit + "^{commit}"]).strip().decode("ascii")
    _require(resolved == commit, "missing immutable source commit")
    raw = _git(root, ["ls-tree", "-rz", "--full-tree", commit, "--", *names])
    blobs = {}
    try:
        for line in raw.split(b"\0"):
            if not line:
                continue
            metadata, encoded = line.split(b"\t", 1)
            mode, kind, oid = metadata.split(b" ")
            name = encoded.decode("utf-8")
            _require(name not in blobs and mode in (b"100644", b"100755") and kind == b"blob",
                     "nonregular or duplicate Git source")
            blobs[name] = oid.decode("ascii")
    except (ValueError, UnicodeError) as exc:
        raise FreezeError("malformed Git source entries") from exc
    _require(set(blobs) == set(names), "source absent from immutable Git tree")
    for name in names:
        raw = _source_bytes(_relative(root, name))
        payload = b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw
        oid = blobs[name]
        _require(len(oid) in (40, 64), "unsupported Git blob identity")
        actual = (hashlib.sha1(payload) if len(oid) == 40 else hashlib.sha256(payload)).hexdigest()
        _require(actual == oid, "working source differs from immutable Git blob: " + name)
    return commit


def _validate_resident_expected(value):
    _require(type(value) is dict and set(value) == {"controller", "guest"}, "resident expectations required")
    controllers, guest = value["controller"], value["guest"]
    _require(type(controllers) is dict and set(controllers) == set(CASES), "two resident controller expectations required")
    for controller in controllers.values():
        _require(type(controller) is dict and set(controller) == {"controller_epoch", "code_sha256", "python"},
                 "invalid resident controller expectation")
        epoch = controller["controller_epoch"]
        _require(type(epoch) is str and re.fullmatch(r"[0-9a-f]{32}", epoch) is not None and
                 _digest(controller["code_sha256"]), "invalid resident controller epoch/code")
        _require(type(controller["python"]) is dict and bool(controller["python"]), "missing controller interpreter")
    _require(controllers[CASES[0]]["controller_epoch"] != controllers[CASES[1]]["controller_epoch"], "reused controller epoch")
    _require(type(guest) is dict and set(guest) == {"implementation", "version", "platform", "stat_profile",
                                                "code_sha256", "files"}, "invalid resident guest expectation")
    _require(all(_text(guest[key]) for key in ("implementation", "version", "platform")) and
             _text(guest["stat_profile"]) and
             _digest(guest["code_sha256"]), "missing guest interpreter/resident code")
    files = guest["files"]
    _require(type(files) is dict and 3 <= len(files) <= MAX_SOURCES and
             all(_guest_path(path) and _digest(digest) for path, digest in files.items()),
             "guest runtime/worker/collector file bindings required")
    _require(len({str(PureWindowsPath(path)).casefold() for path in files}) == len(files),
             "aliased guest runtime file binding")
    _plain_json(value)


def _validate_plan(plan, executable=None):
    _plain_json(plan)
    _require(type(plan) is dict and plan.get("schema") == PLAN_SCHEMA, "unsupported exact plan")
    argv = plan.get("argv")
    _require(plan.get("worker_test_name") == WORKER_TEST and type(argv) is list and len(argv) == 6 and
             all(_text(arg) for arg in argv) and _guest_path(argv[0]) and
             set(argv[1:]) == {"--exact", WORKER_TEST, "--ignored", "--nocapture", "--test-threads=1"},
             "exact separately identified guest diagnostic worker argv required")
    _require(all(plan.get(flag) is False for flag in FLAGS), "positive or missing admission flag")
    _require(plan.get("marker") == MARKER and plan.get("fault") == FAULT,
             "exact authored markers and historical persistent whole-volume fault required")
    # Equality alone would accept bools for the integer constants.
    _require(all(type(plan["marker"][key]) is int for key in MARKER) and
             type(plan["fault"]["errno"]) is int and type(plan["fault"]["arm_seq"]) is int and
             plan["fault"]["once"] is False, "invalid fault/marker value types")
    cases = plan.get("cases")
    _require(type(cases) is list and len(cases) == 2, "exact two serial cases required")
    for case, expected in zip(cases, CASES):
        _require(type(case) is dict and case.get("case") == expected and
                 _text(case.get("unit"), 64) and _UNIT.fullmatch(case["unit"]) is not None and
                 _guest_path(case.get("root")), "invalid ordered fresh case identity")
    _require(cases[0]["unit"] != cases[1]["unit"] and
             str(PureWindowsPath(cases[0]["root"])).casefold() !=
             str(PureWindowsPath(cases[1]["root"])).casefold(), "case identity/root reuse")
    bounds = plan.get("bounds")
    maxima = {"stdout_bytes": 4194304, "stderr_bytes": 4194304, "line_bytes": 32768,
              "events": 128, "command_bytes": 1024, "commands": 128}
    _require(type(bounds) is dict and set(bounds) == {"deadline_seconds", *maxima}, "invalid finite bounds")
    deadline = bounds["deadline_seconds"]
    _require(type(deadline) in (int, float) and math.isfinite(deadline) and 0 < deadline <= 120, "invalid deadline")
    _require(all(type(bounds[k]) is int and 0 < bounds[k] <= n for k, n in maxima.items()), "invalid capture/count bounds")
    files = plan.get("freeze_inputs")
    _require(type(files) is dict and set(files) == set(INPUTS), "missing exact build/runtime/config/source files")
    for path in files.values():
        _absolute(path)
    identities = plan.get("identities")
    _validate_identities(identities)
    for item in cases:
        _validate_identities(item.get("identities", identities))
    _validate_resident_expected(plan.get("resident_expected"))
    return plan


def _validate_identities(identities):
    _require(type(identities) is dict and set(identities) == {"guest", "disk", "volume"} and
             all(type(value) is dict and bool(value) for value in identities.values()), "missing guest/disk/volume identities")
    disk_keys = {"disk_path", "raw_node", "file_node", "filter_node", "device_id", "device_serial"}
    _require(set(identities["disk"]) == disk_keys and all(_text(v) for v in identities["disk"].values()),
             "missing exact disk/controller binding")
    _require(set(identities["volume"]) == {"volume_serial"} and _text(identities["volume"]["volume_serial"]),
             "missing exact volume binding")


def _validate_build(raw, commit, worker):
    build = _json(raw)
    _require(build.get("source_commit") == commit and build.get("worker_sha256") == worker["sha256"],
             "build record differs from exact source/worker")
    _require(_text(build.get("target")) and _text(build.get("compiler")) and
             type(build.get("argv")) is list and 0 < len(build["argv"]) <= 64 and
             all(_text(arg) for arg in build["argv"]), "missing exact build request/environment")


def build_manifest(root, executable, plan_path):
    """Read exact identity inputs only; do not approve, build or launch anything."""
    root = Path(root).resolve(strict=True)
    executable, plan_path = Path(executable).resolve(strict=True), Path(plan_path).resolve(strict=True)
    plan = _validate_plan(_json(_read(plan_path, MAX_JSON_BYTES)), executable)
    names = source_inventory(root)
    commit = _published_sources(root, names)
    worker = _binding(executable, MAX_WORKER_BYTES)
    _require(plan["resident_expected"]["guest"]["files"].get(plan["argv"][0]) == worker["sha256"],
             "selected guest argv executable differs from frozen worker")
    _validate_build(_read(plan["freeze_inputs"]["build_record"], MAX_JSON_BYTES), commit, worker)
    _validate_disk(plan)
    _validate_runtime(plan)
    result = {"schema": SCHEMA, "root": str(root), "git_commit": commit, "source_encoding": "git-lf-v1",
            "worker": worker, "plan": _binding(plan_path, MAX_JSON_BYTES),
            "inputs": {key: _binding(_absolute(path), MAX_JSON_BYTES)
                       for key, path in plan["freeze_inputs"].items()},
            "sources": [_binding(_relative(root, name), MAX_SOURCE_BYTES, name=name, source=True) for name in names]}
    _controller_source_binding(result)
    return result


def verify_manifest(manifest, root=None):
    _require(type(manifest) is dict and set(manifest) == {"schema", "root", "git_commit", "source_encoding",
                                                       "worker", "plan", "inputs", "sources"}, "invalid manifest schema")
    _require(manifest["schema"] == SCHEMA and manifest["source_encoding"] == "git-lf-v1", "unsupported source pin")
    declared = _absolute(manifest["root"])
    _require(root is None or Path(root).resolve(strict=True) == declared, "different source root")
    sources = manifest["sources"]
    _require(type(sources) is list and 0 < len(sources) <= MAX_SOURCES, "invalid source count")
    names = [entry.get("path") if type(entry) is dict else None for entry in sources]
    _require(names == source_inventory(declared), "omitted, duplicated or changed source inventory")
    _published_sources(declared, names, manifest["git_commit"])
    for entry in sources:
        _check_binding(entry, _relative(declared, entry["path"]), MAX_SOURCE_BYTES, source=True)
    _require(type(manifest["worker"]) is dict and type(manifest["plan"]) is dict, "missing worker/plan binding")
    worker, plan_path = _absolute(manifest["worker"].get("path")), _absolute(manifest["plan"].get("path"))
    _check_binding(manifest["worker"], worker, MAX_WORKER_BYTES)
    _check_binding(manifest["plan"], plan_path, MAX_JSON_BYTES)
    plan = _validate_plan(_json(_read(plan_path, MAX_JSON_BYTES)), worker)
    _require(plan["resident_expected"]["guest"]["files"].get(plan["argv"][0]) == manifest["worker"]["sha256"],
             "selected guest argv executable differs from frozen worker")
    _require(type(manifest["inputs"]) is dict and set(manifest["inputs"]) == set(INPUTS), "incomplete pinned inputs")
    for key in INPUTS:
        entry = manifest["inputs"][key]
        _require(type(entry) is dict and entry.get("path") == str(_absolute(plan["freeze_inputs"][key])), "different input path")
        _check_binding(entry, _absolute(entry["path"]), MAX_JSON_BYTES)
    _validate_build(_read(manifest["inputs"]["build_record"]["path"], MAX_JSON_BYTES), manifest["git_commit"], manifest["worker"])
    _validate_disk(plan)
    _validate_runtime(plan)
    _controller_source_binding(manifest)
    return {"plan": plan, "freeze": manifest, "executable": str(worker),
            "worker_sha256": manifest["worker"]["sha256"], "plan_sha256": manifest["plan"]["sha256"]}


@dataclass(frozen=True)
class ParentDecision:
    """Current trusted local caller choice; never decode from a saved record."""
    plan_sha256: str
    freeze_sha256: str
    reviewer: str
    scope: str = "two-serial-cells-only"


def verify_current(plan_path, freeze_path, *, parent_decision):
    _require(type(parent_decision) is ParentDecision, "explicit current in-memory parent decision required")
    raw = _read(freeze_path, MAX_JSON_BYTES)
    result = verify_manifest(_json(raw))
    _require(Path(plan_path).resolve(strict=True) == _absolute(result["freeze"]["plan"]["path"]), "different selected plan")
    _require(parent_decision.scope == "two-serial-cells-only" and _text(parent_decision.reviewer, 128) and
             _digest(parent_decision.plan_sha256) and _digest(parent_decision.freeze_sha256) and
             parent_decision.plan_sha256 == result["plan_sha256"] and parent_decision.freeze_sha256 == _sha(raw),
             "current decision binds different exact inputs")
    result["freeze_sha256"] = _sha(raw)
    return result


def _validate_disk(plan):
    value = _json(_read(plan["freeze_inputs"]["disk_configuration"], MAX_JSON_BYTES))
    _require(value.get("identities") == plan["identities"], "disk configuration differs from planned identities")
    selected = {item["case"]: item.get("identities", plan["identities"]) for item in plan["cases"]}
    if any("identities" in item for item in plan["cases"]):
        _require(value.get("cases") == selected, "disk configuration differs from selected per-case identities")


def _validate_runtime(plan):
    value = _json(_read(plan["freeze_inputs"]["runtime_inventory"], MAX_JSON_BYTES))
    expected = plan["resident_expected"]
    interpreters = {case: expected["controller"][case]["python"] for case in CASES}
    _require(value.get("guest") == expected["guest"] and value.get("controller_python") == interpreters,
             "runtime inventory differs from reviewed resident expectations")


def _controller_source_binding(manifest):
    source = next(item for item in manifest["sources"] if item["path"] == EXPERIMENT + "/host_controller.py")
    actual = manifest["inputs"]["controller_source"]
    _require(actual["sha256"] == source["sha256"] and actual["bytes"] == source["bytes"],
             "controller source input differs from immutable published controller")


def load_controller_source(path, expected_sha256):
    """Capture reviewed source bytes before parsing, then load those exact bytes.

    This is an explicit caller operation, never an import-time action. The
    module's functions still require the current owning parent's effects gate.
    Loading arbitrary bytes is not permission to execute their operations.
    """
    _require(_digest(expected_sha256), "invalid expected controller source digest")
    raw = _source_bytes(path)
    _require(_sha(raw) == expected_sha256, "controller source changed before parse")
    name = "namespace_219_captured_controller_" + uuid.uuid4().hex
    module = types.ModuleType(name)
    module.__file__ = str(Path(path).resolve(strict=True))
    module.__resident_source_sha256__ = _sha(raw)
    module.__resident_source_bytes_count__ = len(raw)
    sys.modules[name] = module
    try:
        exec(compile(raw, module.__file__, "exec"), module.__dict__)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


def verify_resident(manifest, observed, *, case):
    """Compare independent live observations; this does not capture them.

    Disk file equality cannot substitute for actual resident code, epoch or
    interpreter observations. Callers must retain their actual capture methods.
    Extra controller state fields are permitted and retained by the caller.
    """
    result = verify_manifest(manifest)
    _require(case in CASES, "unplanned resident case")
    _plain_json(observed)
    _require(type(observed) is dict and set(observed) == {"plan_sha256", "controller", "guest"} and
             observed["plan_sha256"] == result["plan_sha256"], "resident loaded plan differs")
    expected = result["plan"]["resident_expected"]
    controller = observed["controller"]
    _require(type(controller) is dict and all(controller.get(k) == v for k, v in expected["controller"][case].items()) and
             controller.get("plan_sha256") == result["plan_sha256"],
             "resident controller bytes/interpreter/epoch differ")
    source = manifest["inputs"]["controller_source"]
    _require(controller.get("source_sha256") == source["sha256"] and
             type(controller.get("source_bytes")) is int and controller["source_bytes"] == source["bytes"] and
             type(controller.get("pid")) is int and controller["pid"] > 0,
             "missing actual preparse resident controller source capture")
    selected = next(item for item in result["plan"]["cases"] if item["case"] == case)
    binding = controller.get("binding")
    identities = selected.get("identities", result["plan"]["identities"])
    expected_binding = {**identities["disk"], **identities["volume"],
                        "unit": selected["unit"], "case": case, "root": selected["root"]}
    _require(type(binding) is dict and all(binding.get(k) == v for k, v in expected_binding.items()),
             "resident controller differs from exact case/disk/volume binding")
    _require(observed["guest"] == expected["guest"], "resident guest runtime/code/file identities differ")
    return result


def manifest_digest(manifest):
    _plain_json(manifest)
    return _sha(json.dumps(manifest, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--executable", required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    value = build_manifest(args.root, args.executable, args.plan)
    raw = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")
    _require(len(raw) <= MAX_JSON_BYTES, "manifest exceeds byte bound")
    with Path(args.output).open("xb") as handle:
        handle.write(raw)
    print("identity manifest written; current parent execution decision remains separate")


if __name__ == "__main__":
    main()
