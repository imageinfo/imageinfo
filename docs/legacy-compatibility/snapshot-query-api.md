# Current native snapshot, query and discovery API qualification

Ticket #0134 qualifies 22 actual public Rust consumer cases for the existing
bounded R5 read slice. These freeze finite MAP-027, MAP-028 and MAP-031 cells
from [#0121's inventory](native-token-inventory.md). They do not implement the
reference API, establish Perl ABI/object-model compatibility, or close those
families' residual requirements.

The consumer suite is `tests/public_snapshot_api.rs`. It imports the published
crate modules and uses independently authored structural fixtures from the
unchanged `tests/support/mod.rs`; no camera media is involved. Run it with
`cargo test --test public_snapshot_api`. The initial native Windows run passed
all 22 cases with none ignored. Cross-platform qualification requires the
corresponding hosted checks; this native observation alone supplies none.

## Ownership and lifetime

`reader::read` returns caller-owned `Metadata`; it retains decoded values,
occurrence identities and ranges without retaining the input reader or a live
file handle. `select(&Metadata, ...)` and `Metadata::snapshot(&self, ...)` query
that retained state. Case C01 writes a valid authored source, reads it once,
replaces its bytes, confirms a fresh read fails, deletes the source, confirms
`INPUT_IO` on another fresh read, and repeats identical retained queries after
both changes. C02 overwrites and drops the caller's input stream before querying.
These are actual lifetime witnesses, separate from query-result comparisons.

The current Rust types expose public mutable fields: immutability means these
queries operate through shared references and leave the retained observations
unchanged; it is not an opaque, enforced immutable object model. A caller can
edit `Metadata` or its returned JSON. C03 checks query stability; C04 checks that
owned projected JSON survives metadata destruction and that editing one owned
JSON value leaves its clone unchanged. Caller-created or edited metadata is not
authenticated. `snapshot` expects valid indices and reader-consistent binary
occurrences; malformed caller construction is outside this qualification.

Binary values retain source-range references, not copied payloads. Source deletion
does not prevent metadata projection, but it does not make referenced preview or
opaque bytes available or authorize a later reopen. Caller-supplied snapshot IDs
and display paths are labels. Source identity remains unavailable; no live guard,
source hash, mutation authority, storage profile or writer is established.

## Named API headings and exact native differences

The names below are #0121 reference headings, not exported method names.

| Heading | Existing public native cell | Explicit residual |
| --- | --- | --- |
| `ImageInfo`, `ExtractInfo` | `reader::read` / `read_file` produce bounded owned observations; `read_request::execute` produces the read result envelope. | No reference signatures, overloads, arbitrary source forms or complete extraction lifecycle. Structural/profile errors return an error rather than a general recoverable partial extraction object. |
| `GetInfo` | `reader::select` and `Metadata::snapshot` repeatedly project retained observations. | No stateful reference object, query builder or generic projection service. |
| `GetTagList` | Selection indices enumerate every matching observed occurrence in source order. Repeated selectors do not duplicate occurrences. | No requested-tag list service or alternate reference sorting conventions. |
| `GetFoundTags`, `GetRequestedTags` | Caller retains the requested selector strings; selection indices identify observed matches. Known selectors with no match return an empty vector. Unknown selectors refuse the whole query. Coverage remains partial. | No distinct requested/found result API or per-selector status. JSON `selections` is empty, including when selectors were supplied. A mixed found/unobserved query does not enumerate the unobserved request or prove global absence. The request envelope emits `TAG_UNRESOLVED` only when the entire observed selection is empty. |
| `GetValue` | Occurrence `Value`, `text_value`, and snapshot raw/normalized/display representations cover integers, rationals, text and binary references. | No generic conversion pipeline or all reference return conventions. Normalization here preserves the exact stored value. |
| `GetTagID`, `GetTagName [static]` | Native ID, namespace, canonical name, path, source range and source-order ordinal remain visible. The two declared dimension aliases resolve through `selector`. | No generic native-ID dictionary, arbitrary alias lookup or globally stable occurrence IDs across fresh reads. |
| `GetGroup`, `GetGroups` | Each projected occurrence exposes its metadata-family namespace and structural path. | No group-family query/enumeration service or full upstream group axes. |
| `GetDescription` | Display formatting covers finite value mappings. | No localized tag-description API; display text does not replace identity. |
| `GetAllTags [static]` | `reader::NAMES` lists 20 finite canonical selector names independently of observed presence. | No complete tag dictionary, metadata shapes, all namespace definitions or dynamic definitions. |
| `GetShortcuts [static]` | `selector` recognizes the two dimension aliases. | No shortcut enumeration/expansion service. |
| `GetAllGroups [static]` | Finite accepted namespace prefixes can be passed to `selector`. | No static group definition service. |
| `GetFileType [static]` | A successful bounded read recognizes the declared CR3/R5 profile from contents, even with an unrelated extension. | No generic file-type detection API or proof that an arbitrary CR3 variant is supported. |
| `GetWritableTags [static]`, `GetDeleteGroups [static]`, `CanWrite [static]`, `CanCreate [static]` | No corresponding public discovery query is qualified here. | Static read definitions and successful reads confer no write/delete/create eligibility or per-target admission. These headings remain explicit native differences. |

## Authored consumer denominator

Exactly 22 test functions form this qualification. Assertions within a case are
parts of that case, not additional hidden denominator entries.

| Case | Actual consumer evidence |
| --- | --- |
| C01 | Source replacement/deletion, fresh-read failures and repeated retained projections. |
| C02 | Input stream overwritten and dropped; decoded text remains owned. |
| C03 | Repeated queries preserve the full projection and captured bytes-read count. |
| C04 | Projected JSON outlives metadata and caller edits remain local to the owned value. |
| C05 | Unqualified ISO selects both EXIF and CTMD occurrences with distinct ranges. |
| C06 | Qualified ISO selectors preserve exact native IDs and distinct structural paths. |
| C07 | Repeated/reordered requests preserve source order without duplicate matches. |
| C08 | Subset projection retains original occurrence IDs, ordinals and namespace grouping. |
| C09 | Dimension alias selects the canonical occurrence. |
| C10 | Supported but unobserved namespace yields no occurrence under partial coverage. |
| C11 | Unknown name, namespace and unsupported case spelling refuse. |
| C12 | Mixed known/unknown query refuses without changing caller request or later queries. |
| C13 | Empty selectors mean all observed occurrences; coverage stays partial. |
| C14 | Native integer, exact JSON value and finite display mapping remain distinct. |
| C15 | Rational numerator/denominator remain unreduced; display is separate. |
| C16 | Date text remains literal; omitted display is unavailable. |
| C17 | Zero denominator yields invalid views, an issue and exact retained byte origin. |
| C18 | Binary value references a source range without a payload or hash. |
| C19 | Caller labels coexist with observed basis and unavailable source identity. |
| C20 | Exact 20-name declaration, alias exclusion and reader/capability revisions. |
| C21 | Valid contents with unrelated extension succeed; invalid `.cr3` contents refuse. |
| C22 | Actual request/result distinguishes a fully unobserved supported selector from an unsupported selector. |

The resource-lifetime review must consider both owned decoded values and borrowed
source-resource semantics. No binary materialization after deletion, arbitrary
public-field construction, extraction parity, comprehensive resource bound,
concurrent invocation, persistent session or serialization-import compatibility
is claimed. #0135 owns concurrent caller qualification; the remaining API and
discovery scopes stay with #0015, #0117 and their recorded owners.
