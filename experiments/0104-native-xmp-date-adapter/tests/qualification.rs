//! Independent authored CR3/XML integration vectors. No camera fixtures or I/O API.
#[allow(dead_code)]
#[path = "../../../tests/support/mod.rs"]
mod support;

use imageinfo_native_xmp_date_adapter_research::{Candidate, Refusal, prepare};
use imageinfo_xmp_date_mapping_research::{
    ConflictPolicy, Decision, Loss, Refusal as MappingRefusal,
};
use imageinfo_xmp_model_research::{Limits, Value, inspect};
use imageinfo_xmp_preservation_research::{Kind, Refusal as PreservationRefusal};
use std::{borrow::Cow, fs};

const TARGET: &str = "http://ns.adobe.com/exif/1.0/";
const OLD: &str = "2020-02-29T01:02:03";
const MAPPED: &str = "2026-01-02T03:04:05.00+00:00";

fn fixture() -> Vec<u8> {
    support::fixture_with_previews(
        "Firmware Version 2.2.1",
        vec![255, 216, 255, 217],
        vec![255, 216, 255, 217],
        vec![255, 216, 255, 217],
    )
    .bytes
}
fn xml(date: &str) -> String {
    format!(
        "<?xml version='1.0'?>\r\n<r:RDF xmlns:r='http://www.w3.org/1999/02/22-rdf-syntax-ns#' xmlns:e='{TARGET}' xmlns:u='urn:authored:untouched'><r:Description r:about=''><u:note>unknown&lt;kept&gt;</u:note><e:DateTimeOriginal>{date}</e:DateTimeOriginal><u:values><r:Seq><r:li>second</r:li><r:li>first</r:li></r:Seq></u:values></r:Description></r:RDF>\r\n"
    )
}
fn ordinal(xmp: &[u8]) -> usize {
    inspect(xmp, Limits::default())
        .unwrap()
        .properties
        .iter()
        .find(|p| p.name.namespace == TARGET && p.name.local == "DateTimeOriginal")
        .unwrap()
        .ordinal
}
fn replace() -> ConflictPolicy<'static> {
    ConflictPolicy::ReplaceSelected { acknowledged: &[] }
}
fn no_authority(candidate: &Candidate<'_>) {
    assert!(!candidate.publication_allowed);
    assert!(!candidate.raw_mutation_allowed);
    assert!(!candidate.storage_profile_admitted);
    assert!(!candidate.prepared.production_mutation_allowed);
}
fn base(raw: &[u8]) -> usize {
    raw.windows(4).position(|p| p == b"CMT2").unwrap() + 4
}
fn entry(raw: &[u8], tag: u16) -> usize {
    let b = base(raw);
    let n = u16::from_le_bytes(raw[b + 8..b + 10].try_into().unwrap()) as usize;
    (0..n)
        .map(|i| b + 10 + i * 12)
        .find(|&i| raw[i..i + 2] == tag.to_le_bytes())
        .unwrap()
}
fn remove(raw: &mut [u8], tag: u16) {
    let b = base(raw);
    let n = u16::from_le_bytes(raw[b + 8..b + 10].try_into().unwrap()) as usize;
    let at = entry(raw, tag);
    raw.copy_within(at + 12..b + 10 + n * 12, at);
    raw[b + 10 + (n - 1) * 12..b + 14 + n * 12].fill(0);
    raw[b + 8..b + 10].copy_from_slice(&((n - 1) as u16).to_le_bytes());
}

#[test]
fn actual_native_source_fields_drive_only_the_selected_xmp_value() {
    let raw = fixture();
    let xmp = xml(OLD);
    let selected = ordinal(xmp.as_bytes());
    let candidate = prepare(&raw, xmp.as_bytes(), selected, replace()).unwrap();
    no_authority(&candidate);
    assert_eq!(candidate.prepared.kind, Kind::Derivative);
    assert!(matches!(candidate.prepared.bytes, Cow::Owned(_)));
    assert!(!candidate.prepared.production_mutation_allowed);
    let changed = candidate.prepared.changed.as_ref().unwrap();
    let start = xmp.find(OLD).unwrap();
    assert_eq!(changed.original, start..start + OLD.len());
    assert_eq!(changed.derivative, start..start + MAPPED.len());
    let expected = xmp.replacen(OLD, MAPPED, 1);
    assert_eq!(candidate.prepared.bytes.as_ref(), expected.as_bytes());
    let mut expected_properties = inspect(xmp.as_bytes(), Limits::default())
        .unwrap()
        .properties;
    expected_properties
        .iter_mut()
        .find(|p| p.ordinal == selected)
        .unwrap()
        .value = Value::Text(MAPPED.into());
    assert_eq!(
        inspect(candidate.prepared.bytes.as_ref(), Limits::default())
            .unwrap()
            .properties,
        expected_properties
    );
    assert_eq!(&candidate.prepared.bytes[..start], &xmp.as_bytes()[..start]);
    assert_eq!(
        &candidate.prepared.bytes[changed.derivative.end..],
        &xmp.as_bytes()[changed.original.end..]
    );
    assert_eq!(candidate.source.len(), 3);
    for source in &candidate.source {
        assert!(source.path.iter().any(|p| p.name == "CMT2"));
        assert!(matches!(source.native_id, 0x9003 | 0x9291 | 0x9011));
        let stored = &raw
            [source.range.offset as usize..(source.range.offset + source.range.length) as usize];
        assert_eq!(stored.last(), Some(&0));
        assert_eq!(
            std::str::from_utf8(&stored[..stored.len() - 1]).unwrap(),
            source.text
        );
    }
    assert_eq!(candidate.raw_length, raw.len() as u64);
}

#[test]
fn no_op_borrows_exact_original_sidecar_after_actual_native_read() {
    let raw = fixture();
    let xmp = xml(MAPPED);
    let candidate = prepare(
        &raw,
        xmp.as_bytes(),
        ordinal(xmp.as_bytes()),
        ConflictPolicy::Refuse,
    )
    .unwrap();
    no_authority(&candidate);
    assert_eq!(candidate.prepared.kind, Kind::NoOp);
    assert!(matches!(candidate.prepared.bytes, Cow::Borrowed(_)));
    assert_eq!(candidate.prepared.bytes.as_ptr(), xmp.as_ptr());
    assert_eq!(candidate.prepared.bytes.as_ref(), xmp.as_bytes());
    assert!(candidate.prepared.changed.is_none());
}

#[test]
fn a_second_actual_native_snapshot_drives_its_own_date_fraction_and_zone() {
    let mut raw = fixture();
    let date = support::field_offset(&raw, b"CMT2", 0x9003);
    let fraction = support::field_offset(&raw, b"CMT2", 0x9291);
    let zone = support::field_offset(&raw, b"CMT2", 0x9011);
    raw[date..date + 20].copy_from_slice(b"2000:02:29 23:59:59\0");
    raw[fraction..fraction + 3].copy_from_slice(b"07\0");
    raw[zone..zone + 7].copy_from_slice(b"-05:30\0");
    let unchanged = raw.clone();
    let xmp = xml(OLD);
    let candidate = prepare(&raw, xmp.as_bytes(), ordinal(xmp.as_bytes()), replace()).unwrap();
    no_authority(&candidate);
    assert_eq!(
        candidate.prepared.bytes.as_ref(),
        xmp.replacen(OLD, "2000-02-29T23:59:59.07-05:30", 1)
            .as_bytes()
    );
    for (tag, text) in [
        (0x9003, "2000:02:29 23:59:59"),
        (0x9291, "07"),
        (0x9011, "-05:30"),
    ] {
        assert_eq!(
            candidate
                .source
                .iter()
                .find(|s| s.native_id == tag)
                .unwrap()
                .text,
            text
        );
    }
    assert_eq!(raw, unchanged);
}

#[test]
fn absent_companions_are_observed_from_exhaustive_known_cmt2_entries() {
    let mut raw = fixture();
    remove(&mut raw, 0x9291);
    remove(&mut raw, 0x9011);
    let xmp = xml(OLD);
    let candidate = prepare(&raw, xmp.as_bytes(), ordinal(xmp.as_bytes()), replace()).unwrap();
    assert_eq!(candidate.source.len(), 1);
    assert_eq!(
        candidate.prepared.bytes.as_ref(),
        xmp.replacen(OLD, "2026-01-02T03:04:05", 1).as_bytes()
    );
}

#[test]
fn opaque_cmt2_entry_never_supplies_a_forged_complete_coverage_attestation() {
    let xmp = xml(OLD);
    for unknown in [0x014au16, 0xff01] {
        let mut raw = fixture();
        let at = entry(&raw, 0x829a);
        raw[at..at + 2].copy_from_slice(&unknown.to_le_bytes());
        raw[at + 2..at + 4].copy_from_slice(&4u16.to_le_bytes());
        raw[at + 4..at + 8].copy_from_slice(&1u32.to_le_bytes());
        raw[at + 8..at + 12].copy_from_slice(&8u32.to_le_bytes());
        assert!(matches!(
            prepare(&raw, xmp.as_bytes(), ordinal(xmp.as_bytes()), replace()),
            Err(Refusal::IncompleteCmt2Coverage)
        ));
    }
}

#[test]
fn a_companion_from_a_second_ifd_is_not_combined_with_the_selected_primary() {
    let mut raw = fixture();
    let original = entry(&raw, 0x9011);
    let offset_entry = raw[original..original + 12].to_vec();
    remove(&mut raw, 0x9011);
    remove(&mut raw, 0x9291);
    let b = base(&raw);
    let count = u16::from_le_bytes(raw[b + 8..b + 10].try_into().unwrap()) as usize;
    let footer = b + 10 + count * 12;
    let second = footer + 4;
    raw[footer..footer + 4].copy_from_slice(&((second - b) as u32).to_le_bytes());
    raw[second..second + 2].copy_from_slice(&1u16.to_le_bytes());
    raw[second + 2..second + 14].copy_from_slice(&offset_entry);
    raw[second + 14..second + 18].fill(0);
    let xmp = xml(OLD);
    assert!(matches!(
        prepare(&raw, xmp.as_bytes(), ordinal(xmp.as_bytes()), replace()),
        Err(Refusal::SourcePath)
    ));
}

#[test]
fn missing_and_duplicate_source_occurrences_refuse_instead_of_choosing_one() {
    let xmp = xml(OLD);
    let selected = ordinal(xmp.as_bytes());
    let mut missing = fixture();
    remove(&mut missing, 0x9003);
    assert!(matches!(
        prepare(&missing, xmp.as_bytes(), selected, replace()),
        Err(Refusal::Sidecar(PreservationRefusal::Mapping(
            MappingRefusal::SourceCardinality
        )))
    ));
    for duplicate in [0x9003u16, 0x9291] {
        let mut raw = fixture();
        let at = entry(&raw, 0x9011);
        raw[at..at + 2].copy_from_slice(&duplicate.to_le_bytes());
        assert!(matches!(
            prepare(&raw, xmp.as_bytes(), selected, replace()),
            Err(Refusal::Sidecar(PreservationRefusal::Mapping(
                MappingRefusal::SourceCardinality
            )))
        ));
    }
}

#[test]
fn conflict_loss_and_target_selection_decisions_remain_explicit() {
    let raw = fixture();
    let xmp = xml(OLD);
    let selected = ordinal(xmp.as_bytes());
    for (policy, decision) in [
        (ConflictPolicy::Refuse, Decision::ConflictRefused),
        (ConflictPolicy::KeepDestination, Decision::KeepDestination),
    ] {
        assert!(
            matches!(prepare(&raw,xmp.as_bytes(),selected,policy),Err(Refusal::Sidecar(PreservationRefusal::Decision(actual))) if actual==decision)
        );
    }
    assert!(matches!(
        prepare(&raw, xmp.as_bytes(), selected + 1, replace()),
        Err(Refusal::Sidecar(PreservationRefusal::Mapping(
            MappingRefusal::TargetSelection
        )))
    ));
    let mut source = raw.clone();
    remove(&mut source, 0x9291);
    remove(&mut source, 0x9011);
    let xmp = xml("2020-02-29T01:02:03.123Z");
    let selected = ordinal(xmp.as_bytes());
    assert!(matches!(
        prepare(&source, xmp.as_bytes(), selected, replace()),
        Err(Refusal::Sidecar(PreservationRefusal::Decision(
            Decision::LossRefused
        )))
    ));
    let losses = [
        Loss::DestinationFractionDiscarded,
        Loss::DestinationZoneDiscarded,
    ];
    let candidate = prepare(
        &source,
        xmp.as_bytes(),
        selected,
        ConflictPolicy::ReplaceSelected {
            acknowledged: &losses,
        },
    )
    .unwrap();
    assert_eq!(
        candidate.prepared.bytes.as_ref(),
        xmp.replacen("2020-02-29T01:02:03.123Z", "2026-01-02T03:04:05", 1)
            .as_bytes()
    );
}

#[test]
fn reader_byte_order_and_exact_source_calendar_are_respected() {
    let mut raw = fixture();
    support::big_endian_tiff_boxes(&mut raw);
    let xmp = xml(OLD);
    let candidate = prepare(&raw, xmp.as_bytes(), ordinal(xmp.as_bytes()), replace()).unwrap();
    assert_eq!(
        candidate.prepared.bytes.as_ref(),
        xmp.replacen(OLD, MAPPED, 1).as_bytes()
    );
    let mut invalid = fixture();
    let at = support::field_offset(&invalid, b"CMT2", 0x9003);
    invalid[at..at + 20].copy_from_slice(b"2026:02:30 03:04:05\0");
    assert!(prepare(&invalid, xmp.as_bytes(), ordinal(xmp.as_bytes()), replace()).is_err());
}

#[test]
fn malformed_or_unbounded_inputs_refuse_without_any_candidate() {
    let raw = fixture();
    let xmp = xml(OLD);
    assert!(matches!(
        prepare(b"", xmp.as_bytes(), 0, replace()),
        Err(Refusal::Raw { .. })
    ));
    assert!(prepare(&raw, b"<r:broken>", 0, replace()).is_err());
    assert!(prepare(&raw, &vec![b' '; 65537], 0, replace()).is_err());
    let oversized = vec![0; 256 * 1024 * 1024 + 1];
    assert!(matches!(
        prepare(&oversized, xmp.as_bytes(), 0, replace()),
        Err(Refusal::RawTooLarge)
    ));
}

#[test]
fn actual_input_files_and_neighbor_remain_byte_name_and_mtime_unchanged() {
    let dir = support::TempDir::new();
    let raw_path = dir.path.join("authored.cr3");
    let xmp_path = dir.path.join("authored.xmp");
    let neighbor = dir.path.join("keep.marker");
    fs::write(&raw_path, fixture()).unwrap();
    fs::write(&xmp_path, xml(OLD)).unwrap();
    fs::write(&neighbor, b"owned-neighbor").unwrap();
    let before: Vec<_> = [&raw_path, &xmp_path, &neighbor]
        .into_iter()
        .map(|p| {
            (
                fs::read(p).unwrap(),
                fs::metadata(p).unwrap().modified().unwrap(),
            )
        })
        .collect();
    let raw = fs::read(&raw_path).unwrap();
    let xmp = fs::read(&xmp_path).unwrap();
    let candidate = prepare(&raw, &xmp, ordinal(&xmp), replace()).unwrap();
    assert_eq!(candidate.prepared.kind, Kind::Derivative);
    drop(candidate);
    assert!(prepare(&raw, &xmp, ordinal(&xmp), ConflictPolicy::Refuse).is_err());
    for (path, (bytes, time)) in [&raw_path, &xmp_path, &neighbor].into_iter().zip(before) {
        assert_eq!(fs::read(path).unwrap(), bytes);
        assert_eq!(fs::metadata(path).unwrap().modified().unwrap(), time);
    }
    assert_eq!(fs::read_dir(&dir.path).unwrap().count(), 3);
}
