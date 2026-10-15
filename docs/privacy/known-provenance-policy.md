# One known-provenance policy cell (#0091)

Status: **reviewable recommendation**, observed **2026-10-15**. Recommend retaining
the existing **refuse before mutation** behavior for **AUTH-004,
`CANON_ORIGINAL_DECISION_INDICATOR`**, tag **`0x0083` in a CR3 CMT3 Canon directory**.
This document proposes that choice for future privacy operations. It records no
new Terry acceptance, production privacy operation or invalidation capability.

The boundary is the [#0027 catalog](../write-safety/known-authenticity.v1.json),
revision `raw-known-provenance-2026-10-12.1`, AUTH-004 only. Other C2PA indicators,
preview maker notes, XMP/sidecar/remote credentials and unknown schemes retain
their existing refusals or uninspectable status. A same numeric tag in another
directory is not this selected identity. The [R5 privacy catalog](r5-catalog.md)
does not authorize deleting this tag or a whole Canon maker-note block.

## Facts and their limits

The pinned primary [ExifTool Canon.pm definition](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/lib/Image/ExifTool/Canon.pm#L1769)
(ExifTool 13.59, revision `2200871d9cef988051d2a99d67df3bda6cbb30a8`, checked
2026-10-15) names `0x83` OriginalDecisionDataOffset and relates it to original
decision data. This supplies an identifier fact, not CR3 pointer semantics,
signature validity, signed-camera coverage or a safe removal recipe. No upstream
implementation or tag table is imported.

The existing [read-only admission implementation](../../src/reader/admission.rs)
reports the selected indicator for a reached CMT3 entry and does not follow its
value as a provenance pointer. It adds `KNOWN_AUTHENTICITY_STRUCTURE` to refusals.
See the [#0027 scope and limits](../write-safety/write-admission.md) and its
[authored indicator test](../../tests/admission_contract.rs). A parseable entry
with a zero or uninterpretable reference still warrants refusal. TIFF storage
allocation bounds must still be inspectable. A malformed directory or allocation
that prevents reaching the finding is an inspection error/refusal; it does not
guarantee an indicator finding.

Presence establishes only a known-indicator observation. Absence establishes at
most no match in the completely inspected selected location. Neither observation
proves authentic origin, a valid or invalid signature, an unsigned asset, absence
of other provenance, or preservation of provenance by a later edit. General
authenticity absence and cryptographic validation remain false. Byte equality,
unchanged RAW unpacking and a caller's claimed validity cannot fill those gaps.

## Explicit alternatives and recommended product choice

| Alternative | Behavior and consequences | Disposition |
| --- | --- | --- |
| A: refuse on the selected indicator | Refuse a proposed metadata/privacy mutation or requested new output before target effects. Preserve the source and indicator; report that the requested privacy change was not performed. An unusable or spurious indicator can therefore prevent a useful edit. | **Recommended.** Matches the implemented #0027 refusal and requires no new signing service, SDK, keys or cryptographic feature. |
| B: explicit derivative with declared provenance loss | A separately designed operation could intentionally remove or alter an exactly understood indicator/data structure, with explicit user choice and a truthful loss report. It would lose the retained structure's evidentiary use and could leave stale or orphaned provenance elsewhere. Clearing the tag or changing unrelated metadata alone would not establish successful invalidation or removal. | **Deferred and unimplemented.** No exact CR3 extent, dependency/pointer treatment or independently verified invalidation/removal method is qualified here. This proposal grants no execution permission. |

Choose A for this bounded product recommendation. Do not add a force switch,
automatic fallback to B, silent stripping or a claim that an edited derivative
remains authentic because the indicator bytes were retained. In a future API or
CLI, explain the refusal as “Known Canon original-decision indicator encountered;
requested change not performed; authenticity unverified.” This wording is a
proposed reporting consequence, not an implemented command or wire contract.

If B is proposed later, name its exact affected occurrences and losses, retain
protected sensor/rendering and unknown data, and independently establish its
claimed structural effect with suitable lawful fixtures and observers. Distinguish
“indicator removed” from “credential invalidated” and from “validity unverified.”
No crypto adoption is prescribed by this document. Consent to loss cannot waive
format, alias/dependency, byte/name guard, storage, recovery or publication gates.

## Finite policy rules

For an edit or a no-op that nevertheless requests a new output:

1. Any reached exact AUTH-004 occurrence causes refusal, including zero,
   uninterpretable or repeated references. Preserve occurrence count; a later
   inspection error cannot erase an already observed match.
2. With no exact match, incomplete inventory, malformed directory, unsupported
   layout or exhausted bounds means uninspectable and refusal. Never translate
   “could not inspect” into “absent.”
3. A complete inventory with no exact match reports only no match in that scope.
   This one indicator gate adds no refusal; all other admission gates still apply.
   It grants no writer permission and no general provenance-absence claim.
4. Explicit invalidation requests remain unsupported, even with a complete
   no-match observation or a caller's “invalid signature” assertion. Existing
   source-indicator findings retain their refusal rather than becoming a waiver.

These are proposed policy rules over observations. They do not implement a media
parser or extend #0027's parser coverage. #0027's finite byte/box/TIFF bounds and
inspection errors still apply. A missing CMT3 supports a scoped no-match only if
the containing inventory was completely inspected; an uninspected document does
not. No remote lookup or same-stem sidecar discovery is introduced.

## Reviewable evidence and handoff

[Version-1 authored vectors](known-provenance-vectors.v1.json) exercise only this
decision table using abstract observations. An occurrence names an already
reached structural entry; an out-of-scope occurrence tests identity isolation.
`referenceShape` is diagnostic and is never dereferenced. `inventoryComplete`
means complete bounded inventory of the selected CMT3 scope, not all asset
metadata. `externalValidityClaim` is untrusted and does not change a decision.

The vectors include positive indicator observations and negative/adversarial
policy cases. They contain no signed-camera assets, actual signature results,
camera-derived reports, media bytes or private evidence. They are not executions
of the native reader, evidence that a malformed camera file reaches a given tag,
or proof that a real signed asset can be edited or invalidated safely. The
[independent finite checker](../../scripts/check_provenance_policy.py) validates
policy consistency only: **14 authored decision vectors and zero media fixtures**.
Run `python scripts/check_provenance_policy.py`; the checker uses only the Python
standard library and local authored JSON and performs no network lookup.

| Cell | Status |
| --- | --- |
| Named identifier and current native refusal | Existing #0027 read-only implementation; bounded authored tests exist. |
| Refusal-versus-invalidation recommendation | Proposed here for AUTH-004; no new policy acceptance implied. |
| Finite policy/vector consistency | Independently reviewable authored model; no media execution. |
| Authenticity/signature verification and signed-camera invalidation | Unrun and unimplemented by this work. |
| Production mutation, privacy removal, invalidation and storage profile | Disabled; unchanged by this handoff. |

WS-020/021/022 and the [write-safety contract](../write-safety/README.md) remain
separate obligations. Known-indicator refusal cannot certify privacy, anonymity,
secure erasure, sensor usability or complete unknown-data preservation. This
bounded policy cell does not close #0025 or enable a production writer.
