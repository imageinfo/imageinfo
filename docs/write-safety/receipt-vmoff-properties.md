# Native receipt properties around VM-off recovery (#0106)

This research diagnostic follows [the earlier guest receipt observations](namespace-receipt-guest.md)
and [the native timestamp-lifecycle non-reproduction](receipt-timestamp-completion.md).
It observes the unchanged F869 marker actor with a separately built read-only
observer. It adds no timestamp fix, rebinding, setter, SDK API or dependency.

The `ordinary-receipt-properties` mode in
[`ordinary.rs`](../../experiments/0032-windows-publication/src/ordinary.rs)
opens seven fixed objects: the root, source, installed output, three prior
records and receipt. Each open requests only `READ_CONTROL | FILE_READ_ATTRIBUTES`,
shares read/write/delete and uses the existing open-reparse-point/backup-semantics
flags. These flags constrain the final path component, without ancestor guards.
It captures native identity, byte length, links, attributes and integer creation
and last-write FILETIME before security/stream queries, then queries the existing
private-owner descriptor check, default-stream check and pathname binding, and
captures native information again. It reads no content and invokes no setters,
flushes, rename, removal or repair. Query failures are retained per object.

A root open/type/property/binding failure stops child traversal. These permissive
diagnostic handles provide snapshots, without continuous pathname or property
exclusion. The observer does not export an arbitrary security descriptor: its
native security result is equality/refusal against the existing current-owner
policy; the separately ordered rich inventory retains actual SDDL.

The [controller and independent auditor](../../experiments/0106-receipt-properties/README.md)
use two checkpoints (`receipt-written`, `receipt-file-flushed`), process
termination/VM-off and native-first/rich-inventory-first order, plus a normal
control: nine fresh transactions and at most four VM-offs. The guest agent runs
the observer synchronously while the actor is held, before termination or the
external VM-off. Generic wrapper content inventories are omitted, so they cannot
precede an intended first native observation.

For each cell the controller preserves the actor's actual emitted receipt
context, pre-interruption native information, first post-interruption observation,
rich inventory, native information before inspection, frozen F869 inspection,
native information after inspection, a second rich inventory and final native
information. The auditor independently checks receipt/record hashes and bindings,
actual event order, integer/native and rich property differences, byte/name
preservation and the earliest **observed** mismatch. Equality cannot establish
that no unobserved transient change occurred.

The frozen restart helper also bootstraps the agent after signing in. An
automatic logon agent can consume a read-only request before that bootstrap
replaces it. A lost observation is never invented: an explicitly recorded
operator continuation may resubmit only the missing read-only inventory or
native observation. Its pending history and exact request are retained. Such a
cell is operator-assisted and can contain an additional, possibly partial native
or rich observation; it does not establish the unassisted exact observer schedule or
causal resolution across that interval. The writer and fault are never replayed.

The observer source freeze contains complete canonical-LF sources and exact
hashes. It deliberately excludes the concurrently developed restore module and
its two routing declarations, while retaining the exact published observer in
`ordinary.rs`. Its static executable differs from F869 and the later integrated
research binary. The frozen actor and its accepted 93-case native audit/source
binding remain unchanged.

Collection uses a fresh private QCOW2 overlay and copied TPM/firmware state,
preserving the stopped original guest, base disk, settings and earlier captures.
No evaluation rearm, host crash, NMI, guest bugcheck or physical-power campaign
is part of this work. The controller verifies its exact scoped emulator before
QMP `quit`, confirms its exit, and checks the base's bytes again afterward.
Host caches remain alive; QMP emulator-off is a bounded VM-off observation,
without a claim about physical storage power loss. QMP `quit` may drain backend
I/O, so it is distinct from the historical emulator SIGKILL/NMI cases and cannot
explain those cases by matching native observations alone.

On 2026-10-15 the independent audit reconciled all nine cells and four VM-offs.
The [public evidence](receipt-vmoff-properties-guest.json) preserves the results:

| Cells | Frozen receipt inspection |
| --- | --- |
| One normal control | Observation-only receipt matches |
| Four process terminations | Observation-only receipt matches |
| Two VM-offs at `receipt-written` | Refused with `FILE_PROPERTIES_CHANGED` |
| Two VM-offs at `receipt-file-flushed` | Observation-only receipt matches |

Both `receipt-written` VM-off cells show native receipt last-write FILETIME drift
between the pre-fault observation and the first completed post-fault native
observation. No within-query native change was observed. The rich-first cell's
first rich inventory additionally reports receipt length zero, while its captured
receipt bytes and stream length are 1,815 bytes; the later native and rich lengths
are 1,815 bytes. This is a disagreement among observations, without proof of
physical truncation or its cause. All nine cells retain matching names, hashes
and captured record bytes; eight retain equal complete reported-size inventories.
Sampled rich and native timestamp observations agree with each other.

In the rich-first cell the first rich inventory already exposes the property
disagreement before the first completed post-fault native snapshot. The native
comparison therefore identifies its earliest **native** observation, without
claiming that native observation caused the change. The native-first
`receipt-written` cell and native-first `receipt-file-flushed` cell required one
explicit read-only continuation each: a missing rich inventory and a missing
native snapshot, respectively. Their original incomplete read-only execution may
have been partial or absent. Both are labeled operator-assisted; no writer,
publication or fault was replayed, and no additional VM-off occurred.

The initial bound verifier is retained unchanged. A separately identified final
verifier corrects its blanket LF requirement for unchanged historical imported
helpers and retains actual cross-source inventory disagreements instead of
assuming an atomic rich snapshot. It changes neither captures nor frozen actors.
Source hashes before/after match; original base disk, firmware and manifest hashes
match; the actual Windows host boot and WSL boot are unchanged. The overlay guest
was shut down normally and its scoped emulator, TPM helper and transport stopped.

No result changes the existing `property-policy` admission outcome. Namespace
acknowledgement, durable caller custody, complete storage profiles, automatic
recovery, production publication and RAW mutation remain unqualified; parent
#0022 remains open.
