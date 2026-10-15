//! Serializer-only boundary cases use authored metadata, never camera media.
#[allow(dead_code)]
mod support;

use imageinfo::reader::{self, Limits, Value};
use std::io::Cursor;

#[test]
fn native_serializer_retains_wide_integer_and_unreduced_rational_strings() {
    let mut metadata =
        reader::read(Cursor::new(support::fixture().bytes), Limits::default()).unwrap();
    let integer = metadata
        .occurrences
        .iter()
        .position(|occurrence| occurrence.name == "ISO")
        .unwrap();
    // The current TIFF/CTMD input slice is at most u32. This explicitly authored
    // native-value boundary test does not claim parsing a u64 camera tag.
    metadata.occurrences[integer].value = Value::Integer(u64::MAX);
    let rational = metadata
        .occurrences
        .iter()
        .position(|occurrence| occurrence.name == "ExposureTime")
        .unwrap();
    metadata.occurrences[rational].value = Value::Rational(2, 500);
    let mut selected = vec![integer, rational];
    selected.sort_unstable();
    let snapshot = metadata.snapshot("wide-authored", "authored.cr3", &selected, false);
    let roundtrip: serde_json::Value =
        serde_json::from_slice(&serde_json::to_vec(&snapshot).unwrap()).unwrap();
    let occurrences = roundtrip["occurrences"].as_array().unwrap();
    let integer = occurrences
        .iter()
        .find(|item| item["tag"]["name"] == "ISO")
        .unwrap();
    let rational = occurrences
        .iter()
        .find(|item| item["tag"]["name"] == "ExposureTime")
        .unwrap();
    assert_eq!(
        integer["values"]["raw"]["value"]["decimal"],
        "18446744073709551615"
    );
    assert_eq!(integer["values"]["normalized"], integer["values"]["raw"]);
    assert_eq!(rational["values"]["raw"]["value"]["numerator"], "2");
    assert_eq!(rational["values"]["raw"]["value"]["denominator"], "500");
    assert_eq!(rational["values"]["normalized"], rational["values"]["raw"]);
}

#[test]
fn filtered_occurrences_keep_original_identity_ordinals_and_partial_coverage() {
    let metadata = reader::read(Cursor::new(support::fixture().bytes), Limits::default()).unwrap();
    let all: Vec<_> = (0..metadata.occurrences.len()).collect();
    let selected = reader::select(&metadata, &["ISO".into()]).unwrap();
    let full = metadata.snapshot("same-snapshot", "authored.cr3", &all, false);
    let filtered = metadata.snapshot("same-snapshot", "authored.cr3", &selected, false);
    assert_eq!(filtered["occurrences"].as_array().unwrap().len(), 2);
    for (position, index) in selected.iter().enumerate() {
        assert_eq!(
            filtered["occurrences"][position],
            full["occurrences"][*index]
        );
    }
    assert_eq!(filtered["coverage"][0]["state"], "partial");
    assert_eq!(filtered["sources"][0]["identity"]["kind"], "unavailable");
    assert_eq!(filtered["associations"], serde_json::json!([]));
    assert_eq!(filtered["selections"], serde_json::json!([]));
}

#[test]
fn invalid_zero_denominator_retains_encoded_origin_without_present_rational() {
    let mut fixture = support::fixture().bytes;
    let at = support::field_offset(&fixture, b"CMT2", 0x829a);
    fixture[at + 4..at + 8].copy_from_slice(&0u32.to_le_bytes());
    let metadata = reader::read(Cursor::new(fixture), Limits::default()).unwrap();
    let index = metadata
        .occurrences
        .iter()
        .position(|occurrence| occurrence.name == "ExposureTime" && occurrence.namespace == "exif")
        .unwrap();
    let snapshot = metadata.snapshot("invalid-authored", "invalid.cr3", &[index], true);
    let occurrence = &snapshot["occurrences"][0];
    assert_eq!(occurrence["values"]["raw"]["state"], "invalid");
    assert_eq!(occurrence["values"]["raw"]["code"], "ZERO_DENOMINATOR");
    assert!(occurrence["values"]["raw"].get("value").is_none());
    assert_eq!(
        occurrence["values"]["normalized"],
        occurrence["values"]["raw"]
    );
    assert_eq!(occurrence["values"]["display"]["state"], "unavailable");
    let resource = snapshot["resources"]
        .as_array()
        .unwrap()
        .iter()
        .find(|resource| resource["id"] == occurrence["origin"]["resourceRef"])
        .unwrap();
    assert_eq!(resource["byteLength"], "8");
    assert_eq!(resource["content"]["ranges"][0]["offset"], at.to_string());
    assert_eq!(resource["content"]["ranges"][0]["length"], "8");
    assert_eq!(snapshot["issues"][0]["occurrenceRefs"][0], occurrence["id"]);
    assert_eq!(occurrence["issueRefs"][0], snapshot["issues"][0]["id"]);
}
