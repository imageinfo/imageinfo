# Collector overhead and repeatability (#0150)

The fixed experiment compares elapsed-only collection with the existing opt-in
10 ms direct-process telemetry on one authored structural CR3 metadata read.
Both arms use the same frozen executable, `metadata read --values all --output
json --max-bytes 8388608`, input, environment, concurrently drained bounded
stdout/stderr pipes, expected full JSON envelope and output verification.
Only attaching the existing telemetry observer differs. This measures the
elapsed effect of that collector configuration, including scheduling noise.

`scripts/measure_collector_overhead_150.py` prepares an exclusive private run
directory, authored fixture, independent published-snapshot oracle, SHA-256
bindings and complete preregistered order before collection. Three rounds each
contain three warmup pairs and thirty measured pairs: 198 total attempts,
18 warmups and 180 measured attempts. Every pair executes both arms; first-arm
order alternates and reverses in the next round. Each measured round has fifteen
elapsed-first and fifteen telemetry-first pairs. There are no adaptive retries,
trims or stops based on observed timings. Interrupted campaigns retain attempts
and an aborted record and fail the complete-campaign audit.

The exact required frozen inventory includes the executable, generated fixture,
all imported experiment/oracle/auditor tools, the published oracle, fixture helper
and Rust/Cargo/toolchain/configuration build inputs. Preparation requires the
current full Git HEAD; collection and audit recheck it alongside the actual source
file inventory and hashes (which also bind any uncommitted source). An incomplete
inventory refuses. Audit precedes the parent's final integration commit; the public
report retains that frozen source identity rather than relabeling the measurement.

`scripts/audit_collector_overhead_150.py` independently checks the fixed order,
stopping denominator, every retained per-attempt record, stdout/stderr hashes,
full authored JSON correctness, telemetry consistency and frozen bindings. It
reports each round/arm's planned, attempted, missing, failed and censored counts;
success-conditional median, median absolute deviation, nearest-rank descriptive
p95, sample standard deviation divided by mean (CV), and last-ten minus first-ten
median drift. Complete valid pairs supply telemetry-minus-elapsed differences
with the same descriptive summaries. CV is omitted for signed differences.
Drift is omitted when the ordered measured series has missing/invalid values.
Failed/censored attempts are retained, never imputed as zero. No overhead is
subtracted from another measurement and the unadopted #0064 rule is no gate.

The actual campaign followed the final executable freeze in one serialized timed
slot. Preparation was outside measurement. Source hashes expose the OS cache;
each process is fresh, while OS/device caches, background work, scanners, power
conditions and physical storage topology remain uncontrolled. The protocol
records these limits. Measurements describe this host, build and tiny authored
read; they are neither a camera baseline nor a version regression, zero-overhead
proof, cross-host confidence interval, resource policy or user deadline.

Run the authored controls with:

```powershell
python -m unittest discover -s scripts -p test_collector_overhead_150.py
```

## Actual authored observations

The fixed protocol and complete descriptive results are in
[results.v1.json](collector-overhead/results.v1.json). The campaign was fixed at
2026-10-17T16:07:24.694056Z against source commit
`61e6e8b719c35d9fc48412f6702faea7f14ea618` and executable SHA-256
`6da5f13d712fa075b8dd77f705dc36725212f226f16c32cf1d6a0814993ee20e`.
The JSON binds the authored fixture and experiment tools. Full verification of
910 tracked files and both frozen binaries passed before and after collection.

All 198 planned attempts were retained: 18 warmups and 180 measured attempts,
forming 90 measured pairs. All output was correct and all 99 telemetry attempts
were valid. Every measured round/arm retained 30/30 attempts; failed, censored and
missing counts were zero, and no measured pair was excluded. The single campaign
and audit had no retries or replacements. A fresh independent reviewer checked
retained output, exact order/stopping and explicit arithmetic for every reported
statistic. Raw captures remain private; the public report contains authored
observations and sanitized protocol fields only.

Windows 11 build 26200, the same local volume and the inherited host power state
were used throughout. Physical storage topology, background load and OS/device
caches remained uncontrolled. Each invocation used a fresh application process
and identical 4 MiB/channel capture bounds, 4096-byte pipe draining and 30-second
deadline. These are measured collection conditions, not selected product limits.

Round numbers below are one-based. Times are milliseconds; CV is a percentage.
Drift is the last-ten minus first-ten median within that ordered measured arm.

| Round | Arm | Median | MAD | Descriptive p95 | CV | Drift |
|---|---|---:|---:|---:|---:|---:|
| 1 | Elapsed only | 9.48905 | 0.29220 | 13.23900 | 13.5204% | -0.20125 |
| 1 | Telemetry | 9.44315 | 0.31020 | 10.97110 | 9.5973% | -0.34430 |
| 2 | Elapsed only | 9.68950 | 0.34945 | 11.14930 | 11.9021% | -0.12085 |
| 2 | Telemetry | 9.55225 | 0.25870 | 13.98090 | 13.6132% | -0.16390 |
| 3 | Elapsed only | 9.17640 | 0.46330 | 10.61260 | 11.3735% | -0.18305 |
| 3 | Telemetry | 9.44455 | 0.27855 | 14.01570 | 14.6332% | 0.10215 |

Each following row contains 30 adjacent telemetry-minus-elapsed differences.
The paired median is calculated from those differences; it is not the difference
between marginal arm medians. Signed differences have no reported CV.

| Round | Paired median | Paired MAD | Descriptive p95 | Paired drift |
|---|---:|---:|---:|---:|
| 1 | 0.11640 | 0.54210 | 1.82950 | 0.02615 |
| 2 | 0.12630 | 0.65800 | 4.30090 | -0.01915 |
| 3 | 0.46200 | 0.78975 | 4.83240 | 0.57950 |

Paired dispersion exceeds the paired median in each round. The observed
instrumentation effect therefore remains mixed with substantial noise on this
tiny read. These observations do not establish stable or zero overhead; no
assumed overhead was subtracted, historical builds pooled or release policy
threshold applied.
