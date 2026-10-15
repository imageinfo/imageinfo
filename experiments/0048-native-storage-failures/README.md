# Native storage-full marker qualification (#0048)

This finite research controller targets the frozen #0046 receipt worker used by
[#0047](../0047-receipt-guest/README.md), source revision
`b819f54533c495b332c3d4dbb0caccef49923036`, static worker SHA-256
`f86918a7fb3880cf8e09590fcc7d58155ef64d98c95cf9c2a6afc541c5b040fa`.
It adds no Rust or SDK boundary and enables no production profile or RAW writing.

## Declared fixture and finite schedule

The parent supervisor prepares one **secondary disposable 64–128 MiB NTFS volume**
inside the retained Windows evaluation guest, label `IMAGEINFO0048`. Never target
the guest system disk, Terry's host, personal media or another volume. The script
does not create, attach, format or fault a disk and refuses an administrator token.

At the secondary root, the parent writes `.imageinfo-0048-fixture.json`:

```json
{
  "schema": "imageinfo-native-errors-fixture-v1",
  "fixture_id": "unique-supervisor-supplied-id",
  "drive": "R:\\",
  "max_bytes": 134217728
}
```

The exact ID and drive must match the invocation. The script additionally checks
NTFS, label, volume size, non-system/non-boot partition and absence of a reparse
root. A fresh ID is required for a repeat; retained transaction directories are
never reused or removed. Captures go outside the exhausted fixture.

The five scheduled cells are a normal control, full volume before candidate
creation, an attempted partial candidate with 32 KiB released after exhausting
the volume, full volume before the prepared record, and full volume before the
receipt. Allocation uses actual 4 KiB non-sparse writes with `Flush(true)` until
the native filler call fails, bounded by 128 MiB. The filler exception's operation,
HRESULT and write count are recorded separately from the worker's actual native
error diagnostic. The worker receives only `continue` controls: no protocol
failure, short producer, permission actor or synthetic syscall fault is injected.

This schedule does not assume a partial write will occur. The actual retained
candidate length determines whether that cell observed one. NTFS allocation or
resident-record behavior can make native exhaustion differ across boundaries.
An unavailable intended cell must be recorded explicitly, never relabeled from a
protocol injection. An actual filler flush failure does not establish a worker
device-flush failure. Native read/device-flush and isolated metadata-only failure
cells remain unrun and unqualified unless separately observed.

## Run and independently audit

Run the following **in the disposable guest as its standard user**, after the
parent has verified the fixture and staged the exact bound worker. Replace the
example ID and paths with the parent's actual values:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File qualify.ps1 `
  -Drive 'R:\' -FixtureId 'unique-supervisor-supplied-id' `
  -Worker 'C:\ImageInfoGuest\probe.exe' `
  -WorkerSha256 'f86918a7fb3880cf8e09590fcc7d58155ef64d98c95cf9c2a6afc541c5b040fa' `
  -Capture 'C:\ImageInfoGuest\native-errors-unique-id'
```

Every transaction/source/output/partial record remains retained. The controller
removes only its own filler, after worker exit and read-only inspection, to permit
the next bounded cell. This is harness reclamation of fixture filler, not worker
cleanup, restart prune or general cleanup authority. Inspectors receive the
actual emitted receipt context for the successful control and explicit `{}` when
none exists; the latter measures missing-context refusal, not artifact validation
under invented bindings. Inventories include bytes/hash, `fsutil` file-ID query,
timestamps, attributes and SDDL before/after inspection.

After privately retrieving captures:

```powershell
python experiments/0048-native-storage-failures/audit.py PRIVATE_CAPTURE_DIRECTORY
```

The auditor requires real native storage-full codes from both filler and worker
for scheduled failure cells, complete unchanged source and inspection inventories,
no owned-handle removals and false commitment/admission flags throughout. It emits
bounded observations only after those checks. A 45-second controller line/exit
deadline is a harness bound; it does not qualify native I/O cancellation or a
production deadline. Retain private captures, fixture disk, exact script hash and
parent guest/host bindings outside source control. No success ledger is supplied
by this reproduction description itself.
