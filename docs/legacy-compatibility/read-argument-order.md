# Finite native read argument ordering

**#0052**, observed **2026-10-15**. This qualifies 94 enumerated actual argv
invocations of the implemented `metadata read`, `binary list` and `binary extract`
commands. It changes no production grammar, dependency, read or extraction code.

The [case ledger](read-argument-order.cases.json) is the complete finite scope:
each row supplies an ID, token array, expected status, output channel, semantic
checks and native difference/refusal classification. The
[observed results](read-argument-order.results.json) record every actual status,
channel, capture lengths and verified effect classification, with exact binary,
checker, ledger, fixture-support and relevant source hashes. Status 2 rows are
successful qualification of a refusal, rather than implemented support for their
rejected syntax.

## Native differences and refusals

This is the explicitly documented **native difference** route under #0052.
No ExifTool executable was invoked. The prior survey remains pinned to ExifTool
13.59, source revision `2200871d9cef988051d2a99d67df3bda6cbb30a8`, observed
2026-10-10; see the [compatibility recommendation](README.md) and
[surface ledger](surface-ledger.md), especially MAP-002/003/004/006/007/024 and
LG-001/LG-006. These native token arrays are not ExifTool command translations.
`native-difference` describes the declared native interface; it does not mean an
executable reference comparison passed, or that Terry accepted every wider
proposed compatibility difference. Native refusal rows have `native-refusal`.

The observed contract is:

- One `--output json` or `--output=json` can appear at root, command group, leaf,
  or after the input. It selects a native version-1 envelope, with native
  request/file/summary records. Repeated output selectors refuse with status 2
  and plain stderr, even when repeated across command scopes. Duplicate color
  settings refuse with a JSON error when a separate unambiguous JSON selector
  exists. Neither scalar is a last-value-wins operation.
- Leaf options stay at their declared leaf. Repeated metadata-byte and
  preview-byte budget scalars refuse; a budget before the leaf refuses. These
  cells qualify ordering and duplicate rejection, not a resource-limit policy.
- Read `--tag` appends selectors. Repeating `ISO` selects the same two stored
  occurrences once each. Requesting `ISO` and `Model`, in either selector order,
  returns the fixture's source occurrence order `Model`, `ISO`, `ISO`; it does
  not reorder the snapshot to selector order. Options between two inputs retain
  the supplied input order.
- Read `--values` is a scalar: repetition refuses. The current JSON snapshot
  retains raw and normalized typed values in all four modes. Display is present
  for `display`/`all`, and unavailable for `raw`/`normalized`. The same option also
  selects text presentation; this matrix verifies the JSON representation, not
  every exact text rendering or display conversion.
- `--` makes following tokens literal input paths, including `help`,
  `-photo.cr3` and `--output=json`. The latter does not select JSON. Space and
  Unicode filenames are passed as single native argv tokens. A leading-hyphen
  input without `--` refuses. Bare `help` remains a command; the literal tests
  deliberately use `--`.
- Extraction requires one input, one case-sensitive registered preview tag and
  one output path. Repeated tag/output-path scalars refuse. An attached
  `--output-file=-new.jpg` is a valid destination; the separate hyphen-leading
  value refuses. The three preview types produce exact stored fixture bytes at
  owned fresh destinations. `--dry-run` creates no output. An existing destination
  returns status 1 with `DESTINATION_EXISTS` and preserves its sentinel bytes.
- Malformed syntax wins over a simultaneous help request. Valid help is plain
  text even with JSON selection. Legacy `-j`, abbreviated `--out`, unknown read
  selectors, missing/empty operands and missing extraction output refuse; no
  legacy compatibility interpretation is inferred.

JSON syntax-error routing follows [#0037](native-json-errors.md). This matrix
verifies actual error envelopes with zero discovered inputs and no artifacts,
not merely parser return values.

## Enumerated coverage

Every individual token array and expected result is in the public ledger; ranges
below are an index, not additional unenumerated claims.

| Case IDs | Actual operation and finite interactions |
| --- | --- |
| RA-001–024 | Metadata read: output placement; scalar duplication; group/leaf boundaries; help precedence; literal, spaced and Unicode paths; legacy/abbreviation/empty/missing refusals |
| RA-025–048 | Binary list: the same finite placement, duplicate, literal and refusal cells; three stored resource names where specified |
| RA-049–072 | Binary extract: the same finite cells; successful copies use owned fresh output paths |
| RA-073–075 | Repeated/reversed read selectors and exact source occurrence order |
| RA-076–079 | Four read value modes and raw/normalized/display availability |
| RA-080–082 | Duplicate values, interspersed options/two-input order, misplaced tag refusal |
| RA-083–084 | Extraction duplicate tag and output-path scalar refusals |
| RA-085–086 | Exact ThumbnailImage and JpgFromRaw bytes; PreviewImage covered above |
| RA-087–089 | Dry run, existing destination refusal, attached hyphen destination |
| RA-090–094 | Separate hyphen destination, extra input, missing output, case-sensitive preview selector and unknown read selector refusals |

## Reproduce and inspect

Build the current native executable, then run the standard-library Python checker:

```console
cargo build --locked --bin imageinfo
python scripts/check_read_arguments.py
cargo test --locked --test cli_contract --test syntax_output_contract --test reader_contract
```

For a deliberate evidence refresh, add
`--public-results docs/legacy-compatibility/read-argument-order.results.json`.
The default leaves the checked-in evidence unchanged. `--binary PATH` selects an
already built executable explicitly; its actual bytes are hashed in the report.

The checker compiles a small fixture exporter with `rustc --edition=2024`,
importing the existing [authored structural fixture](../../tests/support/mod.rs).
It never consumes camera media. Each argv invocation has an isolated working
directory containing known source copies and an occupied-destination sentinel.
Every case rejects an unexpected directory, link or non-file entry and compares
the full immediate file inventory, byte lengths, SHA-256
hashes and modification times. A successful extraction permits exactly its named
new destination, checks every byte against the fixture's expected preview, then
requires the remaining inventory to equal its original state. Every other case
requires an unchanged inventory. This does not claim continuous exclusion or
unchanged access times, ACLs, allocation layout or other filesystem properties.

Processes receive argv arrays directly with `shell=False`, closed stdin, a
15-second command deadline and a one-MiB capture threshold per stream. Fixture
compilation has a 60-second deadline. Captures go directly to files and are
monitored during execution; a threshold crossing kills the child and fails the
case (the final file may overshoot between polls). The checker never reads an
oversized capture into memory. Failures, successful captures, fixtures and partial
case output are retained under ignored `.local/read-arguments/run-*`; paths are
printed for private inspection. Public results contain only fixed IDs, statuses,
channel labels, lengths, assertions and hashes. No raw logs or media enter Git.

## Evidence and limits

The final native Windows run passed **94/94** cells. Relevant Rust contracts
passed **12 CLI**, **8 syntax-output** and **9 reader** tests. A prior sandboxed
run encountered filesystem `PermissionDenied` during actual no-clobber preview
publication; rerunning with native filesystem permissions passed the extraction
cells. The failed captures remain private and are not reclassified as expected
product refusals.

The matrix is finite and Windows-executed. Non-Unicode native path units,
newline filenames, other platforms, shell tokenization/quoting, argument files,
configuration, recursive traversal, arbitrary ExifTool options, persistent
sessions and exhaustive option combinations remain outside these cells. Existing
platform-specific Rust parser tests are separate evidence. No reference runtime
parity, general LG-001 closure, metadata writer, storage profile, privacy removal,
RAW mutation or expanded format support follows from these results.
