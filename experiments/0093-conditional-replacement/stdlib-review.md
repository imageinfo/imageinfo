# Rust standard-library boundary review

Card **#0093**, observed **2026-10-15**. This review concerns the separate marker
experiment, not production replacement support or the frozen #0032 SDK boundary.
The worker uses safe Rust APIs; this experiment adds no direct SDK FFI, privilege,
source ACL change, host crash or personal-media operation.

## Exact implementation being exercised

The pinned compiler reports Rust **1.99.0**, source commit
`b940084d7eb6a299eb4bfeb8e34901bc051e7ac4` (2026-09-28), host
`x86_64-pc-windows-msvc`. The experiment must retain its actual worker/compiler
identities with private captures rather than treating this document as execution
evidence.

`input.marker` is the protected original and remains held in every mode. Only the
separate staging file `candidate.bin` is passed as the rename source. The mode
named `source-guard` refers to that staging operand. Protected-input write/name
actors are disposable foreign-attempt tests expected to fail, never steps of a
preservation or replacement protocol. Their actual refusal and unchanged input
bytes/identity/security observations are required in every affected case.

[Rust's rename documentation](https://doc.rust-lang.org/std/fs/fn.rename.html)
describes Windows `MoveFileExW` with a `SetFileInformationByHandle` fallback.
The [pinned Windows implementation](https://github.com/rust-lang/rust/blob/b940084d7eb6a299eb4bfeb8e34901bc051e7ac4/library/std/src/sys/fs/windows.rs#L1248-L1311)
first requests `MOVEFILE_REPLACE_EXISTING`. If the original error is access denied,
it opens the source with DELETE access and no-follow/backup semantics, then requests
`FileRenameInfoEx` with replacement and POSIX flags. Other original failures return
without that fallback. The source handle is opened by pathname; the standard API
does not consume the experiment's previously held candidate handle or an expected
destination identity.

Consequently this worker must be described as measuring **the pinned standard
library operation**, not one custom syscall with immutable flags or no fallback.
A returned error does not independently identify every internal OS call made.
In particular, readonly/property controls may exercise a different internal route.
No upstream implementation code is copied into the experiment.

## Conditions to check against actual evidence

- Retained read-share-only source and target handles should be distinguished from
  target-only and source-only controls. Failure with both handles does not isolate
  which object's sharing made the operation incompatible.
- A read/delete-shared target control deliberately permits name movement. A final
  pathname check followed by replacement has no expected-target-ID operand, so a
  successful API return after target substitution is not conditional commitment.
- The positive unguarded control establishes that the disposable same-volume
  replacement operation actually works in the measured environment. It does not
  qualify the guarded profile.
- Strongly guarded refusals need independent before/after comparisons of the
  actual target identity, bytes, names and observed security/properties. Error
  codes alone cannot prove target preservation.
- A fresh-root directory hold concerns that root only. It supplies no claim about
  all ancestors, mount mappings, alternate providers or privileged attackers.
- Property checks are named observation boundaries under OD-11 option A, not
  continuous exclusion of same-owner timestamps, ACLs, streams or link topology.
  Uninspected fields remain missing cells rather than assumed preservation.

Safe `OpenOptionsExt` access/share/custom flags still choose Windows access
semantics and require source review. No handle may be released or weakened after
validation to turn a refused guarded attempt into a claimed success. Handles must
remain retained through result inspection, and every mode must keep commitment,
profile and production-replacement permission false.

## Primary references

Viewed **2026-10-15**. The Rust implementation link is revision pinned; live
Microsoft pages have no immutable revision bound by this review.

- [Rust OpenOptionsExt](https://doc.rust-lang.org/std/os/windows/fs/trait.OpenOptionsExt.html): explicit access/share/flag selection.
- [Microsoft MoveFileExW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-movefileexw): replacement access and failure semantics; its documented page update is 2023-06-01.
- [Microsoft CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew): access/sharing compatibility and directory handle conditions.
- [Microsoft FILE_RENAME_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_rename_info): replacement/POSIX flags and structure semantics.

Documentation supports the boundary reasoning. Only the retained marker calls and
independent observations establish this experiment's bounded outcomes. No Windows
replacement primitive is ruled out merely because this one profile is unsupported.
