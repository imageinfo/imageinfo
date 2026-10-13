# Scoped overlapped Windows boundary review

Reviewed **2026-10-13**, Rust **1.99.0**, `windows-sys` **0.61.2**. Root production
unsafe policy and dependency graph are unchanged. The separate research crate
reuses the project-owned [#0032 boundary](../0032-windows-publication/ffi-review.md)
unchanged. It adds the SDK `Win32_System_Ioctl` feature without a package/version
change; [exact admission and notices](../../docs/write-safety/source-oplock-dependencies.json)
remain distinct from approval of this new API sequence.

## Ownership and pointers

- `CreateEventW` receives null security/name pointers and returns a real owned
  manual-reset event. Each event is closed once through `OwnedHandle`.
- `DeviceIoControl(FSCTL_REQUEST_OPLOCK)` receives initialized SDK input/output
  layouts and exact sizes. A pending request is the documented grant observation;
  synchronous success or another error is not treated as a granted exclusion.
- Input, output and `OVERLAPPED` stay in private boxed `UnsafeCell` storage whose address does
  not change when the owner moves. No output is read while the request is pending.
  The SDK method receives raw field pointers; no overlapping Rust borrow is held
  across asynchronous completion. File and event remain owned for that interval.
  Interior mutability permits kernel updates while owner methods borrow the
  containing structure; raw pointers do not create references to pending output.
- A zero-time event query is followed by successful `GetOverlappedResult` before
  output is read. Reported structure version/length and returned length are checked.
  Break/ACK flags are observations; they cannot authorize publication or repair.
- Drop cancels only the exact pending request and drains its completion before
  boxed storage/events are released. Racing `ERROR_NOT_FOUND` does not skip the
  drain. The holder's duplicated file object closes with the original holder.
- Bounded 65,537-byte marker reads use a separate event and `UnsafeCell<OVERLAPPED>` at offset
  zero. Read completion is drained before stack storage/buffer access or release.
  The default stream is read through the held object rather than reopening a name.
- No callback, kernel pointer interpretation, handwritten ABI layout, foreign
  ownership transfer, privilege adjustment or source-property setter is introduced.

Blocking completion is required to preserve pointer lifetime. The qualifier's
process watchdog bounds the experiment if a driver stalls; the worker does not
claim a hard native I/O deadline. Process termination and actual OS/power loss are
different cells. Ordinary existing-source opening is followed by initial read and
property checks, then a request: this is **not atomic create-with-oplock admission**.
The earlier interval remains unqualified and cannot be hidden by a final check.

## Source/API basis

Primary Microsoft documentation observed **2026-10-13**:

- [FSCTL_REQUEST_OPLOCK](https://learn.microsoft.com/en-us/windows/win32/api/winioctl/ni-winioctl-fsctl-request-oplock):
  request layouts, pending request/break completion and RH/RW/RWH flag meanings.
- [Breaking oplocks](https://learn.microsoft.com/en-us/windows-hardware/drivers/ifs/breaking-oplocks)
  (updated 2024-12-19): some operations wait for acknowledgment; advisory breaks
  differ. This documentation does not establish exclusion of every property.
- [Types of oplocks](https://learn.microsoft.com/en-us/windows/win32/fileio/types-of-opportunistic-locks):
  atomic create-with-oplock is a separate procedure and is not implemented here.
- [CancelIoEx](https://learn.microsoft.com/en-us/windows/win32/api/ioapiset/nf-ioapiset-cancelioex)
  (updated 2021-10-13): a cancellation request does not establish completion;
  asynchronous storage must remain live until completion is known.
- [GetOverlappedResult](https://learn.microsoft.com/en-us/windows/win32/api/ioapiset/nf-ioapiset-getoverlappedresult):
  exact file/request pairing and completion wait semantics.

The actor's CreateFile/time/security/read/write signatures remain the reviewed
#0033 signatures. Added late-alias operations use `os.link` and then the explicit
alias path; only new owned markers are affected. No upstream implementation or
personal media is imported. This scoped source/API review is not an independent
maintainer signoff, full threat proof or production integration review.
