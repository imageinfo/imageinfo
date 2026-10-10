# Camera RAW compatibility and validation requirements

Research date: **2026-10-10**. Status: requirements proposal; no implementation or compatibility claims yet. Programming language, runtime, libraries, and packaging technology remain undecided.

**First validation target: Canon EOS R5 CR3**, its associated XMP sidecars, and its
embedded previews. Prioritize that corpus and acceptance path before other RAW
families. See [the CR3 milestone](canon-eos-r5-cr3.md).

Upstream source snapshot: [`2200871d9cef988051d2a99d67df3bda6cbb30a8`](https://github.com/exiftool/exiftool/commit/2200871d9cef988051d2a99d67df3bda6cbb30a8), observed through the official repository. Repository-file citations below pin that revision; linked issue reports are dated observations. No executable reference or fixture corpus has been installed or run in this requirements phase.

## Active scope: camera RAW metadata

The current project scope is **metadata operations on camera RAW still images**, including DNG and proprietary formats such as CR2/CR3, NEF/NRW, ARW/SR2/SRF, RAF, ORF/ORI, RW2/RWL, PEF, SRW, IIQ, MRW, and X3F. Inventory other camera RAW families from the pinned ExifTool baseline rather than treating this example list as exhaustive. Coverage must distinguish camera model, firmware, compression, and layout variants.

Related XMP sidecars and metadata/extraction of previews embedded in a RAW file are in scope. Preview extraction copies existing embedded bytes; it does not generate or render a new image. Creation means adding supported metadata or creating an associated XMP sidecar, not creating new RAW sensor data.

Standalone JPEG/PNG/HEIF and other rendered images, video, audio, documents, archives, and unrelated metadata-only formats are deferred from the initial release scope. **Full ExifTool feature parity remains the eventual project goal**; the current delivery and acceptance matrix covers RAW first. RAW pixel developing, demosaicing, transcoding, and conversion between RAW formats are excluded product features. A shared container parser must not silently expand the initial release scope.

Within the camera RAW boundary, imageinfo aims for ExifTool-equivalent operations and data fidelity with a more discoverable interface. A modern command hierarchy alone does not establish parity.

The upstream support tables distinguish reading, writing, and creation, across both file formats and metadata families. These distinctions must survive in our requirements; support for reading a container does not imply every tag can be created or changed. [Upstream support tables](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/README)

Compatibility has several independently testable layers:

| Layer | Required evidence |
| --- | --- |
| Container recognition | Correct detected RAW format, camera/layout variant, byte order, nesting, and unsupported/corrupt distinction |
| Metadata extraction | Same relevant occurrences, groups, values, embedded resources, and diagnostics under stated options |
| Metadata interpretation | Raw, converted, and display views; units, date/time rules, charset behavior, and derived values |
| Mutations | Set, add, remove, create, copy, shift, and rebuild semantics, including precedence and constraints |
| Preservation | Untouched metadata, sensor payloads, and previews retained according to a documented, RAW-specific contract |
| Workflows | RAW batch selection, associated XMP sidecars, geotagging, reports/import, renaming, streams, and persistent sessions |
| Automation interface | Stable schemas, exit behavior, diagnostics, and explicitly documented compatibility modes |
| Extensions | Equivalent custom metadata definitions and transformation outcomes, with transparent migration limits |

A language-specific ExifTool API cannot be binary-compatible with an undecided new implementation. The requirement is equivalent operations and data fidelity through a stable imageinfo API and CLI. Existing ExifTool argument syntax is a separate migration/compatibility surface to evaluate, not an assumption that the default CLI must reproduce its syntax.

## Coverage matrix

Maintain a versioned, machine-readable inventory of **in-scope RAW formats and related workflows**, eventually generated into human-readable documentation. Each row identifies **RAW container + camera/layout variant + metadata family + tag/group + operation**, with evidence links. File-extension counts alone are insufficient. Keep the broad upstream inventory as background; exclude out-of-scope formats from active milestones and parity denominators.

The five capability columns are independent:

| Capability | Meaning | Minimum acceptance evidence |
| --- | --- | --- |
| Read | Identify and extract an existing occurrence | Positive fixture, duplicates/groups, raw and interpreted value, malformed case |
| Write | Change an existing occurrence | Read-back, intended change only, structural validation, preservation assertions |
| Create | Add absent metadata or create a related XMP sidecar | Empty/absent case, allocation/layout validation, target application acceptance |
| Preserve | Retain unselected known and unknown content across a mutation | Before/after identity or an explicit relocation proof; sensor/preview integrity |
| Delete | Remove a tag, family, block, or targeted sensitive data | Intended scope gone, dependent structures valid, retained data checked, physical-retention status |

Use statuses `unresearched`, `specified`, `implemented`, `verified`, `limited`, and `not-applicable`. A `limited` or `not-applicable` cell needs a reason, affected variants, source, and intended behavior. “Unsupported by ExifTool” and “not implemented by imageinfo” are different reasons. Require evidence before `verified`.

Illustrative inventory rows below describe what to track, not what imageinfo currently supports:

| Inventory row | Read | Write | Create | Preserve | Delete |
| --- | --- | --- | --- | --- | --- |
| TIFF-family RAW / ordinary EXIF and GPS | Tag + IFD location | Existing value where permitted | Absent tag/block where permitted | RAW strips/tiles + unselected IFDs | Dependency-aware tag/group removal |
| TIFF-family RAW / vendor MakerNotes | Vendor/model-specific | Existing field where valid | Field versus whole block restrictions | Offset-sensitive blocks + RAW payloads | Dependency-aware removal |
| DNG / private data and rendering metadata | Version + structured values | Definition-specific constraints | Definition-specific constraints | Sensor payloads + private data + original-RAW blocks | Required versus optional fields |
| CR3 / ISO BMFF metadata and Canon structures | Box/track/subdocument identity | RAW-specific location rules | Permitted metadata boxes only | Samples + references + unknown boxes | Removal versus retained inaccessible bytes |
| Other proprietary RAW layouts / embedded families | Variant-specific | Record supported mutation rules | Record supported insertion rules | Sensor data + private regions + previews | Record supported removal rules |
| Embedded XMP or associated XMP sidecar | Tree + list semantics | Field or language entry | Namespace/property/sidecar | Unknown namespaces + unselected fields | Entry/field/property distinction |
| Embedded preview/thumbnail / metadata and extraction | Preview identity + nested tags | Only if verified within RAW | No preview generation | Encoded preview bytes + references | Only if optional and verified safe |

Attach workflow dimensions to every relevant cell: source/destination RAW family or XMP sidecar; same-file versus cross-file copy; tags selected by group/name/wildcard; duplicate policy; list replacement/add/remove; raw versus display input; structured versus flattened output; character encoding; timestamps/timezones; preview/subdocument extraction depth; RAW compression and private-data encoding variants; and fast versus complete scans. Record filesystem and streaming constraints separately.

Do not promise creating a RAW file when “create” means adding a metadata family. Likewise, preserving unknown bytes does not prove that pointers into those bytes remain valid. Copying RAW files and extracting an already embedded original-RAW block do not imply RAW conversion support.

CR3 needs its own ISO BMFF/Canon constraints rather than TIFF assumptions. Upstream identifies CR3 among its QuickTime-family image containers and documents different padding behavior when writing it. Reusing structural knowledge for CR3 does not require accepting MOV/MP4 or HEIF files. [CR3 container and padding context](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/TagNames/QuickTime.html)

DNG private data and embedded original-RAW information need explicit rows. Upstream describes vendor material carried in DNG private structures and documents historical external-pointer loss in converted MakerNotes; this is preservation background, not a requirement to implement a DNG converter. [DNG private/original-RAW structures](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/TagNames/DNG.html)

## A pinned reference and reproducible evidence

Use an explicitly pinned, reviewed ExifTool release as a **development/test oracle**, without making it an eventual runtime dependency. Record its version, immutable source revision, download origin, archive/executable hash, dependency capabilities, and full invocation. Do not silently update the oracle when upstream releases change.

During this research the accessible upstream `master` history showed version 13.59 dated May 27, 2026 and identified 13.55 as a production release. Those observed documents are not proof of the newest available release on October 10. Selecting and verifying the actual test baseline remains a milestone. [Observed upstream history](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/Changes)

A differential test record must include:

1. Fixture ID and hash, provenance/license record, and feature/variant labels.
2. Imageinfo revision and oracle revision with complete options/configuration.
3. OS, architecture, locale, timezone, working-directory/path setup, environment, and optional capabilities.
4. Original stdout, stderr, status, extracted binaries, and mutation outputs as artifacts.
5. Canonical semantic comparison plus exact comparison where syntax/bytes are the contract.
6. An expected difference entry explaining any accepted divergence, with owner, rationale, and regression case.

Normalize only declared incidental differences such as test-root paths or deliberately controlled filesystem times. Preserve duplicates, ordering where meaningful, namespaces, null versus absent, exact rationals, list members, warnings, and binary lengths/hashes. Floating-point tolerance is per tag/unit and justified; a blanket tolerance would hide conversion defects. Compare presentation separately from metadata semantics.

Some reference invocations suppress duplicates or convert values for presentation. Test both default behavior and deliberate exhaustive modes. A JSON object keyed only by bare tag name cannot prove duplicate parity. Use a representation that retains occurrence identities when comparing results.

The reference is evidence, not unquestionable truth. RAW structural checks, independent decoder validation, and preservation invariants take precedence over matching a demonstrated corruption bug. Test-oracle behavior that changes sensor payloads or loses required rendering data must become a documented difference and regression case, not desired imageinfo behavior.

## Fixture inventory and provenance

The upstream distribution manifest includes RAW fixtures such as Canon CR2/CR3/CRW, DNG, FujiFilm RAF, Nikon NEF, Panasonic RW2, Phase One IIQ, and Sigma X3F, alongside a much broader corpus. Select only RAW and related XMP/embedded-preview test cases for the active project. Core tests exercise duplicates, groups, exclusions, and value selection; writer tests include selected binary round trips. They are coverage leads, not proof of complete RAW coverage. [Manifest](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/MANIFEST), [core tests](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/t/ExifTool.t), [writer tests](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/t/Writer.t)

Build an imageinfo-owned corpus with these categories:

- Small synthetic, documented fixtures for one feature at a time, including unknown data and conflicting duplicate locations.
- Real camera samples across vendors, models, firmware versions, RAW compression/layout variants, multi-image captures, private blocks, embedded previews/thumbnails, and DNG profiles/opcodes.
- Paired RAW/XMP sidecar samples with matching, conflicting, missing, stale, and unknown-namespace metadata.
- Cross-application RAW samples demonstrating what independent RAW readers and catalog tools actually accept after metadata edits.
- Damaged fixtures for truncated input, invalid offsets/counts, overlapping structures, cyclic references, corrupt compression, and invalid text.
- Regressions reduced from specific failures, retaining the important layout condition.
- Large-file and high-cardinality cases generated reproducibly rather than storing enormous binaries in the repository.

Each fixture needs a source URL or generator description, acquired date, creator/owner, explicit redistribution permission/license, allowed transformations, attribution, content hash, and privacy review. Download access and a public issue attachment are not equivalent to redistribution permission. Keep restricted samples out of the public repository; tests should explain how authorized maintainers can obtain them. Never publish incidental GPS, serial numbers, faces, names, or private source paths from a contributor's sample without appropriate permission. Sanitization itself must be documented because it can erase the behavior under test.

## Safe mutation acceptance

Require every writer to pass this gate before describing its format/operation as verified:

1. **Plan:** identify every target occurrence, implicit destination, dependency change, and preservation claim before modifying files.
2. **Stage:** perform mutations on an output/staging file, with defined backup and collision behavior.
3. **Reparse:** confirm the intended semantic result using imageinfo and the reference reader where supported.
4. **Validate structure:** check lengths, offsets, counts, nesting, alignment, references, checksums, and format-specific invariants independently of the code path that wrote them.
5. **Check preservation:** compare protected RAW sensor/preview payloads and unselected content using the format contract below.
6. **Check usability:** use an independent RAW decoder/reader for representative camera/layout variants. This is a validation tool, not an imageinfo developing feature.
7. **Commit output:** replace the destination only after required checks succeed; test interrupted writes, full disks, permission failures, and competing changes.

ExifTool's own FAQ says its validation feature performs additional checks, mainly for JPEG and TIFF, and does not position it as a general image validator. Therefore, passing the oracle's validation is one layer of evidence. [Validation limitations](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/faq.html)

Preservation rules must be precise:

- Read-only operations leave file bytes untouched. A mutation that determines no effective change must not rewrite the file without an explicit reason.
- Metadata changes preserve encoded RAW sensor payload bytes. They must not decompress/recompress, develop, demosaic, transcode, or convert sensor data.
- Relocating payloads may change container offsets, layout, size, or checksums; verify payload identity and valid references rather than requiring whole-file identity.
- Preserve order-sensitive lists, unknown fields/boxes, opaque trailers, previews, calibration/profiles, and unselected metadata where safe. Record every intentional omission in the plan/result.
- Preserve sensor/rendering-critical dimensions, CFA description, compression parameters, bit depth, black/white levels, color/calibration matrices, active area/crop, and relevant DNG opcodes unless a separately researched operation explicitly permits changing them. Changes to orientation or other interpretation metadata can affect appearance despite unchanged sensor bytes; show those effects in the plan.
- Filesystem properties need a separate contract for names, timestamps, permissions, ownership, attributes, links, and platform-specific metadata; unsupported preservation must be explicit.
- Whole-file byte equality after write-then-undo is valuable where promised, but semantic reversibility and byte reversibility are different guarantees.

### MakerNotes and unknown content

Upstream documents that MakerNote pointers can be invalidated by edits, that Make/Model affect recognition, and that individual MakerNote tags generally cannot be created/deleted independently. Those conditions require dedicated cases instead of a generic “EXIF supported” label. [MakerNote cautions](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/faq.html)

Require vendor-specific relocation rules, known offset bases, original block boundaries, and explicit dependency tracking. Preserve unknown blocks only when their layout can remain valid; otherwise refuse the unsafe mutation or require an explicit override that reports exactly what cannot be guaranteed. Repair is a separate requested operation with evidence and a retained original, not a side effect of ordinary editing. A malformed MakerNote must not make a generic “ignore warnings” option quietly destructive.

### RAW payload and rendering checks

For TIFF-derived RAW files, enumerate every protected strip/tile/image payload and assert byte identity after mutation, then verify its offsets/counts, dimensions, compression description, and directory references remain valid. Retain all image planes, alternate exposures, and previews that exist in the tested variant, rather than hashing only the first IFD's data.

For CR3, validate box lengths/nesting, sample/track relationships, sample locations and sizes, metadata references, and required Canon structures. Hash protected RAW sample payloads and embedded previews before and after; verify offset changes rather than assuming a smaller metadata box is harmless. For other proprietary containers, document an equivalent payload map and reference-validation contract before enabling writes.

For DNG, include private data, profiles/opcodes, CFA and linear-RAW variants, compressed/uncompressed storage, and embedded original-RAW blocks where present. A preserved sensor-payload hash is necessary but insufficient when changed calibration or layout metadata could make the file unreadable or render differently. Independent RAW decoding for QA can verify usability and compare sensor data where appropriate; imageinfo itself does not acquire a decoding/developing feature.

### Deletion, sidecars, and privacy

Require distinct outcomes for logical deletion, metadata-block removal, and physical removal of recoverable content in RAW/XMP. Privacy workflows must report what was removed, what remained, and what was uninspectable. Scan alternate metadata locations, embedded previews/thumbnails, MakerNotes, owner/serial fields, GPS, related XMP sidecars, and opaque vendor regions. A successful command must not imply all sensitive data is gone when unknown regions remain. Physical removal is a RAW-variant-specific requirement to research and validate; it is not supplied by changing the API label.

Do not apply a blanket metadata purge that removes fields needed to interpret sensor data. Distinguish personal/descriptive data from required container, calibration, and rendering information. If a privacy operation cannot safely remove opaque MakerNotes, explain the retained risk and offer a sidecar-only or copy/output workflow where useful; do not claim the RAW has been sanitized.

Define RAW-to-XMP and XMP-to-RAW mapping, conflict precedence, explicit synchronization scope, sidecar naming/discovery, orphan/stale sidecar behavior, and backup/collision policy. Creating/editing a sidecar must leave RAW bytes untouched unless the user explicitly requested a RAW mutation. A paired RAW/sidecar rename or copy needs a manifest and clear partial-failure results; do not advertise a multi-file atomic transaction where the filesystem cannot guarantee one.

## Adversarial and platform validation

Treat RAW, sidecar, and embedded-preview bytes as untrusted. Upstream security history motivates regression coverage and bounded parsing without treating any language as a security guarantee; vulnerabilities in other upstream format readers are background, not requirements to implement those readers. [Upstream security history](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/Changes)

Define explicit limits for input size, nesting depth, decoded/decompressed bytes, record/tag counts, embedded extraction, allocation, expression evaluation, output volume, and execution time. Defaults must protect interactive and batch use; documented overrides must retain enforceable ceilings. A limit-triggered result is “incomplete/limited,” not “no metadata.”

Fuzz recognizers, parsers, converters, registry loading, mutation planning, and writers. Cover offset arithmetic overflow, out-of-bounds spans, cycles, overlapping pointers, decompression bombs, entity expansion, invalid Unicode, pathological expressions, filename traversal, and command-like metadata. Persist minimized crash/hang inputs with fixed seeds and bounds. Tests must assert no code execution, arbitrary file writes, network fetches, uncontrolled resource use, or partial destination corruption.

Publish reproducible test results on Windows, macOS, and Linux, with representative architectures declared before release. Control locales and timezones, and separately test DST transitions, subsecond precision, non-ASCII paths, long paths, case sensitivity, symlinks, permissions, newline/shell quoting behavior, pipes, non-seekable streams, cancellation, and parallel batch ordering. Record filesystem-specific exceptions rather than masking them through broad normalization. Baseline performance on a published corpus with cold/warm conditions, memory limits, throughput, and tail latency; choose numeric release budgets after measurement.

## Release and parity claims

Publish **camera RAW scope** coverage by operation, RAW family, metadata family, camera/layout variant, and workflow, with verified cells over a stated in-scope denominator. Also publish untested cells, known limitations, expected differences, and preservation failures. An aggregate percentage must never hide an unsupported major RAW family or a writer that loses sensor data.

A release gate must require passing tests for all advertised cells, no unexplained semantic differential failures, no known corruption in verified RAW write paths, bounded malformed-input behavior, and evidence on the declared platforms. New in-scope upstream tags/features extend the inventory rather than changing yesterday's denominator silently. A RAW-parity claim requires a named reference revision and evidence for its relevant RAW inventory, including related XMP/preview workflows and documented exclusions. This phase must not claim full ExifTool parity. Marketing claims must match the published evidence.

## Custom configuration compatibility

ExifTool's example configuration includes custom namespaces, structured/list tags, composite expressions, and function callbacks. It is executable configuration, not simply a data-format schema. [Example configuration](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/config_files/example.config)

Imageinfo must support relevant RAW/XMP custom-definition use cases through an inspectable extension contract. It must detect an ExifTool configuration and explain which in-scope definitions can be migrated, which need manual translation, which target excluded formats, and which arbitrary code cannot be translated. Do not silently ignore a file or claim full compatibility by executing it without consent. Arbitrary existing Perl callbacks and expressions are an explicit migration limitation until a reviewed compatibility design exists; they must not cause a language choice in this phase.

Provide a migration report with source locations, converted definitions, unsupported behavior, and recommended next steps. Separate declarative tag definitions from executable transformations. Extensions need provenance, versioning, validation, resource constraints, and a documented trust boundary.

## Upstream reuse and license due diligence

Facts observed in primary sources: the upstream README offers redistribution/modification under the terms of Perl, referring to the Artistic License or GPL; the repository's observed `LICENSE` file contains GPL version 3 text. These facts should be recorded together, without assuming they settle the license of every source file, table, sample, or generated output. [README license statement](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/README), [repository LICENSE](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/LICENSE)

Project requirements: track origin, exact revision, applicable notices/terms, transformations, and intended distribution for every reused artifact. Review source code, tag tables, documentation, tests, fixtures, optional databases, and generated outputs separately. An independently rewritten parser does not automatically settle the status of copied data tables. Public availability is insufficient provenance. Before selecting the project license or importing substantial upstream material, resolve the intended reuse path and get appropriate licensing review. These are planning requirements, not a legal conclusion or a decision to adopt upstream code.

This requirements phase imports no upstream implementation, tables, test files, or samples. Source links identify research evidence. Later testing may use a separately installed, pinned ExifTool oracle; production imageinfo must eventually stand on its own.
