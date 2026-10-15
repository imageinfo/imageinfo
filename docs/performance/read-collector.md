# Bounded metadata-read collector

Implemented under **#0060**, observed **2026-10-15**, recipe `read-collector-v1`.
This is collector qualification for the current single-file EOS R5 full RAW
metadata read. It does not complete the measurement workloads on #0061–0063,
choose performance defaults, or establish a numerical speed or parity claim.

[Collector source](../../scripts/read_benchmark.py),
[record schema v1](read-collector/record.schema.json),
[synthetic contract vector](read-collector/synthetic-record.v1.json), and
[QA tests](../../scripts/test_read_benchmark.py) implement a bounded part of the
[measurement protocol](measurement.md). The vector's durations/hashes are invented
schema examples. [Qualification evidence](read-collector/qualification.v1.json)
is a separate sanitized derivation of an actual invocation.

## Reproduction and input admission

Run from the repository root, with a **fresh** private record destination:

```console
python scripts/read_benchmark.py --config .local/batch-ten-20261015/benchmark60/config.private.json --output .local/batch-ten-20261015/benchmark60/record-qualified.private.json
```

The first command is the actual qualification recipe; the private configuration
requires local corpus permission and is not distributed. Repeating it requires a
fresh output name. QA uses `jsonschema` 4.26.0, a test-only dependency already used
by project output-schema QA; the collector uses only the Python standard library.
The actual PowerShell QA invocation used an isolated ignored QA package directory:

```powershell
$env:PYTHONPATH = (Resolve-Path .local/benchmark60-qa).Path
python scripts/test_read_benchmark.py
```

On a fresh checkout, provide `jsonschema==4.26.0` in the test interpreter first;
the ignored package directory itself is not distributed.
Do not install a runtime dependency or open private media in public CI.

A configuration has exactly the fields in the schema's `configuration` property.
`binary`, `input`, and `oracle` are absolute paths with corresponding
`binarySha256`, `inputSha256`, and `oracleSha256` identities. `fixtureId`,
`admissionEvidence`, and `correctnessEvidence` bind the fixture manifest and prior
differential experiment. `environment` declares allowlisted hardware/storage,
power, locale, scanner and load facts; unknowns need reasons. `repeats`, `warmups`,
`timeoutMs`, `captureBytes`, and `maxBytes` declare the finite collection budget.

The collector checks #0013 admission, analysis permission, full RAW CR3 mode and
matching fixture hash. The #0020 passing read experiment must bind the same fixture
and exact prior native stdout hash. These are caller-trusted local evidence records,
not authentication of arbitrary imported JSON or new corpus admission authority.
See the [corpus/fixture contract](../fixture-plan/README.md) and
[reader validation](../reader/validation.md). The qualification used the existing
reviewed oracle rather than generating a new expected result from the tested tool.

## What one attempt means

Each attempt starts one direct executable with this token array:

```text
[binary, "metadata", "read", "--values", "all", "--output", "json",
 "--max-bytes", maxBytes-as-decimal, "--", input]
```

One attempt means **one ordinary process and one explicit file**, with the entire
currently supported metadata subset, all value views, partial coverage and the
existing read guards. It includes startup, metadata I/O, JSON serialization,
two pipe drains and process exit. It includes no preview extraction, batch,
persistent session, ExifTool comparison timing or RAW pixel development. The
current executable has no child processes; this collector is not suitable for
launchers or tools that spawn descendants.

`time.perf_counter_ns` measures integer nanoseconds from immediately before
`Popen` until direct process exit and pipe-drain completion. UTC start timestamps,
clock resolution and the boundary are recorded separately. First-result latency,
CPU, memory, logical/physical I/O, queue depth and scratch telemetry are unavailable
with explicit nulls/reasons. Their absence is not a zero-cost observation. The
collector does not subtract polling, thread or measurement overhead.

Both stdout and stderr are drained concurrently in 4096-byte chunks, retaining
at most `captureBytes` **per pipe**. The record reports received byte counts,
retained byte counts and SHA-256 of the retained bytes. Hashes after truncation
are prefix evidence, never full-output identities. JSON decoding, comparison and
before/after source hashing occur outside the timed interval. The consumer is
bounded in-memory capture, not a terminal, discard sink or deliberately slow
consumer; no first-byte/backpressure series is measured.

Success requires exit 0, empty stderr, one read result, complete selection/output,
no interruption/artifacts/source effects and explicitly partial coverage. The
whole decoded envelope must equal the linked oracle after rebinding only request
IDs, their snapshot-ID prefix, file path and source display path. Tag identities,
occurrence order, stored exact values, displays, ranges, producer revisions,
issues and coverage remain compared. This repeats the declared #0020 correctness
closure; it is not a new independent decoder or wider ExifTool parity result.

## Bounds, failures and cache scope

Bounds are 1–100 measured repeats, 0–10 retained warmups, 1–60000 ms deadline,
1 byte–4 MiB retained bytes per pipe, and the native 1 byte–256 MiB metadata-read budget.
These are collector safety bounds, not selected product performance policy.
Order is fixed: declared warmups followed by all repeats; there is no adaptive
stopping or outlier removal. No aggregates are produced by this increment.

Every attempted process is retained, including launch errors, nonzero exits,
malformed/mismatching outputs, timeouts and output-limit stops. Warmups cannot be
eligible samples. Timeout/output-limit/consumer-error durations are censored
elapsed-at-stop observations, not completion latencies. Complete exits failing
correctness remain in the ledger and are ineligible. The collector kills the
direct process at its supervised deadline or capture overflow. It does not promise
an OS hard memory cap, process-tree containment, immediate cancellation of blocked
kernel I/O or a hard wall-clock bound around OS process creation/termination.

Preflight hash reads can warm the OS cache. Application state is fresh per process;
OS/device/server caches are uncontrolled or unknown. No cache eviction, workstation
policy change or fabricated cold-cache label is used. Source SHA-256, length and
mtime and executable SHA-256 are checked across collection. A changed source or
binary invalidates the record and every sample. These ordinary checks do not
exclude hostile same-byte replacement or supply continuous source locks.

Output creation is exclusive and existing destinations refuse before attempts,
including aliases of corpus inputs. A name inserted after preflight is not
overwritten. Unexpected collector/filesystem exceptions can prevent final record
creation; this increment has no crash-resilient journal and must not be reported
as a complete experiment if its private record was not written.

## Evidence and remaining cells

The private record pins executable, driver, Python interpreter, oracle, fixture
and evidence hashes; exact argv/cwd, allowlisted process environment, OS/build,
configuration and all per-attempt samples remain private. Hardware/storage facts
are caller declarations or explicit unknowns. Interpreter hash/version do not pin
every OS runtime library. The public qualification record excludes private paths,
media, identifying values, per-image hashes and raw stdout/stderr.

Qualification verifies the actual native invocation and the finite timeout,
nonzero/invalid-output, launch-error and overflow mechanisms. Schema QA validates
the positive vector and rejects wrong revisions, missing fields, fabricated zero
telemetry, unbounded budgets, negative durations and contradictory eligibility or
censoring. The schema checks record shape and selected local invariants; hash
truth, evidence trust, sample ordering/count agreement and timing authenticity
still depend on collector execution and review.

The [single-file baseline](single-read-baseline.md) now records #0061's bounded
distributions and explicit environment/noise limits;
preview collection and scaling workloads remain #0062/#0063. Comparison,
regression thresholds, memory/CPU/I/O instrumentation and resource-policy selection
remain unrun here. No production reader behavior or mutation/profile gate changes.
