# Bounded JSON and JSONL output consumers

Work under **#0147**, recipe `output-consumers-v1`. The
[collector](../../scripts/output_consumers.py),
[independent auditor](../../scripts/audit_output_consumers.py) and
[authored controls](../../scripts/test_output_consumers.py) measure the existing
ordinary JSON and session JSONL transports. The experiment uses public authored
structural bytes from the existing Rust test fixture. It reads no camera media.

The timed campaign is pending the final frozen executable and a serialized
measurement slot. Preparation and authored collector controls establish the
measurement mechanism, not measured imageinfo timings or a resource policy.

## Fixed workload and oracle

The ordinary command is `metadata read --output=json --values all -- authored.cr3`.
The session receives one v1 `read` with ID `r147`, the same token array without
`--output`, and a `close` with ID `done147`, followed by input EOF. Expected session
order is ready, one complete read-result, then session-complete. No request queue,
CSV projection, pager or terminal rendering is measured.

The oracle reconstructs the entire expected output from the existing public
[authored snapshot](../legacy-compatibility/native-read-json/example.v1.json),
independently specified request/file/summary envelopes and exact session limits.
It does not capture one run as the expected result for later runs. Ordinary CLI
IDs must match the native numeric invocation shape; the observed ID is inserted
only into its four request-ID fields and snapshot ID. Every remaining byte,
including escaping, key order, source paths, values, coverage and newline framing,
must match the independent reconstruction. Session IDs and frame order are exact.
Existing native/result/session schemas and native semantic checks also run.
Both expected complete outputs must fit 262144 bytes before the campaign starts.

## Consumers, timing and supervision

Each transport has two warmups and ten retained samples for each consumer:

- Fast: unbuffered binary OS-pipe reads requesting at most 1024 bytes each.
- Slow: the same reads, with at least 5 ms between successive read starts. Slow
  processing is intentional harness delay. A read itself may block, and scheduler
  delay can lengthen its interval. All actual start/end offsets and returned sizes
  are retained; there is no buffered reader or hidden downstream drain queue.
- Close control: once per transport, the pipe reader is closed before child spawn.
  Actual exit, diagnostics and counters are retained. No final result or terminal
  frame is promised after a failed stdout write.

The stopwatch starts immediately before pipe/process setup. First-byte latency is
the return of the first nonempty read. First-usable latency is the read returning
the complete ordinary envelope or session read-result, including its LF. Session
ready is not counted as a usable metadata result. Framing timestamps are accepted
as usable only after the independent whole-output audit succeeds. Delivery
completion is stdout EOF observed by the consumer; direct-process exit is the
first poll observing exit. Those events can occur in either order. Elapsed time
includes process launch, observer setup/sampling, consumer waits and final drains.
No harness cost or intentional delay is subtracted.

A 30-second research watchdog supervises both process execution and pipe delivery.
It kills the owned direct child on a live-child timeout; this adds no product
deadline or cancellation capability. Stdout capture is bounded to 262144 bytes,
stderr to 8192 bytes, input to 2048 bytes, and stdout read events to 4096. Overflow,
launch failure, timeout, cancellation, broken output and consumer errors remain
retained with their captured prefixes and explicit outcomes. Records are saved
after every attempted cell; an interrupted/incomplete campaign fails the complete
denominator audit rather than silently discarding failed attempts.

Resources reuse the unchanged [direct-process telemetry helper](read-telemetry.md)
at a requested 10 ms interval. The existing independent telemetry arithmetic
auditor checks counters, sample brackets, availability and maxima. Logical process
I/O is not physical traffic; sampled membership is not process-tree containment.
Unavailable fields stay unavailable. Cache state and concurrent host load must be
declared; output-consumer timing cannot select resource defaults by itself.

## Reproduction

Use the repository's test-only `jsonschema==4.26.0` dependency and the pinned Rust
toolchain. First prepare a fresh ignored fixture directory, then wait for the
frozen executable and serialized measurement slot:

```console
python scripts/output_consumers.py --prepare FRESH_PRIVATE_FIXTURE_DIR
python -m unittest discover -s scripts -p test_output_consumers.py
python scripts/output_consumers.py --binary FROZEN_IMAGEINFO --fixture-dir PRIVATE_FIXTURE_DIR --output FRESH_PRIVATE_RECORD_DIR --environment PRIVATE_ENVIRONMENT_JSON --source-revision FROZEN_COMMIT --source-freeze-sha256 FROZEN_SOURCE_MANIFEST_HASH
python scripts/audit_output_consumers.py PRIVATE_RECORD_DIR/record.json --binary FROZEN_IMAGEINFO --fixture-dir PRIVATE_FIXTURE_DIR --source-revision FROZEN_COMMIT --source-freeze-sha256 FROZEN_SOURCE_MANIFEST_HASH
```

The environment file is a bounded nonempty JSON object recording hardware,
storage, power, cache and load facts or their explicit unknowns. Binary, fixture,
collector, telemetry helper and public oracle hashes bind the record. Source and
binary hashes are rechecked after each attempt. The auditor requires independently
supplied executable/fixture paths, source revision and source-freeze manifest hash;
it compares current retained executable/fixture bytes and all six tool/oracle
bindings. These bindings detect mismatched artifacts; they do not authenticate an
edited record or prove that an executable was built from a clean revision. Exact
invocation, cwd, input bytes, process launch/exit endpoints and the 10 ms telemetry
schedule are audited. Close controls retain actual zero/nonzero, launch-error,
timeout or other supported outcomes; only an observed status-1 output-incomplete
diagnostic is counted as an output failure. Unknown outcomes and contradictory
endpoints refuse audit. A complete campaign retains 48
warmup/sample attempts plus two consumer-close controls. Warmups and close controls
are never eligible samples. A sample requires complete exact output, exit zero,
empty stderr, unchanged identities and valid direct-process telemetry.

Slow total delivery includes the declared consumer schedule. A longer elapsed
time alone does not measure blocked-writer duration or establish pipe saturation.
The recipe does not instrument writer wait states or kernel pipe capacity, so
any backpressure attribution remains unproven. Product pipe writes can wait
indefinitely when a reader stops; the research watchdog supplies no final-frame,
buffer, spill, deadline or terminal-rendering guarantee for the product.
