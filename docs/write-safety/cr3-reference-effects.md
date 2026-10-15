# Private CR3 reference-write effects method

Method revision `0099-reference-effects-2026-10-15.2`, #0099, a bounded format
prerequisite of #0078. [#0021](new-output-preservation.md) checks a native fixed-width
candidate's complement and independent RAW unpack, but explicitly did not execute
an equivalent independent reference mutation. [#0027](write-admission.md) adds
allocation alias checks and opaque/checksum dependency refusals. Neither establishes
what a reference writer changes when given this exact date intent.

This increment asks a concrete new question: given the exact admitted private
source and one existing unique CMT2 DateTimeOriginal ASCII20 value, what byte,
decoded-field and layout effects does the pinned reference writer actually make,
and how do those effects compare with the already bounded native patch?

## Disclosure and actual evidence

The actual source provenance grants private analysis and separately named test
derivatives, while `rights.permissions.publishReports` is `denied`. New camera-
derived observations are therefore retained privately, including aggregate counts,
Boolean results, byte/dependency inventories, metadata changes and decoder
comparisons. Public files contain no such outcomes. Prior public aggregate reports
do not override this grant. The private audit can be reviewed through the local
ticket handoff; public reproduction does not imply access to that private corpus.

This document and the [research package](../../experiments/0099-cr3-reference-effects/README.md)
publish the method, authored controls and limits. They are not a public claim about
the outcome of any actual camera run. Actual private records, when run, remain in
the explicitly selected private directory and are not uploaded or committed.

## Exact private protocol

1. Bind every source hash to its revised #0021 fixture and provenance records,
   requiring approved analysis/modify rights and both reference-characterization
   and differential phases. Verify the independently decoded baseline's actual
   hash against its retained admission. Preserve original manifests unchanged.
2. Record a #0099 scoped private review for the current authorized reference-write
   characterization. Reference-produced private derivatives may resize/rewrite;
   that is an observed effect to classify, not permission to broaden native intent.
   Record all tool/driver hashes and private-only disclosure restrictions.
3. Require a fresh owner-only private output root and at least 8 GiB free scratch.
   Record its actual ACL. Hold the existing Windows `source_guard` read handle,
   whose sharing mode denies new content-write/delete handles. Recheck source
   hash and modification time across all external commands.
4. Read the source with pinned ExifTool 13.59, configuration disabled, duplicate/
   unknown extraction enabled and group families `0:1:4:5`. Confirm there is exactly
   one DateTimeOriginal key in `EXIF:ExifIFD`, and its observed date encodes to the
   same physical ASCII20 allocation as the independent bounded CMT inspection.
5. Run the pinned #0021 native stage tool into a fresh `.candidate.cr3` name, using
   the existing invented value `2001:02:03 04:05:06`. Verify its private-only report
   and exact full-file replacement/complement condition independently.
6. Run ExifTool with the predeclared selector
   `-ExifIFD:DateTimeOriginal=2001:02:03 04:05:06`, `-config ""` and `-o` into a
   distinct fresh output. Supply no overwrite/ignore-error flags. The source is
   never a write destination. A reference refusal or incomplete output is an
   explicit bounded outcome, not a format capability claim.
7. If the reference output completes, stream the **complete** same-offset differing
   run sequence into a count, changed-byte count and SHA-256 over ordered big-endian
   `u64` offset/length pairs. Retain only the first 256 run samples, marking the
   retained list incomplete when appropriate. Runs within the common file extent
   close at its end; an unequal-length suffix is one separate final length-effect
   run, even when adjacent to the preceding run. Classify samples against source/
   candidate allocations, structures, selected date, `mdat` or unmapped bytes.
   Independently partition **every byte** in each file into nonoverlapping indexed
   BMFF header, Canon UUID prefix and leaf payload regions. Compare corresponding
   paths' content/locations, recording equal content moved versus changed/added/
   removed regions and complete relative-run digests with bounded samples. Path
   correspondence is structural, not a proof of semantic object identity. Compare
   ordered complete `mdat` payload hashes independently of their file offsets.
   Preserve length/layout effects and sampling limits instead of silently relaxing
   the fixed native intent. Uninspectable output retains incomplete evidence.
8. Read source/native/reference metadata with identical reference options. Retain
   every changed decoded key/value, separating locator/filesystem observations,
   derived Composite values and stored/other metadata. Preserve both added and
   missing keys, exact raw captures and all unexpected changes.
9. Independently unpack each completed candidate using the previously reviewed
   private LibRaw 0.22.2 tool. Require actual unpack output, expected marker and
   clean termination/stderr, then compare the complete PGM bytes/hash with the
   bound baseline. Preserve decoder errors and partial artifacts; successful
   tool exit alone is insufficient. Release the source guard only after the final
   source hash/time check and retain the complete private evidence manifest.

The reference options are recorded as exact argv, not shell strings. `-config ""`
disables automatic reference configuration. Known tool versions/source and private
binary provenance are inherited from the existing #0013/#0021/#0027 records;
the actual hash is checked before execution. No upstream code or metadata tables
are copied into production.

## What this can and cannot establish

An independent write can expose extra tag updates, allocation relocation,
byte rewrites or apparent checksum effects missing from a proposed native patch.
The private audit classifies what the actual tools do; it must not erase an extra
effect to manufacture agreement. A reference refusal is a concrete capability
observation and a complete finite research outcome when its evidence is retained.
Observed extra effects do not establish that those effects are required or
universal, or that they should be adopted by imageinfo.

Equal candidates, equal decoded metadata, equal stored payloads or equal RAW
unpacks would provide bounded corroboration for those exact inputs/tools/options.
They cannot prove that an unknown pointer/checksum/signature has no dependency,
that all semantic effects are known, or that a different date/firmware/layout is
safe. Reference output is an oracle observation, not a specification of imageinfo
architecture or permission to reproduce every rewrite.

The independent parser inventories bounded top-level/movie/Canon UUID/CMT
structures and TIFF allocations. It does not become a general CR3 parser or
interpret opaque allocation semantics. Byte-run labels can overlap; they are an
effects inventory, not a source-wide nonoverlapping ownership map. `mdat` payload
equality is about bytes in observed extents, not authenticity or sensor rendering.

The declared workload budget is one to eight explicitly admitted sources; this is
a resource cap, not a published count of actual private inputs or results.
Source length/candidates are capped at 256 MiB, BMFF inventory at 4,096 boxes and
depth 16, CMT TIFF entries at 4,096 per block and depth 16, and retained differing-run
samples at 256 per comparison. Counts/digests still consume the complete sequence;
the full-list helper used by authored controls separately refuses over 65,536 runs.
External commands have a 120-second supervisor timeout. Scratch availability
is observed, not reserved; no OS memory, filesystem quota, external decoded-byte
quota or hard native-I/O deadline is promised. Source share mode does not qualify
ancestor/path/property exclusion, crash durability or publication/recovery.

All production format/profile/apply flags remain unchanged and refused. #0078
still needs independently admitted RAW effects and an actually supported storage
profile. A finished #0099 private research increment does not satisfy those gates
by implication, and it must not be presented as completion of #0078.

## Public verification

The [twelve authored controls](../../experiments/0099-cr3-reference-effects/test_controls.py)
exercise effect accounting, exact patch boundaries, added payload corruption,
ambiguity/alias/structure refusals, endian parsing, malformed/cyclic inputs and
strict duplicate reference JSON keys. They contain marker bytes, not camera media.
They qualify the bounded research checker, not the private camera operation or a
production writer. Run the package's standard-library test recipe and the ordinary
documentation/whitespace checks. Camera-derived qualification outcomes remain
private under the grant above.
