# Actual selected-operation provenance refusal (#0189)

Implemented **2026-10-16**, revision
`privacy-provenance-refusal-2026-10-16.1`. The
[OwnerName removal boundary](../../src/privacy.rs) calls the
[provenance gate](../../src/privacy/provenance.rs) after fresh inspection of the
actual immutable sidecar bytes and before target selection, the absent-target
return or derivative allocation. This implements the inherited WS-021 refusal
for [the selected #0188 operation](xmp-owner-removal-contract.md); it introduces
no new policy-adoption decision or invalidation alternative.

The packet gate uses the actual private-field `xmp::Packet` inspection result.
Existing concrete XML-signature, XMP media-management/basic, extended-XMP and
Photoshop namespace coupling constraints and read-only packet instructions
refuse. Declared coupling namespaces refuse even without a property. Exact
parsed property identity, original ordinal, form, value and original lexical
range are retained for every observed coupling property, including repeated,
empty and uninterpretable values. Complex properties retain their observation
range without becoming deletable. Malformed, unsupported or exhausted packet
inspection refuses through the operation's packet error before a derivative
exists. Unknown supported namespaces remain unknown preserved data; they are
not certified independent, unsigned or provenance-free.

An optional explicitly supplied native byte snapshot uses the existing
[#0027 inspector](../../src/reader/admission.rs), revision
`r5-date-admission-2026-10-12.1`, and catalog
`raw-known-provenance-2026-10-12.1`. It retains the exact existing finding codes
and byte ranges, including AUTH-004 `CANON_ORIGINAL_DECISION_INDICATOR` for
`0x0083` in reached CMT3 Canon scope. Equal, zero and uninterpretable stored
values are not followed as pointers and do not waive refusal. Every occurrence
is retained separately. All existing native refusals remain conservative gates,
including opaque dependencies and incomplete affected inspection. This may
refuse an otherwise useful sidecar edit; a no-match is not admission.

The additive `inspect_with_partial` API runs the same inspector as `inspect`.
On failure it returns a distinctly incomplete result containing the exact error
and only observations reached before that error. A later malformed preview
cannot erase an earlier reached native indicator. Empty partial observations
never mean absence. The original `inspect` API still returns its original
error without an assessment, and every production-mutation flag remains false.
The inspector's existing byte, box, TIFF, preview and marker bounds apply.
Pending APP11 assembly inspection also retains a completed earlier JUMBF when
a later segment/marker-limit error or unsupported continuation prevents normal
assembly completion. The same bounded parser supplies these findings; retries
do not duplicate already reached occurrences, and the original error or
continuation-refusal outcome is retained.

Native snapshots are optional because this slice selects only an explicitly
provided sidecar. Omitting native bytes means native scope is **unexamined**;
there is no same-stem discovery or assertion about a RAW file, preview, sidecar,
remote credential or other unprovided document. Native bytes supplied for this
check remain immutable and are not imported caller reports or booleans.
The request type has no validity assertion or inspection-completeness waiver.

Both `Invalidate` and `Force` requests refuse, including when the target is
absent. A no-op that would supply unchanged new-output bytes receives the same
gate before those bytes are returned. Refusals report
`requested_change_performed() == false`, retain source and indicator bytes and
return no derivative. Known source observations remain visible alongside later
inspection errors. No authenticity, signature-validity, unknown-provenance
absence, signing, key-management, removal-of-provenance or cryptographic
preservation capability is supplied.

## Finite authored verification and limits

[Actual-byte boundary tests](../../tests/privacy_provenance.rs) cover coupling
declarations and exact occurrences, duplicate/empty/uninterpretable signature
properties, absent-target new-output refusal, malformed packet/native scope,
unsupported force/invalidation, native zero/max-valued duplicate indicators,
native no-match with opaque dependencies and a reached native indicator followed
by a genuine malformed JPEG inspection error. Complete APP11 controls cover a
later malformed segment, malformed trailing box, unsupported continuation and
marker exhaustion, retaining exactly one occurrence. They also check unchanged input
bytes and distinct retained native ranges. All inputs are independently authored
public controls; no private media, camera-derived outcomes or signature validity
results are included.

Run `cargo test --locked --test privacy_provenance --test admission_contract`.
The original [policy vectors](known-provenance-vectors.v1.json) remain historical
abstract decision-model evidence. These new tests execute the actual selected
operation; they do not qualify signed-camera media, private lawful-media privacy
use, independent removal certification, a file writer or any publication/storage
profile. [Operation-specific rights](xmp-owner-removal-contract.md) and all format,
dependency, recovery and publication gates remain separate. Originals and external
copies remain privacy residuals. No anonymity or secure-erasure claim follows.
