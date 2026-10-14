# #0022 option A source/output protocol

Research implementation under the existing In progress **#0022**, after Terry's
explicit OD-11 option A decision on **2026-10-14**. No new card is pulled into work.
Rust lives in the existing [#0032 crate](../0032-windows-publication/README.md), with
the same dependencies and reviewed SDK. Root production code/unsafe policy is unchanged.

```console
cargo test --locked --manifest-path experiments/0032-windows-publication/Cargo.toml
cargo build --locked --release --manifest-path experiments/0032-windows-publication/Cargo.toml
python experiments/0022-ordinary-output/qualify.py --binary experiments/0032-windows-publication/target/release/imageinfo-windows-publication-probe.exe --parent .local/ordinary-output-qualification
python experiments/0022-ordinary-output/audit.py --root <retained-private-run> --binary experiments/0032-windows-publication/target/release/imageinfo-windows-publication-probe.exe --public docs/write-safety/ordinary-output-observations.json
```

The probe uses an explicitly selected new private root with fixed `source.marker`,
`candidate.marker`, `output.marker` and three record leaves. `ordinary-prepare`
creates an exclusively owned root and authored 64 KiB source; `ordinary` opens the
existing source read-only and copies its exact bytes while retaining default-stream
byte/name guards. Only this known marker payload is accepted, never camera media.
The ordinary private-owner policy is used at creation throughout; no source sealing,
DACL release call or owner/privilege changes are performed by the worker.

Checkpoints cover source preflight, prepublication properties, and installed output.
The candidate is renamed by its creating handle without replacement. Successful
namespace calls are distinct from passed installed checks and qualified persistence.
All outcomes remain observation/recovery-required; there is no committed receipt or
production profile. Before publication, cooperative cancellation checks and deletes
only live files created by this invocation through retained handles, preserving the
input/root/foreign entries. Once a namespace call is attempted, artifacts remain.

`ordinary-inspect` bounds and validates typed checksummed records and actual fixed
artifacts read-only; it grants no repair. `ordinary-admit`, `ordinary-finalize` and
`ordinary-prune` refuse before effects. Legacy #0032/#0036 commands remain separate.
Other OS filesystem adapters refuse; portable record/staging tests still run there.

Native qualification has 64 cases: byte/name actors and late aliases, property changes
at the observation boundaries, preexisting writers/mappings, foreign collision,
eight kill/cancel/failure boundaries, ordinary owner editing after exit and restart
record/namespace conflicts. Property-only actors intentionally alter newly owned
test markers. No user media/original ACL is touched. Inventories verify 56 read-only
inspection runs leave bytes, identity, modification times, attributes and link counts
unchanged, apart from normal access-time semantics. Inaccessible files stay untouched.

Two labeled malformed producer-stream cases retain partial stages and pending work
even when copying fails before the owned-artifact constructor returns. They do not
simulate or claim native ENOSPC/EIO. The logical staging cap is 262,144 bytes: one candidate plus three bounded records;
source and old retained runs are excluded. Reads/records are bounded to 65,536 bytes,
control lines to 32 bytes, process watchdogs to 60 seconds and message waits to 15.
These are not OS quotas or hard I/O deadlines. Local NTFS observations do not prove
all future interleavings, kernel versions, providers, OS crashes or physical power loss.

`windows_guest.py` prepares a disposable official evaluation guest for the separate
Windows interruption qualification. Generated credentials/ISO/disks/state/captures
must stay private. It exposes no host disks/shared folders; QEMU opens KVM using
the existing root launcher then drops to the ordinary WSL uid/gid before guest code.
The Windows worker runs as a standard local test user; provisioning/crash settings
belong only to this disposable guest. See [the guest notes](../../docs/write-safety/windows-guest.md).
