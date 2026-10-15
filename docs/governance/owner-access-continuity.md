# One owner-access continuity drill plan

**#0068 proposal, 2026-10-15**, revision `owner-access-continuity-v1`.
This is a planning handoff for **GOV-OPEN-03**, under
[governance](../../GOVERNANCE.md) and the
[release/recovery proposal](release-and-recovery.md). No private inventory was
collected and no account drill was performed. No owner, backup or reviewer is
appointed by this document. The [blank record](owner-access-continuity-record.template.json)
is **not run**; copy and fill it only in an agreed restricted location after
authorization. Do not commit a populated private record.

The future exercise, **ACCESS-01**, asks one narrow question: while one project
owner is treated as unavailable, can a different, already authorized human locate
the private access record and independently inspect the project's existing
GitHub organization/repository administration access using their own account?
It checks existing access without changing it. It does not recover a locked
account, validate a recovery code, restore a store, publish an artifact or prove
that a future access-changing operation will succeed.

## Available evidence and unavailable inputs

The repository identifies `imageinfo/imageinfo` as its GitHub project and Terry
as coordinator. These public facts do not establish organization ownership or
the number of owners. The [#0066 observation](security-intake-readiness.md)
reports repository admin permission for its caller on 2026-10-15; repository
admin permission alone does not establish organization owner status or a backup.
No fresh account, membership, owner-list or recovery check was made for #0068.

| Input | Disposition at this handoff |
| --- | --- |
| Public governance/runbook and GitHub documentation | Available; process proposals and platform guidance only |
| Actual owner roster/count and organization-role evidence | Unavailable; not inspected or inferred from public membership |
| Consenting primary owner and different existing backup owner | Unconfirmed; no recruitment, appointment or invitation performed |
| Authorization for a private inventory/check session | Not granted by this plan; scope and participants must be recorded later |
| Restricted inventory location, custodian and independent backup access | Unavailable; no private store selected, created or inspected here |
| Individual account recovery preparedness | Uninspected; no credentials or recovery material requested |
| Other adopted publication/signing/domain/private-store resources | Complete inventory unavailable; do not assume a service exists or is absent |
| Actual primary absence, independent administrative inspection and handback | Unrun |
| Account recovery, access changes and restoration | Outside ACCESS-01 and unrun |

Neither this plan nor the separate
[contributor handoff](maintainer-handoff-exercise.md) establishes access redundancy.
The [security-intake proposal](security-intake-readiness.md) has its own consenting
responders, settings and delivery exercise; those roles and outcomes cannot be
substituted for owner continuity.

## Authorization and operators before any session

All roles below remain unfilled. Terry may participate after consenting to a
specific role; the coordinator designation does not enroll him. Automated agents
do not count as independent human owners.

| Role | Required evidence before starting |
| --- | --- |
| Approver | Terry or a documented authorized delegate records scoped approval for this private read-only exercise |
| Primary owner / inventory custodian | Consents; confirms existing authority for the exact organization, repository and inventory records to be inspected |
| Backup owner | Different consenting human, already authorized as an organization owner; uses their own identity and existing access without the primary's session |
| Evidence reviewer | Authorized to inspect the minimum private evidence and verify the distinct identities, scope and outcomes; may be the returning primary for this limited exercise |

The private authorization record must name the exact organization and repository,
participants and consent references, definition commit, permitted read-only pages
or queries, restricted record location and its permitted readers. Agree a start,
end and stop contact using an existing human communication route; allow one
proposed **30–45 minute** session, adjusting the bound before starting if needed.
Record how the backup can access the approved nonsecret inventory without the
primary's workstation/session and who receives the handback. Agree chosen public
attribution separately, or keep identities private with reviewer confirmation.

Approval covers only inventory facts, ordinary authentication by each account
holder, administrative inspection and the tabletop prompts below. Each person
consents to inspection of their relevant role evidence and may withdraw. Personal
recovery preparedness is an optional private self-attestation by its account
holder, never permission for another person to inspect recovery secrets. Missing
consent or authority stops the corresponding check before access.

Standing source commit/push permission does not authorize private account drills,
access grants, invitations, role changes, repository/security settings changes,
new tokens/apps/keys, credential retrieval, rotation or revocation, recovery-code
view/download/copy/use, sign-out/session invalidation, account lockout or messages
to other people. None is needed to execute ACCESS-01. Any later such action is
separate work requiring its applicable scoped authorization; do not expand this
exercise to make it pass.

## Private inventory: minimum useful facts

Use an existing approved restricted document or file. No new service, shared
account, signing ceremony or encryption/key-management system is proposed.
The inventory contains metadata, not secrets. Limit it to resources the custodian
confirms are adopted; mark unknown resources **unknown**, not absent. Begin with
the named GitHub organization and repository. Other adopted resources may be
listed as gaps, but this one exercise performs no checks against them.
Inventory completeness for ACCESS-01 means the agreed GitHub fields are evidenced
and other-resource unknowns are disclosed. It is not a complete project-wide
resource audit; those unknowns remain open after a completed bounded drill.

For each confirmed resource record privately:

- Exact service/resource identity, purpose and why continuity matters.
- Actual individual primary and backup, consent/authorization references and
  required versus currently observed privilege. Use `unassigned` or `unknown`
  where appropriate; an invited person is not an active authorized backup.
- Nonsecret custody description for any project credential, responsible account
  holder, expiry/review or rotation policy if one exists, and approved recovery
  procedure reference. Never copy the credential or its retrieval instructions.
- Inventory custodian/readers, last check date, observation method, result and
  restricted evidence reference; record unavailable access and dependencies.
- Current next action, consenting responsible person or `unassigned`, and agreed
  review date or trigger. Do not convert a proposed action into granted authority.

The owner roster, private usernames/contacts, access paths, inventory location,
custody details, screenshots and account observations stay private. Do not put
them in Git, public issues/PRs, CI artifacts, local-board comments or chat transcripts
used as public evidence. Public material is limited to this procedure, the blank
record and a reviewed summary of date, definition revision, bounded checks,
sanitized outcome and remaining gaps. Publish names only with separate attribution
consent; omit owner counts and identifying failure details from the public summary.
The private reviewer must still verify independence rather than accepting invented
anonymous participants. Do not collect passwords, tokens, private keys, passkeys,
recovery codes, personal mail, sensitive reports or fixture contents in either record.

## Proposed read-only procedure

1. **Freeze and prepare.** Record the published definition commit and authorized
   resource scope, consent, session bound and restricted destination. The custodian
   prepares the minimum inventory above, identifying missing fields explicitly.
   Confirm the backup can locate that record through existing authorized access.
   If its only copy depends on the primary's unavailable machine, record that gap;
   do not copy unrelated private files or change store permissions.
2. **Verify existing roles.** Each owner uses their own ordinary GitHub account.
   Inspect the exact organization's **People** page and filter **Role** to owners;
   check the relevant participants, all pages and active status privately. Record
   time, resource, method and result without exporting the roster. Inspect the
   repository's existing access overview and distinguish organization ownership
   from repository administration. Do not select **Change role**, invite anyone
   or save a settings change. A public contributor list or the ability to clone
   the public repository is insufficient evidence.
3. **Primary steps away.** Simulate unavailability only by agreed nonparticipation
   during the remaining bounded session. Keep accounts, sessions, devices and
   services intact. The backup independently locates the inventory, identifies
   the relevant resource and own existing authority, then repeats the read-only
   organization/repository inspection without the primary's account, machine or
   undocumented guidance. Record any help needed; required primary assistance
   leaves independent access unproved.
4. **Discuss the failure prompts.** Record the backup's proposed next action for
   each row below. These are tabletop answers, not instructions to cause faults,
   retrieve secrets, open recovery flows or contact support.
5. **Hand back and review.** The backup records completed/pending checks, failed
   cells and the next proposed action. The returning primary acknowledges receipt
   and current responsibility; the reviewer verifies evidence, distinct humans,
   permitted scope and outcome. Agree the next review trigger/date and responsible
   person. A pending acknowledgement or discrepancy leaves the result partial.
   Produce a sanitized public summary only after its privacy review.

For these inspections prefer a connected GitHub tool if it exposes the exact
read-only fact. At planning time the connector exposed repository metadata,
authenticated-user organization memberships and one-user repository permission;
those capabilities alone do not establish a complete owner roster or individual
recovery readiness. No connector account lookup or CLI account query was run for
this plan. The authorized human UI inspection above is the documented fallback;
no CLI command, token scope expansion, new credential or raw response export is
needed. Permission denial, incomplete pagination, hidden membership or a transport
failure is **unknown/unavailable**, not proof that no owner exists.

## Finite prompts and outcomes

| ID / prompt | Required bounded response |
| --- | --- |
| ACCESS-F01 — No distinct existing owner, consent or scoped authority | Do not start the account check. Record unrun/unavailable and the missing prerequisite; any appointment/access grant is separate work. |
| ACCESS-F02 — Inventory missing, stale, inaccessible or dependent on primary | Retain the exact gap and last completed step; no guessed owner, new store or permission workaround. Independent inventory access has not passed. |
| ACCESS-F03 — Public clone works, but owner/admin evidence is denied or incomplete | Record the failed/unknown cell and observation method. Do not count public read access, repo admin or one visible owner as a complete owner audit. |
| ACCESS-F04 — Primary's account is hypothetically locked out | Backup describes use of their own existing project authority; personal recovery stays with the account holder. Do not test a code, borrow a session or promise support can restore access. |
| ACCESS-F05 — Hypothetical lost workstation or unavailable private store | Identify the permitted independent copy/procedure if known, otherwise state unavailable. No restoration, private media retrieval or copying is performed. |
| ACCESS-F06 — Hypothetical departure or suspected credential compromise | Identify responsible authority and separate inventory-driven transfer/revoke/rotate work; preserve uncertainty. Do not perform that work or contact anyone during the exercise. |
| ACCESS-F07 — Interruption, withdrawal, sensitive material or disagreement | Stop affected work, retain only appropriate restricted notes, record completed/pending steps and current responsibility. No public attachment of sensitive material; unresolved outcome remains partial/failed/withdrawn. |

Use `not-run` before execution; `withdrawn` if consent ends; `partial` if a subset
is observed but required evidence or handback is missing; `failed` if an attempted
required check contradicts its expected result; and `completed` only when all
authorized ACCESS-01 checks, seven prompts and review/handback are complete with
no unresolved required gap. Record each cell independently so a failure is not
hidden by the overall status. An `unavailable` check cannot count as passed.

A completed ACCESS-01 result supports only the observed independent inventory
and existing administrative inspection at that time. It does not prove personal
account recovery, access-changing operations, notification coverage, publication,
store restoration, durable access or future availability. Optional account-holder
self-attestation of preparedness remains an attestation, not a recovery test.
Recheck after relevant ownership/access/resource changes and before claiming
release readiness; the proposed timing is not a staffed service commitment.

**Delivered now:** a reviewable private inventory/check/drill plan and blank record.
**Unrun:** private inventory, all participant authorizations/consents, actual access
checks, absence drill, tabletop responses and handback. **GOV-OPEN-03 / #0017 stay
open** for real ownership, private inventory, separate personal recovery and
applicable exercised evidence. #0068's planning handoff closes none of those
operational gaps and enables no product capability or storage/RAW profile.

## Primary platform references

Observed **2026-10-15**; live GitHub documentation, no immutable revision fixed.
Recheck before execution. These describe platform procedures, not imageinfo settings.

- [Ownership continuity](https://docs.github.com/en/organizations/managing-peoples-access-to-your-organization-with-roles/maintaining-ownership-continuity-for-your-organization): GitHub recommends at least two organization owners because an unreachable sole owner risks access. This is no evidence of the project's actual owner count or authorization to promote anyone.
- [Viewing organization roles](https://docs.github.com/en/account-and-profile/how-tos/organization-membership/viewing-peoples-roles-in-an-organization): organization members can inspect People and filter by role. Inspecting roles is distinct from changing them.
- [Viewing repository access](https://docs.github.com/en/organizations/managing-user-access-to-your-organizations-repositories/managing-repository-roles/viewing-people-with-access-to-your-repository): organization owners can inspect the repository access overview of teams and people. ACCESS-01 needs no roster export.
- [Individual recovery methods](https://docs.github.com/en/authentication/securing-your-account-with-two-factor-authentication-2fa/configuring-two-factor-authentication-recovery-methods): personal recovery codes must not be shared; generating a new set invalidates older codes. This plan never opens, collects, generates or uses them.
- [Lost-2FA recovery limits](https://docs.github.com/en/authentication/securing-your-account-with-two-factor-authentication-2fa/recovering-your-account-if-you-lose-your-2fa-credentials): GitHub warns that support cannot restore a 2FA account when its authentication and recovery methods are lost. Another project owner cannot thereby recover that person's account. No recovery request is submitted here.
