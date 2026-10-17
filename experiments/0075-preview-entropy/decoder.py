"""Bounded research TurboJPEG adapter; callers own phase and runtime admission.

Importing this module does not load a codec.  No file/path input is supported.
The full immutable stored extent is passed unchanged to both native operations.
"""
import ctypes as C
import hashlib
import sys

from syntax import DECODED_LIMIT, DIMENSION_LIMIT, INPUT_LIMIT, inspect_extent

STOPONWARNING = 8192
TJPF_RGB = 0
DIAGNOSTIC_LIMIT = 240
API = "tjDecompress2"


def configure_library(dll):
    """Declare the historical #0111 Windows x64 cdecl TurboJPEG ABI explicitly."""
    if sys.platform != "win32" or C.sizeof(C.c_ulong) != 4 or C.sizeof(C.c_void_p) != 8:
        raise RuntimeError("reviewed Windows x64 ABI required")
    signatures = {
        "tjInitDecompress": ([], C.c_void_p),
        "tjDecompressHeader3": ([C.c_void_p, C.c_void_p, C.c_ulong]
                                + [C.POINTER(C.c_int)] * 4, C.c_int),
        "tjDecompress2": ([C.c_void_p, C.c_void_p, C.c_ulong, C.c_void_p,
                           C.c_int, C.c_int, C.c_int, C.c_int, C.c_int], C.c_int),
        "tjGetErrorCode": ([C.c_void_p], C.c_int),
        "tjGetErrorStr2": ([C.c_void_p], C.c_void_p),
        "tjDestroy": ([C.c_void_p], C.c_int),
    }
    for name, (args, result) in signatures.items():
        function = getattr(dll, name)
        function.argtypes, function.restype = args, result
    return dll


def _diagnostic(dll, handle, status):
    # Read one byte at a time and stop at NUL: do not read beyond a short native
    # string merely to impose the diagnostic output ceiling.
    pointer = dll.tjGetErrorStr2(handle)
    if not pointer:
        raise RuntimeError("native diagnostic absent")
    message = bytearray()
    for offset in range(DIAGNOSTIC_LIMIT + 1):
        value = C.c_ubyte.from_address(pointer + offset).value
        if value == 0:
            break
        message.append(value)
    else:
        raise RuntimeError("native diagnostic exceeds reviewed ceiling")
    severity = dll.tjGetErrorCode(handle)
    if status != 0 and severity not in (0, 1):
        raise RuntimeError("unknown native failure severity")
    return {"returnCode": status, "severityRaw": severity,
            "severityMeaningful": status != 0,
            "severity": ({0: "warning", 1: "fatal"}[severity]
                         if status != 0 else "not-meaningful-on-success"),
            "diagnosticRaw": message.decode("utf-8", "replace")}


def decode(data, *, load_library, verify_loaded, pixel_sink=None):
    """Return private-capable evidence, optionally passing complete pixels to a sink.

    ``load_library`` must verify the exact pinned runtime before loading and
    return its CDLL. ``verify_loaded`` checks its loaded non-OS closure after
    native work. These mandatory callbacks are supplied by the admitted worker,
    not by data or a serialized input. Profile/phase authorization remains a
    separate caller prerequisite. Rejected syntax invokes neither callback.
    ``pixel_sink``, if supplied, synchronously consumes one read-only view of
    complete successful output. The caller owns derivative admission, exact-size
    writing and cleanup. The view is valid only during that call. Exceptions
    propagate after handle destruction and closure verification; no success
    report is returned for an incomplete derivative.
    """
    if type(data) is not bytes:
        raise TypeError("one immutable bytes extent is required")
    if pixel_sink is not None and not callable(pixel_sink):
        raise TypeError("pixel sink must be callable or absent")
    syntax = inspect_extent(data)
    row = {"accepted": False, "syntax": syntax, "api": API,
           "flags": STOPONWARNING, "pixelFormat": "RGB", "pitch": 0,
           "storedExtentBytes": len(data), "nativeInvoked": False,
           "pixelsRetainedByAdapter": False, "pixelSinkCompleted": False}
    if not syntax["accepted"]:
        return {**row, "outcome": "syntax-refused"}
    width, height, decoded_bytes = syntax["width"], syntax["height"], syntax["decodedBytes"]
    # Defense in depth before any codec load or source/output C allocation.
    if (not 0 < len(data) <= INPUT_LIMIT or
            not 0 < width <= DIMENSION_LIMIT or not 0 < height <= DIMENSION_LIMIT or
            decoded_bytes != width * height * 3 or not 0 < decoded_bytes <= DECODED_LIMIT):
        raise RuntimeError("accepted syntax violated adapter bounds")
    dll = configure_library(load_library())
    source = (C.c_ubyte * len(data)).from_buffer_copy(data)
    handle = dll.tjInitDecompress()
    if not handle:
        verify_loaded()
        raise RuntimeError("native initialization failed")
    row["nativeInvoked"] = True
    try:
        w, h, sampling, colorspace = (C.c_int() for _ in range(4))
        status = dll.tjDecompressHeader3(handle, source, len(data), C.byref(w),
                                       C.byref(h), C.byref(sampling), C.byref(colorspace))
        row["header"] = _diagnostic(dll, handle, status)
        row["headerDimensions"] = [w.value, h.value]
        row["subsamplingRaw"], row["colorspaceRaw"] = sampling.value, colorspace.value
        if status != 0:
            row["outcome"] = "header-refused"
        elif (w.value, h.value) != (width, height):
            row["outcome"] = "header-syntax-mismatch"
        else:
            pixels = (C.c_ubyte * decoded_bytes)()
            status = dll.tjDecompress2(handle, source, len(data), pixels,
                                       width, 0, height, TJPF_RGB, STOPONWARNING)
            row["decode"] = _diagnostic(dll, handle, status)
            row["dimensions"] = [width, height]
            row["outcome"] = "warning-free-pixels" if status == 0 else "native-refused"
            if status == 0:
                # Hash every packed RGB byte directly; no second full-size copy
                # and no adapter-owned pixel file, image object or display.
                consumed = memoryview(pixels).cast("B")
                try:
                    row.update(decodedBytes=consumed.nbytes,
                               pixelSha256=hashlib.sha256(consumed).hexdigest(),
                               consumption="sha256-all-packed-rgb-bytes")
                    if pixel_sink is not None:
                        readonly = consumed.toreadonly()
                        try:
                            pixel_sink(readonly)
                        finally:
                            readonly.release()
                        row["pixelSinkCompleted"] = True
                    row["accepted"] = True
                finally:
                    consumed.release()
    finally:
        destroyed = dll.tjDestroy(handle)
        row["destroy"] = {"returnCode": destroyed, "succeeded": destroyed == 0}
        verify_loaded()
        if destroyed != 0:
            raise RuntimeError("native destroy failed")
    return row
