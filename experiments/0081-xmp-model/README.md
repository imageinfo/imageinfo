# Bounded XMP component and identity research (#0081)

This standalone crate implements a small read-only inspection model over authored
XML. It is outside the root package and has its own reviewed lockfile. It performs
no file I/O, network lookup, pairing, date conversion, rewriting or mutation.

See the [component decision](../../docs/sidecars/xmp-component.md) for exact
provenance, limits, model choices and refused cells. Source and tests are authored
for imageinfo; no upstream parser source, tag tables, specification text or media
fixtures are vendored. Dependency notices are retained in [notices](notices/).

Run with the repository's pinned Rust toolchain:

```powershell
cargo fmt --manifest-path experiments/0081-xmp-model/Cargo.toml --all --check
cargo clippy --manifest-path experiments/0081-xmp-model/Cargo.toml --locked --all-targets -- -D warnings
cargo test --manifest-path experiments/0081-xmp-model/Cargo.toml --locked
cargo build --manifest-path experiments/0081-xmp-model/Cargo.toml --locked --release
```

The vector tests assert complete typed identity/value results where material,
plus parser, shape, language and exact boundary refusals. Passing these authored
vectors does not qualify real-camera XMP, production parsing, writing or the
complete metadata contract.
