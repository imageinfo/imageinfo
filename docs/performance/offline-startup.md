# Offline help and version startup (#0143)

This finite protocol measures five existing offline invocations with no media
operands. It does not execute a metadata read, initialize a persistent session,
discover tags/formats, or perform a network workload. Unsupported discovery
operations remain explicit unrun matrix cells.

| Case | Exact tokens after the frozen executable | Warmups | Measured |
|---|---|---:|---:|
| Root help | `help` | 3 | 10 |
| Metadata-read leaf help | `metadata read help` | 3 | 10 |
| Session-read leaf help | `session read help` | 3 | 10 |
| Version text | `--version` | 3 | 10 |
| Version JSON | `--version --output json` | 3 | 10 |
| Format discovery | Unsupported; unrun | 0 | 0 |
| Tag discovery | Unsupported; unrun | 0 | 0 |

The order is case-major as displayed: three warmups immediately followed by ten
measured attempts for each case, totaling 65 fresh processes. There are no retries,
trimming, replacement samples, timing-dependent stopping decisions, or invented
discovery commands. Failures, unavailable counters, censoring and interruptions
remain in the denominator. A cancelled or interrupted campaign retains its partial
record; it cannot satisfy the complete-campaign audit.

## Boundaries and retained evidence

`scripts/measure_offline_startup.py` reuses the existing bounded
`read_benchmark.run_process` and Windows `read_telemetry.Observer` without changing
those shared implementations. An adapter uses each buffered pipe's `read1(4096)`
to return available bytes instead of waiting for a full 4096-byte read. Separate
threads drain stdout and stderr with a 1 MiB bound per channel and a 10-second
attempt deadline. Stdin is closed through `DEVNULL`; no shell is invoked.

All elapsed endpoints use `perf_counter_ns` offsets from immediately before
`Popen`. These are observer timestamps, including Python scheduling, process launch,
pipe capture and instrumentation overhead; no overhead is subtracted.

- `firstStdoutByteNs` and `firstStderrByteNs` record when the consumer receives its
  first nonempty block on each channel. `firstByteNs` is the earlier available
  value. A channel producing no bytes has no first-byte value. This is not a
  kernel write timestamp or a usable metadata result.
- `stdoutEofNs` and `stderrEofNs` record observed EOF independently.
  `completeOutputNs` is their maximum only when both EOFs were observed. An EOF
  after forced termination does not make a censored output successful.
- `exitObservedNs` records the observer entry immediately after the shared runner
  has returned from `Popen.wait`, before the final native-counter sample. It is
  an upper bound on exit observation, not the kernel's exact exit time.
- `completeOutputExitNs` is the maximum of both EOF observations and exit
  observation. The shared `elapsedNs` additionally includes final telemetry and
  drain joins; it is retained separately as collector completion.

The first native counter snapshot is taken after launch and before drain threads
start. Sampling and scheduling may therefore delay the first-byte observation.
The output/exit endpoint excludes the final counter call when both pipes have
already ended, while the shared collector-completion endpoint includes it.

The existing 10 ms telemetry samples the direct Popen-owned Windows process
handle. CPU and logical-I/O counters, sampled working set/private commit and the
OS lifetime working-set high-water mark retain their existing definitions and
explicit API errors. Sampling may miss memory peaks; post-exit memory reads may
be unavailable. Immediate-child snapshots are observation, not continuous process
containment. Neither logical process transfer counts nor pipe byte counts measure
physical-device I/O. See [read-telemetry.md](read-telemetry.md) and
[collector-overhead.md](collector-overhead.md).

Preparation creates a fresh private directory, copies and binds every expected
stdout/stderr byte and exit status, and writes the fixed schedule before any
campaign attempt. The frozen inventory binds the executable, Python executable,
collector, auditor, controls, shared collector/counter/audit modules, this method,
and every file under production `src`/`crates` (except `target` directories),
including embedded JSON/byte inputs, plus Cargo/toolchain/configuration inputs.
Exact Git HEAD and source
inventory are checked before and after collection. Hashing warms OS caches;
working-tree hashes supplement the commit identity. Changed/missing bindings
refuse collection or invalidate completion.

The [oracle manifest](offline-startup/oracle/manifest.json) names exact stdout and
stderr snapshots of independently invoked, source-reviewed current CLI output.
It is a snapshot of this implementation, not an external compatibility oracle.
Help text/options/usage and version fields are checked against the current source;
the measured collector never generates its own oracle from measured output.

Each attempt retains its complete bounded stdout/stderr, hashes/byte counts,
status, timing endpoints, telemetry, fixed schedule position and separate attempt
record. Exact output comparison and record serialization occur after timing.
The independent auditor checks output identity, statuses, timestamp consistency,
counter consistency, tool/source identities and all 65 planned attempts. Output
correctness and counter availability are reported separately; failed/unavailable
resource evidence is never relabeled zero or repaired from an earlier sample.

## Execution and interpretation

First run the authored controls:

```powershell
python -m unittest discover -s scripts -p test_offline_startup.py
```

After source/executable review and freeze, prepare a fresh `.local` directory:

```powershell
python scripts/measure_offline_startup.py --run-root .local/offline-startup-143 --prepare-binary PATH_TO_FROZEN_EXE --source-revision EXACT_HEAD --expected-root docs/performance/offline-startup/oracle
```

Only in the parent-assigned exclusive timing slot, with VM and other timed
campaigns stopped, run collection and then the independent auditor:

```powershell
python scripts/measure_offline_startup.py --run-root .local/offline-startup-143
python scripts/audit_offline_startup.py --run-root .local/offline-startup-143
```

This preparation is not a measured baseline. Actual campaign results require
the frozen protocol, all retained attempts and independent audit. No campaign
has been run by this preparation step.

Each process is fresh; OS/device caches, background work, scanners, power state
and physical storage topology are uncontrolled. These observations can describe
this build/host and these tiny offline outputs. They do not establish cold-start
latency, a media/network workload, metadata-result latency, a regression threshold,
cross-host performance, resource defaults or release deadlines.
