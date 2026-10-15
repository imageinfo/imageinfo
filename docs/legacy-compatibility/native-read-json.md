# Bounded native metadata-read JSON

Implemented and observed 2026-10-15 under #0053. This closes one finite LG-002
serialization cell for the current [Canon EOS R5 full RAW read slice](../reader/README.md).
It specifies the emitted metadata snapshot, its exact value types, identity and
coverage limits, and the differences relevant to exporting this data. Legacy
reports/imports, templates, filename formatting and other RAW profiles remain
outside this increment. No importer or write capability is introduced.

## Versioned package and actual output

| Artifact | Scope |
| --- | --- |
| [Native snapshot schema v1](native-read-json/snapshot.schema.v1.json) | Draft 2020-12 finite emitted subset of the accepted metadata contract. |
| [Authored CLI example](native-read-json/example.v1.json) | Actual observed snapshot emitted from an independently authored structural CR3 fixture, with no private camera media. |
| [Invalid-rational CLI example](native-read-json/zero-denominator.v1.json) | Actual partial failed read whose invalid states retain the offending source range. |
| [Conformance vectors](native-read-json/vectors.v1.json) | Positive boundary and rejection mutations of the example, including exact-number, identity, coverage and loss failures. |
| [Executable QA](../../scripts/check_native_read_json.py) | Validates actual CLI snapshots/envelopes and the committed package; rejects lexical/schema/semantic failures. |

The wire remains `schemaVersion: 1`, `kind: metadata-snapshot`, with its existing
`$schema` URL pointing at the [metadata contract](../metadata-model/metadata-contract.schema.json).
The new native schema narrows that contract; it does not replace the model or add
a second snapshot protocol. Producer model revision is `2026-10-10.1`; reader and
registry revisions are `r5-read-slice-2026-10-11.1`. A native-profile validator must
load both committed schemas locally. Reading these declarations never causes the
application to fetch a schema URL or evaluate configuration.

The snapshot appears in `files[i].snapshot` within the existing
[result envelope](result.schema.json). The envelope retains request identity,
per-file state/issues, summary status and zero content-mutation effects. The
snapshot's `issues` describe metadata interpretation and refer to its own
occurrence/document IDs; these are distinct from enclosing result issues.

Completed `--output json` writes one compact UTF-8 envelope and a terminating LF,
then flushes stdout. Strings use ordinary JSON escaping for quotes, backslashes
and control characters; metadata numbers are never locale-formatted. Object member
order and alternative equivalent JSON string escapes are not identity or digest
contracts. Array order, duplicate occurrence multiplicity, typed strings and
explicit null/state distinctions are significant. The public examples are
pretty-printed parsed snapshots for review, not byte-for-byte stdout captures;
their snapshot IDs retain the actual generated request identity. A rerun compares
their content while excluding only that volatile top-level snapshot ID. Truncated
or failed output transport does not constitute a complete snapshot.

For a supported file:

```text
imageinfo metadata read --output json --values all -- authored.cr3
imageinfo metadata read --output json --values raw --tag ISO -- authored.cr3
```

These are implemented commands, not a request-file/import grammar. All JSON modes
retain `raw`, `normalized` and `normalization`. `--values display` or `all` also
requests present display text for valid values. `raw` or `normalized` makes display
unavailable with reason `Not requested`; the flag does not erase the other exact
layers. Invalid values never get a present display. Tag filtering selects
occurrences without renumbering their original ordinal; resource/coverage records
still describe the reader's declared observation. Even an empty selected
occurrence array can retain preview/opaque resources and partial coverage.

## Identity, occurrence and resources

One snapshot contains exactly one source `src-raw` and one CR3 document `doc-raw`.
`displayPath` is a locator label, not content identity or proof of an opened
object's continuing identity. Full-source hashing is not performed by metadata
read; source identity is explicitly unavailable and every resource `sha256` is
null. Snapshot/occurrence IDs are local references within that observation, not
durable IDs across requests, filtered views, changed inputs or reader revisions.
If a native filesystem path cannot be represented as Unicode text, I/O retains
the native path while JSON display uses replacement characters and the enclosing
file issues include `PATH_DISPLAY_LOSSY`. The snapshot does not export those
original path bytes; reconstructing or reopening a path from `displayPath` is not
a lossless or authorized operation. This platform-dependent loss is separate
from exact metadata integer/rational serialization.
The example's `basis: observed` describes an actual native read of authored bytes;
it is not a claim of real-camera fixture provenance.

Occurrences form an array. Same-named tags in Exif/CTMD namespaces, and repeated
native tags at distinct paths, remain distinct occurrences. `tag` contains
namespace, native ID, display name and definition revision; `path` contains every
indexed box/IFD/record/tag/field part. `ordinal` is the reader's source enumeration
index and its `occ-N` ID uses that number. Increasing ordinals can have gaps after
selection. A tag name or JSON object key never substitutes for exact occurrence
identity. Group labels report the metadata family and do not collapse values.

Each selected scalar's `origin.resourceRef` resolves to its `value-N` resource.
Each binary occurrence refers to a shared `preview-N` resource; opaque uninterpreted
regions get `opaque-N` resources. Resources have one source-address-space range,
referencing `src-raw` with exact decimal-string offset/length. Resource byte length
equals that span's length and its end must be inside the source. Resources can
overlap; this is not a disjoint source partition or a complete dependency map.
Binary previews retain their stored extent, including verified zero padding,
rather than silently trimming to a JPEG end marker. Snapshot JSON does not inline,
base64-encode or copy those bytes. A source range is useful only with the unchanged
source; it is not a standalone lossless media export.

## Exact types, interpretation and loss

| Boundary data | Current representation |
| --- | --- |
| Stored integer | `{"kind":"integer","decimal":"800"}` with canonical unsigned decimal in the native `u64` value type. No sign, exponent, leading zeros, JSON numeric coercion or floating-point intermediate. The current parser's concrete TIFF/CTMD integer fields are 16/32-bit; a serializer-only wide-integer vector does not claim wider file storage support. |
| Stored rational | `{"kind":"rational","numerator":"2","denominator":"500"}` with canonical unsigned `u32` components and nonzero denominator. Preserve the pair unreduced; normalized output remains `2/500`, not `1/250` or `0.004`. CTMD's `rational32u` has two stored 16-bit components widened into this native value type; TIFF's `rational64u` has two 32-bit components. |
| Stored ASCII | `{"kind":"string","text":"..."}` after checked printable-ASCII decoding and terminator/padding validation. The logical text omits trailing NUL storage padding; origin range/encoding retains its location and full stored width. No replacement decoding, date/timezone interpretation or Unicode normalization is claimed. |
| Binary | `{"kind":"binary","resourceRef":"preview-N"}`. The origin also identifies that resource; no opaque byte string is substituted for a value. |
| Byte lengths/offsets | Canonical unsigned `u64` decimal strings. JSON Schema constrains spelling/length; semantic checks enforce `<=18446744073709551615` and checked range arithmetic. |
| Structural indexes | JSON integers within the accepted path/ordinal range, independent of arbitrary-precision metadata value strings. |

Valid raw and normalized value states are identical in this slice. Normalization
names `identity-exact-stored-value`, has `exact` reversibility, empty assumptions
and dependencies, and an explicitly selected unit or null. This is exactness of
the decoded stored value, not a guarantee that text or displayed output can recreate
the original bytes. Unsupported generic metadata-model values, such as arrays,
structures, signed integers, floats or structured datetimes, are not emitted by
this reader profile.

Display uses `native-r5-display-v1`, locale `en`, null timezone and human-readable
formatting. It may use rounded floating-point text or symbolic names. Display is
not an exact rational serialization, an input format, a reversible conversion or
write authorization. The exact typed layers remain alongside it.

A zero-denominator stored pair is an invalid encountered value. Both `raw` and
`normalized` emit `state: invalid`, code `ZERO_DENOMINATOR`, and explanatory detail;
there is no present rational value whose denominator is zero. Normalization is
`not-applicable`, display is unavailable, and a linked severity-error issue retains
the occurrence/document references. The origin's full stored range remains in the
snapshot, so invalid bytes are neither discarded nor manufactured into a valid
number. The enclosing file result is `failed`, can retain its partial snapshot,
and contributes an exit-status-1 outcome; unrelated valid observations remain
explicit rather than being presented as a fully successful read.

Prior serializer output incorrectly labeled that invalid raw pair as a present
rational with denominator `"0"`, contrary to the already accepted MDL grammar.
#0053 corrects only that invalid raw-state representation. The existing diagnostic,
normalized invalid state, failed-file outcome, retained storage and valid-value
wire representations remain intact. Consumers must handle the explicit invalid
state; accepting the prior invalid rational by widening the grammar would hide
the stored interpretation failure.

## Partial coverage and validation

Coverage is always the single `coverage-raw` partial record, namespace `*`, empty
path prefix and an explicit reason describing the limited reader and missing
hashes. No associations or complete-selection records are emitted. Omission is
therefore not an assertion of absence, privacy removal, unsupported-field safety,
full-source preservation or complete ExifTool parity. Empty text, absent occurrence,
invalid value and unrequested display are distinct states.

The package requires these semantic rules in addition to schema validation:

| Rule | Required check |
| --- | --- |
| NRJ-001 | IDs are unique in their table; all source/document/resource/occurrence/issue references resolve to the correct table. |
| NRJ-002 | Unsigned lengths/offsets fit `u64`; source spans have checked in-bounds ends and sums matching resource byte length. |
| NRJ-003 | Distinct increasing ordinals retain `occ-N` identity; exact indexed paths and native tag identities remain separate from names/group labels. |
| NRJ-004 | Native integer values fit `u64`; rational components fit `u32` and have a nonzero denominator. No reduction/coercion silently changes a pair. |
| NRJ-005 | Valid normalized values equal raw values; invalid states, normalization reversibility, display availability, issue links and origin references agree. |
| NRJ-006 | Coverage stays partial, identity unavailable, hashes null, associations/selections empty, and no field claims mutation authority. |

Duplicate JSON member names, bare nonfinite numbers, invalid Unicode scalar text
and trailing documents must fail lexical validation. Unknown members and
unsupported value shapes fail the closed inherited schema/native subset. Syntactic
validity alone cannot prove a digest, source range, equal-value relationship or
capability. The QA helper checks boundary data; it is not an application importer,
general schema engine, callback framework or runtime trust source.

## Finite reference/export differences

These are observed documentation differences, not an ExifTool compatibility test:

| ExifTool documented JSON option behavior | Current native snapshot |
| --- | --- |
| Equal JSON names may be suppressed; `-G4` can distinguish instances. | Occurrence arrays keep separate IDs and exact paths. |
| Numeric-looking values can be JSON numbers; `StructFormat=JSONQ` forces quoting. | Exact integers and rational components always have typed decimal strings. |
| `SaveBin` can add original rational text in a `rat` field. | Unreduced numerator/denominator are the ordinary raw typed value. |
| `-b` may embed binary data using a base64 prefix. | Binary values use named source-range resources. |
| `-j=JSONFILE` can import values using SourceFile matching. | Snapshot JSON is descriptive and has no importer/apply behavior. |

Source: [ExifTool application documentation at pinned revision
2200871d9cef988051d2a99d67df3bda6cbb30a8, JSON section](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/exiftool#L5747-L5808),
observed 2026-10-15. No upstream code, tables or fixtures are imported. Native
differences follow the accepted [metadata model](../metadata-model/README.md),
especially MDL-006 and MDL-010–012, and the [LG-002 ledger](surface-ledger.md).

## Reproduce the bounded checks

Build the current root executable and run the public QA helper with its test-only
`jsonschema==4.26.0` dependency available:

```text
cargo build --locked
python scripts/check_native_read_json.py
```

It must validate authored positive native metadata output, including invalid-value
snapshots, against the actual accepted schemas rather than validating only version
or error envelopes. The guide/package is finite verification of serialization;
camera-read support remains bounded by the reader evidence. No new report/import,
template, filename-format, mutation, plan or storage capability follows.

The 2026-10-15 native Windows check passed **10 actual CLI records and 40 authored
conformance vectors**, including all value modes, filtered/empty selections,
duplicate native tags, big-endian values, printable-ASCII JSON escaping and the
zero-denominator failure. Three Rust serializer-boundary tests separately passed,
including authored `u64::MAX` serialization, exact filtering and retained invalid
storage. Required root formatting, all-target clippy, tests and release build also
passed. Filesystem-dependent tests required the existing temporary-hardlink
capability outside the restricted sandbox; there was no source change to bypass
that verification. Native non-Unicode path loss is documented from the existing
adapter; it is not asserted as a Windows authored filename observation.
