# Prepared-source namespace attribution — #0217

**Retained evidence does not establish the cause of #0174's prepared-source
namespace discrepancy.** It remains a contrary preservation observation, with
no demonstrated fix. This read-only source/evidence investigation preserves
[#0174's negative qualification](production-native-errors.md) and
[#0176's unsupported admission result](new-output-admission.md).

## Exact evidence boundary

The investigated worker is SHA-256
`9495e70fea1e5b91eaeb3d02ebcbe1da04a83268ef8743e02c7e24f78a6d73a6`.
Its privately retained frozen runtime, adapter, observer and SDK sources bind
the source analysis; later production changes are not attributed to that worker.
The authored source is 16 MiB; the independently supplied candidate is 4 MiB.
Candidate bytes are not copied from the source file.

The retained guest-script binding matches the checked-in
[preparer](../../experiments/0174-native-errors/guest.ps1). That binding records
served script bytes, not an independent measurement of the executing script.
Preparation, original execution and continuation controller revisions differ.
Controller binding snapshots record these file hashes:

| Binding epoch | Controller SHA-256 |
| --- | --- |
| Earliest control binding | `291666fdf913e7c1ebceb8ea8bf1597dbd700a813bdc0ebfedfce92a8a5c9158` |
| Intermediate before-unused-resume binding | `f40dc5b2045d491ef4424ec20647a1e8a000bde983f9601b7cef7a05451f2729` |
| Final binding/current file | `74bb22cbb793d7f15fd541a36d5d6c91d75f121cb54462d2b6f3028e17336090` |

A file hash at a binding epoch does not by itself identify code loaded by a
resident controller. Historical controller source bytes were not located in
this investigation, and the table does not certify which revision was loaded
for staged execution. Captured commands establish the actual staged rule and
graph facts. Final source must not be presented as the exact controller for
earlier observations. Exact bindings and reconciliation remain private.

## Observed facts and their limits

The following names are logical names inside the disposable authored fixture.
They are not operational host paths.

| Boundary | Retained observation | What it does not establish |
| --- | --- | --- |
| Guest preparation | Metadata inventory finds `/case/source.bin`; worker preflight reads and binds the full source successfully. | Independent persistence of the preparation, or source continuity after the error. |
| Before fault | Preflight, transaction-root creation, root flush and parent flush return success. | A qualified durable namespace baseline. |
| Armed backend rule | Persistent (`once=false`), sector-unrestricted `write_aio`/write rule with Linux errno 28; staged raw node's failed-write counter increases from zero to four. | Four identified Win32 calls, candidate-data-only faults, or Windows disk-full/actual exhausted capacity. |
| Compound candidate operation | `create-Candidate` returns `BackendIo`, Windows 433; terminal is `FailedBeforePublish`, phase `CandidateCreated`. | Which create/write/check substep failed, or a Windows disk-full/WriteFile result. |
| Guest post-error inventory | Source and transaction inventories are empty arrays. | Deletion: the inventory also returns empty for a failed path test and does not retain that test's explicit result/error. |
| Stopped-image observation | Prepared source and transaction child paths do not resolve; the retained root listing lacks `case`; `/source.bin` yields the exact authored source bytes. | Deletion, rollback, when the namespace changed, or the old-name file's identity and full properties. |

Exactly one staged worker/error/result history is retained. No staged worker
restart or publication retry is recorded. Preparation failures and the later
continuation for two unused flush cells do not supply missing staged observations.
The worker reports no publication and zero removals; that is not a post-error
namespace inventory.

The retained QMP commands bind the staged USB/raw device and its temporary
write-filter child to the same intended raw file, separately from the system
QCOW2 overlay. The rule exposes writes across that volume, including potentially
delayed metadata. The four failed backend requests have no captured offsets or
ownership; none is attributed to candidate data, source-directory metadata,
NTFS journal work or preparation. Current controller source uses `once=true`;
that later code does not replace the retained staged rule's `once=false`.

Successful filter removal is recorded after receipt of the failed compound
result; there is no staged removal failure/retry. The observer does not pause
after emitting that result. Worker failure handling, terminal generation and
handle drops can therefore overlap the guest's synchronous HTTP post and host
filter removal. Later receipt of the terminal does not order those worker
actions after removal. The guest's empty inventories and normal exit result
already precede the next cell, so later shutdown/offline inspection cannot
alone explain that earlier observation.

The [offline auditor](../../experiments/0174-native-errors/audit_retained.py)
uses a stopped-image NTFS tool view. A nonzero prepared-path read is a failed
lookup/read observation, not a recorded NTFS deletion. Successful old-name reads
bind stream bytes, not continuous Windows object identity, ACLs, times, links or
streams. The root listing adds a separate namespace observation, but its exit
status and a direct `case` enumeration were not retained. Earlier independent
review reproduced the six readable/unreadable results and partition-copy
equality. The separately bound observation below does not retroactively fill
that auditor's missing identity or query-status records.

## New bounded stopped-copy observation

One freshly reviewed metadata observation read the exact retained staged raw
image through a read-only descriptor. Its original full hash and file identity
matched before and after collection. The actual MBR bounded one type-7 NTFS
partition at LBA 2048, with 260,096 sectors. A new 133,169,152-byte partition copy
was independently rehashed, made read-only and observed without mounting or
repairing it; its final hash and identity also matched.

Pinned `ntfsinfo`/`ntfsls` 2022.10.3 and their shared library collected exactly
eight predetermined record/path/index views, plus two version records. Each
process had a 20-second deadline and 65,536-byte combined capture ceiling.
All outputs, errors and statuses were retained; there were no retries or
queries selected in response to a result.

| View | Observed result | Scope |
| --- | --- | --- |
| Direct source record and old-name lookup | Both describe record 64, sequence 1, one link, and a `source.bin` filename with parent record 5. | Agrees with the initial record reference and prepared live identifier on this fixture; it does not prove continuous custody or an historical transition. |
| Root record and root listing | The source appears as inode 64; the root listing has no `case` entry. | Final shared-library record/index interpretation, not a separate filesystem decoder. |
| `case` and prepared-source path queries | Exit code 0, empty stdout and an ENOENT-style error on stderr. | A lookup-error report; exit code 0 alone is not evidence of lookup success. |
| `case` index query | Exit code 3 with empty output streams. | A failed query, not an observed empty directory. |

The direct record and old-name views narrow the previous content-only identity
gap. Their source-record dumps also match the retained pre-guest metadata
rendering. Record/sequence agreement supports retained on-disk linkage within this
fixture; it cannot exclude every historical reconstruction or identify when
the preparation names stopped resolving. The tools share libntfs and therefore
do not provide independent filesystem-parser agreement. No result establishes
deletion, rollback, journaling/writeback cause or preparation durability.

## Reachable effects in the frozen source

The fixture creates `case` and moves the source from `/source.bin` to
`/case/source.bin` before starting the worker. Its source contains no move-back,
source deletion or filesystem teardown. Its finalizer can stop a remaining
worker and clear the controller filter; neither action is a source cleanup.

The frozen worker opens the source for reading/read-control with retained
ancestry and a read-sharing hold. Before the named failure, its explicit
namespace effects are transaction-root creation and possible candidate
creation/writing. The compound candidate operation includes exclusive creation,
security checks, `write_all`, snapshot and binding checks. On error, later source
checks, records and publication are skipped. No source rename, delete,
source-byte write or custom filesystem-cleanup destructor is reachable in this
branch. Ordinary handle closure still occurs; source analysis does not prove
that filesystem/cache error handling has no effects.

Preparation had no independent durable acknowledgement. This does **not** mean
there were no pre-fault flush calls: frozen root creation calls `sync_all` on
the held `case` parent before creating `unit`; the subsequent explicit root and
parent operations flush `unit` and `case`. All return success in the staged
capture. These are actual API acknowledgements. There is no explicit source-file
or volume-root directory flush for the earlier preparation, nor a stopped-image
pre-fault baseline. The successful case/unit calls alone do not establish the
unqualified backend's durable namespace guarantees.

## Smallest unresolved causal contrast

Retained evidence cannot distinguish incomplete persistence of preparation,
metadata effects during the fault/filter-removal/close/shutdown sequence, or an
offline interpretation limitation. None is an established cause.

A finite diagnostic proposal should retain the authored preparation, frozen
production runtime/adapter/SDK operation ordering and staged error rule, adding
only the observations needed to separate those boundaries:

- Bind volume identity, root/case/unit directory identities and name sets, and
  held-source identity/properties plus old/prepared pathname results immediately
  before fault activation and after child reopen before native continuation.
  Retain explicit lookup errors.
- Identify the failing SDK substep and failed backend request offsets/statuses;
  repeat the observations after its return while worker handles remain paused,
  then after filter removal before worker release. Current captures do not
  isolate these boundaries or attribute the four failed writes.
- Compare a matched cell with the same preparation, timing and child-reopen
  sequence without an error rule, retaining the actual persistent whole-volume
  rule as the faulted contrast. If
  preparation persistence remains the question, isolate one explicit preparation
  persistence checkpoint as the contrast; do not count the existing case/unit
  flush returns as an independent baseline.
- On verified stopped-image copies, compare direct file-record and directory-index
  views with pathname lookups. Retain the shared NTFS-library interpretation limit;
  these views do not supply an independent filesystem decoder. Preserve original
  images and failed observations.

These are missing observations and a bounded method proposal, not a completed
reproduction or permission to execute it. An exact source/fixture/observer plan
requires fresh independent review before any new native diagnostic execution.
The original worker cannot pause after the candidate-operation result. Reliable
pre-close checkpoints therefore need a separately bound test-only observer and
guest/controller coordination, with new source/executable identities and declared
timing effects. Such observations cannot be attributed to the unchanged original
worker.
No worker, guest, fault, mount, repair, replay or cleanup was run for this handoff.

Bot storage integration under #0022 owns the next separately scoped corrective
increment. #0217 delivers this bounded diagnostic and contrast definition;
execution of the new instrumented native contrast and a supported correction
remain subsequent work. A correction must be supported by the actual result.
Cause attribution alone will not establish preservation on the proposed profile.
The three native flush-error classes and live configuration binding remain
separate unresolved predicates. All commitment, profile and RAW admission gates,
strict preservation requirements, ordinary-owner option A and VM-off-only
best-effort limits remain unchanged.
