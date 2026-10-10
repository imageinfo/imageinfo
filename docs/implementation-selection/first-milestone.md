# First implementation milestone

Proposed under **ADR-0011**, 2026-10-10. This is a small delivered slice of the
accepted RAW scope, not a downgrade of PR-004 or the eventual parity goal.

## Increment 1: executable foundation

Bootstrap the accepted language/toolchain with a library and CLI in one package.
Record the actual compiler, MSRV, exact dependency graph, provenance and reproducible
commands. Add Windows x64, Linux x64 and macOS arm64 CI jobs where runners are
available; unsupported/unrun targets must be visible rather than marked successful.
No installer, package-manager publication or public release is required here.

Use the existing command grammar. Root, `metadata`, and `metadata read` help are
the first contract examples; add `binary`, `tags`, `formats` and `version` only as
their behavior becomes real. Do not advertise a read stub as working media support.
The disposable spike's assertions become requirements for a new implementation,
not code to copy into production.

Gate this increment with CLI-001/002/004/005/007/008/009/014/017 cases: help at each
level, malformed options even with help, duplicate scalars across levels, literal
operands after `--`, Unicode paths, no ANSI/prompt in redirected output and distinct
result/diagnostic streams. Synthetic results may test serialization only when
explicitly labeled test data. Root/help/version must not open media or use a network.

## Increment 2: bounded recognition and metadata

Implement a deliberately limited R5 full RAW reader with the smallest practical
bounded source API. Start with top-level and required nested BMFF structures,
checked spans, extended/to-end sizes, limits and explicit unknown-region reporting.
Recognizing `crx ` alone cannot establish EOS R5 model, mode, complete parsing or
successful metadata interpretation. Malformed or ambiguous structures must not
become an accidental success path.

The first published read subset should identify these stored fields where present:

- Canon make/model, full RAW quality, Dual Pixel RAW state and firmware.
- EXIF capture date, offset/subseconds when separately present, exposure time,
  aperture, ISO, focal length and dimensions, retaining exact stored forms.
- Repeated ISO occurrences across the implemented EXIF/CTMD locations, with source
  identity; computed Composite equivalents remain explicit later work.
- The thumbnail, preview and JPEG-track resources observed in the initial corpus,
  with distinct locations, bounded sizes and exact extraction including padding.

Before coding each mapping, record the native tag/location, independent source
basis, expected reference view and fixture evidence. This is a representative
subset of CAP-001/002/003/004/008/010/013/015/016/017; it does not verify whole rows.
Unsupported tags/regions retain honest coverage status. Unknown bytes should not
be guessed into strings or silently treated as absent.

Proposed existing command spellings remain:

```console
imageinfo metadata read --values all --output json -- photo.cr3
imageinfo binary list -- photo.cr3
```

For extraction, use the exact resource selector/destination contract already
specified by CLI walkthroughs, closing any unresolved details before advertising
the leaf. Reading never mutates a source; extraction creates a separate bounded
output and needs collision/path safety even though RAW metadata is read-only.

## Evidence needed before calling the slice delivered

1. Run on the eight admitted originals through newly reviewed private working-copy
   admission for native tests. The #0013 reference-only phase does not silently
   become differential-test approval. Reuse existing rights; update experiment
   scope and identities explicitly, without asking again for already authorized
   private operations.
2. Compare declared fields/views and resource bytes against the pinned reference.
   Keep original captures and explain every mapping difference. Do not compare a
   display string to a raw value or use our prototype header scanner as an oracle.
3. Add public independently authored malformed/truncated/overflow/limit cases and
   fuzz the actual reader. Include nested structure bounds and unknown-data paths;
   the spike's six flat-header cases are insufficient.
4. Exercise the supported filename, error, output and read behavior on each declared
   OS. Native target compilation alone is insufficient.
5. Report input/output/read/allocation limits, cancellation boundaries and every
   untested case. Keep the inventory at its real per-operation evidence state.

A single firmware/ISO/lens stratum limits claims. #0018 supplies targeted additional
fixtures, not an indiscriminate request for thousands more images.

## Following increments

Associated XMP read support and exact time/structure semantics follow under PR-004;
select the XML component through a focused preservation/security spike. Add plain
cascading line menus over the same real operations and command definitions before
calling the CLI experience complete. Rich terminal widgets and completions can
then be evaluated against accessibility and shell requirements.

Embedded mutation waits for #0014. Full legacy behavior and persistent integration
remain #0015; measured budgets #0016; contributor/release readiness #0017. They can
advance in parallel where their prerequisites allow, but their unresolved breadth
does not require finishing full ExifTool parity before this reader is useful.
