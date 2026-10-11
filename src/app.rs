//! Filesystem workflow and result adaptation for the thin executable.
use imageinfo::{
    cli::{ExtractRequest, OutputFormat, ReadRequest, ValueView},
    output::{ArtifactRecord, Effects, FileRecord, Issue, ResultEnvelope},
    reader::{self, Value},
};
use std::collections::BTreeSet;

pub struct Report {
    pub format: OutputFormat,
    pub record: ResultEnvelope,
    pub text: String,
    pub diagnostics: Vec<String>,
    pub status: u8,
}

fn issue(
    code: &'static str,
    severity: &'static str,
    message: String,
    input: Option<String>,
) -> Issue {
    Issue {
        code,
        severity,
        message,
        input_id: input,
        path: None,
        occurrence_ref: None,
    }
}

pub fn read(request: ReadRequest, id: String, binary_only: bool) -> Report {
    let operation = if binary_only {
        "binary list"
    } else {
        "metadata read"
    };
    for tag in &request.tags {
        if let Err(error) = reader::selector(tag) {
            return invalid(request.output, id, operation, error.code, error.message);
        }
    }
    if request.inputs.len() > 16 {
        return invalid(request.output,id,operation,"LIMIT_EXCEEDED","At most 16 explicit inputs are supported per invocation; use separate requests for larger collections.".into());
    }
    let mut record = ResultEnvelope::empty(id.clone(), operation, "read");
    let mut text = String::new();
    let mut diagnostics = Vec::new();
    let mut seen = BTreeSet::new();
    for path in &request.inputs {
        if !seen.insert(path.clone()) {
            record.summary.counts.deduplicated += 1;
            continue;
        }
        let input_id = format!("input-{}", record.files.len());
        let display = path.to_string_lossy().into_owned();
        let mut file = FileRecord {
            schema_version: 1,
            kind: "file",
            request_id: id.clone(),
            input_id: input_id.clone(),
            path: display.clone(),
            state: "failed",
            snapshot: None,
            transaction_id: None,
            effects: Effects::default(),
            issues: Vec::new(),
        };
        match reader::read_file(path, request.limits) {
            Ok(metadata) => {
                let indices = if binary_only {
                    metadata
                        .occurrences
                        .iter()
                        .enumerate()
                        .filter(|(_, o)| matches!(o.value, Value::Binary(_)))
                        .map(|(i, _)| i)
                        .collect()
                } else {
                    reader::select(&metadata, &request.tags)
                        .expect("Selectors validated before reading")
                };
                let invalid_value = indices
                    .iter()
                    .any(|&i| matches!(metadata.occurrences[i].value, Value::Rational(_, 0)));
                file.state = if invalid_value { "failed" } else { "read" };
                if invalid_value {
                    file.issues.push(issue("INVALID_VALUE","error","A selected rational has a zero denominator; raw bytes remain represented in the partial snapshot.".into(),Some(input_id.clone())));
                }
                file.issues.push(issue("COVERAGE_PARTIAL","warning","Only the declared R5 metadata/preview slice is interpreted. Other fields and embedded metadata are not inspected.".into(),Some(input_id.clone())));
                if !path.as_os_str().is_empty() && path.to_str().is_none() {
                    file.issues.push(issue("PATH_DISPLAY_LOSSY","warning","Native path bytes were preserved for I/O; JSON display uses replacement characters and is not path authority.".into(),Some(input_id.clone())));
                }
                if indices.is_empty() {
                    file.issues.push(issue("TAG_UNRESOLVED","warning","No requested occurrence was observed within partial coverage; this does not establish global absence.".into(),Some(input_id.clone())));
                }
                text.push_str(&format!(
                    "{display:?} — Canon EOS R5 full RAW (declared profile), partial coverage\n"
                ));
                for &i in &indices {
                    let occurrence = &metadata.occurrences[i];
                    let mut value = match request.values {
                        ValueView::Display => reader::text_value(occurrence),
                        _ => match &occurrence.value {
                            Value::Integer(n) => n.to_string(),
                            Value::Rational(n, d) => format!("{n}/{d}"),
                            Value::Text(s) => s.clone(),
                            Value::Binary(range) => {
                                format!("{} stored bytes at offset {}", range.length, range.offset)
                            }
                        },
                    };
                    if request.values == ValueView::All {
                        value = format!(
                            "raw={value}; normalized={value}; display={:?}",
                            reader::text_value(occurrence)
                        );
                    }
                    text.push_str(&format!(
                        "  {}:{} [{}] = {value}\n",
                        occurrence.namespace, occurrence.name, i
                    ));
                }
                file.snapshot = Some(metadata.snapshot(
                    &format!("{id}-snapshot-{}", record.files.len()),
                    &display,
                    &indices,
                    matches!(request.values, ValueView::All | ValueView::Display),
                ));
            }
            Err(error) => {
                file.state = if error.code == "CAPABILITY_UNSUPPORTED" {
                    "refused"
                } else {
                    "failed"
                };
                diagnostics.push(format!("{}: {} ({display:?})", error.code, error.message));
                file.issues
                    .push(issue(error.code, "error", error.message, Some(input_id)));
            }
        }
        record.files.push(file);
    }
    record.summary.counts.discovered = record.files.len() as u32;
    let successes = record.files.iter().filter(|f| f.state == "read").count();
    let status = if successes == record.files.len() {
        0
    } else if successes > 0 {
        3
    } else {
        1
    };
    for file in &record.files {
        *record
            .summary
            .counts
            .by_state
            .entry(file.state.into())
            .or_default() += 1;
    }
    record.summary.exit_status = status;
    Report {
        format: request.output,
        record,
        text,
        diagnostics,
        status,
    }
}

pub fn extract(request: ExtractRequest, id: String) -> Report {
    let mut record = ResultEnvelope::empty(
        id.clone(),
        "binary extract",
        if request.dry_run { "preview" } else { "read" },
    );
    let display = request.input.to_string_lossy().into_owned();
    let target = request.destination.to_string_lossy().into_owned();
    let input_id = "input-0".to_owned();
    let mut file = FileRecord {
        schema_version: 1,
        kind: "file",
        request_id: id,
        input_id: input_id.clone(),
        path: display,
        state: "failed",
        snapshot: None,
        transaction_id: None,
        effects: Effects::default(),
        issues: Vec::new(),
    };
    let (status, text, diagnostics) = match reader::extract(
        &request.input,
        &request.destination,
        &request.tag,
        request.limits,
        request.dry_run,
    ) {
        Ok(bytes) => {
            file.state = if request.dry_run { "previewed" } else { "read" };
            if !request.dry_run {
                record.summary.artifacts.push(ArtifactRecord {
                    kind: "extraction",
                    path: target.clone(),
                    retained_path: None,
                    state: "committed",
                    transaction_id: None,
                    recovery_ids: Vec::new(),
                });
            }
            (
                0,
                format!(
                    "{} {}: {bytes} stored bytes -> {target:?}\n",
                    if request.dry_run {
                        "Would extract"
                    } else {
                        "Extracted"
                    },
                    request.tag
                ),
                Vec::new(),
            )
        }
        Err(error) => {
            let status = if error.code == "CLEANUP_REQUIRED" {
                5
            } else {
                1
            };
            if status == 5 {
                record.summary.artifacts.push(ArtifactRecord {
                    kind: "extraction",
                    path: target,
                    retained_path: None,
                    state: "recovery-required",
                    transaction_id: None,
                    recovery_ids: Vec::new(),
                });
            }
            file.issues.push(issue(
                error.code,
                "error",
                error.message.clone(),
                Some(input_id),
            ));
            (
                status,
                String::new(),
                vec![format!("{}: {}", error.code, error.message)],
            )
        }
    };
    record.summary.counts.discovered = 1;
    record.summary.counts.by_state.insert(file.state.into(), 1);
    record.files.push(file);
    record.summary.exit_status = status;
    Report {
        format: request.output,
        record,
        text,
        diagnostics,
        status,
    }
}

fn invalid(
    format: OutputFormat,
    id: String,
    operation: &'static str,
    code: &'static str,
    message: String,
) -> Report {
    let diagnostics = vec![format!("{code}: {message}")];
    Report {
        format,
        record: ResultEnvelope::new(id, Some(operation), code, message, 2),
        text: String::new(),
        diagnostics,
        status: 2,
    }
}
