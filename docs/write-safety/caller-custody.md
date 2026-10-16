# Explicit current caller custody

**#0169 implementation, 2026-10-16.** The crate-private
[`custody` module](../../src/storage/custody.rs) implements the trusted explicit
current caller selected by [#0165](new-output-contract.md). It hands off one
specific action decision for one exact known operation. It executes no restart
inspection, finalization, recognition, prune, publication or rollback. Those
action layers retain their own fresh native checks and profile requirements.
No public apply entry point or storage profile is enabled.

The actual Windows adapter's `custody_snapshot` first performs fresh full checks
under its original retained guards. Its observation binds operation, profile and
implementation revisions, output leaf and installed/unpublished state; the held
parent; the source/root/candidate identities and property/content facts; and every
actual owned record's identity, facts and exact bytes. Captures have a 65,536-byte
construction ceiling, checked before copying. Records retain their actual order;
duplicate identities, missing bindings, invalid lengths and excessive construction
refuse. Output remains the same candidate object after its one native rename.
The snapshot alone grants no action authority.

The adapter borrows each held record's bytes for this aggregate preflight and
includes the parent binding retained at root creation. It refuses an excessive
aggregate before copying either expected bindings or record payloads. Only an
admitted aggregate is copied for the fresh full check and owned caller snapshot;
an individual record fitting its own limit does not admit the combined capture.

`TrustedCurrentCaller` starts without authority. Its deliberately named
`attest_current` method is the selected application trust boundary: the current
caller independently asserts its exact retained operation and actual history.
It must not source that authority from editable transaction records. There is no
transaction/history/checksum/PID/path importer, automatic receipt recognition,
service, key store or new approval gate. The API does not authenticate a malicious
application in the same Rust process; executable selection, independent retained
history and a new post-reboot attestation are trusted caller responsibilities.
An application that has lost that independent knowledge remains read-only.

The current decision selects exactly one action. Unpublished prune requires
stopped-before-release history and the original absent output; finalization
requires stopped release history and the installed output; historical recognition
requires independently retained terminal completion and actual worker stop.
This is eligibility handed to a later action executor, not evidence that any
action or historical acknowledgement occurred. The original caller may deliberately
make a fresh current attestation, but a matching observation never does that for it.
Four attestation constructions bound one caller instance. A token is non-cloneable,
nonserializable and single-use. Replacing, renewing or dropping the caller revokes
outstanding tokens. A failed fresh binding comparison consumes the old decision;
restoring earlier matching bytes cannot revive it. Unknown roots, changed exact
bindings, missing or stale authority and contradictory history have distinct
retained-artifact refusals.

`OwnedWorker` retains the actual `std::process::Child`, not a PID lookup. The
selected worker and its bounded private-pipe observation callback are trusted to
report the known operation; an unrelated process exit is not evidence about it.
The caller supplies that operation when taking ownership, and capture rejects a
different operation. A completed bounded caller capture precedes release or stop.
The release path permanently enters uncertainty **before attempting** its external
fence save; only complete save success permits continuation. Failed, incomplete or
ambiguous initial/stop/fence saves and failed continuation prevent stop-before-release
handoff. Stop confirms exit of that actual owned child, then completely saves the
stop observation before transferring authority. Close transfers nothing and stops
only its original owned child. Released exit confirmation accepts only the actual
owned handle and success status; it cannot restore unpublished prune eligibility.
Caller save callbacks must perform their required complete write/flush; they are
not filesystem durability acknowledgements by themselves. Native calls and pipe
decoding remain synchronous, without a hard I/O deadline guarantee.

The private original-process channel is not an authentication mechanism against a
malicious same-owner process. As in [#0114](checked-receipt-custody.md), the selected
executable and application/decoder remain trusted. Unlike revival of #0114's
local eligibility, a recreated caller has no inherited capability: the explicitly
trusted current caller must make a new independent attestation if it still knows
the operation after a process or OS restart. No universal antirollback theorem,
automatic durable custody or same-owner security guarantee is claimed.

## Verification and retained limits

Authored tests cover empty recreated callers, exact explicit current decisions,
action separation, one-use tokens, renewal/close revocation, stale/rolled-back or
same-byte-replaced records, changed source/parent/output bindings, unknown roots,
contradictory histories and construction bounds. The Windows integration fixture
launches the actual Rust test executable as an owned worker. That child invokes
the production Windows adapter and pauses after the actual intent/root flush,
before the runtime begins caller release. The parent captures its bounded notice
from the original private pipe and saves independently outside the transaction.
Separate cases exercise actual stopped-child handoff, successful release and exit,
current recognition eligibility, and authored initial-save, stop-save, fence-save
and continuation failures. A real same-byte native record replacement changes its
object identity and refuses the original current decision. Test results and full
retained artifacts remain private under `.local/work-wave-20261016e/169-*`.
An additional native fixture creates four actual 16,000-byte held records and
verifies aggregate custody refusal before owned payload copying; a positive copy
control and a parent-only boundary vector qualify that check separately.

The faulted saves/continuation are authored caller-protocol failures, not native
storage-device or flush errors. Actual native completion supplies bounded caller
integration evidence, not profile admission, OS-restart survivor qualification,
namespace durability or VM-off evidence. No restart mutation or source-media
mutation is run. Existing best-effort power policy and separate RAW/format,
inspection/action and profile gates remain unchanged.
