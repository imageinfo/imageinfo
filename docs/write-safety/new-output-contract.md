# Bounded Windows new-output acknowledgement and restart contract

**#0165 engineering contract, 2026-10-16; revision `windows-new-output-contract-v1`.**
This specifies one implementable interpretation of the accepted [WS contract](README.md),
[OD-11 option A](practical-output-policy.md) and [best-effort power policy](power-test-policy.md).
It selects the already permitted **trusted explicit caller** recovery path. It does
not require automatic durable custody, encryption, receipt keys or a new Terry
approval. No requirement guarantee changes, production code, admitted profile,
writer, restart action or RAW permission are delivered here.

The [earlier receipt proposal](namespace-receipt-protocol.md) left qualified
acknowledgement and restart-survivor premises abstract. Here, acknowledgement means
completion of the exact ordered OS requests and guarded checks below under an
implemented, independently reviewed and evidenced profile. It does not mean a
promise that hardware will preserve every acknowledged write. A surviving receipt
does not retrospectively prove that its later flush or final check happened.

## Scope and configuration boundary

The initial topology retains the existing held-candidate, same-parent, no-clobber
sequence: one existing read-only source, one complete new candidate, one
expected-absent output leaf, four bounded records, and one fresh private
transaction/output directory under a bound parent. Candidate, output and records
are children of that directory. The source is never overwritten or deleted;
the directory is retained. Publication changes only the candidate's name. A
different topology, including a final output outside that directory, needs its
own bound parents, ordered namespace requests and profile evidence; it is not
implicitly covered. This bounds the first implementation, not #0022's complete
remaining acceptance.

| Profile field | Concrete initial candidate and admission boundary |
| --- | --- |
| OS and architecture | Windows 11 EnterpriseEval, `10.0.26300`, x86_64, standard user. Record the observed servicing revision, filesystem version and actual binary/toolchain when collecting the implementation's evidence; no evidence for unknown revisions is invented. |
| Filesystem and namespace | Local NTFS system volume, ordinary DOS namespace, held physical parent/ancestor bindings, same-volume and same-parent candidate-to-output rename, no replacement. Actual volume/object identities bind each operation. |
| Controller and image | The existing guest configuration: QEMU `q35,accel=kvm,smm=on`, guest SATA via `if=ide`, QCOW2 system image, explicit `cache=writeback`. Record the actual launcher and implementation revisions. |
| Cache and fault limits | Guest, host and device caching remain possible; host caches remain alive during VM-off tests. Available file/parent operations and bounded interruption observations support best-effort behavior only. Unknown physical cache behavior is disclosed, not a new hardware-test prerequisite. |
| Output policy | Fresh private, ordinary owner-editable output; no sealed OWNER RIGHTS descriptor, source ACL changes, copied source streams or silent broad inheritance. Owner property changes are trusted and checked at the declared boundaries. |
| Other configurations | Native Windows `10.0.26200` observations, the secondary USB/raw NTFS error fixture, WSL/Linux/macOS, other controller/cache combinations and production removable/network/cloud locations do not inherit this candidate's admission. Their distinct evidence remains usable only within its original scope. |

This is the concrete **candidate for implementation and later admission**, not a
claim that the existing evaluation guest or research binary is supported. Its
configuration comes from the [current profile ledger](profile-admission.md).
The [ordinary-output](ordinary-output.md), [persistence comparison](windows-persistence.md),
[checked-context](checked-receipt-context.md) and [process-custody](checked-receipt-custody.md)
observations inform this ordering but do not qualify a new production binary.
Profile admission must bind the actual implementation/configuration and cover
its finite required process, native-error and VM-off cells. It must not add
physical-power tests, dedicated hardware or a universal-survival proof.

## Concrete API predicates and ordered live completion

These are semantic predicates for the implementation and review, not public API
names, a new serialized format or editable admission switches. `B` is one
operation/unit binding: protocol/profile/implementation revisions; source, root,
candidate and parent volume/object identities; fixed output leaf and expected
absence; exact source/candidate bytes and lengths; declared property observations;
request/retention policy; and each actual owned record's identity and exact bytes.
Its components are captured as exclusive creation succeeds and are immutable once
captured. A record encodes only previously established bindings, never its own
future identity/content digest or future operations. The caller separately retains
that record's actual identity/bytes. Identity plus bytes is required; neither
substitutes for the other.

`G(B)` means the actual retained source/candidate default-stream byte/object/name
guards and bound parent/ancestor guards remain continuously valid through final
verification. Reacquisition after interruption is a new interval, not proof that
the earlier interval continued. Required preexisting writable handles/mappings
must make acquisition refuse. No hash-then-rename or pathname reopen/copy fallback
satisfies `G`.

`C(B, phase)` means a fresh full check of the phase's exact expected namespace,
physical identities, complete bytes/lengths, source preservation and declared
properties: owner/DACL policy, attributes and planned times, no unexpected reparse
point, alternate stream or link topology. Preflight, immediately before publication,
installed verification, after each receipt flush and final verification are
declared boundaries. Intermediate record checks also bind their actual objects.
An observed mismatch never updates the original baseline. An edit/reversion
between property observations is outside option A's continuous-exclusion promise.

`F(h, B, phase)` means the required synchronous file flush on the actual held
object returned success for this binding/revision at this phase. `P(d, B, phase)`
means the required flush on the actual held writable directory returned success
after the named namespace effects and preceding file flushes. Record each result
in the running protocol; a request label or on-disk `true` is not a result.
The implementation uses the existing reviewed Windows boundary and ordinary
`File::sync_all`/`FlushFileBuffers` semantics. Parent-flush refusal/error is an
unsupported or failed operation, never an optional call. No administrative volume
flush or privilege elevation is introduced.

Use buffered synchronous candidate/record handles, as in the original ordering;
do not silently interchange write-through or immediate-post-rename modes.
The [reviewed research wrapper](../../experiments/0032-windows-publication/src/native.rs)
creates files exclusively with `CREATE_NEW`, explicit private security,
`GENERIC_READ | GENERIC_WRITE | DELETE | READ_CONTROL` and `FILE_SHARE_READ`;
its held directory creation uses read/write access and read/write sharing without
delete sharing. The no-replacement rename uses `SetFileInformationByHandle`,
`FileRenameInfo`, zero flags and the validated absolute destination under the
continuously held full ancestry/root, with null `RootDirectory`. The separately
tested rooted form refused and supplies no supported directory-relative shortcut.
Production porting and its
complete handle/ancestor/access audit remain #0166, not an implicit promotion of
research unsafe code.

| ID | Required order and predicate established |
| --- | --- |
| NO-01 | Admit the implemented exact profile and independent format operation; resolve the explicit application request, bounds, expected absence and properties. Acquire source byte/object/name and full parent/ancestor guards before effects. Exclusively create/bind the private root; flush it and its held writable containing parent before staging. Exclusively create the candidate with its creator guard already effective, capture its actual identity, copy complete planned bytes and run `C(B, candidate)`. Extend `B` and the required guards monotonically as owned objects arise; complete all required bindings/guards before publication, never predict future identities. |
| NO-02 | `F(candidate, B, candidate)` then `P(root, B, candidate-created)`. These establish candidate acknowledgement only; they cannot acknowledge a later rename. |
| NO-03 | Exclusively create/verify the bounded prepared record, then flush its file and root. Repeat for the publication-intent record. Bind the actual held identities/bytes; both phase acknowledgements must precede release. |
| NO-04 | The trusted caller retains the complete exact prepublication bindings and records that release **may occur before** allowing continuation. Run `C(B, prepublication)` with `G(B)` still held. Once release begins or its outcome is uncertain, stop-before-release authority is permanently unavailable for that attempt. |
| NO-05 | Mark publication possible before invoking the single held-object no-replacement rename. A foreign winner is preserved. An ambiguous failure, lost response or interruption cannot undo the possible-publication fact. |
| NO-06 | On definite call success, run `C(B, installed)` under `G(B)`, then `F(installed, B, installed)`, then `P(root, B, output-installed)`. Recheck the installed name/object/properties. The conjunction of NO-01–06 is the **live namespace acknowledgement** for this exact output/name/revision. A raw directory-flush return alone is insufficient. |
| NO-07 | Exclusively create the diagnostic observation binding actual installed facts and completed prior phases, verify it, then flush its file and root. This is not a commitment receipt. |
| NO-08 | Exclusively create/verify the separate receipt, binding `B`, the three actual prior records and prior namespace acknowledgement facts. It contains no assertion about its own future flush or final checks. A partial, occupied or conflicting receipt refuses further advancement. |
| NO-09 | Flush the actual held receipt file; immediately run `C(B, receipt-file-flushed)`. Then flush the root for receipt creation and run `C(B, receipt-parent-flushed)`. Only afterward may the caller receive the checked receipt context. The conjunction through this boundary is the **live receipt acknowledgement**. No snapshot is rebased after a flush. |
| NO-10 | Run the final complete `C(B, final)` with all guards still held and all phase results bound to `B`; verify noncontradictory current caller history and retain required recovery material. Only the conjunction NO-01–10 permits a live `committed` result under this best-effort contract. Export the terminal result before guard release; account-owner edits after release can invalidate later matching checks. |

For a future admitted implementation, **committed** means this entire supported
protocol completed and the installed output matched while guarded. It is stronger
than rename success and narrower than universal persistence. A lost final response
does not authorize replay. Later owner edits are not silently overwritten to make
an old commitment match again. Existing research flags remain false regardless of
the number of successful calls in their retained captures.

Before publication can occur, failure/cancellation reports no publication attempted;
eligible explicit live cleanup may remove exact owned staging handles. Once it
can occur, any missing/failed/ambiguous acknowledgement, lost guard, malformed
record or failed check yields `recovery-required` with artifacts retained. A
detected conflict is terminal for that attempt: a later matching check cannot
resume it. Cleanup failure after justified commitment reports committed with
pending cleanup, without replaying the edit.

## Noncircular survivor rule and explicit caller authority

**NO-11 — Inspect first.** Restart inspection is read-only. Reacquire required
guards, parse bounded typed records, compare exact actual objects/bytes/properties
and report what remains. Surviving complete receipt bytes prove only that those
bytes survived and match the current objects. They prove neither that the original
worker reached NO-09/10 nor that an old caller context is current.

**NO-12 — Authority is an explicit current caller act.** A trusted caller may
request one named recovery action with independently retained exact `B` bindings,
actual original-worker/protocol provenance and relevant history. The caller takes
responsibility for the origin, completeness and current applicability of that
history, including any release or later work; the library must still validate the
action and all fresh objects itself. The original live process or an explicit
trusted user/controller can be that caller. The action is not inferred from
discovery, a receipt checksum, a phase string, a PID, a copied JSON history or the
mere fact that the same account can open a file. No transaction-file importer may
construct authority merely by parsing its own claims.

This is a caller trust boundary, not a hostile same-account security boundary.
An explicitly trusted caller can lie; integrity hashes cannot fix that. The caller
can retain bindings/history outside the transaction using its chosen ordinary
private record or application state. No cryptographic signature, secret store,
permanent service, hardware token or automatic antirollback mechanism is required.
After caller restart, reasserting authority is a fresh explicit act from retained
independent evidence, not automatic rehydration from the transaction. If the caller
cannot supply it, inspection remains available and effects refuse.

**NO-13 — Three distinct survivor decisions.** No receipt-for-the-receipt is needed:

| Independent caller evidence plus fresh guarded actual state | Decision |
| --- | --- |
| The caller retained the actual NO-10 terminal completion, exact checked receipt context, binding and complete noncontradictory history; all current artifacts still match. | Recognize the **previously completed** unit without republishing. Evidence of the terminal comes from the caller, not a field inside the receipt. This does not promise that it can be recognized after every restart. |
| There is no retained terminal proof, but the caller independently attributes the exact installed output and complete required prior records to this operation, attests the original worker has stopped, and explicitly requests finalization. No failed-check history is erased and no contradictory later work exists. | The survivor is **eligible for fresh finalization**, not evidence of old commitment. Reacquire guards and verify all bindings/properties; flush the held installed file then root; verify and flush the complete existing receipt then root; perform NO-09/10 full checks using a new finalization attempt identity. Commitment is established **now**, after these actual operations succeed. Never rename/publish again or rewrite the receipt to claim the old flush occurred. |
| The worker is proven stopped before any release; the caller independently retained exact unpublished owned bindings; expected output absence and all fresh required checks hold. | Establish the original expected-absent state. Only an explicitly requested unpublished prune may select the exact eligible owned handles; no mutation replay. |
| Output/record is missing unexpectedly, partial, changed, foreign, inaccessible or inconsistent; earlier checks failed; history/authority is missing or contradictory; or the profile cannot perform the required operations. | Retain `recovery-required` or refuse the requested effect. Preserve source, output, root and unresolved material. Matching current bytes cannot repair missing authority or a known failed check. |

The second row is a **new bounded completion attempt** under WS-015. It does not
fabricate lost earlier acknowledgements. Fresh installed-file/root flushing
establishes current namespace evidence; the held containing parent is also flushed
to cover the surviving root name. Fresh receipt-file/root flushing and final
checks establish current receipt/completion evidence. Required prior records must
be complete, consistent and independently attributable; a valid-looking receipt
cannot supply their missing provenance. If a receipt was never created and its
absence is consistent with independently retained actual history, explicit
finalization may exclusively create it only after freshly completing the prior
namespace and observation obligations in order. An unexpectedly missing or partial
previously bound receipt is a conflict, not permission to replace it.

The caller's exact finalization-attempt/old-operation relationship and actual
results are retained independently; no mutation of old historical facts is needed.
For a surviving receipt, the fresh attempt binds its exact old bytes as retained
evidence and the fresh acknowledgements as new evidence; its prior namespace facts
are not rewritten to assert that they describe the new attempt. The independently
retained completion context links both. This is a new completion of the same
installed unit, not a claim that the old receipt proves its own historical flushes.
If interrupted again, the same rules apply to the new attempt. Any IO failure or
failed fresh check retains uncertainty. Inspection or finalization never grants
deletion authority. Postcommit cleanup is a separate explicit action with a
current retention decision and per-handle validation; unresolved material, source,
output, root and foreign entries remain. Partial prune requires a fresh exact
remaining-artifact authorization; no stale-context retry or directory sweep.

## Minimum availability and unsupported requests

**NO-14 — Finite admission before effects.** Require a readable held source,
supported writable local NTFS destination/parent and private transaction location,
working required file/directory operations, and a checked total logical-byte budget
for the complete candidate, all records, caller-state artifacts actually created,
and retained failed work. Charge before construction; never refund a retained or
uncertain attempt merely because it failed. Each of the four transaction records
is bounded to 65,536 bytes. With a candidate of `S` bytes and at most four such
external caller snapshots, their logical construction bound is
`S + 8 * 65,536`; constructing a separate authored source adds its size. An existing
read-only original is not newly allocated scratch space.

This minimum promises no preallocated disk reserve, physical allocation quota,
free-space guarantee or global persistent budget. A reported free-space amount is
advisory and can change; full disk or inaccessible/failed IO must produce the
phase-appropriate refusal or retained uncertainty. Never free unresolved material
or delete originals to meet a budget. If an application cannot accept retention
within its finite admitted bound, refuse the next unit before effects. No arbitrary
minimum number of free gigabytes or new equipment requirement is selected.

Replacement, source deletion, cross-volume copy/delete, symlink/reparse traversal,
unsupported streams/properties, occupied-name restore, pairs/batches and automatic
restart effects remain outside this profile. #0177 owns the retained Linux/WSL
support boundary. Independent format admission remains mandatory; none of these
storage rules authorizes any current CR3 mutation or XMP publication.

## Exact normative interpretation and verification examples

The following are the complete normative deltas supplied by this contract.
They specialize accepted requirements; **no baseline WS/SAF text, scenario result,
research ledger status or old evidence is changed** by this document.

| Requirement/proposal premise | Concrete specialization; retained limit |
| --- | --- |
| WS-002/009/010/011; SAF-005/006/007 | `B`, `G` and `C` name byte/name guards, same-parent no-clobber topology and property boundaries. Ordinary owner editing and option A's between-check limit remain. No relaxation for existing-target replacement follows. |
| WS-013; candidate/prepared/intent acknowledgement | NO-01–04 require actual per-artifact file/root success in order, complete current bindings and a release-possible caller history before continuation. Earlier flushes are not reusable Booleans. |
| WS-014; abstract namespace/receipt acknowledgement | NO-05–10 supply the exact operations/conjunction under a later admitted best-effort profile. Neither single API success nor finite survival alone is commitment; physical-power survival is not promised or required. |
| WS-015; abstract proven receipt-survivor premise | NO-11–13 use independently retained actual terminal evidence for historical recognition, or fresh explicit finalization for present completion. Receipt survival alone never proves its later flush. Automatic durable custody is not required. |
| WS-016/019/022; SAF-008/009/015 | Terminal conflict/uncertainty, explicit per-object action, no replay/overwrite, stop-before-release prune and separate pending cleanup remain mandatory. |
| WS-023/024; SAF-016 | NO-14 names finite cumulative logical construction/retention policy and exact configuration admission. Implementation, native-error and VM-off evidence still must be supplied. Hardware survival and universal proof are not admission premises. |
| WS-006–008/020/021 and separate scopes | Format/unknown-data/sensor/authenticity/privacy and existing-target guarantees remain unchanged. A new-output contract cannot satisfy them by analogy. |

| Example | Required result when implemented/admitted |
| --- | --- |
| Rename succeeds; output/file/root checks and all later receipt/final obligations complete. | Live committed under this bounded best-effort profile. |
| Rename succeeds; parent flush fails, or installed timestamp conflicts. | Recovery-required; retain artifacts. A later matching timestamp does not resume the failed attempt. |
| Full receipt survives a VM-off, but caller has no independently retained bindings/history. | Read-only report; no commit recognition, finalization or prune authority. |
| Full receipt/output survive; exact trusted caller binding/history exists, original worker stopped, terminal result was lost and no contradictory failure exists. | Eligible only for explicit fresh finalization; report committed only after fresh ordered flushes and full checks succeed. |
| Same circumstances, but actual prior NO-10 terminal evidence was independently retained. | Fresh matching checks can recognize previous completion without republishing. |
| Output is absent after possible release; candidate survives. | Recovery-required. Absence is not stop-before-release evidence. |
| Same object has a later owner edit, receipt bytes differ, unexpected ADS/link exists or an original snapshot is stale. | Refuse action, retain artifacts; no rebaseline, rollback or overwrite. |
| Caller proves actual stop before release and explicitly selects exact owned unpublished files; one removal fails. | Preserve source/root; report partial prune. A fresh per-object authorization is required for any retry. |
| Physical power evidence is absent; required actual software/VM-off/profile evidence is otherwise complete. | Physical evidence is not a refusal/admission premise. |

Static review covers the predicates, all examples, source/API attribution, inherited
option A and power-policy limits, and each requirement mapping. This is a design
handoff with no new marker/media/VM execution, production dependency or native API.
There is no unresolved product choice necessary for this explicit-caller contract.
Automatic receipt-only restart recognition or stronger physical/hardware survival
would be a different guarantee, not an implied acceptance prerequisite. #0166–0176
retain implementation and actual evidence/admission work.

## Primary API basis

Microsoft documentation checked **2026-10-16**; mutable pages, no immutable revision
asserted. [CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew)
documents exclusive creation, share/access rules, directory handles and independent
buffering/write-through flags. [FILE_RENAME_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_rename_info)
documents the held-object rename parameters and refusal when replacement is disabled.
[FlushFileBuffers](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-flushfilebuffers)
documents file flush requests and write-access requirements; an all-files volume
flush requires administrative privileges. [File Caching](https://learn.microsoft.com/en-us/windows/win32/fileio/file-caching)
describes delayed cached writes and file metadata flushing. These sources motivate
the requests; they do not establish a universal directory-flush persistence theorem
or qualify this implementation. The exact conjunction and fresh-finalization rule
above are imageinfo's engineering interpretation of its accepted best-effort contract.
