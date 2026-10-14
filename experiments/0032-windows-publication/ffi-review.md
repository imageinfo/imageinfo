# Native SDK boundary review

Scope **#0032**, reviewed **2026-10-11**, exact bindings **windows-sys 0.61.2**.
This is a source/API/ownership review with actual Windows actor evidence, not an
independent security audit or production admission. The production crate remains
unsafe-forbidden; this research crate denies unsafe except its one `native` module.

## Why this boundary exists

Win32 managed/std pathname moves cannot rename the candidate while preserving its
read-share-only handle. `SetFileInformationByHandle` acts on the held source instead.
Parent handles must share directory-entry writes while excluding parent DELETE
opens. The ordinary absolute destination works with those guards; the separately
tested directory-relative Win32 form refuses. No undocumented syscall, POSIX flag,
replacement flag, guard release or automatic fallback is used for publication.

`CreateDirectory` followed by opening that name cannot bind the just-created object
atomically. Documented user-mode `NtCreateFile` with a checked parent handle, single
leaf, `FILE_CREATE`, directory/synchronous flags and supplied security descriptor
returns the created handle itself. This specific binding constraint earns the
less usual API; no native call is introduced merely to make the design novel.

## Safety and policy review

Extension reviewed **2026-10-14** for direct #0022 ordinary-output persistence:
the existing `CreateFileW` call optionally adds only `FILE_FLAG_WRITE_THROUGH` for
fresh candidates/records. The private helper accepts a boolean, not caller-supplied
flags. All old callers select false; exclusive creation, access/sharing, noninheritance,
SD/path lifetimes, error capture and one-time handle ownership transfer are unchanged.
No `FILE_FLAG_NO_BUFFERING`, alignment requirement, volume access or new API/feature
is added. Microsoft documents NTFS metadata flushing for write-through requests;
actual profile/restart/power evidence is separate. See
[the comparison and limits](../../docs/write-safety/windows-persistence.md).

| Boundary | Reviewed conditions |
| --- | --- |
| Process-token query and SID text | Query-only owned token; aligned initialized buffer after bounded size query; exact returned size and in-buffer SID checked. Only OS-produced valid terminated SID text is read, then freed. SID text is never emitted. No impersonation/token privilege changes. |
| Security descriptor conversions | Internally generated protected owner-only DACL; counted/terminated UTF-16 outputs owned through `LocalFree`. Canonical owner+DACL is compared from a copy retrieved through the actual live handle with READ_CONTROL. Group/SACL/mandatory labels and other-user token access are not claimed. |
| Atomic directory creation | Pinned `OBJECT_ATTRIBUTES`/`UNICODE_STRING`/`IO_STATUS_BLOCK`; byte counts exclude terminator, capacity includes it. Parent, descriptor and outputs stay live. Exclusive disposition refuses existing leaf, including tested junction. Returned handle transfers once into std `File`; no raw handle cloning/closing outside ownership. |
| Synchronous create completion | SYNCHRONIZE accompanies synchronous nonalert creation. Unexpected pending aborts instead of returning and releasing an OS-pending stack buffer. No async reuse, interruptible OS deadline or successful pending-path qualification is claimed. |
| Private file creation | Live terminated bounded path, noninherited security attributes, CREATE_NEW, explicit read/write/delete/control access and read-only sharing. Handle is converted only after success; failures never overwrite winners. |
| Rename buffer | Pinned SDK fields/offsets, native-word aligned initialized allocation, bounded UTF-16 tail including terminator, byte length excluding it. Flags=0 forbids replacement. Handle is borrowed for synchronous call; ownership stays in std. Error captured without pathname retry. |
| Stream/volume inspection | Fixed initialized aligned 64 KiB stream output; only single default stream accepted, header/name bounds checked. Bound parent handle supplies filesystem name in a fixed buffer. Errors/oversized results refuse instead of guessing. |
| Resource release | LocalFree-compatible outputs have lexical RAII release; successful owned handles use std close. Borrowed process/parent/stage handles are never closed or exported by helpers. |

Ordinary external stage writes/truncation/name deletion/rename are excluded in the
measured interval. Another hard-link name can be created/deleted; default-stream
writes through it are refused. Link count, ACL, timestamps and alternate streams
are mutable property cells. Checks are snapshots, not mandatory exclusion or
authentication; the strict full-profile query therefore refuses before effects.

## Independent ADS actor boundary

Python's CRT open lacks the delete-sharing mode needed to exercise a new stream
while this holder has DELETE access. The test-only `ctypes` actor uses explicit
SDK argument/return types for `CreateFileW`, `WriteFile` and `CloseHandle`:

- Only a named stream of an owned marker file is targeted; CREATE_NEW never
  overwrites a preexisting stream. Sharing explicitly includes read/write/delete.
- A live 12-byte buffer supplies exactly 11 authored bytes, a live DWORD receives
  the count, and NULL OVERLAPPED keeps the write synchronous.
- Invalid-handle/error results are checked; the successful actor handle is closed
  in `finally`. No user code, callback, native structure parser or privilege is used.

This actor is a concrete OS contender, not an independent metadata engine or audit.

## Sources and supported observation

Live primary references viewed **2026-10-11**; no immutable documentation revision
asserted. Binding declarations/features were read from the exact admitted crate.
No upstream implementation or manual text is copied into imageinfo.

- [NtCreateFile](https://learn.microsoft.com/en-us/windows/win32/api/winternl/nf-winternl-ntcreatefile)
- [SetFileInformationByHandle](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-setfileinformationbyhandle) and [FILE_RENAME_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_rename_info)
- [GetSecurityInfo](https://learn.microsoft.com/en-us/windows/win32/api/aclapi/nf-aclapi-getsecurityinfo)
- [SDDL to descriptor](https://learn.microsoft.com/en-us/windows/win32/api/sddl/nf-sddl-convertstringsecuritydescriptortosecuritydescriptorw), [descriptor to SDDL](https://learn.microsoft.com/en-us/windows/win32/api/sddl/nf-sddl-convertsecuritydescriptortostringsecuritydescriptorw), [SID to text](https://learn.microsoft.com/en-us/windows/win32/api/sddl/nf-sddl-convertsidtostringsidw)
- [GetTokenInformation](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-gettokeninformation)
- [GetVolumeInformationByHandleW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getvolumeinformationbyhandlew), [GetFileInformationByHandleEx](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getfileinformationbyhandleex)
- [CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew), [WriteFile](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-writefile), [LocalFree](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-localfree)
- [Pinned SDK crate](https://docs.rs/windows-sys/0.61.2/windows_sys/)

Measured x64 local NTFS, Windows 11 build 26200. Privileged device/mount remapping,
raw-volume access, cloud/remote/removable/provider behavior and complete namespace
persistence are excluded/unqualified. File/directory flush call success is not
power-loss survival, authenticated custody or permission to use this on media.
