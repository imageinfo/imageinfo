//! #0134: authored consumers of the existing public API, without producer internals.
#[allow(dead_code)]
mod support;

use imageinfo::reader::{self, Limits, Metadata, Value};
use serde_json::{Value as Json, json};
use std::{fs, io::Cursor};

fn metadata() -> Metadata {
    reader::read(Cursor::new(support::fixture().bytes), Limits::default()).unwrap()
}
fn selected(metadata: &Metadata, tags: &[&str]) -> Vec<usize> {
    reader::select(
        metadata,
        &tags.iter().map(|s| (*s).into()).collect::<Vec<_>>(),
    )
    .unwrap()
}
fn projection(metadata: &Metadata, tags: &[&str], display: bool) -> Json {
    metadata.snapshot(
        "consumer",
        "authored.cr3",
        &selected(metadata, tags),
        display,
    )
}

#[test]
fn c01_retained_metadata_queries_survive_source_replacement_and_deletion() {
    let dir = support::TempDir::new();
    let path = dir.path.join("authored.cr3");
    let original = support::fixture().bytes;
    fs::write(&path, &original).unwrap();
    let retained = reader::read_file(&path, Limits::default()).unwrap();
    let expected = projection(&retained, &["ISO", "DateTimeOriginal"], true);
    // Independent filesystem witness: a new read now fails, retained queries work.
    fs::write(&path, b"replaced after extraction").unwrap();
    assert_eq!(fs::read(&path).unwrap(), b"replaced after extraction");
    assert!(reader::read_file(&path, Limits::default()).is_err());
    assert_eq!(
        projection(&retained, &["ISO", "DateTimeOriginal"], true),
        expected
    );
    fs::remove_file(&path).unwrap();
    assert!(!path.exists());
    assert_eq!(
        reader::read_file(&path, Limits::default())
            .unwrap_err()
            .code,
        "INPUT_IO"
    );
    assert_eq!(
        projection(&retained, &["ISO", "DateTimeOriginal"], true),
        expected
    );
    assert_eq!(retained.length, original.len() as u64);
}

#[test]
fn c02_owned_result_outlives_input_stream() {
    let retained = {
        let mut input = Cursor::new(support::fixture().bytes);
        let result = reader::read(&mut input, Limits::default()).unwrap();
        input.get_mut().fill(0);
        result
    };
    assert_eq!(
        projection(&retained, &["Make"], false)["occurrences"][0]["values"]["raw"]["value"]["text"],
        "Canon"
    );
}

#[test]
fn c03_queries_do_not_change_retained_metadata() {
    let retained = metadata();
    let before = projection(&retained, &[], true);
    let bytes_read = retained.bytes_read;
    projection(&retained, &["ISO"], false);
    projection(&retained, &["Make"], true);
    assert_eq!(projection(&retained, &[], true), before);
    assert_eq!(retained.bytes_read, bytes_read);
}

#[test]
fn c04_projection_is_owned_and_survives_metadata_drop() {
    let mut first = projection(&metadata(), &["Make"], true);
    let second = first.clone();
    first["occurrences"][0]["tag"]["name"] = json!("caller edit");
    assert_eq!(second["occurrences"][0]["tag"]["name"], "Make");
}

#[test]
fn c05_unqualified_query_retains_both_iso_occurrences() {
    let m = metadata();
    let ids = selected(&m, &["ISO"]);
    assert_eq!(ids.len(), 2);
    assert_eq!(m.occurrences[ids[0]].namespace, "exif");
    assert_eq!(m.occurrences[ids[1]].namespace, "canon:ctmd");
    assert_ne!(m.occurrences[ids[0]].range, m.occurrences[ids[1]].range);
}

#[test]
fn c06_qualified_query_retains_exact_native_identity_and_path() {
    let m = metadata();
    let exif = selected(&m, &["EXIF:ISO"]);
    let ctmd = selected(&m, &["CTMD:ISO"]);
    assert_eq!((exif.len(), ctmd.len()), (1, 1));
    assert_eq!(m.occurrences[exif[0]].native_id, "34855");
    assert_eq!(m.occurrences[ctmd[0]].native_id, "5/8");
    let a = serde_json::to_value(&m.occurrences[exif[0]].path).unwrap();
    let b = serde_json::to_value(&m.occurrences[ctmd[0]].path).unwrap();
    assert_ne!(a, b);
    assert_eq!(a.as_array().unwrap().last().unwrap()["name"], "34855");
    assert_eq!(b.as_array().unwrap().last().unwrap()["name"], "ISO");
}

#[test]
fn c07_repeated_and_reordered_requests_preserve_source_order_without_duplicates() {
    let m = metadata();
    assert_eq!(
        selected(&m, &["ISO", "Make", "ISO"]),
        selected(&m, &["Make", "ISO"])
    );
    let ids = selected(&m, &["ISO", "Make"]);
    assert!(ids.windows(2).all(|w| w[0] < w[1]));
}

#[test]
fn c08_projection_keeps_original_occurrence_ids_and_ordinals() {
    let m = metadata();
    let ids = selected(&m, &["CTMD:ISO"]);
    let p = projection(&m, &["CTMD:ISO"], false);
    assert_eq!(p["occurrences"][0]["id"], format!("occ-{}", ids[0]));
    assert_eq!(p["occurrences"][0]["ordinal"], ids[0]);
    assert_eq!(
        p["occurrences"][0]["groups"],
        json!([{"axis":"metadata-family","label":"canon:ctmd"}])
    );
}

#[test]
fn c09_alias_resolves_to_canonical_name() {
    assert_eq!(
        reader::selector("EXIF:ExifImageWidth").unwrap(),
        (Some("exif"), "PixelXDimension")
    );
    let m = metadata();
    assert_eq!(
        selected(&m, &["ExifImageWidth"]),
        selected(&m, &["PixelXDimension"])
    );
}

#[test]
fn c10_known_but_unobserved_namespace_is_empty_under_partial_coverage() {
    let m = metadata();
    assert_eq!(
        reader::selector("Canon:ISO").unwrap(),
        (Some("canon"), "ISO")
    );
    let p = projection(&m, &["Canon:ISO"], false);
    assert_eq!(p["occurrences"], json!([]));
    assert_eq!(p["coverage"][0]["state"], "partial");
    assert_eq!(p["selections"], json!([]));
    assert_eq!(
        selected(&m, &["EXIF:ISO", "Canon:ISO"]),
        selected(&m, &["EXIF:ISO"])
    );
}

#[test]
fn c11_unknown_name_and_namespace_are_explicit_errors() {
    assert_eq!(
        reader::selector("UnknownTag").unwrap_err().code,
        "TAG_UNSUPPORTED"
    );
    assert_eq!(
        reader::selector("Unknown:ISO").unwrap_err().code,
        "CAPABILITY_UNSUPPORTED"
    );
    assert!(reader::selector("iso").is_err());
}

#[test]
fn c12_mixed_known_and_unknown_selection_refuses_whole_query() {
    let m = metadata();
    let request = vec!["ISO".into(), "UnknownTag".into()];
    assert_eq!(
        reader::select(&m, &request).unwrap_err().code,
        "TAG_UNSUPPORTED"
    );
    assert_eq!(selected(&m, &["ISO"]).len(), 2);
    assert_eq!(request, ["ISO", "UnknownTag"]);
}

#[test]
fn c13_empty_request_means_all_observed_not_all_definitions() {
    let m = metadata();
    assert_eq!(
        selected(&m, &[]),
        (0..m.occurrences.len()).collect::<Vec<_>>()
    );
    assert_eq!(
        projection(&m, &[], false)["coverage"][0]["state"],
        "partial"
    );
}

#[test]
fn c14_integer_value_keeps_native_number_and_display_mapping() {
    let m = metadata();
    let i = selected(&m, &["Quality"])[0];
    assert_eq!(m.occurrences[i].value, Value::Integer(4));
    assert_eq!(reader::text_value(&m.occurrences[i]), "RAW");
    let p = projection(&m, &["Quality"], true);
    assert_eq!(
        p["occurrences"][0]["values"]["raw"]["value"],
        json!({"kind":"integer","decimal":"4"})
    );
    assert_eq!(p["occurrences"][0]["values"]["display"]["text"], "RAW");
}

#[test]
fn c15_rational_is_exact_and_normalization_does_not_reduce_it() {
    let p = projection(&metadata(), &["EXIF:ExposureTime"], true);
    let values = &p["occurrences"][0]["values"];
    assert_eq!(
        values["raw"]["value"],
        json!({"kind":"rational","numerator":"2","denominator":"500"})
    );
    assert_eq!(values["raw"], values["normalized"]);
    assert_eq!(values["normalization"]["reversibility"], "exact");
    assert_eq!(values["display"]["text"], "0.004");
}

#[test]
fn c16_text_value_is_literal_and_display_can_be_omitted() {
    let p = projection(&metadata(), &["DateTimeOriginal"], false);
    let values = &p["occurrences"][0]["values"];
    assert_eq!(values["raw"]["value"]["text"], "2026:01:02 03:04:05");
    assert_eq!(
        values["display"],
        json!({"state":"unavailable","reason":"Not requested"})
    );
}

#[test]
fn c17_invalid_rational_retains_origin_and_issue_without_value() {
    let mut bytes = support::fixture().bytes;
    let offset = support::field_offset(&bytes, b"CMT2", 0x829a);
    bytes[offset + 4..offset + 8].fill(0);
    let m = reader::read(Cursor::new(bytes), Limits::default()).unwrap();
    let p = projection(&m, &["EXIF:ExposureTime"], true);
    let o = &p["occurrences"][0];
    assert_eq!(o["values"]["raw"]["state"], "invalid");
    assert_eq!(o["values"]["normalized"]["state"], "invalid");
    assert_eq!(o["values"]["display"]["state"], "unavailable");
    assert_eq!(p["issues"][0]["code"], "ZERO_DENOMINATOR");
    let resource = p["resources"]
        .as_array()
        .unwrap()
        .iter()
        .find(|r| r["id"] == o["origin"]["resourceRef"])
        .unwrap();
    assert_eq!(
        resource["content"]["ranges"][0]["offset"],
        offset.to_string()
    );
    assert_eq!(resource["byteLength"], "8");
}

#[test]
fn c18_binary_value_is_a_source_range_reference_not_retained_payload() {
    let m = metadata();
    let p = projection(&m, &["ThumbnailImage"], true);
    let v = &p["occurrences"][0]["values"]["raw"]["value"];
    assert_eq!(v, &json!({"kind":"binary","resourceRef":"preview-0"}));
    let resource = p["resources"]
        .as_array()
        .unwrap()
        .iter()
        .find(|r| r["id"] == "preview-0")
        .unwrap();
    assert_eq!(resource["content"]["kind"], "source-ranges");
    assert!(resource["sha256"].is_null());
}

#[test]
fn c19_caller_supplies_snapshot_labels_without_source_authority() {
    let m = metadata();
    let p = m.snapshot("caller-id", "caller-label", &selected(&m, &["Make"]), false);
    assert_eq!(p["id"], "caller-id");
    assert_eq!(p["sources"][0]["displayPath"], "caller-label");
    assert_eq!(p["sources"][0]["identity"]["kind"], "unavailable");
    assert_eq!(p["basis"], "observed");
}

#[test]
fn c20_static_names_freeze_finite_definitions_separate_from_observation() {
    assert_eq!(
        reader::NAMES,
        [
            "ThumbnailImage",
            "PreviewImage",
            "JpgFromRaw",
            "Make",
            "Model",
            "ImageWidth",
            "ImageHeight",
            "ExposureTime",
            "FNumber",
            "ISO",
            "FocalLength",
            "DateTimeOriginal",
            "OffsetTimeOriginal",
            "SubSecTimeOriginal",
            "PixelXDimension",
            "PixelYDimension",
            "CanonFirmwareVersion",
            "CanonModelID",
            "Quality",
            "DualPixelRaw"
        ]
    );
    assert!(!reader::NAMES.contains(&"ExifImageWidth"));
    for name in reader::NAMES {
        assert_eq!(reader::selector(name).unwrap(), (None, *name));
    }
    assert_eq!(reader::READER_REVISION, "r5-read-slice-2026-10-11.1");
    assert_eq!(imageinfo::CAPABILITY_DATA_REVISION, "2026-10-12.1");
}

#[test]
fn c21_format_detection_uses_bytes_instead_of_filename_extension() {
    let dir = support::TempDir::new();
    let path = dir.path.join("authored.unrelated");
    fs::write(&path, support::fixture().bytes).unwrap();
    assert_eq!(
        projection(
            &reader::read_file(&path, Limits::default()).unwrap(),
            &["Make"],
            false
        )["documents"][0]["format"],
        "CR3"
    );
    let invalid = dir.path.join("invalid.cr3");
    fs::write(&invalid, b"not a supported container").unwrap();
    assert!(reader::read_file(&invalid, Limits::default()).is_err());
}

#[test]
fn c22_request_result_distinguishes_unobserved_from_unknown_selector() {
    let dir = support::TempDir::new();
    let path = dir.path.join("authored.cr3");
    fs::write(&path, support::fixture().bytes).unwrap();
    let execute = |tag: &str| {
        imageinfo::read_request::execute(
            "consumer",
            &[
                "metadata".into(),
                "read".into(),
                "--tag".into(),
                tag.into(),
                path.as_os_str().to_owned(),
            ],
        )
    };
    let absent = execute("Canon:ISO");
    assert_eq!(absent.files[0].state, "read");
    assert!(
        absent.files[0]
            .issues
            .iter()
            .any(|i| i.code == "TAG_UNRESOLVED")
    );
    assert!(
        absent.files[0]
            .issues
            .iter()
            .any(|i| i.code == "COVERAGE_PARTIAL")
    );
    assert_eq!(
        absent.files[0].snapshot.as_ref().unwrap()["occurrences"],
        json!([])
    );
    let mixed = imageinfo::read_request::execute(
        "consumer",
        &[
            "metadata".into(),
            "read".into(),
            "--tag".into(),
            "EXIF:ISO".into(),
            "--tag".into(),
            "Canon:ISO".into(),
            path.as_os_str().to_owned(),
        ],
    );
    assert_eq!(
        mixed.files[0].snapshot.as_ref().unwrap()["occurrences"]
            .as_array()
            .unwrap()
            .len(),
        1
    );
    assert!(
        !mixed.files[0]
            .issues
            .iter()
            .any(|i| i.code == "TAG_UNRESOLVED")
    );
    let unknown = execute("UnknownTag");
    assert!(unknown.files.is_empty());
    assert!(
        unknown
            .request
            .issues
            .iter()
            .any(|i| i.code == "TAG_UNSUPPORTED")
    );
}
