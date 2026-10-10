# RAW first, full parity over time

Agreed direction on **2026-10-10**:

- **Long-term ambition:** full ExifTool feature parity through a modern, friendly tool.
- **Initial delivery scope:** metadata workflows for camera RAW images.
- **First camera/format:** Canon EOS R5 CR3, selected by Terry; other RAW families
  follow after this first milestone. See [the CR3 milestone](canon-eos-r5-cr3.md).
- **Primary capture mode:** full RAW, matching Terry's files. C-RAW remains
  separately tracked secondary coverage.
- **Current project phase:** requirements and features; language, frameworks, and
  implementation dependencies remain undecided.

The narrower first scope follows Terry's actual use of ExifTool. The broader research
is retained so later expansion can reuse what was learned without burdening the
initial product with every supported media type.

## What RAW scope includes

This table defines the RAW roadmap boundary. The first delivered slice is EOS R5
CR3; it does not require implementing every listed RAW family at once.

| Area | Initial scope boundary |
| --- | --- |
| Camera RAW containers | DNG and proprietary formats such as CR2/CR3, NEF/NRW, ARW, RAF, ORF, RW2, and PEF. This list names candidate families, not verified implementation support or a final first-release list. |
| Metadata | Applicable EXIF, GPS, XMP, IPTC, ICC, maker notes, file/container information, and derived values, preserving identity and source provenance. |
| Inspection | Discover tags, select fields, inspect duplicate instances, view raw and interpreted values, export reports, and diagnose metadata problems. |
| Editing | Capability-gated updates, selective removal, copying, synchronization, date shifts, and safe preservation of untouched and rendering-critical data. Support varies by format, tag, and camera variant. |
| XMP sidecars | Read, create, update, copy, and synchronize sidecars associated with RAW files. Define conflicts and correspondence explicitly. |
| Embedded previews | Inspect metadata about thumbnails/previews and extract stored preview bytes where supported. This does not add general standalone JPEG editing or RAW development. |
| Photo workflows | Batch selection, filtering, output formats, renaming/organizing by metadata, geotagging, privacy inspection, and documented removal limits. |
| CLI experience | Discoverable command hierarchy, help at every level, optional cascading interaction, completion, stable scripted output, and useful errors. |

RAW is a family of containers and variants, not a universal file structure. Even
related TIFF-derived formats may differ in maker-note offsets, compression, sensor
layout, and rendering-critical metadata. CR3 needs its own container treatment.
File extensions alone do not establish safe write support. The
[capability research](exiftool-capabilities.md) records upstream distinctions.

The initial safe-write requirements must protect the sensor payload and the metadata
needed to interpret it. A blanket instruction to remove all metadata must not silently
produce a RAW file that no longer renders correctly. The exact refusal and selective
removal UX belongs in the write-safety contract.

## Deferred breadth

Standalone rendered images (including JPEG, PNG, HEIF, and AVIF), video, audio,
documents, archives, and other ExifTool-supported formats belong to the longer-term
roadmap. They are not required to complete the initial RAW milestone. Embedded
content is handled only in the context of its parent RAW workflow.

RAW development, demosaicing, rendering, pixel editing, and converting sensor data
to rendered images are outside the metadata-tool goal. ExifTool parity does not
require building a photo editor or RAW rendering engine.

## What remains to decide

The first camera/format is settled: Canon EOS R5 CR3. Supported capture variants,
read/write depth, detailed workflow ordering, and performance targets still need
requirements evidence and review.
There is no promise that every RAW format ships simultaneously. Publish the coverage
matrix and gaps for each milestone, then broaden deliberately.
