# Source-reader alpha candidate preparation

#0160 prepares **v0.2.0-alpha.1**, under the [adopted solo policy](first-release-policy.md).
The distribution is unsigned source obtained from a pinned public Git commit or
the eventual GitHub tag archives. Terry retains authority over the exact candidate
and notes. This preparation creates no tag, release, upload or registry package.

The [candidate notes](source-reader-alpha-notes.md) state the finite capability
denominator. Build only the root package. Tracked `experiments/` source remains
research even when present in a full repository archive. Root Windows storage
implementation is internal and does not expose a production writer or admitted
storage profile.

## Freeze and exact-source checks

Freeze all candidate source, notes, root version `0.2.0-alpha.1`, lockfiles,
licenses and toolchain in one pushed commit. Use its full object ID rather than
a moving branch name. The GitHub `Rust foundation` workflow must succeed for that
exact commit on `windows-2025`, `ubuntu-24.04` and `macos-15`; retain the actual
job image/architecture/tool versions from its logs. The [contributor procedure](../contributing/clean-machine.md)
and committed workflow define the required checks. They include root formatting,
lints, tests, release-profile build, authored command/schema checks and public
documentation checks. Earlier passing runs do not qualify a later candidate.

The root test suite supplies authored read/list/extract/date-preview/pair/session
and refusal/effect checks. The workflow also checks contextual help, text/JSON
version, schema/error routing and inert translation. Tests establish their named
finite cases; they do not establish broad camera compatibility, cancellation or
filesystem durability. Keep failed runs and corrections identifiable.

After CI completion, capture its sanitized machine-readable run record:

```powershell
gh run view RUN_ID --repo imageinfo/imageinfo --json headSha,status,conclusion,workflowName,url,databaseId,jobs > .local/candidate-ci.json
python scripts/prepare_reader_release.py --commit FULL_SOURCE_COMMIT --ci-json .local/candidate-ci.json --output .local/reader-alpha-candidate
python scripts/test_prepare_reader_release.py
```

Use a UTF-8 CI JSON file. The assembler rejects another source commit, an
unsuccessful/incomplete workflow or a missing/duplicate/failed matrix job.
Without `--ci-json`, it can prepare an intermediate local archive, but records
missing CI explicitly and cannot establish candidate readiness.

## Reviewable local payload

The assembler reads Git objects at the selected commit and creates a local tar,
an unpacked `source/` directory and an external `candidate.json`. The archive
contains every ordinary tracked file, with Git metadata and ignored/untracked
state excluded. Links, submodules, path escapes, build/private-state directories,
camera RAWs and packaged Windows executables are refused. Every archive file is
compared with its exact Git blob before unpacking; the external manifest records
each file's SHA-256, full commit/tree, actual archive size/hash, root locked
packages, project/license/toolchain hashes, reviewed package checksum identities,
all retained license hashes and included research manifests. Root dependency
sources are fetched by Cargo, not bundled.

This is a local rehearsal archive, **not an upload asset**. GitHub-generated
compression bytes may differ; eventual publication verifies extracted paths and
file bytes against the frozen tree. The external manifest avoids a commit/hash
self-reference: it describes immutable source and is retained as review evidence,
not inserted into the candidate source it identifies.

Inspect the full file list for unintended/private or uncleared content. Check
[LICENSE](../../LICENSE), [third-party notices](../../THIRD_PARTY_NOTICES.md),
the exact [dependency inventory](../foundation/dependencies.json),
[provenance review rules](../provenance/review-workflow.md), tracked research and
fixture grants. Hash agreement and filename filters are checks, not privacy or
rights clearance. Private reports, board state, credentials and camera data must
never be added to the source candidate.

Build from the separately unpacked tree, using the committed Rust toolchain and
root lockfile:

```powershell
cd .local/reader-alpha-candidate/source
cargo build --locked --release
```

Record the command, result, environment, compiler/linker and exact lock/toolchain
hashes in the local rehearsal evidence. Cargo may create fresh ignored build
files; compare the extracted source before the build. No executable-byte
reproducibility claim is made. The recipe requires Git, Python 3.11+ for assembly,
Rust and documented native prerequisites; it does not promise offline bootstrap.

## Review, correction and authority

Complete the [rehearsal record](first-release-rehearsal.template.md) against this
exact source and payload. Record actual automated results, independent agent
artifact/claim review, access/security disposition and remaining discrepancies.
Multiple agents are not independent human verification. No backup operator is
claimed or required for the accepted solo alpha.

Walk through the documented correction path: identify a bad version by full
commit and observed behavior; preserve history, describe the bounded defect,
prepare a corrected `0.2.0-alpha.2` with fresh checks and notes, and seek Terry's
exact publication decision. Do not move an existing published tag or replace
bytes under its identity. A hypothetical exercise changes no public artifact.

The security route is [solo best effort](security-intake-readiness.md): private
reporting is configuration-verified, while external submission/delivery remains
unverified. The [accepted operating scope](../../GOVERNANCE.md) retains the solo
continuity limit; the historical [owner-access exercise](owner-access-continuity.md)
is not a new two-person gate for this alpha. Record actual authorized access
without publishing private recovery material. Unsigned checksums detect differences relative to a
trusted value; they do not independently authenticate a compromised GitHub
account/channel.

Candidate preparation is complete only with exact-source three-OS CI, actual
unpacked build, contents/notices review and agent review recorded. Terry's exact
candidate/notes approval and actual public tag/archive verification belong to
#0161. They are separate from source commit/push approval.
