# Measurement protocol and selection of limits

Proposal `2026-10-10.1`, observed/reviewed **2026-10-10**. The numbers in arithmetic
examples are invented; there are no measured imageinfo or ExifTool results here.

## Run procedure

1. Pin the workload, fixture manifests, operation/output contract, tool distributions,
   driver, adapters and policy revisions. Confirm provenance and permitted operations.
2. Admit an environment stratum: OS/build/architecture, CPU/RAM, storage topology,
   filesystem/mount/encryption/compression, power plan/source, locale/timezone,
   security/scanner/indexer activity, free space and relevant background load.
   Include network/server/cloud state when used. Capture allowlisted facts, not secrets.
3. Declare repeats, warmup policy, order/seed, conditioning method, consumer, sampling
   intervals and stopping/exclusion rules before seeing candidate results. Log setup
   and clone costs separately; do not call them metadata execution time.
4. Prepare isolated inputs/destinations and validate identity. Apply declared cache
   conditioning afterward. Record which layers are controlled, unknown or impossible
   to control on that environment; do not change workstation-wide policies silently.
5. Collect monotonic elapsed intervals, process-tree CPU/memory/I/O and output evidence.
   Preserve raw samples, timestamps, counter methods and errors. Record clock units,
   resolution and calibration/measurement overhead; do not subtract an assumed overhead.
6. Complete per-run correctness and preservation assertions. Keep invalid/failed/timed-out
   trials in the ledger with their reason and artifacts. Completed-success latency
   distributions exclude unfinished/failed work and are labeled conditional on success.
   Success rates retain all valid attempted operations in their denominator; disclose
   invalid measurements separately. Never present a conditional tail as the whole workload.
7. Aggregate only matched, valid strata. Report reproducibility limits, distribution,
   unsuccessful attempts and comparison uncertainty before recommending any default.

Warmup trials are retained and labeled. Do not keep warming until a desired number
appears. Predeclare a run count or precision-based stopping rule with a maximum
trial budget; never stop on the first favorable comparison. Aborted experiments
remain distinguishable from a normal completed experiment with operation failures.

## Record fields

Use the [fixture-plan records](../fixture-plan/README.md) for admitted assets,
executable identities, operation correctness and independent validators. A performance
run adds the following fields to its own record and links that experiment by ID/hash;
it does not change the fixture schema or invent a successful parity record.

| Field group | Required content |
| --- | --- |
| Identity | Schema/recipe/workload revision, run ID, UTC observation time, operator/driver identity, baseline/candidate role |
| Status | `not-run`, `completed`, `invalid-measurement` or `aborted`; reason; linked operation outcome and correctness result |
| Inputs | Manifest/hash references, ordered fixture IDs, variant, count, input bytes and metadata/preview sizes when known |
| Tool | Full executable/runtime/distribution hashes, command token arrays, working-directory token and effective configuration/capability/schema revisions |
| Environment | Hardware/OS/storage/power/locale/timezone and load fields above; sampling/clock methods and tool identities |
| Conditioning | New/reused process and session, app/OS/device/server cache state, exact preparation/order and observed uncertainty |
| Policy | Warmup/repeat/order/seed, configured resource caps and deadlines, output consumer/capture, safety and backup policy |
| Per-attempt samples | Start/end events, elapsed/CPU, first-result/complete-result, memory and I/O series/peaks, output and scratch sizes, queue depth; units and scope for each |
| Outcomes | Exits versus launch error/timeout/cancel; selected/excluded/refused/failed/committed counts; completeness and recovery/cleanup facts |
| Evidence | Raw measurement/log/output artifact hashes and provenance, correctness/independent-validator links, missing telemetry and exclusions |
| Aggregates | Eligible sample IDs, exact formulas/quantile method, distribution/sample count, failure counts and uncertainty; no aggregate for unavailable metrics |
| Comparison | Matched environment/workload pair IDs, comparable scope, known differences, direction and statistic; no single unexplained speed score |

Missing telemetry is null with a reason. A not-run record has null tool/environment/
sample/aggregate evidence, identifies missing prerequisites, and never has a pass
or a plausible-looking duration. Actual measurement records require a reviewed
versioned schema/collector before collection; this table is its language-agnostic
field contract, not an implemented telemetry system.

## Metric definitions

| Metric | Definition and boundary |
| --- | --- |
| Startup | Launch request to first valid output/ready record, and launch to final exit separately; record any shell/launcher time included |
| Request latency | Client submission to complete request summary, with queue wait included; server execution time reported separately |
| First-result latency | Submission to first complete usable file/resource record; first byte is a separate metric |
| Successful throughput | Completed equivalent units divided by end-to-end batch elapsed seconds for a fully valid success workload |
| Mixed workload rate | Attempted/completed/succeeded counts separately per elapsed interval; never label all attempts successful throughput |
| CPU | Aggregate user/system time for the declared process tree; distinguish from wall time and CPU percentage |
| Memory | Simultaneous tree resident/private measures with method/interval; per-process high-water values separately; include runtime and helpers |
| I/O | Logical application/process bytes, actual physical/storage/network bytes if available, and payload/output bytes separately |
| Scratch | Peak simultaneously allocated staging, original recovery, records, spill and final output space; also report retained space after success/failure |
| Cancellation | Client send-to-ack, send-to-safe-boundary and send-to-terminal-result; missing acknowledgement/summary is explicit |
| Determinism | Metadata/effects/order match the declared contract across repetitions; compare with the fixture policy, not blanket deletion of timestamps/IDs |

Memory sampling can miss short peaks; report that limitation or use an appropriate
high-water metric with its actual semantics. Sum of individual process peaks is
not the same statistic as peak concurrent tree usage. Device cache flush/persistence
cost belongs in promised mutation finalization; buffered-write completion is not a
substitute. Independent RAW decoding used for QA stays outside production execution
timing but remains a required correctness gate for enabled edits.

## Aggregation and comparisons

Use exact integer durations/byte counts at capture, with a named unit and clock
frequency. Keep sufficient precision through aggregation; round only display values.
Zero/negative elapsed durations cannot produce throughput or speed ratios.

- Median: sorted middle sample, or mean of the two middle samples for an even count.
- Descriptive p95: nearest rank `ceil(0.95 * n)` in sorted samples, one-based. Report
  method and `n`; a small sample's maximum is not a demonstrated tail guarantee.
- Repeated-batch aggregate throughput: total successful units divided by total
  elapsed time for comparable completed batches, not the mean of individual rates.
- Reference/candidate latency ratio: explicitly name numerator and denominator.
  Matched-pair ratios and ratio of medians are different statistics; never substitute
  one silently. Preserve paired order and environmental drift information.

Do not combine primary/secondary RAW modes, cache states, storage devices, read
coverage, write policies or output formats into one unlabeled mean. Report strata
separately. A higher observed throughput with larger omissions is not a speedup for
the same work. Reference and native tools can have incomparable safety guarantees;
show both end-to-end workflows without implying exact equivalence.

Timeouts are censored observations: elapsed-at-stop is a lower bound on unfinished
completion latency, not a measured completion time. Do not remove them and publish
the remaining p95 as the whole workload's tail. Separate instrumentation failure
from product failure. Predeclared contamination exclusions retain reasons/raw data;
unexpected slow results are not automatically outliers to discard.

## Choosing limits and targets

All defaults and release thresholds below have status **unmeasured/unset**. Finite
values must be chosen before a release enables the corresponding operation. A
capability can remain unavailable until a safe bounded configuration is established.
This specification does not authorize running an unbounded implementation meanwhile.

| Budget | Evidence required to choose default and supported ceiling | Boundary/failure tests |
| --- | --- | --- |
| Cumulative input bytes / `--max-bytes` | Actual read amplification, including repeated passes, sidecars and nested reads | Below/at/above limit; no false complete coverage |
| Metadata depth, occurrences, allocations | Legitimate large structures plus malformed/cyclic derivatives | Reject before dangerous allocation; controlled diagnostic |
| Extracted/decoded/output bytes | Every preview and bounded consumer/projection behavior | Expansion and slow-output cases, no partial final artifact labeled complete |
| Memory / worker count | Whole process-tree series across batch size and concurrency | Bounded queues/buffers and deterministic order; no parallel writes to one physical file |
| Scratch and retained storage | Staging + original recovery + spill + outputs on supported profiles | Space exhaustion before/during staging/finalization, safe recovery and cleanup reporting |
| Elapsed deadline | Latency distributions and maximum safe noninterruptible work | Before/in/after publication, truthful 130/5 and retained receipts |
| Filter work/depth/length | Pure-filter shape, text length, comparisons and read amplification | Unknown/ambiguous semantics, adversarial nesting and bounded rejection |
| Session `maxFrameBytes` | Largest legitimate encoded UTF-8 frame and parser overhead | Multibyte text, below/at/above bytes, truncated/oversized frame |
| Session `maxQueuedRequests` | Queue memory and output backpressure with an active request | Full queue rejection without blocking control processing |
| Session `maxRequests` | Retained ID/state memory including rejected frames and controls | Bounded session lifetime, orderly drain and explicit limit close |

For each budget, publish unit/scope, measured distribution, chosen default/maximum,
margin rationale, override rules and named failure. Measure on the slowest/smallest
declared supported environment as well as the primary developer machine. Do not
choose a memory cap solely from the developer laptop's available RAM.

Select release/regression targets only after repeatable characterization and noise
assessment. Propose an absolute user-facing budget and a relative regression budget
where useful; record rationale and review acceptance. Use the same pinned workload
and comparable environment for future checks. If measurements cannot distinguish a
change from noise, report inconclusive and collect evidence under the declared rule.
Correctness, boundedness and recovery failures block acceptance regardless of speed.

## Primary measurement references

Observed **2026-10-10**, live Microsoft documentation; no immutable page revision
was established. These references explain metric distinctions for a possible
Windows collector. They do not choose an API implementation or imply cross-platform
counter equivalence.

- [High-resolution timestamps](https://learn.microsoft.com/en-us/windows/win32/sysinfo/acquiring-high-resolution-time-stamps): interval timing and external wall-clock timestamps serve different purposes. Record the clock and event boundaries; do not infer elapsed duration from adjustable calendar time.
- [Process memory counters](https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-process_memory_counters): working set and peak working set are distinct named counters. State the exact counter instead of publishing an unexplained “memory” number.
- [Process I/O counters](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-io_counters): transfer/operation counts have their own definitions. They do not alone establish physical-device traffic or durable completion.

Equivalent collector semantics on other supported OSes must be documented and
validated before comparing them. The methodology above is imageinfo's proposal;
source documentation is not performance evidence for imageinfo.
