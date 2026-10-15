# Native RAW read limits proposal

Card **#0064**, proposal `read-limits-v1`, reviewed 2026-10-15. **Proposed;
Terry has not adopted these policy choices.** This handoff changes no runtime
default, override, parser, API or enabled capability. It recommends retaining the
existing parser defaults and initially treating those same values as the operating
ceilings for a declared read configuration. Larger existing hard ceilings remain
implemented but lack measured resource qualification. This conservative ceiling
is a policy recommendation, not evidence that every input below it succeeds.

## Evidence and its limits

The [single-file baseline](single-read-baseline.md) and its
[public ledger](single-read/results.v1.json) provide one full-RAW R5 fixture,
99 passing attempts including nine warmups, and 90 eligible measured attempts.
The fixed invocation used an 8,388,608-byte metadata budget with the remaining
native defaults. Pooled median is 10.0131 ms; descriptive p95 is 10.9693 ms.
Output is 61,194 or 61,199 bytes. Output bytes measure JSON transport, not metadata
bytes read, allocated bytes, source length or resident memory. These observations
show that configuration completed this one workload; they do not measure the
minimum sufficient parser limits, a largest legitimate structure or headroom.

The [batch baseline](batch-read-baseline.md) fixes sizes 1, 2, 4 and 8, with an
8 MiB per-input metadata budget. Its actual camera-derived sizes, timings and
outcomes remain private because publication is denied. The public authored grid
and six controls qualify collection/classification behavior, not camera scaling
or maximum parser capacity. No private report was read or used for numerical
policy selection here. #0061 and #0063 use different frozen executables; their
timings must not be pooled. Both use fresh processes and warm-exposed,
uncontrolled OS caches on one shared Windows host.

CPU, RSS/private memory, logical/physical I/O, read amplification distributions,
controlled cold-cache behavior, smallest/slowest supported environments and
large/adversarial structure saturation measurements are unavailable. No measured
OS memory limit, quota, worker count, source-length cap or hard elapsed deadline
can be selected from this evidence. The experiment's 10 s/30 s deadlines and
pipe capture bounds remain experiment settings.

## Concrete proposal

All byte quantities below are integer bytes (MiB = 1,048,576 bytes). Proposed
ceilings apply independently to each input/parser scope, with inclusive equality.
Keep smaller caller budgets available; propose no automatic increase or retry
after a limit refusal. Enlarging the operating envelope requires explicit policy
review and appropriate authored and legitimate-structure evidence. This document
does not implement the proposed ceiling or remove current larger overrides.

| Limit | Existing default = proposed default and operating ceiling | Existing runtime hard ceiling | Exact scope |
| --- | ---: | ---: | --- |
| `metadata_bytes` | 8,388,608 | 268,435,456 | Cumulative successful metadata-request bytes in one reader invocation; repeated reads count again |
| `block_bytes` | 1,048,576 | 8,388,608 | One metadata buffer request |
| `boxes` | 4,096 | 65,536 | Total scanned BMFF boxes per input |
| `depth` | 16 | 64 | BMFF recursion parent-path length; separately TIFF IFD traversal depth, starting at zero |
| `entries` | 4,096 | 65,536 | Cumulative entries in one TIFF parse, independently for each CMT allocation |
| `records` | 4,096 | 65,536 | Timed records in one supported track sample |

The byte default is retained because it is the tested configuration, not because
8 MiB is a measured optimum. Structural defaults are retained because current
bounded parsing completed the measured read and raising them has no public
large-structure/resource justification. Equal operating ceilings keep that
proposed envelope explicit. These choices trade larger-input acceptance for a
smaller initially declared configuration; they require Terry's acceptance.
No measured percentage safety margin or capacity guarantee is claimed.

The actual definitions are in [the reader](../../src/reader/mod.rs),
[byte charging](../../src/reader/bounded.rs), [BMFF scan](../../src/reader/bmff.rs),
[TIFF traversal](../../src/reader/tiff.rs) and
[timed records](../../src/reader/tracks.rs). `entries` is not a total-file
occurrence limit. `block_bytes` is not peak memory: retained objects, strings,
paths, output serialization and other allocations remain additional. No total
allocation count or total occurrence cap is newly proposed or implemented.

`--max-bytes` currently permits 1 through 268,435,456 and means metadata reads,
not full input-file length or cumulative batch bytes. The request/result API
separately caps inputs at four and metadata budget at 8 MiB; the ordinary CLI
batch is a different interface. Neither boundary is inferred from batch timing.
The reader's existing preview default/hard ceiling (64 MiB/1 GiB), source-binding
256 MiB length restriction and API transport limits are separate existing bounds.
This proposal selects no new preview/extraction, source-binding or transport limit.
The preview bound is also checked when metadata read recognizes a stored preview
extent, including its declared padding; retaining it does not enable extraction
or qualify large preview handling. Ordinary CLI read also has an existing
16-explicit-operand preflight bound, before deduplication; this proposal changes
neither that bound nor the separate four-input API boundary. The batch method
stops at eight; it does not qualify the 16-operand boundary by measurement.

## Finite boundary vectors and outcomes

[The versioned proposal and vectors](read-limits/proposal.v1.json) specify six
limit rows, with below/at/above triplets for both proposed operating limits and
existing hard configuration ceilings: 36 scalar vectors. `within` means only
that the scalar comparison passes; it never means the media parser succeeds.
The independent checker validates the proposal arithmetic without reading media.
It is not an enforcement implementation or parser saturation experiment.

Run `python scripts/check_read_limits.py` from the repository root.
The [independent checker](../../scripts/check_read_limits.py) passes 36 scalar
vectors, 15 unsigned range/charging arithmetic model controls (including u64
overflow), and nine malformed/drift rejection controls. It independently rechecks
the 99 public attempts/90 measured samples and recomputes the noise formula from
ordered samples. The checker fixes the six reviewed constants explicitly; it
does not parse Rust or invoke the collector, auditor or native reader. Its
arithmetic controls do not execute native overflow/allocation failure branches.

For a live read, exceeding a supported ceiling refuses with `LIMIT_EXCEEDED`
before constructing the bounded source. Cumulative metadata checked-add overflow
also refuses, and byte/block requests over their budget refuse before buffer
reservation or a read of that requested range. Earlier successful reads can have
occurred. The counter advances only after a successful `read_exact`; a failed
read does not establish attempted-I/O or resource accounting. Excess box count
refuses before the next box header read; excess TIFF
entries refuse before iterating that directory; excess timed-record count refuses
before reading the next record header. Depth checks use the internal zero-based
depth/path value; they are not a promise about an informal count of nested tags.
Invalid ranges/cycles can instead produce `INVALID_STRUCTURE` before a budget
check; no error precedence is promised for multiply-invalid input.

Existing [authored parser tests](../../tests/reader_contract.rs) cover small-budget
refusals, truncation, cyclic TIFF and malformed lengths. They do not establish
all exact default/hard-ceiling saturation cells. Full live below/at/above parser
cases, cumulative overflow and allocation-failure behavior at the proposed sizes
remain unrun under this ticket. A refusal must remain distinct from a complete
successful result; no performance gain from less work qualifies as improvement.

## Noise-based regression recommendation

Recommend an **advisory median investigation budget**, not a release gate or user
deadline. From the public #0061 ledger, trial-median span is 356,850 ns and the
largest absolute first-ten/last-ten window shift is 399,650 ns. Set descriptive
noise scale `N = max(span, absolute window shifts) = 399650 ns`. Propose a budget
`B = max(0.10 * baseline median, 3 * N) = 1198950 ns` (1.19895 ms,
about 11.97% of the observed median). The 10% floor and factor three are explicit
policy margins proposed for review; they are not fitted confidence levels,
statistical significance or a measured tail bound.

For a future comparison, preregister the same workload/consumer/cache stratum,
three trials of three warmups plus 30 measured attempts, no trimming/retries,
and a matched baseline and candidate on the same host. Recompute `N` from that
matched baseline and retain the formula; the historical 1.19895 ms is only the
worked recommendation for #0061. Investigate when all three candidate trial
medians exceed the matched baseline pooled median plus `B`. Otherwise report
no advisory signal or inconclusive comparison, never proof of no regression.
Keep failure/censor/invalid counts and all 90 measured opportunities; any such
outcome prevents a clean latency comparison and must be reviewed independently.
Correctness/boundedness failures take priority regardless of speed. Report p95
descriptively without applying this median budget to it.

No numeric batch regression budget can be published from the available public
camera evidence. A later lawfully reviewable batch comparison must compute
size-separated noise against its own matched baseline, retaining the full slot
denominators and changed file mix. Authored timings cannot substitute for that.
No absolute user-facing latency promise is recommended before representative
environment/cold-cache and broader workload measurements.

## Terry choices and handoff

Terry must choose whether to accept the six retained defaults and conservative
operating ceilings, whether a future implementation should restrict today's
larger overrides or expose a separately qualified configuration, and whether to
accept the advisory 10%/three-noise-scale median investigation rule. These are
three concrete policy choices; this handoff adopts none. Broader measurements
are needed before enlarging/qualifying the envelope or setting resource/release
guarantees, rather than prerequisites invented for delivering this proposal.
RAW read coverage remains partial; write, storage, repair and privacy admission
are unchanged. See [the general measurement rules](measurement.md).
