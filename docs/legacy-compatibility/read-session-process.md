# Metadata-read session CLI and pipes (#0116)

`imageinfo session read` runs the production
[#0112 library runtime](read-session-library.md) over locked process stdin and
stdout. It uses the unchanged [v1 wire contract](read-session-framing.md): UTF-8
JSON input frames terminated by LF or CRLF, canonical LF output, sequential
metadata reads and explicit IDs. No shell or configuration file interprets the
token strings. Relative input paths use the process startup working directory.

Start the executable, wait for its complete LF-terminated `session-ready` frame,
then send a read or close frame. For example, these are authored input examples,
not an observed camera session:

```json
{"protocolVersion":1,"kind":"read","id":"first","tokens":["metadata","read","--tag","ISO","--","authored.cr3"]}
{"protocolVersion":1,"kind":"close","id":"done"}
```

Each admitted read emits one `read-result` containing the complete native
request/result envelope. The runtime flushes that result before reading another
frame. Close emits `session-complete` with reason `close`, matching `closeId` and
status 0. Closing stdin between frames instead completes with reason `eof`.
Trailing requests after close or a fatal error are never executed. Standard
input buffering can prefetch bytes; this is a logical admission boundary rather
than a promise about physical pipe consumption.

## Startup and exit behavior

Use `imageinfo session help` and `imageinfo session read help` for contextual
help. The ordinary `help` command path and `--help` forms also work. Whole-argv
syntax validation precedes help/version dispatch. Help/version never start a
session or read stdin. Help stays plain text; version retains ordinary native
text/JSON behavior.

Successful session startup owns fixed v1 JSONL transport. Both explicit
`--output=text` and `--output=json` therefore refuse startup with status 2; omit
the selector. For startup errors, the existing
[JSON syntax-error routing](native-json-errors.md) remains in effect: one valid
explicit JSON selector can produce the ordinary CLI error envelope. That
startup envelope is separate from session frames; it has no `session-ready`
prefix. Invalid or duplicate selectors keep bounded plain stderr diagnostics.
Color and noninteractive preferences follow ordinary CLI handling; guided mode
remains unavailable. Startup accepts no media operands, metadata settings,
apply permission, request-file or alternate protocol option.

| Session condition | Process exit status |
| --- | --- |
| Clean EOF, explicit close or the 256-attempt limit | 0 |
| Fatal protocol admission error | 2, after error/completion frames if output succeeds |
| Input transport failure | 1, after error/completion frames if output succeeds |
| Output write or flush failure | 1, with no promised final frame |

Request-level statuses 0/1/2/3 remain inside each read result. A failed request
does not change a clean session's final status or persist settings into the next
request. Tokens selecting `session read` inside a read frame are an unsupported
operation, just like other non-metadata-read commands; they cannot recursively
start another session. The next admitted metadata read still executes normally.

Once started, stdout contains protocol frames only. Protocol/input errors need
no duplicate stderr message. A failed output can produce one best-effort bounded
`OUTPUT_INCOMPLETE` diagnostic naming only the I/O error kind, without copying
input content. Stderr delivery is not authoritative. Callers must check complete
LF framing, matching IDs, the final completion, process exit and transport
completion. A result's inner `outputComplete:true` does not establish delivery of
the outer frame or success of the session.

## Bounds and verification boundary

The ready frame advertises the existing v1 constants: 524,288 input bytes per
frame including delimiters, 256 frame attempts, 128 tokens, 32,768 UTF-8 bytes
per token, 65,536 combined token bytes, four explicit inputs and an 8 MiB
metadata budget per input. IDs use the specified 1–128 ASCII-byte grammar.
Nested results retain the 16 MiB cap; outer results allow another 512 bytes.
There is no accepted queue, request concurrency or persistent read cache.
Backpressure can wait indefinitely. These are logical stream/request bounds,
not measured RSS, physical allocation quotas or timeouts.

The [startup tests](../../tests/cli_session_startup.rs) exercise actual executable
help/version, startup selector refusals, ordinary syntax routing and parser
admission. The [pipe tests](../../tests/cli_read_session.rs) use actual child
processes and OS pipes with authored fixtures to exercise ready/result visibility,
sequential request isolation, lifecycle, malformed/truncated/oversized input and
broken stdout. Exact executed cases and platform results belong to the ticket
and its source CI handoff. Test watchdogs bound harness hangs; they do not add a
product deadline guarantee.

Real pipe EOF is not an input I/O failure. Native failing-stdin-handle behavior
and flush-only faults are separate from these pipe observations; #0112's actual
faulting I/O-trait tests retain those runtime paths. Successful pipe writes do
not prove later consumer delivery. Forced termination promises neither final
output nor an exit status, and reopening starts a fresh session without replay.

This entry adds no cancellation/signal policy, server, SDK lifecycle, request-file
importer, per-request cwd/environment, arbitrary native non-Unicode paths,
legacy stay-open compatibility, extensions, performance default or resource
measurement. Reads create no source metadata changes, publication, cleanup or
recovery authority; ordinary filesystem access-time accounting remains outside
that claim. The broader #0015 compatibility acceptance and all RAW mutation and
storage-profile gates remain separate.
