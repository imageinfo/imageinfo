# #0047 Windows marker receipt interruption research

This bounded matrix interrupts the accepted #0046 receipt worker at 11 barriers
using three distinct fault methods, plus one normal control. Read the
[method and limits](../../docs/write-safety/namespace-receipt-guest.md) and
[#0046 caller-context contract](../../docs/write-safety/namespace-receipt-marker.md)
first. All inputs are authored 64 KiB markers; no camera media is accepted.

Freeze exact source revision `b819f54533c495b332c3d4dbb0caccef49923036`, rebuild
with static CRT linkage using the existing locked dependencies, and run the
original 93-case native receipt qualifier with that exact executable. Bind the
frozen Git blobs, Rust/manifest inputs, executable and loaded controller/driver
bytes separately. Historical dynamic-worker evidence remains historical evidence.

Use only the existing installed Windows 11 EnterpriseEval build 26300 fixture,
with its standard test user and existing guest-only crash configuration. Preserve
the guest disk and historical source, binaries and captures. Keep credentials,
VM/ISO files, service descriptors, QMP state, transcripts, screenshots, host-boot
records and raw inventories private. Never inject faults into Terry's host,
rearm the evaluation, attach wipe-capable setup media or change OS policy.

The controller holds the worker at the selected barrier before the fault. It
captures any actual emitted `receiptContext` outside the editable transaction;
it never reconstructs one from matching transaction JSON. A missing context
must refuse. After process-only termination the guest boot remains the same;
emulator-kill and NMI cases require fresh boots, and NMI cases require fresh
bugcheck evidence. The host boot remains unchanged throughout.

Read-only receipt inspections are bracketed by inventories. Byte/name agreement
and exact property-observation agreement are counted separately. Inventories do
not read native file identities; the native inspector performs fresh guarded
current-object identity and property checks. Independently decoded
`matching-context` survivor content does not itself establish native inspection
success, authority or durability. Matching observations and refusals are both
recorded. Every missing name, mismatching binding
or unexpected survivor remains a counterexample to the relevant persistence
expectation. Inspection never authorizes cleanup or repair. The normal control
checks successful explicit-context inspection.

The driver and audit live in `qualify.py` and `audit.py`. Use their `--help`
output for the exact current arguments before running against private paths.
Run only after the frozen static build, native baseline and existing installed
guest/controller are ready. The audit must reconcile the actual captures and
bindings before producing `docs/write-safety/namespace-receipt-guest.json`.
The public ledger contains bounded sanitized observations; raw captures and its
private hash manifest are not publication artifacts.

At this drafting stage no guest cells are claimed to pass. A completed audit
must state the actual counts and survivor outcomes, retain any counterexamples,
and record the guest/controller's final shutdown state. Successful flush returns
and surviving receipts do not qualify namespace acknowledgements, a committed
receipt, a production profile, automatic freshness, repair or RAW mutation.

The first attempt stopped after 19 progress rows in the emulator-kill
`receipt-written` cell. Its receipt timestamp differed by about 2.56 ms across
the rich inspection inventory pair; the native inspector refused
`FILE_PROPERTIES_CHANGED`. Names, bytes, hashes, sizes, streams, SDDL and root
observations matched. The cause is unproven. Keep that incomplete attempt and
its twentieth-cell before/after evidence private, and preserve it when starting
a fresh full run. The revised inventory audit distinguishes property drift from
byte/name changes without weakening native guarded checks.

Host caches remain live; the OS, crash dump and markers share the guest's test
volume. NMI followed by controlled quit may drain I/O and is distinct from
emulator kill. No physical-power qualification is implied.
