# Windows storage SDK boundary review

**#0166, 2026-10-16.** This is the production-owned primitive boundary for the
[new-output contract](../../docs/write-safety/new-output-contract.md), isolated
from the root crate's unsafe-forbidden source. It does not admit a storage
profile, metadata writer, committed result, or restart action. The separate
[existing-object move](../../docs/write-safety/held-existing-move.md) is another
safe consumer of the same private helpers.

## Ownership, access and namespace

`GuardedSource` owns a read/control, read-share-only `OPEN_EXISTING` handle and
all ordinary DOS ancestors. Writable handles/mappings must make acquisition
refuse. The library never changes the source ACL, bytes, attributes or times.
Reading can affect OS-managed access metadata; last-access time is outside the
captured preservation fields. Existing source owner/DACL is observed and retained,
not replaced with the private-artifact policy.

`PrivateRoot` creates a new directory atomically relative to the actual writable
held parent. Source/parent lineage is acquired root-first; directory handles
share read/write and exclude delete. Reparse components and case-sensitive
directories refuse. Exact directory enumeration rejects source case and 8.3
aliases; each enumerated directory has at most 4,096 entries. Ordinary absolute
DOS paths are bounded to 200 UTF-16 units; leaves to 100 UTF-8 bytes. UNC, device,
extended namespace, stream, wildcard, dot-component and reserved-device names
refuse. Volume inspection requires NTFS and the drive-type query requires fixed
media classification. This classification is not controller, bus, cloud-filter,
or storage-profile qualification. Privileged DOS/mount remapping, kernel/admin
attackers, and changing the configured storage stack are outside this boundary.
Compressed, encrypted and offline containing-parent inheritance refuses before
root creation. Explicit unsupported policy conditions return typed
`io::ErrorKind::Unsupported`; actual native I/O errors keep their OS provenance.

The private owner/DACL is supplied during exclusive creation: protected current
process user owner, one full-control owner ACE, no inherited ACE. Files are
buffered synchronous `CREATE_NEW` handles with read/write/delete/control access,
read-only sharing, and no inheritance. They are ordinary owner-editable files
after release, without sealing or OWNER RIGHTS restrictions. The safe API never
exports a raw `File`, raw handle, mutable path, caller-selected flags, descriptor,
or pathname-to-owned-handle conversion.

Publication uses one `SetFileInformationByHandle(FileRenameInfo)` on the held
candidate, absolute same-root destination, zero flags and null `RootDirectory`.
No replacement, rooted-form retry, pathname source reopen, copy/delete fallback,
or guard release occurs. An issued call marks publication possible before entry;
failure retains uncertainty and retry refuses. An occupied winner remains.
`Drop` closes handles only and retains all names, partial files and directories.

## Every unsafe and SDK operation

The crate denies unsafe code except `src/native.rs`; unsafe operations in unsafe
functions are separately denied. Every unsafe block has a local safety comment.
No research CLI, supervisor, record importer or recovery implementation is copied.
The narrowed OS mechanics derive from the reviewed
[#0032 wrapper](../../experiments/0032-windows-publication/src/native.rs) and
[its review](../../experiments/0032-windows-publication/ffi-review.md).

| Operation | Pointer, ownership and failure review |
| --- | --- |
| `OpenProcessToken`, `GetCurrentProcess`, `GetTokenInformation` | Query-only owned token; process pseudo-handle borrowed. Bounded sizing query, initialized native-word-aligned buffer, checked returned length and SID pointer range. OS-produced SID remains live during conversion. No token/privilege changes. |
| `ConvertSidToStringSidW` | OS SID conversion; terminated output read to at most 192 UTF-16 units and released exactly once through `LocalMemory`. SID text stays in private object snapshots, never diagnostics. |
| Security descriptor conversions and `GetSecurityInfo` | Internally generated terminated SDDL; OS-owned descriptor/string allocations released by `LocalFree` RAII. Canonical owner+DACL from live READ_CONTROL handles is compared exactly. No source setter, group, SACL, label or privilege API. |
| `NtCreateFile`, `RtlNtStatusToDosError` | Checked single leaf; pinned SDK `OBJECT_ATTRIBUTES`, `UNICODE_STRING`, `IO_STATUS_BLOCK`; live parent/descriptor/name/output throughout synchronous `FILE_CREATE`. Noninheritance, explicit private descriptor and returned handle close the create/open race. Error mapping preserves failure. Unexpected pending aborts this process rather than release OS-pending stack storage; that exceptional path is not positively qualified. |
| `CreateFileW`, `File::from_raw_handle`, `OwnedHandle::from_raw_handle` | Exclusive create with live bounded terminated path/security; only API-success handles transfer once into RAII ownership. Failures return before conversion. Source/observer opens use safe `OpenOptionsExt` with fixed access/sharing/flags. |
| `GetFileInformationByHandleEx(FileStreamInfo)` | Fixed initialized native-word-aligned 64 KiB buffer; only the exact single default stream is accepted for ordinary files. Directory no-stream `ERROR_HANDLE_EOF` is accepted; named streams, malformed/oversized results and other errors refuse. SDK header and 14-byte default-name tail are bounded inside that allocation. |
| `GetFileInformationByHandleEx(FileCaseSensitiveInfo)` | Initialized correctly sized SDK output. Any nonzero flag or query error refuses; no assumption of case-insensitive behavior on unsupported versions. |
| `GetVolumeInformationByHandleW`, `GetDriveTypeW` | Filesystem queried from actual held volume object into fixed initialized UTF-16 output. Drive query receives only checked terminated ordinary drive-root spelling. No volume/device handle or privileged flush. |
| `SetFileInformationByHandle(FileRenameInfo)` | Pinned offsets, initialized native-word-aligned bounded buffer, exact counted UTF-16 destination tail. Zero flags forbid replacement. Borrowed held object survives synchronous call; errors captured without fallback. |
| `LocalFree` | Only documented compatible OS allocations enter `LocalMemory`; lexical drop frees once. Borrowed pointers never escape their owner's lifetime. |
| Safe file methods, `winapi_util::file::information` | Owned handles supply identity, bounded bytes and properties. `sync_all` results are returned individually, never interpreted as durable commitment. No raw handles escape and clones are not exposed. |

Production SDK features exactly match #0032: `Win32_Foundation`,
`Win32_Security`, `Win32_Security_Authorization`, `Win32_Storage_FileSystem`,
`Win32_System_Threading`, `Win32_System_IO`, `Wdk_Foundation`, and
`Wdk_Storage_FileSystem`. The only external packages are `winapi-util =0.1.11`,
`windows-sys =0.61.2`, and transitive `windows-link 0.2.1`, already in the root
[exact archive/notice inventory](../../docs/foundation/dependencies.json).
The [retained MIT notices](../../THIRD_PARTY_NOTICES.md) continue to apply.
This change adds no external package identity or vendored implementation.

## Checks and finite native evidence

Immutable snapshots bind volume/file identity, size, link count, creation and
last-write times, attributes and canonical owner/DACL. Source and artifact checks
compare complete bounded bytes (maximum 64 MiB) before/after property checks;
nondefault streams, extra links and unsupported file types/attributes refuse.
Root checks bind its identity, creation time, owner/DACL, indexing preference,
supported directory attributes and no named streams. Directory last-write/size
changes caused by the protocol's own children are not source-file properties.
Root/source/artifact check failures latch terminal conflict; a property edit and
reversion cannot resume after an observed conflict. Option A makes no continuous
same-owner property exclusion promise. Protocol consumers must invoke checks at
every required boundary and account for logical bytes before construction.

Five actual Windows integration tests in `tests/native_guards.rs` cover source
writer/name exclusion, parent/ancestor rename refusal, exact no-clobber winner,
held-object identity, post-drop ordinary owner editing, acquisition with an open
writer, wrong case, hard links, file ADS, size bounds, readonly/timestamp conflicts,
timestamp reversion, directory ADS and junction-parent refusal. Retained artifacts
are independently reopened by pathname after handle release and checked for exact
expected bytes, names, source write time, and foreign-winner retention.

Two additional native unit schedules issue a test-only `FileRenameInfoEx` POSIX
replacement actor. Both read/control and read/delete/control source holds refuse
the actual actor with sharing violation 32 on the measured host. Production
rename never generates these actor flags. `tests/native_actors.py` and the
`guard_probe` example additionally retain a writable mapping after closing its
original file handle: both exact acquisition access modes refuse with error 32.
An authored ADS actor succeeds while the source is held; its next check refuses
and default-stream bytes remain unchanged. These results do not promote property
changes to continuously excluded events.

A third native unit schedule opens a fresh candidate with WRITE_DAC and supplies
an owner-only DACL with changed inheritance flags. `GetSecurityDescriptorDacl`
borrows its ACL from the retained converted descriptor; test-only
`SetSecurityInfo` uses that live ACL and the retained actor handle. The subsequent
candidate check refuses and the independently reopened candidate bytes match.
This is an authored candidate ACL edit; no existing source ACL is changed and no
production security setter is exposed.

The test-only Python API boundary uses explicit ctypes signatures for
`CreateFileW`, `CreateFileMappingW`, `MapViewOfFile`, `UnmapViewOfFile`, and
`CloseHandle`. Only authored fixtures are mapped; pointer writes stay within the
known nonempty mapping, which remains live until unmap. Handles/views close in
`finally`. Child commands and waits are bounded to ten seconds after startup;
there is no native-I/O interruptibility/deadline claim. The junction test creates
one explicit authored junction through Windows `mklink /J` and never traverses it
for mutation. No recursive deletion is performed.

Evidence concerns this actual native Windows host, not the specified evaluation
guest or an admitted profile. No VM, crash, power, device flush, source-media,
source ACL, privilege, process-kill or recovery effect is executed. Profile,
native error, VM-off, concurrency and independent format admission obligations
remain with their owning tickets. Unsupported platforms return before effects.

## Primary API basis

Microsoft references checked 2026-10-16; live pages have no immutable revision:
[CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew),
[GetFileInformationByHandleEx](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getfileinformationbyhandleex),
[GetDriveTypeW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getdrivetypew),
[FILE_RENAME_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_rename_info),
and [ordinary namespace grammar](https://learn.microsoft.com/en-us/windows/win32/fileio/naming-a-file).
The preexisting #0032 review supplies the unchanged token, security, native-create
and resource-release references. Documentation supports API reasoning, not
universal persistence or profile admission.
