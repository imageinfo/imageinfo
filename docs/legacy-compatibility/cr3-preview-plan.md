# Single CR3 date saved preview contract

Observed and implemented 2026-10-15 under #0055. This is a bounded **nonexecuting**
LG-004 slice: one existing unique CMT2 Exif DateTimeOriginal (`0x9003`, decimal
36867) in an existing 20-byte ASCII allocation. It does not complete LG-004's
general persisted-plan grammar or WS-002's executable-plan obligations.

[The Rust boundary](../../src/plan.rs) parses and validates saved intent without
opening a source, destination, configuration file, callback or recovery artifact.
`PreviewPlan::from_json` accepts at most 32 KiB of UTF-8 JSON. Typed deserialization
also validates the contract, but callers using the serde boundary directly must
bound their input independently. All nested objects deny unknown and duplicate
members; missing fields, unknown enum values and trailing documents refuse.

## Bound data

The wire shape is [schema.v1.json](preview-plan/schema.v1.json). JSON Schema
describes its structure; Rust additionally checks calendar values, UTF-8 byte
bounds/control characters, exact occurrence-path grammar, source/output locator
inequality and overflow-safe allocation containment. Schema validation alone is
not the Rust validation or a capability decision. There is no generic schema
interpreter in production.

| Field | Binding and limits |
| --- | --- |
| `schema` | Exactly `imageinfo.cr3-date-preview.v1`; other operations or versions refuse. |
| `revisions` | Exact current model, reader, admission, known-provenance registry, capability, conversion and policy revisions. Stale rules require replanning. |
| `source` | Bounded path locator, complete source length at most 256 MiB, and SHA-256 assertion as 64 lowercase hexadecimal digits. No digest is computed here. |
| `occurrence` | Complete reader path of indexed box/IFD/tag parts, numeric native tag, allocation offset/length, TIFF byte order and exact original bytes. The path ends in one CMT2 box, `IFD@` unsigned-decimal offset and tag `36867`. |
| `intended_bytes` | Exactly 20 unsigned byte values: complete Gregorian `YYYY:MM:DD HH:MM:SS` and one trailing NUL. Both old/new values use the existing date parser; no timezone conversion, normalization, insertion or loss is implied. Equal old/new bytes are a valid no-op intent. |
| `output` | One bounded new-output locator, `require-absent` collision selection, accepted OD-11 option A policy and explicitly `unavailable-production` storage profile. Equal source/output locator strings refuse; filesystem aliases remain a later validation obligation. |
| `preservation` | Required effect is replacement only within the selected allocation, preserving all other source bytes. This declares the intended complement, not evidence that unknown dependencies or implicit metadata effects are safe. |
| `execution_bindings` | Only `must-recompute-before-any-apply`: unresolved current object/path/property, protected-reference, guard, persistence and destination-state checks cannot be represented as satisfied. |
| `recovery` | Only `no-mutation-or-recovery-authority`: no backup creation, staging, rollback, replay, pruning or cleanup. |
| `apply_authorization` | Only `separate-caller-required`. There is deliberately no serialized authorized value. |

The fixed operation has one source, one exact existing occurrence and one proposed
new output. There are no mutable copy sources, paired members, transformations,
ordering choices, or requested implicit updates. Adding those effects requires a
new contract. The original bytes are the read set; the allocation plus intended
bytes is the proposed write set. The output selection never requests overwrite
or in-place mutation.

## Trust and refusal boundary

A valid `PreviewPlan` means only that supplied assertions have the supported shape
and revisions. The synthetic [positive vector](preview-plan/valid.v1.json), including
its invented all-zero digest, intentionally passes without any file present. Its
digest does not identify a verified source or authenticate a caller. Paths are
inert locators; strings resembling commands are never evaluated.

Imported plans, metadata snapshots and their embedded revision/digest/profile
labels cannot authorize themselves. `production_mutation_allowed()` is always
false. Even fresh source equality and separate caller consent would not enable
execution through this contract: independent format admission, storage/profile,
publication, recovery and authorization gates remain required. Unsupported RAW
format/storage stays refused; no writer or plan-apply command is added by #0055.

#0077 implements [actual source-content revalidation](cr3-preview-source-binding.md)
against this protocol, including complete source digest, occurrence
uniqueness/path/allocation/old-byte equality and stale source refusals. A saved
occurrence path alone does not prove uniqueness. That implementation uses current
source/rule observations rather than importing capability booleans. A later
executable contract must also bind the resolved
objects/properties, protected dependencies, required guards and qualified storage
acknowledgements required by WS-002. Fresh checks must not silently broaden intent.

## Verification and coverage

#0078's bounded [advisory recomputation](cr3-plan-observation.md) compares this
intent to a fresh source snapshot and exposes changed fields and the requested
fresh-name effect. It adds no executable wire fields or apply authority; the
complete WS-002 execution gaps remain explicit there.

[Typed negative vectors](preview-plan/negative.v1.json) replace fields in the
positive vector and must refuse. They cover self-authorization, invented storage,
stale rules, malformed digest, wrong/out-of-range allocations, wrong tag, invalid
calendar/NUL bytes, unknown authority fields and same-locator output. Unit tests
also exercise strict duplicate members at every object boundary, occurrence path
grammar, overflow, trailing documents, bounded input, typed roundtrip and the
invariant that successful imports never permit mutation. Vectors contain invented
public data and no camera media or private snapshots.

Source and requirement observations: [LG-004 and serialization boundary](integration.md#plan-serialization-boundary),
[WS-002](../write-safety/README.md#plan-before-effects),
[existing date admission](../write-safety/write-admission.md), and
[OD-11 option A](../write-safety/practical-output-policy.md), as present in this
checkout on 2026-10-15. These establish obligations; this contract makes no new
qualification claim about format effects, filesystem properties or durability.
