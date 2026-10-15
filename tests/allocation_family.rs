#[allow(dead_code)]
mod support;

use imageinfo::reader::{self, Limits, Range, Value, admission};
use serde::Deserialize;
use std::{collections::BTreeSet, fs, io::Cursor, panic::catch_unwind};

#[derive(Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Ledger {
    revision: String,
    source_revision: String,
    recipe: String,
    source: String,
    target: Span,
    denominator: usize,
    cases: Vec<Case>,
}
#[derive(Clone, Copy, Deserialize)]
#[serde(deny_unknown_fields)]
struct Span {
    offset: usize,
    length: usize,
}
#[derive(Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Case {
    id: String,
    byte_order: String,
    allocation: String,
    boundary: String,
    offset: usize,
    length: usize,
    overlap_bytes: usize,
}

fn word16(value: u16, big: bool) -> [u8; 2] {
    if big {
        value.to_be_bytes()
    } else {
        value.to_le_bytes()
    }
}
fn word32(value: u32, big: bool) -> [u8; 4] {
    if big {
        value.to_be_bytes()
    } else {
        value.to_le_bytes()
    }
}

// Same-size CMT2 substitution keeps every original container/sample offset valid.
// DateTimeDigitized is deliberately undecoded; its entry still allocates bytes.
fn fixture(case: &Case, target: Span) -> (Vec<u8>, usize) {
    let jpeg = vec![0xff, 0xd8, 0xff, 0xd9];
    let mut bytes =
        support::fixture_with_previews("Firmware Version 2.2.1", jpeg.clone(), jpeg.clone(), jpeg)
            .bytes;
    let big = case.byte_order == "MM";
    if big {
        support::big_endian_tiff_boxes(&mut bytes);
    }
    let kind = bytes.windows(4).position(|v| v == b"CMT2").unwrap();
    let base = kind + 4;
    let size = u32::from_be_bytes(bytes[kind - 4..kind].try_into().unwrap()) as usize;
    let data = &mut bytes[base..base + size - 8];
    data.fill(0);
    data[..2].copy_from_slice(if big { b"MM" } else { b"II" });
    data[2..4].copy_from_slice(&word16(42, big));
    data[4..8].copy_from_slice(&word32(8, big));
    data[8..10].copy_from_slice(&word16(2, big));
    let companion = if case.allocation == "DateTimeDigitized" {
        (0x9004, 2, 20, case.offset)
    } else {
        assert_eq!(case.allocation, "ExposureTime");
        (0x829a, 5, 1, case.offset)
    };
    let mut entries = [(0x9003, 2, 20, target.offset), companion];
    entries.sort_by_key(|entry| entry.0);
    for (i, (tag, format, count, offset)) in entries.into_iter().enumerate() {
        let at = 10 + i * 12;
        data[at..at + 2].copy_from_slice(&word16(tag, big));
        data[at + 2..at + 4].copy_from_slice(&word16(format, big));
        data[at + 4..at + 8].copy_from_slice(&word32(count, big));
        data[at + 8..at + 12].copy_from_slice(&word32(offset as u32, big));
    }
    data[case.offset..case.offset + case.length].fill(1);
    data[target.offset..target.offset + target.length].copy_from_slice(b"2026:01:02 03:04:05\0");
    (bytes, base)
}

// Enumerate occupied byte addresses, independently of the production endpoint
// inequality. This finite oracle intentionally does not call reader Range::end.
fn occupied(span: Span) -> BTreeSet<usize> {
    (0..span.length).map(|i| span.offset + i).collect()
}

#[test]
fn authored_allocation_boundary_family_matches_independent_byte_oracle() {
    let ledger: Ledger = serde_json::from_str(include_str!(
        "../docs/fixture-plan/alias-boundary-family.v1.json"
    ))
    .unwrap();
    assert_eq!(ledger.revision, "alias-boundary-family-2026-10-15.1");
    assert_eq!(
        ledger.source_revision,
        "881f8762654787e115a44e103502d376b34756cd"
    );
    assert_eq!(ledger.recipe, "tests/allocation_family.rs::fixture");
    assert_eq!(ledger.source, "tests/support/mod.rs::fixture_with_previews");
    assert_eq!((ledger.target.offset, ledger.target.length), (64, 20));
    assert_eq!(ledger.denominator, 16);
    assert_eq!(ledger.cases.len(), ledger.denominator);
    let mut expected = BTreeSet::new();
    for order in ["II", "MM"] {
        for allocation in ["DateTimeDigitized", "ExposureTime"] {
            for boundary in [
                "before-overlap",
                "before-touch",
                "after-overlap",
                "after-touch",
            ] {
                expected.insert(format!("{order}-{allocation}-{boundary}"));
            }
        }
    }
    let actual: BTreeSet<_> = ledger.cases.iter().map(|case| case.id.clone()).collect();
    assert_eq!(actual, expected);
    let temp = support::TempDir::new();
    for case in ledger.cases {
        assert_eq!(
            case.id,
            format!("{}-{}-{}", case.byte_order, case.allocation, case.boundary)
        );
        let length = if case.allocation == "DateTimeDigitized" {
            20
        } else {
            8
        };
        assert_eq!(case.length, length);
        let (expected_start, overlap) = match case.boundary.as_str() {
            "before-overlap" => (65 - length, 1),
            "before-touch" => (64 - length, 0),
            "after-overlap" => (83, 1),
            "after-touch" => (84, 0),
            _ => panic!("unlisted boundary"),
        };
        assert_eq!((case.offset, case.overlap_bytes), (expected_start, overlap));
        let companion = Span {
            offset: case.offset,
            length: case.length,
        };
        let intersection = occupied(ledger.target)
            .intersection(&occupied(companion))
            .count();
        assert_eq!(intersection, case.overlap_bytes, "{}", case.id);
        let (bytes, base) = fixture(&case, ledger.target);
        let original = bytes.clone();
        let path = temp.path.join(format!("{}.cr3", case.id));
        fs::write(&path, &bytes).unwrap();
        let target = Range {
            offset: (base + ledger.target.offset) as u64,
            length: 20,
        };
        let other = Range {
            offset: (base + case.offset) as u64,
            length: case.length as u64,
        };
        let observed = catch_unwind(|| {
            let metadata = reader::read(fs::File::open(&path).unwrap(), Limits::default()).unwrap();
            let dates: Vec<_> = metadata
                .occurrences
                .iter()
                .filter(|o| o.name == "DateTimeOriginal")
                .collect();
            assert_eq!(dates.len(), 1);
            assert_eq!(dates[0].range, target);
            assert_eq!(dates[0].value, Value::Text("2026:01:02 03:04:05".into()));
            assert_eq!(
                dates[0].order,
                if case.byte_order == "II" {
                    "little"
                } else {
                    "big"
                }
            );
            if case.allocation == "DateTimeDigitized" {
                assert_eq!(
                    metadata.opaque.iter().filter(|(r, _)| *r == other).count(),
                    1
                );
            } else {
                let exposure: Vec<_> = metadata
                    .occurrences
                    .iter()
                    .filter(|o| o.name == "ExposureTime" && o.path.iter().any(|p| p.name == "CMT2"))
                    .collect();
                assert_eq!(exposure.len(), 1);
                assert_eq!(exposure[0].range, other);
                let (numerator, denominator) = match case.boundary.as_str() {
                    "before-overlap" => (
                        0x01010101,
                        if case.byte_order == "II" {
                            0x32010101
                        } else {
                            0x01010132
                        },
                    ),
                    "after-overlap" => (
                        if case.byte_order == "II" {
                            0x01010100
                        } else {
                            0x00010101
                        },
                        0x01010101,
                    ),
                    _ => (0x01010101, 0x01010101),
                };
                assert_eq!(exposure[0].value, Value::Rational(numerator, denominator));
            }
            admission::inspect(
                fs::File::open(&path).unwrap(),
                admission::DateTime::parse("2000:02:29 23:59:59").unwrap(),
                Some(target),
            )
            .unwrap()
        })
        .unwrap_or_else(|_| panic!("{} panicked", case.id));
        let aliases: Vec<_> = observed
            .refusals
            .iter()
            .filter(|f| f.code == "FIELD_ALLOCATION_ALIAS")
            .map(|f| f.range)
            .collect();
        assert_eq!(
            aliases,
            if intersection == 1 {
                vec![Some(other)]
            } else {
                vec![]
            },
            "{}",
            case.id
        );
        assert_eq!(observed.field, Some(target));
        assert!(observed.field_shape_verified);
        assert!(observed.expected_occurrence_matches);
        assert!(!observed.value_already_matches);
        assert!(
            observed
                .refusals
                .iter()
                .any(|f| f.code == "OPAQUE_DEPENDENCY_UNPROVEN")
        );
        assert!(!observed.production_mutation_allowed());
        assert_eq!(bytes, original);
        assert_eq!(
            fs::read(&path).unwrap(),
            original,
            "{} changed input",
            case.id
        );
        // Exercise the same stable stream API with an immutable borrowed input.
        assert!(reader::read(Cursor::new(&bytes), Limits::default()).is_ok());
    }
    assert_eq!(
        fs::read_dir(&temp.path).unwrap().count(),
        ledger.denominator
    );
}
