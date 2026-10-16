# Bounded in-memory XMP OwnerName removal (#0190)

The library function `privacy::remove_owner_name` implements the single
[R5P-026 sidecar operation](xmp-owner-removal-contract.md). Its input is one
explicit immutable byte snapshot and an opaque document ID; its output is either
borrowed original bytes for complete supported absence, a separate owned byte
vector with one property removed, or a refusal. It performs no file I/O.

## Actual boundary and supported deletion

Every call freshly runs the [bounded packet inspector](../sidecars/packet-profile.md)
and the inherited [provenance refusal](provenance-refusal.md), including an absent
target and unchanged derivative intent. No caller-supplied occurrence count,
coverage flag or permission Boolean can grant technical admission. Known coupling,
read-only packets, invalidation requests and force requests refuse. Native bytes
are inspected only when explicitly supplied to the provenance request; unspecified
native sources remain unexamined. Source-specific unknown semantic dependencies
remain distinct from the bounded lexical/model checks.

Selection uses exactly `{http://ns.adobe.com/exif/1.0/aux/}OwnerName`, independent
of prefix spelling. One description attribute or simple scalar property element
can be deleted. Empty values count. Aliases and attribute/element duplicates refuse;
there is no first-match or remove-all fallback. Nested, list or qualified targets
refuse. A selected element containing a comment or a local namespace declaration
also refuses so declaration and comment bytes are never silently deleted. Simple
text, entity spellings, CDATA and empty element forms are supported within the
packet profile. Unknown supported siblings and namespace lookalikes are retained.

The XML component supplies the whole attribute or element range. The attribute
range includes its name, equal sign and quoted value, retaining surrounding
whitespace. The element range includes its start/end tags and scalar content.
The returned occurrence binds the opaque document ID, original ordinal, expanded
name, form, decoded value and original deletion range. Ordinals are local to the
original packet and are allowed to shift in the derivative.

Construction uses a checked length subtraction and fallible exact vector
reservation. A separate output byte limit applies to changed and unchanged
results; document IDs also have an explicit byte limit. Existing packet byte,
node, depth, attribute, namespace, property, list-member and text limits bound
inspection and the fresh derivative parse. These are logical input/output bounds,
not an OS quota or an exact measurement of parser allocator overhead.

Before returning a changed candidate, the mechanism checks exact prefix and suffix
complements against the original and freshly reparses the derivative. It checks
that no selected property remains, that packet constraints remain consistent and
that all other property names, forms, values and relative order match the original
with the selected occurrence omitted. Failure returns no usable candidate. The
original bytes remain borrowed and unmodified throughout; the owned output does
not rewrite namespace declarations, packet instructions, padding or siblings.

## Finite evidence and remaining scope

`tests/xmp_owner_removal.rs` exercises actual authored bytes: attribute separators,
entities, simple/empty/CDATA elements, borrowed absence, namespace aliases and
lookalikes, duplicates, qualified/nested/list/comment/declaration refusals, malformed
input and finite input/output bounds. The provenance integration tests additionally
exercise known packet/native indicators and the no-op boundary. Authored controls
establish this finite mechanism only; actual private privacy media use remains
unrun pending the operation-specific rights and independent evidence required by
the contract. No camera-derived outcomes or reports are published here.

The original sidecar, RAW, previews, backups and external copies remain residuals.
This function supplies no filesystem publication, source identity guard, RAW edit,
arbitrary-tag operation, general lossless XMP writer, authenticity certificate,
anonymity or secure-erasure guarantee. Other catalog selectors and unknown source
couplings are not cleared by this one checked removal.
