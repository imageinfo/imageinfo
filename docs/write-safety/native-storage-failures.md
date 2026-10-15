# Native storage-full observations on a disposable Windows volume

**#0048 research, observed 2026-10-15.** The
[audited five-cell ledger](native-storage-failures-native.json) records actual
native storage-full failures from the accepted [#0046 receipt marker
worker](namespace-receipt-marker.md). This qualifies the bounded failure reports
and retained artifacts below. It does not qualify a complete storage profile,
durability, repair or RAW writing.

## Exact fixture and worker

The existing Windows 11 Enterprise Evaluation guest, version **10.0.26300**,
ran the workload as its ordinary standard user on x86_64 QEMU. The supervisor
created one new **134,217,728-byte secondary raw image** with an MBR type-07
partition starting at LBA 2048. A separately formatted 127 MiB NTFS partition
image was embedded at that offset. Windows reported **133,165,056 volume bytes**,
label `IMAGEINFO0048`, on a non-system, non-boot secondary partition. The workload
checked the exact supervisor fixture marker, label, size, filesystem and partition
before writing; it refused an administrator token and a reparse root.

QMP attached that file using `raw` over `file`, with `usb-storage` on the existing
`qemu-xhci` controller. No explicit cache flags were supplied. The actual
`query-block` secondary-device observation reports `writeback=false`,
`direct=false`, `no-flush=false`; `query-named-block-nodes` reports
`writeback=true`, `direct=false`, `no-flush=false` for both the raw and backing-file
nodes. These distinct layer observations are retained separately in the ledger;
they do not establish one uniform cache mode or qualify the host storage stack.
The system volume and original guest disk were not exhaustion targets. These
secondary USB observations do not generalize [#0047's system-volume interruption
results](namespace-receipt-guest.md).

The static worker SHA-256 is
`f86918a7fb3880cf8e09590fcc7d58155ef64d98c95cf9c2a6afc541c5b040fa`,
from frozen source `b819f54533c495b332c3d4dbb0caccef49923036`.
The actually served controller SHA-256 is
`14628dec7f18ffb797cce4b26a561ddb470b0e6ad0782cbc2e440697be87802c`.
The ledger also binds the auditor, private capture manifest and initial/final
secondary image hashes. The [controller and reproduction instructions](../../experiments/0048-native-storage-failures/README.md)
declare the fixture and finite schedule. No Rust code, dependency or SDK API was
added or changed for this child.

## Actual finite matrix

The filler performs allocated 4 KiB writes with `FileStream.Flush(true)` until
Windows actually returns disk full. Its exception HRESULT, operation and successful
byte count are retained separately from the worker's native error. Every worker
control was `continue`. There was no injected protocol failure, short producer,
permission actor, invented syscall status or device crash.

| Cell | Actual worker observation | Retained transaction artifacts |
| --- | --- | --- |
| Normal control | Receipt sequence and context-bound read-only inspection succeed as observations. | Source, 65,536-byte output, three prior records and 1,810-byte receipt. |
| Full at `source-guarded` | Native `os error 112` before candidate completion. | Unchanged source and empty candidate. |
| Full at `source-guarded`, then release 32 KiB | Native `os error 112` with an actual partial candidate. | Unchanged source and **32,768-byte candidate**. |
| Full at `candidate-flushed` | Native `os error 112` before the prepared record exists. | Unchanged source and complete 65,536-byte candidate. |
| Full at `observation-parent-flushed` | Native `os error 112` after publication, before receipt completion. | Unchanged source, complete 65,536-byte output, three prior records and **empty receipt**. |

All four filler failures and all four worker failures carry actual Windows
storage-full code **112**. The partial-candidate cell observed partial retained
bytes rather than assuming a short write from the intended schedule. The small
record failure was not isolated as metadata-only exhaustion: native full-volume
allocation and file creation/write behavior remain coupled.

Every source's content, length, file-ID query, timestamps, attributes and SDDL
match its prepared inventory. Every retained file's actual ID query succeeds;
IDs are distinct within each transaction. All five before/after read-only
inspection inventories match exactly. The successful control supplies the actual
emitted receipt context. Failure cells have no such context and explicitly supply
`{}`: they measure missing-context refusal, **not** validation of incomplete
artifacts under an invented binding. All transaction artifacts remain retained.

Every worker and inspector event reports `committed=false`,
`namespaceAcknowledged=false`, `repairAllowed=false` and
`productionPublicationAllowed=false`. Every terminal worker reports zero owned
handles removed. The postpublication failure retains the installed output and
unresolved receipt; it grants no replay, rollback or cleanup authority. Between
cells the harness removes only its own sibling filler after worker exit and
inventory, to make the same bounded volume available to the next cell.

## Verification and remaining limits

The independent auditor reconciles the actual private captures and exact served
worker/controller bindings before emitting the public ledger. It checks native
error provenance, false flags, actual partial lengths, distinct file IDs, source
preservation, namespace/length bounds and unchanged inspection inventories.
Independent review reran the audit against retained captures. PowerShell syntax,
Python compilation, documentation checks and `git diff --check` pass.

After the five cells, the guest completed a **normal `shutdown.exe /s /t 0`**;
its emulator PID and QMP socket disappeared. Original guest disk, secondary image
and private captures remain retained. The actual host boot UTC/ticks match before
and after; host caches stayed alive. No host crash, system-disk exhaustion,
evaluation rearm, source-media mutation or privilege/policy change occurred.

Actual native **read failures**, worker **device-flush failures**, isolated
metadata-only exhaustion, physical power loss and other storage stacks remain
**unrun and unqualified**. A filler `Write/Flush(true)` exception is not evidence
of a worker device-flush failure. The controller's 45-second worker line/exit
deadline is a harness bound, not qualified native-I/O cancellation behavior.
The receipt remains observational, with no qualified namespace acknowledgement.
[#0051's exact admission ledger](profile-admission.md) must retain
these missing cells and the separate custody, persistence and RAW gates.
