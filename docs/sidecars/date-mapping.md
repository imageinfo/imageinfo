# One explicit RAW-to-XMP original-date mapping (#0083)

Decision proposal and observation date: **2026-10-15**. Versioned mapping ID:
**`r5-cmt2-original-to-xmp-exif-original/1`**. The
[test-only model](../../experiments/0083-xmp-date-mapping/README.md) implements a
finite comparison and conflict decision. It produces intent-only data with
`production_mutation_allowed = false`; it cannot serialize XML, create a sidecar,
edit RAW, or authorize storage effects. #0084 retains no-op/unknown-data preservation
qualification. Production parser/planner adoption and sidecar writes remain open.

The concrete product proposal is **one explicit mapping per request, default
refusal on a differing destination, with explicit keep or named-target replacement
alternatives**. There is no default synchronization or implicit copy operation.
This proposal needs no global choice between overwriting RAW or XMP: direction is
fixed, and each differing existing value requires its own conflict selection.
Acceptance of this bounded specification does not accept a production write policy.

## Exact field selection and prerequisites

| Role | Exact identity |
| --- | --- |
| Primary source | One selected Canon EOS R5 full RAW CMT2 EXIF `0x9003` DateTimeOriginal occurrence |
| Fraction companion | Zero or one same-original-CMT2 EXIF `0x9291` SubSecTimeOriginal occurrence |
| Zone companion | Zero or one same-original-CMT2 EXIF `0x9011` OffsetTimeOriginal occurrence |
| Destination | Exactly one existing simple XMP property `{http://ns.adobe.com/exif/1.0/}DateTimeOriginal`, with an explicitly selected matching packet ordinal |

The primary date is an existing field characterized in the
[initial R5 read slice](../reader/README.md) and the bounded
[DateTimeOriginal allocation experiment](../write-safety/new-output-preservation.md).
This is not a new composite label guessed from any tag named `CreateDate`.
`DateTimeDigitized`, `xmp:CreateDate`, CTMD dates, maker-note aliases, EXIF dates in
other documents, and filesystem times are outside this mapping. The
[read format evidence](../reader/format-evidence.md) remains the field/layout
reference; this ticket adds no new camera corpus claim.

The user explicitly selects the RAW and existing XMP sidecar as in
[pairing #0082](pairing.md). Pairing establishes a bounded path observation only:
it does not bind later contents or prove the two files describe the same image.
A future application must independently read and bind the actual selected
documents, establish coverage, and pass all preservation/storage gates. This
research model consumes caller-provided typed observations; its document IDs,
coverage boolean and occurrence IDs are not authenticated authority or a RAW
adapter. No imported JSON or comparison result may assert its own admission.

The selected CMT2 block must have complete enumeration for all three source tags.
Zero companions then means observed absence. Unexamined/limited/invalid companion
coverage refuses, because treating it as absent could silently lose precision or
zone. Missing/duplicate primary, duplicate companions, empty/reused occurrence IDs,
or missing/equal RAW and sidecar document IDs refuse. Equal duplicate values do
not resolve ambiguity. Every successful comparison retains the original snapshot,
both document IDs, every source occurrence ID, exact destination ordinal, previous
text, mapped text, losses and decision.

## Original-snapshot semantics

All source values and destination comparison values come from **one immutable
original observation**. An earlier set/delete/copy intent in the same proposed
batch cannot alter this mapping's inputs. It neither reads a previous intent as
an overlay nor chains the output into a later copy. Two requests to the same
destination in a future batch must refuse as conflicting intent, even if their
proposed text matches; no last-request-wins rule is defined. This standalone model
compares one request and implements no batch executor. Any later reparse receives
a new snapshot identity and requires a fresh comparison.

## Exact date conversion and finite limits

The source primary is exactly `YYYY:MM:DD hh:mm:ss`, decoded stored ASCII text
after the EXIF terminator, with no whitespace trimming or display conversion.
Calendar validation uses Gregorian years 0001–9999 and real month/day ranges.
Hours are 00–23 and minutes/seconds 00–59. Partial/blank dates, year zero,
24:00, leap seconds and malformed dates refuse. Missing date parts are never
filled from the destination, filesystem, host clock or another occurrence.

The date separators become hyphens, and the date/time separator becomes `T`.
The exact source fraction digits, if present, are appended after `.`. This version
accepts **1–9 ASCII digits**, retaining all leading/trailing zeros; present empty,
spaces, punctuation or more digits refuse. It does not round, truncate, pad to
milliseconds or convert through floating point. Absent fraction stays absent;
`.0`, `.000` and no fraction are observably different precision representations.

An observed source offset, if present, is copied exactly as `+hh:mm` or `-hh:mm`.
The bounded subset accepts offsets from -14:00 to +14:00, with minutes 00–59
and zero minutes at hour 14. `-00:00`, `Z`, blank/space offsets and larger ranges
refuse as source companion values. This conservative subset does not interpret
the ambiguous negative-zero spelling or broaden the source EXIF representation.
Absent offset means unknown timezone and stays absent; never append `Z`, use the
host zone, resolve daylight saving time or convert the local clock to an instant.
The output is at most 35 ASCII bytes. No source precision or timezone component
accepted by this version is discarded in the mapping.

Destination parsing accepts this same complete date/time syntax with hyphen/`T`
separators, optional 1–9-digit fraction, and absent zone, `Z` or the bounded
numeric offset. Malformed/partial dates, lists/structures, unknown target
namespaces and duplicate exact target properties refuse. Missing target refuses
with no insertion or sidecar creation alternative. XMP prefixes and attribute
versus element spelling are handled by
[#0081's bounded component](xmp-component.md), while property selection always
uses exact expanded names. Other unknown primitive/list properties remain in the
packet/source; this model makes no preservation or rewrite claim for them.

## No-op, conflicts and explicit loss alternatives

Equality is **exact decoded date text after the defined source mapping**. It is
not an instant comparison: `.10` differs from `.1`, and `Z` differs from `+00:00`.
Equivalent instants with different local clocks/offsets are also different. This
avoids erasing offset/precision information in a normalization step. An identical
value yields `NoOp` under every policy, with no proposed content change; lexical
XML bytes need no rewrite. Actual byte/no-op preservation is #0084's gate.

For a differing existing value, every comparison records both complete texts.
These finite alternatives are explicit; there is no implicit preference based on
mtime, a friendly date label or which file was read last:

| Conflict selection | Typed outcome |
| --- | --- |
| Omitted / `Refuse` | `ConflictRefused`; reports proposed mapping, previous text and loss set |
| `KeepDestination` | `KeepDestination`; records intentional skipped synchronization, never claims the two documents agree |
| `ReplaceSelected { acknowledged: [...] }` | `ReplaceIntentOnly` only when the exact required named loss set is acknowledged; otherwise `LossRefused` |

Replacement selects the existing singleton destination ordinal. It is a proposal
for replacing that one value, not a merge, append, broad date-copy, repair or
write. A changed second/date is already an explicit replacement conflict; these
additional loss names identify discarded destination information:

- `DestinationFractionDiscarded`: the destination has fraction text and the
  proposed fraction is absent or differs in any digit/precision spelling.
- `DestinationZoneDiscarded`: the destination has a zone spelling and the proposed
  zone is absent or differs, including `Z` versus `+00:00`.

These names conservatively cover replacement as well as reduced precision: a
same-length changed fraction or changed known offset still discards that original
component. Losses describe destination replacement, while accepted source
components survive exactly. The acknowledgment must match the computed set, with
no missing, extra or duplicate members; there is no generic `allow_loss` switch.
If there are no component losses, explicit replacement still must be selected,
with an empty acknowledgment set. A future applicable plan must retain the entire
previous destination value and provenance; acknowledgment does not authorize a
sidecar writer or weaken unknown-data/storage safety gates.

## Authored vectors and verification boundary

[Typed executable vectors](../../experiments/0083-xmp-date-mapping/tests/vectors.rs)
exercise exact full fractional/offset mapping and provenance, unknown-zone/no-
fraction mapping, each conflict alternative and exact loss acknowledgment,
equivalent-spelling conflicts, repeated evaluation against the unchanged original
observation, malformed/non-leap/partial dates, fraction/offset bounds, expanded-name
attribute selection, missing/duplicate/list/malformed destinations and unexamined
or ambiguous sources. Values are invented; no private media or reference fixtures
are copied. The comparison never mutates the source packet or source observations.

The standalone pinned-toolchain fmt, denied-warning Clippy, ten vector test
functions and release build are required verification. There is no native RAW-to-
snapshot adapter, live pair-to-content binding, production command, XML patcher,
no-op byte qualification, real-camera mapping run or publication in this ticket.
The one-request model does not execute or validate multi-intent batches. #0084 and
the umbrella retain their independent format/preservation/storage acceptance.

## Primary semantic references

Observed 2026-10-15; live Adobe pages display no exact revision. Only behavioral
facts are referenced; no property table or SDK implementation is imported.

- [Adobe EXIF namespace](https://developer.adobe.com/xmp/docs/xmp-namespaces/exif/):
  exact XMP EXIF namespace and DateTimeOriginal's primary/subsecond association.
  Its older note that EXIF dates lack timezone does not authorize dropping the
  separately observed modern source OffsetTimeOriginal field; explicit preservation
  of that field is this version's stated mapping choice.
- [Adobe XMP data types](https://developer.adobe.com/xmp/docs/xmp-namespaces/xmp-data-types/):
  date syntax, fractional seconds and absent-zone unknown semantics; local offset
  retention conveys information beyond UTC normalization.
- [Metadata identity/value contract](../metadata-model/README.md), MDL-008/013/018/019:
  separate origins, precision and offset semantics, explicit mapping/loss intent,
  and independent planning admission.
