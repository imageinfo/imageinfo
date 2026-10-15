# Native original-date to XMP candidate (#0104)

Implemented **2026-10-15**, as a bounded prerequisite child of **#0085**. The
[standalone adapter](../../experiments/0104-native-xmp-date-adapter/README.md)
connects actual native CR3 reading to the existing
[#0083 mapping](date-mapping.md) and [#0084 candidate mechanism](date-preservation.md).
It removes the caller-asserted date/coverage seam for this narrow invocation.
It does not finish #0085's new-name sidecar publication, adopt a production XMP
writer or enable any filesystem/storage/RAW mutation capability.

## Actual function and useful result

`prepare(raw_bytes, sidecar_bytes, target_ordinal, conflict_policy)` accepts two
already allocated immutable byte slices. It invokes the root
[`reader::read`](../../src/reader/mod.rs) with its default bounded limits and
`Cursor` over the actual RAW bytes. It accepts no caller-supplied parsed Metadata,
coverage flag, date string, companion string or source occurrence ID.

The existing reader must recognize its declared EOS R5 full RAW layout and
successfully finish parsing the supported container/metadata/preview declarations.
That recognition is an existing read capability, not proof of camera authenticity,
sensor decoding, source admission for mutation or independent RAW usability.
Its [implemented scope and bounds](../reader/README.md) remain unchanged.

After the coverage checks below, the adapter selects exact namespace `exif`, CMT2
box paths and numeric tags `0x9003`, `0x9291`, `0x9011`. It uses decoded stored ASCII
text and retains each native ID, original allocation range, full structural path
and text in the result. It does not select by friendly name, composite date,
filesystem time, matching value, display normalization or a sidecar alias.

It builds an invocation-local #0083 original snapshot internally, then calls #0084
against the actual sidecar bytes with the explicit target ordinal and conflict
policy. #0083 verifies cardinality, calendar, fraction and timezone semantics;
#0084 rechecks exact property identity and lexical preservation. Successful results
contain an actual mapped derivative byte vector or the original borrowed no-op
slice, alongside the native source observations and reader revision. Original
source and sidecar bytes remain immutable throughout.

## Coverage is narrower than reader success

The root reader is deliberately partial. Its TIFF traversal follows recognized
directory links and next-IFD links; an unknown pointer could hide another date or
companion. Therefore **any opaque metadata entry whose path includes CMT2 refuses
this adapter** with `IncompleteCmt2Coverage`, even if it looks harmless or contains
zero bytes. The public reader currently also records some recognized pointer
entries as opaque; those conservatively refuse too. There is no guess that an
unknown integer is a scalar rather than an unrecognized pointer.

This admits only the fully decoded CMT2 subset under the reader's declared classic
TIFF grammar. It does not establish absence in undeclared/opaque metadata,
proprietary aliases, other boxes or arbitrary byte patterns. A normal camera file
with additional CMT2 fields may therefore refuse; this ticket makes no passing
real-camera/corpus coverage claim. It does not loosen the reader to manufacture a
successful adapter result.

All selected date/companion occurrences must also share the same complete parent
IFD path. It refuses to combine one IFD's original date with another IFD's offset
or fraction. Missing/duplicate primary or duplicate companions are passed into
#0083's finite cardinality checks rather than choosing a first match or merging
equal values. Unsupported storage shapes, malformed strings, reader limits,
ambiguous/missing container declarations and unsupported variants refuse.

Only after native read success, no opaque CMT2 paths and consistent source paths
does the adapter internally attest complete enumeration for those three exact
tags in that narrow source subset. Companion absence is then observation of the
admitted parsed grammar, not a statement that the whole photo has no timezone,
subseconds, other dates or uninspected metadata. Opaque data outside CMT2 remains
explicitly outside this proof; it is never declared harmless.

## Bounds, provenance and no effects

RAW input is limited to **256 MiB** before invoking the reader. This API receives
already allocated bytes, so its caller must independently bound any earlier read
or allocation. The root reader retains default 8 MiB metadata-read, 1 MiB block,
4,096 box/entry/record and depth-16 bounds, plus its preview bound. Successful
reader traversal returns complete metadata for that invocation or an error;
there is no partial-return fallback used as complete coverage.

Sidecar/candidate input/output remain at #0084's **65,536-byte** bound and inherit
its exact namespace/property/lexical refusals. The adapter uses no deadline, OS
allocation quota, cancellation scheduler or storage reservation. It performs no
hash or live filesystem binding; byte slices are the original immutable
observation for this invocation. Generated IDs are invocation-local descriptive
IDs, not cross-snapshot content identities, authentication or saved apply tokens.

Every result fixes `publication_allowed`, `raw_mutation_allowed` and
`storage_profile_admitted` to **false**, in addition to #0084's false production
mutation flag. No target path is accepted, no file is opened/created/deleted and no
RAW byte is edited. There is no packet serialization or fallback to insertion of
a missing destination property. The adapter cannot publish the owned derivative.

The root path dependency reuses the existing read library. It changes no root
manifest/source/lockfile and introduces no SDK boundary. The standalone graph uses
the existing root dependency versions plus the already reviewed XML research
closure. Existing dependency/license notices are retained; the experiment adds
independently authored glue and public structural test data only.

## Qualification and remaining #0085 work

The [independent authored tests](../../experiments/0104-native-xmp-date-adapter/tests/qualification.rs)
exercise actual structural CR3 bytes, native observed date/companion values and
actual XMP bytes through the entire adapter. Positive derivative and no-op cells
are useful executable integration evidence, separate from unsupported-source
refusals. They establish no sensor-image validity or real-camera write admission.
All fixtures are independently authored project data; private images, identifying
values, private hashes and new private-camera results are excluded.

The [executed qualification record](../../experiments/0104-native-xmp-date-adapter/qualification.json)
reports **11 functions and 23 actual adapter calls**: six derivatives, one borrowed
byte-exact no-op and sixteen refusals. Tests cover exact native allocations,
fraction/offset retention, opaque CMT2 pointers, cross-IFD companions, duplicates,
both TIFF byte orders, malformed calendars, explicit conflict/target/loss choices,
input bounds and an unchanged authored file/neighbor witness. A repeated authored
invocation is not an independently sourced camera fixture.

The standalone pinned-toolchain formatting, denied-warning Clippy, test suite and
release build, plus repository documentation checks, are required for handoff.
The qualification record reports the executed cells and source bindings; tests
of pure decision combinations are not substituted for the actual parser path.

[#0051's current ledger](../write-safety/profile-admission.md) still has **no
supported actual storage profile**. #0085 independently requires an applicable
qualified profile, explicit creation intent/new output name, source retention,
collision/cancel/error/no-op evidence and all relevant format/workflow checks.
This child supplies none of those storage/publication proofs. The accepted
[best-effort power policy](../write-safety/power-test-policy.md) remains unchanged;
future power work is VM-off only, with no physical-power or host-crash requirement.
This adapter runs no VM or interruption test. Existing-sidecar replacement,
two-member RAW–XMP commit, authenticated saved plans, restart repair and automatic
cleanup remain outside its scope.
