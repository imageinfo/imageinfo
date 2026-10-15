# Native receipt timestamp completion observations

**#0100 research, observed 2026-10-15.** The
[audited twelve-cell ledger](receipt-timestamp-completion-native.json) records a
controlled native investigation of write-handle completion and receipt property
binding. **No timestamp drift was reproduced.** This narrows the measured native
lifecycle hypothesis; the two [#0047 guest crash counterexamples](namespace-receipt-guest.md)
remain unexplained and continue to refuse exact property agreement.

## Exact question and profile

The frozen receipt worker captures receipt metadata while its write-through
handle remains open. The `receipt-written` checkpoint precedes its explicit
receipt-file flush. The question here was whether normal process completion,
direct process termination, explicit flush or closing a marker's writer changes
the property value visible through held versus fresh read-only handles.

This run used **Windows 11 Pro 10.0.26200, AMD64**, on the local fixed **NTFS**
volume containing fresh authored marker fixtures. A separate read-only OS/volume
query records that actual profile privately. It is distinct from #0047's
**Windows Enterprise Evaluation 10.0.26300 guest** and its emulator/NMI faults.
No OS crash, host fault, VM run, media mutation or policy/privilege change occurred.
The driver used the current user token; no standard-user-token qualification is
claimed from the host run.

The worker SHA-256 remains
`f86918a7fb3880cf8e09590fcc7d58155ef64d98c95cf9c2a6afc541c5b040fa`,
from frozen source `b819f54533c495b332c3d4dbb0caccef49923036`.
Historical worker/source/captures were not edited or regenerated. The
[isolated experiment](../../experiments/0100-receipt-timestamps/README.md) declares
the complete schedule, exact observer access/sharing/lifetime, ABI and reproduction
commands. The ledger binds the actual driver/native-adapter/auditor/harness bytes.

## Finite observations

| Cells | Controlled schedule | Actual result |
| --- | --- | --- |
| 6 frozen-worker cells | `receipt-written`, `receipt-file-flushed`, `final-checked`, each followed by normal continuation or direct process termination. | Receipt `lastWriteTime` unchanged across worker exit with observer retained and subsequent fresh observer. |
| 6 authored-marker cells | Buffered and write-through writers, each binding after write, explicit flush or writer close. | No later timestamp difference from the selected binding; fresh post-close bindings repeat unchanged. |
| 12 receipt inspections | Actual phase context and latest emitted context, independently inspected after each worker exit. | All return `observed-receipt-recovery-required`; all before/after inventories match. |

Every observation compares metadata from the retained observer, a fresh path
handle, and the retained observer again after bounded read-only queries/reads.
Those views agree. File identity, size, link count, attributes, creation time,
owner/DACL SDDL and bytes remain unchanged across the measured lifecycle;
source/output marker hashes remain exact. Last-access time is not included:
observer reads may affect it, and this experiment makes no exclusion claim for it.

The authored writer queries creation metadata, waits 20 ms, then writes. Its six
first post-write timestamps differ from their creation values by approximately
20–22 ms. Those are observations of the deliberate separation, not performance
results. Neither explicit flush nor ordinary close adds an observed mtime change
in these cells. The experiment therefore supplies **no demonstrated benefit** for
the candidate mitigation of closing the writer before establishing a fresh
read-only property binding. It does not justify changing the frozen worker or
weakening its property checks.

All twelve actual receipt inspections preserve the complete fixed namespace,
bytes and owner/DACL observations, report no effects and zero owned removals.
Worker/inspector events keep `committed`, `namespaceAcknowledged`, `repairAllowed`
and `productionPublicationAllowed` false. All objects and private captures remain
retained; no cleanup or restart action is enabled.

## Interpretation and remaining work

Microsoft's [file-times documentation](https://learn.microsoft.com/en-us/windows/win32/sysinfo/file-times)
places its update guarantee at closure of the handle making the change and
describes last-write updates while writer handles remain open. That motivated
the hypothesis; it does not identify the cause of an observed crash timestamp
difference. The [handle-information structure](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/ns-fileapi-by_handle_file_information)
defines the queried identity/time fields. These primary references were reviewed
2026-10-15; no documentation revision is pinned.

The measured native process-completion schedule did not reproduce the guest
emulator/NMI `receipt-written` mismatch. It does not rule out recovery-specific
metadata behavior, other storage layers, observer timing or a different OS build.
The historical counterexamples are neither dismissed as cache effects nor blamed
on inspection. Targeted guest/recovery observations remain necessary to explain
them. There is no qualified namespace acknowledgement, persistence, physical-power
result, complete storage profile or RAW admission from this child. #0078's format
and storage prerequisites and [#0051's refusal ledger](profile-admission.md)
remain in force.

The independent auditor reruns against actual retained captures, preserves every
timestamp difference if one exists, checks actual emitted contexts and exact
non-mtime invariants, and creates a fresh public result. Independent review
checked the native ABI/handle lifetimes and recomputed all twelve cells and twelve
inspection pairs. Python compilation, documentation links/JSON and
`git diff --check` pass.

Two setup attempts remain private and separate from the twelve-cell run: an
initial relative-path preparation refused `PATH_UNVERIFIED`; a second attempt
stopped when Python's ordinary file open conflicted with the writer's sharing
contract. The final run resolves paths and reads through the declared native
read-only sharing contract. These aborted attempts are not counted as completed
cells or erased from the evidence.
