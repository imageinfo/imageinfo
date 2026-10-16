# Governance proposal validation and handoff

Reviewed **2026-10-10**, revision `2026-10-10.1`, card **#0009**. This is a practical
process proposal with contributor-facing guidance. It does not establish a staffed
team, enabled repository controls or a tested release/recovery system.

Subsequent accepted scope, **#0154 / 2026-10-16**: Terry selected
[solo, best-effort operation](../../GOVERNANCE.md#accepted-initial-operating-scope--0154),
with Terry as coordinator and conduct/escalation contact. No human backup or
response deadline is claimed. GOV-OPEN-01's staffing and independent handoff goals
remain future outcomes, not initial solo-operation requirements. GOV-OPEN-06's
existing contributor verification evidence remains separate from staffed coverage.
Security intake and review enforcement remain separate decisions. Terry subsequently
accepted [#0159's solo source-alpha release policy](first-release-policy.md), with
automated checks and agent review, no independent human verification/backup gate,
and exact candidate approval before publication. No release operation is verified.
The historical proposal audit below does not establish those operations.

## Delivered artifacts

- [GOVERNANCE.md](../../GOVERNANCE.md): twelve rules, six ownership areas, review and
  decision responsibilities, and six explicit readiness actions.
- [CONTRIBUTING.md](../../CONTRIBUTING.md): public onboarding, current documentation
  checks, format evidence, authorship and a contribution path without local-board access.
- [SECURITY.md](../../SECURITY.md): current reporting limitation, minimal contact
  route and safe transition to private investigation.
- [Release/recovery runbook](release-and-recovery.md): candidate gates, independent
  verification, publication, incident response and seven continuity exercises.
- [PR template](../../.github/PULL_REQUEST_TEMPLATE.md): problem, evidence, compatibility/
  safety and provenance prompts; no new access permissions or automated workflow.

## Repository observations

Read-only checks on 2026-10-10 confirmed the repository is public, its default branch
is `main`, public issues are enabled, and private vulnerability reporting is disabled.
Repository metadata came through the GitHub connector; the private-reporting flag
and issues setting were checked through the authenticated read-only GitHub API
because the connector did not expose that settings endpoint.

No settings were changed, no collaborator was added, no review rule or CODEOWNERS
file was installed, no notification subscription was changed, and no release was
published. Other owners' access, personal account recovery, existing private contact
arrangements and signing custody were not audited. The documents do not invent
facts about those unknowns.

Private reporting enablement and responder verification are **GOV-OPEN-02**, not
silently completed by adding SECURITY.md. Its fallback asks only for a minimal
public contact request, never exploit details, credentials or private media.

The subsequent [#0066 readiness proposal](security-intake-readiness.md) rechecked
the reporting setting read-only on 2026-10-15: HTTP 200, disabled. It prepares the
activation, consent and notification-test package; no setting change, human
appointment or completed intake exercise follows from that proposal.

## Scenario review

These are walkthrough checks of the process, not executed permission/release drills.

| ID | Scenario | Expected handling / supporting rule |
| --- | --- | --- |
| GOV-CASE-01 | New contributor has no local board or author-machine access | CONTRIBUTING supplies clone, public issue/PR path and artifact-specific checks; GOV-001/007 |
| GOV-CASE-02 | A researched tag is described as universally writable | Reviewer keeps exact capability/location/variant claims and demands applicable preservation evidence; GOV-002/005/007 |
| GOV-CASE-03 | The only available technical reviewer is the author | Record missing independence; do not count bots as backup maintainers or enable unverified production writes; GOV-003/005 |
| GOV-CASE-04 | Private vulnerability button is absent | Follow SECURITY's minimal contact route; no exploit upload or invented inbox; GOV-010/OPEN-02 |
| GOV-CASE-05 | A clean build succeeds but artifact bytes differ | Reproduction is not established; investigate and scope/disclose the claim rather than publishing a false reproducibility assertion; GOV-009 |
| GOV-CASE-06 | Primary publisher or laptop is unavailable | Named backup uses documented instructions and their own authorized access; absent backup/recovery proof remains an open readiness gap; GOV-003/010 |
| GOV-CASE-07 | An existing release has an unsafe writer or compromised artifact | Preserve evidence, stop further unsafe publication, coordinate mitigation and identify corrected artifacts without silent tag replacement; GOV-009/010 |
| GOV-CASE-08 | A contributor disputes a design or leaves maintainership | Record scoped reasoning/decision; transfer duties/access through authorized owners and retain attribution; GOV-004/011 |

The scenario review preserves the current approved documentation workflow: direct
commits/pushes remain authorized, and Terry alone accepts local cards into Completed.
Future review enforcement is proposed and must be adopted/tested separately.

## Ticket acceptance trace

| Requirement | Proposal and outstanding operational evidence |
| --- | --- |
| Format ownership | Six named responsibility areas with primary/backup slots; consented appointments and handoffs remain open |
| Onboarding | Contributor guide, public issue/PR route, verification recipes and small PR template; eventual language setup still requires the authorized toolchain decision |
| Review expectations | Independent human review, capability/evidence checks, ordinary code and explicit disagreement handling; repository enforcement not configured |
| Reproducible releases | Concrete candidate/build/verification/publication sequence and artifact comparison; no pipeline or release has run |
| Security reporting | Disabled private route verified and honest fallback documented; staffing/enablement/notifications still to be established |
| Access recovery and succession | Private inventory model, individual accounts, primary/backup duties and seven rehearsal scenarios; none claimed successfully exercised |
| Multiple maintainers and open decisions | Responsibilities and six readiness actions are explicit; this document does not claim the concentration risk is already solved |

## Verification and limits

Checked all twelve GOV identifiers, six OWN areas and six GOV-OPEN actions for
unique coverage, reviewed the eight scenarios, and checked internal Markdown links,
source attribution, fenced examples and Git whitespace. The link pass includes
root documents, the docs tree and the GitHub PR template. Existing schemas and
capability evidence were not changed, so no unrelated runtime/schema test is claimed.

The runbook cites primary GitHub documentation for ownership continuity, private
reporting, account recovery and CODEOWNERS, and the Reproducible Builds definition
for artifact identity. All were observed 2026-10-10; no immutable documentation
revision was established. Recommendations are original project policy proposals,
not a claim that platform features are configured or that account recovery is guaranteed.

**#0017, governance-readiness**, owns the actual GOV-OPEN-01–06 follow-up. Its scope
requires separately authorized appointments/access/settings/publication actions and
sanitized evidence. No credentials or private operational data belong in this repo.

Card #0010 now supplies the [artifact provenance policy](../provenance/README.md).
MIT remains accepted and locked; actual artifact permissions/admission remain
evidence work, beginning with #0013 for the first corpus/reference baseline. Language and implementation architecture remain undecided.
