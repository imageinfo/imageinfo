# Bounded privacy coverage observations (#0088)

Standalone research using the actual existing root reader and #0081 XMP subset.
It reports the named #0087 catalog's declared locations, actual reader opaque
allocation candidates, recognized previews and optional explicitly selected XMP
properties. It performs no removal, mutation or privacy certification and changes
no root parser, command or dependency.

Reports from restricted media remain **private**, including their counts, ranges,
flags and hashes held by a separate audit. Omitting decoded values does not grant
publication permission. See the [guide](../../docs/privacy/read-coverage.md),
[implementation](src/lib.rs) and [independent authored tests](tests/qualification.rs).

```powershell
cargo run --manifest-path experiments/0088-privacy-coverage/Cargo.toml --locked --release -- selected.cr3
cargo run --manifest-path experiments/0088-privacy-coverage/Cargo.toml --locked --release -- selected.cr3 --sidecar selected.xmp
```

The standalone program opens only explicitly supplied regular-file inputs, reads
bounded byte snapshots and writes the JSON report to stdout. It creates no report
file by itself, discovers no sidecar and accepts no write/delete options. Its
process argument/output handling is research-specific, not the production CLI
contract. Callers must direct restricted output only to authorized private storage.

```powershell
cargo fmt --manifest-path experiments/0088-privacy-coverage/Cargo.toml --all --check
cargo clippy --manifest-path experiments/0088-privacy-coverage/Cargo.toml --locked --all-targets -- -D warnings
cargo test --manifest-path experiments/0088-privacy-coverage/Cargo.toml --locked
cargo build --manifest-path experiments/0088-privacy-coverage/Cargo.toml --locked --release
```

The standalone lock reuses the exact root registry versions/checksums and reviewed
roxmltree 0.21.1 XMP dependency. Existing root and
[XML notices](../0081-xmp-model/notices/) remain required for redistribution.
No third-party parser/table source or private fixture is imported.
