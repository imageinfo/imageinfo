# ExifTool capability research

Research date: **2026-10-10**. Status: research and proposed requirements; imageinfo has no implementation claim in this document. Language, libraries, packaging, and frameworks remain undecided.

**Initial delivery scope: camera RAW still images only. Long-term goal: full ExifTool functional parity.** The initial target is ExifTool-like metadata inspection, supported editing, copying, date/location operations, file organization, embedded-preview extraction, and XMP sidecar workflows for camera RAW files. RAW development, demosaicing, pixel editing, and format conversion are outside this metadata project's scope. Standalone JPEG/PNG/HEIC, video, audio, documents, and archives are researched as background for the eventual parity roadmap; they are outside initial delivery. A JPEG extracted from a RAW file is an output artifact, not an initial commitment to a general JPEG editor.

All active imageinfo proposals below apply to camera RAW files and their supporting metadata artifacts. Sections explicitly labeled background describe ExifTool's broader ecosystem for later parity work and do not expand initial delivery.

This survey uses the upstream ExifTool project, pinned to source revision `2200871d9cef988051d2a99d67df3bda6cbb30a8`. Direct requests to exiftool.org returned HTTP 403 during research, so citations generally point to the official project's documentation and source on GitHub. The observed source declares **13.59**, and its home-page source labels that release **May 27, 2026**. These observations identify the material consulted, rather than establish that every distribution channel is current. Future compatibility runs must record an exact ExifTool binary version and source revision. [Version declaration](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/lib/Image/ExifTool.pm), [upstream home-page source](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/index.html)

## What ExifTool parity means within the initial camera RAW scope

The proposed parity target should be a collection of observable contracts:

1. Recognize containers and find metadata blocks, including unusual placements and embedded documents.
2. Decode known tags and preserve unknown data with its provenance.
3. Expose faithful values and useful human descriptions.
4. Perform supported changes without damaging media or unrelated metadata.
5. Support the workflows built on those operations: export, import, copying, sidecars, synchronization, dates, location, file organization, and automation.
6. Provide clear capability discovery, diagnostics, and documentation.

This is broader than an EXIF parser. Each RAW format, metadata family, operation, and vendor/model variant needs a separate compatibility status. Matching a familiar sample does not establish write safety across other camera models or compression variants.

## Verified: camera RAW support is a matrix

The upstream table records these support levels. R = read, W = write, C = create metadata; a dash means no listed support. The ICC column refers to whole-block operations. These are **ExifTool's** capabilities, not implemented imageinfo support. [Pinned support matrix](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/index.html#supported)

| RAW type | Container family | Overall | EXIF | IPTC | XMP | ICC |
| --- | --- | --- | --- | --- | --- | --- |
| DNG | TIFF | R/W | R/W/C | R/W/C | R/W/C | R/W/C |
| CR2 | TIFF | R/W | R/W/C | R/W/C | R/W/C | R/W/C |
| CR3 | QuickTime | R/W | R/W/C | — | R/W/C | — |
| NEF | TIFF | R/W | R/W/C | R/W/C | R/W/C | R/W/C |
| NRW | TIFF | R/W | R/W/C | R/W/C | R/W/C | R/W/C |
| ARW/ARQ | TIFF | R/W | R/W/C | R/W/C | R/W/C | R/W/C |
| RAF | FujiFilm | R/W | R/W/C | R/W/C | R/W/C | R/W/C |
| ORF/ORI | TIFF | R/W | R/W/C | R/W/C | R/W/C | R/W/C |
| RW2/Panasonic RAW | TIFF | R/W | R/W/C | R/W/C | R/W/C | R/W/C |
| PEF | TIFF | R/W | R/W/C | R/W/C | R/W/C | R/W/C |
| IIQ | TIFF | R/W | R/W/C | R/W/C | R/W/C | R/W/C |
| X3F | Sigma/Foveon | R/W | R/W/C | R/W/C | R/W/C | R/W/C |
| MRW | Minolta | R/W | R/W/C | R/W/C | R/W/C | R/W/C |
| SRW | TIFF | R/W | R/W/C | R/W/C | R/W/C | R/W/C |
| CRW/CIFF | CIFF | R/W | — | — | R/W/C | — |
| 3FR | TIFF | R | R | R | R | R |
| DCR/KDC | TIFF | R | R | R | R | R |
| SRF | TIFF | R | R | R | R | R |

This table cannot answer whether an individual vendor field is writable or whether a specific camera's file can safely be rewritten. The .RAW extension is ambiguous: the upstream table separately identifies Kyocera RAW as read-only and Panasonic RAW as read/write. Recognition must inspect content.

### RAW-specific priorities and preservation

ExifTool's writer-limitations section explicitly warns that removing all metadata from RAW images can remove proprietary information needed for rendering. [RAW deletion limitation](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/index.html#limitations)

**Proposed active requirements:**

- Preserve sensor payloads, calibration/rendering data, offsets, vendor blocks, and unfamiliar records during ordinary edits.
- Make selective privacy edits explicit; do not offer a blanket RAW metadata wipe as if it were a safe equivalent to removing captions.
- Support XMP sidecar creation, inspection, updates, copying, and conflict reporting without requiring modification of the RAW file.
- Inventory ThumbnailImage, PreviewImage, JpgFromRaw, and other embedded assets per format/model. Extraction should return existing bytes, with dimensions/type/provenance where available. It should not develop a new image from sensor data.
- Distinguish extracting an embedded image, replacing an existing one, and creating/deleting one. ExifTool's composite tables document different limits for these operations. [Embedded-image composites](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/TagNames/Composite.html)
- Include DNG's specialized structures and optional original-RAW information in the inventory; these are separate from ordinary capture tags. [DNG structures](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/TagNames/DNG.html)
- Test metadata writes by camera model and file variant, and retain originals until preservation and third-party readability are demonstrated.

## Background: ExifTool's broader support matrix

ExifTool distinguishes reading, writing existing information, creating metadata, and sometimes deletion. Container support does not imply that every tag is writable or that new media files can be created. Representative entries from the upstream support table are below; its footnotes remain authoritative. [Supported-format matrix](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/index.html#supported)

| Container | Overall support | Important distinction |
| --- | --- | --- |
| JPEG, TIFF | Read/write | EXIF, IPTC, XMP, and ICC metadata support creation. |
| PNG | Read/write | Native and legacy/nonstandard metadata placements coexist. |
| HEIC/HEIF | Read/write | EXIF/XMP creation; ICC read/write; no IPTC entry. |
| CR3 | Read/write | EXIF/XMP creation; Canon/QuickTime metadata support differs. |
| Hasselblad 3FR | Read | RAW support is not uniformly writable. |
| MP4 | Read/write | XMP/QuickTime creation; EXIF/IPTC entries are nonstandard. |
| MP3 | Read | Reading ID3 does not imply editing it. |
| ICC/ICM | Read/write/create | Whole-profile operations, not arbitrary field editing. |
| ZIP | Read | Archive inspection is not archive rewriting. |

**Proposed imageinfo requirement:** a query such as “can this file receive this tag here?” must answer more precisely than “format supported.” Capability records should distinguish read, update, create, delete, whole-block replacement, constraints, and verified fixture coverage. Unknown and unsupported cases must remain visible.

## Verified: metadata families and their limits

### EXIF, TIFF, GPS, and specialized TIFF metadata

EXIF uses TIFF-style Image File Directories. ExifTool's specific-location groups include IFD0, ExifIFD, GPS, and other directories. The EXIF table also covers coexisting TIFF/DNG fields. It distinguishes writable types, mandatory fields, protected fields, and fields unsafe for general copying. Creating or removing directories can add or remove mandatory defaults. Its current documentation points to EXIF 3.1. [EXIF tag tables](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/TagNames/EXIF.html)

GPS values include coordinates, reference hemispheres, units, altitude reference, and separate date/time components. ExifTool automatically supplies GPSVersionID when creating a GPS directory. [GPS tag table](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/TagNames/GPS.html)

**Proposed imageinfo requirement:** retain the original storage type, directory path, byte order, exact rational components, and relationships among coordinate/reference fields. Validate changes as a related set. Orientation editing must be described as a metadata operation; a separate media transform would require its own specification.

### IPTC IIM and XMP

ExifTool's IPTC table describes the older IIM record/dataset format; IPTC Core uses XMP. IIM fields have length constraints, and ExifTool can truncate excessive values with a minor warning. Character-set handling, repeating fields, and fixed-format dates deserve explicit compatibility cases. [IPTC tables](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/TagNames/IPTC.html)

XMP has namespaces, typed properties, arrays, structures, and language alternatives. Writing a language-alternative property without a suffix targets x-default and deletes other languages; explicitly choosing x-default preserves them. [XMP tables and language behavior](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/TagNames/XMP.html)

ExifTool normally presents XMP structures as flattened tags, while copying preserves structures by default. Explicit flattened-field copying and `-struct`/`--struct` have different rules. Structure field order is insignificant, whereas array order is preserved. Some field-conversion failures can leave other fields written and issue a warning. [Structured-information guide](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/struct.html)

**Proposed imageinfo requirement:** preserve namespace identity, array kind and ordering, nested objects, language maps, and unknown properties. Editing one language should have an explicit merge/replace policy. Previews should show structure-level consequences and partial conversion failures before applying a change.

### ICC profiles, Photoshop resources, and binary blocks

ExifTool reads profile fields but does not individually write the ICC table's tags. The complete ICC_Profile block must be requested explicitly for extraction or writing. [ICC profile tables](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/TagNames/ICC_Profile.html)

JPEG metadata spans marker segments rather than a single header: EXIF/XMP, profiles, Photoshop resources, vendor data, comments, previews, and other records have separate identities. ExifTool's JPEG tag tables also expose encoding parameters. [JPEG tables](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/TagNames/JPEG.html)

**Proposed imageinfo requirement:** differentiate decoded-field operations from byte-exact block extraction/replacement. “Set a profile” should identify its effect on color interpretation. Binary values need byte length, digest, media type where known, and an explicit output destination; large payloads should not be silently coerced to text.

### Maker notes and proprietary camera metadata

The Canon tables include nested settings and shot-information tables alongside writable strings such as OwnerName and read-only entries. Nikon likewise has typed vendor fields and many nested version-dependent records. Their differing structures demonstrate why “MakerNotes supported” is too coarse. [Canon tables](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/TagNames/Canon.html), [Nikon tables](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/TagNames/Nikon.html)

**Proposed imageinfo requirement:** inventory vendor/model/version variants independently. Preserve opaque blocks unless a change has verified relocation and offset behavior. Treat creating, transplanting, and editing maker notes as separate capabilities. Add real-camera regression samples and vendor-application compatibility observations without promising that all vendor software accepts every rewrite.

### Background: video, audio, tracks, and timed metadata

The CR3 container shares machinery with this family, so its container/tag-location details inform RAW work. Standalone media and timed-video extraction are outside imageinfo's active scope.

QuickTime-based formats include MOV/MP4 and image containers such as HEIC/CR3. New QuickTime metadata normally prefers ItemList, then UserData, then Keys. Writing video metadata can create both QuickTime and XMP tags unless a group restricts the operation. Some track-specific Keys fields are writable. Duplicate IDs and language variants matter.

Integer QuickTime times are specified as UTC, but cameras often store local values; ExifTool therefore does not assume UTC unless QuickTimeUTC is enabled. String dates have separate timezone behavior. Timed metadata extraction exposes GPS and sensor records. [QuickTime behavior and tables](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/TagNames/QuickTime.html)

ID3 contains multiple versions and language-specific fields; the tag tables describe extraction of audio metadata independently of write capabilities. [ID3 tables](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/TagNames/ID3.html)

**Proposed RAW requirement:** preserve CR3 container/location identity and distinguish UTC, assumed-local, explicit-offset, and unknown-zone date states where relevant. Report any camera-specific interpretation. Timed video processing remains background.

### Background: documents, archives, and non-image files

These standalone formats are outside initial delivery and belong to eventual parity research. JUMBF/provenance concepts remain relevant where found inside an in-scope RAW container.

PDF supports native and XMP metadata plus password-protected processing. ExifTool uses reversible incremental updates; earlier metadata remains in the file after editing, and linearization is lost. Deleting the PDF-update pseudo-group restores its changes. [PDF update behavior](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/TagNames/PDF.html)

ZIP inspection includes additional metadata in selected ZIP-based packages. OOXML extraction reads properties from the docProps XML files, including properties beyond the table's named examples. [ZIP tables](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/TagNames/ZIP.html), [OOXML tables](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/TagNames/OOXML.html)

C2PA/JUMBF is a separate structured metadata family; tag extraction should not be confused with cryptographic authenticity verification. The observed upstream support matrix describes C2PA as readable and deletable in some containers, not writable. [JUMBF tables](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/TagNames/Jpeg2000.html), [C2PA support statement](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/index.html#supported)

**Background design lessons:** logical deletion differs from irreversible sanitization; archive scanning needs expansion limits; provenance-manifest parsing differs from validation/signing. No PDF, archive, or signing implementation is proposed for the active RAW scope. RAW privacy reports should enumerate the fields changed and the bytes preserved.

### Background: PNG illustrates ecosystem-specific behavior

ExifTool preserves bytes after IEND unless the trailer is explicitly deleted. It moves text chunks before IDAT for compatibility with applications that otherwise miss metadata. PNG CRC checking also varies by operation/options. [PNG interoperability behavior](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/TagNames/PNG.html)

**Lesson applicable to RAW:** write specifications need both format validity and ecosystem compatibility. Preserve unfamiliar bytes by default, expose their existence, and require an explicit deletion intent. PNG processing itself is outside initial delivery.

## Verified: values, duplicates, and provenance

The API distinguishes human-readable PrintConv, machine-oriented ValueConv, decoded Raw, saved binary, and exact Rational representations. ExifTool has group families for information type, location, category, document, instance, metadata path, EXIF/TIFF format, tag ID, and alternate input file. [Value layers and group families](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/ExifTool.html#GetValue)

Default extraction suppresses duplicate tags. A broad group selection such as EXIF:all can therefore miss values hidden by duplicates unless duplicate extraction is enabled. A bare tag name also behaves differently when writing: same-named tags in multiple groups can be affected. [Common mistakes](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/mistakes.html)

Composite tags derive values from other fields. Most are changed by editing their source fields, although some composites, including certain date and embedded-image fields, are writable. Updating an existing preview does not imply creation or deletion support. [Composite tables](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/TagNames/Composite.html)

**Proposed imageinfo requirement:** represent metadata as records with identity and provenance, then build optional simplified views. A displayed “capture date” should show its source and conflict policy. Keep stored, decoded, normalized, and formatted values separate; distinguish a missing field from a failed conversion. Derived fields should expose their dependencies.

## Verified: workflows beyond tag inspection

### Copying, mappings, synchronization, and sidecars

ExifTool's sidecar guide distinguishes copying same-named fields into preferred XMP locations from copying existing XMP. It documents cross-family conversion through mapping argument files and metadata-only backups in EXIF, MIE, EXV, ICC, and VRD. Those metadata formats are the files ExifTool can create from scratch. ExifTool XML is also a metadata sidecar representation, with different semantics from native XMP. [Sidecar guide](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/metafiles.html)

MWG composite fields reconcile overlapping EXIF, IPTC, and XMP on reading and synchronize associated tags on writing. IPTC is written only when already present; digest updates depend on the prior consistency state. Loading MWG changes behavior and is an explicit feature. [MWG behavior](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/TagNames/MWG.html)

**Proposed imageinfo requirement:** separate same-name copying, schema mapping, synchronization, and byte-exact backup. Each mapping should document units, character encodings, precision, missing values, and conflicts. Sidecar association needs collision and missing-sidecar policies, rather than assuming filename stems are unique.

### Geotagging and geolocation

ExifTool interpolates positions from GPS tracks using an image time. Geosync supports constant offsets and multiple synchronization points for clock-drift correction. Its scalar offset is seconds, unlike the usual date-time shift shorthand. The default image time prefers SubSecDateTimeOriginal, then DateTimeOriginal. Its guide also covers generating track logs from geotagged images. [Geotagging guide](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/geotag.html)

Geolocation derives city, region, subregion, and country from coordinates, and supports the reverse direction, using a bundled city database and optional extended data. [Geolocation guide](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/geolocation.html)

**Proposed imageinfo requirement:** publish supported track formats and interpolation/extrapolation limits. A plan should show track coverage, timezone assumptions, clock corrections, and selected fixes. Record database provenance/version and distinguish nearest-city lookup from precise address geocoding.

### Date repair and file organization

Date shifting accepts date-only, time-only, combined, and timezone forms. Calendar shifts around month boundaries require special treatment to keep related timestamps relatively aligned. [Time-shift semantics](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/Shift.html)

FileName and Directory operations rename/move files, while TestName provides a rename preview. Filename templates expose original directory, stem, extension, and collision copy numbers; date templates add another formatting layer. [File organization guide](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/filename.html)

**Proposed imageinfo requirement:** offer explicit duration, calendar, offset, and clock-correction operations. File organization needs a complete collision-aware plan, a report of each result, and recovery information. Path planning must consider case-insensitive filesystems, illegal characters, long paths, and multiple files targeting the same name.

## Proposed active RAW scope ledger

The following capabilities belong in the RAW parity backlog even when their delivery is deferred. They apply to camera RAW files, embedded previews, and associated sidecars/metadata artifacts:

| Area | Required coverage before claiming parity |
| --- | --- |
| Discovery | Formats, tags, groups, writable types, delete groups, aliases, languages, custom definitions |
| Reading | RAW container sniffing, duplicate records, unknown fields, embedded assets, partial-file diagnostics |
| Mutation | Typed assignments, lists, structures, language alternatives, groups/blocks, preservation constraints |
| Transfer | RAW/sidecar copy, redirect, additive copy, mappings, MWG, XMP sidecars, metadata backups |
| Output | Human views, JSON, CSV, XML, HTML, tables, templates, binary extraction, PHP/SVG legacy surfaces |
| Automation | Recursive selection, conditions, ordering, argument files, persistent process, library use |
| Analysis | Metadata diff, validation, verbose/hex inspection, payload hashes, performance tradeoffs |
| Filesystem | Rename, move, copy/output routing, timestamps, backup/restore, attributes where supported |
| Location/time | Tracks, drift, reverse track generation, geolocation, timezone/calendar handling |
| Extensibility | Custom tags, aliases, composites, defaults, tag translations, mapping definitions |

No fixed tag or format count is a sufficient acceptance target: upstream data and newly discovered camera variants will continue changing. The next research artifact should be a machine-readable, revision-pinned RAW capability inventory linked to fixtures, with states such as investigated, unsupported, implemented, and verified. The state must remain honest while broad RAW parity is developed.

## Long-term full-parity reference

The eventual goal retains ExifTool's full functional breadth: standalone raster/image containers, video/audio and timed metadata, documents, archives, metadata-only formats, vendor variants, all supported mutation/transfer workflows, integrations, and output surfaces. The background sections above provide starting evidence for that roadmap. Initial delivery must publish its RAW-only support honestly and keep deferred capabilities visible, rather than implying that the long-term goal has already been reached.
