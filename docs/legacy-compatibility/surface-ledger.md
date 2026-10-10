# Surveyed surface ledger

Proposal `2026-10-10.1`. All **32** [inventory MAP families](../inventory/README.md)
receive a disposition below. Upstream tokens are representative identifiers; the
inventory retains the fuller previously surveyed lists and source references.
This is not an exhaustive flag/alias/API-option audit or a runtime parity claim.

**Equivalent-proposed** means the named functional use case has a native proposal.
**Difference-proposed** means a material observable change needs migration review.
**Open-gap** means a specific part is still unspecified. A difference is not accepted
until reviewed; an unsupported diagnostic does not implement the missing function.

| Family | Representative legacy surface | Disposition | Native contract / acceptance consequence |
| --- | --- | --- | --- |
| MAP-001 | `-listw`, `-listx`, `-ver` | Difference-proposed | Discover camera/location/operation limits; global writable names never enable a specific occurrence. |
| MAP-002 | `-TAG`, `-GROUP:TAG`, `-x` | Equivalent-proposed | Explicit read selection/exclusion; aliases map to native identity. Wildcard expansion needs a bounded, listed match set. |
| MAP-003 | `-a`, `-G`, `-g`, `-sort` | Difference-proposed | Occurrences survive independently; deterministic source order and explicit projection replace duplicate suppression. |
| MAP-004 | `-n`, `TAG#`, `-d`, `-sep` | Difference-proposed | Choose normalized/raw/display views explicitly; no equivalence between disabling display conversion and exact stored bytes. |
| MAP-005 | `-struct`, `--struct` | Difference-proposed | Preserve typed lists, structures and language entries; flattening is a declared lossy projection. |
| MAP-006 | `-b`, `-w`, `-W` | Difference-proposed | Select one asset for binary stdout or explicit no-clobber artifacts; multiple assets require separately identified outputs. |
| MAP-007 | `-s`, `-j`, `-csv`, `-X` | Difference-proposed | Native envelopes and fixed CSV projection differ; old consumers need field/shape adapters, not flag substitution. |
| MAP-008 | `-p`, `-args`, `-php`, `-plot` | Open-gap | LG-002: exact report serializers, template escaping and legacy replay formats remain unverified/specification work. |
| MAP-009 | `-TAG=`, `-TAG+=`, `-TAG<=` | Difference-proposed | Typed set/delete/list/time intents; reject ambiguous overloads and treat file payloads as explicit bound sources. |
| MAP-010 | `-GROUP:All=`, `-All=` | Difference-proposed | Scope deletions to eligible occurrences; retain RAW interpretation/payload and disclose privacy residuals. No blanket wipe translation. |
| MAP-011 | `-wm`, `WriteMode` | Equivalent-proposed | Distinguish update from explicit insertion and required group creation; preview mandatory coupled changes. |
| MAP-012 | `-tagsFromFile`, `-all:all` | Difference-proposed | Frozen copy sources and named mappings; preserve-location requests refuse unsupported destinations rather than relocating silently. |
| MAP-013 | `-j=`, `-csv=`, `SourceFile` | Difference-proposed | Explicit target matching and typed intent. Report unmatched rows; empty cells never imply deletion. Exact legacy import decoding is LG-002. |
| MAP-014 | `-srcfile`, output templates | Difference-proposed | CW-006 pairing and explicit source/destination mapping; no inferred file substitution or overwrite. |
| MAP-015 | `-r`, `-if`, `-fileOrder` | Difference-proposed | CW selection plus pure filters; hidden-file defaults, order and empty selection can differ. Arbitrary expressions are LG-003. |
| MAP-016 | `-fast`, `-ee`, `-u`, `-scanForXMP` | Difference-proposed | State exact coverage and limits for each mode; no numeric level-to-level equivalence without per-variant evidence. |
| MAP-017 | `FileName`, `Directory`, `TestName` | Difference-proposed | Explicit file operations with pairing/collision/recovery plans. Complex naming placeholders remain LG-002. |
| MAP-018 | `AllDates`, date `+=`, `-globalTimeShift` | Equivalent-proposed | Declare field set, calendar/duration/offset semantics and unknown zones; legacy shape/inverse conversion needs recorded cases. |
| MAP-019 | `Geotime`, `Geosync`, `-geotag` | Equivalent-proposed | Track-clock correction is separate from changing stored capture time; show interpolation, missing-zone and target policy. |
| MAP-020 | `Geolocation`, `-listgeo` | Open-gap | LG-005: lookup datasets, licensing, offline behavior and reverse-export fidelity are not chosen. |
| MAP-021 | overwrite/restore/original utilities | Difference-proposed | WS recovery and explicit apply override legacy overwrite habits; no-backup retains temporary recovery through success. |
| MAP-022 | `-validate`, `-F`, `-m` | Difference-proposed | Validation and repair are separate operations; warnings/minor-error suppression cannot disable preservation gates. Detailed repair is LG-005. |
| MAP-023 | `-stay_open`, `-execute`, `-common_args` | Difference-proposed | Framed request-local native session; migration reports persistent settings/order differences. No legacy ready-marker compatibility claimed. |
| MAP-024 | `-@`, `--`, `-charset filename` | Difference-proposed | Explicit token-array requests and JSON/NUL manifests; request file paths have a fixed base. Argument-file recursion/encodings need LG-001 evidence. |
| MAP-025 | `-q`, `-progress`, `-efile`, exit status | Difference-proposed | Typed per-file results, plain stderr and native precedence. Completion and success are distinct. |
| MAP-026 | `-config`, `-use`, `-userParam` | Open-gap | Declarative definitions/pure parameters proposed; LG-003 retains arbitrary code/module equivalence and trust decisions. |
| MAP-027 | `ImageInfo`, `ExtractInfo`, `GetInfo` | Equivalent-proposed | Read once to an immutable snapshot; query/project it repeatedly with explicit input ownership and coverage. |
| MAP-028 | `GetValue`, tag/group lookup methods | Equivalent-proposed | Exact occurrence selection, separate representations and native identity; descriptions are presentation. |
| MAP-029 | `SetNewValue`, `WriteInfo`, save/restore queue | Difference-proposed | Explicit reusable intent values and per-target plans; no ambient queued mutation state. |
| MAP-030 | `SetNewValuesFromFile` | Difference-proposed | Source snapshot plus mapping/loss policy, then preview/apply. Snapshot values never confer destination permission. |
| MAP-031 | tag/type/static discovery methods | Equivalent-proposed | Distinguish definition availability, observed file structure and actual enabled operations. |
| MAP-032 | `Options`, `RequestTags`, `FastScan` | Open-gap | LG-001: classify every remaining option independently; do not pass arbitrary options through to an undeclared backend. |

## Library coverage beyond the family headings

The pinned [API reference](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/lib/Image/ExifTool.pod)
provides the following named entry points. This grouping records a proposed native
role rather than copying its object model. Optional arguments, overloads and every
option value remain LG-001 until individually tested.

| Native role | Surveyed API names | Proposed disposition |
| --- | --- | --- |
| Request settings | `new`, `Options`, `ClearOptions`, `AvailableOptions` | Difference: immutable explicit options; reusable settings do not leak edits. |
| Extraction/query | `ImageInfo`, `ExtractInfo`, `GetInfo`, `GetTagList`, `GetFoundTags`, `GetRequestedTags` | Equivalent functional intent; preserve partial/requested/found distinctions in coverage and selectors. |
| Values/identity | `GetValue`, `GetTagID`, `GetDescription`, `GetGroup`, `GetGroups`, `GetTagName` | Equivalent functional intent; exact occurrence and explicit view replace context-dependent return conventions. |
| Intent lifetime | `SetNewValue`, `GetNewValue`, `CountNewValues`, `SaveNewValues`, `RestoreNewValues`, `WriteInfo` | Difference: inspect/copy immutable intents, separately plan each target and apply with WS gates. |
| Copy/context | `SetNewValuesFromFile`, `SetAlternateFile`, `SetNewGroups`, `GetNewGroups` | Difference: explicitly bound sources/locations and visible mappings. |
| Filesystem effects | `SetFileName`, `SetFileModifyDate` | Difference: planned file effects and property policy; no hidden setters during a read. |
| Discovery | `GetShortcuts`, `GetAllTags`, `GetWritableTags`, `GetAllGroups`, `GetDeleteGroups`, `GetFileType`, `CanWrite`, `CanCreate` | Equivalent functional questions; return scoped definitions/evidence, not universal write permission. |
| Extension/ordering | `BuildCompositeTags`, `AddUserDefinedTags`, `OrderedKeys` | Declarative dependency/order requirements proposed; arbitrary extension behavior remains LG-003. |

This covers all 39 method headings in the pinned API's METHODS section, including
static entries. Encoding-section headings are not methods. It does not claim ABI,
call signature, pointer/handle, error-return or executable compatibility.

## Explicit open gaps

| ID | Unresolved part | Required closure evidence / owner |
| --- | --- | --- |
| LG-001 | Exhaustive grammar, abbreviations, aliases, API options and ordering interactions | Expand token/option-level cases against the pinned executable on lawful fixtures; record each difference. Compatibility evidence follow-up, with corpus #0013. |
| LG-002 | Exact legacy reports/imports, templates, filename formatting and serialization adapters | Specify field/encoding/escaping/lookup rules with collision, newline, duplicate and round-trip cases. Compatibility follow-up; no exact serializer claimed here. |
| LG-003 | Arbitrary executable expressions, modules and user-defined parsing/conversion | Choose an explicit trusted-code model later; document provenance, authority and failure isolation. No automatic execution or invented sandbox guarantee. |
| LG-004 | Complete persisted plan grammar for all operations | The WS-002 field obligations remain binding. A complete per-operation wire schema needs actual planner effects, platform identities and recovery profiles; this card supplies request/result schemas, not a fake universal executable plan. |
| LG-005 | Advanced lookup datasets, repair, unusual flags and mapping catalogs | Separate scoped requirements and lawful resources; preserve every unmet functional goal in the ledger. |
| LG-006 | Actual CLI/API/process behavior, precision, performance and robustness | Real implementation, reference binaries, OS/stream tests and user review. Synthetic records do not close this gap; #0008/#0013/#0014 supply prerequisites. |

Current gap ownership is recorded on the local compatibility follow-up and in
inventory GAP-006/GAP-012. These open items prevent full/drop-in parity claims;
they do not disappear because a migration report can explain them. Non-RAW behavior
remains separately deferred under the long-term full-parity roadmap.
