# Canon EOS R5 full RAW read slice

Implemented under **#0020**, observed **2026-10-11**, version **0.2.0-dev**.
The native Rust reader interprets a declared subset of Canon EOS R5 full RAW CR3,
lists stored previews, and copies one preview to a separately named new file.
It does not invoke ExifTool or decode/develop/recompress sensor pixels.

```console
cargo run --locked -- metadata read --values all --output json -- photo.cr3
cargo run --locked -- metadata read --tag ISO -- photo.cr3
cargo run --locked -- binary list -- photo.cr3
cargo run --locked -- binary extract --tag PreviewImage --output-file preview.jpg -- photo.cr3
cargo run --locked -- binary extract --tag PreviewImage --output-file preview.jpg --dry-run -- photo.cr3
```

Build/setup and checks remain in the [foundation guide](../foundation/README.md).
Help is available at every advertised root/group/leaf node. Only implemented
commands are advertised. `--interactive`, XMP operations, metadata mutation,
directory traversal, input manifests and richer output formats remain unavailable.

## Supported fields and source locations

The [mapping/format evidence](format-evidence.md) records identifiers, byte-layout
sources and actual observation limits. This table is the support denominator;
it does not mean all EXIF/Canon/CR3 tags are implemented.

| Names | Native source | Stored values |
| --- | --- | --- |
| Make, Model | CMT1 TIFF | ASCII, exact text with storage span retained |
| ImageWidth, ImageHeight | CMT1 TIFF | Unsigned integer |
| ExposureTime, FNumber, FocalLength | CMT2 TIFF | Exact unsigned rational pairs |
| ISO | CMT2 TIFF | Unsigned integer |
| DateTimeOriginal, OffsetTimeOriginal, SubSecTimeOriginal | CMT2 TIFF | Separate exact stored strings; no implicit host timezone or instant conversion |
| PixelXDimension, PixelYDimension | CMT2 TIFF | Unsigned integer; ExifImageWidth/ExifImageHeight are selector aliases |
| CanonFirmwareVersion, CanonModelID | CMT3 TIFF | Exact text / unsigned model code |
| Quality | CMT3 CameraSettings element 3 | Stored integer; display `RAW` for code 4 |
| DualPixelRaw | CMT3 LightingOpt element 11 | Stored integer; display Off/On |
| ISO, FNumber, ExposureTime | CTMD type-5 exposure record | Separate occurrences with track/record/field provenance; rational pairs retained |
| ThumbnailImage, PreviewImage, JpgFromRaw | THMB, PRVW, declared JPEG track | Named binary references, bounded source ranges and exact stored-byte extraction |

An unqualified `--tag ISO` returns both implemented ISO occurrences. `EXIF:ISO`
selects the EXIF occurrence; `CTMD:ISO` selects timed metadata. `Canon:Quality`
selects the maker field. Unknown names/prefixes fail before media I/O. No match
within this partial coverage is reported as unresolved, never globally absent.
Repeated selectors do not duplicate an occurrence or erase its origin.

Raw/normalized numeric values remain exact native integers/rational pairs. JSON
serializes their decimal strings under the existing metadata contract. Identity
normalization preserves the stored pair; comparison to the reference uses exact
numeric equivalence, not a float-to-string equality test. Display is a separate
English formatter; aperture uses one decimal and focal length includes mm. Text
`--values all` includes raw, normalized and display views. JSON always retains
raw/normalized information; `all`/`display` additionally request display fields.

## Recognition and explicit incompleteness

Detection uses file bytes rather than the filename extension. Recognition requires
`crx `, the supported Canon metadata container, consistent camera/model/mode
fields, local single-sample track references, and a main-sensor CMP1 declaration
consistent with full RAW and visible dimensions. C-RAW/wavelet, DPRAW, burst,
other-camera and unknown descriptor/reference profiles are refused. These are
stored declarations and structural checks, not tamper-proof camera identity or
independent validation of sensor encoding.

All eight private captures tested use firmware **2.2.1**, ISO **400** and one lens.
There is no real-camera coverage of other firmware/settings or negative variants.
Public negative cases are independently authored structural data, not sample photos.

Every snapshot labels coverage **partial** and exposes unknown regions as opaque
source ranges. Embedded JPEG metadata, GPS interpretation, XMP, calibration tables,
composites and other maker-note families are not decoded. Source/resource hashes
are not computed by ordinary bounded reading; `identity: unavailable` and nullable
resource hashes are honest. Such snapshots cannot authorize a write or reopening
an arbitrary resource path. Native extraction reparses a live file and resolves a
registered preview name rather than accepting ranges from imported JSON.

## Bounds and cancellation

| Guard | Default / behavior |
| --- | --- |
| Actual metadata reads | 8 MiB per source; `--max-bytes` can change it within a 256 MiB ceiling |
| One metadata block | 1 MiB; fixed CLI default |
| Box count / recursion depth | 4096 boxes / depth guard 16, root depth zero |
| TIFF | 4096 entries per CMT and pointer-hop guard 16; cycles/aliases and out-of-range values refused |
| Timed metadata | 4096 records in the declared single-sample track |
| One preview | 64 MiB; `--max-preview-bytes` up to 1 GiB; copying uses a 32 KiB buffer |
| Explicit input list | At most 16 arguments; exact repeated paths deduplicated, physical aliases not merged |
| Diagnostics | Escaped and capped at 4 KiB; result data is not silently truncated |

These are conservative enforced guards, not performance targets selected through
benchmarks. There is no OS hard process-memory limit or interruptible/deadlined
filesystem abstraction. Blocking filesystem calls may delay cancellation. Forced
termination of extraction may leave a recognizable private temporary file; this
slice does not implement persistent recovery. No metadata/sensor write is enabled.

## Extraction publication

Stored extents retain padding; matching an EOI marker does not authorize trimming.
The reader recognizes the selected JPEG resource start but does not certify JPEG
decoding. `--dry-run` validates selection/destination and writes nothing.

Extraction writes a unique same-directory temporary file, flushes/syncs it, then
publishes through a no-clobber hard link. This avoids Unix `rename` overwrite
behavior and rejects a destination that appears after preflight. Existing files,
directories, symlinks and the source are never overwritten. Unsupported hard-link
filesystems fail; there is no fallback to a weaker overwrite policy. Scope is a
trusted local output directory on the tested filesystems; hostile namespace races,
remote filesystem guarantees, directory durability and power-loss recovery remain
separate #0014 work. Ordinary length/mtime checks detect many source changes, but
do not provide a strong lock or content identity against adversarial editing.

JSON results retain per-file read/refused/failed states, zero source effects and
explicit extraction artifacts. All failures return 1, mixed successes/failures 3,
whole-request errors 2, and cleanup/publication uncertainty 5. Syntax failures that
prevent validated output selection still use bounded plain stderr; LG-006 remains
open. Machine output requires acceptable process status and a complete final summary.

See [validation](validation.md) and [sanitized private comparison totals](summary.json).
