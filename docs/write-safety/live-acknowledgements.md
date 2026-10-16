# Native phase-bound live acknowledgements

**#0168 implementation, 2026-10-16.** The internal production executor now retains
actual ordered live acknowledgements for the [new-output contract](new-output-contract.md).
The [runtime](publication-runtime.md) calls the reviewed Windows held-object
facade; records cannot advance this executor by claiming that an operation happened.
Public apply, exact storage-profile admission and independent format admission
remain separate. No current production entry point returns an admitted commitment.

Each successful native operation contributes its exact phase, target role and
complete immutable binding prefix to one live evidence value. That value binds
the protocol, profile and implementation revisions, operation and format identity,
fixed expected-absent output leaf and planned candidate length. Native bindings
contain actual volume/file identity, captured properties and exact content hash;
the held facade also checks complete bytes. Root facts additionally bind the
actual containing-directory snapshot from its held writable handle. No pathname
reopen supplies publication or parent-flush identity.

The complete predicate requires all 36 ordered native/caller phases, each with
its exact target role and complete expected binding count/prefix. Candidate and
installed-file flushes are separate acknowledgements on the same held object;
each intervening root flush is distinct. No earlier file or directory operation
substitutes for a later one. Evidence is retained in caller memory before guard
release, including the successful prefix when an operation fails. Source-reader
chunking is bounded separately and does not manufacture persistence evidence.
Borrowed request identity fields are validated and the logical construction
budget is reserved before caller text is copied into live evidence. Invalid or
unfunded requests retain empty identity diagnostics. Custody snapshots preflight
the complete aggregate binding/record construction, including the original held
parent binding, using borrowed record views before copying record contents.

| Contract boundaries | Implemented live evidence |
| --- | --- |
| NO-01, NO-14 | Bounded request/budget/source preflight; actual private root, root and containing-parent flush; actual candidate binding and complete check. |
| NO-02, NO-03 | Candidate file/root, prepared file/root and intent file/root acknowledgements, each after exclusive creation and full checks. |
| NO-04, NO-05 | Independent caller release capture before the final prepublication check; permanent release/publication possibility before the corresponding calls. One held-object no-replace rename. |
| NO-06 | Fresh installed-byte/property/namespace check, installed-file flush, root flush and installed recheck. |
| NO-07, NO-08 | Independent exclusive observation and receipt creation, verification and exact original bindings. Receipt bytes contain only prior facts. |
| NO-09, NO-10 | Actual receipt-file flush then full check, root flush then full check, checked caller capture, final complete check and terminal export while guarded. |
| NO-11 through NO-13 | The separate [caller custody boundary](caller-custody.md) observes exact bindings; restart inspection and action execution do not follow from these live acknowledgements. |

Only a complete predicate plus an exact internal admission capability can report
`Committed`. The authored-test capability exists only under `cfg(test)` and binds
the exact backend profile/implementation revisions. Production execution remains
unqualified and reports completed internal execution as `Refused`. There is no
public boolean admission switch. The explicit caller no-op seam returns
`Unchanged` before constructing an executor request, reading a source, reserving
budget or creating a target; the storage layer does not infer a no-op from bytes.

Any reported error or lost response stops advancement. Once publication is
possible, errors, cancellation, property/namespace mismatch and lost terminal
response permanently yield `RecoveryRequired` for that attempt. Artifacts remain;
neither retry, cleanup nor publication replay occurs. A foreign winner is preserved.
Owner editing works after guard release; the source remains unchanged.

## Finite actual evidence

The Windows joined tests run the production executor and native adapter on
authored bytes. A positive test-admitted control completes all phases; a separate
unqualified native control still reports no admitted commitment. Actual collision,
readonly-property conflict, caller no-op and cancellation after every nonterminal
native operation are covered. Each of the 36 native/caller operation boundaries
also has injected reported-I/O-error and lost-response cases both before and
after the actual call, including every file and parent persistence operation.
The injected controller responses are not actual device/read/flush failures;
those remain #0174's separate guest work.

Each schedule closes the executor guards, independently reopens every actual
artifact name, and compares volume/file identities, complete bytes and captured
properties. It also compares source preservation, exact names and the root's
identity, retains foreign winners and records the known property actor's exact
change. Private evidence remains under `.local/work-wave-20261016e/168-*`.
Deterministic controls additionally reject missing, repeated, reordered,
wrong-target, incomplete-binding and foreign acknowledgements.

These are finite native observations on the current host, not the exact guest
profile, VM-off evidence or a hardware-survival claim. No media, VM, host crash,
power interruption, device campaign, target replacement or source ACL change is
performed. Historical research receipts are unchanged. The
[best-effort VM-off-only policy](power-test-policy.md) remains in force.
