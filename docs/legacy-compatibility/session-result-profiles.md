# Actual read-session v1 result qualification (#0128)

The [closed output schema](session-result-profiles/schema.v1.json) freezes the
actual four frame kinds emitted by the [library runtime](read-session-library.md)
and [CLI adapter](read-session-process.md). It qualifies the bounded existing
metadata-read session. The historical [#0058 schema](read-session/schema.v1.json)
and synthetic transcripts remain proposal/model evidence; this package validates
actual process output and separately identified caller-owned transport faults.

| Frame | Current fields and meaning |
| --- | --- |
| `session-ready` | Protocol 1, exact fixed limit object, `allowApply:false`; emitted before input admission. `maxQueuedRequests:0` advertises the absence of a queue. |
| `read-result` | Protocol 1, admitted request ID and complete nested native request/result envelope. Every nested request/file/summary ID matches the outer ID. |
| `protocol-error` | Protocol 1, `id:null`, one of the seven current error codes. A rejected or duplicate input ID is never echoed here. |
| `session-complete` | Protocol 1, exact reason/status, attempt count, flushed-result count and matching explicit `closeId` or null. |

The nested envelope reuses the existing [result contract](result.schema.json).
The current session subset has at most four explicit inputs, metadata-read or
null operation/mode, no transaction/artifact effects, `interrupted:false` and
`outputComplete:true`. Request refusals can contain no files and incomplete
selection. Actual file reads have exact file/state counters, complete selection
and status 0 (all read), 1 (none read) or 3 (mixed). Ordinary request usage errors
remain status 2. These inner statuses do not change a clean session's status 0.

The schema checks closed individual shapes. The
[independent checker](../../scripts/check_session_result_profiles.py) adds
strict UTF-8 JSON, duplicate-member and Unicode-scalar rejection, integer-type
checks, nested identity/count/status rules and full transcript validation. Its
expected IDs, number of attempts, final reason and process status come from the
authored input cases, independently of the output being checked. Authored request
expectations also bind exact input paths, per-file outcomes, source byte lengths,
issue codes/severities, default value views and both fixture ISO occurrences and
their independently authored value 800. Snapshot source paths must match file
paths; file issue identities and severities must agree with their file outcomes.
File result status is also calculated from the observed state sequence. This is
finite qualification, not a general session importer or client library.

## Completion and delivery

| Ending | Completion reason / status | Attempts and results |
| --- | --- | --- |
| EOF between frames | `eof` / 0; null close ID | EOF adds no attempt. |
| Explicit close | `close` / 0; exact close ID | Close adds one attempt, no result. Trailing requests are not admitted. |
| 256th admitted read | `limit` / 0; null close ID | Exactly 256 attempts and flushed results. Attempt 257 is not admitted. |
| Protocol admission failure | `protocol-error` / 2; null close ID | The failed frame adds an attempt; error then completion follow prior results. |
| Input transport failure | `input-error` / 1; null close ID | Failure before a frame adds no attempt; failure after pending bytes adds one. This package exercises caller-owned traits only. |
| Output write/flush failure | No successfully delivered completion promised; status-1 semantics | Only successful result flushes count, even if a complete JSON object is already visible. |

The process cases cover empty EOF/close, successful reads, missing input, usage
refusal, mixed request results, read then EOF, limit, malformed/truncated/invalid
encoding/schema/oversized input and duplicate ID. Source bytes and missing-path
absence are checked. Inputs are authored structural CR3 fixtures only.

The [qualification-only Rust harness](session-result-profiles/trait-harness.rs)
links the actual library and exercises ready/result/completion flush failures,
partial broken/write-zero output, before/after-pending-byte input faults and
successful positive short writes. Those eight observations are explicitly
`actual-caller-owned-traits`; they are not native failing-stdin, OS-pipe flush
fault or process-exit evidence. The harness executable returns its observation
normally; its report's status belongs to the library outcome, not that harness's
process exit. The CLI process cases independently compare actual process exits.

A result object with `outputComplete:true` cannot prove outer delivery. A full
completion object can also be visible when its final flush fails. Complete LF
framing, matching identities/counts, successful transport and the process exit
must all agree. The checker never accepts a missing final frame as a successful
transcript or invents a final frame after an output fault.

## Reproduction and retained evidence

Use the pinned Rust toolchain and the existing test-only `jsonschema==4.26.0`
environment. Build the actual executable and matching library together, then:

```text
cargo build --locked
python scripts/check_session_result_profiles.py --binary target/debug/imageinfo.exe --write-examples --public docs/legacy-compatibility/session-result-profiles/qualification.v1.json
python scripts/check_docs.py
```

On other platforms use `target/debug/imageinfo`. An isolated Cargo target can be
supplied through `--binary`; its sibling `libimageinfo.rlib` is the default trait
library. `--library` can select an exact matching dependency artifact explicitly.
The checker invokes `rustc` for the fixture builder and transport harness.
The JSON-schema package is QA-only; this work adds no product dependency.

The evidence report binds producer/checker/schema/vector/harness source hashes
and exact executable/library hashes. The parent refreshes it after integrated
source freeze; source hashes alone do not attest how an arbitrary binary was
built. Actual path-independent control examples are
[EOF](session-result-profiles/eof-empty.example.json),
[close](session-result-profiles/close-empty.example.json),
[protocol refusal](session-result-profiles/invalid-json.example.json) and
[duplicate ID](session-result-profiles/duplicate-id.example.json).

[Negative vectors](session-result-profiles/negative-vectors.v1.json) alter actual
captured frames or supply independently authored malformed wire bytes. They
cover identity/count/status contradictions, missing/extra/reordered frames,
closed-kind/authority/completeness violations, malformed JSON/UTF-8, duplicate
members, surrogates, wrong scalar/container/integer types and process-exit
contradictions. A valid schema alone is insufficient for cross-frame acceptance.
Lexical controls start with otherwise accepted actual frames: duplicating a
member, inserting a surrogate or invalid UTF-8 into an allowed issue message,
adding BOM/CRLF or removing LF. Each control must become accepted when only its
targeted detector is disabled during QA. NaN is tested directly at the strict
JSON layer because every current closed numeric schema position would also
reject it; schema rejection receives no credit for that lexical control.

No historical queue, cancellation or apply records are adopted. This work adds
no runtime behavior, deadline, resource policy, general compatibility acceptance,
source mutation, storage-profile admission or RAW write permission.
