// Shared independently authored structural generator; unrelated helper methods
// remain unused because this suite does not extract previews or mutate files.
#[allow(dead_code)]
#[path = "../../../tests/support/mod.rs"]
mod support;

use imageinfo_privacy_coverage_research::{Cell, CoverageState, Report, inspect};
use std::collections::BTreeSet;

fn selected<'a>(report: &'a Report, id: &str, location: &str) -> &'a Cell {
    report
        .cells
        .iter()
        .find(|cell| cell.entry_id == id && cell.location == location)
        .expect("authored selector/location exists")
}

fn no_certificate(report: &Report) {
    assert!(!report.privacy_absence_certified);
    assert!(!report.anonymity_established);
    assert!(!report.removal_implemented);
    assert!(!report.production_mutation_allowed);
}

fn replace_cmt(mut bytes: Vec<u8>, kind: &[u8; 4], payload: Vec<u8>) -> Vec<u8> {
    let at = bytes.windows(4).position(|part| part == kind).unwrap() - 4;
    let old_length = u32::from_be_bytes(bytes[at..at + 4].try_into().unwrap()) as usize;
    let canon_uuid = [
        0x85, 0xc0, 0xb6, 0x87, 0x82, 0x0f, 0x11, 0xe0, 0x81, 0x11, 0xf4, 0xce, 0x46, 0x2b, 0x6a,
        0x48,
    ];
    let canon = bytes
        .windows(16)
        .position(|part| part == canon_uuid)
        .unwrap()
        - 8;
    let moov = bytes.windows(4).position(|part| part == b"moov").unwrap() - 4;
    let replacement = support::atom(kind, payload);
    let delta = replacement.len() as i64 - old_length as i64;
    bytes.splice(at..at + old_length, replacement);
    for parent in [canon, moov] {
        let size = i64::from(u32::from_be_bytes(
            bytes[parent..parent + 4].try_into().unwrap(),
        ));
        bytes[parent..parent + 4]
            .copy_from_slice(&u32::try_from(size + delta).unwrap().to_be_bytes());
    }
    let offsets: Vec<_> = bytes
        .windows(4)
        .enumerate()
        .filter_map(|(index, part)| (part == b"co64").then_some(index + 12))
        .collect();
    for offset in offsets {
        let value = u64::from_be_bytes(bytes[offset..offset + 8].try_into().unwrap());
        let changed = u64::try_from(i64::try_from(value).unwrap() + delta).unwrap();
        bytes[offset..offset + 8].copy_from_slice(&changed.to_be_bytes());
    }
    bytes
}

fn packet(description: &str, declarations: &str) -> Vec<u8> {
    format!(
        "<rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'><rdf:Description {declarations}>{description}</rdf:Description></rdf:RDF>"
    )
    .into_bytes()
}

#[test]
fn denominator_is_expanded_known_documents_not_global_coverage() {
    let fixture = support::fixture();
    let before = fixture.bytes.clone();
    let report = inspect(&fixture.bytes, None).unwrap();
    assert_eq!(report.catalog_entries, 31);
    assert_eq!(report.location_templates, 59);
    assert_eq!(
        report.expanded_cells,
        31 + 28 * report.declared_previews.len()
    );
    assert_eq!(report.cells.len(), 115);
    let keys: BTreeSet<_> = report
        .cells
        .iter()
        .map(|cell| (&cell.entry_id, &cell.location, &cell.document))
        .collect();
    assert_eq!(keys.len(), report.cells.len());
    assert!(!report.residuals.is_empty());
    assert_eq!(fixture.bytes, before);
    no_certificate(&report);
}

#[test]
fn duplicate_zero_and_empty_opaque_allocations_are_candidates_not_absence() {
    let raw = replace_cmt(
        support::fixture().bytes,
        b"CMT4",
        support::tiff(vec![(1, 3, vec![0, 0]), (1, 2, vec![])]),
    );
    let report = inspect(&raw, None).unwrap();
    let cell = selected(&report, "R5P-001", "cr3.cmt4.gps");
    assert_eq!(cell.state, CoverageState::Uninspectable);
    assert!(cell.occurrences.is_empty());
    assert_eq!(cell.allocation_candidates.len(), 2);
    assert_eq!(cell.allocation_candidates[1].length, 0);
    assert_ne!(
        cell.allocation_candidates[0].path.last().unwrap().index,
        cell.allocation_candidates[1].path.last().unwrap().index
    );
    no_certificate(&report);
}

#[test]
fn equal_numeric_ids_in_wrong_cmt_context_do_not_select_another_catalog_entry() {
    let raw = replace_cmt(
        replace_cmt(
            support::fixture().bytes,
            b"CMT2",
            support::tiff(vec![
                (1, 3, vec![0, 0]),
                (0xa430, 2, b"authored\0".to_vec()),
            ]),
        ),
        b"CMT4",
        support::tiff(vec![
            (1, 3, vec![0, 0]),
            (0xa430, 2, b"authored\0".to_vec()),
        ]),
    );
    let report = inspect(&raw, None).unwrap();
    assert_eq!(
        selected(&report, "R5P-001", "cr3.cmt4.gps")
            .allocation_candidates
            .len(),
        1
    );
    assert_eq!(
        selected(&report, "R5P-013", "cr3.cmt2.exif")
            .allocation_candidates
            .len(),
        1
    );
    assert!(
        report
            .cells
            .iter()
            .filter(|cell| cell.location.starts_with("cr3."))
            .all(|cell| {
                cell.state == CoverageState::Uninspectable && cell.occurrences.is_empty()
            })
    );
}

#[test]
fn nested_ifd_role_loss_remains_uninspectable_even_with_a_matching_tag_number() {
    let mut tiff = support::tiff(vec![(0x8769, 4, 26u32.to_le_bytes().to_vec())]);
    assert_eq!(tiff.len(), 26);
    tiff.extend(1u16.to_le_bytes());
    tiff.extend(1u16.to_le_bytes());
    tiff.extend(3u16.to_le_bytes());
    tiff.extend(1u32.to_le_bytes());
    tiff.extend([0, 0, 0, 0]);
    tiff.extend([0; 4]);
    let raw = replace_cmt(support::fixture().bytes, b"CMT4", tiff);
    let report = inspect(&raw, None).unwrap();
    let cell = selected(&report, "R5P-001", "cr3.cmt4.gps");
    assert_eq!(cell.state, CoverageState::Uninspectable);
    assert!(cell.occurrences.is_empty());
    assert_eq!(cell.allocation_candidates.len(), 1);
    assert!(
        cell.allocation_candidates[0]
            .path
            .iter()
            .any(|part| part.kind == "ifd" && part.name == "IFD@26")
    );
}

#[test]
fn exact_sidecar_duplicates_retain_form_ordinal_and_logical_path_without_values() {
    let sidecar = packet(
        "<a:OwnerName/><a:OwnerName/>",
        "xmlns:a='http://ns.adobe.com/exif/1.0/aux/' a:OwnerName=''",
    );
    let report = inspect(&support::fixture().bytes, Some(&sidecar)).unwrap();
    let cell = selected(&report, "R5P-026", "sidecar.xmp");
    assert_eq!(cell.state, CoverageState::ObservedRetained);
    assert_eq!(cell.occurrences.len(), 3);
    let wire = serde_json::to_value(cell).unwrap();
    assert_eq!(wire["occurrences"][0]["form"], "attribute");
    assert_eq!(wire["occurrences"][1]["form"], "element");
    assert_ne!(
        wire["occurrences"][0]["ordinal"],
        wire["occurrences"][1]["ordinal"]
    );
    assert_ne!(
        wire["occurrences"][1]["path"],
        wire["occurrences"][2]["path"]
    );
    assert!(
        wire["occurrences"]
            .as_array()
            .unwrap()
            .iter()
            .all(|item| item.get("value").is_none())
    );
    no_certificate(&report);
}

#[test]
fn same_labels_wrong_uri_case_or_trailing_slash_never_alias_exact_names() {
    for uri in [
        "urn:authored:unknown",
        "http://ns.adobe.com/exif/1.0/aux",
        "http://NS.adobe.com/exif/1.0/aux/",
    ] {
        let sidecar = packet(
            "<a:OwnerName>authored</a:OwnerName>",
            &format!("xmlns:a='{uri}'"),
        );
        let report = inspect(&support::fixture().bytes, Some(&sidecar)).unwrap();
        let cell = selected(&report, "R5P-026", "sidecar.xmp");
        assert_eq!(cell.state, CoverageState::CheckedNoExactPropertyMatch);
        assert!(cell.occurrences.is_empty());
        no_certificate(&report);
    }
}

#[test]
fn unselected_sidecar_is_unexamined_and_no_same_stem_search_is_implied() {
    let report = inspect(&support::fixture().bytes, None).unwrap();
    assert!(
        report
            .cells
            .iter()
            .filter(|cell| cell.location == "sidecar.xmp")
            .all(|cell| { cell.state == CoverageState::Unexamined && cell.occurrences.is_empty() })
    );
}

#[test]
fn unsupported_nested_or_qualified_xmp_prevents_checked_coverage() {
    for description in [
        "<a:OwnerName a:qualifier='authored'>text</a:OwnerName>",
        "<a:wrapper><a:OwnerName>authored</a:OwnerName></a:wrapper>",
    ] {
        let sidecar = packet(description, "xmlns:a='http://ns.adobe.com/exif/1.0/aux/'");
        let report = inspect(&support::fixture().bytes, Some(&sidecar)).unwrap();
        assert!(
            report
                .cells
                .iter()
                .filter(|cell| cell.location == "sidecar.xmp")
                .all(|cell| {
                    cell.state == CoverageState::Uninspectable && cell.occurrences.is_empty()
                })
        );
        no_certificate(&report);
    }
}

#[test]
fn preview_payload_lookalikes_are_retained_but_metadata_is_not_inspected() {
    let marker = b"\xff\xd8<a:OwnerName>authored-private-lookalike</a:OwnerName>\xff\xd9".to_vec();
    let fixture = support::fixture_with_previews(
        "Firmware Version test",
        marker.clone(),
        marker.clone(),
        marker,
    );
    let report = inspect(&fixture.bytes, None).unwrap();
    assert_eq!(report.declared_previews.len(), 3);
    assert!(
        report
            .cells
            .iter()
            .filter(|cell| cell.location.starts_with("preview."))
            .all(|cell| {
                cell.state == CoverageState::Uninspectable && cell.occurrences.is_empty()
            })
    );
    assert!(
        !serde_json::to_string(&report)
            .unwrap()
            .contains("authored-private-lookalike")
    );
}

#[test]
fn malformed_raw_cannot_return_an_absence_report() {
    assert!(inspect(b"authored-not-a-RAW-container", None).is_err());
}

#[test]
fn cli_reads_only_explicit_inputs_and_preserves_authored_files() {
    let directory = support::TempDir::new();
    let raw = directory.path.join("authored.cr3");
    let sidecar = directory.path.join("authored.xmp");
    let source = support::fixture().bytes;
    std::fs::write(&raw, &source).unwrap();
    let sidecar_source = packet(
        "<a:OwnerName>authored-neighbor-sentinel</a:OwnerName>",
        "xmlns:a='http://ns.adobe.com/exif/1.0/aux/'",
    );
    std::fs::write(&sidecar, &sidecar_source).unwrap();
    let before = std::fs::metadata(&raw).unwrap().modified().unwrap();
    let result =
        std::process::Command::new(env!("CARGO_BIN_EXE_imageinfo-privacy-coverage-research"))
            .arg(&raw)
            .output()
            .unwrap();
    assert!(result.status.success());
    assert!(result.stderr.is_empty());
    let report: serde_json::Value = serde_json::from_slice(&result.stdout).unwrap();
    assert!(
        report["cells"]
            .as_array()
            .unwrap()
            .iter()
            .filter(|cell| cell["location"] == "sidecar.xmp")
            .all(|cell| cell["state"] == "unexamined")
    );
    assert!(
        !String::from_utf8(result.stdout)
            .unwrap()
            .contains("authored-neighbor-sentinel")
    );
    assert_eq!(std::fs::read(&raw).unwrap(), source);
    assert_eq!(std::fs::read(&sidecar).unwrap(), sidecar_source);
    assert_eq!(std::fs::metadata(&raw).unwrap().modified().unwrap(), before);
    assert_eq!(std::fs::read_dir(&directory.path).unwrap().count(), 2);
}

#[test]
fn cli_missing_input_reports_a_fixed_code_without_disclosing_the_argument() {
    let directory = support::TempDir::new();
    let absent = directory
        .path
        .join("authored-argument-must-not-be-echoed.cr3");
    let result =
        std::process::Command::new(env!("CARGO_BIN_EXE_imageinfo-privacy-coverage-research"))
            .arg(absent)
            .output()
            .unwrap();
    assert!(!result.status.success());
    assert!(result.stdout.is_empty());
    assert_eq!(String::from_utf8(result.stderr).unwrap().trim(), "INPUT_IO");
}

#[cfg(unix)]
#[test]
fn cli_non_unicode_path_is_handled_without_argument_panic_or_path_disclosure() {
    use std::os::unix::ffi::OsStringExt;
    let directory = support::TempDir::new();
    let path = directory
        .path
        .join(std::ffi::OsString::from_vec(b"authored-\xff.cr3".to_vec()));
    #[cfg(not(target_os = "macos"))]
    std::fs::write(&path, support::fixture().bytes).unwrap();
    // APFS rejects invalid UTF-8 filenames. A lossy-display neighbor must not be
    // opened on behalf of the distinct invalid native argument.
    #[cfg(target_os = "macos")]
    let neighbor = {
        let neighbor = directory.path.join("authored-\u{fffd}.cr3");
        std::fs::write(&neighbor, support::fixture().bytes).unwrap();
        neighbor
    };
    let result =
        std::process::Command::new(env!("CARGO_BIN_EXE_imageinfo-privacy-coverage-research"))
            .arg(&path)
            .output()
            .unwrap();
    #[cfg(not(target_os = "macos"))]
    {
        assert!(result.status.success());
        assert!(result.stderr.is_empty());
        let report: serde_json::Value = serde_json::from_slice(&result.stdout).unwrap();
        assert_eq!(report["privacyAbsenceCertified"], false);
    }
    #[cfg(target_os = "macos")]
    {
        assert!(!result.status.success());
        assert!(result.stdout.is_empty());
        assert_eq!(String::from_utf8(result.stderr).unwrap().trim(), "INPUT_IO");
        assert_eq!(std::fs::read(neighbor).unwrap(), support::fixture().bytes);
    }
    let absent = directory
        .path
        .join(std::ffi::OsString::from_vec(b"missing-\xff.cr3".to_vec()));
    let missing =
        std::process::Command::new(env!("CARGO_BIN_EXE_imageinfo-privacy-coverage-research"))
            .arg(absent)
            .output()
            .unwrap();
    assert!(!missing.status.success());
    assert!(missing.stdout.is_empty());
    assert_eq!(
        String::from_utf8(missing.stderr).unwrap().trim(),
        "INPUT_IO"
    );
    let usage =
        std::process::Command::new(env!("CARGO_BIN_EXE_imageinfo-privacy-coverage-research"))
            .arg(&path)
            .arg(std::ffi::OsString::from_vec(vec![0xff]))
            .arg("authored.xmp")
            .output()
            .unwrap();
    assert!(!usage.status.success());
    assert!(usage.stdout.is_empty());
    assert_eq!(
        String::from_utf8(usage.stderr).unwrap().trim(),
        "USAGE: imageinfo-privacy-coverage-research RAW [--sidecar XMP]"
    );
}

#[cfg(windows)]
#[test]
fn cli_unpaired_utf16_path_is_not_converted_or_disclosed() {
    use std::os::windows::ffi::OsStringExt;
    let directory = support::TempDir::new();
    let mut units: Vec<_> = "authored-".encode_utf16().collect();
    units.push(0xd800);
    units.extend(".cr3".encode_utf16());
    let path = directory.path.join(std::ffi::OsString::from_wide(&units));
    let source = support::fixture().bytes;
    std::fs::write(&path, &source).unwrap();
    let result =
        std::process::Command::new(env!("CARGO_BIN_EXE_imageinfo-privacy-coverage-research"))
            .arg(&path)
            .output()
            .unwrap();
    assert!(result.status.success());
    assert!(result.stderr.is_empty());
    let report: serde_json::Value = serde_json::from_slice(&result.stdout).unwrap();
    assert_eq!(report["privacyAbsenceCertified"], false);
    assert_eq!(std::fs::read(path).unwrap(), source);
}
