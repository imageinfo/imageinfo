# Implementation decision: Rust for the first R5 reader

**ADR-0011 — Recommendation ready for review, 2026-10-10.** Terry opened language
selection by authorizing card #0011 and explicitly permitted disposable spikes.
This supersedes the earlier deferral for this evaluation. It does not record Terry's
acceptance of Rust or authorize calling the prototypes production imageinfo.

**Recommend Rust, edition 2024, with Cargo, a small synchronous library and CLI,
clap for command definitions, and Serde/serde_json at the JSON boundary.** Use the
standard library for bounded file access and binary primitives. Start with one
Cargo package containing a library and a thin binary; split crates only when an
actual independent consumer or dependency boundary warrants it.

The deciding benefit is control over byte ownership and resource lifetimes while
keeping the parser in safe code. Rust's ownership checks operate without a tracing
garbage collector [S01]. That fits large RAW files with small selected metadata
regions. It does **not** establish faster execution, lower memory use, correct
parsing, safe writes, or immunity to allocation failure.

The cost is real: ownership/lifetime reasoning and dependency/build tooling can
make contribution harder. Favor owned metadata records and explicit file ranges
over a zero-copy object graph tied to a giant mapped file. The spike provides a
small feasibility check, not a maintainer productivity study.

Read the [comparison and sources](comparison.md), [first milestone](first-milestone.md),
[spike findings](spikes.md), and [validation](validation.md). Bracketed S references
resolve to the source ledger in the comparison document.

## Selected direction and deferred details

| Area | Recommendation | Reason and boundary |
| --- | --- | --- |
| Language | Rust 2024 edition, stable compiler | Safe parsing and explicit ownership; no nightly product requirement. Tested locally with 1.99.0, not a promise that it is the minimum supported compiler. |
| Build | Cargo, committed application lockfile, pinned toolchain at bootstrap | Ordinary Rust workflow and explicit resolved dependencies [S03]. Pick/test an MSRV before advertising it. |
| Core | Synchronous library functions, structs/enums, `Result` and ordinary collections | File-oriented first slice needs neither an async runtime nor service framework. CLI concerns stay outside parsing. |
| CLI | clap 4.x builder definitions plus a small policy adapter | Definitions are inspectable for help and future menus [S04]. Tested version 4.6.7 needs explicit help/duplicate policy; see spike findings. |
| JSON | Serde 1.x and serde_json 1.x, explicit wire structs | Keep native exact values separate from decimal-string/binary wire forms. The tiny round trip is not full schema conformance [S05]. |
| Binary access | `File`, `Read`, `Seek`, checked arithmetic, bounded buffers | No whole-file load or memory mapping by default. A bounded top-level scanner was feasible in both Rust and Go [S06]. |
| Parsing | Small independently authored CR3/BMFF and TIFF/EXIF readers for the declared slice | This is product-specific work, not a new general parsing framework. Evaluate a third-party parser for coverage, limits, provenance and maintainership before replacing it; no suitable complete CR3 dependency was established here. |
| XMP | Defer XML dependency selection until the XMP increment | A full XML parser is not something to invent casually. Require namespace/encoding fidelity and explicit entity/expansion/resource behavior in a focused evaluation. |
| Menus | First implement plain line navigation over the same command/request definitions | Contextual help remains mandatory. Terminal widgets, completion and richer navigation are later bounded additions, not reasons to adopt a UI framework now. |
| Tests | Cargo tests, public synthetic cases, private admitted differential corpus | Standard tools first. A separate pinned nightly fuzzing job can use cargo-fuzz; nightly does not become the product compiler [S07]. |
| Distribution | Per-target native CLI artifacts, initially Windows x64 validation plus Linux x64/macOS arm64 CI gates | These targets are a proposed initial matrix, not tested releases. OS baselines, signing, installers and package-manager delivery remain bootstrap/release decisions [S02]. |
| Extensibility | Compiled-in definitions initially, later reviewed declarative data | No arbitrary callbacks, embedded interpreter, dynamic plugin ABI or generic rule engine in the first slice. Full parity remains a future goal. |

Exact first-spike versions are locked in the [research Cargo.lock](../../experiments/0011-language-selection/rust/Cargo.lock).
They do not freeze the future product dependency set. Resolve security, licenses,
notices, MSRV and necessary features on the exact bootstrap graph; then pin it.
The [research dependency review](dependency-review.json) records this probe's graph.
MIT remains the project's accepted license; dependency terms remain their own.

## Keep the implementation ordinary

Start with one library API taking a source and read options and returning a
snapshot plus diagnostics. Give file access, CR3 traversal, metadata decoding and
output formatting clear names; organize modules as code earns them. Do not turn
every responsibility in the architecture notes into a trait or crate.

Use `u64` file offsets with checked addition/multiplication and checked conversion
to allocation/index sizes. Keep counts, nesting and decoded-byte budgets explicit.
Retain exact rationals and float bit patterns where required. Keep binary resources
as checked ranges or bounded owned buffers, and use `Path`/`OsString` for filesystem
inputs [S08]. Rust strings are not a universal filename representation.

Forbid unsafe code in the first-party reader initially. That does not certify
dependencies or the standard library as unsafe-free [S09]. Avoid unchecked indexes,
`unwrap` on input-dependent states, self-referential structures, macro-generated
parsers, pervasive lifetimes and speculative abstraction. The disposable probe
intentionally uses assertions/panics and lacks production diagnostics; rewrite it
when implementing, rather than promoting it.

Fallible reservation helps some allocations [S10]; it is not a hard process-memory
limit. Budget checks, fallible paths, OOM handling and any OS containment need their
own evidence. Blocking filesystem I/O cannot be given a reliable wall-clock deadline
merely by checking elapsed time between reads. The first release must state the
limits it actually enforces and what cancellation can interrupt.

Future safe mutation still requires #0014's platform-specific concurrency,
publication, preservation and recovery evidence. RAII, file flushes and memory
safety do not establish those guarantees. Do not enable embedded writes as a
side effect of choosing Rust.

## What could change the recommendation

**Go is the preferred fallback.** Its standard-library reader spike was equally
straightforward and passed the same header cases. If a representative metadata
slice needs intricate Rust lifetimes/unsafe code to meet ordinary requirements,
or independent contributors cannot comfortably maintain it, revisit Rust against
Go before expanding the implementation. Go's GC is an engineering tradeoff, not
a correctness failure or measured performance disadvantage [S11].

C# remains credible where the actual contributor team strongly favors .NET. Native
AOT can remove the end-user runtime-install requirement but introduces deployment
constraints [S13]. Lack of a local SDK prevented a C# spike; it is not a language
disqualification. A team-preference change deserves a comparable prototype.

No language prevents a new single-maintainer bottleneck. Small reviewed changes,
public synthetic tests, documented format knowledge and backup ownership from
#0017 remain necessary. Claims about recruitment, ecosystem longevity or performance
are not established by repository stars, package counts or this comparison.

## Handoff

Acceptance of this card records the Rust direction and the bounded first-milestone
plan. Architecture remains iterative. **#0019** bootstraps the chosen toolchain
and proves the shared command/help contract with synthetic inputs; **#0020** follows
with bounded container reading and the first exact metadata mappings.
No production implementation or full R5 read support is delivered by this card.
