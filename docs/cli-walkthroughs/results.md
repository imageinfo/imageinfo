# Results, diagnostics and exit precedence

Proposal `2026-10-10.1`; no executable/protocol implementation. This specifies the
observable CLI boundary used by the [walkthroughs](walkthroughs.md), not internal
types. [Card #0007](../legacy-compatibility/integration.md) now supplies request-file
and persistent-session proposals plus a [result schema](../legacy-compatibility/result.schema.json).
Complete saved-plan/session-output schemas and runtime integration remain #0015 work.
The [metadata schema](../metadata-model/metadata-contract.schema.json) remains
the authority for snapshot payloads.

## Streams and record fields

Text/table mode puts requested results and the final summary on stdout. Diagnostics
and optional progress use stderr. JSON/JSONL stdout contains data only, no banners,
colors, prompt fragments or progress. Issue records remain in structured data so
scripts do not parse human stderr wording. Binary stdout contains bytes only.

Each JSONL request emits one `request`, zero or more `file` records in input order,
then one `summary` when output completes. Each line is a complete UTF-8 JSON object.
Every record has `schemaVersion: 1`, `kind`, and `requestId`. A new invocation gets
a fresh request ID; the invented IDs in examples are not reusable authorization.

| Kind | Additional required fields | Meaning |
| --- | --- | --- |
| `request` | `operation`, `mode`, `issues` | Canonical group/leaf string, `read`/`preview`/`apply`, and whole-request issues. |
| `file` | `inputId`, `path`, `state`, `snapshot`, `transactionId`, `effects`, `issues` | Stable per-request input identity; escaped display path; explicit state; snapshot or null; owned transaction ID or null; effect summary; attributable issues. |
| `summary` | `exitStatus`, `selectionComplete`, `counts`, `artifacts`, `issues`, `interrupted`, `outputComplete` | Authoritative outcome, completeness and counts; it does not erase earlier per-file facts. |

If parsing cannot establish a known operation or mode, those two request fields
may be null in a status-2 error envelope; do not invent a valid command path.

`snapshot` contains the entire emitted metadata-model snapshot object when the
operation returns metadata. It is null for operations without metadata payloads
and inputs that failed before extraction. It is never a flat object keyed by tag
label. A projected/partial snapshot retains its own coverage/value states and
required reference closure; it cannot label omitted fields absent.

`effects` always contains `publicationMayHaveOccurred`, `changed`, and
`cleanupPending` as booleans, plus string arrays `recoveryIds` and `notes`. `changed` may be
null only when the state is recovery-required and the effect cannot be established.
It reports changes attributable to this operation, not an external editor.
Notes are human explanations, never commands. Recovery IDs are opaque IDs resolved
through owned records; no arbitrary path in an imported result grants access.

Every issue contains `code`, `severity` (`warning` or `error`), `message`, and nullable
`inputId`, `path`, `occurrenceRef`. An occurrence reference, when present, is an
object containing both `snapshotId` and `occurrenceId`. Stable codes identify the
condition; message text can improve. A path/message is escaped data, never terminal
control or shell source. Diagnostics must not include private metadata values unless
needed for the user's requested result; private transaction details stay protected.

`counts` contains nonnegative integers for `discovered`, `excluded`, `deduplicated`,
and `byState` (an object keyed by the states below, omitting zero entries).
`discovered` is the count of unique selected input units known to the request;
`excluded`/`deduplicated` count skipped candidates separately. Each known input
receives at most one final file record; summed state counts equal discovered when
the summary is complete. A single selected RAW with included sidecar can yield a
snapshot containing both sources, but mutation units are per physical destination.
The request's operation/mode determines the unit; the plan shows it before apply.

`artifacts` reports requested saved plans, reports and extracted assets separately
from selected inputs. Each entry has `kind` (`plan`, `report`, or `extraction`),
`path` (requested destination), nullable `retainedPath` (owned incomplete artifact),
`state`, nullable `transactionId`, and `recoveryIds`. Its state uses
`committed`, `failed-before-publish` or `recovery-required`; artifacts do not inflate
input counts. An artifact publication/transport failure still affects request status,
and artifact recovery uncertainty also takes precedence as status 5.

JSON mode uses one object with `schemaVersion`, `requestId`, `request`, `files`,
and `summary`; the last three hold the same records defined above. Serialization
must not silently discard file records to fit memory. Spool within declared limits
or recommend JSONL before failing; stdout is either a complete envelope or an
explicitly unsuccessful/incomplete stream. A transport failure can truncate JSON.

| File state | Meaning |
| --- | --- |
| `read` | Requested read completed; snapshot still reports its actual coverage. |
| `previewed` | Applicable effects were resolved; no target publication. |
| `committed` | All required write/finalization checks passed. |
| `unchanged` | A valid effect was already satisfied; no rewrite/backup. |
| `skipped-policy` | An explicit conflict/selection policy kept the destination; not proof of synchronization. |
| `refused` | Capability, policy or per-file preflight prevented the operation. |
| `conflict` | A bound input/destination is stale or changed before publication. |
| `failed` | Read, verification or other non-publication work failed. |
| `failed-before-publish` | A mutation failed without imageinfo publication. |
| `cancelled-before-publish` | Cancellation prevented this unit's publication. |
| `unattempted` | A known input was not attempted after a prior stop/failure. |
| `recovered-original` | Recovery established original/expected-absent state; mutation was not replayed. |
| `recovery-required` | Publication or required guarantees remain uncertain; inspect owned artifacts. |

If a reader returns available fields alongside a required-read error, its state is
`failed` with a partial snapshot. If a user explicitly selected a partial/fast read
mode and its declared guarantees were met, `read` can have partial coverage. The
mode and omission issue are visible. Missing values under incomplete coverage never
become success assertions of absence.

## Exit algorithm

Evaluate this table top to bottom. It refines the earlier status meanings; it does
not mirror ExifTool's status numbers. “Succeeded” means `read`, `previewed`,
`committed`, `unchanged`, or `recovered-original` for the operation being requested.
The last means a recovery request succeeded, not that the original edit succeeded.

| Order | Condition | Exit |
| --- | --- | --- |
| 1 | Any unit has recovery uncertainty or failed required post-publication verification/persistence | 5 |
| 2 | Request interrupted/cancelled after safe unit handling | 130 |
| 3 | Whole-request syntax, configuration, input-document or global policy preflight invalid | 2 |
| 4 | Output transport failed (including broken pipe) | 1 |
| 5 | At least one unit succeeded, and at least one failed/refused/conflicted or a dependency group remains incomplete | 3 |
| 6 | No unit succeeded and any bound input/destination conflict occurred | 4 |
| 7 | Any other failed/refused input, failed artifact/verification, incomplete group, or empty selection without explicit allowance | 1 |
| 8 | No earlier condition, but warnings-as-errors rejects a warning | 1 |
| 9 | All requested work satisfied, including permitted empty selection or explicit policy skips | 0 |

Whole-request invalidity is determined before applying any unit; a stream claiming
both that state and committed units is invalid. Known per-file capability refusals
are per-file failures, not syntax errors. Default mutation preflight refuses the
batch before any writes if such a failure is known; eligible units are unattempted,
and exit is 1 (or 4 for a bound conflict). Explicit continue allows independent
eligible units; it cannot authorize an unsafe unit or broken dependency group.
An unattempted unit without a reported stop, interruption or incomplete dependency
reason is an inconsistent result, never implicit success.

Stop-on-error can still yield exit 3 after earlier runtime successes. Cancellation
with committed units returns 130 unless uncertainty requires 5. Neither status
means rollback. Explicit policy skips alone may return 0 with skipped counts;
the result must not say “all synchronized.” Warning policy changes status, never
rewrites a committed file's state to failed or replays it.

On broken stdout, stop scheduling work, finish the in-flight mutation safely or
record recovery-required, and preserve durable outcomes. Return nonzero when the
process can report it; write a bounded stderr diagnostic. Forced termination may
prevent a summary or controlled exit. Consumers require both an acceptable process
status and the final `outputComplete: true` summary before calling a stream complete.
They must not treat missing records as evidence of no changes; inspect durable
batch/recovery records before retrying mutations.

## Example: whole-request error

This is a complete proposed JSON envelope for an invalid privacy option. No input
was discovered and no source was read. It deliberately has no metadata payload.

```json
{
  "schemaVersion": 1,
  "requestId": "example-invalid-1",
  "request": {
    "schemaVersion": 1,
    "kind": "request",
    "requestId": "example-invalid-1",
    "operation": "privacy scrub",
    "mode": "preview",
    "issues": [{"code":"INVALID_OPTION","severity":"error","message":"Unknown option --erase-everything. See imageinfo privacy scrub help.","inputId":null,"path":null,"occurrenceRef":null}]
  },
  "files": [],
  "summary": {
    "schemaVersion": 1,
    "kind": "summary",
    "requestId": "example-invalid-1",
    "exitStatus": 2,
    "selectionComplete": false,
    "counts": {"discovered":0,"excluded":0,"deduplicated":0,"byState":{}},
    "artifacts": [],
    "issues": [],
    "interrupted": false,
    "outputComplete": true
  }
}
```

`outputComplete` means the report finished, not that selection or the operation
succeeded. With valid JSON output selection, preflight errors use this envelope.
If output mode itself is unknown, use bounded plain stderr and exit 2; do not guess
a serialization format. Help remains text even alongside a valid `--output json`.

## Codes needed by these walkthroughs

| Code | Condition and next step |
| --- | --- |
| `INVALID_COMMAND`, `INVALID_OPTION`, `MISSING_ARGUMENT`, `INVALID_INPUT_DOCUMENT` | Fix syntax/document using the nearest help node. |
| `INTERACTION_REQUIRES_TTY` | Use the exported noninteractive command/request. |
| `TAG_AMBIGUOUS`, `PAIRING_AMBIGUOUS`, `SYNC_CONFLICT` | Inspect alternatives; choose an exact intent, explicit pairing or conflict policy. |
| `CAPABILITY_UNSUPPORTED`, `STORAGE_PROFILE_UNVERIFIED` | Inspect format support; explicitly choose a separately supported workflow. |
| `PLAN_STALE`, `DESTINATION_EXISTS` | Inspect current inputs/destination and make a fresh plan. |
| `LIMIT_EXCEEDED`, `OUTPUT_INCOMPLETE` | Review limits or transport; inspect durable mutation state before retrying. |
| `RECOVERY_REQUIRED` | Inspect the named owned transaction; preserve artifacts. |
| `PRIVACY_RESIDUAL`, `PRIVACY_UNINSPECTABLE` | Review the actual checked scope; do not claim anonymization. |

These codes are proposed stable identifiers for this set of scenarios, not an
exhaustive error taxonomy. Product releases will version the actual result schema
and full code catalog before scripts depend on them.
