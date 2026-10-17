//! Filesystem workflow and result adaptation for the thin executable.
use imageinfo::{
    cli::{DatePreviewRequest, ExtractRequest, OutputFormat, PairRequest, ReadRequest},
    output::{ArtifactRecord, Effects, FileRecord, Issue, ResultEnvelope},
    reader,
};

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

pub fn date_preview(request: DatePreviewRequest, id: String) -> Report {
    let mut report = observation_report(
        request.output,
        id,
        "preview date-time-original",
        "preview",
        &request.input,
    );
    let result = (|| {
        let unsupported = || reader::Error {
            code: "CAPABILITY_UNSUPPORTED",
            message: "Only regular file inputs are supported".into(),
        };
        if !std::fs::metadata(&request.input)?.is_file() {
            return Err(unsupported());
        }
        let input = std::fs::File::open(&request.input)?;
        if !input.metadata()?.is_file() {
            return Err(unsupported());
        }
        imageinfo::preview::date_time_original(
            input,
            &request.value,
            request
                .offset
                .map(|offset| reader::Range { offset, length: 20 }),
        )
    })();
    match result {
        Ok(preview) => {
            report.record.files[0].state =
                if preview.status == imageinfo::preview::PreviewStatus::Refused {
                    "refused"
                } else {
                    "previewed"
                };
            report.text = format!(
                "Read-only DateTimeOriginal preview: {:?}\nHypothetical changed bytes: {}; preserved bytes: {:?}\nProduction mutation allowed: false\n",
                preview.status, preview.changed_bytes, preview.preserved_bytes
            );
            for finding in &preview.refusals {
                observation_error(
                    &mut report,
                    finding.code,
                    "Date intent refused by the actual admission checks.".into(),
                );
            }
            report.record.files[0].snapshot = Some(
                serde_json::json!({"schemaVersion": 1, "kind": "date-preview", "preview": preview}),
            );
        }
        Err(error) => observation_error(&mut report, error.code, error.message),
    }
    finish_observation(report)
}

pub fn pair(request: PairRequest, id: String) -> Report {
    let mut report = observation_report(request.output, id, "sidecar pair", "read", &request.raw);
    match imageinfo::pairing::resolve_pair(&request.raw, request.sidecar.as_deref()) {
        Ok(pair) => {
            report.record.files[0].state = "read";
            report.text = format!(
                "Explicit RAW/sidecar association: {:?} -> {:?}\nNo files created or modified; contents not interpreted.\n",
                pair.raw_path, pair.sidecar_path
            );
            report.record.files[0].snapshot = Some(
                serde_json::json!({"schemaVersion": 1, "kind": "explicit-pair", "pair": pair}),
            );
        }
        Err(error) => observation_error(&mut report, error.code, error.message),
    }
    finish_observation(report)
}

pub fn infer_pair(request: PairRequest, id: String) -> Report {
    let mut report =
        observation_report(request.output, id, "sidecar pair", "preview", &request.raw);
    match imageinfo::pairing::infer_same_stem(&request.raw) {
        Ok(proposal) => {
            report.record.files[0].state = "previewed";
            report.text = format!(
                "Proposed same-stem RAW/sidecar association: {:?} -> {:?}\nRule: {}; both origins retained in JSON preview.\nPath observation only; no files created or modified.\n",
                proposal.raw_origin, proposal.sidecar_origin, proposal.rule
            );
            report.record.files[0].snapshot = Some(
                serde_json::json!({"schemaVersion": 1, "kind": "inferred-pair-preview", "proposal": proposal, "mutationAllowed": false}),
            );
        }
        Err(error) => observation_error(&mut report, error.code, error.message),
    }
    finish_observation(report)
}

fn observation_report(
    format: OutputFormat,
    id: String,
    operation: &'static str,
    mode: &'static str,
    input: &std::path::Path,
) -> Report {
    let mut record = ResultEnvelope::empty(id.clone(), operation, mode);
    record.files.push(FileRecord {
        schema_version: 1,
        kind: "file",
        request_id: id,
        input_id: "input-0".into(),
        path: input.to_string_lossy().into_owned(),
        state: "refused",
        snapshot: None,
        transaction_id: None,
        effects: Effects::default(),
        issues: Vec::new(),
    });
    Report {
        format,
        record,
        text: String::new(),
        diagnostics: Vec::new(),
        status: 0,
    }
}

fn observation_error(report: &mut Report, code: &'static str, message: String) {
    report.status = 1;
    report.diagnostics.push(format!("{code}: {message}"));
    report.record.files[0]
        .issues
        .push(issue(code, "error", message, Some("input-0".into())));
}

fn finish_observation(mut report: Report) -> Report {
    report.record.summary.counts.discovered = 1;
    report
        .record
        .summary
        .counts
        .by_state
        .insert(report.record.files[0].state.into(), 1);
    report.record.summary.exit_status = report.status;
    report
}

pub fn read(request: ReadRequest, id: String, binary_only: bool) -> Report {
    let shared = imageinfo::read_request::read_report(request, id, binary_only);
    Report {
        format: shared.format,
        record: shared.record,
        text: shared.text,
        diagnostics: shared.diagnostics,
        status: shared.status,
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
