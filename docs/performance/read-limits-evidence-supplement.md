# Current-read evidence supplement (#0152)

This supplement to `read-limits-v1` is advisory. The six proposed constants and
operating ceilings remain **unadopted historical proposals**. No runtime default,
override, policy, release budget or guarantee changes. Ordinary numerical
engineering does not acquire a generic repeated approval gate from this review.
The [machine ledger](read-limits/evidence-supplement.v1.json) binds exact public
source summaries and exposes their actual distributions without pooling builds,
workloads, consumers or denominators. Private camera evidence is reviewed in a
separate private companion; none is a source for this public supplement.

## Evidence and recommendations

| Evidence | Actual population and observation | Bound disposition |
| --- | --- | --- |
| [#0146 session](read-session-resources.md) | 16 cells; nine explicit-close sessions at 1/64/255 reads produce 960 results; automatic close produces 256 and duplicate-ID control one. All 1,217 results are retained. Three fresh sessions per lifetime, not 960 independent process samples. | Retain current framing and lifetime boundaries as independently tested correctness limits; select no memory or latency allowance. |
| [#0147 consumers](output-consumers.md) | 50 attempts = eight warmups + 40 measured + two broken-pipe controls; ten samples per transport/consumer. Complete output verified for 48 ordinary attempts. Slow delivery includes intentional waits. | Keep consumer strata separate. Fast drains describe this harness; slow consumers require delivery-inclusive reporting. No product timeout or pipe-capacity inference. |
| [#0148 bytes](reader-byte-boundaries.md) | Six single observations: four successes and two precise default-budget refusals. Metadata totals 8,388,607/8,388,608/8,388,609 planned bytes; block requests 1,048,575/1,048,576/1,048,577 bytes. | Default boundaries have finite positive/refusal evidence. Retain implementation defaults for now; neither raise nor adopt operating ceilings from six observations. Hard ceilings remain configuration-only tests. |
| [#0149 structures](reader-structural-boundaries.md) | 45 native outcomes across 15 cells: 30 successes, 15 expected refusals. Strict resource audit **FAILED: one inconsistent memory pair; 44 whole attempts valid**. All 45 native outcomes remain verified. | Preserve the failed audit, cause unproven, without retry or validator relaxation. Valid-only ranges cannot qualify a resource envelope. |
| [#0150 observer](collector-overhead.md) | 198 attempts = 18 warmups + 180 measured; 90 paired comparisons, three rounds of 30 pairs; all 99 telemetry attempts valid. Paired median telemetry-minus-elapsed is 116,400/126,300/462,000 ns; paired MAD is 542,100/658,000/789,750 ns. | Dispersion exceeds median effect. Use matched instrumentation, alternating order and a complete retained denominator for this tiny authored workload; subtract no assumed overhead. |

The ledger retains per-cell ranges and distributions by exact JSON pointer, with
their units and original denominators. #0146 request medians span
5.6027–5.8245 ms in the one-read group, 5.6250–5.8168 ms at 64 and
5.6144–5.7634 ms at 255 only as given by the source summary; consult its exact
group values rather than treating these observations as a universal latency
distribution. Request timings include planned request failures, writer scheduling
and complete-LF delivery. Automatic-close final live memory is unavailable;
post-exit memory does not fill it. #0147 fast/slow elapsed medians range from
10.193/539.137 ms for JSON to 10.775/554.303 ms for JSONL. Scheduling stretches the
requested slow read cadence; writer blocking was not instrumented.

The [original proposal](read-limits-proposal.md) retains its historical public
#0061 worked advisory noise rule and historical evidence. #0150 does not fit a
new numeric threshold, validate that rule across workloads or authorize pooling
#0061 with newer builds. No absolute/release latency budget is selected: smallest
and slowest supported environments, cold-cache strata and broader workloads
remain undeclared or unmeasured.

PERF-001–012 and BW-001–015 retain their existing residual obligations. This
supplement supplies bounded evidence for current reads; it does not replace the
tracking map, close unsupported workload groups or establish parity acceptance.

## Units, failure and override boundaries

Source file length is stored extent, not metadata request volume. Metadata bytes
count successful requests, including repeated reads; a failed request is not
attempted-I/O accounting. Block bytes bound one requested metadata buffer, not
all allocations. Output bytes count encoded UTF-8 transport including framing,
not source size, parser bytes or memory. Physical/device traffic is unavailable;
process logical I/O includes output and process activity. CPU is process-lifetime
counter nanoseconds, with zero values at counter resolution retained as observed.
OS peak working set, sampled working set, private commit and live checkpoint
growth are distinct quantities; none is a quota or all-allocation peak.

Box count is per input; TIFF entries accumulate per CMT parse. BMFF parent-path
depth and zero-based TIFF directory depth are different traversal measures.
Timed records are per supported track sample, not a generic frame queue. Native
above-boundary reads refuse without exposing complete metadata. Earlier reads
may already have happened; TIFF checks follow the whole-CMT read. #0149's
above-boundary authored structures succeed with just the relevant limit raised
by one, independently of their failed resource audit. This supports finite
override mechanics, not resource qualification of the larger hard envelope.

`--max-bytes` still permits 1–268,435,456 metadata bytes. Its existing default is
8,388,608; per-block default/hard ceiling are 1,048,576/8,388,608. Box/entry/record
defaults are 4,096 and hard ceilings 65,536; depth is 16/64. Lower budgets remain
available; this review adds no retry, escalation or override restriction. Preview
64 MiB/1 GiB, source-binding 256 MiB and request/result API four-input/8 MiB
boundaries are separate existing scopes, not adopted ceilings here.

The sequential session tests cover 128/129 UTF-8-byte IDs, duplicate IDs,
524,288-byte input frames including line terminators and the 256-read lifetime.
Oversized/nonterminated frames and duplicate IDs refuse; exactly bounded valid
frames and automatic completion retain their independently checked results.
UTF-8 bytes are not character counts. Session frame/result limits and captured
research output caps must remain separate. Broken output gives
`OUTPUT_INCOMPLETE/BrokenPipe`; no final session frame is guaranteed after a
failed write. Research watchdogs/capture caps retain censored or partial attempts
and do not implement product deadlines or cancellation.

## Concrete remaining choices

| Dimension | Remaining choice or evidence; current disposition |
| --- | --- |
| Memory / workers | Declare supported environment and all-allocation/OS-memory objective before selecting a quota or worker count. Sampled direct-child membership is not containment. No concurrent reader queue is measured or introduced. |
| Scratch / output | Separate harness captures, product output and filesystem allocated space. No product scratch quota, free-space reserve or physical-allocation accounting is measured. Preview output space/camera distributions remain private; no public numeric selection follows. |
| Deadlines | Declare execution versus delivery scope and failure/cancellation contract before any product deadline. A 10/30-second harness watchdog supplies neither. |
| Filters | Selected `Make`, selected ISO/raw and all-values workloads differ. Filtering is not a proven bound on parsing, opaque coverage or output allocations. Dynamic executable filters remain unsupported. |
| Frames / IDs / queues | Retain implemented sequential session frame/ID/lifetime boundaries; no queue depth, concurrent requests, tag-discovery queue or persistent session cache is available to tune. New mechanisms would require their own exact implementation/review. |
| Storage / caches | Fresh processes coexist with uncontrolled warm-exposed OS/device caches and preflight hashing. Declare physical topology, cold/warm strata and background/power conditions before portability/resource budgets. Logical I/O is insufficient. |
| Unsupported operations | No mutation, writer, storage profile, restart repair, RAW write or general privacy guarantee is inferred. Missing capabilities are not numerical tunables. |

Run `python scripts/check_read_limits_supplement.py`. It verifies the exact public
summary identities, copied distributions, denominator arithmetic, units/scopes,
six unchanged proposal constants and failed #0149 audit. Its corruption controls
check rejection of altered sources, populations, units, metrics and adoption.
It reads JSON only; it executes no media, reader or benchmark. Independent
requirement-to-evidence review remains separate from this author's checks.
