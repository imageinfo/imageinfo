# Alternatives and primary-source evidence

Observed **2026-10-10**. The recommendation is engineering judgment against the
accepted requirements, not a benchmark ranking or proof that only one language
can work. The small Rust/Go probes provide additional local evidence.

## Shortlist

| Criterion | Rust | Go | C# / modern .NET |
| --- | --- | --- | --- |
| Untrusted byte parsing, PR-026 | Safe slices, ownership and explicit integer checks; unsafe dependencies still require review | Bounds-checked slices and ordinary explicit errors; integer/range checks still required | Managed memory and span-based APIs; explicit length/range checks still required |
| Exact metadata model, PR-003 / MDL rules | Enums/structs naturally express alternatives; ordinary integer/rational records | Structs/interfaces or explicit discriminants work; validate combinations deliberately | Records/classes/enums and explicit discriminants work; validate combinations deliberately |
| Large files and bounded work, PR-028 | Explicit lifetimes and allocation choices suit file ranges; not an automatic memory cap | `ReadSeeker` and standard endian helpers make a simple bounded reader; GC soft limit is not a hard cap | Stream/span approaches are viable; managed allocation and AOT implications require measurement |
| CLI/help, CLI-001–009 | clap supports an inspectable command tree; local probe needed policy adaptation | Standard `flag` alone is not the full hierarchy/menu solution; a library such as Cobra would need equivalent contract tests | A command library would need equivalent contract tests; not exercised here |
| Cross-platform delivery, PR-023 | Native builds for declared Rust targets; native OS testing remains necessary | GOOS/GOARCH support and ordinary compiled tools; target/OS behavior still needs testing | Self-contained or Native AOT delivery possible; AOT feature and platform restrictions matter |
| Maintenance, PR-030 | Consistent Cargo workflow; ownership can raise onboarding cost | Smaller set of everyday language mechanisms and a documented Go 1 compatibility commitment | Familiar to .NET contributors; deployment/reflection choices need explicit discipline |
| Extensibility | Data-first extensions fit; native ABI/interpreters are not needed initially | Data-first extensions fit; language choice does not translate Perl callbacks | Data-first extensions fit; AOT is not compatible with every dynamic-code strategy |
| Evidence here | 21 CLI cases, exact wire example, six synthetic header cases and eight private file walks | Same six synthetic header cases and eight private file walks | Official documentation only; no SDK/prototype |
| Decision | **Recommended for the core and CLI** | **Strong fallback** | Credible alternative if contributor needs favor it |

The Go spike avoids reflection, unsafe code and nonstandard parser libraries. It
shows that Rust's recommendation is a preference for ownership/resource semantics,
not a claim that Go cannot parse safely. We have no comparative startup, throughput,
memory, binary-size or development-time measurement. C#'s missing local SDK did not
increase Rust's score; no numeric scoring system is used.

C/C++ would make first-party memory-safety discipline a larger design burden than
this project needs. Python or TypeScript could support research and orchestration,
but are not the first choices for the independently distributed binary-parser core.
These are shortlist judgments, not claims that those languages cannot implement it;
they were not benchmarked or subjected to a comparable prototype.

## Source ledger

Sources establish the named language/library behavior, not imageinfo correctness.
Living documentation was retrieved on the observation date. Where no immutable
revision is supplied by the page, that limitation is explicit; executable probe
versions and the dependency lockfile provide the stronger local identity.

| ID | Primary source | Observation used |
| --- | --- | --- |
| S01 | [Rust ownership](https://doc.rust-lang.org/book/ch04-01-what-is-ownership.html) | Compile-time ownership and scoped release; learning cost acknowledged by the book. Living documentation. |
| S02 | [Rust target support](https://doc.rust-lang.org/rustc/platform-support.html) | Support tiers distinguish target guarantees; target support does not replace application tests. Living documentation. |
| S03 | [Cargo manifests and lockfiles](https://doc.rust-lang.org/cargo/guide/cargo-toml-vs-cargo-lock.html), [MSRV field](https://doc.rust-lang.org/cargo/reference/manifest.html#the-rust-version-field) | Separate declared compatibility, resolved graph and compiler policy. Living documentation. |
| S04 | [clap 4.6.7](https://docs.rs/clap/4.6.7/clap/), [Command API](https://docs.rs/clap/latest/clap/struct.Command.html) | Hierarchy, builder/introspection, configurable help. Crate overview is pinned to the spike version; Command API is living documentation. CLI requirements still need an adapter. |
| S05 | [Serde overview](https://serde.rs/), [serde_json repository](https://github.com/serde-rs/json) | Typed serialization boundaries; no automatic guarantee of imageinfo's lossless contract. Living sources; spike resolves Serde 1.0.229 / serde_json 1.0.152. |
| S06 | [Rust Read](https://doc.rust-lang.org/std/io/trait.Read.html), [Go encoding/binary](https://pkg.go.dev/encoding/binary) | Ordinary bounded buffers/endian decoding. Living API pages; local toolchains are recorded separately. |
| S07 | [cargo-fuzz setup](https://rust-fuzz.github.io/book/cargo-fuzz/setup.html), [Go fuzzing](https://go.dev/doc/security/fuzz/) | Rust fuzz tooling has sanitizer/compiler prerequisites; Go has native fuzz tooling. No fuzz campaign ran for this card. |
| S08 | [Rust Path](https://doc.rust-lang.org/std/path/struct.Path.html) | Filesystem paths are not limited to Unicode strings. Living API documentation, reported as 1.99.0 when retrieved. |
| S09 | [Unsafe Rust](https://doc.rust-lang.org/book/ch20-01-unsafe-rust.html) | Safe interfaces may encapsulate unsafe implementations; first-party prohibition is not a whole-stack proof. Living documentation. |
| S10 | [Vec::try_reserve](https://doc.rust-lang.org/std/vec/struct.Vec.html#method.try_reserve) | Fallible reservation exists; broad OOM/resource policy remains application work. Living API documentation, reported as 1.99.0 when retrieved. |
| S11 | [Go GC guide](https://go.dev/doc/gc-guide) | GC tradeoffs and explicitly soft runtime memory limit; no claim of hard isolation. Living documentation. |
| S12 | [Go compatibility](https://go.dev/doc/go1compat), [target environment](https://go.dev/doc/install/source#environment) | Go 1 compatibility commitment has caveats; target selection is not platform proof. Living documentation. |
| S13 | [.NET Native AOT](https://learn.microsoft.com/en-us/dotnet/core/deploying/native-aot/), [JSON source generation](https://learn.microsoft.com/en-us/dotnet/standard/serialization/system-text-json/source-generation) | Self-contained native deployment, dynamic-code/reflection constraints and source-generated serialization options. Living documentation. |
| S14 | [Rust 2024 edition](https://doc.rust-lang.org/edition-guide/rust-2024/index.html) | Edition available since Rust 1.85; choosing it does not establish the product MSRV. |
| S15 | [clap licenses](https://github.com/clap-rs/clap), [Serde licenses](https://github.com/serde-rs/serde) | Upstream MIT-or-Apache declarations; actual resolved artifacts reviewed separately. |

The exact research dependency versions/checksums, declared licenses and retained
notice hashes are in [dependency-review.json](dependency-review.json). No library
source or compiled dependency is vendored or redistributed by this change.
