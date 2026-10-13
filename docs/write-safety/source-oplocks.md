# Existing-source Windows oplock observations

**#0034**, observed **2026-10-13**, continues #0014/#0022 after Terry accepted
#0027 and #0033. [The isolated marker worker](../../experiments/0034-source-oplocks/README.md)
tests a possible existing-source guard without changing its ACL. **It fails the
complete source-property exclusion gate. No writer or storage profile is enabled.**

## Result and implication

The measured ordinary read-share-only handle and RH, RW and RWH oplocks all permit
new same-user timestamp, readonly-attribute, alternate-stream and hard-link changes
while the holder remains open. Those changes do not complete the oplock request or
emit a break notification. Operating through a late-created hard-link alias gives
the same timestamp/ADS counterexamples. Held default-stream bytes and identity
remain equal while these other properties change.

Thus neither an unbroken oplock nor equal bytes/object identity establishes an
unchanged source. A final property comparison detects these deliberate changes;
it cannot prevent a later change or turn detection into atomic exclusion through
publication. #0033's fresh-artifact policy does not transfer to an already exposed
source without altering the source's existing property policy.

Some security/data/name actors do cause a break requiring acknowledgment and wait
until the holder closes. The worker records that wait, then releases the holder;
those actors may subsequently succeed. Their post-release success is explicitly
separate from acting during the held interval. No explicit break acknowledgment,
publication, source ACL sealing, privileged repair or cleanup is attempted.

## Measured cells

| Cell | Observation | Boundary |
| --- | --- | --- |
| Sharing alone | Reads/time/readonly/DACL/owner-access/ADS/new link succeed while held; default data/delete/rename refuse. | Content sharing does not exclude all properties. |
| RH | Compatible read succeeds. Time/readonly/ADS/new link act without a break. New DACL/data/delete/rename actors wait for an ACK-required break, then act after release. | The waiting cases do not rescue the property bypasses. |
| RW | Read/DACL/owner-access cause an ACK-required break and wait. Default data/delete/rename refuse with sharing. Time/readonly/ADS/new link bypass. | Reader interruption cost with no complete property exclusion. |
| RWH | Read/DACL/owner-access and default data/delete/rename cause an ACK-required break and wait. Time/readonly/ADS/new link bypass. | Compatible activity is more restricted; bypass cells remain. |
| Late hard-link alias | Creation succeeds; alias time/ADS change the held object without a break. Alias data/security behavior follows the measured held sharing/oplock boundaries. | A one-link initial check does not preserve link topology. |
| Preopened time/security | Time handle still acts without a break. RH preopened DACL mutation waits on a break; RW/RWH requests refuse with Windows error 300 when the DACL handle is already open. | A denied grant is recorded as refusal, never downgraded to a successful guard. |
| Holder process kill | Pending RH/RWH data actors proceed after termination; RW data actor already refuses. | Process-only lifetime observation, not OS crash or persistence. |
| Existing multilink/path/full-profile queries | Four multilink shapes, five unsafe names and complete-profile query refuse. | Refusals do not establish a supported backend. |

This worker does not implement atomic create-with-oplock. The ordinary open,
initial validation and request interval remains unqualified even before the actual
property bypasses. Other oplock types, directory oplocks, filters/providers,
privileged actors, extended attributes, mapped sections and hardware persistence
are not qualified by these cases. No conclusion about all possible Windows source
mechanisms is inferred from this bounded failure.

## Evidence and verification

The [75-case sanitized ledger](source-oplock-observations.json) contains 40 new-open
actors, 16 late-alias operations, six preopened actors, three kills, four multilink,
five path and one full-admission refusal. It audits **75 worker captures** and
**63 held observations**, including real property mismatches and break flags.
The final artifact manifest counts readable files/streams and separately retains
deliberately inaccessible marker paths; hard-link and ADS path counts are not
unique-object counts. No ACL repair is used to obtain a hash.
The audited final run hashes **1,137 readable artifacts/stream paths**, including
**12 alternate-stream paths**, and retains **15 inaccessible marker paths**.

Each marker is 64 KiB of authored bytes, ordinary local NTFS on Windows 11 x64 build
26200, with unchanged DOS namespace/current ordinary token. Native Rust 1.99.0 and
the pinned SDK execute the API sequence. Independent Python same-user actor
processes reuse the reviewed #0033 ABI declarations. Each process has a 60-second
watchdog; messages/controls use 15-second waits and a 32-byte control bound. The
one-second actor observation window and later held snapshot are observations, not
an OS I/O deadline or a race-free publication protocol. Normal access-time effects
of reading are separate from explicit holder property mutation.

[The SDK review](../../experiments/0034-source-oplocks/ffi-review.md) covers stable
overlapped storage, event/file ownership, cancellation/completion draining and
bounded reads. [Dependency admission](source-oplock-dependencies.json) reuses 14
exact registry packages and 15 notices; the only SDK feature addition is Ioctl.
Root dependency/lockfile and production unsafe policy are unchanged. No upstream
implementation, personal media or compiled distribution is imported.
[Platform CI](source-oplock-ci.json) records source gates and unsupported-platform
refusals separately from native Windows actor evidence.

## Remaining gates

#0014/#0022 retain complete immutable source/path/property handling, authenticated
restart custody/finalization/cleanup, operational output policy and actual Windows
OS-crash/namespace/receipt and hardware qualification. WS-009/010/011/013/014/015/
023/024 and applicable SAF criteria remain in force. #0027 is accepted refusal
evidence; current RAW opaque/checksum dependencies still deny mutation. #0023 cannot
enable a workflow from completed research-card lanes alone.

Primary API references and dated observations are in the linked SDK review.
Passing this qualification means its stated supported/refused/bypass observations
reproduce; the complete source guard and parent backend remain unqualified.
