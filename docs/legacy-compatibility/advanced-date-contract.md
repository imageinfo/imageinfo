# Finite advanced date, location and repair boundaries (#0133)

Revision **1**, specified **2026-10-17**. The [machine contract](advanced-date-contract.v1.json)
contains ten operation rows and 42 public authored vectors for MAP-018/019/020/022.
The [independent checker and test-only arithmetic oracle](../../scripts/check_advanced_date_contract.py)
checks proposed results and conservative refusals. It opens no media and adds no
native command, dataset, repair, writer or reference-parity claim. All ten advanced
operations have runtime status `unavailable`; the existing narrower read/preview
capabilities below remain distinct.

## Existing evidence and targets

[#0056](r5-date-mapping.md) remains the native baseline: four field rows, twenty
cells, **5 supported / 11 refused / 4 unverified**. Its three decoded CMT2 fields
are `exif` DateTimeOriginal `0x9003`, OffsetTimeOriginal `0x9011` and
SubSecTimeOriginal `0x9291`. DateTimeDigitized `0x9004` is an opaque alias witness,
not a named decoded occurrence. Stored ASCII reading, one exact fixed-width DTO
advisory preview and dependency refusal do not implement time arithmetic.
The baseline's published historical evidence is reused without new camera reads,
reference writes, private report aggregates or additional fixture claims.

Every future native proposal must bind one immutable original source observation,
full occurrence paths/ranges and exact selected field identities. Duplicate values
do not resolve duplicate occurrences. Partial coverage is unknown, never absence.
No `AllDates` expansion, CTMD/container alias, filesystem timestamp or inferred
sidecar target is defined here. RAW versus sidecar is an explicit destination
choice; no operation writes both implicitly. Matching filenames do not pair them.

The [#0083 date mapping](../sidecars/date-mapping.md) and
[#0104 native adapter](../sidecars/native-date-adapter.md) retain their separate
exact original DTO/fraction/offset-to-existing-XMP-property scope. A successful
in-memory derivative supplies no file publication permission. The
[privacy catalog](../privacy/r5-catalog.md) identifies exact GPS properties and
locations; [read coverage](../privacy/read-coverage.md) can report candidates
where IFD roles are lost. Neither supplies a geotag destination writer. No new
GPS numeric IDs or XMP aliases are inferred by this contract.

## MAP-018: calendar, elapsed time and zone conversion

These are separate proposed operations; no automatic mode selection is allowed.
The finite oracle uses Gregorian civil dates `YYYY:MM:DD HH:MM:SS`, years 1–9999,
seconds 0–59. It rejects whitespace, partial dates, leap seconds and invalid dates.
Its integer-only vectors do not claim subsecond arithmetic or native parsing.

| Operation | Exact proposed semantics | Refusal and destination boundary |
| --- | --- | --- |
| `calendar-months` | Signed integral months, bounded to ±120000; add to year/month and retain day/time. January 31 + one month refuses if the resulting day does not exist. | No end-of-month clamp, elapsed-duration inference, offset adjustment or companion edit. Proposal for one DTO civil value only. |
| `elapsed-seconds` | Signed integer seconds, bounded to ±86400, applied with an explicit fixed source offset. Fixed offset remains the same. February 28 can roll into February 29. | Zone-less EXIF never inherits the host zone. Named-zone DST elapsed arithmetic is unavailable. |
| `offset-convert` | Preserve instant: target civil time = source civil time + target offset − source offset. Explicit source and target offsets are required. | Offsets use `±HH:MM`, up to ±14:00; reject `-00:00` as unknown, invalid minutes and overflow. No timezone identifier or DST rule is inferred. |
| `named-zone` | No selected database or supported rule semantics. | Every named-zone request refuses, including fold/gap inputs. No silent choice of earlier/later instant or nearest valid wall time. |

Future fraction handling must retain exact original digits and precision; no
rounding or silently dropping companion data is permitted. A future offset change
must explicitly name DTO and offset targets together and show exact old/new values;
independent companion coverage remains necessary. Calendar-day/year units,
legacy shift grammar, inverse textual conversions, UTC/Z lexical distinctions,
AllDates enumeration and variable-length allocations remain unmet. An equal-result
proposal retains all admission refusals; it cannot authorize output creation.

The next finite cells are read-bound fixed-offset/DTO proposals with exact
companion coverage, then independently tested field-target policy. Named-zone work
first needs a versioned lawful database and explicit fold/gap/historical-range
rules. No data download or service selection is authorized by this specification.

## MAP-019: clock correction and track matching

Clock correction changes **the time used to query a track**, not the stored capture
date. Inputs must declare camera time's offset/UTC interpretation and sample time
scale. The authored oracle already receives UTC integer seconds; it does not
establish any camera's offset or infer missing zones. All times in the oracle are
bounded to 0–1000000 seconds in an invented common epoch.

For one synchronization pair `(camera0, UTC0)`, use `UTC0 + camera − camera0`
within ±86400 seconds of the anchor. For exactly two pairs, require strictly
increasing camera and UTC times, a camera span at most 86400 seconds, and a query
inside the anchor interval. Use the exact rational affine mapping
`UTC0 + (camera − camera0) × (UTC1 − UTC0) / (camera1 − camera0)`.
Refuse duplicate/reversed anchors, extrapolation, unrepresentable nonintegral
results and output overflow. More than two anchors, fitted drift, uncertainty,
sample selection and real anchor provenance remain unmet.

The separate track oracle receives exactly two strictly increasing UTC samples,
each `(time, latitude_microdegrees, longitude_microdegrees)`. Coordinates are
bounded to ±90/±180 degrees. Require a gap at most 300 seconds and an inclusive
query within that interval. Linearly interpolate each coordinate using exact
rationals and refuse fractional microdegrees rather than round. Endpoints return
the exact endpoint. Longitude differences greater than 180 degrees refuse; this
is no spherical, shortest-path or antimeridian interpolation claim. No altitude,
speed, accuracy, HDOP/PDOP/satellite defaults or extrapolation are supplied.

These limits are proposed finite model constants, not measured performance
defaults, legacy compatibility or a recommended camera workflow. Track file
ingestion, rights/provenance, quality filters, missing-zone diagnostics and actual
read-bound corrected-query integration are the next cells. Explicit catalog-bound
GPS/XMP target mapping, original-value conflicts, exact preservation and storage
admission are separate prerequisites before any geotag publication.

## MAP-020: offline geographic lookup, rights and inverse export

Track matching and geographic-name lookup have separate inputs, evidence and
destinations. No geographic or timezone dataset, network provider, license or paid
service is selected. The only modeled lookup dataset, `authored-rectangle-v1`, is
an invented half-open rectangle `[0,1000000)` on both microdegree axes returning
the invented label `authored-cell-A`. It models deterministic offline containment,
not a real place, nearest settlement, reverse geocoder or measured accuracy.
Unknown datasets, coordinates outside that rectangle and online fallback refuse.

A future real dataset candidate must record the exact provider, version/digest,
license, attribution, redistribution and derivative-export rights, geographic and
temporal coverage, accuracy limits and privacy implications. These are required
manifest facts to verify for the chosen candidate, not legal clearance inferred
from a successful download or this authored fixture. User-supplied track/location
data similarly needs bounded use/export authority; possessing a file does not
authorize publishing its location history. Existing private fixture grants retain
their original limits. No new assets, contacts or external communication follow.

The proposed default is offline with explicit absence/coverage/refusal results;
never send coordinates, dates or filenames to a network service as a fallback.
Alternate names, language, feature/population filters, maximum distance, tie
ordering, boundary uncertainty and dataset freshness require distinct contracts
before real lookup. Record the selected database identity with any future result.

Inverse named-location lookup cannot recover a unique coordinate from a label.
GPS-to-track/template export is a different operation and needs its own exact
schema, coordinate/time precision, ordering, escaping, missing-zone handling and
export rights. Both forms remain refused here. The next bounded cells are a lawful
offline candidate manifest plus authored tie/distance/coverage controls, followed
separately by one exact track-export format. No legacy `-listgeo` or template
output fidelity is claimed.

## MAP-022: validation never confers repair authority

The oracle's `validate` checks only the authored DTO calendar/shape. The result
`calendar-shape-only` makes no claim about camera consistency, RAW decoding,
dependencies, signatures, checksums, file usability or absence of unknown tags.
Existing native parser/preview/admission diagnostics remain their documented finite
checks. An unknown scope stays unknown; passing a selected check is not global
format validity. Warnings and hard refusal reasons must remain distinguishable.

Every `repair` request refuses. Force/minor-warning suppression cannot bypass an
invalid calendar, occurrence ambiguity, allocation overlap, opaque dependency,
provenance refusal, source binding or missing storage profile. The paired authored
validation vectors have the same outcome with suppression true and false. A
diagnostic can report a defect without guessing a replacement or producing an
executable repair plan. In particular, no invented checksum, opaque-block deletion,
copy synchronization or repair-on-read is allowed.

A positive repair slice would need one exact named defect and source stratum,
explicit old/new bytes and all affected fields, a documented semantic mapping,
independent preservation/dependency evidence and qualified publication. Importing
a proposed fix or seeing a successful external read supplies none of those.
General validation, unusual flags and general repair remain unmet under #0015;
this handoff finishes the bounded specification, not those capabilities.

## Verification and residual denominator

Run `python scripts/check_advanced_date_contract.py`,
`python scripts/check_date_mapping.py` and `python scripts/check_docs.py`.
The first checks ten operation/destination/data/coverage/refusal/next-cell rows,
42 independently declared expected vectors and 26 rejected authority, baseline,
dataset/runtime, result or malformed-JSON alterations. The oracle's positive
outputs are labeled `proposed`; rejected requests are `refused`. These labels
introduce no native status codes or runtime feature registry.

All four MAP families remain incomplete. The machine contract retains the full
runtime/dataset/repair/parity residuals and next finite cells. No test counts here
are camera evidence, production semantic admission or positive preservation proof.
