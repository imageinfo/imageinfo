# Documentation map

This is the initial, language-agnostic requirements baseline, researched on
2026-10-10. All imageinfo features and commands described here are proposed.
No parsing, editing, or compatibility implementation exists yet.

**Delivery focus: camera RAW metadata first. Long-term goal: full ExifTool feature
parity.** Broader research is retained as future reference; it does not expand the
current milestone. Implementation selection is now open under #0011; the Rust
recommendation awaits review and the requirements remain language independent.
The first camera/format target is **Canon EOS R5 CR3**.

| Document | Purpose |
| --- | --- |
| [Implementation selection](implementation-selection/README.md) | ADR-0011: Rust recommendation, Go/C# alternatives, disposable probes, component choices and the first read milestone. |
| [RAW scope](raw-scope.md) | Current format/workflow boundaries and the distinction from eventual full parity. |
| [Canon EOS R5 CR3](canon-eos-r5-cr3.md) | First camera/format milestone, priority workflows, and variant evidence. |
| [CR3 capability inventory](inventory/README.md) | Versioned capability rows, schema, CLI/API mapping, evidence gates, and audit gaps for card #0002. |
| [Metadata contract](metadata-model/README.md) | Occurrence identity, exact values, source provenance, selection and edit-intent schemas/examples for card #0004. |
| [Fixture and parity plan](fixture-plan/README.md) | Prioritized corpus cases, provenance/admission, oracle profile, experiment records, and comparison rules for card #0005. |
| [First private corpus baseline](corpus-baseline/README.md) | Eight admitted R5 full RAW originals, acquired references, actual read/preview/XMP observations and remaining evidence limits for #0013. |
| [Safe mutation and recovery](write-safety/README.md) | Per-file publication, preserved originals, concurrency, recovery, platform constraints and synthetic acceptance cases for card #0006. |
| [Product requirements](product-requirements.md) | Scope, users, feature requirements, priorities, and acceptance criteria. |
| [ExifTool capabilities](exiftool-capabilities.md) | What the upstream tool does, including formats beyond images. |
| [ExifTool CLI semantics](exiftool-cli-semantics.md) | Behaviors and interactions that a workalike must account for. |
| [CLI requirements](cli-requirements.md) | Hierarchical help, optional menus, proposed commands, scripting, and mutation UX. |
| [CLI walkthroughs](cli-walkthroughs/README.md) | Eight concrete user journeys, help/menu recommendations, pairing, scripting, recovery and exit precedence for card #0003. |
| [Compatibility and validation](compatibility-and-validation.md) | Evidence needed to claim parity, fixture strategy, and write-safety tests. |
| [RAW compatibility recommendation](legacy-compatibility/README.md) | CLI/API surface ledger, migration and expression/trust choices, request/result schemas and persistent-session proposal for card #0007. |
| [Performance protocol](performance/README.md) | Workloads, measurement/environment fields, correctness gates and criteria for later measured limits; no benchmark claims. |
| [Architecture principles](architecture-principles.md) | Language-independent boundaries and data requirements. |
| [Governance proposal](../GOVERNANCE.md) | Responsibility/backup coverage, decisions, review and open readiness actions for card #0009. |
| [Contributing](../CONTRIBUTING.md) | Public onboarding, documentation verification, focused review and provenance expectations. |
| [Security reporting](../SECURITY.md) | Current reporting route and private-intake readiness limitation. |
| [Release and recovery runbook](governance/release-and-recovery.md) | Future reproducible-release gates, incident response and access/succession exercises. |
| [Governance validation](governance/validation.md) | Scenario review, actual settings observations and outstanding operational readiness. |
| [Roadmap](roadmap.md) | Staged delivery, review gates, and the next requirements work. |
| [Research sources](research-sources.md) | Primary references, pinned upstream revision, and research limits. |
| [Open decisions](open-decisions.md) | Unresolved product choices and explicitly deferred implementation decisions. |
| [MIT license decision](license-decision.md) | Accepted and locked project-license policy and remaining third-party provenance work. |
| [Artifact provenance](provenance/README.md) | Scoped rights/privacy/notice reviews, release/corpus admission and record schema under the locked MIT project license. |
| [Local board](local-board.md) | Private planning workflow and service lifecycle. |

Read the RAW scope and product requirements first, then the capabilities and CLI documents.
Use the validation document before deciding whether a milestone can be called
compatible. A checked-off feature category alone is insufficient: the evidence
must identify the applicable format, tag, operation, and behavior.

Changes to scope should update the requirements, roadmap, and local board together.
Record accepted design decisions with their rationale when those decisions are made.
