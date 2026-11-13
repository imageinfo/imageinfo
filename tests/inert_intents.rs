use std::{collections::BTreeMap, num::NonZeroU32};

use imageinfo::inert_intents::{
    DecodeError, ErrorKind, ErrorLocation, Format, Intent, OccurrenceObservation, PathPart, Scalar,
    SourceObservation, decode,
};
use serde::Deserialize;
use serde_json::{Value, json};

const HEADER: &str = "sourceKey,snapshotId,occurrenceId,namespace,nativeId,valueKind,decimal,numerator,denominator,text\r\n";

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct Fixture {
    vector_count: usize,
    accepted_count: usize,
    vectors: Vec<Vector>,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct Vector {
    id: String,
    transport: String,
    bindings: Vec<FixtureBinding>,
    input: String,
    pad_input_to_bytes: Option<usize>,
    expected_state: String,
    expected_document: Option<Value>,
    equivalence_group: Option<String>,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct FixtureBinding {
    source_key: String,
    snapshot_id: String,
    occurrences: Vec<FixtureOccurrence>,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct FixtureOccurrence {
    occurrence_id: String,
    namespace: String,
    native_id: String,
    document_ref: String,
    path: Vec<FixturePart>,
    ordinal: usize,
}

#[derive(Deserialize)]
struct FixturePart {
    kind: String,
    name: Option<String>,
    index: usize,
}

impl From<FixtureBinding> for SourceObservation {
    fn from(binding: FixtureBinding) -> Self {
        Self {
            source_key: binding.source_key,
            snapshot_id: binding.snapshot_id,
            occurrences: binding
                .occurrences
                .into_iter()
                .map(|occurrence| OccurrenceObservation {
                    occurrence_id: occurrence.occurrence_id,
                    namespace: occurrence.namespace,
                    native_id: occurrence.native_id,
                    document_ref: occurrence.document_ref,
                    path: occurrence
                        .path
                        .into_iter()
                        .map(|part| PathPart {
                            kind: part.kind,
                            name: part.name,
                            index: part.index,
                        })
                        .collect(),
                    ordinal: occurrence.ordinal,
                })
                .collect(),
        }
    }
}

#[test]
fn runtime_matches_every_frozen_vector() {
    let fixture: Fixture = serde_json::from_str(include_str!(
        "../docs/legacy-compatibility/report-import/vectors.v1.json"
    ))
    .unwrap();
    assert_eq!(fixture.vectors.len(), fixture.vector_count);
    let mut groups = BTreeMap::new();
    let mut accepted = 0;
    for vector in fixture.vectors {
        let format = match vector.transport.as_str() {
            "json" => Format::JsonV1,
            "csv" => Format::CsvV1,
            other => panic!("Unexpected fixture transport {other}"),
        };
        let bindings: Vec<_> = vector.bindings.into_iter().map(Into::into).collect();
        let mut input = vector.input.into_bytes();
        if let Some(size) = vector.pad_input_to_bytes {
            input.resize(input.len().max(size), b' ');
        }
        let result = decode(&input, format, &bindings);
        match vector.expected_state.as_str() {
            "refused" => assert!(result.is_err(), "{}", vector.id),
            "modeled-intents" => {
                let actual = result.unwrap_or_else(|error| panic!("{}: {error}", vector.id));
                let document = vector.expected_document.unwrap();
                let expected: Vec<_> = document["edits"]
                    .as_array()
                    .unwrap()
                    .iter()
                    .map(|edit| expected_intent(edit, &bindings))
                    .collect();
                assert_eq!(actual, expected, "{}", vector.id);
                if let Some(group) = vector.equivalence_group {
                    let group = groups.entry(group).or_insert_with(Vec::new);
                    group.push((format, actual));
                }
                accepted += 1;
            }
            other => panic!("Unexpected fixture state {other}"),
        }
    }
    assert_eq!(accepted, fixture.accepted_count);
    assert!(!groups.is_empty());
    for (group, actual) in groups {
        assert_eq!(actual.len(), 2, "{group}");
        assert_ne!(actual[0].0, actual[1].0, "{group}");
        assert_eq!(actual[0].1, actual[1].1, "{group}");
    }
}

fn expected_intent(edit: &Value, bindings: &[SourceObservation]) -> Intent {
    let binding = bindings
        .iter()
        .find(|binding| binding.source_key == edit["sourceKey"])
        .unwrap();
    assert_eq!(binding.snapshot_id, edit["snapshotId"]);
    let occurrence = binding
        .occurrences
        .iter()
        .find(|occurrence| occurrence.occurrence_id == edit["occurrenceId"])
        .unwrap();
    assert_eq!(occurrence.namespace, edit["namespace"]);
    assert_eq!(occurrence.native_id, edit["nativeId"]);
    let value = &edit["value"];
    let value = match value["kind"].as_str().unwrap() {
        "integer" => Scalar::Integer(value["decimal"].as_str().unwrap().parse().unwrap()),
        "rational" => Scalar::Rational {
            numerator: value["numerator"].as_str().unwrap().parse().unwrap(),
            denominator: value["denominator"].as_str().unwrap().parse().unwrap(),
        },
        "string" => Scalar::Text(value["text"].as_str().unwrap().to_owned()),
        other => panic!("Unexpected fixture value kind {other}"),
    };
    Intent {
        source_key: binding.source_key.clone(),
        snapshot_id: binding.snapshot_id.clone(),
        occurrence: occurrence.clone(),
        value,
    }
}

fn binding() -> SourceObservation {
    SourceObservation {
        source_key: "key".into(),
        snapshot_id: "snapshot".into(),
        occurrences: (1..=3)
            .map(|ordinal| OccurrenceObservation {
                occurrence_id: format!("occ-{ordinal}"),
                namespace: format!("namespace-{ordinal}"),
                native_id: "tag".into(),
                document_ref: "caller/document".into(),
                path: vec![PathPart {
                    kind: "tag".into(),
                    name: Some("path segment".into()),
                    index: ordinal + 20,
                }],
                ordinal,
            })
            .collect(),
    }
}

fn row(source: &SourceObservation, index: usize, value: Value) -> Value {
    let occurrence = &source.occurrences[index];
    json!({
        "sourceKey": source.source_key,
        "snapshotId": source.snapshot_id,
        "occurrenceId": occurrence.occurrence_id,
        "namespace": occurrence.namespace,
        "nativeId": occurrence.native_id,
        "operation": "set",
        "value": value,
    })
}

fn document(edits: Vec<Value>) -> String {
    json!({
        "schemaVersion": 1,
        "kind": "inert-scalar-intents",
        "edits": edits,
    })
    .to_string()
}

fn assert_error(
    input: impl AsRef<[u8]>,
    format: Format,
    bindings: &[SourceObservation],
    location: ErrorLocation,
    kind: ErrorKind,
) {
    assert_eq!(
        decode(input.as_ref(), format, bindings),
        Err(DecodeError { location, kind })
    );
}

#[test]
fn batches_are_owned_ordered_and_independent_across_callers() {
    let literal = "=SUM(1,2); \"$HOME\"\r\n{{é}} $(echo)\r\n🚲";
    let intents = {
        let table = [binding()];
        let input = document(vec![
            row(&table[0], 2, json!({"kind": "string", "text": literal})),
            row(&table[0], 0, json!({"kind": "integer", "decimal": "0"})),
            row(
                &table[0],
                1,
                json!({"kind": "rational", "numerator": "0", "denominator": "4294967295"}),
            ),
        ]);
        let csv = format!(
            "{HEADER}key,snapshot,occ-3,namespace-3,tag,string,,,,\"{}\"\r\nkey,snapshot,occ-1,namespace-1,tag,integer,0,,,\r\nkey,snapshot,occ-2,namespace-2,tag,rational,,0,4294967295,\r\n",
            literal.replace('"', "\"\"")
        );
        std::thread::scope(|scope| {
            let worker = scope.spawn(|| decode(input.as_bytes(), Format::JsonV1, &table).unwrap());
            let csv_intents = decode(csv.as_bytes(), Format::CsvV1, &table).unwrap();
            assert_eq!(worker.join().unwrap(), csv_intents);
            let mut changed = table.clone();
            changed[0].occurrences[2].ordinal = 90;
            let next = decode(input.as_bytes(), Format::JsonV1, &changed).unwrap();
            assert_eq!(next[0].occurrence.ordinal, 90);
            csv_intents
        })
    };
    assert_eq!(intents.len(), 3);
    assert_eq!(intents[0].value, Scalar::Text(literal.into()));
    assert_eq!(intents[0].occurrence.ordinal, 3);
    assert_eq!(intents[0].occurrence.path[0].index, 23);
    assert_eq!(intents[1].value, Scalar::Integer(0));
    assert_eq!(
        intents[2].value,
        Scalar::Rational {
            numerator: 0,
            denominator: NonZeroU32::MAX,
        }
    );
}

#[test]
fn json_object_types_and_row_errors_are_attributable() {
    let bindings = [binding()];
    let first = row(&bindings[0], 0, json!({"kind": "string", "text": ""})).to_string();
    let valid_second = row(&bindings[0], 1, json!({"kind": "string", "text": ""})).to_string();
    let envelope = |second: &str| {
        format!(r#"{{"edits":[{first},{second}],"kind":"inert-scalar-intents","schemaVersion":1}}"#)
    };
    let malformed_values = [
        r#"["key","snapshot","occ-2","namespace-2","tag","set",{"kind":"string","text":""}]"#,
        r#"{"sourceKey":"key","snapshotId":"snapshot","occurrenceId":"occ-2","namespace":"namespace-2","nativeId":"tag","operation":"set","value":["string",""]}"#,
        r#"{"sourceKey":"key","source\u004bey":"key","snapshotId":"snapshot","occurrenceId":"occ-2","namespace":"namespace-2","nativeId":"tag","operation":"set","value":{"kind":"string","text":""}}"#,
        r#"{"sourceKey":"key","snapshotId":"snapshot","occurrenceId":"occ-2","namespace":"namespace-2","nativeId":"tag","operation":"set","value":{"text":"","te\u0078t":"","kind":"string"}}"#,
        r#"{"sourceKey":"key","snapshotId":"snapshot","occurrenceId":"occ-2","namespace":"namespace-2","nativeId":"tag","operation":"set","value":{"kind":"string","ki\u006ed":"string","text":""}}"#,
    ];
    for second in malformed_values {
        assert_error(
            envelope(second),
            Format::JsonV1,
            &bindings,
            ErrorLocation::Row(2),
            ErrorKind::JsonShape,
        );
    }
    assert_error(
        envelope(&valid_second.replace(r#""text":"""#, r#""text":"\ud800""#)),
        Format::JsonV1,
        &bindings,
        ErrorLocation::Row(2),
        ErrorKind::JsonSyntax,
    );
    assert_error(
        envelope(&valid_second.replace("namespace-2", "Namespace-2")),
        Format::JsonV1,
        &bindings,
        ErrorLocation::Row(2),
        ErrorKind::IdentityMismatch,
    );
    assert_error(
        envelope(&first),
        Format::JsonV1,
        &bindings,
        ErrorLocation::Row(2),
        ErrorKind::DuplicateTarget,
    );
    assert_error(
        envelope(&valid_second).replace(
            r#""schemaVersion":1"#,
            r#""schemaVersion":1,"schemaVersio\u006e":1"#,
        ),
        Format::JsonV1,
        &bindings,
        ErrorLocation::Input,
        ErrorKind::JsonShape,
    );
    assert_error(
        r#"[1,"inert-scalar-intents",[]]"#,
        Format::JsonV1,
        &bindings,
        ErrorLocation::Input,
        ErrorKind::JsonShape,
    );
}

#[test]
fn csv_refusals_use_logical_rows_after_quoted_newlines() {
    let bindings = [binding()];
    let first = "key,snapshot,occ-1,namespace-1,tag,string,,,,\"x\ry\nz\r\nw\"\r\n";
    for (second, kind) in [
        ("# comment\r\n", ErrorKind::CsvWidth),
        ("\r\n", ErrorKind::CsvWidth),
        (
            "key,snapshot,occ-2,namespace-2,tag,string,,,,x\n",
            ErrorKind::CsvRecordEnding,
        ),
        (
            "key,snapshot,occ-2,namespace-2,tag,string,,,,x",
            ErrorKind::CsvRecordEnding,
        ),
        (
            "key,snapshot,occ-2,namespace-2,tag,string,,,,\"x",
            ErrorKind::CsvQuote,
        ),
        (
            "key,snapshot,occ-2,namespace-2,tag,string,,,,x\"\r\n",
            ErrorKind::CsvQuote,
        ),
        (
            "key,snapshot,occ-2,namespace-2,tag,string,,,,\"x\" \r\n",
            ErrorKind::CsvAfterQuote,
        ),
        (
            "key,snapshot,occ-2,namespace-2,tag,rational,,0,0,\r\n",
            ErrorKind::ZeroDenominator,
        ),
        (
            "key,snapshot,occ-2,namespace-2,tag,string,, , ,x\r\n",
            ErrorKind::CsvUnusedCell,
        ),
    ] {
        assert_error(
            format!("{HEADER}{first}{second}"),
            Format::CsvV1,
            &bindings,
            ErrorLocation::Row(2),
            kind,
        );
    }
    let text = format!("{HEADER}{first}");
    let result = decode(text.as_bytes(), Format::CsvV1, &bindings).unwrap();
    assert_eq!(result[0].value, Scalar::Text("x\ry\nz\r\nw".into()));
}

#[test]
fn bounds_apply_to_decoded_identity_and_both_byte_transports() {
    let mut source = binding();
    source.source_key = "_".repeat(64);
    source.snapshot_id = "é".repeat(256);
    source.occurrences[0].occurrence_id = "🚲".repeat(256);
    source.occurrences[0].namespace = "界".repeat(256);
    source.occurrences[0].native_id = "n".repeat(256);
    let valid = row(&source, 0, json!({"kind": "string", "text": ""}));
    let table = [source];
    let input = document(vec![valid.clone()]);
    let decoded = decode(input.as_bytes(), Format::JsonV1, &table).unwrap();
    assert_eq!(decoded[0].occurrence, table[0].occurrences[0]);
    for (field, extra, kind) in [
        ("sourceKey", "-", ErrorKind::SourceKey),
        ("snapshotId", "é", ErrorKind::IdentityLength),
        ("occurrenceId", "🚲", ErrorKind::IdentityLength),
        ("namespace", "界", ErrorKind::IdentityLength),
        ("nativeId", "n", ErrorKind::IdentityLength),
    ] {
        for invalid in [
            String::new(),
            format!("{}{extra}", valid[field].as_str().unwrap()),
        ] {
            let mut invalid_edit = valid.clone();
            invalid_edit[field] = json!(invalid);
            assert_error(
                document(vec![invalid_edit]),
                Format::JsonV1,
                &table,
                ErrorLocation::Row(1),
                kind,
            );
        }
    }
    for format in [Format::JsonV1, Format::CsvV1] {
        assert_error(
            [0xff],
            format,
            &table,
            ErrorLocation::Input,
            ErrorKind::Utf8,
        );
        assert_error(
            vec![b' '; 1_048_577],
            format,
            &table,
            ErrorLocation::Input,
            ErrorKind::InputBytes,
        );
    }
    let table = [binding()];
    let prefix = format!("{HEADER}key,snapshot,occ-1,namespace-1,tag,string,,,,");
    let scalar = "é".repeat(2_048);
    let valid_csv = format!("{prefix}{scalar}\r\n");
    assert_eq!(
        decode(valid_csv.as_bytes(), Format::CsvV1, &table).unwrap()[0].value,
        Scalar::Text(scalar.clone())
    );
    assert_error(
        format!("{prefix}{scalar}!\r\n"),
        Format::CsvV1,
        &table,
        ErrorLocation::Row(1),
        ErrorKind::TextBytes,
    );
    assert_error(
        valid_csv,
        Format::CsvV1,
        &[],
        ErrorLocation::Input,
        ErrorKind::BindingCount,
    );
}

#[test]
fn table_ambiguity_is_rejected_even_in_unused_bindings() {
    let first = binding();
    let edit = row(&first, 0, json!({"kind": "integer", "decimal": "0"}));
    let input = document(vec![edit]);
    let mut second = first.clone();
    second.snapshot_id = "other".into();
    assert_error(
        &input,
        Format::JsonV1,
        &[first.clone(), second.clone()],
        ErrorLocation::Binding(2),
        ErrorKind::DuplicateSourceKey,
    );
    second.source_key = "other".into();
    second.snapshot_id = first.snapshot_id.clone();
    assert_error(
        &input,
        Format::JsonV1,
        &[first.clone(), second.clone()],
        ErrorLocation::Binding(2),
        ErrorKind::DuplicateSnapshotId,
    );
    second.snapshot_id = "other".into();
    second.occurrences.push(second.occurrences[0].clone());
    assert_error(
        input,
        Format::JsonV1,
        &[first, second],
        ErrorLocation::Binding(2),
        ErrorKind::DuplicateOccurrenceId,
    );
}

#[test]
fn csv_accepts_64_distinct_edits_and_refuses_a_valid_65th() {
    use std::fmt::Write as _;

    let mut source = binding();
    let template = source.occurrences[0].clone();
    source.occurrences = (1..=65)
        .map(|ordinal| OccurrenceObservation {
            occurrence_id: format!("occ-{ordinal}"),
            ordinal,
            ..template.clone()
        })
        .collect();
    let bindings = [source];
    let mut csv = HEADER.to_owned();
    for index in 1..=64 {
        write!(
            csv,
            "key,snapshot,occ-{index},namespace-1,tag,integer,{index},,,\r\n"
        )
        .unwrap();
    }

    let accepted = decode(csv.as_bytes(), Format::CsvV1, &bindings).unwrap();
    assert_eq!(accepted.len(), 64);
    for (ordinal, intent) in (1..=64).zip(accepted) {
        assert_eq!(intent.occurrence.ordinal, ordinal);
        assert_eq!(intent.value, Scalar::Integer(ordinal as u64));
    }

    let extra = "key,snapshot,occ-65,namespace-1,tag,integer,65,,,\r\n";
    let single = decode(
        format!("{HEADER}{extra}").as_bytes(),
        Format::CsvV1,
        &bindings,
    )
    .unwrap();
    assert_eq!(single[0].value, Scalar::Integer(65));
    csv.push_str(extra);
    assert_error(
        csv,
        Format::CsvV1,
        &bindings,
        ErrorLocation::Input,
        ErrorKind::EditCount,
    );
}
