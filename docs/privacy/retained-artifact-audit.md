# Explicit retained-artifact privacy report (#0221)

Status: bounded implementation and authored evidence, 2026-10-18. Twelve
authored tests pass, with fresh independent review and passing focused formatting
and denied-warning Clippy checks. This preparation reports
bounded explicitly supplied snapshots; #0090's independent whole-operation
all-artifact acceptance remains open.

## Inputs and report meaning

The separate read-only
[`privacy-artifact-audit`](../../experiments/privacy-artifact-audit/src/lib.rs)
crate consumes the existing parsers and catalog reporter. It does not fork
metadata parsing. A finite expected-slot manifest binds the operation, attempt,
artifact kind, byte length and content identity of each supplied snapshot.
Lineage distinguishes originals, derivatives, backups, partial staging,
recovery material and report artifacts. Requested effects are reported separately
from effects observed in actual supported metadata.

Closed artifact kinds distinguish supported RAW, supported XMP, recognized
previews and opaque/partial/nonmedia/report material. Opaque artifacts retain
uninspectable residuals; they are not blindly parsed as RAW. Unsupported native
roles and nested preview metadata remain incomplete. The report cannot produce
an overall clean or private certification.

The named [catalog](r5-catalog.md) retains all 31 selectors and 59 templates:
18 native, 13 sidecar and 28 per recognized preview. Expansion is per media
unit; the same sidecar must not be counted twice. Document and occurrence
identity, duplicates and per-artifact target retention remain visible.

## Completeness and evidence limits

Declared-set completeness asks whether snapshots match every slot in the supplied
manifest. Independent whole-operation completeness asks whether that manifest
actually enumerates every retained artifact of the operation. The first cannot
establish the second. Unknown omitted external copies are not detectable through
this interface, and caller `removed` or `complete` flags confer no evidence.

Exact hash/length bindings detect conflicts within the declared set. They confer
no live guard, ownership, historical custody or authenticity. Metadata recomputed
through the same parser is labeled accordingly and cannot be counted as
independent format evidence.

Current implementation ceilings are 64 manifest slots and supplied snapshots,
256 MiB aggregate declared bytes and aggregate supplied bytes (each checked),
8,192 conservative construction-cell reservations, 128-byte identifiers and
128 requested effects. Limits can be narrowed. RAW reserves the existing
coverage reporter's full cell ceiling before invoking it; XMP reserves 13 cells
and a recognized preview reserves 28. These are construction bounds, not an
exact allocator or encoded-report byte quota. Parser-specific bounds still apply.

## Finite acceptance

The actual [authored controls](../../experiments/privacy-artifact-audit/tests/authored_operation.rs)
include before/after derivatives plus original,
backup, partial staging, and failure/refusal artifacts. Independent assertions
catch omitted expected slots, conflicting lineage/bindings and false
removed/absence claims. Exact slot, aggregate input and report-construction
limits, plus one-over refusals, are covered within these twelve tests. They
exercise the actual reporter on public authored snapshots and independently
assert declared inventory/effect outcomes; metadata parsing still reuses the
same components and remains labeled as same-parser recomputation.

The mechanism has no write, removal or cleanup API. It neither discovers external
copies nor certifies a selected privacy operation. Public authored evidence
supplies no private camera results, execution of #0089, or positive closure of
#0090.
