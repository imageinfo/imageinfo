# Process-owned checked receipt observation (#0114)

The separate [research runtime](../../experiments/0114-checked-receipt-custody/runtime.py)
connects [process-owned caller custody](process-custody.md) to the
[checked receipt context boundary](checked-receipt-context.md). It owns the actual
checked actor subprocess, retains its bounded event history and receipt binding
in process memory, and exposes a fresh read-only inspection using only that
internally captured context. This is an observational authored-marker API.

`CheckedReceiptCustody(root, actor, inspector, byte_limit=655360, observe=None,
control=None)` requires a fresh operation root. The actor hash is
`e378d436ed478cc4fe31ec84ff0ab91f27a459d8c6b636fcb55d0c700c11f941` and its
mode is exactly `ordinary-receipt-checked-flush`. The separate helper/inspector is
F869, hash `f86918a7fb3880cf8e09590fcc7d58155ef64d98c95cf9c2a6afc541c5b040fa`.
Both bindings are checked before root creation; the selected executable is checked
again before every invocation. As in #0103, the trusted caller must prevent an
adversarial binary substitution between the hash check and launch. Hash matching
does not supply exclusion or caller authentication.

`begin()` captures the original child's before-publication caller context and
completely saves the existing captured-history snapshot before returning at the
withheld publication barrier. `stop()` and one-attempt `prune()` retain #0103's
actual owned-child exit, completed stop save and fresh guarded exact-handle rules.
`release()` saves the complete release fence before continuation. Beginning that
release attempt permanently excludes the stop/prune branch, even on an uncertain
pipe write or failed save. A recreated instance cannot adopt a surviving root.

For checked receipt eligibility the runtime consumes the original child's events
itself, before passing copied observations to hooks. No receipt context may appear
through `receipt-written`. The required subsequent sequence is:

1. A `receipt-file-flushed` checked-boundary notice with both original-properties
   and file-flush success booleans true; its receipt context; its matching barrier.
2. A `receipt-parent-flushed` checked-boundary notice with both booleans true;
   an identical receipt context; its matching barrier.
3. The `final-checked` barrier, a successful receipt terminal reporting file flush,
   parent flush and final checks, then confirmed exit of this actual owned child.

Each receipt context must bind the actual preceding renewed caller context. The
two exports retain the original identical receipt identity, properties and bytes.
The runtime does not rebase snapshots. Early, missing, duplicated, reordered or
inconsistent relevant events invalidate eligibility. A successful terminal alone
cannot replace this sequence or actual process exit. Native receipt parsing and
fresh file/property validation remain the frozen inspector's responsibility.

Only completed checked release enables `inspect_receipt()`. It accepts no caller
context, JSON history, PID or path sweep. It launches F869
`ordinary-receipt-inspect` with the internally retained actual context. A later
ordinary owner edit can make that original context stale; the inspector's refusal
is preserved as an observation. Repeated inspection on the same eligible live
instance repeats fresh read-only checks. An inspection error or uncertain runtime
state disables further action; close invalidates and clears the retained receipt
binding. Hooks and returned dictionaries cannot overwrite internal observations
through the public API. Python callers in the same interpreter remain trusted.

The unchanged logical admission is 655,360 bytes for one source, one candidate,
four bounded transaction records and at most four custody snapshots. Charges
never refund. The new receipt binding and complete finite original event history
stay in memory: at most 128 original events, each within the existing 65,536-byte
line limit. No fifth custody snapshot or persisted receipt-context journal is
created. Independent qualification captures are external evidence. Existing
30-second response waits are protocol limits, not hard OS-I/O deadlines.

Status exposes actual selected hash/mode provenance, event/export and inspection
counts, and a separate checked-context eligibility observation. `committed`,
`namespaceAcknowledged`, `repairAllowed`, `productionPublicationAllowed` and
`automaticDurableCustody` remain false. Receipt-context v1 does not authenticate
its own emission mode; this live caller retains that provenance. Closing or
restarting loses the process-local eligibility. Source, roots, custody snapshots
and unresolved postpublication artifacts remain retained.

Focused portable tests cover exact sequence, legacy early context, missing/false
checks, reordering, duplicate export, changed original binding, terminal-only
success, copied observations, real owned synthetic child exit and failure cleanup,
invalid inspection lifecycle, no context import, binary refusal and byte admission.
These are authored protocol controls, not native storage errors or durability
evidence. All six focused portable tests and the six unchanged #0103 portable
tests pass with warnings treated as errors.

The [five-cell native ledger](../../experiments/0114-checked-receipt-custody/native-result.json)
records independent retained-artifact audit on Windows 10.0.26200 AMD64. Normal
release retains two identical checked exports, all four existing custody snapshots
and an actual matching frozen inspection. An authored caller exception at
`receipt-written` causes actual owned-child termination with no checked context
or inspector launch. A native receipt last-write change at that same pre-context
barrier yields actual worker refusal and no eligible context or inspection. A
later ordinary-owner same-object output edit leaves the original captured binding
unchanged and the fresh inspector refuses. The separate confirmed unpublished
stop/prune path removes exactly three owned handles; retry launches no worker.

The auditor reconciles exact binary/tooling hashes, actual mode and controls,
worker events, contexts, completed custody snapshots, process exit, native file
identities/bytes/properties and unchanged read-only inspection inventories. All
59 independent source observations retain the original identity, bytes and
properties. Wrong actor/inspector, below-budget, existing-root and invalid
inspection/prune lifecycle controls refuse. Source, roots, custody and unresolved
postpublication artifacts remain retained after close. Twelve auditor negative
controls cover fabricated or conflicting evidence independently of the collector's
summary. The bound runtime SHA-256 is
`8b650a3eddce22115c07986478e12d9fa38561f0c43a168b6480598daf3ed80c`.
The caller exception is an authored protocol interruption; the receipt/output
changes are deliberate native actors. None is a storage-device or flush error.
No VM fault was run and no #0110 guest observation is rebound to this runtime.

This increment changes no #0103/#0110 evidence, native worker, receipt/context
format, SDK boundary, dependency or production API. It introduces no automatic
OS-restart custody, namespace/receipt acknowledgement, repair/finalize/replay,
production storage profile or independent RAW-format admission. No VM fault or
hardware power test is needed for this process-local integration. The accepted
[VM-off policy](power-test-policy.md) and host-cache limits remain unchanged.
