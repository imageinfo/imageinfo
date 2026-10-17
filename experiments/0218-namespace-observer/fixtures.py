"""Fresh, retained authored fixtures for the two reviewed #0218 controls.

No import-time effects, overwrite, cleanup, media access or native probe. The
caller supplies a new root beneath this checkout's ignored .local directory.
Checks reject observed aliases; they do not promise adversarial path exclusion.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat


SCHEMA = "imageinfo-0218-fixture-v1"
MARKER = b"imageinfo-0218-disposable-authored-only-v1\n"
SOURCE_BYTES = 16 * 1024 * 1024
CANDIDATE_BYTES = 4 * 1024 * 1024
SOURCE_BYTE = 0x53
CANDIDATE_BYTE = 0x18
FOREIGN = b"imageinfo-0218 foreign candidate collision v1\n"
CASES = frozenset(("normal", "candidate-collision"))
_IGNORED = Path(__file__).absolute().parents[2] / ".local"


def _identity(info):
    return {"device": info.st_dev, "inode": info.st_ino}


def _plain(path: Path, *, directory: bool):
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise ValueError("symlink/reparse fixture path refused")
    if not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)):
        raise ValueError("unexpected fixture object type")
    return info


def _checked_root(root, *, exists):
    path = Path(root)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("explicit absolute nontraversing fixture root required")
    path = Path(os.path.abspath(path))
    try:
        relative = path.relative_to(_IGNORED)
    except ValueError as error:
        raise ValueError("fixture root must be beneath checkout .local") from error
    if not relative.parts:
        raise ValueError("fresh child root required")
    # Check each existing ancestor without resolve(), which would follow aliases.
    ancestors = list(path.parents)
    for ancestor in reversed(ancestors):
        _plain(ancestor, directory=True)
    if exists:
        _plain(path, directory=True)
    elif os.path.lexists(path):
        raise FileExistsError(path)
    return path


def _write_new(path, data):
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def _json_new(path, value):
    _write_new(path, (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8"))


def _repeated_hash(byte, count):
    digest = hashlib.sha256()
    block = bytes((byte,)) * 65536
    while count:
        piece = block[:min(count, len(block))]
        digest.update(piece)
        count -= len(piece)
    return digest.hexdigest()


def prepare_fixture(root, case: str, *, unit: str = "unit") -> dict:
    """Create one exact fresh fixture; partial failures remain for inspection."""
    if case not in CASES or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", unit):
        raise ValueError("undeclared case or invalid unit")
    path = _checked_root(root, exists=False)
    path.mkdir()
    _write_new(path / "fixture218.marker", MARKER)
    source = path / "source.bin"
    digest = hashlib.sha256()
    block = bytes((SOURCE_BYTE,)) * 65536
    with source.open("xb") as stream:
        remaining = SOURCE_BYTES
        while remaining:
            piece = block[:min(remaining, len(block))]
            stream.write(piece)
            digest.update(piece)
            remaining -= len(piece)
        stream.flush()
        os.fsync(stream.fileno())
    manifest = {
        "schema": SCHEMA, "case": case, "root": str(path), "unit": unit,
        "transactionDir": "unit",
        "rootIdentity": _identity(_plain(path, directory=True)),
        "source": str(source), "sourceIdentity": _identity(_plain(source, directory=False)),
        "sourceBytes": SOURCE_BYTES, "sourceSha256": digest.hexdigest(),
        "sourceByte": SOURCE_BYTE, "candidateBytes": CANDIDATE_BYTES,
        "candidateByte": CANDIDATE_BYTE,
        "candidateSha256": _repeated_hash(CANDIDATE_BYTE, CANDIDATE_BYTES),
        "candidate": str(path / "unit" / "candidate.bin"),
        "output": str(path / "unit" / "output.bin"),
        "unitInitiallyAbsent": True, "outputExpectedAbsent": True,
        "authoredOnly": True, "cleanupAuthorized": False,
    }
    _json_new(path / "fixture.private.json", manifest)
    return manifest


def inject_candidate_collision(fixture: dict, event: dict) -> dict:
    """Create the declared foreign candidate once at the reviewed pre-call pause.

    The caller must first validate the event using the protocol state machine.
    This local guard also checks the exact expected stage and retained fixture.
    The file and collision record survive every subsequent failure.
    """
    if fixture.get("schema") != SCHEMA or fixture.get("case") != "candidate-collision":
        raise ValueError("collision requires its predeclared fixture")
    from protocol import validate_event
    validate_event(event)
    if (event.get("kind") != "before_operation" or event.get("stage") != "create-Candidate"
            or event.get("seq") != 9 or event.get("result") is not None
            or event.get("unit") != fixture.get("unit")):
        raise ValueError("collision permitted only immediately before candidate creation")
    root = _checked_root(fixture["root"], exists=True)
    if _identity(_plain(root, directory=True)) != fixture["rootIdentity"]:
        raise ValueError("fixture root identity changed")
    marker = root / "fixture218.marker"
    _plain(marker, directory=False)
    if marker.stat().st_size != len(MARKER) or marker.read_bytes() != MARKER:
        raise ValueError("fixture marker changed")
    manifest_path = root / "fixture.private.json"
    _plain(manifest_path, directory=False)
    if manifest_path.stat().st_size > 8192 or json.loads(manifest_path.read_bytes()) != fixture:
        raise ValueError("fixture declaration changed")
    unit = fixture["unit"]
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", unit):
        raise ValueError("invalid fixture unit")
    if fixture.get("transactionDir") != "unit":
        raise ValueError("unexpected transaction directory")
    unit_path = root / "unit"
    unit_info = _plain(unit_path, directory=True)
    candidate = unit_path / "candidate.bin"
    if str(candidate) != fixture["candidate"] or os.path.lexists(root / "collision.private.json"):
        raise ValueError("collision path changed or already attempted")
    _write_new(candidate, FOREIGN)
    record = {
        "schema": "imageinfo-0218-collision-v1", "case": fixture["case"],
        "root": str(root), "unitIdentity": _identity(unit_info),
        "candidate": str(candidate), "bytes": len(FOREIGN),
        "sha256": hashlib.sha256(FOREIGN).hexdigest(),
        "identity": _identity(_plain(candidate, directory=False)),
        "event": event, "preserveForeign": True,
    }
    _json_new(root / "collision.private.json", record)
    return record
