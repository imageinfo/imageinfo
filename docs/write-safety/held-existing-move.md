# Held existing-object no-replace move

Status: #0195 bounded implementation and preliminary native mechanism evidence,
2026-10-16. The production-boundary crate implements one same-parent move of
the **same existing object** to another ordinary name. No storage profile,
metadata writer, occupied-target replacement, durable commitment, restart repair,
source-deletion workflow or grouped-operation capability is admitted.

The requirement mapping is specific: WS-009 binds expected identity, retained
default bytes and actual parent/name custody; WS-010 rejects initial aliases,
case/reparse configurations and atomically refuses a destination winner; WS-011
preserves live properties by retaining the same object rather than merging or
cloning them; WS-018 supplies the guarded same-volume rename requirement.
WS-012's immutable recovery-before-replacement is not discharged or weakened.

## Exact preservation boundary

[WS-018](README.md) requires guarded identity and no-clobber semantics for a
same-volume rename. This operation retains the existing object; it does not
replace it with a candidate, create an immutable original copy, or replay an old
property snapshot. [WS-012](README.md)'s original-before-replacement obligation
and the missing replacement guarantees in the
[#0193 boundary review](existing-target-boundary.md) remain unchanged.
[OD-11 option A](practical-output-policy.md) is not applied to existing targets.

This distinction matters for strict preservation. A permitted timestamp, security
or stream edit changes the very object subsequently moved. Keeping that object
preserves the edit; copying a stale property snapshot onto a different object
would not. No setter, ACL change, security merge, owner change, timestamp reset,
stream copy or property rebaseline occurs in this operation. Snapshot equality
is an acquisition expectation, not permission to restore an earlier state.

The primitive does **not** promise continuously frozen properties or link topology.
Initial multiple links and named streams are refused by this bounded profile.
A later actor-created alias, stream or security edit remains attached to the same
object; the primitive never converts it into an independent backup or discards it.
Default-stream and source-name protection remain independent requirements. This
reasoning does not authorize replacement, property cloning or an existing-target
checkpoint exemption. Required properties beyond this same-object operation still
need their own applicable evidence.

Creation and last-write times remain unchanged by the measured ordinary rename;
the preopened time actor's changed last-write value remains the installed value.
Reads may have normal access-time effects. NTFS change-time and name/index metadata
have OS semantics; no change-time preservation is promised. No real content edit
is performed, so there is no deliberate modification-time update.

## Acquisition, ownership and call

The implementation is
[`HeldExistingMove`](../../crates/imageinfo-windows-storage/src/existing_move.rs).
It accepts bounded ordinary absolute DOS paths on a local fixed NTFS volume,
two distinct ASCII ordinary components with the same parent, and a supplied
expected actual source observation. Case-only moves, alternate spellings,
reparse paths, initial multi-link files, initial named streams, unsupported
attributes, read-only sources and files above the 64 MiB comparison bound refuse
before a rename call. Directory enumeration is limited to 4,096 entries.

All ancestors through the common parent are retained with read/write sharing and
without delete sharing. They remain actual non-reparse directories with supported
case behavior. Source acquisition uses `OpenOptions` with access
`GENERIC_READ | DELETE | READ_CONTROL`, sharing `FILE_SHARE_READ`,
`FILE_FLAG_OPEN_REPARSE_POINT`, and **OPEN_EXISTING**. No creation or truncation
flag is set. The ordinary Rust Windows open boundary supplies this acquisition;
it is distinct from the fresh-file `CREATE_NEW` constructor.

Successful acquisition returns one owned `File`. Its DELETE access authorizes
the retained handle's rename while its sharing rejects incompatible existing
default-stream write or delete handles and later ordinary write/delete opens.
It retains the expected volume/file identity and exact default-stream bytes.
Borrowed handles remain owned by the operation across the synchronous SDK call
and subsequent inspection. No pathname reopen supplies the rename source.

The existing reviewed `FileRenameInfo` helper uses flags zero, null
`RootDirectory`, and a bounded absolute destination. It conditionally refuses an
occupied name, including a different object containing identical bytes. It uses
no replace/POSIX/readonly-override flags, weaker-sharing retry, cross-volume
copy/delete fallback or speculative restore. Drop closes handles and retains
all names/artifacts.

The primary contracts are Microsoft's
[CreateFileW sharing/access rules](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew),
[FILE_RENAME_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_rename_info),
and [File streams](https://learn.microsoft.com/en-us/windows/win32/fileio/file-streams),
reviewed 2026-10-16. In particular stream sharing is per stream, while delete
acquisition also checks open streams. The driver-level
[extended rename flags](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntifs/ns-ntifs-_file_rename_information)
describe open-target POSIX replacement; their existence alone neither proves nor
disproves compatibility with this exact non-delete-sharing hold. The shared
[SDK boundary review](../../crates/imageinfo-windows-storage/SDK-REVIEW.md)
records the exact adversarial scope and mapping/name limits. No admin, kernel,
raw-volume or privileged actor claim follows from these finite schedules.

The actual shared critical probes also exercise this exact DELETE-capable,
read-share-only existing-object acquisition. Extended POSIX replacement of its
held source name refuses with sharing violation 32; a preexisting writable mapping
whose original file handle has closed also causes acquisition refusal 32. The
same probes separately exercise the read-only source guard. These finite native
observations close the measured compatibility questions; they are not a proof
against arbitrary mapping/provider/kernel behavior or permission to weaken guards.

## Result and uncertainty boundary

`execute` issues at most one rename. Cancellation and failed preflight return
`NotAttempted`. Once a call is issued, the attempt flag stays set before entering
the OS boundary; subsequent execution only inspects and cannot replay the call.
An ambiguous result never initiates rollback, source removal or cleanup.

| Observation | Result |
| --- | --- |
| No rename call issued | `NotAttempted` |
| Call failed; retained source identity/default bytes remain at the old name; destination is observably absent or another identity | `ObservedNoEffect` |
| Call succeeded; same held identity/default bytes are at the destination; old name is observably absent | `ObservedMoved` |
| Lineage/content/binding checks fail, access prevents inspection, or result/bindings contradict each other | `RecoveryRequired` |

`ObservedNoEffect` is the verified rename/default-byte/name result, not a claim
that independent property actors were inactive. Their edits are not rolled back.
Neither positive observation is a persistence acknowledgement. The old name can
become available after rename; a foreign reinsertion causes uncertainty rather
than deletion of that new object. Losing the live operation/process loses its
custody: a saved path or snapshot does not recreate this authority.

## Twelve authored native cases

The dedicated [native tests](../../crates/imageinfo-windows-storage/tests/existing_move.rs)
exercise the production crate. Authored files are created in fresh private roots,
then **all creator/root handles are closed** before existing-object acquisition.
This setup avoids reliance on creation custody and is not promotion of fresh-file
evidence as an existing-object test.

| Case | Actual bounded assertion |
| --- | --- |
| 01 normal | Same identity, bytes, creation/write times, attributes and owner/DACL at new name; old absent |
| 02 foreign collision | Failed no-replace call; foreign bytes/identity remain; source remains |
| 03 same-byte collision | Equal bytes do not permit replacing a distinct destination identity |
| 04 directory collision | Existing directory and source remain |
| 05 source alias | Initial hard-linked object refuses acquisition |
| 06 preopened writer | Existing incompatible content writer refuses acquisition |
| 07 preopened rename handle | Existing incompatible DELETE access refuses acquisition |
| 08 source substitution | Ordinary source rename and overwrite actors refuse while custody remains; held object moves |
| 09 ancestor move | Ordinary parent rename refuses; held source moves |
| 10 property actor | Preopened attribute handle sets mtime after acquisition; same changed value survives rename |
| 11 cancellation | No call issued; original name/properties remain; destination absent |
| 12 lost response | Caller discards first return; live inspection identifies actual move; later old-name winner yields recovery-required and remains retained; execution never replays |

All twelve pass in the authorized ordinary-token Windows native run, with retained
artifacts and initial identity/property observations kept privately. A restricted
sandbox setup denied hard-link creation; that was not counted as a passing alias
case. The successful native run uses the actual host API boundary. Tests audit
retained pathname bytes/properties after closing worker handles; the integrated
handoff also requires independent retained-artifact inspection. No VM-off,
crash/power, persistence or real-media experiment is claimed by this run.

The exact production caller and final frozen integration require their own later
qualification. This finite mechanism evidence does not complete #0201 ordinary/
case-only planning, #0202 cycles, #0194 replacement, #0196 property policy, or
#0026's full original scope. The existing new-output no-replace tests remain
separate regressions.
