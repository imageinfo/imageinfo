//! Public authored oracles; no real media, native handles, writes or custody evidence.
#[allow(dead_code)]
#[path = "../../../tests/support/mod.rs"]
mod support;

use imageinfo_privacy_artifact_audit::*;
use std::collections::BTreeSet;

const BEFORE: &[u8] = include_bytes!("fixtures/before.xmp");
const AFTER: &[u8] = include_bytes!("fixtures/derivative.xmp");
const ABSENT: &[u8] = include_bytes!("fixtures/absent.xmp");
const FALSE_REPORT: &[u8] = include_bytes!("fixtures/false-clean-report.txt");

fn slot<'a>(
    id: &'a str,
    bytes: &[u8],
    kind: ArtifactKind,
    role: Role,
    parent: Option<&'a str>,
) -> ManifestSlot<'a> {
    ManifestSlot {
        slot_id: id,
        operation_id: "op-authored",
        attempt_id: "attempt-1",
        document_id: id,
        kind,
        role,
        parent_slot: parent,
        length: bytes.len(),
        sha256: hash(bytes),
    }
}
fn snap<'a>(id: &'a str, bytes: &'a [u8]) -> Snapshot<'a> {
    Snapshot {
        slot_id: id,
        operation_id: "op-authored",
        attempt_id: "attempt-1",
        bytes,
    }
}
fn run(
    manifest: &[ManifestSlot<'_>],
    snapshots: &[Snapshot<'_>],
    claims: &[EffectClaim<'_>],
    limits: Limits,
) -> Result<Report, Refusal> {
    audit(
        &Request {
            operation_id: "op-authored",
            attempt_id: "attempt-1",
            manifest,
            snapshots,
            claims,
        },
        limits,
    )
}
fn uncertified(report: &Report) {
    assert!(!report.independently_enumerated_operation_complete);
    assert!(!report.privacy_absence_certified);
    assert!(!report.custody_established);
    assert!(!report.independent_format_evidence);
}
fn owner(report: &ArtifactReport) -> &imageinfo_privacy_coverage_research::Cell {
    report
        .cells
        .iter()
        .find(|cell| cell.entry_id == "R5P-026")
        .expect("owner selector")
}
fn claim(requested: RequestedEffect) -> EffectClaim<'static> {
    EffectClaim {
        before_slot: "original",
        after_slot: "derivative",
        selector: "R5P-026",
        requested,
    }
}

#[test]
fn authored_operation_preserves_every_artifact_and_duplicate_occurrence() {
    let raw = support::fixture().bytes;
    let entries = [
        (
            "raw",
            raw.as_slice(),
            ArtifactKind::Raw,
            Role::Original,
            None,
        ),
        ("original", BEFORE, ArtifactKind::Xmp, Role::Original, None),
        (
            "derivative",
            AFTER,
            ArtifactKind::Xmp,
            Role::Derivative,
            Some("original"),
        ),
        (
            "backup",
            BEFORE,
            ArtifactKind::Xmp,
            Role::Backup,
            Some("original"),
        ),
        (
            "staging",
            &b"<rdf:"[..],
            ArtifactKind::Opaque,
            Role::PartialStaging,
            Some("original"),
        ),
        (
            "recovery",
            BEFORE,
            ArtifactKind::Xmp,
            Role::Recovery,
            Some("original"),
        ),
        (
            "failure",
            &b"refused before publication"[..],
            ArtifactKind::Opaque,
            Role::Failure,
            Some("original"),
        ),
        (
            "report",
            FALSE_REPORT,
            ArtifactKind::Opaque,
            Role::Report,
            Some("original"),
        ),
    ];
    let manifest: Vec<_> = entries
        .iter()
        .map(|&(id, bytes, kind, role, parent)| slot(id, bytes, kind, role, parent))
        .collect();
    let snapshots: Vec<_> = entries
        .iter()
        .map(|&(id, bytes, _, _, _)| snap(id, bytes))
        .collect();
    let report = run(
        &manifest,
        &snapshots,
        &[claim(RequestedEffect::Removed)],
        Limits::default(),
    )
    .unwrap();
    assert_eq!(
        (report.catalog_entries, report.location_templates),
        (31, 59)
    );
    assert_eq!(report.artifacts.len(), 8);
    assert!(report.declared_set_complete);
    for id in ["original", "backup", "recovery"] {
        let artifact = report
            .artifacts
            .iter()
            .find(|item| item.slot_id == id)
            .unwrap();
        assert_eq!(artifact.cells.len(), 13);
        assert_eq!(
            owner(artifact).occurrences.len(),
            3,
            "manual authored count for {id}"
        );
        let identities: BTreeSet<_> = owner(artifact)
            .occurrences
            .iter()
            .map(|o| (o.ordinal, &o.path, o.form))
            .collect();
        assert_eq!(identities.len(), 3);
    }
    let derivative = report
        .artifacts
        .iter()
        .find(|item| item.slot_id == "derivative")
        .unwrap();
    assert_eq!(owner(derivative).occurrences.len(), 2);
    assert!(!report.effects[0].supported);
    assert_eq!(
        (
            report.effects[0].before_occurrences,
            report.effects[0].after_occurrences
        ),
        (3, 2)
    );
    assert!(report.issues.contains(&Issue::FalseEffectClaim));
    for id in ["staging", "failure", "report"] {
        let artifact = report
            .artifacts
            .iter()
            .find(|item| item.slot_id == id)
            .unwrap();
        assert!(artifact.cells.is_empty());
        assert!(artifact.issues.contains(&Issue::Uninspectable));
    }
    uncertified(&report);
}

#[test]
fn denominator_is_per_media_unit_without_fictitious_sidecar_or_nested_inspection() {
    let raw = support::fixture().bytes;
    let preview = support::fixture().preview;
    let manifest = [
        slot("raw", &raw, ArtifactKind::Raw, Role::Original, None),
        slot("xmp", BEFORE, ArtifactKind::Xmp, Role::Original, None),
        slot(
            "preview",
            &preview,
            ArtifactKind::RecognizedPreview,
            Role::Other,
            Some("raw"),
        ),
    ];
    let snapshots = [
        snap("raw", &raw),
        snap("xmp", BEFORE),
        snap("preview", &preview),
    ];
    let report = run(&manifest, &snapshots, &[], Limits::default()).unwrap();
    assert_eq!(report.artifacts[0].cells.len(), 18 + 3 * 28);
    assert!(
        report.artifacts[0]
            .cells
            .iter()
            .all(|cell| cell.location != "sidecar.xmp")
    );
    assert_eq!(report.artifacts[1].cells.len(), 13);
    assert_eq!(report.artifacts[2].cells.len(), 28);
    for cell in &report.artifacts[0].cells {
        assert_eq!(
            cell.state,
            imageinfo_privacy_coverage_research::CoverageState::Uninspectable
        );
    }
    assert!(report.artifacts[2].cells.iter().all(
        |cell| cell.state == imageinfo_privacy_coverage_research::CoverageState::Uninspectable
    ));
    uncertified(&report);
}

#[test]
fn independently_authored_absence_oracle_supports_only_exact_declared_derivative() {
    let manifest = [
        slot("original", BEFORE, ArtifactKind::Xmp, Role::Original, None),
        slot(
            "derivative",
            ABSENT,
            ArtifactKind::Xmp,
            Role::Derivative,
            Some("original"),
        ),
    ];
    let snapshots = [snap("original", BEFORE), snap("derivative", ABSENT)];
    for requested in [RequestedEffect::Removed, RequestedEffect::Absent] {
        let report = run(
            &manifest,
            &snapshots,
            &[claim(requested)],
            Limits::default(),
        )
        .unwrap();
        assert!(report.effects[0].supported);
        assert_eq!(
            (
                report.effects[0].before_occurrences,
                report.effects[0].after_occurrences
            ),
            (3, 0)
        );
        assert_eq!(owner(&report.artifacts[0]).occurrences.len(), 3);
        uncertified(&report);
    }
}

#[test]
fn missing_declared_artifact_cannot_hide_behind_a_clean_derivative() {
    let manifest = [
        slot("original", BEFORE, ArtifactKind::Xmp, Role::Original, None),
        slot(
            "backup",
            BEFORE,
            ArtifactKind::Xmp,
            Role::Backup,
            Some("original"),
        ),
    ];
    let report = run(
        &manifest,
        &[snap("original", BEFORE)],
        &[],
        Limits::default(),
    )
    .unwrap();
    assert!(!report.declared_set_complete);
    assert!(report.artifacts[1].issues.contains(&Issue::MissingSnapshot));
    uncertified(&report);
    // Omitting a slot from BOTH lists cannot be discovered: explicit set only.
    let report = run(
        &manifest[..1],
        &[snap("original", BEFORE)],
        &[],
        Limits::default(),
    )
    .unwrap();
    assert!(report.declared_set_complete);
    uncertified(&report);
}

#[test]
fn wrong_length_hash_attempt_operation_and_extra_snapshot_refuse_completeness() {
    for change in 0..5 {
        let mut manifest = [slot(
            "original",
            BEFORE,
            ArtifactKind::Xmp,
            Role::Original,
            None,
        )];
        let mut snapshots = vec![snap("original", BEFORE)];
        match change {
            0 => manifest[0].length += 1,
            1 => manifest[0].sha256[0] ^= 1,
            2 => snapshots[0].attempt_id = "wrong",
            3 => snapshots[0].operation_id = "wrong",
            _ => snapshots.push(snap("undeclared", BEFORE)),
        }
        let report = run(&manifest, &snapshots, &[], Limits::default()).unwrap();
        assert!(!report.declared_set_complete, "case {change}");
        uncertified(&report);
    }
}

#[test]
fn duplicate_slots_documents_and_conflicting_parent_cannot_establish_lineage() {
    for change in 0..4 {
        let mut manifest = [
            slot("original", BEFORE, ArtifactKind::Xmp, Role::Original, None),
            slot(
                "derivative",
                ABSENT,
                ArtifactKind::Xmp,
                Role::Derivative,
                Some("original"),
            ),
        ];
        match change {
            0 => manifest[1].slot_id = "original",
            1 => manifest[1].document_id = "original",
            2 => manifest[1].parent_slot = Some("unknown"),
            _ => manifest[1].parent_slot = Some("derivative"),
        }
        let report = run(
            &manifest,
            &[snap("original", BEFORE), snap("derivative", ABSENT)],
            &[claim(RequestedEffect::Removed)],
            Limits::default(),
        )
        .unwrap();
        assert!(!report.declared_set_complete, "case {change}");
        assert!(!report.effects[0].supported, "case {change}");
        uncertified(&report);
    }
}

#[test]
fn unsupported_nested_xmp_is_uninspectable_even_when_target_looks_present() {
    let bytes = b"<rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'><rdf:Description xmlns:a='http://ns.adobe.com/exif/1.0/aux/'><a:wrapper><a:OwnerName>authored</a:OwnerName></a:wrapper></rdf:Description></rdf:RDF>";
    let report = run(
        &[slot("unknown", bytes, ArtifactKind::Xmp, Role::Other, None)],
        &[snap("unknown", bytes)],
        &[],
        Limits::default(),
    )
    .unwrap();
    assert!(report.artifacts[0].cells.iter().all(
        |cell| cell.state == imageinfo_privacy_coverage_research::CoverageState::Uninspectable
    ));
    uncertified(&report);
}

#[test]
fn finite_slots_bytes_cells_identifiers_and_effects_accept_exact_and_reject_one_over() {
    let manifest = [
        slot("original", BEFORE, ArtifactKind::Xmp, Role::Original, None),
        slot(
            "derivative",
            ABSENT,
            ArtifactKind::Xmp,
            Role::Derivative,
            Some("original"),
        ),
    ];
    let snapshots = [snap("original", BEFORE), snap("derivative", ABSENT)];
    let claims = [claim(RequestedEffect::Removed)];
    let exact = Limits {
        slots: 2,
        input_bytes: BEFORE.len() + ABSENT.len(),
        cells: 26,
        id_bytes: 11,
        effects: 1,
    };
    assert!(run(&manifest, &snapshots, &claims, exact).is_ok());
    for change in 0..5 {
        let mut limits = exact;
        match change {
            0 => limits.slots -= 1,
            1 => limits.input_bytes -= 1,
            2 => limits.cells -= 1,
            3 => limits.id_bytes -= 1,
            _ => limits.effects -= 1,
        }
        assert!(
            run(&manifest, &snapshots, &claims, limits).is_err(),
            "one-over case {change}"
        );
    }
    let limits = Limits {
        slots: MAX_SLOTS + 1,
        ..Limits::default()
    };
    assert_eq!(
        run(&manifest, &snapshots, &claims, limits).unwrap_err(),
        Refusal::Limits
    );
}

#[test]
fn hard_ceiling_configuration_cannot_be_expanded_by_caller() {
    for change in 0..5 {
        let mut limits = Limits::default();
        match change {
            0 => limits.slots = MAX_SLOTS + 1,
            1 => limits.input_bytes = MAX_INPUT_BYTES + 1,
            2 => limits.cells = MAX_CELLS + 1,
            3 => limits.id_bytes = MAX_ID_BYTES + 1,
            _ => limits.effects = MAX_EFFECTS + 1,
        }
        assert_eq!(run(&[], &[], &[], limits).unwrap_err(), Refusal::Limits);
    }
}

#[test]
fn slot_identifier_effect_and_report_reservation_hard_limits_are_exact() {
    let ids: Vec<_> = (0..=MAX_SLOTS).map(|n| format!("artifact-{n}")).collect();
    let manifest: Vec<_> = ids
        .iter()
        .map(|id| slot(id, b"", ArtifactKind::Opaque, Role::Other, None))
        .collect();
    let snapshots: Vec<_> = ids.iter().map(|id| snap(id, b"")).collect();
    assert_eq!(
        run(
            &manifest[..MAX_SLOTS],
            &snapshots[..MAX_SLOTS],
            &[],
            Limits::default()
        )
        .unwrap()
        .artifacts
        .len(),
        MAX_SLOTS
    );
    assert_eq!(
        run(&manifest, &snapshots, &[], Limits::default()).unwrap_err(),
        Refusal::Limits
    );
    let id = "a".repeat(MAX_ID_BYTES + 1);
    assert!(
        run(
            &[slot(
                &id[..MAX_ID_BYTES],
                b"",
                ArtifactKind::Opaque,
                Role::Other,
                None
            )],
            &[snap(&id[..MAX_ID_BYTES], b"")],
            &[],
            Limits::default()
        )
        .is_ok()
    );
    assert_eq!(
        run(
            &[slot(&id, b"", ArtifactKind::Opaque, Role::Other, None)],
            &[snap(&id, b"")],
            &[],
            Limits::default()
        )
        .unwrap_err(),
        Refusal::Identifier
    );
    let manifest = [
        slot("original", BEFORE, ArtifactKind::Xmp, Role::Original, None),
        slot(
            "derivative",
            ABSENT,
            ArtifactKind::Xmp,
            Role::Derivative,
            Some("original"),
        ),
    ];
    let snapshots = [snap("original", BEFORE), snap("derivative", ABSENT)];
    let claims = vec![claim(RequestedEffect::Removed); MAX_EFFECTS + 1];
    assert_eq!(
        run(
            &manifest,
            &snapshots,
            &claims[..MAX_EFFECTS],
            Limits::default()
        )
        .unwrap()
        .effects
        .len(),
        MAX_EFFECTS
    );
    assert_eq!(
        run(&manifest, &snapshots, &claims, Limits::default()).unwrap_err(),
        Refusal::Limits
    );
    let raw = support::fixture().bytes;
    let manifest = [
        slot("raw-1", &raw, ArtifactKind::Raw, Role::Original, None),
        slot(
            "raw-2",
            &raw,
            ArtifactKind::Raw,
            Role::Backup,
            Some("raw-1"),
        ),
    ];
    let snapshots = [snap("raw-1", &raw), snap("raw-2", &raw)];
    assert_eq!(
        run(&manifest, &snapshots, &[], Limits::default())
            .unwrap()
            .construction_cell_reservation,
        MAX_CELLS
    );
    let mut limits = Limits::default();
    limits.cells -= 1;
    assert_eq!(
        run(&manifest, &snapshots, &[], limits).unwrap_err(),
        Refusal::Limits
    );
}

#[test]
fn empty_declaration_never_claims_unknown_inventory_or_clean_operation() {
    let report = run(&[], &[], &[], Limits::default()).unwrap();
    assert!(report.declared_set_complete);
    assert!(report.artifacts.is_empty());
    uncertified(&report);
}
#[test]
fn every_catalog_selector_location_and_document_has_the_authored_expansion() {
    // Frozen contract oracle, deliberately independent of deserializing the catalog.
    let raw = support::fixture().bytes;
    let manifest = [
        slot("raw", &raw, ArtifactKind::Raw, Role::Original, None),
        slot("xmp", BEFORE, ArtifactKind::Xmp, Role::Original, None),
    ];
    let report = run(
        &manifest,
        &[snap("raw", &raw), snap("xmp", BEFORE)],
        &[],
        Limits::default(),
    )
    .unwrap();
    let actual: BTreeSet<_> = report
        .artifacts
        .iter()
        .flat_map(|a| &a.cells)
        .map(|c| (c.entry_id.clone(), c.location.clone(), c.document.clone()))
        .collect();
    let mut expected = BTreeSet::new();
    for n in 1..=31 {
        let id = format!("R5P-{n:03}");
        let native = match n {
            1..=12 => Some("cr3.cmt4.gps"),
            13..=15 => Some("cr3.cmt2.exif"),
            16..=18 => Some("cr3.cmt3.canon"),
            _ => None,
        };
        if let Some(location) = native {
            expected.insert((id.clone(), location.into(), "raw/raw-original".into()));
        }
        if n >= 19 {
            expected.insert((id.clone(), "sidecar.xmp".into(), "xmp".into()));
        }
        let preview = match n {
            1..=12 => Some("preview.exif.gps"),
            13..=15 => Some("preview.exif.exif"),
            19..=31 => Some("preview.xmp"),
            _ => None,
        };
        if let Some(location) = preview {
            for p in 0..3 {
                expected.insert((id.clone(), location.into(), format!("raw/preview-{p}")));
            }
        }
    }
    assert_eq!(actual, expected);
    assert_eq!(
        actual.len(),
        report
            .artifacts
            .iter()
            .map(|a| a.cells.len())
            .sum::<usize>()
    );
}
