# Current compatibility coverage audit (#0141)

The audit reconciles all six original LG clauses and all twelve original inventory
GAP clauses to existing evidence and named residual owners. **All eighteen complete
clauses remain unmet.** Finite delivered cells remain usable at their documented
boundaries; this audit establishes neither first-RAW acceptance nor full/drop-in
ExifTool parity. It adds no implementation, media observation or reference run.

The [merged ledger](coverage/audit.v1.json) retains the exact original requirements,
the independently authored [LG slice](coverage/lg-evidence.v1.json) and
[GAP/current-native slice](coverage/gap-evidence.v1.json), their SHA-256 bindings,
scoped evidence kinds, stable residual IDs and reverse owner trace. Its
[schema](coverage/audit.schema.v1.json) describes the stored audit shape. The
[native surface companion](native-surface-evidence.md) explains the
fixed inventory and current operation boundaries.

## Coverage and counting

| Trace view | Retained denominator | Meaning |
| --- | --- | --- |
| Original LG requirements | LG-001–006 | Exact unresolved and required-closure text; 58 residual cells |
| Original inventory gaps | GAP-001–012 | Exact complete inventory objects; 28 residual cells |
| MAP families | 32 | Exact full family requirements, finite evidence and full-family residuals |
| API method roles | 39 | Pinned headings, including static headings, and required native roles |
| Token/option inventory | 32 MAP / 39 method / 87 CLI / 102 API-option / 12 setter-option entries | Exact identifiers and original inventory records; not overload/value/ordering qualification |
| Current native cells | 14 | Nine command forms plus five API/admission boundaries; finite runtime and refusal distinctions retained |

There are **86 residual cells attached to the eighteen original clauses**. Across
the original clauses and all overlapping trace views, the ledger records **444
residual records**. A record can describe the same unmet capability from a family,
method, token and original-clause perspective. Their sum is not a count of unique
capabilities, remaining tickets, implementation steps or required new cards.

| Residual classification | Records across overlapping views | Next-step meaning |
| --- | ---: | --- |
| Finite current work | 23 | Existing named engineering/evidence scope; ordinary authorization is retained |
| Scope definition | 378 | Exact missing form, behavior, resource or assertion still needs bounded scope |
| Permission/guarantee decision | 3 | A concrete authority or promised-guarantee choice remains with its owner |
| Conditional alternative | 3 | Unselected mutually exclusive branch; no implementation is silently selected |
| Unknown planner scope | 23 | Missing actual effects/identity/recovery contract; no universal executable plan is invented |
| Eventual #0012 | 14 | Broader deferred parity retains its original owner |

Every residual lists explicit owner ticket numbers. `reverseOwners` maps each
owner back to stable residual IDs across every view. #0015 continues to own unmet
RAW compatibility; #0012 retains eventual broader parity. Completed finite
qualification cards are evidence sources, not proof that their parent requirement
is complete. The existing [delivery matrix](delivery-matrix.md),
[planning map](../remaining-work.md) and original source contracts retain their
full acceptance requirements.

## Delivered cells and retained limits

LG-001 retains exhaustive grammar, aliases, API options and ordering obligations
after finite read/extract/preview/pair/session qualification. LG-002 distinguishes
the five actual result profiles and inert MIG-001–012 translation from unavailable
legacy serializers, import execution and templates. LG-003 retains the explicitly
selected trusted-code/pure-data boundaries and unselected alternatives. LG-004
keeps actual per-operation WS-002 ownership, including unknown planner profiles.
LG-005 retains lookup, repair, unusual flags and catalog obligations. LG-006 keeps
actual API/process/terminal/resource evidence separate from synthetic contracts,
future runtime work and required human review. The slice records the individual
clauses, evidence scopes and owners for each of these statements.

The negative delivery from [#0140](native-session-handles.md) remains explicit:
seven Windows cases completed naturally; NULL stdin was watchdog-censored with
no natural completion/status claim. Invalid and previously closed stdin values
produced EOF observations, while valid write-only stdin exercised `INPUT_IO`.
Best-effort standard diagnostics and platform observations do not create a
portable failing-handle or authoritative-delivery guarantee. The LG/GAP slices
retain the MUSL read-only-stdout counterexample: natural status 0 with no captured
stdout or stderr, no observed `OUTPUT_INCOMPLETE` and no established delivery.
That observation does not qualify hosted GNU Linux or macOS. The slices
also retain #0149's failed strict resource audit; passing native outcomes never
erase that separate failure or establish a resource policy.

No contract/model/refusal-only result establishes a positive implementation.
No passing finite read cell establishes RAW writer admission, a storage profile,
saved-plan execution, legacy API ABI equivalence or general semantic parity.
This audit requests no new product adoption gate for unchanged authorized work.

## Reproduce the audit

Run `python scripts/check_compatibility_coverage.py --self-test`. With the
repository-pinned `jsonschema==4.26.0` installed, add `--schema` to self-validate
and apply the Draft 2020-12 schema. The checker reads repository documentation and
JSON only; it never invokes a reference executable, implementation or media parser.

The checker verifies exact original clause copies, slice/evidence hashes, complete
inventory identities and native manifest, owner/reverse trace and all residual
counts. Fifteen in-memory controls reject omitted/duplicate clauses, lost owners
or residuals, false acceptance/parity, incorrect counts, missing reverse trace,
stale slice/evidence bindings, option omission, native expansion and promotion of
the censored standard-handle case or MUSL no-delivery observation. These are documentation integrity controls,
not additional runtime qualification. Independent requirement review is separate
from the author's checker execution.
