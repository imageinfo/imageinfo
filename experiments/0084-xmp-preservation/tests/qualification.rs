//! Independently authored finite XML vectors; no camera media or upstream fixtures.
use imageinfo_xmp_date_mapping_research::{
    ConflictPolicy, Decision, Loss, Occurrence, OriginalSnapshot, Refusal as MappingRefusal,
    TARGET_LOCAL, TARGET_NAMESPACE,
};
use imageinfo_xmp_model_research::{Limits, Refusal as InspectRefusal, Value, inspect};
use imageinfo_xmp_preservation_research::{Kind, Refusal, prepare};
use std::borrow::Cow;

const DATE: [Occurrence<'static>; 1] = [Occurrence {
    id: "authored-original-date",
    text: "2024:02:29 12:34:56",
}];
const FRACTION: [Occurrence<'static>; 1] = [Occurrence {
    id: "authored-fraction",
    text: "001230000",
}];
const OFFSET: [Occurrence<'static>; 1] = [Occurrence {
    id: "authored-offset",
    text: "+05:30",
}];
const NEW: &str = "2024-02-29T12:34:56";
const OLD: &str = "2023-01-02T03:04:05";

fn original(full: bool) -> OriginalSnapshot<'static> {
    OriginalSnapshot {
        id: "authored-snapshot",
        raw_document: "explicit-authored-raw-observation",
        sidecar_document: "explicit-authored-sidecar-observation",
        complete_selected_tag_coverage: true,
        original: &DATE,
        subseconds: if full { &FRACTION } else { &[] },
        offset: if full { &OFFSET } else { &[] },
    }
}

fn document(attributes: &str, properties: &str) -> String {
    format!(
        "<?xml version='1.0' encoding='UTF-8'?>\r\n<?xpacket begin='authored'?>\r\n<r:RDF xmlns:r='http://www.w3.org/1999/02/22-rdf-syntax-ns#' xmlns:e='{TARGET_NAMESPACE}' xmlns:u='urn:authored:unknown'><r:Description r:about='' {attributes}>{properties}</r:Description></r:RDF>\r\n<?xpacket end='w'?>"
    )
}

fn target_ordinal(bytes: &[u8]) -> usize {
    inspect(bytes, Limits::default())
        .unwrap()
        .properties
        .iter()
        .find(|property| {
            property.name.namespace == TARGET_NAMESPACE && property.name.local == TARGET_LOCAL
        })
        .unwrap()
        .ordinal
}

fn replacement() -> ConflictPolicy<'static> {
    ConflictPolicy::ReplaceSelected { acknowledged: &[] }
}

fn assert_derivative(input: &str, raw_value: &str, expected: &str, full: bool) {
    assert_derivative_at(
        input,
        raw_value,
        expected,
        full,
        input.find(raw_value).unwrap(),
    );
}

fn assert_derivative_at(input: &str, raw_value: &str, expected: &str, full: bool, start: usize) {
    let original = original(full);
    let before = input.as_bytes().to_vec();
    let ordinal = target_ordinal(input.as_bytes());
    let result = prepare(input.as_bytes(), &original, ordinal, replacement()).unwrap();
    assert_eq!(result.kind, Kind::Derivative);
    assert!(matches!(result.bytes, Cow::Owned(_)));
    assert!(!result.production_mutation_allowed);
    let change = result.changed.as_ref().unwrap();
    assert_eq!(change.original, start..start + raw_value.len());
    assert_eq!(change.derivative, start..start + expected.len());
    assert_eq!(&result.bytes[..start], &before[..start]);
    assert_eq!(
        &result.bytes[change.derivative.end..],
        &before[change.original.end..]
    );
    assert_eq!(
        &result.bytes[change.derivative.clone()],
        expected.as_bytes()
    );
    let mut exact = before[..start].to_vec();
    exact.extend_from_slice(expected.as_bytes());
    exact.extend_from_slice(&before[start + raw_value.len()..]);
    assert_eq!(result.bytes.as_ref(), exact);
    assert_eq!(input.as_bytes(), before);
    let old_packet = inspect(&before, Limits::default()).unwrap();
    let new_packet = inspect(result.bytes.as_ref(), Limits::default()).unwrap();
    assert_eq!(old_packet.properties.len(), new_packet.properties.len());
    for (old, new) in old_packet.properties.iter().zip(&new_packet.properties) {
        if old.ordinal == ordinal {
            assert_eq!(new.name, old.name);
            assert_eq!(new.form, old.form);
            assert_eq!(new.value, Value::Text(expected.into()));
        } else {
            assert_eq!(old, new);
        }
    }
}

#[test]
fn element_derivative_preserves_all_unknown_bytes_and_sibling_meanings() {
    let input = document(
        "u:opaque='A &amp; B'",
        &format!(
            "<!--keep this spacing-->\r\n<u:sequence><r:Seq><r:li>zero</r:li><r:li>二</r:li></r:Seq></u:sequence><?authored keep?><e:DateTimeOriginal>{OLD}</e:DateTimeOriginal>\r\n<u:tail><![CDATA[<opaque>&tail]]></u:tail>"
        ),
    );
    assert_derivative(&input, OLD, NEW, false);
}

#[test]
fn attribute_quote_styles_preserve_namespaces_whitespace_and_unknown_attributes() {
    for quote in ['\'', '"'] {
        let input = document(
            &format!(
                "u:before='2022-01-01T00:00:00' e:DateTimeOriginal = {quote}{OLD}{quote} u:after='&quot;&amp;'"
            ),
            "<u:untouched>unrelated text</u:untouched>",
        );
        assert_derivative(&input, OLD, NEW, false);
    }
}

#[test]
fn alternate_prefix_and_default_element_namespace_select_expanded_identity() {
    for property in [
        format!(
            "<date:DateTimeOriginal xmlns:date='{TARGET_NAMESPACE}'>{OLD}</date:DateTimeOriginal>"
        ),
        format!("<DateTimeOriginal xmlns='{TARGET_NAMESPACE}'>{OLD}</DateTimeOriginal>"),
    ] {
        let input = document("u:untouched='opaque'", &property);
        assert_derivative(&input, OLD, NEW, false);
    }
}

#[test]
fn prefix_rebinding_does_not_select_an_unknown_same_local_name() {
    let input = document(
        "",
        &format!(
            "<e:DateTimeOriginal xmlns:e='urn:authored:other'>2022-01-01T00:00:00</e:DateTimeOriginal><e:DateTimeOriginal>{OLD}</e:DateTimeOriginal>"
        ),
    );
    assert_derivative(&input, OLD, NEW, false);
}

#[test]
fn identical_unknown_dates_and_comment_decoys_remain_byte_exact() {
    let target = format!("<e:DateTimeOriginal>{OLD}</e:DateTimeOriginal>");
    let input = document(
        &format!("u:DateTimeOriginal='{OLD}'"),
        &format!(
            "<!--<e:DateTimeOriginal>{OLD}</e:DateTimeOriginal>--><u:DateTimeOriginal>{OLD}</u:DateTimeOriginal>{target}<u:tail>{OLD}</u:tail>"
        ),
    );
    let start = input.rfind(&target).unwrap() + "<e:DateTimeOriginal>".len();
    assert_derivative_at(&input, OLD, NEW, false, start);
}

#[test]
fn attribute_no_op_retains_entity_spelling_quotes_and_crlf() {
    let input = document(
        "u:before='opaque' e:DateTimeOriginal = \"&#50;024-02-29T12:34:56\"",
        "",
    );
    let bytes = input.as_bytes();
    let original = original(false);
    let result = prepare(bytes, &original, target_ordinal(bytes), replacement()).unwrap();
    assert_eq!(result.kind, Kind::NoOp);
    assert!(matches!(result.bytes, Cow::Borrowed(_)));
    assert_eq!(result.bytes.as_ptr(), bytes.as_ptr());
    assert_eq!(result.bytes.as_ref(), bytes);
    assert_eq!(result.changed, None);
    assert!(!result.production_mutation_allowed);
}

#[test]
fn unequal_length_fraction_and_offset_patch_has_exact_complement() {
    let input = document(
        "",
        &format!("<e:DateTimeOriginal>{OLD}</e:DateTimeOriginal>"),
    );
    assert_derivative(&input, OLD, "2024-02-29T12:34:56.001230000+05:30", true);
}

#[test]
fn no_op_borrows_original_bytes_for_plain_entities_cdata_and_comment_splits() {
    let forms = [
        NEW.to_owned(),
        "&#50;024-02-29T12:34:56".into(),
        "<![CDATA[2024-02-29T12:34:56]]>".into(),
        "2024-02-29<!--preserve-comment-->T12:34:56".into(),
    ];
    for form in forms {
        let input = document(
            "u:untouched='&#x41;'",
            &format!("<e:DateTimeOriginal>{form}</e:DateTimeOriginal>"),
        );
        let bytes = input.as_bytes();
        let original = original(false);
        let result = prepare(
            bytes,
            &original,
            target_ordinal(bytes),
            ConflictPolicy::Refuse,
        )
        .unwrap();
        assert_eq!(result.kind, Kind::NoOp);
        assert!(matches!(result.bytes, Cow::Borrowed(_)));
        assert_eq!(result.bytes.as_ptr(), bytes.as_ptr());
        assert_eq!(result.bytes.as_ref(), bytes);
        assert_eq!(result.changed, None);
        assert!(!result.production_mutation_allowed);
    }
}

#[test]
fn replacement_refuses_non_plain_target_lexical_representations() {
    for form in [
        "&#50;023-01-02T03:04:05",
        "<![CDATA[2023-01-02T03:04:05]]>",
        "2023-01-02<!--split-->T03:04:05",
        "2023-01-02<?split value?>T03:04:05",
    ] {
        let input = document(
            "",
            &format!("<e:DateTimeOriginal>{form}</e:DateTimeOriginal>"),
        );
        let original = original(false);
        assert_eq!(
            prepare(input.as_bytes(), &original, 0, replacement()).unwrap_err(),
            Refusal::LexicalTarget
        );
    }
    let input = document("e:DateTimeOriginal='&#50;023-01-02T03:04:05'", "");
    assert_eq!(
        prepare(input.as_bytes(), &original(false), 0, replacement()).unwrap_err(),
        Refusal::LexicalTarget
    );
}

#[test]
fn duplicate_missing_list_and_wrong_ordinal_targets_refuse() {
    let original = original(false);
    for (input, refusal) in [
        (
            document(
                "e:DateTimeOriginal='2023-01-02T03:04:05'",
                &format!("<e:DateTimeOriginal>{OLD}</e:DateTimeOriginal>"),
            ),
            MappingRefusal::TargetCardinality,
        ),
        (
            document(
                "",
                "<u:DateTimeOriginal>2023-01-02T03:04:05</u:DateTimeOriginal>",
            ),
            MappingRefusal::TargetCardinality,
        ),
        (
            document(
                "",
                "<e:DateTimeOriginal><r:Seq><r:li>2023-01-02T03:04:05</r:li></r:Seq></e:DateTimeOriginal>",
            ),
            MappingRefusal::TargetType,
        ),
    ] {
        assert_eq!(
            prepare(input.as_bytes(), &original, 0, replacement()).unwrap_err(),
            Refusal::Mapping(refusal)
        );
    }
    let input = document(
        "u:before='opaque'",
        &format!("<e:DateTimeOriginal>{OLD}</e:DateTimeOriginal>"),
    );
    assert_eq!(
        prepare(input.as_bytes(), &original, 0, replacement()).unwrap_err(),
        Refusal::Mapping(MappingRefusal::TargetSelection)
    );
}

#[test]
fn conflict_keep_and_loss_refusals_never_yield_derivative_bytes() {
    let original = original(false);
    let input = document(
        "",
        "<e:DateTimeOriginal>2023-01-02T03:04:05.1Z</e:DateTimeOriginal>",
    );
    for (policy, decision) in [
        (ConflictPolicy::Refuse, Decision::ConflictRefused),
        (ConflictPolicy::KeepDestination, Decision::KeepDestination),
        (replacement(), Decision::LossRefused),
    ] {
        assert_eq!(
            prepare(input.as_bytes(), &original, 0, policy).unwrap_err(),
            Refusal::Decision(decision)
        );
    }
    let losses = [
        Loss::DestinationFractionDiscarded,
        Loss::DestinationZoneDiscarded,
    ];
    let result = prepare(
        input.as_bytes(),
        &original,
        0,
        ConflictPolicy::ReplaceSelected {
            acknowledged: &losses,
        },
    )
    .unwrap();
    let span = result.changed.unwrap();
    assert_eq!(&result.bytes[span.derivative.clone()], NEW.as_bytes());
    assert_eq!(
        &result.bytes[..span.derivative.start],
        &input.as_bytes()[..span.original.start]
    );
    assert_eq!(
        &result.bytes[span.derivative.end..],
        &input.as_bytes()[span.original.end..]
    );
    let reparsed = inspect(&result.bytes, Limits::default()).unwrap();
    assert_eq!(reparsed.properties[0].value, Value::Text(NEW.into()));
    assert!(!result.production_mutation_allowed);
}

#[test]
fn malformed_xml_dtd_and_non_utf8_refuse_before_derivative() {
    let original = original(false);
    for (input, refusal) in [
        (b"<broken>".to_vec(), InspectRefusal::Xml),
        (
            b"<!DOCTYPE r:RDF []><r:RDF/>".to_vec(),
            InspectRefusal::Doctype,
        ),
        (vec![0xff, 0xfe, b'<', 0], InspectRefusal::Utf8),
    ] {
        assert_eq!(
            prepare(&input, &original, 0, replacement()).unwrap_err(),
            Refusal::Inspect(refusal)
        );
    }
}

#[test]
fn input_and_derivative_byte_bounds_refuse_without_mutating_input() {
    let original = original(true);
    let base = document(
        "",
        &format!("<e:DateTimeOriginal>{OLD}</e:DateTimeOriginal><!--PAD-->"),
    );
    let input = base.replace("PAD", &"p".repeat(65_530 - base.len() + 3));
    assert_eq!(input.len(), 65_530);
    let before = input.clone();
    assert_eq!(
        prepare(input.as_bytes(), &original, 0, replacement()).unwrap_err(),
        Refusal::DerivativeLimit
    );
    assert_eq!(input, before);
    let oversized = vec![b' '; 65_537];
    assert_eq!(
        prepare(&oversized, &original, 0, replacement()).unwrap_err(),
        Refusal::Inspect(InspectRefusal::Bytes)
    );
}

#[test]
fn fresh_inspection_rejects_a_stale_ordinal_and_incomplete_source_observation() {
    let before = document(
        "",
        &format!("<e:DateTimeOriginal>{OLD}</e:DateTimeOriginal>"),
    );
    let old_ordinal = target_ordinal(before.as_bytes());
    let changed = document(
        "u:inserted='changes-ordinal'",
        &format!("<e:DateTimeOriginal>{OLD}</e:DateTimeOriginal>"),
    );
    let original = original(false);
    assert_eq!(
        prepare(changed.as_bytes(), &original, old_ordinal, replacement()).unwrap_err(),
        Refusal::Mapping(MappingRefusal::TargetSelection)
    );
    let mut incomplete = original;
    incomplete.complete_selected_tag_coverage = false;
    assert_eq!(
        prepare(before.as_bytes(), &incomplete, old_ordinal, replacement()).unwrap_err(),
        Refusal::Mapping(MappingRefusal::IncompleteCoverage)
    );
}
