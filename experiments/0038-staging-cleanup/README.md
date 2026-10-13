# Live prepublication staging cleanup

**#0038**, observed **2026-10-13**, advances #0022's cancellation/cleanup work.
Standalone marker research, with no RAW input or production writer/profile.
[Measured cells](../../docs/write-safety/staging-cleanup.md) and
[the disposition review](ffi-review.md) define its exact scope.

The probe exclusively creates a private root and two fresh sealed owned files.
Before publication, cancellation checks live identity, bytes, time, attributes,
one-link/default-stream policy and the existing private descriptors. It then marks
only those retained file handles for deletion and closes them. It never deletes a
path from a record or enumeration, retries an old name or removes the root tree.
Reinserted names and unrelated entries remain retained.

```console
cargo fmt --manifest-path experiments/0038-staging-cleanup/Cargo.toml --check
cargo clippy --locked --manifest-path experiments/0038-staging-cleanup/Cargo.toml --all-targets -- -D warnings
cargo test --locked --manifest-path experiments/0038-staging-cleanup/Cargo.toml
cargo build --locked --release --manifest-path experiments/0038-staging-cleanup/Cargo.toml
python experiments/0038-staging-cleanup/qualify.py --binary experiments/0038-staging-cleanup/target/release/imageinfo-staging-cleanup-probe.exe --parent .local/staging-cleanup-qualification
```

Arguments are `<mode> <new-absolute-local-root.marker>`. Modes `abort`, `publish`,
`inject-error` and `no-delete` qualify actual lifetime/error boundaries. `publish`
is a marker fixture: cancellation before its namespace call cleans owned staging;
after a call is attempted, cleanup refuses even on a collision/error. There is no
rollback or committed receipt. `admit`, `finalize` and `prune` refuse before effects.
Other platforms explicitly refuse this Windows adapter.

The private root is intentionally retained, including when empty. Compatible
readers can defer removal beyond the creator's close; pending work is reported
without forcing readers closed or reopening their paths for deletion. Logical
deletion is not secure erasure or proof of crash/power-loss persistence.

The 27 cases cover normal cancellation, cancellation just before publication,
old-name reinsertion, unrelated entries, compatible/incompatible readers, nine
property/data/name actors, changed root policy, actual missing DELETE access,
labeled injected partial failure, publication/collision preservation, three worker
kill boundaries and three admission/restart-action refusals. SDK/actor/capture
helpers are project-owned reuse; the only new native call is the standard file
disposition operation. No encryption, privileges or source ACL changes occur.

Each process has a 60-second watchdog; message waits are 15 seconds and controls
32 bytes. Marker data is 64 KiB, with a small fixed record. These are experiment
bounds, not a hard native-I/O deadline or complete OS quota.
`audit.py --root <retained-root> --binary <worker> --public <sanitized-json>` binds
source/binary and captured events, hashes readable evidence, and records inaccessible
roots without ACL repair. Private captures, paths, SIDs and binaries stay local.
