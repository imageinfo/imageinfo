# Ordinary-output Windows persistence ordering

Direct **#0022** research, **2026-10-14**, under accepted OD-11 option A. The
previous [guest matrix](windows-guest.md) lost the output name after the namespace
API returned successfully. This increment isolates the calls after that return
and compares a documented write-through handle. It does not enable a writer,
committed receipt, restart repair or complete storage profile.

## Implemented comparison

The existing #0032 worker adds three explicit marker modes:

| Command mode | Candidate and records | Post-rename order |
| --- | --- | --- |
| `ordinary-persistence-buffered` | Existing buffered handles | Installed property checks, held-file flush, parent flush, observation-file flush, observation-parent flush. |
| `ordinary-flush-after-rename` | Existing buffered handles | Held-file flush immediately after rename, installed property checks, parent flush, observation-file flush, observation-parent flush. |
| `ordinary-write-through` | Fresh handles with `FILE_FLAG_WRITE_THROUGH` | Installed property checks, explicit held-file and parent flushes, observation-file and parent flushes. |

Each operation retains the source, candidate and ancestor/name guards across the
same conditional held-object rename. No re-open/pathname copy/delete fallback is
introduced. Fixed private owner-editable creation policy and declared property
checks remain. Source ACLs, accounts and privileges are unchanged.

New barriers are `installed-file-flushed`, `parent-flushed`,
`observation-file-flushed` and `observation-parent-flushed`. `published` remains
the earlier API-success checkpoint. The legacy `ordinary` mode keeps its original
barriers. Terminal reports separate four successful flush returns from installed
verification, publication call success and qualified persistence. All
`namespaceAcknowledged`, `committed`, `repairAllowed` and production flags remain
false, even when every call returns success.

Typed records retain a bounded optional `persistenceMode` request label. Old
records without it decode as buffered. Unknown variants and disagreement between
records refuse. A checksummed request label does not establish OS behavior,
durability or repair authority. Read-only inspection supports these observations;
admission/finalization/prune still refuse before effects.

## API basis and review

Primary Microsoft documentation viewed **2026-10-14**:

- [File Caching](https://learn.microsoft.com/en-us/windows/win32/fileio/file-caching)
  describes cached metadata and flushing/write-through requests.
- [CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew)
  documents NTFS metadata effects of write-through requests, including rename.
  Hardware support and cache behavior still matter.
- [FlushFileBuffers](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-flushfilebuffers)
  describes the per-file flush and write-access requirement. A volume flush
  requires administrative privileges and is not part of this worker.
- [FILE_RENAME_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_rename_info)
  preserves the existing no-replacement behavior.

No immutable documentation revision is asserted; the visible documentation dates
were 2021-01-07 for caching and 2021-10-13 for flush semantics. The exact admitted
SDK is still **windows-sys 0.61.2**, with the existing features/package graph.

The [FFI review](../../experiments/0032-windows-publication/ffi-review.md) now covers
one fixed additional flag in the existing `CreateFileW` call. It preserves exclusive
creation, read-only sharing, explicit security, synchronous completion and owned
handle transfer. `FILE_FLAG_NO_BUFFERING` is deliberately absent: write-through
does not require inventing aligned buffers or changing byte-copy semantics.
Ordinary source/record/protocol code remains safe Rust; root unsafe policy is
unchanged. No new SDK function, library, dependency or privileged production helper.

## Verification status

The [audited native comparison](windows-persistence-native.json) has **69 cases**, with normal owner editing, source/candidate
data guards, property conflicts, foreign collision, early cancellation and
cancel/failure/kill at five postpublication boundaries. Three correctly checksummed
mixed-mode record sets refuse read-only. These injected protocol failures are not
native disk-full/device-error or failed-flush observations.
The audit verifies **72 unchanged inspection inventories** and hashes **1,498
readable artifact paths**, retaining raw worker/actor/exit captures privately.

The research crate has **19 portable tests**. The original **64 ordinary-output,
78 publication and 35 inspection** regressions pass locally, as do the root
format/Clippy/44 Windows tests/release checks. Native and guest evidence audits
bind exact worker/helper bytes; private identifiers, media and raw logs stay local.

The [audited guest comparison](windows-persistence-guest.json) completed **33
faults and six normal runs**: the full three-mode/five-checkpoint/NMI/SIGKILL matrix,
then one extra NMI at rename-success per mode. It binds **18 fresh NMI bugchecks,
166 private capture files and 144 post-fault artifact paths**. Source bytes remain
unchanged and every retained candidate/output is the full expected marker.
It uses the existing standard-user Windows EnterpriseEval 10.0.26300/local NTFS fixture and the exact restart limits
in [the guest notes](windows-guest.md): NMI plus controlled emulator quit/relaunch,
and separate SIGKILL/relaunch. Host caches stay alive. A matching output or a later
record cannot retroactively qualify an earlier boundary or physical power loss.

| Mode | NMI at rename-success, two observations | All four later flush checkpoints, NMI and SIGKILL |
| --- | --- | --- |
| Buffered | One matching output; one output name lost with matching candidate retained. | All eight retain matching output. |
| Immediate flush after rename | One output name lost before the flush; one matching output before the flush. | All eight retain matching output. |
| Write-through candidate/records | Both retain matching output. | All eight retain matching output. |

All three SIGKILL cases at rename-success also retain matching output. These
finite observations reproduce **variation before the explicit flush** in both
buffered-handle modes. All **24 post-flush cells** retain output, but that does not
establish the necessity/sufficiency of any individual later call or a universal
write-through guarantee. The guest uses its Windows system NTFS volume; OS
background I/O and crash-dump activity share that storage. Restart includes the
named emulator actions, and controlled exit can drain submitted work.

The request mode is consistently recovered from matching records; two records are
present at the earlier checkpoints and three after the observation-file flush.
No missing receipt is promoted into a committed result. The laptop stayed on the
same verified boot, and the guest was normally shut down with all captures retained.
All three [source CI jobs](windows-persistence-ci.json) pass for `dc0e6e1`; CI
checks the native/portable protocols and tooling syntax, not these private guest runs.

Complete namespace/receipt persistence, safely authorized restart finalization/
prune, native storage-error/resource cells and physical-power evidence remain
open. RAW admission under #0027 remains independent; #0023/#0024 are not enabled.

## Retained OD-11 evidence cells

| Cell | Position at this increment |
| --- | --- |
| OD-11-T01 byte/name/no-clobber | Existing 64 cases plus the three-mode data/foreign-winner cases; no wider adapter claim. |
| OD-11-T02 ordinary editing | Native owner-edit cases and prior guest actor controls succeed after exit. |
| OD-11-T03 property checkpoints | Native pre-check and late installed-output changes keep their conflict/recovery outcomes. No continuous same-owner property exclusion. |
| OD-11-T04 staging/storage errors | Existing bounded short/overlong producers and labeled injected failures; native disk-full/device/failed-flush evidence is still missing. |
| OD-11-T05 interruption/receipt ordering | Explicit new barriers and guest comparison; API/flush success and matching records remain observation-only. |
| OD-11-T06 safe restart actions | Bounded inspection and mixed-record refusals; actual safely authorized finalize/prune still unimplemented. |
| OD-11-T07 exact profiles | Windows host NTFS and the named NTFS virtual guest only. Other adapters refuse; physical caches/power boundaries remain explicit. |
| OD-11-T08 RAW gate | #0027's independent opaque/checksum refusal remains; this marker copy cannot enable #0023. |

The next restart-action implementation must reacquire byte/name guards, validate
actual source/output/record identities and ownership against the caller's trusted
operation context, and preserve foreign/missing/changed/inaccessible artifacts.
Successful classification, an editable record or its checksum alone grants no
repair or deletion authority. No secret key or privileged service is inferred.
