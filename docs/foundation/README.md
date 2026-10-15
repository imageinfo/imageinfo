# Executable and CLI foundation

Subsequent #0020 implements the [native R5 slice](../reader/README.md).
The foundation record below describes its original increment; current read/list/
extract behavior and tests are authoritative in the linked reader guide.
Subsequent #0027 supplies [read-only field/admission observations](../write-safety/write-admission.md)
through the library and a separate research executable. Product CLI writes remain
unsupported; neither a field match nor a read-only query authorizes mutation.
Subsequent #0055/#0076/#0077 add the bounded
[saved date-preview contract](../legacy-compatibility/cr3-preview-plan.md),
[nonmutating CLI preview](../reader/date-preview.md), and
[source-content revalidation](../legacy-compatibility/cr3-preview-source-binding.md).
#0082 adds [explicit path pairing](../sidecars/pairing.md). These implemented
read-only boundaries preserve all format/storage admission and caller-authority gates.

Implemented under **#0019**, 2026-10-10, after Terry accepted Rust/ADR-0011.
This package provides a production library/binary boundary, command definitions,
help, version output and explicit refusals. It contains no CR3 parser or writer.
The first reader is separately scoped on #0020.

## Build and check

Install Rust through the [official rustup instructions](https://rustup.rs/).
On Windows, the MSVC toolchain also needs the C++ build tools/linker described in
the [Rust installation guide](https://doc.rust-lang.org/book/ch01-01-installation.html).
Linux also needs a native C compiler/linker (GCC or Clang, such as Ubuntu's
`build-essential` package); macOS needs the compiler/linker and SDK supplied by
Xcode Command Line Tools or Xcode. The same official guide describes these
prerequisites. The verified hosted images already provide them; installing them
on a bare OS was not exercised by the contributor check.
Documentation/schema QA also needs Python 3.10 or newer available as `python`, with pip
(the pinned `jsonschema` package's declared installation minimum).
Install its pinned QA dependency in a disposable or isolated Python environment;
it is separate from the Cargo graph and imageinfo runtime. Then, at the repository root:

```console
rustup toolchain install 1.99.0 --profile minimal --component clippy,rustfmt
python -m pip install jsonschema==4.26.0
cargo build --locked
cargo run --locked -- help
cargo run --locked -- metadata read help
cargo run --locked -- version --output json
cargo fmt --all --check
cargo clippy --locked --all-targets -- -D warnings
cargo test --locked
python scripts/check_output_schemas.py
cargo build --locked --release
python scripts/check_docs.py
```

`rust-toolchain.toml` pins **Rust 1.99.0**, including rustfmt/clippy. Cargo declares
**MSRV 1.99**: this is the minimum this foundation promises and tests, not a claim
that every line or dependency requires that compiler. Lowering it needs a separate
tested change. Ordinary dependency resolution is recorded in the root Cargo.lock;
use `--locked`, and use `--offline` after populating a trusted dependency cache.
Build-time downloads are separate from runtime: help/version/refusal dispatch
uses no network, media or user-configuration access.

The [clean hosted contributor verification](../contributing/clean-machine.md)
maps these checks to actual Windows, Ubuntu and macOS jobs at an exact source
revision. Its fresh hosted images include development prerequisites; bare-OS
installation and a fully locked Python environment remain separate.

The installed development executable is `target/debug/imageinfo` on Unix or
`target/debug/imageinfo.exe` on Windows. `cargo build --locked --release` produces
the release-profile executable locally; there is no public packaged release yet.

## Implemented command subset

| Invocation | Actual behavior |
| --- | --- |
| Bare root/group, `help`, `--help` | Plain contextual help, status 0, no inputs opened |
| `help metadata read`, `metadata help read`, `metadata read help` | The same leaf help |
| `version`, `--version` | Version and current implementation scope; text or JSON |
| `metadata read <inputs...>` | `CAPABILITY_UNSUPPORTED`, status 1, before selection/media access |
| `metadata read` | `MISSING_ARGUMENT`, status 2; contextual help suppresses this requirement |
| Valid syntax plus `--interactive` | `INTERACTION_UNAVAILABLE`, status 2; no implicit menu |
| Invalid command/option/value or duplicate scalar | Usage error, status 2; help cannot hide malformed syntax |

Only `text` and `json` result formats are accepted. Help is always plain text,
including with `--output json` or `--color always`. Color preference is parsed
for consistency; this foundation does not generate ANSI, launch a pager, or read
stdin. Menus, completions, data configuration, JSONL and other formats follow in
their own increments.

Global presentation/help options work at root, group or leaf before `--`. Scalar
`--output` and `--color` may occur only once across levels. Leaf `--values` is one
of `raw`, `normalized`, `display`, `all`; repeated `--tag` retains each supplied
value. These settings are parsed requests, not evidence of implemented tag reads.
Unknown long-option abbreviations are rejected. Paths are native `PathBuf` values;
literal `help`, leading-hyphen, Unicode and newline-containing names use `--`.
The parser does not perform an extra shell/glob expansion.

## Output and error boundaries

Successful version JSON follows [version.schema.json](version.schema.json) and
reports `mediaReadingImplemented: false`. Once arguments have parsed successfully,
request validation/refusal JSON uses the implemented no-selection subset of the
[result envelope](../legacy-compatibility/result.schema.json). It has stable issue
codes, status, a shared request ID, zero discovered inputs, empty file/artifact
arrays, `selectionComplete: false`, and `outputComplete: true` only for a finished
report. The binary writes diagnostics to stderr and result data to stdout.

**#0037 update, 2026-10-13:** Syntax failures now emit the existing status-2 JSON
envelope when exactly one valid explicit output selector is present before `--`.
Absent, invalid or duplicate output selection keeps bounded plain stderr. Literal
operands and attached option data do not select a format; valid help stays text.
See [native JSON errors](../legacy-compatibility/native-json-errors.md) for the
implemented routing boundary. Broader #0015/LG-006 CLI/API/session compatibility
remains open. The original #0019 foundation initially used plain stderr for grammar
failures; that limit is superseded only for this scoped routing cell.

Output transport failures return status 1 when the process can report it, with
`OUTPUT_INCOMPLETE` on stderr if possible. A truncated stream is not a complete
result. User control characters in diagnostics are escaped. No returned refusal
claims that a source was examined or that a supplied path was absent.

## Ordinary code boundaries

`src/cli.rs` constructs one inspectable clap command tree, validates settings and
returns a typed invocation. It has no file/configuration access. Help subcommands
resolve paths through that same tree rather than a second grammar. Common options
retain separate matches at each scope so duplicate scalar values cannot disappear.
The nearby comments explain these departures from clap's normal shortcuts.

`src/output.rs` owns the small implemented wire records. `src/main.rs` adapts the
typed invocation to stdout/stderr and exit status. The public synthetic metadata
fixture is exercised only by tests; the binary never emits invented camera data.
No async runtime, service framework, parser framework or production code from the
disposable #0011 experiments is introduced.

The dependency graph, licenses and notice retention are recorded in
[dependencies.json](dependencies.json) and [THIRD_PARTY_NOTICES.md](../../THIRD_PARTY_NOTICES.md).
No dependency implementation is vendored. A public binary release still requires
review of the actual assembled artifacts/notices and release-readiness controls.

## Verification and platform matrix

The [CI workflow](../../.github/workflows/ci.yml) runs formatting, clippy, library/
process contract tests, a release build, and public documentation/JSON checks on
Windows x64, Ubuntu x64 and macOS arm64. The workflow uses an immutable checkout
action pin and read-only repository permissions; personal media never enters CI.
Its scoped acquired identity/license review is in [ci-action.json](ci-action.json).
Runner labels are `windows-2025`, `ubuntu-24.04`, `macos-15`, observed against the
[GitHub runner reference](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
on 2026-10-10. These jobs are foundation test environments, not an OS support promise
for the future RAW reader or an installer/distribution matrix.

See the [validation record](validation.md) for actual results and remaining scope.
