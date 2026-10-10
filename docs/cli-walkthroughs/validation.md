# CLI walkthrough validation and handoff

Reviewed **2026-10-10**, proposal revision `2026-10-10.1`, card **#0003**.
The deliverable is a language-agnostic CLI recommendation. No parser, menu,
filesystem backend, shell integration or screen-reader session was executed.

## Checks and limits

| Check | Result |
| --- | --- |
| User journeys | Eight synthetic walkthroughs, including all six requested workflows |
| Refined interface rules | CW-001 through CW-014, unique |
| Command references | 64 command occurrences in fenced examples checked against the proposed tree and documented option spellings |
| Discovery tree | 17 groups and 55 group leaves; root help/version/interactive are separate |
| Status precedence | 28 synthetic cases passed |
| Invalid status-contract input | Three rejected: unknown file state, invalid-request plus successful unit, non-Boolean flag |
| Complete JSON examples | Three parsed; error envelope IDs/counts/completeness are consistent |
| CLI requirement coverage | CLI-001 through CLI-017 accounted for below |
| Source/contract review | AWS/shell references dated; grammar, metadata identity and safety flows reviewed together |
| Implementation/usability evidence | Zero runtime CLI runs and zero user study sessions |

Checks used local documentation tooling, not a chosen product language or test
framework. Public [status cases](status-cases.v1.json) are ordinary JSON with
`purpose: synthetic-cli-status-cases`. Flags omitted from a case mean false.
Cases with transport failure classify the outcome only; they do not imply that a
final summary was successfully delivered on the failed stream.

To reproduce the status check, classify each case's states/flags using the ordered
table in [results](results.md), then compare `expectedExit`. `artifactUncertain`
contributes recovery uncertainty; `artifactFailed` contributes an ordinary failure.
`incompleteGroup` contributes failure, becoming partial only when some unit also
succeeded. `emptySelection` fails unless `allowEmpty`. `warning` changes status only
with `warningsAsErrors` and no higher-precedence outcome. The other flags correspond
directly to table conditions. Reject unknown states, non-Boolean flags and impossible
invalid-whole-request/success combinations before classification.

For documentation validation, parse the proposed command tree, verify the command
paths and option spellings in fenced examples, parse complete JSON blocks, and
check links and unique requirement IDs. The deliberate error examples in WALK-008
are reviewed against their expected failures, not counted as accepted commands.
This does not test a parser or every combination of options; leaf signatures and
the negative table supply future implementation criteria.

## Requirements coverage

| Requirement | Evidence in this proposal | Still requires implementation evidence |
| --- | --- | --- |
| CLI-001 | CW-001/002, WALK-001/008: root/group/leaf equivalent help and no media effects | Exercise every published help node and spelling |
| CLI-002 | CW-001/004, WALK-008: full option names, errors, nearest help | Real parser/error corpus |
| CLI-003 | CW-008, WALK-002: breadcrumbs, Help/Back/Cancel, preview then explicit Apply | Interactive usability and keyboard testing |
| CLI-004 | CW-009, WALK-002/003: non-TTY error or ordinary noninteractive execution | Redirected/missing-terminal integrations |
| CLI-005 | Shared signatures/options and menu-exported request equivalence | One consistent command definition; no framework mandated |
| CLI-006 | CW-009, WALK-008: bounded, side-effect-free completion | Chosen-shell completion corpus |
| CLI-007 | CW-004/010, results: embedded occurrence-aware snapshot, typed/null/coverage states | Emitted payload validation against the metadata schema |
| CLI-008 | CW-010, WALK-003: stdout/stderr/binary separation | Broken-pipe and mixed-output tests |
| CLI-009 | CW-014, result fields/codes and 28 precedence cases | Versioned executable result schema and process exits |
| CLI-010 | CW-001/012/013, WALK-004/007: mutation preview, plan apply, recovery/restore/prune | Real no-effects and exact-effects assertions |
| CLI-011 | CW-004/012, WALK-004/005: capability/refusal, loss and privacy scope | Format/profile/mapping evidence |
| CLI-012 | WALK-004/007: stale plan, retained original, guarded recovery and resume | Writer/storage proofs on #0014 |
| CLI-013 | CW-005/011, WALK-003: manifests, input order, backpressure and resource bounds | Persistent framing under #0007; measured defaults under #0008 |
| CLI-014 | CW-001/005, WALK-004/008: literal paths, separator, quoting, escaped control characters | Cross-platform Unicode/newline/long-path corpus |
| CLI-015 | CW-003/005/006/007: configuration origins, selection, pairing and one-way sync | Real pairing/collision and policy tests |
| CLI-016 | WALK-001/005, profile/format help and explicit unsupported alternatives | Exact privacy catalogs and compatibility translations |
| CLI-017 | CW-008, WALK-002: 40-column/no-color/line-menu equivalents | Screen-reader, resize, localization and human usability review |

## Card acceptance

Novice inspection, expert batch JSON export, safe editing, GPS removal, sidecar
synchronization and recovery are WALK-001/003/004/005/006/007. WALK-002 focuses on
cascading menus; WALK-008 captures ordinary mistakes and safe discovery.

Resolved ambiguities are recorded as proposals: configuration profile naming,
snapshot-bound exact edits, deterministic selection/pairing, explicit sync direction,
recovery command names, no-op/backup meaning, and mixed-error exit precedence.
The mock output states what changed, what stayed outside the requested operation,
what remains uncertain, and what the user can do next.

The existing CLI baseline, documentation index, roadmap and inventory now link this
recommendation. Inventory revision `2026-10-10.5` keeps all 49 capabilities at
`specified`; its schema/reference/dependency checks and ten rejection cases passed.
Internal links and Git whitespace checks were included in handoff verification.

## Remaining work and ownership

**#0007 now supplies the [compatibility recommendation](../legacy-compatibility/README.md)**,
including a pure filter grammar, request/result schemas, request-file semantics and
persistent framing. #0015 retains the explicit remaining GAP-006/GAP-012 work,
including full saved-plan/session-output schemas, advanced mappings and runtime proofs. Advanced CSV/XML reports and alias
policy still need concrete compatibility cases; do not infer them from the tree.

**#0008** owns measured default limits and performance budgets. **#0010/#0013** own
lawful corpus admission and acquisition. **#0014** owns writer/storage and privacy
evidence. Actual CLI implementation, shell integration, accessibility and usability
validation follow a later explicitly authorized implementation decision. This card
does not declare those concerns solved or invent a new implementation framework.

Terry can review the proposed ergonomics now. Full ExifTool parity remains eventual;
the first user journeys continue to target EOS R5 full RAW, associated XMP and
stored previews. MIT remains locked; no upstream code, personal media or private
board data is part of this deliverable.
