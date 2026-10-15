# R5 GPS, owner and serial core catalog (#0087)

Status: **versioned proposal**, observed **2026-10-15**. The single catalog is
**`r5-gps-owner-serial-core`, revision 1** in
[r5-catalog.v1.json](r5-catalog.v1.json), with its
[closed schema](r5-catalog.schema.json). It names 31 exact selectors and coverage
rules. It implements no media reader, removal, anonymity test, runtime framework,
privacy CLI or production mutation profile. #0088/#0089/#0091/#0092 retain their
separate read, one-field removal, provenance-policy and independent-assertion work.

This is a deliberately finite **core catalog**, not an “all GPS” or “all personal
information” operation. Selecting a listed field does not make deleting it safe.
The [write-safety contract](../write-safety/README.md), WS-020/021/022, continues
to require protected-data preservation, known-provenance refusal and honest
residual reporting. Neither a schema-valid catalog nor zero selected occurrences
establishes privacy, absence of provenance, RAW usability or secure erasure.

## Exact selectors and independently checked sources

Native keys include namespace/IFD context and location as well as numeric ID.
These are semantic catalog namespaces, not a new internal reader architecture.
A tag with the same numeric ID in another IFD/table is a different key. XMP keys
are exact resolved namespace URI and local property name. Friendly labels,
ExifTool aliases, prefixes and derived composites are not selectors.

| Group | Exact selected identities | Declared locations |
| --- | --- | --- |
| Native GPS (12) | `0x0001` LatitudeRef, `0x0002` Latitude, `0x0003` LongitudeRef, `0x0004` Longitude, `0x0005` AltitudeRef, `0x0006` Altitude, `0x0007` TimeStamp; `0x0013` DestLatitudeRef, `0x0014` DestLatitude, `0x0015` DestLongitudeRef, `0x0016` DestLongitude; `0x001d` DateStamp | `tiff-gps` in CR3 CMT4 GPS and each preview's EXIF GPS IFD |
| Native owner/serial (3) | `0xa430` CameraOwnerName, `0xa431` BodySerialNumber, `0xa435` LensSerialNumber | `tiff-exif` in CR3 CMT2 and each preview's EXIF ExifIFD |
| Canon owner/serial (3) | Main `0x0009` OwnerName, `0x000c` SerialNumber, `0x0096` InternalSerialNumber under the R5 scalar branch only | `canon-main` in CR3 CMT3 |
| XMP GPS (7) | `GPSLatitude`, `GPSLongitude`, `GPSAltitude`, `GPSAltitudeRef`, `GPSTimeStamp`, `GPSDestLatitude`, `GPSDestLongitude` | URI `http://ns.adobe.com/exif/1.0/`, explicitly selected sidecar or preview XMP document |
| XMP auxiliary (3) | `OwnerName`, `SerialNumber`, `LensSerialNumber` | URI `http://ns.adobe.com/exif/1.0/aux/`, same two XMP locations |
| XMP EXIF extension (3) | `CameraOwnerName`, `BodySerialNumber`, `LensSerialNumber` | URI `http://cipa.jp/exif/1.0/`, same two XMP locations |

GPS labels in the table abbreviate their `GPS` prefix; JSON retains exact labels.
XMP coordinate reference directions are represented within the coordinate values;
this version does **not** invent XMP `GPSLatitudeRef`, `GPSLongitudeRef`, destination
reference properties or `GPSDateStamp`. XMP `GPSTimeStamp` carries the combined
date/time representation. This catalog identifies properties; it defines no
normalization, cross-document alias folding, copying or removal recipe.

Canon `0x0096` has model-dependent meaning in the pinned source. Its EOS 5D branch
is a `SerialInfo` subdirectory, while the fallback is scalar InternalSerialNumber.
The catalog selects only the proposed R5 scalar interpretation. A subdirectory,
unknown/contradictory model context or unsupported type cannot become a selected
scalar by label; report it uninspectable. Never delete a maker-note block to
simulate removing a nested serial. Presence in source documentation does not prove
that a specific R5 capture contains any of these fields.
Canon owner/serial selections are limited to CMT3 in this revision; Canon maker
notes inside previews remain a separate residual location.

Primary facts were checked independently on 2026-10-15:

- ExifTool **13.59**, revision
  `2200871d9cef988051d2a99d67df3bda6cbb30a8`:
  [GPS.pm](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/lib/Image/ExifTool/GPS.pm),
  [Exif.pm](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/lib/Image/ExifTool/Exif.pm),
  [Canon.pm](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/lib/Image/ExifTool/Canon.pm),
  [XMP.pm](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/lib/Image/ExifTool/XMP.pm).
  Selected factual IDs/names/context only; no upstream implementation or whole tag
  table is imported. EXIF source labels OwnerName/SerialNumber differ from the
  standard CameraOwnerName/BodySerialNumber; exact IDs resolve that distinction.
  Canon's UUID directory descriptors additionally map CMT2/CMT3/CMT4 to the EXIF,
  Canon and GPS tables respectively; these establish source-location context,
  not a claim that all those directories or selected tags occur in any camera file.
- [Adobe EXIF XMP namespace](https://developer.adobe.com/xmp/docs/xmp-namespaces/exif/),
  live official reference with no displayed revision: exact EXIF URI and selected
  GPS property forms. No inferred namespace alias or URI rewriting is permitted.
- [CIPA DC-X010-2017, Exif 2.31 metadata for XMP](https://cipa.jp/std/documents/e/DC-X010-2017.pdf),
  historical official PDF, Table 1 and Table 14 (PDF page 22, printed page 18):
  selected owner/body/lens names, IDs and EXIF-extension URI. This PDF contains
  placeholder publication dates; this review identifies the named revision and
  does not claim a precise establishment date or the latest standard revision.

Every JSON entry carries source references and fixture-family references. The
sources establish identity facts, not implementation, safe deletion, occurrence
presence in private captures or a source-data redistribution grant.

## Checked occurrence rules

For each exact selector/location, a future reader must retain each reached source,
document, structural path and ordinal separately. Equal duplicates are separate
occurrences; sorting or a JSON object must not erase them. A scalar value of zero,
an empty owner string, malformed serial or invalid coordinate still counts as an
encountered target. There is no “empty means absent” or first-match-wins rule.

An absence result is allowed only after complete bounded enumeration of that
specific key in that specific document/location. A missing CMT4/preview/XMP document
can support a narrowly scoped document-absent result if the document inventory is
complete; it never proves other location data absent. Unsupported layouts,
pointer cycles, scan limits, incomplete preview inventories, unknown namespaces,
opaque bytes and unrequested documents are uninspectable/unexamined as applicable.
None may be collapsed into an absent/safe result. A reference engine finding a
field does not make the native implementation capable of checking its absence.

Each declared preview is its own document. Merely listing/extracting its bytes
does not inspect its GPS/EXIF/XMP. Sidecar selection is explicit as in
[#0082](../sidecars/pairing.md); no same-stem discovery or inherited RAW coverage.
Root CR3 embedded XMP packets are explicitly **outside this version's locations**
and remain uninspectable. A report must show that residual rather than silently
claiming all XMP was checked.

For XMP, match selected properties at every structurally supported depth, retaining
their full occurrence paths. A same-name qualifier is a residual diagnostic, not
an automatically selected property. Unsupported structures/qualifiers prevent a
complete coverage claim. Namespace URIs remain exact opaque strings: no case
folding, trailing-slash repair, prefix/name guessing or runtime URI fetch. An
unknown namespace's `OwnerName` or `GPSLatitude` is residual unknown content, not
a known field and not safe. #0081's bounded read-only subset does not magically
implement these coverage obligations for all XMP packets.

## Protected rendering data and residual product choices

The selected policy is to preserve all sensor samples/additional planes and their
rendering interpretation. CMP1/CCTP, sample tables, offsets/lengths, CFA layout,
black/white levels, linearization, calibration/color matrices, correction data,
preview payloads, ICC and maker-note rendering parameters are protected. Opaque
metadata, unknown pointers/checksums and container structure are also protected
unless a separate exact edit proves preservation. A field overlapping protected
data cannot be removed merely because the catalog names a nearby serial.

Concrete version-1 scope choices are:

- Cover the listed coordinate/altitude/time/destination-coordinate keys, while
  treating other GPS metadata—including map datum, area information, processing
  method, speed, track, direction and destination bearing/distance—as residual.
  The catalog must never be advertised as a full GPS scrub.
- Cover only named owner/body/lens serial identities. Artist, Copyright, XPAuthor,
  `dc:creator`, contact data, face/region metadata, comments, ImageUniqueID and
  other document/image identifiers remain residual. These may identify a person
  even after every selected field is absent.
- Protect previews as image content. Metadata selectors inside a separately
  inspected preview can be reported, but a whole preview drop or pixel rewrite
  is not an implied privacy operation.
- Keep C-RAW, DPRAW, other cameras, unqualified firmware/layouts, CTMD, other Canon
  serial substructures and root embedded XMP outside this catalog's coverage.
  Mutable camera/model strings alone do not qualify a variant.
- Treat visible pixel content, filenames/paths, logs/plans, backup/recovery copies,
  storage journals/snapshots and external copies as residual. Logical metadata
  deletion cannot establish anonymity or secure erasure.

These are reviewable bounded product choices, not decisions to weaken future
privacy or rendering guarantees. Expanding any selector or location requires a
new catalog revision, source evidence, fixture trace and new qualification.

## Known provenance and fixture trace

The independent
[known-provenance refusal catalog](../write-safety/known-authenticity.v1.json)
remains authoritative for its measured #0027 scope: C2PA BMFF/JPEG/TIFF indicators
and Canon's original-decision indicator cause the existing bounded refusals. It
performs no cryptographic validation and cannot prove general absence of signatures,
remote credentials or unknown schemes. This privacy catalog neither removes nor
invalidates those structures and cannot infer preservation from an absent match.
#0091 owns its separate refusal/invalidation policy cell.

The [fixture-family trace](fixture-trace.v1.json) connects every selected group to
the existing [29-family plan](../fixture-plan/case-plan.v1.json), distinguishing
required future cells, contextual preservation/provenance coverage and exclusions.
It is a trace, not a claim that families passed. GPS presence/absence and coupled
fields, repeated owner/serial locations, previews/sidecars, protected rendering,
opaque data and known provenance need independent fixtures and per-location
results. Authored positive/negative catalog vectors test the **catalog contract**,
not an actual photo reader or metadata removal.

The [lawful #0013 baseline](../corpus-baseline/README.md) supplies restricted
reference context only. Its original permission/admission phases remain intact;
no private input, identifying value, per-image hash or new private-camera result
is published here, and no reference observation becomes native privacy qualification.
The accepted [#0027 admission evidence](../write-safety/write-admission.md) retains
all format/unknown-dependency gates.

## Verification and handoff boundary

The [independent checker](../../scripts/check_privacy_catalog.py) checks schema,
exact field/location sets, source/family references, false capability flags,
protected-data/residual rules and adversarial vectors in
[catalog-vectors.v1.json](catalog-vectors.v1.json). Its outcome is structural and
semantic catalog consistency; it cannot prove upstream ownership, real-media
coverage, removal success or privacy. The ordinary documentation checks include
internal links and JSON, with `git diff --check`.

The [executed catalog QA record](catalog-qa.v1.json) reports **31 exact selectors,
29 traced families and 57 authored vectors**, with zero media fixtures executed.
The checker uses the existing foundation QA dependency `jsonschema==4.26.0`; see
[setup](../foundation/README.md). Run `python scripts/check_privacy_catalog.py`
in that configured environment. Source URLs are review citations only; the checker
loads local JSON/schema data and does not fetch namespace URIs or references.

No media parsing, removal, cryptographic verification, signed-camera run, RAW
usability test, filesystem publication or physical-data erasure is implemented or
qualified by this handoff. A future read report must label target occurrence,
checked absence, residual, uninspectable and protected scope explicitly; a single
“private” Boolean would lose the catalog's essential boundary.
