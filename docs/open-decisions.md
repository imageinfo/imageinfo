# Open product decisions

Updated 2026-10-14; OD-11 records Terry's option A storage-policy decision after the accepted
guard/output experiments. The initial requirements and corpus work remain accepted.
These remaining questions refine implementation and evidence. Full ExifTool parity remains the eventual goal; camera RAW
metadata is the current delivery scope agreed with Terry. See [RAW scope](raw-scope.md).

| ID | Decision | Current position | Evidence needed |
| --- | --- | --- | --- |
| OD-01 | Functional workalike versus command-line drop-in compatibility | Full functional breadth remains the goal. [Card #0007](legacy-compatibility/README.md) recommends a native CLI plus nonexecuting migration reports; exact drop-in syntax/output stays separately scoped. The initial recommendation was accepted with its card; remaining detailed specifications and runtime evidence are open. | Map common scripts and all documented upstream option families; identify observable differences and migration paths. |
| OD-02 | Executable configuration and expressions | [Card #0007](legacy-compatibility/migration.md) proposes bounded pure filtering and explicit data definitions first. Arbitrary executable expressions/modules remain an explicit future gap; no runtime or sandbox is selected. The initial recommendation was accepted with its card; remaining detailed specifications and runtime evidence are open. | Inventory Perl expressions, callbacks, user-defined tags, argument files, and API use cases; define which need translation or an optional compatibility mechanism. |
| OD-03 | Mutation defaults | The [write-safety proposal](write-safety/README.md) defines preview/apply, original retention, no-ops, guarded publication and evidence-based recovery; the baseline was accepted with #0006; storage-profile proof remains open. | Walk through single-file, recursive, unattended, large-batch, and recovery scenarios; settle ergonomic and storage tradeoffs. |
| OD-04 | Meaning of metadata removal | Expose the limits of logical deletion, recoverability, embedded assets, and signatures. Never equate a missing displayed tag with secure erasure. | Per-RAW-container removal contracts; retain rendering-critical calibration/proprietary data and examine embedded previews. PDF-specific behavior is deferred. |
| OD-05 | First delivered camera/format and depth | Canon EOS R5 full RAW CR3 is selected; C-RAW is secondary. Detailed capture variants and read/write depth remain to be specified; other RAW families follow later. | Full RAW fixtures first, separately tracked C-RAW and Dual Pixel RAW evidence, lawful provenance, safe-write constraints, and measurable milestone acceptance; see the [CR3 milestone](canon-eos-r5-cr3.md). |
| OD-06 | Performance targets | The [performance protocol](performance/README.md) specifies workloads, measurements and limit-selection criteria. Actual baselines and numerical targets/defaults remain #0016; no speed multiplier is promised. | Reproducible baseline by file size, metadata size, batch count, storage type, and enabled extraction options. |
| OD-07 | API and long-lived process contract | [Card #0007](legacy-compatibility/integration.md) proposes explicit snapshot/intent lifetimes and bounded local JSONL sessions with request-local settings and separate transport status. Request/result schemas are drafted; complete plan/session-output schemas and runtime evidence remain open. The initial recommendation was accepted with its card; remaining detailed specifications and runtime evidence are open. | Inventory relevant upstream API and stay-open workflows, concurrency, framing, cancellation, and error handling. |
| OD-08 | Sustainability | [Card #0009](../GOVERNANCE.md) proposes contributor/review duties, primary/backup ownership, security intake and release/access recovery. The proposal was accepted with #0009; operational readiness is not established. | Consent-based appointments, private reporting, actual review controls and independent release/recovery drills remain GOV-OPEN-01–06 on #0017. |
| OD-09 | Project and imported-artifact licenses | MIT accepted and locked on 2026-10-10; preserve copyright/license notices without mandatory visible UI credit. See [decision](license-decision.md). | The [provenance policy](provenance/README.md) now specifies scoped reviews and admission records; initial private corpus/reference permissions were reviewed on accepted #0013; every new source/table/fixture use remains asset-specific. The project-license choice is settled. |
| OD-10 | Interactive menu behavior | Contextual help is mandatory. Cascading interaction is optional and must never block scripts. | The [walkthrough recommendation](cli-walkthroughs/README.md) specifies keyboard/line navigation, cancellation, previews and non-TTY behavior. The initial walkthrough was accepted with #0003; real accessibility/usability testing remains open. |
| OD-11 | New-output property concurrency and ordinary editing | [#0041 / option A](write-safety/practical-output-policy.md) explicitly accepted by Terry in chat on 2026-10-14: guarded default-stream bytes/no-clobber names, boundary property checks and ordinary private-owner editable new output. WS-009/010/011 and SAF-005/006/007 reflect the choice; other guarantees and all writer gates remain. | Implement/qualify the complete actual marker protocol and per-platform evidence cells before profile admission; independently satisfy format/RAW admission. |

## Implementation selection now open

Terry authorized #0011 and disposable prototypes on 2026-10-10. [ADR-0011](implementation-selection/README.md)
records the accepted Rust, Cargo, clap and Serde direction with a small synchronous
library/CLI. #0019 provides the [executable foundation](foundation/README.md). The [first milestone](implementation-selection/first-milestone.md)
defines the proposed read-only increment. Product XML, richer terminal widgets,
plugins, installers and exact release/OS baselines remain scoped later decisions.
Requirements and wire contracts remain independent of internal Rust organization.

## Decision process

Work on a scoped question can proceed on the local board. A recommendation should
include alternatives, evidence, user-visible consequences, and remaining uncertainty.
Once accepted, record the decision and update affected requirements and examples.
