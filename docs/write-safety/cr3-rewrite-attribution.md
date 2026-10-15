# Read-only CR3 rewrite attribution method

Method revision `0102-attribution-2026-10-15.1`, #0102. The
[#0099 reference-write characterization](cr3-reference-effects.md) records file
effects and relocation-aware region comparisons. This increment asks the next
finite question: which effects can be attributed to exact stored allocations and
parsed address relationships, and which byte relationships remain unexplained?
It reads only existing frozen artifacts. It neither repeats a reference write nor
uses a hypothetical-checksum absence requirement as a substitute for attribution.

## Private evidence and public controls

Actual camera-derived outcomes, counts, Boolean observations, byte values/hashes,
allocation inventories and residual intervals remain private. The source grant's
`rights.permissions.publishReports` remains `denied`; prior public reports do not
widen it. Public files contain the method, implementation and independently
authored structural tests. Actual retained analysis and its independent audit are
reviewed through the local handoff, not uploaded or committed.

The [research package](../../experiments/0102-cr3-rewrite-attribution/README.md)
provides standard-library checks and the private invocation. It requires the
reviewed #0099 hash manifest, scoped grants, source-manifest binding and independent
review. Each current source must still match the frozen hash. There are no external
tool processes or new media writes, and source content/mtime is checked after
inspection. The private output directory must be fresh and owner-only.

## Stored-allocation correspondence

The bounded independent reader walks the declared BMFF containers and Canon UUID
wrapper, then classic TIFF directories in each CMT block. Standard Exif/GPS/
interoperability directory pointers and next-directory links have explicit bounds,
depth and cycle/shared-directory refusals. Other entry payloads remain bytes;
storage width is not a claim that an unknown tag has no pointer or checksum meaning.

Match allocations by **CMT block, full logical directory path, native tag, duplicate
ordinal within that tag, TIFF type and count**. The match never uses displayed names
or payload equality to choose an identity. Changing type/count, adding/removing a
tag or changing a directory route creates an explicit unmatched allocation. Inline
values retain their actual slot location and width; out-of-line values retain the
CMT-relative pointer and complete bounded stored extent. Both TIFF byte orders are
supported by the research reader.

Compare every matched allocation's complete bytes, including undecoded and partial
Canon arrays. The selected date is a unique existing CMT2 tag `0x9003`, ASCII20,
with the existing invented intent `2001:02:03 04:05:06`. A selected allocation with
another owner or structural overlap refuses attribution as that single-date
operation. Other overlapping byte ownership is explicit in the interval report;
it never increases total byte coverage by counting an alias twice.

Every source and candidate byte belongs to a disjoint interval partition. Roles
can overlap within one interval: box size/kind, UUID identifier, TIFF header,
IFD tag/type/count, value/address/inline padding, CTBO fields, chunk-offset cells,
leaf payload or bytes unallocated to the scanned directories. The partition must
cover the entire file exactly once. Logical allocation comparisons are separate
from that physical byte denominator.

Unallocated CMT intervals retain exact ranges, hashes and zero/nonzero byte counts.
They are called **unallocated to the scanned IFDs**, not disposable padding. Zeros
alone establish no absence of semantics or future pointer use. Changed, removed
or unmatched storage remains an explicit residual relationship.

## Address and sample relationships

The CTBO subset has a big-endian count followed by 20-byte records containing an
ID, unsigned 64-bit offset and unsigned 64-bit length. Each non-null reference must
fit the file. The report resolves an exact parsed-box extent when there is one,
keeps null references distinct, and otherwise reports an unknown target. Source/
candidate record IDs and box paths must agree to label a numeric change as target
relocation. This documents the bounded relationship inspected; it is not a general
Canon CTBO specification or permission to synthesize entries.

The track subset requires one self-contained local sample description of type
`CRAW` or `CTMD`, data-reference index 1, one `dref` self-contained `url ` entry,
one `stsc` mapping and one `stsz` sample. One `stco` or `co64` offset must bound the
sample inside exactly one parsed `mdat`. Comparison retains the sample length,
relative position within that `mdat`, complete byte hash and offset-cell width.
Only equal bounded sample relationships qualify an offset change as relocation.
Each changed offset cell needs its own exact path/record witness; another valid
table or an empty witness set cannot qualify an orphan cell.
External references, ambiguous/multiple table forms, unknown versions, invalid
entry sizes and out-of-bounds samples refuse this finite subset.

The byte-cell comparison distinguishes unchanged bytes, the declared date value,
parsed box extents, TIFF allocation addresses, validated CTBO/sample relocations,
and unexplained/unallocated or added/missing relationships. A label describes the
relationship actually checked. It does not infer that the reference writer needed
every rewrite, or that imageinfo should reproduce that rewrite.

Unknown leaf payloads and unrecognized offset families remain uninterpreted.
Unchanged bytes establish byte preservation; they do not certify their semantic
independence. Changed leaf/structural cells outside the supported relationships
remain residuals rather than being renamed harmless. The method makes no blanket
claim that other reference-bearing box families are absent because they were not
decoded. A same-value reference-write causal control would answer a different
question and is outside this read-only increment.

## Bounds, verification and admission

Inputs are capped at 256 MiB, parsed boxes at 4,096 and nesting at 16, TIFF entries
at 4,096 per CMT block and directory depth at 16, and CTBO records at 256. These are
research input/record bounds, not an OS memory quota or I/O deadline. Whole stored
values are compared without sensor decoding or recompression. Frozen #0099 RAW
unpacks are evidence from that earlier experiment, not a new decoder run here.

The public authored controls exercise allocation identity, endian values, aliases,
duplicate/missing cases, complete interval coverage, nonzero unallocated bytes,
both chunk-offset widths, invalid sample-reference indexes, pointer overflow and
directory/format failures. The separate independent audit reconstructs relationships
from actual frozen bytes instead of importing this implementation. Camera-derived
verification remains private, including any supported relationships and residuals.

No root writer, SDK boundary, dependency, admission flag or storage profile changes.
#0078 retains its actual supported format/storage acceptance; a completed attribution
child does not imply a supported production apply operation. The project power-test
policy remains [best effort with disposable VM-off tests](power-test-policy.md);
this read-only format increment requires no new power campaign or hardware.

Primary factual reference: pinned ExifTool
[WriteQuickTime source](https://github.com/exiftool/exiftool/blob/2200871d9cef988051d2a99d67df3bda6cbb30a8/lib/Image/ExifTool/WriteQuickTime.pl)
at revision `2200871d9cef988051d2a99d67df3bda6cbb30a8`, inspected 2026-10-15,
corroborates the bounded CTBO layout. The existing
[root track reader](../../src/reader/tracks.rs) and
[format evidence](../reader/format-evidence.md) define the current single-sample
subset; neither is a complete format-mutation specification. No upstream code or
tables are copied wholesale.
