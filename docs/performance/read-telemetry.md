# Direct-process read telemetry v2

Implemented under **#0142**, observed **2026-10-16**, recipe `read-telemetry-v2`.
This extends the [elapsed collector](read-collector.md) with a separately selected
Windows counter companion. It qualifies the collection mechanism on authored child
processes, not a camera benchmark or a resource-policy recommendation. The original
[record schema](read-collector/record.schema.json), original examples and historical
evidence remain unchanged; omitting the new option still emits elapsed-only v1.

[Collector](../../scripts/read_benchmark.py),
[counter helper](../../scripts/read_telemetry.py),
[v2 schema](read-telemetry/record.v2.schema.json),
[invented contract example](read-telemetry/synthetic-record.v2.json),
[independent arithmetic auditor](../../scripts/audit_read_telemetry.py), and
[authored tests](../../scripts/test_read_telemetry.py) supply this increment.
The example contains invented durations, counters and identities; it is not a run.
[Qualification summary](read-telemetry/qualification.v2.json) records the actual
finite authored qualification without distributing private local paths or records.

## Selection and record boundary

Use an already authorized, admitted fixture and correctness oracle under the
unchanged v1 admission rules, with a fresh private output name:

```console
python scripts/read_benchmark.py --config PRIVATE_CONFIG --output FRESH_PRIVATE_RECORD --telemetry-interval-ms 10
python scripts/audit_read_telemetry.py FRESH_PRIVATE_RECORD
```

This is a recipe, not a request to run private media. No private media was read for
#0142. No new fixture, publication or derivative authority follows from telemetry.
The top-level v2 envelope binds the telemetry helper hash, counter units/methods,
scope, timing alignment, overhead policy, and one telemetry entry per actual attempt.
Its `elapsedRecord` retains the admission/configuration/correctness/capture fields
of v1, with its own explicit v2 revision and two added termination outcomes.
Its historical null fields describe that elapsed-only core; resource observations
and their availability reasons live in the companion. The outer `purpose` separates
ordinary `metadata-read` from `authored-child-qualification` wrappers. Authored QA
wrappers use an explicitly synthetic fixture/oracle configuration, retain actual
child argv and observed attempt/counter data, and never claim media admission or
eligible samples. Hashes do not authenticate imported records or establish a trust
boundary against an editor of the collector or JSON.

Only the Windows direct process launched by `Popen` is measured. The helper borrows
CPython's retained process handle through direct exit; it never closes that handle.
It owns and closes each Toolhelp process snapshot. Typed `ctypes` structures and
function signatures use the Python standard library. No privilege, process job,
root Rust API, unsafe policy or root SDK boundary is added. Other platforms retain
the attempt with unavailable telemetry and an explicit setup reason. Cross-platform
counter equivalence is unqualified.

## Counter meanings

| Fields | Unit and scope |
| --- | --- |
| `userCpuNs`, `systemCpuNs` | Cumulative direct-process thread user/kernel time, native 100 ns units converted to integer ns. CPU time can exceed elapsed wall time across threads. |
| `workingSetBytes` | Current resident working set, including shared pages. |
| `privateCommitBytes` | Current committed private memory, not private resident memory. |
| `peakWorkingSetBytes` | OS-reported lifetime working-set high-water through the observation. |
| `readOperations`, `writeOperations`, `otherOperations` | Cumulative process I/O operations. |
| `readTransferBytes`, `writeTransferBytes`, `otherTransferBytes` | Cumulative process transfer bytes, including process I/O beyond file storage; these are not physical/device traffic. |
| `physicalIoBytes` | Always null with an unavailability reason. |

The Windows mappings follow Microsoft's
[GetProcessTimes](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getprocesstimes),
[PROCESS_MEMORY_COUNTERS_EX](https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-process_memory_counters_ex),
[GetProcessIoCounters](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getprocessiocounters)
and [IO_COUNTERS](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-io_counters)
contracts, checked 2026-10-16. A successful zero is retained as a measured zero;
failed/inaccessible groups remain null with the API's error code, never a fabricated
zero. A read exception similarly retains nulls and its reason. Earlier samples
never substitute for a failed final counter read. After exit the current working
set/private commit may collapse; the final lifetime high-water remains separately
named. `sampledMaxima` is exactly the maximum of available sampled current working
set/private commit values. It is not an allocation peak or guaranteed resident peak.

## Sampling, membership and bounds

Requested intervals are 1–1000 ms. Each observation has monotonic integer begin/end
offsets from immediately before `Popen`, aligned to the elapsed collector's
`perf_counter_ns` clock. Counter calls and membership enumeration occur sequentially
inside that bracket; values are not simultaneous. One initial observation and a
forced post-wait final observation bracket ordinary sampling. Actual begin/end
values expose jitter and query duration. Intervals are requested minimum spacing
between ordinary sample starts, not a scheduler guarantee; the final sample may
be closer. A short-lived child can have only initial/final observations. Counters
include work before the first sample, because they are lifetime counters.

`observerWallNs` sums the measured observation brackets, including membership
snapshots. It excludes helper setup and other collector work; all setup, polling,
pipe drain and observation overhead remains in elapsed wall time, with none
subtracted. #0150 retains actual overhead/noise characterization; recording this
cost does not establish that it is negligible.

Membership uses sampled Toolhelp process IDs and parent IDs via
[PROCESSENTRY32W](https://learn.microsoft.com/en-us/windows/win32/api/tlhelp32/ns-tlhelp32-processentry32w).
An observed immediate child marks membership invalid and retains its PID. A failed
or over-bound enumeration marks membership unavailable. Either makes the telemetry
ineligible. This catches authored unexpected-child cases; short-lived/reparented
processes, gaps between observations and PID reuse remain limitations. No process
name, command line or unrelated process list is retained. These observations do
not prove continuous descendant exclusion. Descendant counters are never summed,
and the collector provides no generic tree sandbox or descendant cleanup promise.
Only the direct child is killed on its supervised stop.

There are at most 2048 samples per attempt, reserving the last slot for the final
observation. Exhaustion stops the direct child with `telemetry-limit`, retains
partial counters/captures, and marks elapsed time censored. Enumeration has a
32768-entry bound. Original deadline/repeat/output-capture bounds remain in force;
stdout/stderr counts and retained-prefix hashes retain their original meanings.
No OS CPU/memory/disk quota or device instrumentation follows from these bounds.

## Failure, cancellation and qualification

Launch errors, nonzero exits, timeouts, output overflow, counter failure, unsupported
setup and invalid membership remain recorded. Counter/membership failure does not
convert successful command output into a correctness failure, but it prevents
measurement eligibility and the v2 CLI reports failure. Timeout/output-limit/
consumer-error/cancellation/sample-limit durations are censored. A caller can supply
a cancellation event to the direct-process runner; in v2, a keyboard interrupt in
the supervised polling loop also kills/waits for the child and retains `cancelled`.
Collection stops scheduling later attempts after cancellation, then performs the
ordinary source/binary checks and exclusive record write. Repeated interrupts,
collector crashes and errors outside that supervised loop can still prevent the
final write: this remains a non-journaled research collector.

QA uses the existing test-only `jsonschema==4.26.0`; runtime collection and arithmetic
audit have no third-party dependency. The qualification runs only authored children:
CPU + touched memory + temporary logical file I/O; short exit; nonzero exit;
deadline; capture overflow; explicit cancellation; unexpected child; injected
counter-read failure; injected membership failure; launch error; unavailable setup;
and an injected small sample bound. Fault injection qualifies the collector's
failure handling, not a naturally occurring permission or Windows API failure.

```powershell
$env:PYTHONPATH = (Resolve-Path .local/benchmark60-qa).Path
$env:IMAGEINFO_TELEMETRY_QA_RECORDS = 'FRESH_PRIVATE_AUTHORED_RECORD_DIRECTORY'
python scripts/test_read_telemetry.py
python scripts/test_read_benchmark.py
python scripts/check_docs.py
```

On a fresh checkout provide the pinned test-only package in the QA interpreter;
`.local/benchmark60-qa` is existing ignored test infrastructure, not distributed.
The optional retention variable requires fresh per-case paths. The independent
auditor imports no collector/counter helper. It reloads serialized records and
checks count/order, alignment, monotonic cumulative counters, failure nulls/reasons,
physical-I/O nulls, censoring, output bounds, membership validity, exact sampled
maxima, high-water relationships and observation-overhead arithmetic. JSON Schema
separately checks shape, bounds, method/unit declarations and local classifications.
Neither proves OS counter truth, historical authenticity or continuous membership.
No performance baseline, camera measurement, threshold or production behavior is
selected by this finite mechanism qualification.
