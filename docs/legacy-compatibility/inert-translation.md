# Inert legacy-invocation translation contract

2026-10-16, #0129. This freezes the finite `mig-001-012-inert-v1` report
contract against [#0121's actual native surface](native-token-inventory.md)
and the twelve [MIG examples](migration.md). It follows the already accepted
#0007 inert reporting direction; there is no renewed human adoption gate.
The [invocation schema](inert-translation/invocation.schema.v1.json),
[report schema](inert-translation/report.schema.v1.json) and
[authored vectors](inert-translation/vectors.v1.json) are specification evidence.
The accompanying checker validates authored data and invariants. **No production
translator, `compat translate` CLI, legacy decoder or media operation is implemented
by this ticket.** #0130 owns that separate finite runtime.

The old migration table describes proposed workflows. Its `metadata delete`,
`metadata write`, `--recursive`, `--output jsonl` and `batch run --stream`
spellings are unavailable in the actual native CLI. They must not appear as usable
suggestions. Production `session read` exists, but uses native v1 read/close frames
and does not emulate ExifTool's argument stream or ready markers. This contract
records those distinctions rather than treating a proposal as implemented.

## Input and validation boundary

Input is one UTF-8 JSON object with exactly `schemaVersion: 1`,
`kind: "legacy-invocation"`, a caller `id`, `pathStyle`, `workingDirectory`
and `arguments`. `pathStyle` is `posix` or `windows`; it describes the source
invocation's path syntax without changing the host's directory. The directory is
explicit and absolute: one leading `/` for POSIX, drive-rooted `C:\...` or
`\\server\share\...` for Windows. Drive-relative, current-drive-root-relative,
relative and mismatched-style directories refuse. No directory existence,
permissions, current identity or actual file support is asserted by the string.

`arguments` omits argv[0] and is already tokenized by the caller. It begins with
a legacy option in this finite profile. Executable-name/path input is malformed.
Do not split a command string, parse shell quoting, expand wildcards, substitute
environment variables, normalize path spelling or evaluate shell metacharacters.
`$HOME/*.cr3`, `$(literal)` and `;literal` are data. An empty **argument string**
is malformed in this profile; the valid attached empty value in `-Label=` is
distinct and remains deletion intent. Non-Unicode OS token sequences are outside
this UTF-8 contract, not silently replaced.

Reject duplicate JSON members, unknown members, wrong types/version/kind, BOM,
invalid UTF-8, unpaired surrogate escapes, NUL, trailing JSON/data and excess
limits before translation. Object member order has no semantic meaning; argument
array order does. JSON `null` is not an argument string. Do not coerce values.

| Limit | Frozen maximum |
| --- | --- |
| Invocation encoded UTF-8 document, including whitespace | 131,072 bytes |
| Container nesting, outside JSON strings | 8 |
| Caller ID | 1–128 UTF-8 bytes |
| Working directory | 1–32,768 UTF-8 bytes |
| Arguments | 1–128 strings |
| Each argument | 1–32,768 UTF-8 bytes |
| Sum of argument UTF-8 bytes | 65,536 |
| Encoded report | 1,048,576 bytes |

JSON Schema string lengths count Unicode scalars, not encoded bytes; byte limits,
absolute-path syntax and cross-field invariants below are mandatory companion
checks. Schema validity alone is insufficient. #0130 must enforce document/depth
bounds before unbounded decoding/allocation; the test checker's whole-buffer oracle
does not prove bounded production I/O. No output may be truncated into apparent
success. Oversize invocation data yields malformed; an internal inability to form
the bounded report is a runtime failure, never a usable partial suggestion.

Opening the caller-supplied invocation document in a future explicitly selected
entry point grants **only** data decoding. Paths inside it are never followed.
Media, config, argument files, stdin argument streams, JSON/CSV import files and
source-copy operands stay unopened. There is no `stat`, directory walk, subprocess,
network fetch, callback, filter evaluation or native request execution. Selection
of a future import/report profile cannot make an unsupported suggestion runnable.

## Report fields and total accounting

A report has the exact schema-versioned fields in the report schema. `request`
echoes the validated invocation losslessly at the JSON value level; it does not
claim preservation of JSON whitespace, escape spelling or object member order.
`accounting` contains exactly one entry per source argument, in its original
zero-based order. Indices are integers and never occurrence-elided. Duplicate
tokens each receive their own entry. A token is never silently dropped, merged,
deduplicated or reordered.

Each accounting entry repeats the exact token and records `role`, `valueOwner`,
`parts` and `findingIds`. Roles are `option`, `option-value`, `operand`,
`terminator` or `unknown`. `parts` cover the entire token exactly once, contiguously,
using half-open Unicode scalar offsets `[start,end)` and the exact substring.
Parts are `syntax`, `value` or `literal`. An attached empty assignment has an
explicit zero-length trailing `value` part. `-G1` has syntax `-G` and value `1`;
`-Subject+=travel` has syntax `-Subject+=` and literal value `travel`. No list or
date semantics are inferred by retaining their spelling.

`valueOwner` points to the same index for attached values and the immediately
preceding option for a separate value. The option remains independently accounted.
Tokens without value parts use null. `source.cr3` in MIG-006 belongs to
`-tagsFromFile`; `target.cr3` remains a target operand. `True` belongs to
`-stay_open`, and `-` belongs to `-@`. Config and expression strings are linked
to their options, not interpreted. All findings have unique IDs and valid source
indices; every accounting entry names at least one finding covering its index.
Questions likewise name only existing indices. Whole-request/order findings can
cover several indices while preserving each original token entry.

`findings` carry diagnostic codes and explain token meanings, unsupported syntax
and interactions. `differences` describe changes to occurrence selection, native
value/serialization policy, lifetime or effects. `questions` ask for concrete
missing intent/evidence; they do not authorize file access. `prerequisites` give
the actual absent operation/input/contract and its existing owner. Recording a
question cannot hide a known missing production writer. Owner identifiers are
traceability, not proof that an operation is admitted or that its ticket is done.
All four code-bearing fields share the finite vocabulary below, enforced by the
schema's `diagnosticCode` definition and independently by the companion checker.
`MALFORMED_INVOCATION` identifies invocation preflight failure, including decoding,
shape and bounds failures; its finding has no inferred token indices. Codes are
stable for this profile as retained in the vectors; messages are human explanations,
not executable directives. Empty or unknown codes refuse. Adding a code requires
a profile revision before interoperability claims.

```text
APPEND_UNAVAILABLE                BLANKET_DELETE_UNSUPPORTED
COPY_ALL_UNAVAILABLE              DATE_SHIFT_UNAVAILABLE
DELETE_UNAVAILABLE                DUPLICATE_OPTION
ENUMERATION_REQUIRED              EXECUTABLE_CONFIG_UNSUPPORTED
IMPORT_UNAVAILABLE                MALFORMED_INVOCATION
ORDER_OUTSIDE_FINITE_PROFILE       OVERWRITE_UNAVAILABLE
READ_VIEW_DIFFERENCE               REFERENCED_FILES_UNOPENED
SESSION_PROTOCOL_REQUIRED          UNKNOWN_TOKEN
WRITE_UNAVAILABLE
```

`suggestion` uses `state`, `executable`, `arguments`, `workingDirectory`,
`operation` and `authority`. A usable suggestion is a token array for the actual
`imageinfo` executable, without shell quoting and without argv[0]. Its working
directory equals the source directory. `authority` is always `none-report-only`.
A withheld suggestion has null executable, arguments, directory and operation;
proposed command strings are never smuggled into runnable fields. The four
`effects` flags are always false: media/referenced-file opens, command execution
and authorization are not report effects. A consumer must treat reports as inert
data; do not dispatch on their contents automatically.

## Frozen dispositions and prerequisites

| Case | State | Concrete result or prerequisite |
| --- | --- | --- |
| MIG-001 | complete-with-differences | Existing `metadata read --tag ISO --values normalized -- INPUT`; native matching occurrences and view differ from legacy `-ISO -n`. |
| MIG-002 | unsupported | Production XMP Label deletion, exact destination/preservation and publication are absent (#0015 MAP-010, #0085). Empty assignment never becomes empty-string setting. |
| MIG-003 | unsupported | Label insertion/update, conflict/occurrence policy and publication are absent (#0015 MAP-010, #0085). No upsert equivalence. |
| MIG-004 | unsupported | Typed Subject/list mutation and publication are absent (#0015 MAP-010, #0085); also ask for namespace, target and duplicate/list policy. |
| MIG-005 | unsupported | Date shift and RAW write admission are absent (#0133, #0078); also ask for unit, calendar, shape and offset semantics. Absolute-date advisory preview cannot perform a shift. |
| MIG-006 | unsupported | Enumerated copy mappings, protected-block policy and copy/write operation are absent (#0015 MAP-011, #0078); ask for exact source/destination occurrences. |
| MIG-007 | unsupported | Import decoder/row-target/null policy and target mutation are absent (#0126, LG-002, #0078). `edits.json` stays unopened. |
| MIG-008 | needs-input | Supply an explicit list of at most 16 supported RAW files and choose native JSON semantics (#0122, #0126). No recursive directory or legacy grouped serializer suggestion is formed. |
| MIG-009 | unsupported | Label mutation/publication and original-retention policy are absent (#0085, #0093, #0094). Overwrite intent does not authorize deleting originals/recovery. |
| MIG-010 | needs-input | Redesign the caller for native session v1 read/close/result framing (#0125, #0128, #0116). Existing `session read` is context, not a complete legacy protocol suggestion. |
| MIG-011 | unsupported | Executable config/EXPR automatic translation is unsupported (#0054, #0131, LG-003). No file loading or expression evaluation. |
| MIG-012 | unsupported | Scoped privacy inspection/removal and writer admission are absent (#0087, #0088, #0078). Blanket deletion cannot promise privacy or erase opaque dependencies. |

For MIG-001 the bounded pattern is exactly `[-n, -ISO, INPUT]`, with one literal
nonempty input operand. The sole usable output template is
`[metadata, read, --tag, ISO, --values, normalized, --, INPUT]`. The terminator
protects the original operand even when its spelling begins with a dash.
Unqualified native `ISO` deliberately retains matching observed EXIF/CTMD
occurrences rather than claiming ExifTool preferred-tag selection or silently
narrowing to EXIF. This is an explicitly described workflow difference, not a
measured equivalence. The file is not checked or opened. Later native execution
may refuse unsupported media; a valid suggestion does not establish successful
execution, alias parity, conversion parity or an accepted compatibility delta.

The other eleven examples retain their exact token/value/ordering forms and
literal opaque operands in authored reports; none yields a usable command. The
profile does not implement arbitrary legacy grammar. Unknown options produce
`unsupported` / `UNKNOWN_TOKEN`; unqualified permutations or terminators outside
the finite pattern produce `unsupported` / `ORDER_OUTSIDE_FINITE_PROFILE`.
Repeated options produce `needs-input` / `DUPLICATE_OPTION` unless an independent
unsupported feature already requires `unsupported`. Never apply last-wins,
first-wins or deduplication. Extending the recognized ordering set requires an
explicit profile change and independent evidence. Argument files and import paths
are accounted as values; they are not recursively translated.

## Status and output contract

- `complete-with-differences`, status 0: a real usable native read suggestion,
  nonempty declared differences, no unresolved questions/prerequisites. Still inert.
- `needs-input`, status 1: concrete caller choices can form a bounded native
  workflow; suggestion withheld and actual prerequisites recorded.
- `unsupported`, status 1: an operation, executable behavior or finite mapping is
  absent; suggestion withheld and actual prerequisites recorded.
- `malformed`, status 2: invocation decoding/schema/bounds fail. No validated
  request is echoed (`request: null`), no token accounting or suggestion exists,
  and a diagnostic finding explains the rejection. No prefix translation.

Malformed preflight dominates all content analysis. Otherwise any unsupported
feature dominates needs-input; either dominates completeness. Diagnostics do not
claim unseen tokens were semantically decoded after a preflight failure. The
status numbers describe the proposed translator operation, not any media/tool exit
that occurred during this specification. Report status does not replace separate
transport error handling in #0130.

## Verification and remaining work

Run `python scripts/check_inert_translation.py` with the existing test-only
`jsonschema==4.26.0` dependency. It validates both schemas, all 12 MIG reports,
five extra unknown/duplicate/import/order reports, 24 malformed inputs, seven
positive byte/path/literal controls and 23 deliberately corrupted reports. Ten
code controls cover empty/unknown codes in all four code-bearing fields and in
malformed-report findings; schema and companion validation reject each independently. It
compares all twelve source argument arrays to the historical migration examples,
checks accounting/value/order coverage and native command/selector/view membership,
and patches file-open APIs to fail during pure validation. Fixed public schema,
vector, migration and inventory files are the only checker inputs. No reference
executable, media/config/argument/import file, native command or translator ran.

The model's report checks complement JSON Schema; the schema cannot express every
cross-field invariant. Authored vectors are not an exhaustive legacy parser,
runtime resource proof, real-media comparison or current-format admission.
#0130 retains actual translation/runtime/I/O/transport qualification; #0122 retains
read differences, #0125 session reconciliation, #0126 import/report choices and
#0015 every remaining parity obligation. Storage/RAW/sidecar publication gates and
explicit later caller application remain independent technical boundaries; this
report neither grants them nor creates another human approval requirement.
