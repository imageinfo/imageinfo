# Finite metadata-read interruption contract (#0139)

Revision `2026-10-17.1` specifies the existing v1 boundary and one future,
cooperative read-only improvement. It implements no cancellation runtime. The
[#0112 library](read-session-library.md) and [#0116 process](read-session-process.md)
remain the current behavior. Mutation cancellation, publication boundaries and
safe recovery outcomes remain #0079; this contract grants none of that authority.

## Current mechanism and outcome matrix

The source baseline is [`read_session::run`](../../src/read_session.rs),
[`read_request::execute`](../../src/read_request.rs), the CLI adapter in
[`main.rs`](../../src/main.rs), and the explicit exclusion in
[`cli.rs`](../../src/cli.rs). An OS interruption is not a cancellation request.
The matrix distinguishes a specified source path from an actually qualified
native OS fault or signal. No signal campaign is claimed here.

| Mechanism / boundary | Current v1 result | Exit / return | Output completeness | Ownership / evidence |
| --- | --- | --- | --- | --- |
| Ctrl-C, SIGINT, SIGTERM, Windows console control | No installed read-session cancellation policy; host/OS behavior governs interruption or termination | No portable promised status, including 130 | No promised final frame after termination | Invoker owns process control; signal behavior unqualified |
| Caller requests API cancellation | Neither `run` nor `execute` accepts a cancellation token | No cancellation result or status exists | No cancellation completion exists | Caller owns borrowed streams; dropping a waiting caller task does not establish that synchronous work stopped |
| `BufRead::fill_buf` returns `Interrupted` | Retry, including while accumulating a partial frame; do not increment attempts again | Continue until another outcome | No error/completion solely for `Interrupted` | Actual trait-fault test `actual_short_writes_interrupted_reads_and_flush_order` |
| Input read blocks / no LF yet | Wait synchronously; no deadline or cancellation poll | No return promised while blocked | Ready may have flushed; no completion promised while waiting | Caller owns input; finite byte caps do not bound elapsed time |
| Input returns a non-`Interrupted` error | `INPUT_IO`; discard pending partial frame; stop admission | `Ok` outcome / process 1 if error and completion flush; otherwise output `Err` / 1 | Error then completion only if output succeeds | Actual trait-fault test `actual_input_faults_override_pending_truncation_and_count_only_started_frames`; native failing handles are separately #0140 |
| Input EOF | Between frames: clean EOF; pending bytes: `FRAME_TRUNCATED` | 0 / 2 if completion flushes | Completion / error plus completion | Actual #0116 pipes; closing stdin is not cancellation of an active read |
| Active metadata read blocks | Synchronous `execute` continues until underlying work returns | No hard deadline or interrupt result | No partial result emitted by the session | Runtime owns current bounded work; caller has no asynchronous abort API |
| Output blocks / slow live consumer | Finish current write/LF/flush before reading next frame | May wait indefinitely | No final frame promised while blocked | Caller owns writer/consumer; #0147 measurements do not create a deadline |
| Output positive short write | Continue writing remaining bytes | Ordinary outcome if later writes and flush succeed | Full frame only after LF and successful flush | Actual #0112 faulting writer tests |
| Output write-zero, broken write or flush failure | Stop input and dispatch immediately; never replay | `SessionError` / process 1 | No promised final frame; a visible object or LF can precede failed flush | Actual trait faults and #0116 broken stdout; `results` counts only successfully flushed read results |
| `{"protocolVersion":1,"kind":"cancel","id":"stop"}` | Fatal `FRAME_SCHEMA`, not a cancellation acknowledgement | 2 if completion flushes | Protocol error and completion if possible | Exact v1 shape permits only read/close; no queued or concurrent control reader |
| Close sent behind active work | Process only after current result flush | Close completion / 0 if transport succeeds | Earlier read finishes; close is not interruption | Actual #0116 sequential lifecycle; OS-buffered bytes are not admitted queued work |
| Forced process exit / kill / repeated operator interrupt | Runtime cannot finish a protocol after termination | OS/invoker observation only; no guaranteed numeric status | No guaranteed final frame, cleanup or replay | Invoker owns escalation and must retain incomplete-session classification |

The named trait tests are in
[`read_session_adversarial.rs`](../../tests/read_session_adversarial.rs); process
tests are in [`cli_read_session.rs`](../../tests/cli_read_session.rs).
These are exact baseline references, not a claim that tests were rerun for this
specification. #0140 native-handle faults, #0146 resource observations and #0147
backpressure observations remain unfinished prerequisites for their own claims
until their independent evidence is supplied. They cannot prove signal handling,
cancellation latency or cancellation completion by association.

For v1 clients, session completeness requires complete LF frames, matching IDs,
final completion, and successful process/transport completion. Earlier flushed
read results remain usable read observations after a later failure; they do not
make the session complete. An inner `outputComplete:true` is insufficient.
No output failure or interruption grants permission to retry a mutation.

## Finite future cooperative improvement

The engineering specification below is authorized preparation, with runtime and
platform evidence still required. Keep existing v1 entry points and wire shapes
unchanged. Use separately selected protocol **2** and a separate proposed library
entry `run_cancellable(input, output, token)`; neither exists today. Do not add a
v1 `cancel` operation or infer support from historical
[integration proposals](integration.md).

One caller owns a sticky, thread-safe cancellation token and the input/output
streams. A request can only set the token; it cannot reset it or claim completion.
The session owns at most one active read and zero queued requests. A separate
proposed cancellable metadata-read entry uses the same token, polling before
opening each input, between bounded parser/read units and before serializing a
result. It must unwind/drop all request-owned handles before reporting cancelled.
Partial metadata is discarded; no truncated ordinary result envelope is emitted.
Source metadata writes, output artifacts, apply, cleanup and recovery remain absent.

The session polls before the next frame read, after each returned input read,
before read dispatch, at the native-reader checkpoints and before starting a
result frame. Cancellation before admission adds no attempt; cancellation of
pending bytes counts the already started frame once and discards it. Cancellation
of an admitted read identifies its admitted ID and keeps its attempt count.
It emits no read result for that read. A prepared but unstarted result is discarded
if cancellation is observed. Once any byte of a result frame is written, finish
that entire frame and its flush before observing cancellation. This prevents a
cooperative cancellation from deliberately cutting JSON in half. A later I/O
failure still overrides this intent.

At the next reached checkpoint, stop further input/admission, unwind current read
resources, then attempt exactly one v2 terminal frame:

```json
{"protocolVersion":2,"kind":"session-complete","reason":"cancelled","exitStatus":130,"frames":1,"results":0,"closeId":null,"activeId":"read-1"}
```

The example is authored specification data. The v2 completion extends the v1
completion shape with `activeId`, null unless cancelling an admitted unfinished
read. `frames` and `results` retain v1 counting and bounds; `results` counts
successfully flushed read-result frames. Other v2 completion reasons use null
`activeId`. Existing successful reads retain ordinary statuses 0/1/2/3, not a
fabricated cancellation envelope. The proposed API returns a typed cancelled
outcome with status 130 only after terminal flush succeeds; a selected CLI adapter
then exits 130. Transport failure returns status-1 error semantics, with no
promised terminal frame, even if cancellation was requested. Completed normal
outcomes remain final; later cancellation never retracts a result or completion.

If an input/output call has already returned an error, handle that error before
cancellation at the next checkpoint. `Interrupted` remains retryable, but the
future runtime polls the token before retrying. Protocol failures already
classified also retain their ordinary error outcome. Forced termination always
remains outside cooperative completion guarantees.

This design adds no concurrent control reader. A `cancel` frame remains invalid
in v2 as well; token cancellation is out of band. Close remains sequential. A
future wire cancellation mechanism would need its own explicit version and
bounded control admission design; sending bytes behind an active request cannot
interrupt it in this design.

An opt-in future process adapter may translate the first supported Ctrl-C/SIGINT
or termination-control event into the sticky token. The handler only requests
cancellation: no JSON, I/O, allocation or handle cleanup in signal context.
Each platform event needs actual handler, active-read and process-exit evidence
before advertising support. Repeated interrupts/forced kill retain OS behavior
and no final-frame guarantee. There is no installed signal handler in this work.

There is **no bounded cancellation latency**. Polling does not wake a blocked
filesystem read, input read, output write or flush. Cancellation may wait for that
call and for an already started frame to finish. The caller must continue draining
output if it wants a terminal frame. An invoker may use its own timeout and kill;
that produces an incomplete session, not cooperative success. Native asynchronous
I/O cancellation, deadlines, detached workers and request queues are outside this
bounded design. #0146/#0147 measurements cannot silently add those guarantees.

## Finite specification verification

The authored [checkpoint vectors](read-cancellation/vectors.v1.json) and
independent [checker](../../scripts/check_read_cancellation.py) test mechanism,
result, exit, completeness and ownership claims using a finite state model.
The model covers v1 exclusions and proposed v2 checkpoint races, partial-frame
delivery, blocking, fault precedence and post-completion requests. Altered outcomes
must fail. A blocked-call marker prevents every progress event until explicit
return, an appropriate returned I/O error or forced exit. In particular, neither
a result flush nor a terminal flush can complete while output remains blocked;
an `Interrupted` input return clears the blocked input before retry/checkpoint.
Negative vectors also reject input admission and result preparation while their
underlying calls remain blocked. It neither calls a cancellation runtime nor qualifies OS signals,
native I/O cancellation, resource measurements or elapsed-time guarantees.

```text
python scripts/check_read_cancellation.py
python scripts/check_docs.py
```
