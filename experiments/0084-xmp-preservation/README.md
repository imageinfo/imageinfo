# One-date XMP lexical preservation (#0084)

Standalone, authored research. `prepare` receives immutable sidecar bytes, the
original #0083 snapshot, a selected existing target ordinal and explicit conflict
policy. It recomputes #0081 inspection/#0083 comparison and returns either borrowed
unchanged bytes or a separately owned in-memory derivative. It performs no file
I/O, XML serialization, RAW editing, publication or production admission.

See the [qualification guide](../../docs/sidecars/date-preservation.md),
[implementation](src/lib.rs) and [independent authored tests](tests/qualification.rs).
Every test fixture is authored synthetic XML under the project's MIT license;
no private media, sidecar contents or derivatives are distributed here.

The sibling #0081/#0083 crates remain research dependencies. roxmltree 0.21.1
additionally enables `positions` here to recover actual lexical spans; its only
registry dependency remains memchr 2.8.3. Retain the existing
[dependency notices](../0081-xmp-model/notices/) with redistributions. No upstream
source is copied and root dependencies/CLI remain unchanged.

```powershell
cargo fmt --manifest-path experiments/0084-xmp-preservation/Cargo.toml --all --check
cargo clippy --manifest-path experiments/0084-xmp-preservation/Cargo.toml --locked --all-targets -- -D warnings
cargo test --manifest-path experiments/0084-xmp-preservation/Cargo.toml --locked
cargo build --manifest-path experiments/0084-xmp-preservation/Cargo.toml --locked --release
```

The returned ranges describe the entire replaced lexical date value. They are not
a minimal differing-byte set or permission to apply a patch to a file/path later.
