# imageinfo project guidance

This repository is in its requirements and research phase. Keep work language
agnostic. Do not choose an implementation language, framework, dependency stack,
or package layout until Terry explicitly advances that decision.

## Product intent

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

Write card descriptions and comments for easy human scanning. Terry explicitly
requested more line breaks on 2026-10-10: use short paragraphs separated by blank
lines, and compact bullets for parallel items or acceptance criteria. Separate
context, findings, verification, and next steps when present. Avoid dense blocks
that combine the entire update into one paragraph. Preserve actual newlines when
passing text through the CLI; prefer `--detail-file` for substantial descriptions.

## Verification and publishing

For documentation changes, check internal links, consistency of proposed command
examples, requirement coverage, source attribution, and `git diff --check`.
There is no software test/build gate until an implementation exists.

Terry's standing instruction dated 2026-09-12 authorizes commits and pushes of
in-scope work after appropriate verification, including direct pushes to main.
Preserve unrelated changes and do not ask for a new per-commit approval.
