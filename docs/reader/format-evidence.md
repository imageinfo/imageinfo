# Read-slice mapping and format evidence

Observed **2026-10-11**. Native code and synthetic byte fixtures are independently
authored. No upstream implementation, complete tag table, camera fixture or
documentation body is imported. Selected factual identifiers are distinguished
from code reuse; this is not a formal clean-room claim.

| Source | What supports this slice |
| --- | --- |
| [CIPA DC-X008-2016 English specification](https://www.cipa.jp/std/documents/e/CIPA_DC-X008-Translation-2016-E.pdf) | Classic TIFF/IFD storage, EXIF tag identities, unsigned rationals and separate capture-time fields. Published vendor/standards document; viewed 2026-10-11. |
| [Apple sample-to-chunk](https://developer.apple.com/documentation/quicktime-file-format/sample-to-chunk_atom), [sample sizes](https://developer.apple.com/documentation/quicktime-file-format/sample_size_atom), [chunk offsets](https://developer.apple.com/documentation/quicktime-file-format/chunk_offset_atom) | Standard track/sample/chunk relationships. Living primary documentation; actual used headers independently checked on the private files. |
| [Laurent Clévy CR3 research notes, revision 151c1a965775ef409ace17714c24ed491cfcf9c4](https://github.com/lclevy/canon_cr3/blob/151c1a965775ef409ace17714c24ed491cfcf9c4/readme.md) | CMT/preview/timed-metadata and CMP1 structure context; facts corroborated against the private bytes. Notes version 16sep2026, retrieved 2026-10-11. No GPL implementation or sample imported. |
| [ExifTool Canon tag documentation, pinned 13.59](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/TagNames/Canon.html) | Selected vendor field identities and labels only: firmware/model, CameraSettings quality and LightingOpt DPRAW. No wholesale table or parser translation. |
| [Private baseline](../corpus-baseline/README.md) | Input-bound reference identities and captures; native checks use those exact immutable bytes and source-qualified occurrences. |

The observed native profile uses Canon UUID `85c0b687820f11e08111f4ce462b6a48`
and preview UUID `eaf42b5e1c984b88b9fbb7dc406e4d16`. Its CCTP declares image roles
and track IDs; each supported track has one local sample/chunk/description. CTMD
exposure type 5 provides two short rational pairs followed by ISO. CMP1's declared
encoding/wavelet fields gate the main RAW profile; no sensor bitstream is decoded.
Preview extents include verified padding. These facts were independently inspected
at their own bounded locations, not assumed from a filename or file-wide byte scan.

## Independently recorded field map

| Native namespace/location | IDs / interpretation |
| --- | --- |
| exif, CMT1 | 0x0100 width, 0x0101 height, 0x010f make, 0x0110 model |
| exif, CMT2 | 0x829a exposure, 0x829d f-number, 0x8827 ISO, 0x920a focal length |
| exif, CMT2 time strings | 0x9003 original date/time, 0x9011 original offset, 0x9291 original subsecond |
| exif, CMT2 dimensions | 0xa002 pixel X, 0xa003 pixel Y |
| canon, CMT3 | 7 firmware, 16 model code; accepted R5 model value 0x80000421 |
| canon, CMT3 packed fields | CameraSettings tag 1 / element 3, LightingOpt tag 0x4018 / element 11 |
| canon:ctmd | Type-5 payload offsets 0 and 4 rational pairs, offset 8 ISO; each has its own track/record path |
| canon:binary | THMB, PRVW and assigned JPEG sample; named extents, not rendered values |

The reference adapter selects CMT occurrences through UUID/namespace paths and
direct CTMD ExposureInfo occurrences through track paths. It does not compare a
derived Composite ISO or nested maker-note copy to a stored EXIF/CTMD occurrence.
Native rational pairs are independently checked against the reported byte spans;
numeric equivalence to reference values is exact. Fields from unimplemented
locations remain unclaimed even when their names resemble supported ones.

The [32 scoped differential records](validation.md) do not close whole case families
or the 49-row inventory. Model, preservation, per-tag breadth, extensions, privacy,
independent image usability and additional variants retain their separate gates.
