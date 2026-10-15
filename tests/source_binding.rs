#[allow(dead_code)]
mod support;
use imageinfo::{
    plan::{PreviewPlan, Revisions, Sha256Digest},
    source_binding::{self, BindingFinding},
};
use std::{
    fs,
    io::{self, Cursor, Read, Seek, SeekFrom},
};

const INTENT: &str = "2000:02:29 23:59:59";
fn fixture() -> Vec<u8> {
    support::fixture_with_previews(
        "Firmware Version 2.2.1",
        vec![0xff, 0xd8, 0xff, 0xd9],
        vec![0xff, 0xd8, 0xff, 0xd9],
        vec![0xff, 0xd8, 0xff, 0xd9],
    )
    .bytes
}
fn capture(bytes: &[u8]) -> source_binding::BoundPreview {
    source_binding::capture(Cursor::new(bytes), "source.cr3", "new-output.cr3", INTENT).unwrap()
}
fn has(report: &source_binding::BindingReport, finding: BindingFinding) -> bool {
    report.findings.contains(&finding)
}
fn entry(bytes: &[u8], tag: u16) -> usize {
    let base = bytes.windows(4).position(|w| w == b"CMT2").unwrap() + 4;
    let count = u16::from_le_bytes(bytes[base + 8..base + 10].try_into().unwrap()) as usize;
    (0..count)
        .map(|i| base + 10 + i * 12)
        .find(|&at| bytes[at..at + 2] == tag.to_le_bytes())
        .unwrap()
}

#[test]
fn exact_source_and_imported_plan_match_but_never_enable_mutation() {
    let bytes = fixture();
    let bound = capture(&bytes);
    assert_eq!(bound.plan.saved().revisions, Revisions::default());
    assert!(!bound.preview.production_mutation_allowed);
    let imported = PreviewPlan::from_json(&serde_json::to_string(&bound.plan).unwrap()).unwrap();
    let report = source_binding::revalidate(Cursor::new(&bytes), &imported).unwrap();
    assert!(
        report.binding_matches
            && report.source_revision_matches
            && report.occurrence_matches
            && report.original_bytes_match
    );
    assert!(has(&report, BindingFinding::FormatAdmissionRefused));
    assert!(has(&report, BindingFinding::StorageProfileUnavailable));
    assert!(
        !report.production_mutation_allowed && !report.preview.unwrap().production_mutation_allowed
    );
    assert_eq!(capture(&bytes).plan, bound.plan);
}

#[test]
fn whole_source_digest_detects_change_outside_selected_date() {
    let mut bytes = fixture();
    let bound = capture(&bytes);
    let at = bytes.len() - 1;
    bytes[at] ^= 1;
    let report = source_binding::revalidate(Cursor::new(bytes), &bound.plan).unwrap();
    assert!(!report.binding_matches && !report.source_revision_matches);
    assert!(report.occurrence_matches && report.original_bytes_match);
    assert!(has(&report, BindingFinding::SourceRevisionChanged));
    assert!(report.preview.is_none());
}

#[test]
fn changed_original_bytes_refuse_without_silently_replanning() {
    let mut bytes = fixture();
    let bound = capture(&bytes);
    let offset = bound.plan.saved().occurrence.allocation.offset as usize;
    bytes[offset..offset + 20].copy_from_slice(b"2025:01:02 03:04:05\0");
    let report = source_binding::revalidate(Cursor::new(bytes), &bound.plan).unwrap();
    assert!(report.occurrence_matches && !report.original_bytes_match);
    assert!(has(&report, BindingFinding::OriginalBytesChanged));
    assert!(!report.binding_matches && report.preview.is_none());
}

#[test]
fn missing_and_ambiguous_actual_occurrences_refuse() {
    let original = fixture();
    let plan = capture(&original).plan;
    for (old, new) in [(0x9003u16, 0x9004u16), (0x9011, 0x9003)] {
        let mut bytes = original.clone();
        let at = entry(&bytes, old);
        bytes[at..at + 2].copy_from_slice(&new.to_le_bytes());
        let report = source_binding::revalidate(Cursor::new(&bytes), &plan).unwrap();
        assert!(has(&report, BindingFinding::OccurrenceMissingOrAmbiguous));
        assert!(!report.binding_matches && report.preview.is_none());
        assert_eq!(
            source_binding::capture(Cursor::new(bytes), "source.cr3", "out.cr3", INTENT)
                .unwrap_err()
                .code,
            "FIELD_MISSING_OR_AMBIGUOUS"
        );
    }
}

#[test]
fn exact_binding_vectors_refuse_changed_path_allocation_order_and_old_bytes() {
    let bytes = fixture();
    let bound = capture(&bytes);
    for case in 0..5 {
        let mut saved = bound.plan.saved().clone();
        let expected = match case {
            0 => {
                saved.occurrence.path[0].index += 1;
                BindingFinding::OccurrenceChanged
            }
            1 => {
                saved.occurrence.allocation.offset += 1;
                BindingFinding::OccurrenceChanged
            }
            2 => {
                saved.occurrence.byte_order = imageinfo::plan::ByteOrder::BigEndian;
                BindingFinding::OccurrenceChanged
            }
            3 => {
                saved.occurrence.original_bytes = *b"2025:01:02 03:04:05\0";
                BindingFinding::OriginalBytesChanged
            }
            _ => {
                saved.source.sha256 = Sha256Digest::try_from("0".repeat(64)).unwrap();
                BindingFinding::SourceRevisionChanged
            }
        };
        let imported = PreviewPlan::new(saved).unwrap();
        let report = source_binding::revalidate(Cursor::new(&bytes), &imported).unwrap();
        assert!(has(&report, expected), "case {case}");
        assert!(
            !report.binding_matches
                && report.preview.is_none()
                && !report.production_mutation_allowed
        );
    }
}

#[test]
fn stale_revision_and_invented_authority_profile_refuse_before_source_inspection() {
    let bound = capture(&fixture());
    for pointer in [
        "/revisions/reader",
        "/revisions/capability",
        "/output/profile",
        "/apply_authorization",
    ] {
        let mut wire = serde_json::to_value(&bound.plan).unwrap();
        *wire.pointer_mut(pointer).unwrap() = "invented-or-stale".into();
        assert!(PreviewPlan::from_json(&wire.to_string()).is_err());
    }
}

#[test]
fn big_endian_capture_revalidation_and_equal_date_intent_work_read_only() {
    let mut bytes = fixture();
    support::big_endian_tiff_boxes(&mut bytes);
    let bound = source_binding::capture(
        Cursor::new(&bytes),
        "source.cr3",
        "new.cr3",
        "2026:01:02 03:04:05",
    )
    .unwrap();
    assert_eq!(
        bound.plan.saved().occurrence.byte_order,
        imageinfo::plan::ByteOrder::BigEndian
    );
    let report = source_binding::revalidate(Cursor::new(bytes), &bound.plan).unwrap();
    assert!(report.binding_matches);
    let preview = report.preview.unwrap();
    assert!(preview.value_already_matches && preview.changed_ranges.is_empty());
    assert!(!report.production_mutation_allowed);
}

#[test]
fn file_capture_revalidation_creates_no_output_and_same_bytes_replacement_is_only_content_equality()
{
    // Keep rename evidence inside the workspace's permitted filesystem root.
    let temp = support::TempDir {
        path: std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("target")
            .join(format!("source-binding-test-{}", std::process::id())),
    };
    fs::create_dir(&temp.path).unwrap();
    let source = temp.path.join("source.cr3");
    let output = temp.path.join("output.cr3");
    let bytes = fixture();
    fs::write(&source, &bytes).unwrap();
    let bound = source_binding::capture_file(&source, &output, INTENT).unwrap();
    assert!(!output.exists());
    assert_eq!(fs::read(&source).unwrap(), bytes);
    assert_eq!(
        source_binding::capture_file(&temp.path, &output, INTENT)
            .unwrap_err()
            .code,
        "CAPABILITY_UNSUPPORTED"
    );
    let mut directory_source = bound.plan.saved().clone();
    directory_source.source.path = temp.path.to_str().unwrap().into();
    assert_eq!(
        source_binding::revalidate_file(&PreviewPlan::new(directory_source).unwrap())
            .unwrap_err()
            .code,
        "CAPABILITY_UNSUPPORTED"
    );
    // The previous object is retained under another name, proving replacement
    // rather than modification of its contents. The protocol claims no object guard.
    fs::rename(&source, temp.path.join("old-source.cr3")).unwrap();
    fs::write(&source, &bytes).unwrap();
    let report = source_binding::revalidate_file(&bound.plan).unwrap();
    assert!(report.binding_matches && !report.production_mutation_allowed);
    assert!(!output.exists());
    assert_eq!(fs::read(&source).unwrap(), bytes);
    fs::write(&output, b"existing foreign output").unwrap();
    assert!(
        source_binding::revalidate_file(&bound.plan)
            .unwrap()
            .binding_matches
    );
    assert_eq!(fs::read(output).unwrap(), b"existing foreign output");
}

struct Oversized;
impl Read for Oversized {
    fn read(&mut self, _: &mut [u8]) -> io::Result<usize> {
        panic!("must refuse before reading")
    }
}
impl Seek for Oversized {
    fn seek(&mut self, _: SeekFrom) -> io::Result<u64> {
        Ok(source_binding::MAX_SOURCE_BYTES + 1)
    }
}
#[test]
fn unsupported_and_oversized_sources_never_create_an_effect() {
    assert_eq!(
        source_binding::capture(Oversized, "source.cr3", "out.cr3", INTENT)
            .unwrap_err()
            .code,
        "LIMIT_EXCEEDED"
    );
    assert!(
        source_binding::capture(Cursor::new(b"not CR3"), "source.cr3", "out.cr3", INTENT).is_err()
    );
    let bound = capture(&fixture());
    assert!(source_binding::revalidate(Cursor::new(b"not CR3"), &bound.plan).is_err());
}
