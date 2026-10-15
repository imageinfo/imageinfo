# Documentation map

This is the initial, language-agnostic requirements baseline, researched on
2026-10-10, advanced on 2026-10-11. The [native R5 reader](reader/README.md) implements
a declared metadata/preview subset with partial coverage. The [foundation](foundation/README.md)
supplies help/version/wire boundaries. Editing and broader compatibility remain
proposed/unimplemented.

**Delivery focus: camera RAW metadata first. Long-term goal: full ExifTool feature
parity.** Broader research is retained as future reference; it does not expand the
current milestone. Rust/ADR-0011 is accepted; requirements remain independent of
internal code organization.
The first camera/format target is **Canon EOS R5 CR3**.

| Document | Purpose |
| --- | --- |
| [Delivery increments](delivery-increments.md) | All-ticket scope audit, bounded child breakdown and unchanged acceptance/triage gates. |
| [Native R5 read slice](reader/README.md) | Actual supported fields/resources, limits, source mapping and scoped differential/fuzz/CI evidence for #0020. |
| [Executable foundation](foundation/README.md) | Implemented CLI subset, pinned build/checks, wire output, dependency notices and actual validation for #0019. |
| [Implementation selection](implementation-selection/README.md) | ADR-0011: Rust recommendation, Go/C# alternatives, disposable probes, component choices and the first read milestone. |
| [RAW scope](raw-scope.md) | Current format/workflow boundaries and the distinction from eventual full parity. |
| [Canon EOS R5 CR3](canon-eos-r5-cr3.md) | First camera/format milestone, priority workflows, and variant evidence. |
| [CR3 capability inventory](inventory/README.md) | Versioned capability rows, schema, CLI/API mapping, evidence gates, and audit gaps for card #0002. |
| [Metadata contract](metadata-model/README.md) | Occurrence identity, exact values, source provenance, selection and edit-intent schemas/examples for card #0004. |
| [Fixture and parity plan](fixture-plan/README.md) | Prioritized corpus cases, provenance/admission, oracle profile, experiment records, and comparison rules for card #0005. |
| [First private corpus baseline](corpus-baseline/README.md) | Eight admitted R5 full RAW originals, acquired references, actual read/preview/XMP observations and remaining evidence limits for #0013. |
| [Safe mutation and recovery](write-safety/README.md) | Per-file publication, preserved originals, concurrency, recovery, platform constraints and synthetic acceptance cases for card #0006. |
| [New-output preservation evidence](write-safety/new-output-preservation.md) | #0021 experimental fixed-width candidate, independent RAW decode and NTFS/WSL primitive observations; #0014 stays open and no writer profile is enabled. |
| [Recovery qualification](write-safety/recovery-inspection.md) | #0028 actual Rust worker/read-only inspector, adversarial Linux/Windows/mount evidence and failed enablement gate; #0022 stays open. |
| [Object guard qualification](write-safety/object-guards.md) | #0029 Windows mandatory sharing/identities, Linux anonymous stages/lease limits and explicit full-profile refusals. |
| [Windows property/publication qualification](write-safety/windows-properties.md) | #0030 private ACL creation, actual guard/move incompatibility, late substitution and missing namespace acknowledgement; #0032 retains implementation gates. |
| [Held-candidate Windows publication](write-safety/bound-windows-publication.md) | #0032 private atomic creation, retained guards/live identity, actual directory flush ordering and explicit unsupported complete-profile admission. |
| [Disposable guest durability/recovery](write-safety/guest-durability.md) | #0031 isolated Linux guest interruptions, restart/adversarial/flush-failure observations, retained safe repair/prune refusals and unverified Windows/physical power-loss cells. |
| [CR3 date admission/provenance refusals](write-safety/write-admission.md) | #0027 native calendar/occurrence/allocation checks, known indicator catalog, private alias counterexamples and unproved dependency refusals; no writer enabled. |
| [Windows OWNER RIGHTS qualification](write-safety/owner-rights.md) | #0033 fresh artifact time/security/link/ADS guard improvement, held publication, preopened-handle and read-only post-exit limits; complete profile remains unsupported. |
| [Existing-source Windows oplocks](write-safety/source-oplocks.md) | #0034 actual RH/RW/RWH property and late-alias bypasses, ACK-required waits, preopened-handle/refusal and process lifetime evidence; complete source guard remains unqualified. |
| [Windows restart inspection](write-safety/windows-inspection.md) | #0036 read-only classification of interrupted #0032 transactions, portable record tests and no-effect repair refusals; no keys or new OS APIs. |
| [Native JSON syntax errors](legacy-compatibility/native-json-errors.md) | #0037 production error-envelope routing for one explicit JSON selector, literal/native argv boundaries and portable no-effect tests; broader integration remains open. |
| [Owned staging cleanup](write-safety/staging-cleanup.md) | #0038 actual live prepublication file-handle cleanup, foreign-entry preservation, reader deferral and partial/refused outcomes; roots/restart/postpublication actions remain retained. |
| [Owned output policy](write-safety/output-release.md) | #0039 creator-held release returns access denied; controlled descriptor mismatch, editing/name effects and interruption evidence; ordinary editable output remains unqualified. |
| [Staging byte limits](write-safety/staging-limits.md) | #0040 portable total-byte preflight and exact-length copies in the existing worker, native partial/refusal/cancellation evidence and cleanup regression; no OS quota or space reservation. |
| [Practical output-policy decision](write-safety/practical-output-policy.md) | OD-11/#0041 option A accepted: guarded byte/name guarantees, ordinary owner editing and property check boundaries; requirements refined, backend/format gates remain. |
| [Ordinary-owner output protocol](write-safety/ordinary-output.md) | Direct #0022 live source/candidate/name guards, declared property observations, ordinary owner editing and read-only restart evidence; complete profiles remain gated. |
| [Disposable Windows guest](write-safety/windows-guest.md) | Installed evaluation guest; eight NMI/restart and eight emulator-kill/restart observations, owner actors and preserved namespace/receipt limits. |
| [Windows persistence ordering](write-safety/windows-persistence.md) | Direct #0022 three-mode comparison: 69 native cases, 33 guest faults, variable pre-flush name survival and unchanged admission/repair gates. |
| [Caller-bound restart actions](write-safety/windows-restart-actions.md) | Direct #0022 explicit-context marker prune and output observation: 61 native cases, five guest faults, fresh guards, partial/foreign retention and unchanged production recovery gates. |
| [Caller-history custody snapshots](write-safety/windows-custody.md) | #0043 external whole-history snapshots, release-fence ordering and 41 native cases; explicit caller trust, accepted same-byte replacement and separate #0044 guest qualification. |
| [Windows caller-history guest qualification](write-safety/windows-custody-guest.md) | #0044 four audited interruption cells: two NMI and two emulator terminations; exact #0043 source/static worker binding, explicit caller controls and retained freshness/profile limits. |
| [Bounded namespace and receipt protocol](write-safety/namespace-receipt-protocol.md) | #0045 proposed single-output state/receipt ordering, portable logical model and finite fault plan; profile, backend and actual durability qualification remain separate. |
| [Windows marker receipt sequence](write-safety/namespace-receipt-marker.md) | #0046 bounded exclusive receipt construction and caller-bound read-only inspection; raw flush observations retain all commitment/profile refusals. |
| [Windows marker receipt guest qualification](write-safety/namespace-receipt-guest.md) | #0047 exact #0046 static worker; 34 audited cases, three fault methods, two property-drift refusals and disclosed operator continuation; all commitment/profile/repair gates retained. |
| [Cumulative retained-work budget](write-safety/cumulative-budget.md) | #0049 fixed-worker supervisor, monotonic logical charges and 15 native cases; no disk reservation or persistent quota. |
| [XMP component and model review](sidecars/xmp-component.md) | #0081 pinned read-only XML experiment, expanded-name/occurrence model and finite limits; no production parser or serializer. |
| [Reproducible read collector](performance/read-collector.md) | #0060 bounded timed subprocess collection, correctness oracle and versioned records; actual smoke evidence without a performance baseline claim. |
| [Single-date saved preview contract](legacy-compatibility/cr3-preview-plan.md) | #0055 strict nonexecuting versioned plan, exact occurrence/bytes and separate caller authority. |
| [Nonmutating date preview](reader/date-preview.md) | #0076 actual field/admission checks, advisory byte partition and CLI observations with no output effects. |
| [Saved preview source binding](legacy-compatibility/cr3-preview-source-binding.md) | #0077 actual bounded content hash, exact occurrence revalidation and stale-plan refusals without live guard or mutation authority. |
| [Explicit RAW/XMP pairing](sidecars/pairing.md) | #0082 explicit canonical paths, held physical-identity comparison and alias/collision refusals without basename inference or XMP parsing. |
| [One-way XMP date mapping](sidecars/date-mapping.md) | #0083 bounded versioned original-snapshot date intent, exact fraction/zone preservation and explicit conflict/loss choices; no serializer or write integration. |
| [Native storage-full observations](write-safety/native-storage-failures.md) | #0048 five actual secondary-volume Windows guest cases, native errors, retained partial/postpublication artifacts and read-only inspection; device-error and production gates remain. |
| [Exact backend admission ledger](write-safety/profile-admission.md) | #0051 complete WS/SAF trace and portable refusal model; every current profile remains refused and hypothetical premises grant no authority. |
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
