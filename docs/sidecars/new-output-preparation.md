# Deferred new-name sidecar preparation

Ticket #0085 now has an internal operation/result boundary connecting explicit
new-name selection to the real shared `new_output::prepare` selector. This is a
partial preparation checkpoint. An actually admitted derivative from #0185 and
an actually supported storage sink remain required for positive publication.

The implementation is in
[`publication.rs`](../../src/sidecar_candidate/publication.rs). It accepts borrowed
live RAW/XMP selections, one destination date intent, explicit new-name creation
intent, the shared cancellation object and the retained resource owner. There is
no public apply command, plan importer, admission-token constructor or execution
method. A saved profile label, receipt or previous candidate cannot release work.

The real storage selector runs before source guards, candidate parsing, intent
validation, cancellation handling, collision probing or logical construction
charges. All current profiles return an explicit unsupported preflight result;
the deferred constructor does not run. This ordering intentionally means an
unsupported request with cancellation, invalid intent or an original-name target
still returns unsupported, rather than pretending those later checks ran.

After storage admission, the deferred builder would validate explicit new-name
intent and check cancellation before invoking the existing actual held-source
candidate mechanism. It retains a changed candidate internally as awaiting
independent derivative admission; it does not construct a storage backend,
transaction or installed output. Its lexical name checks do not establish native
name uniqueness or detect an existing target. A future admitted sink must perform
the actual guarded collision check.

The post-storage-admission no-op branch returns an internal unchanged result after
candidate preparation, without transaction/output creation, construction charges
or serialization. Both branches remain enclosed by the shared move-only prepared
wrapper, which currently has no extractor or executor. No reachable positive
no-op/publication execution is claimed by this checkpoint.

The result boundary uses shared `UnitResult`, `Failure`, `Status` and `Phase`
types. Its pure pre-effect mapping distinguishes unsupported/invalid intent,
collision, cancellation and failure. Every mapped result has no publication or
release possibility, no new charge, no retained transaction material and no
protocol-complete claim. This helper is restricted to pre-effect failures; it
must never summarize an attempted publication or uncertain sink operation.

Five authored controls in
[`tests.rs`](../../src/sidecar_candidate/publication/tests.rs) exercise the actual
sidecar-to-shared-selector path and the pure validation/result mapping. They use
nonexistent authored path selections and in-memory retained accounting. Constructor
instrumentation verifies zero calls, and an existing failed operation's charges
remain unchanged. Invalid intent, original-name selection and pre-requested cancel
are tested as unreachable behind selector refusal. Collision/cancel/no-op result
mapping is separately labeled pure evidence; it does not simulate a supported
profile or run the deferred branch. No native sink, VM or media experiment runs.

The original positive publication, installed binding, exact mapping/loss reporting,
property checks and functional success/failure matrix remain open. This increment
does not complete #0085 or qualify sidecar restart/fault behavior.
