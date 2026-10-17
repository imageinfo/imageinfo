# Caller-owned cumulative production resource admission

**#0173, 2026-10-17.** The crate-private `storage::resources` owner runs the
actual [single-unit production executor](publication-runtime.md) with cumulative
logical admission across repeated authored operations. It retains charges after
completion, failed reads/allocations/backend responses, cancellation, partial
removal and unresolved recovery. This infrastructure has no public apply entry,
admitted storage profile, source-media mutation or RAW admission.

## Ownership and admission

The selected boundary is one explicit trusted current caller's bounded ownership
scope. `RetainedSession::start` requires an explicitly known empty operation set.
Unknown state or a nonempty set without its original accounting refuses. This
assertion is the current trusted caller's responsibility; it is not established
by a directory listing, byte count, editable record, checksum or PID.

The session privately owns its budget and complete ledger, with at most 256
operations. Each operation has bounded borrowed operation/root keys; duplicate
operation or root keys refuse. Keys label the caller's complete set and confer
neither filesystem identity nor restart-action authority. Native guards and the
[current-caller custody contract](caller-custody.md) remain separate.

Before copying keys, reserving ledger capacity, allocating a candidate or calling
the backend, one checked charge admits:

- The exact planned candidate length.
- Four maximum 65,536-byte transaction records and four maximum caller captures,
  as enforced by the existing executor and native adapter.
- One additional 65,536-byte allowance for the bounded ledger entry and retained
  result, including its operation/root keys.

The charge is therefore `candidate_length + 9 * 65,536`. Overflow or a total above
the session limit refuses before construction/backend invocation. The session
then creates an unexported exact one-unit allowance for the existing executor.
That helper cannot reset the cumulative owner, which was already fully charged.

Additional custody, recovery and manifest constructors require a bounded borrowed
size, at most 65,536 bytes, and reserve it before invoking the trusted internal
constructor. Failure retains the charge. The concrete native custody wrapper
reserves the full maximum before the existing capture's borrowed whole-input
preflight and copy. These callbacks are trusted crate implementation seams, not
an external extension or a claim that arbitrary callbacks obey a declared size.
Their actual construction bounds must be audited at each caller.

The shared two-unit seam atomically reserves both complete unit allowances plus
the bounded manifest size before returning separate byte-limited runtime budgets.
The group caller owns their one-time use and the surrounding operation/manifest
bookkeeping. Failed total admission returns neither helper and changes no charge.

## Recreated callers and retention

`suspend` moves the complete non-cloneable ledger and budget into `RetainedWork`.
`adopt` consumes that original object and requires an independently selected
complete operation/root-key set. Missing, additional, duplicate, conflicting or
unknown keys refuse and return the unchanged retained object. The limit and all
charges stay attached to it; adoption provides no reset or increase. There is no
decoder or constructor from transaction files. A new process without this exact
in-process ownership object cannot adopt nonempty state through this API and
must refuse it. Automatic durable accounting/custody remains separate work.

A panic or an interrupted constructor leaves uncertain state and prevents later
effects or adoption. Known failed/cancelled operations retain their full maximum
even when they produced no artifact or left only a partial artifact. This is
deliberately conservative logical construction accounting. The implementation
offers no refunds, including after explicit partial removal. It never prunes,
replays or discards recovery material to make room.

## Availability and actual failures

Before each new executor invocation, the selected native advisory query holds
the output parent's ancestry, checks local NTFS and fresh stable identities and
properties around `GetDiskFreeSpaceExW`, and returns caller-available bytes. The
new call remains in the [isolated SDK boundary](../../crates/imageinfo-windows-storage/SDK-REVIEW.md).
The production session compares that observation with its unit construction
allowance. Low availability reports `StorageUnavailable`; query errors retain
their failure class. Neither case calls the transaction backend. Both retain the
already admitted logical charge.

The observation expires immediately: it reserves no space and promises no quota,
physical allocation, future read/write/flush success or freedom from concurrent
allocators. Actual executor errors retain their existing phase/status facts and
charges. Later construction can still fail. There is no machine-wide service,
hidden durable ledger, directory-size authority, key management or new product
storage guarantee.

## Evidence and limits

Portable tests cover exact/below limits, arithmetic overflow, actual candidate
capacity refusal, unavailable/failed advisory observations, exact-set adoption,
pre-construction charging, failed constructors, uncertain-state refusal, and
atomic two-unit admission with exhausted helper reuse.

The actual Windows test uses the production native adapter and authored bytes
for five operations under one caller: complete execution, a lost create response
after actual record creation, cancellation after actual candidate creation, a
short reader, and a lost terminal response after actual complete publication.
An extra actual bounded custody capture, failed recovery-file construction and
manifest construction retain separate charges. Explicit test-operator removal
of one authored candidate leaves its prepared record and every charge intact;
this is a no-refund observation, not a production cleanup capability.

An independent construction observer reconciles candidate/record counts and
lengths, native capture counts, retained actual file sizes and the cumulative
formula. Exact complete-set adoption retains the exhausted budget and refuses a
new operation before backend effects. Private inventories and outcome evidence
remain under `.local/work-wave-20261017a/173-*`; no real media, VM interruption or
power test is involved. These finite native observations establish neither
storage-profile qualification nor persistence/restart repair.
