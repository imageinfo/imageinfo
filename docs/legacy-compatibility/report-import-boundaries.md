# Finite report and inert import boundaries (#0126)

This contract selects the existing native metadata JSON as the exact reporting
profile and proposes two data-only scalar intent encodings. The latter have no
application importer. The [16-profile matrix](report-import/profiles.v1.json),
[inert JSON schema](report-import/intent.schema.v1.json) and
[authored vectors](report-import/vectors.v1.json) are specification/model evidence.
They add no CLI option, report renderer, import execution or mutation authority.
The selection is ordinary authorized engineering, with no renewed adoption gate.

`supported` means an existing bounded native surface with the linked evidence;
`unimplemented` means a required positive capability remains open; `refused` in
the model means a particular input violates the proposed profile. A model refusal
does not claim that the CLI implements that refusal or completes the positive
capability. Unsupported cases remain requirements in #0015/LG-002, LG-006,
GAP-006 and GAP-012. No permanently deferred report family is introduced.

## Profiles and next bounded outcomes

| Profile | Current status and contract | Next bounded schema/evidence outcome |
| --- | --- | --- |
| Native JSON | Supported finite R5 metadata snapshot and result envelope; occurrence arrays, typed exact layers and partial coverage. | Continue actual emitted-output schema/semantic qualification under #0053/#0127; richer shapes require separately evidenced profile revisions. |
| Native plain text | Supported human read output: quoted path heading, namespace/name, source ordinal and selected value text. It is a presentation, with no decoding/import grammar. | Retain terminal observations and add exact authored control/escaping/value projection records before any machine-consumer promise. |
| Legacy JSON | Unimplemented compatibility renderer; native JSON is a different protocol. | Define a closed projection schema and collision/duplicate/group/numeric/binary vectors, then compare actual pinned-reference/native outputs. |
| Legacy CSV | Unimplemented compatibility renderer. | Define header/order, occurrence cells, list separator, quoting/newline/charset and missing-cell schema; compare actual authored outputs. |
| Legacy XML | Unimplemented compatibility renderer; native XMP inspection is a separate input operation. | Define exact namespace-expanded element/attribute, duplicate/list/language and escaping schema; compare actual authored outputs. |
| Legacy short | Unimplemented short-level compatibility renderer. | Define each short-level label/value/order grammar and ambiguous-label vectors, then actual output comparison. |
| Legacy plain | Unimplemented legacy presentation compatibility; native plain does not establish equivalence. | Define aligned labels, group selection, escaping and repeated-value transcript grammar; compare actual outputs. |
| Legacy args | Unimplemented report/replay serializer. | Specify bytes/newlines/quoting and inert token records; test embedded option-looking data without replaying it. |
| Legacy PHP | Unimplemented PHP-shaped report serializer. | Specify a data grammar, typed values, escaping and duplicate keys; validate without a PHP interpreter. |
| Legacy plot | Unimplemented plotting report. | Specify data/domain/ordering, missing samples and output asset schema; compare authored deterministic plots/data without claiming rendering parity. |
| Templates | Unimplemented template renderer; no expression or callback evaluator is selected here. | Define a nonexecuting placeholder AST, escaping and missing/ambiguous lookup vectors before rendering implementation. |
| Filename placeholders | Unimplemented filename formatter; pairing/path resolution is not formatting. | Define a pure component-result schema, counter/extension/width rules and collision/path-separator refusals; no filesystem effect. |
| Inert JSON intent | Unimplemented product importer; proposed closed scalar-set schema below. | Use this schema and model vectors for a future decoder producing only nonexecuting intents and per-row diagnostics. |
| Inert CSV intent | Unimplemented product importer; exact rectangular grammar below projects to the same scalar intent model. | Qualify a future decoder against JSON/CSV equivalence, lexical negatives and all-or-nothing row matching. |
| Legacy JSON import | Unimplemented `-j=`/SourceFile adapter; arbitrary native snapshots are not intent input. | Specify exact pinned-reference SourceFile/wildcard/duplicate semantics and explicit loss diagnostics before an inert adapter. |
| Legacy CSV import | Unimplemented `-csv=`/SourceFile adapter. Empty cells never silently delete. | Specify reference missing/empty/header/duplicate/encoding semantics and explicit target matching before an inert adapter. |

The machine matrix assigns every profile every rule dimension. The shared
`native-exact`, `native-display`, `legacy-open` and `inert-scalar` rule sets are
closed contracts, not claims of cross-format equality. Existing evidence is
[native JSON](native-read-json.md), [operation result profiles](result-profiles/read.schema.v1.json),
[plain terminals](plain-terminals.md), the [surface ledger](surface-ledger.md)
and the [complete delivery matrix](delivery-matrix.md). Existing source establishes
native text details in `src/read_request.rs`; no new upstream experiment is claimed.

## Exact native and legacy boundaries

Native JSON keeps distinct occurrences with exact namespace/native tag identity,
indexed paths and source ordinal. Group labels do not replace that identity.
Arrays in the envelope are occurrence/resource tables, not evidence that list-valued
metadata or language alternatives are supported. Generic list/structure/lang-alt
metadata is outside the bounded R5 snapshot profile. Integers use canonical
unsigned decimal strings; rational pairs stay unreduced. Binary uses source-range
resource references, with no inline/base64 payload. UTF-8, JSON escapes and valid
Unicode scalars apply; invalid JSON members, duplicate member names, trailing
documents and nonfinite numbers fail the native-profile validator.

Omitted occurrences do not prove absence under partial coverage. Empty text,
invalid value, unavailable display, null hash and absent occurrence remain distinct.
Missing required members violate the schema; optional omissions follow that exact
schema. Display locale is `en`, timezone null; it is not an import value. Source
display paths are labels and can be lossy for native non-Unicode paths. Neither
report paths nor snapshot IDs authorize target reopening, matching or writing.

Native plain emits occurrences separately in reader order and includes ordinals,
but has no complete machine identity/value-state schema. Its rational `n/d`,
integer and checked ASCII strings differ from display projection; `--values all`
labels raw/normalized/display. Binary is an extent description. A missing printed
row or empty printed value cannot serve as delete/null/absence syntax. No locale,
list separator, legacy short level, filename or template parity is inferred.

Every legacy profile currently refuses translation into a supported exact profile
when doing so would flatten duplicate occurrences, erase groups, join lists,
choose a language, stringify binary or coerce numbers without an explicit loss
record. This is a specification refusal, not a new runtime error. In particular,
the existence of JSON/CSV syntax does not select legacy empty/null/omitted/missing
or SourceFile matching semantics. Each positive legacy serializer/adapter must
define those cases and preserve/report losses before any equivalence claim.

## Proposed scalar intent v1 (JSON and CSV)

The model accepts only a nonempty ordered batch of at most 64 existing-occurrence
`set` requests, across at most 16 explicitly supplied binding keys. The complete
UTF-8 input is at most 1,048,576 bytes; each text scalar is at most 4,096 UTF-8
bytes. These are proposed finite decoder limits, not measured resource policy.
No deletion, append, creation, group creation, list, language alternative, binary,
filename, template, executable expression, callback or external content is allowed.
Unknown fields/version/operations/types refuse the entire batch.

The caller supplies a separate immutable observation table. Each `sourceKey`
selects exactly one table entry; `snapshotId`, `occurrenceId`, `namespace` and
`nativeId` must match exactly, case sensitively, without trimming, normalization,
glob, basename, path, SourceFile or positional fallback. The table retains the
full document/path/ordinal identity. An ambiguous/missing table binding or
occurrence refuses. No duplicate `(sourceKey, snapshotId, occurrenceId)` edit is
allowed, even for equal proposed values. Same-named tags in different namespaces
or distinct occurrence IDs remain separate. Input row order is retained.
Binding entries must have unique source keys and snapshot IDs, preventing two
keys from aliasing the same snapshot; each entry has unique occurrence IDs.
Every identity field has 1–256 Unicode scalar characters, except `sourceKey`,
which has 1–64 ASCII letters, digits, underscores or hyphens.

The model accepts canonical `u64` integer decimal strings, unreduced `u32`
rational numerator/denominator strings with nonzero denominator, and Unicode
scalar strings. Signed, floating, exponent and numeric JSON forms refuse.
An empty string is an explicit set-to-empty intent; it is never omission, null or
delete. Null values, missing required fields, unknown fields and unavailable/
invalid/display-only input values refuse. Unicode text receives no normalization;
non-ASCII text can pass this abstract encoding contract while actual destination
format feasibility still refuses elsewhere. Literal shell/template/code text is
data; no interpreter receives it. Text that resembles a CSV formula stays exact
data and must not be opened as an executable spreadsheet by the checker.

JSON is one strict UTF-8 document without BOM, duplicate object members, unpaired
surrogates, nonfinite numbers or trailing data. The fixed root fields are
`schemaVersion: 1`, `kind: inert-scalar-intents` and `edits`. Each edit has fixed
identity fields, `operation: set` and a typed `value`. The schema is closed.

CSV has this exact ASCII header, one field per cell, in this exact order:

```text
sourceKey,snapshotId,occurrenceId,namespace,nativeId,valueKind,decimal,numerator,denominator,text
```

It is strict UTF-8 without BOM; record terminators are CRLF, including the final
record. Comma delimiter and double-quote quoting apply: a quoted quote doubles;
commas, quotes, CR and LF require quoting. Quoted fields can contain CR/LF.
Unquoted quotes and data after a closing quote refuse. Every row has ten fields;
no comments, blank records, duplicate/missing/reordered headers or extra columns.
The version/profile is selected out of band as inert CSV v1, never sniffed from
an arbitrary file. Integer fills only `decimal`; rational fills only `numerator`
and `denominator`; string fills only `text`. Unused cells must be empty. Empty
`text` is therefore representable and distinct from a missing cell; empty numeric
cells refuse. CSV has no null sentinel and no implicit deletion. Cells are never
trimmed, coerced, split on list separators or interpreted as formulas/options.

Both transports either produce the same nonexecuting ordered intents or refuse
the entire batch with a row-local reason; neither performs partial application.
There is no silent loss path or loss acknowledgement escape in v1. Any requested
conversion needing a loss report belongs to a future explicit adapter schema.
Matching a table is only local observation identity. It supplies no live object
guard, freshness, content revalidation, privacy guarantee or source/destination
admission. Actual format, coupling, planned effects, storage, caller authority and
publication requirements remain independently required.

## Verification and remaining work

Run `python scripts/check_report_import_boundaries.py`. This dependency-free
checker validates the matrix denominator, rule coverage, local evidence paths,
schema vocabulary and authored strict lexical/typed/matching/equivalence cases.
It is a test-only model of trusted authored strings and observation tables, has
no CLI import entry point, opens no media, and performs no target effects.
It does not establish legacy serializer/reference parity, actual decoder
integration, streaming/error transport, measured limits or positive write admission.
The full report/import/template/filename residuals stay in #0015; the next bounded
outcomes above name evidence to prepare, not arbitrary new successor tickets.
