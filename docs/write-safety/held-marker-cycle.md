# Held two-name marker cycle (#0202)

Status: bounded implementation and preliminary native evidence, 2026-10-18.
The explicitly selected delayed continuation passes the original twelve native
cells, a prefix-zero property-check supplement and cancellation-during-wait
subcase. Sixteen attempted fixtures have an independent strict-property,
#0097-prefix-map and journal audit.
This is preliminary mechanism work, with no admitted profile, persistence
acknowledgement, committed group outcome or production RAW operation.

## Exact protocol

[`path_cycle.rs`](../../src/storage/path_cycle.rs) implements the existing
[#0097 protocol](two-name-cycle.md), rather than replacing its specification.
One common parent contains two distinct originals, alpha at `a` and beta at `b`.
One explicit temporary component must initially be absent. The only calls are:

1. Move held alpha from `a` to `temp`.
2. Move held beta from `b` to `a`.
3. Move held alpha from `temp` to `b`.

Both original objects and their ancestor guards remain simultaneously owned by
the cycle. Every call uses the shared retained-source, flags-zero no-replace
rename session. No copied candidate or pathname reopen substitutes for either
original. Unsupported paths, identities, comparison modes, properties and
initial maps refuse before rename effects.

| Confirmed prefix | `a` | `b` | `temp` |
| --- | --- | --- | --- |
| 0 | alpha | beta | absent |
| 1 | absent | beta | alpha |
| 2 | beta | absent | alpha |
| 3 | beta | alpha | absent |

The live owner checks original bytes, identity, properties and the actual name
map around each call. A bounded private record captures the plan, confirmed
prefix and uncertain-call state before effects. Records are observations, not
restart authorization or durable receipts. A stored prefix never permits
roll-forward. At most eight records of at most 64 KiB each are retained with
their private-root and record guards until drop. Property changes are reported
without restoring old snapshots. Access-time exclusions retain the shared SDK
baseline's scope and do not establish a complete property profile.

## Selected continuation and contrary evidence

The immediate three-move method has a retained counterexample: moving beta into
the vacated `a` changed its creation time to alpha's original value. The SDK's
full-snapshot comparison correctly stops on this mismatch. Distinct creation
times remain part of the fixture; there is no setter, property rebaseline or
equalized-time fixture concealing the change.

This observation is consistent with name tunneling, an inference rather than a
proved cause. Microsoft's
[FltGetTunneledName remarks](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/fltkernel/nf-fltkernel-fltgettunneledname)
describe creation-time caching for a removed name and the paired rename-away /
rename-into-vacated-name pattern. That minifilter routine is not a user-mode
preflight or cache-clear API.

Only the explicit `GuardHeldQuiet20Seconds` continuation has the passing finite
qualification here. On controlled fresh NTFS marker namespaces it keeps both
original and ancestor guards held for a measured approximately twenty seconds
before reusing each vacated name, then rechecks cancellation, exact properties
and the complete map before the next call. A normal three-move cycle therefore
takes approximately forty seconds. The immediate diagnostic method remains
contrary evidence; it has not been qualified by these passing delayed cells.

Elapsed time does not prove quiet namespace history, universal cache expiry,
causality or pre-effect preservation in arbitrary existing namespaces. Recent
create/delete activity, initial temporary-name history and other configurations
remain outside this controlled evidence. A post-call property refusal reports a
change after effects; it does not undo that change.

## Stops and finite acceptance

Cancellation stops before the next move. A failed checkpoint, guard loss, lost
response or contradictory map is terminal. The last observed map and confirmed
prefix remain distinct from current provable custody. Neither an original under
`temp` nor a foreign winner is cleanup material. There are no compensating moves,
replays or speculative rollback.

The [authored native controls](../../src/storage/path_cycle/native_tests.rs)
cover completion, initially occupied temporary
name, foreign winners at each newly empty slot, failures after confirmed prefixes,
preopened writer/name actors, property mismatch, cancellation, process exit and
lost response. The selected run's independent audit checks exact retained
identities, bytes, properties, prefix maps and bounded journals, including both
originals and every foreign winner. It also checks the prefix-zero property
failure and cancellation during the actual held wait. Earlier immediate-method
failures remain retained separately and are not counted as passing acceptance.

`CompleteObserved` means the checked final map is alpha at `b`, beta at `a` and
temporary absent. It does not mean the three calls were atomic or durable.
Final frozen production-caller qualification, #0213 integration, #0206 acceptance, replacement,
receipt/custody admission and #0026's positive scope remain separate.
