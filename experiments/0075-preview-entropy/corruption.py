"""Finite public authored JPEG mutations; no encoder, decoder or media access.

These are preregistered fault controls, not a universal entropy-validity proof.
The early-EOI case preserves #0107's rejected Pillow counterexample construction;
actual warning-aware native observations are required before qualification.
"""

from copy import deepcopy


CORRUPTION_VERSION = "0075-authored-corruption-v2-zero-interval"
BASE_ID = "formula-64-444"
INPUT_LIMIT = 32 * 1024 * 1024
_DECLARATIONS = (
    ("entropy-truncated", False, False, "half entropy, original EOI removed"),
    ("early-eoi", True, True, "half entropy followed by early EOI; historical Pillow counterexample"),
    ("immediate-eoi", True, True, "scan header followed by EOI without entropy"),
    ("suffix-nonzero-middle", False, False, "32-byte suffix with nonzero byte at zero-based position 16"),
    ("suffix-nonzero-last", False, False, "32-byte suffix with nonzero byte at zero-based position 31"),
    ("suffix-zero33", False, False, "33 zeros after complete EOI"),
    ("suffix-nonzero", False, False, "32-byte suffix with nonzero byte at zero-based position 0"),
    ("suffix-second-jpeg", False, False, "second complete authored JPEG after first EOI"),
    ("segment-length-one", False, False, "DQT length changed to forbidden one"),
    ("segment-length-overrun", False, False, "DQT length extends beyond stored extent"),
    ("quant-table-selector", False, False, "first frame component references forbidden quantization table 4"),
    ("huffman-table-selector", False, False, "first scan component references forbidden Huffman table 4"),
    ("scan-nonbaseline", False, False, "baseline scan spectral start changed to one"),
    ("entropy-restart-marker", False, False, "restart marker inserted into no-restart profile"),
    ("entropy-tem-marker", False, False, "unescaped FF01 inserted into entropy"),
    ("duplicate-soi", False, False, "second SOI inserted before marker sequence"),
)


def specs():
    """Return fresh declarations; structural refusals never invoke native code.

    Syntax-valid early/immediate EOI require actual native warning/error refusal.
    Syntax refusal requires nativeInvoked=false and decodeAccepted=None.
    """
    return tuple({
        "id": name,
        "baseId": BASE_ID,
        "mutation": description,
        "expected": {
            "syntaxAccepted": syntax,
            "decodeAccepted": False if native_refusal else None,
            "nativeInvoked": syntax,
            "nativeWarningOrErrorRequired": native_refusal,
            "combinedAccepted": False,
        },
    } for name, syntax, native_refusal, description in _DECLARATIONS)


def corruption_spec(case_id):
    for declaration in specs():
        if declaration["id"] == case_id:
            return declaration
    raise ValueError("unknown preregistered authored corruption")


def _layout(data):
    """Locate mutation offsets in one complete bounded baseline fixture.

    This helper is only a mutation locator, not the syntax or entropy validator.
    Lengths locate headers; stuffed FF00 is traversed while locating final EOI.
    """
    if type(data) is not bytes:
        raise TypeError("immutable authored bytes required")
    if not 4 <= len(data) <= INPUT_LIMIT or data[:2] != b"\xff\xd8":
        raise ValueError("authored baseline envelope required")
    cursor, segments = 2, {}
    while cursor < len(data):
        start = cursor
        if cursor + 4 > len(data) or data[cursor] != 255:
            raise ValueError("authored segment envelope required")
        marker = data[cursor + 1]
        length = int.from_bytes(data[cursor + 2:cursor + 4], "big")
        if marker not in (192, 196, 218, 219, 254, *range(224, 240)):
            raise ValueError("authored baseline segment required")
        if length < 2 or cursor + 2 + length > len(data):
            raise ValueError("authored complete segment required")
        cursor += 2 + length
        segments.setdefault(marker, start)
        if marker == 218:
            break
    else:
        raise ValueError("authored scan required")
    if not all(marker in segments for marker in (192, 196, 218, 219)):
        raise ValueError("authored baseline frame and tables required")
    scan_start = cursor
    while cursor < len(data):
        if data[cursor] != 255:
            cursor += 1
            continue
        if cursor + 1 >= len(data):
            break
        if data[cursor + 1] == 0:
            cursor += 2
            continue
        if data[cursor:cursor + 2] == b"\xff\xd9" and cursor + 2 == len(data):
            if cursor - scan_start < 4:
                raise ValueError("nontrivial authored entropy required")
            return segments, scan_start, cursor
        raise ValueError("single authored scan with exact final EOI required")
    raise ValueError("complete authored entropy extent required")


def build_corruption(case_id, complete):
    """Apply exactly one declared mutation without touching source bytes."""
    corruption_spec(case_id)
    segments, scan_start, eoi = _layout(complete)
    cut = scan_start + (eoi - scan_start) // 2
    # Preserve the exact halfway construction from #0107/#0111. Any unexpected
    # syntax mismatch on the fixed authored base invalidates this experiment.
    if case_id == "entropy-truncated":
        result = complete[:cut]
    elif case_id == "early-eoi":
        result = complete[:cut] + b"\xff\xd9"
    elif case_id == "immediate-eoi":
        result = complete[:scan_start] + b"\xff\xd9"
    elif case_id.startswith("suffix-zero"):
        result = complete + bytes(int(case_id.removeprefix("suffix-zero")))
    elif case_id in ("suffix-nonzero", "suffix-nonzero-middle", "suffix-nonzero-last"):
        position = {"suffix-nonzero": 0, "suffix-nonzero-middle": 16,
                    "suffix-nonzero-last": 31}[case_id]
        suffix = bytearray(32)
        suffix[position] = 1
        result = complete + bytes(suffix)
    elif case_id == "suffix-second-jpeg":
        result = complete + complete
    elif case_id in ("entropy-restart-marker", "entropy-tem-marker"):
        inserted = b"\xff\xd0" if case_id == "entropy-restart-marker" else b"\xff\x01"
        result = complete[:scan_start] + inserted + complete[scan_start:]
    elif case_id == "duplicate-soi":
        result = complete[:2] + b"\xff\xd8" + complete[2:]
    else:
        result = bytearray(complete)
        if case_id in ("segment-length-one", "segment-length-overrun"):
            at = segments[219] + 2
            result[at:at + 2] = b"\x00\x01" if case_id == "segment-length-one" else b"\xff\xff"
        elif case_id == "quant-table-selector":
            result[segments[192] + 12] = 4
        elif case_id == "huffman-table-selector":
            result[segments[218] + 6] = 0x44
        elif case_id == "scan-nonbaseline":
            result[scan_start - 3] = 1
        else:
            raise AssertionError("declaration lacks mutation implementation")
        result = bytes(result)
    if len(result) > INPUT_LIMIT:
        raise ValueError("mutated authored extent exceeds input ceiling")
    return result


def declaration():
    return {"version": CORRUPTION_VERSION, "baseId": BASE_ID,
            "cases": deepcopy(list(specs())),
            "universalEntropyProofClaimed": False,
            "historicalPillowStrictCandidateAccepted": False}
