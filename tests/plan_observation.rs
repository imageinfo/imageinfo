#[allow(dead_code)]
mod support;
use imageinfo::{
    plan::{ByteOrder, PreviewPlan, Sha256Digest},
    plan_observation::{self as observation, ChangedField as Field, DateValueEffect},
    source_binding,
};
use std::io::Cursor;

const DATE: &str = "2000:02:29 23:59:59";
fn fixture() -> Vec<u8> {
    support::fixture_with_previews(
        "Firmware Version 2.2.1",
        vec![0xff, 0xd8, 0xff, 0xd9],
        vec![0xff, 0xd8, 0xff, 0xd9],
        vec![0xff, 0xd8, 0xff, 0xd9],
    )
    .bytes
}
fn capture(bytes: &[u8]) -> PreviewPlan {
    source_binding::capture(Cursor::new(bytes), "source.cr3", "new.cr3", DATE)
        .unwrap()
        .plan
}

#[test]
fn every_variable_v1_binding_is_compared_in_contract_order() {
    let plan = capture(&fixture());
    let mut changed = plan.saved().clone();
    changed.source.path = "other-source.cr3".into();
    changed.source.length += 1;
    changed.source.sha256 = Sha256Digest::try_from("f".repeat(64)).unwrap();
    changed.occurrence.path[0].index += 1;
    changed.occurrence.allocation.offset += 1;
    changed.occurrence.byte_order = ByteOrder::BigEndian;
    changed.occurrence.original_bytes = *b"2024:01:02 03:04:05\0";
    changed.intended_bytes = *b"2025:01:02 03:04:05\0";
    changed.output.path = "other-new.cr3".into();
    let changed = PreviewPlan::new(changed).unwrap();
    assert_eq!(
        observation::changed_fields(&plan, &changed),
        vec![
            Field::SourceLocator,
            Field::SourceLength,
            Field::SourceDigest,
            Field::OccurrencePath,
            Field::Allocation,
            Field::ByteOrder,
            Field::OriginalBytes,
            Field::IntendedBytes,
            Field::OutputLocator,
        ]
    );
    assert!(observation::changed_fields(&plan, &plan).is_empty());
}

#[test]
fn equal_date_keeps_explicit_new_name_effect_and_format_refusal() {
    let bytes = fixture();
    let plan = capture(&bytes);
    let old = std::str::from_utf8(&plan.saved().occurrence.original_bytes[..19]).unwrap();
    let report =
        observation::recompute(Cursor::new(&bytes), &plan, "source.cr3", "new.cr3", old).unwrap();
    assert_eq!(
        report.requested_effects.date_value,
        DateValueEffect::AlreadyEqual
    );
    assert_eq!(report.requested_effects.new_output_locator, "new.cr3");
    assert_eq!(report.changed_fields, vec![Field::IntendedBytes]);
    assert!(!report.current.preview.refusals.is_empty());
    assert!(!report.production_mutation_allowed());
}

#[test]
fn fresh_content_and_changed_request_are_visible_without_accepting_them() {
    let mut bytes = fixture();
    let plan = capture(&bytes);
    let original = plan.clone();
    let offset = plan.saved().occurrence.allocation.offset as usize;
    bytes[offset..offset + 20].copy_from_slice(b"2024:01:02 03:04:05\0");
    let last = bytes.len() - 1;
    bytes[last] ^= 1;
    let report = observation::recompute(
        Cursor::new(bytes),
        &plan,
        "source.cr3",
        "different.cr3",
        "2026:01:02 03:04:05",
    )
    .unwrap();
    assert_eq!(
        report.changed_fields,
        vec![
            Field::SourceDigest,
            Field::OriginalBytes,
            Field::IntendedBytes,
            Field::OutputLocator
        ]
    );
    assert_eq!(plan, original);
    assert!(!report.production_mutation_allowed());
    assert!(!report.current.plan.production_mutation_allowed());
}

#[test]
fn forged_saved_assertions_are_compared_to_actual_snapshot() {
    let bytes = fixture();
    let mut forged = capture(&bytes).saved().clone();
    forged.source.sha256 = Sha256Digest::try_from("0".repeat(64)).unwrap();
    forged.occurrence.path[0].index += 1;
    let saved = PreviewPlan::new(forged).unwrap();
    let report =
        observation::recompute(Cursor::new(bytes), &saved, "source.cr3", "new.cr3", DATE).unwrap();
    assert_eq!(
        report.changed_fields,
        vec![Field::SourceDigest, Field::OccurrencePath]
    );
    assert!(!report.production_mutation_allowed());
}

#[test]
fn malformed_current_source_or_intent_never_becomes_equal_noop() {
    let bytes = fixture();
    let plan = capture(&bytes);
    for proposed in ["", "2025:02:29 00:00:00", "$(command)"] {
        assert!(
            observation::recompute(
                Cursor::new(&bytes),
                &plan,
                "source.cr3",
                "new.cr3",
                proposed
            )
            .is_err()
        );
    }
    assert!(
        observation::recompute(
            Cursor::new(b"not CR3"),
            &plan,
            "source.cr3",
            "new.cr3",
            DATE
        )
        .is_err()
    );
    assert!(
        observation::recompute(Cursor::new(&bytes), &plan, "source.cr3", "source.cr3", DATE)
            .is_err()
    );
}

#[test]
fn exact_recomputation_and_roundtrip_remain_advisory() {
    let bytes = fixture();
    let saved = capture(&bytes);
    let report =
        observation::recompute(Cursor::new(&bytes), &saved, "source.cr3", "new.cr3", DATE).unwrap();
    assert!(report.changed_fields.is_empty());
    let imported =
        PreviewPlan::from_json(&serde_json::to_string(&report.current.plan).unwrap()).unwrap();
    assert_eq!(saved, imported);
    assert!(!imported.production_mutation_allowed());
    assert!(!report.production_mutation_allowed());
}
