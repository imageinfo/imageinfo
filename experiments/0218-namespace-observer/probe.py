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
import sys
import ctypes


DEFAULT_SOURCE_BYTES = 65_536
MAX_SOURCE_BYTES = 16 * 1024 * 1024
SAME_FIELDS = "same-fields-v1"
WINDOWS_3147 = "cpython-3.14.7-windows-path-creation-handle-change-v1"
STAT_NAMES = ("path_before", "handle_before", "handle_after", "path_after")
SHARED_FIELDS = ("device", "inode", "mode", "size", "mtime_ns", "birthtime_ns")
WINDOWS_BRIDGE = "win32-bhfi-same-read-fd-v1"
NO_BRIDGE = "unavailable-non-windows-v1"
BRIDGE_NAMES = ("identity_bridge_profile", "bridge_before", "bridge_after")


class _FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", ctypes.c_uint32), ("dwHighDateTime", ctypes.c_uint32)]


class _BY_HANDLE_FILE_INFORMATION(ctypes.Structure):
    # Windows DWORD and BOOL are exactly32 bits, including on64-bit Python.
    # https://learn.microsoft.com/windows/win32/api/fileapi/ns-fileapi-by_handle_file_information
    _fields_ = [
        ("dwFileAttributes", ctypes.c_uint32),
        ("ftCreationTime", _FILETIME),
        ("ftLastAccessTime", _FILETIME),
        ("ftLastWriteTime", _FILETIME),
        ("dwVolumeSerialNumber", ctypes.c_uint32),
        ("nFileSizeHigh", ctypes.c_uint32),
        ("nFileSizeLow", ctypes.c_uint32),
        ("nNumberOfLinks", ctypes.c_uint32),
        ("nFileIndexHigh", ctypes.c_uint32),
        ("nFileIndexLow", ctypes.c_uint32),
    ]


def _windows_api():
    # No DLL loading at import time. This boundary only observes the retained
    # existing read FD: it neither opens a pathname nor duplicates/closes it.
    import msvcrt
    library = ctypes.WinDLL("kernel32", use_last_error=True)
    information = library.GetFileInformationByHandle
    information.argtypes = [ctypes.c_void_p, ctypes.POINTER(_BY_HANDLE_FILE_INFORMATION)]
    information.restype = ctypes.c_int32
    return information, msvcrt.get_osfhandle


def _bridge_for_fd(fd: int) -> dict | None:
    if os.name != "nt":
        return None
    information, get_osfhandle = _windows_api()
    native_handle = get_osfhandle(fd)
    if native_handle == -1:
        raise OSError(errno.EBADF, "invalid retained read descriptor")
    observed = _BY_HANDLE_FILE_INFORMATION()
    # use_last_error keeps the calling thread's actual failure before any other
    # Win32 call. WinError preserves its native number in the snapshot error.
    if not information(ctypes.c_void_p(native_handle), ctypes.byref(observed)):
        code = ctypes.get_last_error()
        raise ctypes.WinError(code)
    return {
        "volume_serial_u32": int(observed.dwVolumeSerialNumber),
        "file_index_u64": (int(observed.nFileIndexHigh) << 32) | int(observed.nFileIndexLow),
    }


def _bridge_matches(result: dict) -> bool:
    profile = result["identity_bridge_profile"]
    before, after = result["bridge_before"], result["bridge_after"]
    if profile == NO_BRIDGE:
        return before is None and after is None and result["stat_profile"] != WINDOWS_3147
    if profile != WINDOWS_BRIDGE or before != after:
        return False
    for bridge, raw in ((before, result["handle_before"]), (after, result["handle_after"])):
        if type(bridge) is not dict or set(bridge) != {"volume_serial_u32", "file_index_u64"}:
            return False
        if not (
            type(bridge["volume_serial_u32"]) is int and 0 <= bridge["volume_serial_u32"] < 2**32
            and type(bridge["file_index_u64"]) is int and 0 <= bridge["file_index_u64"] < 2**64
            and bridge["file_index_u64"] == raw["inode"]
        ):
            return False
    return True


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
        "birthtime_ns": getattr(value, "st_birthtime_ns", None),
    }


def _stat_profile() -> str:
    # Exact inspected interpreter, not a general claim about Windows Python.
    return WINDOWS_3147 if (
        os.name == "nt" and sys.implementation.name == "cpython"
        and sys.version_info[:3] == (3, 14, 7)
    ) else SAME_FIELDS


def _observations_match(result: dict) -> bool:
    observations = [result[key] for key in STAT_NAMES]
    if any(item is None for item in observations):
        return False
    if not _bridge_matches(result):
        return False
    path_before, handle_before, handle_after, path_after = observations
    if result["stat_profile"] == SAME_FIELDS:
        return all(item == path_before for item in observations)
    if result["stat_profile"] != WINDOWS_3147:
        return False
    # CPython v3.14.7 Modules/posixmodule.c win32_xstat copies birthtime into
    # path-stat ctime (lines2152-2154), whereas Python/fileutils.c's fstat leaves
    # FILE_BASIC_INFO.ChangeTime in ctime (lines1038-1040,1195). Preserve both
    # raw fields and require complete stability within each API. Creation time
    # is compared across APIs through the explicit st_birthtime_ns field.
    # https://github.com/python/cpython/blob/v3.14.7/Modules/posixmodule.c#L2152
    # https://github.com/python/cpython/blob/v3.14.7/Python/fileutils.c#L1038
    return (
        path_before == path_after and handle_before == handle_after
        and all(type(item["birthtime_ns"]) is int for item in observations)
        and all(item["ctime_ns"] == item["birthtime_ns"] for item in (path_before, path_after))
        and all(
            all(item[field] == path_before[field] for field in SHARED_FIELDS)
            for item in observations
        )
    )


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
        "stat_profile": _stat_profile(),
        "identity_bridge_profile": WINDOWS_BRIDGE if os.name == "nt" else NO_BRIDGE,
        "bridge_before": None,
        "bridge_after": None,
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
            result["bridge_before"] = _bridge_for_fd(source.fileno())
            content = source.read(max_bytes + 1)
            result["bytes_read"] = len(content)
            result["handle_after"] = _stat(os.fstat(source.fileno()))
            result["bridge_after"] = _bridge_for_fd(source.fileno())
        result["path_after"] = _stat(selected.lstat())
        if len(content) > max_bytes:
            result.update(status="refused", reason="source_grew_beyond_bound")
            return result
        result["sha256"] = hashlib.sha256(content).hexdigest()
        result["observations_match"] = _observations_match(result)
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
        and before["stat_profile"] == after["stat_profile"]
        and all(before[key] == after[key] for key in STAT_NAMES)
        and all(before[key] == after[key] for key in BRIDGE_NAMES)
    )
    access_matches = result["status"] == "opened" if expected_access else (
        result["status"] == "open_error" and result["denial_observation"] is not None
    )
    result["expectation_met"] = bool(
        access_matches and result["close_error"] is None and result["source_unchanged"]
        and (result["opened_stat"] is None or result["opened_stat"] == before["handle_before"])
    )
    return result
