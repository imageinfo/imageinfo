# First new-output preservation evidence

Card **#0021**, observed **2026-10-11**. Terry selected new CR3 outputs first and
authorized splitting #0014. This handoff proves a narrow **private candidate**
operation. The parent safety card remains open; production metadata writes,
supported publication profiles, GAP-004 and GAP-009 remain unverified/open.

## Declared operation

The [standalone Rust experiment](../../experiments/0021-cr3-candidate/README.md)
uses the accepted reader to select one existing CMT2 EXIF tag 0x9003,
`DateTimeOriginal`, with a 20-byte ASCII allocation. It applies one fixed invented
date string, without relocation, insertion, deletion or sensor recompression.
Decoded-field overlap, ambiguous/missing occurrences, unsupported reader layouts,
over-size inputs and existing staging names refuse before creating a candidate.

Every actual candidate is reread. All file bytes outside that value allocation are
compared with the held original handle; the exact replacement bytes, unchanged file
length, occurrence spans/other values and all three declared preview extents are
checked. This stronger byte comparison covers stored sensor samples, CFA/calibration
bytes, offsets, preview bytes, opaque blocks and trailers **outside the changed span**.
It does not infer the semantics of an unknown pointer into that span, validate an
unknown checksum/signature, or establish that a date change preserves authenticity.

The original offset/subsecond and all other date occurrences remain unchanged.
Date copies may disagree intentionally. Calendar/timezone conversion, linked-date
policy and arbitrary date input are outside this fixed-value experiment.
The satisfied-edit test creates no research artifact; production new-output
requests must separately account for the effect of creating a destination name,
even when the source value already matches. That behavior remains #0023.

## Actual admitted-media results

- Eight privately admitted EOS R5 full RAW files produced eight validated candidates.
- **415,430,672 bytes** outside the eight planned allocations compared equal;
  every changed byte was inside its intended 20-byte span. No structure moved.
- Pinned ExifTool 13.59 independently observed the intended value and unchanged
  selected other time/mode fields. It read the generated candidates; it did not
  perform an equivalent reference mutation.
- Independent LibRaw 0.22.2 identification and unprocessed Bayer unpack ran on
  each original clone and candidate: **all eight decoded PGM pairs matched** in
  complete bytes/hash, dimensions and validated output size. Selected camera,
  dimensions, CFA/filter and white-balance observations matched where reported.
- Eight destination collisions refused without changing existing candidate bytes.
  Eight satisfied repeat edits created no candidate. Original hashes/mtimes stayed
  unchanged; every tool invocation also checked its actual input hash before/after.
- Seventy-two invocations were retained: 24 native candidate/refusal/no-op,
  16 reference reads, and 32 independent identifier/decoder calls.

The RAW unpack test includes masked pixels and avoids autoscaling/gamma. It is an
independent decoder/usability check, not proprietary Canon rendering, a second
independent metadata writer, or an authenticity certificate. The validator sample
can report some errors with status zero, so QA also required its unpack marker,
empty stderr, output presence, valid PGM header/dimensions and exact pixel-byte length.

Real-camera coverage remains the initial eight-file stratum: firmware 2.2.1, ISO
400 and one lens. No C-RAW, DPRAW, other camera/layout, arbitrary field growth/shrinkage
or general CR3 write support follows. Big-endian evidence is authored structural
testing only, not a new real-camera variant.

Eight scoped experiment records contain 32 independent-run records. Eight revised
source admissions, eight candidate admissions, 16 decoded derivative admissions
and 33 provenance reviews validate against the existing contracts. Tool/source/
driver/recipe identities, exact argv/environment/termination/captures and artifact
hashes are retained privately. Original media, sensor pixels, identifying metadata,
per-image hashes/offsets and machine paths stay outside public Git and CI.

The supervisor imposed a 120-second per-run timeout. No OS hard memory cap or
external decoder depth/decoded-byte/aggregate-record cap was imposed; records use
version 2's explicit nulls and reasons. Native reader limits remain as declared;
the probe also refuses sources over 256 MiB. These are not performance baselines.

## Storage primitive observations

The same disposable marker-data probe ran on:

| Environment | Observed storage | Guard/flush observations |
| --- | --- | --- |
| Windows 11 build 26200, x64 | Local fixed NTFS volume | Native share mode blocked independent writes through source and hard-link alias, and rename. A timestamp update still succeeded. No complete directory persistence protocol tested. |
| Ubuntu 26.04, WSL2 kernel 6.18.33.2 | Native ext4, `data=ordered` | An unrelated writer bypassed advisory `flock`; a directory `fsync` call succeeded. |
| Same WSL2 distribution | Windows mount reported `v9fs` | Advisory lock was bypassed; directory `fsync` returned success. This is a distinct observation, not ext4 or Windows profile inheritance. |

On all three, a controlled hash-then-replace interleaving lost a simulated external
edit. Conditional hard-link creation refused a destination created at the publication
boundary and retained its complete bytes. A fresh link exposed the complete staged
marker payload and shared its object identity. These observations are not a general
concurrency/observer stress campaign or a tested metadata backend.

Four exact process-kill boundaries ran per environment (**12 kills**). Before the
link, staging remained and the output was absent. After the link, a complete output
remained; a kill before receipt creation left no receipt. A final receipt can exist
without a proven namespace durability acknowledgement. The probe retained evidence
and performed no automated repair or rollback. These runs prove neither OS-crash
nor power-loss survival; successful flush calls do not close that evidence gap.

See [sanitized observations](storage-observations.json) and
[aggregate evidence](new-output-summary.json). All **mutation profiles remain
unverified**. In particular the existing read/preview extractor's trusted-directory
hard-link behavior is not inherited as a durable metadata-write profile.

## Review and sequencing

| Card | Deliverable / evidence gate |
| --- | --- |
| #0021 | This private fixed-width candidate proof, independently decoded media, seven public tests and primitive observations. |
| #0022 | Bind source/stage/parent identities and private properties; prove guarded new-name publication, persistence, cancellation and evidence-based recovery on declared profiles. |
| #0027 | Prove exact write-format admission, coupled/checksum constraints and known-authenticity refusals for the first CR3 output increment. |
| #0023 | Integrate preview/explicit apply and truthful results for exactly the evidenced new-output operation/profile. |
| #0024 | Explicit RAW/XMP pairing, one-way mappings, sidecar no-ops and partial synchronization/storage evidence. |
| #0025 | Named privacy catalogs, known signatures, residual/uninspectable coverage and independent targeted fixtures; no anonymity/secure-erasure claim. |
| #0026 | Existing-file replacement, properties, retained originals, grouped operations, restore/prune and interruption recovery. |

#0014 retains the full acceptance criteria. None is waived by splitting, and none
of the sixteen SAF scenarios is declared fully completed by this increment.
Correct refusals and private byte-preserving candidates are distinct from enabled
mutations. Before production integration, #0022/#0027/#0023 must add real ownership,
identity, property, publication and recovery checks; authenticity refusal coverage
must also be evidenced for the proposed embedded operation.

Public tests exercise the actual experiment on authored little/big-endian structures,
exact complement checks, no-op/collision/source preservation, unsupported/malformed
inputs and injected short-read/scratch-write failures. A fixed-seed 512-case
patch/corruption smoke test covers varied lengths/positions. It is not a long-running
or coverage-guided fuzz campaign. The production test gates remain independent.

## Primary observations and provenance

Viewed **2026-10-11**; living references unless a revision is noted. No upstream
implementation, fixture or full tag table was imported.

- [CIPA DC-X008-2016](https://www.cipa.jp/std/documents/e/CIPA_DC-X008-Translation-2016-E.pdf)
  identifies the existing date field and separate offset/subsecond representations.
- [Microsoft CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew)
  documents share modes and the distinction from attribute access.
  [CreateHardLinkW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-createhardlinkw),
  [FlushFileBuffers](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-flushfilebuffers)
  and [ReplaceFileW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-replacefilew)
  constrain future profile design; API documentation is not runtime durability proof.
- [LibRaw official downloads](https://www.libraw.org/download) supplies the versioned
  portable 0.22.2 binary/source package. Its copyright and dual LGPL/CDDL notices are
  retained; the scoped review admits unchanged private subprocess validation under
  the LGPL option, without linkage, distribution or product dependency selection.
- The [existing reference baseline](../corpus-baseline/README.md) supplies the
  ExifTool pin, runtime and media rights. [Reader format evidence](../reader/format-evidence.md)
  records factual CR3 mappings independently checked on these source bytes.
