# Read-only fixed-width CR3 date preview

Implemented for **#0076**, observed **2026-10-15**. The root `preview`
library describes one intent for the unique existing CMT2 EXIF
`DateTimeOriginal` ASCII20 allocation. It calls the actual
[`reader::admission` checks](../write-safety/write-admission.md), including
occurrence, type, calendar, allocation overlap, opaque dependency and known
authenticity refusals. No source write, candidate/output creation, application,
or production storage profile is implemented by this preview.

```console
imageinfo preview --help
imageinfo preview date-time-original --help
imageinfo preview date-time-original photo.cr3 --value "2000:02:29 23:59:59"
imageinfo preview date-time-original photo.cr3 --value "2000:02:29 23:59:59" --offset 1234 --output json
```

The optional decimal `--offset` asserts a specific 20-byte allocation. It never
selects one member of an ambiguous set. Missing or repeated target occurrences,
an allocation mismatch, or an unverified stored shape withhold the byte proposal.
Malformed structures and resource bounds fail with existing reader error codes.
The intended value must be exactly `YYYY:MM:DD HH:MM:SS`, using Gregorian years
1–9999 and seconds 0–59. No trimming, timezone conversion, blank/partial date,
leap second, insertion, type conversion, or width change is supported. The exact
stored original is revalidated as 19 ASCII date bytes plus one NUL.

When the field and expected occurrence pass, the report contains the original
and proposed 20-byte arrays, contiguous differing ranges, their total byte count,
and the exact complement across the source. These are **hypothetical proposed
byte effects**, including when a separate admission check refuses. Preserved
ranges describe bytes the intent would leave untouched; they are not evidence
that unknown checksums, signatures, or coupled fields remain valid. No candidate
is generated or compared with a rewritten file. An identical intent has zero
changed bytes and still retains every applicable refusal.

`status: refused` carries the admission refusal codes and known-structure
findings. `status: previewed`, if all those isolated checks pass, only means that
the advisory inspection completed without those findings. The
`production_mutation_allowed` flag is always false. Current real-camera layouts
may all refuse because opaque dependencies remain unproved. A refusal report
with an advisory byte proposal grants no exception.

The CLI uses the existing result envelope. A completed inspection occupies the
file record's `snapshot` as `{schemaVersion: 1, kind: "date-preview", preview:
...}`. Admission refusal returns status 1 and retains its findings in the file
issues and preview. Invalid syntax or an invalid intended date returns status 2
before opening the source. JSON selection follows the existing explicit
`--output json` routing. Effects remain false, transaction identifiers remain
absent, and the artifact list remains empty. No output path or apply option is
accepted.

The [result schema](../legacy-compatibility/result.schema.json) retains the
metadata snapshot alternative and adds closed, versioned date-preview and
explicit-pair observation alternatives. Their required fields, exact byte-array
shape, fixed authority flag and fixed association kind are checked; arbitrary
snapshot objects remain invalid. Cross-field byte partition, Gregorian calendar,
and occurrence/admission semantics are checked by the implementation and tests.
`scripts/check_output_schemas.py` builds the public authored fixture in a
temporary directory and validates actual executable preview/pairing records,
then rejects altered authority, unknown fields and malformed observation shapes.

The API accepts only `Read + Seek`, uses no filesystem or output APIs, and inherits
the admission ceiling of 256 MiB source length, bounded metadata passes, JPEG
marker/assembly bounds and reader structural limits. Its only extra data read is
20 bytes. The caller must supply a stable stream for the invocation; the preview
does not establish a continuous source guard or authenticate subsequent reads.
Source revision binding, imported-plan validation and saved-plan authority are
separate later work under #0077. Reading can have normal filesystem access-time
effects; byte/name preservation is the tested no-target-effect boundary here.

## Finite public evidence

`tests/date_preview.rs` uses independently authored structural fixtures from
`tests/support`, with no camera/pixel media. It checks:

- Exact changed/preserved partition against an independently assembled in-memory
  hypothetical candidate; every source byte belongs to exactly one range.
- Identical intent, missing/ambiguous target, stale allocation, invalid original
  and intended dates, wrong stored type, and both TIFF byte orders.
- Actual opaque dependency, allocation alias and known C2PA BMFF refusals.
- Oversize stream rejection before data reads and malformed input rejection.
- Preview through a read-only file handle with identical source bytes and
  modification time, and no added directory entries.

The eight tests pass with `cargo test --locked --test date_preview`. Separate
private read-only library and CLI invocations on all eight retained R5 full RAW captures with the
intended value `2000:02:29 23:59:59` observed unique valid existing allocations,
8–10 proposed differing bytes per capture, and
`OPAQUE_DEPENDENCY_UNPROVEN` refusal for every capture. All eight before/after
SHA-256 values and the corpus directory names remained unchanged. No private
media or generated per-capture reports are published. This is finite refusal
evidence for those captures, not a RAW mutation admission.

`tests/cli_preview_pairing.rs` separately verifies root/group/leaf help, JSON
syntax-error routing, actual preview and stale-allocation refusal, and unchanged
source bytes/modification time/directory names through the executable. The same
integration suite checks explicit sidecar association and its no-effect refusals.
The CLI requires ordinary regular files before opening and verifies the held
file type before inspection; a directory refusal is covered explicitly. This
preflight does not establish a continuous pathname guard.

This evidence does not qualify real-camera mutation, source-revision custody,
output publication, persistence, recovery, or an apply command. Private media,
board data and local logs are not part of the public fixture set.
