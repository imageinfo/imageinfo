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
#0022 is split into #0028–0031. #0028's Rust worker/inspector is qualification
research; its late-stage counterexample fails the enablement gate. Read-only
inspection grants no repair authority. See `docs/write-safety/recovery-inspection.md`.

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

The machine-local board is `boards/imageinfo.json` (ignored). Read and mutate it
through `localswim-cli`; use the live service for card mutations. Follow the embedded
Terry workflow. Bot moves completed work to `ready_for_review`; Terry alone accepts
it into `completed`. Do not launch a duplicate service or enable board autopush
without an explicit request.

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
