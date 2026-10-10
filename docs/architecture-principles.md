# Camera RAW architecture principles

Research date: **2026-10-10**. Status: language-agnostic design constraints for discussion. This document chooses no programming language, runtime, parsing library, serialization library, build system, or deployment technology.

**First implementation target: Canon EOS R5 CR3**, followed by broader RAW support.
Prove the initial vertical slice on CR3's container and Canon structures; the TIFF
and DNG principles below prepare later RAW work. See [the CR3 milestone](canon-eos-r5-cr3.md).

Primary source citations pin ExifTool revision `2200871d9cef988051d2a99d67df3bda6cbb30a8`; they establish research context, not that these proposed imageinfo requirements are implemented.

## Greenfield design boundary

Terry explicitly clarified on 2026-10-10 that imageinfo starts from a clean
whiteboard. ExifTool provides observable functionality and compatibility cases.
Its internal architecture, tables-as-code, module organization, mutable API state,
and group numbering do not prescribe imageinfo's design.

All boundaries below are proposals to evaluate against concrete requirements.
They are not a mandated package layout or a demand for one abstraction per row.
Use the smallest design that makes correctness, preservation, testing, and change
comprehensible. Adopt patterns only when their benefits justify their cost.

Honor the principle of least surprise: familiar names, conventional control flow,
standard types and libraries, and idioms natural to the eventual language. Review
an unconventional choice against a simpler conventional alternative and require a
concrete reason for it. Experience should make the code easier to predict.

Departures from convention are allowed when justified. Put a concise explanation
near the choice, naming the constraint and tradeoff; link a design note when the
rationale needs more space. Keep the repository inviting to outside contributors
through reproducible setup, clear boundaries, and decisions discoverable from the
code and documentation rather than private conversations.

Wire contracts specify what information crosses a boundary; they do not dictate
internal class hierarchies, packages, or value representations. For example, an
exact integer serialized as a decimal string can still use the language's natural
integer type internally. Keep documentation precision from turning into an
unnecessary runtime framework.

Keep native file-format concepts distinct from reference-tool conventions. A
Canon CMT block or an XMP namespace is source data; an ExifTool API method or group
family number is an interoperability concern. Preserve needed behavior through
explicit mappings without building the core model around legacy calling conventions.

No source-code quality audit of ExifTool has been performed. Assertions about its
technical debt are not premises or acceptance criteria for imageinfo's design.

The [safe mutation contract](write-safety/README.md) adds observable requirements
and acceptance scenarios. Its state model is a reasoning aid, not a required
transaction framework or package layout. Storage/API selection remains open.

## Product and independence

Imageinfo's active scope is **metadata operations on camera RAW still images**, including DNG and proprietary RAW families, with related XMP sidecars and embedded preview metadata/extraction. It will expose those operations through a consistent, discoverable CLI with help at every level. Its engine must also be usable independently of terminal interaction. RAW parity is measured using [compatibility and validation requirements](compatibility-and-validation.md), not a release label attached to an attractive interface.

Standalone rendered images (including JPEG/PNG/HEIF), video, audio, documents, archives, and unrelated metadata-only formats are deferred from this phase. **Full ExifTool feature parity remains the eventual project goal, with RAW as the initial delivery scope.** RAW developing, demosaicing, pixel transcoding, and format conversion are excluded product features. Extracting an existing embedded preview copies its bytes; it does not render a preview. Broader format work belongs to later roadmap milestones.

The production tool must eventually parse and mutate supported RAW/XMP data independently. ExifTool may be a pinned development/test oracle, but embedding it, invoking it as the primary engine, or requiring its runtime for normal operation would not satisfy the intended modernization and maintenance goals.

Modernity here means predictable data contracts, safe writes, useful diagnostics, accessible help, robust distribution, measurable performance, documented behavior, and shared maintainership. Language and dependency evaluation comes after requirements are sufficiently clear to compare options.

## One engine, multiple interfaces

Keep these responsibilities explicit:

| Responsibility | Contract |
| --- | --- |
| Input discovery and source access | RAW paths/directories, related sidecars, streams, seek requirements, detection, bounded byte access |
| RAW container parsers | Structure, spans, nesting, byte order, offsets, protected sensor payloads, opaque regions, and format diagnostics |
| Metadata family readers/writers | EXIF/IPTC/XMP/ICC/DNG/vendor semantics where present and supported inside RAW or related sidecars |
| Versioned tag registry | Names/IDs, namespaces/groups, types, conversions, units, descriptions, capabilities, constraints, provenance |
| Canonical metadata model | Every occurrence with typed values and origin retained |
| Query and transformation layer | Selection, duplicate policies, derived values, mappings, and explicit conversions |
| Mutation planner | Intended changes, dependencies, preservation guarantees, validation, and refusal reasons |
| Output transaction layer | Staged writes, backups, collisions, destination replacement, and cancellation |
| Workflow layer | RAW batch jobs, copying, paired XMP sidecars, import/export, renaming, geotagging, preview extraction, and persistent requests |
| Interfaces | CLI, optional interactive navigation, machine-readable output, and programmatic API |

These are architectural boundaries rather than required processes, packages, or deployment units. Choose their implementation later. Avoid one parser per filename extension when RAW variants share a container; equally, do not assume sharing a container makes all vendor layouts interchangeable. Reuse TIFF-family structure for applicable RAW types, add RAW-specific readers for other layouts, and support ISO BMFF structure only as needed for CR3. A reusable box parser does not authorize MOV/MP4 or HEIF features.

CR3's box/sample structure needs distinct bounds and reference contracts from TIFF IFD/strip/tile layouts. Upstream explicitly identifies CR3 as a QuickTime-family image container; its writing documentation also calls out CR3 padding behavior. [CR3 container context](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/TagNames/QuickTime.html)

The CLI must call the same operations available to automation clients. Interactive menus produce an inspectable operation/request that can be saved and run without prompts. Help and capability descriptions should be generated from the same contracts used to validate operations. Container parsers must not know about terminal colors, menus, shell quoting, or display formatting.

ExifTool itself separates reading/editing flows and application output formatting from core API operations. Its documentation also distinguishes stored binary data, raw decoded values, machine-oriented converted values, and display values. Preserve those distinctions while defining our own interfaces. [Upstream information flow and conversions](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/under.html)

## Canonical typed, ordered metadata model

The [metadata boundary contract](metadata-model/README.md) develops these
requirements into explicit identities, values, provenance, examples, and invariants.
Its wire schema does not dictate internal classes or replace idiomatic native types.

A flat map of tag name to string loses necessary information. Require a model representing a RAW document or associated XMP sidecar as an ordered collection of **tag occurrences**, plus a container structure/preservation view. An occurrence has an identity independent of its human-readable name. RAW, embedded preview, and sidecar occurrences remain separately attributable even when shown together.

| Model field | Requirement |
| --- | --- |
| Identity | Namespace/family, native tag ID, canonical name, group families, and stable occurrence identifier |
| Location | RAW container path, IFD/box/track, instance, embedded preview/subdocument, or sidecar field |
| Provenance | Source document, parser/registry revision, byte span when available, original encoding and byte order |
| Stored form | Binary data or bounded source reference; original typed raw value and exact rational representation |
| Machine form | Converted value with units, precision, conversion rule, and invalid/unknown state |
| Display form | Localized/formatted view generated on demand without replacing machine/raw values |
| Shape | Scalar, binary, ordered list, unordered bag, alternate-language map, structure, or nested combinations |
| Capabilities | Read/write/create/delete/preserve constraints for this occurrence and target context |
| Diagnostics | Warnings/errors attached to occurrence or source region, with recovery and completeness status |
| Derived status | Stored versus synthetic/composite value and dependency/provenance graph |

Preserve file order and repeated occurrences, even when the normal CLI chooses a prioritized view. Group qualification, duplicate suppression, sorting, flattening, and “best value” selection are views over the model. They must be reversible choices where the data permits. An API consumer must be able to request all occurrences and locations.

Retain rational numerators/denominators and integer widths where meaningful; do not turn every number into a rounded string or a floating-point value. Distinguish absent, empty, null/undefined, invalid, undecoded, and resource-limit states. Maintain the original time representation, available offset, fractional precision, and timezone assumptions; a timezone-free date must not silently become a UTC instant.

Binary resources should support bounded extraction/streaming and carry type/length/source-span information; embedded previews, original-RAW blocks, and opaque vendor regions must not be accidentally stringified. Protected sensor payloads belong to the preservation map rather than a decoded pixel-processing model. Structured XMP and language alternatives must retain their native shape; flattened aliases remain an interface feature. Metadata value conversions must say whether they are reversible and how information may be lost; they do not imply pixel or RAW-format conversion.

The upstream API exposes different value views and handles lists, structures, and binary values separately. Its `SetNewValue` queues mutations before `WriteInfo`, reinforcing the need to separate requested values from current extracted values. Imageinfo requires equivalent expressive power, without committing to the API's implementation language or exact calling conventions. [Upstream API contract](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/lib/Image/ExifTool.pod)

## Registries are reviewable product knowledge

Tag definitions and container layouts change as standards, devices, and firmware change. Make that knowledge versioned, independently reviewable, and testable.

Registry entries should include native IDs and aliases; descriptions and help; family/group taxonomy; applicable containers/device variants; stored type/cardinality; units and conversions; list/structure/language shape; allowed values; writing constraints; dependencies; unsafe/appearance/privacy classification; provenance; and linked fixture evidence. Schema validation must reject ambiguous IDs, broken dependencies, invalid shapes, and unsupported conversion declarations.

Prefer declarative definitions for ordinary tag descriptions, enums, mappings, units, and structural constraints. Provide a separate, bounded mechanism for transformations that cannot be declared as data. Do not hide arbitrary code execution inside a supposedly safe registry file. Changes to a tag name or conversion are observable product changes with changelog and compatibility consequences.

Generating help, capability reports, and public tag catalogs from the registry reduces drift. The registry must still distinguish a globally writable definition from an actual occurrence that cannot be written in a particular container or vendor variant.

Custom RAW/XMP definitions need the same validation and provenance rules as built-in definitions. ExifTool configuration examples contain both declarative custom definitions and executable callbacks. Migration should preserve in-scope use cases where possible, identify definitions for excluded formats, and report arbitrary code that requires translation; importing a configuration is a trust boundary. [Upstream extension examples](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/config_files/example.config)

## Editing is a planned transaction

Represent changes as explicit requests before writing: set, replace-list, add-list-item, remove-list-item, delete occurrence/group/block, copy with mapping, shift time, change filesystem attribute, or repair. Keep the original extraction snapshot separate from queued mutations and document the evaluation order for conditions, copying, derived values, and dependent changes.

A mutation plan must expose:

- Resolved source and destination occurrences, including default destination selection and conflicts.
- Requested values, conversion mode, validation results, and resulting values.
- Creation versus editing and format-specific restrictions.
- Implicit changes to counts, lengths, IFD/box/sample pointers, digests, linked metadata, or explicitly synchronized RAW/XMP families.
- Opaque content that can be preserved, content that must move, and preservation that cannot be guaranteed.
- Filesystem effects, paired-sidecar effects, backups, output collisions, and changed RAW interpretation or authenticity implications.

Plan inspection is available from both CLI and API. Preview must evaluate the same constraints as execution, while identifying facts that can only be confirmed when writing. A reusable plan needs an input-identity precondition so executing it against a changed file cannot silently produce a different result.

Stage writes and validate before final replacement. Define per-file success, failure, skipped, unchanged, and incomplete states. Batch operations can report partial success, but must not pretend the entire batch is one filesystem transaction. Cancellation should stop safely, preserve valid completed outputs according to policy, and leave a resumable record where appropriate.

Unknown fields are first-class content, not disposal candidates. A preserved blob with absolute pointers can become invalid when moved, so opaque copying requires a justified layout contract. Repair, ignoring corruption, stripping unknown content, and bypassing checks must be distinct explicit actions with meaningful outcomes.

### Protect sensor data and interpretation

RAW editing needs a protected-region map that identifies all sensor strips/tiles/samples and associated structural references, including alternate image planes where present. Validate byte identity of every protected payload after metadata mutation. Validate changed offsets, counts, box sizes, and required IFD/track relationships independently of the writer.

Preserve rendering-critical metadata by default: dimensions, bit depth, compression parameters, CFA arrangement, black/white levels, calibration/color matrices, active area/crop, profiles, and applicable DNG opcodes. Even identical sensor bytes can become unusable or render differently if those fields change. Classify potentially writable interpretation tags separately from descriptive/personal metadata and expose their effects in the plan.

Embedded previews remain protected encoded resources with metadata occurrences, references, and extraction capabilities. Inspection/extraction does not imply generic standalone JPEG/PNG support or preview generation. Required previews or vendor references must not disappear during unrelated edits.

Use independent RAW decoding/reader validation in the test pipeline to prove representative edited files remain usable. The production engine does not need a pixel developing feature to satisfy that validation requirement.

### RAW and XMP relationships

Represent a RAW file and its associated sidecar as a relationship with explicit discovery/naming rules. Preserve both source identities and origin locations in the model. A merged display can offer a chosen precedence policy, but must expose conflicts and permit an exhaustive view.

Embedded-XMP editing, sidecar-only editing, and synchronization are distinct requested operations. Creating a sidecar leaves RAW bytes untouched. Specify mapping rules, eligible tags, timestamp/identity checks for stale sidecars, and how unsupported RAW writes are reported. Batch copy/rename operations need coordinated RAW/sidecar plans and clear partial-success recovery; independent file replacements do not constitute an atomic pair.

## Bounded parsing and controlled effects

The core must treat metadata as data. Parsing must not evaluate source strings as code, invoke a shell with metadata-derived text, fetch external resources, or execute extension callbacks implicitly. Filename templates and batch expressions need specified syntax, escaping, limits, and failure behavior.

Apply cumulative budgets across nested content for bytes read, bytes decoded, decompression ratio/output, tag/record count, recursion, allocations, extracted files, expression work, and time. Validate arithmetic before allocation and validate every range against the correct container/base. Detect cycles and conflicting spans. A permissive recovery mode can extract useful content, but must keep diagnostics and completeness status visible.

Embedded extraction needs path confinement, collision controls, and a bounded output plan. Independent references such as XML entities or external sidecar links need explicit policies that do not silently read unrelated files or networks. Trusted extension activation is separate from opening a document.

Threat modeling and regression tests must cover recognizers, parsers, conversion rules, writers, config loading, filename handling, and OS integrations. Reduce privileges and isolate parsing where the eventual deployment requires it; the method remains undecided. Architecture should permit isolation without tying metadata operations to one host process model.

## Platform consistency and resource use

Require first-class Windows, macOS, and Linux behavior. State platform differences for filesystems and shell interaction rather than hiding them. Unicode paths, long paths, case-sensitive/case-insensitive volumes, links, timestamps, permissions, and streams belong in requirements and fixture planning.

Support bounded access to large RAW files and extraction that does not load all sensor payloads into memory. Expose seek requirements and meaningful stream errors. Parallel processing may improve throughput, but deterministic ordering and per-file outcomes remain specified behaviors. Persistent request sessions must isolate state, handle EOF/cancellation, and prevent one request's options or queued writes from leaking into the next.

“Fast” modes must report their completeness tradeoff and list which regions or families were skipped. Performance goals require a published workload and measured latency/memory/throughput budgets; no language or library can substitute for those measurements.

## Maintainability and shared ownership

Reducing dependence on one maintainer is an organizational requirement, not something a syntax change can accomplish. Require:

- At least two trained reviewers/maintainers for critical format families and release operations as the project grows.
- Contributor documentation, fixture generators, format notes, and reproducible debugging procedures sufficient for a new contributor to fix a parser without private knowledge.
- Public ownership records, issue triage rules, review criteria, and a documented process for disagreements and compatibility exceptions.
- Release instructions, credential/access succession, security reporting, and recovery procedures that do not depend on one person's machine/account.
- Evidence-linked registry changes and small, reviewable parser changes; every regression becomes an explained fixture.
- Automated validation and platform evidence tied to each published release, with transparent support limitations.
- Versioned API/output schemas, deprecation rules, migration notes, and observable behavior changes recorded in release notes.

Contributors should be credited and upstream research acknowledged. Avoid framing ExifTool's language or maintainer as evidence that its behavior is inherently deficient. Its accumulated format knowledge is a major compatibility asset to understand. Imageinfo's responsibility is to make equivalent knowledge safer to change, easier to inspect, and maintainable by a team.

## Decisions deferred

Do not choose or rank implementation languages yet. Runtime dependencies, parser libraries, platform bindings, distribution forms, extension execution technology, and build/CI tools remain open. Once the inventory, data model, mutation guarantees, threat model, corpus rules, and CLI contract are agreed, evaluate candidate technologies against those constraints with prototypes and measurements.

Early implementation should prove a camera RAW end-to-end slice: correct extraction, typed occurrence preservation, discoverable help, planned editing, independent sensor-payload/structure validation, and evidence-based support reporting. Expand RAW breadth by verified capability cells, keeping related XMP/preview workflows explicit. Maintain the full ExifTool inventory as the eventual parity roadmap; wider format delivery is deferred beyond the initial RAW phase.
