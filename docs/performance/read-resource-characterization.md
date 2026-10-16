# Current single and batch read resource method

Ticket **#0144**, method observed **2026-10-16**. The deliverable is a fixed
private characterization procedure and public authored controls. All camera-derived
records, counts, outcomes, resource values, hashes and summaries remain private
under the retained corpus grants. This document discloses schedule constants and
method only; it supplies no camera benchmark result or product limit recommendation.

The [grid runner](../../scripts/measure_read_resources_144.py) reuses the
[#0060 direct-process collector](read-collector.md) and
[#0142 Windows telemetry companion](read-telemetry.md). The
[separate auditor](../../scripts/audit_read_resources_144.py) reloads retained
captures, independently projects the prior native oracle and invokes the existing
independent telemetry arithmetic audit. The
[authored controls](../../scripts/test_read_resources_144.py) compare twelve native
configurations with the published authored snapshot and check projection preservation
and refusal before evidence/media access. Historical
[#0061](single-read-baseline.md) and [#0063](batch-read-baseline.md) observations
remain separate; their timings are never pooled with this build.

## Frozen source, lawful use and preregistration

The reader revision is exactly `98a658e1857ee7f220c6c11bc87f5dd83499dd9d`.
Extract `git archive` into a fresh private directory, compare every extracted file's
Git blob identity against that revision, and build release with the frozen lockfile
using `cargo build --offline --locked --release` and a separate target directory.
Retain archive, manifest, toolchain, build log and binary hashes privately. The live
working tree cannot supply or replace the measured reader.

Before media access, review the original grant, restricted privacy review, exact
revision-2 full-RAW admission/provenance and passing native-read correctness evidence.
Bind the exact prior oracle bytes and all rights evidence. Private metadata/resource
analysis requires its own current task admission; a preview-specific grant supplies
no broader permission. Missing or changed permission refuses before media hashing.
Originals and received copies remain read-only. Reports and captures stay under
ignored `.local`; public report permission is never inferred from successful analysis.

Preregister the exact binary, source/build manifest, interpreter, runner, collector,
telemetry helper, auditor and all configurations before collection. The private
protocol binds the existing ordered admitted prefix of four distinct physical files.
Recheck the rights/evidence bindings before every source check and hash/stat each
source before the grid and after every configuration. Retain device/inode identity,
length and last-write time alongside hashes, and compare all boundaries. This
does not promise continuous exclusion of external actors.

## Fixed configuration and denominators

The fixed order is selected `EXIF:ISO`, then full supported metadata; within each,
raw, then all value views; within each view, one input, four distinct inputs, then
four exact repetitions of the first operand. Every configuration has two warmups
followed by ten measured attempts, with no adaptive stopping, retry or outlier removal.

| Planned denominator | Warmup | Measured | Total |
| --- | ---: | ---: | ---: |
| Complete CLI batch attempts | 24 | 120 | 144 |
| Operand slots, including duplicate operands | 72 | 360 | 432 |
| Distinct physical-file slots within batches | 48 | 240 | 288 |

The duplicate control has four operand slots and one physical-file slot per attempt;
expected native deduplication is three. Distinct batches expect no deduplication.
Four-file input mix changes with count, so differences cannot establish a general
causal file-count law. No sixteen-operand saturation, worker-count selection,
cross-host guarantee or camera-population inference is made.

Each attempt starts a fresh ordinary CLI process:

```text
imageinfo metadata read --values VIEW --output json --max-bytes 8388608 [--tag EXIF:ISO] -- INPUTS...
```

The per-input native read budget is 8 MiB. The supervisor deadline is 30 seconds,
each pipe retains at most 4 MiB, and requested resource sampling is 10 ms using the
existing 2048-sample ceiling. These are experiment bounds, not product policy.
Output pipes drain into bounded memory; capture writes, correctness checks and
source hashing occur outside timed attempts. All observation overhead remains in
elapsed time. The shared workstation's background load is uncontrolled; source
hashing warm-exposes the OS cache, device cache is uncontrolled, and no eviction,
power manipulation or host setting change is part of the method.

## Correctness and resource audit

All-values historical native oracles remain the correctness source. Selection
projects every exact `exif` namespace ISO occurrence, retains its original identity,
order, value and source range, and removes only unselected scalar resources and
their issues. Raw view changes only the requested display availability; exact raw,
normalized and normalization structures remain compared. Preview/opaque resources,
producer identity, sources, coverage, effects and nonselected envelope structures
remain exact. Only invocation identities and source display paths are normalized.
The native selected-file paths are separately checked against scheduled operands.

Retained outputs must match complete request/summary identity relationships,
occurrences, selection/output completion, explicitly partial coverage, deduplication
and unchanged effects. Capture lengths/hashes are audited. Failures and censors
remain attempts with their file-slot denominators; they are never successful samples.
An aborted source/build validation invalidates final eligibility.

The existing Windows companion supplies user/kernel CPU nanoseconds; working-set,
private-commit and lifetime peak working-set bytes; timestamped observations;
logical I/O operation and transfer counters; sample maxima; observation overhead;
and stdout/stderr counts. Lifetime endpoint counters and sampled current-memory
maxima are distinct. Counter API errors, unavailable values and arithmetic
inconsistencies retain explicit audit dispositions and exclude affected attempts
from resource summaries. No earlier sample substitutes for a failed endpoint.

The private audit retains every attempt's disposition and per-configuration eligible
count, minimum, median, maximum and mean for each available metric. These are
success-conditional descriptive observations. Logical transfers are not physical
device traffic; sampled maxima are not guaranteed allocation/resident peaks.
Sampled direct-child detection is not containment. The CLI emits one final batch
envelope, so first-result and per-file latency remain unavailable. Dividing batch
elapsed time cannot create those metrics. Collector overhead/noise and policy
evaluation remain separate #0150/#0152 work.

## Local verification

With a private protocol and an exact frozen binary already prepared:

```console
python scripts/measure_read_resources_144.py --run-root FRESH_PRIVATE_ROOT
python scripts/audit_read_resources_144.py --run-root FRESH_PRIVATE_ROOT
```

Set `IMAGEINFO_144_BINARY` to the frozen executable for the native authored grid,
then run `python scripts/test_read_resources_144.py`. Run existing
`scripts/test_read_telemetry.py` with its documented test-only dependency and
`scripts/test_measure_batch_read.py` for inherited rights controls. Private execution
logs and the integration manifest identify exact build, grants, oracle, superseded
attempts and final retained evidence without publishing camera outcomes.
