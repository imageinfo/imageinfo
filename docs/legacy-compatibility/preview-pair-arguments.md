# Finite preview and explicit-pair argument additions

**#0124**, observed **2026-10-16**. The [32-case authored ledger](preview-pair-arguments.cases.json)
extends [#0052's read argument evidence](read-argument-order.md) to exactly
`preview date-time-original` and `sidecar pair`. The
[actual results](preview-pair-arguments.results.json) bind the executable,
checker, runner, fixture support and relevant source hashes. This is finite
native difference/refusal evidence; no reference executable was invoked and no
broader compatibility difference or parity decision is accepted here.

| Cases | Actual interactions |
| --- | --- |
| PP-001Ã¢â‚¬â€œ004 | Preview JSON selector at root, group, leaf and after input |
| PP-005Ã¢â‚¬â€œ006 | Duplicate value and allocation-offset scalar refusals |
| PP-007Ã¢â‚¬â€œ009 | Help wins over version; version skips required operation operands; malformed offset syntax wins over help |
| PP-010 | `--` protects the literal input named `--output=json` |
| PP-011Ã¢â‚¬â€œ014 | Invalid Gregorian date, overflowing offset, absent input and extra input |
| PP-015Ã¢â‚¬â€œ016 | Correct allocation assertion and stale zero-offset refusal |
| PP-017Ã¢â‚¬â€œ020 | Pair JSON selector at root, group, leaf and after input; opaque invalid RAW and non-XML sidecar succeed |
| PP-021Ã¢â‚¬â€œ022 | Duplicate sidecar and JSON selectors refuse; ambiguous duplicate output selection uses plain stderr |
| PP-023Ã¢â‚¬â€œ025 | Help/version precedence and missing sidecar option operand syntax before help |
| PP-026Ã¢â‚¬â€œ028 | Literal input named `help`, absent input and extra input |
| PP-029Ã¢â‚¬â€œ032 | Omitted sidecar despite existing basename decoy, nonexistent sidecar, same path and distinct hard-link alias |

Every syntax row asserts actual status 2 and the declared output channel/code.
Unambiguous JSON syntax failures have zero discovered inputs and empty files;
ambiguous output selection emits no stdout. Help and version are plain text in
the enumerated rows. Version needs no operation operands; full grammar errors
still precede help. These claims concern the exact tokens in the ledger rather
than every possible help/version combination.

The successful advisory inspection rows return status 1 because actual opaque
dependency admission refuses. They still inspect the authored DateTimeOriginal,
verify its unique allocation, retain exact original/proposed ASCII20 bytes and
report exact differing spans and their complement. The checker independently
constructs the hypothetical byte replacement and checks every source byte is
covered exactly once by the reported changed/preserved partition. The stale
offset row refuses with `OCCURRENCE_CHANGED` and exposes no original bytes.
All preview rows assert `production_mutation_allowed: false`; none publishes.
These are positive advisory observations alongside an actual mutation refusal,
not positive RAW write admission.

Pair success uses deliberately invalid RAW marker bytes and a non-UTF-8,
non-XML sidecar marker, demonstrating the named path-association operation does
not require content interpretation. Each operation result must name its independently declared ledger input exactly.
Returned pair paths must also identify the physical RAW and sidecar objects named
by that ledger, independently of the product-returned input path. A separately present `source.xmp` does not make omission of
`--sidecar` succeed. Same-path and hard-link aliases refuse. This is no inference
of basename pairing, content parsing, continuing identity guards or sidecar
creation/synchronization authority.

## Reproduce and effects

```console
cargo build --locked --bin imageinfo
python scripts/check_preview_pair_arguments.py
cargo test --locked --test cli_preview_pairing --test date_preview --test pairing
```

Use `--binary PATH` to select a built executable. Deliberate public refresh uses
`--public-results docs/legacy-compatibility/preview-pair-arguments.results.json`;
the default retains results privately. Native filesystem permission to create a
disposable hard link is required; the checker fails rather than skipping aliases.

The standard-library checker compiles a tiny exporter with `rustc --edition=2024`
and the existing authored structural fixture support. SOI/EOI-only authored JPEG
markers support bounded structural inspection; they are no camera or entropy
validation evidence. Captures and all fixture/case files remain under ignored
`.local/work-wave-20261016e/124-run-*`. Each case receives a fresh directory and
argv array with no shell, closed stdin, a 15-second deadline and one-MiB capture
limit per stream, using #0052's process runner. Fixture compilation has a
60-second deadline. Captures are monitored on disk; they can overshoot a threshold
between polls and any excess fails the case before capture loading.

Before and after each successful case, the checker requires the entire immediate
file-name set, bytes/SHA-256, size, modification time, mode, device/file identity,
link count and exposed file attributes to match. Non-file and symbolic-link
entries fail. Every JSON operation also asserts empty artifacts, no transaction,
no changed/publication/cleanup flags and no recovery IDs. Actual directory/byte
checks verify the effect independently of reported flags. Access times, ACLs,
creation times, alternate streams, allocation, directory timestamps, continuous
exclusion and arbitrary filesystem properties are outside these observations.

## Evidence and limits

The native Windows run passed **32/32** cells. Four in-memory negative oracle
controls reject wrong-input substitutions in the literal preview and pair captures,
including a substituted pair RAW identity with both matching and unchanged
reported input paths. These controls add no executable argv cases. The related existing Rust
contracts passed **6 CLI**, **8 date-preview** and **8 pairing** tests with native
filesystem permissions. A preliminary sandboxed run could
not create its hard-link fixture; it is retained privately as an environment
failure, not an accepted product refusal. Public results contain only fixed case
IDs, statuses, channel labels, capture sizes, hashes and effect assertions.
No camera data, raw captures or local private paths are published.

Non-Windows execution, shell quoting, non-Unicode paths, case-ambiguous directory
layouts, symbolic aliases, every option combination, JSON profile exhaustiveness,
reference parity and all broader LG-001/LG-006 residuals remain outside this
matrix. It changes no production grammar, parser, reader, preview, pairing or
storage policy. No writer, apply, RAW mutation, storage-profile or privacy
certification follows from the finite evidence.
