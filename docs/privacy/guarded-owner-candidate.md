# Guarded OwnerName candidate (#0220)

Status: bounded implementation and authored native evidence, 2026-10-18.
All ten focused Windows native tests pass, with fresh author-separated review.
This internal
Windows mechanism constructs an in-memory derivative; it publishes no file and
does not complete #0089's positive operation acceptance.

## Explicit inputs and live binding

[`candidate.rs`](../../src/privacy/candidate.rs) binds one explicitly selected
XMP sidecar and optional explicitly selected native context to the shared
`GuardedSource`. It retains actual handles, original byte snapshots and their
object/name/property expectations. There is no same-stem discovery. A selected
native object aliasing the sidecar refuses.

Construction invokes the actual
[`privacy::remove_owner_name`](xmp-owner-removal.md) mechanism on the immutable
original packet. A changed candidate retains the exact original occurrence and
deletion range. Complete supported absence retains unchanged candidate facts.
Attribute and scalar-element removal use exact complement checks; duplicates,
unsupported structures and inherited provenance conflicts remain refusals.

Omitted native context stays `Unexamined`. Supplied context passes through the
existing provenance inspection and its refusals; an inspected status is neither
complete native metadata coverage nor authenticity. No rights Boolean, output
profile or serialized authority grants admission.

## Checkpoints and limits

The process-owned, move-only preparation retains candidate bytes and their hash.
Recheck compares the original bytes through the guards, verifies object/name and
property boundaries, verifies candidate integrity, and regenerates the exact
removal facts from the original snapshot. Any observed conflict or stale state
permanently poisons the preparation. A restored byte value cannot revive it.

The sidecar and derivative are bounded to at most 65,536 bytes, document IDs to
128 bytes, native input to the shared artifact bound, and XML structures to the
existing packet limits. Caller limits can narrow these ceilings. These logical
bounds do not measure all allocator overhead or reserve filesystem space.

Shared guards exclude the default-stream/name actors in their declared scope;
properties remain checkpoint observations. This increment changes neither guard
semantics nor unsupported-platform behavior. It exposes no serialization,
transaction, output, source-mutation or public apply interface.

## Finite acceptance

The ten actual [authored native controls](../../src/privacy/candidate/tests.rs)
cover attribute and element deletion, exact
complements, unchanged absence, duplicates, unsupported forms, provenance,
omitted/supplied native context, aliases, reparses, stale state and exact limits.
Source inventories remain unchanged in these finite schedules. The first native
attempt passed two tests and failed eight because a test fixture mixed path
separators in the shared parent comparison. Its artifacts were retained. The
corrected fixture was independently reviewed; the candidate source was unchanged,
and the second run passed all ten. This is authored disposable-file evidence,
not media, publication or complete property-actor qualification.

Candidate construction alone establishes no publication, retained-artifact
completeness, admitted storage profile, privacy certification or RAW mutation
permission. #0089 retains its actual positive operation acceptance.
