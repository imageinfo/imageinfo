# Performance specification validation and handoff

Reviewed **2026-10-10**, revision `2026-10-10.1`, card **#0008**. These checks concern
the measurement specification. **No imageinfo/ExifTool benchmark ran and no numeric
target or default was selected.**

## Results

| Check | Result |
| --- | --- |
| Performance requirements | PERF-001 through PERF-012, unique |
| Planned workloads | BW-001 through BW-015; fixture references resolve |
| Synthetic calculation/eligibility cases | 12 passed |
| Not-run example | Tool/environment/samples/aggregates/correctness/target remain null; missing prerequisites stated |
| Resource categories | Ten limit categories include measurement criteria and boundary/failure tests |
| Source/contract review | Measurement references dated; fixture, RAW safety, output and session obligations retained |
| Real benchmark runs | 0 |
| Numeric targets/defaults chosen | 0 |

The [examples](examples.v1.json) contain invented values only. A local documentation
checker evaluated exact arithmetic and requirement/fixture references; this is not
a benchmark harness, language selection or product dependency.

## Reproduction and arithmetic review

Read the JSON and apply the formulas in [measurement](measurement.md). Compare
exact rational results with each `expected` value; round only when presenting real
measurements later. The cases verify:

- Odd and even medians, with an empty set reported unavailable.
- Nearest-rank p95 on a deliberately small synthetic sample, not a tail guarantee.
- Aggregate throughput as total units divided by total elapsed time.
- Explicit reference/candidate ratio direction and rejection of zero duration.
- Peak simultaneous process-tree memory instead of sum of individual peaks.
- Completed, correct, matched-stratum samples are eligible for success summaries;
  timeouts, incorrect outputs and mismatched strata are not.

For example, synthetic batches of ten units in two seconds and ten units in eight
seconds yield **two units/second** together. Averaging the individual rates would
answer a different question. Likewise, two processes peaking at different times
need not reach the sum of their separate peaks concurrently. These examples explain
the method; they are not imageinfo performance numbers.

Retain ineligible attempts and their reasons in the real run ledger. The eligibility
check does not authorize discarding failures or reporting a success-only percentile
as the entire workload's tail. Censored timeout duration is not completion duration.

## Ticket and requirement coverage

| Requested scope | Delivered |
| --- | --- |
| Single file and large batches | BW-001–003; startup, first result, throughput, ordered buffering and input-shape fields |
| Huge metadata and embedded extraction | BW-004/005; depth/size/expansion budgets, bounded allocation and exact asset checks |
| RAW/local/remote storage and caches | BW-002/011/015; full RAW priority, variant strata, explicit process/app/OS/device/server cache state |
| Writes | BW-006–008/014; complete safety/finalization/scratch cost, isolated copies, no-op and recovery distinctions |
| Persistent operations and output | BW-009/010/013; queue/ID/record budgets, pure filters, state isolation and slow-consumer effects |
| Determinism/cancellation/failures | PERF-008/009; BW-012; outcome, send/ack/safe-boundary and completeness evidence |
| Reproducible methodology and environment | PERF-002–007/010; record fields, raw samples, conditioning/order and comparable strata |
| Criteria for later targets | PERF-011/012; finite defaults, supported ceilings, margin/noise analysis and review before release |
| PR-028 and CLI-013 | Repeatable workloads, explicit measurement boundaries and bounded collections/sessions |
| PR-023–027 and WS-007–024 | Platform scope, correctness/privacy, resource bounds, recoverability and preservation stay prerequisites |

The documentation index, roadmap, open performance decision and earlier references
now point to this protocol. Inventory revision `2026-10-10.7` assigns actual measured
limits to #0016 while retaining all capability states; inventory schema/reference/
dependency checks and the existing ten negative cases pass. Internal links, source
attribution and Git whitespace are checked for handoff.

## Follow-up

**#0016, performance-measurements**, owns the actual record schema/collector, admitted
baseline runs, raw results and proposals for numeric defaults and release budgets.
It depends on lawful corpus/reference setup (#0010/#0013) and later authorized
implementation plus relevant writer/integration evidence (#0014/#0015).

The [governance proposal](../../GOVERNANCE.md) is now recorded; actual operational
readiness remains #0017. The next requirements ticket is #0010, artifact provenance.
This card's handoff does not select a language, claim a speed advantage, enable a
storage profile or pretend that a benchmark can precede its required fixtures.
