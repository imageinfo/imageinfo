# Comparison and verdict policy v1

Status: proposed specification, `2026-10-10.1`. Apply this policy only to a named
experiment case, admitted fixtures, a recorded reference profile, and recorded
tool/configuration identities. Preserve the original captures alongside any
canonical observations. The policy is data-contract guidance, not an application
framework or a requirement to copy ExifTool's architecture.

## Before comparing

**CMP-001 — Validate the experiment.** Confirm fixture hashes and admission, tool
distribution/runtime/driver identities, complete argument arrays, controlled
environment, and the exact policy/mapping revision. A missing or inconsistent
baseline is an invalid experiment, not an imageinfo failure or a successful match.
Do not run against the immutable corpus original; make fresh working copies for
the reference and candidate independently.

**CMP-002 — Preserve observations.** Capture stdout and stderr as separate byte
artifacts, termination status, input/output hashes, extracted resources, canonical
observations, and independent reports. Parse textual JSON strictly. Duplicate keys,
truncated output, invalid Unicode, or lost binary bytes invalidate that capture.
Never overwrite a golden artifact because a new tool version disagrees.

**CMP-003 — Match occurrences before values.** IDs from separate snapshots are
not comparable directly. Use a versioned correspondence map based on fixture/source
identity, logical document/embedded-resource identity, native tag key, structural
location, and instance. ExifTool group names/numbers are inputs to its reference
adapter, not imageinfo's native identity. Same-named tags cannot be paired by first
match, value similarity, or a flat dictionary.

Missing candidate data is a failure when a valid oracle observation and correspondence
establish what is required. An adapter that cannot represent or disambiguate the
reference observation yields an invalid/incomplete experiment. It must not drop
the field to manufacture a pass. Preserve raw captures so the adapter itself can be
audited and tested with duplicate/state examples from the metadata contract.

## Compare the declared representation

**CMP-004 — Exact and semantic values are separate.** Compare encoded bytes, typed
raw values, normalized values, and display output independently when the case calls
for them. Raw `2/500` differs from `1/250`; normalized numeric values can be equal.
Integers/rationals/decimals are exact unless the specific field contract says
otherwise. Floating-point source bits preserve NaN payloads and negative zero.

A tolerance must name the field/native occurrence, units, comparison layer, bound,
and reason. It belongs to the hashed policy/case revision. Never introduce a broad
epsilon to hide unexpected differences. GPS interpolation tolerances, for example,
do not permit rounding unrelated exposure or timestamp values.

**CMP-005 — Shape and state survive.** Distinguish missing, empty, explicit null,
invalid, undecoded, unrequested, and resource-limited results. Compare duplicate
counts and XMP structure, qualifiers, namespaces and language alternatives. Sequence
order matters. Bag order may be ignored for semantic comparison, but multiplicity
must remain; raw/source order is a separate check. Unknown values are not equal
merely because neither side produced display text.

**CMP-006 — Time semantics are explicit.** Preserve precision, fractional digits,
offset presence, assumptions and original representations. Compare UTC instants
only where they are known. Do not assign the host zone to unqualified EXIF time.
CR3 integer-time conversion receives dedicated UTC/non-UTC runs. RFC 3339's unknown
local-offset convention is distinct from a clock value with no known offset.
Display differences are tested under recorded locale/timezone settings, separately
from stored or normalized values.

**CMP-007 — Binary data is measured.** Compare extracted-resource byte lengths and
hashes after resolving exact resource instances. A preview label does not identify
every preview. A file-level hash proves read-only byte stability but cannot replace
a protected-region/reference map for metadata writes that legitimately relocate
data. A digest from one tool over a subset of image data is not a full preservation
proof.

## Allowed normalization is narrow

**CMP-008 — Normalize only declared incidental context.** Allowed examples include
replacing an exact, typed source-path field with its fixture ID, or comparing a
declared unordered bag as a multiset. Record each normalization rule used. Do not
perform global string replacements, strip all timestamps, sort all arrays, erase
diagnostics, collapse duplicates, normalize metadata Unicode silently, or remove
unknown fields.

Temporary paths, filesystem times, processing duration, and native diagnostic
wording should be controlled or tested in their own expected fields. If excluded
from one semantic assertion, they remain present in captured artifacts. A two-file
basename collision must not disappear under path normalization.

**CMP-009 — Compare behavior, not accidental spelling.** Imageinfo's native CLI,
schema, and issue codes can differ from ExifTool's. Test the accepted functional
contract and declare such differences explicitly. Exact legacy output/exit/argument
compatibility is a separate surface on card #0007. Do not demand text equality
where the requirement is semantic equivalence, or use semantic equality where the
requirement is exact bytes.

## Mutation evidence

**CMP-010 — Check preservation independently.** Every advertised embedded-write
case needs exact intended-value readback, independent structure/reference checks,
protected sensor/preview/opaque-region hashes, required interpretation metadata,
and independent usability evidence for the specific variant. No sensor recompression
is allowed. The independent checker must not reuse the writer's traversal or
preservation decisions as its sole evidence.

The original corpus bytes remain unchanged. Reference and candidate write to fresh,
separate clones of the same original. Capture each clone before and after, even if
the operation fails. Sidecar-only edits additionally require the RAW file hash to
remain unchanged. Incomplete checks leave the write unverified; a readable thumbnail
does not prove the sensor payload is intact.

**CMP-011 — Exercise failure behavior.** Inject bounded failures at the transaction
boundaries specified by #0006: temporary output, flush, validation, backup, and
replacement, plus competing source changes and cancellation. Record surviving
original/output/backup states and per-file outcomes. Define the expected state
before the experiment; do not classify whatever survived as success after the fact.

## Result meanings

| Verdict | Meaning | Counts as implemented parity? |
| --- | --- | --- |
| not-run | Fixtures, tool identity, driver, implementation, or another prerequisite is missing; include a reason. | No |
| reference-observed | A valid reference-only characterization was captured. It can contain reference errors or limitations; it does not test imageinfo. | No |
| invalid-experiment | Identity/configuration/capture/correspondence is invalid or required evidence is missing. | No |
| unsupported | The candidate cannot perform an in-scope requested capability; preserve the result as a gap. | No |
| fail | A valid experiment violates an assertion, has an unexplained difference, or fails required preservation/recovery checks. | No |
| accepted-difference | All required safety/preservation checks pass; specific observed differences are covered by reviewed, exact-scope records. | Only the declared compatible subset, with the difference published |
| pass | All required assertions for this exact case pass, with no unexplained or hidden difference and no required check left unrun. | Only the exact fixture/variant/operation/platform subset |

A correct refusal can pass a **refusal test** while the refused operation remains
unsupported. For example, refusing a direct read-only CTMD edit can satisfy its
safety contract without implementing that edit. Keep test outcome and advertised
operation capability separate.

**CMP-012 — Differences require bounded review.** Each accepted difference names
the failed comparison check(s), affected native fields/behavior, rationale, review
record, fixture hash, both tool-distribution manifests, and comparison-policy hash.
Re-evaluate it when any bound input changes. No wildcard waiver or unreviewed
baseline update may convert a failure into a pass.

An accepted difference cannot waive failed structure, preservation, usability,
environment-validity, or safety assertions. It may account for a deliberate
representation/semantic boundary already accepted by the project. If the oracle
has a demonstrated corruption bug, imageinfo must preserve safety and document the
reference defect, not reproduce it to achieve a matching output.

## Reporting

Report case IDs, fixture/variant/operation/platform cells, tool identities, verdicts,
and unresolved gaps. Do not calculate a parity percentage from scenario counts,
or count not-run/unsupported cases as passes. A passing fixture category does not
establish every tag or camera firmware variant. Keep artifact access restrictions
in the report and publish only cleared summaries/artifacts.

The schema checks record shape and a few state transitions. The future harness and
review process must enforce the semantic rules above; a schema-valid record alone
does not prove that an experiment happened or that its evidence is sufficient.
