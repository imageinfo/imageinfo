# Finite RAW/XMP operation matrix (#0117)

Revision **2026-10-17.1**. The [machine ledger](raw-xmp-operation-matrix.v1.json)
retains 20 selected operation/residual rows, every original #0014 acceptance
paragraph, all **80** SAF/TX/VAL/REC/BKP/GRP criteria and all **22** existing
`proposal:*` identities in the metadata-model examples. This is a requirements
inventory. No row grants a production mutation, storage profile or imported-plan
authority, and none completes #0014, GAP-004 or GAP-009.

The first increment remains **one unique existing CMT2 Exif `0x9003`
DateTimeOriginal, ASCII20, into a new absent CR3 output**. Its current outcome is
**refused**: [opaque dependencies and coupled effects](write-admission.md) have
no positive independent admission under the unchanged preservation contract.
Exact complements, matching RAW unpack and authored reference controls do not
resolve that gap. #0119 owns that exact admission; #0078 owns the apply bridge
only after actual format and storage admission. This matrix does not replace
those owners with a new generic implementation card.

Terry already authorized this scope and engineering selection. Subsequent work
uses the existing owners and the concrete finish lines below. Ordinary property
selection, decomposition and specification need no renewed adoption decision.
An actual weakening of the original preservation guarantee remains the separate
Terry-only `format_contract_decision`; automatic refusal remains the safe result
while technical evidence is missing.

## Exact operations and outcomes

Every row in the ledger records operation, tag/property identity, container and
location, raw/normalized input view, preservation basis, owner allocation,
actual prerequisites, evidence and its next bounded finish line. Owner numbers
allocate work; they do not claim that a card or its prerequisites are complete.
“Unverified” means no positive end-to-end mutation claim, even where an in-memory
mechanism already exists. “Refused” is a specific unsupported current admission,
not successful implementation of the requested positive operation.

| Ledger row | Exact selection and view | Current outcome; existing finish-line owner |
| --- | --- | --- |
| `cr3-date-new` | Unique full-RAW CMT2 Exif `0x9003`, original allocation, raw ASCII20; calendar validation does not infer a zone. | Refused; #0119 independent dependency admission, #0078 actual adapter, #0080 preservation evidence; #0176 storage admission remains independent. |
| `xmp-date-new` | Existing singleton `{http://ns.adobe.com/exif/1.0/}DateTimeOriginal` in an explicitly selected packet; original RAW primary/fraction/offset mapping. | Unverified; #0185 independent actual-pair derivative evidence, #0186 guarded candidate binding, #0085 new-name publication. No missing-property insertion or empty-sidecar creation is implied. |
| `pair-date` | Those exact two member operations, original read sets and explicit pair/direction/conflict policy. | Unverified; #0086 and shared #0179–0181 ordered executor/resume evidence; per-member outcomes, no group atomicity. |
| `xmp-owner-delete` | R5P-026, `{http://ns.adobe.com/exif/1.0/aux/}OwnerName`, exact sidecar document/ordinal/form and whole-property range. | Unverified; #0089 actual one-field removal and #0090 retained-artifact/residual audit; #0188–0190 supply scoped mechanisms. |
| `xmp-label` | Existing singleton `{http://ns.adobe.com/xap/1.0/}Label`; raw Unicode text, no display parsing. | Unverified; #0024 owns one existing-property candidate schema and changed/equal/absent/duplicate/escaping controls. Creation needs an explicit separate insertion binding. |
| `caption` | Existing `{http://purl.org/dc/elements/1.1/}description` `rdf:Alt` entry `x-default`, raw text. | Unverified; #0024 owns the one-entry contract and sibling/qualifier controls. No native CR3 caption tag, allocation or alias is invented. #0023 retains embedded-caption scope. |
| `list` | `{http://purl.org/dc/elements/1.1/}subject` `rdf:Bag`, plain strings and exact item ordinals; raw order/multiplicity retained. | Unverified; #0024 owns bounded replace/append/remove-index/remove-all schema and VAL-001–004. Deduplicate still needs explicit equality, survivor/order and loss semantics. |
| `language` | `{http://purl.org/dc/elements/1.1/}rights` existing `rdf:Alt`: set `x-default` or delete `fr`, preserving other spellings/order. | Unverified; #0024 owns exactly these two entry operations, VAL-005/006 and duplicate case-key refusal. No default entry is fabricated. |
| `structure` | Authored `known`/`unknown` fields only; actual expanded production property/path/qualifiers unresolved. | Unverified; #0024 must select one real representation, then distinguish merge and explicit replacement under VAL-007/008. Unknown production-family size remains unknown. |
| `snapshot-copy` | Existing synthetic `proposal:exif/Artist@1` to `proposal:xmp-dc/creator@1` using `proposal:string-to-creator-sequence-v1`; normalized source, never display. | Unverified; #0024 owns the exact insertion/mapping contract and independent original-snapshot VAL-009 swap oracle. #0023 retains embedded-copy scope. |
| `rational` | `proposal:exif/ExposureTime@1`, Exif `0x829a`; actual CMT/IFD allocation/type/encoding still unresolved. Explicit normalized fraction versus raw pair. | Unverified; #0023 owns one actual allocation/dependency selection and VAL-010/011. Numeric equality must not canonicalize stored bytes; zero denominator stays invalid with storage retained. |
| `null` | No production null-capable definition/encoding selected. Tagged raw null differs from absent, empty, invalid and delete. | Unverified; #0023/#0024 must name one eligible destination before implementation; VAL-012 remains explicit. Null never grants implicit deletion. |
| `growth-shrink` | Embedded EXIF/GPS/XMP/caption layouts are not selected merely by naming families. Exact changed lengths/counts/offsets/checksums and opaque dependencies are required. | Refused; #0023/#0119 retain one actual field/layout selection and independent grow/shrink/relocation and RAW-usability evidence. No fixed count of undefined layouts is asserted. |
| `insert-delete-block` | Extra native field/block and XMP insertion locations are unresolved; explicit absence, defaults and losses required. | Unverified; #0023/#0024/#0025 retain their native/sidecar/privacy portions. A selected region/dependency map must precede an executable slice. |
| `date-transform` | Extra date/calendar/zone repair or geotag fields and transformations remain operation-specific. | Unverified; #0133 supplies its finite lookup/repair contract; #0023/#0024 retain actual writable destinations, transforms and companion effects. No host-zone assumption. |
| `preview-variant` | Direct CTMD edit, stored-preview replacement, C-RAW and DPRAW are distinct unqualified requests. | Refused; #0023/#0025 retain specific zero-publication refusals. Positive evidence for full RAW does not admit another variant or silently select XMP fallback. |
| `file-rename` | Explicit RAW/XMP identities/parents; ordinary/case-only rename and two-name cycle. No metadata conversion. | Unverified; #0212 pair rename and #0213 exchange use existing #0201/#0202 mechanics. Cross-volume copy/verify/publish/delete is a separate unselected positive residual in #0026. |
| `replacement-restore-prune` | Exact expected-old/current/candidate/retained-original objects; occupied and fresh restore destinations are separate. | Refused; #0209 replacement, #0210 occupied restore, #0211 selected-backup prune retain strict exclusion, complete required properties and later-version preservation. |
| `group` | Exact two-member replacement/resume types and receipts, frozen original copy inputs. | Unverified; #0214 actual pair resume, #0096 marker evidence and shared #0179. A general graph/batch wire is undefined; committed members must not be replayed. |
| `privacy-other` | Catalog native GPS/serial selectors, previews and provenance-bearing structures remain separately scoped. | Unverified; #0092/#0191 targeted lawful assertions and #0091/#0192 provenance refusal. Catalog counts are not admitted-operation counts; no secure-erasure or anonymity claim. |

## Next schema and evidence boundaries

The next engineering selection after the existing date adapters is the finite
XMP existing-label/caption/list/language work above, within #0024. This is an
ordering of authorized work, not another successor batch or an extra gate.
Each slice starts with **one named property and one representation**. Existing
packet inspection does not serialize `rdf:Bag`, `rdf:Alt`, arbitrary structures
or insertion; those remain explicit schema and implementation work.

The ledger's `nextContract.requiredFields` lists the exact selection-record
fields that must be resolved: operation ID; document and occurrence/insertion
identity; container path; raw type/encoding; input view; original read set;
exact proposed value; allocation/dependency map; preserved complements;
expected effects/losses; equality/no-op rule; refusal cases; independent oracle;
owner; and evidence references. This inert inventory record is **not** a runtime
saved-plan schema. No unresolved string or editable admission flag can satisfy
a real execution binding.

The first new bag contract must name finite item/text bounds, container and item
lexical identities, explicit operation and equality enums, duplicate/qualifier
refusals, and exact complements. An independent oracle must compare all four
VAL-001–004 outcomes, including duplicated append, selected duplicate removal,
explicit remove-all and empty replacement. The two language operations must
add exact language key/ordinal, case-insensitive uniqueness, original spelling
and sibling retention, with VAL-005/006 and missing/duplicate-entry controls.
Structure, rational and null slices cannot start by inventing production
properties/encodings; their next schema must first resolve the exact unknown
identity and preservation basis recorded in their rows.

Every eventual execution schema inherits all eleven duties in the
[per-operation plan map](../legacy-compatibility/operation-plan-map.md), including
physical identity, continuing guards, properties, losses, revisions, publication,
recovery, ordering and separate caller authority. Independent effects/structure
oracles must inspect actual output, not the writer's intended-value cache.
Actual media requires its exact grant; camera-derived reports remain private.
No model result, proposal key or digest grants format/storage/media authority.

## Original #0014 acceptance retained

The following seven original paragraphs remain unmet, independently of this
matrix's handoff. The ledger gives each an `A14-*` trace and mapped operations.

1. Exercise docs/write-safety/acceptance-scenarios.md and the transaction/value cases against actual implementations and admitted media.
2. Declare each OS/filesystem/storage profile and exclusions. Prove publication, collision/concurrency, properties, persistence, cancellation and recovery.
3. Validate sensor samples, references, calibration/CFA interpretation, opaque data, previews and known signatures for each supported CR3 operation/layout.
4. Finish exact pairing/mappings and named privacy field catalogs; measure removed/residual/uninspectable data and retained copies.
5. Record independent validators, RAW usability checks and bounded failure injection through the fixture-plan records.
6. Separate process kill, OS crash and power loss. Separate supported/refused/failed/unverified combinations. Full RAW does not enable C-RAW/DPRAW.
7. Close GAP-004/GAP-009 only when their specified evidence exists. Logical deletion never establishes secure erasure.

Paragraph 6 is preserved as history, with the current
[VM-off-only best-effort policy](power-test-policy.md) applied explicitly:
future power-related tests stop at disposable VM-off. Physical-power hardware,
host crashes and new NMI campaigns are not requirements; host-cache limits and
unverified physical survival stay stated honestly. The accepted
[OD-11 option A](practical-output-policy.md) likewise refines new-output property
checks without relaxing continuous default-stream/object/name guards. Existing
replacement retains its separate strict requirements. The initial positive
new-output milestone is Windows-only under the
[accepted Linux deferral](linux-new-output-boundary.md).

## Complete criterion and proposal-key trace

The ledger's `criteria` array retains each criterion's exact source title,
required result and WS references, mapped operations, owners and unresolved
full-parent acceptance status. SAF rows also retain fixture-family references.
These are acceptance allocations, not claims that all model cases fit every
operation. Original recovery/backup obligations apply to replacement; new-output
uses expected absence and retained sources. A successful hypothetical TX/VAL
case or a passing marker cell does not complete the actual RAW scenario.

| Source | Exact denominator | Remaining obligation |
| --- | --- | --- |
| [SAF contract](acceptance-scenarios.md) | SAF-001–016: 16 | Preview/caption, sidecar create/no-op, growth/shrink, unsupported variants, concurrency, aliases, properties, failures, interruption, partial pairs, file operations, restore/prune, privacy, signatures, cleanup and storage admission. |
| [Transaction cases](scenarios.v1.json) | TX-001–034: 34 | Successful, refused, failed and uncertain paths; all current guards and noncircular persistence/receipt conditions. |
| Same source, values | VAL-001–012: 12 | Lists/list entries 001–004; language 005–006; structures 007–008; original-snapshot copies 009; rational views 010–011; typed null 012. |
| Same source, recovery | REC-001–008: 8 | Original/absence/candidate classification, foreign/missing/untrusted/invalid recovery refusal and fresh final checks. |
| Same source, originals | BKP-001–004: 4 | Retain before commit and by default afterward; discard only after explicit successful cleanup; report retained pending cleanup. |
| Same source, groups | GRP-001–006: 6 | Partial failure/conflict/cancellation, committed-plus-unchanged success, uncertainty and wholly refused preflight. |

`proposalKeys` reconciles all exact `proposal:*` strings in the
[snapshot](../metadata-model/examples/snapshot.synthetic.json) and
[copy intent](../metadata-model/examples/copy-intent.synthetic.json), including
definitions, mappings, normalization rules, formatters and the synthetic decoder.
Each points to its source and selected operation/residual. They remain synthetic
identities, including derived/read-only and opaque cases; none becomes an admitted
registry entry or an executable callback. The
[delivery matrix](../legacy-compatibility/delivery-matrix.md) and
[remaining-work map](../remaining-work.md) retain the wider scope.

## Verification

Run `python scripts/check_raw_xmp_operation_matrix.py`,
`python scripts/check_operation_plan_map.py`, `python scripts/check_docs.py`
and `git diff --check`. The [dedicated checker](../../scripts/check_raw_xmp_operation_matrix.py)
checks exact operation/owner allocation, 80 source criteria and their original
results, all seven original acceptance paragraphs, exact reciprocal operation links,
fixed criterion owners, all proposal-key allocations and evidence paths.
Twenty-seven negative controls reject removed
criteria/residuals/owners/keys, original-requirement weakening, duplicate JSON/IDs,
misallocated null semantics, removed/added reciprocal links across every criterion
family, arbitrary owners/proposal remaps and invented admission/completion.

These checks validate public inventory consistency only. No media parsing,
mutation, publication, new runtime dependency or external action is performed.
