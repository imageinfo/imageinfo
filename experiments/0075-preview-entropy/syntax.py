"""Fixed authored research JPEG extent profile; never proves entropy correctness.

No file access, native imports, decoding, trimming, or input rewriting occurs here.
This separately qualified #0075 profile does not widen historical #0111.
"""

INPUT_LIMIT = 32 * 1024 * 1024
DIMENSION_LIMIT = 8192
DECODED_LIMIT = 256 * 1024 * 1024
PROFILE_ID = "0075-baseline-interleaved-rgb-zero-padding-v2"


def inspect_extent(data: bytes) -> dict:
    """Inspect the entire stored extent under one fixed, finite syntax policy.

    ``accepted`` means syntax/extent fit only. Even empty or corrupt entropy
    may fit; a separately qualified warning-enforcing full decoder is required.
    Offsets are zero-based, with eoiEnd exclusive. No slices are returned as a
    replacement decoder input: callers must retain and submit all original bytes.
    """
    def refuse(reason):
        return {"accepted": False, "reason": reason, "profileId": PROFILE_ID}

    if type(data) is not bytes:
        return refuse("input-type")
    if len(data) > INPUT_LIMIT:
        return refuse("input-bound")
    if data[:2] != b"\xff\xd8":
        return refuse("missing-soi")
    cursor, frame, scan_start = 2, None, None
    quant_tables, huffman_tables = set(), set()
    while cursor < len(data):
        if data[cursor] != 255:
            return refuse("expected-marker")
        while cursor < len(data) and data[cursor] == 255:
            cursor += 1
        if cursor == len(data):
            return refuse("incomplete-extent")
        marker = data[cursor]
        cursor += 1
        if marker == 0xD9:
            if frame is None or scan_start is None:
                return refuse("missing-frame-or-scan")
            suffix = data[cursor:]
            if len(suffix) > 32 or any(suffix):
                return refuse("unsupported-suffix")
            return {"accepted": True, "reason": "supported", "profileId": PROFILE_ID,
                    "inputBytes": len(data), "width": frame[0], "height": frame[1],
                    "decodedBytes": frame[0] * frame[1] * 3,
                    "scanStart": scan_start, "eoiEnd": cursor, "suffixBytes": len(suffix)}
        if scan_start is not None:
            return refuse("unsupported-postscan-marker")
        if marker not in (0xC0, 0xC4, 0xDA, 0xDB, 0xFE, *range(0xE0, 0xF0)):
            return refuse("unsupported-marker")
        if cursor + 2 > len(data):
            return refuse("segment-length")
        length = int.from_bytes(data[cursor:cursor + 2], "big")
        if length < 2 or cursor + length > len(data):
            return refuse("segment-length")
        payload = data[cursor + 2:cursor + length]
        cursor += length
        if marker == 0xDB:
            position = 0
            while position < len(payload):
                selector = payload[position]
                if selector > 3 or position + 65 > len(payload):
                    return refuse("unsupported-quantization-table")
                if 0 in payload[position + 1:position + 65]:
                    return refuse("zero-quantization-value")
                quant_tables.add(selector)
                position += 65
            if not payload:
                return refuse("empty-quantization-segment")
        elif marker == 0xC4:
            position = 0
            while position < len(payload):
                if position + 17 > len(payload):
                    return refuse("huffman-table-length")
                selector = payload[position]
                symbols = sum(payload[position + 1:position + 17])
                if selector >> 4 > 1 or selector & 15 > 3 or not 0 < symbols <= 256:
                    return refuse("unsupported-huffman-table")
                if position + 17 + symbols > len(payload):
                    return refuse("huffman-table-length")
                huffman_tables.add(selector)
                position += 17 + symbols
            if not payload:
                return refuse("empty-huffman-segment")
        elif marker == 0xC0:
            if frame is not None or len(payload) != 15 or payload[0] != 8 or payload[5] != 3:
                return refuse("unsupported-frame")
            height = int.from_bytes(payload[1:3], "big")
            width = int.from_bytes(payload[3:5], "big")
            if not (0 < width <= DIMENSION_LIMIT and 0 < height <= DIMENSION_LIMIT):
                return refuse("dimension-bound")
            if width * height * 3 > DECODED_LIMIT:
                return refuse("decoded-bound")
            components = {}
            blocks = 0
            for position in (6, 9, 12):
                component, sampling, table = payload[position:position + 3]
                horizontal, vertical = sampling >> 4, sampling & 15
                if not (1 <= horizontal <= 4 and 1 <= vertical <= 4) or table > 3:
                    return refuse("unsupported-frame-component")
                if component in components:
                    return refuse("duplicate-component")
                components[component] = table
                blocks += horizontal * vertical
            if blocks > 10:
                return refuse("unsupported-mcu-block-count")
            frame = (width, height, components)
        elif marker == 0xDA:
            if frame is None or len(payload) != 10 or payload[0] != 3 or payload[-3:] != b"\x00\x3f\x00":
                return refuse("unsupported-scan")
            identifiers = payload[1:7:2]
            if len(set(identifiers)) != 3 or set(identifiers) != set(frame[2]):
                return refuse("scan-components")
            if not set(frame[2].values()) <= quant_tables:
                return refuse("missing-quantization-table")
            for selector in payload[2:7:2]:
                dc, ac = selector >> 4, selector & 15
                if dc > 3 or ac > 3 or dc not in huffman_tables or (0x10 | ac) not in huffman_tables:
                    return refuse("missing-or-unsupported-huffman-table")
            scan_start = cursor
            # FF00 represents an entropy data byte, never an EOI. Only a real
            # marker ends this walk. Restart/multiple scans are outside profile.
            while cursor < len(data):
                if data[cursor] != 255:
                    cursor += 1
                    continue
                start = cursor
                cursor += 1
                if cursor < len(data) and data[cursor] == 0:
                    cursor += 1
                    continue
                while cursor < len(data) and data[cursor] == 255:
                    cursor += 1
                if cursor == len(data):
                    return refuse("incomplete-extent")
                if data[cursor] == 0:
                    return refuse("invalid-entropy-stuffing")
                cursor = start
                break
    return refuse("incomplete-extent")
