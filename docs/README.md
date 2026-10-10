# Documentation map

This is the initial, language-agnostic requirements baseline, researched on
2026-10-10. All imageinfo features and commands described here are proposed.
No parsing, editing, or compatibility implementation exists yet.

**Delivery focus: camera RAW metadata first. Long-term goal: full ExifTool feature
parity.** Broader research is retained as future reference; it does not expand the
current milestone. Language and framework choices remain deferred.
The first camera/format target is **Canon EOS R5 CR3**.

| Document | Purpose |
| --- | --- |
| [RAW scope](raw-scope.md) | Current format/workflow boundaries and the distinction from eventual full parity. |
| [Canon EOS R5 CR3](canon-eos-r5-cr3.md) | First camera/format milestone, priority workflows, and variant evidence. |
| [CR3 capability inventory](inventory/README.md) | Versioned capability rows, schema, CLI/API mapping, evidence gates, and audit gaps for card #0002. |
| [Metadata contract](metadata-model/README.md) | Occurrence identity, exact values, source provenance, selection and edit-intent schemas/examples for card #0004. |
| [Product requirements](product-requirements.md) | Scope, users, feature requirements, priorities, and acceptance criteria. |
| [ExifTool capabilities](exiftool-capabilities.md) | What the upstream tool does, including formats beyond images. |
| [ExifTool CLI semantics](exiftool-cli-semantics.md) | Behaviors and interactions that a workalike must account for. |
| [CLI requirements](cli-requirements.md) | Hierarchical help, optional menus, proposed commands, scripting, and mutation UX. |
| [Compatibility and validation](compatibility-and-validation.md) | Evidence needed to claim parity, fixture strategy, and write-safety tests. |
| [Architecture principles](architecture-principles.md) | Language-independent boundaries and data requirements. |
| [Roadmap](roadmap.md) | Staged delivery, review gates, and the next requirements work. |
| [Research sources](research-sources.md) | Primary references, pinned upstream revision, and research limits. |
| [Open decisions](open-decisions.md) | Unresolved product choices and explicitly deferred implementation decisions. |
| [MIT license decision](license-decision.md) | Accepted and locked project-license policy and remaining third-party provenance work. |
| [Local board](local-board.md) | Private planning workflow and service lifecycle. |

Read the RAW scope and product requirements first, then the capabilities and CLI documents.
Use the validation document before deciding whether a milestone can be called
compatible. A checked-off feature category alone is insufficient: the evidence
must identify the applicable format, tag, operation, and behavior.

Changes to scope should update the requirements, roadmap, and local board together.
Record accepted design decisions with their rationale when those decisions are made.
