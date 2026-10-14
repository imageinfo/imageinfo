# Write-safety validation and handoff

Validated **2026-10-10**, proposal revision `2026-10-10.1`, document structure
version 1. This is card **#0006**'s requirements deliverable. No imageinfo writer,
filesystem backend, RAW mutation or crash test ran.

## Artifact results

**2026-10-14 follow-up, #0041:** Terry explicitly accepted OD-11 option A. The
[decision record](practical-output-policy.md) maps the refinement to WS-009/010/011
and SAF-005/006/007: continuous default-stream byte/name guards, ordinary private-owner
editable output and property observations at declared boundaries. Other WS clauses,
the state/guard JSON model and its synthetic cases remain unchanged. A profile's
publication guard still must be effective for its declared guarantee; old synthetic
traces are not evidence of any actual OD-11 implementation. Internal links, normative
scope, JSON and diff checks pass; native/RAW/profile qualification remains pending.

The results table below is the historical #0006 baseline, not a new runtime result.

| Check | Result |
| --- | --- |
| Normative requirements | WS-001 through WS-024; unique and covered by acceptance criteria |
| State model | 15 states, 25 named guards, 32 unique state/event transitions; all references resolve |
| Valid synthetic traces | 21 reached their expected state and publication-possibility result |
| Invalid synthetic traces | 13 rejected as intended |
| Exact value semantics | 12 synthetic cases passed |
| Recovery decisions | 8 synthetic cases passed |
| Original retention/cleanup decisions | 4 synthetic cases passed |
| Partial-group classifications | 6 synthetic cases passed |
| Model regression checks | 4 unsafe model changes rejected |
| RAW acceptance criteria | 16 reviewed scenarios; WS and FXP references resolve; **runtime execution pending** |
| Real media and OS/power-loss experiments | 0 |
| Verified storage/writer profiles | 0 |

The 64 JSON cases and four model-regression checks were evaluated with a small
local documentation checker. It uses ordinary data traversal and exact rational
arithmetic; it selects no product language, state-machine library, harness or
runtime dependency. The public artifacts are data and language-independent rules.
`schemaVersion` versions these documents' structures; it does not refer to an
executable-plan JSON Schema. Neither file is an executable plan.

## Reproducing the checks

Load [the model](transaction-model.v1.json) and [cases](scenarios.v1.json) as JSON.
Reject duplicate state IDs or `(from, event)` entries; require every endpoint and
guard to resolve. Validate all WS references against the contract and FXP references
against [the case plan](../fixture-plan/case-plan.v1.json).

For each trace, start at `planned` with publication possibility false. For each
event, find the unique transition from the current state. Reject if it is absent
or any required guard is withheld. Otherwise advance and accumulate the logical OR
of `publicationPossible`. Compare accepted/rejected status, final state and cumulative
possibility with `expected`. A rejected trace has null state/possibility outputs;
it is a malformed contract sequence, not an observed failed filesystem operation.

All unwithheld guards in these cases are **hypothetically true at the current
event**. There is no real backend evidence hidden in the fixture data. In particular,
recovery/finalization needs a current publication guard; an earlier acknowledgement
cannot substitute for it. The `recoveryCases` decision table assumes those guards
hold; separate rejection traces cover their absence.

Evaluate value cases using the operations in WS-004/005. Append preserves duplicates;
remove-index affects one element; remove-all affects every equal element. Named
field/language updates retain siblings. Copy reads the original input map for all
assignments. Rational numeric equality uses exact fractions, whereas raw equality
compares the stored pair. Null remains a set value only for an eligible destination.

Evaluate recovery cases with WS-015: untrusted records or missing recovery evidence
remain uncertain. Proven original/expected absence yields recovered-original;
proven candidate plus final checks yields committed. Evaluate backup retention by
WS-012: retain before commit, retain by default afterward, discard only on requested
successful cleanup, otherwise report pending cleanup.

Evaluate the group examples as follows: recovery-required in any member prevents
group success; all committed/unchanged members form a complete group; a committed
member alongside failures yields partial; the illustrated wholly refused group is
not-applied. This small table does not define every CLI exit-code combination.

Independently reject four model regressions, even if the sample traces are changed:

- Publication readiness without verified original/absence recovery.
- Commit without namespace persistence acknowledgement.
- A no-op path that bypasses the capability gate.
- Beginning publication without a current input check.

Also require committed transitions to retain installed-output, property, receipt,
recovery-retention and current publication guards. States at/after publication must
not transition to ordinary before-publication failure/cancellation. The accepted
recovered-original case retains publication possibility: final recovery state does
not prove that a publication was never attempted or visible.

## Acceptance trace

| Card requirement | Delivered contract and criteria |
| --- | --- |
| Preview/apply and exact edits | WS-001–006; value cases; SAF-001/002/004 |
| Originals, atomic visibility and crash recovery | WS-008/012–016; transaction/recovery/retention cases; SAF-008/009/015 |
| Collisions, concurrency and properties | WS-009–011/024; platform ledger; SAF-005–007/016 |
| Partial batches and paired files | WS-003/017/018/022; group cases; SAF-010/011 |
| Sensor, calibration/CFA, maker notes, opaque data and previews | WS-006–008; SAF-003/004 |
| Restore/prune and bounded private artifacts | WS-019/023; SAF-008/012/015 |
| Privacy and signatures | WS-020/021; SAF-013/014 |
| Language-agnostic, greenfield design | Observable requirements only; no backend, internal architecture or dependencies selected |

The source ledger distinguishes observed OS documentation from imageinfo's proposed
policy. Existing CLI examples were checked against no-op, plan-file, backup,
cancellation and outcome rules. Documentation links, stable requirement references,
inventory consistency and Git whitespace were checked for the handoff.

## Remaining work

The contract is **for review**, not an accepted or implemented architecture. The
strict publication guard and private new-output permission default are explicit
product tradeoffs with rationale in the contract. Broader ExifTool parity and the
locked MIT decision remain unchanged.

Card #0003 now supplies [CLI walkthroughs](../cli-walkthroughs/README.md): concrete
pairing, plans, help/menu flows, proposed recovery commands and mixed-error status
precedence. These refine this safety proposal without claiming runtime verification.

**#0013** retains lawful full RAW corpus acquisition and reference experiments.
**#0014, write-validation**, retains storage/writer proof and exact privacy-profile
catalogs/mappings under GAP-004/GAP-009. These need admitted fixtures, independent
validators and a later authorized implementation decision. All 49 inventory
capabilities remain `specified`; no “correct refusal” is counted as a working edit.
