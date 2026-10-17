"""Bounded, nonwriting observations of an explicitly selected authored source.

The write-open requests ordinary write access without create/truncate flags and
never writes, renames or changes properties. Successful access and a sharing
refusal are lifetime observations, not continuous property or identity guards.
Only the reviewed owning parent invokes these functions on native fixtures.
"""

from __future__ import annotations

import hashlib
import errno
import os
from pathlib import Path
import stat


DEFAULT_SOURCE_BYTES = 65_536
MAX_SOURCE_BYTES = 16 * 1024 * 1024


def _error(error: OSError) -> dict:
    return {
        "type": type(error).__name__,
        "errno": error.errno,
        "winerror": getattr(error, "winerror", None),
    }


def _stat(value: os.stat_result) -> dict:
    return {
        "device": value.st_dev,
        "inode": value.st_ino,
        "mode": value.st_mode,
        "size": value.st_size,
        "mtime_ns": value.st_mtime_ns,
        "ctime_ns": value.st_ctime_ns,
    }


def _bound(max_bytes: int) -> None:
    if type(max_bytes) is not int or not 1 <= max_bytes <= MAX_SOURCE_BYTES:
        raise ValueError("source byte bound must be in 1..16777216")


def read_snapshot(path: str | Path, *, max_bytes: int = DEFAULT_SOURCE_BYTES) -> dict:
    """Hash at most max_bytes+1 source bytes and retain ordinary stat observations.

    Reject links, nonregular files and over-bound inputs. The observations can
    expose a race but do not exclude substitution or authenticate ownership.
    """
    _bound(max_bytes)
    selected = Path(path)
    result = {
        "path": str(selected),
        "max_bytes": max_bytes,
        "status": "error",
        "error": None,
        "reason": None,
        "path_before": None,
        "handle_before": None,
        "handle_after": None,
        "path_after": None,
        "bytes_read": 0,
        "sha256": None,
        "observations_match": False,
    }
    try:
        initial = selected.lstat()
        result["path_before"] = _stat(initial)
        if not stat.S_ISREG(initial.st_mode) or selected.is_symlink():
            result.update(status="refused", reason="not_regular_nonlink_source")
            return result
        if initial.st_size > max_bytes:
            result.update(status="refused", reason="source_exceeds_bound")
            return result
        with selected.open("rb") as source:
            held = os.fstat(source.fileno())
            result["handle_before"] = _stat(held)
            if not stat.S_ISREG(held.st_mode) or held.st_size > max_bytes:
                result.update(status="refused", reason="opened_source_outside_bound")
                return result
            content = source.read(max_bytes + 1)
            result["bytes_read"] = len(content)
            result["handle_after"] = _stat(os.fstat(source.fileno()))
        result["path_after"] = _stat(selected.lstat())
        if len(content) > max_bytes:
            result.update(status="refused", reason="source_grew_beyond_bound")
            return result
        result["sha256"] = hashlib.sha256(content).hexdigest()
        observations = [result[key] for key in (
            "path_before", "handle_before", "handle_after", "path_after"
        )]
        result["observations_match"] = all(item == observations[0] for item in observations)
        result["status"] = "ok"
    except OSError as error:
        result["error"] = _error(error)
    return result


def write_open_probe(
    path: str | Path, *, expected_access: bool, max_bytes: int = DEFAULT_SOURCE_BYTES
) -> dict:
    """Request nonwriting write access and preserve the actual error interface.

    Windows CRT may expose only EACCES, losing the native sharing error. That
    weaker access-denial observation is explicitly distinguished from winerror
    32. The independent audit must also verify baseline/pause/exit ordering.
    """
    _bound(max_bytes)
    if type(expected_access) is not bool:
        raise ValueError("expected_access must be boolean")
    selected = Path(path)
    before = read_snapshot(selected, max_bytes=max_bytes)
    result = {
        "path": str(selected),
        "expected_access": expected_access,
        "status": "not_attempted",
        "denial_observation": None,
        "error": None,
        "close_error": None,
        "opened_stat": None,
        "flags": os.O_WRONLY | getattr(os, "O_BINARY", 0),
        "before": before,
        "after": None,
        "source_unchanged": False,
        "expectation_met": False,
    }
    if before["status"] != "ok" or not before["observations_match"]:
        return result
    handle = None
    try:
        handle = os.open(selected, result["flags"])
        result["status"] = "opened"
        result["opened_stat"] = _stat(os.fstat(handle))
    except OSError as error:
        result["status"] = "open_error" if handle is None else "handle_stat_error"
        result["error"] = _error(error)
        if handle is None:
            if result["error"]["winerror"] == 32:
                result["denial_observation"] = "win32_sharing_violation"
            elif result["error"]["winerror"] is None and error.errno == errno.EACCES:
                result["denial_observation"] = "crt_eacces_without_native_error"
    finally:
        if handle is not None:
            try:
                os.close(handle)
            except OSError as error:
                result["close_error"] = _error(error)
    after = read_snapshot(selected, max_bytes=max_bytes)
    result["after"] = after
    result["source_unchanged"] = (
        after["status"] == "ok"
        and after["observations_match"]
        and before["sha256"] == after["sha256"]
        and before["path_before"] == after["path_before"]
    )
    access_matches = result["status"] == "opened" if expected_access else (
        result["status"] == "open_error" and result["denial_observation"] is not None
    )
    result["expectation_met"] = bool(
        access_matches and result["close_error"] is None and result["source_unchanged"]
        and (result["opened_stat"] is None or result["opened_stat"] == before["path_before"])
    )
    return result
