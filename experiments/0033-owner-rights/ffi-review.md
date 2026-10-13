# OWNER RIGHTS boundary and actor review

Scope **#0033**, reviewed **2026-10-13**, exact `windows-sys 0.61.2`.
This extends [#0032's project-owned ABI review](../0032-windows-publication/ffi-review.md),
not the root production unsafe policy. It is source/API/ownership review and actual
actor qualification, not an independent security audit or complete profile admission.

The ordinary `PrivateSecurity::current()` still creates exactly the same protected
current-user owner/DACL. Fixed research constructors add an OWNER RIGHTS deny ACE
before the current-user full-access allow. Property-only mask `0x000c0110` covers
WRITE_DAC, WRITE_OWNER, FILE_WRITE_EA and FILE_WRITE_ATTRIBUTES; sealed mask
`0x000c0116` additionally covers FILE_WRITE_DATA and FILE_APPEND_DATA. These are
internally generated, not imported SDDL, arbitrary callbacks or runtime profile flags.
The SDK creates new objects with the descriptor supplied in their creation call.

Microsoft documents OWNER RIGHTS as controlling the owner's otherwise implicit
READ_CONTROL/WRITE_DAC. The allow still supplies read/control access. Actual creator
write/rename/flush and actor denials are measured, not inferred from the string.
Retained security restoration and post-seal exact-policy mismatch are observed
limits, not permission to weaken comparisons or use elevated recovery.

`create_file_access` only parameterizes SDK desired access for fixed reviewed worker
modes. `create_file` delegates with its original mask. Same wide-name bounds,
CREATE_NEW disposition, noninherited handle, read-only sharing and lexical `File`
ownership are retained. No raw borrowed handle is cloned, closed twice or exported.

`apply_to_owned_marker` uses documented GetSecurityDescriptorDacl on the retained
OS-converted descriptor, with live initialized BOOL/ACL outputs. It refuses a missing
or null DACL. SetSecurityInfo receives the live caller-owned marker handle and a
borrowed ACL that remains allocated for the synchronous call; only protected DACL
information is changed. It checks the return code and reuses exact live-policy
comparison. It never sets an owner, group, SACL, privilege, volume or system setting.
Only the explicit after-open/holder tests call it on their newly created markers.

The Rust worker uses safe std control/ownership/observations outside that native
module. Atomic root creation, held-source rename, stream inventory and filesystem
inspection reuse #0032's reviewed buffer/ownership conditions. No new native async
or pending-I/O path is introduced. Unsupported constructor pending still aborts;
it is not claimed as a tested successful branch.

The independent Python actor declares exact ctypes WinDLL signatures for CreateFileW,
SetFileTime, SetFileAttributesW, ReadFile/WriteFile, CloseHandle, descriptor conversion,
GetSecurityDescriptorDacl, SetSecurityInfo and LocalFree. Only fixed owned marker
names and the fixed new `:probe` stream are targeted. Sharing includes read/write/
delete to expose actual policy rather than a CRT sharing artifact. DACL opens request
READ_CONTROL plus WRITE_DAC. The first narrower WRITE_DAC-only actor was insufficient
for this call composition; its earlier results remain retained, and final ordinary
DACL mutation succeeds while newly restricted opens refuse.

FILETIME is an initialized two-DWORD fixed invented timestamp. Read/write buffers
stay live; reads are 65,536 bytes, marker writes are 14 authored bytes and NULL
OVERLAPPED makes calls synchronous. Output counts are initialized and checked for
reads; audit captures the exact resulting ADS sizes/hashes. Successful real handles
are closed in `finally`; LocalFree owns only API-returned descriptor allocations.
Preopened actors acquire only owned-marker time/control rights and wait for a fixed
word; no source/media path or serialized record can authorize these operations.

Local environment: Windows 11 x64 build 26200, ordinary local NTFS, unchanged DOS
mapping, same-user ordinary process tokens. Elevated privilege, device/raw-volume,
mount/provider/cloud/removable, another-user token and SACL/mandatory-label threats
are not qualified. No original/source property mutation, host/WSL/guest crash,
pattern cleanup or broad permission restoration is performed.

Primary references, viewed **2026-10-13**, living documentation; no upstream code copied:

- [Microsoft security identifiers](https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/manage/understand-security-identifiers)
  for OWNER RIGHTS `S-1-3-4` and implicit owner rights.
- [File security/access](https://learn.microsoft.com/en-us/windows/win32/fileio/file-security-and-access-rights)
  and [new-file/open behavior](https://learn.microsoft.com/en-us/windows/win32/fileio/creating-and-opening-files).
- [GetSecurityDescriptorDacl](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-getsecuritydescriptordacl),
  [SetSecurityInfo](https://learn.microsoft.com/en-us/windows/win32/api/aclapi/nf-aclapi-setsecurityinfo),
  [SetFileTime](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-setfiletime).
- [Pinned SDK](https://docs.rs/windows-sys/0.61.2/windows_sys/), with the existing admitted
  security/filesystem features and archive identity; no new registry version.
