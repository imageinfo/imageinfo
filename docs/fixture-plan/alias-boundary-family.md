# Authored CMT2 allocation boundary family

Revision `alias-boundary-family-2026-10-15.1`, observed 2026-10-15, #0072.
This supplies the finite authored boundary evidence selected by
[P0A-001](p0-assertion-gaps.v1.json). It qualifies the current read-only admission
diagnostic on 16 declared cases; it does not qualify a RAW writer or storage profile.

## Public source and deterministic recipe

All bytes are project-authored structural markers and metadata. There are no
camera photographs, sensor samples, imported upstream fixtures or private reports.
The exact source lineage is root revision
`881f8762654787e115a44e103502d376b34756cd`,
[`fixture_with_previews`](../../tests/support/mod.rs), with firmware text
`Firmware Version 2.2.1` and each of its three preview arguments set to the four
bytes `ff d8 ff d9`. These are marker controls, not decoded JPEG pictures.
The [versioned case ledger](alias-boundary-family.v1.json) fixes the denominator,
byte orders, companion kinds, offsets and expected intersection cardinalities.
The executable recipe is [`fixture`](../../tests/allocation_family.rs).

For MM cases the existing shared helper first converts the authored TIFF boxes.
The recipe locates the authored CMT2 payload and replaces it with an equal-length
zero-filled payload, preserving outer box lengths and all track offsets. It writes
classic TIFF order/magic, first IFD offset 8, two sorted entries and zero next-IFD
pointer. DateTimeOriginal (`0x9003`, ASCII, count 20) occupies relative bytes
`[64,84)` and contains `2026:01:02 03:04:05` plus NUL. The companion allocation
is filled with `01` bytes before the target string is installed, so shared bytes
contain the target value. No operation changes fixture files after creation.

The named P0A-001 companion is DateTimeDigitized (`0x9004`, ASCII, count 20).
The native reader does not decode this tag; its declared allocation still counts
for alias admission. Its bytes are intentionally not asserted to be a valid date
or selected ASCII string. A second companion, ExposureTime (`0x829a`, RATIONAL,
count 1, eight bytes), tests the same boundary with a decoded allocation. Its
exact endian-dependent numerator and denominator are checked separately.

## Fixed 16-case denominator

Each row below runs in both TIFF byte orders II/MM, with both companion kinds:
four boundaries × two companion kinds × two orders = 16 cases. Coordinates are
relative to the TIFF payload; all intervals are half-open.

| Boundary | DateTimeDigitized ASCII20 | ExposureTime RATIONAL | Shared target bytes |
| --- | --- | --- | --- |
| before-overlap | `[45,65)` | `[57,65)` | 1, at 64 |
| before-touch | `[44,64)` | `[56,64)` | 0 |
| after-overlap | `[83,103)` | `[83,91)` | 1, at 83 |
| after-touch | `[84,104)` | `[84,92)` | 0 |

The test independently enumerates occupied byte-address sets and counts their
intersection. It does not call the production interval predicate or `Range::end`.
It also checks the exact 16 unique case IDs against an independently constructed
cross-product, hardcoded boundary starts, widths and intersection counts. Removing
or duplicating a row cannot silently reduce the denominator.

## Actual bounded observations

`cargo test --locked --test allocation_family` passed all 16 cases on 2026-10-15.
The single harness test contains the full fixed denominator; its one Rust test
count is not a one-case fixture denominator.

- 16/16 reader calls returned successfully without panic, with the exact target
  range, stored date text and TIFF order. The undecoded companion retained one
  exact opaque allocation identity; decoded controls retained their exact CMT2
  ExposureTime range and rational value.
- 16/16 admission calls returned successfully without panic. All eight overlaps
  produced exactly one `FIELD_ALLOCATION_ALIAS` with the companion's absolute
  range; all eight touching controls produced none. The after-overlap case shares
  the date terminator, proving that allocation identity includes that byte.
- 16/16 assessments verified the target shape and expected occurrence. The proposed
  date differed from the stored value. All retained
  `OPAQUE_DEPENDENCY_UNPROVEN` and `production_mutation_allowed() == false`.
- 16/16 complete on-disk input comparisons matched the original bytes after the
  reader/admission calls. In-memory inputs also matched their original copies;
  a further immutable borrowed-stream reader call succeeded for every case.

These are successful reader observations and negative mutation-admission evidence,
not parser-refusal cases: aliased data can be read while admission rejects the edit.
Touching controls are positive controls for interval separation only. They retain
all other mutation gates. The source is opened read-only; there is no candidate
write, publication, repair, preview decoding, camera coverage or broad fuzzing.
The family does not prove independent DateTimeDigitized semantics, unknown-data
preservation, checksum absence or any live byte/name/property/storage guarantee.

## Reproduction and audit

Run from the repository root with the pinned toolchain and locked dependencies:

```text
cargo test --locked --test allocation_family
python scripts/check_docs.py
git diff --check
```

Full required root Rust verification remains the integrating maintainer's
responsibility. Independent review details are retained privately; no private
logs or workspace paths form part of this public fixture family.
