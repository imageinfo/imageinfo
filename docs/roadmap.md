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
sequence. Its 78-case marker qualification closes the late default-stream substitution
route. Property/link protection, namespace durability and guarded recovery remain
explicitly unsupported; complete-profile admission refuses before filesystem effects.
#0031 owns isolated durability/repair against the sequence; #0022/#0014 stay open.

[#0031 guest qualification](write-safety/guest-durability.md) supplies bounded
Linux anonymous-stage interruption/restart observations, adversarial evidence and
actual guest ENOSPC/emulated device flush errors. Every state refuses automated
repair/prune because complete property/path exclusion, custody authentication and
durable-receipt admission are missing. Windows namespace/persistence against #0032
remains unverified. The #0022/#0014 parent retains the applicable software/VM
enablement cells. Terry's [best-effort power-test policy](write-safety/power-test-policy.md)
excludes physical-power and dedicated-hardware qualification; no such cell blocks
implementation or release. Other correctness gates remain unchanged.

[#0027 read-only admission](write-safety/write-admission.md) adds native calendar,
occurrence/all-allocation checks and bounded known-provenance refusals. Eight private
alias candidates change two interpreted date names while retaining all sensor bytes;
this is a counterexample to treating byte complement/RAW decode alone as field-scope
proof. The new gate refuses those aliases and unproved opaque/checksum dependencies.
All current real-camera mutation admissions remain refused. #0022/#0014 and #0023
still require an actually supported operation/storage profile; #0025/#0018 retain
broader authenticity/privacy/corpus coverage. Acceptance of this scoped refusal
handoff does not authorize skipping the remaining gates.

[#0033](write-safety/owner-rights.md) continues #0022 with actual fresh-artifact
OWNER RIGHTS property/link/ADS exclusion and held publication. It qualifies the
stronger creation policy separately from after-open sealing and records preexisting
handle bypasses plus constrained post-exit owner access. Complete source exclusion,
authenticated custody/guarded recovery and Windows crash/receipt persistence remain
open; no ordinary editable-output or weaker concurrency promise is assumed.

[#0034](write-safety/source-oplocks.md) follows Terry's acceptance of #0027/#0033
with existing-source RH/RW/RWH oplock qualification. Time/readonly/ADS/new links
and late alias time/ADS bypass every measured request without a break. Other
actors' ACK-required waits and preexisting-handle refusals are separate cells;
source property exclusion remains unqualified. No source ACL, production profile,
parent safety requirement or supported mutation policy is changed.

[#0036](write-safety/windows-inspection.md) adds read-only Windows restart inspection
for #0032. Five portable tests and 35 interruption/conflict/refusal cases distinguish
matching observations from committed outcomes. It reuses the OS boundary/checksums,
adds no keys/encryption or OS APIs, and preserves production storage/admission gates.

[#0037](legacy-compatibility/native-json-errors.md) starts #0015's concrete native
integration work: one valid explicit JSON selector survives CLI syntax failure.
Portable ordering, literal/native argv, bounded diagnostics and no-extraction tests
verify the production behavior. Broader compatibility/session/plan gaps remain open.

[#0038](write-safety/staging-cleanup.md) advances first-ranked blocker #0022 with
live guarded prepublication file cleanup. Actual owned-handle deletion preserves
foreign names/entries and records partial/deferred/error states; roots remain.
Publication attempts, restart prune and complete profiles still refuse.

[#0039](write-safety/output-release.md) tests creator-held release of fresh sealed
outputs to ordinary private-owner editing. Both WRITE_DAC and full-control requests
still return access denied; the unsealed control's setter succeeds but fails exact
descriptor verification. Thirty marker cases preserve real interruption/collision
outcomes and distinguish post-exit restricted editing from allowed rename/delete.
No ordinary output policy, production profile or parent criterion is enabled.

[#0040](write-safety/staging-limits.md) resumes #0022's bounded-scratch cell with
portable checked total-byte preflight and exact-length copies in the existing
staging worker. Ten portable tests, 17 actual limit/source/cancellation cases and
the retained 27-case cleanup regression pass. This bounds logical artifact bytes,
not disk allocation/available space or cumulative recovery storage. Usable output,
complete guards, persistence/recovery and actual RAW admission remain open.

[#0041 / OD-11 option A](write-safety/practical-output-policy.md) was explicitly
accepted by Terry in chat on 2026-10-14: ordinary private-owner editable new output,
continuous byte/name guards and boundary property checks. WS-009/010/011 and
SAF-005/006/007 now record that specific refinement; the eight next evidence cells
remain unimplemented. Format admission and complete storage/persistence/recovery
gates are unchanged. Replacement does not inherit this new-output policy.

Direct work on [#0022](write-safety/ordinary-output.md) implements the accepted
ordinary-owner marker sequence in the existing research crate. Native byte/name,
property-check, owner-editing and read-only restart observations do not enable a
complete profile or RAW write. A [disposable Windows guest](write-safety/windows-guest.md)
is separately provisioned for Windows interruption qualification; host/other-OS
results and physical power loss remain distinct evidence boundaries.
