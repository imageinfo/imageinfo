# Explicit paired RAW/XMP rename caller (#0212)

Status: **implemented internal caller with public authored controls; restricted
operation-specific qualification reports remain private**, 2026-10-18. Required
local checks pass. Exact hosted verification is tracked on the ticket for the
published revision; per-operation admission and final frozen qualification remain
separate.

## Implemented method

The caller is scoped to one explicitly selected R5 RAW and XMP pair. Pairing is
explicit; filenames do not infer the association. It binds the immutable pair,
ordered member names and parents, each member's original identity and exact
authority, then retains actual same-object rename sessions from
[#0201](case-rename-plan.md). It composes them with the fixed two-unit executor
in [#0179](two-unit-runtime.md), preserving deterministic guard and member order.

The caller's preview exposes each member's exact ordinary or case-only name
plan, including any fresh temporary component. Per-member cancellation, failure
and uncertainty retain exact observed names and leave the other member unattempted
when required. The executor supports a distinct live observed-rename completion
through explicit adapter opt-in. This path does not produce `Committed`, a
`QualifiedReceipt`, or resume authority. The pair adapter does not imply group
atomicity, rollback, basename pairing, or temporary-original deletion.

## Execution and evidence status

The public authored campaign passed seven controls: the six card controls and a
final-step authority-revocation regression. In the sixth control, the actual
second move is followed by deliberate response loss at the planner boundary,
before the step is acknowledged; this is injected caller uncertainty, not an
observed ambiguous OS return. Terminal unknown history remains distinct from the
live observed names. A fresh independent SDK and journal audit passed.
Independent source review recorded a final GO. These authored controls exercise
the implementation and do not establish format or storage admission.
Operation-specific reports remain restricted and are not summarized here. In
particular, a first-member `RecoveryRequired` result alone would not complete the
positive acceptance.

Final evidence must independently inspect both original objects and any foreign
winner, including identities, default bytes, applicable properties and the exact
name map. The six controls are ordinary success, case-only success, missing or
ambiguous explicit pairing, late foreign or temporary collision, cancellation
after the first confirmed move, and uncertainty on the second move. See the
[card's readiness record](../planning/readiness-audit-2026-10-18.md) for the
retained acceptance scope.

Required local verification passes: 441 tests, with 11 existing ignored tests,
formatting, denied-warning Clippy, documentation checks and optimized build.
Hosted verification is tracked on the ticket for the exact published revision.
Authored evidence does not
establish format/storage admission, a qualified receipt, durable commitment,
restart authority, storage profile, or RAW admission. The exact production caller
and final frozen qualification remain separately owned by #0215.
