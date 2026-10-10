# EOS R5 CR3 capability inventory v1

Status: **draft for review**, 2026-10-10. This is the deliverable for board card
**#0002, capability-inventory**. Implementation coverage remains zero. No imageinfo
executable, upstream executable experiment, or media-fixture validation is claimed.

## Review entry points

- [Machine-readable inventory](canon-eos-r5-cr3.v1.json): the normative capability,
  option/API mapping, source, variant, dependency, and gap records.
- [JSON Schema](capability-inventory.schema.json): structural contract, version 1.
- [Validation record](validation.md): checks performed on this documentation artifact.
- [Camera milestone](../canon-eos-r5-cr3.md): user-selected EOS R5 full RAW target.
- [Compatibility contract](../compatibility-and-validation.md): evidence required
  before any implemented capability becomes verified.

The inventory contains **49 capability rows, 32 CLI/API family mappings, 12 explicit
audit gaps, and 20 primary-source entries**. These are planning rows, not a count of
supported tags or a denominator for a parity percentage.

The source baseline is ExifTool **13.59**, commit
[2200871d9cef988051d2a99d67df3bda6cbb30a8](https://github.com/exiftool/exiftool/commit/2200871d9cef988051d2a99d67df3bda6cbb30a8).
It is a pinned research snapshot, not a claim about the newest release.
Executable version and hash are deliberately null; runtimeExperiments is false.

## What this card resolves

There is now a concrete format/variant/family/location/operation inventory rather
than a single “CR3 supported” checkbox. It supplies the contracts the metadata model,
fixture plan, CLI walkthroughs, and write-safety work can refine. Each capability
has representative selectors, source-backed reference notes, a proposed result,
acceptance evidence, requirement references, and explicit gaps.

Terry's full RAW captures are primary. C-RAW and Dual Pixel RAW have separate
secondary records; neither gates the first full-RAW read milestone. Associated
XMP is a separate file/variant. Other RAW families remain future expansion.
The artifact selects no implementation language, framework, or runtime dependency.

## CR3 findings that change the requirements

1. **Recognition needs more than the extension or brand.** The upstream `crx `
   brand entry covers CR3 and CRM and uses additional compressor context. Imageinfo
   must distinguish a still image, a video, and an ambiguous/corrupt file. Model and
   capture-mode evidence also need cross-checks; a mutable Model string is not proof
   of write eligibility. [Container source](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/lib/Image/ExifTool/QuickTime.pm)
2. **Canon metadata has multiple locations.** Upstream routes CMT1 to IFD0, CMT2 to
   ExifIFD, CMT3 to Canon maker notes, and CMT4 to GPS. CTMD carries additional records,
   including duplicate capture data. Its embedded extraction is automatic for CR3.
   A CMT-only parser would miss part of the normal read contract.
   [Canon definitions](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/TagNames/Canon.html#CTMD),
   [Canon source](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/lib/Image/ExifTool/Canon.pm)
3. **CR3 time handling has a specific exception.** The pinned container source
   applies UTC conversion when reading CR3 integer time fields even if QuickTimeUTC
   was not enabled. General QuickTime documentation about not assuming UTC is
   insufficient for this format. Keep original values and test controlled host
   timezones separately from EXIF's optional offsets.
   [Time conversion source](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/lib/Image/ExifTool/QuickTime.pm)
4. **A tag name does not imply one resource or one write capability.** THMB,
   PRVW/preview UUID, and JPEG-stream assets need separate extraction evidence.
   Generic writable Composite preview names do not grant CR3 replacement support.
   [CR3 asset definitions](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/lib/Image/ExifTool/QuickTime.pm),
   [Composite definitions](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/TagNames/Composite.html)
5. **Writes need location and preservation gates.** Direct CTMD time/focal/exposure
   fields listed in CAP-036 are read-only in the reference tables. The writer handles
   CMT3 and CTBO references, and CR3 padding can change. “Same file size” and one
   payload hash are inadequate validation. [Canon source](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/lib/Image/ExifTool/Canon.pm),
   [Padding behavior](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/TagNames/QuickTime.html)

The source also places EOS R5/R6 CameraInfo under the CameraInfoR6 table name.
That is a reason to inspect model dispatch, not filter tables by an R5 substring.
Actual field presence and firmware-layout coverage await fixtures.
[CameraInfoR6 table](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/TagNames/Canon.html#CameraInfoR6)

## Inventory contract and measurable states

One capability row represents a subject/location and **one operation**, scoped to
one or more explicit variants. Reading, writing an existing value, creating absent
metadata, deleting a value, preserving other content, and extracting bytes remain
separate claims. `create` never means generating RAW sensor data.

`reference.support` records what the cited upstream material establishes:

| Value | Meaning |
| --- | --- |
| documented | The selected upstream operation is explicitly described or defined; this is not an EOS R5 runtime test. |
| conditional | Support depends on field, layout, options, destination, or other stated conditions. |
| not-supported | The stated operation is not offered by the cited definition/support row; the note bounds that statement. |
| unresolved | This investigation cannot yet establish the operation's behavior or preservation. |
| not-applicable | The operation does not apply to this row; requires a reason. |

`status` records imageinfo progress, independently of reference support:

| Value | Entry criterion |
| --- | --- |
| unresearched | A named gap exists but source or target behavior is not sufficiently characterized. |
| specified | Source basis/uncertainty, target behavior, acceptance criteria, and follow-up gaps are recorded. All current rows are here. |
| implemented | An implementation exists and links to its revision; conformance is not yet established. |
| verified | Runtime evidence identifies fixture, artifact, result and reference hash; required preservation/independent checks pass for the exact claimed subset. |
| limited | A supported subset and the reason/affected variants/remaining evidence are explicitly bounded. |
| not-applicable | A justified exclusion for the operation, not a shortcut for missing implementation. |

A reference `not-supported` row can still be `specified`: correctly refusing an
unsupported edit is a specified imageinfo behavior. Source-only `documented`
is never promoted to runtime `verified`.
Priorities P0/P1/P2 have the meanings in [product requirements](../product-requirements.md),
not the local board's urgency labels.

The JSON Schema rejects unknown fields, malformed IDs, invalid states and ungrounded
`verified` rows without evidence or a hashed executable baseline. Schema validation
cannot prove the truth/sufficiency of evidence, unique IDs across distinct objects,
reference integrity, dependency acyclicity, or source applicability. Those semantic
checks are also mandatory and are recorded in [validation](validation.md).

`dependsOn` describes capability-specification/delivery ordering, not an instruction
to call another operation at runtime. A sidecar workflow may be delivered before
embedded RAW mutation; the latter depends on CAP-038 preservation evidence. A refusal
case can be tested without implementing a successful writer.

## Capability index

The JSON contains the actual target behavior, selectors, source constraints and
acceptance criteria for each row. This table is a navigation summary.

| ID | Capability | Operation | Milestone | Reference basis |
| --- | --- | --- | --- | --- |
| CAP-001 | Recognize a CR3 still container | recognize | read-foundation | conditional |
| CAP-002 | Identify EOS R5 and full RAW evidence | recognize | read-foundation | conditional |
| CAP-003 | Read descriptive EXIF | read | read-foundation | documented |
| CAP-004 | Read capture and lens EXIF | read | read-foundation | documented |
| CAP-005 | Read optional GPS metadata | read | read-foundation | conditional |
| CAP-006 | Read Canon capture and lens subtables | read | read-foundation | conditional |
| CAP-007 | Read R5-specific CameraInfo fields | read | read-foundation | conditional |
| CAP-008 | Read Canon timed metadata | read | read-foundation | documented |
| CAP-009 | Interpret CR3 container times | read | read-foundation | conditional |
| CAP-010 | Expose all value layers | read | read-foundation | documented |
| CAP-011 | Read embedded XMP | read | read-foundation | conditional |
| CAP-012 | Read associated sidecar XMP | read | read-foundation | documented |
| CAP-013 | Retain duplicate and document identity | read | read-foundation | documented |
| CAP-014 | Inspect unknown metadata conservatively | read | read-foundation | conditional |
| CAP-015 | Extract Canon thumbnail | extract | read-foundation | documented |
| CAP-016 | Extract Canon preview | extract | read-foundation | documented |
| CAP-017 | Extract JPEG-track preview | extract | read-foundation | conditional |
| CAP-018 | Inspect metadata inside extracted preview assets | read | advanced-workflows | unresolved |
| CAP-019 | Derive composite photo values | derive | read-foundation | conditional |
| CAP-020 | Create associated XMP sidecar | create | sidecar-workflows | documented |
| CAP-021 | Edit associated XMP values | write | sidecar-workflows | documented |
| CAP-022 | Delete selected sidecar metadata | delete | sidecar-workflows | conditional |
| CAP-023 | Preserve sidecar information and CR3 pairing | preserve | sidecar-workflows | unresolved |
| CAP-024 | Copy RAW metadata into mapped XMP | copy | sidecar-workflows | conditional |
| CAP-025 | Reconcile RAW and sidecar values | sync | advanced-workflows | conditional |
| CAP-026 | Update selected embedded EXIF fields | write | embedded-write | conditional |
| CAP-027 | Create absent embedded EXIF fields | create | embedded-write | conditional |
| CAP-028 | Delete selected embedded EXIF fields | delete | embedded-write | conditional |
| CAP-029 | Update existing GPS coordinates | write | embedded-write | conditional |
| CAP-030 | Create absent GPS metadata | create | embedded-write | conditional |
| CAP-031 | Remove selected embedded location metadata | delete | embedded-write | conditional |
| CAP-032 | Update embedded XMP | write | embedded-write | conditional |
| CAP-033 | Create absent embedded XMP | create | embedded-write | conditional |
| CAP-034 | Delete selected embedded XMP | delete | embedded-write | conditional |
| CAP-035 | Gate Canon maker-note edits | write | embedded-write | conditional |
| CAP-036 | Refuse unsupported CTMD field edits | write | embedded-write | not-supported |
| CAP-037 | Gate embedded preview replacement | write | advanced-workflows | unresolved |
| CAP-038 | Preserve sensor samples and opaque structure | preserve | embedded-write | unresolved |
| CAP-039 | Export occurrence-aware reports | export | read-foundation | conditional |
| CAP-040 | Import explicit metadata changes | import | advanced-workflows | conditional |
| CAP-041 | Compare metadata across RAW/XMP sources | diff | sidecar-workflows | documented |
| CAP-042 | Shift and format capture timestamps | transform | advanced-workflows | conditional |
| CAP-043 | Geotag from auxiliary tracks | transform | advanced-workflows | conditional |
| CAP-044 | Organize files and paired sidecars | organize | advanced-workflows | conditional |
| CAP-045 | Validate and inspect privacy limits | validate | advanced-workflows | conditional |
| CAP-046 | Process ordered persistent requests | process | advanced-workflows | documented |
| CAP-047 | Track C-RAW separately | read | secondary-variants | conditional |
| CAP-048 | Protect additional Dual Pixel RAW data | preserve | secondary-variants | unresolved |
| CAP-049 | Record absent general IPTC/ICC CR3 support | create | embedded-write | not-supported |

## CLI/API mapping index

Each JSON mapping names the upstream forms, the proposed native surface, its
compatibility disposition, an acceptance condition, and remaining audit gaps.
`equivalent-proposed` describes intended function, not implemented compatibility.
`difference-proposed` records deliberate UX/data/safety changes for review.
`open-gap` preserves an unresolved part of the RAW parity surface.

This is a **family-level** map. It does not claim every flag, API option, abbreviation,
ordering interaction, configuration callback, or report template has been audited.
That detailed work belongs to GAP-006/card #0007. A friendlier native CLI can change
spelling while the later full-parity ledger still accounts for every use case.

| ID | Family | Disposition |
| --- | --- | --- |
| MAP-001 | CLI: Capability discovery | difference-proposed |
| MAP-002 | CLI: Tag inclusion, exclusion and groups | equivalent-proposed |
| MAP-003 | CLI: Duplicates, families and ordering | difference-proposed |
| MAP-004 | CLI: Value layers and display conversion | difference-proposed |
| MAP-005 | CLI: Structured XMP | equivalent-proposed |
| MAP-006 | CLI: Binary extraction and routing | difference-proposed |
| MAP-007 | CLI: Human and machine reports | difference-proposed |
| MAP-008 | CLI: Advanced report and serialization forms | open-gap |
| MAP-009 | CLI: Assignment, lists and file-sourced values | difference-proposed |
| MAP-010 | CLI: Tag/group deletion | difference-proposed |
| MAP-011 | CLI: Creation and update modes | equivalent-proposed |
| MAP-012 | CLI: Copy and redirection | difference-proposed |
| MAP-013 | CLI: JSON/CSV imports | difference-proposed |
| MAP-014 | CLI: Sidecar association and metadata mapping | difference-proposed |
| MAP-015 | CLI: Input traversal and filtering | difference-proposed |
| MAP-016 | CLI: Fast, unknown and embedded extraction | difference-proposed |
| MAP-017 | CLI: Filesystem and date organization | difference-proposed |
| MAP-018 | CLI: Date shifts | equivalent-proposed |
| MAP-019 | CLI: Geotagging and clock correction | equivalent-proposed |
| MAP-020 | CLI: Geolocation lookup and inverse export | open-gap |
| MAP-021 | CLI: Backups, overwrite and output policy | difference-proposed |
| MAP-022 | CLI: Diagnostics and repair controls | difference-proposed |
| MAP-023 | CLI: Ordered and persistent execution | difference-proposed |
| MAP-024 | CLI: Argument/request files and filenames | difference-proposed |
| MAP-025 | CLI: Warnings, progress and status | difference-proposed |
| MAP-026 | CLI: Custom definitions and expressions | open-gap |
| MAP-027 | API: Extraction lifecycle | equivalent-proposed |
| MAP-028 | API: Identity and values | equivalent-proposed |
| MAP-029 | API: Queued mutation lifetime | difference-proposed |
| MAP-030 | API: Copy/mapping lifecycle | equivalent-proposed |
| MAP-031 | API: Static discovery versus detection | difference-proposed |
| MAP-032 | API: Option families | open-gap |

## Remaining audit and ownership

No gaps below block handing off this *inventory specification*. They block later
implementation, runtime verification, or broader compatibility claims as described
in the JSON. Do not close them merely because a source contains a similarly named tag.

| ID | Gap | Follow-up card | Closes when |
| --- | --- | --- | --- |
| GAP-001 | EOS R5 fixture observations | `fixture-plan` | A provenance-approved full RAW corpus records camera/firmware/mode, discovered structures, optional-tag presence and source hashes. |
| GAP-002 | Camera mode and damaged-file discrimination | `capability-inventory` | Cross-check brand, Canon model, Quality and structural clues on full RAW/C-RAW/DPRAW and negative CRM/other-camera cases; record ambiguity rules. |
| GAP-003 | Tag-level and mutation-depth expansion | `capability-inventory` | Expand representative families into occurrence/tag/location rows; audit insertion/deletion flags, defaults and all relevant maker-note subtables without copying upstream tables. |
| GAP-004 | Saved plans and preservation oracle | `write-safety-contract` | Specify per-file and paired-sidecar outcomes; validate all sensor samples, references, calibration/opaque blocks and interruption recovery. |
| GAP-005 | Metadata identity and conversions | `metadata-contract` | Specify groups/instances, rational and raw values, XMP shape, encodings, CR3 UTC/Exif time distinctions and conflict handling. |
| GAP-006 | Legacy argument and API completeness | `legacy-compatibility` | Expand family mapping to every in-scope flag/API option, ordering interaction and executable extension; assign equivalence or an accepted difference. |
| GAP-007 | Preview variants and nested metadata | `fixture-plan` | Enumerate THMB, PRVW and JPEG-track assets per full RAW fixture; prove bytes and nested metadata coverage; audit any replacement path separately. |
| GAP-008 | Repeatable runtime reference | `fixture-plan` | Choose an executable distribution, hash it and its configuration/dependencies, then run recorded experiments in controlled locale/timezone environments. |
| GAP-009 | Privacy and sidecar synchronization policy | `write-safety-contract` | Define explicit destinations, pairing, mappings, residual/uninspectable data, and rendering-critical retention for each named profile. |
| GAP-010 | Secondary and later format breadth | `capability-inventory` | Scope and collect independent evidence for C-RAW/DPRAW, other Canon cameras and later RAW families before adding their capabilities. |
| GAP-011 | Asset licensing and provenance | `license-provenance` | Apply the selected MIT project license while preserving and reviewing separate source/table/fixture terms before importing third-party assets. |
| GAP-012 | CLI workflows and large-input boundaries | `cli-walkthroughs` | Walk through canonical command grammar, non-TTY/help behavior, selection, source/destination effects and failure output; define bounded processing. |

The next dependent work should turn these rows into the metadata contract and fixture
plan, then refine the CLI and safe-write contracts against those concrete cases.
This card does not complete those follow-up cards or authorize language selection.

## Sources and provenance

All ExifTool file sources below use the same immutable commit. The data records
independent requirements and selected factual identifiers; no upstream implementation,
complete tag table, or media fixture is imported. Terry selected MIT for imageinfo on
card #0010; that choice does not change third-party material's terms. GAP-011 remains
the artifact-specific provenance follow-up.

| Source ID | Primary source | Reviewed scope |
| --- | --- | --- |
| `support` | [Upstream support and writer limitations](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/index.html) | CR3 row; writer limitations |
| `canon` | [Canon metadata tables](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/TagNames/Canon.html) | uuid, CTMD, CameraSettings, CameraInfoR6, CanonModelID |
| `canon-source` | [Canon reader/writer definitions](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/lib/Image/ExifTool/Canon.pm) | Canon::uuid CMT1-4, CTBO, THMB; Canon::CTMD; ProcessCMT3 |
| `quicktime` | [QuickTime metadata tables](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/TagNames/QuickTime.html) | CR3 padding; Stream CTMD and JpgFromRaw; uuid |
| `quicktime-source` | [QuickTime container implementation](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/lib/Image/ExifTool/QuickTime.pm) | ftypLookup crx; timeInfo CR3 conversion; Canon uuid preview; JPEGInfo |
| `exif` | [EXIF definitions](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/TagNames/EXIF.html) | IFD0/ExifIFD fields; writable/protected/mandatory flags |
| `gps` | [GPS definitions](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/TagNames/GPS.html) | coordinate/reference fields; GPSVersionID |
| `xmp` | [XMP definitions](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/TagNames/XMP.html) | dc, xmp, exif schemas and list/language/structure types |
| `structures` | [Structured XMP](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/struct.html) | read/copy/write structure and flattened-field behavior |
| `sidecars` | [Metadata sidecars](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/metafiles.html) | XMP creation, mapping, application |
| `cli` | [Application manual](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/exiftool_pod.html) | tag operations; input/output; processing; other options; special features; exit status |
| `api` | [Library API](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/lib/Image/ExifTool.pod) | ImageInfo, ExtractInfo, GetInfo, GetValue, SetNewValue, WriteInfo, options and static discovery |
| `values` | [Information and conversion flow](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/under.html) | Raw, ValueConv, PrintConv; read/write flow |
| `composite` | [Composite definitions](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/TagNames/Composite.html) | derived values; preview extraction/replacement distinctions |
| `files` | [Filename workflows](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/filename.html) | FileName, Directory, TestName, formatting and collisions |
| `geo` | [Geotagging](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/geotag.html) | track interpolation, Geotime, Geosync |
| `extra` | [Filesystem and extra tags](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/TagNames/Extra.html) | System, warnings, validation, ImageDataHash |
| `config` | [Configuration examples](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/config_files/example.config) | custom tags, composites, executable callbacks |
| `canon-modes` | [Canon EOS R5 capture modes](https://cam.start.canon/en/C003/manual/html/UG-03_Shooting-1_0030.html) | RAW and Compact RAW; CR3 naming |
| `canon-dpraw` | [Canon EOS R5 Dual Pixel RAW](https://support.usa.canon.com/kb/index?id=ART178251&page=content) | Additional dual pixel sensor information and recording mode |

## Versioning and maintenance

`schemaVersion` changes when the structure or state meanings become incompatible.
`inventoryVersion` changes for every published inventory revision. Stable CAP/MAP/GAP
IDs are never reused; splitting a row needs documented successor IDs and retained
history. Changing the upstream source baseline is an explicit revision, with changed
findings and newly required experiments identified.

For this initial draft, keeping a single active JSON inventory and Git history is
sufficient. Do not silently overwrite runtime evidence when a new oracle disagrees.
Future fixture/tag-level expansion should refine these family rows, not claim that
49 planning rows represent all EOS R5 metadata.
