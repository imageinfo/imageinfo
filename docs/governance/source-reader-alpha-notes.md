# v0.2.0-alpha.1 source-reader candidate notes

**Candidate notes for review; not a published release.** The
[candidate preparation record](source-reader-candidate.md) binds the eventual
full source commit, root Cargo.lock/toolchain identity, archive file inventory,
exact hosted Windows/Ubuntu/macOS checks and agent review. The source version is
`0.2.0-alpha.1`; the intended tag is `v0.2.0-alpha.1`. No tag or publication is
created by preparing these notes. Terry must approve the exact candidate and
notes before the separate publication step.

This is an unsigned, source-only alpha. Build the root package using the
[contributor instructions](../contributing/clean-machine.md) and committed
Rust toolchain/lockfile. No prebuilt binaries, installer, bundled dependencies,
container, signature or registry publication is supplied. MIT project terms
and [third-party notices](../../THIRD_PARTY_NOTICES.md) accompany the source.

## Implemented scope

- Read the bounded native EOS R5 full RAW CR3 metadata and stored-preview
  declarations in the [reader denominator](../reader/README.md). Unknown/opaque
  coverage and unsupported profiles remain explicit; this is not ExifTool parity
  or support for every camera, firmware, lens and mode.
- List and extract exact stored-preview bytes. Extraction writes a new file and
  requires a trusted local output directory and hard-link no-clobber publication.
  It refuses existing destinations and has no overwrite fallback. It does not
  decode, render or certify JPEG entropy, or recompress the sensor RAW.
- Compute an advisory [DateTimeOriginal preview](../reader/date-preview.md),
  validate nonexecuting saved intent and revalidate bounded source content.
  No matching preview/plan/hash authorizes apply or RAW mutation.
- Observe selected RAW/XMP associations through the bounded
  [pairing surface](../sidecars/pairing.md). Explicit `--sidecar` remains available;
  `sidecar pair RAW --infer-same-stem` opts into finite ASCII case-insensitive
  CR3/XMP matching in the same parent and refuses conflicts, aliases and missing
  matches. Association does not validate contents,
  create sidecars, establish synchronization or retain a continuing guard.
- Run the bounded sequential v1 [JSONL metadata-read session](../legacy-compatibility/read-session-process.md),
  including fresh request state, framing/size limits and explicit outcomes.
  Cancellation, queue/server semantics and persistent recovery remain outside
  this release promise.
- Use current Rust library modules, including bounded
  [request/result transport](../legacy-compatibility/read-request-result.md) and
  [in-memory XML/XMP packet inspection](../sidecars/packet-profile.md).
  These APIs are alpha interfaces, without a stable ABI promise. Packet parsing
  is not sidecar filesystem publication or semantic clearance of unknown XML.
- Use contextual help, text/JSON version and the implemented finite
  [native token surface](../legacy-compatibility/native-token-inventory.md).
  Inert translation validates data and never executes an extension/module.

The actual [native JSON subset](../legacy-compatibility/native-read-json.md),
[error routing](../legacy-compatibility/native-json-errors.md) and session v1
framing retain their own schema/contracts. Partial evidence is not a broader
wire/API compatibility claim. Report unsupported tokens rather than assuming
reference-tool option compatibility.

## Limits and support

Reading may update filesystem access times. Preview extraction has documented
partial/uncertain outcomes, and process termination may leave a temporary file.
Exit status alone does not prove JSONL delivery: the bounded
[native standard-handle observations](../legacy-compatibility/native-session-handles.md)
include normalized EOF and zero-status/no-output cases.
Source length/mtime checks are not continuous adversarial guards. Hostile namespace
races, directory persistence, remote filesystem guarantees and physical power
survival are not certified. The project uses
[best-effort VM-off testing](../write-safety/power-test-policy.md).

No metadata/RAW writer, public apply, admitted production storage profile,
privacy-removal certification, automatic repair/recovery, general sidecar
publication or executable extension runtime is enabled. Tracked `experiments/`
crates are research and are not shipped production commands. C-RAW, DPRAW,
burst, other cameras and unknown declarations retain their documented refusals.

Only the latest published alpha receives best-effort triage and fixes; no
backports, response deadline or LTS support is promised. Compatible corrections
use `0.2.0-alpha.2` and later; intentional incompatible interface/safety changes
start a new minor alpha line and explain migration. Schema revisions follow
their own contracts. No previous published alpha is displaced by this unpublished
candidate.

Report public bugs through [project issues](https://github.com/imageinfo/imageinfo/issues)
with version/full commit, OS/architecture, command, expected/actual status and a
minimal lawful reproduction; personal photos are not required. Security reports
follow [SECURITY.md](../../SECURITY.md). The solo private-reporting configuration
is verified, but external report submission/delivery is unverified. There is no
claimed backup operator or independent human verification. Unsigned source and
checksums rely on the trusted GitHub channel and do not authenticate a compromised
account. See the [accepted support/authority policy](first-release-policy.md).
