# Windows marker receipt guest interruption qualification

Bounded **#0047** research under **#0022**, using the
[#0046 marker receipt sequence](namespace-receipt-marker.md) and the existing
[disposable Windows evaluation guest](windows-guest.md). The matrix uses authored
65,536-byte markers. It does not accept camera media.

## Exact implementation and fixture

The worker source is frozen at accepted #0046 revision
`b819f54533c495b332c3d4dbb0caccef49923036`. The guest executable is rebuilt with
static CRT linkage for the installed guest. Its exact executable hash and frozen
source bindings must be recorded separately from the historical dynamically
linked worker. The exact static executable must pass the original **93-case
native receipt matrix** before guest fault observations are admitted. Reusing a
historical passing label does not verify a rebuilt executable.

The retained fixture runs Windows 11 EnterpriseEval build **26300**, local NTFS,
as its existing standard local test user. The same frozen worker and loaded
controller/driver sources are bound across the run. Private source archives,
executables, guest disk, controller state and captures remain outside the public
repository. Historical evidence is preserved.

The existing installed fixture and guest-only crash configuration are reused.
This work introduces no OS policy change, evaluation rearm, new SDK boundary,
production helper or dependency. Fault injection targets only the disposable
guest; Terry's host is never crashed.

## Matrix and caller context

One normal transaction exercises completion and explicit read-only inspection.
Each of the following **11 barriers** is then crossed with three fault methods,
for **33 fault cells** on independent fresh marker transactions:

| Barrier | Observation before interruption |
| --- | --- |
| `before-namespace-call` | Prepared candidate and intent exist; publication has not been released. |
| `published` | The held no-replacement rename returned successfully. |
| `installed-file-flushed` | The installed-file flush returned successfully. |
| `parent-flushed` | The parent flush returned after the installed-file flush. |
| `observation-file-flushed` | The separate observation record was written and its file flush returned. |
| `observation-parent-flushed` | The parent flush returned after the observation-file flush. |
| `observed-record-flushed` | The worker reached its ordinary observation checkpoint. |
| `receipt-written` | The separate receipt exists and an external receipt context was emitted; its explicit file flush has not yet been called. |
| `receipt-file-flushed` | The held receipt-file flush returned successfully. |
| `receipt-parent-flushed` | The parent flush returned after the receipt-file flush. |
| `final-checked` | Fresh guarded artifact/property/namespace checks passed before the final control continuation. |

The three fault methods remain distinct:

- Kill the held worker process and confirm exit, with no guest OS restart.
- Kill the emulator and relaunch the same retained guest disk.
- Trigger a guest NMI bugcheck, collect fresh bugcheck evidence, then perform a
  controlled emulator quit and relaunch.

Restart cells require a distinct fresh guest boot. Process-only cells require
the same guest boot. The independently recorded host boot must remain unchanged.
Every worker token must remain the fixture's standard-user token.

The supervisor captures the actual emitted `receiptContext` outside editable
transaction records, before interrupting a receipt-stage cell. It supplies that
exact context to `ordinary-receipt-inspect` after the fault. Earlier cells have
no receipt context: missing context must refuse, even if matching record bytes
or a receipt name can be found. The test never synthesizes authority from those
records. The normal control checks explicit matching-context inspection.

Inventories bracket each read-only inspection, including the missing-context
request. Byte/name inventory agreement and exact property-observation agreement
are audited and counted separately. These inventories do not read native file
identities. The native inspector supplies freshly guarded checks of current
object identities and properties. An inspection may validate surviving bindings
or refuse a missing/conflicting survivor; neither outcome permits repair.

The public `recordSurvivors` and `receiptClassification` value
`matching-context` describes independently decoded content, size, hash and
context-body agreement. It does not itself assert current native object identity,
a successful native inspection, caller authority or durability. Lost names,
changed bytes, inaccessible objects and other mismatches must be retained as
counterexamples rather than converted into assumed successful persistence.

## Evidence status

The method above defines the requested matrix. No guest result is claimed until
the private raw captures and exact static native baseline have been reconciled
by the #0047 audit. The sanitized ledger will distinguish completed cells,
matching receipt observations, refusals and survivor counterexamples. Successful
Windows calls and barrier labels alone cannot establish those outcomes.

A preliminary attempt completed 19 progress rows and stopped in the twentieth
cell, emulator kill at `receipt-written`, when the rich inventory pair observed
the receipt's `lastWriteTimeUtc` differing by approximately **2.56 ms**. Names,
bytes, hashes, sizes, alternate streams, SDDL and root observations matched. The
native inspector refused with `FILE_PROPERTIES_CHANGED`. The cause is unproven:
the observation does not establish that inspection wrote the timestamp, and it
is not dismissed as a cache effect. The incomplete attempt, including the
twentieth cell's before/after captures and source copies, remains private.

The driver and audit now distinguish byte/name agreement from property-observation
drift while retaining the native inspector's property checks. A fresh complete
run is required; the preliminary rows are not a completed matrix or final audit.

Reproduction and private-evidence requirements are in the
[qualification tooling README](../../experiments/0047-receipt-guest/README.md).

## Limits and remaining gates

Host caches remain alive during all three methods. A controlled emulator exit
after NMI can drain submitted I/O; emulator kill is a separate method. The guest
OS, crash dump and marker operations share the same NTFS/QCOW2 test volume.
These finite cells do not qualify physical power loss, every storage provider,
an unmeasured crash window or a universal Windows persistence guarantee.

The external context is an explicit caller binding. Its capture does not
authenticate durable caller authority, automatic freshness or history custody.
The minimal observation receipt cannot satisfy #0045's qualified outcome receipt
obligations or attest its own future flush. Relevant properties remain checks at
declared OD-11 option A boundaries; continuous exclusion of same-owner property
changes is not promised.

All commitment, namespace acknowledgement, repair and production-publication
flags remain false. There is no finalize, prune, replay, rollback or automatic
recovery authority. Actual storage-error qualification (#0048), cumulative
resource/retention policy (#0049), complete profile admission (#0051), durable
caller-history custody and independent RAW admission remain separate gates.
#0027's real-camera refusals and #0023/#0024 restrictions remain unchanged.
