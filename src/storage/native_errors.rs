//! Explicitly selected disposable-guest controller for actual native I/O errors.
//! This test never returns an injected protocol failure or admits a profile.

use super::runtime::{Artifact, Backend, Binding, LiveEvidence, ValidatedCandidate};
use super::windows::WindowsBackend;
use super::{Cancellation, Failure, LogicalBudget, Phase};
use std::io::{self, BufRead, Cursor, Write};
use std::path::PathBuf;

struct Observed {
    native: WindowsBackend,
    sequence: usize,
}

fn emit(value: serde_json::Value) {
    println!("IMAGEINFO174 {}", value);
    io::stdout().flush().unwrap();
}

impl Observed {
    fn call<T>(
        &mut self,
        label: String,
        operation: impl FnOnce(&mut WindowsBackend) -> Result<T, Failure>,
    ) -> Result<T, Failure> {
        self.sequence += 1;
        emit(serde_json::json!({"barrier": label, "sequence": self.sequence}));
        let mut line = String::new();
        io::stdin().lock().read_line(&mut line).unwrap();
        assert_eq!(line.trim_end(), "continue", "Only continuation is accepted");
        let _ = super::windows::take_native_error();
        let result = operation(&mut self.native);
        let native = super::windows::take_native_error();
        emit(
            serde_json::json!({"operation": label, "sequence": self.sequence,
            "success": result.is_ok(), "failure": result.as_ref().err().map(|e| format!("{e:?}")),
            "nativeErrorKind": native.map(|(kind, _)| format!("{kind:?}")),
            "nativeOsError": native.and_then(|(_, code)| code)}),
        );
        result
    }
}

impl Backend for Observed {
    fn profile(&self) -> &'static str {
        self.native.profile()
    }
    fn implementation(&self) -> &'static str {
        self.native.implementation()
    }
    fn preflight(&mut self, output: &str) -> Result<Binding, Failure> {
        self.call("preflight".into(), |b| b.preflight(output))
    }
    fn create_root(&mut self) -> Result<Binding, Failure> {
        self.call("create-root".into(), Backend::create_root)
    }
    fn create(&mut self, kind: Artifact, bytes: &[u8]) -> Result<Binding, Failure> {
        self.call(format!("create-{kind:?}"), |b| b.create(kind, bytes))
    }
    fn check(&mut self, phase: Phase, bindings: &[Binding]) -> Result<(), Failure> {
        self.call(format!("check-{phase:?}"), |b| b.check(phase, bindings))
    }
    fn flush_file(&mut self, kind: Artifact) -> Result<(), Failure> {
        self.call(format!("file-{kind:?}"), |b| b.flush_file(kind))
    }
    fn flush_root(&mut self) -> Result<(), Failure> {
        self.call("root-flush".into(), Backend::flush_root)
    }
    fn flush_parent(&mut self) -> Result<(), Failure> {
        self.call("parent-flush".into(), Backend::flush_parent)
    }
    fn publish(&mut self, output: &str) -> Result<(), Failure> {
        self.call("publish".into(), |b| b.publish(output))
    }
    fn caller_release(&mut self, bindings: &[Binding]) -> Result<(), Failure> {
        self.call("release".into(), |b| b.caller_release(bindings))
    }
    fn checked_context(&mut self, bindings: &[Binding]) -> Result<(), Failure> {
        self.call("checked-context".into(), |b| b.checked_context(bindings))
    }
    fn export_terminal(&mut self, bindings: &[Binding]) -> Result<(), Failure> {
        self.call("terminal".into(), |b| b.export_terminal(bindings))
    }
    fn retain_live_evidence(&mut self, evidence: &LiveEvidence) {
        emit(
            serde_json::json!({"acknowledgements": evidence.acknowledgements.iter()
            .map(|ack| format!("{:?}", ack.phase)).collect::<Vec<_>>()}),
        );
        self.native.retain_live_evidence(evidence);
    }
}

#[test]
#[ignore = "requires the explicitly prepared disposable #0174 guest fixture"]
fn guest_native_error_worker() {
    let path =
        PathBuf::from(std::env::var_os("IMAGEINFO_174_ROOT").expect("explicit fixture required"));
    let drive = path
        .components()
        .next()
        .unwrap()
        .as_os_str()
        .to_string_lossy();
    assert!(drive.ends_with(':') && !drive.eq_ignore_ascii_case("C:"));
    assert_eq!(
        std::fs::read(path.parent().unwrap().join("fixture174.marker")).unwrap(),
        b"imageinfo-0174-disposable-authored-only-v1\n"
    );
    assert!(path.join("source.bin").is_file());
    assert!(!path.join("unit").exists());
    let mut backend = Observed {
        native: WindowsBackend::new(&path.join("source.bin"), &path.join("unit")),
        sequence: 0,
    };
    let bytes = vec![0x74; 4 * 1024 * 1024];
    let mut source = Cursor::new(&bytes);
    let result = super::runtime::execute(
        &mut backend,
        ValidatedCandidate {
            operation: "174-authored-native-errors",
            format_revision: "174-authored-v1",
            source: &mut source,
            planned_len: bytes.len() as u64,
            max_len: bytes.len() as u64,
            output: super::runtime::ExpectedAbsent("output.bin"),
        },
        &mut LogicalBudget::new(5 * 1024 * 1024),
        &Cancellation::default(),
    );
    emit(
        serde_json::json!({"terminal": true, "status": format!("{:?}", result.status),
        "phase": format!("{:?}", result.phase), "failure": result.failure.map(|e| format!("{e:?}")),
        "publicationPossible": result.publication_possible, "releasePossible": result.release_possible,
        "retainedMaterial": result.retained_material, "pendingCleanup": result.pending_cleanup,
        "chargedBytes": result.charged_bytes, "protocolComplete": result.protocol_complete,
        "committed": false, "productionProfileAdmitted": false, "rawAdmission": false,
        "ownedHandlesRemoved": 0}),
    );
    assert_ne!(result.status, super::Status::Committed);
}
