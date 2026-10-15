# Source-bound CR3 date preview

Implemented 2026-10-15 under #0077. [The root source-binding module](../../src/source_binding.rs)
captures and revalidates the [#0055 saved preview contract](cr3-preview-plan.md)
using the actual source bytes and the [#0076 preview](../../src/preview.rs).
There is one saved-plan protocol; this increment adds no alternate schema or
executable plan. No writer, apply command or recovery action is enabled.

## Implemented boundary

`capture` reads a caller-provided stable `Read + Seek` stream into one bounded
in-memory snapshot. It computes SHA-256 over **every byte**, resolves the unique
existing CMT2 Exif DateTimeOriginal, binds its complete indexed path, allocation,
byte order and original bytes, and preserves the exact proposed ASCII20 intent.
Current model/reader/admission/registry/capability/conversion/policy revisions are
taken from the existing typed contract. Actual admission findings remain visible
in the preview, including opaque dependencies that currently refuse format writes.
A valid field can therefore yield a saved advisory intent alongside a refused
mutation assessment. Missing/ambiguous fields and unsupported shapes return errors
instead of inventing an occurrence.

`revalidate` takes a validated imported `PreviewPlan` and a current stable stream.
It rechecks current rules, snapshots and hashes the complete source, parses current
metadata and compares the exact saved occurrence and original bytes. Source
revision equality requires both the full SHA-256 and source length to match.
Only a complete binding match returns a fresh preview for the saved intended bytes;
a mismatch never silently replans a changed source. The result has separate
`source_revision_matches`, `occurrence_matches`, `original_bytes_match` and
`binding_matches` observations.

| Typed finding or error | Meaning |
| --- | --- |
| `source_revision_changed` | Complete source length/digest differs, including changes outside the selected metadata. |
| `occurrence_missing_or_ambiguous` | Current parser finds zero or multiple matching date occurrences. |
| `occurrence_changed` | Exact indexed path, allocation or TIFF byte order differs. |
| `original_bytes_changed` | Selected original bytes no longer match, or no unique occurrence exists. |
| `format_admission_refused` | The matching source's actual admission assessment still contains format refusals. |
| `storage_profile_unavailable` | Always present: the only supported contract profile remains explicitly unavailable. |
| `INVALID_PLAN` / strict import error | Invalid/stale contract, unsupported profile or invented authorization. |
| Reader/IO/shape error | Source cannot be inspected within the supported parser and field bounds. No matching preview is returned. |

The file wrappers `capture_file` and `revalidate_file` preflight regular-file state
before opening, recheck the held source object, and compare its length/modification
observations before and after inspection. This preflight avoids opening a known
pipe/device/directory and does not exclude pathname races. `revalidate_file` uses
the saved source locator. Neither wrapper opens,
creates or modifies the proposed output. A preexisting destination does not change
a **source binding** match; destination absence/collision checking is a separate,
still unresolved publication requirement.

## Explicit limits

Source length is at most 256 MiB, matching the existing admission ceiling. Snapshot
reads are capped at that ceiling plus one detection byte; a length change refuses.
The snapshot costs memory proportional to source length and is not an OS memory
quota. Reader metadata/structural bounds remain active. Snapshot parsing, digesting
and previewing use the same immutable bytes so those observations cannot disagree
because of later reads from a changing stream.

Callers must still supply a stable stream. Reading bytes and checking file
length/time observations do not establish an atomic filesystem snapshot or a live
source guard. Same-length modifications can evade the metadata observations;
concurrent changing streams are outside the stable-stream contract. File
read/access-time observations may occur, as with other read-only operations.

The saved digest is a content identity, not object identity, authenticity, caller
authority or a continuous byte/name guard. Replacing a source object at the same
locator with exactly equal bytes is deliberately reported as content equality.
The file test retains the original under another name before installing equal
bytes and verifies this limit. Relative locators resolve in the caller's current
working directory; aliases, links, parents, filesystem properties and destination
object identities are not qualified by this API.

An imported plan's intended date is untrusted intent. Editing it can request a
different advisory preview but cannot preserve an earlier reviewer's approval or
grant new authority. Strict imports reject serialized self-authorization and
invented storage profiles. Fresh source equality, no-op intent, a successful hash
and successful parsing still leave `production_mutation_allowed` false. Independent
RAW effect admission, qualified storage/publication/recovery and separate caller
authorization remain required by WS-002 and the #0078 dependency.

SHA-256 uses the pinned `sha2` 0.10.9 dependency with `std`; this introduces no
key management, signatures, cryptographic authentication or private context store.

## Verification

[Nine integration tests](../../tests/source_binding.rs) use independently authored
structural CR3 fixtures. They exercise capture/typed import/fresh revalidation,
changes outside the selected date, changed old bytes, actual missing/ambiguous
occurrences, altered exact path/allocation/order/digest assertions, stale rules,
invented profile/authority, big-endian and equal-date intents, unsupported/oversized
sources, and read-only file behavior including equal-byte object replacement and
retention of an existing foreign output. The [#0055 vectors](preview-plan/negative.v1.json)
continue to cover strict wire failures; its synthetic all-zero digest is not
mistaken for a verified source binding.

These are portable source-content and parser observations, exercised natively on
Windows. They do not qualify source-property exclusion, current RAW write effects,
publication, persistence, restart actions or any production storage profile. No
private media or generated local logs are included. Primary local contracts:
[WS-002](../write-safety/README.md#plan-before-effects),
[date admission](../write-safety/write-admission.md), and
[LG-004](integration.md#plan-serialization-boundary), observed 2026-10-15.
