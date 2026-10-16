# RAW compatibility delivery matrix (#0120)

Revision `2026-10-16.1`. This matrix assigns all **32 MAP families**, **39 API
method headings**, and **LG-001–006 / GAP-006 / GAP-012** requirements to current
evidence, existing finite work and an explicit unmet residual. It completes the
requirements reconciliation; it establishes no additional runtime capability.

The [machine-readable matrix](delivery-matrix.v1.json) retains every inventory MAP
record (including upstream forms, target, acceptance, capability and gap references)
and both inventory gap records unchanged. It retains each LG unresolved clause and
closure obligation from the [surface ledger](surface-ledger.md). These are coverage
denominators, never parity percentages. All rows remain incomplete as full families.

The baseline is pinned ExifTool 13.59 source commit
`2200871d9cef988051d2a99d67df3bda6cbb30a8`, observed in the existing
[inventory](../inventory/README.md); this work performs no new upstream or media
comparison. Native evidence references are the scoped, dated public reports already
in the repository, not proof of all overloads/options or reference equivalence.
The parallel #0121 native-token inventory freezes the finite current surface; its
evidence is an input to #0122–0125/#0134, not closure of this denominator.

RAW-first and EOS R5 full RAW CR3 remain the engineering priority, followed by
paired XMP/stored previews and admitted new-CR3 outputs before broader mutation.
Other RAW families remain required future expansion; non-RAW full parity stays
deferred under #0012. No requirement is reduced because a difference is documented.
Ordinary engineering within authorized scopes needs no renewed adoption approval.

`Next` names existing ticket owners in the [remaining-work map](../remaining-work.md).
These tickets finish only their stated finite slices. #0015 retains every RAW
residual below, including functions beyond those slices. Refusal/model/specification
evidence cannot satisfy a positive implementation requirement. Every mutation also
retains independent format, byte/name, property, persistence, custody/recovery and
storage-profile admission; this matrix grants none of them. VM-off best-effort testing
uses the [current policy](../write-safety/power-test-policy.md).

Engineering order is inventory/read/preview/query, report/translation/schema work,
pure/data and planner/date contracts, isolation/shell/robustness, then #0141 coverage
audit. Dependency order does not change priority or turn a tracking residual into
an implementation claim. The JSON records the exact order and row assignments.

## Family delivery

Each current-evidence link documents its own finite tests and limits. The complete
original targets and acceptance clauses remain in the JSON `requirement` records.

| Family | Current evidence / implemented boundary | Next | Unmet residual (owner #0015) |
| --- | --- | --- | --- |
| MAP-001 — Capability discovery | [Built-in version and finite discovery definitions only.](../foundation/README.md) | #0121, #0134 | Global tag/group/type inventories, per-occurrence writable/create discovery and reference option equivalence remain unmet. |
| MAP-002 — Tag inclusion, exclusion and groups | [Finite native --tag selection and current selector behavior.](read-argument-order.md) | #0121, #0122 | Legacy aliases, exclusion, wildcard/group expansion and ordering combinations beyond enumerated vectors remain unmet. |
| MAP-003 — Duplicates, families and ordering | [Occurrence records retain source identity and finite native ordering.](native-read-json.md) | #0122, #0134 | All duplicate/grouping/sort projections and upstream suppression/order equivalence remain unmet. |
| MAP-004 — Value layers and display conversion | [Bounded raw/normalized/display JSON observations retain stored-value ranges.](native-read-json.md) | #0122, #0126 | General print conversion, date/list separators, locale and TAG# equivalence remain unmet. |
| MAP-005 — Structured XMP | [Bounded production in-memory UTF-8 XML/XMP packet inspection with typed properties, source retention and edit-constraint checks; no CLI XML read or serializer.](../sidecars/packet-profile.md) | #0184, #0185, #0186 | General lists, structures, language alternatives, flattening, full XML/RDF/XMP conformance, qualified media admission, round-trip writing and publication remain unmet. |
| MAP-006 — Binary extraction and routing | [Finite stored-preview listing and exact no-clobber extraction; extraction is not JPEG decoding.](../reader/README.md) | #0123, #0124 | All binary stdout/routing/template forms, variants and reference/native differences remain unmet. |
| MAP-007 — Human and machine reports | [Partial native read JSON contract and finite existing CLI envelopes.](native-read-json.md) | #0126, #0127 | Exact legacy JSON/CSV/XML/text output, all operations and lossy-projection/adapter rules remain unmet. |
| MAP-008 — Advanced report and serialization forms | [Worked inert migration examples and proposed serializers only.](migration.md) | #0126, #0129, #0130 | Print templates, escaping, -args/-php/-plot and exact replay/report serialization remain unmet. |
| MAP-009 — Assignment, lists and file-sourced values | [One nonexecuting existing fixed-width date intent and preview; mutation admission refuses.](cr3-preview-plan.md) | #0132, #0078 | General set/delete/list/append/file-value intents and production apply remain unmet. |
| MAP-010 — Tag/group deletion | [Read-only catalog coverage; no production removal.](../privacy/read-coverage.md) | #0188, #0189, #0190, #0089, #0090 | Group/all deletion, GPS/serial/owner residual accounting and independently qualified anonymity remain unmet; targeted XMP work is not blanket wipe. |
| MAP-011 — Creation and update modes | [Read-only bounded date admission/refusal checks; no writer.](../write-safety/write-admission.md) | #0117, #0119, #0078 | General existing update, insertion/group creation and reference WriteMode equivalence remain unmet. |
| MAP-012 — Copy and redirection | [One original-snapshot date mapping model and native adapter research.](../sidecars/date-mapping.md) | #0132, #0186, #0085, #0086 | General copy/redirection, all:all location preservation, mappings and qualified publication remain unmet. |
| MAP-013 — JSON/CSV imports | [Inert import/translation proposals only.](migration.md) | #0126, #0129, #0130 | JSON/CSV decoders, row/target matching, duplicates, empty/null semantics and loss accounting remain unmet. |
| MAP-014 — Sidecar association and metadata mapping | [Explicit safe physical-file RAW/XMP pairing; no basename inference.](../sidecars/pairing.md) | #0124, #0182, #0186 | General srcfile/template substitution and mapping remain unmet; opt-in same-stem inference and guarded derivative binding have separate owners. |
| MAP-015 — Input traversal and filtering | [Pure filter/data-definition boundary specified; no filter runtime.](executable-extension-boundary.md) | #0131, #0129 | Traversal, hidden-file/order/empty-selection and pure filter implementation remain unmet; arbitrary expressions stay explicit future functional residuals. |
| MAP-016 — Fast, unknown and embedded extraction | [Declared bounded R5 parser/coverage and stored-preview slice.](../reader/README.md) | #0121, #0122, #0123 | Each fast/unknown/embedded/scan mode and variant needs separate evidence; numeric level equivalence is unmet. |
| MAP-017 — Filesystem and date organization | [Authored-marker file/restore research only; no production rename/move.](../write-safety/fresh-name-restore.md) | #0132, #0201, #0202, #0212, #0213 | General naming placeholders, directory/date organization, collision, recovery and actual RAW-XMP operations remain unmet. |
| MAP-018 — Date shifts | [Four bounded date fields, observation/refusal matrix and one fixed-width preview.](r5-date-mapping.md) | #0133, #0132, #0078 | AllDates field sets, calendar/duration/offset/zone semantics, inverse conversions and general date writes remain unmet. |
| MAP-019 — Geotagging and clock correction | [No track interpolation/geotagging implementation; date lookup evidence is not geotagging.](r5-date-mapping.md) | #0133 | Track ingestion, clock correction, interpolation, missing zones, mapping and target policy remain unmet scoped residuals under #0015/#0012. |
| MAP-020 — Geolocation lookup and inverse export | [No lookup dataset or reverse-geolocation implementation.](r5-date-mapping.md) | #0133 | Lawful datasets/licensing, offline lookup, inverse export and reference fidelity remain unmet. |
| MAP-021 — Backups, overwrite and output policy | [Marker retention/restore research; no qualified production replacement profile.](../write-safety/original-retention.md) | #0165, #0176, #0198, #0199, #0200, #0206 | Production original retention, no-backup recovery through success, overwrite/restore/prune and profile-specific persistence remain unmet. |
| MAP-022 — Diagnostics and repair controls | [Bounded parser/preview/admission diagnostics; no repair.](../write-safety/write-admission.md) | #0133, #0132 | General validation/repair and unusual flags remain unmet; suppression never bypasses preservation or admission. |
| MAP-023 — Ordered and persistent execution | [Actual bounded v1 read/close JSONL process and caller-owned library runtime.](read-session-process.md) | #0125, #0128, #0135, #0139, #0140 | Legacy ready markers/common settings/order, concurrency, cancellation, non-Unicode wire paths and broader sessions remain unmet. |
| MAP-024 — Argument/request files and filenames | [Finite native OsString argv, -- and declared-shell paths; in-process token-array API.](native-paths.md) | #0121, #0125, #0129, #0136, #0137 | Request files, recursive argument files, encodings, manifests and exact legacy charset/expansion behavior remain unmet. |
| MAP-025 — Warnings, progress and status | [Actual finite CLI status/error envelopes and read-session transport outcomes.](native-json-errors.md) | #0127, #0128, #0136, #0138, #0139, #0140 | General quiet/progress/error-file behavior, cancellation/precision/performance and narrow-terminal robustness remain unmet. |
| MAP-026 — Custom definitions and expressions | [Accepted bounded pure/data direction does not implement a runtime.](executable-extension-boundary.md) | #0131 | Arbitrary modules/config/user code, custom calculations, execution trust/failure isolation and future equivalence remain unmet; no automatic execution. |
| MAP-027 — Extraction lifecycle | [Native reader Metadata and bounded metadata-read request/result API.](read-request-result.md) | #0134, #0135 | Full snapshot lifecycle, repeated query/project operations, requested/found distinctions and upstream call signatures remain unmet. |
| MAP-028 — Identity and values | [Bounded occurrence identity/value views in native Metadata and JSON.](native-read-json.md) | #0134 | Complete lookup/group/description APIs, all identities/value forms and return conventions remain unmet. |
| MAP-029 — Queued mutation lifetime | [Reusable nonexecuting saved one-date intent; no ambient mutation queue.](cr3-preview-plan.md) | #0132, #0078 | General intent construction/inspection/save/restore and qualified per-target write lifecycle remain unmet. |
| MAP-030 — Copy/mapping lifecycle | [Separate immutable native date to in-memory XMP derivative research.](../sidecars/native-date-adapter.md) | #0132, #0186, #0085, #0086 | General copy/context/mapping intent lifetime, source binding and per-target publication remain unmet. |
| MAP-031 — Static discovery versus detection | [Finite built-in declarations and bounded actual format detection; admission remains separate.](../foundation/README.md) | #0134, #0117 | All static tag/group/shortcut/type and scoped writable/create questions remain unmet beyond current declarations. |
| MAP-032 — Option families | [Finite actual native grammar and read options only.](read-argument-order.md) | #0121, #0134 | Every upstream Options/RequestTags/FastScan value, overload, alias and interaction remains individually unqualified. |

## Every API method heading

Each name is individually assigned; grouping does not omit overloads/options from
the remaining requirement. No native method-name, ABI or calling-signature parity
is claimed. Present evidence and exact residuals inherit the linked MAP row in the
JSON; these rows do not imply that a similarly named native API already exists.

| API heading | Native role / MAP | Next | Full API requirement |
| --- | --- | --- | --- |
| `new` | Request settings / MAP-032 | #0121, #0134 | Explicit construction, option defaults, input ownership and reusable-instance lifetime. Unmet beyond finite MAP evidence; #0015 retains full options/overloads. |
| `Options` | Request settings / MAP-032 | #0121, #0134 | Every option name/value, getter/setter interaction and request-local precedence. Unmet beyond finite MAP evidence; #0015 retains full options/overloads. |
| `ClearOptions` | Request settings / MAP-032 | #0121, #0134 | Exact reset/default behavior and isolation from other requests and intents. Unmet beyond finite MAP evidence; #0015 retains full options/overloads. |
| `AvailableOptions` | Request settings / MAP-032 | #0121, #0134 | Complete option discovery and valid value/capability distinctions. Unmet beyond finite MAP evidence; #0015 retains full options/overloads. |
| `ImageInfo` | Extraction/query / MAP-027 | #0134, #0135 | Combined extraction/query lifecycle, all input forms and partial/error results. Unmet beyond finite MAP evidence; #0015 retains full options/overloads. |
| `ExtractInfo` | Extraction/query / MAP-027 | #0134, #0135 | Read-once snapshot extraction, ownership and retained-data lifetime. Unmet beyond finite MAP evidence; #0015 retains full options/overloads. |
| `GetInfo` | Extraction/query / MAP-027 | #0134, #0135 | Repeated snapshot query/projection without rereading or hidden side effects. Unmet beyond finite MAP evidence; #0015 retains full options/overloads. |
| `GetTagList` | Extraction/query / MAP-027 | #0134, #0135 | Requested snapshot tag lists, duplicate occurrences and ordering. Unmet beyond finite MAP evidence; #0015 retains full options/overloads. |
| `GetFoundTags` | Extraction/query / MAP-027 | #0134, #0135 | Found-versus-requested sets with partial coverage and exact occurrences. Unmet beyond finite MAP evidence; #0015 retains full options/overloads. |
| `GetRequestedTags` | Extraction/query / MAP-027 | #0134, #0135 | Requested-versus-found sets including absent, unknown and refused selectors. Unmet beyond finite MAP evidence; #0015 retains full options/overloads. |
| `GetValue` | Values/identity / MAP-028 | #0134 | Exact occurrence selection and raw/normalized/display forms for every supported type. Unmet beyond finite MAP evidence; #0015 retains full options/overloads. |
| `GetTagID` | Values/identity / MAP-028 | #0134 | Complete native identifiers, location/occurrence identity and unknown identifiers. Unmet beyond finite MAP evidence; #0015 retains full options/overloads. |
| `GetDescription` | Values/identity / MAP-028 | #0134 | Localized descriptions as presentation, without changing identity. Unmet beyond finite MAP evidence; #0015 retains full options/overloads. |
| `GetGroup` | Values/identity / MAP-028 | #0134 | Single-occurrence group-family lookup with explicit family selection. Unmet beyond finite MAP evidence; #0015 retains full options/overloads. |
| `GetGroups` | Values/identity / MAP-028 | #0134 | Complete observed group enumeration and deterministic grouping. Unmet beyond finite MAP evidence; #0015 retains full options/overloads. |
| `GetTagName` | Values/identity / MAP-028 | #0134 | Canonical name/alias lookup with exact native occurrence identity. Unmet beyond finite MAP evidence; #0015 retains full options/overloads. |
| `SetNewValue` | Intent lifetime / MAP-029 | #0132, #0078 | General typed intent construction, delete/append distinctions and validation. Unmet beyond finite MAP evidence; #0015 retains full options/overloads. |
| `GetNewValue` | Intent lifetime / MAP-029 | #0132, #0078 | Inspect pending immutable intents without implying applied target state. Unmet beyond finite MAP evidence; #0015 retains full options/overloads. |
| `CountNewValues` | Intent lifetime / MAP-029 | #0132, #0078 | Exact intent counts, duplicate targets and rejected/removed intent behavior. Unmet beyond finite MAP evidence; #0015 retains full options/overloads. |
| `SaveNewValues` | Intent lifetime / MAP-029 | #0132, #0078 | Explicit immutable intent save semantics and reusable-value ownership. Unmet beyond finite MAP evidence; #0015 retains full options/overloads. |
| `RestoreNewValues` | Intent lifetime / MAP-029 | #0132, #0078 | Explicit intent restore semantics without ambient edits or transferred authority. Unmet beyond finite MAP evidence; #0015 retains full options/overloads. |
| `WriteInfo` | Intent lifetime / MAP-029 | #0132, #0078 | Actual per-target planning/apply with admitted format/storage and truthful outcomes. Unmet beyond finite MAP evidence; #0015 retains full options/overloads. |
| `SetNewValuesFromFile` | Copy/context / MAP-030 | #0132, #0186, #0085, #0086 | Frozen source snapshot, mapping/loss policy and destination-specific authority. Unmet beyond finite MAP evidence; #0015 retains full options/overloads. |
| `SetAlternateFile` | Copy/context / MAP-030 | #0132, #0186, #0085, #0086 | Explicit bound alternate source resolution, order and failure behavior. Unmet beyond finite MAP evidence; #0015 retains full options/overloads. |
| `SetNewGroups` | Copy/context / MAP-030 | #0132, #0186, #0085, #0086 | Explicit destination group intent and group-creation feasibility. Unmet beyond finite MAP evidence; #0015 retains full options/overloads. |
| `GetNewGroups` | Copy/context / MAP-030 | #0132, #0186, #0085, #0086 | Inspect intended destination groups separately from observed file groups. Unmet beyond finite MAP evidence; #0015 retains full options/overloads. |
| `SetFileName` | Filesystem effects / MAP-017 | #0132, #0201, #0202, #0212, #0213 | Planned rename/move with collision, pairing, identity and recovery evidence. Unmet beyond finite MAP evidence; #0015 retains full options/overloads. |
| `SetFileModifyDate` | Filesystem effects / MAP-017 | #0132, #0201, #0202, #0212, #0213 | Explicit filesystem timestamp plan, property preservation and precision. Unmet beyond finite MAP evidence; #0015 retains full options/overloads. |
| `GetShortcuts` | Discovery / MAP-031 | #0134, #0117 | Complete alias/shortcut discovery with expansion and namespace collisions. Unmet beyond finite MAP evidence; #0015 retains full options/overloads. |
| `GetAllTags` | Discovery / MAP-031 | #0134, #0117 | Definition inventory separate from actual observed file presence. Unmet beyond finite MAP evidence; #0015 retains full options/overloads. |
| `GetWritableTags` | Discovery / MAP-031 | #0134, #0117 | Scoped operation discovery distinct from per-target admission. Unmet beyond finite MAP evidence; #0015 retains full options/overloads. |
| `GetAllGroups` | Discovery / MAP-031 | #0134, #0117 | Complete static group definitions separate from observed file structure. Unmet beyond finite MAP evidence; #0015 retains full options/overloads. |
| `GetDeleteGroups` | Discovery / MAP-031 | #0134, #0117 | Scoped deletable-group discovery with protected-data and privacy residuals. Unmet beyond finite MAP evidence; #0015 retains full options/overloads. |
| `GetFileType` | Discovery / MAP-031 | #0134, #0117 | Qualified variant/container detection beyond extension or mutable model names. Unmet beyond finite MAP evidence; #0015 retains full options/overloads. |
| `CanWrite` | Discovery / MAP-031 | #0134, #0117 | Exact format/location/operation eligibility separate from a writable tag table. Unmet beyond finite MAP evidence; #0015 retains full options/overloads. |
| `CanCreate` | Discovery / MAP-031 | #0134, #0117 | Absent-value/group creation eligibility, never generation of RAW sensor content. Unmet beyond finite MAP evidence; #0015 retains full options/overloads. |
| `BuildCompositeTags` | Extension/ordering / MAP-026 | #0131 | Declarative dependencies, cycle/coverage handling and custom calculation residuals. Unmet beyond finite MAP evidence; #0015 retains full options/overloads. |
| `AddUserDefinedTags` | Extension/ordering / MAP-026 | #0131 | Explicit versioned definitions, provenance/collisions and executable-parser residuals. Unmet beyond finite MAP evidence; #0015 retains full options/overloads. |
| `OrderedKeys` | Extension/ordering / MAP-026 | #0131 | Complete deterministic dependency/key ordering and caller-visible order semantics. Unmet beyond finite MAP evidence; #0015 retains full options/overloads. |

## Gap closure remains complete

| Gap | Retained closure obligation | Existing finite owners / residual |
| --- | --- | --- |
| LG-001 | Expand token/option-level cases against the pinned executable on lawful fixtures; record each difference. Compatibility evidence follow-up, with corpus #0013. | #0121, #0122, #0123, #0124, #0125, #0129, #0134, #0141; #0015 retains the complete unmet clause. |
| LG-002 | Specify field/encoding/escaping/lookup rules with collision, newline, duplicate and round-trip cases. Compatibility follow-up; no exact serializer claimed here. | #0126, #0127, #0128, #0129, #0130; #0015 retains the complete unmet clause. |
| LG-003 | Choose an explicit trusted-code model later; document provenance, authority and failure isolation. No automatic execution or invented sandbox guarantee. | #0131; #0015 retains the complete unmet clause. |
| LG-004 | The WS-002 field obligations remain binding. A complete per-operation wire schema needs actual planner effects, platform identities and recovery profiles; this card supplies request/result schemas, not a fake universal executable plan. | #0132; #0015 retains the complete unmet clause. |
| LG-005 | Separate scoped requirements and lawful resources; preserve every unmet functional goal in the ledger. | #0133; #0015 retains the complete unmet clause. |
| LG-006 | Real implementation, reference binaries, OS/stream tests and user review. Synthetic records do not close this gap; #0013/#0014/#0016 supply evidence under the #0008 measurement protocol. | #0122, #0123, #0124, #0125, #0127, #0128, #0134, #0135, #0136, #0137, #0138, #0139, #0140, #0141, #0142, #0143, #0144, #0145, #0146, #0147, #0148, #0149, #0150, #0151, #0152; #0015 retains the complete unmet clause. |
| GAP-006 | The surveyed surface ledger and migration/trust recommendations are in docs/legacy-compatibility. Close LG-001/LG-002/LG-003/LG-005/LG-006 through exhaustive option/API/ordering cases, accepted differences and actual reference/native evidence before claiming full or drop-in parity. | #0121, #0122, #0123, #0124, #0125, #0126, #0127, #0128, #0129, #0130, #0131, #0132, #0133, #0134, #0135, #0136, #0137, #0138, #0139, #0140, #0141, #0142, #0143, #0144, #0145, #0146, #0147, #0148, #0149, #0150, #0151, #0152; #0015 retains the complete unmet clause. |
| GAP-012 | CLI walkthroughs, request/result schemas, pure filter and persistent-session proposals are recorded. Complete saved-plan and session-output schemas, advanced mappings and remaining LG-001–006 specifications on #0015; use the #0008 performance protocol to establish measured limits on #0016 and later prove actual CLI/help/menu/transport behavior. | #0121, #0122, #0123, #0124, #0125, #0126, #0127, #0128, #0129, #0130, #0131, #0132, #0133, #0134, #0135, #0136, #0137, #0138, #0139, #0140, #0141, #0142, #0143, #0144, #0145, #0146, #0147, #0148, #0149, #0150, #0151, #0152; #0015 retains the complete unmet clause. |

The original ledger's prospective “accepted differences” language does not create
a fresh approval gate for this authorized preparation. It also does not mean that
any unexplained or unevidenced difference has been accepted. #0131 refines the
already selected pure/data boundary while arbitrary executable behavior remains
an explicit unmet functional requirement. #0132 allocates actual per-operation
WS-002 contracts; a saved one-date preview never becomes a universal apply plan.
#0133 retains lawful lookup resources and validation/repair separation.

## Verification

Run `python scripts/check_compat_delivery.py` and `python scripts/check_docs.py`.
The dedicated checker compares all original MAP and GAP records exactly, all 39
method names and proposed roles, and every LG clause; requires row-level evidence,
existing-ticket assignments and residual owners; checks local evidence paths; and
checks false parity/mutation authority flags and the document denominator. It does
not run media operations, assert ticket completion or replace runtime qualification.
