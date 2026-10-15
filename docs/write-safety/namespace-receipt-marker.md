# Windows marker receipt construction and inspection

**#0046 research, 2026-10-14.** This implements a bounded receipt-construction
sequence and read-only inspection in the existing
[#0032 marker worker](../../experiments/0032-windows-publication/README.md), following
the [#0045 namespace/receipt proposal](namespace-receipt-protocol.md).
It uses the accepted [OD-11 option A](practical-output-policy.md) boundary policy.
**No storage profile is qualified and no result reports committed.**

## Implemented boundary

`ordinary-receipt` operates on the existing exclusively created private marker
root and its authored 65,536-byte source. It retains the ordinary worker's
source/candidate default-stream byte/object/name guards, held no-replacement
publication and fixed namespace. It selects write-through candidate and record
handles and performs the existing installed-file, parent and diagnostic
observation-file/parent flush sequence. A successful Windows call remains an
observation rather than a qualified namespace acknowledgement.

After the ordinary observation exists, the new sequence exclusively creates
`receipt.record`. Its bounded typed payload binds the actual after-publication
context: root, source and installed candidate identities/properties, marker
digest, request mode and the three prepared/intent/observation records with their
individual identities and digests. This receipt describes prior observations;
it cannot assert that its own later file or parent flush has completed. Integrity
checks do not establish caller authority, freshness or durable storage behavior.

The receipt has fixed purpose `imageinfo-od11-receipt-v1`, protocol
`imageinfo-new-output-protocol-v1`, and profile label
`unqualified-windows-marker-v1`; the last label explicitly denotes an unqualified
experiment. The existing checksummed envelope holds its typed body. Unknown or
duplicate fields, invalid identities/digests, aliased objects, wrong stages and
wrong record sets refuse. Receipt and external-context input each have a 65,536-byte
bound. These research schemas do not establish the proposed production receipt ABI.
This minimal observation receipt has no qualified namespace acknowledgement or
phase-evidence claims. It therefore cannot satisfy #0045's final qualified outcome
receipt obligations, even when its own structure and actual bindings are valid.

The live worker holds the existing artifacts and fresh receipt through these
additional checkpoints:

| Barrier | Observation immediately preceding the barrier |
| --- | --- |
| `receipt-written` | Exclusive creation and bounded receipt write; receipt-file flush has not yet been called. |
| `receipt-file-flushed` | The held receipt-file flush returned successfully. |
| `receipt-parent-flushed` | The required parent flush call returned successfully after the receipt-file call. |
| `final-checked` | Fresh guarded source/output/record/property and exact-namespace checks passed. |

Failure, cancellation, a competing receipt name or a late conflict after
publication retains the source, output, root and unresolved records. There is no
receipt overwrite, record conversion, replay, rollback or postpublication cleanup.
The worker's `committed`, `namespaceAcknowledged`, `repairAllowed` and
`productionPublicationAllowed` values remain false even after every call and final
check succeeds. The proposed qualified acknowledgements in #0045 are additional
profile obligations, not aliases for these barrier names.

The logical preflight is **327,680 bytes**: one candidate plus four records, each
bounded to 65,536 bytes. It excludes the retained source and external caller
context. This bound is neither physical allocation accounting nor a reservation,
free-space guarantee, cumulative retention policy or hard native-I/O deadline.
The older ordinary modes retain their three-record scope and budget.

## External context and read-only inspection

The running supervisor captures the emitted typed `receiptContext` outside the
editable transaction. It binds the exact prior three-record after-publication
context and the actual receipt object's identity/properties and content digest.
Its fixed purpose is `imageinfo-od11-receipt-context-v1`.
It is a current caller-supplied binding, not an authenticated receipt or automatic
durable history service. Parsing arbitrary matching JSON cannot establish who
created it, whether it is current or whether a previous release occurred.

`ordinary-receipt-inspect` requires one explicit bounded context JSON line on
standard input before its control lines. It reacquires byte/name guards, validates
all fixed artifacts and their complete bindings and checks exact namespace and
ordinary-owner properties. At `receipt-inspect-guarded` these fresh checks have
passed. Inspection creates, removes and repairs nothing. Missing, stale, malformed,
foreign, changed, aliased or inaccessible required material refuses without
inventing a valid prefix. A matching receipt remains observation-only; no
finalization, prune or production admission follows.

Relevant properties are checks at the declared boundaries, as option A requires.
The new modes do not promise continuous exclusion of same-owner time, security,
stream or link changes. After the worker exits, ordinary owner editing remains
possible and can invalidate a later inspection. The legacy ordinary inspector and
restart actions do not accept an extra receipt as an implicitly authorized record.

## Verification and limits

The native observation profile is **Windows 11 Pro 10.0.26200**, local **NTFS**,
using the existing current-token private-marker policy. A passing finite matrix
on this host does not establish a universal Windows or storage-stack guarantee.
CI runner results and the separately retained guest profile remain distinct.

The [audited native ledger](namespace-receipt-native.json) records **93 cases**,
including **43 completed live receipt observations**, **75 unchanged receipt
inspection inventories** and **5,617 readable artifact paths hashed**, including
alternate streams. Three deliberately DACL-inaccessible paths remain retained
without permission repair. The matrix includes 21 cancellation/failure/termination
cases at seven barriers, competing receipt and extra-name actors, held
source/output/receipt byte/name actors, root rename refusal, malformed or stale
contexts, changed records and property conflicts.

Three additional inspection cases change a source, output or receipt timestamp
at the guarded inspection barrier. They establish inspector refusal after the
explicit actor change; their inventories match apart from that actor's timestamp.
They are not counted among the 75 unchanged inventories. This measures option A's
property checkpoint behavior without claiming continuous property exclusion.
The [reproduction commands](../../experiments/0046-namespace-receipt/README.md)
bind the exact native worker and retained private evidence. The release-fence
history precedes publication continuation in the supervised runs. These current
caller observations do not authenticate durable history or qualify storage.

Six new portable receipt/context tests bring the research crate to **45 tests**.
Research formatting, Clippy, tests and release checks pass, as do the root checks
with **44 Windows tests**. Existing ordinary, persistence, restart, custody,
publication and inspection matrices remain regression obligations; their older
results do not qualify the new receipt path by themselves.

The [CI ledger](namespace-receipt-marker-ci.json) records source `b819f54`
passing on Windows, Ubuntu and macOS, with all 45 research tests per platform
and root contracts (44 Windows tests; 45 on each Unix platform). Windows also
passes the 93-case receipt matrix and all six regression matrices listed above;
Unix workers refuse the receipt adapter before creating artifacts. These checks
do not qualify namespace persistence, receipt survivor rules or a storage profile.

The implementation reuses the existing reviewed Windows SDK calls, dependencies
and unsafe boundary. It adds no secret, key service, privileged production helper,
source ACL mutation or production writer. The portable proposal model remains
test-only and does not grant runtime storage-profile admission.

#0047 retains separate guest interruption qualification, #0048 actual storage-error
qualification, #0049 cumulative resource/retention policy and #0051 profile
admission. Durable caller-history provenance/freshness and independent RAW admission
remain open. Physical-power testing is excluded by the current
[VM-off-only policy](power-test-policy.md), not an additional gate. #0027's real-camera mutation refusals
and #0023/#0024 gates are unchanged. #0046 ends at the implemented and verified
marker receipt sequence and its explicit unsupported qualification boundary.
