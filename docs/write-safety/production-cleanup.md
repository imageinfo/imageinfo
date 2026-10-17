# Exact-owned production cleanup

#0172 adds explicit internal cleanup to the production Windows storage facade.
Actual authored native controls exercise positive unpublished pruning and
selective cleanup after actual terminal completion. No production storage
profile, public apply command, RAW permission or durable deletion acknowledgement
is enabled.

## Authority and retention

Unpublished cleanup consumes one nonserializable `PruneUnpublished` authority
for independently retained exact bindings and confirmed stop before caller
release. It also handles the live creator's fully captured candidate before any
record exists. Released, uncertain, changed and revoked operations cannot enter
this action. Partially constructed files without a retained complete binding
remain untouched.

Postcommit cleanup uses a separate `CleanupCompleted` authority and independently
retained actual terminal evidence. It accepts either the original live protocol's
complete proof or a complete fresh [finalization context](production-finalization.md).
An incomplete prefix, disk receipt or caller status alone cannot construct that
proof. The trusted current caller additionally selects each fixed record whose
recovery-retention obligations are resolved elsewhere. Unselected records remain
recovery evidence; the API cannot select the source, installed output or any
directory. The current profile remains explicitly unqualified even when its
internal protocol and cleanup complete.

The action is bounded to one source, one transaction root, one candidate/output
and at most four fixed record names. It imports no arbitrary paths or filenames
from records, performs no pattern sweep or recursive directory removal, and
never calls a pathname-deletion fallback. Source, output, root, containing parent,
foreign names, reinserted objects and unrelated entries remain protected.

## Fresh effects and outcomes

The adapter holds the independent source and complete directory ancestry,
requires the ordinary private root policy, and checks the exact namespace.
Selected files are opened with read/DELETE access but no write/delete sharing;
unselected files and installed output have read-only guards. Complete identity,
bytes, supported properties, streams, link count, root/parent properties and
current authority are checked before each effect. Regular-file snapshots are
never rebased. The existing mutable-directory policy excludes only directory
size/write time and the archive bit. Same-owner property changes remain boundary
checks under [option A](practical-output-policy.md).

The separate SDK capability calls ordinary `FileDispositionInfo` on the freshly
verified retained handle and consumes it. Failed checks distinguish a disposition
call that was never issued from an attempted call with an uncertain/error return.
There is no POSIX disposition, directory removal, write, rename or permission
setter. [The SDK review](../../crates/imageinfo-windows-storage/SDK-REVIEW.md)
records the exact added boundary.

Each result reports exact expected physical identities, purposes, per-object
dispositions and whether fresh verification succeeded. This supports privacy
residual reporting without inferring that every expected object still occupies
its old name after a conflict. Remaining objects become unverified after failure;
observed removed names retain their individual outcome.

| Observation | Result |
| --- | --- |
| Every selected handle removed and exact names observed absent | Removed; source/output/root and unselected records retained |
| Compatible reader defers final unlink | Pending, removal-requested identity retained; reader closure may finish unlink |
| Existing reader prevents DELETE acquisition | Refused, pending cleanup, no effects |
| Failure, cancellation, changed properties, foreign insertion or revoked authority after an earlier removal | Partial; exact prior removals retained and remaining objects preserved |
| Missing/changed/reinserted object, stale authority or extra entry before effects | Refused, no deletion fallback |
| Original full binding reused after partial cleanup | Refused; no stale retry or edit replay |

The whole attempt is single use. A partial remainder requires new independently
established exact remaining-object authorization; this API does not automatically
derive or resume it. Cleanup failure preserves prior terminal completion and
never rolls back, republishes or reapplies an edit. Observed absence is a live
namespace observation, not a flush/power-loss guarantee.

## Finite verification

Eleven native Rust tests exercise actual authored Windows files, including:

- Early live candidate and confirmed unpublished candidate/record removal.
- Positive selective postcommit cleanup and actual #0171 finalized-context cleanup.
- Reader deferral, acquisition refusal, partial removal and stale retry.
- Missing, byte-changed, foreign-reinserted and extra-entry refusal.
- Actual property mutation between removals, foreign insertion, cancellation and
  authority revocation stopping the next effect.
- Incomplete terminal evidence refusal and retained source/output/root controls.
- A real read-only SDK disposition failure with exact retained-file audit and no
  pathname fallback.

Positive/partial controls independently reopen surviving paths, compare original
physical identities, complete bytes and properties, and audit the exact removed
name set. Detailed fixture artifacts remain under the ignored local evidence
directory. Injected pre-effect errors are controller fault observations, not
physical-device failure claims. No VM-off or physical-power campaign is added.

Run `cargo test --locked --lib storage::cleanup -- --test-threads=1` on Windows.
The portable authority model and all existing inspection/finalization checks
remain separate verification. Actual profile admission and broader recovery
retention policy remain their own scopes.
