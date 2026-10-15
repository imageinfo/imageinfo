# Bounded original retention (#0094)

The isolated [marker worker](../../experiments/0094-original-retention/README.md)
implements one actual retention sequence for #0093's
[unsupported existing-target primitive](conditional-replacement.md). Retention
and refusal observations cannot enable positive replacement, restore, commitment,
durability, automatic recovery or a production storage profile. Every emitted
authority/admission flag remains false.

## Implemented sequence

The caller selects a fresh nonexistent root below this checkout's `.local`.
The worker creates fixed authored markers, captures their actual identities and
holds the target, candidate and unrelated file read-only with read sharing.
The fresh root directory is held without delete sharing. No real media or existing
caller file is accepted. For each initial marker a read-only identity handle
that shares writes bridges the writable creator to the final read-sharing-only
guard. Each overlap compares actual identity, so there is no handle-custody gap.
Exact authored bytes, basic properties and single-link status are checked before
`ready`.

After `ready`, the worker checks the held root and exact entry set, then each
current name's identity against its retained handle, bounded exact bytes and
basic properties. It creates `retained-original.bin` with `create_new` and holds
that very read/write creation handle with read sharing for the entire sequence.
This is a distinct owned object containing copied original bytes, not the same
object as the original target. The original target handle remains held throughout.
No later pathname reopen creates custody or substitutes for the retained handle.

The copy reads the held target, writes its exact bounded bytes through the owned
retention handle, and captures the completed copy's properties. It then calls
`sync_all` on that file. Successful sync is an observed API return, not a qualified
namespace or durable-original acknowledgement. Its property baseline is not
refreshed across sync. Every later checkpoint rechecks exact content, identities,
properties, single-link baselines and the expected four-entry root.

After the last caller gate, the worker renews these checks and measures the same
ordinary `std::fs::rename(candidate, target)` operation under both strong file
guards. It never drops a guard to obtain success. A native refusal leaves both
original representations and the candidate retained. Unexpected success is
explicitly labelled unsupported and grants no permission. Nothing is deleted,
restored, replayed or retried.

`no-backup` follows the identical precommit sequence as `keep`: it cannot skip
the retained original or remove either original representation. There is no
qualified commit transition at which any original could be discarded, so there
is deliberately no implemented backup-disposal action.

## Finite boundaries and truthful states

| Boundary | Current target | Retained copy | Permitted classification |
| --- | --- | --- | --- |
| `ready` | Exact held original | Absent | `retained-current` |
| `retention-created` | Exact held original | Exact owned empty marker | `retained-current` |
| `retention-written` | Exact held original | Exact distinct original bytes | `retained-current-and-original` |
| `retention-synced` | Exact held original | Same copy; sync returned | Same observed retention state |
| `precommit` | Exact held original | Same checked copy | Same observed retention state |
| `result` after native refusal | Checked current original | Checked original copy | Same observed retention state |
| Any detected binding/content/property/entry mismatch | Preserve actual artifacts | Preserve actual artifacts | `refusal-unverified`; no inferred recoverability |

The worker emits each gate while handles remain live and waits for an exact
caller continuation. Malformed input/EOF or I/O failure stops with artifacts
retained. A failed or partial retention write never permits the rename call.
The copy-created boundary is explicitly incomplete; the held current original
remains the sole complete original there. The worker has no restart importer:
an independent observer can compare process-interruption artifacts against the
trusted live caller's captured identities and bytes, but editable JSON cannot
authorize recovery, cleanup or restore. Identity equality after exit is an
observation, not continuous custody after handles have closed.

## Verification and limits

The independent [qualifier](../../experiments/0094-original-retention/qualify.py),
[artifact audit](../../experiments/0094-original-retention/audit.py) and
[curated evidence](../../experiments/0094-original-retention/qualification.json)
bind the actual final run on 2026-10-15: Windows **10.0.26200**, AMD64, local
**NTFS, Fixed**, Rust **1.99.0** at the pinned revision and the exact release worker.
All seven bound raw source files match their Git canonical bytes. The independent
audit checks retained actual artifacts against the captured live observations.

| Final native observation | Cases |
| --- | --- |
| Marker cells | 32 |
| Additional entrypoint refusals | 3 |
| Actual owned-worker process kills, including two after result | 12 |
| Attempted native replacement refused, all OS error 32 | 11 |
| Refused before replacement attempt | 11 |
| Killed before a result | 10 |

The current original and candidate identities and exact default-stream bytes
remain retained in every marker cell. Twenty-two cells retain a complete owned
copy; two retain the owned empty copy and three have no retained-copy name.
Five occupied-name cells refuse without adopting or replacing that entry. In two
of those controls its bytes equal the original, but byte equality does not make
it an owned copy; the 24 original-byte matches must not be reported as 24 owned
originals. Both retention options pass normal controls and every declared kill
boundary. The actor cells cover occupied foreign/same-byte/directory/alias names,
denied data/name attempts and checkpoint property changes. No retained-copy
last-write drift was observed on the measured writer-close transitions.

A first qualifier setup run stopped because two private capture filenames
collided; the qualifier was corrected and a fresh complete run passed. A further
fresh run after manifest/lock line-ending normalization supplies the published
exact-byte evidence. Earlier scratch and error artifacts remain private and
retained. No raw local paths, security snapshots or process logs are published.
Compilation and zero unit tests alone establish no Windows sharing or
process-interruption behavior.

The worker's property subset is length, creation/write timestamps, readonly and
attribute bits, link count, volume and file index. Reads exclude access time.
It does not qualify owner/DACL/SACL, named-stream preservation, all ancestor
exclusion, other volumes or filesystems, OS/VM shutdown, physical power survival,
native storage errors, durable context custody or fresh guarded restore. The
retained writable creation handle is intentionally never used again for writes
after the copy: this bounded implementation discipline does not claim an OS deny
against its own process. Same-owner property changes may bypass sharing and must
be detected at the declared checkpoints; their continuous exclusion is unclaimed.
Any read-only observer's additional property coverage stays separate.

The original target and copy can both be retained after observed process exit;
that is not a durable recovery promise. #0093 remains unsupported. #0095 owns
fresh guarded restore, and #0096 owns grouped partial outcomes. No broader backup
manager, restore action, source deletion, production writer or RAW admission is
implemented by this ticket. Current testing follows the
[best-effort power-test policy](power-test-policy.md); physical power evidence is
not an admission prerequisite.
