# Single-file EOS R5 metadata-read baseline

Card **#0061**, protocol `single-read-v1`, fixed **2026-10-15 before collection**.
This protocol measures the current full supported metadata subset for one admitted
EOS R5 full RAW fixture. It does not measure full RAW decoding, selected-field
projections, preview extraction, writes, sessions, other files or ExifTool speed.

## Fixed collection protocol

The [machine-readable protocol](single-read/protocol.v1.json) pins the executable,
collector, capture runner and private trial-configuration hashes before the first
attempt. The frozen executable is built from accepted source commit
`5f7a86eca8e36b48d8334c8e754e3859dd9bb213`, with the pinned Rust 1.99.0 toolchain,
root lockfile and `cargo build --locked --release`. Every one of the source
archive's 439 tracked blobs was compared byte-for-byte with that Git revision
before the separate target-directory build. Working-tree implementation activity
cannot replace this executable during collection.

The exact preregistered public-protocol bytes used Windows CRLF line endings and
remain preserved privately under their original hash. Publication normalizes only
those line endings to the repository's LF convention. The auditor verifies this
byte-only transformation and reports both the original precollection identity and
the published LF identity; no protocol value, configuration pin or sample changed.

Three separately initialized calls to the accepted
[#0060 collector](read-collector.md), inside one Python runner process, each retain
three warmups followed by exactly
30 measured attempts. Trials run in order 1, 2, 3 with a fixed five-second delay
between trials. There are 99 total attempts and 90 measured opportunities. There
is no retry, trimming, outlier removal or adaptive stopping; all failed, malformed,
censored and invalid attempts remain in their original position. These adjacent
trials share a host and cache history; they are not independent machine samples.

Each attempt launches a fresh direct process for one explicit file with
`metadata read --values all --output json --max-bytes 8388608 -- INPUT`.
The process deadline is 10000 ms and capture is bounded to 1048576 bytes per pipe.
The native read limits remain enabled. The consumer drains stdout/stderr into
bounded memory. Timing uses integer `perf_counter_ns` nanoseconds from immediately
before process creation through direct exit and both pipe drains. Polling/thread
overhead is included; no estimated overhead is subtracted.

The [capture runner](../../scripts/measure_single_read.py) calls the unchanged
collector and saves its already bounded returned stdout/stderr **after** the timed
return. This makes every output available to an independent verifier. These
private evidence writes and subsequent validation lie outside timing, but may
affect the following attempt's cache/load. They are part of this recipe's declared
conditioning history. Capture files are never public benchmark fixtures.

## Cache and environment scope

The observed stratum is **fresh process, OS cache warm-exposed/uncontrolled**.
Whole-file identity hashing during collector preflight exposes the input to the
OS cache before each trial, and repeated reads follow it. No observation proves
every required page is resident. Application state is fresh per attempt; OS,
device and server cache states are not independently controlled.

| Cell | Status / reason |
| --- | --- |
| Fresh process, preflight hash plus repeated-read exposure | Run by this protocol; no cache-residency guarantee |
| Controlled OS-cold input | Unrun: no validated per-input cache-eviction procedure; hashing itself warms the input; no workstation-wide cache/policy changes authorized or performed |
| Controlled device-cold input | Unrun: no independent device-cache control/evidence or physical power cycle |
| Persistent application/session warm state | Unrun: workload launches ordinary processes |

The local fixed NTFS corpus volume maps to a Kingston SNV2S2000G NVMe SSD. The
host reports an Intel Core i7-13700H (14 cores, 20 logical processors),
68374552576 bytes physical memory and Windows AMD64. Balanced is the observed
power scheme; power source, thermal state, dynamic clock behavior, scanner/indexer
activity and background workload remain uncontrolled or unknown. Read-only
allowlisted before/after hardware, volume, power and aggregate load snapshots are
retained privately. The input has ReadOnly/Archive attributes; compression and
encryption policies beyond those observed attributes are not inferred.

## Correctness, failures and analysis rule

Fixture FX-R5-001 is admitted under [#0013](../fixture-plan/README.md). Its private
manifest grants analysis, declares full RAW CR3 and binds the actual source hash.
The exact prior native JSON oracle is bound by the passing
[#0020 differential experiment](../reader/validation.md), rather than recreated
from the measured executable. Source length/mtime/SHA-256 and executable SHA-256
must remain unchanged across every trial.

The independent audit verifies every captured byte count/digest, parse, request
identity relationship and narrow invocation-ID/display-path normalization against
that oracle. Stored values, producer revisions, occurrences/order, ranges,
coverage, issues and effects remain compared. A successful sample needs exit 0,
empty stderr, complete selection/output, exactly one read, explicitly partial
coverage and no source effects. This repeats the existing declared read closure;
it is not a new independent sensor decoder or broader parity result.

Statistics use only eligible successful measured samples, conditional on success.
Warmups are retained separately. Per-trial and pooled distributions report count,
minimum, maximum, arithmetic mean, sample standard deviation (`n-1`), median
(even count: mean of the two center values), median absolute deviation and
descriptive nearest-rank p95 at sorted index `ceil(0.95*n)`, one based. CV is
sample standard deviation divided by mean. Exact sample durations retain integer
nanoseconds; display conversion divides by 1000000 to milliseconds.

Noise reporting includes the range of the three trial medians and each trial's
first-ten versus last-ten attempted measured windows, with eligibility counts.
No inference of a stable tail, regression threshold or statistically independent
confidence interval follows from these three adjacent uncontrolled trials. A slow
sample is retained; a failure or censor is not a completed latency. CPU, memory,
physical/logical I/O, first-result timing and time-varying load are unavailable,
not zero. No resource default or numerical superiority claim follows.

## Reproduction and results

With lawful local corpus/evidence access, the actual driver command was:

```console
python scripts/measure_single_read.py --run-root .local/parallel-wave-20261015/benchmark61
```

The retained completed run root now refuses another invocation because its
capture directory already exists. Reproduce into a **fresh private run root**:

1. Build the pinned source revision in a separate target directory and verify its
   source bytes; record executable, lockfile and toolchain identities privately.
2. Prepare three #0060 configurations using its
   [versioned configuration shape](read-collector/record.schema.json), the same
   admitted input/oracle/evidence bindings and fixed budgets above. Only the
   declared trial index differs. Name them `trial-1.config.private.json` through
   `trial-3.config.private.json` and SHA-256 each complete file.
3. Write `protocol.private.json` using the
   [public fixed-protocol template](single-read/protocol.v1.json): schemaVersion 1,
   trialCount 3, interTrialDelaySeconds 5, runnerSha256, collectorSha256 and
   `trials` entries containing each `config` filename, its `sha256`, and a fresh
   `trial-N.record.private.json` destination. Pin those hashes before any attempt;
   retain build/environment evidence with their manifest/hash bindings and publish
   the sanitized protocol first. Preserve its exact bytes privately as
   `public-protocol-as-fixed.private.json`, with `publicProtocolPath` and
   `publicProtocolSha256` binding that preregistration. Prefer UTF-8/LF at creation
   so publication requires no line-ending transformation.
4. Invoke the command above with that fresh root. Retain all configurations,
   records, capture manifest and bounded private output pairs. Audit the completed
   run with the independent verifier and report unsuccessful attempts as well as
   success-conditional statistics. A new run has its own identities and results;
   never replace the retained original records or reuse their claimed results.

Paths, media, identifying metadata, per-image hashes and
raw logs remain private. Public evidence contains derived numeric samples and
scope only. The fixed protocol above was written and hashed before collection;
the results below were added afterward.

## Observed results

All **99 attempts**, including nine warmups, passed exact oracle comparison and
the source/executable stability checks. All 90 measured opportunities were
eligible: zero launch errors, nonzero exits, malformed/mismatching results,
timeouts, output-limit stops or invalid measurements were observed. These zero
counts describe this run, not a failure-rate guarantee. The public
[derived sample ledger and statistics](single-read/results.v1.json) retains every
ordered attempt, including warmups and its eligibility flag.

Actual stdout sizes were 61194 or 61199 bytes with zero stderr bytes. Independent
inspection attributes that size difference only to invocation-ID width; the
normalized metadata envelope remains identical. No successful output hit the
capture bound or required truncation.

| Samples | n | Minimum ms | Median ms | Descriptive p95 ms | Maximum ms | Mean ms | Sample SD ms |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Trial 1 | 30 | 8.4573 | 10.2050 | 11.2895 | 11.3142 | 10.2727 | 0.5587 |
| Trial 2 | 30 | 8.8787 | 9.9715 | 10.4607 | 10.5798 | 9.9393 | 0.4124 |
| Trial 3 | 30 | 8.7452 | 9.8482 | 10.9490 | 11.7465 | 9.9347 | 0.5525 |
| Pooled, same stratum | 90 | 8.4573 | 10.0131 | 10.9693 | 11.7465 | 10.0489 | 0.5310 |

Pooled median absolute deviation is **0.27165 ms** and sample CV is **5.284%**.
The three trial medians span **0.35685 ms**. First-ten to last-ten measured-window
median changes were **+0.2868 ms**, **−0.39965 ms** and **+0.2262 ms**, respectively;
every window retained ten eligible attempts. The alternating direction and the
uncontrolled host conditions prevent attributing these changes to the reader,
thermal state, device activity or any particular source of noise.

The first declared warmup took **148.577 ms**; it remains in the published ledger
and is excluded from measured distributions by the predeclared phase rule. Its
cause is unproven. No inspection after seeing this value extended warmup or
removed an additional attempt. Other warmups and all timing samples remain in
their original order.

Allowlisted CPU-load snapshots changed from 3% before to 7% after, and process
counts from 465 to 466. These snapshots are not a time-varying load trace or proof
of idle measurement. Free space also changed while other host work remained
allowed. The reported times include ordinary process startup and this Python
consumer's overhead; there is no separate parser-only or cached-page timing.

The [independent auditor](../../scripts/audit_read_baseline.py) imports neither
collector nor capture-runner code. It recomputes statistics and checks all retained
outputs against the prior oracle with type-sensitive JSON comparison, in addition
to validating fixture/tool/configuration/protocol and output identities. Public
results contain no captured metadata or per-image/output identities. Their
descriptive precision preserves the samples; it does not establish an accuracy
or stability guarantee to that many decimal places.

The seven [portable audit tests](../../scripts/test_read_baseline.py) cover exact
statistics, empty/single-sample behavior, capture corruption, JSON type changes,
duplicate/malformed output, unsuccessful/censored eligibility and preservation of
existing audit destinations. They use authored
data and invented durations, not corpus captures. All three actual private trial
records also validate against the accepted #0060 schema.

Controlled OS/device-cold measurements remain unavailable for the reasons in the
protocol. Other fixtures, selected-field views, preview/batch/session/write timing,
physical/logical I/O, CPU/memory telemetry, comparison uncertainty across machines
and performance/default-policy decisions remain unrun. This completes the bounded
single-file observation; it enables no broader capability or mutation/storage
profile.
