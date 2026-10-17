# RAW expression and module boundary (#0054)

Status: **historical #0054 proposal**, revision `2026-10-15.1`. The accepted
#0007 pure/data direction is now refined by the [#0131 contract](pure-data-boundary.md)
without another adoption gate. That contract supersedes the pending-decision
wording below for bounded filters and explicit definitions; arbitrary executable
support remains unmet. The remaining text records the original recommendation.
This completes
the bounded #0054 recommendation for **LG-003 / OD-02**; it does not close the
long-term executable compatibility gap. The existing #0007 recommendation was
accepted with that card. The more precise milestone choice below has not been
accepted. No production code, dependency, command or permission changes here.

Recommend **option B: bounded native selection and explicit data definitions,
with executable expressions/modules refused for the first RAW milestone**. Keep
advanced calculations, parser additions and external processing visible as distinct
unmet uses. This gives ordinary R5 full RAW selection a small native path without
adopting a general extension runtime merely to resemble the reference tool.

## Current capability and evidence

The root exposes a [bounded read-only request/result API](read-request-result.md)
and the [native read JSON subset](native-read-json.md). It has no executable
extension loader, user expression evaluator or module registration interface
in its [CLI definition](../../src/cli.rs) or
[runtime dependencies](../../Cargo.toml).
The [pure-filter grammar](migration.md) and LEG-006 data-definition boundary are
proposals. An ordinary compiled contributor change is code review and a new build,
not a runtime plugin. The Rust library is usable by caller-written code; that does
not make the caller's code an imageinfo extension or a restricted execution domain.

The finite uses below are **project-authored product examples** for Canon EOS R5
full RAW CR3 and explicitly paired XMP. They are not measured legacy invocations,
an exhaustive callback survey or promises about every camera tag. A selector must
first resolve against actual reader coverage. C-RAW and other RAW families do not
inherit evidence. No private media was opened for this proposal.

## Finite use-case set

The IDs identify this review matrix, not a new execution protocol. “Plan” means a
recommended future capability requiring implementation and evidence. “Refuse” is
the recommended milestone boundary, not a report that an extension refusal engine
was implemented. Current unsupported native syntax still follows normal CLI errors.

| ID and concrete use | Option B support/refusal and consequence | Alternative path and its limit |
| --- | --- | --- |
| EXT-001: select CR3 inputs with a unique normalized ISO value at least 400 | **Plan:** the existing pure-filter grammar, with exact typed comparison, explicit coverage and three-valued results. Ambiguous/missing conversion or incomplete uniqueness yields unknown, not selection. No arbitrary Perl condition compatibility. | Read native snapshots and filter in caller code today where the required metadata is actually available. The caller owns its logic, limits and selection errors. |
| EXT-002: call an existing canonical field `capture_iso` and supply a numeric threshold as a parameter | **Plan:** explicit versioned alias/parameter data, after a finite format is specified. An alias resolves to the existing identity; it neither adds a parser nor converts types. No substitution of parameter text into an expression. | Use canonical selectors and literal values. Friendly naming convenience is deferred until its data contract exists. |
| EXT-003: name a private XMP namespace property `reviewRating` with an integer type | **Plan:** inspect an explicitly selected data definition with namespace URI, local name, type, provenance, revision and collision policy. This declares interpretation only; readable presence and enabled operations remain separate. No inferred insertion, RAW write or sidecar publication authority. | Retain/report unknown XMP under supported reader coverage, or contribute a reviewed definition. A new label alone cannot establish its type or writability. |
| EXT-004: calculate a custom exposure score from ISO and exposure time, including rounding | **Refuse custom calculation at this milestone.** The initial filter grammar has no arithmetic or user function. LEG-006's broader bounded-calculation ambition remains an explicit gap until exact units, rational arithmetic, missing/duplicate inputs and limits are specified. | Compute a report field in caller code from explicit value views. Do not relabel it as a stored tag or use it to bypass an independently validated mutation plan. |
| EXT-005: copy original capture date, fractions and offset to explicitly paired XMP | **Use the separately bounded native mapping work, not a callback.** The [native date adapter](../sidecars/native-date-adapter.md) supplies in-memory authored integration evidence only. Unsupported companion/dependency cases refuse; publication remains unavailable. No generic executable conversion is planned here. | Export observations for caller review or pursue the existing sidecar acceptance work. Neither is permission to write RAW or publish XMP. |
| EXT-006: use Perl/regex/interpolation to format captions or metadata-derived filenames | **Refuse automatic expression translation/execution.** The pure filter does not supply regex, formatting or filename effects. Print templates and planned rename semantics remain separate PR-013/PR-018 and LG-002 work. | Format exported data in caller code. Running a separate rename tool is the caller's operation and does not receive imageinfo's preservation/recovery guarantees. |
| EXT-007: load a module that parses a previously unknown maker-note field or supplies a conversion callback | **Refuse runtime loading**, including native dynamic libraries and legacy module/config code. Unknown data remains unknown. No extension can declare opaque dependencies safe or certify a writer. | Submit a normal reviewed source change with provenance, bounds and lawful fixtures. This costs a new build/release and retains format-specific acceptance. |
| EXT-008: consult a local catalog or web service while evaluating a condition | **Refuse implicit lookup/I/O inside filters or definitions.** No callbacks, file paths to evaluate, environment lookup or network calls become filter functions. Offline/privacy defaults remain. | The caller explicitly obtains data and supplies typed literal parameters to a future supported request. The request does not silently refresh that data or claim external data provenance. |
| EXT-009: run a per-file hook, shell command or persistent module state before/after reads or writes | **Refuse hooks and session code loading.** No auto-discovery from the photo directory, request, saved plan, XMP or imported config. Neither a read nor preview starts a subprocess on the caller's behalf. | Explicit caller orchestration can invoke imageinfo's available operations. It owns its process state and external effects; the proposed session contract still isolates request settings and grants no hook facility. |

EXT-001's intended example is the existing proposed grammar:

```text
exists("EXIF:ISO") and value("EXIF:ISO","normalized") >= 400
```

It is design data, not executable native CLI syntax today. Absence is true only
under complete relevant coverage; an explicit null remains present. Unknown is a
reported selection failure by default. Aliases, values and definition fields are
literal data; none are accepted as code fragments. No proposed syntax is invented
for EXT-002/003 before their bounded data formats exist.

## Alternatives and costs

| Choice | Concrete support boundary | Consequence |
| --- | --- | --- |
| A: fixed built-ins only | Refuse all user expressions and definitions, including EXT-001/002/003; keep ordinary existing selectors and caller-side processing. | Smallest implementation commitment, but ordinary selection/custom-name workflows need external code and LEG-006/007 are deferred further. Long-term parity gaps remain. |
| **B: selected pure/data forms (recommended)** | Plan EXT-001/002/003 with their stated bounds; retain the independent EXT-005 mapping path. Refuse EXT-004 and EXT-006–009 executable/general-purpose behavior. | Adds finite parser/data-validation work and explicit unknown semantics, with no new runtime dependency chosen here. Existing scripts need migration; full arbitrary-code parity remains open. |
| C: explicit trusted executable support | Permit selected expressions/modules only after a separate design chooses code provenance, load path, startup consent, authority, errors, resource behavior and compatibility/versioning. | Could address advanced uses, but execution could affect caller files, process state and network under the chosen authority. Same-process code requires a different trust contract from input data; separate-process execution alone does not establish a sandbox. No such model or implementation is adopted here. |

Option C is a future product alternative, not an opt-in switch supplied by this
proposal. There is no demonstrated need here that justifies selecting an ABI,
plugin discovery system, interpreter, worker protocol or isolation mechanism.
The long-term functional parity goal is preserved under all three choices;
none promises that arbitrary old executable scripts will run unchanged.

## Authority and failure contract proposed for B

1. Selection reads supported immutable observations. Definitions/parameters cannot
   open another input, load a module, spawn a process, alter environment/settings,
   access the network or perform a mutation. Implement this through the actual
   finite language/data contract and ordinary code review; a disabled capability
   is **not** an OS sandbox or evidence of safe arbitrary-code execution.
2. Inspect explicitly chosen definition data with visible provenance/revision.
   Reject built-in shadowing, unknown members, invalid types, duplicate/conflicting
   definitions and unsupported versions before applying the definition set.
   Cycles and excessive dependency nesting/work refuse. Do not partially install
   an invalid set or retain it as ambient state for a later unrelated request.
3. Syntax/unknown function/unsupported executable forms fail whole-request
   preflight before media work, with an attributable native diagnostic. A future
   nonexecuting migration report identifies unsupported tokens and the relevant
   EXT use; it never imports a config to discover its effects. Runtime value/coverage
   uncertainty uses the existing proposed unknown/partial-selection contract.
4. Publish finite expression bytes, nesting, definition counts, dependency work and
   result limits before advertising these features. Values/defaults are not chosen
   here. Verify exact arithmetic and coverage behavior and fail explicitly on limits;
   do not claim a hard time/memory sandbox from an operation counter.
5. Derived reports/definitions confer no mutation or privacy certification. Any
   future use in a write must bind the actual source observations, conversions,
   target identity, losses and revisions through ordinary independent admission.
   The current RAW/storage/sidecar publication gates remain unchanged.

## Exact decision and requirements impacts

**Decision requested when Terry reviews #0054:** accept B for the first RAW
milestone: plan EXT-001/002/003 under these bounds, keep EXT-005 within its existing
independent mapping work, and refuse EXT-004/006/007/008/009 executable behavior.
This accepts a scope boundary, not implementation readiness or numeric limits.
Choosing A instead explicitly defers even the pure/data forms. Choosing C requires
a separately scoped executable-support design before implementation. No pending
answer prevents delivery/review of this proposal.

The following are **proposed updates on acceptance**, not edits to accepted
requirements made by this document:

| Existing identifier | Exact impact if B is accepted |
| --- | --- |
| [OD-02](../open-decisions.md) | Record: “First RAW milestone uses bounded pure filters and explicit alias/parameter/XMP definition data (EXT-001–003); arbitrary executable expressions/modules/hooks and custom calculations are refused. Separate mapping evidence remains independent. No execution runtime or sandbox selected.” Keep later executable model and implementation evidence open. |
| [PR-018](../product-requirements.md) | Preserve the full requirement. Add a milestone qualification naming EXT-001–009 and explicitly defer arithmetic/custom composites, executable conversion and general print expressions. Do not mark all transformations/templates/extensible definitions implemented. |
| PR-017, PR-022; [CLI-015](../cli-requirements.md) | Tie future filters/aliases to exact canonical identity, named revision, value view, complete/partial coverage and documented unknown results. Alias declaration changes neither presence nor writability. |
| PR-026, PR-027, PR-029 | Preserve untrusted-data/offline/versioning requirements; define finite data/parser limits and reject unsupported versions. Add no exception that lets a template/config run commands or access I/O implicitly. Actual robustness evidence is still required. |
| CLI-002, CLI-005, CLI-009, CLI-016; LEG-002/003/007 | Require help, validation and migration findings to agree on supported forms and fail unsupported syntax explicitly. No legacy pass-through or silent rewriting. Publish issue/status semantics with implementation; this proposal adds no production issue code. |
| LEG-006; [MAP-015/MAP-026 and LG-003](surface-ledger.md) | Refine the milestone subset using this matrix. Keep MAP-026/LG-003 open for executable equivalence and future trust design; do not change the entire row to equivalent or close it because a refusal policy is documented. |
| [CAP-019/CAP-040/CAP-046, GAP-006/GAP-011](../inventory/canon-eos-r5-cr3.v1.json) | Retain existing capability statuses and gaps. MAP-026's references do not become implementation evidence. Add scoped disposition references only; no broad capability or inventory gap closes. |
| [LEG-008/009 and OD-07 integration](integration.md) | Preserve ordinary library caller authority and request-local settings. No config/module load or persistent callbacks in the proposed session protocol; no ABI/FFI promise. |
| PR-009/011/013/024/025; WS/SAF admission | No weakening or enablement. Mapping, date transforms, filename effects, preservation, storage/recovery and write admission retain their existing separate evidence requirements. |

## Verification and source limits

Review this document for all nine IDs, a concrete disposition and consequence for
each, A/B/C comparison, and the exact Terry choice above. Check local links,
requirement references and `git diff --check`; run `python scripts/check_docs.py`.
These are documentation checks. No expression parser, extension loader, reference
execution, real-media test, malicious-code isolation test or performance benchmark
was run or qualified by #0054. Future implementation must test supported forms,
unknown/duplicate/partial values, rejected executable forms, invalid/cyclic data,
limits, state isolation and attempted authority escalation before claiming support.

Upstream facts are inherited from the existing **2026-10-10 source observation**,
ExifTool **13.59**, commit `2200871d9cef988051d2a99d67df3bda6cbb30a8`.
This 2026-10-15 proposal does not assert a refreshed or latest-release observation:

- The [application manual](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/exiftool_pod.html)
  supplies the surveyed `-if`, `-config`, `-use` and parameter/report surfaces.
- The [configuration example](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/config_files/example.config)
  supplies the existing observation that definitions/composites can include
  executable expressions; it is not imported, executed or copied here.
- The [API reference](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/lib/Image/ExifTool.pod)
  supplies the surveyed extension and request-state surfaces. See the
  [existing validation record](validation.md) for observation scope.

The recommendation follows imageinfo's own RAW requirements and small Rust
library/CLI direction. Upstream identifiers describe functional migration needs;
they prescribe no internal architecture, API shape or execution mechanism.
