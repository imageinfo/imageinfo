# Metadata identity, values, and provenance

Status: **proposed boundary contract, ready for review**, revision `2026-10-10.1`.
This is card **#0004**. It defines what information must survive inspection,
selection, export, and preparation of edits. It does not implement a parser,
select a language, prescribe internal classes, or prove any CR3 write safe.

Start with the [schema](metadata-contract.schema.json), the
[synthetic snapshot](examples/snapshot.synthetic.json), and the
[validation record](validation.md). The [capability inventory](../inventory/README.md)
provides the source-backed behavioral requirements.

## Design approach

The design starts from the needs of a metadata tool: identify the input, keep every
occurrence, retain its value and origin, and make transformations explicit.
ExifTool provides useful behavior and edge cases to compare against. Its APIs,
group-family numbers, and internal table organization do not define this model.

The eventual code should be idiomatic and conventional in its chosen language.
These JSON shapes are an external representation. Use ordinary native types and
small functions internally where they fit; a serialization detail is not a reason
to build a generic runtime framework. Boring is a compliment.

Deliberate exceptions need a nearby explanation of the constraint and tradeoff.
The table below records the rationale for the less-obvious wire choices so a new
contributor can understand them without private context.

| Choice | Why it is needed | Internal implementation freedom |
| --- | --- | --- |
| A list of occurrences, not an object keyed by tag name | Different locations can contain the same tag name, and even the same native tag ID can repeat. | Ordinary records and collections; indexes are an optimization. |
| Decimal strings for metadata integers and byte positions | JSON consumers do not uniformly preserve arbitrary integer precision. | Use suitable native numeric types. |
| Rational pairs and floating-point bit patterns | Reducing fractions or serializing NaN/negative zero as JSON numbers loses source information. | Use ordinary exact numeric/bit utilities where available. |
| Explicit value states | Missing, empty, invalid, and unexamined data must lead to different results. | The language's standard result/optional/sum-type idioms may fit. |
| Named binary resources and address spaces | Large images should not be copied into every value; a decoded-buffer offset is not a file offset. | Bounded slices, streams, or other conventional representations. |
| Expanded XMP names and ordered field entries | Prefixes are aliases; namespace identity and original field order must remain recoverable. | Established XML/data structures with a faithful export adapter. |

JSON's number/interoperability and duplicate-object-name limitations motivate these
wire rules. [RFC 8259, sections 4 and 6](https://www.rfc-editor.org/rfc/rfc8259.html)

## Four concepts, with explicit relationships

| Concept | Responsibility |
| --- | --- |
| Source | Identifies an input file and the strength of its content identity. Its display path is not authority to reopen or overwrite that path. |
| Document | Identifies a logical RAW, sidecar, or embedded-preview document within a source. Parent and resource references preserve nesting. |
| Occurrence | Identifies one observed or deliberately derived metadata value, with its native tag key, location, value views, and issues. |
| Binary resource | Describes bounded bytes, either from declared ranges, inline content, a named transformation, or unavailable content. |

Coverage, selections, diagnostics, and sidecar associations are supporting records.
They do not introduce services, plugin systems, or independent runtime layers.
The schema uses named definitions to keep the document readable and avoid repetition.

## Identity and ordering

**MDL-001 — Snapshot scope.** IDs are opaque and unique within their named collection
in a snapshot. An occurrence's identity is `(snapshot ID, occurrence ID)`. Preserve
these IDs when sorting or projecting a view of that same snapshot. Do not promise
the same IDs after reparsing changed bytes, changing parser/registry versions, or
merging another snapshot. Cross-snapshot matching is an explicit comparison task.

**MDL-002 — Native tag key.** `tag.namespace` and `tag.nativeId` identify the source
format's field definition within its declared namespace/table context. XMP uses
the full namespace URI and local property name. Other formats use independently
documented namespace/native-ID conventions tied to the registry revision.
`name` is a canonical, searchable label; `definitionRef` may be null for unknown
fields. Neither a friendly label nor an ExifTool alias is occurrence identity.

**MDL-003 — Location.** An occurrence belongs to one document and has an ordered
structural path. Repeated path segments have explicit indices. Paths are descriptive
locators within this snapshot, not a promise that offsets or layout remain stable
after a write. Native CMT/CTMD/IFD names describe file structures, not implementation
modules. `groups` are advisory classification labels by named axis; they cannot
grant writability or replace the native key and occurrence ID.

**MDL-004 — Duplicates and order.** Store each occurrence separately. Stored
occurrences have unique nonnegative ordinals within their document. Ordinals record
reader traversal order, not byte offsets; preserve them through views. Derived
occurrences have null ordinals. A reader must define deterministic traversal for
the same source, configuration, and reader revision. Do not merge equal values,
deduplicate bags, or let JSON object keys erase repeated tags.

The synthetic snapshot includes EXIF ISO and CTMD ISO with different values. The
exact numbers are invented to force ambiguous selection; they are not camera findings.
The upstream Canon documentation establishes why CTMD and ordinary metadata locations
need independent coverage. [Canon CTMD definitions](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/TagNames/Canon.html#CTMD)

## Sources, bytes, and provenance

**MDL-005 — Content identity.** A source records its byte length and either a SHA-256
identity, an explicit reason identity is unavailable, or an unmistakable synthetic
marker. Normal metadata reads need not hash the entire sensor payload merely to
produce a snapshot. A saved write plan must later establish and recheck sufficient
source identity; an unavailable identity never authorizes applying stale edits.

**MDL-006 — Bounds and address spaces.** Byte offsets and lengths are zero-based
unsigned decimal strings. A range is half-open: `[offset, offset + length)` in its
declared source or resource. Validate arithmetic, reference existence, and bounds
before reading or allocating. Resource ranges are concatenated in listed order;
their lengths must sum to the resource's declared byte length. Do not sort ranges
or infer that a logical resource is physically contiguous.

Resource dependencies must be acyclic. A resource can describe a transformation
of another resource, but that output's offsets address the decoded output only.
A nonlinear transformation does not provide a byte-for-byte mapping back to the
input. A missing physical location is reported as unavailable, never guessed.

**MDL-007 — Retained storage.** A stored occurrence may reference its encoded bytes
and records known encoding/byte order. The `raw` value is the decoded source value;
it is not a synonym for those encoded bytes. Byte-exact reproduction needs the
storage resource as well as interpretation data. Unknown encodings can leave both
raw and normalized values unavailable while retaining the bytes.

Inline base64 must decode strictly and match its declared length. Hashes, when
present, cover the logical resource bytes in order. Referenced source bytes require
the matching source identity to be useful after the source changes. A resource
reference or parser name is data, never an instruction to fetch a URL or execute code.

**MDL-008 — Embedded documents and sidecars.** A preview document has a parent and
a resource, and shares the parent's source unless a separately materialized source
is explicitly represented. The parent graph is acyclic. A sidecar is a separate
source/document connected by an explicit association. Pairing and display precedence
do not make sidecar values embedded RAW values. Preserve conflicts and both origins.

**MDL-009 — Derivation.** A derived occurrence names its rule and input occurrence
IDs. Normalization additionally records any other occurrences it used; its own raw
value is implicit input. Derivation/normalization dependencies must resolve and be
acyclic. Missing inputs produce an explicit unavailable/invalid result. A derived
value is never directly writable merely because its name resembles a stored tag.

## Value views and exact types

**MDL-010 — Three views.** `raw`, `normalized`, and `display` serve different uses.
Normalization identifies its rule, dependencies, assumptions, and reversibility.
It also records the normalized unit when applicable (for example, `s` for an
exposure duration). Unit names and conversions are defined by the registry/rule;
they are not inferred from a translated display suffix. A null unit means no unit
is asserted, not permission to assume one for a write.
`exact` means the raw representation can be reconstructed under the named rule;
numeric equality alone does not qualify. Reducing `2/500` to `1/250` preserves the
number but loses the original pair, so the example marks that conversion lossy and
retains the pair in `raw`. Display text carries locale/formatter context and is
never the default input to a copy or write.

ExifTool likewise exposes multiple value layers; its `-n`/ValueConv behavior does
not equate to exact stored bytes. That is useful behavior to preserve independently
of its API shape. [Reference value layers](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/lib/Image/ExifTool.pod)

**MDL-011 — Missing versus empty.** An absent tag has no occurrence and is established
through a complete selection result. A present value may be an empty string, empty
list, zero-length binary, zero, false, or explicit typed null. `invalid` means a
field was encountered but its interpretation failed. `unavailable` records whether
it was unrequested, unsupported, undecodable, limited by a budget, or missing a
dependency. None of these states means delete.

| Value kind | Wire representation and invariant |
| --- | --- |
| string | Unicode text without implicit normalization. Preserve original bytes/encoding when byte fidelity matters; invalid input bytes are not silently replaced. |
| integer | Canonical signed decimal string; no leading zeros or negative zero. Original integer width and encoding belong in storage/registry context. |
| decimal | Exact finite decimal lexical form, including meaningful trailing precision/exponent. No binary-float intermediate is required. |
| rational | Original numerator and nonzero denominator as signed decimal strings. Keep unreduced pairs and denominator sign. A zero denominator is an invalid value with retained storage. |
| float | IEEE binary32 or binary64 bits, written as most-significant-byte-first lowercase hex. Preserves negative zero and NaN payloads without illegal JSON numbers. |
| boolean / null | Explicit tagged values. Null is not a wildcard, omission, or deletion marker. |
| binary | Reference to a bounded binary resource. Empty bytes remain distinct from unavailable bytes. |
| datetime | Structured clock representation, precision, fraction, offset semantics, and optional known instant; see below. |
| array | Sequence or bag, with typed members. Preserve order in the representation and duplicate multiplicity in both. |
| struct | Ordered entries with expanded names and typed values. Names are unique within a valid structure; malformed duplicate properties require retained bytes and diagnostics. |
| lang-alt | Language-tagged text entries, including `x-default` when present. Preserve entry order and language spelling; uniqueness is case-insensitive. Do not invent a default entry. |
| qualified | A typed value plus expanded-name qualifiers. Qualifier names are unique; do not flatten them into text. |

**MDL-012 — XMP structure.** Namespace URIs, not document prefixes, identify
properties. `dc:subject` and another prefix bound to the same URI name the same
property. Unknown namespaces and qualifiers remain in the value tree. Flattened
aliases are views; they cannot replace the authoritative structured occurrence or
silently count the same field twice. Known RDF container semantics remain explicit.
[Reference structured XMP behavior](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/html/struct.html)

**MDL-013 — Time.** `local` holds the represented calendar/clock components at the
declared precision, using the Gregorian calendar. Validate real calendar dates and
component ranges. Do not invent missing month/day/time components or strip fractional
trailing zeros. Fractions require second precision. This draft handles seconds
00–59; retain leap-second/other exceptional source text and report unsupported or
invalid normalization until a supported conversion is specified.

`zone.kind=absent` means no offset is known and requires `instant=null`. A numeric
offset is minutes east of UTC. A complete second-precision value with a known offset
can carry a corresponding UTC `instant`; recompute and check consistency without
discarding fractional precision. Partial dates do not carry invented instants.

`utc-local-offset-unknown` is specifically the RFC 3339 `-00:00` convention: UTC
time is known but the local offset is not. It is different from an EXIF local time
with no offset. Preserve that distinction. Named-zone assumptions need a recorded
normalization rule/context; never silently use the host timezone.
[RFC 3339 section 4.3](https://www.rfc-editor.org/rfc/rfc3339.html#section-4.3)

CR3 container UTC interpretation is a format-specific conversion rule. The example
keeps its source integer, UTC interpretation, and local display separately. It also
keeps a zone-less EXIF capture time distinct. Real correctness needs controlled-timezone
fixtures in #0005. [Pinned CR3 conversion source](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/lib/Image/ExifTool/QuickTime.pm)

## Selection, comparison, and export

**MDL-014 — Coverage.** A coverage record identifies a document, namespace, and
structural prefix. `complete` means enumeration of that stated scope completed
under the reader/registry revision; it does not mean every opaque byte is understood
or all possible metadata formats are supported. Other states are partial, unread,
unsupported, or failed. A partial export must downgrade affected coverage or retain
the information needed for its narrow claim; it cannot claim omitted metadata absent.

**MDL-015 — Resolution.** Exact native-key and canonical-name selectors are examples
of boundary requests, not a complete query language. Match within explicit documents
and path prefixes. Resolve a one-match expectation to ambiguous if more than one
occurrence matches. Zero matches become absent only when coverage is complete for
the entire requested scope; otherwise they are unresolved. Matching some values in
partial coverage does not claim the result set is complete.

Never choose the first duplicate for mutation implicitly. Human summaries may select
a preferred value only when the policy and alternatives remain discoverable.
`query-iso`, `query-no-gps`, and `query-unknown-vendor` in the synthetic snapshot show
ambiguity, demonstrated absence, and unresolved absence respectively.

**MDL-016 — Equality.** Offer explicitly named comparison levels: stored bytes,
typed raw representation, normalized semantic value, and display. At raw level,
`2/500` differs from `1/250`; at numeric normalized level they can compare equal.
Bag comparison ignores order but preserves multiplicity. Sequence order matters.
Structure comparison uses expanded names; language alternatives use case-insensitive
language keys without deleting the original spelling. Unknown/invalid values do not
compare equal just because both lack normalized output.

**MDL-017 — Export fidelity.** A complete metadata export retains identities, value
states/types, provenance, diagnostics, coverage and dependency closure. Referenced
binary content must remain explicitly referenced; label whether an export needs
original sources or contains all relevant resources inline. “Loss-aware metadata
export” does not promise reconstructing an entire CR3 or retaining every XML lexical
detail. Those require source bytes and a separate preservation contract.

UTF-8 JSON must reject duplicate object member names, invalid Unicode scalar text,
bare NaN/Infinity, and values exceeding configured depth/size budgets. Preserve array
order. Do not silently coerce typed strings to numbers or fill absent values with null.
Projection and rendering cannot mutate the underlying snapshot.

## Copy and future write planning

**MDL-018 — Intent is separate.** The schema also defines `metadata-edit-intent`.
It references one immutable snapshot and contains explicit set, delete, or copy
requests. It is not an executable plan: `purpose` is always `intent-only`.
No snapshot import or report replay automatically changes media files.

`set` names a raw or normalized input view and an explicit typed value. `delete`
names the exact stored occurrence. `copy` chooses an exact source occurrence/view,
an existing target or explicit insertion location, a mapping when identities/types
change, and a loss policy. A present null or empty value can be a set request; it
never means deletion. A derived occurrence can supply an explicitly chosen value
for mapping, but is not itself a stored edit target.

The [copy example](examples/copy-intent.synthetic.json) maps the synthetic Artist
string into a new XMP creator sequence using a named, proposed mapping. The raw
metadata source remains distinct from the sidecar destination. The
[delete example](examples/delete-intent.synthetic.json) illustrates a separate
explicit deletion request. Neither example can be applied to a real file.

**MDL-019 — Planning gates.** Before producing an executable plan, #0006 must resolve
all IDs against trusted input, establish/recheck source identities, validate the
destination type and exact variant/location capability, evaluate mapping losses,
identify implicit structural changes, and prove preservation/recovery requirements.
Untrusted snapshots cannot assert their own write permission. Synthetic sources,
ambiguous selectors, invalid/unavailable copy values, derived targets, or unsupported
insertions must not become successful writes.

Array append/remove/replace, structure merge/replace, language updates, and creation
of an entirely new sidecar need explicit planner operations/policies. This card
defines the values those operations act on; #0006 specifies their transaction and
recovery behavior. Display strings are not a fallback when a typed conversion fails.

**MDL-020 — Change and diagnostics.** Every input/reference issue has a stable code,
severity, and attributable source/document/occurrence references. Do not discard
unknown content to silence a warning. Readers enforce bounds and resource limits
before constructing objects. Schema validation is necessary but insufficient:
cross-references, bounds, calendars, dependency cycles and policy require semantic checks.

Schema version 1 is a proposal. Changing identity or value meanings requires an
explicit contract revision and updated examples. The still-unimplemented CLI
envelope uses this snapshot as its payload rather than establishing a second,
inconsistent metadata model.

## Handoff boundaries

This specifies the model portion of inventory GAP-005. It does not close runtime
conversion/encoding evidence for every tag, approve all query grammar, choose
internal architecture, or finish the write-safety contract.

- #0005 should turn these invariants and synthetic edge cases into lawful real
  fixtures and oracle experiments.
- #0003 should use exact occurrence selection and the value/absence distinctions
  in help, menus, and workflow examples.
- #0006 should consume edit intents and specify capability checks, mapping losses,
  coordinated file effects, preservation, and recovery.

The schema and examples contain independently written design data. They do not
copy an ExifTool parser, runtime class model, or tag database.
