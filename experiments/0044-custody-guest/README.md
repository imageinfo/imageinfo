# #0044 Windows caller-history interruption research

This bounded guest matrix exercises the existing #0043 caller-history worker,
not the later #0046 receipt sequence. Read the
[method, outcomes and limits](../../docs/write-safety/windows-custody-guest.md)
and [caller trust contract](../../docs/write-safety/windows-custody.md) first.
All files are authored markers; no camera media is accepted.

The worker is rebuilt from exact source revision `b381576`, using the existing
locked dependencies and static CRT linkage needed by the installed guest. The
native 41-case custody matrix passes with the **exact static guest executable**:
117 worker captures and 1,398 readable hashed paths, with one deliberately
inaccessible DACL path retained without repair. This static executable differs
from the historical dynamically linked #0043 worker; its source bindings match.
Executable,
archived source, loaded driver/controller and capture hashes remain separately
bound so an older evidence label cannot silently describe a newer implementation.

The guest supervisor holds the original worker at `before-namespace-call`, then
uses a second worker to save each whole-history snapshot in a separate fresh
private directory. It must observe complete save success before advancing. Stop
attestation requires the actual held process to exit without publication release;
the release fence must be saved before the original receives `continue`.

Four independent transactions cover captured-only NMI, confirmed-stop emulator
termination, fenced-before-release NMI and renewed-postpublication emulator
termination. The installed standard user runs both worker processes. Each fault
requires a fresh boot, and NMI cases require actual fresh bugcheck evidence.
Custody/transaction inspection is read-only; any caller-directed prune or
observation validation is a separate request subject to fresh guards.

Use only the existing installed disposable evaluation fixture. Keep credentials,
VM/ISO files, service descriptors, QMP state, transcripts, screenshots, host-boot
records and raw capture inventories private. Preserve historical source/binary
and capture artifacts. Never inject faults into Terry's host, reattach the
initial wipe-capable setup media, rearm the evaluation or change host OS policy.

After rebuilding the exact source, running the original native qualifier and
starting the existing installed guest/controller with the exact static executable,
run the guest driver and audit inside WSL:

```console
python3 experiments/0044-custody-guest/qualify.py --root <installed-private-guest> --binary <exact-static-worker> --source-root <frozen-b381576-source> --output <fresh-private-capture-directory>
python3 experiments/0044-custody-guest/audit.py --root <private-capture-directory> --binary <exact-static-worker> --source-root <frozen-b381576-source> --public docs/write-safety/windows-custody-guest.json
```

`--output` is optional; when omitted the driver selects a fresh directory under
the private guest root. Paths above are placeholders for owned private test
artifacts, not arguments selecting an arbitrary Windows installation. The
controller must provide the custody-supervisor operation and restart/inspection
adapters used by this driver.

Before auditing, retain the historical native source/executable binding as
`native-binding.private.json`, the exact static executable's fresh native binding
as `static-native-binding.private.json`, and the archive's Git-blob provenance as
`frozen-git-blobs.private.json`. Preserve the loaded controller sources under
`controller-sources.private` and independently verified host boot continuity as
`host-continuity.private.json`. These are private evidence inputs from the
actual build/run; do not manufacture them from the expected outcomes.
Driver-start and driver-end source bindings must match. The audit reconciles
those bindings, the loaded driver and served guest-agent bytes, fixed case set,
actual control ordering, standard token,
distinct post-fault boots, fresh NMI events, inventories and false permission
flags before writing a sanitized public ledger. It also writes a private SHA-256
manifest of the evidence files. Do not publish raw captures.

The [audited result](../../docs/write-safety/windows-custody-guest.json) passes
four cells/faults, with two fresh NMI bugchecks, two emulator terminations, four
distinct post-fault boots, nine custody saves and 43 private evidence files. Four
transaction inventory pairs remain unchanged across custody inspection, and four
custody inventory pairs remain unchanged across the explicit caller actions and
reinspection. Captured-only and fenced histories yield no context and refuse
unattested prune. Confirmed-stop history permits an explicit guarded three-handle
prune. Renewed history validates the exact existing observation; the stale
two-record context and postpublication prune refuse. Source and root remain.

Successful flush calls and surviving snapshots remain bounded observations;
they do not authenticate caller authority/freshness or enable a committed
receipt, automatic recovery, a storage profile or RAW mutation.
