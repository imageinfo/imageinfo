# Post-operation namespace observer — #0218

**This increment qualifies a separately bound, test-only observer for the
post-candidate boundary missing from [#0217](prepared-source-namespace-attribution.md).**
Two fresh local native controls have passing retained-evidence audits. The
historical prepared-source discrepancy
and its causal uncertainty remain. This observer supplies no correction,
qualified storage profile, durable acknowledgement or RAW admission.

## Worker boundary and lifetime

The diagnostic lives in the Windows-only test module
[`namespace_diagnostic.rs`](../../src/storage/namespace_diagnostic.rs), with an
explicitly ignored authored-marker entry point. It uses the ordinary unqualified
Windows backend and runtime. The diagnostic wrapper preserves the production
runtime, adapter and SDK operation order; it adds pauses and observations rather
than changing the production sequence or SDK boundary. The frozen #0174 worker
and its historical results retain their own identities.

The important pause occurs immediately after the compound candidate operation
returns its result to the diagnostic wrapper, before that result returns to
runtime success or failure handling. The backend and its retained source and
ancestor holds are still live while the owning parent observes this boundary.
Only an explicit matching release permits continuation. A temporary SDK handle
created inside a failed compound operation may already have closed before the
pause. A live backend does not imply that such a failed temporary handle remains
open, or identify which SDK substep failed.

The worker emits separately ordered candidate-result, runtime-result and
backend-dropped records. The latter marks the diagnostic's explicit backend-drop
boundary; an exit record comes from the owning parent. These records must be
reconciled with actual process and nonwriting source-hold observations. A child
exit status alone does not establish that the observer reached its pause.

## Owning parent and bounded exchange

The collector uses a directly owned child with stdin/stdout. Its authority is
the current explicit owning parent; serialized commands, hashes and event
records cannot import or recreate that authority. No HTTP service, credentials
or cryptographic authority scheme is introduced.

The [protocol](../../experiments/0218-namespace-observer/protocol.py) carries
versioned, unit-bound events with contiguous sequence numbers. A before-operation
pause accepts only its matching `continue`; the candidate-result pause accepts
only its matching `release`. Commands bind the exact unit, sequence and stage.
Cancellation, stale or duplicate commands, wrong-stage commands, malformed
records, EOF and deadlines refuse the attempt. They do not authorize replay,
publication continuation or cleanup.

The declared wire ceilings are 32,768 bytes per event line, 1,024 bytes per
command and 128 events. Each worker acknowledgement gate has a 15-second limit.
The exact reviewed run plan must also freeze the whole-process deadline,
stdout/stderr capture ceilings and command count. Limits bound the collector's
logical capture and the owned process; they are not an OS quota or descendant
containment. Trusted in-process callbacks must remain bounded: the collector
cannot preempt arbitrary Python code inside them.

Every attempt receives a new retained directory. Requests, exact argv, source
and worker hashes, plan/bounds bindings, raw captures, parsed events, commands,
ordering, process status and failures remain available for audit. A failed or
partial attempt is retained under its original identity; a later attempt must
be separately declared. No automatic cleanup or adaptive replay is part of this
method.

## Exactly two local native controls

Required regression checks also exposed an accumulated test-fixture directory
with 4,098 retained entries, exceeding the unchanged 4,096-entry ancestor guard.
Three test helpers now place future cases in fresh process-session directories;
historical artifacts, assertions and production limits remain intact. The exact
regression and required root checks pass with normal host filesystem access.

Both cells use fresh disposable authored markers, with a 16 MiB source
and an independently generated 4 MiB candidate. Candidate bytes are not copied
from the source. The fixture preparer refuses existing roots and observed path
aliases; these checks do not promise adversarial pathname exclusion. The exact
source, collector, auditor, worker and native plan require independent review
before execution.

| Cell | Declared action | Required observation |
| --- | --- | --- |
| Normal | Leave the candidate name absent, then continue the ordinary candidate operation. | A successful compound candidate result reaches the live-backend pause; only its matching release allows runtime continuation. |
| Candidate collision | At the reviewed pre-candidate pause, create the predeclared foreign marker at the candidate name once. | The exclusive-create error reaches the same post-result pause; actual error fields, failure outcome and the retained foreign marker are recorded. |

For each cell, nonwriting write-open probes should show baseline access before
the child, denied access while paused, and access after confirmed child exit.
A probe requests ordinary write access without creating, truncating, writing,
renaming or changing properties. A native sharing error 32 and CRT `EACCES`
without a native error code are recorded as distinct observations. The latter
is not relabeled as Win32 error 32. Denial alone is insufficient: the bounded
audit also requires the exact baseline/pause/postexit ordering and unchanged
source bindings; an absent source or unrelated failure does not satisfy it.
Bounded read snapshots and artifact inventories reconcile source identity,
length and hash across these observations. The source, partial artifacts and
foreign collision bytes must survive the attempt and audit.

### Actual finite outcomes — 2026-10-17

The passing declaration binds source
`92bfbd10eff50ec0353361990b808344240857b9` and worker SHA-256
`cb32947dfe6aa38eff3c8dacd931718355e10494e81f0dc4644bf7a9c3d684cb`.
Each cell ran once in a fresh fixture and attempt directory.

| Cell | Actual observation | Retained outcome |
| --- | --- | --- |
| Normal | 74 protocol events, 37 commands, successful candidate operation, explicit release, runtime result, backend drop and confirmed zero exit. | Unqualified runtime `Refused` at `TerminalExport`; the source and 4 MiB authored output match their expected names and bytes. |
| Candidate collision | 12 events, six commands, actual `AlreadyExists` / Windows error 80, explicit release and confirmed zero exit. | `Conflict` at `CandidateCreated`, no output publication and unchanged foreign candidate bytes. |

Both cells show baseline write-open access, CRT `EACCES` without a native error
while paused, and access after confirmed exit. All source snapshots match.
The normal held-candidate read was denied and remains recorded as an error;
its live bytes are not claimed observed. Its final output is independently
readable and matches the authored candidate. The collision marker was readable
at the pause and preserved afterward. Both audits reconcile the raw identity
bridges, exact release order and final artifacts. Every commitment, production
profile, RAW and importable-authority flag remains false.

Four two-cell declarations were retained in total. The first three each have
one failed normal attempt and one explicitly unstarted collision cell; their
failures are explained below. The fourth has two passing controls. No failed
attempt was overwritten, relabeled as passing or retried under the same identity.

Verification includes independent source, exact-plan and retained-evidence review:

- All 115 combined Python controls pass on Windows. The 54 changed probe/audit
  controls also pass on Ubuntu WSL; earlier complete portable runs remain retained.
- Eleven pure Rust diagnostic controls and the required root formatting, lint,
  test and release-build checks pass. The native worker remains ignored in CI.
- The independent reviewer recomputes both finite audits and separately reconciles
  captures, release/exit ordering, probes, identity pairs and actual artifacts.

The first declared normal attempt stopped during its baseline snapshot, before
launching a worker or requesting write access; its collision cell stayed unstarted.
CPython 3.14.7 on Windows exposes creation time through path-stat `ctime` and
change time through handle-stat `ctime`. The original equality check refused
those different fields. Both raw values remain retained. The revised observer
compares complete snapshots within each API and across probes, and compares
shared identity, mode, length, modification time and explicit birth time across
APIs under an exact interpreter profile. A changed property still refuses.
The failed declaration is retained separately from any freshly reviewed run.

The next normal attempt completed its worker protocol, but its audit rejected
a post-write liveness poll taken after the worker consumed its final command
and exited. That audit failure and its unstarted collision cell also remain
retained. The revised audit preserves the false poll and requires a matching
live pre-write observation, the exact downstream continuation and confirmed
exit. The candidate checkpoint and held-source probes still require actual
live observations; command delivery alone cannot substitute for them.

A third normal attempt also completed its worker protocol, then exposed a
signed-range assumption in the audit: this NTFS volume's valid 64-bit device
identifier exceeds the signed maximum. Its rejected audit and unstarted
collision cell remain retained. Device and inode observations require unsigned
64-bit validation; timestamp and other numeric fields keep their own checks.

The Python and SDK identity interfaces also expose different volume identifiers.
The revised test-only observer queries `GetFileInformationByHandle` on the same
existing Python read handle, retaining its legacy 32-bit volume serial and
64-bit file index alongside Python's full volume identifier. It neither truncates
an identifier nor changes the production SDK. Source, output and record snapshots
retain these pairs. The root comparison requires the same observed Python volume
as the source, and matches the SDK root's legacy serial against the captured
source pair. This is a finite local volume observation, not a universal conversion,
global uniqueness proof or imported authority.

The independent retained-evidence audit must reconcile the exact source and
worker bindings, request/plan, event sequence, explicit release, runtime result,
backend drop, process exit, hold observations and final artifacts. Matching
hashes establish observed byte equality, not continuous custody, current
ownership, complete filesystem properties or authenticated historical records.
Producer success and audit success are separate observations.

These controls qualify only the diagnostic's finite operation and lifetime
observations. A candidate-name collision is not the historical Windows 433
result, a backend ENOSPC rule, actual exhausted capacity or a reproduction of
#0174's namespace discrepancy. Even a normal protocol completion retains the
unqualified backend's refusal of positive commitment/profile admission. All
`committed`, production-profile, RAW-admission and importable-authority flags
remain false.

## Future historical-rule contrast remains unrun

The subsequent causal experiment remains the two-cell proposal in
[#0217](prepared-source-namespace-attribution.md#smallest-unresolved-causal-contrast):
one separately bound diagnostic cell with the historical persistent,
sector-unrestricted whole-volume write-error rule, and one matched cell with
the same preparation, timing and child-reopen sequence without the error rule.
It requires its own exact reviewed execution scope and is not executed by this
local observer increment.

That future plan must bind volume/root/case/unit and held-source observations
before fault activation and after child reopen; preserve explicit old/prepared
pathname lookup errors; observe the candidate result while holds remain live;
then observe after filter removal before release and again after exit. Failing
SDK substep and backend request offset/status attribution remain separate missing
observations. The post-result pause alone does not supply them.

Verified stopped-image copies may later supply direct record/index and pathname
views, retaining every query's output, error and status. Tools sharing an NTFS
library do not constitute independent filesystem decoders. The new diagnostic's
identities and timing effects must remain explicit; new results cannot be
attributed to the frozen #0174 executable. No guest, fault-rule execution,
VM-off, mount, repair, source-media work or storage-fault contrast is performed
by the method described here. No cause or fix is established, and all existing
preservation, custody, profile and RAW gates remain unchanged.
