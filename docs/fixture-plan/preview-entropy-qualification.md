# Bounded PreviewImage entropy qualification method

#0075 supplies the method for the selected [P0A-002 assertion](p0-assertion-gaps.md).
Its public evidence concerns project-authored controls and the qualification
mechanism. Camera-derived evidence, including whether an actual assertion ran or
its outcome, belongs only in the restricted local record. This document neither
reports that evidence nor closes P0A-002 by a method or refusal alone.

## Historical evidence and the new candidate

The [#0107 Pillow candidate](jpeg-entropy-validator.md) remains rejected: early
EOI after shortened entropy returned substituted pixels. Full pixel production,
EOI presence and disabled truncation tolerance do not establish entropy completeness.

The accepted [#0111 warning-aware qualification](warning-aware-jpeg-validator.md)
remains its original seven authored controls, 65,536-byte input ceiling and
128-by-128 dimension ceiling. Its frozen profile is not widened. The separate
`experiments/0075-preview-entropy` candidate must qualify its own finite authored
controls and exact runtime/recipe before it can support the selected private cell.
Before authored native execution, #0075 selected a new candidate revision requiring
separate review, with an all-zero suffix interval of zero through 32 bytes. Its rationale
is finite zero-padding tolerance with exact whole-extent accounting. Zero padding
does not establish entropy correctness. The historical #0111 suffix policy stays
unchanged; the earlier unexecuted #0075 candidate is retained privately as history.

Both candidates use the installed libjpeg-turbo family. The warning-aware API
offers a different observable failure policy from Pillow's earlier wrapper; it
does not supply an independently implemented decoder relative to Pillow. Its
entropy observation is independent of imageinfo's extraction and structural parser.
The authored encoder shares that codec family, so its output is fault-qualification
material rather than independent proof of encoder correctness.

## Permission and execution order

Terry already answered [#0164 option A](p0-assertion-gaps.md#accepted-limited-preview-use--0164-2026-10-16).
The exact existing private PreviewImage has permission for bounded non-decoding
preflight and this one differential P0A-002 use, including temporary separately
named local decoded derivatives consumed and hashed for validation. No repeated
consent decision is required for that exact use.

The technical gates remain separate:

1. Bind the unchanged historical grants, selected immutable source lineage and
   exact scoped permission overlay before any camera-byte inspection.
2. Freeze the new generic authored profile independently of camera-derived values.
   Qualify its authored positive, negative and process controls and obtain fresh
   independent source, provenance and retained-artifact review.
3. Perform permitted non-decoding identity, syntax and complete stored-extent
   preflight. Compare its private findings with the independently qualified profile.
   A mismatch stops before decoder access; it cannot trigger an adaptive profile
   expansion or another selected input.
4. Only after the parent's reviewed execution gate, execute exactly the declared
   permitted immutable existing cell. Retain every attempt and independently audit
   the resulting artifacts and before/after input binding. Do not adapt or retry.

All new camera input identities, values, counts, hashes, decoded pixels, captures,
Boolean outcomes and reports stay private. Public method and authored-control
evidence do not authorize publication of even aggregate camera results. The project
license does not enlarge source grants. No new media, upload or dependency download
is part of this method.

## Generic technical envelope

The new candidate's constants are selected from authored practical limits. They
are not inferred from the selected private preview. The separate
[profile](../../experiments/0075-preview-entropy/profile.json) identifies this
candidate as `0075-baseline-interleaved-rgb-zero-padding-v2`.

| Property | Candidate limit or policy |
| --- | --- |
| Entire stored input | At most 32 MiB, checked before native decoder access |
| Dimensions | Positive width and height, each at most 8,192 |
| Decoded layout | Full-resolution packed RGB; at most 256 MiB |
| JPEG syntax | Three-component, eight-bit Huffman baseline sequential; one interleaved scan |
| Restart/progressive modes | Unsupported |
| Suffix after structurally located EOI | All-zero bytes, every integer length from zero through 32 inclusive |
| Native failure policy | Every header/decode warning or error refuses |

The per-dimension bound permits at most 201,326,592 packed RGB bytes; the separate
256 MiB ceiling is an additional checked allocation policy, not a claim of total
process memory use. Input buffers, encoder allocations, native workspace, interpreter
state and captures are additional resources. These checks are logical allocation
bounds, not an OS memory quota or containment guarantee.

The structural walk respects marker lengths and entropy byte stuffing; it does
not locate EOI by a raw byte search. It determines supported syntax and the full
stored-extent/suffix disposition, not entropy correctness. Decoder success cannot
waive a structural refusal. The whole stored input is passed unchanged: zero suffix
acceptance does not assert that those bytes are JPEG syntax or authorize trimming
imageinfo's extracted bytes.

## Authored qualification and denominators

### First encoder campaign: preparation failure

The first fixed six-base encoder campaign failed its exact loaded-module closure
guard during preparation. All six process attempts were retained and audited;
no base or provenance was published, and that campaign has no decoder artifacts.
Therefore, no decoder invocation or entropy assertion was evaluated. This is a
preparation failure, not a failed JPEG control or a change to the declared
expectations.

A load-only diagnosis identified a missing separate encoder-closure pin. The
reviewed correction preserved the decoder pin and 59-case denominator. Its
fresh campaign is recorded under [actual authored qualification](#actual-authored-qualification);
the failed attempts were neither replayed nor counted as qualification.
The retained authored failure audit is
`.local/work-wave-20261017e/75-first-encoder-failure-audit.private.json`.

[The positive recipe](../../experiments/0075-preview-entropy/controls.py) declares
43 cases before execution under `0075-authored-controls-v2-zero-interval`. It uses modular
integer RGB formulas and a solid RGB formula, explicit encoder settings and named
4:4:4, 4:2:2 and 4:2:0 sampling controls. Small, odd-dimension, width/height boundary
and square boundary images exercise different declared shapes. The historical
64-by-64 formula base covers every integer zero-suffix length from zero through
32: 33 cases. Five other dimension/sampling bases each cover zero and 32 bytes:
ten cases. Endpoints are not counted twice. These are authored choices rather than camera
observations. JPEG is lossy: decoded pixels are not expected to equal source RGB.
Every positive case requires `nativeInvoked=true` and warning-free full decoding.
Every suffixed case must produce the same complete RGB bytes and hash as its
unsuffixed base, with identical dimensions. All stored bytes, including the full
suffix, remain the input to native decoding.

[The negative recipe](../../experiments/0075-preview-entropy/corruption.py) fixes
sixteen additional cases under `0075-authored-corruption-v2-zero-interval`.
Three shorten the entropy: absent EOI, early EOI and
immediate EOI. The syntax-valid early/immediate-EOI controls require actual native
warning/error refusal. The absent-EOI control refuses before native loading and
must record `nativeInvoked=false`; it supplies no native warning observation.
The same pre-native syntax gate applies to authored and private inputs, with no
bypass mode. The remaining thirteen
exercise disallowed suffixes, marker lengths, table selectors, scan parameters,
restart/TEM markers and duplicate SOI. All thirteen require preflight refusal
with `nativeInvoked=false`; they supply no native outcome. Together with absent
EOI, fourteen negatives require no native invocation.
Suffix negatives include 33 zeros, a nonzero byte at the beginning/middle/end of
an otherwise zero 32-byte suffix, and a concatenated second JPEG.
Structural, native-warning and combined-profile decisions are distinct assertions.
A structural refusal cannot be counted as an observed native entropy failure.
The #0107 early-EOI counterexample remains a required negative control.

The preregistered image-control denominator is 59: 43 positive and sixteen
negative cases. Syntax unit controls and process failure controls have separate
denominators; they are not extra successful image observations. Declaration is
not evidence that any case executed or passed.

The runner must retain each declaration, exact input identity, expected assertions,
actual phase and disposition. No skipped or malformed case can disappear from the
declared denominator. Any changed recipe, runtime or profile requires a new review;
regenerating expectations to silence a mismatch is not qualification. Passing this
finite authored corpus does not prove that every JPEG within the envelope is valid
or that the candidate detects every possible entropy corruption.

## Native observation, process records and independent audit

The adapter binds the warning-aware TurboJPEG C ABI explicitly. It checks header
dimensions before RGB allocation, requests native-size packed RGB with
`TJFLAG_STOPONWARNING`, and consumes and hashes the full output. Header and decode
status, raw severity and bounded diagnostic are separate retained observations.
On success, a stale native severity/diagnostic is uninterpreted; zero status is
the success signal. Handles are destroyed on every completed adapter path.

Runtime binding must verify the installed interpreter, native DLL, control encoder,
notices, recipe source and actual loaded non-OS module closure. The #0111 provenance
is an input to review, not permission to load changed components. OS modules remain
outside the local component pin; this is not reproducible-build or complete runtime
provenance evidence. The recipe redistributes no native binary. Future binary
redistribution requires its own applicable notice/license review.

The profile gives each child a 120-second deadline and independently drained
stdout/stderr capped at 16,384 bytes per stream. Only the direct child is supervised.
The worker retains its full report separately under a fixed name and emits a
small byte-length/hash binding on stdout. The supervisor and independent auditor
require that exact report; its 64 KiB record bound does not raise the pipe capture,
input, pixel or diagnostic limits.
Deadline, cancellation, capture overflow, launch failure, native fault, unexpected
exit or incomplete record cannot become a passing assertion. Fresh attempt roots
retain partial captures and failures. Actual authored child controls must exercise
these failure paths. A deadline is a best-effort process observation, not a hard
scheduling promise; bounded capture is not bounded total process allocation.

The separate auditor reconstructs the declared authored inputs, expected assertions,
runtime/profile/source bindings, stored-extent decision, native observations,
complete output-consumption evidence, termination/capture records and input
immutability from retained artifacts. It does not invoke the producer and accept a
matching self-report as independent evidence. Private execution additionally needs
the exact scoped phase/grant/source bindings; public controls cannot stand in for it.

## Actual authored qualification

The corrected source at `b5495053ad3cd90633376ffb9895c8102385abce` ran the
fixed campaign after the separate encoder-closure and bounded-report corrections.
All six formula encoders retained exact provenance. The
[authored-only results](../../experiments/0075-preview-entropy/authored-results.json)
retain input identities and complete consumed RGB identities without runtime paths.

| Declared controls | Actual audited assertion | Count |
|---|---|---|
| Supported complete inputs, including zero suffixes | Full warning-free decode and complete output consumption | 43 |
| Unsupported syntax or stored extent | Syntax refusal before native invocation | 14 |
| Syntax-admitted early/immediate EOI | Native entropy failure under warning enforcement | 2 |

Every declared cell has valid retained-artifact audit evidence. All positive
suffix variants match their unsuffixed base's complete RGB identity. These
results qualify this finite authored profile only; the separately authorized
private assertion and its independent review are separate work.

## Private completion and limits

The private record must distinguish `pass`, `fail`, `unsupported`, `not-run` and
`invalid-experiment`. A source/profile mismatch is unsupported or not-run as
appropriate; an incomplete, contradictory or unauditable experiment is invalid.
Only actual permitted execution evaluating the named assertion can satisfy #0075's
actual-cell acceptance. Refusal-only evidence or a reviewed plan leaves that
condition unresolved and cannot close the card.

Even a successful selected cell supports only its exact bounded assertion. It does
not complete a camera family, validate RAW sensor data, prove all preview usability,
or enable mutation. No root JPEG decoder/dependency, RAW development feature,
production validator, release gate or prerequisite to byte-exact preview extraction
is introduced. Historical #0107/#0111 evidence retains its original scope.
