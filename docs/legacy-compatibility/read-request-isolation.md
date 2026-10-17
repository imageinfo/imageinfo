# Independent read callers (#0135)

`tests/read_request_isolation.rs` qualifies a finite concurrent use of the
existing production `read_request` and caller-owned `read_session` library APIs.
It adds no executor, parser settings, queue or global configuration. Fixtures
are authored CR3 structural bytes from the existing test support; they contain
no camera photographs. No process-wide current directory or environment is
changed by the test.

## Actual calls and independent expectations

One test creates twelve distinct absolute input paths with per-input firmware
strings and starts twelve Rust threads. Each thread makes two sequential direct
read calls and one session containing one read. Thus at most twelve callers can
be executing these APIs at once. The caller-owned session writers rendezvous
inside the actual `run` calls at ready-frame flush and again at read-result
flush. The test asserts all twelve arrivals at both phases. At the second phase
every session retains its actual read-result record and its session ID set.
This establishes overlapping API lifetimes with live request state even under a
schedule that serializes all other work. It does not claim simultaneous parser
or filesystem instructions. No shared source is changed while the threads run.

Each rendezvous has a ten-second wait deadline and propagates timeout/abort to
late arrivals. A worker failure before a rendezvous therefore fails the test
without an indefinite barrier wait. Every worker is joined before propagating
failures or cleaning fixtures. A separate missing-participant control exercises
timeout and late-arrival refusal with a twenty-millisecond deadline; it calls no
production API and adds no concurrent read caller.

The first direct call and the session read repeat six cases twice:

| Case | Selected setting | Independently asserted outcome |
| --- | --- | --- |
| Firmware/raw | `CanonFirmwareVersion`, raw | Exact caller-specific string; one occurrence; display unavailable |
| Exposure/all | `EXIF:ExposureTime`, all | Exact stored rational `2/500`; one occurrence; display present |
| Width/normalized | `EXIF:ImageWidth`, normalized | Exact integer `8192`; one occurrence; display unavailable |
| Firmware/display | `CanonFirmwareVersion`, display | Exact caller-specific string; one occurrence; display present |
| Small budget | `--max-bytes 16` | File failure, no snapshot, `LIMIT_EXCEEDED`, status 1 |
| Excess API budget | `--max-bytes 8388609` | No files, `REQUEST_LIMIT`, status 2 |

Expected values and states are literals derived from authored fixture inputs,
not captured serial output. Direct successes also assert the selected path,
request/input/snapshot IDs, raw/normalized equality and no mutation effects.
Every thread then makes a default-view firmware read, including after both
failure forms, and asserts its own exact value and unavailable display. This
checks that a caller's selectors, display setting, budgets and errors do not
become the next call's settings. Session reads use the same ID in all twelve
independent sessions and assert their own input/value/error outcome. Each session
success independently asserts the exact selected tag, raw and normalized present
states/values and expected display present/unavailable state. Synthetic controls
first pass this oracle, then require it to reject a forced-raw display state and
a wrong selected tag. No session ID registry or setting crosses caller-owned
sessions.

## Ownership and failure observations

Each thread retains its first result during later calls, injects a broken-pipe
error into its own `write_result` sink, re-enables that same sink and successfully
serializes the retained result. All result envelopes are returned through thread
join; the parent test reads their independent values after worker exit.

The session checks use separate caller-owned readers and writers per thread:

- A read followed by close leaves its exact caller-specific trailing bytes
  available and the writer usable.
- A protocol error leaves bytes after that frame available and the writer usable.
- An injected input error leaves the input object recoverable after its failure
  flag is cleared, with its exact bytes and writable output still owned by the caller.
- An initial output error returns `BrokenPipe`, consumes no input and leaves both
  caller objects usable after the injected sink failure is cleared.

These are actual Rust stream calls, not process pipes, cancellation or deadline
tests. The test confirms source bytes and last-write timestamps are unchanged
and the fixture directory has exactly its twelve original files before the
deliberate later edit.

## Same-path observations and limits

After all threads join, the caller deliberately writes a new firmware value at
one existing input path. A new read observes that value while the earlier owned
snapshot retains the original value. A completed read grants no continuous
source or name guard, no authority for a later write and no object-identity proof.
This sequential authored edit is not a concurrent-write qualification.

The finite twelve-thread exercise does not prove arbitrary scheduling, a hard
resource quota, lock freedom, throughput, shared-stream safety, request queues,
process-global environment isolation under hostile caller changes, parallel
writes, storage-profile admission or RAW mutation. Broader public API ownership
coverage belongs to #0134; session schema/framing profiles belong to #0128.

Run the qualification with:

```text
cargo test --test read_request_isolation
```

Independent concurrency review and the parent integration/hosted checks remain
required before handoff.
