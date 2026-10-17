# Stored-preview reference/native differences

#0123, observed 2026-10-17. Eighteen authored cases compare the retained pinned
ExifTool 13.59 executable interface with actual native `binary list`/`binary
extract` invocations. All 18 paired cases passed their declared observations.
The [case ledger](stored-preview-differences.cases.json) contains the exact argv
arrays and expected effects; the [results](stored-preview-differences.results.json)
bind actual statuses, captures, stored-byte hashes, input identities/properties,
source hashes and output inventories. A passing difference/refusal case does not
establish support for the refused native syntax.

## Observed behavior

| Cases | Reference / native observation |
| --- | --- |
| SP-001–003 | `-b -TAG` emits each of ThumbnailImage, PreviewImage and JpgFromRaw to stdout; native copies the same exact stored extent to its explicit new output file. |
| SP-004–006 | `-b -TAG -w .jpg` creates `source.jpg`; native creates that explicitly selected filename. Each side creates exactly one file containing the independent expected bytes. |
| SP-007–009 | `-b -TAG -W %t.jpg` derives the selected tag filename; native uses that same explicitly supplied destination. Exactly one matching file is created per side. |
| SP-010 | Repeated reference `-PreviewImage` concatenates two exact preview copies to stdout. Repeated native `--tag` is a status-2 grammar refusal with no output file. |
| SP-011–012 | Occupied `-w`/`-W` destinations and the corresponding native destinations fail with status 1. Existing sentinel identity, bytes and measured properties remain unchanged. Native reports `DESTINATION_EXISTS`. |
| SP-013–014 | A hyphen-leading input after `--` and a spaced input are passed literally as individual argv elements. Reference and native extract the exact expected bytes from the named source. |
| SP-015 | Reference text descriptions and native JSON list all three named previews. Native resource offsets/lengths match independently located authored extents. No file is created. |
| SP-016 | Native `--dry-run` reports `previewed`, no artifact and no new file. The reference comparator extracts the preview to stdout; it has no asserted equivalent dry-run option. |
| SP-017 | Native dry-run still refuses an occupied destination with status 1 and `DESTINATION_EXISTS`. Reference `-w` also refuses that occupied name. Both preserve it. |
| SP-018 | Three reference selectors with `-W %t.jpg` create exactly three independently checked named previews. Native multiple `--tag` values refuse with status 2 and create nothing. |

These are measured interface differences. The native interface requires one
case-sensitive registered preview and one explicit output filename; it does not
implement reference stdout binary mode, filename templates, or multiple extraction
selectors. This finite comparison neither adopts every difference nor closes
LG-001/LG-006, MAP-006/007/024 or the remaining #0015/#0141 scope. The
[#0052 argument evidence](read-argument-order.md) and
[#0121 inventory](native-token-inventory.md) retain their separate denominators.

## Authored input and exact byte oracle

The checker reuses only the repository's independently authored CR3 structural
fixture, with three separately specified marker byte arrays. It adds four authored
32-byte video-handler atoms and adjusts sample offsets by their exact aggregate
128-byte size, allowing both tools to discover the same three preview resources.
The fixture and expected bytes are constructed before either tool runs; neither
producer's output supplies the other producer's byte oracle. Distinct payloads
prevent selecting the wrong preview from satisfying a byte comparison.

The stored extents are 10, 11 and 12 bytes, including respectively one, two and
three zero suffix bytes after the terminal marker. Their exact hashes, unique
source offsets and the full 2469-byte authored input hash are recorded in results.
Every extracted file or binary stdout stream is compared byte-for-byte with its
specified extent. Duplicate stdout selection is checked against two full copies.
These deliberately tiny structural marker resources are not decodable JPEGs.
No JPEG decoder, entropy/completeness test, pixel rendering or decoding gate is
invoked or inferred. Byte extraction preserves the entire stored extent, including
padding, under the existing [reader contract](../reader/README.md#extraction-publication).

Each producer runs in a fresh isolated case directory with a single correctly
named source and, only for occupied cases, one known sentinel. Before and after
inventories reject directories, symbolic links and nonregular files, and compare
all existing filenames, full SHA-256 bytes, lengths, device/file identity, mode,
link count, mtime, ctime, available birth time and Windows attributes. Expected
outputs are the only permitted new names. Public observations retain the input
and sentinel properties and all new output properties; complete before/after
inventories remain private. Access times, ACLs, alternate streams, allocation and
continuous source/namespace exclusion are not tested by these snapshots.

## Reference and execution binding

The reference is the retained lawful ExifTool 13.59 checkout at
`2200871d9cef988051d2a99d67df3bda6cbb30a8`, rather than a latest-version claim.
The runner verifies its actual clean Git revision and the three #0121 pinned
source hashes. Before and after execution it verifies every entry and relevant
file set in the retained reference, Perl runtime and JSON::PP manifests. Results
record manifest hashes/file counts; these are local byte bindings, not proof of
all OS modules or a reproducible runtime build. No reference implementation,
tag tables, binary or camera media is imported into the repository.

Every reference argv begins with the explicitly selected retained Perl runtime,
its pinned reference library and `exiftool -config ""`. The isolated environment
excludes inherited Perl/config settings, uses the retained JSON::PP/runtime library
paths, C locale and UTC0. The actual `-ver` result must be 13.59. Native source and
binary bytes are hashed and checked unchanged during the run. The report records
all production Rust sources and manifests so integration can refresh this evidence
after the batch source/binary freeze.

Commands receive argv arrays with `shell=False`, closed stdin, a 15-second deadline
and a one-MiB capture limit per stream. Fixture compilation has a 60-second bound.
Captures stream to private files; threshold/deadline failure kills the child and
fails qualification. A capture can overshoot between polls but is never read if
oversized. Fixtures, captures, complete inventories and partial failure reports
remain under ignored `.local/work-wave-20261017a/123-run-*`. No camera inputs are
opened. This Windows execution needed native filesystem/runtime permissions;
sandboxed retained Perl startup failed before reference execution in the shared
setup probe, rather than qualifying a reference/media refusal.

## Reproduce and limits

Build the native executable from the intended frozen source, then run:

```console
python scripts/check_stored_preview_differences.py --binary PATH_TO_IMAGEINFO --reference-root PATH_TO_PINNED_EXIFTOOL --perl PATH_TO_RETAINED_PERL
```

The retained manifests default to ignored `.local/tools/manifests`; an explicit
`--manifests PATH` may select their location. Add
`--public-results docs/legacy-compatibility/stored-preview-differences.results.json`
only for a deliberate evidence refresh. The default leaves public evidence intact.

These 18 Windows authored cases are finite. They do not qualify camera JPEG
contents, broader filename templates, overwrite/append reference options, all
duplicate/group/selector interactions, reference configuration files, Unicode
reference path semantics, native raw stdout, other platforms, cancellation or
exhaustive parity. No writer, storage profile, RAW mutation, privacy removal,
JPEG-decoding prerequisite or production publication authority follows.
