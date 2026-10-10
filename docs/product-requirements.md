# imageinfo product requirements

Status: proposed requirements; no executable, format support, or ExifTool parity is implemented by these documents. Research date and RAW-only scope revision: 2026-10-10. Language, runtime, framework, parser implementation, and packaging decisions are deferred.

## Product intent

Build a public, community-maintained metadata tool, starting with camera RAW images, a discoverable command hierarchy, and a useful experience for both occasional users and automation. The long-term ambition remains feature parity with the full ExifTool. On 2026-10-10 the user narrowed the current delivery scope to RAW images so the project can start with a manageable subset. Related XMP sidecars and metadata/extraction of embedded previews remain part of RAW workflows. Broader ExifTool functionality is deferred research and future ambition, not an initial delivery gate.

In scope are DNG and proprietary camera RAW families such as Canon CR2/CR3, Nikon NEF/NRW, Sony ARW, Fujifilm RAF, Olympus ORF, Panasonic RW2, Pentax PEF, and Samsung SRW. This list describes the research/requirements horizon, not implemented support or a guarantee that every variant is writable. Standalone JPEG/PNG, video, audio, documents, archives, and other non-RAW media are out of active scope. RAW pixel developing, rendering, demosaicing, and format conversion are also out of scope.

The user identified dependence on one primary maintainer as a concern. The response is shared ownership, documented behavior, reproducible releases, and a usable contribution process. A different implementation language alone would not establish better safety, durability, or maintenance.

ExifTool's own documentation describes read/write functionality, camera maker-note support, and separate read/write/create capabilities for many formats. Its RAW-relevant tag selection, editing, copying, formatting, and batching behavior inform this project. Its wider format list is research context, not initial imageinfo scope, and a readable RAW format does not imply that each of its tags is writable. [Official README](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/README), [application documentation](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/exiftool_pod.html).

Repository references below are anchored to the observed upstream source snapshot [2200871](https://github.com/exiftool/exiftool/commit/2200871d9cef988051d2a99d67df3bda6cbb30a8), labeled “Update to 13.59” and dated 2026-05-27. This is a reproducible research anchor, not a claim about the latest available release; a formal parity-release baseline still needs to be selected.

## Who it serves

| User | Primary job | Evidence of success |
| --- | --- | --- |
| Photographer or archivist | Inspect, correct, organize, and preserve a camera RAW collection | Find the right command through help; preview edits; recover RAW originals and paired sidecars |
| Publisher or privacy-conscious user | Identify and remove a specified class of metadata | See what remains and whether removal is complete for that format |
| Automation author | Process large collections and integrate metadata workflows | Stable structured results, meaningful exit status, resumable batches |
| Forensic or preservation specialist | Examine original values, structures, duplicates, and embedded information | Provenance and raw representations survive extraction |
| Contributor or maintainer | Add a format, tag, regression case, or workflow | Documented extension boundary and conformance evidence |

## RAW scope and reference equivalence

Within an explicitly declared RAW subset, reference equivalence means a documented equivalent for each claimed metadata capability, with conformance evidence for its supported container/variant/tag combinations. It does not require reproducing every legacy spelling or accidental behavior in the primary CLI. A future migration surface may support RAW-specific legacy command and output behavior where useful. Requirements never imply coverage of non-RAW formats.

Coverage must be described as a matrix of RAW container/variant, metadata family, operation, supported value types, and constraints. Read, safe embedded write, sidecar create/apply, delete, copy, preview extraction, and validation are separate claims. A passing DNG read case must never imply DNG write support, proprietary RAW write support, or complete maker-note coverage. XMP sidecar application to a RAW file requires that exact target's write capability; it is not automatically permitted.

The baseline must pin an ExifTool release and record primary documentation/source revisions for the selected RAW features. Relevant upstream changes enter an explicit tracking process. Unsupported RAW variants stay visible as gaps; non-RAW functionality belongs to the deferred full-parity horizon and enters delivery only through later scope decisions.

Priorities express implementation order inside the RAW-only scope:

- **P0 — foundation:** required before shipping an initial release that touches user files.
- **P1 — useful workflows:** required for practical RAW collection workflows, with honest coverage limits.
- **P2 — extended RAW coverage:** later RAW variants and advanced RAW-specific workflows; any equivalence claim names its precise tested subset.

## Functional requirements

The following requirements are imageinfo design proposals. ExifTool behavior informs the RAW capability inventory; proposed safety and usability policies are imageinfo's own requirements. Existing requirement IDs are retained after the scope revision so board links remain stable.

| ID | Priority | Requirement | Measurable acceptance criterion |
| --- | --- | --- | --- |
| PR-001 | P0 | Maintain a versioned RAW capability inventory with source references and unresolved cases. | Every claimed RAW variant/operation and associated XMP capability has a status, baseline version, limitations, and linked conformance case; unimplemented cells remain visible. |
| PR-002 | P0 | Identify RAW containers from contents, distinguish detection from successful parsing, and report extension mismatches or out-of-scope inputs. | RAW fixtures with correct, missing, and misleading extensions produce the same detected container; non-RAW inputs return an explicit out-of-scope result; truncated or ambiguous inputs report a bounded diagnostic. |
| PR-003 | P0 | Preserve tag identity, group/namespace, document/instance path, duplicates, ordering where meaningful, raw/normalized/display values, and provenance. | A fixture with same-named tags in multiple groups and repeated instances loses no values in structured output; each record identifies its origin. |
| PR-004 | P0 | Read metadata from a declared initial RAW subset and its associated XMP sidecars. | Published DNG and selected proprietary-RAW fixtures pass the read conformance suite; additional RAW variants remain tracked separately; no non-RAW support is advertised. |
| PR-005 | P0 | Provide consistent root, group, and operation help and machine-readable interfaces. | Every advertised operation has offline help, typed parameter documentation, a valid example, output schema, and exit-status documentation; see CLI-001 through CLI-017. |
| PR-006 | P0 | Make mutations reviewable, reversible by default, and explicit in automation. | Every modification can produce a no-write plan; applying it preserves a recoverable original and reports actual before/after values; invalid requests produce zero writes. |
| PR-007 | P0 | Enforce embedded RAW write capability by exact container/variant, namespace, tag, and operation; offer XMP sidecars when direct writing is unsupported. | An unsupported tag or read-only RAW target fails preflight with the reason and supported sidecar alternatives; it is never silently ignored or reported as written. |
| PR-008 | P1 | Set and delete scalars, lists, structured fields, language alternatives, and metadata blocks in associated XMP or explicitly supported RAW locations. | Round-trip fixtures cover null/absent/empty distinctions, list replace/append/remove/deduplicate, structure merge/replace, and language-specific changes without unrelated-field loss; unsafe RAW block deletion is rejected. |
| PR-009 | P1 | Copy, map, synchronize, and compare metadata across RAW files and their associated XMP sidecars. | A documented workflow can preserve supported original locations or choose an explicit XMP mapping policy; preview names conversions, missing values, conflicts, and losses. |
| PR-010 | P1 | Import/export RAW metadata as machine formats, human reports, and associated XMP sidecars. | Round trips preserve supported types and duplicate identity; schemas distinguish display exports from lossless exports; XMP overwrite conflicts fail by default; creating RAW containers is not promised. |
| PR-011 | P1 | Read and change date/time values with explicit offset, subsecond precision, absent-zone, and calendar policies. | Tests include leap days, month/year boundaries, negative shifts, fractional seconds, zoned and zone-less values; zone-less timestamps are never silently assigned a host timezone. |
| PR-012 | P1 | Geotag RAW collections or associated XMP from auxiliary tracks; support explicit clock/timezone/interpolation policies and inverse coordinate export. | Known tracks produce expected coordinates within declared tolerance; missing timezones, large gaps, and out-of-range timestamps are diagnosed; writes require a safe supported RAW location or explicit sidecar destination. |
| PR-013 | P1 | Rename, move, copy, and change filesystem timestamps in RAW collections using metadata-derived templates and conditions; preserve sidecar associations. | Collision, case-only rename, missing-tag, cross-volume, orphan-sidecar, and duplicate-basename cases have defined results; plans show both RAW and paired-XMP destinations and refuse unintended overwrites. |
| PR-014 | P1 | Inspect metadata in and extract embedded RAW previews, thumbnails, profiles, and supported binary metadata blocks. | Extracted bytes match reference fixture hashes; each item identifies its RAW parent and instance; extraction obeys depth/size/destination limits; no new preview is rendered and no sensor data is changed. |
| PR-015 | P1 | Offer explainable RAW/XMP privacy inspection and safe named scrub profiles with verification. | Profiles list targeted tags, required camera/rendering metadata, embedded-preview checks, and residual risks; unsafe or uninspectable RAW regions remain explicit; reversible deletion is never labeled secure erasure. |
| PR-016 | P1 | Validate metadata structure and provide bounded diagnostics and repairs where justified. | Known malformed fixtures produce stable issue codes; repair requires an explicit plan, preserves the original, and passes post-write validation or reports failure. |
| PR-017 | P1 | Provide directory traversal, input manifests, tag/group selectors, conditions, sorting, and multi-step batch workflows. | Selected files match documented hidden-file, recursion, symlink, filter, and ordering policies; manifest inputs safely represent filenames containing newlines. |
| PR-018 | P1 | Provide typed transformations, derived/composite tags, print templates, value conversion controls, and extensible tag definitions. | Each declared reference transformation capability has a documented equivalent or an explicit gap; user expressions are bounded, have no implicit shell execution, and preserve types unless conversion is requested. |
| PR-019 | P2 | Expand the declared RAW subset to additional camera/container variants, vendor maker notes, and embedded-preview metadata. | Each added RAW capability has fixture-backed conformance results and limitations; unsupported variants remain visible; no broader ExifTool-format parity claim is made. |
| PR-020 | P2 | Evaluate advanced RAW-specific processing: persistent requests, ordered operations, argument files, partial reads, group-family selection, and diagnostics. | Any adopted advanced RAW feature has an executable equivalence case; partial reads label omissions, and persistent sessions isolate request state; wider reference-tool behavior is not a mandatory deliverable. |
| PR-021 | P2 | Provide migration guidance for declared RAW-focused ExifTool workflows. | A compatibility table maps supported RAW-related flags, values, quoting concerns, schemas, and differences; non-RAW/unknown constructs fail clearly; no claim of full drop-in compatibility is made. |
| PR-022 | P0 | Make capability and tag discovery searchable locally. | Users can discover a tag's type, groups, units, value choices, writability, format restrictions, and examples without an internet connection; aliases and friendly labels resolve to a canonical identity. |

ExifTool treats XMP structures and flattened fields as separate representations and documents XMP sidecar workflows. Imageinfo's active sidecar requirement is associated XMP; other standalone metadata container types are background research. [Structured information](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/struct.html), [metadata sidecars](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/metafiles.html).

Reference geotagging includes interpolation and clock synchronization/drift behavior. Date/time shifting has calendar and offset subtleties. These deserve independent conformance suites rather than only successful command examples. [Geotagging](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/geotag.html), [date/time shifting](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/Shift.html).

## Quality and project requirements

| ID | Priority | Requirement | Measurable acceptance criterion |
| --- | --- | --- | --- |
| PR-023 | P0 | Support Windows, macOS, and Linux with documented filename, terminal, permission, and filesystem behavior. | The supported platform matrix passes a shared corpus covering spaces, non-ASCII text, supplementary Unicode characters, leading hyphens, long paths where supported, and equivalent command outcomes. |
| PR-024 | P0 | Preserve RAW sensor payloads, decoding-critical camera information, embedded previews, and unrelated metadata during edits. | Every enabled RAW write has independent payload-preservation evidence, byte hashes where feasible, unchanged protected metadata, and renderability checks through independent tools in the test process; imageinfo itself need not develop or render pixels. |
| PR-025 | P0 | Survive interruption, write failure, concurrent edits, and stale plans without silent data loss. | Fault injection at each write stage leaves the original or a verified replacement recoverable; stale content identity blocks application; writers never update the same physical file concurrently. |
| PR-026 | P0 | Treat input files and templates as untrusted data. | A malformed/fuzz corpus cannot hang indefinitely, write outside declared targets, or execute commands; configurable time, recursion, memory, and extraction-size limits yield explicit resource errors. |
| PR-027 | P0 | Keep local workflows offline and private by default. | Normal reads, writes, help, completions, and discovery succeed with network disabled; no metadata, filenames, or telemetry leave the machine without an explicit enabled feature. |
| PR-028 | P1 | Publish repeatable performance measurements and bounded batch behavior. | Benchmarks publish corpus, environment, baseline, throughput, startup latency, and peak memory; streaming a large manifest keeps memory within a declared configured budget; targets are set after measurement. |
| PR-029 | P0 | Version command behavior, JSON schemas, capability data, and persistent protocols. | Releases include migration notes; same-schema outputs remain backward compatible; incompatible changes require a new documented version and compatibility tests. |
| PR-030 | P0 | Reduce dependence on any one contributor through reviewable knowledge and release procedures. | Public governance names ownership/backup responsibilities; maintainers can follow documented triage, format-extension, security, and release checklists; release verification is reproducible from the repository. |
| PR-031 | P0 | Establish license, provenance, and lawful fixture handling before accepting implementation assets. | Every copied/adapted asset and fixture has recorded origin and applicable terms; the project license is explicitly chosen; test media contains no unintended personal information. |
| PR-032 | P1 | Make help accessible and localization-ready while keeping script identities stable. | All interaction has a plain-text equivalent, keyboard navigation, and no color-only meaning; translated labels never change canonical tag keys, command names, or machine schemas. |

Maker-note offsets and related camera identifiers can affect interpretation and safe rewriting. Text encodings also vary by metadata family. Write safety must address these semantics; successful file replacement is insufficient. [Official FAQ, sections 8, 10, and 15](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/faq.html).

## Release gates

1. **RAW research baseline:** inventory primary sources for selected RAW families, characterize read versus safe write, define associated-XMP policies and a RAW oracle corpus. No implementation language decision is required.
2. **Read-only RAW preview:** demonstrate root/group/leaf help, discovery, deterministic metadata identity, structured output, embedded-preview extraction, and inspection of a declared RAW subset.
3. **XMP editing preview:** satisfy P0 safety requirements for associated sidecar changes; exercise reversible edits, RAW/XMP pairing, plans, interruption, and unsupported direct-write handling.
4. **Safe RAW editing/workflow milestone:** enable embedded writes only for individually validated RAW variants; verify payload preservation, then deliver P1 workflows within the published subset.
5. **Extended RAW coverage:** add P2 RAW capabilities with independent conformance evidence and stated gaps. The eventual full ExifTool parity ambition proceeds through later scope decisions; non-RAW support is outside this initial release plan.

A requirement is done only when behavior, documentation, fixtures, and capability reporting agree. A proposal appearing in the CLI tree is not an implemented feature.

## Initial acceptance scenarios

- A first-time user starts at `imageinfo help`, discovers `metadata read`, inspects a DNG or supported proprietary RAW file, and finds tag-specific help without a web search.
- An archivist previews a batch copyright edit and date correction in paired XMP sidecars, sees all affected files, applies a saved plan, and restores an original sidecar.
- A script extracts duplicate grouped RAW tags to typed JSON, handles one malformed RAW file, and distinguishes partial failure from success.
- A user exports a RAW file's metadata to XMP, reviews namespace conversions, and reapplies supported edits without implying that all original binary structures round-trip through XMP.
- A RAW owner selects a location scrub profile, receives a preview that includes embedded-preview limitations, and obtains a verification report stating remaining and uninspectable regions.
- A contributor adds one RAW variant capability with sources, privacy-safe fixtures, mutation safety tests if applicable, and an updated capability matrix.

## Deferred decisions and open research

Implementation language and framework remain unselected. Also defer final parser/extension boundaries, expression syntax, distribution mechanisms, GUI scope, and whether an optional reference-tool bridge is useful. Any such bridge would be disclosed and would not count as independent implementation parity.

The next specification work should pin a RAW baseline, define metadata identity and RAW/XMP pairing, establish a first RAW corpus, classify RAW-relevant ExifTool options, and finalize safe plan/application behavior. Safe maker-note rewriting, embedded-preview privacy limits, RAW variant identification, and filesystem atomicity need dedicated evidence before claims are made.

Product constraints: no RAW pixel developing/rendering/conversion, standalone non-RAW metadata support, cloud storage service, digital-asset-management server, or mandatory network dependency is required. Auxiliary GPX tracks, request manifests, JSON/CSV reports, and extracted preview files serve RAW workflows; they do not expand supported primary media inputs. Any future scope expansion requires an explicit product decision.
