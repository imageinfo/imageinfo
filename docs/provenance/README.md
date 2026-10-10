# Artifact provenance under the locked MIT license

Status: **proposal for review**, revision `2026-10-10.1`, card **#0010**.
The [project MIT decision](../license-decision.md) is accepted and locked. This
document governs third-party assets and their permitted uses; it does not compare
replacement project licenses or change LICENSE.

Read the [review workflow and examples](review-workflow.md),
[review-record schema](review-record.schema.json), [synthetic examples](examples.v1.json)
and [validation record](validation.md). These records supplement the
[fixture plan](../fixture-plan/README.md); they are not a new runtime framework,
automatic license-clearance service or approval to acquire a corpus.

## Rules

**PROV-001 — Review the artifact and the proposed use.** Permission to inspect a
reference, run an external test tool, modify a photo, publish a fixture and ship
third-party source/binaries are separate decisions. Record the exact bytes/revision,
origin, applicable terms, audience, intended use and obligations. An MIT project
does not automatically relicense imported material or grant permission for it.

**PROV-002 — Identify before admission.** Pin source URL/revision and acquisition
date when available. Hash received bytes and record length, creator/rightsholder
claims, distributor and original notices. A hash proves identity, not authorship
or permission. A URL, a download button or an informal repository label is not a
substitute for the applicable grant. A not-acquired candidate has null byte evidence;
never invent a hash or mark its actual content reviewed.

**PROV-003 — Preserve declarations and conclusions separately.** Keep the upstream
declared license/terms and the reviewer's selected basis distinct. Use a verified
SPDX identifier/expression where appropriate, or a stable custom-terms reference;
keep the actual terms/notices and their provenance too. Unknown/conflicting terms
remain unresolved. Choosing a convenient identifier is not legal permission.

**PROV-004 — No import on unresolved reuse terms.** Research citations and reading
source documentation do not authorize vendoring that source, its tag tables,
fixtures or documentation. Before admission into maintained project source/corpus/
release assets, resolve the intended use and conditions. If terms conflict, rights
are unclear or the intended distribution cannot satisfy them, hold the import,
seek clarification/permission, use an independently authored alternative or decline.
Do not infer blanket relicensing from the fact that material is public.

**PROV-005 — Make permissions explicit.** Record scoped conclusions for storage,
analysis, modification, execution, redistribution, source inclusion, release inclusion
and publication of reports. Each is allowed, denied, unreviewed or not-applicable.
Only allowed permits that action; no Boolean default, not-applicable label or missing
field grants permission. Record restrictions on purpose, users, location/service,
retention, publication and required notices alongside the conclusion.

**PROV-006 — Privacy is independent.** Rights approval does not clear faces, addresses,
location/serial/owner metadata, embedded previews, filenames or private documents.
Review visible and embedded content and list relevant uninspected regions. Restricted
assets remain in approved private storage and are accessible only to authorized
people/services. Public CI, logs, issue attachments, cached artifacts and model/tool
uploads are publication/access decisions too, not invisible testing conveniences.

**PROV-007 — Prefer independent implementation and minimal lawful fixtures.** Write
native code/data descriptions from documented requirements and independently recorded
observations. Do not mechanically translate upstream code or export complete tag
tables and describe the result as original merely because syntax changed. This is
an authorship/review policy, not a claim of formal clean-room certification.
Start the R5 corpus with a small purpose-made owned/explicitly permitted full RAW
set, not a personal archive. C-RAW/DPRAW retain separate evidence and permission.

**PROV-008 — Derivatives and outputs have lineage.** For a transformed fixture,
generated mapping, extracted preview, oracle report or generated code, name parent
IDs/hashes, recipe/tool revisions and modifications. Reassess rights, required
notices, privacy and test meaning for the resulting artifact. Tool execution does
not automatically make its output either MIT or the tool's license. The output's
actual content and source material determine what must be reviewed.

**PROV-009 — Retain and fulfill obligations.** Store exact applicable notices and
license/permission evidence with controlled access. Map each required attribution,
change notice, license copy, source provision or distribution restriction to how
it will be satisfied for the intended package/corpus/report. Do not strip upstream
authorship, add an MIT header to third-party code as a substitute, or hide an
unfulfilled condition behind an approved flag. Release review checks the actual
assembled artifact, not merely a dependency name in a manifest.

**PROV-010 — Keep private evidence private.** Consent correspondence, personal contact
details, private filenames and credentials do not belong in the public repository.
Public records use sanitized summaries and opaque private evidence references; an
authorized reviewer can resolve the evidence separately. Evidence records never
auto-fetch URLs, execute recipes or grant file-system access. Confine artifact paths
to trusted roots as the fixture plan specifies. Do not put expiring secret URLs in
public manifests.

**PROV-011 — Approval is scoped, versioned and reviewable.** The reviewer records
who/when, exact asset identity, selected basis, permitted uses, privacy decision,
conditions and rationale. Pending/denied/superseded/example-only records cannot
authorize operational reuse. A source/version, use, audience, recipe or terms
change requires re-review. A previous approval for private analysis is not approval
to publish a sample or bundle a runtime.

**PROV-012 — Handle challenges without erasing history or making false promises.**
If ownership, permission or privacy is challenged, stop new affected uses while
reviewing the applicable facts/terms. Preserve a restricted audit record and identify
dependent fixtures, results and releases. Replace or withdraw assets when required
and record the impact on coverage. Do not promise erasure from all Git history,
forks/backups or automatic legal revocation of previously granted licenses.

## Asset-specific defaults

These are conservative project admission choices, not universal legal conclusions
about every artifact carrying a license name.

| Artifact/use | Initial project policy |
| --- | --- |
| Reference documentation | Cite primary facts/revisions in independently written notes. Any quoted/reproduced material needs its own applicable attribution/reuse assessment; no wholesale documentation import. |
| Upstream code or tag tables | Default to independently authored implementation/definitions. A proposed import needs exact file-level terms and intended distribution review first. |
| External ExifTool oracle | Treat installation/execution and redistribution as separate reviews, including its runtime/dependencies. It remains a development reference, not imageinfo's production engine. |
| Contributor-owned camera media | Obtain explicit scope for storage/analysis/derivatives/public redistribution and separate privacy review. Ownership of a camera or supplying a file alone does not establish every relevant right. |
| Public-download samples | Hold corpus admission until asset-specific terms and privacy are verified; no inference from download availability. |
| Public fixtures | Prefer terms that permit downstream testing, modification and redistribution with maintainable obligations; publish clear attribution and restrictions rather than implying the whole corpus is MIT. |
| Restricted fixtures | Use only within approved people/services/purposes; keep originals, reports and derived assets under appropriate restrictions. A private CI run is not automatically authorized. |
| Third-party dependencies/tools/data | Review the exact version and package contents, notices and distribution mode; a package-manager license string is only a declaration. No stack/dependency choice is made here. |
| Lookup databases/specification tables | Review data/source terms, extraction and redistribution scope separately from the program that reads them. Do not assume a generated table has no upstream obligations. |
| Generated results or previews | Track input/tool/recipe lineage; review whether content reproduces protected or private material before publishing. |
| Project-authored synthetic examples | Record authorship and project-license basis; label invented values. They do not establish real-camera correctness, consent or permission for future media. |

For the first distributable source/release path, prefer original material or reviewed
permissive imports whose conditions fit the intended distribution. Copyleft,
noncommercial, no-derivatives, custom or ambiguous terms are not silently treated as
MIT-compatible. They require a specific reviewed reuse path or remain out of the
shipped artifact. External reference use and a separately licensed public corpus
are distinct possibilities; neither is an automatic license workaround.

## Observed upstream and license facts

Observed **2026-10-10**, ExifTool source 13.59 at
`2200871d9cef988051d2a99d67df3bda6cbb30a8`:

- The pinned [README](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/README) describes licensing under Perl's terms, offering Artistic or GPL routes.
- The same revision's [LICENSE](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/LICENSE) contains the GNU GPL version 3 text.
- [Perl's project site](https://www.perl.org/about.html) describes its Artistic/GPL alternatives. This general statement does not resolve every ExifTool file, bundled fixture, distribution or selected license version for a proposed import.

Record both source declarations. This card does **not** conclude that the entire
ExifTool distribution is GPL-only, freely relicensable as MIT, or automatically
covered by one chosen Artistic version. Any actual copied artifact needs its own
applicable notices and resolved terms. No upstream code/table/media is imported here.

The [SPDX License List](https://spdx.org/licenses/) supplies standardized identifiers;
an identifier records a licensing conclusion rather than granting permission.
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/legalcode.en) contains attribution
conditions and treats other rights separately; [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/legalcode.en)
adds a noncommercial restriction. These are examples of artifact-level conditions,
not alternatives being proposed for imageinfo's locked MIT license. Live reference
pages were observed on 2026-10-10; no immutable revision was established for them.

## Handoff boundary

This policy and record contract are ready for review. Actual third-party imports,
source-license clarifications, permissions, corpus admission and release checks
need real evidence for each asset. #0013 owns the first lawful R5 corpus/reference
acquisition; #0017 owns operational reviewer/security readiness. None of those
permissions or capabilities is invented by a schema-valid example.
