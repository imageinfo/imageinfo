# Authored date literals across process TZ settings

Observed 2026-10-16, #0162, selected assertion P0A-004 under #0018.
The same project-authored CR3-shaped fixture was read in four actual subprocesses:
the native reader and ordinary CLI, each with `TZ=UTC` and
`TZ=America/New_York`. All four retained exactly these stored strings in raw,
normalized and display values:

| CMT2 tag | Stored literal | Source offset | Length including NUL |
| --- | --- | --- | --- |
| DateTimeOriginal / 36867 | `2020:11:01 01:30:00` | 383 | 20 |
| OffsetTimeOriginal / 36881 | `-04:00` | 403 | 7 |
| SubSecTimeOriginal / 37521 | `050` | 335 | 4 |

The ambiguous local clock text remains text. The offset and fraction are separate
occurrences; the reader does not combine them into an instant, discard the leading
zero or select one side of a daylight-saving transition. Display `timeZone` stays
null and normalization declares `identity-exact-stored-value`.

## Exact authored recipe

The [integration test](../../tests/date_timezone_literals.rs) starts from the
existing [project-authored structural builder](../../tests/support/mod.rs).
It pins the 2,331-byte baseline SHA-256 to
`7781896f985d5af5153e17b8959df04053fe8418262ca99a7ef2290d853992af`.
It replaces the date and offset in their existing allocations, then changes the
inline SubSecTimeOriginal ASCII count from three to four and stores `050` plus
NUL in that same four-byte entry slot. Every byte outside those declared ranges
and the count word must remain equal to the baseline. No allocation moves.

The resulting 2,331-byte fixture has SHA-256
`a2f26feaf5a28c6ef42a85ea6fb213d59d0c01a944e29e013aebff82690dbbac`.
The [machine-readable recipe and observations](date-timezone-literals.v1.json)
bind the offsets, subprocess settings, comparison exclusions and fixed denominator.
These hashes identify authored controls, with no camera provenance claim.

## Actual checks and interpretation

The parent test writes one fresh fixture and does not modify it during the reads.
Each native child checks the requested `TZ` environment, calls `reader::read_file`,
asserts exact native `Value::Text` values and source ranges, and emits its snapshot
through captured stdout. Each CLI process runs `metadata read --output json
--values all` with the three explicit tags. Independent fixed literal assertions
run on every snapshot, so agreement between two wrong results cannot pass.

The test compares both complete native snapshots, both complete CLI envelopes,
and native versus CLI snapshots. The only rewritten comparison fields are the
CLI request ID at the envelope, request, file and summary locations, and the
snapshot ID. The four original request-ID references must agree before rewriting.
Occurrence IDs, ordinals, source paths, resource references, byte ranges, issues
and partial-coverage declarations remain in those comparisons. All three
occurrences must be distinct and retain their EXIF namespace, native tag ID,
ASCII encoding and little-endian origin.

After each native/CLI pair, the test requires identical complete source bytes,
the same physical file identity via `same-file`, unchanged modification time and
exactly one directory entry. CLI artifact reporting must be empty. This records
finite no-effects observations; it is not a continuous exclusion or general
filesystem-property preservation guarantee.

The actual observed platform is Windows with the pinned Rust 1.99.0 toolchain.
`Command::env` supplies the exact two strings to child process environments; it
does not change the Windows machine timezone. Neither the test nor this result
claims that the Windows runtime recognizes the IANA name as a timezone setting,
that a zone database was consulted, or that these names yield different OS clock
behavior. The native date reader transports stored ASCII and performs no timezone
conversion. Other platforms can rerun the same process-environment test; the
observations here do not claim an already-run platform matrix.

Reproduce with:

```text
cargo test --locked --offline --test date_timezone_literals
cargo clippy --locked --offline --test date_timezone_literals -- -D warnings
rustfmt --edition 2024 --check tests/date_timezone_literals.rs
python scripts/check_fixture_gaps.py
python scripts/check_docs.py
```

Two test entries pass: one parent matrix and its subprocess-only native entry
(which is inert without the parent's fixture environment). The fixed execution
denominator is two TZ settings times two entry paths, four actual reads of one
immutable authored input, with three expected literal occurrences per read.
Full root verification remains the integration gate.

This delivers the selected authored literal-transport assertion. The historical
[P0 selection ledger](p0-assertion-gaps.md) remains a planning/evidence checkpoint;
this is no new camera stratum or complete FXP family. No private media, JPEG
decoding, container integer-time conversion, calendar validation, clock accuracy,
timezone database, inferred timezone, writer or mutation admission is qualified.
