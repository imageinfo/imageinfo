# Bounded planned staging bytes

**#0040**, observed **2026-10-14**, resumes first-ranked #0022 from its explicit
handoff. Portable resource checks now guard actual file construction in the
[#0038 staging worker](../../experiments/0038-staging-cleanup/README.md).
**This supplies a logical-byte bound, not a complete storage/writer profile.**

## Implemented behavior

Before creating a transaction root or file, the worker checks the combined planned
stage and record lengths using checked u64 addition. Its 65,536-byte stage and
31-byte record require **65,567 bytes**. The optional explicit limit defaults to
131,072 bytes; below-budget or malformed limits refuse before transaction artifacts.

Every fresh file is then copied through an exact-length reader bound. A separate
one-byte probe detects extra source data without writing that byte. Short input,
extra input, read error, partial sink error or WriteZero does not produce a successful
stage. Partial files can remain and still consume space. No budget is refunded or
reused after a failure, and a record alone never grants publication/cleanup authority.

| Actual cell | Observation |
| --- | --- |
| Limits 0, 1, 65,535, 65,536 and 65,566 | No transaction root/files created; explicit byte-limit refusal. |
| Exact 65,567, one above, u64::MAX and omitted default | Exactly 65,567 logical bytes staged; cooperative cancellation removes both owned files, retaining the empty root. |
| Negative, nonnumeric or u64-overflow selector | Invalid-limit refusal before transaction artifacts. |
| Kill at exact-budget prepared barrier | Both complete owned artifacts retained; no output or terminal/committed report fabricated. |
| Publish fixture cancelled before its namespace call | Owned-file cleanup succeeds; no output. |
| One-byte short marker recipe | Actual partial stage is 65,535 bytes; record/output absent. |
| One-byte overlong marker recipe | Actual stage stops at 65,536 bytes; extra byte is not written, record/output absent. |
| Existing foreign root | Exclusive creation refuses; foreign bytes unchanged. |

The scope is WS-016/023's bounded staging/cancellation cell. It does not silently
replace source exclusion or grant a supported output policy. Short/overlong native
recipes model producer-length errors; portable stream tests also use an unending
reader to check the byte bound. This is not proof of a stable concurrently changing
source or an atomic filesystem snapshot.

## Verification and implementation review

Ten portable tests cover exact boundaries/checked overflow, zero and multi-buffer
copies, short/overlong streams, partial/interrupted reads and writes, source/probe
failure, sink error/WriteZero, and a u64::MAX declared length without a huge buffer.
The injected errors are protocol tests, not actual ENOSPC/device-failure claims.
The native qualifier passes **17 cases**; the existing **27-case cleanup regression**
also passes. [The audit](staging-limits-observations.json) binds **44 worker captures**,
**99 limit artifacts** and **212 regression artifacts**, retaining one inaccessible
regression root without repair. Original media and source ACLs are untouched.

The new module uses checked arithmetic, standard `Read::take` and `io::copy`.
Primary Rust documentation observed **2026-10-14**, std **1.99.0**, revision
**b940084d7 (2026-09-28)**:

- [`Read::take`](https://doc.rust-lang.org/std/io/trait.Read.html#method.take)
  limits reader output; source EOF must still be checked separately.
- [`io::copy`](https://doc.rust-lang.org/std/io/fn.copy.html)
  streams data, reports copied bytes and propagates non-interrupted I/O errors.
  The caller checks the expected length and handles the separate probe's interrupts.

No custom copying framework or runtime transaction abstraction is introduced.
The [existing SDK review](../../experiments/0038-staging-cleanup/ffi-review.md) and
[14-package/15-notice admission](staging-cleanup-dependencies.json) are reused unchanged.
Exact lock/archive identities and notice hashes were checked. Shared native source,
Cargo manifests/locks and root production unsafe policy remain unchanged.

Root format/Clippy/**44 Windows tests**/release, research format/Clippy/ten tests/
release, Python syntax, docs/link/JSON and diff checks pass. The portable tests run
on Windows, Ubuntu and macOS; other platforms refuse the Windows filesystem adapter.
[CI](staging-limits-ci.json) separately records source and platform results.

## Limits and remaining work

The byte sum covers one transaction's planned artifact contents. It does not bound
allocation units, filesystem metadata, ADS, memory, captures/logs or accumulated
older retained transactions. It neither checks nor reserves available disk space;
it is not an OS quota. The existing watchdog is not a hard native-I/O deadline.
OS-crash and physical power loss were not exercised by this increment.

#0022 still needs a usable editable-output strategy, complete source/property/path
support, qualified Windows namespace/receipt persistence and safe restart/finalization/
prune. #0039's failed release mechanism is not repeated or relaxed. Current RAW
mutation admission remains refused under #0027. This increment enables no production
writer, replacement, replay, directory cleanup or broader filesystem profile.
