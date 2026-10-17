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
Neither branch skips the case assertions. Successful and refused observations
retain input bytes and unrelated neighboring files.

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

## Opt-in same-stem inference (#0182)

`imageinfo sidecar pair RAW --infer-same-stem` previews one inferred association.
The flag conflicts with `--sidecar`; omitting both retains the explicit resolver's
`EXPLICIT_SIDECAR_REQUIRED` refusal. `PairRequest` and `resolve_pair` retain their
existing shape and behavior. The separate library entry is
`pairing::infer_same_stem(raw)`.

The exact `ascii-cr3-xmp-v1` rule is deliberately finite:

- Select one existing ordinary ASCII `.cr3` leaf. The stem must be nonempty,
  cannot end in a space or dot, and the leaf cannot contain controls or the
  Windows-reserved punctuation `<>:"/\|?*`.
- Examine only its selected parent, with at most 4,096 entries. There is no
  recursive search, other-directory search, metadata matching or creation path.
  Non-ASCII entries refuse because their stem equivalence is unqualified.
- Compare stems and `.cr3`/`.xmp` extensions using ASCII case-insensitive
  equality. Require exactly one same-stem ordinary CR3 entry and one ordinary
  XMP entry. Two distinct case-equivalent CR3 or XMP entries refuse.
- Any other same-stem extension, a bare same-stem leaf, same-stem directory or
  same-stem symlink refuses as ambiguous. Unrelated entries and subdirectories
  do not supply candidates. A symlink RAW also refuses. Ancestor resolution
  remains ordinary filesystem resolution; no ancestor security claim follows.
- Apply the explicit resolver's regular-file, case-entry and held physical
  identity checks to the selected pair. Hard-link aliases refuse, while
  identical bytes in two distinct objects are allowed. No file content is
  interpreted, including RAW or XML format validation.

Success returns `association: "inferred_same_stem"`, the exact rule identifier,
caller-selected `raw_origin`, enumerated `sidecar_origin`, canonical selected
parent and canonical resolved pair. CLI JSON stores these in an
`inferred-pair-preview` snapshot with `mutationAllowed: false` and `previewed`
state. Both origins remain explicit in the proposal; the normal explicit mode
retains its `explicit-pair` snapshot.

Missing sidecars return `SIDECAR_MISSING`; competing names return
`PAIRING_INFERENCE_AMBIGUOUS`. Unsupported names and directory overflow return
`PAIRING_NAME_UNSUPPORTED` and `PAIRING_DIRECTORY_LIMIT`. None selects a first
candidate or creates any file. The returned library observation retains two
read-only identity handles, excluded from JSON, so its explicit `revalidate()`
can repeat the rule and compare actual physical identities. Missing origins or
replacement at an origin return `PAIRING_INFERENCE_STALE`; newly competing
names return the ambiguity refusal. A serialized preview cannot reconstruct
these private handles or confer revalidation authority.

Revalidation observes path/object association only, not file-content freshness.
In-place edits do not prove a stale association. The retained handles are not
namespace or property guards. Enumeration, canonicalization and opens remain
separate observations of a quiescent filesystem, and inference supplies no
association authenticity, continuing exclusion or later mutation permission.
OS access-time accounting remains outside the no-requested-effects claim.

On 2026-10-17, nine actual Windows authored inference tests and all eight
existing explicit-pair tests passed on the local NTFS test volume. Native
hard-link setup required running outside the filesystem sandbox after its
access-denied setup failure. The inference cases cover unique case-varied names,
equal-byte distinct objects, complete recursive input/neighbor byte and name
inventories, other-directory refusal, conflicting extensions and directories,
replacement/missing stale observations, hard-link aliases, case behavior,
unsupported names, the exact directory bound and actual CLI opt-in/conflict/JSON
preview behavior. The Unix symlink test and Unix case-sensitive branch remain
unrun here; ordinary Windows case-insensitive behavior was executed. Windows
case-sensitive directories and privileged symlink configurations remain unrun.
