#[allow(dead_code)]
mod support;
use imageinfo::{
    preview::{self, PreviewStatus},
    reader::Range,
};
use std::io::{Cursor, Read, Seek, SeekFrom};

fn fixture() -> Vec<u8> {
    support::fixture_with_previews(
        "Firmware Version 2.2.1",
        vec![0xff, 0xd8, 0xff, 0xd9],
        vec![0xff, 0xd8, 0xff, 0xd9],
        vec![0xff, 0xd8, 0xff, 0xd9],
    )
    .bytes
}
fn entry(bytes: &[u8], tag: u16) -> usize {
    let base = bytes.windows(4).position(|w| w == b"CMT2").unwrap() + 4;
    let count = u16::from_le_bytes(bytes[base + 8..base + 10].try_into().unwrap()) as usize;
    (0..count)
        .map(|i| base + 10 + i * 12)
        .find(|&at| bytes[at..at + 2] == tag.to_le_bytes())
        .unwrap()
}
fn has(result: &preview::DatePreview, code: &str) -> bool {
    result.refusals.iter().any(|finding| finding.code == code)
}

#[test]
fn actual_checks_refuse_opaque_dependencies_but_describe_exact_advisory_byte_partition() {
    let bytes = fixture();
    let at = support::field_offset(&bytes, b"CMT2", 0x9003) as u64;
    let report = preview::date_time_original(
        Cursor::new(&bytes),
        "2000:02:29 23:59:59",
        Some(Range {
            offset: at,
            length: 20,
        }),
    )
    .unwrap();
    assert_eq!(report.status, PreviewStatus::Refused);
    assert!(has(&report, "OPAQUE_DEPENDENCY_UNPROVEN"));
    assert!(report.field_shape_verified && report.expected_occurrence_matches);
    assert!(!report.production_mutation_allowed);
    assert_eq!(report.original_bytes.unwrap(), *b"2026:01:02 03:04:05\0");
    assert_eq!(report.proposed_bytes, *b"2000:02:29 23:59:59\0");
    let mut candidate = bytes.clone();
    candidate[at as usize..at as usize + 20].copy_from_slice(&report.proposed_bytes);
    let mut counts = vec![0; bytes.len()];
    for range in &report.changed_ranges {
        for offset in range.offset..range.offset + range.length {
            assert_ne!(bytes[offset as usize], candidate[offset as usize]);
            counts[offset as usize] += 1;
        }
    }
    for range in &report.preserved_ranges {
        for offset in range.offset..range.offset + range.length {
            assert_eq!(bytes[offset as usize], candidate[offset as usize]);
            counts[offset as usize] += 1;
        }
    }
    assert!(counts.iter().all(|count| *count == 1));
    assert_eq!(
        report.changed_bytes + report.preserved_bytes.unwrap(),
        bytes.len() as u64
    );
    assert_eq!(
        report.changed_bytes,
        bytes.iter().zip(&candidate).filter(|(a, b)| a != b).count() as u64
    );
}

#[test]
fn identical_intent_preserves_every_byte_but_is_still_refused() {
    let bytes = fixture();
    let report =
        preview::date_time_original(Cursor::new(&bytes), "2026:01:02 03:04:05", None).unwrap();
    assert_eq!(report.status, PreviewStatus::Refused);
    assert!(report.value_already_matches);
    assert_eq!(report.changed_bytes, 0);
    assert!(report.changed_ranges.is_empty());
    assert_eq!(
        report.preserved_ranges,
        vec![preview::ByteRange {
            offset: 0,
            length: bytes.len() as u64
        }]
    );
}

#[test]
fn byte_order_does_not_change_ascii_intent_or_expected_width() {
    let mut bytes = fixture();
    let offset = support::field_offset(&bytes, b"CMT2", 0x9003) as u64;
    support::big_endian_tiff_boxes(&mut bytes);
    let report = preview::date_time_original(
        Cursor::new(&bytes),
        "2000:02:29 23:59:59",
        Some(Range { offset, length: 20 }),
    )
    .unwrap();
    assert!(report.field_shape_verified && report.expected_occurrence_matches);
    assert_eq!(report.original_bytes.unwrap(), *b"2026:01:02 03:04:05\0");
    let report = preview::date_time_original(
        Cursor::new(bytes),
        "2000:02:29 23:59:59",
        Some(Range { offset, length: 19 }),
    )
    .unwrap();
    assert!(has(&report, "OCCURRENCE_CHANGED"));
    assert!(report.original_bytes.is_none());
}

#[test]
fn missing_ambiguous_and_changed_occurrences_never_receive_a_byte_proposal() {
    let original = fixture();
    for (replacement, code) in [
        (0x9004u16, "FIELD_MISSING_OR_AMBIGUOUS"),
        (0x9003, "FIELD_MISSING_OR_AMBIGUOUS"),
    ] {
        let mut bytes = original.clone();
        let at = entry(
            &bytes,
            if replacement == 0x9004 {
                0x9003
            } else {
                0x9011
            },
        );
        bytes[at..at + 2].copy_from_slice(&replacement.to_le_bytes());
        let report =
            preview::date_time_original(Cursor::new(bytes), "2000:02:29 23:59:59", None).unwrap();
        assert!(has(&report, code));
        assert!(report.original_bytes.is_none() && report.preserved_bytes.is_none());
        assert!(report.changed_ranges.is_empty() && report.preserved_ranges.is_empty());
    }
    let report = preview::date_time_original(
        Cursor::new(original),
        "2000:02:29 23:59:59",
        Some(Range {
            offset: u64::MAX,
            length: 20,
        }),
    )
    .unwrap();
    assert!(has(&report, "OCCURRENCE_CHANGED"));
    assert!(report.original_bytes.is_none());
}

#[test]
fn alias_and_authenticity_findings_are_carried_from_actual_admission() {
    let mut bytes = fixture();
    let base = bytes.windows(4).position(|w| w == b"CMT2").unwrap() + 4;
    let date = support::field_offset(&bytes, b"CMT2", 0x9003) - base;
    let at = entry(&bytes, 0x9011);
    bytes[at..at + 2].copy_from_slice(&0x9004u16.to_le_bytes());
    bytes[at + 4..at + 8].copy_from_slice(&20u32.to_le_bytes());
    bytes[at + 8..at + 12].copy_from_slice(&(date as u32).to_le_bytes());
    let report =
        preview::date_time_original(Cursor::new(bytes), "2000:02:29 23:59:59", None).unwrap();
    assert!(has(&report, "FIELD_ALLOCATION_ALIAS"));
    let mut bytes = fixture();
    bytes.extend(support::atom(
        b"uuid",
        vec![
            0xd8, 0xfe, 0xc3, 0xd6, 0x1b, 0x0e, 0x48, 0x3c, 0x92, 0x97, 0x58, 0x28, 0x87, 0x7e,
            0xc4, 0x81,
        ],
    ));
    let report =
        preview::date_time_original(Cursor::new(bytes), "2000:02:29 23:59:59", None).unwrap();
    assert!(has(&report, "KNOWN_AUTHENTICITY_STRUCTURE"));
    assert!(
        report
            .known_structures
            .iter()
            .any(|f| f.code == "C2PA_BMFF_UUID")
    );
}

#[test]
fn exact_existing_shape_and_intended_calendar_are_required() {
    let mut bytes = fixture();
    let at = support::field_offset(&bytes, b"CMT2", 0x9003);
    bytes[at..at + 20].copy_from_slice(b"2026:02:30 03:04:05\0");
    let report =
        preview::date_time_original(Cursor::new(bytes), "2000:02:29 23:59:59", None).unwrap();
    assert!(has(&report, "FIELD_SHAPE_UNVERIFIED"));
    assert!(report.original_bytes.is_none());
    for value in [
        "1900:02:29 00:00:00",
        "2026:01:02 03:04:60",
        "2026:01:02 03:04:05Z",
        "2026:01:02 03:04:05\0",
    ] {
        assert_eq!(
            preview::date_time_original(Cursor::new(fixture()), value, None)
                .unwrap_err()
                .code,
            "INVALID_DATE"
        );
    }
    let mut bytes = fixture();
    let at = entry(&bytes, 0x9003);
    bytes[at + 2..at + 4].copy_from_slice(&7u16.to_le_bytes());
    assert!(preview::date_time_original(Cursor::new(bytes), "2000:02:29 23:59:59", None).is_err());
}

#[test]
fn bounded_stream_and_malformed_inputs_fail_closed() {
    struct Large;
    impl Read for Large {
        fn read(&mut self, _: &mut [u8]) -> std::io::Result<usize> {
            panic!("oversize input must not be read")
        }
    }
    impl Seek for Large {
        fn seek(&mut self, _: SeekFrom) -> std::io::Result<u64> {
            Ok(256 * 1024 * 1024 + 1)
        }
    }
    assert_eq!(
        preview::date_time_original(Large, "2000:02:29 23:59:59", None)
            .unwrap_err()
            .code,
        "LIMIT_EXCEEDED"
    );
    for bytes in [vec![], vec![0; 8], fixture()[..64].to_vec()] {
        assert!(
            preview::date_time_original(Cursor::new(bytes), "2000:02:29 23:59:59", None).is_err()
        );
    }
}

#[test]
fn read_only_file_preview_has_no_source_or_directory_effect() {
    let dir = support::TempDir::new();
    let path = dir.path.join("source.cr3");
    let bytes = fixture();
    std::fs::write(&path, &bytes).unwrap();
    let before = std::fs::metadata(&path).unwrap().modified().unwrap();
    let input = std::fs::File::open(&path).unwrap();
    let report = preview::date_time_original(input, "2000:02:29 23:59:59", None).unwrap();
    assert_eq!(report.status, PreviewStatus::Refused);
    assert_eq!(std::fs::read(&path).unwrap(), bytes);
    assert_eq!(
        std::fs::metadata(&path).unwrap().modified().unwrap(),
        before
    );
    assert_eq!(std::fs::read_dir(&dir.path).unwrap().count(), 1);
    let json = serde_json::to_value(report).unwrap();
    assert_eq!(json["production_mutation_allowed"], false);
    assert_eq!(json["status"], "refused");
}
