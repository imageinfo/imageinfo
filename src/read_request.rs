//! Bounded request-local metadata reads through the ordinary native read workflow.
use crate::{
    cli::{self, Invocation, OutputFormat, ReadRequest, ValueView},
    output::{Effects, FileRecord, Issue, ResultEnvelope},
    reader::{self, Value},
};
use std::{
    collections::BTreeSet,
    ffi::OsString,
    io::{self, Write},
};

pub const MAX_REQUEST_ID_BYTES: usize = 128;
pub const MAX_TOKENS: usize = 128;
pub const MAX_TOKEN_BYTES: usize = 32_768;
pub const MAX_TOTAL_TOKEN_BYTES: usize = 65_536;
pub const MAX_API_INPUTS: usize = 4;
pub const MAX_METADATA_BYTES: u64 = 8 * 1024 * 1024;
/// Includes the final LF, and bounds the serialized result rather than heap use.
pub const MAX_RESULT_BYTES: usize = 16 * 1024 * 1024;

/// Execute command tokens without argv[0], admitting only `metadata read`.
///
/// Tokens remain native `OsString` values; no shell, configuration load, process,
/// persistent state or current-directory change is involved. Relative paths use
/// the caller process's current directory. The API owns JSON result transport:
/// output selectors are rejected except when they are literal operands after `--`.
pub fn execute(request_id: &str, tokens: &[OsString]) -> ResultEnvelope {
    if request_id.is_empty()
        || request_id.len() > MAX_REQUEST_ID_BYTES
        || !request_id.as_bytes()[0].is_ascii_alphabetic()
        || !request_id
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || b"._:-".contains(&byte))
    {
        return refusal(
            "invalid-request",
            "REQUEST_ID_INVALID",
            "Request IDs use 1–128 ASCII bytes: a leading letter followed by letters, digits, period, underscore, colon or hyphen.",
            2,
        );
    }
    if tokens.len() > MAX_TOKENS
        || tokens
            .iter()
            .any(|token| token.as_encoded_bytes().len() > MAX_TOKEN_BYTES)
        || tokens
            .iter()
            .try_fold(0_usize, |size, token| {
                size.checked_add(token.as_encoded_bytes().len())
            })
            .is_none_or(|size| size > MAX_TOTAL_TOKEN_BYTES)
    {
        return refusal(
            request_id,
            "REQUEST_LIMIT",
            "The token count or native encoded-byte budget exceeds this API's finite limits.",
            2,
        );
    }
    let parsed =
        cli::parse(std::iter::once(OsString::from("imageinfo")).chain(tokens.iter().cloned()));
    let mut request = match parsed {
        Ok(Invocation::Read(request)) => request,
        Ok(_) => {
            return refusal(
                request_id,
                "REQUEST_OPERATION_UNSUPPORTED",
                "This API admits metadata read only; help, version, preview, binary, pairing and mutation commands are outside this entry point.",
                2,
            );
        }
        Err(error) => return bounded(refusal(request_id, error.code, &error.message, 2)),
    };
    if tokens
        .iter()
        .take_while(|token| token.as_os_str() != "--")
        .any(|token| {
            token == "--output"
                || token
                    .to_str()
                    .is_some_and(|token| token.starts_with("--output="))
        })
    {
        return refusal(
            request_id,
            "REQUEST_OUTPUT_UNSUPPORTED",
            "The API owns JSON transport; omit CLI output selectors. Operands after -- remain literal paths.",
            2,
        );
    }
    if request.inputs.len() > MAX_API_INPUTS || request.limits.metadata_bytes > MAX_METADATA_BYTES {
        return refusal(
            request_id,
            "REQUEST_LIMIT",
            "This API admits at most four explicit inputs and at most 8 MiB metadata-read budget per input.",
            2,
        );
    }
    request.output = OutputFormat::Json;
    bounded(read_report(request, request_id.into(), false).record)
}

fn refusal(id: &str, code: &'static str, message: &str, status: u8) -> ResultEnvelope {
    ResultEnvelope::new(id.into(), None, code, message.into(), status)
}

fn bounded(record: ResultEnvelope) -> ResultEnvelope {
    if size_check(&record).is_ok() {
        record
    } else {
        refusal(
            &record.request_id,
            "RESULT_LIMIT",
            "The serialized read result exceeds the 16 MiB API result budget; no source changes or output artifacts occurred.",
            1,
        )
    }
}

struct SizeCheck(usize);
impl Write for SizeCheck {
    fn write(&mut self, bytes: &[u8]) -> io::Result<usize> {
        self.0 = self
            .0
            .checked_add(bytes.len())
            .filter(|size| *size < MAX_RESULT_BYTES)
            .ok_or_else(|| io::Error::from(io::ErrorKind::FileTooLarge))?;
        Ok(bytes.len())
    }
    fn flush(&mut self) -> io::Result<()> {
        Ok(())
    }
}

fn serialization_error(error: serde_json::Error) -> io::Error {
    io::Error::new(
        error.io_error_kind().unwrap_or(io::ErrorKind::InvalidData),
        error,
    )
}

fn size_check(record: &ResultEnvelope) -> io::Result<()> {
    // Leave exactly one byte for the transport LF. The preflight never writes
    // to the caller's sink, so a size refusal cannot emit a misleading prefix.
    serde_json::to_writer(SizeCheck(0), record).map_err(serialization_error)
}

/// Serialize one bounded envelope plus LF and flush the caller-owned sink.
///
/// An error means transport is incomplete even if the in-memory record is valid.
/// Callers must not treat a partial prefix or `outputComplete` inside a truncated
/// stream as delivery success. No sink is opened or selected by this function.
pub fn write_result(writer: &mut impl Write, record: &ResultEnvelope) -> io::Result<()> {
    size_check(record)?;
    serde_json::to_writer(&mut *writer, record).map_err(serialization_error)?;
    writer.write_all(b"\n")?;
    writer.flush()
}

/// Shared CLI adapter data. The token-array API returns the envelope directly.
#[doc(hidden)]
pub struct NativeReadReport {
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

/// Shared existing CLI read implementation; the binary retains its original
/// 16-input boundary. Integration callers use `execute` for the narrower API.
#[doc(hidden)]
pub fn read_report(request: ReadRequest, id: String, binary_only: bool) -> NativeReadReport {
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
    NativeReadReport {
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
) -> NativeReadReport {
    let diagnostics = vec![format!("{code}: {message}")];
    NativeReadReport {
        format,
        record: ResultEnvelope::new(id, Some(operation), code, message, 2),
        text: String::new(),
        diagnostics,
        status: 2,
    }
}
