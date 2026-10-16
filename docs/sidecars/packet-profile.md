# Bounded production XML/XMP packet profile (#0183)

Implemented **2026-10-16** in [the in-memory library](../../src/xmp.rs), with
[authored tests](../../tests/xmp_packet_profile.rs). This adopts one positive,
finite packet inspection profile, not full XML/RDF/XMP conformance. There is no
path opening, network resolution, XML serializer, encoding conversion, media
inspection, output creation or publication. The existing [#0081](xmp-component.md)
and [#0084](date-preservation.md) experiments and their historical results remain
unchanged. Their authored identity/preservation cases supply prior evidence,
not production file admission.

## Exact envelope and lexical profile

`xmp::inspect(bytes, Limits)` retains the complete immutable UTF-8 source and
returns typed properties, packet mode and concrete coupling observations. Packet fields are private and exposed through borrowed getters, so callers cannot
clear an observed coupling or alter mode/source before its constraint check. Input
may have one leading UTF-8 BOM. UTF-16/32, invalid UTF-8 and a second leading BOM
refuse. An XML declaration is optional. The only supported declaration grammar is
`<?xml version=Q1.0Q[ encoding=QUTF-8Q][ standalone=Qyes|noQ]?>`, where each `Q`
pair independently uses matching single or double quotes, brackets denote optional
fields, and each displayed separator is exactly one ASCII space. No space around
`=`, trailing space, alternate encoding case, XML 1.1, other version, duplicate or
reordered fields is admitted. Otherwise-valid XML declarations outside this
finite syntax explicitly refuse. Declaration success never overrides actual UTF-8
validation. The component checks placement and declaration syntax; the wrapper
checks the finite supported values and spellings.

A bare XML packet has no processing instructions. A wrapped packet has exactly
two PIs outside its document element: one preceding begin instruction and one
following end instruction. The begin spelling is
`<?xpacket begin=QQ id=QW5M0MpCehiHzreSzNTczkc9dQ?>` or the same with one actual
U+FEFF between the `begin` quotes. Each quote pair independently uses matching
single or double quotes. The end is exactly `<?xpacket end=QwQ?>` or
`<?xpacket end=QrQ?>`. Other IDs, missing/extra instructions, instructions inside
the tree, alternate spaces/fields and other PI targets refuse. Ordinary XML
whitespace, comments and padding remain original bytes. Mode `r` is inspectable
but `check_edit_constraints()` refuses it, including requests to create a new
output from an unchanged packet. This implementation does not consume padding or
promise fixed packet length.

Element/attribute/namespace declaration QNames are restricted to ASCII NCNames:
start `[A-Za-z_]`, continuation `[A-Za-z0-9_.-]`, with at most one colon and two
nonempty valid parts. Valid Unicode XML names are outside this profile. Namespace
bindings, duplicate expanded attributes and matching end tags are checked by the
component. The wrapper additionally refuses reserved `xmlns:xmlns` declarations
and XML-1.0 prefixed namespace undeclaration, which the component accepts; prefix rebinding retains the resolved URI,
not prefix identity. All references remain the component's responsibility except
that the wrapper also requires numeric references to represent actual XML 1.0
characters, excluding surrogate/out-of-range scalars. Only predefined XML names
and valid numeric references can succeed without a DTD. Every DTD refuses, with
no external resolver installed. Comments and CDATA are inert for reference/name
validation; their spelling remains retained. Structural whitespace means the
four XML whitespace characters, not arbitrary Unicode whitespace.

This narrow supplement is necessary because the exact pinned [tokenizer source](https://docs.rs/crate/roxmltree/0.21.1/source/src/tokenizer.rs)
`consume_qname` tests ASCII name continuation at the initial byte, and
`consume_reference` replaces non-Unicode scalar numbers with U+FFFD. Successful
component parsing alone therefore cannot enforce this profile. Post-parse lexical
checks only validate these named gaps and the namespace gaps above and the finite envelope; they do not replace
the component's syntax, namespace, nesting or entity parser. The tests include
actual supplementary-plane text, malformed name starts, namespace declarations,
invalid numeric scalars and inert CDATA/comments.

## Shape, identity and bounds

The [#0081 shape and identity rules](xmp-component.md#bounded-implemented-slice)
are now implemented directly in the production module: one `rdf:RDF`, optionally
inside `x:xmpmeta`, exactly one empty/absent-subject `rdf:Description`, simple
namespaced attribute/element properties, and simple Seq/Bag/language Alt lists.
`x:xmptk` is the only wrapper attribute; `rdf:about` must be absent or empty.
Unsupported resource/structure/qualifier/mixed-content forms refuse the entire
packet. No unknown field is silently omitted. Expanded URI/local names, property
ordinals, attribute/element form, list kind, one-based member positions,
duplicates and language spelling/lowercase identity are retained. Language tags
use #0081's explicitly bounded subset, with unique Alt keys and first x-default.

| Logical bound | Default | Enforcement |
| --- | --- | --- |
| Input bytes | 65,536 | Before UTF-8 or parsing |
| XML nodes | 2,048 | Component parser, includes document/text/comments/PIs |
| Element depth | 16 | After bounded tree; root element depth 1 |
| Attributes per element | 32 | After bounded tree; namespace declarations excluded |
| Namespace declarations per element | 32 | Lexical count after bounded tree, includes repeated declarations |
| Property occurrences | 128 | Before model insertion |
| Members per list | 128 | Before model insertion |
| Decoded text bytes per value | 8,192 | Before model copy/extension |

Callers may supply explicit bounds; default values are the adopted profile for
ordinary callers, not allocator/RSS, deadline or cancellation guarantees. Names,
namespace declarations and total tree storage also depend on the input bound.
Depth and attribute checks do not prevent the initial bounded tree allocation.
Tests exercise every bound at its exact accepted value and one over using reduced
budgets; the input default and oversized source also have explicit coverage.

## Concrete coupling observations and edit constraints

Inspection does not claim that unknown namespaces are harmless. Unknown primitive
or list siblings keep their complete original bytes and exact semantic identity;
their application semantics remain unverified. A successful
`Packet::check_edit_constraints()` is only a necessary local profile check. It
neither grants an edit nor proves absence of unknown dependencies. Any later
candidate needs actual source-specific impact review and its ordinary intent,
preservation, binding and storage checks. There is no hypothetical universal
hidden-checksum proof requirement or arbitrary checksum invention.

The actual pinned component reads names/text and resolves no namespace URI or
application data. It verifies no signatures/checksums/provenance. The authored
#0081/#0084 packets contain no declared scheme in the following table; this
observes only those public finite sources, not camera packets. Concrete declared
namespaces trigger conservative edit refusal, even when declared but unused:

| Exact declared URI | Observation and unresolved edit consequence |
| --- | --- |
| `http://www.w3.org/2000/09/xmldsig#` | XML Signature scheme; no signed coverage or validity check |
| `http://ns.adobe.com/xap/1.0/mm/` | Media-management incarnation/history/relationship scheme; no ID/history maintenance |
| `http://ns.adobe.com/xap/1.0/` | XMP basic scheme includes MetadataDate; no companion-date impact policy |
| `http://ns.adobe.com/xmp/note/` | Extended-XMP linkage scheme; no external packet/digest reconstruction |
| `http://ns.adobe.com/photoshop/1.0/` | Application history/date-reconciliation scheme; no application-specific coupling update |

A matching declaration is an indicator, not proof that all properties in the
namespace are coupled or that a valid credential exists. Shapes too complex to
inspect still refuse rather than reporting clean absence. Unknown aliases or
other schemes are outside detector coverage. Detection supplies neither loss
consent nor automatic stripping/invalidation. The existing
[known-provenance policy](../privacy/known-provenance-policy.md) remains distinct;
this slice uses its conservative refuse-before-effects behavior and makes no
cryptographic claim. No private source bytes or outcomes entered these tests.

Primary semantic references checked 2026-10-16: [XML 1.0 Fifth Edition](https://www.w3.org/TR/2008/REC-xml-20081126/),
[Namespaces in XML](https://www.w3.org/TR/2009/REC-xml-names-20091208/),
[XML Signature 1.1](https://www.w3.org/TR/2013/REC-xmldsig-core1-20130411/),
[Adobe XMP basic](https://developer.adobe.com/xmp/docs/xmp-namespaces/xmp/),
[media management](https://developer.adobe.com/xmp/docs/xmp-namespaces/xmp-mm/),
and [XMP specifications](https://developer.adobe.com/xmp/docs/xmp-specifications/).
[Adobe toolkit XMPUtils.cpp](https://raw.githubusercontent.com/adobe/XMP-Toolkit-SDK/main/XMPCore/source/XMPUtils.cpp)
was also inspected for `PackageForJPEG`: it computes a digest over extended XMP
and stores `HasExtendedXMP`. [ReconcileLegacy.cpp](https://raw.githubusercontent.com/adobe/XMP-Toolkit-SDK/main/XMPFiles/source/FormatSupport/ReconcileLegacy.cpp)
contains an actual `photoshop:DateCreated` fallback from `exif:DateTimeOriginal`.
These upstream application behaviors motivate conservative scheme-level refusal;
they do not establish the semantics of every packet or permit JPEG work here.
Only facts were recorded; no upstream code was copied. These live `main` source
observations have no pinned commit claim. Live Adobe references expose no pinned page revision; these are identifier and
semantic observations, not imported implementation or conformance certification.

## Dependency and verification boundary

Adopt exact roxmltree **0.21.1**, default features disabled, features `std` and
`positions`. Its only linked dependency is already-locked memchr **2.8.3** with
`std`/`alloc`. No new resolver, native library, framework or build script is added.
Root `unsafe_code = forbid` remains; optimized dependency unsafe code is not
covered by that root lint. Position storage is enabled for ordinary downstream
lexical inspection, but this API returns no editable range or derivative.

The [root inventory](../foundation/dependencies.json) binds package checksums,
packaged revision and [MIT notice](../../licenses/dependencies/roxmltree-0.21.1-LICENSE-MIT.txt).
MIT is selected for roxmltree and memchr; retain the existing memchr notice and
[ego-tree ISC lineage attribution](../../licenses/dependencies/roxmltree-0.21.1-ego-tree-ISC.txt)
for redistribution. #0081's missing original fork-revision limitation persists.
The root lock adds only roxmltree; existing package versions remain unchanged.
The standalone #0021/#0027/#0088/#0104 research lockfiles also record the new
dependency edge of their path-dependent root library. Their locked builds must
remain reproducible. This updates dependency resolution only; old source/lock
qualification identities and media observations retain their historical scope.

Focused authored tests, root fmt/Clippy/tests/release build, graph/notice inventory
and documentation checks are the verification gates. This is finite authored
positive/refusal evidence; real-camera media, source authenticity, complete XMP,
fuzzing, serialization, derivative publication and storage/recovery remain outside
the implemented claim. Historical research crates remain independently buildable
and are not linked into production.
