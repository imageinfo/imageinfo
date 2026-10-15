# Explicit RAW–XMP path pairing

#0082 implements a finite, read-only path resolver. The caller selects both the
RAW and existing sidecar paths. The resolver does not discover sidecars, inspect
CR3 or XML contents, validate extensions, or establish that metadata describes
the selected photo. Format/content validation remains a separate boundary.

`pairing::resolve_pair(raw, Some(sidecar))` returns canonical `raw_path` and
`sidecar_path` with `association: "explicit_paths"`. Passing `None` refuses with
`EXPLICIT_SIDECAR_REQUIRED`, even when a same-stem `.xmp` exists. A missing
selected sidecar refuses with `SIDECAR_MISSING`; it is never created and a nearby
sidecar is never substituted.

The implemented CLI is `imageinfo sidecar pair RAW --sidecar XMP`, with contextual
help at `sidecar` and `sidecar pair`. Omitting `--sidecar` gives the same explicit
selection refusal. JSON output uses the existing envelope with a snapshot
`{"schemaVersion":1,"kind":"explicit-pair","pair":...}` and reports no mutation
effects or created artifacts.

Different stems and directories are permitted because the association is explicit.
For example, selecting `camera.CR3` and `notes/custom.xmp` remains explicit even
with `camera.xmp` or another RAW family beside the RAW. The resolver makes no
choice among same-stem candidates. No sidecar synchronization or write capability
follows from a successful path observation.

## Aliases and finite refusal rules

Both inputs must exist and resolve to regular files. Canonicalization follows
symlinks; identical canonical paths refuse with `PAIRING_SAME_FILE`. Distinct
paths are opened read-only and compared while both handles remain open, so
hard-link aliases also refuse. Distinct files with identical bytes remain distinct.

The caller-selected leaves and resolved leaves each receive a directory-entry
scan. More than one ASCII case-equivalent entry, or no matching entry, refuses
with `PAIRING_CASE_AMBIGUITY`. Each scan examines at most 4,096 entries; an
additional entry refuses with `PAIRING_DIRECTORY_LIMIT`. This is at most four
bounded parent scans, with no recursive traversal. Selected non-ASCII leaf names
refuse with `PAIRING_NAME_UNSUPPORTED`: Unicode case equivalence is not inferred.
Ancestor names are resolved by the filesystem rather than case-normalized by us.
I/O failures refuse with `PAIRING_IO`; directories refuse with `PAIRING_NOT_FILE`.
Unsupported identity platforms refuse rather than treating distinct text paths
as proof of different physical files.

This is an observation of a quiescent filesystem, not a guard against adversarial
namespace changes. Canonicalization, enumeration and opening are separate calls;
the returned paths carry no retained handles or continuing identity guarantee.
Callers must not use this result as write admission, synchronization authority,
or a substitute for later format and filesystem checks. The resolver performs
no writes, creates no target, and changes no requested permissions or timestamps;
ordinary OS access-time accounting is outside that claim.

## Identity dependency review

Reviewed on 2026-10-15: exact `same-file` 1.0.6, published source revision
`5799cd323b8eefd17a089c950dac113f66c89c9e`. Its safe `Handle::from_file` API takes
ownership of our read-only `std::fs::File` values. Unix compares device/inode;
Windows compares volume serial and 64-bit file index with both handles live.
The Windows implementation warns that filesystems such as ReFS can have wider
identifiers, producing conservative false-same refusals. Its public prose mentions
file size, but the reviewed 1.0.6 equality implementation uses only volume/index;
the implementation determines this boundary. Network filesystems, ReFS, unusual
identity providers and concurrently changing namespaces are not qualified here.

The locked Windows graph adds `winapi-util` 0.1.11, `windows-sys` 0.61.2 and
`windows-link` 0.2.1. The first two same-file/winapi-util packages offer MIT or
Unlicense; the Windows binding packages offer MIT or Apache-2.0. Project dependency
records retain the selected notices. No hand-written SDK wrapper or root unsafe
code is introduced. This dependency supplies file identity only, with no storage
publication, durability or recovery contract.

Primary sources: [same-file 1.0.6 API](https://docs.rs/same-file/1.0.6/same_file/struct.Handle.html),
[published implementation source](https://docs.rs/crate/same-file/1.0.6/source/src/win.rs),
[package manifest](https://docs.rs/crate/same-file/1.0.6/source/Cargo.toml),
[winapi-util manifest](https://docs.rs/crate/winapi-util/0.1.11/source/Cargo.toml).

## Platform evidence

`tests/pairing.rs` uses synthetic, independently authored ordinary files. The
vectors cover explicit differing stems/directories, no basename inference,
missing sidecar without creation, lexical aliases, hard links versus equal-byte
distinct files, directories, unsupported non-ASCII leaves, and the directory bound.
Windows adds a case-alias refusal; Unix adds a symlink alias and a directory-entry
case check. When the filesystem retains two distinct case-equivalent names, the
Unix vector requires ambiguity refusal. When the names alias one directory entry,
as on commonly case-insensitive APFS, it requires successful explicit pairing with
the distinct RAW and same-file refusal between the sidecar's two spellings.
Neither branch skips the case assertions. Successful and refused observations retain input bytes and
unrelated neighboring files.

On 2026-10-15, `cargo test --locked --test pairing` passed all eight Windows vectors
on the actual local NTFS test volume. The synthetic hard-link fixture required
running outside the filesystem sandbox, which otherwise denied link creation.
The Unix-specific vectors remain unrun in this handoff unless separately recorded
with an actual Unix run. Compilation or Windows success does not establish those
Unix observations.
Windows case-sensitive directories and Windows symlink privilege variations are
not qualified by the ordinary case-insensitive NTFS vectors. No private media or
generated local logs are committed.

See [RAW scope](../raw-scope.md) and the separate
[write-admission boundary](../write-safety/write-admission.md).
