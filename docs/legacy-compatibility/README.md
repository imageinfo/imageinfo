# RAW compatibility recommendation


Subsequent #0019 implements a [limited CLI foundation](../foundation/README.md).
The broader examples/requirements below retain their proposed status; media parsing
and full result/CLI compatibility are not established by foundation help/version.
[#0037](native-json-errors.md) implements the scoped native JSON syntax-error routing
cell with actual executable tests; other compatibility gaps remain open.
[#0057](read-request-result.md) supplies a bounded in-process metadata-read
request/result path with native tokens and caller-owned JSON transport.
[#0052](read-argument-order.md) qualifies the finite implemented native argv
surface. [#0056](r5-date-mapping.md) maps the bounded date family to actual lookup
and refusal behavior. The [#0054 extension boundary](executable-extension-boundary.md)
remains a proposal. [#0058 session framing](read-session-framing.md) supplies the
v1 wire contract; [#0112](read-session-library.md) implements its bounded
caller-owned library runtime. A CLI process entry, OS-pipe lifecycle and broader
session compatibility remain open.
[#0059 native path qualification](native-paths.md) separately exercises a finite
set of native argv and declared shell paths; it does not establish all-shell parity.

Status: **proposal for review**, `2026-10-10.1`, card **#0007**. Source observation
date: **2026-10-10**. Baseline: ExifTool source 13.59 at commit
`2200871d9cef988051d2a99d67df3bda6cbb30a8`, not a claim about the latest release.
No reference executable, imageinfo implementation or real-media comparison ran.

This recommendation addresses OD-01, OD-02 and OD-07. It preserves eventual full
functional parity while prioritizing EOS R5 full RAW CR3, paired XMP and stored
previews. It chooses no language, library, plugin mechanism or internal architecture.

- [Surface ledger](surface-ledger.md): every existing MAP family and explicit gaps.
- [Migration and expressions](migration.md): worked examples and trust boundaries.
- [Integration contract](integration.md): request files, persistent framing and API use cases.
- [Request schema](request.schema.json) and [result schema](result.schema.json): proposed external records.
- [Validation and handoff](validation.md): synthetic checks, sources and remaining evidence.

## Recommendations for review

**LEG-001 — Functional parity first.** Recommend a native interface plus a
nonexecuting migration assistant. Do not advertise an ExifTool drop-in executable,
Perl API compatibility or a replacement that accepts arbitrary old scripts.
Exact legacy syntax/output compatibility remains a separately scoped future mode.
This is a recommendation, not an accepted change to the long-term parity goal.

**LEG-002 — Translation is a report.** `compat translate --request-file <file>`
accepts a versioned `legacy-invocation` containing already separated argument
strings and an explicit working directory. It does not parse a shell command line,
expand globs/environment variables, load configuration, follow argument files or
execute callbacks merely to understand them. The input is data.

Return the source tokens, per-token/interaction findings, proposed native request
when complete, changed behavior and manual questions. Every token must be accounted
for, including an option's value and its order. Unknown or ambiguous syntax prevents
a runnable suggestion; never silently drop a flag. Report `complete-with-differences`,
`needs-input`, or `unsupported`, with diagnostic codes. A complete suggestion is still
a preview, not authorization to edit. Native command export uses token arrays;
shell-specific quoted text is a separate display convenience.

Translation returns status 0 for a complete report with a usable preview suggestion,
1 for needs-input/unsupported, or 2 for malformed invocation data. No media operation
ran in any of these cases. Its report schema remains part of LG-002; the CLI result
schema supplied here is not a claim that every future serializer is already specified.

**LEG-003 — No automatic compatibility execution.** Native commands reject legacy
flags instead of guessing. A translator recognizes mutation intent before producing
any suggestion. Empty legacy assignment must not become an empty native string;
value conversion, preferred destination, list operations and time shifts must be
resolved against typed, location-specific definitions. When those facts need actual
media, return needs-input and identify the requested evidence. Importing a reference
tool's report is not an executable mutation plan.

**LEG-004 — Order and lifetime are observable.** Preserve source-copy ordering,
argument expansion position and request boundaries in the translation report.
Expose any difference between a sequential legacy operation and a native immutable
snapshot. Do not rearrange a multi-command request into a single write unless its
effects are proven equivalent. Unknown ordering interactions remain unresolved.

**LEG-005 — Report formats are distinct contracts.** Native JSON/JSONL embeds the
metadata model and uses the [CLI envelope](../cli-walkthroughs/results.md). It is not
ExifTool JSON with renamed flags. A requested legacy serializer must specify exact
duplicates, grouping, arrays, language, formatting, binary, encoding and omission
behavior independently. Until then its ledger row remains open. Do not claim an
output is native XMP merely because it is XML.

**LEG-006 — Data extensions before executable extensions.** Recommend explicit
versioned data definitions for custom XMP namespaces/fields, aliases and bounded
declarative calculations. Definition provenance, native keys, type/encoding,
dependencies, collision policy and capability restrictions must be visible.
Extensions cannot shadow built-ins silently, mark a RAW writer safe, or grant their
own permission to mutate. Reject dependency cycles and unbounded nesting/work.

Loading a RAW parser or implementing an arbitrary conversion function is different
from declaring a name. Arbitrary legacy Perl/config/module execution is unresolved
future functionality, not a promised sandbox or initial runtime dependency. No
executable code is auto-discovered from a photo directory or request document.
Choosing a trusted-code extension model requires a later explicit design decision.

**LEG-007 — Ordinary filtering is bounded and pure.** The initial filter proposal
in [migration](migration.md) supports exact typed comparisons and Boolean composition.
No shell, network, filesystem reads, dynamic evaluation, loops or implicit conversion
callbacks occur inside a filter. Parameters are values, not executable fragments.
Unknown/partial metadata does not quietly become false or absent. Advanced arbitrary
expressions remain visible in the parity ledger instead of being mislabeled equivalent.

**LEG-008 — APIs expose the same operations.** The eventual library should support
read snapshots, select/project values, discover definitions/capabilities, construct
intents, preview/apply and inspect recovery. Inputs, ownership, errors and cancellation
must be explicit. Reusing an operation description is allowed; hidden queued edits
must not leak into a later read or unrelated target. Choose names/types in the
eventual language's ordinary idiom rather than copying ExifTool methods/classes.

**LEG-009 — Persistent transport has separate success semantics.** Recommend a
local standard-input/output JSONL session with bounded records, explicit IDs,
request-local settings and per-request summaries. A ready marker does not imply
successful work. Session transport status and each request's operation status are
different; see [integration](integration.md). No server, network endpoint, event bus,
database or general RPC framework is required by this proposal.

**LEG-010 — Schemas constrain data, not authority.** Schema-valid requests, metadata,
results and plans are untrusted boundary data. Recompute source bindings, capabilities,
limits and WS guards from trusted current inputs. Resolve local schema references
without fetching URLs at runtime. The schemas do not establish cross-reference
integrity, filesystem safety or an implementation architecture.

## Source facts that matter

The pinned CLI documents assignment/delete/copy syntax, ordered execution and a
line-oriented stay-open facility. Its documented exit convention differs from the
native proposal. Configuration/module effects can persist across execute boundaries.
These are source observations, not measured behavior on R5 media.
[Application manual](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/exiftool_pod.html).

The library documents extraction separately from queued write values. SetNewValue
queues changes that can survive multiple WriteInfo calls; SaveNewValues and
RestoreNewValues preserve that queue state. GetValue exposes several conversion
views. The native proposal deliberately makes those lifetimes/views explicit.
[API reference](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/lib/Image/ExifTool.pod).

The configuration example includes custom definitions, shortcuts and computed
values with executable expressions. Reading its syntax as documentation does not
authorize executing or importing it. [Configuration example](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/config_files/example.config).

The source review used the pinned files, including direct read-only retrieval when
web retrieval failed. No upstream code, complete tag tables, configuration or media
assets are included in this deliverable. MIT remains the imageinfo license; separate
artifact provenance work remains #0010.
