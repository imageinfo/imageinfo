# Release stewardship and access recovery

Status: **proposal for review**, revision `2026-10-10.1`, card **#0009**.
This runbook is preparation for future software releases. There is no selected
toolchain, build pipeline, signing arrangement or exercised recovery process yet.
No access grant, repository-rule change or release publication is performed here.

See [governance](../../GOVERNANCE.md) for role/decision rules and
[security reporting](../../SECURITY.md) for the currently available intake path.

## Before a release can be considered ready

The release coordinator records a candidate commit, proposed version, scope and
named verifier. A second qualified person must be able to follow the public setup,
build and validation instructions independently. For production RAW writes, the
relevant format primary/backup and evidenced writer/storage profiles must exist.
Missing people, fixtures, signing/recovery choices or platform evidence are explicit
readiness gaps, not checkboxes an automation can waive.

| Gate | Evidence the coordinator and verifier inspect |
| --- | --- |
| Scope and decisions | Accepted native behavior, supported camera/mode/tag/operation/storage cells, known gaps, migrations and version/support policy |
| Source identity | Exact commit/tag intent, clean checkout, reviewed dependencies and source/distribution identities |
| Reproducible setup | Public commands and pinned environment/dependencies, documented locale/timezone/flags and no private author-machine prerequisite |
| Provenance | Apply the [artifact review workflow](../provenance/review-workflow.md) to exact source/data/dependency terms, required notices, admitted uses and assembled release contents |
| Correctness | Applicable metadata/model/CLI/schema cases, RAW structure/payload/interpretation evidence, independent validators and scoped platform results |
| Safety | Refusal paths, stale/concurrent sources, originals, atomic visibility/durability profiles, cancellation, interrupted recovery and privacy limits |
| Resource behavior | Measured workload/limit evidence from the performance program, including failures and uncertainty |
| Artifact contents | Expected binaries/packages and notices only; no private corpus, board data, credentials, developer logs or unintended executable extensions |
| Reproduction | Independent build of the declared reproducible artifact set and comparison of hashes/bytes; investigate any mismatch |
| Operations | Named publication/backup operator, private security route tested, access inventory and recovery drill current |

An ordinary rebuild from documented inputs establishes that instructions can be
followed. A reproducible-build claim additionally requires identical bytes for
the declared artifact set. Define how unsigned build outputs relate to signing,
timestamps or packaging rather than hiding differences in a blanket normalization.
If some artifacts are not reproducible, disclose exactly which ones and why; do
not label the entire release reproducible from a successful compilation alone.

## Prepare, verify, publish

1. **Prepare the candidate.** Freeze the source revision, supported capability
   manifest, schema/protocol versions and release notes. Link the prior release's
   compatibility changes, fixed issues, known limitations and evidence revisions.
2. **Build in a clean declared environment.** Record toolchain, dependencies and
   input identities, exact commands, output hashes and relevant logs. A source
   archive needs the same identity/provenance discipline as a binary package.
3. **Verify independently.** The second operator recreates the declared artifact
   set and runs the required checks using the documented instructions. Record
   verifier, date, environment, artifact hashes, discrepancies and outcome.
4. **Approve the concrete candidate.** The authorized release steward accepts this
   exact commit/artifact/evidence set. Approval of earlier requirements, or standing
   permission to push source commits, does not by itself publish a software release.
5. **Publish through the chosen least-privilege route.** Keep build validation and
   publication credentials separate. Do not expose publishing secrets to untrusted
   pull-request code. Confirm the public version, source commit, notes, artifact
   identities and verification information agree after upload.
6. **Record the handoff.** Retain the public manifest, reproducibility result,
   compatibility/support statement and known gaps. Store private operational records
   separately. A backup operator should be able to explain and repeat the release.

Signing/attestation technology, package registries, CI platform and dependency tools
are intentionally unspecified until the implementation/distribution decision.
Selecting a technology does not replace the roles, evidence or independent checks.

## A bad release or suspected compromise

The incident coordinator distinguishes an unsafe capability, ordinary regression,
bad artifact and compromised publication channel. Preserve exact affected versions,
hashes, reports and relevant logs privately as needed. Stop further publication or
disable the affected capability in a reviewed fix; do not erase the evidence.

Tell users which versions/operations are affected, the recommended avoidance or
rollback action and the limits of recovery. If credentials may be compromised,
authorized owners revoke/rotate the relevant project credentials and review related
access before republishing. No automated rollback should overwrite user photographs.

Prefer a corrected, separately versioned release with traceable source/artifact
identities. Do not silently move an existing release tag or replace its bytes while
retaining the same published checksum/version. If unsafe assets must be withdrawn,
record the withdrawal and reason without redistributing secrets or exploit details.
Coordinate sensitive disclosure through the security process; communicate confirmed
facts and uncertainty rather than a fabricated all-clear.

## Private operational inventory

Keep a maintained access inventory outside the public repository. It records the
service/resource, individual owner and backup, required privilege, credential
custody mechanism, expiration/rotation policy and last verified recovery procedure.
Examples include GitHub organization/repository ownership, publication accounts,
signing material, domain ownership if used, and any private fixture/evidence store.
Do not invent services the project has not adopted.

The public repository records roles, process and sanitized verification dates.
It never contains secret values, recovery codes, service tokens, private contacts
or copies of sensitive security reports. Each maintainer maintains their own account
recovery methods. Personal recovery codes are not a shared team backup; another
authorized owner should be able to manage project access using their own identity.

## Recovery and succession exercises

Run these after relevant role/infrastructure changes and before claiming release
readiness. Record participants, scoped actions and outcome without exposing secrets.
Avoid destructive drills on the only live publication or fixture store.

| Scenario | Exercise and acceptance evidence |
| --- | --- |
| Primary maintainer unavailable | Backup locates current scope, reproduces an area's checks and handles a sample issue without private author instructions; document every missing step |
| Publisher unavailable | Backup builds/verifies a candidate from a clean environment and demonstrates the authorized publication path in an agreed safe rehearsal |
| One account locked out | A separately authorized owner verifies project administration from their own account; personal account recovery stays with its owner |
| Lost workstation | Recover repository, public recipes and permitted evidence from independent copies; verify identities and access without depending on a single laptop |
| Restricted fixture store unavailable | Restore an authorized copy and verify manifests/hashes/access restrictions; if rights or bytes are missing, mark dependent evidence unavailable |
| Maintainer departure | Transfer accepted duties, verify replacement access, revoke unnecessary permissions and rotate affected project credentials without removing attribution |
| Suspected token/signing-key compromise | Rehearse the inventory-driven revoke/rotate/reverify sequence; preserve incident facts and distinguish trust in old artifacts from new credentials |

If the sole organization owner becomes unreachable before continuity is established,
this documentation cannot guarantee control of the original organization. Record the
limitation; use the platform's legitimate recovery process. A community fork may
preserve public work under its applicable terms, but it is not proof of recovered
official accounts, private assets or signing identity. Do not impersonate ownership.

## Readiness review record

For each adopted operational control, record: control/area, named primary/backup,
authorization scope, verification date, procedure revision, evidence location,
sanitized outcome and next action. An unsuccessful drill remains unsuccessful until
repeated evidence fixes the gap. Do not populate this record with fictitious people
or successful dates just to make the proposal look staffed.

## Primary references

Observed **2026-10-10**. These are live unpinned reference pages; this document does
not assert that their settings are enabled in imageinfo.

- [GitHub ownership continuity](https://docs.github.com/en/organizations/managing-peoples-access-to-your-organization-with-roles/maintaining-ownership-continuity-for-your-organization) explains the risk of an unreachable sole owner and recommends more than one owner. Real authorization and consent are still required before adding anyone.
- [GitHub account recovery methods](https://docs.github.com/en/authentication/securing-your-account-with-two-factor-authentication-2fa/configuring-two-factor-authentication-recovery-methods) describes individual recovery arrangements and secure handling of personal recovery codes.
- [GitHub CODEOWNERS](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners) documents ownership-based review requests and permissions. A file alone is not a configured required-review rule; actual people/teams and enforcement must be checked.
- [GitHub private reporting](https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/configure-vulnerability-reporting/configure-for-a-repository) describes enabling private intake and responder notification dependencies. The repository check on 2026-10-10 reported it disabled; no setting was changed here.
- [Reproducible Builds definition](https://reproducible-builds.org/docs/definition/) distinguishes reproducing the specified artifact bytes from merely compiling the source. The release recipe must name its inputs, environment and artifact set.
