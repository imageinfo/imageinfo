# Contributing to imageinfo

The project is currently documenting requirements for Canon EOS R5 full RAW CR3
metadata, paired XMP and stored previews. There is **no executable or build system
yet**. Language and internal architecture are deliberately open. Research corrections,
clearer examples and carefully sourced edge cases are useful contributions now.

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
| Capability inventory | [Inventory validation](docs/inventory/validation.md) |
| Metadata values/identity | [Metadata validation](docs/metadata-model/validation.md) |
| Fixtures/reference records | [Fixture validation](docs/fixture-plan/validation.md) |
| Mutation/recovery | [Write-safety validation](docs/write-safety/validation.md) |
| CLI examples/status | [CLI validation](docs/cli-walkthroughs/validation.md) |
| Request/result compatibility | [Compatibility validation](docs/legacy-compatibility/validation.md) |
| Measurement methods | [Performance validation](docs/performance/validation.md) |
| Asset rights/privacy/lineage | [Provenance validation](docs/provenance/validation.md) |

The six current schema files live under `docs/inventory`, `docs/metadata-model`,
`docs/fixture-plan`, `docs/legacy-compatibility` and `docs/provenance`. Their validation recipes explain
what JSON Schema alone cannot prove. Choose available validation tooling for this
documentation work; that does not choose the product language. There is no software
test/build gate yet. The first implementation contribution must add reproducible,
public setup and check commands appropriate to the approved language/toolchain.

## Make review straightforward

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
