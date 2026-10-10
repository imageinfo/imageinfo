# Review, admission and release workflow

Proposal `2026-10-10.1`. Use the [provenance rules](README.md) with the
[fixture admission process](../fixture-plan/README.md). The review record is an
auditable decision about exact bytes and uses; it never authorizes itself.

## Before bringing an asset into the maintained project

1. **Describe the need.** Identify the smallest artifact needed and its intended
   uses: private reference/test, public source/fixture/report or release bundle.
   Prefer an independent implementation, a citation or an owned synthetic fixture
   when those satisfy the requirement without importing third-party expression.
2. **Locate the terms.** Record pinned origin, creator/distributor claims, applicable
   file/package notices, license text/version, any exceptions and evidence of a
   separate permission grant. If the provider's authority or the applicable terms
   are unresolved, record pending rather than copying into source or public corpus.
3. **Identify received bytes when acquisition is authorized.** Preserve the exact
   received artifact, SHA-256 and length in an approved quarantine location. Do not
   execute an incoming tool/configuration or perform normal fixture experiments
   merely because a file arrived. Temporary research retrieval is not vendoring
   or corpus admission.
4. **Review rights and privacy independently.** Map permitted actions to the actual
   purpose, audience and services. Examine original pixels, previews and metadata
   where relevant. Use restricted handling when complete privacy clearance is not
   possible; unknown coverage does not support public clearance.
5. **Resolve conditions.** Identify retained notices, attribution text/location,
   change/source obligations, access restrictions and any publication limits.
   Record evidence of fulfillment for the particular intended distribution/use.
   Ask the rights holder or a qualified reviewer to resolve material ambiguity;
   do not choose the most convenient interpretation silently.
6. **Approve the scoped use.** An authorized project reviewer records their identity,
   date, rationale and evidence. Recheck hashes and conditions at admission/use.
   A signed or schema-valid review file is not a substitute for checking current
   trusted admission records, source identity and the user's requested operation.
7. **Publish the appropriate record.** Keep private evidence restricted. Public
   summaries show provenance, applicable terms, attribution and the scope actually
   approved without exposing personal information or secret locators.

Do not request broad rights to an entire personal photo archive when a purpose-made
full RAW example is sufficient. The contributor can decline public redistribution;
that does not make a separately permitted private characterization automatically
worthless. It does mean public CI/corpus/release use needs different permission or
a different fixture.

## Record contract

For a real media contribution, obtain answers tied to exact asset IDs: who created
and can authorize the material; which storage/test/derivative/publication uses are
permitted; applicable terms/notices; any people/location/other-content concerns;
who may access originals and outputs; and any limits on purpose, services or retention.
Keep personal correspondence private and publish only an appropriate summary.
Do not prefill a contributor's consent or take ownership claims from editable EXIF
fields as proof. This checklist requests evidence when an actual asset is offered;
no contributor permission is being solicited or invented by this document.

[review-record.schema.json](review-record.schema.json) checks structure. Semantic
admission still requires evidence, consistency and authorized review.

| Field | Meaning |
| --- | --- |
| Identity/version | Stable review ID, record revision, schema version and `purpose` (`operational` or `illustration`) |
| `artifact` | Category, origin type/location/revision, creator/rightsholder claims, distributor, acquisition date, acquired flag and exact SHA-256/byte length when acquired |
| `intendedUses` | Explicit set of requested uses; no automatic expansion from private reference to public redistribution |
| `evidence` | Stable IDs, type, locator, digest when captured and disclosure level; private locators in public summaries are opaque IDs |
| `rights` | Declared license, selected reviewed basis, evidence references and eight action-specific conclusions |
| `privacy` | Cleared/restricted/unreviewed, evidence references, relevant uninspected content and access/handling controls |
| `obligations` | Each required condition, the source evidence and fulfillment references; unresolved obligations cannot disappear from the release check |
| `lineage` | Parent IDs/hashes and derivation evidence reference for generated/modified/extracted content |
| `review` | Pending/approved/denied/superseded/example-only, reviewer/date, rationale and restrictions |

Permission labels are `allowed`, `denied`, `unreviewed`, or `not-applicable`.
Only allowed can satisfy a requested action. An approved record requires acquired
identified bytes, a supported rights-holder claim, selected basis, rights evidence, completed privacy disposition,
reviewer/date and fulfilled obligations for its scoped uses. Public uses require
redistribution permission and privacy clearance; source/release/report uses require
their respective additional permission. Relevant uninspected privacy content prevents
clearance. Restricted private use needs documented controls.

Every evidence reference must resolve. A fulfillment reference must demonstrate the
required condition for that artifact/use, not merely point back to an unrelated
license name. Review lineage as a graph: resolve parents and hashes, reject cycles,
retain all inherited obligations and review the derivative independently. A new
recipe/output hash needs a new or revised review; do not carry approval by filename.

An acquired=false candidate has null hash/length/acquisition date. It can be discussed
and kept pending, but cannot become approved. Illustration records always remain
example-only, even when they point to a real project-authored documentation file.
Pending/denied records carry no allowed permissions. A superseded review may retain
its historical conclusions but cannot authorize new uses. Preserve its prior revision
and evidence; superseding records project admission state, not legal revocation.

## Bridge to fixture manifests

Keep the existing fixture schema intact. Its `rights.evidenceRef` links the applicable
provenance review ID/revision. Set `rights.status: approved` only for a current
approved use, and derive analyze/modify/redistribute booleans from allowed conclusions
within that scope. False also covers unresolved/not-applicable actions; the detailed
record retains why. Do not collapse unknown permission into a blanket legal denial.

Retain the fixture's independent privacy review, storage access, allowed phases and
media/variant observations. Admission uses the intersection of these restrictions
and the provenance record, not whichever is more permissive. A public fixture needs
public clearance and redistribution evidence; write experiments need modification
permission. An admitted private fixture does not become a public report source by
default. The existing illustrative fixtures retain `allowedPhases: []`.

## Release and corpus review

Before publishing an assembled source archive, binary, corpus or report:

- Enumerate its exact included assets and generated content, using hashes/versions.
- Check each current review permits that use and its actual audience; inspect
  transitive dependencies and generated/derived content, not just top-level names.
- Assemble the required license texts/notices/attribution/change information and
  verify source/distribution obligations where applicable. Record actual paths.
- Verify no restricted media, reports, consent correspondence, metadata or secret
  locators leaked through examples, caches, logs or package build inputs.
- Record reviewer, artifact manifest, results and unresolved blockers. Do not ship
  an unresolved asset under a blanket MIT notice; omit/replace it or resolve the use.

There is no third-party notice bundle to populate with invented imports today.
When an import is approved, add the actual applicable notices with it and ensure
the release includes them. The project LICENSE stays MIT; third-party notices
describe their own material and do not rewrite the project-license decision.

## Reuse alternatives and tradeoffs

| Path | Appropriate use / limitation |
| --- | --- |
| Cite and independently author | Preferred for design/implementation research. Preserve traceability and avoid reproducing whole source/table/docs bodies; no automatic formal clean-room claim. |
| External reference execution | Useful for differential evidence after tool/runtime and input permissions are reviewed. Does not authorize bundling the tool or publishing private outputs. |
| Reviewed import | Retains needed upstream work with its actual notices/conditions. Requires asset/use review and may constrain the intended distribution. |
| Ask for an explicit grant | Can clarify missing or unsuitable terms. Record the grantor's authority, exact assets and permitted scope; a vague approval to view a sample is insufficient. |
| Hold, replace or decline | Keeps an unresolved asset out of maintained/public artifacts while preserving the unmet requirement in the backlog. |

## Acceptance scenarios

| ID | Proposed use | Required decision |
| --- | --- | --- |
| PV-CASE-01 | Existing project-authored synthetic model JSON | Retain actual hash and MIT basis; illustration is not a camera corpus admission. |
| PV-CASE-02 | Copy an ExifTool parser/table based only on the README label | Hold import; reconcile exact file/distribution notices and chosen applicable terms first. |
| PV-CASE-03 | Download a camera sample from a public review site | Pending until asset-specific storage/test/derivative/publication rights and privacy are reviewed. |
| PV-CASE-04 | Owner permits private analysis only | Can admit only that reviewed private purpose; no modification, public CI, redistribution or reports beyond the grant. |
| PV-CASE-05 | Permissively licensed image still exposes a person's location/identity | Rights approval does not grant privacy clearance; restrict/replace or obtain appropriate clearance. |
| PV-CASE-06 | CC BY asset proposed for a public fixture | Verify actual grant and all applicable attribution/other conditions plus privacy; preserve its terms instead of labeling it MIT. |
| PV-CASE-07 | Noncommercial/custom-term asset proposed for a broadly reusable release | Hold default release inclusion; review the exact permitted distribution or choose another asset. |
| PV-CASE-08 | Metadata scrub/extracted preview from a restricted RAW | Retain lineage and re-review; derivative is not automatically public or anonymous. |
| PV-CASE-09 | Oracle output contains copied descriptions or private metadata | Review output content, source and intended publication independently; neither automatic MIT nor automatic tool-license conclusion. |
| PV-CASE-10 | New asset version or changed intended audience | Prior identity/use approval does not transfer automatically; revise evidence and admission. |
| PV-CASE-11 | Missing required notice in a release archive | Block that publication until its actual conditions are fulfilled; a manifest label is insufficient. |
| PV-CASE-12 | Permission/privacy challenge after distribution | Pause new affected uses, preserve restricted audit evidence, assess applicable terms and downstream impact; do not promise universal erasure. |
