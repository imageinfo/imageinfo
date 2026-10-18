# Ordinary and case-only held marker rename (#0201)

Status: bounded implementation and preliminary native evidence, 2026-10-18.
All ten native cells pass in a fresh run, with independent retained-artifact
identity, bytes, property and name-map audit.
The finite mechanism does not admit a public storage profile, replacement,
durable commitment, paired operation or production RAW rename.

## Method and retained ownership

[`path_rename.rs`](../../src/storage/path_rename.rs) previews one same-parent
ordinary move, or a case-only move through one explicitly named fresh temporary
component. The bounded ASCII name classifier selects the plan; it does not
establish the filesystem's comparison behavior. Native acquisition must verify
the actual parent, comparison mode, exact spelling, source identity and applicable
properties before effects. Unresolved comparison rules, reparse paths and
equivalent occupied destinations refuse.

The native plan retains one
[`HeldExistingMoveSession`](../../crates/imageinfo-windows-storage/src/existing_move.rs).
Both case-only steps rename the same held object without closing and reopening
the source. The common ancestor guards remain held. Every move uses the reviewed
flags-zero no-replace rename boundary; a destination winner is never overwritten.
The earlier [single-move evidence](held-existing-move.md) remains a separate
baseline and does not qualify this two-step caller.

For source `marker.xmp` and destination `MARKER.xmp`, the preview must include
an explicit distinct temporary component. The only sequence is source to
temporary, then temporary to destination. The temporary name contains the
original object. It is never disposable staging or cleanup material.

Properties are checked at declared boundaries. A detected change stops the
operation; no stale snapshot is written back over an actor's edit. This is not
continuous exclusion of all same-owner property changes. Default bytes, identity,
name custody and property observations remain separate assertions.

## Finite acceptance and uncertainty

The ten actual [authored native cells](../../src/storage/path_rename/native_tests.rs)
cover:

- Ordinary and case-only success.
- Initial and late temporary collisions, and a final foreign winner.
- Preopened writer and attempted parent move.
- Property change, cancellation between moves and unknown in-flight result.

Each cell retains an independently checked map of exact names, object identities,
default bytes and applicable properties after handles close. An earlier native
attempt failed on the fixture's path-length boundary; that failed attempt remains
separate from the fresh passing run and is not counted as acceptance.

Cancellation stops before the next call. A pre-call binding-map failure stops
without another move; uncertainty after an issued call requires recovery. Neither
path triggers compensation, replay or deletion. A partial case-only result
reports the original at its observed temporary name. The lost-response cell
performs the real first SDK move, then injects loss of its response at the planner
boundary before classification or confirmed-prefix advancement. This exercises
caller uncertainty; it is not an observation of an ambiguous Windows API result.

`Finished` or an observed moved result describes the live checked map. It is not
a persistence acknowledgement or committed outcome. Loss of process-owned guards
cannot be repaired by loading a saved plan. Final qualification of the exact
production caller and frozen source remains separate, as do #0212 integration
and #0026's broader positive acceptance.
