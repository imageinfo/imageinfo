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

Collection must follow the parent's final executable freeze and serialized timed
slot. Preparation is outside measurement. Source hashes expose the OS cache;
each process is fresh, while OS/device caches, background work, scanners, power
conditions and physical storage topology remain uncontrolled. The protocol
records these limits. Measurements describe this host, build and tiny authored
read; they are neither a camera baseline nor a version regression, zero-overhead
proof, cross-host confidence interval, resource policy or user deadline.

Run the authored controls with:

```powershell
python -m unittest discover -s scripts -p test_collector_overhead_150.py
```

Exact measured protocol/results are added after the authorized frozen campaign.
