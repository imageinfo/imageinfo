# Process-owned marker custody and unpublished prune

**#0103 research runtime, observed 2026-10-15.** The new
[isolated runtime](../../experiments/0103-process-custody/runtime.py) turns the
previous hand-authored marker-supervision schedule into a reusable caller API.
It owns the actual subprocess object and captures its emitted context directly.
The existing [custody worker](windows-custody.md) still validates bounded snapshots,
and the existing [restart worker](windows-restart-actions.md) still reacquires
guards and selects exact eligible owned file handles. No worker/SDK code changes.

The scoped improvement is real process-local control: a matching editable journal
or a supplied PID/context cannot stand in for an observed child lifecycle. It
does not solve automatic cross-process/OS-restart custody. All commitment,
namespace acknowledgement, general repair, production publication and automatic
durable-custody flags remain false. Independent RAW/format and storage admission
remain separate gates; this is not a production API or writer.

## One trusted caller and one operation

`ProcessCustody(root, binary, byte_limit=655360, observe=None, control=None)` accepts
one fresh supervisor root and the exact reviewed F869 worker. Construction refuses
a preexisting root, unsupported binary or insufficient budget. Before creating the
root or invoking a worker it charges the full checked #0049 plan: one 65,536-byte
source, one candidate/output, four bounded transaction records and at most four
bounded custody snapshots, each no larger than 65,536 bytes. Charges never refund,
including after prune, cancellation, errors or close. This is logical admission
for this one instance, not a global quota, allocation accounting, free-space
reservation or a persistent cross-session budget.

The native worker authors `root/transaction.marker/source.marker` and creates its
private transaction/custody roots using the reviewed existing boundary. It accepts
no camera media or arbitrary source. `root/custody.marker` contains only the fixed
snapshot leaves; the outer caller-selected fresh directory is not a new security
or authentication mechanism. Source/root/custody records remain retained.

| Method | Required live state | Concrete behavior |
| --- | --- | --- |
| `begin()` | New instance | Prepare the authored source, start the actual receipt child, consume its before-publication context, completely save the captured snapshot, and pause at `before-namespace-call` without sending continuation. |
| `stop()` | Captured, unreleased | Kill if necessary and wait for this exact owned child process. Only confirmed exit without any release permits saving `stop-confirmed-before-publication`. Only a complete successful save creates the instance's internal stopped context. |
| `prune()` | Stop attested and saved | Mark the invocation attempted before starting the existing restart-prune worker with that internal context. Fresh native identities, bytes, properties and namespace decide which exact held objects can be removed. No retry is exposed. |
| `release()` | Captured, unreleased | Irrevocably mark fence/release work attempted, save the complete release fence, then continue the same child. Save observed and renewed contexts at their actual barriers and finish the unqualified receipt sequence. |
| `close()` | No other caller action active | Stop/wait only the owned child and invalidate process-local action context. Retain every file; do not manufacture a stop attestation, prune or refund. |
| `status()` | Any state | Return a fresh observation dictionary containing lifecycle/counters and false capability flags. Changing that dictionary grants no action. |

The internal enum and serialized public actions prevent reentry/double use. Prune
before confirmed stop, after fencing/release, after close, after any failed save,
after a refused/partial prune, or from a newly constructed instance is refused
before launching an action worker. The API accepts no caller-context argument,
JSON authority import, path sweep or arbitrary PID. Python callers are trusted:
private object attributes are ordinary implementation details, not protection
against malicious code running in the same interpreter. Worker hashing assumes
the trusted binary is not adversarially swapped between its check and launch.

A successful unpublished prune removes only the original owned candidate and two
records. The worker retains source and roots. A foreign extra name, a substituted
same-byte object or failed property check cannot be accepted through a matching
content digest. Compatible readers can defer removal; partial/error results remain
explicit and the runtime consumes the one action attempt even if no object was
removed. It never retries by filename or deletes custody material.

## Ordering, failures and observations

Captured history alone is not stop proof. The stop path observes exact child exit
before constructing its second snapshot; save completion precedes prune eligibility.
The release path completes the fence save before the original publication-barrier
continuation. Starting fence work permanently excludes the stop/prune branch even
if saving later fails. Publication becomes possible before attempting the pipe
write, so an ambiguous write cannot restore unpublished authority. The sanitized
status distinguishes that possible release from a completed write/flush.

Timeout, EOF, malformed/oversized output, excessive events, unexpected admission
flags, caller exceptions and interrupts terminate the owned child when possible,
invalidate action context and retain uncertain work. Pipe startup failure also
stops/waits the process already created by `Popen`. Failure to confirm exit never
permits stop attestation. Responses have a 30-second wait limit, at most 128 events
per child and 65,536-byte complete lines/requests. These are bounded protocol waits,
not a guarantee that arbitrary OS I/O completes within a hard deadline.

Observe/control hooks are explicit authored-qualification tools. They receive
copies of native events; controls are limited to `continue`, `cancel` and `fail`.
`begin()` still withholds its publication barrier regardless of a hook's proposed
control. Hooks cannot supply authority through the public API. Runtime lifecycle
observations (`captured-save-complete`, confirmed exit, completed stop/fence save,
publication continuation and prune start) complement actual worker events; an
independent audit reconciles both with the retained actual records and inventories.

This child changes no old evidence or [#0051 ledger](profile-admission.md), introduces
no key, encryption, service or new OS privilege, and authorizes no restart replay,
rollback or general finalize. A new supervisor refuses old roots even if their
records look valid. Surviving files remain the caller's unresolved material until
another separately authorized action establishes eligibility. The accepted
[VM-off power policy](power-test-policy.md) remains in force; no physical hardware,
guest NMI, host crash or VM fault is run by this qualification.

## Portable control verification

Six standard-library tests cover synthetic owned subprocesses: EOF, malformed and
incomplete lines, oversized output, fabricated admission flags, timeout, caller
exception/interrupt, finite event counts, bounded requests/controls, wrong-binary
refusal before root creation and reader-thread startup failure after actual process
creation. Fault cases verify the actual child stopped and an authored unresolved
witness remains unchanged. They deliberately do not supply F869/native filesystem
or publication evidence.

```console
python -W error experiments/0103-process-custody/test_runtime.py
python -m py_compile experiments/0103-process-custody/runtime.py experiments/0103-process-custody/test_runtime.py experiments/0103-process-custody/qualify.py experiments/0103-process-custody/audit.py
python scripts/check_docs.py
git diff --check
```

## Native qualification

The [audited twelve-case native ledger](process-custody-native.json) records
actual frozen-worker operations on **Windows 11 Pro 10.0.26200, AMD64, local fixed
NTFS**. An independent read-only post-run query found no remaining probe process
whose command line names the final qualification root. No unrelated process was
stopped. The current host token is not represented as a qualified standard-user
token; this is distinct from earlier evaluation-guest evidence.

| Case | Actual observation |
| --- | --- |
| Confirmed stop and complete stop save | One prune removes exactly the candidate and two records; source and both roots/custody remain. A second prune launches no worker. |
| Captured live child | Prune refuses before effects. Mutating a returned status dictionary and supplying an arbitrary context keyword grant no authority. |
| Released child | Complete fence save precedes publication continuation; the ordinary observational receipt sequence finishes, and prune remains unavailable. |
| Original failure; incomplete captured/stop/fence saves | Explicit protocol failure controls invalidate action authority and retain artifacts. Failed fence save sends no publication continuation. |
| Foreign extra name | Fresh guarded prune refuses before effects and retains the foreign file and exact prior inventory. |
| Same-byte candidate substitution | The replacement has the same marker digest but a different actual file identity. Prune refuses before effects; both the replacement and separately retained original remain. |
| Partial prune | An explicit protocol failure after the first actual removal leaves partial work and reports one removed owned handle; retry launches no worker. |
| Existing root and insufficient budget | Root adoption refuses. A 655,359-byte budget refuses construction before root creation or any native worker event. |

The twelve cases reconcile **248 native worker events** and **55 independent
source observations**. Every observed source retains exact identity, bytes,
timestamps, attributes and owner/DACL SDDL. Native custody acknowledgements are
checked against contexts actually emitted by the owned original child and against
the bytes of the retained bounded `custody-N.record` files. A runtime lifecycle
notice alone is not accepted as saved-history evidence. The audit verifies
captured save, confirmed owned-child exit, complete stop save and prune ordering;
the release case separately verifies fence completion before continuation.

All native and runtime commitment/admission flags remain false. Five authored
`fail` controls are explicitly **protocol injections**, not native storage errors,
device failures or crash evidence. Actual pruning is still measured: three owned
removals in the successful case and one in the partial case. Other attempted
prunes either refuse at the API without spawning a worker, or perform fresh
native validation and refuse without removal. No source, root, custody snapshot,
foreign extra or replacement object is swept or repaired.

The final runtime SHA-256 is
`4b80b2cc5885a70294fb548727b3f8eb0a1ea76d64278e2eff3ab0e3bcd99c36`;
the ledger binds implementation, qualifier, independent auditor, existing budget
module and bounded native observation adapter. Its worker remains F869 from frozen
source `b819f54533c495b332c3d4dbb0caccef49923036`. The first twelve-case run is
retained privately as superseded evidence: source review and portable tests then
fixed reader-pipe cleanup and failure during reader-thread startup after `Popen`.
The final twelve-case run was collected again against the final runtime hash.
No historical worker/capture was modified and no earlier result is silently
rebound to changed code.

Independent source review, the final native audit, all six portable tests with
warnings treated as errors, Python compilation, documentation checks and
`git diff --check` pass. The reusable runtime now enforces the previously manual
live caller sequence. Automatic OS-restart custody, a production integration and
independent format/storage admission remain separate work.
