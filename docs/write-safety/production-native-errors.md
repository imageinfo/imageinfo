# Production-worker native errors: bounded negative qualification

**#0174, observed 2026-10-17. The current candidate is not qualified.** The
actual production runtime received Windows **1117** during a source-data read
and **433** during candidate creation's compound create/write/check operation.
The second cell lost the prepared source and transaction namespace: the exact
16 MiB authored source bytes survive at the earlier fixture name, but the
prepared source name and properties are **not qualified as preserved**.
All three requested native flush-error classes remain **unproduced**. These
contrary and missing cells require [profile admission](profile-admission.md)
to refuse; this handoff supplies no storage profile, commitment or RAW permission.

## Exact worker and separate error fixture

The ignored, explicitly selected [guest test](../../src/storage/native_errors.rs)
calls the actual internal Windows adapter and ordinary runtime with authored
bytes. It uses unqualified execution, never test admission. Every controller
response is `continue`; no protocol error, short producer or invented native
status replaces a device failure. A bounded `cfg(test)` observer records only
the returned `ErrorKind` and `raw_os_error`; production classification is unchanged.

The static-CRT test executable SHA-256 is
`9495e70fea1e5b91eaeb3d02ebcbe1da04a83268ef8743e02c7e24f78a6d73a6`.
Exact source snapshots, per-file hashes, build output and that executable are
retained privately. The relevant frozen runtime, adapter, observer and SDK
sources bind this executable; later unrelated inspection/group source changes
are not retrospectively attributed to its observations.

The existing [evaluation guest](windows-guest.md) ran from a **new QCOW2 overlay**
with its existing disk as immutable backing. New copies of its firmware/TPM
state preserve the existing evaluation; no license reset/rearm occurred.
Installed restarts excluded setup media, physical devices, shared folders and
original camera/source media. The launcher opens existing KVM access and drops
to the existing ordinary operator before guest execution. The workload refused
an administrator token and checked each secondary volume's label, NTFS type,
bounded size and non-system/non-boot partition. The primary retained guest
configuration and these secondary observations remain separate evidence.

QEMU **10.2.1**, q35/KVM, four CPUs and 8 GiB RAM hosted six new **134,217,728-byte**
raw secondary images, each with a 127 MiB NTFS partition at LBA 2048. Each used
`usb-storage` on `qemu-xhci`, explicit `write-cache=on`, `rerror=report`,
`werror=report`, and file-node `direct=false`, `no-flush=false`. Actual
`query-block` and named-node cache facts are retained independently. This is
an error fixture, not the selected system SATA/QCOW2 durability profile.

An offline-authored source occupies known NTFS data clusters. The read cell's
Linux EIO rule targets one sector 8 MiB into those source bytes. The staged
cell arms Linux ENOSPC for backend writes. The three flush cells arm Linux EIO
for `flush_to_disk`. Arming changes the secondary raw node's child through
QMP `blockdev-reopen` at an actual worker barrier. Each requested class is
armed once. Initial colliding MBR signatures prevented unused volumes mounting;
only those unused images were detached, independently source-hashed and given
unique signatures before their cells. The successful control was not rerun.

## Actual finite outcomes

| Cell / actual boundary | Returned worker result | Retained facts and qualification |
| --- | --- | --- |
| Normal control | Complete unqualified protocol; `Refused`, no failure. | Exact 4 MiB output and all four records; prepared source name/bytes and captured properties match. |
| Source-data read / preflight | Native **1117**, `FailedBeforePublish`, phase `Preflight`. | Targeted authored data-sector EIO; prepared source name/bytes and captured properties match. No publication operation ran. |
| Staged backend writes / `create-Candidate` | Native **433**, `FailedBeforePublish`, phase `CandidateCreated`. | This compound SDK call includes create, write and checks; the observation does not isolate `WriteFile`, or establish Windows disk-full code 112. The guest's post-error source inventory was empty. Independent stopped-image reads find the exact source only at `/source.bin`; `/case/source.bin` and the prepared transaction namespace do not resolve. **Preservation qualification is refused.** |
| Candidate file flush | Actual file flush returned success; **no runtime terminal captured**. | QEMU's filter-removal drain returned EIO; the controller connection failed and its `finally` stopped the waiting original worker before publication. Exact 4 MiB candidate and prepared source name/bytes remain; source-property preservation after interruption is unverified. This is an explicit partial cell, not a native flush-error pass. |
| Installed-root flush after publication | Actual root flush returned success; complete unqualified protocol. | One backend EIO was instead consumed by QEMU's filter-removal drain. The next bounded filter-removal request succeeded; the worker was never replayed. Exact output/four records and prepared source name/bytes/captured properties match. Native namespace-flush error remains unproduced. |
| Receipt-file flush | Actual receipt-file flush returned success; complete unqualified protocol. | Same separate QEMU drain observation. Exact output/four records and prepared source name/bytes/captured properties match. Native receipt-file flush error remains unproduced. |

The first candidate-flush rule was persistent and prevented filter removal.
After stopping that original worker, its image was retained detached. Only the
two still-unattempted flush filters changed to once-only EIO, permitting one
bounded removal retry after QEMU consumed the error. This retries an emulator
filter-removal operation, never publication, a worker operation or recovery.
The candidate cell was not rerun. QEMU's own drain error is not a Windows
`FlushFileBuffers` error. A successful guest flush while a backend rule is armed
cannot qualify handling of a returned native flush failure.

The staged fixture's source move/directory preparation had no independent
durable acknowledgement before faults. Its loss does not establish that the
worker wrote source bytes, nor identify a filesystem/device cause. Conversely,
finding bytes at the old fixture name does not repair the failed prepared-name
observation or establish property preservation. The original failed inventory
and all images remain retained; no repair, remount for repair, replay or cleanup
was attempted. Existing [#0048 storage-full research](native-storage-failures.md)
is history only; its worker and passing cells were not substituted or rerun.

## Independent audit and disposition

The guest shut down normally after the finite campaign. The original guest
base's full SHA-256, inode, size and modification time match preflight exactly.
Before/after host uptime estimates remain consistent; no VM-off, bugcheck,
host-failure or physical-power action was used in this campaign.

The separate [stopped-image auditor](../../experiments/0174-native-errors/audit_retained.py)
reads each original image without mounting or modifying it, creates a new
bounded partition copy, and checks actual NTFS file contents and metadata
reports. Full original-image hashes match before/after each audit. A fresh
independent reviewer reproduced all six images' readable-file lengths/hashes,
the staged source's old-name retention and the candidate's retained bytes.
Unreadable names remain explicit, never treated as empty files or safe cleanup.

The [capture auditor](../../experiments/0174-native-errors/audit.py) reconciles
the exact worker, continuations, native results, phase outcomes, original failed
inventory, explicit partial cell and stopped-image facts. Four separate native
software-boundary tests pass, including before/after errors, lost responses,
publication uncertainty and cancellation. These are explicitly controller-error
coverage around actual calls, not produced native device-flush failures.

**Disposition: refuse qualification of this candidate.** The prepared-namespace
counterexample and missing native file/namespace/receipt flush-error classes
remain admission gaps for #0176. The finite fixture handoff is complete with
those limits; no new product relaxation or equipment search is selected.
Any later positive qualification must supply separately scoped actual evidence
for the missing classes and resolve the contrary preservation observation.
All completed worker results keep `committed=false`, profile/RAW admission false,
and zero cleanup; the partial cell makes no invented terminal claim.

The [controller and reproduction limits](../../experiments/0174-native-errors/README.md)
retain the exact finite method. Raw images, guest credentials, snapshots and
detailed captures stay private; all media content here is independently authored.
