# Authored CMT reference serialization

#0109 is a bounded research experiment on ExifTool 13.59, revision
`2200871d9cef988051d2a99d67df3bda6cbb30a8`, observed 2026-10-16. It tests a
serializer mechanism using wholly project-authored bytes. It is neither a CR3
format specification nor an imageinfo writer. The parent
[write-admission requirements](write-admission.md) remain unchanged.

## Independently authored controls

The [research runner](../../experiments/0109-cmt-serialization/README.md)
declares 32 controls before executing any reference operation and constructs each
input before its command:

| Dimension | Values |
| --- | --- |
| TIFF byte order | II, MM |
| Companion CMT4 storage | No tail; 24 zero tail bytes; nonzero tail bytes 1 through 24; reachable nonzero GPSMapDatum value |
| DateTimeOriginal assignment | Original invented value; changed invented value |
| Reference padding mode | Default; explicit `QuickTimePad=1` |

The fixed original date is `2001:02:03 04:05:06`; the changed date is
`2007:08:09 10:11:12`. These values and `AUTHORED-0109` are invented for the
controls. The minimal container has `ftyp`, `moov`, the documented Canon UUID
routing identifier, `CNCV`, CMT2 with the date and CMT4 with GPSVersionID plus the
selected storage shape. It has no sensor media. Inputs are at most 64 KiB.
The reference emits its minor no-media warning; the command neither ignores
errors nor asks to rewrite unrelated tags to manufacture a result.

No camera-derived fixture constants or media bytes are used. The routing
identifier and CMT bindings come from the pinned public reference source;
the fixture layout and payloads are authored here. No upstream implementation,
tag table or fixture is copied wholesale, and no reference code is vendored.

## Execution and evidence

Only the already reviewed source and Perl/runtime closure are used. Exact
distribution manifests and every listed component hash/length are revalidated
before and after execution. Source archives and hashes, the full matrix and
environment precede commands. Each command disables configuration, selects only
ExifIFD DateTimeOriginal, writes to a fresh destination and has a 120-second bound.
Complete stdout/stderr, exit/timeout/launch status, input/output byte hashes and
mtime observations remain in the private capture, including failed attempts.
The final capture manifest binds all retained files except itself.

The independent auditor does not import the runner. It parses actual BMFF box
extents, CMT TIFF directories, entry types/counts/full values, owned ranges and
unallocated gaps. Literal adversarial tests reject malformed extents and pointers,
cycles and aliases. They distinguish an absent range from empty equality and
new zero padding from retained nonzero bytes. Reachable value storage is checked
by its actual complete bytes. Non-CMT leaf payloads must remain exact complements.

## Observed authored boundary

For both byte orders and both assignments, the reference rebuilds the companion
TIFF from reachable entries. Default mode removes the authored unallocated tail,
whether zero or nonzero. Explicit QuickTimePad retains the original allocation
length by appending zeros: it does not preserve the authored nonzero tail bytes.
The no-tail controls and complete reachable nonzero value survive both modes.
Same-value assignment still exercises the serializer; it is not inferred to be a
whole-file no-op. The final independent audit records the finite cell outcomes.
All 32 operations created a derivative and passed the independent byte checks;
the [public authored report](../../experiments/0109-cmt-serialization/authored-results.json)
binds the frozen research-source and tool-manifest digests without machine paths.

| Authored companion storage | Default result | QuickTimePad result |
| --- | --- | --- |
| No tail | No unallocated storage | No unallocated storage |
| Zero tail | Tail removed | Equal-length, byte-identical zero tail |
| Nonzero tail | Tail removed | Equal-length zero storage; original nonzero bytes absent |
| Reachable nonzero value | Complete value retained | Complete value retained |

The zero-tail observation alone cannot distinguish copying from zero generation.
The nonzero control and the reviewed source path establish that distinction for
this finite family. Eighteen local tests include literal observer challenges and
launch/timeout capture checks. Earlier setup and viability attempts remain
separate from the final source-frozen capture.

This behavior matches the pinned public source path. The
[Canon CMT bindings](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/lib/Image/ExifTool/Canon.pm)
select WriteTIFF and PreservePadding. The
[QuickTime writer](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/lib/Image/ExifTool/WriteQuickTime.pl)
dispatches the directory writer and, when both padding switches apply and the
rebuilt directory shrinks, appends zero bytes to the old size. The
[TIFF writer](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/lib/Image/ExifTool/WriteExif.pl)
reconstructs directories from their entries, value storage and subdirectories.
These are source-mechanism observations at the pinned revision, not a general
promise about other tools or every CR3.

## Limits

This finite authored family does not establish that unallocated camera storage
is disposable, semantically independent or free of checksums/signatures. It
does not prove rewrite necessity, unknown-data preservation, complete TIFF/CR3
conformance, sensor equivalence, a storage profile or RAW mutation admission.
QuickTimePad's allocation-length behavior supplies no nonzero-byte preservation
guarantee. No camera write or decoder operation is part of this experiment.

Any read-only reconciliation with existing frozen camera evidence remains private
under its grants, including values, counts, hashes, inventories, Boolean outcomes
and conclusions. Public controls and outcomes disclose no such reconciliation.
No production dependency, SDK/unsafe boundary, automatic repair or write
permission is enabled. #0078 retains its full positive admission requirements.
