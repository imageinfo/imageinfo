# Cumulative marker supervisor admission

Card **#0049**, observed **2026-10-15**. The standalone research
[supervisor](../../experiments/0049-cumulative-budget/supervisor.py) wraps the unchanged
[#0046 receipt worker](namespace-receipt-marker.md) and its
[#0043 custody snapshots](windows-custody.md). It exercises actual Windows marker
construction, rather than only calculating proposed sizes. Production publication,
RAW admission, qualified persistence and automatic recovery remain disabled.

The caller supplies a finite unsigned 64-bit logical-byte limit and operation-count
limit. Each operation is charged **655,360 bytes** before its operation directory
or source worker is created. Checked addition rejects overflow and exceeding either
limit without updating either counter. Every later construction belongs to that
already charged fixed plan:

| Retained construction | Count | Maximum default-stream bytes each |
| --- | ---: | ---: |
| Authored marker source | 1 | 65,536 |
| Candidate, subsequently renamed to output | 1 | 65,536 |
| Prepared, intent, observation and receipt records | 4 | 65,536 |
| External immutable custody snapshots | 4 | 65,536 |

The receipt worker already preflights its 327,680-byte candidate/record total,
checks encoded record lengths and copies exact bounded lengths. Source preparation
authors exactly 65,536 bytes. Custody encoding refuses beyond 65,536 bytes before
exclusive record creation. The supervisor checks the actual compact custody request
length before launching each save and permits at most four saves. The complete
release-fence save precedes the original worker's publication continuation.
Only fixed receipt, short-source and short-receipt modes are exposed. Before root
creation the executable must match the explicit reviewed SHA-256 profile
`f86918a7fb3880cf8e09590fcc7d58155ef64d98c95cf9c2a6afc541c5b040fa`.
That hash is rechecked before every invocation. A different build requires review
and an explicit profile update; merely being stable does not qualify a worker.
This is trusted caller operation, without a concurrent adversary swapping the
executable between its check and launch; hashing does not provide that exclusion.

Charges are monotonic for the lifetime of this supervisor. Success, partial writes,
failed controls, cancellation and worker or supervisor exceptions never refund them.
Two incomplete operations therefore consume two full charges before a third can
be considered. The supervisor has no delete, prune, refund or ledger reload API.
The existing worker may remove its verified fresh prepublication candidate/records
on cancellation; that cleanup does not release the supervisor charge. Unknown and
unresolved files are never selected for deletion by this supervisor.

Every supervisor directory must be exclusively fresh, including after an earlier
process exits. A preexisting directory is refused even if empty. Before subsequent
operations, bounded inventory comparison rejects new entries or changed lengths;
unexpected directories, reparse entries, oversized files and excess entries refuse.
An unexpected worker/protocol or construction error poisons the instance, retains
its charge and artifacts, and blocks more work. Retained work is never adopted from
JSON or inferred to be safe to clear. Snapshot custody remains the caller's explicit
authority and does not acquire automatic freshness or recovery authority here.

The bound counts authored logical default-stream bytes and finite object counts
(at most three directories and ten files per admitted operation, plus the fresh
supervisor directory). It is not free-space measurement, disk reservation, physical
allocation accounting, filesystem metadata/ADS quota or an OS-enforced storage cap.
Protocol input/output is bounded in memory and is not written as an uncharged log.
Caller-produced audit reports are outside the retained worker plan. Same-owner
external mutation is not prevented by the supervisor inventory; a hostile actor
could add bytes before detection. The bound is on constructions this trusted caller
authorizes using the worker's existing handle guards and byte limits. A new process
must refuse old state; this is not a persistent cross-session budget or a general
concurrent multi-supervisor quota.

The [native evidence](cumulative-budget-native.json) records 15 passing cells,
including actual full receipt construction and four custody snapshots, exact and
one-byte-below admission, unsigned overflow, operation caps, two retained incomplete
operations, 65,535-byte short-source copying, malformed short receipt, cancellation,
foreign state preservation, unsupported-worker refusal before root creation, and a
labeled supervisor interruption after real source
creation. Successful full construction retained ten files and 144,777 logical bytes
under its full 655,360-byte charge. Injected `fail` controls and malformed producer
streams are labeled tests, not native disk-full or device-error observations;
[#0048](../../experiments/0048-native-storage-failures/README.md) owns native storage
errors. No guest interruption, physical-power or production profile gate follows.

Reproduce with the pinned research worker and retain all scratch privately:

```console
python experiments/0049-cumulative-budget/qualify.py --binary .local/0047-build/release/imageinfo-windows-publication-probe.exe --parent .local/0049-cumulative-budget --public docs/write-safety/cumulative-budget-native.json
python scripts/check_docs.py
git diff --check
```

The evidence binds the actual executable and relevant source hashes. Private marker
directories and captures remain ignored; the public JSON contains aggregate outcomes
and hashes, without private paths or source media. This implements a bounded resource
admission child of #0022; namespace, receipt, custody, persistence, independent RAW
admission and full profile requirements remain separately gated.
