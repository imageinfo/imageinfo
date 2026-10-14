# Bounded new-output namespace and receipt protocol

**#0045 proposal and portable model, 2026-10-14.** This is the finite protocol
contract for a single new authored marker output under accepted
[OD-11 option A](practical-output-policy.md). It separates publication visibility,
namespace persistence, diagnostic observations and a final outcome receipt.
**No storage profile is qualified and no worker can report committed from this
proposal.** #0046 separately owns backend implementation and qualification.

The later [#0046 marker implementation](namespace-receipt-marker.md) constructs
a separate unqualified observational receipt and inspects explicit caller-bound
artifacts. Its implemented schema and successful flush calls do not satisfy the
qualified receipt/profile premises below; this proposal and model remain the
contract for those separate obligations.

The existing [ordinary worker](ordinary-output.md),
[flush comparison](windows-persistence.md), [restart actions](windows-restart-actions.md)
and [caller-history snapshots](windows-custody.md) remain research. Their successful
API calls, flush returns, matching markers and editable records are observations.
They are not the qualified acknowledgements described below. This document changes
no native API, SDK feature, source ACL, privilege, key service or production gate.

## Scope and evidence terms

The unit has one retained read-only 65,536-byte authored source, one exclusively
created candidate, one expected-absent output name and one private transaction
root. Publication is the existing held-candidate, same-volume, no-replacement
namespace operation. Replacement, cross-volume moves, batches and actual RAW
mutation are outside this protocol. The source and root are always retained.

The proposed fixed transaction leaves are `source.marker`, `candidate.marker`
or `output.marker`, `prepared.record`, `intent.record`, the diagnostic
`observation.record`, and a separate proposed `receipt.record`. Candidate and
output cannot both be accepted as the same completed namespace. Each record is
bounded to 65,536 bytes with an exact typed schema; arbitrary paths, unknown or
duplicate fields, extra names, invalid links/streams and inconsistent bindings
refuse. The receipt leaf and schema are proposed, not implemented. These finite
logical bounds do not reserve space, account for filesystem allocation or qualify
cumulative retention limits.

At those proposed maxima, candidate plus four transaction records requires a
327,680-byte logical budget, excluding the retained original and the separate
custody directory. The current worker's 262,144-byte three-record budget cannot
be reused unchanged for the proposed receipt. #0046 must check its actual bounded
construction, while #0049 retains cumulative admission and retention accounting.

A **binding** identifies the operation and unit, root/source/candidate objects,
expected output absence/name, exact content revision and relevant observed
properties, protocol revision and exact storage-profile revision. It also binds
the applicable request mode and owned prior records. A **qualified acknowledgement**
is evidence for one such binding, one artifact and one phase under the profile's
declared failure model. It cannot be reused after a changed binding or substituted
for another phase. A request label, checksum or Boolean in an editable file is
not such evidence.

A profile must identify the actual OS/build, filesystem and storage stack/cache
assumptions, namespace operation, flush ordering, failure methods and restart
survivor interpretation it supports. Qualification is an independent admission
decision supported by implementation and fault evidence. The portable model uses
explicit hypothetical qualified evidence to test the logic; it supplies no OS
evidence and admits no profile.

## State and ordered obligations

These are model/proposal states. In particular, `Persisted` names a qualified
obligation, not an alias for the current worker's successful `sync_all` call.
Guards stay held through the final success check. Every relevant property check
uses the accepted option A boundary policy, without promising continuous exclusion
of same-owner time, DACL, link or alternate-stream changes.

| State reached | Required ordered work and evidence |
| --- | --- |
| `CandidateReady` | Bind current source and expected absence, acquire continuous source/candidate default-stream byte/object/name and ancestor guards, exclusively create/copy the complete candidate, and verify its identity/content and declared properties. Preflight and independent format admission remain prerequisites for a production implementation. |
| `CandidatePersisted` | Flush the held candidate and persist its creation in the parent according to the profile; obtain the candidate-phase acknowledgement for this content revision. |
| `PreparedPersisted` | Exclusively create a prepared record binding this unit, expected absence, owned objects, properties, policy and retention; flush its file then required parent namespace and obtain the prepared-phase acknowledgement. |
| `IntentPersisted` | Exclusively create and persist the publication-intent record with the same bindings. Recheck current source/candidate/records/parent properties and exact namespace. The trusted supervisor must completely save its external release fence before allowing the original worker past `before-namespace-call`. |
| `PublicationInFlight` | Mark publication as possible before invoking the held no-clobber operation. API success, failure with possible effects, cancellation, lost response and process/OS interruption cannot reset this fact. |
| `InstalledVerified` | With the same byte/name guards, establish the exact installed candidate under the output name and recheck source, records, parent and relevant properties. A foreign winner is never overwritten. |
| `InstalledFilePersisted` | Flush the held installed object for its current verified revision and obtain the installed-file-phase acknowledgement. Earlier candidate flush evidence cannot stand in for this phase. |
| `NamespaceAcknowledged` | Complete the profile's required namespace/metadata persistence sequence after installed verification and obtain its operation/name/phase-specific acknowledgement. A raw directory-flush return alone cannot advance this state. |
| `ObservationPersisted` | Exclusively create the diagnostic observation with actual installed facts and prior bindings; flush its file and required parent and obtain observation-phase evidence. This retained diagnostic record is still not a commitment receipt. |
| `ReceiptWritten` | Exclusively create the separate bounded receipt and verify its exact content/binding and prior namespace acknowledgement. Its own persistence is not yet established. No overwrite or record conversion fallback is allowed. |
| `ReceiptPersisted` | Flush the receipt file and required parent, and obtain the receipt-phase acknowledgement for this exact record revision. |
| `FinalInstalledVerified` | Recheck the current source/output/record identities, content, relevant properties and exact namespace under guards after receipt persistence. |
| `ModelQualifiedCommitted` | Require every preceding phase acknowledgement for this unit/profile revision, the final guarded checks, trusted current caller provenance, retained recovery evidence and an admitted profile covering the stated failure model. Only this hypothetical conjunction justifies the model's committed result. |

The selected proposal puts installed checks before the installed-file flush. The
existing `ordinary-flush-after-rename` experiment deliberately uses a different
order and remains a comparison, not an interchangeable qualified implementation.
Write-through requests likewise do not eliminate any obligation by themselves.

Before publication becomes possible, cancellation or failure can report that no
publication was attempted. After it becomes possible, failure or uncertainty in
any remaining obligation gives **recovery-required**, with artifacts retained.
It cannot become an ordinary prepublication failure simply because output is
currently absent. A successful visibility call never skips later phases.

## Receipt facts and noncircular completion

The proposed receipt contains a fixed purpose/version, operation/unit and protocol/
profile revision, expected-absence and installed-object/content/property bindings,
prior prepared/intent/observation bindings, namespace acknowledgement reference
and retention/outcome facts established **before receipt creation**. Integrity
checks detect accidental inconsistency; they do not authenticate a caller or
provide freshness.

The receipt cannot record that its own future final file/parent flush has already
succeeded. Live completion depends on the subsequent receipt-phase acknowledgement
held by the running protocol and its final checks. On restart, interpreting a
surviving complete receipt as evidence of completion requires a separately proven
profile survivor/ordering rule, fresh actual bindings and trusted current history.
A field such as `flushed: true`, a matching receipt body or a receipt-file flush
without the required parent acknowledgement is insufficient. This requires no
recursive receipt for the receipt and selects no database or journal framework.

Before that full predicate is met, the outcomes remain observation-only or
recovery-required even when every file looks correct. With no admitted profile,
the existing worker's `namespaceAcknowledged`, `committed`, `repairAllowed` and
`productionPublicationAllowed` stay false. A hypothetical model commit cannot
change them. Cleanup failure after a justified commit is separately reported as
committed with pending cleanup; it never causes the edit to be reapplied.

## Restart and cleanup decisions

Restart inspection is read-only until an explicit authorized action passes fresh
checks. It compares actual identities/content/properties and exact names with
independently retained current caller bindings, rather than trusting the latest
phase string or loading authority from the editable transaction itself.

| Fresh evidence and caller history | Decision and permitted next work |
| --- | --- |
| Trusted current supervisor confirms original process exit before any publication release; expected absence and exact unpublished owned artifacts pass fresh guards/checks. | `OriginalEstablished`. Explicit caller-directed unpublished prune may select the exact verified owned handles, following the existing narrow action contract. It never authorizes replay. |
| Publication may have been released; output is absent, candidate is present, or only an older captured/fenced history remains. | `RecoveryRequired`. Absence does not establish nonrelease or restore prune authority. Preserve artifacts and report the missing evidence. |
| Actual output exactly matches the owned installed candidate; trusted current bindings and retained records are valid; an admitted profile can finish all outstanding final checks and phase acknowledgements without another publication. | `FinalizeWithoutRepublish` is a proposed authorized action. It must finish this protocol's missing obligations and receipt persistence; the classification itself is not committed. No current backend enables this action. |
| Complete receipt evidence satisfies the profile's proven restart survivor rule, actual guarded output/records/properties still match and trusted current provenance is established. | Recognize the qualified committed unit without republishing; allow only separately authorized eligible cleanup. A later output edit instead becomes a conflict, not rollback permission. |
| Unexpectedly missing required objects/prior records; partial, foreign, stale, changed, aliased, inaccessible or contradictory artifacts; no profile; or uncertain caller authority/freshness. | `RecoveryRequired`, or refuse the requested action before effects. Retain artifacts, source and root; do not invent a valid prefix or repair ACLs. |

An expected-absent receipt at an unfinished phase is not a committed receipt. Its
absence does not forbid a separately authorized finalization when independent
trusted bindings and qualified earlier-phase evidence establish every prerequisite;
that action must still exclusively create and qualify the receipt without
republishing. An unexpectedly missing previously bound record is a conflict.

The external [custody snapshots](windows-custody.md) have at most four whole-history
snapshots, each bounded to 65,536 bytes, and enforce release-fence ordering in
their measured live controller. They accept same-byte snapshot replacement and
do not authenticate caller history or prove durable freshness/antirollback.
Missing final snapshots cannot prove that a release never occurred. Their file/
parent flush observations cannot supply a missing current authority or a qualified
receipt. #0044 owns their separate guest qualification; even passing that child
would not establish the full profile or arbitrary automatic recovery authority.

Cleanup is an explicit action on individually proven owned held objects no longer
needed for unresolved recovery. For unpublished prune, stop-before-release proof
is mandatory. For postcommit cleanup, qualified completion and retention policy
must establish eligibility first. Before each effect, revalidate the exact held
object, properties and namespace. Source, output, root, foreign entries and needed
recovery material remain. Do not follow paths from records, sweep patterns, recurse,
unlink by pathname fallback or overwrite a foreign receipt winner. Compatible
readers can defer removal. Partial cleanup, reinsertion or failed checks report
pending/uncertain work; a stale context cannot automatically select residual files.
Restore is a fresh planned mutation under WS-019, outside this new-output protocol.

## Finite fault and evidence matrix

The following **16 cells** define this proposal's finite checkpoint obligations.
They are a test plan, not completed native fault observations. For every persistence
operation named in a cell, exercise failure before the call, a reported error or
lost/ambiguous response, and interruption after the return before advancement.
Separately label injected control failures, process termination, OS crash and
physical power loss; none substitutes for another. Native storage errors and
storage/cache behavior need their own recorded profile evidence.

| Cell | Existing barrier or proposed boundary | Required safe outcome and evidence |
| --- | --- | --- |
| NR-01 | `source-guarded`; candidate copy/flush; `candidate-flushed` | Short/long copy or candidate file/parent persistence failure cannot release publication. Preserve source/root; only explicitly owned staging cleanup is eligible. |
| NR-02 | `prepared-record-flushed` | Partial/missing prepared record or its file/parent acknowledgement cannot advance readiness. No publication. |
| NR-03 | `intent-record-flushed` | Intent file/parent failure or wrong phase/binding blocks release. An intent record alone never proves the namespace operation occurred. |
| NR-04 | `before-property-check`; `before-namespace-call`; custody release-fence save | A mismatch before release refuses. Missing/incomplete fence blocks continuation. A released or uncertain history can never attest stopped-before-release. |
| NR-05 | Namespace call in flight; `published` | Test no-clobber collision, ambiguous errors and interruption around API return. Preserve any winner; possible publication remains recovery-required regardless of current output absence. |
| NR-06 | Installed identity/content/property check | Foreign, changed or inaccessible output, source or namespace keeps recovery-required. No rollback or overwrite. |
| NR-07 | `installed-file-flushed` | Installed-file failure/lost acknowledgement cannot be repaired logically by an earlier candidate flush or request-mode label. |
| NR-08 | `parent-flushed` | Raw successful parent flush, matching output or prior guest survival does not invent namespace acknowledgement. Require the exact qualified profile interpretation. |
| NR-09 | `observation-file-flushed` | Missing, torn, foreign or unbound diagnostic observation remains uncertainty; never convert it into a receipt. |
| NR-10 | `observation-parent-flushed`; `observed-record-flushed` | Observation file/parent acknowledgement and final checks remain distinct. Matching three-record context establishes only the existing observation contract. |
| NR-11 | Proposed receipt exclusive creation/write | Foreign winner, partial write or cancellation after publication preserves objects and recovery-required. Never replace observation or a prior receipt. |
| NR-12 | Proposed receipt-file flush | Lost/error response, incomplete bytes or wrong binding cannot establish receipt persistence. No self-asserted completion field. |
| NR-13 | Proposed receipt-parent acknowledgement | Receipt-file success alone cannot report committed. Interrupted restart requires the profile's proven survivor rule or remains recovery-required. |
| NR-14 | Proposed final guarded checks and success-report boundary | Late property/name/record conflict refuses commitment. A lost success response may later be recognized only with complete qualified evidence, never by reapplying the edit. |
| NR-15 | `restart-guarded`; `restart-before-record`; `restart-record-file-flushed`; `restart-record-parent-flushed` | Reacquire all guards. A stale two-record context refuses an extra observation; renewed exact context can validate it. Observation completion still does not qualify finalization/receipt. |
| NR-16 | `restart-before-remove`; `restart-file-removed`; proposed eligible postcommit cleanup | Remove only individually authorized held owned objects; test reader deferral, partial removal, extra/reinserted names, missing/foreign artifacts and stale retry. Retain source/root/output and unresolved material; report pending work. |

At NR-04 through NR-16, actor coverage includes wrong operation/profile/content
revision, lost guard, source/output byte or object/name substitution, foreign
winner, changed relevant property, extra name, stream/link anomaly and
missing/corrupt/inaccessible record. Byte/name guards must prevent the prohibited
effects; property observations follow option A's narrower checkpoint promise.
No test may silently turn a same-owner property observation into continuous
exclusion. Fault recovery also checks that an absent output after release does
not authorize prune and that a matching output without receipt evidence does not
authorize commit. These are finite required classes, not claims that every OS or
arbitrary actor schedule has been explored.

## Contract mapping and handoff boundary

| Requirement | Concrete obligation in this proposal |
| --- | --- |
| WS-013 | Exact phase/artifact/profile-bound candidate, prepared and intent evidence before publication; bounded typed records and explicit persistence ordering. |
| WS-014 | One held no-clobber publication, verified installed object, separate namespace and receipt acknowledgement, final guarded checks before committed. |
| WS-015 | Read-only actual-state inspection; trusted current provenance; qualified finalization without republishing only when all missing obligations can complete; uncertainty retained. |
| WS-019 | Explicit eligible handle-based prune, no unresolved/source/foreign deletion; restore remains a fresh separately planned operation. |
| OD-11-T05/T06 and SAF-009/015 | Distinct interruption/receipt cells, safe restart actions, truthful pending cleanup and no fabricated success. |

The accompanying [portable test-only model](../../experiments/0032-windows-publication/src/receipt_model.rs)
checks ordered transitions, evidence binding, missing-evidence refusal, restart
classification and unpublished-prune eligibility. It uses small identity/revision
tokens and Boolean guard/property/history premises; it does not implement record
parsing, a filesystem or the future receipt ABI. It models pending cleanup after
commit without deleting anything. Its
hypothetical qualified cases demonstrate logical sufficiency **under assumptions**;
they do not prove those assumptions. Existing native/guest evidence is linked above
with its original method, OS and cache limitations. No previous flush result or
surviving output is promoted into a new qualification claim here.

The model has nine focused tests, explores 23 reachable states across 28 distinct
offered event values (644 state/event applications), and checks all 384 combinations
in its explicitly finite restart-evidence table. Twelve single-event omissions,
eleven adjacent swaps and 26 interruption-prefix/scope combinations exercise the
order and uncertainty boundary. These are model inputs and assertions, not native
fault-run counts or a proof over arbitrary OS schedules.

Run the portable model with the pinned Rust toolchain and existing lockfile:

```console
cargo test --locked --manifest-path experiments/0032-windows-publication/Cargo.toml receipt_model::
```

The normal research test command also runs these tests. `#[cfg(test)]` excludes
the model from release workers; it adds no command or runtime receipt backend.

The [CI ledger](namespace-receipt-ci.json) records source `20c2eaf` passing on
Windows, Ubuntu and macOS: all nine model tests within 39 research tests per
platform, plus root contracts, formatting, lints, release builds and documentation
checks. These results verify the portable model and existing regression gates;
they do not supply OS persistence or storage-profile qualification.

An invalid abstract acknowledgement is rejected without changing model state.
That is not permission to retry a detected filesystem conflict: the backend must
map actual failed identity/property checks or corrupt/foreign required artifacts
to the terminal failure/uncertainty path. In particular, a failed installed or
final check becomes `RecoveryRequired`; a later matching check cannot resume it.

#0045 ends at the reviewable protocol/model and finite fault plan. #0046 starts
the separately scoped backend work. Full namespace/storage profile admission,
durable caller-history provenance/freshness, actual storage-error and resource
qualification, physical-power behavior and independent RAW admission remain open.
#0027's current real-camera mutation refusals and #0023/#0024 gates are unchanged.
