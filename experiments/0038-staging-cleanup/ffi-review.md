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

## #0022 caller-directed restart reuse

Reviewed **2026-10-14** for the bounded
[ordinary-owner marker restart actions](../../docs/write-safety/windows-restart-actions.md).
The SDK structure, information class, borrowed-handle call and synchronous
lifetime contract remain unchanged. No new native API, dependency, feature or
root production unsafe permission is added.

`ordinary-restart-prune` extends the caller contract to a previously
exclusive-created unpublished candidate and records. The live supervisor captures
their identities, bytes, properties and exact fixed names while the creator's
guards are held, then retains that explicit caller context outside the mutable
transaction. At restart, safe protocol code freshly opens and retains the exact
objects with DELETE access and byte/name guards, and revalidates all bindings,
private-owner properties and unpublished scope before disposition. Source and
root are retained. This path does not delete an installed output or accept an
uncertain publication attempt as unpublished.

The caller must preserve the supervisor's history that the original worker was
stopped before its namespace call was permitted. An earlier exported context is
not valid prune authority if publication was later attempted; absent output alone
does not resolve that uncertainty. This history is an explicit caller precondition,
not something the disposition API or JSON parser can authenticate.
The exported `stoppedBeforePublication` field is false. Prune requires the
supervisor's explicit true attestation after the proven stop; postpublication
contexts cannot carry it. Changing this field asserts caller knowledge and
authority, rather than turning arbitrary JSON into a verified permission token.

The supplied context represents the caller's authority; parsing JSON does not
authenticate that caller or establish where the context was retained. Editable
transaction checksums, classifications and directory entries cannot substitute
for that authority. Missing, foreign, changed or inaccessible artifacts refuse;
there is no pathname fallback, recursive deletion, ACL repair or privilege change.

Deletion marking and eventual removal remain distinct, including compatible
reader deferral and partial/error reporting. The separate restart-observe path
does not call disposition. Existing live cleanup rules remain unchanged, and
legacy `ordinary-prune`/`ordinary-finalize`/`ordinary-admit` still refuse. Qualified
commitment, persistence and production repair/profile authority remain gated.

Primary Microsoft references rechecked **2026-10-14**:

- [SetFileInformationByHandle](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-setfileinformationbyhandle)
  (visible update 2021-10-13): the handle must carry DELETE access and the SDK
  structure and information class must agree; failure is reported without a
  different deletion mechanism.
- [FILE_DISPOSITION_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_disposition_info)
  (visible update 2024-02-22): the Boolean member requests deletion on the supplied
  object handle. This worker does not use `FILE_FLAG_DELETE_ON_CLOSE`.

The [61-case native restart ledger](../../docs/write-safety/windows-restart-native.json)
includes hostile-marker refusal, partial action and compatible-reader deferral
observations for this caller path. The old live-cleanup tests alone do not qualify
it. Guest interruption/action evidence remains separate from source/API review;
no independent maintainer signoff or complete profile proof is inferred.
