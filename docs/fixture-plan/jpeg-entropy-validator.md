# Authored JPEG entropy decoder qualification

Observed 2026-10-15, #0107, profile
`pillow-12.3.0-windows-authored-2026-10-15.1`. The installed Pillow decoder
**fails the proposed strict entropy-validator profile**: a deliberately shortened
entropy scan terminated with an early EOI returns substituted pixels. Disabling
truncation tolerance does not turn decoder success into proof of complete entropy.
This finishes the finite authored tool qualification; [P0A-002](p0-assertion-gaps.v1.json)
and #0075 retain the independent camera assertion and phase review.

## Runtime and provenance

The existing Codex workspace dependency bundle `26.1013.11914` supplies Windows
AMD64 CPython 3.12.14, Pillow 12.3.0, JPEG API 8.0 and libjpeg-turbo 3.1.4.1.
No dependency was downloaded, installed or added to the root Rust package.
The [profile](../../experiments/0107-jpeg-validator/profile.json) records exact
SHA-256 identities and lengths for the interpreter, Python runtime DLL and notices, Pillow
native decoder, relevant Python decoder modules, package metadata, notices and
SBOM. Qualification checks those identities before constructing or decoding controls.
This pins the named components, not the entire OS or every transitive runtime file.

Installed distribution evidence is under `pillow-12.3.0.dist-info`:

- `METADATA` identifies Pillow and its `MIT-CMU` license expression.
- `licenses/LICENSE` contains Pillow's MIT-CMU terms and bundled component notices,
  including libjpeg-turbo 3.1.4.1 and its applicable compatible license terms.
- `sboms/pillow-12.3.0.cdx.json` identifies the packaged components.

The interpreter directory's `LICENSE.txt` supplies the installed Python license
and notices; its exact bytes are also pinned.

These are local distribution evidence observed on the date above. The runner uses
the installed package; this repository redistributes no Pillow binary, upstream
fixture or copied implementation. Future redistribution needs its own applicable
notice review. The Python `JpegImagePlugin.load_read` implementation documents its
optional premature-EOF EOI insertion; this recipe explicitly disables that option.
The local source and notices are identified by the profile's hashes.

## Four authored controls and actual outcomes

The [runner](../../experiments/0107-jpeg-validator/qualify.py) creates a 64 by 64 RGB
image from explicit integer formulas, then encodes baseline JPEG with quality 90,
subsampling 0, optimization disabled and progressive encoding disabled. No camera,
preview or imported photograph supplies pixels. Marker lengths locate the single
scan start. The cut is halfway through its entropy extent, before the original EOI.
The encoder and decoder belong to the same installed library: this is finite
decoder fault qualification, not independent proof of the encoder's correctness.

| Control | Construction | Expected and observed result |
| --- | --- | --- |
| `complete` | Full authored baseline codestream | Full load returns RGB pixels. |
| `entropy-truncated` | Prefix ending halfway through entropy, without EOI | Full load raises `OSError`. |
| `trailing-zeros` | Complete codestream followed by exactly 32 zero bytes | Full load returns pixels identical to the complete control. |
| `early-eoi` | Same shortened entropy prefix followed by EOI | Full load returns pixels differing from the complete control; proposed strict validation fails. |

The fixed denominator is four. [Curated observations](../../experiments/0107-jpeg-validator/observations.json)
retain authored input hashes/lengths, structural offsets, decoded pixel hashes,
bounded error text, process exit/capture observations and the false qualification
flag. Returned bytes and dimensions are checked; no pixels are saved or displayed.
The early-EOI counterexample is sufficient to reject this proposed profile. It is
not an exhaustive classification of JPEG corruption or the decoder's error recovery.

## Bounds and stored extent policy

Each child constructs only one of the four named authored controls. There is no
external image-path argument. Input is capped at 65,536 bytes and each dimension
at 128. `ImageFile.LOAD_TRUNCATED_IMAGES` is false; `Image.open` restricts formats
to JPEG, followed by `load()` and decoded-byte consumption. Header-only `verify()`
is insufficient for this assertion and is not used.

Each child has a ten-second deadline. Separate stdout/stderr drains retain at most
8,192 bytes per stream and kill the child on overflow. This bounds captured bytes;
it is not an OS memory quota or a hard real-time scheduling guarantee. Unexpected
process failures, timeouts, capture overflows, changed identities or changed control
outcomes fail the qualification recipe.

Every stored extent is passed unchanged. The trailing-zero result applies to the
exact 32-zero control; it neither authorizes arbitrary suffixes nor permits trimming
bytes from native extraction. A decoder's willingness to ignore a suffix does not
prove that the suffix was consumed as JPEG syntax. EOI presence alone supplies no
entropy-completeness guarantee, as the early-EOI control demonstrates.

## Reproduction and remaining gates

Use the Python executable returned by Codex's workspace dependency tool; ordinary
system Python on the observed machine does not contain Pillow. From the repository
root, with that interpreter selected:

```text
python experiments/0107-jpeg-validator/qualify.py --output .local/0107-replay.json
```

The output is deterministic for the pinned runtime and can be compared with the
committed observations. A different interpreter or component hash refuses before
control generation. Do not regenerate the profile merely to suppress a mismatch;
review a changed runtime as a new candidate.

No private camera/PreviewImage bytes were decoded. Existing reference-only fixture
admission is not expanded. Any later camera run still requires exact fixture,
allowed-phase and decoded-derivative review; all new camera-derived outcomes and
reports remain private where publication is denied. This rejected candidate adds
no production JPEG validator, RAW pixel development feature, writer permission or
new prerequisite to byte-exact preview extraction.
