"""Preregistered formula-authored controls; no media paths or decoder imports.

Encoding is explicit and requires the caller's reviewed-runtime verification hook.
The finite controls exercise representative syntax and dimension/RGB boundaries;
they do not prove all JPEGs inside the generic envelope valid. JPEG is lossy:
expected output is the full declared RGB extent, not equality to source pixels.
"""

from copy import deepcopy
import hashlib
import io


CONTROL_VERSION = "0075-authored-controls-v2-zero-interval"
INPUT_LIMIT = 32 * 1024 * 1024
DIMENSION_LIMIT = 8192
RGB_LIMIT = 256 * 1024 * 1024
FORMULA = "rgb-mod256-x13y7-x3y19-x23y11"
SOLID = "solid-rgb-64-128-192"
ENCODER_OPTIONS = {"quality": 90, "optimize": False, "progressive": False}

# These constants are selected from authored practical boundaries, independently
# of any camera input. Subsampling values are Pillow's fixed 444/422/420 options.
_BASES = (
    ("formula-64-444", 64, 64, FORMULA, 0),
    ("odd-19x17-420", 19, 17, FORMULA, 2),
    ("formula-256-422", 256, 256, FORMULA, 1),
    ("wide-8192x1-444", 8192, 1, SOLID, 0),
    ("tall-1x8192-444", 1, 8192, SOLID, 0),
    ("square-8192-420", 8192, 8192, SOLID, 2),
)


def specs():
    """Return fresh JSON-compatible declarations, without encoding anything."""
    declarations = []
    for name, width, height, formula, subsampling in _BASES:
        suffix_lengths = range(33) if name == "formula-64-444" else (0, 32)
        for suffix_length in suffix_lengths:
            declarations.append({
                "id": name + (f"-zero{suffix_length}" if suffix_length else ""),
                "baseId": name,
                "width": width,
                "height": height,
                "formula": formula,
                "subsampling": subsampling,
                "encoderOptions": deepcopy(ENCODER_OPTIONS),
                "suffixBytes": suffix_length,
                "expected": {
                    "syntaxAccepted": True,
                    "nativeInvoked": True,
                    "decodeAccepted": True,
                    "width": width,
                    "height": height,
                    "decodedBytes": width * height * 3,
                    "pixelFormat": "packed-RGB",
                    "pixelEqualityToSourceAsserted": False,
                    "samePixelsAsBase": bool(suffix_length),
                    "sameRgbBytesAsBase": bool(suffix_length),
                    "nativeInput": "full-stored-input-including-suffix",
                },
            })
    return tuple(declarations)


def control_spec(case_id):
    for specification in specs():
        if specification["id"] == case_id:
            return specification
    raise ValueError("unknown preregistered authored control")


def formula_rgb(width, height, formula=FORMULA):
    """Construct bounded authored packed RGB; reject arbitrary image parameters."""
    if (type(width) is not int or type(height) is not int
            or not 1 <= width <= DIMENSION_LIMIT
            or not 1 <= height <= DIMENSION_LIMIT
            or width * height * 3 > RGB_LIMIT):
        raise ValueError("authored RGB dimensions outside generic envelope")
    if formula == SOLID:
        return bytes((64, 128, 192)) * (width * height)
    if formula != FORMULA:
        raise ValueError("unknown authored pixel formula")
    # Avoid a large Python integer list for each RGB image.
    output = bytearray(width * height * 3)
    offset = 0
    for y in range(height):
        for x in range(width):
            output[offset] = (x * 13 + y * 7) % 256
            output[offset + 1] = (x * 3 + y * 19) % 256
            output[offset + 2] = (x * 23 + y * 11) % 256
            offset += 3
    return bytes(output)


def build_control(case_id, verify_encoder):
    """Encode one exact declared control after caller-owned runtime verification.

    The hook must verify the pinned installed encoder before this function imports
    Pillow; runtime verification exceptions propagate. No decoder is used here.
    The runner additionally owns the reviewed authored execution grant.
    """
    specification = control_spec(case_id)
    if not callable(verify_encoder):
        raise TypeError("reviewed encoder verification hook is required")
    verify_encoder()
    from PIL import Image

    pixels = formula_rgb(specification["width"], specification["height"],
                         specification["formula"])
    output = io.BytesIO()
    with Image.frombytes("RGB", (specification["width"], specification["height"]),
                         pixels) as image:
        image.save(output, "JPEG", subsampling=specification["subsampling"],
                   **specification["encoderOptions"])
    encoded = output.getvalue()
    if not encoded.startswith(b"\xff\xd8") or not encoded.endswith(b"\xff\xd9"):
        raise ValueError("authored encoder did not produce exact JPEG envelope")
    result = encoded + bytes(specification["suffixBytes"])
    if len(result) > INPUT_LIMIT:
        raise ValueError("authored encoding exceeds generic input ceiling")
    return result


def declaration():
    """Public recipe metadata for runner binding and independent reconstruction."""
    return {
        "version": CONTROL_VERSION,
        "inputLimit": INPUT_LIMIT,
        "dimensionLimit": DIMENSION_LIMIT,
        "rgbLimit": RGB_LIMIT,
        "formula": FORMULA,
        "solid": SOLID,
        "cases": list(specs()),
    }


def source_pixel_digest(case_id):
    """Authored source identity only; never a lossy decoded-pixel oracle."""
    specification = control_spec(case_id)
    return hashlib.sha256(formula_rgb(
        specification["width"], specification["height"],
        specification["formula"])).hexdigest()
