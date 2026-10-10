# Safe mutation and recovery contract

Status: **proposal for review**, revision `2026-10-10.1`, card **#0006**.
Scope: EOS R5 full RAW metadata, associated XMP, stored previews, and related file
operations. No writer, platform profile, real-media mutation, or crash-safety claim
is implemented or verified by this document.

The [metadata contract](../metadata-model/README.md) defines values and edit intents.
The [fixture plan](../fixture-plan/README.md) defines evidence. This contract defines
the changes that may be made, what must remain intact, and the outcome when work
cannot finish safely.

Review the [state model](transaction-model.v1.json),
[synthetic scenarios](scenarios.v1.json), [RAW acceptance criteria](acceptance-scenarios.md),
[platform constraints](platform-constraints.md), and
[validation record](validation.md). These are acceptance artifacts, not a mandated
class hierarchy, event-sourcing system, database, or filesystem wrapper framework.
Use ordinary, idiomatic primitives in the eventual language and explain deliberate
departures near the code.

## Plan before effects

**WS-001 — Explicit application.** Preview does not change media, metadata targets,
backup retention, collection paths, or file timestamps. A requested saved-plan/report
artifact may be written after successful planning. `--apply` or the equivalent
explicit application action authorizes the resolved request; a snapshot, template,
or imported plan cannot authorize itself. Read access may have normal filesystem
access-time effects, which are distinct from content mutation.

**WS-002 — Bound inputs and targets.** A saved plan identifies its schema, model,
registry, conversion, capability and policy revisions; source content identities;
resolved object/path identities and relevant attributes; exact occurrences and
destinations; typed changes; implicit updates; expected pre/post conditions; and
backup/recovery policy. Include every mutable copy source. A plan digest identifies
bytes, not authenticity or write permission. Revalidate against trusted current
inputs and capability data; imported booleans cannot grant permission.

| Plan content | Required meaning |
| --- | --- |
| Read set | Original values/bytes needed by the operation, source identity and assumptions. |
| Write set | Exact existing occurrences or insertion locations, destinations and collision policy. |
| Changes | Input view, typed old/new values, explicit transformations/mappings, and any loss. |
| Preservation | Protected payloads, interpretation fields, unknown regions, reference dependencies and applicable properties. |
| Publication | Supported storage profile, expected destination state, required guards and persistence acknowledgements. |
| Recovery | Original/expected-absent state, owned artifacts, identities, retention and recovery conditions. |
| Grouping | Per-file units, dependencies, paired-file membership, ordering and partial-outcome behavior. |

Changing those bound inputs or rules invalidates the old plan. Replanning must
expose changed effects; it cannot silently broaden a previously reviewed write.
Plan/journal files are private data and must not execute shell commands, scripts,
remote fetches, or arbitrary configuration callbacks merely because they are read.

**WS-003 — Resolve the whole request.** Syntax errors, unknown operations, unresolved
ambiguity, conflicting target instructions, or unsafe global policy reject the
request before any target is changed. Default batch preflight also stops for known
per-file failures. With an explicit continue policy, preview may retain eligible
units alongside clearly refused units; application never treats refused files as
successful. Runtime failures after earlier commits produce partial outcomes.

## Metadata semantics

**WS-004 — Exact, unsurprising edits.** Resolve aliases to exact source occurrences
or explicit insertion locations. Display strings are not a fallback input format.
An absent value, explicit null, empty string, and delete request remain different.
Null is accepted only when the destination's definition supports it; otherwise refuse.

| Operation | Proposed semantics |
| --- | --- |
| Set scalar | Replace the named value in the selected raw/normalized view; validate its type/range/units and destination. |
| Create field/block | Separate from update; show required defaults, dependencies and newly allocated structure. Never imply creating sensor data. |
| Delete occurrence | Remove exactly the selected eligible occurrence; show coupled changes and residual duplicates. Protected/mandatory locations may refuse deletion. |
| Replace list | Replace the complete selected list with its explicit sequence/bag shape. |
| Append | Append the supplied entries, preserving order and multiplicity. Deduplication is a separate explicit operation. |
| Remove list entry | Select exact index/identity or explicitly request all matching values; do not guess which duplicate to remove. |
| Structure update | Set/delete an explicit field path; preserve siblings and unknown namespaces. Whole replacement and recursive merge must be named separately. |
| Language alternative | Update/delete the named language entry only. Updating `x-default` does not silently rewrite other languages. Whole-property deletion is explicit. |
| Copy/map | Read from the immutable source snapshot, choose a view and destination, and report unmapped/lossy fields. Exact raw copy and normalized transfer are different requests. |
| Date/location transform | State field set, units, calendar/duration/offset rules and assumptions. No host timezone, geotagging destination, or timestamp synchronization is silently invented. |

For several operations on one destination, require an explicit ordered sequence or
reject conflicting instructions. Evaluate copy sources and selection predicates
against the declared original read set; do not accidentally read partially edited
files. Freeze required values/resources before a dependent publication. If earlier
units intentionally change a shared source, later guards must match their proven
receipts while using the declared frozen values. Otherwise report a conflict.

**WS-005 — No-op means no rewrite.** If the exact requested effect is already
satisfied, leave bytes, modification time, and backup collection unchanged. Do not
reformat XMP, reduce a stored fraction, or move padding merely because a writer ran.
Equality is evaluated at the requested layer: a raw representation change is still
a change even if its normalized number is equal. No-op cannot bypass invalid intent
or a known unsupported/read-only tag operation, and does not prove general writability.

**WS-006 — Capability gate.** Enable writes only for the evidenced container/camera
variant, location, tag, operation, and relevant layout constraints. A global writable
tag name is insufficient. Unknown modes/layouts or unproven preservation refuse
embedded writes and may offer an explicit sidecar/new-output workflow. Never switch
destinations silently. Direct read-only CTMD fields and unproven preview replacement
remain refusals; a correct refusal is not implementation of the refused operation.

## Preserve the photograph

**WS-007 — Protect bytes and interpretation.** Preserve every protected encoded
sensor sample and required extra plane without decoding/recompressing it. Preserve
unselected previews, calibration/rendering data, CFA/channel/plane interpretation,
native dimensions/compression descriptors, maker notes, unknown blocks and trailers
according to a justified map.
Prove relocated references, lengths, counts and checksums are valid. Equal sensor
hashes alone do not prove that the file still has the same interpretation.

Unknown data may be retained byte-for-byte only when its placement/dependencies can
remain valid. If relocation could invalidate opaque pointers, refuse that layout.
Repair, canonicalization, stripping unknown content, and appearance-changing edits
are separate operations; they are never side effects of editing a caption.

**WS-008 — Validate before publication.** Generate a complete candidate in private
staging. Reread the intended values, validate container structure/references and
required properties, and compare all protected payloads with the frozen original.
Do not validate merely against the writer's cached intended values.

Two evidence layers apply: per-application checks of the actual candidate, and
release-enablement evidence using independent structure/payload tools and RAW readers
on the exact supported variants. Independent decoding belongs in testing; normal
operation must not depend on ExifTool or a separate RAW developer. Passing an external
sample test never replaces checks on the user's current file.

## Identity, concurrency, and storage

**WS-009 — Bind object identity through publication.** Serialize cooperating writers
by physical file identity and destination/parent identity, including path aliases
and not-yet-existing destinations. Acquire multi-file guards in a deterministic order.
Recheck content, relevant properties, parent/path bindings, copy sources and staging
identity before publication. No two units may unknowingly edit the same physical file.

A final hash check followed by rename is not a conditional compare-and-swap.
Advisory locks do not exclude unrelated writers. A profile must demonstrate the
exclusion/conditional-publication guarantee it claims across the operation, not
just at preflight. Where strict replacement cannot be guaranteed, refuse replacement
or use an explicitly selected new output with no-clobber publication. Do not silently
downgrade to an overwrite that can lose a concurrent external edit.

This is a conservative proposed initial policy. It does not assert that every
ordinary filesystem already provides the required guard. A later, weaker concurrency
mode would require a separate product decision and clearly different guarantees.

**WS-010 — Paths and aliases.** Bind resolved parents and object identities; reject
destination races, case-folding collisions, incompatible aliases and unexpected
reparse/symlink changes. Mutating through a symlink needs an explicit supported
policy; default refusal is preferable to editing an unintended referent. Existing
multi-link files refuse ordinary replacement until link-preserving semantics are
explicitly supported. Reading an alias does not grant mutation permission.

New outputs must be published conditionally on continued absence. A prior existence
check is not sufficient. Never use a cross-filesystem copy/delete fallback while
claiming an atomic rename. Unverified network, removable, cloud-synchronized or
unusual filesystems do not inherit a local storage profile's guarantees.

**WS-011 — Properties are part of the plan.** Existing-target edits preserve access
controls, ownership/mode and applicable user metadata/streams when the profile can
do so; otherwise refuse or offer an explicit output with a different stated policy.
Do not silently ignore ACL/attribute merge errors. Respect read-only flags rather
than clearing them as an editing shortcut.

The ordinary default updates filesystem modification time for a real content change.
Preserving that time is explicit. Capture dates and application metadata dates do
not change unless requested or required by a stated format rule. Creation time is
preserved where the profile promises it; access time, change time and object IDs
have platform semantics and are not universally preservable. Record relevant changes.

New staging/recovery artifacts use restrictive access. New sidecars/outputs default
to a documented private-owner policy unless a different policy is explicitly selected;
they must not silently expose private metadata through broader inherited permissions.
This deliberate default protects metadata that may contain owner/location information.
It does not prescribe a cross-platform ACL implementation.

## Original recovery and publication

**WS-012 — Original before replacement.** Before replacing an existing target,
establish a verified, recoverable original including its required properties.
Do not rely on a mutable hard link as the sole immutable recovery copy. New-target
creation records expected absence and retains any source inputs it needs; it has
no previous destination to back up.

Default success retains a user-restorable original. An explicit `--no-backup` policy
means discard the temporary original recovery copy only after successful finalization;
it does not disable recovery during the transaction. It cannot be inherited silently
from global configuration. Peak scratch space is still required. Failure retains
needed recovery material regardless of successful-cleanup policy.

**WS-013 — Record and flush the boundary.** Record transaction/plan identity, owned
paths, expected original/absence, candidate/recovery identities, relevant properties,
group membership, phase, and retention policy. Use integrity-checked, access-restricted
records with a supported persistence protocol. Guard acknowledgements are specific to
the current artifact and phase; an earlier flush is not a reusable Boolean.

Required candidate, recovery, and record flushes must succeed before publication.
Record publication intent before issuing the namespace operation. No new database,
event-sourcing framework, or exact journal format is selected here: a conventional
small record can satisfy the contract if its behavior is demonstrated.

**WS-014 — Publish one file at a time.** Publish the validated candidate using the
profile's guarded atomic visibility operation. Never expose a partially written
candidate under the final target name. Atomic visibility is a single-file namespace
property, not multi-file atomicity or proof of power-loss durability.

After publication, verify installed identity/content and required properties, obtain
required namespace/metadata persistence acknowledgements, and persist the outcome
receipt before reporting committed. A successful low-level call alone is insufficient.
On an ambiguous error, interruption, failed post-check or flush failure after the
publication boundary, report recovery-required and retain all relevant artifacts.

**WS-015 — Recover by evidence.** On restart, inspect owned records and actual
identities rather than trusting the last recorded phase alone. Do not automatically
restore a backup over a target that may contain a later external edit.

| Observed state under valid guards | Recovery action |
| --- | --- |
| Original identity/content/properties or expected absence is established | Record recovered-original. A retry needs fresh preflight; do not silently replay the mutation. |
| Installed target matches the owned candidate, recovery material is valid, and final checks/flushes can complete | Finish finalization without republishing and record committed. |
| Target is foreign, missing unexpectedly, mixed, uninspectable, or not attributable | Keep recovery-required; preserve artifacts and report the exact uncertainty. |
| Record/artifact identity or ownership is invalid | Refuse automated repair or cleanup; do not follow arbitrary paths from an untrusted record. |

Cleanup removes only verified owned staging artifacts no longer needed for recovery.
Do not delete by filename pattern alone. Cleanup failure after an otherwise committed
write is a separate reported warning/pending task; it does not justify reapplying
the edit. This also matters for privacy when an old copy remains.

**WS-016 — Cancellation.** Honor cooperative cancellation before publication with
no target publication. Once publication is in flight, complete the short safe
finalization or classify it recovery-required; do not interrupt into a knowingly
ambiguous rollback. A forced process kill or power loss is handled by recovery
inspection. A cancelled batch may already contain committed units and must say so.

## Groups and file operations

**WS-017 — Partial outcomes are first-class.** A batch or RAW/XMP pair is not a
filesystem transaction. Stage/validate a coordinated pair's candidates and recovery
requirements before its first publication where applicable, then publish units in
a declared order. If a later unit fails, report the committed/refused/unattempted
members and keep a recoverable group record. Do not claim the pair is synchronized.

Default behavior stops at the first runtime failure. Explicit continue can process
independent units, but must not proceed through a broken pair/dependency group.
Resume skips a committed unit only when its receipt and current identity still
match; it must not append list values twice. Changes after a receipt are conflicts.

**WS-018 — Rename and cross-volume moves.** Preview RAW and sidecar paths together,
including ambiguous pairing, case-only renames, collisions and any temporary names.
Same-volume rename still needs guarded identity and no-clobber semantics. A cross-
volume move is a separately supported copy/verify/publish/delete workflow, not an
atomic rename. Retain a verified destination and original recovery before a guarded
source removal; if removal cannot be made safe, leave both and report partial work.
Unsupported profiles refuse before changes. Rename cycles require an explicit,
recoverable plan; do not solve them through accidental overwrites.

**WS-019 — Restore and prune.** Restore is a new planned mutation: verify the backup,
bind the current destination and preserve its current version by default. A later
user edit is not permission to overwrite it using an old receipt. Prune selects
specific verified backup IDs/paths, requires explicit application, and refuses
original media or material needed by an unresolved transaction. Neither operation
follows arbitrary recovery paths or deletes unrelated files.

## Privacy, authenticity, and outcomes

**WS-020 — Removal has a stated scope.** A privacy profile names targeted fields,
all checked occurrences, protected rendering metadata, opaque/uninspectable regions,
sidecars and preview coverage. Report residual information, including retained
backups/recovery copies. A sidecar-only scrub never certifies its RAW source.
Do not offer an undifferentiated RAW metadata wipe that can remove decoding-critical
information. Logical deletion and removal of a visible tag are not secure erasure
from storage, snapshots, journals, other copies, or pixel content.

**WS-021 — Authenticity-bearing structures.** Detect known signed/provenance-bearing
structures and show the mutation's effect. Until a verified preservation or explicit
invalidation workflow exists for that structure, refuse the affected embedded write.
Do not claim a signature remains valid or silently remove it to make a write succeed.

**WS-022 — Report what happened.** Each unit reports target/source identity, requested
and actual effects, current observed state, recovery artifacts, outstanding checks,
and whether cleanup remains. Distinguish unchanged, refused, conflict, failed-before-
publish, cancelled-before-publish, committed, recovered-original and recovery-required.
Publication may have happened in the latter case; never summarize it as “no changes.”

The CLI's proposed exit codes remain: 0 for successful/unchanged work, 1 for total
operation or output/warning-policy failure, 2 for invalid whole-request preflight,
3 for partial batch failure,
4 for a stale/conflicting plan, 5 for post-publication verification/durability or
recovery uncertainty, and 130 for interruption. Per-file results are authoritative;
interrupt/partial results can include committed files. The
[CLI result contract](../cli-walkthroughs/results.md) now proposes mixed-error
precedence, giving recovery uncertainty priority without retrying committed effects.

**WS-023 — Keep recovery private and bounded.** Restrict staging, backups, records,
and diagnostic output appropriately; saved plans can contain sensitive metadata.
Check storage availability and enforce resource limits. A full disk, inability to
preserve required security properties, or failure to record recoverability stops
publication. No hidden upload, unreviewed extension, or broad cleanup operation is
part of recovery.

**WS-024 — Verify the backend, then enable it.** A supported profile must demonstrate
publication visibility, concurrency/collision guarantees, property handling, flush
semantics, interrupted-operation recovery and bounded errors on its declared
OS/filesystem/configuration. Real hardware/OS testing remains future evidence.
No profile is marked verified by this proposal, and no API/library is selected.
Document the storage assumptions: software cannot promise survival of lying hardware,
media failure or loss of every recovery copy.

## Handoff

This specifies the general policy portion of GAP-004 and GAP-009. Exact privacy
field catalogs, pairing/mapping details and runtime proof remain open on #0014,
write-validation, using #0003 for CLI pairing choices. #0013 supplies lawful fixtures and reference observations;
implementation work must demonstrate storage and writer profiles before enabling
replacement. The [CLI walkthroughs](../cli-walkthroughs/README.md) now make the
user-facing plan, apply, cancellation and recovery flows concrete; all remain
proposals. The [compatibility contract](../legacy-compatibility/README.md) adds
request/result schemas and integration recommendations; full saved-plan serialization
remains LG-004/#0015. #0008 is next for performance requirements.
