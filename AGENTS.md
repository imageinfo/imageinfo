# imageinfo project guidance

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
is enabled; #0044 retains separate guest qualification and #0022 remains open.

## Product intent

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
- `blocked`: started work cannot progress because of an actual blocking condition.
  Describe the condition and the action/state change needed to unblock it. Do not
  use this merely for an unstarted scoped card with known ticket dependencies.
- `needs_terry`: a specific decision, missing input or approval from Terry is needed.
  State the concrete question and complete independent authorized work first.
- `ready_for_review`: the requested scope is implemented/verified and handed off,
  with committed/pushed work and explicit evidence/limitations where applicable.
- `completed`: Terry has accepted the handoff; bot does not move its own work here.

When triaging, move sufficiently scoped cards out of Backlog unless Terry has
explicitly held them. Distinguish insufficient scope from unmet prerequisites;
keep descriptions, dependencies and lane state consistent with the current phase.

Terry required finer delivery increments on 2026-10-14 after repeated partial
#0022 handoffs. Every implementation handoff should finish at least one bounded
ticket into Ready for review, with its scoped acceptance verified and work pushed.
Use umbrella cards only to track the complete requirements and child dependencies;
park those umbrellas in Backlog with an explicit organizational note. Work a
specific child rather than repeatedly handing off partial progress on an umbrella.
Preserve full safety gates when splitting; a completed research child never enables
its parent's production capability by implication. Review oversized open cards
for independent outcomes and clear one-handoff finish lines before starting them.

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
