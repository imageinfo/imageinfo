# ExifTool CLI semantics and compatibility traps

Research date: **2026-10-10**. This document records the observed upstream **13.59** source/documentation at revision `2200871d9cef988051d2a99d67df3bda6cbb30a8` and proposed imageinfo behavior. It does not select an implementation language or promise that any command exists in imageinfo. See [the capability survey](exiftool-capabilities.md) for container and metadata-family coverage.

**Initial delivery: metadata workflows for camera RAW still images, their embedded previews, and associated XMP sidecars/supporting metadata artifacts. Long-term goal: full ExifTool functional parity.** RAW developing, pixel transforms, and conversion are outside this metadata project's scope. Standalone JPEG/PNG/HEIC, video, audio, documents, and archives are outside initial delivery. References to those formats below are background lessons for eventual parity work.

“Workalike” needs two decisions kept separate: equivalent metadata workflows, and acceptance of ExifTool's existing argument grammar. RAW workflow parity is the initial target, followed by eventual full functional parity. Byte-for-byte CLI compatibility, including abbreviations and legacy option interactions, remains a proposed compatibility surface to specify explicitly.

## Verified: the grammar encodes operations

ExifTool reads by default; assignments, copying, geotagging, and JSON/CSV imports switch it into writing. Its value pipeline separates stored binary, decoded raw, normalized machine values, and human display conversions. `-n` disables PrintConv; it does **not** universally expose the exact stored bytes. Per-tag `#` selects the machine-value layer. [Operation and conversion model](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/under.html)

The principal operation forms are:

| ExifTool form | Meaning to preserve |
| --- | --- |
| `-TAG` | Select a field for reading. |
| `--TAG` / `-x TAG` | Exclude a field. |
| `-GROUP:TAG` | Qualify metadata identity/location. |
| `-TAG=VALUE` | Assign a value. |
| `-TAG=` | Delete the field. |
| `-TAG+=VALUE` / `-TAG-=VALUE` | Type-dependent list editing, conditional removal, or time shift. |
| `-TAG<=FILE` | Read the value payload from a file. |
| `-DEST<SOURCE` | Copy/redirect a field. |
| `-tagsFromFile FILE` | Establish a metadata-copy source. |
| `-tagsFromFile @` | Use each input itself as the copy source. |

These forms, plus wildcard and group selection, are documented in the [application manual](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/exiftool_pod.html#Tag-operations). Shell quotation is part of reliable use: angle brackets, wildcards, and dollar signs can be interpreted before ExifTool receives them. [Common redirection mistakes](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/mistakes.html#M5)

**Proposed imageinfo behavior:** expose explicit read, set, delete, copy, list-edit, and time-shift operations. Help should show the operation, accepted type, destination location, and likely side effects. A compatibility mode can translate legacy forms into the same operation plan.

## Verified: copying is not always structural cloning

Copying without destination groups writes to preferred locations and updates existing writable same-named fields elsewhere. Explicit `all:all` preserves family-1 locations subject to what can actually be written. A source can therefore lose its original arrangement when copied into another container.

Direct list copying preserves items; interpolating a source list into a string can collapse them. Repeated assignments to one destination can replace earlier queued assignments. Additive copying and appending to an existing destination list are distinct actions. [FAQ: copying locations and list values](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/faq.html#Q9)

XMP structure copying also differs from flattened-field copying. Defaults preserve structures; opting into `-struct` restricts copying to structures, while `--struct` uses flattened tags. [XMP structure copy rules](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/struct.html#Copying)

**Proposed imageinfo behavior:** name transfer policies explicitly: preserve locations, map to preferred schema, merge lists, replace lists, and synchronize related schemas. A transfer preview should enumerate skipped fields and changed locations. A “copy everything” label must state whether it includes unsafe tags and whole binary blocks.

## Verified: output choices change the data contract

| Surface | Compatibility concerns |
| --- | --- |
| Human text / `-s`, `-S`, `-s3` | Descriptions, tag identifiers, compact output, and value-only output are different interfaces. |
| JSON / `-j` | Structured mode affects flattening and arrays; duplicate JSON keys can suppress records. |
| CSV / `-csv` | Unique headings and list separators matter; the full dataset is buffered for column discovery. |
| XML / `-X` | ExifTool's RDF/XML vocabulary is different from native XMP. |
| HTML / `-h` | A human report, separate from hex-dump diagnostics. |
| Binary / `-b` | Bytes need an explicit framing/output strategy when extracting multiple values. |
| Templates / `-p` | User-defined reports and formats have missing-value and escaping behavior. |
| Argument output / `-args` | A replay-oriented serialization needs quoting and encoding fidelity. |
| PHP / `-php`, SVG / `-plot` | Existing output surfaces still belong in the parity ledger. |

The manual explains the output switches and their interactions. For JSON/CSV, group/instance names are necessary to retain otherwise colliding output identities; CSV imports use SourceFile as a lookup and still require input files on the command line. [Output and import documentation](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/exiftool_pod.html#Input-output-text-formatting)

**Proposed imageinfo contract:**

- A stable machine schema should represent records in arrays, with explicit identity and provenance, so duplicate names cannot overwrite one another.
- Preserve empty, missing, null, binary, scalar, list, and structure distinctions. Do not let a one-item list become a scalar accidentally.
- Publish how exact rationals, large integers, timestamps, encodings, and non-finite numeric values serialize.
- Offer streaming output for large collections and a documented fixed-schema CSV export.
- Separate stdout data, stderr diagnostics, and progress. Terminal decoration and paging should never corrupt machine output.
- Import should report matched, unmatched, ignored, changed, and failed files. Deletion intent should be explicit; an empty spreadsheet cell is an ambiguous instruction.
- Support raw binary output directly to files; explain shell-dependent redirection where applicable.

## Verified: selection, speed, and extraction depth interact

ExifTool exposes recursion, extension filters, filename exclusions, metadata predicates, ordering, embedded-document extraction, unknown-field extraction, XMP scanning, and fast-scan levels. Predicates and report formatting can use Perl expressions. Fast modes skip parts of scanning, rather than merely make the same scan quicker. [CLI processing controls](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/exiftool_pod.html#Processing-control)

As an out-of-scope background example, PNG illustrates a concrete tradeoff: FastScan can bypass checksums otherwise validated during writing. [PNG checksums](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/TagNames/PNG.html)

The observed QuickTime documentation describes timed GPS/sensor records exposed by ExtractEmbedded. This is background only: timed-video processing is outside initial delivery. CR3's use of the same container family does not bring video into the initial product. [Timed metadata](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/TagNames/QuickTime.html#Stream)

**Proposed imageinfo requirements:** make coverage level visible as complete, selected blocks, shallow, or best-effort. Publish what each performance mode omits. Provide a declarative filter language for routine comparisons and existence checks. List how symbolic links, hidden files, unknown extensions, directories, network paths, and duplicate inputs are handled. Embedded extraction should have explicit recursion, size, and record-count limits.

## Verified: writes affect more than tag values

WriteMode distinguishes updating existing tags, creating tags, and creating necessary groups; the documented default is `wcg`. This matters when a caller intends to update existing capture information without creating another metadata block. [Write-mode controls](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/exiftool_pod.html#wm-MODE--writeMode)

The upstream CLI source implements an original-file backup policy, temporary-file writes, output routing, timestamp-preservation options, original restoration/deletion, and an in-place replacement mode. Those policies must be considered alongside tag assignment. [CLI implementation](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/exiftool)

The extra-tag tables expose filesystem operations including FileName, Directory, file dates, hard links, and symbolic links. The optional ImageDataHash covers defined media payloads and excludes some preview/thumbnail content; it is different from a digest of every byte of the file. [Extra/filesystem tags and payload hashes](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/TagNames/Extra.html)

**Proposed imageinfo requirements:**

1. Show the intended mutation, newly created metadata groups, file replacement strategy, output path, and backup policy.
2. Preserve unrelated blocks and opaque bytes unless the operation specifically requests removal.
3. Define guarantees separately for one-file replacement and an entire batch. Do not describe a partially completed batch as a single atomic transaction.
4. Detect modification between planning and applying, and publish recovery behavior for interrupts, disk-full errors, permissions, and conflicts.
5. Verify media preservation with a documented payload comparison, including all media portions that matter for that format.
6. Explain when file identity, links, dates, permissions, alternate streams, extended attributes, and resource forks can change.

Deleting visible metadata is not automatically safe RAW sanitization. Upstream warns that removing all RAW metadata can remove proprietary information required for rendering. Selective changes must preserve calibration and sensor data. [RAW writer limitation](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/index.html#limitations)

PDF history and PNG trailers are retained here only as out-of-scope background examples of why deletion semantics need precision. Neither format is an active imageinfo target. [PDF behavior](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/TagNames/PDF.html), [PNG trailer behavior](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/TagNames/PNG.html)

## Verified: date/location/file commands have their own semantics

The time-shift module accepts calendar and time components, and distinguishes timezone shifts from changes to clock values. It preserves the original date/time shape and does not add a timezone merely by shifting. [Date/time module](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/Shift.html)

Geosync corrects the time used for track interpolation, which can be separate from editing the camera timestamps. Multiple synchronization points can correct clock drift. [Geosync](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/geotag.html#geosync)

File naming combines date-format placeholders with file-format placeholders; escaping is needed when those layers overlap. TestName previews the resulting path. [Filename and date formatting](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/filename.html)

**Proposed imageinfo requirement:** make duration units and time-zone assumptions explicit. Preview related dates together, show unzoned inputs, and report collisions before renaming. Location help should explain interpolation gaps, daylight-saving assumptions, drift correction, and output-coordinate units.

## Verified: persistent-process automation is an application protocol

ExifTool supports a long-lived process using `-stay_open True -@ ARGFILE`, including standard input with `-@ -`. Each argument occupies a line. An `-execute` terminator submits a command; adding a number produces a corresponding ready marker. Shutdown uses `-stay_open` followed by False or 0. The application source flushes and emits ready markers and tracks command status. [Persistent command handling](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/exiftool)

The library API separately exposes extraction, metadata lookup, values, queued changes, writing, groups, and capability discovery. [Library API](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/ExifTool.html)

The documented process exit statuses are 0 for success, 1 for an error, and 2 when every file fails the `-if` condition. A batch-wide exit code cannot describe every file outcome by itself. [Exit-status contract](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/exiftool_pod.html#EXIT-STATUS)

**Proposed imageinfo requirements:** support both ordinary subprocess use and an efficient integration interface. Specify request IDs, framing, cancellation, per-request state reset, stdout/stderr ordering, diagnostics, completion, and status. A ready marker is completion signaling, so callers also need a success/failure result. Persistent input must not accidentally carry one user's mutation options into the next request.

## Verified: extensibility and discovery belong to the interface

ExifTool's example configuration defines custom tags, shortcuts, structures, composite calculations, and default options. This is executable configuration, rather than only a static list of preferences. [Upstream configuration example](https://raw.githubusercontent.com/exiftool/exiftool/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/config.html)

**Proposed RAW parity inventory:** include capability-listing options, API options, configuration, module loading, user parameters, alternate input files, source-file templates, common arguments, command sequences, report formatting, validation/diff, verbose inspection, and original backup utilities. Determine each surface's role before choosing its syntax. Ordinary RAW filtering and mappings should be convenient to express; advanced executable behavior needs a documented, deliberate compatibility boundary.

## Proposed hierarchical help contract

The user's requested cascading help should apply to every level: project-wide help, command family, action, field selection, and individual tag. The command taxonomy is still a design proposal; examples below describe discoverability requirements rather than implemented syntax.

| Level | Help should answer |
| --- | --- |
| Root | What can I do? Which task family handles reading, editing, transfer, dates, location, files, and diagnostics? |
| Family | What are its actions, examples, default behavior, and supported file types? |
| Action | What changes? Which options are required? Can I preview the operation? |
| Option | Which values/types/units are accepted? How does it interact with other options? |
| Tag | What does it mean? Where was it found? Can it be read, updated, created, deleted, or copied here? |
| Error | What failed? Which file/record caused it? What concrete next step resolves it? |

Help should work in a terminal, pager, and plain-text mode. Interactive browsing and completion should complement deterministic commands so automation can perform the same workflows. An incomplete invocation should present the useful next choices instead of only an opaque usage failure.

## Proposed compatibility scenarios to freeze

These are investigation/acceptance cases, not completed tests:

| Scenario | Contract to determine |
| --- | --- |
| Duplicate DateTimeOriginal across blocks/documents | Extraction visibility, priority, provenance, machine-output identity |
| Orientation under default conversion and `-n` | Human/machine values and inverse assignment |
| Existing EXIF/IPTC/XMP description fields | Bare-name assignment and explicit-group assignment |
| Multi-source copy to one keyword list | Queue replacement, accumulation, existing-value append, duplicates |
| One-item XMP list and nested structures | JSON type stability, direct copying, flattened copying |
| XMP/QuickTime language alternatives | Default-language replacement versus language-preserving update |
| CSV with missing, empty, deletion, and unmatched rows | Lookup behavior, field selection, deletion intent |
| CR3 container dates and location identities | Interpretation, conversion, and precise metadata destination |
| RAW files with previews/vendor blocks under fast scans | Coverage omissions and write validation policy |
| New versus existing metadata groups | Update-only/create-only controls and mandatory fields |
| Binary previews, ICC profiles, RAW embedded JPEGs | Extraction, replacement, block versus field operations |
| Selective RAW privacy edits | Removed fields versus preserved sensor/calibration/vendor blocks |
| File rename collisions and missing capture time | Preview, fallback, collision handling, recovery |
| Persistent command with errors followed by a read | Completion/status framing and request-state isolation |
| Mixed-success batch, predicates rejecting everything | Per-file outcomes and process exit status |

## Remaining research needed before implementation commitments

Pin a reference binary/source revision and generate a RAW option/tag/group inventory. Record intentional compatibility boundaries for executable expressions, configuration modules, platform filesystem features, and legacy output formats. Pair each supported RAW/sidecar mutation with before/after fixtures and preservation checks. A more pleasant interface should make these choices easier to understand while retaining the underlying metadata precision.
