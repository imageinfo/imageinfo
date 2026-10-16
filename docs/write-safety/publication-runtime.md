# Bounded single-unit publication runtime

**#0167 implementation, 2026-10-16.** The crate-private production runtime in
`src/storage` executes one caller-validated candidate and expected-absent output
through the ordered effects in [the #0165 contract](new-output-contract.md).
An actual Windows adapter invokes the safe held-object facade in
`crates/imageinfo-windows-storage`. It is not another record-only protocol model.
The runtime and adapter are disabled internal infrastructure: there is no public
apply entry point, admitted storage profile, RAW permission or transaction importer.

The independent format layer must supply a crate-private `ValidatedCandidate`:
an operation identity, format revision, finite planned length and maximum, byte
reader and `ExpectedAbsent` output leaf. Current imported plans, preview results,
receipt fields and external booleans cannot construct this decision or select an
admitted profile. The actual Windows source guard retains the existing source
separately from the candidate reader; a later format adapter must bind its actual
validated observation to those held source facts. The
[#0168 live acknowledgement bridge](live-acknowledgements.md) binds actual
phase/target/revision results; #0176 still owns exact profile admission.

## Actual orchestration and bindings

The runtime reads the exact planned candidate length in bounded chunks and probes
one additional byte. Short, overlong and failing readers stop before root creation.
The complete candidate is bounded in memory by the caller's explicit maximum;
the native adapter additionally enforces its 64 MiB artifact maximum. It then creates
the private root, flushes that root and its containing parent, exclusively creates
the candidate, verifies it and flushes candidate then root. Prepared and intent
records are created, checked and file/root flushed in that order before caller
release and the final prepublication check.

`Binding` contains a separately compared native object identity plus immutable
property/content facts. Empty, oversized and repeated object identities refuse.
The Windows implementation captures volume/file identity and the native property
snapshot, and includes a SHA-256 content fingerprint for the exact held bytes.
The native facade retains and compares those complete bytes; a fingerprint is
neither an object guard nor action authority. Bindings extend monotonically when
exclusive creation returns an actual object. Expected future identities are never
invented. The adapter compares the exact bounded root namespace at every full
check, including its expected candidate-to-output name transition.

Four length-prefixed records bind the protocol, implementation and unqualified
profile revisions, operation/format identity, output leaf, planned length, actual
previous bindings and completed prior phases. Each is at most 65,536 bytes. They
contain no assertion about their own later identity, flush or final verification.
Prepared and intent precede publication; observation follows installed checks and
file/root flushing; the separate receipt follows the observation's file/root flush.
The receipt is file-flushed and immediately fully checked, then root-flushed and
fully checked again. A checked caller context, final check and terminal export
follow under the retained guards. No parsing of these records advances execution.

The actual Windows backend stores pre-release, checked and terminal captures in
the original caller's memory, separately from the transaction records. Captures
retain exact record bytes and actual bindings, and later checks compare their
unchanged prefixes. This supplies the live original caller seam, not automatic
restart custody or an import format. Restart actions remain #0169's scope.

## Results, cancellation and retention

`Cancellation` is an atomic cooperative token. The runtime checks it between
synchronous backend calls and between source reads; it does not abort an active
Windows call or promise a deadline. Cancellation before publication reports
`CancelledBeforePublish`; a failure before publication reports refusal, conflict
or failure according to the actual facts. `release_possible` becomes permanent
before the caller-release operation: a later cancellation does not recover
stop-before-release authority. `publication_possible` becomes permanent before
the single no-replacement native rename call. Any subsequent error, failed check,
cancellation or lost terminal response yields `RecoveryRequired`. A detected
conflict terminates the attempt; the runtime never rechecks until matching and
resumes, rebases a snapshot, retries publication or sweeps retained artifacts.

The public result vocabulary includes unchanged, refused, conflict,
failed-before-publish, cancelled-before-publish, committed, recovered-original
and recovery-required. The explicit caller no-op bypass returns unchanged before
executor invocation; this executor performs no original restoration. Until actual profile admission is connected,
complete internal execution reports `protocol_complete = true` with `Refused`;
only a test-only exact revision capability exercises `Committed`. This is a completed unqualified execution, not a claim
that a refusal proves the positive admitted storage capability. Every result
identifies phase, failure, possible release/publication, charged construction,
retained material and pending cleanup. Cleanup and recovery are explicit separate
operations and are not performed by this executor. Dropping native guards retains
the namespace.

`LogicalBudget` reserves `S + 8 * 65,536` before candidate allocation or target
effects: the actual planned candidate size, four maximum transaction records and
at most four maximum caller captures. Overflow and insufficient capacity refuse
before backend calls. Failed, cancelled and uncertain attempts retain the entire
reservation. Reusing the same budget across attempts therefore counts retained
work. There is no refund operation. This conservative process-local bound does
not measure physical allocation, reserve free space, provide a durable global
budget or recover accounting after process restart; #0173 retains broader
production resource/retention integration. An existing read-only source is not
new scratch-file construction. The adapter's extra source/candidate comparison
buffers are finitely bounded memory, not additional logical disk constructions.

## Verification and limits

Authored deterministic-backend tests exercise the complete ordered execution,
every backend-call fault boundary with IO, conflict, ambiguity and unsupported
errors, cancellation after each operation, lost terminal response, short/overlong
and failing source reads, record bounds, arithmetic overflow, malformed/duplicate
bindings and exhaustion across retained attempts. These tests establish runtime
control flow and terminal facts; they do not qualify Windows IO or persistence.

The Windows authored test invokes this same runtime through the actual native
adapter and retains its source, artifacts and private outcome under
`.local/storage-runtime-tests`. Unsupported native parent/file operations or
property conflicts are recorded as observed failure phases and fail the authored
completion test; they are never skipped into success. The observed native result
is recorded in the private handoff. The separate
[#0168 joined native schedules](live-acknowledgements.md) add actual phase
acknowledgements and before/after injected-response controls. No media,
guest, VM-off or physical-power tests are run for this scope. Native-error,
interruption, namespace/receipt, source/format binding, restart custody and exact
profile qualification remain independent work. The accepted
[best-effort power policy](power-test-policy.md) remains unchanged.

Separate actual native refusal regressions verify a reserved output leaf and an
existing source exceeding the native 64 MiB limit. Both report unsupported-request
refusal before target construction, with release/publication/retention facts all
false. The SDK supplies typed unsupported errors; the adapter does not infer
policy refusal from message text. Actual OS IO errors retain failure semantics.
