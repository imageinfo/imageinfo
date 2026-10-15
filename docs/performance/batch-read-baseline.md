# Bounded batch metadata-read measurements

Card **#0063**, protocol `batch-read-v1`, 2026-10-15. This increment implements a
finite ordinary-CLI batch measurement and retains its actual camera results
privately. **A public camera-performance baseline is withheld:** the current
camera-corpus grants allow private analysis and deny report publication. No
private-camera timing, size, outcome distribution, image hash or identifying value
is published here. No new report permission is inferred from sanitized output.

The public [authored qualification](batch-read/authored-qualification.v1.json)
exercises the same collection/classification mechanisms with independently authored
structural fixtures. Its samples are collector controls, not camera-performance
measurements. The [fixed method](batch-read/protocol.v1.json) contains only method
and tool identities; the camera configurations, grants, oracle bindings, records,
raw captures and audit remain private.

## Implemented scope and preregistration

[The batch runner](../../scripts/measure_batch_read.py) reuses the accepted
[#0060 subprocess collector](read-collector.md) without changing its timed process
boundary. It extends the ordinary-process methodology of
[#0061](single-read-baseline.md), using a separate frozen executable built from
accepted commit `188049f8ac4c7d0e107439ed385cdd0ee5208201`. All 515 tracked source
blobs were compared with that Git revision before the isolated release build.
Rust 1.99.0 and the frozen root lockfile are retained. Working-tree implementation
work cannot replace that executable during measurement. This is CLI timing, not
the separate request/result API, a persistent session or parallel workers.
It differs from #0061's frozen `5f7a86e` executable. Scaling analysis uses this
grid's own size-one observations; it does not compare numerical results across
those two revisions.

The private preregistration binds the runner/collector, binary, source/build
evidence, Python interpreter, exact native argv/environment and a fresh #0063
task admission. Every selected fixture binds its current native admission,
provenance/privacy/grant records and prior passing #0020 read oracle. Rights and
all those evidence hashes are checked before any new media-content read and again
before every whole-source identity-check phase. Denied report publication keeps
all camera-derived attempts and analysis under ignored `.local` storage.

The fixed grid is **1, 2, 4, 8 distinct admitted files**, using prefixes of one
fixed ordered eight-file set. Each round retains two warmups followed by ten
measured attempts at each size. The three round orders are:

| Round | Batch-size order |
| --- | --- |
| 1 | 1, 2, 4, 8 |
| 2 | 8, 4, 2, 1 |
| 3 | 2, 8, 1, 4 |

There are 144 planned batch attempts: 24 warmups and 120 measured opportunities.
The planned file-slot denominator is 540, including 90 warmup and 450 measured
slots. These are schedule constants, not disclosed camera outcomes. Sizes use
distinct physical files; exact-path deduplication must remain zero in the grid.
Larger prefixes also change the mix of files and their metadata/layouts, so this
is not a pure causal estimate of file-count cost or a general scaling law.
The varying order is only a partial rotation, not a fully balanced experiment.
There is a fixed five-second gap between rounds, no adaptive stopping, retries,
outlier removal or exclusion of unfavorable durations.

## Timing, output, storage and cache

Each attempt launches one fresh process with the fixed token array:

```text
[binary, "metadata", "read", "--values", "all", "--output", "json",
 "--max-bytes", "8388608", "--", ordered-prefix-inputs...]
```

The native 8 MiB metadata-read budget applies per input; native parser limits
remain enabled. The supervisor deadline is 30000 ms and retains at most 4 MiB per
stdout/stderr pipe. These are finite experiment bounds, not proposed product
performance defaults. The existing direct process spawns no helpers; the runner
is not a process-tree sandbox or OS memory/disk quota.

Integer `perf_counter_ns` nanoseconds cover process launch through exit and both
bounded in-memory pipe drains. Clock resolution and UTC starts are retained.
JSON validation, source identity hashing and private capture writes occur after
or outside the timed interval. Their possible effect on the following attempt
is disclosed; measurement/polling/thread overhead is not subtracted.

The CLI emits one final batch envelope. Individual file latency and first-result
timing are **unavailable**, not obtained by dividing batch time. Elapsed divided
by completed file count is explicitly an amortized batch cost; total successfully
completed file units divided by their total eligible batch seconds is a scoped
throughput. Neither is a per-file latency distribution. CPU, memory and logical/
physical I/O counters remain unavailable, with nulls and reasons.

All eight inputs are hashed before and after each round. This exposes them to
the OS cache. The honest cache label is **fresh process, OS warm-exposed and
uncontrolled**; application state is fresh, and device/server cache state is
uncontrolled or unknown. Controlled OS/device-cold cells are unrun because no
validated eviction or device-cache conditioning is available. No workstation
cache purge, power cycle or host policy change occurs. The shared Windows fixed
NTFS workstation, background load, scanner/indexer activity, thermal state and
power source are not an isolated performance environment. Allowlisted before/
after machine/load/storage facts remain with private evidence.

## Correctness, missing work and noise

Every batch attempt has exactly its scheduled number of per-file slots. Failed,
refused, malformed, launch-error, timeout and output-limit outcomes remain in the
ledger. Censored or missing results receive `not-observed` slots; the batch outcome
gives their reason. No completion time or successful file is invented. A flushed private
JSONL ledger retains appended attempts if later collection aborts; capture or
ledger-storage failure can leave partial evidence and cannot establish a complete
experiment. The final
record marks the retained prefix and invalidates eligibility on an aborted run.
This is not a crash-resilient journal or recovery facility.

A successful batch requires an acceptable exit, complete final envelope,
selection/output completeness, exact discovered/read counts, no deduplication,
no source effects/artifacts and all expected per-file results. Independent
comparison preserves strict JSON types, array order, values, occurrence/range
identity, partial coverage and issues. Only validated invocation-local IDs and
the already-bound display paths are normalized against the prior single-file
oracles. Actual file paths and snapshot positions must first match the scheduled
input. Source bytes, length, mtime and physical identity and executable identity
are checked across declared boundaries; these are observations, not continuous
exclusion of hostile replacement.

The [independent auditor](../../scripts/audit_batch_read.py) retains all scheduled
denominators and computes size-separated, success-conditional distributions and
failure/censor counts. Median uses the sorted center/even midpoint; descriptive
p95 uses nearest rank `ceil(0.95*n)`. Sample standard deviation uses `n-1`; MAD,
CV, per-round medians and their span describe noise without an independent-host
confidence interval or regression threshold. Partial rotation, shared caches,
post-timing evidence writes and background activity limit causal interpretation.
Camera-derived numerical analysis stays private because publication is denied.
The fixed private collection and independent audit were completed and retained
locally. The absence of public numerical results is a disclosure restriction,
not a substitute claim that the camera workload was only proposed or that an
authored fixture represents its performance.

## Reproduce and review

The actual private invocation uses a fresh directory containing the pinned
protocol and evidence bindings:

```console
python scripts/measure_batch_read.py --run-root .local/next-wave-20261015/batch63/camera-run
```

A completed run refuses capture/record reuse. Reproduce into a fresh private root,
inspect current lawful-use and report-disclosure grants first, and prepare the
same fixed protocol with new local paths and exact tool/evidence identities before
any media read. The runner enforces private storage and offers no camera-results
public export. Any future disclosure requires actual authorization and its own
review; this increment does not change those rights.

Public-safe qualification is separate:

```console
python scripts/qualify_batch_read.py --binary FROZEN_IMAGEINFO --source-root FROZEN_SOURCE --parent .local/batch-authored --output .local/authored-batch-summary.json
```

It generates authored fixtures from the public test helper and compares actual
native batch results with the independently committed #0053 authored snapshot
and result contract. It exercises all grid sizes, exact duplicate paths, mixed/
missing input outcomes and finite actual timeout/overflow/malformed-output
controls. Only its deliberately authored derived observations may be published.

The actual public-safe qualification passed 16 native grid attempts: one retained
warmup and three repeated samples at each size. Every authored file slot matched
the independent expected subset; source hashes/mtimes and the namespace remained
unchanged across CLI reads. Six separate finite controls passed:

| Authored control | Observed qualified behavior |
| --- | --- |
| Exact duplicate path | One read result and one deduplicated operand |
| Missing input | Status 1 with a failed file result |
| Mixed valid/missing inputs | Status 3 with separate read and failed results |
| Supervisor timeout | Censored batch; both planned slots remain not observed |
| Capture overflow | Censored batch; bounded capture and both slots not observed |
| Malformed helper output | Failed batch correctness; neither planned slot becomes a fabricated success |

The last three are authored supervisor/helper controls, not native camera parser
failures. The six [permission/boundary tests](../../scripts/test_measure_batch_read.py)
separately verify denied analysis, denied report publication, complete grant/evidence
pinning, rejection of reference-only admission, source-size checking before hashing
and private-output enforcement. None reads camera media.
Ten [independent audit tests](../../scripts/test_audit_batch_read.py) also passed,
covering schedule/denominators, complete contract equality, file order/path/value/
coverage binding, malformed JSON, failed/censored eligibility, retained slow
samples, exact statistics and exclusive private report destinations. These tests
use authored records and invented durations, without camera observations.

No camera-report publication, selected-field/binary extraction, batch mutation,
session, concurrency, new resource-policy default or numerical superiority claim
is enabled by these measurements.
