# Interrupted Windows transaction inspection

**#0036**, observed **2026-10-13**, extends the existing
[#0032 marker worker](../0032-windows-publication/README.md). The record parser and
state classifier are ordinary Rust functions tested on every CI platform. The
Windows adapter reuses existing file, identity, owner-policy and stream checks;
no new OS API or unsafe boundary is added.

```console
cargo fmt --manifest-path experiments/0032-windows-publication/Cargo.toml --check
cargo clippy --locked --manifest-path experiments/0032-windows-publication/Cargo.toml --all-targets -- -D warnings
cargo test --locked --manifest-path experiments/0032-windows-publication/Cargo.toml
cargo build --locked --release --manifest-path experiments/0032-windows-publication/Cargo.toml
python experiments/0036-windows-inspection/qualify.py --binary experiments/0032-windows-publication/target/release/imageinfo-windows-publication-probe.exe --parent .local/windows-inspection-qualification
```

The executable takes an explicit absolute local root and a mode: `<root> inspect`,
`<root> finalize`, `<root> prune`, or an existing worker mode. Inspection reads only
`prepared.record`, `intent.record`, `observation.record`, `candidate.bin` and
`output.bin`; it never follows a target path from a record. Finalize/prune/admit
refuse before effects. Non-Windows adapters refuse; portable tests still run there.

The existing wire format, checksum library and pinned graph are reused. No
encryption, receipt keys, account/service setup or new cryptographic facility is
introduced. Records describe observations; checksums and matching IDs do not grant
mutation authority or prove a committed/durable outcome.

The 35 cases use actual process kills/cancellations at nine worker barriers, normal
exit, invalid records, missing/changed outputs, a self-consistent changed record/data
pair, and refusal modes. Every inspected root is inventoried before/after by file
ID, bytes and modification time. No original media, OS crash or cleanup occurs.
The reused capture helper supplies a 60-second process watchdog, 15-second message
waits and 32-byte controls. Records/markers are bounded at 64 KiB; enumeration stops
after 17 entries and refuses unexpected leaves.

`audit.py --root <retained-root> --binary <worker> --public <sanitized-json>` binds
source/binary, checks reports and unchanged inventories, and hashes retained evidence.
Private IDs, hashes, paths, captures and binaries stay local. See the
[measured results](../../docs/write-safety/windows-inspection.md),
[dependency verification](../../docs/write-safety/windows-inspection-dependencies.json)
and [CI](../../docs/write-safety/windows-inspection-ci.json).
