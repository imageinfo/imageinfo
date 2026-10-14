# Caller-directed Windows marker restart actions

Direct **#0022** research under accepted [OD-11 option A](practical-output-policy.md),
observed **2026-10-14**. This increment adds two narrow restart actions to the
existing [ordinary-owner marker worker](ordinary-output.md). It retains the
independent [namespace/receipt persistence limits](windows-persistence.md).
Neither action establishes a committed output or enables a production profile.

## Authority and scope

The caller must supply an explicit context on standard input. A live supervisor
captures that context while the worker still holds the source, candidate, records
and name guards: either before any publication attempt, or after held publication
and the indicated flush observations. The supervisor retains it outside the
editable transaction. A restart worker must receive that independently retained
context from a caller authorized to direct this operation.

The three checkpoint modes emit context before `before-namespace-call` and before
the `parent-flushed` and `observation-parent-flushed` barriers. The latter two
exports follow the respective flush call. Their stage describes
the observed live history, not a durability guarantee.

The bounded portable context has a fixed purpose and stage, root/source/candidate
identities and properties, marker digest, persistence request mode, and the exact
owned record set with individual identities and digests. Its schema excludes
arbitrary paths and commitment/profile claims. `stoppedBeforePublication` defaults
to false in the exported context; only the supervisor may attest true after
proving that the original worker stopped without permitting its namespace call.
Duplicate/unknown fields, invalid shapes, aliased identities and inconsistent
record sets refuse.

This JSON is a representation of the caller's explicit authority, not an
authentication mechanism. The worker cannot tell whether an arbitrary caller
fabricated a matching context or loaded it from mutable transaction files.
Checksums, an inspector classification and an editable record cannot grant
ownership, publication or deletion permission. Preserving a trusted caller context
across an OS restart remains the caller's responsibility; this experiment adds no
secret, key service, encryption or privileged helper.

The only data is the existing authored 64 KiB marker. The context does not permit
arbitrary files, source metadata edits, replay, rollback or source ACL changes.

## Revalidation and actions

Before either action, the worker reacquires held byte/name guards and validates
actual root, source, candidate or installed output, and every record against the
caller context. It checks current content, identity, fixed names, stream/link
shape and ordinary private-owner properties. Relevant properties are observations
at declared boundaries under option A; continuous exclusion of same-owner
property changes is not promised.

| Mode | Required caller stage | Bounded effect |
| --- | --- | --- |
| `ordinary-restart-prune` | Before publication | Mark only the proven unpublished owned candidate and records for removal through newly retained handles. Keep the source and root. |
| `ordinary-restart-observe` | After publication | Validate a matching installed output and create a fresh observation record with exclusive creation, or validate the already existing observation record. Keep source, output and root. |

Prune requires an unpublished operation and no installed output. It does not turn
an absent output after an uncertain namespace call into proof that publication was
never attempted. The supervisor must stop the original worker before permitting
the namespace call and retain that history with the prepublication context. A
previously emitted prepublication context is stale if the supervisor later lets
publication proceed. The restart worker cannot reconstruct that history from JSON.
Prune requires the caller's explicit `stoppedBeforePublication: true` attestation
as well as the before-publication stage. A postpublication context cannot authorize
prune or contain that attestation. Setting the Boolean is a caller assertion, not
an authenticated proof produced by parsing.

The record set and actual namespace must agree with the fixed scope. Foreign,
missing, changed or inaccessible artifacts prevent the action; no pathname
deletion fallback, recursive cleanup or ACL repair follows a failed check.
Deletion disposition is applied to the held verified objects, not to paths taken
from JSON or directory enumeration. Partial or failed disposition is reported;
compatible readers can defer final removal until they close their own handles.
An observation-creation failure after effects reports retained work as pending
cleanup; it does not quietly discard a partial fresh record or retry creation.

Observation records remain observations. Exclusive creation preserves a foreign
winner, and a matching existing record does not become a durable receipt. All
`committed`, `namespaceAcknowledged`, `repairAllowed` and
`productionPublicationAllowed` flags remain false. The separate
`ordinary-admit`, `ordinary-finalize` and `ordinary-prune` modes retain their
refusal before effects.

An existing observation must be bound by a three-record caller context. A saved
two-record context cannot accept an extra observation record just because it looks
matching. After creating and flushing a fresh observation file, restart-observe
exports a renewed three-record `callerContext` before
`restart-record-file-flushed`. The active caller can retain that new context for
later validation of this exact record; the export still carries no commitment or
durability claim. Partial prune does not authorize an automatic retry. If the
retained namespace no longer matches its original exact context, a repeated
request refuses rather than selecting residual files by name alone. A restart that
restores the entire exact original namespace must still pass every fresh guard
and context check before the caller-directed action can proceed.

## Boundary review and verification

The restart path reuses the admitted SDK graph and existing Windows calls. Safe
Rust implements context parsing and operation validation. The existing
[#0038 disposition review](../../experiments/0038-staging-cleanup/ffi-review.md)
now describes the narrow extension from live creator-retained handles to freshly
held objects whose exclusive-creation ownership is explicitly attested by the
caller context and revalidated. No new SDK API, feature, crate, handwritten ABI
layout or root production unsafe permission is introduced.

The [audited native ledger](windows-restart-native.json) covers **61 worker
cases**, **40 unchanged inventories** and **1,385 readable artifact
paths**, including alternate-stream aliases. One deliberately inaccessible DACL
record is retained without ACL repair. The cases exercise successful unpublished
prune and observation creation/validation, explicit stop attestation, malformed or
stale caller contexts, changed identities/content/properties, extra entries,
partial action/error reporting and reader deferral. Namespace checks also run
after fresh observation creation; a foreign extra entry keeps the outcome
uncertain rather than allowing an apparently successful observation result.

Four new portable context tests bring the research crate to **23 tests**. Research
format, Clippy, tests and release checks pass, as do the root checks with **44
Windows tests**. Existing inspection and persistence results do not themselves
qualify these new actions.

The [published CI ledger](windows-restart-ci.json) records successful Ubuntu,
Windows and macOS jobs for `0c8d78e`, including the native Windows restart matrix,
Unix unsupported-adapter refusal and root contracts. The initial `15d1dff` run
found unused Windows-only helpers in Unix test builds; the follow-up gates that
implementation to Windows while retaining portable parsing and tests.

The [audited guest ledger](windows-restart-guest.json) covers **three scenario
sets and five faults**, with **three fresh NMI bugchecks**, **two emulator
terminations**, **five distinct post-fault boots** and **25 bound capture files**.
The worker uses the existing standard-user Windows build **26300** NTFS/QCOW2
fixture and the [documented restart limits](windows-guest.md). The host stayed on
the same independently verified boot; host caches remained alive.

- NMI before publication: caller-attested unpublished prune removes three owned
  handles and retains the unchanged source and root.
- NMI after the publication parent flush, followed by emulator termination after
  restart observation-file flush: the original two-record context refuses the
  extra record; the renewed three-record context validates that exact existing
  observation. Postpublication prune refuses without effects.
- Emulator termination before publication, followed by NMI during prune after one
  file-removal checkpoint: retry with the original context refuses before effects
  and retains the partial namespace. This measured partial removal is not a
  completed prune or permission to delete remaining names automatically.

These are finite caller-directed action observations under the named guest fault
methods. No namespace commitment, durable receipt or automatic context custody
follows from a matching artifact or successful flush return. Physical power loss
and storage-provider error/resource qualification remain open.

This is caller-directed marker research, not unattended recovery from editable
transaction records. Full namespace/receipt qualification, native storage-error
cells, physical power loss, automatic durable caller-context custody and actual
RAW admission remain separate gates. #0027's RAW refusal and #0023/#0024 gates
remain unchanged.
