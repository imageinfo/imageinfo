# #0114 process-owned checked receipt custody

Standalone authored-marker research connects #0103's actual process ownership to
#0110's checked receipt export. See the [contract and limits](../../docs/write-safety/checked-receipt-custody.md).

`runtime.py` provides `CheckedReceiptCustody(root, actor, inspector,
byte_limit=655360, observe=None, control=None)`. `begin`, `stop`, `prune`, `release`,
`close` and `status` retain the existing process-custody lifecycle.
`inspect_receipt()` uses only the completed checked actor's internally retained
context and invokes the separately pinned frozen inspector read-only. It accepts
no context, PID or imported history. Fresh inspections may be repeated while the
same live instance remains eligible; each rechecks current objects.

The actor is pinned to E378 and `ordinary-receipt-checked-flush`; helper actions
and inspection use F869. The existing #0103 runtime, #0110 worker, evidence and
v1 record formats remain unchanged. Wrong binary hashes refuse before operation
root creation and the selected executable is rechecked before each invocation.
Trusted executable paths and no adversarial substitution between hashing and
launch remain assumptions.

```text
python -W error experiments/0114-checked-receipt-custody/test_runtime.py
python -W error experiments/0103-process-custody/test_runtime.py
```

Portable tests use authored protocol events and real owned synthetic subprocesses.
They do not establish native filesystem behavior, flush failure or durability.
The [five-cell native result](native-result.json) records independently audited
integration observations on Windows 10.0.26200 AMD64. Normal checked release
permits one matching frozen inspection; actual owned-child termination and a
native receipt-time conflict before export permit no inspection; a later owner
output edit yields inspection refusal; confirmed unpublished stop/prune removes
three owned handles. All 59 independent source observations remain unchanged.
This does not establish native storage-error or VM-fault behavior.

To collect separate fresh authored native evidence with the exact reviewed binaries:

```text
python experiments/0114-checked-receipt-custody/qualify.py --actor E378 --inspector F869 --root NEW_PRIVATE_ROOT
python experiments/0114-checked-receipt-custody/audit.py NEW_PRIVATE_ROOT
python -W error experiments/0114-checked-receipt-custody/test_audit.py
```

The runtime writes only the existing finite marker/custody construction plan;
qualifier logs and inventories are external evidence, not an extra runtime journal.

No VM fault, source media, SDK/API change, dependency, crypto, recovery replay,
production profile or RAW publication is part of this increment.
