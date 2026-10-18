# Live two-name exchange caller (#0213)

Status: bounded internal caller implementation, 2026-10-18. Six authored native
controls pass against unchanged campaign source. Independent fresh retained-artifact
review passes all six cells and 23 journals. Final local tests, formatting,
Clippy, documentation checks and the release build pass; hosted CI is pending.
This is an unqualified marker caller;
it supplies no storage-profile, durable commitment or RAW operation admission.

## Exact caller and authority

[`exchange.rs`](../../src/storage/exchange.rs) owns the actual retained
[`path_cycle::Cycle`](../../src/storage/path_cycle.rs), using the
[#0202 held-marker method](held-marker-cycle.md). One held common parent contains
distinct single-link alpha and beta originals on the same volume. The explicit
three-name plan performs only alpha `a` to `temp`, beta `b` to `a`, then alpha
`temp` to `b`, with no replacement at each move. Both original guards remain in
the live session; a copied candidate or pathname reopen does not substitute for
either object.

[`ExchangePlan`](../../src/storage/exchange.rs) and
[`ExchangeBindings`](../../src/storage/exchange_authority.rs) bind the exact
operation identifier, ordered three paths, private record root,
ordered original identities and full supplied snapshot-property encodings.
The native cycle validates those original observations through retained holds.
Observations can be copied; matching observations alone confer no authority.
Constructor refusal does not return a live exchange and does not promise holds
that were never returned.

Explicit noncloneable, nonserializable `ExchangeAuthority` uses the existing
[`TrustedCurrentCaller`](../../src/storage/custody.rs) generation. Exchange
decisions and restart attestations share its four-construction ceiling and
revocation domain. Authorizing a new exchange or making a restart attestation
revokes the previous decision; revocation or caller drop invalidates outstanding
tokens. A refused fifth construction also revokes the preceding token. A new
caller cannot revive an old generation. The exchange seam does not alter the
meaning of existing restart actions or fabricate publication-shaped authority.

The adapter checks current authority before opening the cycle, at every advance,
and before and after each qualification hook. In particular, `BeforeCall` checks
authority after the held quiet interval and before the next native move. A hook
that revokes authority cannot then permit that call. Revocation stops the adapter
terminally while retaining the live cycle and its last observed prefix. Losing
authority after a native call retains the cycle's affected-slot uncertainty.

## Selected continuation and terminal results

This caller selects only `GuardHeldQuiet20Seconds`: both original and ancestor
guards remain held across two measured approximately twenty-second gaps before
reusing the vacated names. Normal completion therefore takes approximately forty
seconds. Cancellation, exact properties and the name map are rechecked before
the next move. No timestamp setter, property rebaseline or alternate move engine
is introduced by the adapter.

#0202's immediate-method creation-time counterexample remains contrary evidence.
The delayed controls neither qualify that immediate method nor establish general
NTFS tunnel expiry, quiet namespace history, arbitrary existing-name behavior,
persistence or a production profile. Relevant baseline access-time exclusions
and strict-property limits remain those of the underlying method.

`ExchangeReport` preserves the cycle's exact confirmed prefix, observed or unknown
name bindings, uncertainty and outcome, alongside shared `Failure` and
`Cancellation` handling. Uncertainty takes precedence as `Failure::Ambiguous`.
A terminal advance returns the retained report without another call or journal
change. There is no retry, saved-prefix continuation, import, rollback or automatic
cleanup. An original retained at `temp` and a foreign winner remain artifacts,
not deletion candidates.

`CompleteObserved` means the checked final map is beta at `a`, alpha at `b` and
temporary absent. It has no conversion to `Committed`, `QualifiedReceipt` or a
committed `UnitResult`. The three native calls are not claimed atomic or durable.
Private records and serialized results cannot reconstruct action authority.

## Finite evidence

The [caller controls](../../src/storage/exchange/tests.rs) include six passing
portable authority/report controls. They cover exact-field binding, revocation,
caller replacement/drop, construction bounds, invalid bindings, shared restart
revocation and uncertainty precedence. Separate existing custody controls pass.

The parent-run native matrix executes exactly these six authored marker cells:

| Control | Observed result |
| --- | --- |
| Complete exchange | Prefix 3; beta at `a`, alpha at `b`, temporary absent; both measured gaps at least twenty seconds. |
| Initially occupied temporary name | Open refuses; both originals and the foreign temporary object remain. No exchange report or returned holds are invented. |
| Foreign winner after first move | Prefix 1 partial; foreign object at `a`, beta at `b`, alpha at `temp`; no second move. |
| Original property/identity binding mismatch | A real preopened setter changes alpha's last-write time after prefix 1; the next checkpoint reports `RecoveryRequired` with uncertainty. Both original identities and bytes remain; the changed property is not reset. This native cell changes a property, not object identity. |
| Cancellation at confirmed prefix | Prefix 1 partial with `Failure::Cancelled`; alpha stays at `temp`, beta at `b`, `a` absent. |
| Uncertain in-flight response | The qualification hook deliberately discards the first move's response. Caller prefix remains 0, `a`/`temp` are unknown, beta remains known at `b`, and failure is ambiguous. The retained observer sees alpha at `temp`; this is injected response loss, not measured OS ambiguity. |

The controls retain original identity, bytes, strict observed properties, exact
actual name maps, foreign objects, bounded journals and source manifests.
Terminal cases also check that another advance preserves the report and journal.
An author-separated audit independently reconstructs the snapshot bindings and
checks all six exact maps, original identities/bytes/declared strict properties,
foreign objects, uncertainty, confirmed prefixes and all 23 journals. A separate
parent-run read-only SDK observer supplies fresh held observations matching that
audit, including absent slots and exact journal bytes. All 84 campaign source
entries match their before/after manifests.

The first observer attempt refused at its first held open because its own path
canonicalization introduced an unsupported verbatim prefix; it read no artifact.
An observer-only path correction then permitted the successful audit. SDK ancestry
and reparse restrictions remain unchanged, and the exchange campaign is not
replayed. The independently audited six-cell evidence binds the original campaign
source. Two subsequent source changes are separate: the independently approved
disabled-re-export lint annotation, and a test-only default fixture-path fix to
join directory components separately. Neither changes the exchange runtime or
relabels the original source freeze.

The initial full-suite attempt retained a fixture-path refusal before exchange
effects. After the test-only path correction the complete suite passed. The
release build passed before that fixture-only correction; final tests, Clippy,
formatting and documentation checks passed afterward. Operational paths,
snapshots and detailed results remain private.

This finite native evidence supplies no guest interruption, VM-off persistence,
durable caller custody, whole-profile qualification, imported restart authority,
source-media mutation or production CLI capability. Final frozen replacement
adapter qualification remains #0215; #0026 retains its positive replacement and
grouped-operation acceptance.
