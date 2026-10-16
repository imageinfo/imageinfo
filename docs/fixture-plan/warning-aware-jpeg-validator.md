# Warning-aware authored JPEG qualification

Observed 2026-10-16, #0111, profile
`turbojpeg-3.1.4.1-windows-warning-authored-2026-10-16.1`.
The installed TurboJPEG warning-aware API passes this **finite authored profile**:
it refuses the deliberately incomplete entropy controls, including early EOI.
This advances the tool qualification work under #0075/P0A-002. Actual camera
assertion execution, fixture phase and decoded-derivative permission remain open.
No camera or PreviewImage bytes were decoded.

Subsequent decision, **#0164 / 2026-10-16**: Terry approved the
[limited private preview use](p0-assertion-gaps.md#accepted-limited-preview-use--0164-2026-10-16),
including its scoped differential phase and temporary local decoded derivatives.
Permission is now recorded. Fresh structural preflight, exact-input profile
qualification and the actual #0075 assertion remain separate unrun technical work;
the unchanged finite profile documented below does not establish camera support.

The [#0107 Pillow result](jpeg-entropy-validator.md) remains a rejected profile.
Pillow returned substituted pixels for early EOI. This recipe uses the codec's
warning-aware API and requires zero status after full decoding; returned pixels
cannot waive a warning. The codec belongs to the same family as Pillow's codec.
It is independent of imageinfo's extraction/parser, rather than an independently
implemented second decoder relative to Pillow.

## Available runtime and provenance

The existing Codex dependency bundle `26.1013.11914` supplies Windows x64
CPython 3.12.14 and libheif's `turbojpeg.dll`. The libheif manifest identifies
`libjpeg-turbo=3.1.4.1=hfd05255_0`. The DLL is 1,027,888 bytes with SHA-256
`fb734a4abb87c07eb78a7292facf0944d7331d55573cd9afd0f242dd0c573245`.
These are installed package/component identities, not a reproducible-build claim.
No dependency was installed or downloaded.

The [profile](../../experiments/0111-warning-jpeg/profile.json) pins the interpreter,
Pillow control encoder/modules/metadata/notices, actual loaded non-OS module
closure, exact native DLL, package manifest and qualification/control source hashes.
Module enumeration excludes modules inside the Windows directory; those OS
components are outside the pin. Every pinned module's bytes are checked before
loading the codec or constructing controls, then the observed closure is compared
before and after decoding. Changed identities, unexpected non-OS modules or changed
recipe/settings refuse. This is a local component binding, not a security sandbox
or complete OS/transitive-runtime provenance proof.

Primary references are the upstream tag **3.1.4.1**, observed 2026-10-16:
the [API header](https://github.com/libjpeg-turbo/libjpeg-turbo/blob/3.1.4.1/src/turbojpeg.h),
[implementation](https://github.com/libjpeg-turbo/libjpeg-turbo/blob/3.1.4.1/src/turbojpeg.c)
and [license explanation](https://github.com/libjpeg-turbo/libjpeg-turbo/blob/3.1.4.1/LICENSE.md).
The TurboJPEG API uses Modified BSD terms together with the wrapped IJG license;
the installed Pillow notices also identify the same libjpeg-turbo version and its
notices. No separate notice file was found beside this bundled DLL. The profile
records the local manifest and Pillow notices, and this recipe redistributes no
upstream implementation or native binary. Any future binary redistribution needs
the applicable notices and license review.

## Exact API and stored-extent policy

The [runner](../../experiments/0111-warning-jpeg/qualify.py) binds the published C
ABI with explicit argument/result types. The reviewed Windows x64 ABI requires
four-byte `unsigned long` and eight-byte pointers. `tjDecompressHeader3` provides
dimensions before output allocation; `tjDecompress2` then requests the native
dimensions, packed RGB, full resolution and `TJFLAG_STOPONWARNING` (`8192`).
Every warning/error status refuses. Header and decode status, raw severity and
bounded exact diagnostic are retained separately. On success, raw severity and
diagnostic are explicitly uninterpreted; they are not an additional error signal.
Output bytes are fully hashed and consumed, then the native handle is destroyed.

The wrapper's supported syntax is three-component 8-bit Huffman baseline
sequential with one interleaved scan, no restart markers, and dimensions at most
128 by 128. Other profiles refuse. Its marker-length and entropy-stuffing-aware
walk finds the stored codestream end; it does not search for the first raw EOI
byte sequence or establish entropy correctness itself. The native decoder is the
separate entropy observation. Native decoding executes on all seven controls,
including controls refused by syntax/extent policy.

The entire stored extent is passed unchanged. The declared suffix policy accepts
no suffix or exactly 32 zero bytes after EOI. It refuses the nonzero suffix;
other suffix lengths are unsupported. Zero suffix acceptance is an explicit
wrapper policy, not a claim that the decoder consumed zeros as JPEG syntax.
No extraction bytes are trimmed. EOI alone does not establish entropy completeness.

## Seven actual authored observations

All pixels are project-authored integer formulas; the original baseline controls
reuse #0107's exact construction. The additional progressive control encodes the
same authored pixels. The encoder and tested codec share a library family, so
this is fault qualification rather than independent proof of encoder correctness.

| Control | Native observation | Combined profile result |
| --- | --- | --- |
| Complete | Warning-free full pixels | Accept |
| Half entropy, no EOI | Warning: premature end of file | Refuse |
| Half entropy plus early EOI | Warning: premature end of data segment | Refuse |
| Immediate EOI, no entropy | Warning: premature end of data segment | Refuse |
| Complete plus exactly 32 zeros | Warning-free pixels identical to complete | Accept |
| Complete plus one nonzero byte | Warning-free full pixels | Refuse suffix |
| Progressive | Warning-free full pixels | Refuse unsupported syntax |

The fixed denominator is seven. [Curated authored observations](../../experiments/0111-warning-jpeg/observations.json)
retain exact input hashes/lengths, full native status/diagnostic observations,
output hashes, process/capture results and the profile hash. The decisive new
evidence is actual warning refusal for incomplete entropy, including the #0107
early-EOI counterexample. A warning-free incomplete control would reject this
candidate profile. Passing these controls does not establish universal corruption
detection, all JPEG profiles, or correctness of arbitrary camera previews.

## Bounds, reproduction and remaining work

Input is capped at 65,536 bytes before native access, dimensions at 128 before
output allocation. Each child has a ten-second deadline and independent stdout/
stderr drains capped at 8,192 bytes each. Deadline, capture overflow, native fault
or unexpected child failure refuses. These are logical/process bounds, not an
OS memory quota or hard scheduling guarantee. Fresh private attempt directories
retain bounded streams, process records, the frozen profile and partial/final
observations, including unsuccessful attempts.

With the workspace dependency tool's bundled interpreter selected:

```text
python experiments/0111-warning-jpeg/qualify.py --attempt-root .local/111-fresh-attempt
```

The directory must be fresh. Compare its `report.json` with the committed authored
observations; a changed profile must be reviewed before new evidence, rather than
regenerated to silence a mismatch. The separate independent audit checks the
native ABI/results, authored input identities and harness refusal behavior.

#0075 remains open for the actual independent R5 assertion, exact admitted fixture,
decoded-derivative permissions and phase review. Reference-only admission is not
expanded. New camera-derived reports remain private where publication is denied.
An out-of-profile camera extent must refuse rather than broaden this profile.
No production JPEG validator, root dependency, RAW development/write permission
or new prerequisite to byte-exact preview extraction is enabled.
