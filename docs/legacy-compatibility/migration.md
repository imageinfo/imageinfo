# Migration examples and expression boundary

Proposal `2026-10-10.1`. All commands below are illustrations, not executed sessions.
The legacy forms refer to the pinned source baseline in [the recommendation](README.md).
Native requests always pass the normal metadata and write-safety checks.

## Worked migrations

| ID | Legacy request (already tokenized by the caller) | Proposed native workflow | Reported difference or gap |
| --- | --- | --- | --- |
| MIG-001 | `exiftool -n -ISO photo.cr3` | `imageinfo metadata read --tag EXIF:ISO --values normalized photo.cr3` | Resolve the alias before a complete suggestion. Report all matching occurrences; normalized values are not exact stored bytes. |
| MIG-002 | `exiftool -XMP-xmp:Label= photo.xmp` | `imageinfo metadata delete --tag XMP-xmp:Label photo.xmp` | Preview deletion. Do not translate to `--set XMP-xmp:Label=`, which means an empty string natively. |
| MIG-003 | `exiftool -XMP-xmp:Label=Reviewed photo.xmp` | `imageinfo metadata write --set XMP-xmp:Label=Reviewed photo.xmp` | Native update requires an existing unambiguous occurrence. Legacy creation intent needs a separate insertion plan; no silent upsert equivalence. |
| MIG-004 | `exiftool -Subject+=travel photo.xmp` | Typed append intent after tag/type/destination resolution | Needs-input until list versus other overloaded semantics are known. Preserve duplicates unless deduplication was separately requested. |
| MIG-005 | `exiftool -DateTimeOriginal+=1 photo.cr3` | Explicit date/time transform after unit/shape/zone analysis | Needs-input; never guess a one-second/calendar interpretation or silently edit the sidecar. |
| MIG-006 | `exiftool -tagsFromFile source.cr3 -all:all target.cr3` | Enumerated preserve-location copy plan | Needs-input for exact occurrences, unsupported destinations and protected blocks. No blanket native copy-all suggestion. |
| MIG-007 | `exiftool -json=edits.json photo.cr3` | Inspect external import as data, report row/target matches, then construct explicit typed intent | Needs-input: reading the invocation does not authorize opening arbitrary referenced files or treating empty/null cells as delete. Exact legacy decoder is LG-002. |
| MIG-008 | `exiftool -r -j -G1 collection` | `imageinfo metadata read --recursive --output jsonl collection` | Only a workflow recommendation. Native schema, scope, hidden-file selection, duplicate handling and stream framing differ; update the consumer. |
| MIG-009 | `exiftool -overwrite_original -XMP-xmp:Label=Reviewed photo.xmp` | Native preview, then explicit apply and no-backup policy if desired | Temporary recovery still exists through finalization; strict guards can refuse. Translation itself never discards originals or applies. |
| MIG-010 | `exiftool -stay_open True -@ -` | `imageinfo batch run --stream` with native frames | New protocol, no ready-marker emulation; clients consume per-request summaries and session status. |
| MIG-011 | `exiftool -config custom.config -if EXPR photo.cr3` | Report executable configuration and expression requirements | Unsupported automatic translation. Do not load the file, interpret EXPR, or introduce a Perl runtime silently. |
| MIG-012 | `exiftool -all= photo.cr3` | Privacy inspection and explicitly scoped removal plan | Unsupported blanket translation. Retain sensor/calibration/opaque dependencies and report residual information. |

These are twelve migration acceptance cases, not twelve equivalent transformations.
MIG-001/002/003/008/009/010 can describe useful native workflows while still carrying
material differences. Exact shell quoting is outside the token-array translator;
use the [CLI walkthrough quoting guidance](../cli-walkthroughs/walkthroughs.md).

For example, the translator input for MIG-002 is a data document:

```json
{
  "schemaVersion": 1,
  "kind": "legacy-invocation",
  "id": "migration-delete-label",
  "workingDirectory": "/examples/raw",
  "arguments": ["-XMP-xmp:Label=", "photo.xmp"]
}
```

`workingDirectory` is an explicit absolute path in the caller's platform, not a
request to create a directory. The literal path above is invented. The document
omits the executable name; no program path can be supplied to run another tool.
The caller decides separately whether to submit a native preview after reviewing
the translator's findings. Complete-with-differences means a preview can be formed,
not that the eventual edit is supported on this file.

## Pure filter proposal

The following deliberately small grammar covers ordinary selection. It is a
requirements grammar, not a custom runtime framework or implementation language.
Use familiar Boolean/comparison syntax and a small fixed function set. Request
files carry it as a literal string argument; they do not introduce an evaluator
with system access.

```text
expression  = or-expression
or-expression = and-expression { "or" and-expression }
and-expression = not-expression { "and" not-expression }
not-expression = "not" not-expression | "(" expression ")" | predicate
predicate = "exists(" json-string ")"
          | "absent(" json-string ")"
          | "value(" json-string "," view ")" comparison literal
view = '"raw"' | '"normalized"'
comparison = "==" | "!=" | "<" | "<=" | ">" | ">="
literal = json-string | exact-json-number | "true" | "false" | "null"
```

Whitespace is optional between tokens but cannot split a keyword or quoted string.
`not` binds more tightly than `and`, which binds more tightly than `or`; parentheses
override that order. A grouped expression may also follow `not`. Function and
operator spellings are case-sensitive. Tag aliases resolve through a named registry
revision; unknown names and malformed expressions fail whole-request preflight.
No interpolation, regex, arithmetic, method calls or user-defined functions are in
this initial grammar. Reject trailing tokens rather than evaluating a prefix.

`exists` is true when an eligible occurrence is observed. It is false only when
the requested scope was completely enumerated and none exists; otherwise unknown.
`absent` is the three-valued negation of exists. An explicit null value is present.
`value` requires exactly one occurrence with an available value at the named view;
ambiguity, unavailable conversion or unresolved coverage yields unknown plus an
attributable issue. One observed match in an incomplete scope does not prove uniqueness.

Compare like types only. Strings use exact Unicode scalar sequences without locale
folding; numbers compare exactly (including rational values and decimal literals).
No string-to-number coercion or floating-point rounding is implicit. Null supports
equality/inequality only; lists/structures/datetimes require future explicitly typed
operators rather than comparison to display strings. Type mismatch is unknown with
an issue, not a successful inequality. Limits bound expression length/depth/work.

| Expression | true | false | unknown |
| --- | --- | --- | --- |
| `not x` | false | true | unknown |
| `false and x` | false | false | false |
| `true and x` | true | false | unknown |
| `true or x` | true | true | true |
| `false or x` | true | false | unknown |

For two unknown operands, both conjunction and disjunction remain unknown.
Evaluate left to right with short-circuiting only when the result is already
determined. A skipped branch is not scanned just to manufacture diagnostics.
Selection admits only true. False is an explicit exclusion. Unknown is reported
and fails the selection request by default; it is never silently counted as an
ordinary exclusion. Explicit continue can process independently selected inputs
but reports the unresolved input and native partial/failure status.

```text
imageinfo metadata read --where 'exists("EXIF:ISO") and value("EXIF:ISO","normalized") >= 400' photo.cr3
```

This is a new proposed `--where` grammar, not a translation of arbitrary Perl.
Duplicate ISO occurrences produce unknown rather than choosing the first. Exact
occurrence-qualified filter syntax, collection predicates, date arithmetic and
custom composite calculations remain LG-001/LG-003 until specified independently.

## Mapping and extension acceptance

Mappings declare source selectors/view/types, destination native locations/types,
explicit conversions, insertion/update/conflict policy, loss policy and revision.
Require one unambiguous destination per mutation, or an explicitly enumerated
multi-destination plan. Preserve unselected languages/structure fields; do not turn
an absent source into deletion. Validate conversions before publishing any target.
The copyright mapping in [CW-007](../cli-walkthroughs/README.md) is the first concrete
example; it does not imply a complete EXIF/XMP conversion catalog.

User definitions are inspected as data and approved through explicit configuration.
Unknown namespaces remain readable without becoming writable. Bounds, unknown-data
preservation and signature rules still apply. An executable extension, if later
chosen, must disclose its code provenance, granted authority and failure effects.
No claim of process isolation, permission isolation or safe untrusted code follows
from merely calling it a plugin.
