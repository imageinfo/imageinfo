# Source and stage guard qualification

Card **#0029**, observed **2026-10-11**. Research only: no production metadata writer,
supported publication profile or recovery authority is enabled. See
[the qualification ledger](../../docs/write-safety/object-guards.md).

```console
cargo fmt --manifest-path experiments/0029-object-guards/Cargo.toml --check
cargo clippy --locked --manifest-path experiments/0029-object-guards/Cargo.toml --all-targets -- -D warnings
cargo test --locked --manifest-path experiments/0029-object-guards/Cargo.toml
cargo build --locked --release --manifest-path experiments/0029-object-guards/Cargo.toml
python experiments/0029-object-guards/qualify.py --binary PATH_TO_BUILT_PROBE --parent PRIVATE_SCRATCH_PARENT
```

Use the pinned Rust toolchain and separate lockfile. Public qualification accepts
marker data only; separate private admission supplies camera-image clones. Scratch
directories remain for inspection. No original image, host configuration, lease
timeout or privilege setting is changed.

Windows commands `hold-source ABSOLUTE_FILE` and `hold-stage ABSOLUTE_DIRECTORY`
hold ordinary read-share-only handles plus directory ancestor handles. The stage
uses exclusive new-file creation. Compatible reads remain possible; new content
writes/delete opens are denied through the held object, including aliases. A held
write handle or writable mapping makes source guard acquisition refuse. Safe
`winapi-util` exposes the live handle's volume/file identity without nightly Rust
or application-owned unsafe code. Normal bounded DOS paths only; UNC/device/
verbatim/long/reparse paths are explicitly unverified/refused in this probe.

The probe waits on a stdin barrier and rereads the actual held file. It grants no
publication permission. Sharing does not exclude timestamp/ACL/attribute changes;
reported `propertiesUnchanged` covers the measured fields only. Fixed local volume
mapping and the measured NTFS environment are assumptions, not runtime admission
of all drives or filesystems. Network, removable, cloud, provider and privileged
namespace behavior remains unverified. Ancestor handles can temporarily prevent
ancestor-directory rename; they do not stop unrelated child creation.

Linux `anonymous-stage PRIVATE_DIRECTORY` uses `O_TMPFILE` and a checked procfs
descriptor view to link the held inode into the bound directory with conditional
absence. It follows no user-imported stage filename. This prevents the #0028 named
stage poisoning case, but does not protect every access route or a writable output
after publication, and does not promise the parent pathname remains unchanged.
Unsupported filesystem/procfs/API conditions refuse without a named-stage fallback.

The Linux standard-library lease helper is an OS qualification tool, not an adopted
production Rust lease implementation. Read leases reject preexisting writers/maps;
competing write opens block and trigger a break notification. Tests observe a
pending break and require refusal of publication, then release the lease explicitly.
Leases allow namespace/metadata changes and can be forcibly broken after the kernel
timeout. We do not wait for forced expiry, alter that timeout, or claim a hard I/O
deadline. They are not an unbounded publication guard or an advisory-lock substitute.

All result records state zero production profiles. A successful content/object test
cannot grant a full source/path/property/publication/durability capability. #0030
and #0031 retain properties, persistence and guarded recovery; production integration
still needs the complete #0022/#0027/#0023 evidence. Do not promote a probe by changing
a support boolean.

See [scoped notices](NOTICES.md) and
[dependency admission](../../docs/write-safety/guard-dependencies.json). Root
production dependencies remain unchanged. No upstream implementations, media,
full tag tables or executable releases are included.
