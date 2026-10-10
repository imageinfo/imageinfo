# Storage constraints and evidence gates

Observed **2026-10-10**. These primary-source observations inform WS-009 through
WS-024. They do not select a language, library, syscall sequence, or supported
storage profile. **No imageinfo platform profile is verified.**

## Facts that constrain the design

| Source | Observation | Consequence for the proposed contract |
| --- | --- | --- |
| [Microsoft ReplaceFileW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-replacefilew), page updated 2023-06-01 | Replacement, original and optional backup must share a volume. The write-through flag is unsupported. Ignoring merge/ACL errors can lose properties. Some failure codes leave names or attributes changed. | Do not equate a successful replacement call with durability, or a failed call with no effects. Inspect actual identities after uncertain outcomes. Reject unsupported property preservation. |
| [Microsoft FlushFileBuffers](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-flushfilebuffers), live reference | Flushing uses a suitable handle and can fail. The documented operation concerns the specified file's buffered information. | A file-flush call alone is not evidence for the entire publication/recovery protocol. Establish the namespace, record and storage assumptions separately. |
| [Linux rename manual source](https://raw.githubusercontent.com/mkerrisk/man-pages/master/man2/rename.2), maintainer repository snapshot | Replacement has atomic pathname visibility; existing descriptors and other hard links survive. No-replace publication requires filesystem support. On NFS, a reported failure can follow a completed rename. | Treat alias behavior, conditional creation, and ambiguous remote failures separately. An atomic rename is not an expected-content comparison. |
| [Linux fsync manual source](https://raw.githubusercontent.com/mkerrisk/man-pages/master/man2/fsync.2), document date 2021-03-22 | Persisting a file does not necessarily persist its directory entry; the directory needs its own synchronization. | Candidate data, recovery data, namespace changes and outcome records need an ordered persistence argument. |
| [Linux fcntl manual source](https://raw.githubusercontent.com/mkerrisk/man-pages/master/man2/fcntl.2), document date 2021-03-22 | Advisory record locks coordinate participating processes. | Do not advertise exclusion of unrelated editors merely because imageinfo instances share a lock. |
| [Apple archived fsync manual](https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/fsync.2.html), archived reference | The manual distinguishes ordinary synchronization from asking the drive to flush its cache with F_FULLFSYNC. | Verify current platform/device persistence behavior instead of assuming all calls named fsync have interchangeable guarantees. |

The Linux links are mutable source links to an older maintainer snapshot, not a
claim about the newest kernel/manual release. The Apple page is archived. No
immutable revision was established for these pages during this research. Refresh
these references against the actual target OS/filesystem versions before enabling
a backend. The observations above are paraphrases; no upstream code is imported.

## Required profile evidence

A profile names its OS/version, filesystem and mount/volume configuration, storage
and synchronization assumptions, supported operation, and explicit exclusions.
Separate existing-file replacement, new-file publication, same-volume rename,
cross-volume move, and backup restore/prune. Support for one does not imply another.

The evidence must demonstrate:

- Stable source, candidate and destination/parent bindings, including aliases and
  a competing writer that does not use imageinfo's locks.
- Conditional absence for new names; protection against stale overwrite for
  existing names. The guard covers validation through publication/final checks.
- Atomic visibility of complete content, including observers with existing handles.
  Observing an old complete file can be acceptable; observing partial content cannot.
- Preservation of the declared permissions, ownership, attributes, streams and times;
  supported behavior for case-only names, links, read-only files and long paths.
- The exact order and meaning of persistence acknowledgements for candidates,
  recoverable originals, recovery records, directory changes and final receipts.
- Deterministic fault injection at each boundary, plus separate process-kill,
  OS-crash and power-loss evidence appropriate to the advertised guarantee.
- Recovery with missing, foreign, corrupted and inaccessible artifacts; bounded
  errors; no unguarded restoration or cleanup of unrelated files.

Use [fixture-plan experiment records](../fixture-plan/README.md) for actual runs.
Record expected and observed file identities, bytes, properties, reports and
termination. A process-kill test does not demonstrate power-loss survival.

## Proposed fallback and tradeoff

The inference from these constraints is conservative: “hash, then rename” and
“take an advisory lock” do not by themselves meet the strict replacement contract.
If a profile cannot establish the required exclusion or conditional publication,
the initial proposal refuses replacement. An explicitly selected new output may
still be available when its independent no-clobber and input-stability guarantees
are supported. Its existence does not imply that deleting the source is safe.

This can limit in-place editing on ordinary platforms. It is a visible product
tradeoff for review, not evidence that those platforms are unusable. A weaker
concurrency mode needs its own accepted guarantees before implementation. Do not
hide the gap behind a complicated abstraction or an unsupported universal promise.

## Current readiness

Windows/local volume, macOS/local volume, Linux/local filesystem, removable storage,
network filesystems and cloud-synchronized directories are all **unverified** for
imageinfo mutation. Existing OS documentation helps define experiments; it cannot
replace the experiments. Read-only discovery can advance independently.
