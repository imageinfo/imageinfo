# Requests, persistent sessions and library operations

Subsequent [#0057's implemented read-only API](read-request-result.md) accepts a
bounded native token array and caller request ID in process, returning the existing
result envelope. It shares the ordinary metadata-read workflow. The request-file,
subprocess and persistent-session protocols below remain proposals; this first
library slice does not implement their framing or lifecycle.
Subsequent [#0058's bounded framing specification](read-session-framing.md)
defines a smaller proposed sequential metadata-read/close session with explicit
finite limits and authored wire vectors. Subsequent [#0112](read-session-library.md)
implements that narrower v1 runtime and [#0116](read-session-process.md) exposes it
through `imageinfo session read`. Those implemented boundaries do not adopt the
request-file, queue or apply protocol in this document. The broader
cancel/apply/queue protocol below retains its historical proposed status and is
not permission to advertise those operations through the narrower v1 boundary.

Proposal `2026-10-10.1`, initially local subprocess integration. No executable,
network service, transport library or runtime concurrency model is selected.
The schemas are language-independent boundary data; normal native values remain
free to use the chosen language's standard types.

## Request files

A `native-request` has `schemaVersion: 1`, `id`, absolute `workingDirectory`,
`arguments` (ordered strings without the executable name), and `mode` (`read`,
`preview`, `apply`). Each string is already one argument; no shell splitting,
variable expansion, quoting pass or command substitution occurs. Relative paths
are resolved against the declared directory, including a CLI manifest path;
manifest entries still follow CW-005's own base-directory rules.

```json
{
  "schemaVersion": 1,
  "kind": "native-request",
  "id": "read-1",
  "workingDirectory": "/examples/raw",
  "mode": "read",
  "arguments": ["metadata", "read", "--values", "all", "photo.cr3"]
}
```

Proposed single-request entry: `imageinfo batch run --request-file request.json`.
Mode must agree with the selected operation. A mutation preview defaults to no
publication. An apply-mode document additionally requires explicit outer `--apply`;
without it reject with status 2, rather than applying or silently downgrading.
Read/preview requests cannot inherit apply from another request. Intrinsically
applying leaves such as `plan apply` require apply mode and outer authorization too.

Parsed frame options must not specify `--apply`, `--dry-run`, `--request-file`, interaction
options, process/session controls, `--output`, `--output-file`, or alternate config
loading. These are owned by the envelope/invocation, so reject conflicting sources
of authority/output. No nested `batch run` or arbitrary executable command is allowed.
Operands after `--` remain literal paths, even when named like a forbidden option;
normal file/scope validation still applies. An option value is not a new option.
Ordinary bounded manifests, saved-plan operands and intent/snapshot inputs remain
allowed when the chosen operation explicitly consumes them; reading a document
does not execute code embedded in it. The exact allowlist is derived from the
published native command contract, not a permissive catch-all.

Outputs use the [CLI result records](../cli-walkthroughs/results.md), with the caller's
request ID echoed. Ordinary CLI invocations still generate fresh IDs themselves.
Request/control/input IDs use 1–128 ASCII characters, beginning with a letter and
then letters, digits, period, underscore, colon or hyphen. Snapshot/occurrence IDs
continue to use the metadata model's definition; do not narrow them accidentally.
Result counts are JSON integers from 0 through 9007199254740991; zero state counts
are omitted. This is a wire precision bound, not a memory/performance target.
The envelope's mode maps to the same engine request as native flags; it does not
define a second mutation implementation. Duplicate/unknown JSON members, invalid
Unicode, unsupported versions, negative/oversized fields and non-finite numbers
are rejected before scheduling. Schemas plus semantic validation are both required.

## Persistent JSONL

Propose `imageinfo batch run --stream`. It reads UTF-8 JSON objects, one per line,
from stdin and writes framed JSONL to stdout. Newlines inside strings are escaped.
Only this mode consumes request frames; RAW bytes and binary output cannot share
its stdout. Extracted binary assets require a separately supported artifact operation;
until its request grammar is specified, refuse it here rather than invent framing.

The session starts read/preview-only. Explicit startup `--allow-apply` permits
apply-mode frames from that caller; each frame still has to request apply, pass
normal preflight and satisfy WS. This is permission to accept explicit apply
requests, not a way for a saved plan or imported metadata to authorize itself.
Settings are an immutable session baseline selected at startup; per-request allowed
options do not change it. Config changes and code/module loading are not session
requests in this initial protocol. Native `config` commands remain separate.

Before reading requests, emit `session-ready` with protocol version, a session ID,
and positive finite `maxFrameBytes`, `maxQueuedRequests`, `maxRequests`, plus
`allowApply`. Numeric defaults await #0016 measurements under the [performance protocol](../performance/README.md); clients must not send before readiness.
The host also enforces bounded pre-handshake/line buffering. Version mismatch is
fatal before any media work. Keep all IDs unique within the bounded session,
including controls; do not retain an unbounded lifetime history.
The frame limit counts ID-bearing requests/controls, including rejected requests.
On reaching it, stop admission and drain accepted work, then close normally if
otherwise healthy. Report the limit-triggered close so clients can open a new
session; mutation retries still require receipt checks. Queue limits must not cause
an unbounded set of rejected IDs to accumulate.

Requests run FIFO, one active request at a time. Accept a bounded queue; a full queue
rejects the new request explicitly without admitting it. Do not block control-frame
processing behind a full work queue. Cache immutable definitions or verified read
facts when safe, but never retain queued writes, warning policy, tag filters,
sources, destinations or apply mode from the previous request.

| Input / condition | Required response |
| --- | --- |
| Valid admitted request | One CLI `request`, its ordered file records, then one CLI `summary` with its request ID. Emit request when execution begins. |
| Valid envelope with invalid command, denied apply or full queue | Request plus error summary, status 2, no media I/O/publication; continue the session. ID is consumed. |
| Duplicate ID | `control-result` with rejected status, code `DUPLICATE_ID`; do not emit another indistinguishable request result or replay work. |
| `cancel` naming active request | Acknowledge cancellation request; finish the WS safe boundary and summarize 130 or 5. An acknowledgement is not cancellation completion. |
| `cancel` naming a queued request | Remove it and emit its request/error summary with 130 and no publication. |
| `cancel` naming finished/unknown request | Acknowledge already-finished/not-found; never undo or replay. |
| `close` with `drain` | Stop admitting new requests; finish admitted work, then session-complete. |
| `close` with `cancel` | Stop admission, cancel active/queued work at safe boundaries, then session-complete. |
| Clean EOF between frames | Drain previously admitted requests; do not keep polling a disk argument file. |
| Malformed JSON, duplicate members, bad schema/version or oversized/truncated frame | Stop admission. Emit a bounded protocol error if possible; safely finish active work, cancel queued work and close. Never guess a boundary inside an oversized frame. |
| Broken stdout or forced termination | Stop scheduling; preserve receipts/recovery. No complete output is promised; callers inspect durable state before retrying mutation. |

Control objects have their own unique `id`, plus `requestId` for cancel or `policy`
for close. Control acknowledgements may appear between CLI records; request/file/
summary records keep their own IDs. A queued cancellation may complete before the
active request, so clients demultiplex by ID instead of assuming contiguous replies.
No stdout/stderr arrival ordering is guaranteed; stdout records are authoritative.

Emit a final `session-complete` containing the session transport status when possible.
Session exit is 5 for unresolved recovery, otherwise 130 for interrupted/cancel-close,
2 for fatal framing/version/schema errors, 1 for transport failure, or 0 for a clean
drain. Ordinary operation failures belong to request summaries and do not by
themselves fail the transport. A cancelled individual request does not require
closing the session. Clients check both request summaries and session completeness.

The session/control records have a separate protocol version from CLI/metadata
schemas. Their exact release schema remains LG-006 until the handshake limits and
implementation transport are validated; the request/control **input** schema is
supplied now. No client may infer runtime readiness from this requirements draft.

## Library lifecycle recommendation

| Use case | Required observable contract |
| --- | --- |
| One-call extraction | Return a snapshot with source identities, coverage and diagnostics; do not flatten duplicates. |
| Repeated projection | Select from an immutable snapshot without changing it or silently reading new sources. |
| Values | Request raw/normalized/display explicitly; use native exact types internally where appropriate. |
| File/resource ownership | State whether the caller or library closes resources and how long borrowed data remains valid; no hidden close of caller-owned handles. |
| Reusable edits | Copy/reuse an intent value, then bind/validate each target independently. No ambient edit queue. |
| Cancellation/errors | Same WS outcome states as the CLI; ordinary typed results/diagnostics, with exceptional mechanisms chosen idiomatically later. |
| Discovery/custom definitions | Separate static definitions, observed presence and evidenced writability; definitions cannot self-enable a writer. |
| Concurrency | Independent requests isolate mutable state; serialization/guards protect shared physical targets. Do not expose unbounded parallel mutation. |

No particular function names, classes, ownership framework, exception policy or FFI
are mandated here. An ABI or a drop-in Perl object would be a separate compatibility
project. Experts should see ordinary functions/types for the eventual language.

## Plan serialization boundary

The full saved-plan wire schema remains **LG-004**. Request/result schemas are not
saved plans and must not be substituted for them. WS-002 still requires the plan
to bind all read/write sets, identities/properties, typed effects and losses,
policy/registry/mapping revisions, protected content/references, storage guarantees,
original recovery and group ordering. Fields supplied by an imported plan must be
recomputed against trusted current data before apply.

Do not publish an apparently executable universal plan schema full of untyped
free-form fields merely to call this gap closed. A later per-operation specification
must cover insertion, list/structure/language transforms, file operations and
platform property identities, not just the simple set/delete examples. This gap
blocks plan interoperability claims, while allowing the native workflow recommendation
and migration surface mapping to be reviewed now.
