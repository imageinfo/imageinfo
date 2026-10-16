# Bounded caller-owned read-session runtime (#0112)

The production library exposes
`imageinfo::read_session::run(&mut impl BufRead, &mut impl Write)`.
It implements the fixed v1 wire contract from the
[#0058 session proposal](read-session-framing.md), dispatching each admitted
read through the existing [#0057 token-array API](read-request-result.md).
The library entry owns no process. Subsequent [#0116](read-session-process.md)
adds `imageinfo session read` as a thin CLI adapter with actual pipe tests. The
original proposal's authored transcripts remain specification evidence; they are distinct
from this runtime's actual stream and native-reader tests.

```rust
use imageinfo::read_session;
use std::io::Cursor;

let mut input = Cursor::new(
    b"{\"protocolVersion\":1,\"kind\":\"close\",\"id\":\"done\"}\n".as_slice(),
);
let mut output = Vec::new();
let outcome = read_session::run(&mut input, &mut output)?;
assert_eq!(outcome.exit_status, 0);
assert_eq!(outcome.reason, "close");
# Ok::<(), read_session::SessionError>(())
```

The caller chooses and retains the buffered reader and writer. The runtime opens
no stream, changes no working directory and writes no stderr. A caller-created
`BufReader` can physically prefetch trailing bytes from its underlying stream.
The runtime consumes only through the current frame's LF or the first size
violation; callers can recover any prefetched tail from that same buffered reader.
It does not create a private buffer that loses those bytes when the session ends.
After close, fatal admission failure, output failure or attempt 256, it performs
no further input consumption or request dispatch.

## Admission and execution

LF and CRLF terminate input frames; all output frames end with LF. The input cap
counts every byte including delimiters and whitespace. After 524,288 non-LF bytes,
the next LF could not fit, so the runtime refuses immediately without draining the
line. Complete framing precedes UTF-8/BOM checks, lexical container-depth checks,
JSON syntax and member uniqueness, Unicode scalar checks, exact shape/token
checks, and session-wide ID uniqueness, in that order. No refused frame reaches
media I/O.

The parser keeps decoded string bytes until all JSON syntax and duplicate-member
checks complete. The existing serde_json byte visitor preserves surrogate escapes
as WTF-8; the runtime separately rejects raw string control bytes and later rejects
decoded strings that are not Unicode scalar text. This preserves the specified
error precedence for a malformed or duplicate-bearing object that also contains
an unpaired surrogate. Duplicate decoded keys refuse at every depth, including
unknown nested members. The depth preflight ignores brackets inside strings and
rejects depth greater than eight before recursive structural parsing.
Numeric syntax is checked independently of floating-point range, so a large
exponent cannot hide a later scalar error. A syntactically valid number outside
the decoder's range fails schema admission: v1's only numeric input field is the
fixed protocol version 1.

The fixed safety bounds are 256 frame attempts, 128 ASCII ID bytes, 128 tokens,
32,768 UTF-8 bytes per token, 65,536 combined token bytes, four explicit inputs,
an 8 MiB metadata budget per input, and a 16 MiB nested result including its usual
LF. The outer result cap is 16 MiB plus 512 bytes, including its single outer LF.
These are explicit opt-in protocol limits rather than measured performance
defaults, allocation quotas or deadline guarantees. The runtime retains only its
current bounded frame/request/result and a bounded ID registry, with no earlier
results, cache or queue.

Only complete admitted reads call `read_request::execute`; each call has fresh
read settings, selectors, diagnostics and input selection. Unicode token strings
become native `OsString` values directly. The API rechecks native encoded-byte,
input-count and metadata-budget limits. Non-read commands, CLI output selectors
and ordinary usage failures remain request-level status-2 results; they do not
terminate the session. Operands after `--` remain literal paths. This wire has no
representation for arbitrary non-Unicode native paths.

## Delivery and outcomes

The ready frame flushes before the first input read. Each outer read-result frame
contains the complete existing envelope as a nested object. Its entire serialized
size is checked before any prefix is written, then the runtime writes the object,
LF and flush. It reads no next frame until that flush succeeds. Result counts
increase only after successful flush. A complete object followed by a failed
flush does not increase the flushed-result count.

`Ok(SessionOutcome)` means the completion frame flushed. Its `exit_status` is 0
for clean EOF, explicit close or the attempt limit; 2 for fatal protocol admission;
and 1 for input transport failure. Its `frames` counts attempts and `results`
counts flushed read-result frames. Its `reason` is exactly `eof`, `close`, `limit`,
`protocol-error` or `input-error`. Request result statuses 1, 2 and 3 do not change
a clean session status. Input failure before any byte of a new frame does not
increase the attempt count; failure after pending bytes does. Interrupted reads
retry without creating another attempt.

`Err(SessionError)` means output delivery failed, with status-1 semantics. It
contains the I/O `source`, actual attempt count and already flushed result count.
Positive short writes are completed normally; write-zero, broken write and flush
errors stop immediately. There is no promised final/error frame or replay after
output failure. Callers must check the return even after receiving a full result;
an inner `outputComplete:true` cannot establish successful outer delivery.

Read effects remain those of #0057: no source metadata writes, created artifacts,
publication, cleanup or recovery authority. Ordinary filesystem access-time
accounting from reads remains outside that claim. A supplied writer's side effects
belong to its caller-owned transport.

## Verification boundary

The [basic integration tests](../../tests/read_session.rs) exercise actual
authored CR3 reads, exact direct-API envelope equality, Unicode paths, source
inventories, LF/CRLF, close-tail retention, protocol-size boundaries and combined
syntax/member/scalar precedence. The independent
[adversarial tests](../../tests/read_session_adversarial.rs) check the existing
56 authored input vectors against the real runtime, request-state isolation,
actual native-reader results, consumption/flush ordering, parser boundaries and
faulting `Read`/`BufRead`/`Write` transports. Those failing transports execute the
real runtime's I/O paths; they are distinct from #0058's synthetic delivery
annotations. Exact successful execution counts and platform results belong in
the associated ticket and CI handoff.

This increment makes no process-exit, real OS-pipe, cancellation, elapsed-time,
concurrent-request, persistent-cache, RSS/quota or performance-default claim.
It provides no server, request-file importer, arbitrary executable extension,
mutation command, durable receipt or storage-profile admission. Broader LG-006
and RAW write admission remain separate.
