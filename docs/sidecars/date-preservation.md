# One-date XMP no-op and lexical preservation (#0084)

Implemented and observed **2026-10-15**, in the standalone
[preservation experiment](../../experiments/0084-xmp-preservation/README.md).
This qualifies one finite, in-memory derivative mechanism for the
[#0083 version-1 original-date mapping](date-mapping.md). It does not adopt a
production XMP parser/writer, create a sidecar, modify RAW, open files or publish
outputs. All results explicitly retain `production_mutation_allowed = false`.
#0085 and the umbrella retain their independent admission/storage requirements.

## Exact admitted research intent

`prepare(input, original_snapshot, selected_target_ordinal, conflict_policy)`
first runs the bounded [#0081 inspection](xmp-component.md) on the actual immutable
input bytes, then recomputes #0083's comparison. The caller cannot pass a forged
`Comparison` as permission to edit a different packet. It must select the unique
existing XMP `{http://ns.adobe.com/exif/1.0/}DateTimeOriginal` property and satisfy
the original-snapshot source identity/coverage/date/fraction/offset requirements.
Only a fresh `NoOp` or explicitly selected, loss-acknowledged `ReplaceIntentOnly`
can produce a result. `KeepDestination`, default conflict refusal and loss refusal
produce distinct typed decision refusals without any candidate buffer returned.

The raw/source snapshot is still caller-provided research data. Its IDs/coverage
boolean are not authenticated, and this function has no native RAW adapter, live
pair binding or trust import policy. The separately selected
[RAW–sidecar pair](pairing.md) never grants write authority. This ticket qualifies
bytes and the finite structural interpretation below, not those missing admissions.

## Actual no-op behavior

After bounded inspection and successful #0083 comparison, an exact mapped date
match returns `Kind::NoOp`, `Cow::Borrowed(input)` and no changed range. It returns
the same byte slice; no serializer, lexical normalization or replacement allocation
is invoked. This branch precedes the changed-target lexical restrictions: an
already-correct date represented using XML character references, CDATA or
comment-separated text can remain byte-exact. Authored tests compare full bytes,
length and borrowed pointer identity, including those unusual target spellings.
No-op is exact mapped text equality, not instant/normalized date equality.

## One parser-bound lexical replacement

For `ReplaceIntentOnly`, the experiment obtains actual positions from a second
roxmltree parse with `allow_dtd = false`, no entity resolver and the same node
budget. The direct dependency pins the already reviewed **roxmltree 0.21.1** with
`std` and `positions`; this feature union is confined to the standalone research
graph. The [standalone lock](../../experiments/0084-xmp-preservation/Cargo.lock)
contains only the two sibling research crates, roxmltree and memchr **2.8.3**.
Registry checksums and MIT/ISC notices remain those of the
[#0081 review](xmp-component.md); no new third-party package or root dependency is
introduced. Enabling positions increases per-node/attribute storage, with the
same bounded input/node denominator; no exact RSS guarantee is made.

The property is located by its exact expanded name inside the single admitted
`rdf:Description`, after #0083 has verified its unique occurrence and selected
ordinal. It never substitutes a friendly name or searches source text for a
matching date. The target may be:

- A description attribute: its parser `range_value()` excludes the preserved
  attribute name, spacing and quote delimiters.
- A property element with exactly one text child: that child's parser range is
  the candidate lexical value range; surrounding element markup is preserved.

The raw source slice at the candidate range must **exactly equal the previously
decoded valid date text**. References, CDATA delimiters, comment/PI splits and
other lexical structure in a changed target refuse with `LexicalTarget`; this
small mechanism has no serializer/escaping policy for them. The same structures
in unchanged siblings remain byte-preserved where #0081 accepts their shape.

The mapped value is at most 35 bytes of the exact ASCII date alphabet
`0–9`, `-`, `:`, `T`, `.`, `+`. The experiment checks that alphabet before use, so
a future mapping expansion cannot accidentally introduce XML syntax through this
mechanism. Checked length arithmetic precedes one bounded candidate allocation.
The replacement consists only of original prefix, mapped date and original
suffix. It may change length; there is no fixed-width/packet-padding assumption.

## Independent byte and semantic checks

Before returning a derivative, the implementation compares the complete prefix
and suffix against the original, with the suffix shifted by the exact length
delta. It reparses the derivative through #0081, constructs an expected semantic
property list from the original with only the selected text changed, and requires
the entire resulting list to match. Property order/form/ordinals, duplicate
multiplicity, unknown expanded names, values, list kinds, member order and language
identity all remain equal outside that one value.

`Prepared.changed` contains zero-based half-open original and derivative ranges
for the **whole lexical date value**, not just bytes which differ. The complement
outside these corresponding ranges is exact. Quotes, namespace declarations,
prefix aliases, unrelated property text/attributes, XML whitespace/line endings,
comments, packet instructions and padding outside the date range remain their
original bytes. The input slice is immutable throughout. The implementation never
reserializes a document and reports no incidental XML reserialization changes.

These are byte/model preservation claims for the admitted subset. They do not
establish that changing this date has no unknown semantic dependency, signature,
checksum or application-specific consequence. A namespace URI is never fetched.
Unknown checksum/authenticity dependencies and complete XMP conformance require
their own evidence before any production write; these passing cells cannot grant it.

## Explicit limits and refusals

Input and derivative each have the fixed #0081 default **65,536-byte** bound.
Before extraction, the same 2,048 XML-node, depth-16 and parsed-attribute-32 limits
apply, along with 128 properties/members and 8,192 decoded bytes per text. The
depth/attribute checks remain post-tree checks; these are logical bounds, not
streaming, deadline, allocator quota or filesystem limits. A growing date which
would exceed the derivative bound refuses before allocating that derivative.

Inherited #0081/#0083 refusals include malformed/non-UTF-8 bytes, DTDs/entities
outside supported XML references, multiple descriptions, unsupported qualifiers or
structures, missing/duplicate/list-valued target, wrong/stale selected ordinal,
incomplete original source coverage, malformed dates and unacknowledged losses.
Entities in an otherwise supported target can be inspected and no-op, while an
actual replacement refuses their lexical shape. No fallback serialization,
property insertion, second-field edit or implicit sidecar creation occurs.

UTF-8 source is validated, with no encoding conversion. The component's XML
declaration parser validates attribute ordering, not all declaration values;
successful tree parsing is not a full XML declaration/encoding or ISO XMP
conformance certificate. Declaration/packet instructions remain original bytes,
never an authority to reopen, mutate or publish anything. A future file profile
must resolve its declaration/packet conventions independently.

## Lawful finite evidence

The committed [qualification tests](../../experiments/0084-xmp-preservation/tests/qualification.rs)
are independently authored synthetic XML and invented dates under the project
MIT license. Each candidate is a separately owned in-memory derivative of those
lawful authored bytes. This makes the pass evidence reproducible without importing
private media, upstream fixtures, tag tables or reference-generated sidecar text.

Actual executed cells include full-byte borrowed no-ops, element/attribute target
derivatives, shorter/longer lexical date replacements, unknown simple/list sibling
complement checks, namespace alias/default/rebinding cases, quote styles, semantic
target-only reparses, lexical-target refusals and input/output limits. The
independent qualification record binds exact scope and counts; there is no claim
of a real-camera corpus pass, XML round-trip support or production storage profile.

The [executed qualification record](../../experiments/0084-xmp-preservation/qualification.json)
reports **14 test functions and 33 actual `prepare` calls**: nine derivatives with
exact complements and semantic reparses, five full-byte/pointer no-ops and nineteen
refusals. These counts describe authored inputs only; repeated calls are not
additional independently sourced fixtures.

Existing restricted camera/sidecar references remain under private local-only
grants; their records forbid source/release/report publication. No private input
contributes to this public pass or refusal denominator. Private bytes, private
hashes, filenames, identifying metadata and native camera results are excluded.
Any separate permitted read-only review stays private and cannot qualify this
mechanism's production behavior or expand the existing reference-only admission.

The pinned standalone fmt, denied-warning Clippy, authored test suite and release
build, plus repository documentation checks, are required for the handoff. RAW
editing, sidecar creation/publication, adversarial filesystem races, receipts,
crashes/restart actions and real-camera XMP preservation remain unrun here.
