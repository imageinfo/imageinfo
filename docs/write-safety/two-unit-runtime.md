# Fixed two-unit execution and receipt-bound resume

**#0179 implementation, 2026-10-17.** The crate-private production code in
`src/storage/group.rs` executes exactly two statically selected unit adapters in
unit-1 then unit-2 order. Its fixed control flow is shared infrastructure for
future admitted operation adapters. There is no public apply command, group
atomicity, rollback, arbitrary scheduler, saved-plan importer or newly admitted
storage/RAW capability.

## Original intent, guards and prepublication work

One immutable borrowed `Intent` binds the original captured values, group identity
and both unit identities, operation/revision, profile/implementation, source,
parent, expected target and output name. Its lifetime spans execution and every
explicit resume. A later member receives those same original bytes; it cannot
obtain its original values by reopening a source changed by an earlier member.
Intentional shared sources require equal identity and complete frozen facts.

The runtime checks the complete encoded manifest size without an owned copy.
`LogicalBudget::reserve_group` then atomically charges both conservative unit
allowances plus the actual manifest length before constructing that manifest or
calling an adapter. A unit allowance is the existing candidate length plus eight
65,536-byte record/caller-capture allowances. The group adds exactly one bounded
manifest, at most 65,536 bytes, and at most two retained staged unit contexts.
Failed/cancelled work keeps its charges; consumed unit helpers cannot be reset by
resume. This is process-local logical construction accounting, not an allocation
quota, persistent budget or free-space reservation. See
[cumulative construction resources](production-resource-retention.md).

The manifest uses the single-unit runtime's checked length-prefixed field encoder.
It binds the original snapshot and both complete unit descriptors in declared
order. Unit 1 retains and checks the one exact private manifest through its own
record storage before either publication; the group introduces no record backend.
Fresh manifest checks precede subsequent publication. Manifest bytes and artifact
identity are observations, never caller authority or an all-committed receipt.

Both units receive preflight before staging. Target/source/parent physical aliases,
shared physical targets and equal parent/output write names refuse before adapter
calls. The fixed protocol conservatively compares output names ignoring ASCII
case; the unit adapter's actual physical resolution must reject any additional
platform-specific aliases. Guard acquisition sorts the actual frozen identities,
with unit order as a deterministic tie break. Adapters must acquire and retain the
real guards and recheck current bindings; sortable identities alone confer no
exclusion. Both candidates and required recovery material are staged and validated
before unit 1 receives execution. A known invalid second member prevents the first
publication. Two concrete `UnitAdapter` implementations supply these effects;
there is no callback language or record-selected executable.

## Per-member results and explicit resume

Each member retains its actual `UnitResult`, qualified receipt witness, exact
artifacts and pending cleanup. The group reports unattempted, refused,
cancelled-before-publish, committed or recovery-required per member. A possible
publication remains recovery-required even when a later adapter response is a
refusal. Member 1 uncertainty stops member 2. Member 2 failure preserves member
1's commitment and cleanup. Staged contexts remain retained across an interrupted
run; continuing them never reconstructs uncharged candidates.

`resume` requires an explicit call on the same non-importable run. A completed
member is skipped only after its adapter verifies a fresh qualified receipt,
current identity/content/properties and the shared current-caller
`ActionAuthority`; the fresh receipt must exactly equal the retained witness.
An uncertain member can only enter its own separately admitted typed
inspection/finalization interface. It never receives `execute` again. Every returned finalizer observation is retained even after a failed/uncertain
action: the runtime merges new and prior artifacts, possible effects, release,
retained material, cumulative charges and pending cleanup before refusing further
work. Only a qualified completion permits continuation. Remaining
unattempted work receives fresh preflight and a live execution capability owned
and revalidated by the admitted unit adapter. Missing, revoked or stale authority
and missing/changed/conflicting receipt facts stop selection.

The default inspection/finalization interfaces return `AdapterUnavailable`.
The current [read-only inspection](production-restart-inspection.md) and unqualified
single-unit runtime do not manufacture qualified receipts or finalizer admission.
The independent new-output adapter/qualification belongs to #0180; replacement
operations additionally need their own admitted primitive, original/property
policy and finalizer. Their absence does not prevent this fixed generic runtime,
and does not cause fallback publication or reapplication.

## Verification and limits

The actual group runtime has 27 deterministic authored protocol controls using
two bounded fake unit adapters. They exercise deterministic guard/execution order,
both-stage-before-first-effect, known-invalid member 2, physical/name aliases,
shared original inputs, exact manifest ceiling and overflow, insufficient and
retained budgets, early/late cancellation, per-member failure, unavailable and
qualified finalization, missing/changed receipts/current facts, absent/revoked
current-caller authority, retained cleanup, failed manifest-save retention, new failed-finalizer artifacts
and cancellation at the prepublication context boundary. Repeated explicit
resume is also covered.

Independent effect counters and immutable captured-input witnesses establish
that skipped/uncertain members receive no execution call and repeated qualified
resume leaves exactly one effect per member. The tests use the real shared
current-caller authority revocation checks. They are protocol controls, not native
persistence, actual RAW/XMP modification, append admission, physical-power,
namespace acknowledgement or positive storage-profile evidence.
