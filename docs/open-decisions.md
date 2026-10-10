# Open product decisions

Status: initial proposal, 2026-10-10. These questions refine requirements; they do
not select a language. Full ExifTool parity remains the eventual goal; camera RAW
metadata is the current delivery scope agreed with Terry. See [RAW scope](raw-scope.md).

| ID | Decision | Current position | Evidence needed |
| --- | --- | --- | --- |
| OD-01 | Functional workalike versus command-line drop-in compatibility | Full functional breadth remains the goal. [Card #0007](legacy-compatibility/README.md) recommends a native CLI plus nonexecuting migration reports; exact drop-in syntax/output stays separately scoped. Recommendation awaits review. | Map common scripts and all documented upstream option families; identify observable differences and migration paths. |
| OD-02 | Executable configuration and expressions | [Card #0007](legacy-compatibility/migration.md) proposes bounded pure filtering and explicit data definitions first. Arbitrary executable expressions/modules remain an explicit future gap; no runtime or sandbox is selected. Recommendation awaits review. | Inventory Perl expressions, callbacks, user-defined tags, argument files, and API use cases; define which need translation or an optional compatibility mechanism. |
| OD-03 | Mutation defaults | The [write-safety proposal](write-safety/README.md) defines preview/apply, original retention, no-ops, guarded publication and evidence-based recovery; these defaults remain for review. | Walk through single-file, recursive, unattended, large-batch, and recovery scenarios; settle ergonomic and storage tradeoffs. |
| OD-04 | Meaning of metadata removal | Expose the limits of logical deletion, recoverability, embedded assets, and signatures. Never equate a missing displayed tag with secure erasure. | Per-RAW-container removal contracts; retain rendering-critical calibration/proprietary data and examine embedded previews. PDF-specific behavior is deferred. |
| OD-05 | First delivered camera/format and depth | Canon EOS R5 full RAW CR3 is selected; C-RAW is secondary. Detailed capture variants and read/write depth remain to be specified; other RAW families follow later. | Full RAW fixtures first, separately tracked C-RAW and Dual Pixel RAW evidence, lawful provenance, safe-write constraints, and measurable milestone acceptance; see the [CR3 milestone](canon-eos-r5-cr3.md). |
| OD-06 | Performance targets | The [performance protocol](performance/README.md) specifies workloads, measurements and limit-selection criteria. Actual baselines and numerical targets/defaults remain #0016; no speed multiplier is promised. | Reproducible baseline by file size, metadata size, batch count, storage type, and enabled extraction options. |
| OD-07 | API and long-lived process contract | [Card #0007](legacy-compatibility/integration.md) proposes explicit snapshot/intent lifetimes and bounded local JSONL sessions with request-local settings and separate transport status. Request/result schemas are drafted; complete plan/session-output schemas and runtime evidence remain open. Recommendation awaits review. | Inventory relevant upstream API and stay-open workflows, concurrency, framing, cancellation, and error handling. |
| OD-08 | Sustainability | [Card #0009](../GOVERNANCE.md) proposes contributor/review duties, primary/backup ownership, security intake and release/access recovery. Recommendation awaits review; operational readiness is not established. | Consent-based appointments, private reporting, actual review controls and independent release/recovery drills remain GOV-OPEN-01–06 on #0017. |
| OD-09 | Project and imported-artifact licenses | MIT accepted and locked on 2026-10-10; preserve copyright/license notices without mandatory visible UI credit. See [decision](license-decision.md). | The [provenance policy](provenance/README.md) now specifies scoped reviews and admission records; actual source/table/fixture permissions remain asset-specific work, first on #0013. The project-license choice is settled. |
| OD-10 | Interactive menu behavior | Contextual help is mandatory. Cascading interaction is optional and must never block scripts. | The [walkthrough recommendation](cli-walkthroughs/README.md) specifies keyboard/line navigation, cancellation, previews and non-TTY behavior. User review and real accessibility/usability testing remain open. |

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
