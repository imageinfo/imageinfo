# Native R5 slice validation

Card **#0020**, observed **2026-10-11**. This evidence applies to the declared
read/preview subset, not full R5 or ExifTool functionality.

## Actual private comparison

- Eight immutable received R5 full RAW copies read successfully.
- 160 source-qualified scalar/rational checks and 24 binary-range checks match
  the pinned ExifTool 13.59 captures on the same input hashes.
- 184 primitive source spans were independently reread/decoded by the QA adapter;
  stored integer/string/rational values and binary lengths/digests agree.
- Twenty-four native preview outputs match reference hashes exactly, including
  padding. Twenty-four existing-destination attempts returned refusal and retained
  the prior output hashes.
- Per-invocation source hashes before/after match; received content hashes and
  modification times remain unchanged. Network originals were not opened for write.
- Final display comparisons have zero differences for this subset. An earlier
  retained attempt exposed aperture `8`/`10` versus reference `8.0`/`10.0`; ordinary
  one-decimal display resolved it without altering exact machine values.

Exact capture/argv/environment, tool/source/driver hashes and media remain private.
The final process environment is explicitly allowlisted (system paths, C locale
variables and UTC process setting). Capture values remain literal and receive no
host timezone inference. QA hashes/timestamps and the 60-second supervisor timeout
are not measured native performance or product deadline guarantees.

Thirty-two differential experiment records, eight revised source admissions,
24 native derivative admissions and 32 scoped provenance reviews validate against
the existing contracts. A 466-artifact registry verifies exact lengths/hashes and
inherits reference/permission evidence. Generic memory/decompression/global-record
caps are explicitly unconfigured; actual separate parser guards are recorded.
The same-engine reference comparison is not an independent RAW/JPEG decoder test.

See [sanitized totals](summary.json). Images, capture timestamps, serial/owner data,
private paths, detailed reports and per-image hashes are excluded from public Git/CI.

## Public tests

Authored structural fixtures contain invented metadata and marker bytes, not real
camera photos or valid developed pixels. Standard tests exercise:

- Exact duplicate/source identity and unreduced rational pairs.
- Little/big-endian TIFF and extended BMFF size headers.
- Truncation, overflow, IFD cycles, limits and malformed storage/address shapes.
- Unsupported camera/quality/DPRAW/main-encoding/external-reference declarations.
- All three stored resource extents, no-clobber repeat attempts, dry run, retained
  source bytes and temporary cleanup on ordinary outcomes.
- Real CLI read/list/extract, content detection despite a `.jpg` filename,
  Unicode paths, mixed failure status, JSON contracts, invalid rational state,
  empty-path/unknown-selector preflight, and complete text reports beyond 4 KiB.
- A deterministic 10,000-input mutation/truncation fuzz smoke campaign over the
  actual reader, with a fixed seed and bounded metadata budget; no panics observed.

The fuzz smoke is reproducible in `cargo test --locked`; it is not coverage-guided
fuzzing, a long-running campaign, OOM isolation or proof of adversarial safety.
Further targeted variation and fuzz/validator evidence remain #0018.

## Build and platform gates

Required formatting, clippy with warnings denied, all tests and release builds
are run with the pinned Rust 1.99.0 toolchain and root lockfile. The existing CI
matrix exercises Windows x64, Linux x64 and macOS arm64 with public synthetic data
only. [Run 38155763391](https://github.com/imageinfo/imageinfo/actions/runs/38155763391) passed all three jobs on
code commit `bdd10e5b898e370e6c489ad8c0e0294918670149`. See [actual run/job evidence](ci-results.json).
The Windows suite executes 25 tests; Unix suites add the non-Unicode path test
for 26. No real-camera fixture or private capture is part of those public jobs.

All emitted native snapshots/envelopes in the private corpus are schema checked.
This validates wire shape and the explicitly checked reference/closure/span facts;
it does not implement every metadata/import/edit contract.

## Limits retained

Real-camera coverage remains firmware 2.2.1, one ISO/lens stratum. C-RAW, DPRAW,
other cameras/firmware/layouts, XMP, nested JPEG metadata, time conversions,
composites, writes, privacy removal, strong source locks, hard memory/deadline
limits and power-loss recovery are not verified or enabled by this work.
