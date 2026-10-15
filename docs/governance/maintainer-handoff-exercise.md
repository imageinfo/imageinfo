# One primary/backup contributor handoff exercise

**#0067 proposal, 2026-10-15**, revision `maintainer-handoff-v1`.
This package defines one future exercise for **GOV-OPEN-01 / OWN-003**. It does
not appoint maintainers, establish backup coverage or demonstrate staffed
operations. No participant has been recruited, contacted or enrolled by this
work. The [blank evidence record](maintainer-handoff-record.template.json) is
explicitly **not run**; names, consent and actual observations remain empty.

Two consenting people are sufficient for this bounded, no-change rehearsal:
the primary prepares a public handoff, and a different backup independently
reproduces and reviews it. Terry may volunteer for one role, but the coordinator
role does not enroll him automatically. Automated agents can help prepare this
package; their reviews/runs do not count as two independent human maintainers.
The [governance proposal](../../GOVERNANCE.md) retains its separate rules for
appointments, independent code review, access and releases.

## Freeze the small task

Exercise **HANDOFF-CLI-01** checks contextual help and JSON syntax-error routing
for one already implemented read-only command. The proposed public source is
[`188049f8ac4c7d0e107439ed385cdd0ee5208201`](https://github.com/imageinfo/imageinfo/commit/188049f8ac4c7d0e107439ed385cdd0ee5208201).
The exercise definition and source commit must be recorded before participants
consent. A later source revision requires an explicit new record; nobody silently
follows a moving branch. This authored practice task alleges no existing bug and
requires no source edit, private board, camera file, release credential or extra
GitHub permission.

The backup's practical deliverable is one short review note answering:
“Do the three help spellings agree at this source revision, does malformed syntax
still win over help with the selected JSON channel, and what exact next step
should another contributor take?” The next step may be “no change needed within
this scope,” a specific documented setup correction, or a reproducible discrepancy.
It must not expand this into XMP/RAW application or storage qualification.

From an ordinary public clone, select the frozen source and use the public
[foundation setup](../foundation/README.md), including native linker prerequisites,
Rust 1.99.0, Python 3.10+ and the pinned schema QA dependency. Run the documented
root formatting, clippy, tests, release build and docs/schema checks on that exact
checkout. The [#0065 hosted evidence](../contributing/clean-machine.md) is a useful
baseline and setup reference; it does not prove this person's environment or a
new candidate passed. Record fresh command/status outcomes, including failures.

After `cargo build --locked`, use the actual executable at
`target/debug/imageinfo` on Unix or `target/debug/imageinfo.exe` on Windows.
The table gives arguments to that executable, rather than a new wrapper command.

| Arguments | Expected process status and observation |
| --- | --- |
| `preview date-time-original --help` | 0; plain contextual leaf help; empty stderr. |
| `help preview date-time-original` | 0; stdout byte-identical to the first help form; empty stderr. |
| `preview help date-time-original` | 0; stdout byte-identical to the first help form; empty stderr. |
| `preview date-time-original --help --bogus --output json` | 2; complete JSON usage-error envelope on stdout, with an error diagnostic on stderr; no selected files or artifacts. |

The final case checks grammar failure before any input selection, including
process status 2, `summary.exitStatus` 2, a request error issue, empty `files`
and `summary.artifacts`, and false
`summary.selectionComplete`. It must not be recorded as a successful metadata
operation. Keep Cargo's build messages separate from executable stdout/stderr
when interpreting these observations.

## Consent and finite sessions

The concrete missing input for Terry is **two willing people**, a mutually useful
session window and permission to publish each person's chosen attribution and
sanitized exercise result. This is a request to identify willing participants,
not authorization for Codex to message or recruit anyone. No standing response
deadline or on-call duty is proposed.

Each person can use this short acceptance statement after seeing the frozen task:

> I consent to act as the primary/backup for HANDOFF-CLI-01 at the recorded source
> and exercise revision, within our agreed session window. This is one public,
> no-change rehearsal with no new access, release or security-response duty.
> My chosen public attribution is recorded separately; I can stop or withdraw.

Record primary and backup separately, with dates, their chosen attribution or
private-only preference, and the agreed window. Declining publication of personal
details does not require participation to be public; the public outcome must then
state that independently held consent/identity evidence is private rather than
inventing a public roster. A reviewer cannot count an anonymous generated record
as verified human independence without checking that evidence privately.

Allow roughly 20 minutes for the primary to prepare the packet and one planned
45–90 minute backup session, depending on downloads/builds. These are planning
estimates, not service commitments. Agree a checkpoint or reschedule if setup
takes longer; missing consent or availability leaves the exercise unrun.

## Transfer, independent work and handback

1. **Primary prepares.** Copy the blank record, record the published exercise
   definition commit and frozen source commit, task, expected observations and
   public setup links. Include the last completed check, outstanding question,
   known setup trouble and exact next action. Include only lawful authored/public
   information. No personal tokens, local board state or restricted media.
2. **Backup receives.** Confirm the packet is accessible using ordinary public
   repository access and that both consents cover the scope. Record receipt and
   take explicit responsibility for this exercise's next action. If anything
   essential is missing, name it before starting; do not guess the primary's intent.
3. **Primary steps away.** During the agreed session the primary does not supply
   undocumented instructions or run the checks for the backup. Public docs and
   normal tools remain available. The backup may stop for any uncertainty; an
   agreed absence is not permission to change access or take over other duties.
4. **Backup verifies.** Use a separate checkout/environment, record source/tool
   identities and actual check outcomes, perform the four process observations,
   and write the scoped review note. Record any help received and whether it
   came from public instructions or the original author. Required private help
   is a handoff gap to fix, not a successful independent reproduction.
5. **Backup hands back.** Record done/remaining work, discrepancies, retained
   notes/artifacts and the proposed next action. The returning primary explicitly
   acknowledges receipt and current owner; absence of acknowledgement leaves the
   handback pending. Do not duplicate work or silently restart from an old note.
6. **Review the exercise.** Compare observed results with the task table and
   note what a new contributor could not infer. Terry can accept the exercise
   package/outcome under the existing project workflow; this is not an independent
   approval of authored code or a release. Agree any small documentation follow-up
   as separate scoped work and retain failures in the evidence.

No PR comment, issue, message, merge, publication, account/access change or
security-intake test is performed by this proposal. Future external postings or
governance actions need their applicable authorization. If the exercise expands
to a real code/contract change, the author cannot supply its independent approval;
follow the existing contribution/review policy with a reviewer other than author.

## Finite failure and interruption prompts

After the practical handback, the two participants can discuss these six prompts
in the same session and record the response in the template. They are tabletop
questions, not instructions to break a checkout, revoke access or inject faults.

| Prompt | Expected bounded response / evidence |
| --- | --- |
| Setup or a required check fails; old CI was green | Record exact revision/environment/failed command, preserve the useful diagnostic, and propose the smallest reproducible setup/fix step. No green outcome by reference to #0065. |
| Primary sends a different revision or unclear extra task mid-session | Retain the original packet; pause or explicitly replace it with a new agreed source/scope. No moving-target verification or unrecorded scope expansion. |
| Backup is unavailable or withdraws consent | Park the task with an unassigned next action and tell the coordinator through an already authorized human route. No fake substitute or automatic appointment. |
| Work is interrupted after some checks | Preserve completed statuses and pending work, name the current owner and resume point. A successor confirms receipt; no automatic replay of unrelated actions. |
| Packet or output appears to contain restricted media, credentials or security details | Stop public sharing; retain only an appropriate private reference, follow [SECURITY.md](../../SECURITY.md) for actual concerns, and request a sanitized packet. Do not attach the sensitive material as exercise evidence. |
| Backup and returning primary disagree about completion | Keep the discrepancy and each observation; separate reproducible facts from the proposed next step, ask for a scoped decision, and leave the result partial/failed until resolved. No self-approved success. |

## Evidence and completion boundary

A future successful practical record requires: two distinct consenting people;
exact source/exercise versions; independent checkout and fresh relevant checks;
all four process observations; a review note and concrete next step; explicit
transfer/handback acknowledgements; and responses to all six tabletop prompts.
Use `completed`, `partial`, `failed`, `withdrawn` or `not-run` honestly. A failed
check or unresolved handback cannot be hidden behind a completed checklist.

The small record should link sanitized evidence, not commit raw logs, private
identity/contact details, credentials or media. A public source hash and
check result are useful; no database, signed ceremony, shared account, privileged
service or new key-management system is needed for this exercise. Participants
use their own ordinary tools and identities.

**Delivered now:** this proposal, blank record and
[independent document/scenario review](maintainer-handoff-validation.md).
**Unrun:** participant consent, actual primary absence, backup execution,
handoff/handback and human outcome review. The scoped #0067 planning handoff can
be reviewed without appointments. GOV-OPEN-01 and #0017 retain the real roster,
scope/access, independent human performance and ongoing maintenance evidence;
this package does not close those obligations or prove release/security staffing.
