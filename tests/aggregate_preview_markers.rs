//! P0A-005: authored framing/count evidence, without entropy or camera claims.
#[allow(dead_code)]
mod support;

use imageinfo::reader::{
    self, Limits, Range,
    admission::{self, DateTime},
};
use std::{fs, io::Cursor};

fn jpeg(resource: u8, count: usize) -> Vec<u8> {
    let mut bytes = vec![0xff, 0xd8];
    for index in 0..count {
        bytes.extend([0xff, 0xfe, 0, 5, resource]);
        bytes.extend(u16::try_from(index).unwrap().to_be_bytes());
    }
    bytes.extend([0xff, 0xd9]);
    bytes
}

// A deliberately narrower oracle than the production scanner: only exact SOI,
// numbered COM segments and terminal EOI are admitted. No scanner output is used.
fn count_framing(bytes: &[u8], resource: u8) -> Option<usize> {
    if !bytes.starts_with(&[0xff, 0xd8]) {
        return None;
    }
    let mut position = 2;
    let mut count = 0usize;
    while bytes.get(position..position + 2)? != [0xff, 0xd9] {
        let header = bytes.get(position..position + 4)?;
        if header[..2] != [0xff, 0xfe] {
            return None;
        }
        let length = usize::from(u16::from_be_bytes(header[2..4].try_into().ok()?));
        if length != 5 {
            return None;
        }
        let payload = bytes.get(position + 4..position + 2 + length)?;
        if payload[0] != resource
            || usize::from(u16::from_be_bytes(payload[1..].try_into().ok()?)) != count
        {
            return None;
        }
        count += 1;
        position += 2 + length;
    }
    (position + 2 == bytes.len()).then_some(count)
}

fn fixture(counts: [usize; 3], extra_refusals: bool) -> (Vec<u8>, [Vec<u8>; 3]) {
    let previews = std::array::from_fn(|index| jpeg(index as u8 + 1, counts[index]));
    let mut bytes = support::fixture_with_previews(
        if extra_refusals {
            "Firmware Version test"
        } else {
            "Firmware Version 2.2.1"
        },
        previews[0].clone(),
        previews[1].clone(),
        previews[2].clone(),
    )
    .bytes;
    if extra_refusals {
        bytes.extend(support::atom(
            b"uuid",
            vec![
                0xd8, 0xfe, 0xc3, 0xd6, 0x1b, 0x0e, 0x48, 0x3c, 0x92, 0x97, 0x58, 0x28, 0x87, 0x7e,
                0xc4, 0x81,
            ],
        ));
    }
    (bytes, previews)
}

fn inspect_file(counts: [usize; 3], extra_refusals: bool) -> reader::Result<admission::Assessment> {
    let (bytes, previews) = fixture(counts, extra_refusals);
    let directory = support::TempDir::new();
    let path = directory.path.join("authored.cr3");
    fs::write(&path, &bytes).unwrap();
    let before = fs::metadata(&path).unwrap();
    let held_identity = same_file::Handle::from_path(&path).unwrap();
    let metadata = reader::read(Cursor::new(&bytes), Limits::default()).unwrap();
    assert_eq!(metadata.previews.len(), 3);
    let mut matched = [false; 3];
    for preview in &metadata.previews {
        let start = preview.range.offset as usize;
        let stored = &bytes[start..start + preview.range.length as usize];
        let index = previews
            .iter()
            .position(|expected| expected == stored)
            .unwrap();
        assert!(
            !matched[index],
            "each distinct stored extent is selected once"
        );
        matched[index] = true;
        assert_eq!(count_framing(stored, index as u8 + 1), Some(counts[index]));
        assert_eq!(stored.len(), 4 + 7 * counts[index]);
        assert!(
            counts[index] + 1 < 4096,
            "COM plus EOI individually below bound"
        );
    }
    assert_eq!(matched, [true; 3]);
    let result = admission::inspect(
        fs::File::open(&path).unwrap(),
        DateTime::parse("2000:02:29 23:59:59").unwrap(),
        extra_refusals.then_some(Range {
            offset: 1,
            length: 20,
        }),
    );
    // Err supplies no completed assessment. It cannot become a success or a
    // known-authenticity-absence assertion by treating missing findings as empty.
    assert!(
        !result
            .as_ref()
            .is_ok_and(|assessment| assessment.production_mutation_allowed())
    );
    assert_eq!(fs::read(&path).unwrap(), bytes);
    let after = fs::metadata(&path).unwrap();
    assert_eq!(
        held_identity,
        same_file::Handle::from_path(&path).unwrap(),
        "admission keeps the same physical source"
    );
    assert_eq!(before.len(), after.len());
    assert_eq!(
        before.permissions().readonly(),
        after.permissions().readonly()
    );
    assert_eq!(before.created().ok(), after.created().ok());
    assert_eq!(after.modified().unwrap(), before.modified().unwrap());
    let entries: Vec<_> = fs::read_dir(&directory.path)
        .unwrap()
        .map(|entry| entry.unwrap().file_name())
        .collect();
    assert_eq!(entries, vec![path.file_name().unwrap().to_os_string()]);
    result
}

#[test]
fn aggregate_bound_is_shared_across_three_valid_authored_extents() {
    let report: serde_json::Value = serde_json::from_str(include_str!(
        "../docs/fixture-plan/aggregate-preview-markers.v1.json"
    ))
    .unwrap();
    let recorded = report["cells"].as_array().unwrap();
    let counts = recorded
        .iter()
        .map(|cell| {
            let counts: [usize; 3] = std::array::from_fn(|index| {
                usize::try_from(cell["comCounts"][index].as_u64().unwrap()).unwrap()
            });
            assert_eq!(cell["counterTotal"], counts.iter().sum::<usize>() + 3);
            assert_eq!(
                cell["scanComplete"],
                counts.iter().sum::<usize>() + 3 <= 4096
            );
            assert_eq!(
                cell["result"],
                if counts.iter().sum::<usize>() + 3 <= 4096 {
                    "assessment"
                } else {
                    "LIMIT_EXCEEDED"
                }
            );
            counts
        })
        .collect::<Vec<_>>();
    assert_eq!(
        counts,
        [
            [1, 1, 1],
            [1000, 1000, 1000],
            [2000, 1, 1],
            [1, 2000, 1],
            [1, 1, 2000],
            [1365, 1365, 1363],
            [1365, 1365, 1364],
            [2000, 2000, 2000],
        ]
    );
    assert_eq!(
        report["actualResults"]["production_mutation_allowed"],
        false
    );
    for counts in [
        [1, 1, 1],
        [1000, 1000, 1000],
        [2000, 1, 1],
        [1, 2000, 1],
        [1, 1, 2000],
        [1365, 1365, 1363],
    ] {
        let assessment = inspect_file(counts, false).unwrap();
        // SOI is consumed separately; the scanner counts each COM and each EOI.
        assert_eq!(
            assessment.jpeg_markers_examined,
            counts.iter().sum::<usize>() + 3
        );
        assert!(assessment.field_shape_verified && assessment.expected_occurrence_matches);
        assert!(assessment.opaque_dependency_regions > 0);
        assert_eq!(
            assessment
                .refusals
                .iter()
                .map(|finding| finding.code)
                .collect::<Vec<_>>(),
            ["OPAQUE_DEPENDENCY_UNPROVEN"]
        );
        assert!(assessment.known_structures.is_empty());
        assert!(!assessment.production_mutation_allowed());
    }
    for counts in [[1365, 1365, 1364], [2000, 2000, 2000]] {
        let error = inspect_file(counts, false).unwrap_err();
        assert_eq!(error.code, "LIMIT_EXCEEDED");
        assert_eq!(error.message, "JPEG marker limit exceeded");
        // This is explicitly an incomplete scan: Result::Err contains no
        // Assessment, authenticity-absence conclusion, or mutation permission.
    }
}

#[test]
fn below_limit_keeps_unrelated_refusals_and_known_structure_findings() {
    let baseline = inspect_file([1, 1, 1], true).unwrap();
    let control = inspect_file([1000, 1000, 1000], true).unwrap();
    let codes = |assessment: &admission::Assessment| {
        assessment
            .refusals
            .iter()
            .map(|finding| finding.code)
            .collect::<Vec<_>>()
    };
    assert_eq!(codes(&baseline), codes(&control));
    assert_eq!(
        codes(&control),
        [
            "OCCURRENCE_CHANGED",
            "FIRMWARE_UNVERIFIED",
            "OPAQUE_DEPENDENCY_UNPROVEN",
            "KNOWN_AUTHENTICITY_STRUCTURE"
        ]
    );
    assert_eq!(
        control.opaque_dependency_regions,
        baseline.opaque_dependency_regions
    );
    assert_eq!(
        control
            .known_structures
            .iter()
            .map(|finding| finding.code)
            .collect::<Vec<_>>(),
        ["C2PA_BMFF_UUID"]
    );
    assert!(!control.production_mutation_allowed());
}

#[test]
fn independent_oracle_rejects_earlier_malformed_framing() {
    let original = jpeg(1, 2000);
    assert_eq!(count_framing(&original, 1), Some(2000));
    for index in [0, 3, 5, 6, original.len() - 1] {
        let mut malformed = original.clone();
        malformed[index] ^= 1;
        assert_eq!(count_framing(&malformed, 1), None);
    }
    assert_eq!(count_framing(&original[..original.len() - 1], 1), None);
}
