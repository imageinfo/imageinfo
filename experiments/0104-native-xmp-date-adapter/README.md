# Native original-date to XMP candidate adapter (#0104)

This standalone research crate parses actual immutable CR3 bytes with the root
native reader and feeds the observed CMT2 original-date bundle into #0084's
in-memory lexical derivative. The caller supplies no RAW date values, parsed
Metadata, source occurrence IDs or coverage Boolean.

It exposes no file I/O, output path, publication, RAW mutation, new sidecar
creation, existing-sidecar replacement or storage-admission API. #0085 remains
separately gated on an actually applicable storage profile; #0051 currently admits
none. See the [bounded guide](../../docs/sidecars/native-date-adapter.md),
[implementation](src/lib.rs) and independent [qualification](tests/qualification.rs).

```powershell
cargo fmt --manifest-path experiments/0104-native-xmp-date-adapter/Cargo.toml --all --check
cargo clippy --manifest-path experiments/0104-native-xmp-date-adapter/Cargo.toml --locked --all-targets -- -D warnings
cargo test --manifest-path experiments/0104-native-xmp-date-adapter/Cargo.toml --locked
cargo build --manifest-path experiments/0104-native-xmp-date-adapter/Cargo.toml --locked --release
```

The path dependency reuses the existing root library without changing root source,
dependencies or lockfile. #0083/#0084 remain sibling research crates. The standalone
lock retains the reviewed root registry closure and roxmltree/memchr versions;
existing project and [XML notices](../0081-xmp-model/notices/) still apply. No
third-party implementation or private fixture is vendored here.
