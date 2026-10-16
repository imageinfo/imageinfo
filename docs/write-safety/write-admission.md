# Read-only CR3 date admission and known-provenance refusals

**#0027**, observed **2026-10-12**. The Rust root library now supplies
[native read-only admission observations](../../src/reader/admission.rs), exercised
by a [separate research executable](../../experiments/0027-cr3-admission/README.md).
No production writer, storage profile, committed receipt or apply command is
enabled. Format/field observations do not grant publication permission.

## Accepted disposition — #0118, 2026-10-16

Terry explicitly selected **option A: retain the current preservation contract and
current RAW mutation refusal**. Embedded CR3 writes remain unsupported. No weaker
experimental assurance or acquisition of a format source was selected.

The affected requirements in [the write-safety contract](README.md) remain unchanged:

- **WS-006:** "Unknown modes/layouts or unproven preservation refuse embedded writes".
- **WS-007:** "Unknown data may be retained byte-for-byte only when its placement/dependencies can remain valid."
- **WS-008:** "Passing an external sample test never replaces checks on the user's current file."

The #0027 `OPAQUE_DEPENDENCY_UNPROVEN` boundary remains in force. Equal byte
complements, unchanged opaque values, successful reference writes and matching RAW
unpacks do not establish unknown semantic independence. Known-authenticity and
uninspectable-dependency refusals, explicit no-op/new-name effects, current-source
validation and all storage/publication requirements remain unchanged. Imported
plans and caller assertions cannot grant format authority.

Stop generic reference experiments aimed at clearing this residual. Positive
format work resumes only when a concrete sufficient evidence source or an exact
semantically justified layout can address it. #0119 remains a contingent Backlog
scope with no sufficient implementation basis; #0078 and the original #0014 safe
writer acceptance remain unfulfilled. They are not completed by this decision.
Existing read/preview work and separately qualified XMP sidecar paths can continue.

## Declared field scope

The proposed operation replaces one existing CMT2 EXIF tag 0x9003,
DateTimeOriginal, in its existing 20-byte ASCII allocation. It does not insert,
delete, resize, relocate or synchronize date copies. A complete Gregorian source
and replacement date, one unambiguous occurrence and an optional current-range
assertion are checked. Camera/mode/layout checks reuse the actual bounded R5 reader;
firmware must be the single stored `Firmware Version 2.2.1` value. This is the
observed eight-file stratum, not other firmware/cameras, C-RAW or DPRAW admission.

Years 1..9999, complete dates and seconds 0..59 are this narrower policy. Exif blank
or partially unknown values, leap seconds, fractions, offsets/timezone conversions
and other date storage shapes remain unverified/refused. The exact encoded value
is 19 ASCII characters and a terminating zero. OffsetTimeOriginal,
SubSecTimeOriginal, DateTimeDigitized and container/CTMD copies remain independent.
An already matching value still needs all gates for any requested new-name effect.

The occurrence/range assertion is only a current conflict observation. A root
library caller supplies a stable stream; the research executable holds a read
handle and observes length/mtime. Neither supplies full source/path/property
exclusion or authority from a saved record. There is no imported capability flag,
serialized-plan replay, hidden output or automatic destination switch.

## Alias and dependency gate

Admission checks every CMT TIFF entry's value allocation, including entries outside
the reader's decoded subset, plus TIFF headers and directory tables. Overlap with
any unselected allocation or structure refuses. This closes a concrete gap in
[#0021's scoped candidate proof](new-output-preservation.md): byte complement
equality and unchanged decoded fields can miss an undecoded alias into the edited
allocation. The prior proof explicitly left unknown-pointer semantics unproved.

Opaque entries, partial Canon arrays and unknown UUID dependency regions retain
`OPAQUE_DEPENDENCY_UNPROVEN`. A known TIFF width or unchanged opaque bytes cannot
establish that an unknown pointer/checksum does not depend on the changed date.
All eight initial real-camera files therefore remain refused for mutation despite
their matching field shape. Passing external metadata/RAW reads does not override
that result or qualify an unknown checksum. The bounded query is useful for
specific refusals; no complete format-write profile is advertised.

## Bounded known-provenance catalog

The [versioned four-entry catalog](known-authenticity.v1.json) defines conservative
indicator refusals in the inspected CR3/embedded-preview locations. C2PA BMFF UUID,
JUMBF description UUID and the TIFF provenance-tag identifier are recognized.
Canon's OriginalDecisionDataOffset indicator is also refused without following its
value as a file pointer. Presence is not proof of a valid signature; malformed or
zero references cannot turn the indicator into write permission.

JPEG scanning walks bounded marker/entropy framing, including stuffing, restart
markers, subsequent scan headers and APP11 fragments. Continuations must repeat
the same LBox/TBox before assembly. SOI/EOI and at most 16 verified zero padding
bytes define the inspected extent. Pixels are not decoded by the tool. Unsupported
or malformed envelopes fail closed; preview maker notes and generic JUMBF remain
uninspectable. Arbitrary UUID/magic bytes inside compressed samples are not treated
as structural provenance. No remote manifest, credential or sidecar is fetched.

The report distinguishes **indicator present**, **no match in inspected locations**,
and explicit uninspectable/dependency refusals. It always denies general authenticity
absence and cryptographic validation. Unknown proprietary signatures, opaque
containers, XMP/remote credentials and unsupported packet forms remain outside the
bounded catalog. Broader privacy/invalidation policy and targeted signed-camera
corpus coverage remain #0025/#0018.

## Actual private evidence

[Sanitized observations](admission-observations.json) cover eight previously admitted
EOS R5 full RAW clones, firmware 2.2.1, ISO 400 and one lens, with separately named
authored negative derivatives. Originals/received media are not used as mutation
targets or distributed. Their hashes and original modification times were rechecked
against the intake records; all eight remained unchanged.

- **56 native assessments** and **56 pinned ExifTool 13.59 reads** cover baseline,
  C2PA BMFF indicator, unknown UUID, date-allocation alias, TIFF provenance indicator,
  Canon decision indicator and the resulting private alias candidate per source.
- **40 authored negative derivatives**, eight private alias candidates and eight
  independent LibRaw 0.22.2 unprocessed RAW unpacks were retained.
- All eight alias candidates passed exact file-length/complement comparison and
  complete decoded-PGM hash equality against the earlier admitted baselines.
  ExifTool nevertheless observed DateTimeOriginal **and** DateTimeDigitized changing
  together through their shared allocation. The native gate refuses that alias.
- Offset and subsecond copies remained unchanged in the independent alias reads.
  Every tool input's actual hash/mtime was checked before and after, across
  **128 invocations**. All proposed mutation admissions refused.
- Known indicators are authored structural negatives, **not cryptographically
  valid signed-camera fixtures**. They test refusal/detection, not signature validity
  or provenance-preserving writes. No authenticity certificate follows from RAW
  unpack or checksum equality.

An owner-only ACL was applied to the new empty local scratch directory before any
private bytes were copied. At least 8 GiB free scratch was checked for this bounded
run. Exact tool/source/argv/environment identities, captures, hashes, dates, offsets,
lineage and **323 manifest-verified retained files** stay private. Earlier captures
remain retained. The source/binary was retained for each qualification revision;
public Git contains no camera bytes, pixels, private paths or per-image hashes.

## Limits and verification

Source size is capped at 256 MiB. Existing reader limits apply to its first metadata
pass; the additional admission pass has an aggregate 64 MiB read budget and 1 MiB
block cap. JPEG input uses 64 KiB buffers, at most 4,096 markers across previews,
and at most 1 MiB assembled APP11 payload. TIFF count/depth and BMFF box/depth limits
remain enforced. A control/size-bound failure is a refusal, not evidence of absence.
No hard native I/O deadline or OS memory quota is claimed. Private external tools
have a 120-second supervisor timeout; decoded/output quotas remain unconfigured.

**11 root contract tests** exercise exact calendars, field/no-op/conflict behavior,
decoded/undecoded aliases, firmware/date refusals, BMFF/TIFF/JPEG indicators,
standard fragments and later scan headers, malformed/opaque packet cases,
big-endian authored structures, marker/assembly ceilings and a 1,024-position
corruption smoke. **Two executable tests** verify no source/directory/mtime changes,
space-containing paths and bounded invalid-date refusal before opening an input.
These are authored structural bytes, not a public camera/signature corpus.

Root formatting, Clippy, **36 Windows tests** and release build passed; research
format/lint/two tests/release and Python syntax checks also passed. Platform CI is
bound separately in [the CI ledger](admission-ci.json). Root dependency versions,
lockfile and unsafe policy remain unchanged. The [16-package/17-notice research
admission](admission-dependencies.json) reuses exact root archives/notices; there is
no C2PA SDK/library dependency or upstream implementation import.

## Disposition and remaining gates

| Cell | Disposition |
| --- | --- |
| Native exact calendar/storage/occurrence checks and all-allocation alias refusal | Implemented read-only checks, with actual authored/private observations. |
| Known indicator catalog and bounded packet inspection | Implemented conservative refusal; general absence/signature validity unproved. |
| Unknown checksum/pointer dependencies on the selected field | Unproved; actual baseline mutation admission refuses. |
| Production writer, publication/storage profile and explicit apply | Disabled. #0022/#0014 and #0023 remain open. |
| Broader privacy/signature invalidation and additional camera variants | #0025/#0018; no inherited support from eight full RAW files. |

CAP-026 and CAP-042 remain specified/unverified as whole capabilities. WS-006/007/
008/009/011/014/020/021/024, SAF criteria and GAP-004/GAP-009 stay in force. #0027's
handoff supplies a native refusal boundary and measured admission gaps, not a
passed complete writer gate. Its acceptance does not satisfy #0023's prerequisite
for an enabled new-output operation/profile. Do not convert research/field-match
booleans or catalog silence into mutation permission.

Primary observations, **2026-10-12**, facts only; no upstream code/table copied:

- [CIPA Exif 2.31 date/offset fields](https://www.cipa.jp/std/documents/e/CIPA_DC-X008-Translation-2016-E.pdf)
  (2016 translated draft used by #0021). Supports storage/name facts, not the narrower
  calendar/admission policy or Canon checksum proof.
- [C2PA 2.2 technical specification](https://spec.c2pa.org/specifications/specifications/2.2/specs/C2PA_Specification.html),
  Manifest Store and Appendix A.3/A.5 identifiers. Supplies indicator locations,
  not proof of official CR3 compatibility or any observed signature's validity.
- [Primary JPEG framing observation](https://github.com/contentauth/c2pa-rs/blob/58b9a092882b4dcbdbfe854073a1021d3fcbf9a9/sdk/src/asset_handlers/jpeg_io.rs)
  (revision `58b9a092882b4dcbdbfe854073a1021d3fcbf9a9`): packet fields and repeated
  continuation header corroborate the authored framing checks; no SDK is imported.
- [Pinned Canon decision-data definition](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/lib/Image/ExifTool/Canon.pm)
  maps the Canon 0x83 indicator. CR3 presence/validity is not assumed from its name.
