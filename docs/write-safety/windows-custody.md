# Caller-history snapshots and publication release

Implemented as bounded **#0043** research under organizational parent **#0022**,
observed **2026-10-14**. This increment retains explicit caller contexts outside
the editable marker transaction and records publication-release ordering. It uses
the existing [ordinary-owner worker](ordinary-output.md) and
[caller-directed restart actions](windows-restart-actions.md). It enables no
production writer, storage profile, committed receipt or automatic repair.

## History and caller responsibility

A trusted supervisor captures the live before-publication context while the
original worker is blocked at `before-namespace-call`. It retains the context in
a separate fresh private directory. Before sending that barrier's `continue`, it
must save a publication-release fence and receive the successful snapshot result
after the file flush, parent flush and final checks. A saved fence records that
publication may have been released; it does not prove that the worker attempted
or completed the namespace call.

Alternatively, the supervisor can stop its held original process and wait for
confirmed exit without ever releasing that barrier. Only then may it record
`stop-confirmed-before-publication`. Parsing JSON cannot establish that live
history or authenticate the assertion. The resulting context is a candidate for
the caller's explicit restart request, subject to its existing fresh guards and
artifact checks.

| Latest validated history | Context candidate |
| --- | --- |
| Captured only | None. Missing release history never proves nonrelease. |
| Publication release fenced | None. Publication remains uncertain even if output is absent. |
| Stop confirmed before publication | Before-publication context with the caller's stop attestation. |
| Publication observed | Exact captured operation with its observed output context. |
| Observation renewed | Same operation and prior records, extended from two records to three. |

Stop confirmation is terminal. Release after stop, stop after release, duplicate
capture/release, observation without release and changed operation bindings
refuse. Renewing an observation must preserve the root, source, candidate,
digest, request mode and both prior record bindings. The typed history has a
fixed purpose, at most four events and a 65,536-byte bound. Unknown/duplicate
fields and truncated JSON refuse as a whole; no valid-prefix repair is attempted.

## Snapshot storage and inspection

`ordinary-custody-save` stores one new whole-history snapshot per event as
`custody-1.record` through `custody-4.record`. The first request exclusively
creates a fresh private root. Later saves and `ordinary-custody-inspect` require
the root's actual identity/property binding from the first result. Directory
mtime is deliberately excluded because creating snapshots changes it.

Each new snapshot uses exclusive creation and the already reviewed write-through
handle option, followed by separate file and parent flush calls. Existing
snapshots are opened with retained byte/name guards; their bounded contents must
decode and exactly equal successive prefixes of the proposed full history.
Checks cover the fixed namespace, current private DACL, default-stream shape,
single links, ordinary file type, readonly rejection and held path bindings.
Final checks run after the snapshot and flush barriers, including the exact name
set. Foreign entries and failed/partial records remain without overwrite,
pathname deletion, sweep, ACL repair or root cleanup.

Inspection reads the whole exact available sequence and changes neither custody
files nor the editable transaction. `callerContextCandidate` represents the
history supplied by the caller; `callerAuthorityAuthenticated` and
`custodyFreshnessProven` remain false. Every result also retains false commitment,
namespace acknowledgement, repair and production-publication flags.

The directory identity does **not** bind historical snapshot-file identities.
Inspection accepts the measured same-byte replacement of a snapshot with another
fresh file having the expected current private policy. It also cannot distinguish
a semantically valid forged history or an older restored history from the
caller's current history. A missing final snapshot can expose an older captured
or fenced prefix; neither prefix produces a restart context. These checks do not
provide authentication, antirollback protection or durable freshness. The caller
must retain trusted current provenance and decide whether to use a candidate.

## Evidence and remaining work

The [native audit](windows-custody-native.json) covers **41 cases**, **117 custody
worker captures**, **41 unchanged custody inspection inventories**, **41 unchanged
transaction inventory pairs before the explicit caller action**, and **1,398
readable hashed artifact paths**. One deliberately inaccessible DACL path is
retained without repair. Actual worker controls reconcile whether the publication
barrier was released; the supervisor records process exit before stop attestation
and complete fence save before its one publication continuation.

The cases cover captured/stopped/fenced/observed/renewed states, malformed or
inconsistent histories, missing/changed/extra artifacts, readonly/ADS/link/DACL
conflicts, same-byte replacement, held snapshot write/delete/rename and root-rename
actors, and cancellation, injected failure or forced
snapshot-writer termination at save barriers. Late foreign entries refuse a
successful save. An explicit stopped caller request prunes three owned handles;
the renewed context validates its exact existing observation. Source and root
remain. These are finite native controller and worker observations, not crashes
of the Python supervisor or native storage-error qualification.

Seven portable history tests bring the research crate to **30 tests**. Validation
also closes Serde's tagged-unit-variant extra-field acceptance by using empty
struct variants, and validates nested history during deserialization rather than
normalizing through an untyped JSON value that would lose duplicate fields.

This increment reuses the existing [SDK review](../../experiments/0032-windows-publication/ffi-review.md)
and [dependency admission](windows-inspection-dependencies.json). No SDK call,
feature, dependency, key service, encryption or privileged helper is added; root
production unsafe policy is unchanged. The fixed write-through flag retains its
[documented persistence limits](windows-persistence.md).

**#0044** separately owns guest interruption/restart qualification for this
custody sequence. Prior guest results do not qualify it. Durable context freshness,
full namespace/receipt qualification, storage errors, resource accounting,
physical power loss and complete profile admission remain separate work.
Independent RAW admission remains refused under #0027; #0023/#0024 stay gated.
