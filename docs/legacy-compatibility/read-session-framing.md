# Bounded metadata-read JSONL session proposal (#0058)

Specification revision `2026-10-15.1`, protocol version **1**. This is a
specification-only LG-006 increment grounded in the implemented
[#0057 read request/result API](read-request-result.md), observed in
[`src/read_request.rs`](../../src/read_request.rs) on 2026-10-15. There is no
CLI entry point in this specification increment, server or process-session SDK. Subsequent
[#0112](read-session-library.md) implements this v1 framing, decoder, bounded
output and read execution in an opt-in caller-owned library runtime;
[#0116](read-session-process.md) adds its CLI adapter and finite actual pipe tests. The wire
examples and checker below remain historical proposal evidence; they do not
execute a persistent process or establish throughput, cancellation or broader
compatibility.

The [broader integration proposal](integration.md) retains its historical
request-file, queue, preview/apply, cancellation and concurrency ideas. This
bounded proposal supplies only one local, caller-owned, read-only byte-stream
session. A future implementation must separately earn runtime evidence. No
command shown in that broader document becomes implemented through this proposal.

## Transport and admission

One caller owns the process input/output streams. Startup produces one
`session-ready` object and flushes it before reading input. The caller waits for
that complete LF-terminated frame before sending. There is no negotiation,
network listener, code loading, environment envelope, per-request cwd or config.
Protocol version 1 is exact; unsupported versions are fatal before dispatch.

Each input frame is one UTF-8 JSON object terminated by LF or CRLF; each output
frame ends with canonical LF. The frame byte cap includes all delimiter bytes
and JSON whitespace/escaping, including both CR and LF for CRLF input. Input must
terminate every frame, including its final frame. BOM, blank lines and multiple
JSON values on a line refuse. JSON strings may contain escaped newlines; a raw
LF always terminates a frame. Ordinary JSON whitespace outside strings is
allowed, including CR. Raw CR inside a string is an ordinary JSON syntax error.
Duplicate object members at any depth, unknown members,
non-finite numbers, malformed UTF-8 and unpaired Unicode surrogate escapes refuse.
Here non-finite tokens such as `NaN` and `Infinity` are JSON syntax errors.
A syntactically valid exponent outside the numeric decoder's range fails schema
admission after complete syntax/member and Unicode scalar checks; v1's only
numeric input field is the fixed protocol version.
All token strings contain Unicode scalar values and exclude U+0000. JSON escaping
is decoded once; there is no shell splitting, globbing, variable expansion,
command substitution or argument-file interpretation.

Read a bounded line before parsing or dispatch. Upon seeing enough non-LF bytes
that even a next LF would exceed `maxInputFrameBytes`, fail immediately; do not
buffer the rest, drain the line, guess a new boundary or resume. A bounded parser
must also reject nesting deeper than **8** JSON containers, counting the root as
1, rather than relying on an unbounded recursive parser. This admits the two
input shapes below. No media I/O occurs before complete frame admission.

The proposed input shapes are exactly:

```json
{"protocolVersion":1,"kind":"read","id":"read-1","tokens":["metadata","read","--tag","ISO","--","/caller-selected/example.cr3"]}
{"protocolVersion":1,"kind":"close","id":"close-1"}
```

These lines are separate alternative requests, not one JSON document. Required
fields cannot be omitted or null, and no additional fields are allowed. Every ID
matches `^[A-Za-z][A-Za-z0-9._:-]{0,127}$`, measured in ASCII bytes. IDs are unique
across all admitted read and close frames for this session, including reads whose
command later refuses. The registry is bounded by `maxFrames`; it is discarded
when the session ends. IDs confer no retry, authentication, source identity,
snapshot cache or deduplication authority. Duplicate IDs are fatal and never
replay a previous result. No invalid/duplicate ID is echoed as a result ID or
normalized into #0057's `invalid-request` sentinel.

`tokens` contains complete arguments excluding the executable name. Its strings
convert directly to native `OsString` values and call
`read_request::execute(id, tokens)`. Native byte limits are rechecked after
conversion by that API. The wire covers Unicode paths only: #0057's wider native
unpaired-UTF-16/invalid-UTF-8 path support has no encoding here. Lossy displayed
paths are never reopened. Relative paths retain the process's unchanged startup
cwd, as in #0057; callers needing stable explicit location use absolute paths.
There is no cwd normalization or change between requests.

Only the ordinary metadata-read grammar can dispatch. Valid non-read commands,
CLI output selectors and ordinary usage failures return #0057's status-2
envelopes; they are request failures and the session continues. Operands after
`--` remain literal paths. A token such as `--output` after that delimiter does
not select a transport. No preview, extraction, write, cleanup or recovery
operation is added or inherited from future CLI commands.

## Proposed finite bounds

These are finite **proposal constants**, chosen to bound the protocol and reuse
existing API caps. They are not measured performance defaults, memory quotas,
deadlines or results from private camera benchmarks.

| Boundary | Proposed v1 cap |
| --- | --- |
| Input frame, including LF | 524,288 bytes (512 KiB) |
| Output frame, including LF | 16,777,728 bytes (16 MiB + 512) |
| Input frame attempts in a session | 256 |
| Active request / queued requests | 1 / 0 |
| Input JSON container depth | 8 |
| ID | 128 ASCII bytes |
| Tokens per read frame | 128 |
| One decoded token | 32,768 UTF-8 bytes |
| All decoded tokens combined | 65,536 UTF-8 bytes |
| Explicit read inputs, before API deduplication | 4 |
| Metadata-read budget per input | 8,388,608 bytes (8 MiB) |
| Nested #0057 serialized result, counting its usual LF | 16,777,216 bytes (16 MiB) |

The larger input frame cap permits JSON escaping of bounded token payloads; it
does not relax their decoded byte caps. Token count/UTF-8 byte violations are
frame-schema failures. Native encoded-token, input-count and metadata-budget
violations reported by `execute` remain ordinary `REQUEST_LIMIT` results. The
output cap leaves space for the wrapper around the existing compact API result;
the nested result is not encoded as a string or truncated. The embedded result
has no inner LF. The outer LF replaces it. Preflight the complete outer frame
before any output prefix; an unexpected outer overflow is a transport failure.

Read the next frame only after completely serializing and flushing the preceding
result. There is no accepted queue, worker thread or concurrent media operation.
OS pipe buffering belongs to the caller/transport and is not an admitted request
queue. Backpressure can wait indefinitely; no hard elapsed-time/cancellation
promise is made. Keep only the current bounded frame, bounded ID registry and
current request/result; do not accumulate prior results internally.

An attempt begins on the first byte of the next frame and counts even if that
frame is malformed, truncated, oversized, duplicate or a rejected read. EOF with
no bytes pending is not an attempt. A read error before any bytes is not an
attempt. At 256 attempts, close after the current outcome; do not read a 257th
byte-stream frame. Explicit close and fatal-error reasons take precedence over
the limit reason on attempt 256. Consequently input consumption is at most
256 × 524,288 bytes (128 MiB), and at most 256 read results can be produced.
Ready/error/completion frames each fit 4,096 bytes; total successful output is
bounded by 256 × 16,777,728 + 3 × 4,096 bytes. These are logical stream bounds,
not physical allocation or RSS limits.

## Output and lifecycle

The first output frame is exactly the versioned ready shape below; advertised
limits equal the v1 constants. This is a proposed wire example, not runtime output.

```json
{"protocolVersion":1,"kind":"session-ready","limits":{"maxInputFrameBytes":524288,"maxOutputFrameBytes":16777728,"maxFrames":256,"maxQueuedRequests":0,"maxTokens":128,"maxTokenBytes":32768,"maxTotalTokenBytes":65536,"maxInputs":4,"maxMetadataBytes":8388608,"maxResultBytes":16777216},"allowApply":false}
```

Every admitted read emits one contiguous `read-result` frame with exactly
`protocolVersion`, `kind`, `id` and `result`. `result` is the complete existing
[#0057 result envelope](result.schema.json), including its request, ordered files
and summary; it is neither three separately interleavable frames nor a flattened
snapshot. The wrapper `id`, envelope `requestId`, request/summary `requestId`
values and every file's `requestId` agree. Per-file `inputId` values remain
distinct local input references. Validate embedded snapshots against the
[native subset](native-read-json/snapshot.schema.v1.json) as applicable. No
`session-ready` or control schema changes the nested result's `schemaVersion:1`.

All request-local parser settings, filters, value views, budgets, diagnostics,
input deduplication, files and snapshot IDs start fresh through `execute` for
each frame. No earlier tag selection, path, budget or failed request overlays the
next request. The process retains only startup cwd/environment and bounded
protocol bookkeeping. No read cache is proposed. A successful read retains
partial-coverage semantics; status 0 does not certify complete metadata coverage.
Read results retain status 0/1/2/3 and false source-change/publication effects.
Ordinary OS access-time accounting is outside the no-source-write claim.

An admitted close frame emits no read result. It immediately ends admission and
produces one completion frame after all preceding results have flushed. Since
there is no queue or concurrent input processing, every preceding request has
already finished. Trailing bytes after close are never read, parsed or executed.
Neither `cancel` nor close policies are valid v1 input fields/operations.

| Condition | Output and final process status |
| --- | --- |
| Clean EOF between frames | `session-complete`, reason `eof`, status 0. |
| Valid close | `session-complete`, reason `close`, `closeId` matching close ID, status 0. |
| Attempt limit after ordinary read outcome | Flush that result, then `session-complete`, reason `limit`, status 0. |
| Malformed/schema/version/encoding/depth/size/duplicate-ID input | One bounded `protocol-error`, then `session-complete`, reason `protocol-error`, status 2, if transport allows. No read dispatch for that frame. |
| EOF after nonempty unterminated bytes | `FRAME_TRUNCATED`, then protocol-error completion, status 2; even syntactically complete JSON without LF is truncated. |
| Input transport read failure | `INPUT_IO`, then `session-complete`, reason `input-error`, status 1, if output allows; do not dispatch a partial frame. |
| Output write/short-write/zero-write/flush/serialization failure | Stop input and dispatch immediately; process status 1, no promised final/error frame and no replay. |
| Forced process termination | No promised final output or exit status. Cancellation is unspecified. |

An error frame has exactly `protocolVersion:1`, `kind:"protocol-error"`,
`id:null` and `code`. Codes are `FRAME_TOO_LARGE`, `FRAME_TRUNCATED`,
`FRAME_ENCODING`, `FRAME_JSON`, `FRAME_SCHEMA`, `DUPLICATE_ID` and `INPUT_IO`.
Encoding includes BOM/invalid Unicode; JSON includes duplicate members and
invalid JSON syntax; schema includes unsupported versions, depth and shape/token
violations. Check framing size, then raw UTF-8/BOM validity, container depth,
JSON syntax/member uniqueness, decoded Unicode scalar validity,
schema/semantic token caps and ID uniqueness, in that order. Depth counting
treats brackets inside quoted strings as data; a frame crossing depth 8 refuses
before general JSON parsing even if its later bytes would also be invalid JSON.
EOF with pending bytes is truncated unless the size cap was already crossed. Stream read
failure is `INPUT_IO`, even with pending bytes. No input content, paths, unknown
members or supplied IDs are copied into protocol errors. Best-effort stderr
diagnostics are limited to 4,096 UTF-8 bytes per session and non-authoritative;
they cannot share stdout JSONL or echo input content.

A completion has exactly `protocolVersion:1`, `kind:"session-complete"`,
`reason`, `exitStatus`, `frames`, `results`, and `closeId`. Counts are integers
0–256, `results <= frames`; `results` counts completely flushed read-result
frames. `closeId` is null except for reason `close`. A protocol/input error may
follow earlier successful read results; it never retroactively invalidates those
complete read observations. Ordinary request status 1/2/3 does not change a clean
session's status 0. The session has no mutation outcomes or durable receipts.

Clients require complete LF-terminated JSON, matching IDs, ordered lifecycle and
the final completion plus successful process/transport completion to claim a
complete session. An inner `outputComplete:true` cannot prove outer delivery.
Even a received full result can precede a producer flush failure; callers must
report the session transport failure. Partial output is discarded as a complete
frame. Reopening a session does not resume, replay or authenticate old results.

## Review evidence and remaining work

The versioned [schema](read-session/schema.v1.json),
[authored wire vectors](read-session/vectors.v1.json) and independent
[checker](../../scripts/check_read_session.py) cover the finite proposed
grammar and lifecycle, including rejection and transport outcomes. Vector output
is specification data, never an actual session trace. Schema validation alone
cannot establish byte framing, duplicate-member detection, cross-frame ID
uniqueness, aggregate/depth/token-byte limits or real I/O behavior; the checker
supplies finite independent checks, not a session implementation.

On 2026-10-15, the checker passed **56 authored framing vectors, four complete
wire transcripts, seven authored delivery observations and 16 altered-output
refusals**, using the existing test-only `jsonschema==4.26.0` dependency:

```text
uv run --no-project --with jsonschema==4.26.0 python scripts/check_read_session.py
```

Injected engine-response stubs isolate session status propagation; their
schema-shaped envelopes do not establish native read-result semantic validity.
The native result/snapshot checks remain #0053/#0057's responsibility. The
checker uses whole retained byte strings and synthetic delivery observations;
it does not demonstrate bounded streaming allocation or actual failing pipes.

#0112's [library evidence](read-session-library.md) now covers an actual bounded
decoder/output adapter, native-reader state isolation and real faulting I/O trait
transports. It distinguishes buffered logical consumption from caller-owned
physical prefetch and supplies no process or OS-pipe result itself.
[#0116](read-session-process.md) separately covers the CLI entry, finite
malformed/truncated/oversized pipe observations and actual process exit behavior.
Broader platform path behavior, failing native input handles and memory/resource
measurements remain separate. Cancellation, queues, concurrent requests, persistent
caches, SDK lifecycle, arbitrary native path encoding, performance tuning and
ExifTool parity remain separate scope. This proposal enables no writer, RAW
admission, profile or storage/recovery action.
