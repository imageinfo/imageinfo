# Checked receipt context boundary (#0110)

Observed 2026-10-16. This separate marker research mode hardens the point at which
the caller receives observational receipt context. It does not identify or fix
the last-write drift measured by [#0106](receipt-vmoff-properties.md).

`ordinary-receipt-checked-flush` retains the original creator handles, guards,
receipt bytes and `Info` snapshots throughout the live sequence. At
`receipt-written` it exports no receipt context. After successful explicit receipt
file `sync_all`, it runs the full original `check_live` and emits a
`checkedReceiptBoundary` event immediately before exporting the first context.
It repeats the full check after parent flush and before the later export. Query
failure or any identity, byte, property, security, stream or layout conflict
refuses. No timestamp is rebased and no handle is closed/reopened for export.

The legacy receipt mode and observational receipt/context v1 formats remain
unchanged. A context carries no self-authenticating proof of its emission mode;
external caller custody must retain the actual worker hash, selected mode and
complete event history. Old pre-flush contexts acquire no new contract.

The [authored research harness](../../experiments/0110-receipt-context/README.md)
retains eleven finite native controls and exactly two fresh-overlay VM-off cells.
The native controls cover normal ordering, pre-context cancellation, producer
protocol failure, actual process termination, receipt time/ADS conflicts, held
default-stream write/name denial, a later stale context, source time conflict and
unchanged frozen-inspector refusal of that actual stale context. Failure injected
through a control line is not a native storage-flush failure.

The guest cells stop at `receipt-written` and the first checked file-flush context
barrier. They use a newly frozen candidate/native baseline, the unchanged F869
inspector and separate existing #0106 read-only native observer. Bootstrap
readiness requires exact downloaded payload hashes and a fresh challenge response
from the same agent instance before measurement jobs are queued. Subsequent boots
use the installed script without replacement. Source, controllers, bytes,
properties, host/base bindings and failed attempts are retained privately.

The eleven final native cells pass independent retained-artifact audit; the
unchanged legacy receipt mode also passes its separate 93-cell native regression.
Public results retain the [native](../../experiments/0110-receipt-context/native-result.json)
and [guest](../../experiments/0110-receipt-context/guest-result.json) observations.
In the two new guest cells, the pre-context VM-off again changes the receipt's
native last-write observation. No receipt context or inspector request is
invented for that cell. The first checked-context cell retains a matching
observation under the unchanged F869 inspector. One first-boot sign-in needed an
explicit login-only continuation before any postfault reader was queued; no
actor, fault or read-only job was replayed. The second boot required no assisted
continuation. This finite comparison supplies no timestamp-cause conclusion.

The scope is context-boundary hardening only. File flush API success and finite
VM-off observations do not establish durable namespace/receipt acknowledgement,
automatic custody, repair/finalize/prune authority, a complete production storage
profile or independent RAW-format admission. Host caches remain alive. No host
crash, NMI, hardware power test, source ACL change, SDK/API addition, dependency,
crypto or production mutation capability is introduced.
