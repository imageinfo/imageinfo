//! Explicit local authored-marker observer for #0218. This test-only wrapper
//! preserves the ordinary unqualified backend/runtime operation order. Its
//! diagnostic observations and private-pipe releases confer no storage authority.

use super::runtime::{Artifact, Backend, Binding, LiveEvidence, ValidatedCandidate};
use super::windows::WindowsBackend;
use super::{Cancellation, Failure, LogicalBudget, Phase, UnitResult};
use serde::Deserialize;
use serde_json::{Value, json};
use std::io::{self, BufRead, Cursor, Read, Write};
use std::os::windows::fs::MetadataExt;
use std::path::{Path, PathBuf};
use std::sync::mpsc::{self, Receiver, RecvTimeoutError};
use std::time::Duration;

pub(super) const MAX_ACK_BYTES: usize = 1024;
const MAX_EVENT_BYTES: usize = 32_768;
const MAX_EVENTS: u64 = 128;
const GATE_TIMEOUT: Duration = Duration::from_secs(15);
const SOURCE_LEN: u64 = 16 * 1024 * 1024;
const CANDIDATE_LEN: usize = 4 * 1024 * 1024;
const MARKER: &[u8] = b"imageinfo-0218-disposable-authored-only-v1\n";
const PREFIX: &[u8] = b"IMAGEINFO218 ";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(super) enum GateError {
    Eof,
    TooLong,
    Malformed,
    Mismatch,
    Cancelled,
    Timeout,
    Io,
    EventBound,
    Output,
}

/// Read at most the declared framing bound. An incomplete final line is never
/// an acknowledgement; CRLF and embedded line breaks are outside this profile.
pub(super) fn read_ack_line<R: BufRead>(input: &mut R) -> Result<Vec<u8>, GateError> {
    let mut line = Vec::new();
    loop {
        let available = input.fill_buf().map_err(|_| GateError::Io)?;
        if available.is_empty() {
            return Err(GateError::Eof);
        }
        let count = available
            .iter()
            .position(|byte| *byte == b'\n')
            .map_or(available.len(), |index| index + 1);
        if count > MAX_ACK_BYTES - line.len() {
            return Err(GateError::TooLong);
        }
        let complete = available[count - 1] == b'\n';
        line.extend_from_slice(&available[..count]);
        input.consume(count);
        if complete {
            return if line.contains(&b'\r') {
                Err(GateError::Malformed)
            } else {
                Ok(line)
            };
        }
        if line.len() == MAX_ACK_BYTES {
            return Err(GateError::TooLong);
        }
    }
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Acknowledgement {
    v: u8,
    unit: String,
    seq: u64,
    stage: String,
    command: String,
}

pub(super) fn parse_ack(
    line: &[u8],
    unit: &str,
    sequence: u64,
    stage: &str,
    command: &str,
) -> Result<(), GateError> {
    if line.len() > MAX_ACK_BYTES {
        return Err(GateError::TooLong);
    }
    if line.last() != Some(&b'\n')
        || line[..line.len() - 1].contains(&b'\n')
        || line.contains(&b'\r')
    {
        return Err(GateError::Malformed);
    }
    let ack: Acknowledgement = serde_json::from_slice(line).map_err(|_| GateError::Malformed)?;
    if ack.v != 1 || ack.unit != unit || ack.seq != sequence || ack.stage != stage || sequence == 0
    {
        return Err(GateError::Mismatch);
    }
    if ack.command == "cancel" {
        return Err(GateError::Cancelled);
    }
    if ack.command != command || !matches!(command, "continue" | "release") {
        return Err(GateError::Mismatch);
    }
    Ok(())
}

pub(super) fn receive_ack(
    input: &Receiver<Result<Vec<u8>, GateError>>,
    timeout: Duration,
    unit: &str,
    sequence: u64,
    stage: &str,
    command: &str,
) -> Result<(), GateError> {
    let line = input.recv_timeout(timeout).map_err(|error| match error {
        RecvTimeoutError::Timeout => GateError::Timeout,
        RecvTimeoutError::Disconnected => GateError::Eof,
    })??;
    parse_ack(&line, unit, sequence, stage, command)
}

fn input_channel() -> Receiver<Result<Vec<u8>, GateError>> {
    // One queued bounded line plus the reader's one bounded in-flight line.
    // The detached reader performs no filesystem work. Process exit ends any
    // blocked stdin read after timeout; the owning supervisor also bounds exit.
    let (sender, receiver) = mpsc::sync_channel(1);
    std::thread::spawn(move || {
        let mut input = io::stdin().lock();
        loop {
            let line = read_ack_line(&mut input);
            let failed = line.is_err();
            if sender.send(line).is_err() || failed {
                break;
            }
        }
    });
    receiver
}

fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|byte| format!("{byte:02x}")).collect()
}

fn bindings(native: &WindowsBackend) -> Value {
    // These are the original backend's immutable expected observations. They
    // are neither a fresh native recheck nor a recoverable action capability.
    json!(
        native
            .qualification_bindings()
            .iter()
            .map(|binding| {
                json!({"identity": hex(&binding.identity), "facts": hex(&binding.facts)})
            })
            .collect::<Vec<_>>()
    )
}

struct Notices<W> {
    unit: String,
    sequence: u64,
    input: Receiver<Result<Vec<u8>, GateError>>,
    output: W,
    failed: Option<GateError>,
}

impl<W: Write> Notices<W> {
    fn emit(
        &mut self,
        kind: &str,
        stage: &str,
        result: Value,
        bindings: Value,
    ) -> Result<u64, GateError> {
        let next = self.sequence.checked_add(1).ok_or(GateError::EventBound)?;
        // Keep space for a refusal event and the two terminal lifetime notices
        // if a future runtime ever grows beyond this finite observer profile.
        let limit = match kind {
            "runtime_result" | "backend_dropped" => MAX_EVENTS,
            "gate_error" => MAX_EVENTS - 2,
            _ => MAX_EVENTS - 3,
        };
        if next > limit {
            return Err(GateError::EventBound);
        }
        let event = json!({"v": 1, "unit": self.unit, "seq": next,
            "kind": kind, "stage": stage, "result": result, "bindings": bindings,
            "committed": false, "production_profile_admitted": false,
            "raw_admitted": false, "authority_importable": false});
        let bytes = serde_json::to_vec(&event).map_err(|_| GateError::Output)?;
        if bytes.len() + PREFIX.len() + 1 > MAX_EVENT_BYTES {
            return Err(GateError::EventBound);
        }
        self.output
            .write_all(PREFIX)
            .and_then(|()| self.output.write_all(&bytes))
            .and_then(|()| self.output.write_all(b"\n"))
            .and_then(|()| self.output.flush())
            .map_err(|_| GateError::Output)?;
        self.sequence = next;
        Ok(next)
    }

    fn gate(
        &mut self,
        sequence: u64,
        stage: &str,
        command: &str,
        bindings: Value,
    ) -> Result<(), Failure> {
        let result = receive_ack(
            &self.input,
            GATE_TIMEOUT,
            &self.unit,
            sequence,
            stage,
            command,
        );
        if let Err(error) = result {
            self.failed = Some(error);
            // Best effort only: a broken output pipe itself can prevent capture.
            let _ = self.emit(
                "gate_error",
                stage,
                json!({"error": format!("{error:?}"), "rejected_seq": sequence,
                    "rejected_stage": stage}),
                bindings,
            );
            return Err(Failure::CallerHistory);
        }
        Ok(())
    }

    fn observation_failure(&mut self, error: GateError) -> Failure {
        self.failed = Some(error);
        Failure::CallerHistory
    }
}

struct Observed<W> {
    native: WindowsBackend,
    notices: Notices<W>,
}

impl<W: Write> Observed<W> {
    fn call<T>(
        &mut self,
        stage: &str,
        operation: impl FnOnce(&mut WindowsBackend) -> Result<T, Failure>,
    ) -> Result<T, Failure> {
        if self.notices.failed.is_some() {
            return Err(Failure::CallerHistory);
        }
        let sequence = self
            .notices
            .emit(
                "before_operation",
                stage,
                Value::Null,
                bindings(&self.native),
            )
            .map_err(|error| self.notices.observation_failure(error))?;
        self.notices
            .gate(sequence, stage, "continue", bindings(&self.native))?;
        let _ = super::windows::take_native_error();
        let result = operation(&mut self.native);
        let native_error = super::windows::take_native_error();
        let candidate = stage == "create-Candidate";
        let sequence = self.notices.emit(
            if candidate { "candidate_result" } else { "operation_result" }, stage,
            json!({"success": result.is_ok(), "failure": result.as_ref().err().map(|e| format!("{e:?}")),
                "native_error_kind": native_error.map(|(kind, _)| format!("{kind:?}")),
                "native_os_error": native_error.and_then(|(_, code)| code)}), bindings(&self.native))
            .map_err(|error| self.notices.observation_failure(error))?;
        if candidate {
            // The compound SDK call has returned, but this wrapper has not
            // returned its Result to runtime failure handling. The original
            // backend/source/root remain owned here. A failed temporary SDK
            // artifact handle may already have closed inside that call.
            self.notices
                .gate(sequence, stage, "release", bindings(&self.native))?;
        }
        result
    }
}

impl<W: Write> Backend for Observed<W> {
    fn profile(&self) -> &'static str {
        self.native.profile()
    }
    fn implementation(&self) -> &'static str {
        self.native.implementation()
    }
    fn preflight(&mut self, output: &str) -> Result<Binding, Failure> {
        self.call("preflight", |native| native.preflight(output))
    }
    fn create_root(&mut self) -> Result<Binding, Failure> {
        self.call("create-root", Backend::create_root)
    }
    fn create(&mut self, kind: Artifact, bytes: &[u8]) -> Result<Binding, Failure> {
        self.call(&format!("create-{kind:?}"), |native| {
            native.create(kind, bytes)
        })
    }
    fn check(&mut self, phase: Phase, bindings: &[Binding]) -> Result<(), Failure> {
        self.call(&format!("check-{phase:?}"), |native| {
            native.check(phase, bindings)
        })
    }
    fn flush_file(&mut self, kind: Artifact) -> Result<(), Failure> {
        self.call(&format!("file-{kind:?}"), |native| native.flush_file(kind))
    }
    fn flush_root(&mut self) -> Result<(), Failure> {
        self.call("root-flush", Backend::flush_root)
    }
    fn flush_parent(&mut self) -> Result<(), Failure> {
        self.call("parent-flush", Backend::flush_parent)
    }
    fn publish(&mut self, output: &str) -> Result<(), Failure> {
        self.call("publish", |native| native.publish(output))
    }
    fn caller_release(&mut self, bindings: &[Binding]) -> Result<(), Failure> {
        self.call("release", |native| native.caller_release(bindings))
    }
    fn checked_context(&mut self, bindings: &[Binding]) -> Result<(), Failure> {
        self.call("checked-context", |native| native.checked_context(bindings))
    }
    fn export_terminal(&mut self, bindings: &[Binding]) -> Result<(), Failure> {
        self.call("terminal", |native| native.export_terminal(bindings))
    }
    fn retain_live_evidence(&mut self, evidence: &LiveEvidence) {
        self.native.retain_live_evidence(evidence);
    }
    fn retain_outcome(&mut self, phase: Phase, failure: Option<Failure>) {
        self.native.retain_outcome(phase, failure);
    }
}

fn result(value: &UnitResult) -> Value {
    json!({"status": format!("{:?}", value.status), "phase": format!("{:?}", value.phase),
        "failure": value.failure.map(|error| format!("{error:?}")),
        "publication_possible": value.publication_possible, "release_possible": value.release_possible,
        "protocol_complete": value.protocol_complete, "retained_material": value.retained_material,
        "pending_cleanup": value.pending_cleanup, "charged_bytes": value.charged_bytes})
}

fn authored_fixture(path: &Path) -> io::Result<()> {
    let allowed = std::fs::canonicalize(Path::new(env!("CARGO_MANIFEST_DIR")).join(".local"))?;
    let actual = std::fs::canonicalize(path)?;
    if !actual.starts_with(&allowed) || actual == allowed {
        return Err(io::Error::other("DIAGNOSTIC_LOCAL_FIXTURE_REQUIRED"));
    }
    authored_marker_fixture(path, "fixture218.marker", MARKER)
}

/// Bounded marker/source checks shared by the separately gated test entries.
/// Callers select their path boundary before invoking these read-only checks.
pub(super) fn authored_marker_fixture(
    path: &Path,
    marker_name: &str,
    marker_value: &[u8],
) -> io::Result<()> {
    let meta = std::fs::symlink_metadata(path)?;
    if !meta.is_dir() || meta.file_attributes() & 0x400 != 0 {
        return Err(io::Error::other("DIAGNOSTIC_FIXTURE_DIRECTORY"));
    }
    let marker = path.join(marker_name);
    let meta = std::fs::symlink_metadata(&marker)?;
    if !meta.is_file()
        || meta.len() != marker_value.len() as u64
        || meta.file_attributes() & 0x400 != 0
    {
        return Err(io::Error::other("DIAGNOSTIC_FIXTURE_MARKER"));
    }
    let mut marker_bytes = Vec::new();
    std::fs::File::open(marker)?
        .take(marker_value.len() as u64 + 1)
        .read_to_end(&mut marker_bytes)?;
    if marker_bytes != marker_value {
        return Err(io::Error::other("DIAGNOSTIC_FIXTURE_MARKER"));
    }
    let source = path.join("source.bin");
    let meta = std::fs::symlink_metadata(&source)?;
    if !meta.is_file() || meta.len() != SOURCE_LEN || meta.file_attributes() & 0x400 != 0 {
        return Err(io::Error::other("DIAGNOSTIC_SOURCE_BOUND"));
    }
    let mut file = std::fs::File::open(source)?;
    let mut buffer = [0; 16 * 1024];
    let mut remaining = SOURCE_LEN;
    while remaining != 0 {
        let count = usize::try_from(remaining.min(buffer.len() as u64)).unwrap();
        file.read_exact(&mut buffer[..count])?;
        if buffer[..count].iter().any(|byte| *byte != b'S') {
            return Err(io::Error::other("DIAGNOSTIC_SOURCE_CONTENT"));
        }
        remaining -= count as u64;
    }
    if file.read(&mut buffer[..1])? != 0 || path.join("unit").try_exists()? {
        return Err(io::Error::other("DIAGNOSTIC_FRESH_FIXTURE_REQUIRED"));
    }
    Ok(())
}

#[test]
#[ignore = "requires exact independently reviewed #0218 local authored-marker plan and owning supervisor"]
fn local_namespace_diagnostic_worker() {
    let path =
        PathBuf::from(std::env::var_os("IMAGEINFO_218_ROOT").expect("explicit fixture required"));
    let unit = std::env::var("IMAGEINFO_218_UNIT").expect("explicit attempt identity required");
    assert!(
        !unit.is_empty()
            && unit.len() <= 64
            && unit
                .bytes()
                .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'_' | b'-'))
    );
    authored_fixture(&path).expect("exact fresh authored fixture required");
    run_authored_observer(
        &path,
        unit,
        "218-authored-namespace-diagnostic",
        "218-authored-v1",
    );
}

/// Run the unchanged raw #0218 protocol after the entry-specific fixture gate.
/// This function supplies no guest, volume, custody or admission authority.
pub(super) fn run_authored_observer(
    path: &Path,
    unit: String,
    operation: &'static str,
    format_revision: &'static str,
) {
    // Terminate libtest's `test ... ` prefix before the first protocol frame.
    let mut output = io::stdout();
    output.write_all(b"\n").unwrap();
    output.flush().unwrap();
    let mut backend = Observed {
        native: WindowsBackend::new(&path.join("source.bin"), &path.join("unit")),
        notices: Notices {
            unit,
            sequence: 0,
            input: input_channel(),
            output,
            failed: None,
        },
    };
    let bytes = vec![0x18; CANDIDATE_LEN];
    let mut source = Cursor::new(&bytes);
    let outcome = super::runtime::execute(
        &mut backend,
        ValidatedCandidate {
            operation,
            format_revision,
            source: &mut source,
            planned_len: bytes.len() as u64,
            max_len: bytes.len() as u64,
            output: super::runtime::ExpectedAbsent("output.bin"),
        },
        &mut LogicalBudget::new(5 * 1024 * 1024),
        &Cancellation::default(),
    );
    let runtime_notice = backend.notices.emit(
        "runtime_result",
        "runtime",
        result(&outcome),
        bindings(&backend.native),
    );
    let Observed {
        native,
        mut notices,
    } = backend;
    drop(native);
    let dropped_notice = notices.emit("backend_dropped", "backend-drop", Value::Null, json!([]));
    runtime_notice.expect("runtime capture failed; owning supervisor retains failure");
    dropped_notice.expect("drop capture failed; owning supervisor retains failure");
    assert_ne!(outcome.status, super::Status::Committed);
    assert!(
        notices.failed.is_none(),
        "diagnostic protocol refused: {:?}",
        notices.failed
    );
}

#[cfg(test)]
mod tests;
