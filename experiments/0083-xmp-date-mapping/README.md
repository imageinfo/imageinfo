# One-way date mapping model (#0083)

Authored, standalone research only. `compare` evaluates one explicit CMT2 original
date bundle against one selected existing XMP date property, producing a typed
comparison/intent. It performs no I/O, serialization, sidecar creation, reparse of
RAW data, mutation, chaining, instant conversion or host timezone lookup.

See the [versioned decision](../../docs/sidecars/date-mapping.md),
[source](src/lib.rs) and [authored vectors](tests/vectors.rs). The only direct
dependency is the sibling #0081 research component; its pinned roxmltree/memchr
packages and notices remain governed by its
[component review](../../docs/sidecars/xmp-component.md). No new third-party
component or root runtime dependency is introduced.

```powershell
cargo fmt --manifest-path experiments/0083-xmp-date-mapping/Cargo.toml --all --check
cargo clippy --manifest-path experiments/0083-xmp-date-mapping/Cargo.toml --locked --all-targets -- -D warnings
cargo test --manifest-path experiments/0083-xmp-date-mapping/Cargo.toml --locked
cargo build --manifest-path experiments/0083-xmp-date-mapping/Cargo.toml --locked --release
```

All examples are invented date text and XML; no private corpus bytes are included.
