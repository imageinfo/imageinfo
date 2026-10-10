# Inventory validation and handoff

Validated on **2026-10-10** for inventory `2026-10-10.1`, schema version 1.
This validates the documentation/data contract. It does not validate CR3 parsing,
editing, ExifTool executable behavior, or imageinfo compatibility.

Revision `2026-10-10.2` was revalidated during card #0004. It keeps all capability
states unchanged and transfers GAP-005's remaining runtime evidence to fixture-plan
after delivery of the proposed metadata contract. Schema/reference/dependency
checks and the same 10 negative cases still pass.

Revision `2026-10-10.3` was revalidated during card #0005. It assigns the remaining
corpus/reference observation gaps to backlog follow-up `corpus-baseline` (#0013).
Counts and capability states remain unchanged; schema/reference/dependency checks
and the 10 negative cases pass.

Revision `2026-10-10.4` was revalidated during card #0006. It links the proposed
write-safety contract and moves GAP-004/GAP-009's remaining profile/catalog/runtime
evidence to `write-validation` (#0014). Schema/reference/dependency checks and all
10 negative cases pass; counts and capability states remain unchanged.

## Results

Revision `2026-10-10.8` links #0010's artifact provenance policy/schema and assigns
GAP-011's first actual corpus/reference admission evidence to #0013. Schema,
references, dependency checks and all ten negative cases pass. MIT and all capability
states remain unchanged; no third-party asset is approved or imported by this revision.

Revision `2026-10-10.7` links #0008's performance protocol and points actual measured
limits to #0016. Schema/reference/dependency checks and all ten negative cases pass;
capability counts/states remain unchanged and no numeric performance claim is made.

Revision `2026-10-10.6` was revalidated during card #0007. It links the surveyed
compatibility ledger and request/result proposals, with GAP-006/GAP-012 remaining
specification/runtime work assigned to `compatibility-evidence` (#0015). Schema,
references, dependency checks and all ten negative cases pass; no capabilities
are promoted beyond specified.

Revision `2026-10-10.5` was revalidated during card #0003. It links the native CLI
walkthrough recommendation and assigns GAP-012's remaining specification work to
`legacy-compatibility` (#0007), with measured limits and later runtime/usability
checks still open. Counts and capability states are unchanged; schema/reference/
dependency checks and all ten negative cases pass.

| Check | Result |
| --- | --- |
| JSON parsing and draft 2020-12 schema self-validation | Passed |
| Inventory against schema, with URI/date/date-time format checking | Passed |
| Unique identifiers across capabilities, mappings, gaps, sources, variants | Passed |
| Source/variant/capability/gap references resolve | Passed |
| Requirement references resolve to PR/CLI definitions | Passed |
| Capability dependency graph has no cycles | Passed |
| Upstream source URLs use the pinned commit and existing repository paths | Passed |
| Human indexes contain all capability, mapping, and gap IDs | Passed |
| All current rows are specified, with no implementation revision or runtime evidence | Passed |
| Executable reference version/hash remain null and experiments remain false | Passed |
| Counts | 49 capabilities, 32 mappings, 12 gaps, 20 sources, 4 variants |

The structural checks used `jsonschema 4.26.0` in a temporary isolated tooling
environment. A small local checker also validated references, acyclicity, source
paths, and index coverage. This is verification tooling, not a language/framework
decision for imageinfo; no application dependency or package manifest was added.

## Negative cases rejected

1. Unknown capability field.
2. Invalid operation name.
3. Duplicate capability ID.
4. Dangling source ID.
5. Dangling capability ID in a mapping.
6. Dependency cycle.
7. A verified row with no evidence.
8. An implemented row without an implementation revision.
9. A verified row with synthetic evidence but no executable reference baseline.
10. An upstream source link changed from the pinned commit to a moving branch.

These mutations were made only to in-memory test copies. They are not inventory
records or fabricated conformance evidence.

## Repeatable review procedure

1. Use a JSON Schema draft 2020-12 validator, with format assertions enabled, to
   validate the schema and [inventory](canon-eos-r5-cr3.v1.json).
2. For each named collection, require uniqueness of its `id` values. Check every
   `sourceRefs`, `variantRefs`, `capabilityRefs`, `gapRefs`, `requirementRefs`, and
   `dependsOn` value against its declared collection or requirement document.
3. Traverse `dependsOn` as a directed graph and reject cycles, including self-links.
4. Confirm every upstream source path exists at `reference.commit`; confirm each
   source locator supports the associated note rather than only naming a similar tag.
5. Require all human-index IDs to match the JSON. Check local links, JSON examples,
   Markdown fences, line endings, and staged whitespace.
6. Review state transitions semantically. An executable hash and evidence record
   are necessary, not sufficient, for verified status. Inspect the underlying
   fixture, result, accepted differences, protected-byte checks, and independent
   validation. Do not treat an arbitrary artifact string as proof.

For future inventories, an implemented/verified/limited row must identify its
implementation revision and explain its state in `statusNote`. The fixture-plan
card will specify richer runtime artifact manifests; this schema does not replace
that separate evidence contract.

## Card #0002 acceptance trace

| Requested outcome | Delivered artifact |
| --- | --- |
| Versioned inventory/schema | `canon-eos-r5-cr3.v1.json`, `capability-inventory.schema.json` |
| Prioritized RAW/variant rows | Full RAW and paired XMP primary; C-RAW/DPRAW separate secondary records; operation/milestone/priority fields on every capability |
| Recognition/read/write/create/delete/preservation distinctions | Separate operation rows, with extraction/workflow rows where needed |
| Relevant CLI/API surface mapping | MAP-001 through MAP-032; equivalent proposals, deliberate differences, and unresolved families |
| Constraints and primary sources | 20 source entries, pinned upstream revision, per-row reference notes and gaps |
| Measurable statuses | Reference evidence and imageinfo status kept separate; structural and semantic gates documented |
| Remaining audit scope | GAP-001 through GAP-012, each with owner card, closure evidence, and blocked claim |

No media fixtures were imported or modified, and no upstream tag database or parser
was copied into the project. Actual camera-specific field presence, exhaustive
tag/option coverage, and safe mutation remain explicit follow-up work. These limits
match the inventory card's requested research/specification scope.

The original downstream model and fixture specifications are now recorded in
[metadata-model](../metadata-model/README.md) and [fixture-plan](../fixture-plan/README.md).
The [write-safety proposal](../write-safety/README.md) supplies mutation requirements.
The [CLI walkthroughs](../cli-walkthroughs/README.md) now refine the native interface;
the [compatibility recommendation](../legacy-compatibility/README.md) is recorded.
The [performance protocol](../performance/README.md) is now recorded; numeric limits
await #0016. The [governance proposal](../../GOVERNANCE.md) is now recorded;
the [artifact provenance policy](../provenance/README.md) is now specified, while
#0013/#0014 retain actual
corpus and writer/storage evidence. This validation does not close those cards.
