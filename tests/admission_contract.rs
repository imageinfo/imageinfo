#[allow(dead_code)]
mod support;
use imageinfo::reader::{
    Range,
    admission::{self, DateTime},
};
use std::io::Cursor;

fn fixture() -> Vec<u8> {
    support::fixture_with_previews(
        "Firmware Version 2.2.1",
        vec![0xff, 0xd8, 0xff, 0xd9],
        vec![0xff, 0xd8, 0xff, 0xd9],
        vec![0xff, 0xd8, 0xff, 0xd9],
    )
    .bytes
}
fn inspect(bytes: &[u8]) -> admission::Assessment {
    admission::inspect(
        Cursor::new(bytes),
        DateTime::parse("2000:02:29 23:59:59").unwrap(),
        None,
    )
    .unwrap()
}
fn has(result: &admission::Assessment, code: &str) -> bool {
    result.refusals.iter().any(|f| f.code == code)
}
fn entry(bytes: &[u8], kind: &[u8; 4], tag: u16) -> usize {
    let base = bytes.windows(4).position(|w| w == kind).unwrap() + 4;
    let count = u16::from_le_bytes(bytes[base + 8..base + 10].try_into().unwrap()) as usize;
    (0..count)
        .map(|i| base + 10 + i * 12)
        .find(|&at| u16::from_le_bytes(bytes[at..at + 2].try_into().unwrap()) == tag)
        .unwrap()
}
fn c2pa_uuid() -> Vec<u8> {
    vec![
        0xd8, 0xfe, 0xc3, 0xd6, 0x1b, 0x0e, 0x48, 0x3c, 0x92, 0x97, 0x58, 0x28, 0x87, 0x7e, 0xc4,
        0x81,
    ]
}

fn segment(marker: u8, payload: &[u8]) -> Vec<u8> {
    [
        vec![0xff, marker],
        ((payload.len() + 2) as u16).to_be_bytes().to_vec(),
        payload.to_vec(),
    ]
    .concat()
}
fn jumbf() -> Vec<u8> {
    let mut description = vec![
        0x63, 0x32, 0x70, 0x61, 0, 0x11, 0, 0x10, 0x80, 0, 0, 0xaa, 0, 0x38, 0x9b, 0x71, 3,
    ];
    description.extend(b"c2pa\0");
    support::atom(b"jumb", support::atom(b"jumd", description))
}
fn app11(instance: u16, sequence: u32, data: &[u8]) -> Vec<u8> {
    segment(
        0xeb,
        &[
            b"JP".to_vec(),
            instance.to_be_bytes().to_vec(),
            sequence.to_be_bytes().to_vec(),
            data.to_vec(),
        ]
        .concat(),
    )
}
fn with_jpeg(jpeg: Vec<u8>) -> Vec<u8> {
    support::fixture_with_previews(
        "Firmware Version 2.2.1",
        jpeg,
        vec![0xff, 0xd8, 0xff, 0xd9],
        vec![0xff, 0xd8, 0xff, 0xd9],
    )
    .bytes
}

#[test]
fn jpeg_catalog_handles_fragments_and_later_scan_headers_without_decoding_pixels() {
    let data = jumbf();
    for middle in [
        app11(1, 1, &data),
        [
            app11(1, 1, &data[..17]),
            app11(1, 2, &[&data[..8], &data[17..]].concat()),
        ]
        .concat(),
        [
            segment(0xda, &[1, 1, 0, 0, 63, 0]),
            vec![1, 0xff, 0, 2, 0xff, 0xd0],
            app11(1, 1, &data),
        ]
        .concat(),
    ] {
        let bytes = with_jpeg([vec![0xff, 0xd8], middle, vec![0xff, 0xd9]].concat());
        let result = inspect(&bytes);
        assert!(
            result
                .known_structures
                .iter()
                .any(|f| f.code == "C2PA_JPEG_JUMBF")
        );
        assert!(has(&result, "KNOWN_AUTHENTICITY_STRUCTURE"));
    }
}

#[test]
fn jpeg_exif_tag_is_detected_and_unknown_makernotes_remain_uninspectable() {
    for (tag, code) in [
        (0xcd41u16, "C2PA_PREVIEW_TIFF_TAG"),
        (0x927c, "PREVIEW_MAKERNOTE_UNINSPECTABLE"),
    ] {
        let exif = [
            b"Exif\0\0".to_vec(),
            support::tiff(vec![(tag, 7, b"authored opaque bytes".to_vec())]),
        ]
        .concat();
        let bytes = with_jpeg([vec![0xff, 0xd8], segment(0xe1, &exif), vec![0xff, 0xd9]].concat());
        let result = inspect(&bytes);
        assert!(has(&result, code) || result.known_structures.iter().any(|f| f.code == code));
    }
}

#[test]
fn jpeg_uninspectable_and_malformed_envelopes_are_never_known_absence() {
    for middle in [segment(0xeb, b"not JP"), app11(1, u32::MAX, &jumbf())] {
        let result = inspect(&with_jpeg(
            [vec![0xff, 0xd8], middle, vec![0xff, 0xd9]].concat(),
        ));
        assert!(
            has(&result, "APP11_SCOPE_UNINSPECTABLE") || has(&result, "APP11_SEQUENCE_UNVERIFIED")
        );
    }
    for middle in [vec![0xff, 0xeb, 0, 1], app11(1, 1, b"\0\0\0\x30jumbshort")] {
        assert!(
            admission::inspect(
                Cursor::new(with_jpeg(
                    [vec![0xff, 0xd8], middle, vec![0xff, 0xd9]].concat()
                )),
                DateTime::parse("2026:01:01 00:00:00").unwrap(),
                None
            )
            .is_err()
        );
    }
    let mut padded = vec![0xff, 0xd8, 0xff, 0xd9];
    padded.extend([0; 16]);
    assert!(inspect(&with_jpeg(padded)).known_structures.is_empty());
}

#[test]
fn byte_order_marker_count_and_assembly_limits_do_not_admit_a_larger_profile() {
    let mut bytes = fixture();
    support::big_endian_tiff_boxes(&mut bytes);
    assert!(inspect(&bytes).field_shape_verified);
    let many = with_jpeg(
        [
            vec![0xff, 0xd8],
            segment(0xfe, b"a").repeat(4097),
            vec![0xff, 0xd9],
        ]
        .concat(),
    );
    let result = admission::inspect(
        Cursor::new(many),
        DateTime::parse("2026:01:01 00:00:00").unwrap(),
        None,
    )
    .unwrap_err();
    assert_eq!(result.code, "LIMIT_EXCEEDED");
    let mut data = jumbf();
    data.resize(1024 * 1024 + 1, 0);
    data[..4].copy_from_slice(&((1024 * 1024 + 1) as u32).to_be_bytes());
    let mut middle = Vec::new();
    for (index, chunk) in data.chunks(60000).enumerate() {
        middle.extend(app11(
            1,
            (index + 1) as u32,
            &if index == 0 {
                chunk.to_vec()
            } else {
                [&data[..8], chunk].concat()
            },
        ));
    }
    let result = admission::inspect(
        Cursor::new(with_jpeg(
            [vec![0xff, 0xd8], middle, vec![0xff, 0xd9]].concat(),
        )),
        DateTime::parse("2026:01:01 00:00:00").unwrap(),
        None,
    )
    .unwrap_err();
    assert_eq!(result.code, "LIMIT_EXCEEDED");
}

#[test]
fn calendar_is_exact_and_does_not_guess_timezone_or_partial_fields() {
    for value in [
        "2000:02:29 23:59:59",
        "0001:01:01 00:00:00",
        "9999:12:31 23:59:59",
    ] {
        assert_eq!(DateTime::parse(value).unwrap().encoded()[19], 0);
    }
    for value in [
        "1900:02:29 12:00:00",
        "2001:02:29 00:00:00",
        "2026:04:31 00:00:00",
        "0000:01:01 00:00:00",
        "2026:00:01 00:00:00",
        "2026:01:00 00:00:00",
        "2026:01:01 24:00:00",
        "2026:01:01 00:60:00",
        "2026:01:01 00:00:60",
        "2026-01-01T00:00:00",
        "2026:01:01 00:00:00Z",
        " 2026:01:01 00:00:00",
        "2026:01:01 00:00:00\0",
        "    :  :     :  :  ",
        "二〇二六:01:01 00:00:00",
    ] {
        assert!(DateTime::parse(value).is_err(), "{value:?}");
    }
}

#[test]
fn field_checks_and_identity_observations_never_grant_write_permission() {
    let bytes = fixture();
    let result = inspect(&bytes);
    assert!(result.field_shape_verified && result.expected_occurrence_matches);
    assert!(!result.value_already_matches && !result.production_mutation_allowed());
    assert!(has(&result, "OPAQUE_DEPENDENCY_UNPROVEN"));
    assert!(result.known_structures.is_empty());
    let unchanged = admission::inspect(
        Cursor::new(&bytes),
        DateTime::parse("2026:01:02 03:04:05").unwrap(),
        None,
    )
    .unwrap();
    assert!(unchanged.value_already_matches && !unchanged.production_mutation_allowed());
    let stale = admission::inspect(
        Cursor::new(&bytes),
        DateTime::parse("2026:01:02 03:04:05").unwrap(),
        Some(Range {
            offset: 1,
            length: 20,
        }),
    )
    .unwrap();
    assert!(has(&stale, "OCCURRENCE_CHANGED"));
}

#[test]
fn undecoded_and_decoded_aliases_of_the_allocation_are_refused() {
    for tag in [0x9004u16, 0x9291] {
        let mut bytes = fixture();
        let at = entry(&bytes, b"CMT2", 0x9011);
        let base = bytes.windows(4).position(|w| w == b"CMT2").unwrap() + 4;
        let date = support::field_offset(&bytes, b"CMT2", 0x9003) - base;
        bytes[at..at + 2].copy_from_slice(&tag.to_le_bytes());
        bytes[at + 4..at + 8].copy_from_slice(&20u32.to_le_bytes());
        bytes[at + 8..at + 12].copy_from_slice(&(date as u32).to_le_bytes());
        let result = inspect(&bytes);
        assert!(has(&result, "FIELD_ALLOCATION_ALIAS"));
        assert!(!result.production_mutation_allowed());
    }
}

#[test]
fn unknown_firmware_and_unknown_original_dates_remain_unverified() {
    let result = inspect(
        &support::fixture_with_previews(
            "Firmware Version test",
            vec![0xff, 0xd8, 0xff, 0xd9],
            vec![0xff, 0xd8, 0xff, 0xd9],
            vec![0xff, 0xd8, 0xff, 0xd9],
        )
        .bytes,
    );
    assert!(has(&result, "FIRMWARE_UNVERIFIED"));
    let mut bytes = fixture();
    let at = support::field_offset(&bytes, b"CMT2", 0x9003);
    bytes[at..at + 20].copy_from_slice(b"    :  :     :  :  \0");
    assert!(has(&inspect(&bytes), "FIELD_SHAPE_UNVERIFIED"));
}

#[test]
fn known_bmff_identity_is_a_refusal_even_for_opaque_or_malformed_manifest_data() {
    for payload in [vec![], b"\0\0\0\0update\0authored-indicator-only".to_vec()] {
        let mut bytes = fixture();
        let mut body = c2pa_uuid();
        body.extend(payload);
        bytes.extend(support::atom(b"uuid", body));
        let result = inspect(&bytes);
        assert!(
            result
                .known_structures
                .iter()
                .any(|f| f.code == "C2PA_BMFF_UUID")
        );
        assert!(has(&result, "KNOWN_AUTHENTICITY_STRUCTURE"));
    }
    // Marker bytes inside encoded samples are not a structural UUID box.
    let mut bytes = fixture();
    let start = bytes.windows(4).position(|w| w == b"mdat").unwrap() + 4;
    bytes[start + 4..start + 8].copy_from_slice(&c2pa_uuid()[..4]);
    assert!(inspect(&bytes).known_structures.is_empty());
}

#[test]
fn tagged_authenticity_indicators_are_detected_without_following_arbitrary_offsets() {
    for (kind, new_tag, code) in [
        (b"CMT3", 0x83u16, "CANON_ORIGINAL_DECISION_INDICATOR"),
        (b"CMT2", 0xcd41, "C2PA_TIFF_TAG"),
    ] {
        let mut bytes = fixture();
        let original = if kind == b"CMT3" { 7 } else { 0x9011 };
        let at = entry(&bytes, kind, original);
        bytes[at..at + 2].copy_from_slice(&new_tag.to_le_bytes());
        let result = inspect(&bytes);
        assert!(result.known_structures.iter().any(|f| f.code == code));
        assert!(has(&result, "KNOWN_AUTHENTICITY_STRUCTURE"));
    }
}

#[test]
fn malformed_inputs_and_limits_fail_closed_without_panics() {
    for bytes in [vec![], vec![0; 7], vec![0; 8]] {
        assert!(
            admission::inspect(
                Cursor::new(bytes),
                DateTime::parse("2026:01:01 00:00:00").unwrap(),
                None
            )
            .is_err()
        );
    }
    let original = fixture();
    for i in 0..original.len().min(1024) {
        let mut bytes = original.clone();
        bytes[i] ^= 0xff;
        let result = admission::inspect(
            Cursor::new(bytes),
            DateTime::parse("2026:01:01 00:00:00").unwrap(),
            None,
        );
        if let Ok(result) = result {
            assert!(!result.production_mutation_allowed());
        }
    }
}
