# Bounded R5 date-field lookup and refusal mapping

**#0056 / LG-005**, ledger revision **2026-10-15.1**, inspected **2026-10-15**
against source `211f395e62c2dc35f396c1d40336d87344e4b4d1`.
The [versioned ledger](r5-date-mapping.v1.json) records four finite field rows
and twenty operation cells. It documents existing native observations and
refusals; it is not loaded by the reader and enables no date writer or repair.
LG-005's broader datasets, repair and mapping work remains open in the
[surface ledger](surface-ledger.md). The DATE-family label here means this bounded date-field scope; the broader
[FXP-005 timestamp/timezone and FXP-026 date/GPS workflow cases](../fixture-plan/case-plan.v1.json)
remain unclosed. This four-row catalog does not exhaust date metadata.

## Field and occurrence lookup

| Ledger field | Exact native identity | Named read | Evidence boundary |
| --- | --- | --- | --- |
| `dto` | `exif`, CMT2, `0x9003` / native ID `36867`, DateTimeOriginal | Supported | Exact stored ASCII; Gregorian/calendar validity is checked separately by admission/preview. |
| `offset-original` | `exif`, CMT2, `0x9011` / `36881`, OffsetTimeOriginal | Supported | Independent stored ASCII; no timezone conversion or offset grammar validation by ordinary reading. |
| `subsec-original` | `exif`, CMT2, `0x9291` / `37521`, SubSecTimeOriginal | Supported | Independent stored ASCII; no fraction interpretation, precision conversion or synchronization. |
| `digitized-alias` | CMT2 TIFF tag `0x9004` / `36868`, DateTimeDigitized witness | Refused | Undecoded allocation witness from #0027 negatives; no native named occurrence or selector is emitted. A whole-source read may still succeed and retain its opaque range. |

The [root reader](../../src/reader/mod.rs) binds the decoded rows to CMT2
inside Canon UUID `85c0b687820f11e08111f4ce462b6a48`. The
[TIFF walker](../../src/reader/tiff.rs) retains each traversed directory offset
and entry ordinal. A decoded occurrence's path contains the indexed BMFF path,
`IFD@<TIFF-relative-directory-offset>`, and decimal tag with its entry ordinal;
its value range is an absolute source offset and allocation length. Directory
identity is retained without a semantic ExifIFD/GPS/Interop role classification.
No per-image offsets or global `occ-N` values are hard-coded in this lookup.

For each decoded row, the selectors matching its emitted occurrences are its bare canonical name,
`EXIF:<name>` and `exif:<name>`. Names are case sensitive; no legacy spelling,
CreateDate alias, numeric selector or Digitized selector is added. The
[selector implementation](../../src/reader/wire.rs) returns every matching
occurrence, retaining provenance; repeating a selector does not duplicate results.
An absent match within partial coverage is unresolved, never a global absence.
A raw/normalized value is the same stored string; display supplies no host timezone.

Read support requires TIFF type 2, at most 4096 storage bytes, a final NUL,
printable ASCII before the first NUL and only NULs after it. Reading does not
require a complete Gregorian date or an ASCII20 allocation. A readable blank or
non-calendar DateTimeOriginal can therefore fail the stricter preview shape check.
No container/CTMD date ID or additional date tag is inferred from a familiar name.

## Finite operation denominator

The ledger uses exactly five operations per field. **Supported** means the
bounded observation/report capability exists; an inspection can still return
refusal findings. **Refused** means the requested named operation is unavailable
within this subset. **Unverified** means the requested dependency proof has not
been established. These are ledger dispositions, not new CLI statuses or errors.

| Operation | DTO | OffsetOriginal | SubSecOriginal | Digitized witness | Supported / refused / unverified |
| --- | --- | --- | --- | --- | --- |
| Named stored-value read | Supported | Supported | Supported | Refused | 3 / 1 / 0 |
| Changed-intent advisory preview | Supported | Refused | Refused | Refused | 1 / 3 / 0 |
| Identical-intent advisory preview | Supported | Refused | Refused | Refused | 1 / 3 / 0 |
| Native repair/write/synchronization | Refused | Refused | Refused | Refused | 0 / 4 / 0 |
| Dependency proof for the declared mutation | Unverified | Unverified | Unverified | Unverified | 0 / 0 / 4 |
| **20 cells / 4 fields** | | | | | **5 / 11 / 4** |

Changed and identical intents call the same [read-only preview](../reader/date-preview.md).
The sole target is one unique existing CMT2 DateTimeOriginal ASCII20 allocation:
19 `YYYY:MM:DD HH:MM:SS` bytes plus NUL, Gregorian years 1-9999 and seconds 0-59.
An optional exact range assertion detects a mismatch; it never selects one of
several occurrences. Missing/repeated targets, unverified storage/calendar and
range mismatch withhold the byte proposal. Invalid intended syntax fails before
source inspection. No trimming, leap seconds, partial dates, insertion, resizing,
time shift, conversion or companion repair is supplied.

For a valid target, the report can show hypothetical changed bytes and the exact
source complement even while another admission check refuses. An identical
intent produces zero changed bytes and retains every applicable refusal. It is
not a fast path to a new output name. Every report keeps
`production_mutation_allowed: false`. These distinctions are checked by
[authored preview tests](../../tests/date_preview.rs) and
[admission tests](../../tests/admission_contract.rs).

## Dependencies and coupled effects

[Admission](../write-safety/write-admission.md) checks every traversed CMT entry's
allocation, including undecoded entries, and rejects overlap with an unselected
allocation or TIFF structure. Public authored negatives alias both decoded
`0x9291` and undecoded `0x9004` into the DTO allocation. The latter is a
DateTimeDigitized dependency witness, not a newly supported decoded field.
The historical #0027 report records eight private alias candidates in which
DateTimeOriginal and DateTimeDigitized changed together despite exact complement
comparison and equal independently unpacked RAW pixels. Offset/subsecond copies
remained unchanged in those specific independent reads. This does not claim that
all date copies or dependencies have been identified.

Opaque entries, partial Canon arrays and unknown UUID regions retain
`OPAQUE_DEPENDENCY_UNPROVEN`. An unchanged opaque byte range, recognized TIFF
width, successful external read or matching RAW pixels cannot prove the absence
of a relevant unknown date-dependent checksum, pointer or signature within the
declared mutation scope. This requires coverage of relevant dependencies, not a
universal proof that the entire format contains no checksums. Known authenticity
indicators also refuse; catalog silence is not general authenticity absence.
Source/camera/firmware checks, byte/name guards, storage profiles and explicit
apply authority remain independent. No repair is implied by detecting a conflict.

## Evidence and exact limits

This handoff reads public source/specification artifacts only. It performs no new
camera read, reference write or media import. The public authored fixture source
is [tests/support](../../tests/support/mod.rs); its dates and JPEG markers are
invented structural bytes, not camera images. Existing historical evidence is
reused under its original scope:

| Public evidence | Exact denominator and implication |
| --- | --- |
| [#0020 validation](../reader/validation.md), 2026-10-11 | Eight private full RAW sources; 160 declared scalar/rational checks and 184 primitive source-span checks across the whole read slice. These are **not** 160/184 date-only checks or a new per-date observation count. |
| [#0027 sanitized assessments](../write-safety/admission-observations.json), 2026-10-12 | Eight sources x seven named case kinds = 56 assessments; all 56 refuse mutation and verify the selected field shape. The alias and alias-candidate kinds supply 16 allocation-alias refusal cases. Eight actual private alias candidates supply eight equal unpacked-pixel comparisons. |
| [#0076 preview record](../reader/date-preview.md), 2026-10-15 | Published eight-source read-only preview observations retain opaque-dependency refusal for every source. This separate later result is not counted as new #0020/#0027 work or as mutation admission. |
| [Authored reader/admission/preview sources](../../tests/admission_contract.rs) | Reproducible storage, calendar, occurrence, alias and advisory/no-op contracts; authored structural evidence supplies no additional camera stratum. |

The eight-file historical stratum is EOS R5 full RAW, firmware 2.2.1, ISO 400 and
one lens. No other firmware, C-RAW, DPRAW, camera, blank/partial date repair or
broader DATE-family pass follows. Existing source SHA-256/occurrence revalidation
is documented separately in [#0077](cr3-preview-source-binding.md); content equality
is not object identity or a continuing live guard. The separate
[#0104 native-to-XMP adapter](../sidecars/native-date-adapter.md) has its own finite
in-memory scope; this ledger does not add an XMP operation or file publication.

The historical [field-map primary references](../reader/format-evidence.md)
record CIPA DC-X008-2016 (viewed 2026-10-11), CR3 structural notes at
`151c1a965775ef409ace17714c24ed491cfcf9c4`, and ExifTool 13.59 at
`2200871d9cef988051d2a99d67df3bda6cbb30a8`. They support factual identity/layout
context only. The native code and authored fixtures remain the primary evidence
for current behavior. No upstream tag table is imported and no reference is
presented as a new observation of a living specification. #0099/#0102 private
camera-derived results, including aggregates, are excluded from this handoff.

The independent `scripts/check_date_mapping.py` check validates the finite ledger
and source/evidence bindings; `python scripts/check_docs.py` checks links and JSON.
Neither is runtime admission or a production capability registry.

Validation on 2026-10-15 passes `python scripts/check_date_mapping.py` for four
fields, twenty cells and 31 deliberately rejected ledger alterations. The
independent review ran `cargo test --locked --test admission_contract --test
date_preview --test source_binding`: all 28 authored tests passed (11 + 8 + 9).
Parent-owned verification completes repository-wide checks before commit/push.
