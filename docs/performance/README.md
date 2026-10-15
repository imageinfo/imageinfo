# Reproducible RAW performance requirements

Status: initial **requirements proposal**, revision `2026-10-10.1`, card **#0008**.
These requirements remain language independent and select no numerical speed target.
First target: Canon EOS R5 **full RAW CR3**. C-RAW and
Dual Pixel RAW are separate secondary strata, not substitutes for the first corpus.

Subsequent implementation supplies the [bounded metadata-read collector](read-collector.md)
and an [actual single-file baseline](single-read-baseline.md) for the declared
Rust reader. The requirements below retain their original scope; those finite
observations do not establish broader workloads, controlled cold caches or defaults.
[#0063's batch method](batch-read-baseline.md) adds a finite ordinary-CLI grid
and independent per-file/whole-batch audit. Camera-derived results remain private
under their report grants; its public controls use authored inputs only.

Use [measurement and limit selection](measurement.md), the
[validation record](validation.md), [fixture plan](../fixture-plan/README.md),
[write-safety contract](../write-safety/README.md) and
[integration proposal](../legacy-compatibility/integration.md) together. Performance
work must preserve the behavior being measured. A faster incomplete or unsafe result
is a different workload or a failure, not an optimization claim.

## Requirements

**PERF-001 — Correctness gates timing.** Admit fixtures through the provenance and
fixture contracts. Every measured run retains operation outcomes, completeness,
output identities and required preservation checks. A success benchmark needs all
its required correctness assertions to pass. Expected refusals, cancellation and
fault recovery have their own workloads and outcomes; they are never counted as
successful edits. Reference-only measurements cannot demonstrate imageinfo parity.

**PERF-002 — Reproduce the inputs and executable.** Record fixture IDs/hashes,
camera/firmware/mode when known, file count, actual input bytes, metadata size/depth,
preview count/bytes and layout variation. Unknown properties are null with a reason.
Record complete executed distribution/runtime/driver identity, configuration,
arguments as arrays, policy/schema/capability revisions and environment. Do not
publish private filenames or media to make a benchmark reproducible; share only
admitted assets or an acquisition recipe with disclosure restrictions.

**PERF-003 — Measure equivalent work.** Reference comparisons use the pinned ExifTool
baseline and a versioned correspondence plan from the fixture work. Match selected
fields, value views, duplicate coverage, recursion, output, write effects and storage
conditions. A common comparable subset and full native work are separate rows.
Report differences that cannot be equalized, such as stronger native recovery checks.
Do not disable production safety checks or drop unknown data to win a timing result.

**PERF-004 — Separate startup, cache and storage effects.** Process startup, application
state, OS file cache, device cache and remote-server cache are separate dimensions.
A new process is not proof of cold file caches. Record the conditioning procedure
and observable evidence for each layer; otherwise label it unknown/uncontrolled.
Hash verification, cloning and previous runs can warm caches: do those before the
declared conditioning step or disclose their effect. Do not call a warmed clone a
cold original. Cloud hydration/network latency and local storage are separate strata.

**PERF-005 — Include the promised work.** End-to-end timing begins before launching
an ordinary process or submitting a persistent request and ends after the required
result is received and the process/request completes. Mutation completion includes
candidate checks, original recovery, required flushes and receipt finalization.
Separate phase timings are useful but never replace the end-to-end result.
Independent post-run validation and fixture preparation are measured separately;
they are not runtime dependencies of normal imageinfo operation.

**PERF-006 — Count output and backpressure.** Measure bytes produced and use a declared
consumer/capture path. A terminal, buffered file, bounded validator, fast drain and
deliberately slow consumer have different costs. Capture sufficient output evidence
to prove required results were emitted. Redirecting output into a discard sink alone
does not prove correct serialization. Ordered output buffering must remain bounded;
record stalls and queue depth rather than hiding them with unbounded concurrency.

**PERF-007 — Measure resource use precisely.** Record peak and time-varying memory,
CPU time, process-tree membership, handles/descriptors where available, logical I/O,
physical/device I/O when observable, bytes decoded/extracted, output and scratch space.
Give every metric its unit, collection method, sampling interval and scope. Missing
telemetry is unavailable, not zero. Never equate process transfer bytes with physical
disk traffic or sum independent per-process memory peaks as a simultaneous tree peak.

**PERF-008 — Keep repeated work isolated.** Use fresh destination copies for each
write trial; reset state outside the measured interval and before cache conditioning.
Never modify corpus originals or recompress sensor data. Persistent sessions must
reset request-local settings and show bounded retained memory across admitted reads,
errors, previews, applies and cancellations. Cache benefits are reported alongside
their capacity/eviction policy and retained memory. Failed requests cannot leak edits.

**PERF-009 — Bound cancellation and failure behavior.** Record request-send,
acknowledgement, safe-boundary and terminal-result times separately. Queue cancellation,
active read cancellation, staging cancellation and in-flight publication differ.
WS finalization/recovery takes precedence over a nominal timeout. State the largest
noninterruptible unit and measure its effect; never promise immediate interruption
or discard durability work to meet a latency target.

**PERF-010 — Preserve raw samples and uncertainty.** Declare trial count, order,
warmups, stopping rule, outlier policy and comparison before collection. Retain every
attempt, including failures, timeouts and incomplete telemetry. Counterbalance or
seed-randomize candidate/reference order within matched strata to expose drift.
Publish sample counts, distributions and uncertainty; do not select the fastest run
or average per-file rates into a misleading batch throughput. See measurement rules.

**PERF-011 — Set defaults from evidence.** Initial resource policies must be finite
and discoverable, but no numerical defaults are established here. Choose defaults,
hard ceilings and supported workloads using the procedure below, document the
tradeoffs and review them before release. Exceeding a limit yields a bounded named
failure with honest coverage and WS outcomes. A caller override cannot disable
format bounds, input validation, concurrency guards or recovery obligations.

**PERF-012 — Report scoped claims.** Publish workload/recipe/tool/corpus/environment
revisions with every comparison. State which camera modes, storage profiles and
output formats were exercised. R5 full RAW file size alone does not predict metadata
speed, and C-RAW results do not replace full RAW results. Neither source-level review
nor synthetic arithmetic supports a speed multiplier or cross-platform claim.

## Workload matrix

All rows are **planned/unmeasured**. Use admitted full RAW fixtures unless a row
explicitly concerns generated adversarial inputs or secondary variants. Start with
single-file and small collections; grow file count and total bytes geometrically
within declared test-machine budgets. Record actual values rather than treating a
file-count label as a workload definition.

| ID | Workload and controlled variation | Required metrics / correctness evidence | Fixture families |
| --- | --- | --- | --- |
| BW-001 | Process launch, offline help, format/tag discovery | Launch-to-first output and complete exit; no media or network I/O required | FXP-014 |
| BW-002 | One full RAW: selected fields versus full supported metadata; raw/normalized/display views | First complete result, total latency, bytes read, peak memory; exact identity/value/coverage | FXP-001, FXP-003, FXP-004, FXP-005 |
| BW-003 | Small-to-large manifests with distinct and duplicate physical inputs | Batch throughput, tail file latency, ordered buffering, memory versus total bytes/count; deterministic selection and deduplication | FXP-013, FXP-014 |
| BW-004 | Large XMP, many tags, deeply nested or malformed owned derivatives | Peak memory, work/depth limit response, bounded errors; no uncontrolled allocation, false absence or hang | FXP-009, FXP-010, FXP-012 |
| BW-005 | Enumerate and extract each observed stored preview, including multiple assets | Input/output bytes, time to asset and total, bounded extraction; exact stored bytes and no RAW development | FXP-007, FXP-022 |
| BW-006 | RAW plus paired XMP read/diff/copy planning; conflicts and missing sidecars | Pair resolution/preflight latency and memory; exact mappings, ambiguity/refusal and unchanged media | FXP-008, FXP-016, FXP-017 |
| BW-007 | Existing XMP edit, new sidecar, no-op and retained/discard-after-success backup policies | End-to-end and phase timings, I/O, peak scratch bytes; no-op does not rewrite, RAW untouched, recovery retained until finalization | FXP-016, FXP-017, FXP-023 |
| BW-008 | Individually enabled embedded EXIF/GPS/XMP edits with layout growth/shrinkage | Full safety cost, sensor/reference/calibration/opaque preservation, finalization, temporary disk; independent usability gating | FXP-018, FXP-019, FXP-020, FXP-021, FXP-022 |
| BW-009 | Persistent session: repeated reads, alternating modes, failures then reads, queue saturation and frame/session caps | Startup amortization, per-request latency, sustained throughput, tree memory/IDs/queue depth, control response; state isolation | FXP-015, FXP-023 |
| BW-010 | JSON/JSONL and declared CSV projections with fast/slow output consumers | Serialization/capture volume, first result, end-to-end, backpressure and bounded spill; complete schema/coverage/order | FXP-014, FXP-015 |
| BW-011 | Cold/warm declared layers across local SSD/HDD, removable, network and hydrated/unhydrated storage | Elapsed versus CPU, logical versus device/network I/O and cache evidence; operations stay within supported profile | FXP-013, FXP-023 |
| BW-012 | Cancellation, deadline, disk-full, stale source, output failure and recovery inspection | Send/ack/safe-boundary/completion latency; per-file outcomes and artifacts, never fabricated successful timing | FXP-012, FXP-023 |
| BW-013 | Pure filters: select all/none, unknown/ambiguous values, near expression budgets | Filter cost, input read amplification, excluded/failed counts; three-valued semantics and fixed limits | FXP-004, FXP-012, FXP-014 |
| BW-014 | Paired rename/move and time/location plans where individually supported | Pair preflight, cross-volume copy/finalization cost and scratch space; collision and partial-group recovery | FXP-025, FXP-026 |
| BW-015 | C-RAW and Dual Pixel RAW under separately admitted fixtures | Same metrics with explicit separate variant labels and extra-plane preservation; never combined with primary full RAW | FXP-027, FXP-028 |

Remote/removable/cloud rows do not enable mutation support on those locations.
Unverified writer/storage combinations are reported not-run/unsupported and tested
as refusals separately. A refusal's latency is not a successful edit's throughput.

## Current handoff

This specifies how to measure and choose targets; **all numerical targets/defaults
remain unset**. Actual corpus/reference acquisition remains #0013, writer/storage
proof #0014 and protocol completion #0015. Backlog #0016, performance-measurements,
owns the real baseline and subsequent limit decisions. Implementation still waits
for Terry's explicit language/design decision.
