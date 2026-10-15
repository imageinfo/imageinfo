# Two-name same-volume rename cycle (#0097)

Status: **proposed contract, version 1, 2026-10-15**. This handoff specifies
exactly two existing objects exchanging two names. The
[finite protocol and authored vectors](two-name-cycle.v1.json) and independent
[in-memory checker](../../scripts/check_rename_cycle.py) describe namespace
transitions; they perform no filesystem rename. No native cycle implementation,
supported storage profile, runtime command or media admission is supplied.

[#0093](conditional-replacement.md) remains an unsupported replacement primitive:
strong holds refused its attempted pathname replacement, and weak controls exposed
foreign-object substitution. [#0094](original-retention.md) retains original bytes
but supplies neither guarded rename nor restore admission. Neither result makes
the following proposed moves callable. Runtime work is a separate follow-up after
the missing native boundary below is admitted and reviewed.

## One bounded request

The sole proposed profile is `two-name-local-ntfs-v1`: Windows, local fixed NTFS,
one actual volume and one held parent directory, with exactly two distinct regular
single-link objects at two distinct ordinary component names `a` and `b`. The
profile is **unqualified**. These are symbolic slots, not a CLI syntax or arbitrary
paths imported from a record. Their actual components and parent/volume identities
must be resolved in a fresh explicit application plan.

Let `alpha` be the original object at `a`, and `beta` the original at `b`. The
requested final bindings are `a=beta`, `b=alpha`. Both originals remain the same
objects with the same default-stream bytes; there is no copy, replacement, deletion,
metadata edit or recompression. Byte equality alone cannot identify either object.
The plan exposes the temporary component, ordering, intermediate missing names,
collision policy, exact identities/properties, resource bounds and partial outcomes
before effects. An imported plan cannot assert its own authority or qualification.

Reject cross-volume or cross-directory requests, additional cycle members, same
object aliases, hard links, symlinks/reparse points, directories, alternate streams
as names, case-only/equivalent components, unresolved case rules, and unsupported
properties/configurations. No basename-based RAW/XMP pairing is inferred. A future
caller must resolve any pairing explicitly; this contract handles only these two
selected objects. Broader paired operations remain [WS-017/018](README.md).

## Holds and checks required before the first move

Capture actual simultaneously held volume/file identities for both originals and
the parent. Hold both objects and relevant ancestor/name bindings continuously
through all moves and final inspection. Guards must exclude competing default-
stream modification and source-name substitution, including previously opened
writers and rename/delete handles. The own-process rename must work through these
guards without releasing them, downgrading sharing, reopening an unbound pathname,
or introducing a custody gap. A successful identity check followed by an
unconditional pathname rename does not meet this requirement.

Prove the actual parent/ancestor bindings remain the declared ones, and the actual
objects remain on the declared volume. A parent handle alone is not proof of every
ancestor or child entry's exclusion. Hold each original independently even while
its initial name is absent. A changed, missing, inaccessible or unprovable binding
stops the sequence; no replan or fallback runs inside the cycle.

For these existing originals, relevant properties must be explicitly inventoried
and preserved or refused under WS-009/010/011: security/ownership, named streams,
attributes, timestamps and link topology as applicable. Access-time effects of
inspection must be declared. Check through bound objects and current name bindings
before effects, before every move and at the final observation. Detected property
changes stop; no checkpoint refresh adopts an actor's baseline. Continuous
same-owner property exclusion is not asserted. OD-11's ordinary-new-output policy
is not automatic permission to change existing originals or omit their property
checks. The earlier marker workers' basic-property subset is insufficient to
qualify this complete existing-object policy.

No preservation or concurrency requirement for existing originals is relaxed:
if the selected profile cannot meet the applicable requirement, admission refuses.
The finite model assumes these guards and does not demonstrate their availability.

## Temporary name and three proposed moves

Select exactly one fresh ordinary temporary component `temp` in the same parent,
distinct under actual filesystem comparison from `a` and `b`. Bound its spelling
and finite selection effort in the reviewed plan. An occupied selection refuses;
do not remove it, adopt it, or silently choose another during application. No
placeholder file is created: `temp` is an initially absent name, not a third
original object or an owned staging object. Its absence check is advisory until
the no-replace move itself linearizes.

Each proposed move requires an operation bound to the held expected source object
and a conditional **destination absent** result. It may move that object once or
return a proven no-effect result. A foreign destination wins; it is never replaced.
The source binding and no-replace condition must hold at the operation boundary,
not merely during an earlier check. Validate the resulting map before proceeding.

| Prefix | Proposed move | `a` | `b` | `temp` |
| --- | --- | --- | --- | --- |
| 0 | None | `alpha` | `beta` | absent |
| 1 | Held `alpha`: `a` to absent `temp` | absent | `beta` | `alpha` |
| 2 | Held `beta`: `b` to absent `a` | `beta` | absent | `alpha` |
| 3 | Held `alpha`: `temp` to absent `b` | `beta` | `alpha` | absent |

This is three individually guarded moves, **not group atomicity**. Observers may
see either intermediate map and missing names. `temp=alpha` after the first move
does not confer cleanup authority: deleting it would delete an original object's
remaining name. A stale temporary pathname or matching bytes cannot authorize any
action. After the third move no temporary object remains to clean up.

An actor may create a foreign object in an empty slot after a move. Retain the
foreign winner and both originals wherever actually held/named, stop, and report
the observed map. Even if its bytes equal an original's, do not classify it as
that original. An actor attempting to displace a guarded occupied source must be
excluded; if a guard is broken or exclusion is uncertain, stop without another
move. Do not remove foreign entries to make the planned sequence finish.

## Outcomes and interruption

| Situation | Permitted report and next action |
| --- | --- |
| Unsupported profile, invalid plan or guard refusal before any move | Refused, worker no-effect; report any external changes separately. |
| Proven no-effect native failure/cancellation at prefix 0 | No worker rename effects; originals remain at their checked bindings. |
| Proven no-effect failure/cancellation after prefix 1 or 2 | Partial cycle with exact successful moves and observed bindings; remaining moves unattempted. |
| All three moves and final held-object/property checks succeed | Complete observed exchange only; no durable commit claim from this contract. |
| In-flight error, lost response/guard, failed post-check, process exit or VM-off | Recovery-required; last confirmed prefix is not necessarily the current map. No later move. |
| Foreign, missing or uninspectable state at any checkpoint | Conflict/refusal before effects, or partial/recovery-required after effects; preserve actual artifacts and identify uncertainty. |

The finite vectors use `no-effect`, `partial`, `complete-observed` and
`recovery-required` as specification labels; a runtime must map them truthfully to
[WS-022's result contract](../cli-walkthroughs/results.md). `applied_moves` counts
only confirmed calls. `unknown` marks uncertain bindings, not permission to guess
absence. No-effect describes the worker's moves and cannot erase an actor's effects.
Unknown outcomes are not converted to a proven failure by a returned error code.
Vector `bindings` are the last confirmed/observed symbolic map. After guard loss,
restart or a failed check, retaining that map does not assert the current namespace,
continuous custody, identity preservation or continuing guards. `uncertain=true`
forbids that inference. An unknown move explicitly replaces its affected source
and destination observations with `unknown`; it retains only the other slot's
last observation.

Cancellation is honored before the next move. Once a call may be in flight, retain
uncertainty until authoritative observation is possible; do not start compensating
moves. There is no retry, roll-forward, automatic rollback, replay, restore,
temporary-name removal or cleanup path. Restart inspection requires fresh guards
and trusted current identities and is read-only. An editable record, checksum,
last phase or same-byte file cannot restore live custody or grant repair authority.
Even an intact observed prefix after restart does not authorize its next move.

Any eventual recoverable runtime must retain a bounded private record of the exact
plan, original identities, confirmed prefixes and uncertain call, plus current
observations. Failure to prepare required recovery material stops before the first
move. Record loss after effects means uncertainty; records cannot attest their own
durability. This handoff invents no qualified namespace/receipt acknowledgement.
Persistence and fresh restart actions need separate qualification under WS-013–016
and WS-024. Future power-related tests stop at disposable VM-off under the
[accepted policy](power-test-policy.md), with cache limits stated honestly.

## Missing native mechanism and bounded follow-up

The concrete missing mechanism is an admitted, reviewed native operation that can
rename the **held exact source object** into an **absent destination component under
the held exact parent**, while retaining effective byte/object/name and ancestor
guards, and distinguish proven no-effect failure from ambiguous completion. It
must compose for all three steps, including the original `alpha` at its temporary
name. No such boundary is implemented or qualified by #0093/#0094. Do not relax
their guards or use unconditional `std::fs::rename` as a substitute.

Follow-up must first choose and review the narrow native boundary, its ownership,
flags, guard compatibility and error semantics. Then, using fresh authored markers
only, measure normal prefixes, every collision/source-substitution window, prior
handles, property changes, cancellation, ambiguous errors, process exit, bounded
storage errors and accepted VM-off cells. Prove both originals and foreign winners
remain accounted for. Native observation and persistence evidence are unrun here.
New SDK wrappers, dependencies, unsafe code or production policy require their own
ordinary review; this specification adds none.

| Requirement / acceptance | Contract coverage and remaining evidence |
| --- | --- |
| WS-001–003, WS-006; SAF-001/016 | Explicit bounded plan; current profile refusal; no imported permission. |
| WS-009–011; SAF-005–007 | Held identity/bytes/name/ancestor guards, no-replace, aliases and property refusal; actual mechanism/properties unrun. |
| WS-012–016, WS-023–024; SAF-008/009/015 | Originals remain objects, bounded private evidence, cancellation and uncertainty; no durability or restart-action qualification. |
| WS-017/018/022; SAF-010/011 | Exactly two objects/three moves, visible prefixes, foreign winners and partial reports; no group transaction or cross-volume workflow. |
| WS-015/019; SAF-012 | No compensating restore, arbitrary-record authority or cleanup; separate fresh-plan work. |

The finite checker establishes only model consistency and authored counterexamples
to unsafe simplifications. Proposed transitions are not native evidence; a passing
model does not enable a storage profile, production file operation or RAW mutation.
