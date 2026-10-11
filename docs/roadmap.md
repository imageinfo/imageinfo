# Roadmap

Full ExifTool functionality remains the long-term goal. Camera RAW metadata is the
current scope, beginning with Canon EOS R5 full RAW CR3. C-RAW/DPRAW and other RAW
families need separate evidence. RAW development and sensor recompression are out
of scope.

**As of 2026-10-10:** initial requirements cards #0001–#0010 and private corpus
baseline #0013 are accepted. Terry has opened **implementation selection, #0011**.
[ADR-0011](implementation-selection/README.md) is accepted. The
[foundation](foundation/README.md) now implements help/version/refusal boundaries.
[#0020](reader/README.md) now implements a declared R5 metadata/preview slice.
Whole-format/tag-family support and further RAW capabilities remain open.

An empty Ready for Work lane does not establish completed architecture. It can mean
the prepared queue is exhausted or its next item awaits a decision. Backlog work
must be scoped and triaged against the current milestone before execution.

## Delivery sequence

| Phase | Current position | Exit evidence |
| --- | --- | --- |
| Requirements baseline | Initial scope/workflows/contracts accepted | Stable requirements, source ledger, reviewed CLI examples and explicit gaps |
| RAW compatibility specification | Initial matrix and fixture contracts accepted; breadth remains open | Exact format/tag/location/operation assertions for each increment |
| Implementation selection | #0011 Rust direction accepted | Accepted language/component direction, alternatives and first milestone |
| Executable foundation | Implemented foundation under #0019 | Pinned build, library/CLI boundary, synthetic wire/help tests and declared platform CI |
| R5 read foundation | Declared first slice implemented under #0020 | Bounded recognition, selected exact metadata, preview extraction and malformed-input/private differential evidence |
| Associated XMP and guided CLI | Subsequent read/UX increments | Reviewed XML component, faithful namespaces/values/time, shared commands and accessible menus |
| Safe mutation | #0014 evidence work; no writer enabled | Sensor/calibration/unknown-data preservation, independent checks and per-profile concurrency/recovery |
| RAW workflow breadth | Later increments, with #0015 | Batch, transformations, naming, geotagging, import/export and persistent integration evidence |
| RAW long tail and stewardship | Ongoing | More variants/RAW families, published gaps, independent maintenance and repeatable releases |
| Broader ExifTool parity | #0012 deferred umbrella | Separately accepted media scope and format-specific evidence |

The [first milestone](implementation-selection/first-milestone.md) defines the
read subset and gates. Full legacy CLI compatibility and embedded writes need not
be complete before a useful native reader exists.

## Follow-up ownership

| Card | Responsibility | Relationship to first implementation |
| --- | --- | --- |
| #0011 `implementation-selection` | Language/components against requirements | Rust direction accepted; earlier language deferral lifted |
| `executable-foundation` | Bootstrap accepted stack and shared command/help contracts | First implementation increment after selection acceptance |
| `r5-read-slice` | Bounded recognition, selected metadata and preview extraction | Depends on foundation; grows by reviewed mappings |
| #0014 `write-validation` | Writer/storage profiles, preservation, privacy and fault recovery | Gates mutations, not read-only progress |
| #0015 `compatibility-evidence` | Remaining options, serializers, mappings, plan/session contracts | Pull in first-slice blockers; unrelated legacy breadth can follow |
| #0016 `performance-measurements` | Correctness-gated baselines and numeric budgets | No performance target inferred from spike durations |
| #0017 `governance-readiness` | Maintainers/backups, security and release/recovery controls | Language choice does not establish shared maintenance |
| #0018 `corpus-expansion` | Targeted variation, negative cases and reference repeatability | Initial eight files cover a narrow stratum; request more for specific assertions |
| #0012 `broader-format-parity` | Eventual full ExifTool scope | Deferred; does not expand the R5 milestone |

The accepted [private baseline](corpus-baseline/README.md) includes eight RAWs,
24 previews, three XMP outputs and 97 ExifTool reference invocations. New selection
probes are separate feasibility evidence. Neither establishes native metadata
parity. Personal media and exact private captures remain excluded from public Git.

## Progress reporting

Report capability cells and verified workflows, not percentages derived from tag
counts, extensions, completed design cards or prototype assertions. Keep requirements,
recommendations, accepted decisions, implementation and verified behavior distinct.
Partial read support needs an explicit field/location list. A write claim requires
stronger evidence than a successful read.

## New-output-first increments

On 2026-10-11 Terry selected new CR3 outputs first and authorized multiple cards.
#0014 is now the open parent of seven sufficiently scoped children:

- #0021: [private fixed-width candidate preservation](write-safety/new-output-preservation.md),
  independent RAW unpack and bounded primitive/failure observations.
- #0022: guarded new-name storage, private properties, persistence and recovery.
- #0027: exact CR3 write admission, coupled/checksum constraints and known-authenticity
  refusals before the first production new-output workflow.
- #0023: production preview/apply integration after the exact operation/profile gates.
- #0024: explicit RAW/XMP pairing, mappings and sidecar synchronization.
- #0025: privacy catalogs, residual/uninspectable data and authenticity coverage.
- #0026: existing-target replacement, grouped operations, originals and restore/prune.

#0021 supplies experimental evidence, not an enabled writer. #0022/#0027/#0023 still gate
new CR3 publication; #0024–0026 retain the parent acceptance scope. Scoped cards
remain Ready for Work with explicit dependencies. #0012 remains intentionally held.

#0022 initially had four independently reviewable children. #0028 delivers
[read-only recovery qualification](write-safety/recovery-inspection.md), including
the late-stage counterexample that prevents enablement. #0029 owns live
source/stage/namespace exclusion, #0030 Windows private properties/persistence,
and #0031 isolated crash/durability/guarded repair. The parent remains open; a
research copy or matching checksum cannot authorize production writes or recovery.

[#0029 object guards](write-safety/object-guards.md) now measure Windows content
exclusion, anonymous Linux staging and lease-break/path/property limits separately.
They do not close full source/path/property/persistence admission; #0030/#0031
must combine evidenced cells without weakening the accepted contract.

[#0030 Windows property/publication qualification](write-safety/windows-properties.md)
demonstrates private ACL creation and failed guard/publication composition, including
late named-stage substitution. #0032 retains actual guarded Windows publication,
property windows and namespace/receipt acknowledgements before #0031. No profile is
enabled; neither owner-only ACLs nor a successful file flush establish the full gate.

[#0032 held-candidate publication](write-safety/bound-windows-publication.md) now
implements the actual private atomic root/candidate and guarded Windows rename
sequence. Its 75-case marker qualification closes the late default-stream substitution
route. Property/link protection, namespace durability and guarded recovery remain
explicitly unsupported; complete-profile admission refuses before filesystem effects.
#0031 owns isolated durability/repair against the sequence; #0022/#0014 stay open.
