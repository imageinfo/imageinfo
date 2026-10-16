# Native token and API-option inventory

2026-10-16, #0121. The [versioned inventory](native-token-inventory.v1.json)
freezes the existing native RAW interface and a finite pinned-reference denominator.
It records all **32 MAP families**, **39 API method headings**, **87 CLI option
detail headings**, **102 distinct API option identifiers**, and **12 SetNewValue
option identifiers**. These are inventory counts, not supported-feature or parity
percentages. No difference is accepted by recording it here.

The source baseline is ExifTool **13.59**, commit
`2200871d9cef988051d2a99d67df3bda6cbb30a8`, observed from the retained source on
2026-10-16. The manifest records exact file hashes and pinned links to the
[application source/manual](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/exiftool),
[API reference](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/lib/Image/ExifTool.pod),
and [API option registry](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/lib/Image/ExifTool.pm).
Only identifiers and syntax are transcribed; upstream prose, implementation and
tag tables are not imported. This is a pinned observation, not a latest-release claim.

## Denominator and residual rules

The CLI denominator is each `=item` in the application manual's **Option Details**
section, including the continued discovery heading. A heading can contain several
aliases, value forms or numbered families. Its complete identifier syntax remains
one inventory row. Selection/assignment metasyntax is retained as metasyntax, not
expanded into infinitely many tag names. Special tags, filenames, wildcard
languages and every possible value are not extra option headings.

The API method denominator is each `=head2` under **METHODS**, ending before
**CHARACTER ENCODINGS**: 39, including static entries. Encoding headings are not
methods. The API option denominator is the union of 97 **Options** parameter
headings and 99 entries in `@availableOptions`: 102 distinct identifiers after
normalizing documented `NoWarning[+]` to `NoWarning`. `BlockExtract`, `GeoDir`
and `NoDups` occur only in the documented list; `Debug`, `EncodeHangs`, `List`,
`ListSep` and `XMPShorthand` occur only in the registry. Their omission from one
source is retained explicitly; no implementation inference resolves the mismatch.
The 12 **SetNewValue** options are separate. **SetNewValuesFromFile** documents
inheritance of that set with different defaults and per-tag handling, not 12 new
names or identical behavior.

Every row retains a residual. `current-RAW-unresolved` means some semantics,
compatibility, implementation or qualification remains for the current RAW scope;
it does not demand that an upstream spelling be implemented. `deferred-breadth`
is used only for explicitly document/ID3/RIFF-specific API options and the CLI
password option. Mixed-purpose headings remain current-RAW unresolved so their
relevant portion cannot disappear into a breadth deferral. #0015 retains current
residuals and #0012 retains eventual breadth. The separate
[delivery matrix](delivery-matrix.md) assigns bounded requirement owners; this
inventory does not replace that disposition or create new tickets.

The [surface ledger](surface-ledger.md) supplies the original 32 family identities
and all 39 method names. Each family row here preserves the fuller surveyed forms
from the [capability inventory](../inventory/canon-eos-r5-cr3.v1.json), adds a
source-reviewed native observation and leaves its residual explicit. Each API
option is independently classified and linked to a family. Legacy CLI forms have
no compatibility mode in the current parser; the shared `--` terminator is
explicitly recorded as an actual native token. A similar native operation does not
establish accepted equivalence or a measured reference difference.

## Actual native surface

The manifest binds the reviewed production source revision and hashes. Its `native`
object gives exact command paths, every declared long option, finite value enums,
all 20 canonical selector names, two selector-name aliases, eight namespace
spellings, request limits and session fields. The implemented commands are:

| Command | Implemented boundary |
| --- | --- |
| `help [COMMAND...]`, `version` | Contextual help and current version/scope; no media operation. |
| `metadata read INPUT...` | Partial R5 full-RAW read, repeatable exact selectors and four native value views; at most 16 inputs. |
| `binary list INPUT...` | Stored preview resource descriptions; same read limits. |
| `binary extract INPUT` | One of three stored preview names to a required fresh output path, or dry-run; no JPEG decode. |
| `preview date-time-original INPUT` | Exact Gregorian ASCII20 advisory intent with optional allocation offset assertion; no apply. |
| `sidecar pair INPUT` | Explicit existing sidecar path association; no content parsing or creation. |
| `session read` | Fixed v1 read/close JSONL over stdin/stdout; no CLI output selector. |

Common options are declared at each command scope, not globally propagated.
`--output` and `--color` may each appear once across the invocation. Help validates
the full grammar first. `--interactive` is recognized but refuses guided execution;
it conflicts with `--no-interactive`. `--color` is a presentation preference and
currently does not color plain output. These are recognized controls with explicit
limits, not evidence of menu/color functionality. Short option aliases are not
declared. `--` protects literal operands; it does not load an argument file.

Selectors are case-sensitive canonical names with only the two named aliases.
Namespace spelling aliases are finite. A selector retains every matching observed
occurrence in source order; it does not implement wildcards, exclusions, sorting,
general discovery or arbitrary group-family queries. Raw/normalized values use the
declared native snapshot representation; they are not promises of upstream `-n`
or exact byte-stream equivalence. See the actual
[read JSON subset](native-read-json.md) and [argument qualification](read-argument-order.md).

`read_request::execute` accepts native `OsString` tokens without argv[0], parses
the same CLI grammar, and then admits only `metadata read`. It owns JSON transport,
rejects `--output` before `--` even in attached form, and caps requests at four
inputs and 8 MiB metadata budget per input. Help/version/other operations refuse.
`--interactive` refuses during parsing; presentation flags do not enable new API
operations. Relative paths use the caller process's working directory.
`write_result` writes bounded JSON plus LF and flushes the caller-owned sink;
in-memory success cannot establish successful transport.

`read_session::run` is a separate caller-owned buffered I/O runtime. Its Unicode
token arrays reuse that narrower request API, with exact v1 read/close members,
bounded frames and request-local state. CLI startup exposes that runtime without
adding persistent upstream options, shell parsing or legacy ready markers.
See [request/result](read-request-result.md), [session library](read-session-library.md)
and [session process](read-session-process.md) for existing verification. Public
reader, snapshot, selector, preview, saved-plan, source-revalidation and pairing
functions remain typed Rust functions; this inventory creates no upstream ABI,
method overload or universal API-option compatibility.

## Verification and limits

Run `python scripts/check_native_token_inventory.py`. With a lawful retained
checkout, add `--upstream-root PATH` to verify all three upstream hashes and
re-extract the documented headings/registry. The checker verifies closed counts,
all 32 family identities/forms, all 39 method names, explicit residual classes,
unique identifiers, native source hashes, declared long options and selector names.
It does not infer semantics from regex matches: native observations above and in
the manifest come from review of parser, request/session and reader dispatch.

This handoff ran source/inventory validation and documentation checks only. No
reference executable, camera media, mutation, comparative output, cancellation or
performance experiment is claimed. Abbreviations, undocumented CLI parser branches,
option values/overloads, ordering interactions and signatures remain explicitly
unqualified under LG-001/LG-006. The freeze supplies #0122/#0123/#0125/#0129/#0134
and #0141 with a stable existing-surface denominator; their positive evidence and
all production storage/RAW mutation gates remain separate.
