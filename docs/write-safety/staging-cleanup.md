# Guarded staging cleanup before publication

**#0038**, observed **2026-10-13**, continues the board's first dependency blocker,
#0022. [The marker probe](../../experiments/0038-staging-cleanup/README.md) implements
actual live prepublication file cleanup with the accepted fresh #0033 guards.
**No original/source ACL, encryption, privileged helper or production writer/profile
is introduced. Restart and postpublication cleanup remain refused.**

## Result

Cancellation validates the two exclusively created owned files and marks their
retained handles for deletion, then closes those handles. Normal cancellation and
cancellation just before a namespace call remove the owned stage/record files in
the observed live namespace. Empty private roots remain intentionally retained.

An unrelated writer can insert a new file under an old name after the owned handle
closes. The probe preserves that new object, as well as unrelated extra entries.
It never searches for names to delete, reopens a path for a deletion retry or removes
a directory tree. This supplies a concrete live-ownership cleanup cell under
WS-015/016/023; it is not a restart/prune permission.

| Cell | Actual observation |
| --- | --- |
| Normal prepublication cancellation | Two owned handles marked/closed; files absent, empty root retained. |
| Cancellation before publication call | Same cleanup; no namespace call attempted. |
| Foreign old-name reinsertion / extra entry | Foreign bytes retained; pending retained entries reported. |
| Compatible reader | Creator closes its marked stage handle, but stage remains until reader closes; pending cleanup reported. |
| Incompatible reader sharing | Reader open refuses with sharing violation; ordinary cleanup succeeds. |
| Fresh property/data/name actors | Nine actor operations refuse on the sealed owned stage; cleanup removes its verified owned object. |
| Changed private-root policy | Live guard refuses; no deletion call is issued. Inaccessible root is retained without ACL repair. |
| Missing DELETE right | Actual disposition returns access denied; both objects retained and pending/error reported. |
| Injected second-file failure | Labeled protocol injection, not fake OS error: first object closes/deletes, second remains. |
| Publication succeeds or collides | Cleanup refuses after the attempt boundary; actual output/winner and any candidates remain. |
| Worker kill before mark / after mark / after close | Actual retained names recorded; no fabricated terminal or committed outcome. |
| Admit/finalize/prune / other platforms | Refuse before worker effects; no broader backend inferred. |

Only live handles from this process's own fresh creation can enter the cancellation
path. Checksums, imported paths or phase booleans do not confer ownership. The root
and operator-visible artifacts remain available on partial/error/refused paths.
Logical deletion does not establish secure erasure or persistence after a crash.

## Evidence and limits

[The 27-case ledger](staging-cleanup-observations.json) audits **27 worker captures**,
**213 readable artifacts**, and **one inaccessible root** retained without repair.
Source/native-binary/control/actor bindings and earlier attempts stay private.
No media, SID, object ID, machine path, raw capture or assembled executable is
published. Windows observations are ordinary local NTFS/current token/unchanged DOS
mapping; host/OS crash and physical power loss were not exercised.

The [small SDK review](../../experiments/0038-staging-cleanup/ffi-review.md) adds one
synchronous standard handle-disposition call. [Dependencies](staging-cleanup-dependencies.json)
reuse 14 exact admitted packages and 15 notices, with no new SDK feature or root
dependency/unsafe-policy change. Research format/Clippy/build gates and root
format/Clippy/**44 Windows tests**/release pass; Python syntax and docs/link/JSON
checks pass. [CI](staging-cleanup-ci.json) records source/platform evidence.

#0014/#0022 retain complete source/property/path handling, ordinary output policy,
Windows namespace/receipt persistence and safely qualified restart finalization/
prune. #0027 still refuses current RAW mutation admissions. This live cancellation
increment does not enable a writer, #0023, postpublication rollback or automatic
root/directory cleanup. The Windows adapter's result does not qualify other OS or
filesystem adapters; their differing capabilities remain explicit.
