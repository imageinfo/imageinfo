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

Run only after the frozen static build, native baseline and existing installed
guest/controller are ready. Inside WSL:

```console
python3 experiments/0047-receipt-guest/qualify.py --root <installed-private-guest> --binary <exact-static-worker> --source-root <frozen-b819f54-source> --output <fresh-private-capture-directory>
python3 experiments/0047-receipt-guest/audit.py --root <private-capture-directory> --binary <exact-static-worker> --source-root <frozen-b819f54-source> --public docs/write-safety/namespace-receipt-guest.json
```

`--output` is optional; its omission selects a fresh directory under the private
guest root. Paths above identify the existing owned fixture, not an arbitrary
Windows installation. The audit reconciles actual captures and bindings before
producing the public ledger.
The public ledger contains bounded sanitized observations; raw captures and its
private hash manifest are not publication artifacts.

The [audited ledger](../../docs/write-safety/namespace-receipt-guest.json) covers
34 cases: one normal control and 11 each process kills, emulator kills and NMI
bugchecks, with 22 distinct post-fault boots and 204 private capture files.
All 34 byte/name pairs match; 32 property-observation pairs/full inspection
inventories match. Native inspection reports 11 matching observations and 23
refusals. The emulator-kill and NMI `receipt-written` cells retain matching
receipt content but show receipt timestamp drift and refuse native inspection.
The cause is unproven. Successful flush returns and surviving receipts do not
qualify namespace acknowledgements, a committed receipt, a production profile,
automatic freshness, repair or RAW mutation.

The first attempt stopped after 19 progress rows in the emulator-kill
`receipt-written` cell. Its receipt timestamp differed by about 2.56 ms across
the rich inspection inventory pair; the native inspector refused
`FILE_PROPERTIES_CHANGED`. Names, bytes, hashes, sizes, streams, SDDL and root
observations matched. The cause is unproven. Keep that incomplete attempt and
its twentieth-cell before/after evidence private, and preserve it when starting
a fresh full run. The revised inventory audit distinguishes property drift from
byte/name changes without weakening native guarded checks. This preliminary
attempt is separate from the final audited set.

The fresh run required operator assistance after 32 rows: the already-faulted
and relaunched NMI `receipt-parent-flushed` cell waited at standard-user sign-in
beyond the original 240-second controller deadline. The existing credential
worked with slower QMP keystrokes; no policy, credential or license changed.
A private continuation helper verified frozen bindings, completed read-only
inspection of the pending 33rd transaction and ran one fresh final NMI cell.
There was no publication replay. Do not describe this as an unassisted original
CLI completion. The original timeout bytes remain bound in
`interrupted-before-signin.private.json`. Helper source and SHA-256
`46ec7861ef0ff7862b8b1884f1bec92c4352291a0fab107189c5c3c3d253d27f`
are retained in the private audit manifest. The helper's continuation semantics
were independently reviewed; the frozen auditor independently reconciles all
34 raw cases and common bindings.

The exact static guest worker also passes the fresh original 93-case native
receipt baseline. The [CI ledger](../../docs/write-safety/namespace-receipt-guest-ci.json)
records passing Windows, Ubuntu and macOS checks for tooling source `83b2621`.
CI does not run the private VM matrix or rebuild this frozen static executable.
The guest is normally shut down; its disk and captures remain private and retained.

Host caches remain live; the OS, crash dump and markers share the guest's test
volume. NMI followed by controlled quit may drain I/O and is distinct from
emulator kill. No physical-power qualification is implied.
