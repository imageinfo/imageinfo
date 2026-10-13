# Owned-file disposition boundary

Reviewed **2026-10-13**, Rust **1.99.0**, `windows-sys` **0.61.2**. The separate
research crate reuses the unchanged [#0032 boundary](../0032-windows-publication/ffi-review.md)
and [#0033 fresh guards](../0033-owner-rights/ffi-review.md). Its
[14-package/15-notice graph](../../docs/write-safety/staging-cleanup-dependencies.json)
is identical to #0033; root production dependencies and unsafe policy are unchanged.

One small module calls `SetFileInformationByHandle` with `FileDispositionInfo` and
the SDK's `FILE_DISPOSITION_INFO { DeleteFile: true }`. The SDK layout is used
directly (its Boolean field is Rust `bool`); size comes from `size_of`. The local
initialized structure, immutable pointer and borrowed real file handle survive the
synchronous call. There is no transferred allocation, callback, async buffer,
handwritten ABI layout or extra handle close.

The caller owns the file from exclusive creation and retains its handle throughout
live checks. Ordinary cancellation is the only deletion path. Namespace-call entry
permanently refuses this path, regardless of later syscall success/error. No record
can manufacture phase or ownership authority. The missing-DELETE fixture expects
the OS to refuse, with no pathname fallback. Interrupted/partial cleanup preserves
the root and reports uncertainty; retries and restart repair are not implemented.

Marking is distinct from removal: the creator closes only its own handle, and
compatible readers can retain the object/name until their handles close. The
qualifier measures that deferral and preserves foreign reinsertion/extra entries.
The owner-rights restrictions apply only to newly created staging artifacts, not
source originals or ordinary product output policy. No recursive/pattern cleanup,
privilege, owner reassignment, elevation or encryption is introduced.

Primary Microsoft documentation observed **2026-10-13**:

- [SetFileInformationByHandle](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-setfileinformationbyhandle)
  (updated 2021-10-13): handle permission, information-class/structure pairing and
  return/error contract; delete disposition requires DELETE access.
- [FILE_DISPOSITION_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_disposition_info)
  (updated 2024-02-22): Boolean delete member and its handle-disposition purpose.

This is scoped SDK/source review, not independent maintainer signoff or a complete
storage-profile proof. Driver/provider errors, OS crash, physical power loss,
directory removal, restart authority and postpublication recovery remain separate.
