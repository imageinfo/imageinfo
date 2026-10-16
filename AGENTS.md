# imageinfo project guidance

## Ticket priority default — corrected 2026-10-16

Terry clarified that **P3 is Normal**, superseding the earlier P2 default.
Use P3 for normal new tickets. Elevate above P3 only for concrete urgency,
impact, deadline or explicit owner direction; dependency depth or number of
dependents is not an urgency reason. Preserve dependency relationships and use
the configured triage order to sequence normal work.

## Current power-test scope — Terry's decision, 2026-10-15

This FOSS project uses best-effort testing. No physical power-drop testing or
dedicated test hardware is required or planned. Future power-related tests stop
at turning disposable VMs off; do not add host crashes, guest NMI/bugcheck
campaigns, DUT/storage power cuts or hardware qualification as further gates.
Missing physical-power evidence is not a blocker or admission prerequisite.
#0050/#0101 and their equipment/license requests are retired. Preserve old
observations as history, label VM-off/cache limits honestly, and do not promise
physical hardware survival. This decision supersedes contrary historical power
requirements below. See `docs/write-safety/power-test-policy.md`. Other format,
preservation, concurrency and truthful-outcome requirements remain separate.

## Implemented foundation and historical qualification

Terry accepted Rust/ADR-0011 on 2026-10-10 and authorized the production foundation
under #0019. The root Cargo package contains a small library and CLI; its implemented
foundation is documented in `docs/foundation`; the bounded native R5 read/preview
slice and its verified limits are in `docs/reader`. Requirements contracts remain language
independent. Research code under `experiments/` is not production imageinfo and
must not be promoted without ordinary implementation review and evidence gates.
Terry selected new CR3 outputs first and authorized splitting #0014 on 2026-10-11.
#0021–0027 retain the parent's full safety scope. The fixed-width candidate under
`experiments/0021-cr3-candidate` is research; no production writer or mutation
storage profile is enabled. See `docs/write-safety/new-output-preservation.md`.
#0022 was initially split into #0028–0031. #0028's Rust worker/inspector is qualification
research; its late-stage counterexample fails the enablement gate. Read-only
inspection grants no repair authority. See `docs/write-safety/recovery-inspection.md`.
#0029 qualifies separate content/object/path mechanisms, not a complete backend.
Windows sharing, Linux anonymous staging and breakable leases have different
property/namespace limits. See `docs/write-safety/object-guards.md`; no profile
or production publication permission is inferred from a passing primitive test.
#0030 measures owner-only ACL creation and Windows publication/property boundaries.
#0029's ancestor guard refuses the measured pathname move; without it a late stage
substitution publishes foreign marker bytes before rejection. #0032 retains actual
guarded Windows publication/property/persistence implementation before #0031.
See `docs/write-safety/windows-properties.md`; no full profile is enabled.
#0032 implements researched held-candidate Windows publication, atomic private-root
creation and live identity/property checks. Its isolated SDK boundary is reviewed;
root production unsafe policy remains unchanged. Property/link mutation and actual
namespace/recovery qualification are separate missing cells, so strict admission
refuses before effects. See `docs/write-safety/bound-windows-publication.md`.
#0031 qualifies a separate disposable Linux marker guest's interruption/restart and
adversarial/error observations. Finalize/prune/admit refuse before mutation without
complete property/path exclusion, authenticated custody and qualified receipts.
Linux results do not qualify #0032's Windows sequence; Windows OS crash and physical
power loss remain unverified. See `docs/write-safety/guest-durability.md`; no profile,
production mutation, rollback/replay or cleanup authority is enabled.
#0027 adds root read-only CR3 date/occurrence/all-allocation checks and a bounded
known-provenance refusal catalog. Private DateTimeDigitized aliases expose coupled
date effects despite exact complement and RAW-unpack equality. Opaque/checksum
dependencies refuse every current real-camera mutation admission. See
`docs/write-safety/write-admission.md`; no writer/profile or #0023 permission is enabled.
#0033 qualifies fresh Windows OWNER RIGHTS property/link restrictions, including a
stronger data/append deny that closes the measured ADS route while held publication
works. Preopened time/security handles bypass later sealing; strongly sealed markers
remain read-only after exit. Existing-source, custody/recovery, operational output
policy and Windows persistence remain missing. See `docs/write-safety/owner-rights.md`;
no production profile or source ACL mutation is enabled.
#0034 measures read-only existing-source RH/RW/RWH oplocks. Time/readonly/ADS/new
link actors bypass every measured request without a break; some data/security
actors wait for a break until holder release. Strict admission still refuses.
See `docs/write-safety/source-oplocks.md`; source ACLs and production policy remain
unchanged, and no complete source-property guard or backend is qualified.
#0036 adds bounded read-only Windows restart inspection to #0032, with portable
record parsing/state tests and the existing OS boundary. It validates record
integrity and actual artifact bindings; no encryption, receipt keys or new OS APIs
are introduced. See `docs/write-safety/windows-inspection.md`; repair and writer
profiles remain gated. Keep storage/recovery straightforward and cross-platform;
do not infer secrecy/key-management requirements from integrity/ownership checks
(Terry's clarification, 2026-10-13).
#0037 fixes root production CLI syntax-error routing: one valid explicit JSON
selector before `--` emits the existing status-2 envelope even when grammar fails.
Invalid/duplicate output selection remains plain stderr; literals/attached data do
not select a channel. See `docs/legacy-compatibility/native-json-errors.md`.
Broader #0015 integration/session/plan gaps and all mutation gates remain open.
#0038 implements live prepublication cleanup of verified fresh owned staging files
using their retained handles. Foreign reinserted names/extra entries and roots stay
retained; readers can defer removal and partial/error work is reported. Cleanup
refuses after any publication attempt. See `docs/write-safety/staging-cleanup.md`;
this does not enable restart prune, directory cleanup, a writer or a full profile.
#0039 tests creator-held release from fresh sealed output to ordinary private-owner
editing. WRITE_DAC/full-control requests still return access denied; unsealed control
setter success is distinct from exact descriptor refusal. See
`docs/write-safety/output-release.md`; sealed research files are not an adopted
ordinary output policy. No source ACL, privilege, shared SDK or production gate changes.
#0040 adds portable total planned-byte preflight and exact-length copying to the
#0038 research worker. Short/overlong sources retain bounded partial staging files;
below-budget requests refuse before transaction creation. See
`docs/write-safety/staging-limits.md`; this is a logical-byte bound, not free-space
reservation, allocation accounting, an OS quota or production writer/profile support.
#0041/OD-11 option A was explicitly accepted by Terry in chat on 2026-10-14.
New outputs require proven continuous default-stream byte/name guards and relevant
filesystem-property checks at declared boundaries, with ordinary owner-editable
private output. Continuous exclusion of same-owner property changes is not promised.
See `docs/write-safety/practical-output-policy.md` and revised WS-009/010/011 and
SAF-005/006/007. Actual protocol/profile qualification and independent RAW admission
remain required; format, byte/name, persistence and recovery gates are unchanged.
#0022 now implements the live ordinary-owner marker sequence in the existing #0032
research crate, with source/candidate/name holds, property checkpoints, owner editing
and read-only restart classification. See `docs/write-safety/ordinary-output.md`.
Actual Windows guest qualification is separate; no namespace/receipt/crash, safe
restart finalize/prune, production storage profile or RAW permission follows from
passing live observations. See `docs/write-safety/windows-guest.md` for VM status.
#0022's activated 90-day Windows Enterprise evaluation guest is installed and
retained privately. Eight NMI bugchecks with controlled emulator restarts and eight
SIGKILL/restarts have actual read-only evidence; successful publication loses the
output name in the measured NMI case. Warm reset stalled in a preliminary run;
host caches remain alive and physical power loss is unverified. No complete profile
or restart repair is enabled. Use the exact fixture/restart limits in
`docs/write-safety/windows-guest.md`; never crash Terry's host or rearm the evaluation.
#0022's next marker increment separates held-file, parent and observation-record
flush calls and compares buffered/post-rename-flush/write-through handles. The
existing CreateFileW boundary gains one reviewed fixed FILE_FLAG_WRITE_THROUGH
flag; no dependency/API/privileged production helper is added. See
`docs/write-safety/windows-persistence.md`. Request labels and successful flush
returns remain observations, not namespace/receipt admission or repair authority.
Its audited 33-fault guest comparison finds variable name survival before the
explicit flush in both buffered-handle modes, two matching write-through API-success
observations and matching outputs in all 24 later flush cells. Host caches remain
alive, OS I/O shares the test volume and physical power loss is unverified. Treat
these as bounded observations; full namespace/receipt and restart-action gates remain.
#0022 now has explicit caller-directed marker restart actions: a trusted supervisor
captures actual owned bindings outside editable transaction records and confirms
stop before publication for prune. Fresh guards and identities/hash/property checks
select exact unpublished owned handles; source/root/foreign objects remain. Output
observation creation still never grants durable commit or production repair.
See `docs/write-safety/windows-restart-actions.md`; arbitrary JSON is not authenticated,
and automatic durable context custody, full profiles and RAW admission remain open.
Its 61-case native audit and five-fault guest audit cover caller-attested unpublished
prune, renewed-context observation validation and partial-prune retry refusal.
The guest retains host caches and the same verified host boot; namespace/storage/
physical-power qualification and durable caller-context custody remain separate.
#0043 adds bounded external caller-history snapshots in the same research worker.
A complete release-fence save precedes the original worker's publication continuation;
only actual caller-confirmed process exit before release permits stop attestation.
Captured-only or fenced histories yield no restart context. Typed whole-history
prefixes and fresh guards reject malformed/conflicting snapshots; source/root remain.
See `docs/write-safety/windows-custody.md` and its 41-case native audit. Same-byte
snapshot replacement is accepted: root identity does not authenticate historical
file identity, caller authority or freshness. No automatic durable custody/profile
is enabled; #0044 records separate guest observations and #0022 remains open.
#0045 adds a bounded namespace/receipt protocol proposal and test-only portable
model. Qualified acknowledgements are explicit hypothetical profile premises,
not current flush-return claims; a receipt cannot attest its own future flush.
Final guarded checks and noncontradictory trusted current history remain required.
See `docs/write-safety/namespace-receipt-protocol.md`; #0046 owns backend work.
The current worker and all production/RAW admission flags remain unchanged.
#0046 adds the guarded marker receipt sequence and read-only receipt inspection.
The separate receipt binds the installed candidate and three prior records;
an external caller context binds the actual held receipt identity and bytes.
The fixed unqualified profile label and all false commitment/admission flags
remain explicit. This minimal observational receipt is not #0045's qualified
outcome receipt. See `docs/write-safety/namespace-receipt-marker.md`; guest,
native storage-error, cumulative resource and full profile cells remain on
#0047/#0048/#0049/#0051. No source-media mutation or new SDK API is enabled.
#0044 qualifies four caller-history interruption cells in the retained standard-user
Windows guest against frozen #0043 source and an exact static worker that also
passes the native 41-case custody audit. Two NMI bugchecks and two emulator kills
produce four fresh boots: captured/fenced histories refuse context and prune,
confirmed-stop history permits three owned-handle removals, and renewed history
validates its exact existing observation while stale/postpublication prune refuses.
See `docs/write-safety/windows-custody-guest.md`. The host boot is unchanged, host
caches remain alive and the guest is normally shut down with private disk/captures
retained. No automatic freshness/custody, physical-power, namespace/receipt,
production profile or RAW admission is qualified.

#0047 qualifies 33 receipt interruption cells plus a normal control against frozen
#0046 source and an exact static worker with a separate 93-case native baseline.
Eleven process kills, eleven emulator kills and eleven fresh NMI bugchecks retain
34 unchanged byte/name inspection pairs and 32 matching property-observation pairs.
The `receipt-written` emulator/NMI cells show timestamp drift and guarded inspection
refusal; the cause remains unproven. A sign-in timeout required an explicitly
recorded operator continuation of pending read-only inspection and one final fresh
cell, without publication replay. See `docs/write-safety/namespace-receipt-guest.md`.
Host boot is unchanged; the guest is normally shut down with private disk/captures
retained. Host caches remain alive and no profile, repair or RAW gate is enabled.

#0049 adds an external fixed-worker cumulative logical-byte supervisor. All
candidate, record and custody constructions are charged before effects, and
charges remain retained across failures/cancellation. Fifteen native cells pass;
unknown state and other worker builds refuse. See
`docs/write-safety/cumulative-budget.md`; no physical allocation quota, persistent
budget, automatic custody or production profile is enabled.
#0081 reviews a pinned read-only XML component and bounded expanded-name XMP
model in a separate research crate. Unknown namespaces and duplicate occurrences
retain identity; unsupported structures refuse. See `docs/sidecars/xmp-component.md`;
no production dependency, XML writer or lossless round-trip capability follows.
#0060 adds a bounded read benchmark collector with real nanosecond timing,
deadline/capture limits, retained failed attempts and exact expected-output checks.
Its actual private R5 smoke run is functionality evidence, not a performance
baseline or cache/limit policy. See `docs/performance/read-collector.md`.
#0055/#0076/#0077 implement one nonexecuting saved-date intent, actual read-only
preview and bounded whole-source SHA-256/occurrence revalidation. Imported intent
never authorizes apply; matching content is not object identity or a live guard.
All current RAW dependencies and unavailable production storage profiles still
refuse. See `docs/legacy-compatibility/cr3-preview-plan.md`,
`docs/reader/date-preview.md` and
`docs/legacy-compatibility/cr3-preview-source-binding.md`.
#0082 resolves explicitly selected RAW/XMP paths with retained safe physical-file
identity comparison, finite directory/case checks and alias refusals. Basenames
never infer pairing; no content parsing or continuing guard is promised. See
`docs/sidecars/pairing.md` and the reviewed exact root dependency inventory.
#0083 specifies one original-snapshot CMT2-to-XMP DateTimeOriginal mapping with
exact source fractions/offsets, explicit existing singleton destination and
default conflict refusal. Replacement intent requires named destination losses
to be acknowledged. Its separate test-only model has ten passing vectors; see
`docs/sidecars/date-mapping.md`. No XML serialization or publication is enabled.
#0048 observes five actual native storage cases on a separate bounded secondary
NTFS USB/raw disk in the standard-user Windows guest. Four real storage-full
worker failures retain source and partial/postpublication artifacts, including
a 32 KiB candidate and an output with an empty failed receipt. Read-only inspection
preserves inventories and removes no owned handles. See
`docs/write-safety/native-storage-failures.md`; native read/device-flush failure,
physical power, complete storage profiles and RAW admission remain unqualified.
#0051 assembles the exact candidate's evidence and all 24 WS/16 SAF obligations
in a read-only ledger/model. Secondary USB error observations never qualify the
system SATA/QCOW2 image. Missing, contrary and unqualified evidence mechanically
refuses before target effects; editable qualification claims are rejected. See
`docs/write-safety/profile-admission.md`; no actual profile, production writer,
automatic custody/recovery, repair or independent RAW permission is enabled.
#0053 specifies the current partial native metadata-read JSON subset and verifies
actual emitted snapshots against exact schemas and semantic vectors. A stored
zero-denominator rational now emits invalid raw/normalized states with its exact
source range retained, matching the accepted metadata contract. See
`docs/legacy-compatibility/native-read-json.md`; no importer or broader wire/API
compatibility is inferred.
#0084 implements a standalone in-memory XMP date derivative mechanism. A no-op
borrows the entire original byte slice; replacement uses parser-bound plain-value
ranges, exact prefix/suffix complements and a target-only semantic reparse. Its
finite evidence uses authored fixtures only. See `docs/sidecars/date-preservation.md`;
declaration/full XMP conformance, source dependency admission, RAW mutation and
sidecar publication remain unqualified.
#0061 records one fixed single-file full-RAW metadata-read baseline against frozen
source, with 99 retained attempts and independent output/statistics audit. OS cache
is warm-exposed/uncontrolled; cold-device/OS and resource-policy claims remain
unrun. See `docs/performance/single-read-baseline.md`.
#0065 verifies the documented contributor procedure against exact fresh hosted
Windows, Ubuntu and macOS jobs and records sanitized CI token permissions. Those
images supply development prerequisites; bare-OS installation, hermetic builds,
staffed operations and release readiness are not qualified. See
`docs/contributing/clean-machine.md`.
#0101's physical-power fixture proposal is withdrawn by the current VM-off-only
best-effort policy. Its unrun schedule is historical; no equipment, license,
power-control or execution approval is requested. #0050/#0101 are not prerequisites
for #0078. See `docs/write-safety/power-test-policy.md`.
#0087 defines the versioned `r5-gps-owner-serial-core` catalog: 31 exact native/XMP
selectors, occurrence and protected-data rules, explicit residuals and all 29
fixture-family dispositions. Its 57 authored vectors pass; no media parsing,
removal or anonymity is implemented. See `docs/privacy/r5-catalog.md`.
#0093 measures one isolated standard-library existing-target marker replacement
sequence. All 29 native cases retain the protected original; 25 refusals preserve
the observed namespace, while weak controls expose object-binding failures.
The profile remains unsupported. See `docs/write-safety/conditional-replacement.md`;
no production replacement, source deletion or new root SDK boundary is enabled.
#0099 supplies a bounded exact-reference-write effects method with public authored
controls. Actual RAW-derived reports stay private: the revised fixture grants
permit private modification/differential analysis but deny public reports. Do not
publish even aggregate camera outcomes from those reports. See
`docs/write-safety/cr3-reference-effects.md`; no format or #0078 admission follows.
#0100 records twelve native timestamp-lifecycle cells and twelve receipt
inspections against the unchanged F869 worker, with zero observed drift under
the declared observers. This native non-reproduction does not explain the two
guest crash drifts or establish a mitigation. See
`docs/write-safety/receipt-timestamp-completion.md`; full profile gates remain.

#0057 adds a bounded in-process metadata-read request/result API using native
token arrays and caller-owned JSON transport. It shares the ordinary CLI read
workflow and retains request-local state, finite input/result bounds and explicit
transport errors. See `docs/legacy-compatibility/read-request-result.md`; serialized
request imports and persistent sessions remain separate work.
#0102 attributes frozen #0099 reference-write effects to CMT allocations, gaps and
container/track offsets. Camera-derived reports remain private; the public method
and authored controls do not enable #0078. See
`docs/write-safety/cr3-rewrite-attribution.md`.
#0103 implements a process-owned marker supervisor: actual child custody and a
completed stop-before-release history permit one narrow unpublished prune. Release,
uncertainty, incomplete saves and recreated supervisors confer no prune authority.
See `docs/write-safety/process-custody.md`; automatic durable custody and production
profile admission remain separate.
#0104 connects actual immutable native CR3 date observations to #0084's in-memory
XMP derivative. Opaque CMT2 coverage and cross-IFD companions refuse. Authored
integration evidence supplies no file publication or storage/RAW admission. See
`docs/sidecars/native-date-adapter.md`; #0085 retains its full acceptance.

#0063 adds a fixed ordinary-CLI batch-read runner and independent retained-output
audit. Camera-derived timing/outcomes remain private under their grants; public
method constants and authored controls establish no public camera baseline.
See `docs/performance/batch-read-baseline.md`; no performance defaults are selected.
#0067 supplies a proposed two-person read-only maintainer handoff exercise and
blank not-run record. Automated recipe/review checks do not appoint people or
establish staffed operations. See `docs/governance/maintainer-handoff-exercise.md`.
#0071 reconciles all 29 fixture families with current public scoped evidence and
five finite P0 assertion needs. It requests no new photos and adds no release or
JPEG-decoding gate to byte extraction. See `docs/fixture-plan/p0-assertion-gaps.md`.
#0088 adds a standalone bounded read-only coverage reporter for the named privacy
catalog. Native CMT/tag matches remain candidates where IFD namespace roles are
lost; selected supported XMP properties retain exact identity. Camera results
remain private and no privacy/removal/write certification is enabled. See
`docs/privacy/read-coverage.md`.

#0052 qualifies a finite actual read/list/extract argument matrix with authored
fixtures, exact preview-copy effects and documented native differences. It makes
no reference-executable or exhaustive compatibility claim. See
`docs/legacy-compatibility/read-argument-order.md`.
#0054 proposes one bounded RAW expression/module boundary, including alternatives
and the exact Terry decision. No proposed pure filter/data form or executable
runtime is enabled by delivery. See
`docs/legacy-compatibility/executable-extension-boundary.md`.
#0056 maps four bounded date fields to twenty supported-observation, refused and
unverified cells. ASCII read/lookup, advisory preview and source-content checks
remain distinct from calendar/zone semantics, writer admission and repair. See
`docs/legacy-compatibility/r5-date-mapping.md`.
#0058 specifies a bounded sequential metadata-read/close JSONL session, with LF
and CRLF input and canonical LF output. Schema/model vectors are not a decoder,
process runtime, real pipe/flush test or cancellation implementation. See
`docs/legacy-compatibility/read-session-framing.md`.
#0094 implements a fresh authored-marker retained-original copy with overlapping
identity holds and identical precommit recovery material for keep/no-backup requests.
Finite process-exit and refusal observations do not qualify conditional replacement,
durability, complete filesystem-property backup or fresh guarded restore. See
`docs/write-safety/original-retention.md`; no production profile or RAW writer is enabled.
#0105 adds a same-value reference-write causal control against frozen changed-date
artifacts. Public method and authored controls do not disclose new camera-derived
values, counts or outcomes; actual evidence stays private under the bound grants.
See `docs/write-safety/same-value-control.md`; shared rewrites do not prove necessity
or semantic independence, and #0078 retains its full admission requirements.
#0107 qualifies the installed Pillow/libjpeg candidate on four authored JPEG
controls. Early-EOI acceptance rejects the proposed strict entropy-validator
profile; full decoding with truncation tolerance disabled is insufficient.
See `docs/fixture-plan/jpeg-entropy-validator.md`. #0075/P0A-002 retain actual
camera validation and fixture-phase review; no production validator is enabled.
#0108 implements explicit fresh-name restoration in a recreated typed-owned marker
retention fixture. Fresh guards and authorization preserve the separately named
later-edited current target; 58 native cells and three admission refusals have
independent retained-artifact inspection. See `docs/write-safety/fresh-name-restore.md`.
This does not import external #0094 context, qualify occupied-name restoration or
enable durable authority, complete property backup, a production profile or RAW writes.
#0106 adds a separate read-only native receipt observer and nine frozen-actor
guest observations with four controlled VM-offs. Both receipt-written VM-off
cells show native last-write drift and guarded inspection refusal; one rich
inventory has a separately recorded size disagreement. Two read-only operator
continuations remain explicit. See `docs/write-safety/receipt-vmoff-properties.md`.
No cause/fix, physical truncation, merged storage configuration, namespace/receipt
acknowledgement, custody, production profile or RAW permission follows.
#0109 qualifies pinned reference CMT serialization on 32 independently authored
controls. Rebuilt storage and generated zero padding are distinguished from
preserved nonzero bytes; private frozen-camera reconciliation stays private.
See `docs/write-safety/authored-cmt-serialization.md`; this supplies no format
standard, checksum/semantic-independence proof or #0078 admission.
#0111 qualifies an installed warning-aware TurboJPEG API on seven authored
controls. Complete/exact-zero-suffix controls succeed; incomplete entropy refuses,
and separate syntax/extent policy handles unsupported inputs. See
`docs/fixture-plan/warning-aware-jpeg-validator.md`; no camera phase, production
validator or extraction prerequisite is enabled.
#0112 adds the production opt-in `read_session::run` library API over caller-owned
buffered input/output. Exact v1 framing, fresh native read execution, bounded
output and actual faulting I/O tests remain distinct from the historical model.
See `docs/legacy-compatibility/read-session-library.md`. No CLI/process entry,
OS-pipe lifecycle, deadline, queue, cache or mutation capability follows.
#0110 adds a separately selected research receipt mode that withholds context
until explicit file flush and fresh full checks, retaining original snapshots
and creator guards. Eleven native cells and two bounded VM-offs distinguish
pre-context timestamp drift from a matching checked-context observation. One
assisted sign-in introduces no read-only retry. See
`docs/write-safety/checked-receipt-context.md`; this is neither timestamp rebasing
nor a cause/fix, durable acknowledgement, custody, storage profile or RAW admission.

#0113 adds finite authored opaque CMT dependency controls and an independent
ownership witness. See `docs/write-safety/cmt-opaque-dependencies.md`; invented
dependencies are not Canon semantics or positive RAW admission.
#0114 binds checked receipt observation to an actual process-owned caller and
uses internally retained context for explicit read-only inspection. See
`docs/write-safety/checked-receipt-custody.md`; no automatic restart custody,
namespace acknowledgement or production profile follows.
#0115 adds actual native/CLI authored CMT2/CTMD ISO disagreement evidence for
P0A-003. See `docs/fixture-plan/iso-disagreement.md`; no camera phase or broad
fixture-family completion follows.
#0116 exposes the existing v1 read-session library through `imageinfo session read`
with bounded actual process/pipe tests. See
`docs/legacy-compatibility/read-session-process.md`; cancellation, failing native
input handles, non-Unicode wire paths and broader compatibility remain separate.

## Bounded queue wave — 2026-10-16

#0165 specifies exact best-effort Windows new-output acknowledgements and
noncircular restart rules using the already permitted trusted explicit caller.
No new product approval, automatic custody or production profile follows. See
`docs/write-safety/new-output-contract.md`. #0193's static boundary audit retains
unsupported existing-target replacement: expected-old identity and strict
property/stream/link exclusion remain independent gaps. Its negative result
does not complete positive replacement scopes; see
`docs/write-safety/existing-target-boundary.md`.

#0120/#0121 reconcile all 32 MAP families and 39 API headings, full LG/GAP
obligations, pinned reference option denominators and the exact current native
surface. All unmet residuals remain; inventory is not parity acceptance. See
`docs/legacy-compatibility/delivery-matrix.md` and `native-token-inventory.md`
in that same directory. #0183 adds bounded production in-memory UTF-8 XML/XMP
packet inspection with immutable identity observations, exact lexical/shape
limits and concrete edit-constraint refusals; no file publication or semantic
clearance of arbitrary unknown namespaces. See `docs/sidecars/packet-profile.md`.

#0188 specifies one catalog-bound singleton sidecar OwnerName removal and its
per-artifact effects/rights; authored contract vectors are not actual removal
or privacy certification. See `docs/privacy/xmp-owner-removal-contract.md`.
#0142 adds opt-in v2 Windows direct-process CPU/memory/logical-I/O telemetry,
bounded samples, explicit counter errors and retained failure/cancellation
records. Sampled membership is not containment; logical I/O is not device I/O,
and authored qualification selects no camera performance policy. See
`docs/performance/read-telemetry.md`. #0162's authored native/CLI subprocess
checks preserve literal date/offset/fraction strings under two TZ settings;
no instant conversion or host timezone change is claimed. See
`docs/fixture-plan/date-timezone-literals.md`.

#0166 adds the production-owned safe Windows storage facade and isolated reviewed
SDK module; #0167 executes a bounded internal new-output protocol through it.
Actual authored native execution completes the protocol, while public apply,
Committed and exact profile admission remain gated. #0195 supplies a separate
same-held-object no-replace move; it does not satisfy expected-target replacement.
See `docs/write-safety/windows-production-guards.md`, `publication-runtime.md`
and `held-existing-move.md` in that directory.
#0132 maps finite WS-002 planner/wire ownership; #0163 qualifies the aggregate
preview-marker boundary with authored files. #0184's retained-pair evidence stays
private and confers no positive publication admission. #0189 retains known
provenance findings through later incomplete inspection and refuses mutation;
#0190 removes one supported XMP OwnerName in memory with exact complement and
fresh semantic verification. Neither enables filesystem publication, RAW mutation
or a general privacy certification. See the documentation map for scoped evidence.

#0168 adds phase/object/revision-bound live acknowledgements to the actual internal
Windows protocol; positive admitted execution remains test-only. #0169 supplies
bounded explicit current-caller authority and actual owned-child stop/release
history; imported records confer no authority and restart mutation remains separate.
#0196 implements mandatory pre-effect strict existing-target property refusal;
its native inventories are not positive replacement preservation. #0186 binds
actual guarded RAW/XMP observations to an internal original-snapshot date candidate,
with authored evidence and no file publication or camera admission.
#0124 qualifies thirty-two authored preview/pair argv cases, and #0129 specifies
inert invocation/translation reports with finite token accounting and diagnostics.
#0144 supplies a frozen-source resource runner/auditor and authored method controls;
all actual camera-derived telemetry, audit dispositions and outcomes remain private.
See the documentation map for exact bounded evidence and retained gates.

## Linux new-output scope — Terry's decision, 2026-10-16

Terry selected #0177 option A: defer positive Linux new-output support from the
initial new-output milestone, which is Windows-only. Retain Linux new-output as
future scope under its full continuous byte/object/name, ordinary-owner output
and no-clobber guarantee. WSL-native and mounted Windows paths remain separately
unsupported for mutation; Linux reads are unchanged. Do not weaken the future
guarantee, invent a cooperative-writer fallback or create speculative Linux
implementation cards without a justified selected mechanism. This is a scope
decision, not a Windows profile/writer admission. See
`docs/write-safety/linux-new-output-boundary.md`.

## Default-priority correction completed — 2026-10-16

Terry's queued correction is complete: 102 non-Completed cards whose P2 came
from the mistaken default now use P3 (Normal): 98 active cards (92 Ready for Work
and six Backlog), plus four archived cards. Current details/comments were reviewed
for deliberate urgency or explicit higher-priority direction; none was found.
The shared CLI's atomic `card set-priorities` updated the full reviewed selection
together, avoiding dependency floors that kept some single-card requests at P2.
Completed history, archive/lane state and the existing P5 broader-parity hold were
preserved. Future priorities above P3 require a concrete reason under the global
default rule; this completed correction is not an ongoing instruction to reset
deliberately raised priorities.

## Subagent sidebar names

Terry requires a compact model/effort tag, then the ticket number, then a
Title Case description (2026-10-16). Preferred sidebar examples are
`S_M 124 Review`, `S_H 168 Review`, `S_M 168 Implement`, `L_L 144 Check`,
`5.6L_L 124 Docs` and `A_M 177 Design`. Put the ticket before the description
so agents working the same ticket are easy to count. For non-ticket work use a
clear scope label instead of inventing a ticket number.

The compact tag represents
`[version, only if not latest for the family][L|S|A]-[L|M|H]: `; the sidebar
underscore form above is also preferred. Family letters are L = Luna, S = Sol
and A = Astra; effort letters are L = Light (API low), M = Medium and H = High.
Omit the version for the latest family release; include it for older releases
with no separator before the family letter: 5.6 Luna Light is `5.6L-L: `,
6.1 Sol High is `S-H: ` and 6 Astra Medium is `A-M: ` at this update.
Reassess the latest-family release mapping when releases change.

When the spawn tool only accepts lowercase letters, digits and underscores,
use equivalent names with the same order: `s_m_124_review`, `s_h_168_review`,
`s_m_168_implement`, `l_l_144_check`, `5_6l_l_124_docs` or `a_m_177_design`.
Use uppercase tags and Title Case descriptions when a supported display-name
field permits them. Lowercase task-name constraints and app-controlled formatting
may prevent the exact preferred sidebar rendering. Existing agents may be renamed
only through a supported rename capability; do not claim rendering or existing
names changed without tool support.

Keep explicit model/effort spawn arguments. The compact tag already identifies
the model and effort in delegation updates: write `S_M Integration Review`
without repeating `(Sol / Medium)` after it (Terry, 2026-10-16). This supersedes
earlier guidance requiring a redundant full-word pair alongside the tag.
These examples do not authorize additional models or efforts, change per-turn
Astra approval or alter concurrency limits. Reused agents retain a prefix
matching their actual configured model and effort.

## Subagent authorization

Terry clarified the rolling implementation/review workflow on 2026-10-16:
use available slots for eligible implementation first. As an author finishes,
start a fresh independent reviewer at the permitted model/effort appropriate
to that review. Do not reserve idle reviewer pairs. The author cannot review
its own work; route findings for correction and re-review material changes
before handoff. Retain the eight-active-direct-subagent/depth-1 limits and
the parent's integration, verification, commit/push and handoff responsibilities.

Terry authorized parallel subagent work on all tickets authorized to work,
2026-10-14. Use parallel subagents where practical: separate independent
implementation, verification, documentation and review work when that helps the
authorized ticket. Terry updated the limit on 2026-10-15 to **one parent plus up to
eight direct subagents: nine total threads**, with **maximum depth 1** below the parent.
Subagents must not spawn subagents. The limit is a ceiling, not a quota; use the
number of agents the work benefits from. No separate per-ticket delegation
approval is needed. This does not authorize pulling or starting another ticket
outside the requested work. The primary owns integration, verification,
commits/pushes and the bounded ticket handoff.

Terry authorized task-based model and effort selection on 2026-10-15, superseding
the uniform Sol Medium requirement:

- GPT-6 Luna with Low effort (`gpt-6-luna`, `low`; Terry calls this Light) for
  narrow mechanical documentation, inventories and prescribed test execution.
  Keep code interpretation, safety conclusions and integration with a Sol agent.
- GPT-6.1 Sol with Medium effort (`gpt-6.1-sol`, `medium`) for ordinary
  implementation, tests and substantive documentation.
- GPT-6.1 Sol with High effort (`gpt-6.1-sol`, `high`) for difficult reasoning and
  authentication, transaction, recovery or concurrency review.
- GPT-6 Astra with Medium effort (`gpt-6-astra`, `medium`) for particularly
  difficult debugging, design or architecture problems, only after Terry explicitly
  approves using one or more Astra subagents for that turn. Ask again on each later
  turn that would use Astra; prior approval does not carry forward.

Reassess each agent's assignment each turn. The mix of models and effort levels
may vary from turn to turn with task complexity; no fixed distribution or permanent
per-agent model is required. Set model and effort explicitly when spawning. Use a
fresh context for overrides and supply scope, authority, file ownership, constraints
and handoff criteria. If an existing agent cannot be retuned, use a freshly
configured agent while respecting the eight-active-direct-subagent/depth-1 limits.

Terry chose **Standard speed** for the parent and subagents on 2026-10-15,
superseding the earlier Fast-mode requirement. Subagents inherit the root
session's service tier. Keep `service_tier = "default"` in the user Codex
configuration; do not re-enable Fast mode unless Terry requests it. The model
and reasoning defaults remain GPT-6.1 Sol with Medium effort.

## Product intent

- Terry selected #0164 option A on 2026-10-16: authorize the one selected existing
  private PreviewImage's P0A-002 bounded structural preflight and local JPEG
  completeness/usability decode, including temporary separately named decoded-pixel
  derivatives. Bind the exact private permission overlay and historical fixture
  lineage; the differential phase extension applies only to that use. Keep originals
  immutable and all pixels/results/reports restricted locally, with no uploads,
  public findings, new-media or broader mutation grant. Decode only after an
  independently reviewed authored-qualified profile supports the exact input and
  fresh identity/syntax/extent checks pass. This decision records permission only;
  #0075's technical work and actual assertion remain unrun. See
  `docs/fixture-plan/p0-assertion-gaps.md` and private
  `.local/rfw-decomposition-20261016/corpus.decoder-decision.private.json`.

- Terry selected #0157 option A on 2026-10-16: retain direct commits/pushes after
  required checks, practical agent review without independent-human claims, and
  Terry's review/acceptance of board handoffs into Completed. Do not add mandatory
  PR approvals, CODEOWNERS or branch-protection/ruleset requirements. Public
  contributors still use ordinary PRs; format/preservation verification remains
  required. See `docs/governance/review-routing-plan.md` for the accepted policy
  and historical unselected enforcement proposal.

- Terry selected #0155 option A on 2026-10-16 and authorized enabling/verifying
  private reporting for `imageinfo/imageinfo` plus one harmless synthetic report.
  Reporting is enabled and API/public-entry verified. The actual report POST was
  refused with HTTP 403 for the available administrator account; no report exists.
  Keep external submission and notification delivery explicitly unverified; never
  substitute an admin draft as proof. Terry is sole best-effort responder, with no
  backup/response deadline. No new access or personal notification changes follow.
  See `SECURITY.md` and `docs/governance/security-intake-readiness.md`.

- Terry selected #0159 option A on 2026-10-16: first distribution is a source-only,
  unsigned `v0.2.0-alpha.1` GitHub prerelease of the bounded reader, with
  `publish = false`, no binary/installer/registry/signing infrastructure and
  best-effort latest-alpha support without response/backport guarantees. Terry
  retains release authority; prepare the exact candidate and notes for approval
  before publication. Use required automated checks and agent review, honestly
  labeled; no independent human verification/backup gate or claim for this solo
  alpha. This decision does not itself authorize a tag/release or change versions.
  See `docs/governance/first-release-policy.md`.

- Terry selected #0154 option A on 2026-10-16: solo, best-effort operation, with
  Terry as project coordinator and conduct/escalation contact. Claim no human
  backup, staffed response team, response deadline or operational independence.
  Additional maintainers and independent handoff exercises remain future goals;
  Codex/subagents are assistance, not human backups. Security intake, release
  authority and review enforcement retain their separate decisions. See `GOVERNANCE.md`.

- Terry selected #0118 option A on 2026-10-16: retain the current CR3 semantic
  preservation contract and unsupported embedded-write outcome. Stop generic
  reference probes for opaque dependencies; resume positive format admission only
  with a concrete sufficient evidence source or exact semantically justified layout.
  #0119 remains contingent; #0078/#0014 stay unfulfilled. Reader/preview and
  separately qualified XMP work can continue. See `docs/write-safety/write-admission.md`.

- Design imageinfo from a clean whiteboard. Terry clarified on 2026-10-10 that
  ExifTool is a functional reference, not an architecture, API, class, or module
  template. Existing design notes are proposals, not accepted architecture.
- Choose modern engineering practices for concrete correctness, usability,
  maintainability, and performance needs. Do not add patterns, layers, frameworks,
  or extensibility mechanisms for their own sake. Do not assert that ExifTool's
  code is poor without evidence; imageinfo's design does not depend on that claim.
- Honor the principle of least surprise. Favor the chosen language's established
  idioms, standard types/libraries, familiar names, straightforward control flow,
  and small abstractions with an obvious purpose. Expert maintainers should find
  ordinary decisions obvious. Require a concrete benefit for unconventional choices;
  do not mistake novelty or elaborate patterns for engineering quality.
  Terry's explicit standard: "Boring is a compliment in this code base."
- Deliberate departures from convention are allowed when they earn their cost.
  Add a nearby comment explaining why the conventional approach was insufficient
  and the constraint/tradeoff behind the choice; link a design note for substantial
  rationale. Comments should explain decisions rather than narrate obvious code.
- Make contribution inviting to experienced developers: clear names and boundaries,
  reproducible setup/checks, discoverable decision records, and small reviewable
  changes. Do not rely on private context held by the original authors.
- Keep external data contracts distinct from internal types and code organization.
  Requirements schemas do not prescribe a custom runtime framework or force native
  values to use their JSON serialization representation internally.
- Full ExifTool feature parity is the long-term goal. Current delivery scope is
  camera RAW metadata: DNG and proprietary RAW containers, associated XMP sidecars,
  and embedded preview metadata/extraction. Consult `docs/raw-scope.md`.
- The first camera/format target is Canon EOS R5 CR3. Prioritize that milestone
  before other RAW families; see `docs/canon-eos-r5-cr3.md`.
- Terry shoots the camera's full RAW setting. Prioritize those losslessly compressed
  CR3 files for fixtures and benchmarks; track C-RAW separately as secondary coverage.
  Metadata operations preserve existing sensor bytes without recompression.
- Standalone rendered images, video, audio, documents, and archives are deferred.
  Do not expand current implementation work into them without a scope decision.
  RAW pixel development, rendering, and conversion are outside this metadata tool.
- A hierarchical CLI must provide contextual help at root, group, and leaf levels.
- Optional cascading menus must coexist with predictable noninteractive scripts.
- Distinguish requirements, proposals, observed upstream facts, and implemented
  capabilities. Never imply that proposed commands or compatibility already work.
- Treat metadata writes, unknown-data preservation, and privacy removal as separate
  capabilities that require evidence for each applicable format.

## Documentation and research

- Project license is MIT, explicitly accepted and locked by Terry on 2026-10-10.
  Preserve copyright/license notices; no mandatory visible UI credit. Do not reopen
  the project-license comparison unless Terry asks. Third-party asset provenance
  remains a separate requirement; see `docs/license-decision.md`.
- Cite primary sources and record the observation date and revision when available.
- Keep `docs/README.md` current and use stable requirement identifiers.
- Preserve the long-term parity goal while keeping current work RAW focused.
  Label broader ExifTool research and future requirements as deferred context.
- Do not copy upstream code, tag tables, fixtures, or documentation wholesale.
  Resolve license and provenance requirements before importing artifacts.
- Never commit private board snapshots, credentials, service descriptors, personal
  media, or generated local logs.

## Local board

The active board is `C:\Projects\localswim-state-store\imageinfo\imageinfo.json`,
in Terry's private state store (migration approved 2026-10-12). The ignored
`boards/imageinfo.json` is a retired migration backup; do not launch or mutate it.
Read and mutate the active board
through `localswim-cli`; use the live service for card mutations.
Terry uses the multi-project workspace UI at
`http://localhost:8810/board/imageinfo/imageinfo` (clarified 2026-10-14).
The CLI still targets the imageinfo JSON path and its individual service descriptor;
the workspace URL does not change the active board or its sole writer. Monitor
the individual imageinfo service's actual port, rather than assuming the workspace
gateway port replaces it. Reuse healthy workspace/board services; do not duplicate
them. A workspace launch must also use the official checkout and `--autopush`.
Follow the embedded
Terry workflow. Bot moves completed work to `ready_for_review`; Terry alone accepts
it into `completed`. Do not launch a duplicate service. Terry explicitly authorized
board autopush on 2026-10-12 and requires every future imageinfo service launch to
include `--autopush`; this standing instruction supersedes the earlier opt-in rule.
Always launch from the official local localswim repository at
`C:\Projects\localswim` using `uv run --frozen localswim --autopush` with that
working directory. Do not launch the installed `localswim.exe` copy. Verify the
service reports the checkout's actual build ID, rather than `unknown` (Terry's
instruction, 2026-10-13); never hard-code or spoof the displayed build.

Terry clarified lane meanings on 2026-10-11:

- `backlog`: insufficiently scoped to work, or intentionally held back by Terry.
  Record the missing scope or Terry's hold explicitly. #0012 broader ExifTool parity
  is intentionally held and stays here until Terry releases it.
- `ready_for_work`: sufficiently scoped to work. Dependencies on other Ready for
  Work tickets do not make a card Backlog; record them as relationships/prerequisites.
  Readiness is not permission to skip dependencies or restricted-action approvals.
- `in_progress`: actively being worked, or explicitly designated by Terry as the
  next resumption point. Record an overnight/resume note when work is parked here.
- `blocked`: neither Codex nor Terry can advance the ticket through work or
  decisions under our control; a specific external condition must change.
  Terry clarified this meaning on 2026-10-15. Describe that external condition
  and the change needed to unblock it. Missing implementation, research or
  qualification that we can pursue is work or a prerequisite, not a Blocked lane
  reason. Keep scoped queued work Ready for Work, or In Progress while actively
  advancing it. If Terry can advance it but Codex cannot, use Needs Terry.
- Needs Terry (`needs_terry_action` in the CLI): only Terry can advance the
  ticket. Codex cannot make further authorized progress without a specific action
  by Terry. Terry clarified this
  meaning on 2026-10-15. State the exact decision, input, approval or action
  required from Terry, and complete independent authorized work first. Merely
  having a question or unfinished work does not justify this lane.
- `ready_for_review`: the requested scope is implemented/verified and handed off,
  with committed/pushed work and explicit evidence/limitations where applicable.
- `completed`: Terry has accepted the handoff; bot does not move its own work here.

Terry clarified the queued-work disposition on 2026-10-15: if neither
Needs Terry nor `blocked` applies, the card belongs in Backlog or Ready for Work.
Use Backlog only for insufficient scope/detail or Terry's explicit hold; use
Ready for Work for sufficiently scoped work, including prerequisites we can
advance. In Progress remains for active work or Terry's designated resumption point.

When triaging, move sufficiently scoped cards out of Backlog unless Terry has
explicitly held them. Distinguish insufficient scope from unmet prerequisites;
keep descriptions, dependencies and lane state consistent with the current phase.

Terry required finer delivery increments on 2026-10-14 after repeated partial
#0022 handoffs. Every implementation handoff should finish at least one bounded
ticket into Ready for review, with its scoped acceptance verified and work pushed.
Use umbrella cards only to track complete requirements and child dependencies.
Fully scoped umbrellas remain Ready for Work; an umbrella or an unmet ticket
dependency is never, by itself, a Backlog reason. Work a specific executable child
rather than repeatedly handing off partial progress on an umbrella.
Preserve full safety gates when splitting; a completed research child never enables
its parent's production capability by implication. Review oversized open cards
for independent outcomes and clear one-handoff finish lines before starting them.

Terry requested a complete Ready for Work decomposition on 2026-10-16 after
several batches closed new children while the original queue stayed at twenty.
Use `docs/remaining-work.md` and the linked bounded cards as the remaining-work
inventory. Tracking umbrellas retain their full acceptance and stay Ready for
Work under the lane rule, but are labeled `Tracking:` and excluded from executable
work counts. Traverse their existing children instead of creating another batch
merely to fill subagents. Reuse the scoped queue before inventing new cards.

Each executable scope should finish in one turn once its explicit prerequisites
are met: one concrete outcome, bounded verification and a pushed review handoff.
This is a sizing estimate, not a guarantee about unresolved platform or format
feasibility. Preserve insufficiently specified areas and unselected alternatives
as explicit scope gaps; do not present them as fixed executable work or omit them
from the parent trace. Record any genuinely new scope delta before adding work.
A negative feasibility result does not satisfy its dependent positive capability;
rescope or seek the exact product decision rather than starting endless probes.
Ordinary engineering choices and inherited safe defaults do not need renewed
product-adoption gates. Use Needs Terry only for a genuine remaining human input,
consent/authority or explicit guarantee/policy change after independent Codex work
is complete. Do not turn proposal wording into an extra approval requirement.

Terry reiterated the lane rule on 2026-10-14: **Backlog is only for Terry's explicit
hold or insufficient detail to perform the work.** Move sufficiently scoped cards
to Ready for Work even when they depend on other Ready for Work tickets. Record
those prerequisites as relationships; do not use Backlog as a dependency queue or
as storage for organizational umbrellas. Keep the missing scope or Terry's hold
explicit on every remaining Backlog card.

Terry's triage precedence, clarified 2026-10-14: **every In progress card ranks
ahead of every Ready for Work card**, regardless of blocking depth, priority or
ticket number. Work the existing In progress cards before pulling another card
from Ready for Work. Apply the configured blocking-depth/priority/ticket ordering
within each lane. Query the lanes separately if a combined CLI result interleaves
them; its cross-lane ordering does not override this instruction.

Terry requires the JSON board-write monitor to be running whenever this board's
localswim service is running. At every startup or resume, verify both the service
and monitor, and target the monitor at the active Codex thread. Start or retarget
the shared monitor using the procedure in `docs/local-board.md`; use imageinfo's
own status, target and lock paths so another board's monitor is never displaced.
Verify its running state, live process and current thread target before continuing
board work. Keep it running for the service's lifetime, including between tasks.
All project board services, CLI operations and monitors delegate to the shared
implementation in `C:\Projects\localswim`. Do not maintain local server, CLI,
monitor or actor-filtering copies/forks. Thin launchers may supply project paths,
ports and targets; common fixes belong in the shared package.
Use the official `localswim-monitor` command and optional `monitor` extra from
`C:\Projects\localswim`; do not keep project-local copies. Preserve the original
thread target during upgrades. Use cooperative `--reload` only for a monitor
reporting support; migrate legacy watchers through graceful board stop/restart,
without PID termination. For a queued alert, read sanitized activity metadata
first and stop when a nonempty result is entirely automation-authored. Never
compare activity-event counts with filesystem write counts. Human, mixed,
unknown, empty, malformed and failed results still require attention.
This monitor is local operational tooling, not an imageinfo implementation choice.

Write card descriptions and comments for easy human scanning. Terry explicitly
requested more line breaks on 2026-10-10: use short paragraphs separated by blank
lines, and compact bullets for parallel items or acceptance criteria. Separate
context, findings, verification, and next steps when present. Avoid dense blocks
that combine the entire update into one paragraph. Preserve actual newlines when
passing text through the CLI; prefer `--detail-file` for substantial descriptions.

## Verification and publishing

For documentation changes, check internal links, consistency of proposed command
examples, requirement coverage, source attribution, and `git diff --check`.
For Rust changes, run `cargo fmt --all --check`,
`cargo clippy --locked --all-targets -- -D warnings`, `cargo test --locked`, and
`cargo build --locked --release`. Run `python scripts/check_docs.py` for changed
documentation/JSON. Use the pinned toolchain and root Cargo.lock; review exact
dependency changes and retain required notices. See `docs/foundation/README.md`.

Terry's standing instruction dated 2026-09-12 authorizes commits and pushes of
in-scope work after appropriate verification, including direct pushes to main.
Preserve unrelated changes and do not ask for a new per-commit approval.

Push after every commit, as Terry explicitly required on 2026-10-10. Each commit
must be followed by a push to the configured remote before making another commit
or handing off. Verify the push result. If it fails, report the failure and resolve
it without force-pushing or discarding unrelated work; do not leave the failure
unmentioned or describe the handoff as fully published.
