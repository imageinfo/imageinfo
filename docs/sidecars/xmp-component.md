# Bounded XMP XML component and identity (#0081)

Decision and observation date: **2026-10-15**. Adopt **roxmltree 0.21.1** for the
standalone [research model](../../experiments/0081-xmp-model/README.md). This is a
reviewable proposal for a later production read-only slice, with actual authored
identity/limit vectors. It adds no root dependency, CLI support, runtime framework,
RAW mutation, sidecar creation, rewrite or production admission. #0083 may consume
the exact expanded-name/text model without inferring permission to serialize it.

## Component and provenance

roxmltree is an ordinary read-only XML tree. It resolves element and attribute
namespaces and exposes text, attributes and children directly; these satisfy the
small inspection need without a mutable DOM or general RDF engine. Its
[release manifest](https://docs.rs/crate/roxmltree/0.21.1/source/Cargo.toml.orig),
[parsing source](https://docs.rs/roxmltree/0.21.1/src/roxmltree/parse.rs.html), and
[API](https://docs.rs/roxmltree/0.21.1/roxmltree/struct.ParsingOptions.html)
were reviewed along with the exact cached registry packages. Official docs list
0.21.1 as the latest release when observed; this decision pins that version rather
than tracking `latest` or upstream main.

| Registry package | Packaged VCS revision | Package SHA-256 / lock checksum |
| --- | --- | --- |
| roxmltree 0.21.1 | `67644e16f43c34cadc9e163163dd1aaf7ebe205e` | `f1964b10c76125c36f8afe190065a4bf9a87bf324842c05701330bba9f1cacbb` |
| memchr 2.8.3 | `5fdb40c054e1fff359a2f7bdf7f87a13b34b465d` | `cf8baf1c55e62ffcace7a9f06f4bd9cd3f0c4beb022d3b367256b91b87513d98` |

The `.crate` SHA-256 values were measured locally and match the standalone
[lockfile](../../experiments/0081-xmp-model/Cargo.lock). The packaged
`.cargo_vcs_info.json` files supply the revisions; no repository-head equivalence
or publisher signature is claimed. roxmltree declares MIT OR Apache-2.0, author
Yevhenii Reizner, Rust 1.60 minimum, and one normal dependency `memchr ^2`.
memchr declares Unlicense OR MIT, authors Andrew Gallant and bluss, Rust 1.61
minimum. **MIT is selected for both**, retaining the exact package MIT notices in
[notices](../../experiments/0081-xmp-model/notices/). Redistributed binaries must
carry these notices; the root project's MIT license does not replace them.

roxmltree's own source additionally acknowledges heavily modified `ego-tree` tree
lineage under ISC. Its package contains MIT/Apache files but no separate ISC file.
The retained notice records the
[historical v0.6.2 notice](https://raw.githubusercontent.com/causal-agent/ego-tree/v0.6.2/LICENSE)
and [current upstream attribution](https://raw.githubusercontent.com/causal-agent/ego-tree/master/LICENSE),
including both historical/current author spellings. The exact original fork
revision is not identified by the package; this is recorded rather than invented.
There is no ego-tree linked dependency. Retain the ISC notice with downstream
redistributions as well; root production adoption still needs ordinary review.

Chosen features are roxmltree `std`, with default features disabled. Position
storage is unnecessary because this slice retains the complete immutable source;
it makes no property-offset claim. The resolved graph is exactly roxmltree and
memchr; enabled memchr features are `std` and `alloc`. No optional logging/core
dependency, dev dependency, build script dependency or native library is enabled.
roxmltree forbids unsafe code; memchr contains optimized unsafe implementation.
The research wrapper forbids unsafe code, and does not claim that this forbids
unsafe code inside dependencies. No dependency change reaches root production.

## Bounded implemented slice

`inspect(&[u8], Limits) -> Result<Packet, Refusal>` borrows caller bytes after UTF-8
validation. It never opens paths, follows namespace URIs, resolves resources or
fetches entities. Caller input must already be read with an independent byte bound;
this API cannot undo an oversized allocation made by its caller. UTF-16/legacy
encoded bytes are not transcoded. UTF-8 XML parsing is component behavior, not an
encoding conversion promise based on an XML declaration.

The parser receives `allow_dtd = false`, `entity_resolver = None` and an explicit
node limit. The API documentation still describes an empty-DTD exception, but the
exact 0.21.1 tokenizer refuses every document type before parsing it when
`allow_dtd` is false; its changelog records the empty-DTD fix in 0.19.0. Actual
nonempty/empty/internal/external DTD vectors confirm refusal. The wrapper uses this
component behavior directly; DOCTYPE text inside a comment or CDATA remains inert
text, with explicit acceptance vectors. No second XML tokenizer is introduced.
Unknown entity references and malformed XML refuse. XML predefined and numeric
references are decoded; CDATA and adjacent text separated by comments concatenate.
This is semantic text, not the original lexical bytes. Original source remains
available separately. No callback or URL loader is installed.

| Bound | Default | Enforcement |
| --- | --- | --- |
| Input bytes | 65,536 | Before UTF-8 validation/tree creation |
| XML nodes (including root, text, comments and PIs) | 2,048 | During component parsing |
| Element depth (root element = 1) | 16 | After bounded tree creation, before model extraction |
| Parsed attributes per element | 32 | After bounded tree creation; namespace declarations are not attributes in this API |
| Properties | 128 | Before each model insertion |
| Members per list | 128 | Before each model insertion |
| Decoded UTF-8 bytes per text value | 8,192 | Before extending a model text or copying attribute text |

Limits are explicit caller parameters in this research API; callers can lower
them. These are logical bounds, not exact allocator/RSS, CPU-time or cancellation
guarantees. Attribute/depth limits are checked after parsing; the byte/node bounds
remain the preconditions for the tree allocation. Namespace declarations, names
and aggregate text remain bounded by input bytes; the node cap is not an attribute
or namespace cap. No tiny constant-memory or streaming claim is made.

Accepted shape: one `rdf:RDF`, optionally inside `x:xmpmeta` with optional
`x:xmptk`, containing exactly one `rdf:Description`. `rdf:about` may be absent or
empty. Simple namespaced description attributes and property elements are read.
Elements may contain simple text or one `rdf:Seq`, `rdf:Bag`, or language `rdf:Alt`
containing simple `rdf:li` text. Empty text/list is distinct from missing property.
Comments/PIs are retained only in source; whitespace between structural elements
is ignored. Mixed structural text, multiple subjects, nonempty `rdf:about`, bare
property names, RDF/XML infrastructure used as property names, structures,
resource/datatype/parseType forms, nested lists and qualifiers outside the exact
language case refuse the entire extraction. There is no partial success that
silently omits an unknown field. This bounded subset is not a full RDF/XMP validator.

## Typed identity and unknown namespaces

The [implementation](../../experiments/0081-xmp-model/src/lib.rs) uses ordinary
Rust records/enums, consistent with [MDL-002/004/011/012](../metadata-model/README.md).
It does not serialize the external metadata contract or register friendly aliases.

| Type/identity | Rule |
| --- | --- |
| `ExpandedName { namespace, local }` | Exact resolved namespace URI and local name; prefix spelling is not identity. No URI case folding, slash repair, percent decoding or Unicode normalization. |
| `Property { ordinal, name, form, value }` | Zero-based packet traversal ordinal is occurrence identity in this extraction. Description attributes in source order precede child properties in document order. Equal names/values remain separate occurrences. XML attribute duplicate names are a parser error. |
| `Form::Attribute / Element` | Preserve representation origin; equivalent names do not erase attribute/element occurrences. |
| `Value::Text / List` | Text remains text; no date, number or alias inference from a name. |
| `Container::Sequence / Bag / LanguageAlternative` | Container semantics remain typed. Sequence position is significant; bag order records observed serialization and duplicates remain. |
| `Member { position, language, text }` | One-based serialized member position, scoped to its containing property occurrence. Reordering source creates a new observation, not a stable cross-edit member identity. |
| `Language { spelling, key }` | Preserve spelling; ASCII lowercase key checks uniqueness. No inferred default/fallback language or locale matching. |

Unknown namespace properties are accepted with exactly the same primitive/list
rules as known namespace properties. `urn:unknown/` and `urn:unknown` remain
different. Two prefixes for one URI name the same property definition but retain
their separate occurrence ordinals. Unknown qualifiers/structured shapes cause
explicit whole-packet refusal; the caller still owns original bytes. Successful
inspection therefore preserves unknown primitive/list identity and source, while
making no complete unknown-tree or rewrite preservation claim. Unsupported bytes
must remain available to the caller for diagnostics, never treated as absent.

The language subset is intentionally narrower than BCP 47: `x-default`, or a
two/three ASCII-letter primary optionally followed by a two-letter region or
three-digit region. Comparison is case-insensitive. Script/variant/private/grandfathered
tags outside this subset refuse, even if valid under a larger language standard.
Each Alt member requires exactly `xml:lang`; duplicate lowercase keys refuse.
`x-default`, if supplied, must be first. No default is synthesized. Empty Alt is
retained as an empty list. This uses the existing contract's case-insensitive
uniqueness rule and Adobe's language-alternative behavior, with explicit subset
limits rather than an incomplete claim of full language validation.

## Vectors and verification

[Authored vectors](../../experiments/0081-xmp-model/tests/vectors.rs) assert:

- Exact typed results for prefix aliases, duplicate properties, unknown URI
  distinctions and empty values; description-attribute versus element origin.
- Seq/Bag member positions, order and duplicate multiplicity; language Alt order,
  original language spelling and lowercase identity.
- Duplicate language, misplaced default, out-of-subset language, unknown
  qualifiers, structures, mixed content, RDF resource/parseType, absent namespaces,
  multiple subjects and malformed/duplicate-attribute XML refusals.
- Predefined/numeric entities, CDATA/comment text splitting, invalid UTF-8,
  unknown entities, all DTD forms, optional wrapper and retained packet PIs.
- Exact accepted boundary and one-over refusal for each configurable logical
  budget (using reduced limits to make the boundary unambiguous).

The pinned-toolchain standalone fmt, Clippy with denied warnings, nine test
functions and release build are required verification for this component; exact
results are reported in the handoff. Real sidecar/camera corpus, fuzzing, allocator
instrumentation, full RDF/XMP and language conformance, lossless round-trip and
production integration are unrun. No write or pairing result follows from this
read-only experiment.

## Primary semantic references

Observed 2026-10-15; references are used for behavior, with no copied tag table or
upstream parser/specification implementation:

- [Namespaces in XML 1.0, Third Edition](https://www.w3.org/TR/2009/REC-xml-names-20091208/),
  W3C Recommendation 2009-12-08: expanded names and default namespace behavior.
- [RDF 1.1 XML Syntax](https://www.w3.org/TR/2014/REC-rdf-syntax-grammar-20140225/),
  W3C Recommendation 2014-02-25: property attributes/elements and RDF container
  membership syntax; this slice implements only the explicitly listed shapes.
- [Adobe XMP data types](https://developer.adobe.com/xmp/docs/xmp-namespaces/xmp-data-types/),
  live official reference (no displayed revision): empty Unicode text and language
  alternatives, including uniqueness and first `x-default` position.
- [Adobe XMP specifications](https://developer.adobe.com/xmp/docs/xmp-specifications/),
  live official index (no displayed page revision): Part 1 data model/serialization
  context. This experiment does not claim ISO certification or full conformance.
