# Private security-intake readiness proposal

Status: **proposal for review**, revision `2026-10-15.1`, card **#0066**;
supports **GOV-OPEN-02** under [governance](../../GOVERNANCE.md).
This handoff prepares a setting, procedure, authorization and consenting-operator
package. It does not enable reporting, appoint responders or demonstrate staffed
intake. Actual activation and the test below await explicit authorization and real
consenting people. GOV-OPEN-02 remains open.

## Current observation and limits

An authenticated, read-only GitHub API check on **2026-10-15 at 18:12:47 UTC**
returned **HTTP 200** for
`GET /repos/imageinfo/imageinfo/private-vulnerability-reporting`, with
`enabled: false`. The response selected API version `2022-11-28`.
A separate repository metadata GET reported `imageinfo/imageinfo` as public and
unarchived, with `permissions.admin: true` for the current caller. The local
`origin` points at that same repository. These are bounded observations at that
time, not durable availability or authority to make a setting change.

The GitHub connector did not expose the reporting-settings endpoint; the GitHub
CLI supplied these authorized read-only checks. Initial sandbox network attempts
failed before an HTTP result; the subsequent authorized network check succeeded.
No reporting setting, subscription or access changed. No report, invitation,
message, advisory, CVE request or release was created.

Repeatable read-only commands, with credentials supplied by the operator's
existing approved GitHub authentication rather than command-line token literals:

```powershell
gh api --method GET --include -H 'Accept: application/vnd.github+json' -H 'X-GitHub-Api-Version: 2022-11-28' repos/imageinfo/imageinfo/private-vulnerability-reporting
gh api --method GET repos/imageinfo/imageinfo --jq '{full_name,visibility,archived,permissions}'
```

For a future check, retain the timestamp, endpoint, HTTP result, selected API
version and sanitized flag. Do not publish authorization headers, token scopes,
account recovery material, mail addresses, advisory contents or complete raw
responses. HTTP 200 plus a boolean establishes the returned setting. A transport
failure establishes no setting state; an authentication/permission error or HTTP
404 does not by itself establish that reporting is disabled. Inspect the access
and endpoint before drawing that conclusion.

| Cell | Current disposition |
| --- | --- |
| Repository supports a successful reporting-status query | Observed HTTP 200 on 2026-10-15 |
| Private reporting enabled | Observed false on that date |
| Caller has repository admin permission | Reported by metadata GET; no change authorized by that fact |
| Report button and actual external submission | Unrun; disabled flag is not a submission exercise |
| Consented primary and different human backup | Unassigned; no appointments made here |
| Personal notification settings and delivery | Uninspected and untested |
| Acknowledgement, escalation and backup takeover | Proposed below; unrun |
| Dedicated alternate private route | None established by this work; do not infer an inbox |
| Release, account recovery or production writer readiness | Outside this handoff; no gate satisfied |

The 2026-10-10 check in [the original validation](validation.md) remains historical.
[SECURITY.md](../../SECURITY.md) supplies the public minimal contact-request
fallback while no private route is published. A public issue is never a private
report. Do not attach exploit details, credentials, private media or sensitive
metadata to it.

## Roles and authorization before activation

The following are **role names and unfilled placeholders**, not named appointees.
One person may be the setting operator and primary; the primary and backup must
be different consenting humans. Automated agents do not fill either responder slot.

| Role | Placeholder | Required agreement/evidence |
| --- | --- | --- |
| Approving coordinator | `[COORDINATOR: unconfirmed for this action]` | Terry's explicit scoped authorization or a documented authorized delegate; the existing coordinator role alone is not activation approval |
| Repository setting operator | `[SETTING OPERATOR: unassigned]` | Own GitHub account, verified existing authorized admin access and consent to enable only this repository's reporting |
| OWN-006 primary responder | `[PRIMARY: unassigned]` | Identity, consent, authorized advisory access, monitoring commitment and private escalation route |
| OWN-006 backup responder | `[BACKUP: unassigned]` | Different human, same independently verified access and monitoring ability; accepts takeover during primary absence |
| Test reporter | `[TEST REPORTER: unassigned]` | Consents to one synthetic report and private replies using their own account; uses the external reporting flow rather than an admin-created draft |
| Evidence reviewer | `[REVIEWER: unassigned]` | Reviews sanitized outcomes and distinguishes configuration, delivery and human response |

Before any setting change, the coordinator records an authorization reference
identifying this repository, the setting operator, primary, backup, test reporter,
agreed test window and allowed actions. It must explicitly cover enabling private
reporting, the single synthetic submission, private acknowledgement/takeover
comments and closing that synthetic report. It must also state whether disabling
reporting is authorized if the test fails. Account subscription changes require
each affected account holder's consent. This proposal and standing code
commit/push approval do not authorize those external actions.

Each person confirms their role and chosen public attribution separately.
Keep personal contact, consent evidence, access inventory and private report links
in an agreed restricted location; publish only consented attribution and sanitized
outcomes. Do not invent a team, mailbox or consent. If responders lack necessary
access, stop before activation and request the exact separately authorized access
action; do not grant broad repository permissions merely to finish this exercise.

Proposed response expectations, to be accepted or replaced by both responders
before activation: monitor on their agreed working days; acknowledge within
**three business days**; give an initial triage/next-action update within **seven
business days**; agree the next update date in each substantive reply. Record the
working calendar/timezone, primary absence coverage and backup takeover trigger.
These are suggested commitments, not a current SLA, fix deadline, bounty or
round-the-clock service. A missed acknowledgement target triggers the agreed
private backup escalation; a missed coverage commitment requires a public policy
correction without disclosing the report.

## Proposed activation and notification procedure

Recheck current documentation and repository status before execution; UI names
can change. GitHub describes repository enablement through **Settings → Advanced
Security → Private vulnerability reporting → Enable**, after which the advisories
page offers **Report a vulnerability**. Its documented notification recipients
include repository administrators and security managers who watch **All Activity**
or **Custom → Security alerts**, with notifications enabled. Email delivery also
requires **Watching → Email** in personal notification preferences.
Source: [GitHub configuration guidance](https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/configure-vulnerability-reporting/configure-for-a-repository),
observed 2026-10-15; no immutable revision established.

1. Complete the role/authorization record and confirm a restricted evidence
   location. Verify the exact repository, current setting and setting operator's
   access. Confirm both responders can act using their own authorized accounts.
2. Each responder checks the watch subscription and their personal delivery
   settings against the guidance above, then records only a sanitized confirmation
   and time. They agree a private escalation contact and the time by which the
   backup must take over. Never copy inbox contents or addresses into Git.
3. The authorized operator enables only private vulnerability reporting for
   `imageinfo/imageinfo` through the repository UI. Do not enable organization-wide
   controls, install apps, alter other security settings or add collaborators.
4. Repeat the status GET and record the returned flag and HTTP result. Confirm
   the public advisories page offers the reporting flow, using the consenting
   reporter's account. An enabled flag and visible form establish configuration;
   they do not establish submission, notification or response success.
5. Perform the bounded test below in the agreed window. Until it passes, retain
   an explicit untested/uncovered status; do not advertise staffed intake.

The [GitHub REST documentation](https://docs.github.com/en/rest/repos/repos#check-if-private-vulnerability-reporting-is-enabled-for-a-repository)
describes the status GET, its boolean result and HTTP 200/422 responses. For public
resources it permits unauthenticated status access; fine-grained authenticated
access uses Metadata read permission. The separate enable endpoint requires admin
access (fine-grained Administration write). No mutation command is executed or
needed for this proposal. Source observed 2026-10-15; no immutable revision fixed.

## Proposed single synthetic intake and backup test

GitHub distinguishes a researcher's private report from a maintainer-created
draft. Use a consenting reporter whose account can exercise the external flow;
an admin's draft alone would not test it. The reporter is automatically included
in the proposed advisory collaboration. This participation effect must be part
of their consent. Source: [GitHub reporting guidance](https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/report-privately),
observed 2026-10-15; no immutable revision established.

1. The reporter opens **Report a vulnerability** from the repository's security
   advisories page. Read the displayed policy and actual form, including any
   inherited requirements. Stop and resolve unexpected requirements; do not claim
   to have audited the owner's default form from the local checkout.
2. Submit exactly one report titled `Authorized intake exercise — no vulnerability`.
   Use this authored body, adapted only to satisfy actual required form sections:

   > This is the agreed private intake exercise, not a vulnerability disclosure.
   > No affected software, exploit, real proof of concept or user impact is alleged.
   > Reproduction: submit this authorized synthetic report and verify agreed
   > primary/backup notification and private replies. Impact: none; test only.
   > No attachments, credentials, camera files or personal metadata are included.

3. The reporter records successful submission and time privately. The primary
   independently records whether the agreed notification arrived, its channel
   and time, opens the report using their own account, and privately acknowledges
   that it is a test. The reporter confirms seeing that reply. Opening the page
   after someone sends its link does not count as notification delivery.
4. Simulate primary absence within the agreed window. Without borrowing the
   primary's session or credentials, the backup records their own notification
   arrival, accesses the report and replies privately to accept takeover. The
   reporter confirms receipt. Record elapsed times against the agreed test
   deadlines; a notification to one responder cannot stand in for the other.
5. The operator confirms the synthetic report is not a security risk, posts the
   agreed test-completion explanation and uses **Close security advisory**.
   Do not publish an advisory, request a CVE, create a patch fork or invite other
   collaborators for this test. Verify its final private closed state.

GitHub documents reviewing reports in `Triage`, replying with comments and closing
a report that does not describe a security risk. Regular comments are visible to
the reporter and advisory collaborators; this exercise requires reporter-visible
private replies, not confidential maintainer-only comments.
Source: [GitHub report-management guidance](https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/fix-reported-vulnerabilities/manage-vulnerability-reports),
observed 2026-10-15; no immutable revision established.

If any step fails, record the exact failed cell and next owner. Do not resubmit
repeated reports or silently substitute an admin-created draft. Diagnose the
specific subscription/access/delivery gap and obtain authorization before another
submission or broader action. If the route is enabled but unstaffed, state that
limitation promptly in SECURITY.md; use the agreed failure plan for a separately
authorized disable action if needed. Never imply that disabling a route erases
existing private reports or the duty to handle them.

## Record, decision and continuing operation

Use this minimal record for the later exercise in the restricted evidence
location. Every result starts **not run**; filling a template is not execution.
Publish only a reviewed sanitized summary, without private report URLs or personal
contact details. No additional executable, service or persistent inbox is proposed.

| Record field | Initial value / evidence to retain later |
| --- | --- |
| Definition | `security-intake-2026-10-15.1`; exact proposal commit before execution |
| Authorization | Not granted here; approver, scope, reference and date |
| Operators | Unassigned; role attribution, distinct primary/backup, consent and authorized access checks |
| Response agreement | Not accepted; calendar, targets, private escalation and absence trigger |
| Test agreement | Not agreed; start/end time, per-step deadline, failure/disable decision and reporter consent |
| Before/after status | Before: HTTP 200 / disabled at 2026-10-15 18:12:47 UTC; after: not run |
| Reporter submission | Not run; submission time and restricted report reference |
| Primary notification and reply | Not run; notification channel/time, access result, reply time and reporter confirmation |
| Backup notification and takeover | Not run; independent channel/time, access result, takeover time and reporter confirmation |
| Closure | Not run; closing operator/time, private closed-state confirmation; no publication/CVE |
| Outcome | Not run; passed/failed/partial, failed cells and next owner; reviewer/date |
| Public policy update | Not run; sanitized evidence and exact SECURITY.md revision, chosen attribution/consent |
| Recheck | Not scheduled; responsible primary/backup and next agreed date/trigger |

Only after successful independent notification, access, private acknowledgement,
backup takeover and closure should the coordinator accept the scoped intake test.
Update SECURITY.md with the verified private route, consented responder attribution
or public role contact, accepted response expectations, check date and remaining
coverage limits. An enabled route with a failed test remains enabled-but-unverified;
it does not close GOV-OPEN-02. No test promises future uninterrupted delivery.

For real reports, follow [the security policy](../../SECURITY.md) and
[incident/recovery runbook](release-and-recovery.md). Keep private triage evidence,
agree next updates and disclosure with the reporter, and limit reproductions to
necessary lawful material. Recheck coverage when a responder leaves, permissions
or notifications change, and before claiming release readiness. Agree an explicit
next review date when accepting the exercise. Notification mail and a successful
test do not establish account recovery, fix capacity or a supported release policy.

## Handoff acceptance and verification

#0066's bounded deliverable is the current read-only availability observation plus
this reviewable activation/notification/test/consent package. The actual setting
change, staffing, subscriptions, report exercise and GOV-OPEN-02 acceptance remain
unrun. This separation follows the ticket's explicit scope; it is not a claim that
the broader security-readiness action is complete.

Review checks cover the exact repository and observation date; transport versus
HTTP/permission/setting distinctions; unfilled consenting roles; external-action
authorization; a synthetic-only test; independent notification and takeover;
failure handling; private evidence boundaries; primary-source attribution and
internal links. Run `python scripts/check_docs.py` and `git diff --check` after
integration. No runtime behavior or repository setting changes require a software
test claim for this documentation handoff.
