# First release authority and support boundary

Status: **accepted policy**, revision `2026-10-16.1`, **#0159 / GOV-OPEN-05**;
adapted from the #0070 proposal to #0154's accepted solo operation. Terry explicitly
selected option A on 2026-10-16. The adopted first distribution is
**`v0.2.0-alpha.1`, a source-only GitHub prerelease of the bounded native
EOS R5 full RAW reader**. Terry retains release authority. Support is best effort
for the latest alpha, without response deadlines or promised backports. Automated
checks and agent review must be identified honestly; independent human verification
and backup coverage are not claimed or required for this solo alpha. The exact
candidate and notes must be prepared for Terry's approval before publication.
This policy decision creates no candidate, tag, release, uploaded package, signing
identity or account/access change.

This narrows the earlier [release/recovery proposal](release-and-recovery.md)
to the implemented Rust package. Its statements that implementation selection
and a build pipeline are still undecided describe the 2026-10-10 proposal;
[ADR-0011](../implementation-selection/README.md), the root package and the
[contributor evidence](../contributing/clean-machine.md) now supply that foundation.
Release operation remains unrun; no independent human release verification is claimed.

## Adopted choice and ordinary alternatives

| Decision | Adopted choice and reason | Alternative / cost |
| --- | --- | --- |
| First version | Cargo version `0.2.0-alpha.1`, tag `v0.2.0-alpha.1`, GitHub prerelease; keeps the current `0.2.0-dev` line recognizable and exposes experimental status | A stable `0.2.0` would imply a stronger compatibility/support commitment before adoption and rehearsal |
| Distribution | Public Git checkout pinned to the full candidate commit and GitHub's tag source ZIP/tar links; users build the root package with the existing locked Cargo recipe | Prebuilt binaries/installers would need assembled binary provenance, platform packaging/install/uninstall checks and a separate signing decision |
| Packaged assets | No manually uploaded binary, dependency bundle, container, installer or custom source archive for this first release | Custom packaging adds an artifact recipe and byte-verification duty without helping this source-first milestone |
| Registries | Keep `publish = false`; no crates.io, OS package manager, update feed or automatic updater | Registries need separate account, naming, upload and withdrawal ownership |
| Signing | Explicitly unsigned release tag/source archives; no new signing key, certificate, notarization, external attestation service or secret | Signing could add a distinct identity signal after a threat/benefit decision and real custody/recovery operators exist |
| Support | Best-effort support for the latest published alpha, through existing public issues/PRs and the current security reporting process | No fixed calendar maintenance branch or response SLA without consenting capacity |

These are adopted project choices, not platform requirements. Source-only
distribution lets experienced contributors use the established Rust workflow
without inventing release infrastructure. MIT remains locked, including its
warranty terms. Do not change `Cargo.toml`, version output, access, workflows or
settings merely to record this policy; version changes belong to
a separately prepared concrete candidate.

GitHub releases are tied to tags and provide source archives; the UI supports a
prerelease designation. See [About releases](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases)
and [Managing releases](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository),
observed 2026-10-15; no immutable documentation revision was established.

## What the first package could claim

The candidate notes must freeze exact code, contract and evidence revisions.
This table describes today's implemented boundaries, not a new qualification.

| Capability | Claim and evidence boundary |
| --- | --- |
| CLI help/version | Contextual root/group/leaf help, native argument parsing, text/JSON and declared error/status routing; advertise only actual commands |
| Metadata read | The finite CMT1/2/3, CTMD and preview-reference fields in the [reader denominator](../reader/README.md); partial coverage, exact occurrences and opaque regions remain visible |
| Camera/mode | EOS R5 full RAW CR3 only within recognized structural declarations; private evidence is finite and does not cover every firmware, lens or setting; C-RAW, DPRAW, burst, other cameras and unknown profiles retain refusals |
| Stored preview list/extract | Copy exact bounded stored preview bytes to a new named file; no JPEG decode/render/certification or sensor recompression. Extraction has a real destination effect and is not described as wholly read-only |
| Date preview | [Advisory fixed-width DateTimeOriginal preview](../reader/date-preview.md), with no apply/output command; current RAW dependency and production storage refusals remain |
| Pairing | [Selected RAW/XMP path observation](../sidecars/pairing.md), including only separately documented opt-in association rules; no content validation, sidecar creation, continuing guard or synchronization |
| Library | Current bounded [in-process read request/result API](../legacy-compatibility/read-request-result.md) and implemented modules; no stable ABI or mature library compatibility promise |
| Sequential read session | Bounded [session read CLI](../legacy-compatibility/read-session-process.md); exact framing, request isolation, limits and actual pipe evidence, without cancellation, queue/server or persistent cross-process recovery promises |
| Saved intent | Implemented [validation](../legacy-compatibility/cr3-preview-plan.md) and [source-content revalidation](../legacy-compatibility/cr3-preview-source-binding.md) remain nonexecuting observations; matching bytes never authorize mutation |
| In-memory XML/XMP | [Bounded UTF-8 packet inspection](../sidecars/packet-profile.md) is a library surface; it does not publish files or semantically clear arbitrary unknown namespaces |

Preview extraction retains the reader's actual scope: trusted local output
directory, no-clobber publication requiring hard links, no overwrite fallback,
bounded copy and documented partial/uncertain output outcomes. Source length/mtime
checks are not continuous adversarial guards. Filesystem access-time effects can
occur during reading. A killed extraction may leave a temporary file; persistent
recovery, hostile namespace races, directory durability and remote filesystem
guarantees are not certified by this package.

Metadata/RAW writes, privacy-removal certification, XMP filesystem publication, research workers,
automatic repair/recovery, menus, persistent cross-process sessions, executable extensions,
broader RAW support and full ExifTool parity remain outside this release claim.
Research crates in `experiments/` may be present in repository source archives;
their presence never makes them shipped production commands. Notes must mark
them as research and tell users to build only the root package.

The [current power-test policy](../write-safety/power-test-policy.md) is
best-effort and stops future power-related testing at disposable VM off.
Physical-power testing, dedicated hardware, host crashes or guest bugchecks
are not release gates. No physical survival promise is made. Independent format,
preservation and truthful-outcome obligations still apply to any future writer.

## Adopted version and support rules

**FR-01 — Identify exact behavior.** Each release records its version, full source
commit, root lockfile/toolchain identity, public schema revisions, accepted CLI
differences, finite capability denominator and known gaps. Never silently move
a published tag or replace bytes under the same claimed identity. Fixes get a
new version and release notes; withdrawn versions retain a public reason when
safe to disclose. `cargo build --release` selects optimization settings and
does not make its output an approved release artifact.

**FR-02 — Keep alpha compatibility explicit.** Subsequent compatible fixes in
this candidate line use `0.2.0-alpha.2`, `.3`, and so on. An intentional incompatible
CLI, JSON, library API, default or safety-contract change starts a new minor alpha
line, such as `0.3.0-alpha.1`, and names affected commands/fields plus migration
guidance. A schema version changes only according to its own contract; package
version alone does not excuse a wire-format change. No automatic deprecation
grace period is promised for alpha APIs. Prefer retaining a compatible behavior
when safe and cheap; explain necessary breakage before users upgrade.

**FR-03 — Bound support by capacity.** Only the latest published alpha receives
best-effort triage/fixes. Earlier versions remain identifiable for diagnosis but
have no promised backports, end-date extension, LTS branch, response deadline or
guaranteed fix. When a successor is published, state that the prior alpha's
maintenance has ended; if maintenance stops without a successor, publish that
fact when capacity permits. Preserve issue history and give a concrete next step
or an explicitly unassigned status. This policy does not appoint a support team.

Reports should name version/commit, OS/architecture, command, status, expected and
actual behavior and a minimal lawful reproduction. Users need not supply personal
photos or private-board access. Public bugs go to the existing
[issues](https://github.com/imageinfo/imageinfo/issues); suspected vulnerabilities
follow [SECURITY.md](../../SECURITY.md) and the
[security-intake readiness package](security-intake-readiness.md). Never invent
a staffed address or publish exploit/private-media details to get attention.

**FR-04 — Separate tested environments from user support.** Candidate validation
targets the existing Windows x64/MSVC, Ubuntu x64/GNU and macOS arm64 CI matrix
using Rust 1.99.0 and the committed lockfile. The exact hosted images and results
must be recorded for the actual candidate. Previous hosted jobs are development
evidence, not a blanket desktop OS, older runtime, architecture or filesystem
support promise. Unsupported environments may be reported and investigated
best-effort. No prebuilt binary runtime compatibility matrix is proposed.

The source download requires Git/archive tooling, Rust acquisition and the
documented native linker prerequisites. Python QA is separate from the runtime;
its top-level pinned dependency does not make a hermetic Python environment.
No claim of offline bootstrap or fully reproducible executable bytes follows
from a locked dependency resolution or successful hosted build.

## Authority, consent and custody

**FR-05 — Accept policy separately from publication.** Terry, as current project
coordinator, can accept or revise this version/support/distribution choice.
A future concrete release needs recorded approval of its exact commit, notes,
capability/evidence set and unsigned distribution choice. Standing approval for
source commits/pushes is not approval to publish software, tag a release or grant
accounts. #0159 adopts the policy; #0160 prepares the exact candidate and #0161
publishes only after its exact authorization. GOV-OPEN-05 operational work remains
open until those steps have actual evidence.

| Duty | Consenting person and evidence needed | Current state |
| --- | --- | --- |
| Release authority | Approve the exact candidate and notes; resolve scope/provenance/compatibility gaps | Terry; policy accepted, concrete candidate approval pending |
| Candidate preparation and publication execution | Codex may prepare the candidate and perform the specifically authorized publication using existing authorized access; Terry retains authority | Candidate preparation and actual publication unrun; no new access grant |
| Verification | Required exact-source automated checks and agent artifact/claim review, with results and limitations recorded | No independent human verifier or backup claimed; additional human coverage is a future goal |
| Security coverage | Solo best-effort route adopted separately under #0155–0156 | Private reporting enabled/configuration-verified; synthetic report refused for admin account, external submission/delivery unverified; exact candidate notes must disclose this limit |

This accepted solo-alpha scope supersedes the original proposal's mandatory
different-human verifier/backup and two-person rehearsal gate. Several agents or
a CI runner do not supply a second human. Record actual automated checks, agent
review and Terry's exact candidate decision without claiming human independence.
Future human appointments require consent and scoped access. No recruitment,
invitation, access change or notification test is authorized by these roles.

Unsigned distribution creates **no project signing secret to hold or recover**.
It relies on the selected GitHub repository/account channel and reviewed source
identity; an archive hash detects byte mismatch against a trusted recorded value
but does not independently authenticate a compromised channel. Document that
limit rather than describing checksums or a GitHub badge as a project signature.
Do not disable anyone's existing personal commit signing. If future binaries
need signing/notarization, decide actual benefit, cost, operators and recovery
before adding a service or credential.

The private access/recovery inventory covers the actual authorized publication
identity and permissions; it must disclose the lack of a backup.
Never share a personal login or recovery codes. Publish only consented role names,
dates and sanitized results. No new account, token, org owner or repository setting
is created here. Shared operator continuity remains a future goal, not an
undisclosed staffing prerequisite for this explicitly solo alpha.

## Finite future rehearsal acceptance

**FR-06 — Rehearse locally before seeking publication approval.** This is the
acceptance recipe used by [candidate preparation](source-reader-candidate.md).
Actual results must be recorded separately; this policy does not assert a pass. It requires a frozen
candidate but performs no tag push, GitHub draft/release creation, upload,
notification, settings change or source-media mutation. Use the
[blank rehearsal record](first-release-rehearsal.template.md).

| Cell | Finite action | Pass evidence / refusal |
| --- | --- | --- |
| FRR-01 — authority and identity | Record adopted solo policy, exact candidate/version, Terry's release authority, actual execution identity and approved access status | Missing candidate/access evidence keeps the relevant cell incomplete; no invented backup or independent human review |
| FRR-02 — clean checks | Check out the frozen revision and follow the public contributor recipe; retain exact toolchain/lockfile/environment and all required root/doc/schema checks plus exact candidate CI results | Record each result, reviewer and deviation; earlier green runs cannot stand in for this candidate |
| FRR-03 — public behavior | Run root/leaf help, text/JSON version and existing authored read/list/extract/preview/pairing/session fixtures, including invalid syntax, unsupported format, bounds and existing-output refusal | Exact complete outputs/statuses, unchanged source bytes, no overwrite, declared new-preview effects and no mutation/apply authority; no private photos required |
| FRR-04 — distribution contents | Build a local source archive from that exact revision using ordinary Git tooling, unpack elsewhere, enumerate tracked content and re-run the root build; inspect LICENSE, THIRD_PARTY_NOTICES, licenses, Cargo.lock and rust-toolchain.toml | No private corpus/report/board/credential/log/cache or unintended executable package; inspect tracked research separately and label it; any unresolved provenance/notice issue fails the affected distribution |
| FRR-05 — identity comparison | Compare extracted paths/file bytes to the frozen Git tree and record archive byte identity, excluded Git metadata and any archive substitutions; compare independently built binaries if attempted | Source content matches; a binary-byte mismatch is disclosed/investigated and prevents a binary reproducibility claim, not disguised by normalization |
| FRR-06 — correction walkthrough and continuity gap | Review public instructions and the sanitized candidate record; identify the unsigned trust limit, supported operations, refusal/status handling and simulated bad-release response | Record actual reviewer and no backup coverage; verify correction instructions without claiming backup takeover; no real deletion, release or tag mutation |
| FRR-07 — review decision | Steward reviews discrepancies, capability/compatibility notes, exact contents and linked security/access readiness | Record pass/incomplete/refused for each cell and unresolved actions; rehearsal completion alone never authorizes publication |

Do not require a byte-identical GitHub-generated compressed archive: GitHub
documents [source archive stability](https://docs.github.com/en/repositories/working-with-files/using-files/downloading-source-code-archives).
At a fixed commit, compare extracted file content and record the archive actually
received; generated compression/archive bytes may change. This source-only choice
does not advertise reproducible binaries. The future publisher must still verify
the actual public tag, source archive contents, version and notes after separately
authorized publication; a local rehearsal cannot witness that step.

Run only disposable authored fixtures, ordinary public-source builds and local
archive checks in this rehearsal. No power-fault or equipment campaign is needed.
Actual security-intake activation/tests, owner recovery and publication remain
separate authorized actions under their existing proposals. An incomplete
operational dependency does not prevent reviewing this choice package, but it
prevents claiming an operationally qualified first release.

## Delivery evidence and open actions

The root [Cargo manifest](../../Cargo.toml) is prepared as `0.2.0-alpha.1` under
#0160, MIT,
`publish = false`; pinned Rust/build/dependency evidence exists. The existing
workflow builds a release-profile executable but is not a publication pipeline.
The [dependency review](../foundation/dependencies.json) admits specific local/CI
uses; it does not approve arbitrary assembled release contents. Apply the
[provenance release review](../provenance/review-workflow.md) to the actual source
archive and any later binary set. No fixture grants or restricted camera reports
expand through this proposal.

| Status | Evidence / remaining action |
| --- | --- |
| Accepted | #0159 option A, 2026-10-16: source-only unsigned alpha, latest-alpha best-effort support, Terry's release authority, automated/agent checks without independent human verification claim; FR-01–06 and solo-adapted FRR-01–07 |
| Implemented | Root native package and scoped capabilities linked above; #0160 adds the adopted package version, candidate notes and local source-assembly recipe |
| Previously verified | Frozen reader/contributor/contract evidence at their stated revisions; not a release-candidate rehearsal |
| Exact results recorded separately | [Candidate preparation](source-reader-candidate.md) requires a frozen source, exact-source three-OS CI, local archive/build and agent review; this policy supplies no assumed pass |
| Unrun by policy adoption | Release publication and postpublication verification; shared operator continuity remains a future goal |
| Remaining decisions/evidence | Terry's exact candidate approval; separately chosen security route and actual access/security readiness disposition |
| Outside this delivery | New signing/registry infrastructure, permission changes, uploads, new production capabilities and broad support guarantees |

This document and blank record receive the repository's documentation/link and
whitespace checks. Scenario criteria are an unrun acceptance recipe; they are not
claims that a release drill, notification test or independent human review ran.
