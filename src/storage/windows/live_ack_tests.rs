//! Actual authored-byte native schedules. Injected failures are controller
//! responses around real calls, not claims of actual device failure.
use super::*;
use crate::storage::Status;
use crate::storage::runtime::{TestAdmission, execute_test_admitted};
use std::io::Cursor;
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{SystemTime, UNIX_EPOCH};

static NEXT: AtomicU64 = AtomicU64::new(0);
const ORIGINAL: &[u8] = b"168 authored protected original";
const DERIVATIVE: &[u8] = b"168 authored complete derivative";

#[derive(Clone, Copy, Debug)]
enum Timing {
    Before,
    After,
}

struct Joined<'a> {
    native: WindowsBackend,
    calls: usize,
    fail: Option<(usize, Timing, Failure)>,
    cancel: Option<(&'a Cancellation, usize)>,
    collision: bool,
    property: bool,
    labels: Vec<String>,
}

impl Joined<'_> {
    fn call<T>(
        &mut self,
        label: String,
        operation: impl FnOnce(&mut WindowsBackend) -> Result<T, Failure>,
    ) -> Result<T, Failure> {
        self.calls += 1;
        self.labels.push(label.clone());
        if let Some((at, Timing::Before, failure)) = self.fail
            && at == self.calls
        {
            return Err(failure);
        }
        if self.collision && label == "publish" {
            fs::write(self.native.root_path.join("output.bin"), b"foreign winner").unwrap();
        }
        if self.property && label == "check-Installed" {
            let path = self.native.root_path.join("output.bin");
            let mut permissions = fs::metadata(&path).unwrap().permissions();
            permissions.set_readonly(true);
            fs::set_permissions(path, permissions).unwrap();
        }
        let result = operation(&mut self.native)?;
        if let Some((cancel, at)) = self.cancel
            && at == self.calls
        {
            cancel.request();
        }
        if let Some((at, Timing::After, failure)) = self.fail
            && at == self.calls
        {
            return Err(failure);
        }
        Ok(result)
    }
}

impl Backend for Joined<'_> {
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
        self.native.retain_live_evidence(evidence);
    }
}

fn fixture<'a>(label: &str) -> (PathBuf, Joined<'a>) {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join(".local")
        .join("work-wave-20261016e")
        .join(format!(
            "168-native-{}-{}-{}-{label}",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
    fs::create_dir_all(&path).unwrap();
    fs::write(path.join("source.bin"), ORIGINAL).unwrap();
    let backend = Joined {
        native: WindowsBackend::new(&path.join("source.bin"), &path.join("unit")),
        calls: 0,
        fail: None,
        cancel: None,
        collision: false,
        property: false,
        labels: Vec::new(),
    };
    (path, backend)
}

fn execute_joined(backend: &mut Joined<'_>, cancel: &Cancellation) -> UnitResult {
    let admission = TestAdmission::exact(backend);
    let mut reader = Cursor::new(DERIVATIVE);
    execute_test_admitted(
        backend,
        ValidatedCandidate {
            operation: "168-authored-native",
            format_revision: "168-authored-v1",
            source: &mut reader,
            planned_len: DERIVATIVE.len() as u64,
            max_len: MAX_ARTIFACT_BYTES,
            output: super::super::runtime::ExpectedAbsent("output.bin"),
        },
        &mut LogicalBudget::new(1_000_000),
        cancel,
        admission,
    )
}

/// Gather immutable creator facts, close every guard, then independently reopen
/// actual names and compare exact identities, complete bytes and properties.
fn audit(path: &Path, backend: Joined<'_>, result: &UnitResult, property_conflict: bool) {
    let mut expected = Vec::new();
    for (kind, held) in &backend.native.artifacts {
        let leaf = if *kind == Artifact::Candidate && backend.native.published {
            "output.bin"
        } else {
            kind.leaf()
        };
        expected.push((
            leaf.to_string(),
            held.snapshot().clone(),
            held.bytes().to_vec(),
        ));
    }
    let source_before = backend.native.source.as_ref().map(|s| s.snapshot().clone());
    let root_identity = backend
        .native
        .root
        .as_ref()
        .map(|root| same_file::Handle::from_path(root.path()).unwrap());
    let evidence = backend.native.live_evidence.clone().unwrap();
    assert_eq!(
        evidence.acknowledgements.len(),
        if result.protocol_complete || result.failure == Some(Failure::Cancelled) {
            backend.calls
        } else {
            backend.calls.saturating_sub(1)
        }
    );
    let labels = backend.labels.clone();
    let collision = backend.collision;
    drop(backend);
    let mut source = GuardedSource::open(&path.join("source.bin"), MAX_ARTIFACT_BYTES).unwrap();
    assert_eq!(source.read_exact_bytes().unwrap(), ORIGINAL);
    if let Some(before) = source_before {
        assert_eq!(*source.snapshot(), before);
    }
    let mut manifest = format!("{result:?}\nlabels={labels:?}\n{evidence:?}\n");
    let mut names = Vec::new();
    for (leaf, before, bytes) in expected {
        let mut reopened =
            GuardedSource::open(&path.join("unit").join(&leaf), MAX_ARTIFACT_BYTES).unwrap();
        assert_eq!(reopened.read_exact_bytes().unwrap(), bytes);
        if property_conflict && leaf == "output.bin" {
            let mut changed = before.clone();
            changed.attributes |= 1; // FILE_ATTRIBUTE_READONLY, actual actor above.
            assert_eq!(*reopened.snapshot(), changed);
        } else {
            assert_eq!(*reopened.snapshot(), before);
        }
        manifest.push_str(&format!(
            "audited {leaf} {before:?} sha256={:x}\n",
            Sha256::digest(&bytes)
        ));
        names.push(std::ffi::OsString::from(leaf));
    }
    if collision {
        assert_eq!(
            fs::read(path.join("unit/output.bin")).unwrap(),
            b"foreign winner"
        );
        names.push("output.bin".into());
    }
    if path.join("unit").exists() {
        assert_eq!(
            root_identity.unwrap(),
            same_file::Handle::from_path(path.join("unit")).unwrap()
        );
        let mut actual: Vec<_> = fs::read_dir(path.join("unit"))
            .unwrap()
            .map(|v| v.unwrap().file_name())
            .collect();
        names.sort();
        actual.sort();
        assert_eq!(actual, names);
    }
    fs::write(path.join("audit.private.txt"), manifest).unwrap();
}

#[test]
fn native_live_ack_complete_and_ordinary_owner_edit_after_release() {
    let (path, mut backend) = fixture("complete");
    let result = execute_joined(&mut backend, &Cancellation::default());
    assert_eq!(result.status, Status::Committed, "{result:?}");
    assert!(result.protocol_complete);
    let evidence = backend.native.live_evidence.as_ref().unwrap();
    assert!(evidence.complete(&backend.native.expected));
    assert!(
        backend
            .native
            .custody_snapshot("168-authored-native")
            .is_ok()
    );
    let receipt = backend
        .native
        .artifacts
        .iter()
        .find(|(kind, _)| *kind == Artifact::Receipt)
        .unwrap()
        .1
        .bytes();
    let receipt_text = String::from_utf8_lossy(receipt);
    assert!(!receipt_text.contains("ReceiptFlushed"));
    assert!(!receipt_text.contains("TerminalExport"));
    audit(&path, backend, &result, false);
    fs::write(path.join("unit/output.bin"), b"ordinary owner edit").unwrap();
    assert_eq!(
        fs::read(path.join("unit/output.bin")).unwrap(),
        b"ordinary owner edit"
    );
    assert_eq!(fs::read(path.join("source.bin")).unwrap(), ORIGINAL);
}

#[test]
fn native_every_phase_before_after_reported_errors_and_lost_responses() {
    let (base, mut baseline) = fixture("baseline");
    let success = execute_joined(&mut baseline, &Cancellation::default());
    assert_eq!(success.status, Status::Committed, "{success:?}");
    let calls = baseline.calls;
    let publish = baseline.labels.iter().position(|s| s == "publish").unwrap() + 1;
    audit(&base, baseline, &success, false);
    for timing in [Timing::Before, Timing::After] {
        for failure in [Failure::BackendIo, Failure::Ambiguous] {
            for at in 1..=calls {
                let (path, mut backend) = fixture(&format!("{timing:?}-{failure:?}-{at}"));
                backend.fail = Some((at, timing, failure));
                let result = execute_joined(&mut backend, &Cancellation::default());
                assert_eq!(backend.calls, at);
                assert_eq!(result.failure, Some(failure));
                assert!(!result.protocol_complete);
                assert_eq!(result.publication_possible, at >= publish);
                if at >= publish {
                    assert_eq!(result.status, Status::RecoveryRequired);
                }
                audit(&path, backend, &result, false);
            }
        }
    }
}

#[test]
fn native_collision_property_and_cancellation_keep_truthful_artifacts() {
    for property in [false, true] {
        let (path, mut backend) = fixture(if property { "property" } else { "collision" });
        backend.property = property;
        backend.collision = !property;
        let result = execute_joined(&mut backend, &Cancellation::default());
        assert_eq!(result.status, Status::RecoveryRequired, "{result:?}");
        assert_eq!(
            result.failure,
            Some(if property {
                Failure::Conflict
            } else {
                Failure::Ambiguous
            })
        );
        audit(&path, backend, &result, property);
    }
    let (base, mut baseline) = fixture("cancel-baseline");
    let success = execute_joined(&mut baseline, &Cancellation::default());
    let calls = baseline.calls;
    let publish = baseline.labels.iter().position(|s| s == "publish").unwrap() + 1;
    audit(&base, baseline, &success, false);
    for at in 1..calls {
        let (path, mut backend) = fixture(&format!("cancel-{at}"));
        let cancel = Cancellation::default();
        backend.cancel = Some((&cancel, at));
        let result = execute_joined(&mut backend, &cancel);
        assert_eq!(result.failure, Some(Failure::Cancelled));
        assert_eq!(backend.calls, at);
        assert_eq!(
            result.status,
            if at >= publish {
                Status::RecoveryRequired
            } else {
                Status::CancelledBeforePublish
            }
        );
        audit(&path, backend, &result, false);
    }
}

#[test]
fn native_unchanged_caller_bypasses_protocol_without_budget_or_namespace_effects() {
    let (path, mut backend) = fixture("noop-bypass");
    let mut budget = LogicalBudget::new(1_000_000);
    // The format/caller resolves a proven no-op before constructing the internal
    // publication request. No storage no-op inference from equal bytes exists.
    let result = crate::storage::runtime::execute_resolved(
        &mut backend,
        None,
        &mut budget,
        &Cancellation::default(),
    );
    assert_eq!(result.status, Status::Unchanged);
    assert_eq!(backend.calls, 0);
    assert_eq!(budget.charged(), 0);
    assert!(!path.join("unit").exists());
    assert_eq!(fs::read(path.join("source.bin")).unwrap(), ORIGINAL);
    fs::write(
        path.join("outcome.private.txt"),
        "caller Unchanged; executor not invoked\n",
    )
    .unwrap();
}
