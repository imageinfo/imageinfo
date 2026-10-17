# Review policy and historical enforcement proposal

## Accepted solo workflow — #0157, 2026-10-16

Terry explicitly selected option A: retain authorized direct commits and pushes
after required checks, use agent review where useful without claiming independent
human verification, and hand off board cards to Ready for Review for Terry's
acceptance into Completed. Public contributors can continue submitting ordinary
PRs. No mandatory PR approval, CODEOWNERS file or new branch-protection/ruleset
requirement is adopted. Existing correctness, capability, provenance and format
preservation checks remain required; the policy does not waive technical evidence.

Read-only observations on 2026-10-16 returned zero repository/inherited rulesets
and `main` with `protected: false`. The current tracked tree contains no CODEOWNERS
file. This decision changes no repository rules, permissions or reviewer roster,
and creates no enforcement-test PR. The decision-record commit/push supplies
ordinary direct-push evidence, not a test of hypothetical enforcement.

#0158 retains the bounded follow-up to verify the selected existing workflow and
document actual behavior. Do not run the historical eighteen-case proposed
protection rehearsal or recruit reviewers merely to complete the retained-policy
branch. Record only actual observations; no enforced review or independent human
coverage is claimed. Revisit enforcement only if Terry selects a different policy.

The [#0158 verification](retained-review-policy.md) records the actual retained
route, exact-source check evidence and bounded negative-case dispositions. It
does not activate the historical proposal below.

## Historical unselected #0069 proposal

**#0069 / GOV-OPEN-04, 2026-10-15**, revision `review-routing-v1`.
This is a settings recommendation and future test plan, not an adopted policy or
an enforcement demonstration. The [blank record](review-routing-record.template.json)
starts with every operational case **not-run**. No reviewer has been enrolled,
permission granted, CODEOWNERS installed, rule changed or test PR opened.

[GOV-003–005](../../GOVERNANCE.md) govern appointments and independent review.
Terry's standing direct-commit/push authority and local-board acceptance workflow
continue until Terry explicitly adopts a replacement. Acceptance of this planning
ticket alone does not adopt the settings below. #0017 retains actual readiness;
GOV-OPEN-04 remains open until authorized adoption and real tests succeed.

## Observed repository and available controls

Read-only observation on **2026-10-15** at public
[`imageinfo/imageinfo`, `e21f83303768d7ad5e83372ff0a34f52c4dc8897`](https://github.com/imageinfo/imageinfo/commit/e21f83303768d7ad5e83372ff0a34f52c4dc8897):

| Check | Actual bounded result |
| --- | --- |
| GitHub connector repository metadata | Organization-owned, public, default branch `main`; connector identity reports admin access. This is not another reviewer's access or consent. |
| `GET /repos/imageinfo/imageinfo/rulesets` | Successful empty list; no returned repository/inherited rulesets. |
| `GET /repos/imageinfo/imageinfo/branches/main` | Successful response, exact SHA above, `protected: false`. |
| `GET /repos/imageinfo/imageinfo/branches/main/protection` | HTTP 404 with `Branch not protected`, consistent with the branch response; no classic protection demonstrated. |
| Git tree at that SHA | No `.github/CODEOWNERS`, root `CODEOWNERS` or `docs/CODEOWNERS`. |
| `GET /repos/imageinfo/imageinfo/codeowners/errors` | HTTP 404; this is not a successful zero-error validation of a future file. |
| Commit check runs | Three completed successes named `windows-2025`, `ubuntu-24.04`, `macos-15`, all from `github-actions`, app ID `15368`. These are CI outcomes, not required rules or human reviews. |

The connector supplies metadata but exposes no rules/protection endpoint, so the
remaining remote observations used read-only `gh api`. Initial sandbox network
failures were retried with network permission; no failed request was counted as
an empty configuration. No collaborator roster, organization plan, custom-role
inventory or reviewer permission/availability was inferred. Recheck before adoption:
403, ambiguous 404, unavailable endpoint or unsupported plan means **unknown/blocked
for that operation**, not proof that a control is off or a reviewer is eligible.

[GitHub's protected-branch documentation](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
supports classic protection for public Free organization repositories. Recommend
one exact `main` classic protection rule rather than adding overlapping rulesets.
Reinspect inherited rules before applying anything; multiple controls can constrain
the same branch. This proposal needs no paid-plan evaluation mode or merge queue.
The [rulesets documentation](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets)
describes that alternative; none was installed here.

## People and routing prerequisites

Before activation, identify **two distinct consenting human reviewers**, each with
their own account and verified write-or-higher repository access. Record their
actual logins and accepted scope privately, then obtain consent for public
CODEOWNERS attribution. Terry can volunteer; coordination does not enroll him.
Public contribution and a review comment do not require write access, but neither
establishes eligibility to satisfy the proposed required review. No extra account
or team should be created merely to make a test green.

Two people permit one to author and the other to review; the latest pusher must
leave an independent eligible reviewer available. If both coauthor a change,
another qualified human is needed for independent approval. Multiple bot identities,
agent reviews and an author's second account do not supply that independence.
GitHub checks account actions; it cannot establish distinct human judgment,
domain competence or undisclosed coauthorship.

Start with one small catch-all routing line in a future `.github/CODEOWNERS`:

```text
* <first-consented-human-handle> <second-consented-human-handle>
```

The angle-bracket tokens are unresolved slots, **not valid handles or an
installable CODEOWNERS file**. Substitute the actual `@login` values only after
the prerequisites and separate activation authorization. Both owners appear on
the same line; no path exceptions or team assumptions are proposed. Catch-all
coverage includes `.github/CODEOWNERS`, workflows, governance, schemas, source,
research and new paths. It routes requests to the pair; it does not appoint
OWN-001–006 technical stewards or prove either can approve every format change.
Use GOV-003/005 to obtain relevant expertise, retaining capability gates if absent.

[GitHub's CODEOWNERS documentation](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners)
requires eligible owners and uses the base branch's file. Draft PRs defer automatic
requests until ready; later matching lines override earlier ones. One owner's
approval can satisfy code-owner review; naming two does not require both. Future
path overrides need explicit routing tests, particularly for the ownership file
itself. Paths are case sensitive even on a case-insensitive checkout. Before
activation, require a successful CODEOWNERS error-endpoint response with no
reported errors, verified owner access and actual routing results; the current
404 supplies none of these. A request proves routing only, not completed review
or enforced merge denial.

## Exact proposed settings

After separate adoption and a disposable-branch rehearsal, recommend the following
classic protection values for **`main`**. The record's `proposedProtection` object
is a reviewable recommendation, not an API command. Its field names follow the
[branch-protection REST contract](https://docs.github.com/en/rest/branches/branch-protection#update-branch-protection).
Review a fresh settings diff before any authorized application because arrays
replace previous values and this snapshot can become stale.

| Setting | Proposed value / purpose |
| --- | --- |
| Required approving reviews | 1; one independent human review keeps ordinary contributions workable. |
| Code-owner review | Required, after real eligible owners exist. |
| Dismiss stale approvals | Yes, when the reviewed diff changes. |
| Approval of most recent reviewable push | Required from someone other than its pusher; this does not by itself prove nonauthorship. |
| Administrator enforcement | Yes; no PR-bypass users, teams or apps. Explicit adoption changes current direct-push practice. |
| Review dismissal restrictions | No additional restricted roster proposed; recording dismissal and obtaining fresh human review are policy prerequisites. GitHub can unblock after dismissal if another valid approval remains. Admins can still change configuration. |
| Required status checks | Exact contexts `windows-2025`, `ubuntu-24.04`, `macos-15`, each bound to GitHub Actions app ID `15368`; verify fresh app/context identities first. |
| Branch up to date | Yes; rerun checks after updating the branch. |
| Conversation resolution | Required. |
| Force pushes / deletion | Disabled. |
| Push allowlist / linear history / lock / fork syncing | No allowlist; no new linear-history requirement; unlocked; fork-sync exception off. |

The existing [CI workflow](../../.github/workflows/ci.yml) runs on `main` pushes
and PRs with `contents: read` and checkout credentials disabled. Keep it unchanged
for this proposal. Do not require workflow title `Rust foundation` or job key
`check` instead of the observed matrix contexts. A required check can be accepted
by GitHub as skipped/neutral; the human gate must examine actual work and require
the relevant verification. Binding an app prevents a different app's same-name
status from substituting; it does not make an edited Actions workflow trustworthy.
Review workflow changes and ownership changes as security-relevant configuration.

Before selection, confirm each context has succeeded in this repository within
the previous seven days and has a unique name across workflows. If a commit
status and check share a required name, both must pass. Record the exact current
head/test-merge SHA GitHub evaluates, not an earlier green commit. See
[GitHub's status-check troubleshooting](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks).
The workflow has no `merge_group` trigger, reinforcing the choice to leave merge
queue off. A future renamed runner/job requires a reviewed settings update.

No signed-commit rollout, deployment, mandatory commercial scanner, merge queue
or additional reviewers are added to the ordinary path. These settings do not
qualify RAW correctness, source preservation, release readiness or privacy removal.

## Future finite rehearsal and acceptance

All **18 cases below are unrun**. Prepare public authored, harmless text changes
only; no private fixtures. A separately authorized operator first creates a
temporary base branch `review-rule-rehearsal-0069`, installs the consented routing
file there and mirrors the proposed protection onto that exact branch. Record
the base/head SHAs, rule readback, eligible human roles and check identities.
Use PRs targeting this base, not `main`. Close remaining PRs and remove temporary
objects only under that same authorized rehearsal scope; retain sanitized results.

| Case | Future action | Required observation |
| --- | --- | --- |
| RR-01 | Ready PR changing an ordinary documented path | Eligible nonauthor owner requested; no automatic merge. |
| RR-02 | Draft PR, then mark ready | No draft auto-request; owner request appears when ready. |
| RR-03 | Change source, schema, research, new path, workflow and CODEOWNERS in a finite path set | Catch-all routes every sample; base-branch ownership governs a PR attempting to remove its own owners. |
| RR-04 | Valid final-diff independent owner approval, all checks successful/up to date, conversations resolved | Merge allowed and one harmless rehearsal merge succeeds. |
| RR-05 | Green CI but no approval | Merge denied. |
| RR-06 | Author attempts own approval / agent-only review supplied | Self-approval cannot satisfy required review; automation never counted as independent human evidence, even if a platform identity could submit a review. |
| RR-07 | Approval/comment from a read-only outsider or nonowner | Does not satisfy required code-owner approval; preserve the useful contribution. |
| RR-08 | Push a changed diff after approval | Stale approval dismissed; merge denied until fresh eligible review. |
| RR-09 | Latest pusher attempts to supply the only approval | Does not satisfy latest-push approval; human authorship independence checked separately. |
| RR-10 | Fail, cancel, leave pending or omit each required context in turn | Merge blocked for each actual unmet required check; skipped/neutral acceptance is separately recorded as a platform limitation. |
| RR-11 | Same check name from a different authorized test source | Cannot satisfy app binding; if no harmless test source is authorized, leave unrun rather than grant access or forge identity. |
| RR-12 | Advance base after PR checks, then update and rerun | Out-of-date PR blocked; updated candidate needs fresh checks/review as applicable. |
| RR-13 | Leave an unresolved review thread, then resolve it | Blocked before resolution; other gates still apply afterward. |
| RR-14 | Ordinary writer and admin attempt a direct update without qualifying PR | Both rejected on rehearsal base; no bypass claimed. Do not attempt on `main`. |
| RR-15 | Attempt forced ref update and deletion of rehearsal base | Both rejected; no destructive test on production refs. |
| RR-16 | In isolated rehearsal configuration, use a nonexistent/ineligible owner or invalid ownership line | Record missing routing/error; never conclude ordinary approval proves owner protection. Restore validated routing before positive cases. |
| RR-17 | Dismiss a blocking review while another approval remains; separately propose removing owners or weakening workflow | Record that dismissal may mechanically unblock the PR; policy still requires recorded dismissal and fresh human review. Configuration edits receive owner review, which rejects falsely green/no-op verification. |
| RR-18 | Revoke test access, withdraw consent, encounter 403/ambiguous 404 or unsupported settings | Stop affected cells, record partial/not-run and restore only authorized temporary changes; no invented reviewer or enforcement claim. |

Use own accounts with authorized scope; no unsolicited review requests or external
messages are authorized by this document. RR-14/15 require an operator and explicit
permission to attempt those temporary-ref operations. RR-16 needs its own isolated
temporary configuration; never weaken the candidate while treating other cases as
valid. An admin's power to edit/delete rules remains a control-plane limitation,
not an independent approval or an immutable protection guarantee.

The rehearsal alone does not verify `main`. After separate adoption authorization,
repeat settings/owner/access readback and a harmless positive and negative PR check
on the actual target, without forcing/deleting it. Record production-specific
results separately; do not copy rehearsal success into those cells. All required
cases must have actual outcomes or explicit limitations before any scoped
enforcement claim. A missing RR-11 source leaves that cell unrun and its claim open.

This package complements the [#0067 handoff exercise](maintainer-handoff-exercise.md);
neither recruits or qualifies human operators. Published records should contain
consented attribution, public SHA/PR/check references and sanitized observations,
never access rosters, tokens, raw API captures or private media. Primary GitHub
documentation above was observed 2026-10-15; no immutable documentation revision
was established. Local document/JSON checks validate this proposal's consistency,
not execution of any operational case.
