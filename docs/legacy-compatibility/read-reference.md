# Authored pinned-reference read differences

2026-10-17, #0122. The [27-case ledger](read-reference.cases.json) and
[actual observations](read-reference.results.json) qualify one finite authored
selection/view comparison. Every case runs ExifTool 13.59 and the native CLI;
14 cases exercise successful native reads and 13 qualify native refusals.
Refusal is an observed difference, never implemented support or parity acceptance.
No production parser, metadata reader or value conversion changes in this scope.

The reference is the already retained lawful source at commit
`2200871d9cef988051d2a99d67df3bda6cbb30a8`, using the previously admitted installed
Perl runtime and retained JSON::PP package. The checker verifies all entries of
their retained manifests before and after execution, the clean reference checkout,
the three [#0121 source hashes](native-token-inventory.v1.json), and an actual
`13.59` version response. It neither downloads nor imports upstream code, tables,
fixtures or documentation. The comparison uses only the project's independently
authored structural CR3 fixture; no camera-derived evidence or rights are involved.

## Measured boundaries

| Cases | Actual selected behavior and retained difference |
| --- | --- |
| RR-001â€“003 | Exact Model and EXIF:ISO selection work in both interfaces. Reference IFD0 grouping is not a native namespace; native IFD0:Model refuses. Similar selectors do not establish a general group translation. |
| RR-004â€“008 | The authored reference observation has one ISO; the native snapshot has separate EXIF and CTMD ISO occurrences. Repeating a native selector does not duplicate occurrences. Reference request order ISO,Model differs from native source order Model,ISO,ISO. `-a` produces no additional ISO in this particular reference fixture; no general reference duplicate suppression rule is inferred. |
| RR-009â€“012 | Reference exclusion, group prefixes/headings and sorting are exercised. Native has family labels and source order; the tested `-x`, `-g1` and `-sort` tokens refuse. Reference IFD0/ExifIFD labels do not equal native exif/CTMD identity. |
| RR-013â€“015, RR-024â€“025 | Reference numeric `-n` and `ExposureTime#` emit 0.004; reference display emits 1/250. Native raw/normalized layers preserve stored EXIF 2/500 and CTMD 1/250 separately, without reduction. Raw and normalized modes omit display; display/all retain both exact layers alongside presentation: EXIF text `0.004` and CTMD text `1/250`, with English locale, null time zone and the named native formatter. These are distinct contracts, not equivalent serializers. |
| RR-016â€“018 | Reference date formatting changes the authored date to 2026-01-02. Native `-d`, `-sep` and `-struct` refuse. Separator and struct reference cases select a scalar Model only; list joining and structured XMP behavior are unqualified. |
| RR-019â€“023 | Literal legacy `-Model`, `-a`, `-G`, `-g` and `-n` syntax refuses in the native grammar with a status-2 JSON envelope plus stderr. Positive native counterparts elsewhere do not support those spellings. |
| RR-026â€“027 | An absent CTMD date selection yields no selected occurrences. Native retains partial coverage, resources and TAG_UNRESOLVED; it does not prove global absence. Reference wildcard selection works for authored Model; native wildcard selection refuses. |

All successful native snapshots explicitly retain unavailable source identity,
null resource hashes, partial coverage and no mutation effects. The harness checks
exact occurrence multiplicity/order and the ledger's independently authored
EXIF/CTMD namespaces, native tag identifiers, definition and occurrence identifiers,
ordinals and metadata-family groups. Raw and normalized layers must each be
`present` with the exact typed value; display must equal its complete expected
structure, including text, locale, time zone and formatter (or the exact unrequested
state). Source ranges against authored bytes, status, stdout/stderr channel and
zero publication/artifact claims are also checked.
The existing [#0052 argument](read-argument-order.md) and
[#0053 JSON](native-read-json.md) contracts remain separate broader evidence.

## Reproduction and independent input binding

```console
cargo build --locked --bin imageinfo
python scripts/check_read_reference.py --binary target/debug/imageinfo.exe --reference-root .local/tools/exiftool-13.59-source --perl PATH_TO_RETAINED_PERL
```

Use `--public-results docs/legacy-compatibility/read-reference.results.json` only
for a deliberate evidence refresh. The executable is explicit and hashed; relevant
reader/dispatch sources, Cargo.lock, checker, ledger, fixture support and authored
bytes are also hashed. No reference runtime is acquired by this procedure.

Each case owns a new directory with a selected source, a differently valued decoy
and a sentinel. Expected input path, fixture hash and physical identity are bound
before launching either process, independently of emitted SourceFile/displayPath.
The reference JSON locator and native file/snapshot locators must name that exact
expected path. Text group cases include the independently known Model, which the
decoy deliberately changes. A separate TIFF decoder confirms authored ISO and
the unreduced rational before either tool runs. The ledger pins expected occurrence
contracts from the authored fixture and declared wire contract; expectations are
never learned from emitted reports. Forty-three deliberate false-report controls
exercise wrong input, changed or mistyped values, independently invalid raw and
normalized states, both-invalid layers, false complete coverage and effects,
EXIF/CTMD relabeling, wrong groups/identifiers/ordinals, duplicated EXIF identity,
and every selected display field for both rational occurrences in display/all.
Each mutation must be rejected while the actual unmodified report passes; the
wrong reference SourceFile control retains unchanged values.

Before/after inventories compare names, bytes, lengths, device/file identity,
link count, mode, available Windows attributes, modification time and available
creation time after each tool. Retained private captures include complete argv,
expected identity and before/after measurements under ignored
`.local/work-wave-20261017a/122-run-*`. Source access time, ACLs, named streams,
allocation, complete filesystem properties and continuous exclusion are not claimed.
These measurements do not supply a production source guard.

Commands use direct argv with closed stdin, disabled reference configuration,
English/C locale, UTC, a 20-second deadline and a one-MiB threshold per capture.
Captures go to files and are monitored while running; a threshold crossing fails
the case and may overshoot between polls. Oversized captures are never loaded.
The authored fixture exporter has a 60-second compilation deadline. Failed runs
remain private and cannot produce passing public evidence. On this Windows host,
the retained Perl executable required ordinary native runtime access outside the
restricted execution sandbox; no runtime installation or system change was made.

The finite Windows evidence does not close LG-001/LG-002/LG-006, general option
equivalence, arbitrary grouping, duplicate/reference coverage, structure/list
formatting, other media, other platforms or camera compatibility. #0015/#0141
retain wider residuals. No writer, source mutation, publication, privacy removal,
storage-profile admission or expanded RAW authority follows.
