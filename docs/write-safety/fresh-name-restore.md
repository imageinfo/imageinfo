# Explicit fresh-name marker restore (#0108)

The separate [marker qualifier](../../experiments/0108-fresh-name-restore/README.md)
exercises a safe module in the existing
[Windows research worker](../../experiments/0032-windows-publication/src/restore.rs).
This is one bounded #0095 slice: copy an owned retained original into the explicit
fresh name `restored.marker`, preserving the separately named later-edited current
target. Occupied-name restoration under WS-019 and SAF-012 remains unqualified;
this slice does not complete those broader requirements or enable a profile.

## Custody and fresh authorization

The worker accepts only a fresh scratch root below this checkout's `.local` and
fixed authored marker modes. It creates `current.marker` containing `OLD108`,
copies its actual held bytes into `retained-original.marker`, then actually edits
the current marker to `LATER108`. `unrelated.marker` is independently retained.
The existing private creation helper establishes the declared canonical owner/DACL
policy. This is a typed-owned recreated retention fixture, not an importer for
#0094's existing files: #0094's inherited security/basic-property observations do
not establish the stronger canonical descriptor checked here.

Read-only identity bridges overlap the writable creators with final setup guards;
timestamps are captured after writable creator close. A private Rust type captures
actual root/original/current/unrelated identities and properties. The synchronous
fixture actor and all its handles stop before the `captured` barrier. No child
process, saved JSON, path or digest supplies stop attestation or repair authority.
Emitted JSON is observation only; the captured type has no deserializer/importer.

After `captured`, the worker acquires fresh root/ancestor and read-sharing-only
file holds, compares live identities, bounded exact bytes, basic properties,
single-link topology, default-stream inventory and canonical owner/DACL. The
explicit `authorize-restore` barrier requires `restore-fresh` with LF or CRLF;
ordinary continuation cannot authorize this fresh mutation. The mode selects the
fixed destination `restored.marker`, whose absence and root entry set are checked.

## Copy, publication and outcomes

Exclusive creation returns the actual held `restored-candidate.marker` handle.
The worker copies exact bounded bytes from the held original. Its completed-copy
property baseline precedes `sync_all`; checks after sync must match that baseline
rather than silently refreshing it. Successful sync is an API observation, not a
durable acknowledgement. Current/original/unrelated identities and bytes, root
binding, properties, entry set and candidate binding are checked again after the
last caller barrier. All guards stay held through the operation and inspection.

Publication reuses the unchanged existing SDK wrapper's absolute held-candidate
rename with replacement flags zero. No pathname candidate reopen, guard release,
directory-relative fallback or occupied-target replacement is used. The retained
original is copied, never moved. Installed identity/content/properties are checked
through the held candidate and fresh installed-name binding.

`restored-copy-observed` describes a successful live observation. Before any
publication attempt, failed checks/control input emit `refused`. After an attempt,
errors/control interruption emit `recovery-required` conservatively. An actual
process termination may leave no result. All artifacts and foreign winners remain;
there is no retry, replay, rollback, cleanup or restart action. Commitment,
namespace acknowledgement, durable custody, repair, production publication and
profile flags stay false.

## Evidence and limits

The [curated qualification](../../experiments/0108-fresh-name-restore/qualification.json)
binds the actual final run on **2026-10-15**, Windows **10.0.26200**, NTFS, the
pinned Rust **1.99.0** toolchain and exact source/worker hashes. The independent
[retained-artifact audit](../../experiments/0108-fresh-name-restore/audit.json)
rereads the completed run without invoking restore or changing marker artifacts.

| Actual final-run observations | Cases |
| --- | --- |
| Fresh-name copy observed, including denied actor controls | 13 |
| Refused before publication attempt | 37 |
| Actual late no-replace collision, reported recovery-required | 1 |
| Owned worker terminated at a declared barrier, without a result | 7 |
| Additional entrypoint/context admission refusals | 3 |

The audit matches all retained actual artifacts across the 58 marker cells and
three admission refusals. Current target versions remain retained. The late native
collision retains both the foreign winner and the completed candidate. Original,
current and candidate byte/name actors were denied under their strong holds;
successful time/readonly/stream changes refused at the relevant checkpoints.
Those observations do not establish continuous property exclusion. LF/CRLF
authorization succeeds; ordinary continuation, JSON authority claims and
unterminated control tokens refuse. The seven process kills include the published
boundary, without replay or automatic cleanup.

One provisional run completed its behavior assertions but correctly refused its
final source manifest after source changed; it is retained privately and supplies
no published qualification. The published record binds a separate fresh complete
run against the frozen final source. No private capture paths, security snapshots
or raw logs are published. Compilation alone supplies no native behavior evidence.

Checks cover length, file identity, creation/write time, attribute bits, link count,
default-stream bytes/inventory and the declared canonical owner/DACL. They do not
establish complete original filesystem-property backup, group/SACL/labels,
continuous same-owner property exclusion, namespace persistence, durable caller
custody or physical-power survival. Access time is excluded because reads can
affect it. This research uses no real media and grants no RAW mutation permission.
Future power tests follow the [VM-off-only best-effort policy](power-test-policy.md).
