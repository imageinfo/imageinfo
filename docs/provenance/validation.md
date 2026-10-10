# Provenance policy validation and handoff

Reviewed **2026-10-10**, revision `2026-10-10.1`, card **#0010**. The project license
remains the accepted, locked MIT license. This work concerns artifact admission
and reuse, not a new project-license decision.

## Results

| Check | Result |
| --- | --- |
| Provenance rules | PROV-001 through PROV-012 |
| Asset/use scenarios | Twelve reviewed scenarios, PV-CASE-01 through PV-CASE-12 |
| Review-record schema | Draft 2020-12 self-validation passed |
| Persisted examples | Two records validated; both are example-only |
| Existing first-party identity | Actual synthetic JSON length/SHA-256 and referenced LICENSE/fixture-manifest hashes matched unchanged files |
| Pending/approval/history branches | Six in-memory cases exercised pending, scoped source/private/release approval, derivative lineage and superseded history |
| Invalid-use/record checks | 29 rejected as intended |
| Third-party assets imported | 0 |
| Camera corpus assets admitted | 0 |
| Project-license edits | 0 |

Validation used `jsonschema 4.26.0` with date-format checks and a small local semantic
checker. It selects no product language, admission framework or package layout.
Schema consistency is not proof of authorship, a valid grant or legal applicability;
those require the actual evidence and authorized review described in the workflow.

## Reproduce the checks

Self-validate [review-record.schema.json](review-record.schema.json), then validate
each record in [examples.v1.json](examples.v1.json). The first record identifies
the existing project-authored metadata snapshot; recompute its byte length and
SHA-256, plus every local evidence hash it supplies. Neither the snapshot nor the
fixture manifest changes in this task.

The second example illustrates a hypothetical, unresolved upstream import. Its
acquired flag is false, its byte hash/length/date are null, and all permissions are
unreviewed. Its cited README/LICENSE declarations are real observations; there is
no assertion that a specific upstream file has been approved for reuse.

Perform semantic checks beyond the schema:

- Evidence and obligation IDs are unique; all references resolve.
- Acquired bytes match their identity; unacquired candidates cannot be approved.
- Approved use requires selected basis, reviewer/date, rights evidence, completed
  privacy review and fulfilled conditions. Cleared privacy cannot retain relevant
  uninspected content; restricted use needs explicit controls.
- Each intended use requires its applicable allowed permissions. Public use needs
  redistribution and privacy clearance; source/release/report inclusion has its
  own permission. Private analysis never implies modification or execution.
- Operational use additionally requires a current operational approved record;
  pending, example-only and superseded records cannot authorize it.
- Derived artifacts resolve parent identity/hash and derivation evidence without
  cycles, and need relevant parent modification permission plus independent child
  review. Verify inherited conditions and scope; a separate derivative grant needs
  its own evidence rather than an assumption about the original's permissions.

The six branch checks use temporary hypothetical records derived from the authored
example; none is published as a real asset approval. They demonstrate how a private
analysis scope, source inclusion, release inclusion and historical review differ.
The tests do not contact a licensor, exercise permission, import source or run media.

## Rejection cases

The 29 checks reject unknown fields, invented identity for unacquired bytes, missing
reviewer/basis/rightsholder claim, invalid dates, dangling/duplicate evidence, missing/unfulfilled
notice conditions, denied public/source/release/report use, restricted/uninspected
privacy, pending records with allowed actions, superseded/example-only reuse,
private scope expansion to modification/execution/publication, missing private
controls, and missing/mismatched/cyclic or non-modifiable parent lineage.

These are data/decision consistency checks, not an exhaustive rights audit. In
particular, a maliciously fabricated grant could satisfy a schema; trusted evidence
and reviewer authorization remain indispensable.

## Acceptance and research conclusions

| Ticket requirement | Delivered |
| --- | --- |
| Fixed project-license boundary | MIT unchanged; no renewed comparison or custom attribution clause |
| Code/table/documentation/media/database reuse | Asset-specific defaults and alternative reuse paths, with exact intended-use review |
| Pinned origins and notices | Identity/evidence/selected-basis fields, obligation fulfillment and release-content review |
| Provenance and permission fields | General review schema plus explicit mapping into existing fixture rights/privacy/admission fields |
| Derivatives and generated outputs | Parent/hash/recipe lineage and independent rights/privacy review |
| Unresolved questions | Exact per-file/distribution terms, grant authority, intended audience and conditions remain pending until actual assets are proposed and reviewed |

Primary sources are linked in [the policy](README.md), observed on 2026-10-10.
The pinned ExifTool README describes Perl/Artistic-or-GPL terms while LICENSE contains
GPLv3. Both are retained as observations; no blanket per-file licensing conclusion
or permission to relicense as MIT is inferred. Creative Commons/SPDX references
illustrate artifact conditions and identifiers, not replacement project licenses.

The documentation index, contribution guide, license decision and fixture/release
guidance now link this process. Inventory revision `2026-10-10.8` records the policy
and assigns first actual corpus/oracle admission evidence under GAP-011 to #0013.
All 49 capabilities remain specified; schema/reference/dependency checks and the
existing ten inventory rejection cases pass. Links, source attribution, JSON and
Git whitespace are included in handoff verification.

## Next work

The initial requirements queue is now specified through #0010. **#0013,
corpus-baseline**, is the next evidence-work candidate after review of this policy
and selection of lawful inputs. It must apply these rules to actual full RAW assets
and the exact reference-tool distribution/runtime; no acquisition is claimed here.

Future code/dependency/data imports require their own scoped review in the task
that proposes them; this card grants no blanket approval. #0017 retains authorized
reviewer/operational readiness. #0011 remains deferred until Terry explicitly
advances language/implementation selection. Full ExifTool parity remains eventual.
