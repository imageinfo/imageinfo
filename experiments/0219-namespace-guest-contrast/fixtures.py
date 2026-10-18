"""Retained authored preparation and bounded pathname observations for #0219.

Only the reviewed owning collector calls these entrypoints. Importing this module
has no effects. Checks reject observed aliases, not adversarial substitutions;
neither observations nor a saved manifest grant custody or repair authority.
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import re
import stat


SCHEMA = "imageinfo-0219-fixture-v1"
SNAPSHOT_SCHEMA = "imageinfo-0219-fixture-snapshot-v1"
MARKER = b"imageinfo-0219-disposable-authored-only-v1\n"
MARKER_NAME = "fixture219.marker"
SOURCE_BYTES = 16 * 1024 * 1024
CANDIDATE_BYTES = 4 * 1024 * 1024
SOURCE_BYTE = 0x53
CANDIDATE_BYTE = 0x18
MAX_ENTRIES = 32
CASES = frozenset(("persistent-write-error", "no-error"))
PHASES = frozenset(("original", "prepared", "source_reopened_hold", "before_candidate_hold", "candidate_hold",
                    "cleared_hold", "exited", "final"))
NAMES = {"source": "source.bin", "candidate": "unit/candidate.bin",
         "output": "unit/output.bin", "prepared": "unit/prepared.record",
         "intent": "unit/intent.record", "observation": "unit/observation.record",
         "receipt": "unit/receipt.record"}


def _error(error):
    return {"type": type(error).__name__, "errno": getattr(error, "errno", None),
            "winerror": getattr(error, "winerror", None)}


def _identity(info):
    return {"device": info.st_dev, "inode": info.st_ino}


def _raw_stat(info):
    return {"device": info.st_dev, "inode": info.st_ino, "mode": info.st_mode,
            "size": info.st_size, "mtime_ns": info.st_mtime_ns,
            "ctime_ns": info.st_ctime_ns,
            "birthtime_ns": getattr(info, "st_birthtime_ns", None)}


def _plain(path, *, directory):
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise ValueError("symlink/reparse fixture path refused")
    if not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)):
        raise ValueError("unexpected fixture object type")
    return info


def _root(root):
    path = Path(root)
    if (not path.is_absolute() or ".." in path.parts or len(path.parts) > 64
            or len(str(path)) > 4096 or path == Path(path.anchor)):
        raise ValueError("explicit bounded absolute child fixture root required")
    return Path(os.path.abspath(path))


def _ancestors(path):
    for ancestor in reversed(path.parents):
        _plain(ancestor, directory=True)


def _write_new(path, data):
    with path.open("xb") as stream:
        stream.write(data)


def _repeated_hash(byte, count):
    digest = hashlib.sha256()
    block = bytes((byte,)) * 65536
    while count:
        piece = block[:min(count, len(block))]
        digest.update(piece)
        count -= len(piece)
    return digest.hexdigest()


def _directory(path):
    result = {"path": str(path), "status": "error", "stat": None,
              "entries": [], "error": None, "reason": None}
    try:
        _ancestors(path)
        result["stat"] = _raw_stat(_plain(path, directory=True))
        with os.scandir(path) as entries:
            for entry in entries:
                if len(result["entries"]) >= MAX_ENTRIES:
                    result.update(status="refused", reason="directory_entry_bound")
                    return result
                item = {"name": entry.name, "stat": None, "error": None}
                try:
                    item["stat"] = _raw_stat(entry.stat(follow_symlinks=False))
                except OSError as error:
                    item["error"] = _error(error)
                result["entries"].append(item)
        result["entries"].sort(key=lambda item: item["name"])
        result["status"] = "ok"
    except OSError as error:
        result["error"] = _error(error)
    except ValueError as error:
        result.update(status="refused", reason=str(error))
    return result


def _lookup(path):
    result = {"path": str(path), "status": "error", "stat": None, "error": None,
              "reason": None}
    try:
        _ancestors(path)
        result["stat"] = _raw_stat(_plain(path, directory=False))
        result["status"] = "ok"
    except OSError as error:
        result["error"] = _error(error)
    except ValueError as error:
        result.update(status="refused", reason=str(error))
    return result


def _seed_observation(path):
    """Bounded ordinary Python read; no SDK/native bridge or persistence call."""
    _ancestors(path)
    initial = _plain(path, directory=False)
    if initial.st_size != SOURCE_BYTES:
        raise ValueError("seed source extent refused")
    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        digest = hashlib.sha256()
        count = 0
        while count <= SOURCE_BYTES:
            data = stream.read(min(65536, SOURCE_BYTES + 1 - count))
            if not data:
                break
            digest.update(data)
            count += len(data)
        after = os.fstat(stream.fileno())
    final = _plain(path, directory=False)
    if (count != SOURCE_BYTES or digest.hexdigest() != _repeated_hash(SOURCE_BYTE, SOURCE_BYTES)
            or _raw_stat(initial) != _raw_stat(final)
            or _raw_stat(before) != _raw_stat(after)
            or _identity(initial) != _identity(before)):
        raise ValueError("seed source bytes or identity changed")
    return {"path": str(path), "pathBefore": _raw_stat(initial),
            "handleBefore": _raw_stat(before), "handleAfter": _raw_stat(after),
            "pathAfter": _raw_stat(final), "bytesRead": count,
            "sha256": digest.hexdigest(), "identity": _identity(before)}


def _inventory(root):
    paths = {name: _lookup(root / relative) for name, relative in NAMES.items()}
    paths["old"] = _lookup(root.parent / "source.bin")
    paths["preparedSource"] = paths["source"]
    return {"volume": _directory(root.parent), "root": _directory(root),
            "unit": _directory(root / "unit"), "paths": paths}


def prepare_fixture(root, case: str, *, unit: str = "unit",
                    preparation_mode: str = "existing_offline_seed") -> dict:
    """Move the verified original volume-root source into a fresh case.

    Actual guest execution requires existing_offline_seed. authored_model_seed
    is an explicit changed preparation for portable authored controls only.
    No source, case, or volume flush is added. All partial effects are retained.
    The 0x53 payload deliberately differs from historical #0174's 0x31 payload.
    """
    if case not in CASES or not isinstance(unit, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", unit):
        raise ValueError("undeclared case or invalid unit")
    if not (type(SOURCE_BYTES) is int and 1 <= SOURCE_BYTES <= 16 * 1024 * 1024
            and type(CANDIDATE_BYTES) is int and 1 <= CANDIDATE_BYTES <= 4 * 1024 * 1024):
        raise ValueError("fixture byte bounds refused")
    if preparation_mode not in ("existing_offline_seed", "authored_model_seed"):
        raise ValueError("undeclared fixture preparation mode")
    path = _root(root)
    _ancestors(path)
    if os.path.lexists(path):
        raise FileExistsError(path)
    old = path.parent / "source.bin"
    if preparation_mode == "authored_model_seed":
        with old.open("xb") as stream:
            remaining = SOURCE_BYTES
            block = bytes((SOURCE_BYTE,)) * 65536
            while remaining:
                piece = block[:min(remaining, len(block))]
                stream.write(piece)
                remaining -= len(piece)
    before_move = _seed_observation(old)
    original = _inventory(path)
    path.mkdir()
    _write_new(path / MARKER_NAME, MARKER)
    source = path / "source.bin"
    # The destination is in our newly created plain case and must be absent.
    # These observed checks do not promise adversarial namespace exclusion.
    _plain(path, directory=True)
    if os.path.lexists(source):
        raise FileExistsError(source)
    os.rename(old, source)
    after_move = _seed_observation(source)
    if before_move["identity"] != after_move["identity"]:
        raise ValueError("source move changed object identity")
    prepared_inventory = _inventory(path)
    manifest = {"schema": SCHEMA, "case": case, "root": str(path), "unit": unit,
                "transactionDir": "unit", "rootIdentity": _identity(_plain(path, directory=True)),
                "sourceIdentity": _identity(_plain(source, directory=False)),
                "sourceBytes": SOURCE_BYTES, "sourceByte": SOURCE_BYTE,
                "sourceSha256": _repeated_hash(SOURCE_BYTE, SOURCE_BYTES),
                "candidateBytes": CANDIDATE_BYTES, "candidateByte": CANDIDATE_BYTE,
                "candidateSha256": _repeated_hash(CANDIDATE_BYTE, CANDIDATE_BYTES),
                "unitInitiallyAbsent": True, "outputExpectedAbsent": True,
                "authoredOnly": True, "cleanupAuthorized": False,
                "originalInventory": original, "preparedInventory": prepared_inventory,
                "preparationMode": preparation_mode, "sourceVolumeRoot": str(path.parent),
                "explicitPreparationFlush": False, "durablePreparationAcknowledged": False,
                "historicalPayloadByte": 0x31, "historicalPayloadChanged": True,
                "requiredWorkerMarker": {"path": str(path / MARKER_NAME),
                                         "bytes": len(MARKER),
                                         "sha256": hashlib.sha256(MARKER).hexdigest()},
                "historicalMetadataPreparationChanged": True,
                "manifestPersistedOnTestVolume": False,
                "sourceMove": {"before": before_move, "after": after_move,
                               "identityBefore": before_move["identity"],
                               "identityAfter": after_move["identity"], "sameObject": True}}
    manifest.update({name: str(path / relative) for name, relative in NAMES.items()})
    manifest["old"] = str(old)
    manifest["preparedSource"] = manifest["source"]
    # The collector retains this return value outside the tested volume. No
    # fixture-manifest file or additional marker is written into the case.
    return manifest


def _reader():
    path = Path(__file__).absolute().parent.parent / "0218-namespace-observer" / "probe.py"
    spec = importlib.util.spec_from_file_location("imageinfo_0218_fixture_probe", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.read_snapshot


def snapshot_fixture(fixture: dict, phase: str, *, read_snapshot=None) -> dict:
    """Observe each declared name, retaining missing/error outcomes explicitly.

    The injected/default reader is #0218's read-only same-FD bridge observer.
    No cleanup, write-open probe, process launch or fault action occurs here.
    """
    if (fixture.get("schema") != SCHEMA or fixture.get("case") not in CASES
            or phase not in PHASES or fixture.get("transactionDir") != "unit"):
        raise ValueError("undeclared fixture snapshot")
    if (not isinstance(fixture.get("unit"), str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", fixture["unit"])
            or type(fixture.get("sourceBytes")) is not int
            or not 1 <= fixture["sourceBytes"] <= 16 * 1024 * 1024
            or type(fixture.get("candidateBytes")) is not int
            or not 1 <= fixture["candidateBytes"] <= 4 * 1024 * 1024):
        raise ValueError("fixture snapshot bounds refused")
    root = _root(fixture["root"])
    for name, relative in NAMES.items():
        if fixture.get(name) != str(root / relative):
            raise ValueError("fixture pathname changed")
    if (fixture.get("old") != str(root.parent / "source.bin")
            or fixture.get("sourceVolumeRoot") != str(root.parent)
            or fixture.get("preparedSource") != fixture["source"]):
        raise ValueError("old source pathname changed")
    reader = _reader() if read_snapshot is None else read_snapshot
    result = {"schema": SNAPSHOT_SCHEMA, "case": fixture["case"], "unit": fixture["unit"],
              "phase": phase, "root": str(root), "directories": {}, "paths": {},
              "cleanupAuthorized": False}
    for name, path in (("volume", root.parent), ("root", root), ("unit", root / "unit")):
        result["directories"][name] = _directory(path)
    observed_paths = {name: root / relative for name, relative in NAMES.items()}
    observed_paths["old"] = root.parent / "source.bin"
    for name, path in observed_paths.items():
        bound = fixture["sourceBytes"] if name in ("source", "old") else max(fixture["candidateBytes"], 65536)
        try:
            _ancestors(path)
            result["paths"][name] = reader(path, max_bytes=bound)
        except OSError as error:
            result["paths"][name] = {"path": str(path), "status": "error", "error": _error(error)}
        except ValueError as error:
            result["paths"][name] = {"path": str(path), "status": "refused", "reason": str(error), "error": None}
    result["paths"]["preparedSource"] = result["paths"]["source"]
    return result
