# Bounded read-only privacy coverage (#0088)

Implemented **2026-10-15** in the standalone
[coverage reporter](../../experiments/0088-privacy-coverage/README.md). This is
actual finite read-only reporting for
[`r5-gps-owner-serial-core`, revision 1](r5-catalog.md), using the existing native
reader's real paths/ranges and optional #0081 XMP inspection. It is not a generic
permission/refusal model. It does not broaden the root parser/CLI, adopt a
production privacy profile, remove metadata or certify privacy/anonymity. The
catalog's original proposal/adoption boundary remains intact.

## Input and actual report

`inspect(raw_bytes, optional_explicit_sidecar_bytes)` reads immutable byte slices
through the existing root `reader::read` and its default limits. It accepts no
caller-created Metadata, inferred path association, claimed field list or coverage
Boolean. The standalone binary takes one explicit RAW path and optional
`--sidecar XMP`, opens regular files read-only and reads bounded snapshots. It
does not discover sidecars or scan neighboring files. It emits JSON to stdout;
error messages contain fixed codes rather than metadata values or source paths.
Arguments remain OS-native paths; non-Unicode names are not converted through
`env::args()` or printed by Unicode-conversion panic diagnostics.
Unreadable, non-file or over-limit CLI inputs refuse the invocation rather than
inventing coverage for bytes the program did not load. A loaded sidecar rejected
by the bounded XML parser instead yields explicit uninspectable sidecar cells.

The report records catalog/reader revisions, the declared selector denominator,
source length, recognized preview ranges, every expanded coverage cell, the
reader's opaque region inventory and explicit residuals. It emits **no decoded
metadata values, source filenames or content hashes**. Counts, allocation ranges,
flags and structural paths can still be sensitive; this is not a sanitized export
or publication grant. Root format recognition remains the existing declared R5
full RAW read slice, not independent sensor decoding or write admission.

## Exact denominators and coverage states

The catalog has **31 selectors and 59 selector/location templates**. For each
successful RAW observation, the reporter expands one cell for every declared
selector at every recognized preview document, plus fixed RAW and sidecar cells:

`expanded cells = 18 native RAW cells + 13 sidecar cells + 28 × recognized previews`.

The template count is not an observed-field count. Recognizing several preview
resources does not prove that arbitrary/opaque containers contain no additional
preview or metadata documents. The report always retains that inventory residual.
Opaque regions may overlap and their summed lengths/counts do not establish
disjoint byte coverage, whole-file examination or privacy completeness.

| State | Exact meaning |
| --- | --- |
| `observed_retained` | An explicitly selected sidecar in #0081's supported subset contains one or more exact expanded-name properties. Each property remains in the immutable original bytes. Value validity is not evaluated. |
| `checked_no_exact_property_match` | The complete supported sidecar property list contains no property with this exact URI/local name. This describes that parsed list only; it never certifies whole-photo privacy or unknown namespace absence. |
| `uninspectable` | The current mechanism cannot establish this catalog identity/location's complete interpretation. This includes native namespaces, unparsed preview metadata and selected sidecars outside the bounded XML subset. |
| `unexamined` | No sidecar was explicitly selected. This is not a missing-file or absent-property observation. |

Every report fixes `privacyAbsenceCertified`, `anonymityEstablished`,
`removalImplemented` and `productionMutationAllowed` to **false**. Zero confirmed
observations, zero candidate allocations or a list of checked nonmatches can
never turn any flag true. No sum or overall “clean/private” result is computed.

## Native allocation candidates are not confirmed identities

The native reader currently exposes unrecognized TIFF entries as opaque ranges
with CMT/IFD-offset/numeric-tag paths. The reporter preserves those actual ranges
and full paths, including repeated tag ordinals. Matching the expected CMT box
and numeric tag can identify a **candidate allocation for** a catalog entry. Empty
or zero-length candidates are not discarded. The original allocation remains
retained; no byte is decoded, zeroed, moved or removed by this reporter.

That is deliberately weaker than a confirmed catalog occurrence. The TIFF reader
follows recognized Exif/GPS/Interop pointer and next-IFD links, while its public
opaque paths retain offsets rather than the pointer-derived IFD namespace role.
A numeric owner tag under a GPS/Interop IFD, or a numeric GPS tag under an ExifIFD,
can therefore resemble a target without proving the catalog namespace. The
reporter does **not** assume the first IFD is offset 8, reconstruct role from a
friendly label or promote a CMT/numeric match to an exact target.

All native cells remain `uninspectable`, even when their
`allocationCandidates` list is nonempty. Confirmed `occurrences` is a separate
list and remains empty for those cells. An empty candidate list means only that
this partial scan found no candidate in its represented paths; it is never
recorded as absent. Canon's model-dependent `0x0096` is likewise not promoted to
a verified R5 scalar merely because an opaque range has that tag number.

This distinction makes the finite report useful without manufacturing namespace
or value coverage: it records where actual retained allocations need further
inspection, keeps every duplicate, and identifies which observations the current
reader cannot make. No new native TIFF/GPS/owner/serial parser or SDK is introduced.

## Preview, sidecar and unknown scope

Every recognized stored preview has a distinct document ID and retained range.
Its GPS/EXIF/XMP cells are `uninspectable`: listing/extracting a preview does not
parse its nested metadata. No preview is opened as another filesystem input,
rendered, recompressed or trimmed. Pixel content and protected rendering data
remain outside the metadata coverage assertion.

An explicitly supplied sidecar is parsed only through the
[#0081 bounded subset](../sidecars/xmp-component.md). Matching is exact URI/local
name; prefixes are aliases, while different URI case/trailing-slash spellings
remain different identities. Equal duplicate properties remain separate
occurrences with original ordinal, attribute/element form, explicit sidecar
document and logical `rdf-description/property[ordinal]` path. That path belongs
to #0081's property-list model; it is not a byte offset or a full XML source path.
The reporter never copies the property's value into the report.

Unsupported nested/qualified/multiple-description packets, malformed XML, DTDs,
unknown entity references and XML budget failures make selected sidecar cells
uninspectable. No partial successful property list is used. Namespace URIs are
opaque identities and are never fetched. Unknown namespace fields remain residual
content even when they resemble a known label. Root embedded XMP, opaque maker
notes, other catalog exclusions, filenames/logs/backups/recovery artifacts,
external copies and visible pixel content remain outside scope.

## Bounds and absence of effects

RAW bytes have a **256 MiB** cap before native reading. The caller must bound
earlier allocations independently; the library receives already allocated slices.
Root defaults retain the existing 8 MiB metadata-read, 1 MiB block, 4,096
box/entry/record and depth-16 limits, plus its preview bound. The report preflights
at most **4,096 expanded cells** and **32,768 opaque region observations**.
Exceeding those limits refuses rather than returning a truncated complete report.
Optional sidecar parsing retains #0081's 65,536-byte/node/depth/property/text bounds.
These are logical limits, not process RSS, timing, free-space or concurrency quotas.

The library accepts immutable bytes and has no write/remove/file API. The binary
uses read-only regular-file opens and emits only the requested report; it has no
storage/profile admission, repair, cleanup or publication path. Snapshot reading
does not establish continuous exclusion against a concurrent actor. A private
audit's before/after bytes and mtime witness are bounded quiescent observations;
OS access-time accounting is not claimed unchanged.

## Public authored controls and private actual characterization

The [independent authored tests](../../experiments/0088-privacy-coverage/tests/qualification.rs)
use project-authored structural RAW controls and invented XML/metadata values.
They test the real reporter/parser path, candidate-versus-confirmed distinctions,
wrong-IFD collisions, duplicate ordinals, explicit sidecars, exact expanded names,
unsupported shapes, denominator arithmetic and unchanged input witnesses. They
do not import or reveal private photo/sidecar bytes. The public qualification
record is for these authored controls only, with no camera-derived outcome count,
Boolean, value or source hash included.

The [public authored qualification record](../../experiments/0088-privacy-coverage/qualification.json)
records **13 executed Windows test functions**, including OS-native non-Unicode
argument handling and fixed/redacted CLI failures. Its public source bindings
cover the listed authored files only; separately frozen private source/executable
bindings belong to the controlled actual characterization evidence.

The current lawful full RAW stratum is characterized separately under a **fresh
private scoped addendum**, bound to the exact current source, latest native
admission/scoped reviews, existing grant/privacy evidence and the explicit #0088
read-only purpose before media reads. Historical initial reference-only records
are preserved rather than silently rewritten. Private local analysis permission
does not grant publication: source reports, outcomes/counts/flags, per-source
hashes, paths, logs and input-change witnesses stay in private storage. This
process grants no new privacy certification, redistribution or mutation admission.

The pinned standalone formatting, denied-warning Clippy, authored tests and release
build plus documentation checks are required handoff verification. No removal,
anonymity, secure erasure, independent RAW usability, storage publication or
broader camera/firmware/format coverage is qualified. The separate
[known-provenance refusal catalog](../write-safety/known-authenticity.v1.json)
retains its measured scope; this reporter does not validate or invalidate signatures.
