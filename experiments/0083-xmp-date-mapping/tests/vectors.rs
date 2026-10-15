use imageinfo_xmp_date_mapping_research::*;
use imageinfo_xmp_model_research::{Limits, inspect};

fn packet(text: &str) -> String {
    format!(
        "<r:RDF xmlns:r='http://www.w3.org/1999/02/22-rdf-syntax-ns#' xmlns:e='{TARGET_NAMESPACE}'><r:Description><e:DateTimeOriginal>{text}</e:DateTimeOriginal></r:Description></r:RDF>"
    )
}

fn original<'a>(
    date: &'a [Occurrence<'a>],
    fraction: &'a [Occurrence<'a>],
    offset: &'a [Occurrence<'a>],
) -> OriginalSnapshot<'a> {
    OriginalSnapshot {
        id: "snapshot-original",
        raw_document: "raw",
        sidecar_document: "sidecar",
        complete_selected_tag_coverage: true,
        original: date,
        subseconds: fraction,
        offset,
    }
}

const DATE: [Occurrence<'static>; 1] = [Occurrence {
    id: "raw-date",
    text: "2024:02:29 12:34:56",
}];
const FRACTION: [Occurrence<'static>; 1] = [Occurrence {
    id: "raw-subseconds",
    text: "001230000",
}];
const OFFSET: [Occurrence<'static>; 1] = [Occurrence {
    id: "raw-offset",
    text: "+05:30",
}];

#[test]
fn exact_full_mapping_preserves_precision_offset_and_original_provenance() {
    let raw = original(&DATE, &FRACTION, &OFFSET);
    let xml = packet("2024-02-29T12:34:56.001230000+05:30");
    let sidecar = inspect(xml.as_bytes(), Limits::default()).unwrap();
    let before = sidecar.source.to_owned();
    assert_eq!(
        compare(&raw, &sidecar, 0, ConflictPolicy::Refuse).unwrap(),
        Comparison {
            mapping: MAPPING,
            snapshot: "snapshot-original",
            raw_document: "raw",
            sidecar_document: "sidecar",
            source_occurrences: vec!["raw-date", "raw-subseconds", "raw-offset"],
            target_ordinal: 0,
            previous: "2024-02-29T12:34:56.001230000+05:30".into(),
            mapped: "2024-02-29T12:34:56.001230000+05:30".into(),
            destination_losses: vec![],
            decision: Decision::NoOp,
            production_mutation_allowed: false,
        }
    );
    assert_eq!(sidecar.source, before);
    assert_eq!(raw.original[0].text, DATE[0].text);
}

#[test]
fn absent_fraction_and_zone_are_never_invented() {
    let raw = original(&DATE, &[], &[]);
    let xml = packet("2024-02-29T12:34:56");
    let sidecar = inspect(xml.as_bytes(), Limits::default()).unwrap();
    let result = compare(&raw, &sidecar, 0, ConflictPolicy::Refuse).unwrap();
    assert_eq!(result.mapped, "2024-02-29T12:34:56");
    assert_eq!(result.decision, Decision::NoOp);
}

#[test]
fn conflict_alternatives_and_loss_acknowledgment_are_exact() {
    let raw = original(&DATE, &[], &[]);
    let xml = packet("2023-01-01T01:02:03.120+01:00");
    let sidecar = inspect(xml.as_bytes(), Limits::default()).unwrap();
    let losses = [
        Loss::DestinationFractionDiscarded,
        Loss::DestinationZoneDiscarded,
    ];
    for (policy, expected) in [
        (ConflictPolicy::default(), Decision::ConflictRefused),
        (ConflictPolicy::KeepDestination, Decision::KeepDestination),
        (
            ConflictPolicy::ReplaceSelected { acknowledged: &[] },
            Decision::LossRefused,
        ),
        (
            ConflictPolicy::ReplaceSelected {
                acknowledged: &losses[..1],
            },
            Decision::LossRefused,
        ),
        (
            ConflictPolicy::ReplaceSelected {
                acknowledged: &losses,
            },
            Decision::ReplaceIntentOnly,
        ),
    ] {
        let result = compare(&raw, &sidecar, 0, policy).unwrap();
        assert_eq!(result.decision, expected);
        assert_eq!(result.destination_losses, losses);
        assert_eq!(result.previous, "2023-01-01T01:02:03.120+01:00");
        assert_eq!(result.mapped, "2024-02-29T12:34:56");
        assert!(!result.production_mutation_allowed);
    }
}

#[test]
fn offset_spellings_and_fraction_trailing_zeros_are_never_silently_normalized() {
    let zone = [Occurrence {
        id: "zone",
        text: "+00:00",
    }];
    let frac = [Occurrence {
        id: "frac",
        text: "10",
    }];
    let raw = original(&DATE, &frac, &zone);
    let xml = packet("2024-02-29T12:34:56.1Z");
    let sidecar = inspect(xml.as_bytes(), Limits::default()).unwrap();
    let result = compare(&raw, &sidecar, 0, ConflictPolicy::Refuse).unwrap();
    assert_eq!(result.mapped, "2024-02-29T12:34:56.10+00:00");
    assert_eq!(result.decision, Decision::ConflictRefused);
    assert_eq!(
        result.destination_losses,
        vec![
            Loss::DestinationFractionDiscarded,
            Loss::DestinationZoneDiscarded
        ]
    );
}

#[test]
fn replacement_does_not_read_a_previous_intent_as_a_new_source() {
    let raw = original(&DATE, &[], &[]);
    let xml = packet("2020-01-01T00:00:00");
    let sidecar = inspect(xml.as_bytes(), Limits::default()).unwrap();
    let first = compare(
        &raw,
        &sidecar,
        0,
        ConflictPolicy::ReplaceSelected { acknowledged: &[] },
    )
    .unwrap();
    let second = compare(
        &raw,
        &sidecar,
        0,
        ConflictPolicy::ReplaceSelected { acknowledged: &[] },
    )
    .unwrap();
    assert_eq!(first, second);
    assert_eq!(second.previous, "2020-01-01T00:00:00");
    assert_eq!(second.mapped, "2024-02-29T12:34:56");
    assert_eq!(
        compare(
            &raw,
            &sidecar,
            0,
            ConflictPolicy::ReplaceSelected {
                acknowledged: &[Loss::DestinationFractionDiscarded],
            }
        )
        .unwrap()
        .decision,
        Decision::LossRefused
    );
}

#[test]
fn missing_duplicate_unexamined_and_invalid_source_identities_refuse() {
    let xml = packet("2024-02-29T12:34:56");
    let sidecar = inspect(xml.as_bytes(), Limits::default()).unwrap();
    let duplicate = [DATE[0], DATE[0]];
    for values in [&[][..], &duplicate[..]] {
        assert_eq!(
            compare(
                &original(values, &[], &[]),
                &sidecar,
                0,
                ConflictPolicy::Refuse
            ),
            Err(Refusal::SourceCardinality)
        );
    }
    let mut raw = original(&DATE, &[], &[]);
    raw.complete_selected_tag_coverage = false;
    assert_eq!(
        compare(&raw, &sidecar, 0, ConflictPolicy::Refuse),
        Err(Refusal::IncompleteCoverage)
    );
    let duplicate_id = [Occurrence {
        id: "raw-date",
        text: "12",
    }];
    assert_eq!(
        compare(
            &original(&DATE, &duplicate_id, &[]),
            &sidecar,
            0,
            ConflictPolicy::Refuse
        ),
        Err(Refusal::InvalidIdentity)
    );
    let fractions = [FRACTION[0], FRACTION[0]];
    assert_eq!(
        compare(
            &original(&DATE, &fractions, &[]),
            &sidecar,
            0,
            ConflictPolicy::Refuse
        ),
        Err(Refusal::SourceCardinality)
    );
    let offsets = [OFFSET[0], OFFSET[0]];
    assert_eq!(
        compare(
            &original(&DATE, &[], &offsets),
            &sidecar,
            0,
            ConflictPolicy::Refuse
        ),
        Err(Refusal::SourceCardinality)
    );
}

#[test]
fn malformed_partial_calendar_and_leap_second_dates_refuse() {
    let xml = packet("2024-02-29T12:34:56");
    let sidecar = inspect(xml.as_bytes(), Limits::default()).unwrap();
    for value in [
        "2023:02:29 12:34:56",
        "1900:02:29 00:00:00",
        "0000:01:01 00:00:00",
        "2024:01:01 24:00:00",
        "2024:01:01 23:59:60",
        "2024:01:01",
        "2024:  :   00:00:00",
        "2024:01:01 00:00:00 ",
    ] {
        let date = [Occurrence {
            id: "date",
            text: value,
        }];
        assert_eq!(
            compare(
                &original(&date, &[], &[]),
                &sidecar,
                0,
                ConflictPolicy::Refuse
            ),
            Err(Refusal::SourceDate),
            "{value}"
        );
    }
}

#[test]
fn fraction_and_offset_limits_refuse_instead_of_truncation_or_assumption() {
    let xml = packet("2024-02-29T12:34:56");
    let sidecar = inspect(xml.as_bytes(), Limits::default()).unwrap();
    for value in ["", "1234567890", " 12", "0.12", "a"] {
        let frac = [Occurrence {
            id: "frac",
            text: value,
        }];
        assert_eq!(
            compare(
                &original(&DATE, &frac, &[]),
                &sidecar,
                0,
                ConflictPolicy::Refuse
            ),
            Err(Refusal::SourceFraction)
        );
    }
    for value in ["", "Z", "-00:00", "+14:01", "+15:00", "+01:60", " +01:00"] {
        let zone = [Occurrence {
            id: "zone",
            text: value,
        }];
        assert_eq!(
            compare(
                &original(&DATE, &[], &zone),
                &sidecar,
                0,
                ConflictPolicy::Refuse
            ),
            Err(Refusal::SourceOffset)
        );
    }
    for value in ["+00:00", "+14:00", "-14:00", "-05:45"] {
        let zone = [Occurrence {
            id: "zone",
            text: value,
        }];
        assert!(
            compare(
                &original(&DATE, &[], &zone),
                &sidecar,
                0,
                ConflictPolicy::Refuse
            )
            .is_ok()
        );
    }
}

#[test]
fn expanded_name_attribute_target_is_selected_without_friendly_aliases() {
    let raw = original(&DATE, &[], &[]);
    let xml = format!(
        "<r:RDF xmlns:r='http://www.w3.org/1999/02/22-rdf-syntax-ns#' xmlns:alias='{TARGET_NAMESPACE}' xmlns:u='urn:unknown'><r:Description u:DateTimeOriginal='unknown' alias:DateTimeOriginal='2024-02-29T12:34:56'/></r:RDF>"
    );
    let sidecar = inspect(xml.as_bytes(), Limits::default()).unwrap();
    assert_eq!(
        compare(&raw, &sidecar, 1, ConflictPolicy::Refuse)
            .unwrap()
            .decision,
        Decision::NoOp
    );
    assert_eq!(
        compare(&raw, &sidecar, 0, ConflictPolicy::Refuse),
        Err(Refusal::TargetSelection)
    );
}

#[test]
fn missing_duplicate_structured_and_malformed_targets_refuse() {
    let raw = original(&DATE, &[], &[]);
    for (body, expected) in [
        ("", Refusal::TargetCardinality),
        (
            "<e:DateTimeOriginal>2024-02-29T12:34:56</e:DateTimeOriginal><e:DateTimeOriginal>2024-02-29T12:34:56</e:DateTimeOriginal>",
            Refusal::TargetCardinality,
        ),
        (
            "<e:DateTimeOriginal><r:Bag/></e:DateTimeOriginal>",
            Refusal::TargetType,
        ),
        (
            "<e:DateTimeOriginal>2024</e:DateTimeOriginal>",
            Refusal::TargetDate,
        ),
        (
            "<e:DateTimeOriginal>2023-02-29T00:00:00</e:DateTimeOriginal>",
            Refusal::TargetDate,
        ),
        (
            "<e:DateTimeOriginal>2024-02-29T12:34:56-00:00</e:DateTimeOriginal>",
            Refusal::TargetDate,
        ),
    ] {
        let xml = format!(
            "<r:RDF xmlns:r='http://www.w3.org/1999/02/22-rdf-syntax-ns#' xmlns:e='{TARGET_NAMESPACE}'><r:Description>{body}</r:Description></r:RDF>"
        );
        let sidecar = inspect(xml.as_bytes(), Limits::default()).unwrap();
        assert_eq!(
            compare(&raw, &sidecar, 0, ConflictPolicy::Refuse),
            Err(expected)
        );
    }
}
