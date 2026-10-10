# First milestone: Canon EOS R5 CR3

Decision date: **2026-10-10**. Terry selected Canon CR3 as the starting format because
his current camera is a Canon EOS R5. This is the first camera/format target within
the RAW-first plan. Full ExifTool feature parity remains the eventual goal. Language
and framework decisions remain deferred.

This is a requirements milestone, not an implemented compatibility claim. Support
for another Canon camera, the EOS R5 Mark II, or another RAW family must be declared
and tested separately. Video and CRM are outside this first milestone.

## Verified format context

Canon documents RAW and Compact RAW (C-RAW) recording for the EOS R5, using `.CR3`
for RAW files. Its Dual Pixel RAW mode adds information that can be used by compatible
processing software. These variants must be distinguished in our evidence; a shared
extension alone is insufficient. [Canon image-quality manual](https://cam.start.canon/en/C003/manual/html/UG-03_Shooting-1_0030.html),
[Canon Dual Pixel RAW documentation](https://support.usa.canon.com/kb/index?id=ART178251&page=content).

ExifTool handles CR3 through its QuickTime-family/ISO BMFF structures and Canon
metadata definitions. The upstream support matrix lists CR3 as readable/writable,
with EXIF and XMP capabilities; that does not make every Canon field writable or
prove that any imageinfo write is safe. [Pinned container documentation](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/TagNames/QuickTime.html),
[Canon tag documentation](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/TagNames/Canon.html),
[upstream support table](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/index.html).

Imageinfo will inspect metadata and extract already stored previews. It will not
develop, demosaic, convert, or recompress sensor pixels. Independent RAW readers may
be used to verify preservation during testing without becoming product features.

## Priority workflows

| Order | Workflow | Acceptance evidence |
| --- | --- | --- |
| 1 | Inspect an EOS R5 CR3 through contextual help and guided discovery. | Camera/model, lens, exposure, capture time, dimensions, orientation, and available Canon-specific fields retain canonical identity, provenance, raw/converted values, and duplicate occurrences. Missing fields are reported honestly. |
| 2 | Export metadata from an EOS R5 collection for scripts. | Stable JSON/JSONL, filename handling, bounded batch traversal, useful diagnostics, and per-file outcomes; malformed inputs do not corrupt the output stream. |
| 3 | Inspect and extract embedded previews/thumbnails. | Enumerate all discovered instances and their container locations; extracted bytes match fixture hashes; no sensor decoding or source changes. |
| 4 | Read/create/edit associated XMP sidecars. | Explicit CR3/XMP pairing, namespace mappings, conflict reporting, preview/apply behavior, backups for existing sidecars, and unchanged CR3 bytes. |
| 5 | Organize and correct RAW metadata workflows. | Planned paired renames, capture-time interpretation/shifts, copyright/ratings/keywords, and GPS inspection/geotagging have typed, reversible behavior in supported destinations. |
| 6 | Enable selected embedded CR3 edits. | Each tag/location/variant passes independent structure validation, readback, payload/private-data preservation, and usable-file checks before being advertised writable. |

The order is proposed sequencing inside the selected milestone. Broad Canon tag
coverage should remain visible in the inventory rather than be reduced to the
familiar fields in the first row. Sidecar editing can ship before embedded editing
without claiming full CR3 mutation parity.

Proposed initial examples:

```text
imageinfo help
imageinfo metadata read help
imageinfo formats show CR3
imageinfo metadata read --values all --output json photo.cr3
imageinfo binary list photo.cr3
imageinfo sidecar create --format xmp --to photo.xmp photo.cr3
```

These commands are not implemented. Under the proposed mutation contract, the
sidecar command previews creation until `--apply` is supplied.

## Corpus and safe-write boundaries

The first fixture plan should include original EOS R5 RAW and C-RAW captures,
Dual Pixel RAW examples where available, relevant firmware/capture settings,
different lenses, portrait/landscape orientation, time/subsecond/offset cases,
embedded-preview layouts, existing/absent XMP, and unknown Canon metadata.
Include truncated, damaged, mismatched-extension, and adversarial-size variants.
No personal camera serial numbers, faces, locations, or photographer details should
enter a public fixture corpus without an explicit provenance/privacy decision.

We have not collected or run those fixtures in this documentation phase. Unknown
variants remain unverified; a later release must state whether it recognizes,
reads, refuses, or safely writes each variant. RAW, C-RAW, and Dual Pixel RAW must
not inherit write support from a single successful sample.

Before embedded writes, prove preservation of all sensor samples, any additional
Dual Pixel data, sample/box references, calibration and rendering-critical metadata,
unknown vendor structures, and unselected embedded previews. Relocating bytes also
requires preserving every affected pointer/reference. Failed preflight must leave
the source unchanged, and interrupted application must leave a recoverable original.

The remaining requirements, CLI semantics, and validation rules apply to this first
target. Other RAW families can reuse the resulting contracts after their own
container, tag, and preservation evidence is available.
