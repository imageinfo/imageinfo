# Stored-preview local authored measurements

Implemented #0062 increment, observed **2026-10-15**. This is a finite local
measurement of the existing `binary list` and named `binary extract` operations
using independently authored structural CR3 bytes. It is **not a real-camera
preview baseline**, a JPEG decode/render test, a comparison with another tool,
or evidence for performance defaults. The payloads deliberately are not complete
JPEG images. Their stored starts, extents and padding exercise the existing
bounded byte-copy contract.

The [fixed protocol](preview/protocol.v1.json) pins the executable, collector,
bounded capture implementation, fixture generator and shared authored fixture
support before collection. The [collector](../../scripts/measure_previews.py)
reuses #0060's `read_benchmark.run_process`; no dependency or production behavior
is added. The [independent audit](../../scripts/audit_previews.py) checks the
retained evidence and recomputes success-conditional distributions.

## Workload and timing boundary

The [fixture generator](preview/fixture.rs) uses the existing authored R5
structural profile from `tests/support/mod.rs`. It emits one 1,120,527-byte
source and three separate expected resource files. `ThumbnailImage` contains
4,096 stored bytes, `PreviewImage` 65,536, and `JpgFromRaw` 1,048,583.
Each resource ends with three padding bytes after its EOI marker. Those bytes
are included in the expected size and SHA-256; no decoder determines the copy
extent. These arbitrary authored sizes do not characterize a camera population.

Order is fixed: listing, then each of the three named extractions; each group
has two retained warmups followed by ten measured attempts. Then each tag gets
one preexisting-destination collision and one one-byte preview-limit refusal.
The complete series therefore has 54 attempts: 8 warmups, 40 sample attempts
and 6 refusal controls. No adaptive warming, retries, trimming or exclusions are
allowed. Setup probes are separately retained outside that denominator.

Each attempt launches the ordinary executable directly in a fresh process.
Listing includes startup, bounded metadata reading, JSON serialization, pipe
draining and exit. Extraction additionally includes the reader's byte copy,
file flush/sync and no-clobber hard-link publication. The collector measures
`time.perf_counter_ns` immediately before process creation through direct child
exit and completion of both pipe drains. It does not subtract polling, thread,
or instrumentation overhead. Source/resource hashing and validation, fixture
construction, output-directory creation, and collision seeding occur outside
that interval. First-byte, first-result, CPU, memory, physical I/O and allocated
scratch metrics are unavailable with explicit nulls/reasons.

The consumer drains JSON stdout and stderr concurrently into bounded memory,
with at most 1 MiB retained per pipe and 4 KiB drain chunks. Extracted bytes go
to distinct fresh files on the same local C: NTFS volume as the source,
executable and capture files. This measures that storage/consumer arrangement;
it does not characterize terminal display, slow consumers, discard sinks,
remote storage, or another filesystem. Extraction's successful file sync does
not establish directory or device persistence.

## Correctness and unsuccessful attempts

Preflight validates exact source and expected-resource hashes and verifies each
expected extent against authored bytes. Each listing must retain the three
ordered named occurrences, matching ranges/lengths and partial coverage.
Extraction must return a complete successful summary with the exact committed
artifact path and output size/hash equal to the entire authored resource.
Source effects remain zero. The independent audit reads actual listed source
ranges and compares their bytes with the separately generated expected files
and retained extraction outputs. This is stored-resource correctness, not
JPEG conformance or broader metadata parity.

Collision controls must return `DESTINATION_EXISTS`, preserve the exact seeded
destination hash/length/mtime, and report no artifact. One-byte limit
controls must return `LIMIT_EXCEEDED` and create no destination. Both are expected
operation failures, count in the 54-attempt ledger, and are never successful
extraction latency samples. All outputs and partial/temporary artifacts remain
private for inspection. The collector does not clean them up to manufacture a
successful observation.

Launch failures, nonzero exits, malformed output, hash mismatches, capture-limit
stops and timeouts are retained. A 30-second deadline bounds supervision; capture
overflow or timeout stops the direct child and yields a censored elapsed-at-stop
observation. This is not a hard OS resource quota, process-tree sandbox or promise
to interrupt blocked kernel I/O. Per-attempt records and captures are saved as
the run proceeds. Unexpected exceptions/interruption produce an aborted record
when record creation remains possible; unattempted cells remain separately
counted and every latency sample becomes ineligible. Abrupt interpreter/host
termination or disk errors can prevent the final record; no crash-resilient
journal is claimed.

## Environment, evidence and limits

Preflight hash reads expose the source to a warm OS cache before the first
sample. The application process is fresh, while OS/device caches remain
uncontrolled and server cache is inapplicable. No cold label, eviction or host
policy changes are used. Hardware topology/RAM are unknown because the sandbox
could not query CIM. The protocol declares the observed Windows/architecture,
NTFS volume size/free space, Balanced power plan, unknown power source,
uncontrolled scanner/indexer and shared-workstation background activity.
These limits prevent portable performance or tail guarantees.

Private captures, exact argv/environment/paths, all attempted durations, output
files, before/after source identities and pinned Python runtime evidence reside
under `.local/next-wave-20261015/62/`. A sandbox setup probe returned `OUTPUT_IO`
because no-clobber hard-link publication was denied; a separately retained native
probe outside that sandbox succeeded. An earlier complete 54-attempt series was retained and superseded only to
normalize source line endings and format the fixture generator before freezing
the final protocol. The final frozen series uses the qualified
native execution context. Setup probes are neither discarded benchmark failures
nor silently pooled with it. Early interactive setup probes are not timed
benchmark samples and are not claimed as a complete experiment.

The public [curated result](preview/results.v1.json) contains authored resource
identities, per-attempt timing/outcomes without paths or raw process output,
and independently recomputed descriptive statistics. SHA-256 pins identify
reviewed local evidence; they do not authenticate arbitrary imported records.
Source length/mtime/hash and binary/collector pins are rechecked after collection;
changes invalidate all samples. These ordinary checks do not supply continuous
source locking or hostile same-byte replacement protection.

## Reproduction

Run from the repository root with the documented Rust and Python prerequisites:

```powershell
cargo build --release --locked
New-Item -ItemType Directory -Path .local -Force | Out-Null
rustc --edition 2021 docs/performance/preview/fixture.rs -o .local/preview-fixture.exe
.local/preview-fixture.exe .local/preview-fixture
python scripts/measure_previews.py --protocol docs/performance/preview/protocol.v1.json --binary target/release/imageinfo.exe --fixture .local/preview-fixture --output .local/preview-run
python scripts/audit_previews.py --run-root .local/preview-run --protocol docs/performance/preview/protocol.v1.json --output .local/preview-audit.json
python -m unittest discover -s scripts -p test_measure_previews.py
```

Fixture and run directories must be fresh; retain failed directories and choose
a new explicit run path. Binary hashes differ across toolchains/builds: this
published protocol intentionally refuses a different binary or changed collector.
For a new stratum, review and freeze a separately named protocol with its actual
binary/source/tool pins and environment before collecting; do not edit this
record to pretend it measured that build. On Windows the execution context must
permit native no-clobber hard-link publication in the owned scratch directory.

The ten samples per group support descriptive min/median/nearest-rank p95/max
only; p95 is the observed maximum at this sample size, not a tail guarantee.
No memory/CPU/I/O defaults, regression budget, comparable tool speed claim,
real-camera baseline or production write/profile capability follows.

The final independent audit passed all **54/54** expected outcomes: **40** eligible
successful samples, **8** successful warmups and **6** expected failure controls.
There were no unexpected failures, censored or unattempted cells. Exact listed
ranges and all extracted stored-resource hashes matched, including padding;
source length/mtime/hash and frozen binary/source pins remained unchanged.

| Local authored operation | Stored bytes copied | Eligible n | Median ms | Descriptive p95/max ms |
| --- | ---: | ---: | ---: | ---: |
| Listing | 0 | 10 | 7.78825 | 10.52700 |
| Extract ThumbnailImage | 4,096 | 10 | 11.21630 | 16.64670 |
| Extract PreviewImage | 65,536 | 10 | 13.40960 | 16.33940 |
| Extract JpgFromRaw | 1,048,583 | 10 | 12.83360 | 30.47440 |

These groups copy different resource sizes and are not a matched speed
comparison. In particular the smaller observed median for the largest payload
does not establish a scaling law; process, storage and workstation variability
are included. The complete integer-nanosecond samples, controls and formulas are
retained in the curated result and fixed protocol.
