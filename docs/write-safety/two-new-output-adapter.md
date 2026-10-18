# Staged Windows two-new-output preparation (#0222)

Status: bounded preparation implementation and authored native evidence,
2026-10-18. Eight native preparation controls and sixteen independently executed
portable runtime controls pass, with fresh independent High-effort adapter review.
This independently closeable preparatory increment does not complete #0180's
positive unit-adapter, publication or resume qualification.

## Move-only stage and continuation

The internal adapter in
[`group_new_output.rs`](../../src/storage/group_new_output.rs) uses the shared
[`runtime`](../../src/storage/runtime.rs) prepare/continue seam. Preparation
owns the original backend, request metadata, `Attempt`, phase/binding state and
already-charged ledger. Continuation consumes that exact preparation once. It
does not reconstruct a request, reread an unbound source, refund retained work
or reopen dropped handles.

Stage stops immediately before the existing caller-release boundary. Both actual
units must finish staging before the first release. Invalid second input prevents
publication. Failed or cancelled staging retains the actual backend/source/
candidate holds, exact artifacts, terminal error and retained charge. Existing
single-unit execution must use the same method order, records and fixed binding/
acknowledgement arrays.

The shared group executor stops after an unqualified first-unit result. A truthful
preparation outcome can therefore be unit 1 unqualified and unit 2 staged but
unattempted. No fabricated qualified receipt or committed first unit may advance
execution merely to obtain two completed native calls.

## Manifest and surviving owner

One bounded group manifest has separate ownership, identity binding and a single
retained charge. Its exact namespace slot must be accounted for by unit 1's
namespace checks. It is not inserted into fixed per-unit binding, record,
receipt, custody or acknowledgement arrays, and their parsers are not widened.
The manifest placement and once-only accounting require independent review.

The synchronous process-owned group owner retains the original `Run`, current
authority, manifest hold, ledger and both unit preparations in the same process.
Its owner-local capability is intentionally not transferable between threads.
No subprocess protocol is supplied. Any future stoppable helper must leave this
state with the surviving owner. Owner-process death loses the nonimportable
state; a recreated owner, serialized `Run`, saved path or imported caller history
does not recreate it. This preparation supplies no automatic restart custody,
receipt verification or finalization.

The existing SDK artifact constructor can fail after creating a partial pathname
without returning a `HeldArtifact`. The adapter preserves every actually returned
handle and exact known binding, along with root guards, known material and
retained charge. It neither invents a partial object's identity nor reopens an
unknown partial pathname. Thus handle-retention claims apply only to actual
returned holds; possible unreturned partial paths remain an explicit baseline
constructor limitation.

## Finite acceptance and remaining positive work

The eight actual [authored native checks](../../src/storage/group_new_output/tests.rs)
cover both-stage-before-release ordering,
invalid second input, exact artifacts and charges on unqualified outcomes,
preparation failures, cancellation, retained holds, manifest namespace and
once-only charging. The sixteen independently executed
[portable runtime controls](../../src/storage/runtime/tests.rs) include explicit
call-order comparison of split and ordinary execution, evidence/record/charge
equivalence, and fault/cancellation retention. These finite results preserve
ordinary single-unit method order; they do not establish admitted publication
or resume.

The public unsupported selector continues to refuse before constructors.
Receipt/finalization interfaces remain unavailable without exact unit admission.
No admitted profile, positive token, `QualifiedReceipt`, authority importer,
public bypass, media or VM execution is added. #0180 retains its remaining
positive publication, receipt and resume acceptance on the exact final caller.
