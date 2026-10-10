# Roadmap

Full ExifTool feature parity is the long-term goal. **Camera RAW metadata is the
initial delivery scope.** This roadmap separates those horizons. A milestone's
limited coverage must remain visible; it is not permission to call partial support
complete. The project is currently in **Phase 0**. Language choices are deferred.

**First target: Canon EOS R5 full RAW CR3.** C-RAW is separately tracked secondary
coverage. The read foundation, associated-XMP workflow,
and individually gated embedded edits start there. Other RAW families come after
that first milestone; see the [CR3 requirements](canon-eos-r5-cr3.md).

| Phase | Outcome | Exit evidence |
| --- | --- | --- |
| 0. Requirements baseline | Document RAW workflows, native CLI experience, compatibility scope, safety, and open decisions; retain broader upstream research as reference. | Reviewed requirements with stable IDs, a source ledger, RAW command walkthroughs, and a prioritized local board. |
| 1. RAW compatibility specification | Convert RAW feature areas into a versioned capability matrix and fixture/test contracts. | Each row names RAW format/variant/tag/operation, reference behavior, expected differences, and evidence needed; priority workflows have testable examples. |
| 2. Implementation selection | Evaluate language and component choices against the accepted requirements. | An explicit decision recording alternatives, maintenance implications, portability, parser safety, extensibility, and delivery constraints. Begin only when Terry advances this deferred work. |
| 3. RAW read foundation | Deliver the agreed first RAW format set with full tag identity, provenance, raw values, usable help, and scriptable output. | Differential read results, malformed-input/resource checks, cross-platform behavior, and a published list of supported RAW capabilities. |
| 4. Safe RAW mutation | Add update/delete/copy and metadata-sidecar creation by RAW container and tag family. | Independent readback, preserved sensor payloads and rendering-critical data, round-trip/unknown-data evidence, fault-injection recovery, and explicit unsupported cases. |
| 5. RAW workflow breadth | Add remaining RAW output modes, batch operations, geotagging, dates, naming, embedded extraction, metadata mapping, and API/process workflows. | End-to-end examples and parity results for every accepted RAW workflow, including failure and partial-success cases. |
| 6. RAW long tail and stewardship | Expand vendor notes, camera variants, and advanced RAW options; sustain compatibility as upstream evolves. | Published gaps, regression corpus, reproducible releases, documented format ownership, and coverage review for each release. |
| Later: broader ExifTool parity | Expand into rendered images and other ExifTool-supported media/file types through separately scoped milestones. | Explicit scope choices and equivalent per-format evidence; do not begin every format family at project inception. |

## Next requirements work

These tasks can be refined without choosing a language. Their short IDs match the
local board's stable card IDs; board ticket numbers are machine-local.

| Card ID | Work | Acceptance criteria |
| --- | --- | --- |
| `capability-inventory` | Enumerate Canon EOS R5 CR3 capabilities first. | Inventory EOS R5 CR3 capture variants and metadata families separately; distinguish recognition/read/write/sidecar creation/delete/preserve; attach sources and exceptions; retain other RAW families as later expansion. |
| `cli-walkthroughs` | Exercise the proposed command/help/menu model. | Text walkthroughs for novice inspection, expert batch export, safe edit, GPS removal, sidecar sync, and failures; root/group/leaf help and noninteractive paths reviewed. |
| `metadata-contract` | Specify the loss-aware metadata model. | Examples cover duplicate instances, groups, binary values, rationals, missing versus empty, unknown time zones, XMP structures/languages, offsets, and source provenance. |
| `fixture-plan` | Define reproducible parity evidence. | Fixture manifest/provenance schema, oracle version/hash fields, deterministic comparison rules, and a prioritized corpus plan; no unlicensed/private sample import. |
| `write-safety-contract` | Specify RAW mutation and recovery behavior. | Per-file transaction, originals/backups, collisions, concurrent change detection, failure recovery, unknown/calibration data retention, sensor payload preservation, and signature consequences have acceptance scenarios. |
| `legacy-compatibility` | Map legacy CLI, API, and extension use cases. | A documented equivalent, proposed difference, or open gap for upstream argument grammar, expressions/configuration, structured output, and long-lived process behavior. |
| `performance-baseline` | Specify measurable performance requirements. | Workload categories, environment fields, latency/throughput/memory metrics, cache effects, and comparison methodology; numerical targets supported by later measurement. |
| `governance-proposal` | Make shared maintenance practical. | Format ownership, contributor onboarding, review/release procedures, vulnerability reporting, and succession/access recovery proposals. |
| `license-provenance` | Define provenance under the selected MIT project license. | MIT decision is recorded; complete artifact-specific source/table/fixture provenance rules and resolve reuse questions before implementation imports. |
| `implementation-selection` | Choose a modern implementation stack later. | Explicitly held in backlog until Terry advances language decisions; evaluate only against accepted requirements. |
| `corpus-baseline` | Acquire and characterize the first lawful full RAW corpus later. | Backlog follow-up #0013: select concrete permitted sources, admit fixtures, hash the reference distribution/runtime/driver, and capture reference-only observations. |
| `write-validation` | Prove RAW writer/storage safety later. | Backlog #0014: declared profiles, preservation, interrupted-operation recovery, exact privacy catalogs and independent runtime evidence; no writer enabled by a specification alone. |
| `compatibility-evidence` | Close the surveyed compatibility gaps later. | Backlog #0015: exhaustive option/API cases, exact legacy serializers, advanced extensions/mappings, complete plan/session-output schemas and real integration evidence; see LG-001–006. |
| `broader-format-parity` | Preserve the eventual full ExifTool parity goal. | Deferred umbrella only; choose and scope additional format families after RAW milestones, with independent compatibility evidence. |

## Progress reporting

The [CR3 capability inventory](inventory/README.md),
[metadata contract](metadata-model/README.md),
[fixture and parity plan](fixture-plan/README.md), and
[safe mutation contract](write-safety/README.md), plus
[CLI walkthroughs](cli-walkthroughs/README.md) and
[compatibility recommendation](legacy-compatibility/README.md), provide the current requirements
baseline. They include source-backed scope, synthetic examples, schemas, comparison
rules and remaining evidence gaps. They do not claim implemented capabilities.

The next requirements card is **#0008, performance-baseline**, to define measured
workloads, resource defaults and limits against the read/write/session contracts.
#0015 retains explicit compatibility gaps, including complete saved-plan and
session-output schemas, exhaustive option interactions and runtime integration.
Runtime CLI/usability checks follow a separately authorized implementation decision.
Actual corpus acquisition and reference runs remain backlog work on #0013.
Storage profiles, writer fault injection and per-profile
privacy/preservation evidence remain backlog work on #0014, after requirements
review, lawful fixtures and an explicitly authorized implementation decision.
No runtime capability has been promoted by the planning artifacts.

Report capability cells and verified workflows, not percentages derived solely from
tag or extension counts. A format readable in one fixture may contain variants with
different requirements. A write claim requires stronger evidence than a successful
read. Current implementation coverage is zero; the initial deliverable is research.
