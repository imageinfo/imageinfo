# Actual production-worker native error fixture (#0174)

This is a finite secondary-device error fixture. The
[negative qualification handoff](../../docs/write-safety/production-native-errors.md)
records actual source-read1117 and compound candidate433 errors, a contrary
prepared-source namespace observation, and three unproduced native flush-error
classes. No storage profile or media-writing capability is admitted.

## Preconditions and finite method

Only the preflighted private disposable Windows evaluation guest is supported.
Create a new QCOW2 overlay over its unchanged hashed base, copy its existing
firmware/TPM state, preserve the evaluation creation date, exclude setup media,
host devices, shared folders and original media, and use the existing ordinary
guest/operator identities. No installation, licensing, privilege or ownership
change outside newly created fixture files is part of this experiment.

Prepare six new 128 MiB secondary raw files, each with a uniquely identified
127 MiB NTFS partition at LBA2048. Source bytes are authored 16 MiB ASCII `1`;
the derivative is 4 MiB byte `0x74`. Bind each image's initial hash, source hash,
volume label, exact source allocation and the compiled worker. The checked-in
controller refuses other roots/images, boot/system guest partitions and
administrator workloads. Preparation scripts/configuration containing private
guest bindings remain private; this is not a general disk-formatting tool.

Build the root library test executable with static CRT into a separate target
directory, freeze its exact source tree and hashes, and serve that executable.
The explicitly ignored test is
`storage::native_errors::guest_native_error_worker`; its sole environment input
is the exact freshly prepared secondary `IMAGEINFO_174_ROOT`. It additionally
requires the authored fixture marker, existing source and absent transaction root.
It calls unqualified production execution and accepts only `continue` controls.

The finite schedule is normal control, source-data read EIO, staged backend
ENOSPC, candidate-file flush EIO, postpublication root flush EIO, and receipt-file
flush EIO. Use no process/OS/power fault to substitute for native error evidence.
The observed candidate cell's controller failure is retained as incomplete;
only its two unattempted successors use once-only backend EIO. Resume skips
completed **and already attempted** cells; it does not replay a worker.

The host controller uses loopback port18724 and the guest's existing NAT path:

```text
python3 controller.py EXACT_PREFLIGHTED_PRIVATE_ROOT EXACT_FROZEN_TEST_EXECUTABLE
```

`guest.ps1` runs as the guest standard user. It emits actual worker events,
native code/kind observations and bounded before/after inventories. The
controller changes only QEMU secondary-node children at worker barriers;
its 60-second backend-fault ceiling and guest line/exit deadlines are harness
bounds, not production I/O cancellation guarantees. QEMU drain errors remain
separate from guest API results. Never infer a native flush error from an armed
rule, a QEMU error or a successful guest flush.

## Read-only retained audit

Normally shut down the exact guest before inspecting images. The auditor checks
that no QEMU process is bound to the fixture; it never mounts or repairs NTFS:

```text
python3 audit_retained.py EXACT_PREFLIGHTED_PRIVATE_ROOT --output-name retained-audit-final.private
python3 audit.py EXACT_PREFLIGHTED_PRIVATE_ROOT/captures
```

The private root must contain its preflight and the installed private NTFS tools
already bound by earlier guest work. Audit outputs are fresh bounded child
copies; input raw images are opened read-only and hashed before/after. Retain
all failed reads, partial cells, old controller bindings and raw captures.
The capture audit preserves the empty staged-error inventory and refuses its
preservation claim; finding source bytes at the earlier fixture name never
repairs missing prepared namespace/property evidence. No file/root cleanup,
recovery or general publication authority follows from inspection.
