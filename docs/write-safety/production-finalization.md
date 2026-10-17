# Explicit installed-output finalization

#0171 implements a crate-private Windows completion action for an already
installed, attributable new output. It never republishes, copies, renames,
overwrites or deletes the output, source, prior records or root. The public
apply path, storage profile and independent RAW admission remain closed.

## Authority and survivor boundary

The original native backend retains an exact ordered `LiveEvidence` prefix
outside the transaction records. Its `finalization_prior` seam checks that
actual progress reached creation of the complete observation record, captures
fresh exact object/record bindings and refuses known failed-check history.
`PriorProof` has private fields, no serialized importer and is moved into one
attempt. Parsed phase names cannot construct it. All three required prior
records must exist and match; a previously bound missing receipt is a conflict.

A trusted **current** caller separately attests released-and-stopped history and
authorizes `FinalizeExisting` against exact current bindings. The action checks
this revocable authority before and after every actual boundary. Revocation,
caller closure, stale or conflicting context and an incomplete original live
prefix refuse. This is the explicit caller trust boundary selected by #0165;
it supplies no automatic durable custody, historical authentication or recovery
permission from a receipt alone.

The fresh attempt has a bounded caller-selected identity distinct from the old
operation. Its source, output and every prior record are opened directly with
their final required guards. No read guard is dropped to reopen an object for
write during the attempt. The new interval is checked against independently
retained original identities, complete bytes and property observations; it does
not claim continuity across the earlier interruption.

## Actual bounded sequence

The new safe SDK capabilities are separate from #0170's read-only
`ExistingRoot` and `Inspection` APIs. `FinalizationRoot` holds writable existing
root/containing-parent handles and checked full ancestry. `FinalizationFile`
opens existing files without truncation and without writer/delete sharing.
It exposes exact checks and flush, with no byte writer, rename or deletion API.
The independent source remains read-only. All held guards survive through the
checked-context and terminal callbacks.

The action performs these real operations:

1. Check the entire installed set and exact bounded namespace; flush the actual
   installed file, transaction root and containing parent; recheck the full set.
2. If the receipt was independently proven never created, check/flush the actual
   observation and root, then exclusively create only `receipt.record`. The new
   record binds the actual three prior records and preceding successful phases.
   It contains no assertion about its own future flush. A foreign winner or
   partial/conflicting receipt is preserved and refuses advancement.
3. For either a surviving exact receipt or a newly created one, check the full
   set, flush the held receipt, immediately check, flush the root, and check again.
4. Retain the checked context through a trusted caller callback, run the final
   complete check, then export the terminal context while all guards remain held.
   A failed or lost callback response retains recovery-required.

Existing receipts and their historical assertions are never rewritten. Fresh
acknowledgements bind the new attempt and each immutable actual binding prefix;
only exclusive receipt creation appends a new binding revision. The context
retains the original independent progress and the exact old-operation/new-attempt
relationship. A callback cannot attest its own future successful terminal return.

A separately selected current authorization recognizes either a retained original
terminal completion or a completed fresh-finalization context through read-only
#0170 inspection. Matching later artifacts confer no new authority. A later
source/output edit or missing previously bound object is a conflict, and
recognition performs no duplicate effects.

## Evidence and limits

`src/storage/finalization/native/tests.rs` executes authored native controls:

- Twelve original unfinished observation/receipt/final-check phases successfully
  finish through real held-file/directory flushes and full checks. A separate
  production-mode control completes the protocol while retaining `Refused`.
- Thirty-four controller schedules fail immediately before or after each of
  seventeen actual outstanding boundaries. Every attempt retains
  `RecoveryRequired`; these are injected return/lost-response observations,
  **not actual device-error or power-loss evidence**.
- Missing output/prior record/previously bound receipt, changed source/output,
  stale and midattempt-revoked caller, foreign receipt winner, incomplete original
  acknowledgements, exhausted budget, cancellation and failed caller save refuse.
- Native exclusive receipt creation separately preserves an actual foreign name
  winner. Writer attempts against source, installed output and prior record fail
  while checked and terminal contexts are exported.
- Original and fresh terminal completion can be recognized without duplicate
  effects; a later owner edit refuses. Independently reopened retained artifacts
  verify original source/output identities, full bytes/properties, original prior
  records and absent candidate names. Successful contexts also match a fresh
  read-only inspection. Authored fixtures and detailed inventories stay in the
  private `.local/work-wave-20261017b/171-*` evidence directories.

Positive `Committed` controls use a test-only admission variant that is absent
from production builds. Production protocol completion remains unqualified and
reports `Refused`; all failures/uncertainty report `RecoveryRequired`. Logical
construction charging is cumulative, performed before native acquisition, and
never refunded; native reads and records also retain their existing finite
64 MiB/64 KiB ceilings. This is not a physical allocation quota.

No guest, VM-off, native storage-error, crash, physical-power, format-preservation
or complete profile qualification follows from these host controls. Recovery
material remains retained and pending cleanup; #0172 owns separate eligible
cleanup. There is no rollback, repair of conflicting records, target replacement,
source mutation, general retry or automatic custody mechanism here.
