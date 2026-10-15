# Bounded read request/result API (#0057)

The production library now exposes one in-process token-array integration path:
`imageinfo::read_request::execute(request_id, tokens) -> ResultEnvelope`.
It accepts **metadata read only** and returns the existing
[native JSON result contract](native-read-json.md). The executable and this API
share the ordinary read implementation; this is not a second reader or metadata
interpretation model. It adds no CLI syntax, persistent process, request file,
JSON input parser, session framing or concurrent execution manager.

Each token is a native `OsString`, without the executable name. The existing
grammar validates the entire request before execution. No shell splitting,
quoting pass, variable expansion, command substitution, configuration load or
current-directory change occurs. Native paths reach filesystem I/O unchanged;
JSON's displayed lossy path remains a display, not filesystem authority.
Relative paths use the caller process's current directory. Prefer absolute native
paths when integration must not depend on that ambient directory; a dedicated
request `workingDirectory` field is still only a broader proposal.

```rust
use imageinfo::read_request::{execute, write_result};
use std::ffi::OsString;

let input = std::path::PathBuf::from("/caller-selected/example.cr3");
let tokens = vec![
    OsString::from("metadata"),
    OsString::from("read"),
    OsString::from("--tag"),
    OsString::from("EXIF:DateTimeOriginal"),
    OsString::from("--"),
    input.into_os_string(),
];
let record = execute("read-1", &tokens);
let mut wire = Vec::new();
write_result(&mut wire, &record)?;
# Ok::<(), std::io::Error>(())
```

The example path is illustrative, not an included camera fixture. The typed
result is available even when the request has a usage or per-file failure.
`write_result` is optional caller-owned JSON transport; it does not open a file,
select a destination, print to process streams or mutate a source.

## Admission and request-local state

Every call constructs a fresh parser and effective read settings. Tags, value
view, byte budgets, diagnostics, input selection/deduplication and snapshot IDs
belong to that call. There is no retained configuration or previous-result overlay.
The API validates caller IDs using LG-006's 1–128 ASCII-character grammar: a
leading letter, then letters, digits, period, underscore, colon or hyphen.
An invalid ID yields status 2 with `REQUEST_ID_INVALID` under the fixed valid
sentinel **`invalid-request`**. It is neither echoed nor truncated into an
apparently valid correlation ID. There is no ID registry, duplicate-ID detection,
cache or replay operation. Valid IDs are caller correlation labels; callers
combining results must choose distinct IDs themselves.

Only a successfully parsed `metadata read` invocation is dispatched. Help,
version, binary listing/extraction, date preview, pairing and any future mutation
operation refuse before their operation code runs. This entry point does not
inherit capabilities when the executable gains another command. Malformed
grammar retains the ordinary native usage issue codes. Valid but non-read commands
return `REQUEST_OPERATION_UNSUPPORTED`, status 2.

The API owns JSON serialization, so CLI `--output` selectors refuse with
`REQUEST_OUTPUT_UNSUPPORTED`, status 2. Operand tokens after `--` remain literal
native paths, including filenames such as `--output` or `help`. Existing native
selector/view/budget grammar remains shared; this adapter adds no shell or
ExifTool argument-file compatibility.

## Exact finite bounds

| Boundary | Implemented maximum |
| --- | --- |
| Valid caller ID | 128 ASCII bytes |
| Tokens, excluding executable name | 128 |
| One token | 32,768 `OsStr::as_encoded_bytes()` bytes |
| All token payloads combined | 65,536 native encoded bytes |
| Explicit input operands before deduplication | 4 |
| Metadata-read budget per input | 8 MiB, with lower native budgets allowed |
| Serialized result including final LF | 16 MiB |

Token count/size, input-count and metadata-budget violations yield
`REQUEST_LIMIT`, status 2, before input filesystem reads. The executable retains
its existing 16-input boundary; the integration slice deliberately admits fewer.
Other ordinary reader limits remain in force. The token byte measure is the
standard native encoded representation, not a promise of UTF-8 filename storage
or a Windows UTF-16 code-unit count.

The result is measured by a bounded counting writer before delivery. If an
executed read would exceed the result limit, `execute` returns a small
`RESULT_LIMIT` envelope with status 1 and no partial file snapshots. It does not
silently truncate a snapshot or claim successful selection. This is a serialized
byte cap, not an OS memory quota, hard wall-clock deadline, allocation accounting
contract or guarantee that constructing the record consumes only 16 MiB.

## Results, transport and effects

The caller's valid ID is retained throughout the ordinary request, file, summary
and snapshot records. Existing statuses apply: 0 for successful declared reads,
1 for all-input failure/refusal and 3 for mixed successful/failed inputs; usage
errors use 2. Partial R5 interpretation, duplicate occurrences, raw/display values,
invalid-value issues, native I/O errors and path-display warnings keep the existing
result semantics. A successful read does not imply complete metadata coverage.

`write_result(&mut impl Write, &ResultEnvelope) -> io::Result<()>` preflights the
immutable envelope's complete JSON size before writing any prefix. An oversized
caller-constructed record returns `FileTooLarge` without touching the sink.
Serialization then emits one JSON object, one LF and a flush. Short/zero writes,
broken pipes and flush failures propagate as errors. A returned in-memory record
and an `outputComplete` field inside an incomplete stream cannot establish
successful delivery; callers must check the transport return and discard partial
transport data as a complete result. This API has no retry/replay or framing logic.
The writer is a size-bounded serializer, not a schema or admission validator for
arbitrary caller-constructed envelopes; `execute` establishes this slice's request
and operation checks.

All dispatched operations are reads. File effects retain false changed/publication
flags and no cleanup/recovery authority; the summary contains no created artifacts.
No unsupported command reaches extraction or mutation code. Caller-chosen writer
side effects belong to the supplied transport, not to source metadata mutation.
Ordinary OS access-time accounting from reads is outside the no-source-write claim.

## Verification boundary

The independent [request/result tests](../../tests/read_request_result.rs) use
authored structural RAW fixtures and explicitly selected native paths. They
exercise actual native-result parity, request-local selectors/views/budgets,
malformed/unsupported requests, no-mutation inventories, native path handling,
mixed/invalid-value results, finite bounds and actual failing `Write` sinks.
On 2026-10-15, `cargo test --locked --test read_request_result` passed all **12**
integration tests on actual Windows. The native unpaired-UTF-16 filename was read
successfully with the existing `PATH_DISPLAY_LOSSY` warning, proving it was not
reopened through the displayed replacement-character spelling. An authored legal
duplicate-entry fixture first passes the ordinary reader and then exercises the
actual oversized-result refusal; the test does not confuse a rejected large
string with successful result expansion. No-mutation inventories remain equal
across requests and actual transport failures. Native filename support is
filesystem-specific. The Linux CI vector read the actual invalid-UTF-8 filename
successfully. The initial macOS APFS fixture failed during creation with
`Illegal byte sequence` (OS error 92), before the API ran; those bytes could not
be used to create the test input on that filesystem.

The macOS vectors exercise valid Unicode filenames and an invalid-byte request
alongside an existing valid filename matching its lossy display. The invalid-byte
request must produce a failed-file `INPUT_IO` result without a snapshot, rather
than read that neighbor; the selected valid Unicode neighbor must read
successfully. Both requests require unchanged filesystem inventories and
no-mutation effects. Exact platform run results are recorded in the associated CI
and ticket handoff; defining a vector or compiling it is not execution evidence.

The [broader integration document](integration.md) remains a proposal for request
files and sessions. This slice does not implement its serialized request grammar,
persistent process lifecycle, cancellation, environment/cwd envelope, frame IDs,
session concurrency or advanced operations. LG-006 and the umbrella retain those
remaining requirements; #0058 separately owns bounded session framing and limits.
