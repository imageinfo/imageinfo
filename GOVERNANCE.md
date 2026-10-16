# Project governance

Status: **proposal with accepted solo-operation scope**, original revision
`2026-10-10.1`, card **#0009**; #0154 decision accepted **2026-10-16** below.
This document assigns proposed responsibilities; it does not grant GitHub access,
appoint additional maintainers, enable repository rules or authorize a release.

imageinfo is in requirements and research. Terry Ott is the current project
coordinator and accepts this phase's work. Additional technical stewards, backup
maintainers and release/security operators have **not been appointed by this
proposal**. The project has not demonstrated operational independence from Terry.

Start with [contributing](CONTRIBUTING.md), [security reporting](SECURITY.md), and
the [release and recovery runbook](docs/governance/release-and-recovery.md).
[Validation and open actions](docs/governance/validation.md) distinguish the
documented process from readiness still to be established.

## Accepted initial operating scope — #0154

On 2026-10-16, Terry explicitly selected **solo, best-effort operation**. Terry is
the sole project coordinator and conduct/escalation contact. There is no appointed
human backup, staffed response team, guaranteed response time or continuity promise.
Codex and its subagents assist with work; they do not count as human backups or
independent human reviewers.

The six OWN areas below remain a responsibility map, not six staffed specialties
or demonstrated technical coverage. Additional consenting maintainers, independent
handoff exercises and shared ownership remain future goals under GOV-OPEN-01.
GOV-OPEN-06 retains the existing contributor verification evidence and records
Terry as the conduct/escalation contact; it does not establish a staffed escalation
service. Public contact requests should contain minimal information and follow
[SECURITY.md](SECURITY.md) for security concerns. No new private coordination route
or public personal contact detail is adopted by #0154; the subsequent #0155 route
decision is recorded below.

This accepted scope supersedes treating primary/backup staffing proposals as an
already adopted requirement for initial solo operation. It does not establish
operational independence or complete account recovery, approve release publication
or change format/write guarantees. The subsequent accepted
[#0159 release policy](docs/governance/first-release-policy.md) makes Terry the
release authority for a source-only unsigned reader alpha, using automated checks
and agent review without an independent human verification/backup prerequisite or
claim. Exact candidate approval remains required.

Terry selected **#0157 option A** on 2026-10-16: retain direct commits/pushes after
required checks, practical agent review without an independent-human claim, and
Terry's review/acceptance of board handoffs into Completed. No mandatory PR
approvals, CODEOWNERS or new branch-protection/ruleset requirements are adopted.
Public contributors continue to use PRs. This accepted solo workflow supersedes
the historical independent-human/enforced-review proposal as a current gate;
applicable capability, correctness, provenance and preservation evidence remains
required. See the [review-policy record](docs/governance/review-routing-plan.md).

Terry subsequently adopted #0155's GitHub private-reporting route. It is enabled
and configuration-verified, with Terry as sole best-effort responder. The synthetic
report attempt was refused for the available administrator account; external
submission and notification delivery remain unverified. See
[SECURITY.md](SECURITY.md) for the current route and limits. Historical primary/backup
security proposals do not impose a staffing prerequisite on this solo scope or
establish staffed coverage.

## Decisions and responsibilities

**GOV-001 — Keep project decisions public and specific.** Requirements, rationale,
compatibility differences, source references and acceptance evidence belong in the
repository or linked public issues/PRs. Private security details, access inventories
and restricted media stay private. A local board may coordinate work, but an outside
contributor must not need board access or a private chat to understand a change.

The initial product scope is EOS R5 full RAW CR3 metadata, associated XMP and stored
previews, with broader RAW and eventually full ExifTool functionality later. Terry
explicitly advances language/implementation selection; no workflow document does
that implicitly. MIT is locked. Architecture starts from the product requirements,
with conventional code and a reason for deliberate departures from convention.

**GOV-002 — Separate proposed, accepted, implemented and verified.** A merged document
can describe a proposal. Record acceptance with decision, scope, approver, date and
linked evidence; do not infer it from a commit, generated text or a bot moving a card.
Implementation needs a source revision; verified capabilities need the applicable
fixture/operation/platform evidence. No single status promotes all camera variants,
tags, write operations or storage profiles together.

Keep stable requirement and capability identifiers. For a substantial decision,
record the concrete problem, ordinary alternatives, chosen behavior, tradeoff,
affected contracts and remaining limitations near the affected specification.
A small correction does not need a new committee or a separate architecture essay.

**GOV-003 — Give each critical area a primary and a trained backup.** The following
is the proposed ownership map. The coordinator routes work while positions are
unfilled; that is not evidence of expertise or redundancy in every area.

| Area | Responsibility | Technical primary / backup |
| --- | --- | --- |
| OWN-001 — RAW formats and preservation | Per-camera/layout recognition, fields, references, sensor/calibration/preview protection; never blanket write enablement | Unassigned / unassigned |
| OWN-002 — Metadata and compatibility | Identity/value schemas, mappings, source baselines, API/CLI semantics and accepted differences | Unassigned / unassigned |
| OWN-003 — CLI and integration | Help/menus, scripting, result schemas, request isolation and accessibility | Unassigned / unassigned |
| OWN-004 — Evidence and performance | Lawful fixtures, independent validators, reproducible recipes, malformed inputs and measured limits | Unassigned / unassigned |
| OWN-005 — Releases and infrastructure | Pinned builds, artifact verification, publication, access inventory and recovery drills | Unassigned / unassigned |
| OWN-006 — Security response | Private intake, reproduction, mitigation, coordinated disclosure and incident follow-through | Unassigned / unassigned |

One person may cover several areas; the primary and backup for a critical duty must
be different people. A backup must perform the documented work independently, not
merely appear in a table. Before enabling production RAW writes or claiming release
redundancy, fill the relevant roles and demonstrate the handoff. Until then keep
unverified capabilities unavailable and state the staffing limitation openly.

**GOV-004 — Make maintainership earned and reversible.** A candidate demonstrates
sound scoped changes, review judgment, provenance care and ability to reproduce
the area's checks. Agree a limited responsibility with the coordinator, publish
the role/scope after the person consents, and pair on a handoff before granting
only the needed access. Existing owners perform any access changes through a
separately authorized task. No account, team or access grant is invented here.

On departure, transfer open work and ownership, test the replacement's access, then
remove unnecessary permissions and rotate affected project credentials as warranted.
Preserve contributor credit. Review the roster when responsibilities change and
before each release; stale assignments must not count as active coverage.

## Review and maintenance

**GOV-005 — Keep review small and evidence-driven.** Ordinary changes should have
one focused problem, clear before/after behavior, relevant checks and honest limits.
Favor idiomatic names, standard types and straightforward control flow. Explain
non-obvious tradeoffs near the code; do not make reviewers decipher cleverness.
Review disagreement should identify the requirement, evidence or simpler alternative.

Historical future multi-maintainer proposal (not a gate for the accepted #0157
solo workflow): an author does not supply their own independent
approval. A human reviewer other than the author reviews format/contract changes;
RAW mutations require relevant format and preservation evidence. Release verification
uses a second qualified person. Several automated agents do not constitute multiple
independent maintainers. When expertise is missing, retain the gap and keep the
affected capability disabled rather than inventing an approval.

The current solo development workflow retains Terry's standing authorization for direct
commits/pushes and his review through the local board. Bots hand off to Ready for
review; Terry accepts into Completed. This proposal does not retroactively claim
independent reviews or change that authorized workflow. Proposed future review
rules are not configured GitHub enforcement until separately adopted and verified.

**GOV-006 — Triage with an accountable next step.** Public contributors use
[GitHub issues](https://github.com/imageinfo/imageinfo/issues) and PRs. Capture
affected revision, command/workflow, camera/mode, expected/actual result, minimal
lawful reproduction and relevant requirement/capability IDs. Do not demand personal
photos or a local-board account. Follow SECURITY.md for suspected vulnerabilities.

Prioritize data loss/corruption, unsafe writes, security and incorrect privacy claims
before feature breadth. Then consider blocked dependencies, first-R5 milestone value,
reproducibility and available expertise. Record owner or explicitly unassigned state,
next action, dependencies and why work is deferred. Do not close a reproducible bug
merely because a maintainer cannot obtain the contributor's camera.

**GOV-007 — Treat knowledge as part of the change.** Every new supported RAW variant
needs source/provenance notes, exact capability cells, admitted regression fixtures,
bounded malformed-input behavior, applicable independent evidence and contributor
instructions. Reads, writes, insertion/deletion, previews and preservation are
separate claims. Require a second person to use the instructions for critical areas;
write down anything they needed from the original author.

**GOV-008 — Version public behavior deliberately.** Review incompatible schemas,
CLI grammar, persistent protocols, value conversions, defaults and safety guarantees
as public changes. Name affected versions and migration behavior, preserve regression
cases, and record an accepted difference instead of quietly changing the oracle.
Before a software release, adopt a version/deprecation policy and support window;
there are no released versions or compatibility windows to promise today.

**GOV-009 — Release only evidenced capabilities.** The runbook defines a candidate,
independent verification, publication evidence and rollback response. A green build
or a generated checksum is not proof of metadata correctness or reproducibility.
Never use a release announcement to turn proposed capabilities into verified ones.
Release authority, supported platforms and artifact signing choices remain explicit
readiness decisions; this card publishes no software release.

**GOV-010 — Security and recovery need real operators.** A documented process does
not replace monitored intake, individual account recovery, multiple authorized owners
and exercised restoration. Keep secrets and personal recovery codes out of Git and
public issues. A second owner uses their own identity; do not share one maintainer's
personal account credentials as a continuity strategy.

**GOV-011 — Resolve disagreements without procedural overhead.** Start in the PR or
issue with the requirement and alternatives. Ask the relevant steward and an
independent reviewer to resolve technical disagreements. During bootstrap, Terry
records the scoped product decision or explicitly defers it; silence is not approval.
Safety/provenance claims still need evidence regardless of who decides. Contributors
may propose a reconsideration with new evidence; retain the prior decision history.

Discuss work respectfully, give concrete actionable feedback, and make ownership
boundaries discoverable. Report conduct concerns through a minimal contact request
if a private channel is needed; do not publish personal allegations or private data
as routine issue content. A dedicated conduct/escalation contact remains an open
readiness decision rather than a fictitious staffed team.

**GOV-012 — Make the limitations visible.** The open actions below have to be done
by actual people, not marked satisfied by merging this file. Track their owners,
verification dates and sanitized evidence before claiming shared maintenance.

## Open readiness decisions

| ID | Decision/action | Completion evidence |
| --- | --- | --- |
| GOV-OPEN-01 | Recruit/confirm technical primaries and backups | Named consented roster, scoped access and independent handoff evidence |
| GOV-OPEN-02 | Verify the adopted solo private-reporting route | Enabled flag/public entry verified under #0155–0156; synthetic attempt refused for admin account; external submission/delivery unverified, Terry responds best effort |
| GOV-OPEN-03 | Establish owner/access continuity | Authorized additional owner as appropriate, private access inventory, separate account recovery and recovery drill |
| GOV-OPEN-04 | Retain and verify the accepted #0157 solo review workflow | Required checks, authorized direct pushes and Terry board acceptance; no new enforcement adopted, future multi-maintainer routing remains unselected |
| GOV-OPEN-05 | Execute the accepted #0159 solo source-alpha policy | Exact candidate checks, automated/agent review, Terry's candidate approval and actual publication verification; no human backup or independent human verification claim |
| GOV-OPEN-06 | Publish contributor verification commands for the eventual toolchain | Clean-machine setup/checks reproducible without private paths, plus reviewed CI permissions and a conduct/escalation contact |

The [security-intake package](docs/governance/security-intake-readiness.md),
[owner-access continuity plan](docs/governance/owner-access-continuity.md),
[review-routing plan](docs/governance/review-routing-plan.md) and
[first-release policy proposal](docs/governance/first-release-policy.md) prepare
bounded follow-up decisions and tests. They do not establish staffed operations,
grant permissions, activate settings or publish a release. The
[artifact provenance policy](docs/provenance/README.md) supplies the #0010 review
process under locked MIT. Subsequent native implementation and its verified limits
are documented in the [foundation](docs/foundation/README.md) and
[reader](docs/reader/README.md) guides; their existence does not close these
operational-readiness actions.
