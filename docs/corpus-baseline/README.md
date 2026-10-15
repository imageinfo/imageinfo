# First private EOS R5 full RAW baseline

Observed **2026-10-10**, card **#0013**. This is actual ExifTool reference
characterization at that historical checkpoint. Subsequent [#0020](../reader/README.md)
implements a Rust read/preview slice with scoped native comparisons. That does not
turn the original reference-only baseline into full native parity or a benchmark.

Eight user-owned CR3 files were selected from 202 supplied candidates using file
size and modification-time quantiles. This deliberately small selection covers
some file-size variation; it is not a random sample or a survey of camera settings.
Copies, metadata captures, previews, provenance and exact reproduction records
remain restricted local assets. Original bytes and modification times were checked
before/after acquisition and at the end; all eight remained unchanged.

## What ran

| Reference operation | Invocations |
| --- | ---: |
| Normalized and display CLI reads: eight RAWs, two versions | 32 |
| API Raw/Rational/ValueConv/PrintConv observations: eight RAWs | 8 |
| Stored preview extraction: three resources per RAW | 24 |
| Metadata reads of those RAW-derived JPEG resources | 24 |
| Separately named XMP creation/edit/conflict outputs | 3 |
| CLI and API reads of the three XMP outputs | 6 |
| **Total** | **97** |

All 97 final reference invocations exited zero, with captured stdout/stderr and
unchanged per-invocation input hashes. This does not make every planned assertion
a pass. The bundle contains **35 admitted private fixtures**, **39 scoped provenance
reviews**, two acquired oracle profiles and 97 experiment records. The original
[29-family case plan](../fixture-plan/case-plan.v1.json) remains a requirements
baseline, not a completed coverage checklist.

See the [sanitized aggregate data](summary.json), [method and evidence boundaries](method.md)
and [validation record](validation.md). No photographs, identifying metadata,
source filenames/paths, capture timestamps, per-image hashes or private logs are
published here. Exact reproduction requires authorized access to the private bundle.

The later [#0073 second-environment method](second-environment.md) keeps its new
camera-derived ledger and results private under the existing fixture grants.
Public authored controls and a reproduction method do not extend the disclosure
permission of this historical summary or establish independent camera validation.

## Observations and consequences

- Every selected file has a `crx ` major brand and stored Canon EOS R5 model,
  `RAW` quality and Dual Pixel RAW `Off` observations. These corroborate the user's
  full RAW declaration; mutable tags do not prove camera identity or sensor encoding.
- All eight have firmware **2.2.1**, **ISO 400** and one lens model. More files from
  this same stratum would add little evidence about different settings or firmware.
- Each display capture contains **704 fields**, including `SourceFile`. This is a
  count under these options, not an inventory of all supported tags. ISO occurs in
  EXIF, CTMD and Composite sources; occurrence identity must retain source context.
- Three resources were resolved per file: `Canon:ThumbnailImage`,
  `QuickTime:PreviewImage` and `Track1:JpgFromRaw`. All 24 extracted lengths and
  SHA-256 digests match the explicitly binary API ValueConv values. This compares
  two surfaces of the same engine; it is not independent JPEG or RAW decoding.
- **15 of 24 resources contain bytes after the last JPEG EOI marker.** Extraction
  retained them exactly. Do not trim a stored resource merely because a decoder
  could ignore padding. An EOI marker check is not a complete JPEG validity test.
- The API exposes the thumbnail differently across value views: a raw byte string
  versus a binary scalar reference after conversion. Preserve the actual value
  view and bytes; do not infer a universal type from one Perl reference shape.
- Three controlled XMP outputs exercise a label change, a two-entry subject bag,
  language alternatives and a one-hour base-clock conflict. Only base
  `DateTimeOriginal` was copied/shifted; offset/subsecond synchronization remains
  untested. Auxiliary standard XML parsing checked selected values; it is not a
  complete independent-validator evidence run or an embedded-RAW write proof.
- Sixteen normalized/display capture pairs match between ExifTool **13.55** and
  **13.59** after excluding exactly `ExifToolVersion` and `FileAccessDate`.
  Original captures and excluded keys are retained privately. This is equivalence
  for these captures, not for the versions' complete behavior.

The observed EXIF compression label `JPEG (old-style)` and QuickTime sample
`BitDepth=24` describe their particular source structures. Neither establishes
sensor compression mode or RAW sensor precision. Full RAW remains the intended
losslessly compressed camera setting; no sensor data was developed or recompressed.

## Admission and remaining work

Terry authorized reading/copying their supplied images, metadata analysis and
private test derivatives. Rights to publish images or detailed identifying reports
were not granted. Privacy is **restricted**, not cleared: pixels, preview imagery
and opaque contents were not visually inspected. Received RAW copies are read-only;
outputs have separate names. Every derivative retains its parent's restrictions,
hash and recipe lineage. The [provenance policy](../provenance/README.md) applies
separately from the project's locked MIT license.

| Existing gap | What this baseline supplies | What remains |
| --- | --- | --- |
| GAP-001 | Eight admitted full RAW observations and immutable identities | Targeted capture/layout variation and optional-field coverage |
| GAP-005 | Eleven API view captures and three controlled XMP outputs | Exact per-tag interpretation, encoding, time and native model equivalence |
| GAP-007 | Three resource kinds per RAW, exact extraction and nested metadata captures | Other layouts, independent resource validation, privacy completeness and any replacement path |
| GAP-008 | Two pinned acquired references, hashed components, controlled configuration and recorded runs | Replay on another environment and evidence for additional operations |
| GAP-011 | Scoped private reviews for these media and reference components | Any new import or public redistribution requires its own review |

Targeted corpus expansion **#0018** owns the remaining acquisition/read evidence. Embedded
mutation and preservation remain on **#0014**, compatibility coverage on **#0015**,
and actual performance measurements on **#0016**. No C-RAW, DPRAW, malformed input,
other camera, independent sensor decoding or cross-platform behavior is established.
Rust/ADR-0011 was subsequently accepted; native first-slice evidence is separate
from this reference-only report.
