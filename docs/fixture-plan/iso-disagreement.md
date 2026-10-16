# Authored native ISO disagreement

Observed 2026-10-16, #0115, selected assertion P0A-003 under #0018.
Actual native reads and CLI JSON selection preserve both CMT2 ISO **400** and
CTMD ISO **800** in one project-authored binary fixture. Source-qualified
selection retains the original occurrences and their exact values. The
unchanged equal-800/800 control also retains two occurrences. No preferred-value
merge or synchronization is inferred.

The [integration tests](../../tests/iso_disagreement.rs) use the existing
[authored builder](../../tests/support/mod.rs). They change only the two-byte
CMT2 ISO SHORT, verify its TIFF byte order, tag, type and count, and assert exact
prefix/suffix equality around that field. The CTMD value is separately bound to
the final 40-byte type-5 record within the authored `mdat` extent. These storage
expectations do not come from the reader's emitted values. A separate review
walked the authored BMFF/TIFF bytes and independently constructed the same edit
before checking actual CLI output.

## Exact authored inputs

Both inputs have 2,331 bytes. SHA-256 identities are pinned by the tests:

| Input | SHA-256 |
| --- | --- |
| CMT2 400 / CTMD 800 | `e19356f8baeca53ed23eabd106d045b66f43e0fa3c2b14b5fb9c210f2317b27a` |
| CMT2 800 / CTMD 800 control | `7781896f985d5af5153e17b8959df04053fe8418262ca99a7ef2290d853992af` |

The CMT2 value is little-endian uint16 at source offset 287, length 2, native ID
`34855`, under CMT2 / IFD@8 / tag 34855. The CTMD value is little-endian uint32
at offset 2,311, length 4, native ID `5/8`, under the fourth `trak` /
CTMD-type-5 record / ISO field. Source ranges refer to these unchanged authored
inputs. Their hashes establish fixture identity, not camera provenance.

## Actual finite checks

Two integration tests cover the reader API and real CLI. The CLI matrix contains
56 invocations: two inputs, four value views (`all`, `raw`, `normalized`,
`display`) and seven selector configurations each:

- unqualified `ISO`;
- `EXIF:ISO` and `exif:ISO` separately;
- `CTMD:ISO` and `canon:ctmd:ISO` separately;
- both qualified selectors together, in reverse source order;
- unqualified plus both qualified selectors, checking that overlap adds no duplicate.

Unqualified and combined selection return exactly the two original occurrences.
Single-source selection returns its exact original occurrence, including ID,
ordinal, path, value and referenced source range. Expectations identify origins
by namespace rather than assuming an array position. Raw and normalized integer
values agree exactly; display is checked when requested. The tests also require
the existing partial-coverage declaration, unchanged input bytes, no reported
output artifacts and no additional directory entries. The reader API repeats
source-range/value and selection-identity checks on both authored inputs.

Reproduce with the pinned project Rust toolchain:

```text
cargo test --locked --test iso_disagreement
cargo clippy --locked --test iso_disagreement -- -D warnings
cargo fmt --all --check
python scripts/check_fixture_gaps.py
python scripts/check_docs.py
```

This delivers only the selected authored cross-origin disagreement assertion.
The historical [P0 selection ledger](p0-assertion-gaps.md) remains a versioned
planning/evidence checkpoint. These controls do not establish camera setting
coverage, full FXP-003 completion, arbitrary duplicate semantics or a production
mutation capability. Their embedded preview bytes are authored marker controls;
no JPEG decoding occurred. #0075/P0A-002 retains its independent camera assertion,
fixture-phase and decoded-derivative prerequisites. No private media or new
camera-derived results are included.
