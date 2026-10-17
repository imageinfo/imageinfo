# Contributing to imageinfo

The initial requirements and private reference baseline are reviewed. Implementation
selection is accepted: [ADR-0011](docs/implementation-selection/README.md) chooses
Rust. The [executable foundation](docs/foundation/README.md) has public build and
test commands; the [native R5 slice](docs/reader/README.md) now has public synthetic
reader/extraction/fuzz-smoke tests and scoped private differential evidence. Disposable
[research probes](experiments/0011-language-selection/README.md) have their own
reproduction commands; they are not a production foundation.

Start with the [project overview](README.md), [documentation map](docs/README.md),
[RAW scope](docs/raw-scope.md) and [governance proposal](GOVERNANCE.md).
For security concerns, use [SECURITY.md](SECURITY.md) before opening a public report.

## Find and scope the work

Use [issues](https://github.com/imageinfo/imageinfo/issues) to describe the problem
and discuss substantial changes before investing in an implementation. Small fixes
can come directly as a PR. The local localswim board is an internal coordination
convenience; you do not need access to it. Public changes must carry their own
context, rationale and evidence.

Keep the first milestone and the specific operation in view. Reading a tag is
different from writing, creating, deleting or preserving it. Other RAW families
and eventual full ExifTool parity belong on the roadmap; an attractive example
does not expand the current implementation scope.

For research, cite a primary source and observation date, pin its revision where
available, and separate source facts from proposed imageinfo behavior. An ExifTool
method/table is evidence about functionality, not a required native architecture.
Do not copy upstream implementation, complete tag tables, documentation or media
into a contribution without resolving its own provenance and reuse terms.

## Work locally

```console
git clone https://github.com/imageinfo/imageinfo.git
cd imageinfo
git switch -c your-change-name
```

Read `AGENTS.md` if using an assistant. Contributors can work entirely from the
public repository; private board files, local service credentials and personal
media are not prerequisites. Keep them out of commits.

Follow the [pinned Rust setup and check recipe](docs/foundation/README.md),
including Python/pip and the pinned schema QA dependency. The
[clean hosted contributor verification](docs/contributing/clean-machine.md)
records an actual exact-revision run on fresh Windows, Ubuntu and macOS hosted
images, their supplied prerequisites and the limits of that evidence.

For documentation changes, before opening a PR:

1. Run `git diff --check` after your edits.
2. Follow changed relative links and check the documentation index still leads to
   the new/updated material. Keep identifiers stable and update references together.
3. Check proposed command examples against their declared grammar, expected status,
   target paths and side effects. Mark unimplemented examples clearly.
4. Parse changed JSON examples. For schemas, use a JSON Schema Draft 2020-12 validator
   and resolve the repository's schema `$id` references to local files without
   fetching arbitrary URLs. Check cross-record identities/coverage as documented.
5. Run the affected artifact's published validation recipe and describe exactly
   which checks you performed. Do not report local private helper scripts as a
   prerequisite others must somehow obtain.

| Changed area | Public verification recipe |
| --- | --- |
| Production Rust/CLI | [Foundation setup and gates](docs/foundation/README.md) |
| Implementation selection/probes | [Probe reproduction](experiments/0011-language-selection/README.md) and [decision validation](docs/implementation-selection/validation.md) |
| Capability inventory | [Inventory validation](docs/inventory/validation.md) |
| Metadata values/identity | [Metadata validation](docs/metadata-model/validation.md) |
| Fixtures/reference records | [Fixture validation](docs/fixture-plan/validation.md) |
| Mutation/recovery | [Write-safety validation](docs/write-safety/validation.md) |
| CLI examples/status | [CLI validation](docs/cli-walkthroughs/validation.md) |
| Request/result compatibility | [Compatibility validation](docs/legacy-compatibility/validation.md) |
| Measurement methods | [Performance validation](docs/performance/validation.md) |
| Asset rights/privacy/lineage | [Provenance validation](docs/provenance/validation.md) |

The schema files live under `docs/inventory`, `docs/metadata-model`,
`docs/fixture-plan`, `docs/legacy-compatibility`, `docs/provenance` and `docs/foundation`. Their validation recipes explain
what JSON Schema alone cannot prove. Choose available validation tooling for this
documentation work. For production changes, run the pinned-toolchain formatting,
clippy, tests and release-build commands in the foundation guide. Changed research
probes must still pass their own documented assertions; they are separate packages.
Run `python scripts/check_docs.py` for public links/JSON. Keep required notices
current in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) when dependencies change.

## Make review straightforward

The accepted solo workflow permits Terry-authorized direct commits/pushes after
required checks, agent review where useful and Terry's acceptance of local-board
handoffs. Public contributors use ordinary PRs. No mandatory PR approvals,
CODEOWNERS or new branch-rule requirements were adopted by #0157; see the
[current review policy](docs/governance/review-routing-plan.md#accepted-solo-workflow--0157-2026-10-16).
Agent review does not establish independent human review, and technical evidence
requirements remain applicable. The [dated retained-policy verification](docs/governance/retained-review-policy.md)
records the actual direct-push/check/board route and separates project procedure
from absent machine enforcement. Run its offline record checker when changing
that record; it does not exercise GitHub permissions or replace actual checks.

Explain the problem, changed behavior, evidence, compatibility/safety effects and
remaining limits. Favor small reviewable changes, conventional names and ordinary
control flow. Boring is a compliment here. If a deliberate unconventional choice
earns its cost, explain why near that choice and link substantial rationale.

For a future format or tag implementation, link exact capability cells and fixture
cases. Preserve occurrence identity, unknown information and RAW interpretation.
Include a meaningful regression case and applicable independent preservation evidence;
do not count a correct refusal as implementing an edit. Unverified combinations
remain unavailable and visible in the capability matrix.

Do not upload private originals, serial/location metadata, credentials or unlicensed
samples into issues/PRs. Start with a description, redacted metadata or an owned
minimal reproducer when possible. Real media admission follows the
[fixture plan](docs/fixture-plan/README.md) and
[artifact review workflow](docs/provenance/review-workflow.md); data may need controlled
access rather than public redistribution.

## Credit and decisions

The project uses [MIT](LICENSE), as recorded in the locked
[license decision](docs/license-decision.md). Identify authorship and the origin of
contributed material, preserve applicable notices, and supply only material you
have the right to contribute. Third-party artifacts retain their own terms.
No additional CLA or sign-off program is introduced by this guidance, and merging
a contribution does not assign its author's copyright to another person.

Maintainers review contribution scope and evidence, ask for concrete changes, and
record substantive decisions publicly. Approval of a proposal is separate from
implementation and runtime verification. A request for a change should explain the
requirement or tradeoff; reviewers and contributors should not need private author
context to understand the result.
