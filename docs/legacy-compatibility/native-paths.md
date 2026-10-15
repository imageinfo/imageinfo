# Finite native read paths and declared shells

**#0059**, observed **2026-10-15**. The implemented `metadata read` and
`binary list` commands are exercised with actual native argv and actual shell
invocations over authored structural CR3 fixtures. This changes no production
grammar or file operation. It is the finite native interface route under LG-006;
no ExifTool executable or command translation is involved.

The [case ledger](native-paths/cases.json) enumerates 94 rows, with explicit
platform applicability, transport, native operands, created file contents and
expected status/error outcomes. Each of Windows's 70 applicable rows passed in
the [actual Windows report](native-paths/windows.results.json), using PowerShell
7.6.6. Linux and macOS each have 88 prescribed rows; their execution belongs to
the existing hosted CI jobs, and local Windows results do not qualify those
platforms. The [CI workflow](../../.github/workflows/ci.yml) and its retained
platform reports establish whether those jobs actually ran successfully.

## Exact finite scope

Every row selects JSON explicitly. Metadata reads select `Model`; binary listing
requires the exact three fixture resources `ThumbnailImage`, `PreviewImage` and
`JpgFromRaw`. The checker verifies file order, exact displayed path labels,
snapshot occurrence names, status, output channel, error/warning codes and absence
of artifacts. The ledger's supported observations, file refusals and syntax
refusals remain separate outcomes; an expected refusal passing does not mean the
refused syntax or pathname is supported.

| Rows | Paths and expected native behavior |
| --- | --- |
| NP-001–048 | Literal simple/space/Unicode names, precomposed and combining accents, leading hyphens, `--output=json`, `help`, single quote, dollar/backtick, semicolon/ampersand/parentheses and brackets |
| NP-049–056 | Two explicitly ordered input paths and a `./` relative path |
| NP-057–068 | Missing path yields `INPUT_IO`/status 1; leading hyphen without `--` yields `INVALID_OPTION`/status 2; empty operand yields `INVALID_INPUT`/status 2 |
| NP-069–084 | Unix-only double quote, wildcard-looking characters, literal backslash and embedded newline |
| NP-085–088 | macOS native invalid UTF-8 operand refuses with `INPUT_IO`/status 1 while its valid replacement-character neighbor remains readable |
| NP-089–092 | Linux native invalid UTF-8 operand reads its original fixture, with `PATH_DISPLAY_LOSSY`; a distinct lossy-label neighbor contains invalid sentinel data |
| NP-093–094 | Windows native unpaired UTF-16 surrogate operand reads its original fixture, with `PATH_DISPLAY_LOSSY`; a distinct lossy-label neighbor contains invalid sentinel data |

Common and Unix literal/native-byte groups cover both commands and both
transports. Windows surrogate rows use direct native argv only: the UTF-8 shell
script transport does not represent unpaired UTF-16. Windows-invalid filename
characters are tested only on Unix, without claiming Windows support. On macOS,
the invalid-byte name is deliberately not created; the actual attempted native
open must refuse instead of reconstructing and opening its valid lossy neighbor.
Linux and Windows place invalid data at the lossy neighbor so a lossy reopen
cannot produce the expected successful metadata result.

These path labels are output for people, not authority to reopen native inputs.
The successful non-Unicode rows explicitly require `PATH_DISPLAY_LOSSY`. Distinct
native path units remain separate in the fixture inventory even when their JSON
labels would coincide. Unicode accent cases run in separate directories; they do
not qualify normalization distinctions, case collisions or filesystem aliases.

## Actual shell boundary

Direct argv uses Python `subprocess.Popen(..., shell=False)` with one native
operand per list member; it exercises no shell tokenization. Declared shell rows
start an additional actual shell process, which parses a generated script and
invokes the native executable:

```console
pwsh -NoLogo -NoProfile -NonInteractive -File <script.ps1>
bash --noprofile --norc <script.bash>
```

Only PowerShell **7** is declared on Windows. Unix uses the job's actual GNU Bash,
whose version is captured in each report. PowerShell scripts set UTF-8 console
output, invoke with `&` and propagate `$LASTEXITCODE`. Bash scripts use `exec`.
Every argument is single quoted; embedded single quotes use the respective
shell's escape convention. Bash's native invalid-byte operands use ANSI-C hex
escapes. Quoted wildcards, `$HOME`, backticks and shell metacharacters must reach
the file read literally. No shell expansion or globbing is requested. Windows
PowerShell 5.1, cmd.exe, zsh, fish, interactive profiles, terminal rendering and
every other shell remain unqualified.

Each public result includes the parsed native argv ledger hash, actual shell
version/invocation, sanitized script template, actual script SHA-256, executable
and checker hashes, relevant source/helper hashes, fixture hash and per-row
status/channel/capture lengths. Templates replace only the local executable path
with `<binary>`; actual scripts and raw captures stay private. These templates
make the tested quoting reviewable without publishing a developer's local paths.

## Reproduce and verify

```console
cargo build --locked --bin imageinfo
python scripts/check_native_paths.py
python -m py_compile scripts/check_native_paths.py
```

Use `--binary PATH` for an explicitly selected built executable and `--shell PATH`
for the declared shell executable. `--public-results PATH` writes a sanitized
report only after every applicable row passes. The default preserves checked-in
evidence. Hosted jobs can write `.local/native-paths-ci.json` and retain it as an
artifact. The Windows evidence command uses
`--public-results docs/legacy-compatibility/native-paths/windows.results.json`.

The checker reuses [#0052's capture/fixture helper](../../scripts/check_read_arguments.py),
compiling an exporter of the existing [authored fixture](../../tests/support/mod.rs).
No private/camera media, shell-generated metadata fixture or external Python
dependency is used. Every row has a fresh owned directory. Before and after each
read/refusal, the complete immediate file inventory must match: native names,
lengths, SHA-256 bytes and modification times. Unexpected directories, links or
non-files fail. Scripts and captures are outside that inventory. Access times,
ACLs, allocation and continuous exclusion are not measured.

Processes have closed stdin, a 15-second deadline and one-MiB monitored capture
thresholds per stream, using the #0052 helper's documented poll/overshoot limits.
Fixture compilation has a 60-second deadline. Failures retain evidence under
ignored `.local/native-paths/run-*` and return nonzero; an unavailable declared
shell is a harness failure. A sandboxed Windows attempt failed its clean shell
startup probe because the sandbox's PowerShell filesystem provider failed.
Native filesystem execution then passed all 70 applicable rows. That harness
failure is not classified as an expected product refusal.

This finite matrix does not establish all paths, shells, platforms, reference
runtime parity, extraction/output path behavior, menus, accessibility, recursive
traversal, configuration, argument files, persistent sessions or LG-006's wider
umbrella. It enables no writer, storage profile, privacy removal or RAW mutation.
