# EOS R5 CR3 fixture and parity plan

Status: **proposed plan for review**, revision `2026-10-10.1`, card **#0005**.
The plan is language-independent and starts with Terry's EOS R5 **full RAW** files.
C-RAW and Dual Pixel RAW remain secondary. This card defines experiments; it does
not collect a camera corpus, install an oracle, implement a harness, or claim parity.
Subsequent #0013 [reference characterization](../corpus-baseline/README.md) has now
acquired private fixtures and reference instances; the published examples below
remain historical, synthetic and explicitly planned/not-run.

## Review map

- [Current P0 assertion gaps](p0-assertion-gaps.md): #0071's versioned reconciliation
  of the historical family plan with current scoped evidence and five targeted
  next assertions; no new acquisition or capability permission.
- [Authored JPEG decoder qualification](jpeg-entropy-validator.md): #0107's
  installed candidate fails the proposed strict entropy profile on an authored
  early-EOI control. P0A-002 camera validation remains open on #0075.
- [Warning-aware JPEG qualification](warning-aware-jpeg-validator.md): #0111's
  installed warning-enforcing API passes its finite authored profile; actual
  camera/phase qualification remains open on #0075.
- [Case plan](case-plan.v1.json): 29 prioritized case families, their needed fixtures,
  assertions, and links to all 49 current capability rows.
- [Evidence schema](evidence.schema.json): fixture, oracle-profile, and experiment records.
- [Oracle profile](oracle-profile.v1.json): pinned source baseline and controlled
  extraction recipes; explicitly **planned**, with no executable identity yet.
- [Comparison policy](comparison-policy.md): occurrence/value matching and result rules.
- [Example manifest](examples/fixture.synthetic.json), [derived manifest](examples/fixture-derived.synthetic.json),
  and [not-run experiment](examples/experiment-not-run.synthetic.json).
- [Validation record](validation.md): checks of these artifacts and their boundaries.

The [metadata contract](../metadata-model/README.md) supplies the comparison model.
The [compatibility requirements](../compatibility-and-validation.md) supply the wider
evidence requirements. The future code should use conventional test tooling in the
chosen language; these records do not prescribe a custom testing framework.

## What constitutes evidence

Keep three things distinct:

1. **A case plan** says which behavior needs evidence.
2. **A fixture manifest** identifies admitted bytes, origin, permissions, privacy,
   capture observations, and any derivation.
3. **An experiment record** identifies what actually ran, where, with which exact
   tools/options, what it captured, and how the result was assessed.

A planned recipe is not an executed command. A reference-only observation is not an
imageinfo test. A matching human report is not proof of preserved sensor bytes.
The records make those distinctions explicit rather than relying on a filename or
a checkbox labeled “passed.”

Hashes and lengths in the supplied examples describe actual, project-authored
**synthetic JSON** artifacts. Their offsets, camera labels, and preview labels are
invented model data. They are not CR3 fixtures and cannot establish camera support.
The derived example intentionally introduces a zero denominator, with a reproducible
recipe and parent hash. No private or third-party media was imported.

## Admission and storage

The [artifact provenance policy](../provenance/README.md) and
[review workflow](../provenance/review-workflow.md) now specify the evidence behind
rights/privacy decisions, derived lineage and release obligations. Link their
scoped review IDs through the existing rights evidence field; this does not change
fixture schema version 1 or admit the illustrative examples for experiments.

Use this sequence before a real fixture becomes runnable:

1. **Register and quarantine.** Compute a SHA-256 over the exact received bytes;
   record length, creator/origin, acquisition date, declared camera/mode, and initial
   restrictions. Preserve the received original unchanged.
2. **Review rights.** Record permission to analyze, make derivatives, and redistribute
   separately, with evidence. Public download access is not redistribution permission.
   The project's MIT license does not grant rights to someone else's photos.
3. **Review privacy.** Examine visible image content, embedded previews, metadata,
   serial/owner/location fields, filenames, and accompanying documents as applicable.
   Mark anything uninspectable. Keep restricted media and private provenance outside
   the public source tree.
4. **Authorize characterization.** After rights/privacy review, initially admit
   the bytes for reference-characterization only when identity still needs discovery.
   Record observed format/camera/mode/firmware separately from the
   supplier's declaration, with reference-artifact links. A filename or mutable Model
   field alone is not sufficient mode/variant evidence.
5. **Admit a precise use.** Expand `allowedPhases` to differential testing only
   after the case's required media/variant evidence is established. An admitted
   fixture needs approved analysis rights and a
   completed privacy decision. Public storage additionally requires redistribution
   permission and privacy clearance. Write experiments need derivative permission.
6. **Create derivatives deliberately.** Record parent ID/hash, recipe hash, tool/driver
   identities when used, and what features changed. Re-review rights/privacy for the
   derivative; sanitizing a field can remove the behavior the test was meant to cover.

`example-only` is reserved for illustrative manifests. `quarantined` means the
fixture is not eligible for normal test runs. `admitted` permits only its documented
uses/access level. Restricted admitted fixtures may be tested by authorized maintainers
without becoming redistributable. Every report retains those access restrictions.

Use trusted, configured artifact roots. One ordinary local arrangement is
`.local/corpus`, `.local/runs`, and `.local/tools`, already covered by the project's
ignore rule. Artifact paths are relative to a declared root, not arbitrary absolute
paths. Resolve and confine paths before access, including symlinks. Reading a
manifest must not itself fetch a URL or execute a derivation recipe.

The public examples under `docs/fixture-plan/examples` are reviewed documentation
data. They do not authorize placing personal media in the public repository.
Storage/binary-distribution choices for a future public corpus remain separate from
the implementation language and are not selected here.

## Fixture priorities

Start with a small, deliberate set of owned or explicitly permitted full RAW
captures. Select variations needed by P0 read cases; do not request an entire
personal archive. Record exactly what each file contains and add files when a
specific assertion lacks coverage. A fixed photo count is not a substitute for
coverage, and one passing R5 file cannot establish every firmware/layout variant.

The original case plan retains `acquisitionStatus: not-collected` as its planning
baseline. Actual private manifests and case-linked runs now exist under #0013;
consult the [corpus report](../corpus-baseline/README.md) for their narrow coverage.
Neither those observations nor the illustrative records complete whole case families.
A family may require several fixtures and several concrete experiments. The full
JSON records fixture classes, needs, assertions, CAP references, and MDL rules.

| Case | Priority | Stage | Focus |
| --- | --- | --- | --- |
| FXP-001 | P0 | read | Full RAW baseline and recognition |
| FXP-002 | P1 | read | Camera and capture variation |
| FXP-003 | P0 | read | CMT and CTMD duplicates |
| FXP-004 | P0 | read | Exact values and unknown fields |
| FXP-005 | P0 | read | Timestamp and timezone behavior |
| FXP-006 | P1 | read | GPS presence and absence |
| FXP-007 | P0 | read | All observed preview resources |
| FXP-008 | P0 | read | Embedded XMP and sidecar conflict |
| FXP-009 | P0 | read | XMP typed structures and encodings |
| FXP-010 | P0 | adversarial | Corrupt container bounds and references |
| FXP-011 | P0 | adversarial | Out-of-scope and ambiguous input |
| FXP-012 | P0 | adversarial | Resource limits and cancellation |
| FXP-013 | P0 | platform | Paths, streams and platform boundaries |
| FXP-014 | P0 | read | Reports and mixed batch failures |
| FXP-015 | P2 | automation | Request framing and state isolation |
| FXP-016 | P0 | sidecar-write | Sidecar creation and edits |
| FXP-017 | P1 | sidecar-write | Copy, mapping and import |
| FXP-018 | P1 | embedded-write | Embedded descriptive EXIF operations |
| FXP-019 | P1 | embedded-write | Embedded GPS operations |
| FXP-020 | P1 | embedded-write | Embedded XMP operations |
| FXP-021 | P1 | embedded-write | Maker-note edits and known refusals |
| FXP-022 | P0 | embedded-write | Preservation and independent usability |
| FXP-023 | P0 | embedded-write | Mutation faults and stale sources |
| FXP-024 | P1 | workflow | Privacy inspection and selective removal |
| FXP-025 | P1 | workflow | Paired file organization |
| FXP-026 | P1 | workflow | Date and GPS workflows |
| FXP-027 | P2 | secondary | C-RAW secondary coverage |
| FXP-028 | P2 | secondary | Dual Pixel RAW secondary preservation |
| FXP-029 | P0 | admission | Admission, licensing and privacy controls |

Read admission/identity comes first, followed by the read/preview/sidecar evidence
needed for the first useful slice. Embedded-write rows are gated by the
[transaction/preservation contract](../write-safety/README.md) and independent validators. Secondary variants
never inherit results from full RAW and do not gate its first read milestone.

Synthetic model cases test serialization/interpretation boundaries. Generated
binary fragments test bounded recognition/error paths. Neither replaces actual
camera originals for valid-file behavior. A corrupted derivative is labeled as
such and retains its lineage; it does not overwrite its parent.

## Reference baseline and execution recipe

Use the already researched ExifTool source **13.59** at commit
[2200871d9cef988051d2a99d67df3bda6cbb30a8](https://github.com/exiftool/exiftool/commit/2200871d9cef988051d2a99d67df3bda6cbb30a8).
This is a deliberate baseline, not a newest-release claim. Before reference experiments:

- Acquire the matching official distribution/source and record the origin and archive
  hash. Produce a manifest of the actual executed distribution files.
- Record the executable/launcher, interpreter and optional runtime components,
  capabilities, custom configuration, and observation-driver identities. A launcher
  hash alone does not identify the library code it loads.
- Confirm the reported version. If it differs, fail preflight or explicitly revise
  the baseline and its source review; do not silently accept a moving installation.
- Use a controlled working directory and allowlisted environment. Disable default
  user configuration and unreviewed extensions. Never dump secrets from the full
  inherited environment into a public record.

The oracle profile supplies argument **arrays**, preserving the empty configuration
argument and filename boundaries. Execute arrays through the eventual runner without
shell interpolation. `-config` must precede other arguments; an empty configuration
name disables the default configuration. JSON extraction preserves XMP structures
and includes duplicate-instance/location groups; family-5/6 details require the
recorded SavePath/SaveFormat options. [Pinned application manual](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/exiftool_pod.html)

The converted-value pass uses `-n`; the display pass does not. Neither pass alone
proves exact stored bytes or original rationals. The raw/rational recipe requires
a reviewed, hashed reference-specific API driver before those cases run. That
adapter's use of ExifTool's API is a test boundary, not the application's architecture.
[Reference value API](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/lib/Image/ExifTool.pod)

Resolve a binary resource's exact instance before extracting it. Capture stdout as
bytes directly; do not rely on shell text redirection or concatenate multiple
ambiguous resources. Keep original stdout/stderr even when adapters also produce
canonical observations. API drivers must demonstrate configuration isolation too.

The reference profile remains `planned`; its `tool` is null. Acquiring and running
the baseline is future work, not a condition silently claimed satisfied by this plan.

## Experiment procedure

For each concrete case/fixture/platform combination:

Record whether the concrete operation is a read, mutation, or expected refusal.
A successful refusal test requires unchanged inputs; it does not pretend to be a
successful mutation or require a writer to exist.

1. **Check prerequisites.** Verify admission and permitted operations, fixture hashes,
   recipe/case revisions, reference readiness, driver/mapping identities, and required
   independent validators. Missing prerequisites yield not-run with a reason.
2. **Prepare isolated copies.** Give reference and candidate fresh clones of the
   same immutable input, with independent destinations. Record all initial hashes.
   No test may overwrite the corpus original.
3. **Record the environment.** Capture OS/build, architecture, filesystem, locale,
   effective timezone, controlled variables, working-directory token and resource
   limits. Include an environment probe in cases whose result depends on those settings.
4. **Run and capture.** Record exact arguments, input channel, start/end times,
   termination, raw stdout/stderr, resulting file/resource artifacts and hashes.
   Timeout and launch failure are distinct from a tool's exit code.
   A missing/unreadable working copy after failure is an explicit state with a null
   hash, not a fabricated checksum. A lost stdout/stderr capture is null with a
   recorded capture issue and makes the experiment invalid.
5. **Build canonical observations.** Use versioned adapters and the metadata contract.
   Keep source identity, duplicates, types, state, precision, coverage and diagnostics.
   Adapter/correspondence failure cannot be hidden as missing metadata.
6. **Evaluate the named assertions.** Apply the hashed comparison policy. For mutations,
   include independent structure, payload, interpretation and usability evidence,
   plus failure/recovery assertions from #0006.
   Independent validator records name their own tool/runtime identity, environment,
   arguments, exact input artifacts, report, termination, linked checks and reason
   they are independent of the writer. A report label alone is insufficient.
7. **Classify and retain.** Store pass/fail/unsupported/accepted-difference/not-run/
   invalid-experiment, or reference-observed for characterization. Keep all relevant
   artifacts and restrictions. A failure is not repaired by replacing its expected
   output after the run.

Reference characterization can proceed before imageinfo exists, but its record
cannot claim imageinfo passed. The example experiment is explicitly not-run and
contains no invented executable fingerprints or successful results.

## Platform and adversarial expectations

| Dimension | Required treatment |
| --- | --- |
| Windows, macOS, Linux | Run shared read/model cases on each declared release platform before advertising it; record exact versions and architecture. Architecture support is specified before release, not inferred from this machine. |
| Timezone | Run UTC and a non-UTC/DST case such as America/New_York; prove effective behavior. Use isolated process/test environments rather than changing the user's system timezone. |
| Locale/encoding | Keep a deterministic baseline and add Unicode/path/text-encoding cases. A locale label alone does not prove a runtime used it. |
| Filesystem | Separate byte preservation from names, timestamps, permissions, links and platform-specific attributes. Case-only/newline/long-path tests have platform-specific expectations. |
| Streams/output | Test nonseekable input, partial reads, broken pipes, binary stdout, mixed batch failures and request framing. |
| Malformed inputs | Use owned deterministic fragments/derivatives with bounded seeds/recipes; test lengths, offsets, cycles, nesting, invalid text and resource limits. |
| Fault injection | Bound each injection and assert original/output/backup states. Do not rely on timing races as the only way to reproduce an interruption. |
| Performance | Record actual full RAW sizes and read/write volume; no recompression to make benchmarks look better. The performance protocol is specified under #0008; numeric budgets require actual measurement on #0016. |

An unsupported platform operation stays visible; it is not a pass for the corresponding
feature. A valid refusal test may pass when its expected behavior is refusal.
Do not silently omit a platform from a stated support matrix.

## Independence and acceptance

For embedded-write claims, a second read by the same implementation is insufficient.
Use independent structure/reference inspection and a separately identified RAW
reader/decoder on representative variants, as specified by the preservation contract.
Rendering in the test pipeline does not add RAW-development features to imageinfo.

Every advertised capability cell must link to its admitted fixtures and recorded
experiments. No unexplained differences, missing required checks, or known corruption
may be hidden by an aggregate pass count. Keep accepted differences scoped and
version-bound, and publish limitations. The [comparison policy](comparison-policy.md)
defines the precise verdict rules.

## Handoff and remaining work

This card specifies the fixture/provenance/evidence contract. It leaves actual
acquisition, executable/tool hashes, camera observations and runtime parity open.
The examples demonstrate record integrity, not operational readiness.

The [write-safety contract](../write-safety/README.md),
[CLI walkthroughs](../cli-walkthroughs/README.md),
[compatibility recommendation](../legacy-compatibility/README.md),
[performance protocol](../performance/README.md) and
[artifact provenance policy](../provenance/README.md) now supply the related
requirements and review procedures. The initial requirements-card deliverables
are recorded through #0010; they do not establish runtime capability.

The next evidence-work candidate is #0013 corpus-baseline, after policy review and
lawful input selection. Actual writer/storage proofs remain #0014, compatibility
gaps #0015, and benchmarks/numeric targets #0016. MIT remains locked.

**#0013, corpus-baseline**, preserves the separate acquisition/reference-observation
work in backlog until concrete lawful sources and scoped review are ready.
GAP-001, GAP-005, GAP-007, GAP-008 and initial asset-admission GAP-011 remain open
under that follow-up.

The schema and case plan can be implemented with ordinary test tools after a
language is selected. Any deliberately unconventional harness choice should explain
the constraint and tradeoff near the code, just like the application.

## Experiment record version 2

The #0013 acquired-reference records use `schemaVersion: 2`. External-tool runs
may explicitly leave `memoryBytes`, `maxDecodedBytes`, `maxDepth` or `maxRecords`
null, with a nonempty, matching `limits.unconfiguredReasons` entry for each.
A configured field must not have an unconfigured reason. The positive wall-time
limit remains mandatory. Version 1 still requires configured values and forbids
these reasons, including in independent-run environments. This extension records
missing enforcement honestly; it does not waive any case-specific resource gate.
Fixture/oracle schemas and historical examples remain version 1. See the
[validation](../corpus-baseline/validation.md).
