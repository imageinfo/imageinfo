# Per-operation saved-plan obligations (#0132)

Specified **2026-10-16**, inventory revision `operation-plan-map-2026-10-16.1`.
This maps seven finite operation families to their existing planner owners and
the complete [WS-002](../write-safety/README.md#plan-before-effects) duties.
The [versioned inventory](operation-plan-map.v1.json) is a requirements map,
not a saved-plan schema, importer, capability registry or executable plan.
The [checker](../../scripts/check_operation_plan_map.py) verifies its finite
coverage and references using public authored data only.

The [delivery matrix](delivery-matrix.md) retains all 32 MAP families, 39 API
headings and LG/GAP residuals. The [native token inventory](native-token-inventory.md)
remains the authority for implemented syntax. This mapping adds no command or
API. #0015 retains LG-004; #0132 finishes allocation of its concrete obligations,
not general plan interoperability or any writer. Existing authorized engineering
work proceeds under its owners; there is no renewed user adoption gate.

## Shared obligations before effects

Every row below inherits **all** duties in this table, including an explicit
not-applicable reason where the exact operation has no such effect. A future
wire contract must supply typed concrete fields and semantic validation, rather
than opaque dictionaries or imported `safe`, `admitted` or `authorized` flags.
These inventory duty IDs are trace labels, not proposed runtime field names.

| Duty | Required binding and validation before effects |
| --- | --- |
| P-READ | Immutable original read set: complete source-content identities, bytes/values, input view, assumptions and every mutable copy source. Required source coverage and observed absence must be distinct from unknown/unexamined data. |
| P-WRITE | Exact existing occurrences or explicit insertion locations, typed destination, expected-old/expected-absent state and collision policy. Resolve aliases, duplicates and conflicting instructions for the whole request. |
| P-IDENTITY | Resolved source/target objects, physical identities, parents, path/alias/link bindings and candidate identity; deterministic guard acquisition and continuing byte/name protection appropriate to the selected profile. A path or digest alone is insufficient. |
| P-PROPERTY | Relevant actual attributes, ownership/access policy, times, streams and link topology; expected pre/post conditions, explicit carry-through/refusal rules and required checkpoints. OD-11 option A applies to new output only; strict replacement remains separate. |
| P-EFFECT | Typed old/new values, raw/normalized input view, transformation/mapping, implicit updates, no-op equality and all actual candidate effects. Preserve protected sensor/interpretation bytes, unknown regions, references and checksums under independently admitted dependencies. |
| P-LOSS | Explicit losses, conflict selection and exact required acknowledgements, residuals/uninspectable scope and protected exclusions. Never infer loss consent from a digest or imported plan. |
| P-REVISION | Schema, model, reader, registry, conversion/mapping, capability and policy revisions; operation/profile-specific rules. Recompute against trusted current data; changed inputs/rules invalidate the old plan and changed effects require visible replanning. |
| P-PUBLICATION | Actual supported storage profile, candidate validation, expected destination state, guards and exact persistence acknowledgements. No profile is selected by an editable label; API flush return and output existence do not prove durable commit. |
| P-RECOVERY | Original/expected-absent state, owned staging/backup/receipt identities, private retention/resource bounds and fresh recovery conditions/custody. Imported records never authorize replay, rollback, finalize, restore or prune. |
| P-ORDER | Per-file units, dependencies, pair membership, original-snapshot evaluation, deterministic guard/publication order, frozen shared copy inputs, cancellation boundaries and partial outcomes. No implicit group atomicity or blind retry of committed units. |
| P-AUTHORITY | Separate explicit caller application of the resolved request; strict bounded inert imports, fresh technical admission and trusted current capability checks. Reading plans cannot execute scripts, shell commands, fetches or callbacks. |

These duties expand WS-002 using its adjacent WS-001/003–024 requirements; they
do not reduce them. Requested saved-plan/report artifacts are separate from
metadata/media effects. The current [power-test policy](../write-safety/power-test-policy.md)
does not add physical-power testing as a gate.

## Finite operation and owner matrix

Owner numbers name authorized work, not claims that implementation has finished.
Tracking #0023–0026 retain their complete parent acceptance. Concrete execution
and wire successors stay with the named operation owners, sharing mechanics
where already allocated rather than creating a parallel generic planner.

| Operation | Actual planner owners and binding contract | Exact effects and remaining wire boundary |
| --- | --- | --- |
| Existing date preview | #0055/#0076/#0077; #0023/#0078 own any execution bridge. [Saved preview](cr3-preview-plan.md), [source binding](cr3-preview-source-binding.md). | One unique existing CMT2 Exif `0x9003`, ASCII20, exact original allocation/path/bytes and intended bytes; complete source length/SHA-256 and current revisions. Existing v1 is nonexecuting; output is require-absent with unavailable-production profile. Object/property/guard/persistence/recovery bindings remain unresolved. No ordered group, mutable copy source or implicit transform is requested. |
| New-CR3 date apply | #0023/#0078, with #0022 storage and #0119 format admission; [current refusal](../write-safety/write-admission.md), [new-output contract](../write-safety/new-output-contract.md). | Reuse the #0078 bridge from saved date intent; do not treat v1 as executable. Bind actual source/candidate/new destination, admitted dependency/complement map, property checkpoints, no-clobber guards and receipts, no-op and cancellation/outcome/recovery state. New exact wire fields await the actual typed adapter/profile; all present RAW mutation admissions remain refused. |
| New-XMP date derivative | #0024/#0085 with #0186 candidate binding and #0185 independent derivative evidence. [Mapping](../sidecars/date-mapping.md), [candidate](../sidecars/date-preservation.md), [native adapter](../sidecars/native-date-adapter.md), [packet profile](../sidecars/packet-profile.md). | Bind both immutable RAW and existing XMP snapshots, exact primary/fraction/offset source occurrences, destination expanded name and packet ordinal, previous/mapped text and lexical range. Select a separate new absent output; do not imply missing-property insertion or empty-sidecar creation. Preserve original fraction/zone, XML complement and supported unknown siblings; record conflict/loss policy. In-memory research and packet inspection do not supply guarded production publication/wire bindings. |
| Paired RAW-XMP date sync | #0024/#0086 with #0078/#0085; shared #0179/#0180/#0181 ordered units. [Pair selection](../sidecars/pairing.md), [original mapping](../sidecars/date-mapping.md), [partial outcomes](../write-safety/README.md#groups-and-file-operations). | Bind both explicitly selected members and both destinations, all original read sets and mutable copy sources, direction/conflict policy and frozen mapped values before first publication. Record per-member identities/effects/receipts and exact order, committed/refused/pending/recovery-required outcomes and receipt-bound resume checks. Pair association is not semantic agreement or all-or-nothing commit. Whole pair wire awaits actual admitted member adapters and shared executor; replacement resume remains separate #0096/#0214. |
| One-field XMP privacy removal | #0025/#0089 with #0188/#0189/#0190 and #0090 retained-artifact audit. [Exact removal contract](../privacy/xmp-owner-removal-contract.md), [coverage limits](../privacy/read-coverage.md). | Select only catalog R5P-026 at sidecar.xmp, exact aux OwnerName expanded name, document/ordinal/form and whole-property range. Complete zero/one/multiple occurrence handling and declared no-op must precede effects; preserve prefix/suffix and semantic siblings. Bind catalog revision, known-provenance refusal, lawful operation scope and per-artifact removed/retained/residual/uninspectable reports, including originals/backups/previews. Wire awaits the admitted removal/publication adapter; no blanket privacy or secure-erasure result. |
| Fresh restore | #0026/#0095, #0199 custody and #0200 receipt bridge; actual CR3 adapter remains #0210. [Fresh-name marker slice](../write-safety/fresh-name-restore.md), [original retention](../write-safety/original-retention.md), [WS-019](../write-safety/README.md#groups-and-file-operations). | Restore is a fresh separately authorized mutation: bind retained original content/object/properties/custody, later current version and selected destination state. Preserve the later version separately; original is copied, not consumed. #0108 covers only recreated typed-owned fresh-name markers. Occupied-name #0095 requires strict expected-target replacement and property-complete retention, not fallback overwrite. No imported restore authority or complete wire successor exists. |
| Grouped effects | #0026/#0096 existing-target group and #0024/#0086 pair; shared #0179 executor, #0180/#0181 new-output qualification, #0200/#0208 replacement receipts/finalization. [Grouping requirements](../write-safety/README.md#plan-before-effects), [receipt protocol](../write-safety/namespace-receipt-protocol.md), [replacement boundary](../write-safety/existing-target-boundary.md). | Bind a finite ordered two-member group to exact operation/profile types, object identities, all read/write sets, per-member originals/candidates, dependencies, frozen inputs and receipts. Refuse conflicting targets or unsupported guards. Per-unit publication is authoritative; crash/cancel may leave partial outcomes. Resume uses trusted current receipt-bound evidence and never replays committed members. No free-form graph or generic ordered executable wire is defined. |

Every concrete row's duty specialization and outstanding fields are retained in
the JSON inventory. Referenced research receipts/protocol models never qualify
production storage; new native/protocol implementations qualify only their stated
slices. The current read-session runtime is a read transport, not plan-apply or
group execution authority.

## Existing v1 fields versus execution duties

| Existing preview field | Present meaning | Still required for any apply successor |
| --- | --- | --- |
| `schema`, `revisions` | One exact version and bounded current rule labels. | Fresh trusted revision/capability checks plus actual operation/profile revision identities. |
| `source`, `occurrence` | Content assertion, indexed occurrence/allocation/order/original bytes; #0077 computes and rechecks actual source-content observations. | Physical object/parent/path identities, stable guard interval, all relevant properties and protected/dependency validation. Equal bytes at a replacement object are only content equality. |
| `intended_bytes`, `preservation` | Exact proposed ASCII20 and complement declaration, including equal-byte no-op intent. | Candidate reread, true implicit/semantic effects, losses and independent actual RAW admission. Exact complement alone cannot clear opaque dependencies. |
| `output` | Locator, require-absent, OD-11 private-owner policy and `unavailable-production`. | Actual no-clobber destination/parent binding, qualified profile, candidate checks and acknowledgements; no silent promotion of this literal to an available profile. |
| `execution_bindings`, `recovery`, `apply_authorization` | Must-recompute; no mutation/recovery authority; separate caller required. | Concrete typed execution/recovery bindings and fresh caller action through #0078, while keeping imported assertions non-authorizing. |

This is a bridge allocation, not a new product selection. Extending v1 requires
an explicit versioned operation-specific contract with actual effects/identities;
unknown members and invented authority remain refusals in the existing importer.

## All other plan forms remain unmet

The inventory retains separate residuals for scalar set/delete and file-sourced
assignment; insertion/block creation; list replace/append/remove/deduplicate;
structure merge/replacement; language alternatives; date shift/calendar/zone and
geotag transforms; general copy/redirection/group creation; rename/move/case/cycle;
occupied restore and backup prune; general intent lifetime and grouped execution;
and additional formats, native privacy selectors and stored-preview changes.
The exact finite slices above do not satisfy these residuals.

MAP-005/009/010/011/012/017/018/019/020/021/022/029/030, LG-004 and their complete API
obligations stay in #0015 and the existing #0023–0026 owners as detailed in the
delivery matrix. Unselected semantics and unsupported layouts remain explicit
scope gaps; wire successors are undefined until actual typed effects, bindings
and recovery profiles exist. Do not encode an unselected form as a permissive
extension bag, a runtime callback or a newly invented approval step.

## Verification and limits

Run `python scripts/check_operation_plan_map.py` and `python scripts/check_docs.py`.
The dedicated checker freezes the seven-operation/eleven-duty coverage, required
owner allocation, complete existing preview field inventory and eleven residual
families; it checks local evidence paths and inert/non-admission declarations.
Its deliberate negative controls reject removed duties/owners/fields/residuals,
invented operations, duplicate IDs and authority escalation. It is an inventory
consistency check, not validation of an executable plan or a proof that future
planner effects/guards are correct. No media, private fixture or external tool is
used; no source feature, wire runtime or storage gate is enabled.
