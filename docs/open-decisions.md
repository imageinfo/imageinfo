# Open product decisions

Status: initial proposal, 2026-10-10. These questions refine requirements; they do
not select a language. Full ExifTool parity remains the eventual goal; camera RAW
metadata is the current delivery scope agreed with Terry. See [RAW scope](raw-scope.md).

| ID | Decision | Current position | Evidence needed |
| --- | --- | --- | --- |
| OD-01 | Functional workalike versus command-line drop-in compatibility | Full functional breadth is the goal. A friendlier native CLI is required. Exact legacy argument syntax is an additional compatibility surface whose extent must be decided explicitly. | Map common scripts and all documented upstream option families; identify observable differences and migration paths. |
| OD-02 | Executable configuration and expressions | Custom tags, derived values, filters, and transformations must have equivalents. The execution/trust model remains open. | Inventory Perl expressions, callbacks, user-defined tags, argument files, and API use cases; define which need translation or an optional compatibility mechanism. |
| OD-03 | Mutation defaults | Proposed design previews changes and requires explicit application, with preserved originals and clear per-file outcomes. | Walk through single-file, recursive, unattended, large-batch, and recovery scenarios; settle ergonomic and storage tradeoffs. |
| OD-04 | Meaning of metadata removal | Expose the limits of logical deletion, recoverability, embedded assets, and signatures. Never equate a missing displayed tag with secure erasure. | Per-RAW-container removal contracts; retain rendering-critical calibration/proprietary data and examine embedded previews. PDF-specific behavior is deferred. |
| OD-05 | First delivered RAW format set | Camera RAW is the initial scope; the exact first-release subset and read/write depth remain pending. | Camera models and RAW variants used in real workflows, lawful fixtures, per-format complexity, and measurable milestone acceptance. |
| OD-06 | Performance targets | Predictable resource bounds and large-batch support are requirements. No unsupported speed multiplier is promised. | Reproducible baseline by file size, metadata size, batch count, storage type, and enabled extraction options. |
| OD-07 | API and long-lived process contract | Embeddable and efficient repeated-call use cases belong in the target. Prioritize RAW workflows; the public protocol and versioning contract remain to be specified. | Inventory relevant upstream API and stay-open workflows, concurrency, framing, cancellation, and error handling. |
| OD-08 | Sustainability | Publish contributor paths, format ownership, release procedures, and provenance; avoid depending on undocumented knowledge held by one person. | A governance proposal covering reviewer coverage, release access, recovery, and succession. |
| OD-09 | Project and imported-artifact licenses | Undecided. No upstream implementation assets are copied into this initial repository. | Review intended reuse/distribution, upstream notices, and fixture permissions before choosing licenses or importing material. |
| OD-10 | Interactive menu behavior | Contextual help is mandatory. Cascading interaction is optional and must never block scripts. | Text walkthroughs and usability review for keyboard navigation, accessibility, cancellation, command preview, and non-TTY behavior. |

## Explicitly deferred

Implementation language, runtime, framework, CLI library, parser libraries, plugin
mechanism, binary distribution, package managers, and platform build toolchains are
deferred at Terry's request. Evaluate them only after the feature and compatibility
requirements are sufficiently concrete. No decision in these documents preselects
those implementation choices.

## Decision process

Work on a scoped question can proceed on the local board. A recommendation should
include alternatives, evidence, user-visible consequences, and remaining uncertainty.
Once accepted, record the decision and update affected requirements and examples.
