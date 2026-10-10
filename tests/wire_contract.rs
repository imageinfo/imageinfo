use imageinfo::output::{ErrorEnvelope, VersionInfo};

#[test]
fn synthetic_metadata_wire_example_preserves_exact_values_and_duplicates() {
    // This is deliberately synthetic contract data, never an emitted camera read.
    let source = include_str!("../docs/metadata-model/examples/snapshot.synthetic.json");
    let original: serde_json::Value = serde_json::from_str(source).unwrap();
    let serialized = serde_json::to_vec(&original).unwrap();
    let roundtrip: serde_json::Value = serde_json::from_slice(&serialized).unwrap();
    assert_eq!(roundtrip, original);
    assert_eq!(roundtrip["basis"], "synthetic");
    let values = roundtrip["occurrences"].as_array().unwrap();
    let iso: Vec<_> = values
        .iter()
        .filter(|item| item["tag"]["name"] == "ISO")
        .collect();
    assert_eq!(iso.len(), 2);
    assert_eq!(iso[0]["values"]["raw"]["value"]["decimal"], "400");
    assert_eq!(iso[1]["values"]["raw"]["value"]["decimal"], "800");
    assert_ne!(iso[0]["tag"]["namespace"], iso[1]["tag"]["namespace"]);
    let exposure = values
        .iter()
        .find(|item| item["id"] == "occ-exposure")
        .unwrap();
    assert_eq!(exposure["values"]["raw"]["value"]["numerator"], "2");
    assert_eq!(exposure["values"]["raw"]["value"]["denominator"], "500");
    assert_eq!(exposure["values"]["normalized"]["value"]["numerator"], "1");
    assert_eq!(
        exposure["values"]["normalized"]["value"]["denominator"],
        "250"
    );
    // The full schema/conformance checks live in the public validation recipe;
    // this test protects the serializer boundary's faithful JSON transport only.
}

#[test]
fn typed_version_rejects_unknown_wire_fields() {
    let mut value = serde_json::to_value(VersionInfo::default()).unwrap();
    value["surprise"] = true.into();
    assert!(serde_json::from_value::<VersionInfo>(value).is_err());
}

#[test]
fn refusal_has_zero_selection_and_no_effects_or_payloads() {
    let value = serde_json::to_value(ErrorEnvelope::new(
        "test-request".into(),
        Some("metadata read"),
        "CAPABILITY_UNSUPPORTED",
        "Synthetic refusal".into(),
        1,
    ))
    .unwrap();
    assert_eq!(value["summary"]["counts"]["discovered"], 0);
    assert_eq!(value["summary"]["artifacts"], serde_json::json!([]));
    assert_eq!(value["files"], serde_json::json!([]));
}
