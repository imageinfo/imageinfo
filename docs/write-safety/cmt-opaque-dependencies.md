# Authored opaque CMT dependencies

#0113 is a bounded research experiment on ExifTool 13.59, revision
`2200871d9cef988051d2a99d67df3bda6cbb30a8`. It asks what a successful reference
date rewrite establishes about reachable unknown values and explicitly authored
dependencies. It does not supply a CR3 specification or an imageinfo writer.
The [write-admission requirements](write-admission.md) remain unchanged.

## Independently authored family

The [research package](../../experiments/0113-cmt-opaque-dependencies/README.md)
declares twenty cells before commands: II/MM TIFF order, same/changed assignment,
and five CMT2 storage shapes. The dates are invented `2001:02:03 04:05:06` and
`2007:08:09 10:11:12`, each stored as twenty ASCII bytes including NUL.

| Shape | Authored CMT2 content besides DateTimeOriginal |
| --- | --- |
| Baseline | No opaque entry |
| Inline | Tag `0xdffe`, UNDEFINED4, bytes `91 72 53 34` |
| Out-of-line | Tag `0xdffe`, UNDEFINED14, `AUTHORED-0113` plus NUL |
| Exact alias | Tag `0xdffe`, ASCII20, sharing the complete selected date allocation |
| Invented checksum | Tag `0xdffe`, LONG1, sum of all twenty original date bytes |

The invented checksum is a deliberate semantic trap, not a proposed Canon checksum
or inferred camera behavior. Changing the date changes this authored sum; copying
the stored sum alone cannot maintain that dependency. The alias fixture contains
one physical date allocation with two logical owners and no second orphan copy.

The pinned Canon CMT2 binding selects Exif::Main. Before execution, the runner
checks that `0xdffe` has no hexadecimal or decimal tag definition in the pinned
Exif and Canon tables, recording both source hashes and the choice. This finite
namespace check does not reserve the tag universally. CMT4 contains only a fixed
GPSVersionID; CNCV identifies the authored family. There is no sensor media and
no camera-derived fixture constant. Inputs are at most 64 KiB.

## Execution and observation boundary

Only the already reviewed pinned reference and Perl/runtime closure are used.
Every listed component is hash/length checked before and after execution. All
package Python sources, namespace choice, matrix and restricted environment are
archived before commands. Each command disables configuration, assigns only
ExifIFD DateTimeOriginal, writes to a fresh destination and has a 120-second bound.
Default padding is used throughout; the
[earlier tail experiment](authored-cmt-serialization.md) covers padding separately.
Complete captures include failed commands, partial artifacts and byte/hash/mtime
bindings. The final capture manifest binds retained files except itself.

The independent auditor never imports the fixture runner. It retains every entry
identity, type/count, complete value and physical ownership relationship. Exact
aliases and partial value overlaps are observable with multiple owners;
structure overlaps refuse. The disjoint physical partition accounts for reachable
structures, values and gaps. Physical byte preservation, alias sharing and the
invented dependency's consistency are separate observations.

The pinned [Canon CMT2 binding](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/lib/Image/ExifTool/Canon.pm#L9695)
dispatches to WriteTIFF with Exif::Main. In the
[TIFF writer](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/lib/Image/ExifTool/WriteExif.pl#L982),
existing entries obtain their old value from their declared storage. The
[existing-entry branch](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/lib/Image/ExifTool/WriteExif.pl#L1094)
retains the old format/value for an entry without a new assignment. During
[directory emission](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/lib/Image/ExifTool/WriteExif.pl#L1964),
values larger than four bytes are appended to the rebuilt value buffer and receive
new pointer fixups; small values are placed in the entry slot. This per-entry path
does not infer the invented checksum dependency or promise to retain shared
allocation identity. The trace describes this pinned mechanism; the independent
byte audit supplies the finite actual observations.

## Observed authored boundary

All twenty operations created inspectable derivatives and passed the independent
selected-date and non-CMT complement checks. Each of the sixteen opaque entries
retained its exact stored type, count and complete value bytes. The
[public authored report](../../experiments/0113-cmt-opaque-dependencies/authored-results.json)
binds the frozen package sources and tool manifests without machine paths.

| Authored shape | Same-value assignment | Changed-value assignment |
| --- | --- | --- |
| Baseline | Selected date matches request | Selected date matches request |
| Inline/out-of-line opaque value | Complete stored value retained | Complete stored value retained |
| Exact date alias | Values retained; storage split | Opaque original value retained; selected date changed; storage split |
| Invented checksum | Stored sum retained and consistent | Stored sum retained and stale |

These outcomes hold in both byte orders. All four alias cells become separate
physical allocations, including same-value assignments. The two changed checksum
cells demonstrate the intended oracle boundary: an apparently successful date
rewrite preserves the unknown stored bytes while violating the deliberately
authored dependency. Exact stored-byte preservation therefore cannot establish
semantic independence.

Twenty-two local tests cover fixture/capture handling and independent literal
ownership/dependency challenges. An initial capture retained sandbox launch
failures separately. The final capture used the same frozen source and verified
runtime with ordinary process execution; the failed attempt is not counted as
qualification evidence.

## Limits

An authored opaque value surviving byte-for-byte does not prove that an unknown
camera value is independent of the date. A copied stale checksum is not semantic
preservation. Rebuilt storage can split a shared allocation while retaining some
logical values. These controls cannot establish arbitrary pointer/checksum
semantics, unknown-data preservation, rewrite necessity, full TIFF/CR3 conformance,
sensor equivalence or RAW mutation admission.

Only method, code and independently authored outcomes may be public. No camera
operation or reconciliation is part of this experiment. Production dependencies,
SDK/unsafe boundaries, writer/profile flags, source mutation and repair remain
unchanged. #0078 retains its full positive admission requirements.
