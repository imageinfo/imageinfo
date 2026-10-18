//! Actual native invocation for the disabled, unqualified internal runtime.
//! No profile or format admission is manufactured by this adapter.

use super::runtime::{Artifact, Backend, Binding, LiveEvidence, ValidatedCandidate, execute};
use super::{Cancellation, Failure, LogicalBudget, MAX_RECORD_BYTES, Phase, UnitResult};
use imageinfo_windows_storage::{
    ExistingRoot, GuardedSource, HeldArtifact, MAX_ARTIFACT_BYTES, PrivateRoot, validate_leaf,
};
use sha2::{Digest, Sha256};
use std::{
    fs, io,
    path::{Path, PathBuf},
};

#[cfg(test)]
thread_local! {
    static LAST_NATIVE_ERROR: std::cell::RefCell<Option<(io::ErrorKind, Option<i32>)>> =
        const { std::cell::RefCell::new(None) };
}

#[cfg(test)]
pub(crate) fn take_native_error() -> Option<(io::ErrorKind, Option<i32>)> {
    LAST_NATIVE_ERROR.with(|slot| slot.borrow_mut().take())
}

fn classify(error: io::Error) -> Failure {
    #[cfg(test)]
    LAST_NATIVE_ERROR.with(|slot| {
        *slot.borrow_mut() = Some((error.kind(), error.raw_os_error()));
    });
    match error.kind() {
        io::ErrorKind::Unsupported => Failure::Unsupported,
        io::ErrorKind::AlreadyExists => Failure::Conflict,
        _ => {
            let text = error.to_string();
            if ["CONFLICT", "CHANGED", "FOREIGN", "CASE_ALIAS", "REPARSE"]
                .iter()
                .any(|v| text.contains(v))
            {
                Failure::Conflict
            } else {
                Failure::BackendIo
            }
        }
    }
}

fn custody_failure(error: super::custody::CustodyRefusal) -> Failure {
    match error {
        super::custody::CustodyRefusal::ConstructionBound => Failure::RecordTooLarge,
        _ => Failure::CallerHistory,
    }
}

fn bound(snapshot: &imageinfo_windows_storage::FileSnapshot, bytes: Option<&[u8]>) -> Binding {
    let mut facts = snapshot.binding_bytes();
    if let Some(bytes) = bytes {
        facts.extend_from_slice(&Sha256::digest(bytes));
    }
    let mut identity = snapshot.volume_serial_number.to_le_bytes().to_vec();
    identity.extend_from_slice(&snapshot.file_index.to_le_bytes());
    Binding { identity, facts }
}

/// In-process original observation helper; this grants no execution authority.
pub(super) fn binding_snapshot(
    snapshot: &imageinfo_windows_storage::FileSnapshot,
    bytes: Option<&[u8]>,
) -> Binding {
    bound(snapshot, bytes)
}

pub(super) const GROUP_MANIFEST_LEAF: &str = "group.manifest";

/// A separate group-owned object, deliberately absent from every unit record,
/// binding array, acknowledgement and caller-capture/parser shape.
struct GroupManifest {
    held: HeldArtifact,
    binding: Binding,
}

/// Caller state is independently retained in the actual original caller, never
/// imported from transaction records. It is not automatic restart authority.
#[derive(Clone)]
struct CallerCapture {
    bindings: Vec<Binding>,
    exact_records: Vec<(Artifact, Vec<u8>)>,
}

pub(crate) struct WindowsBackend {
    source_path: PathBuf,
    root_path: PathBuf,
    source: Option<GuardedSource>,
    root: Option<PrivateRoot>,
    parent_binding: Option<Binding>,
    artifacts: Vec<(Artifact, HeldArtifact)>,
    expected: Vec<Binding>,
    output: String,
    published: bool,
    release: Option<CallerCapture>,
    checked: Option<CallerCapture>,
    terminal: Option<CallerCapture>,
    live_evidence: Option<LiveEvidence>,
    failed_check: bool,
    group_source: Option<Binding>,
    group_parent: Option<ExistingRoot>,
    group_parent_binding: Option<Binding>,
    group_manifest: Option<GroupManifest>,
}

impl WindowsBackend {
    /// Borrow immutable creator observations for the bounded test-only guest
    /// collector. This constructs no custody object or action capability and
    /// performs no extra protocol check at an interruption boundary.
    #[cfg(test)]
    pub(in crate::storage) fn qualification_bindings(&self) -> &[Binding] {
        &self.expected
    }

    /// Read-only advisory for the actual selected output parent. This neither
    /// reserves storage nor replaces the runtime's later native parent guards.
    pub(crate) fn available_bytes(&self) -> Result<u64, Failure> {
        let parent = self.root_path.parent().ok_or(Failure::InvalidBinding)?;
        imageinfo_windows_storage::available_bytes(parent).map_err(classify)
    }

    pub(crate) fn new(source: &Path, root: &Path) -> Self {
        Self {
            source_path: source.into(),
            root_path: root.into(),
            source: None,
            root: None,
            parent_binding: None,
            artifacts: Vec::new(),
            expected: Vec::new(),
            output: String::new(),
            published: false,
            release: None,
            checked: None,
            terminal: None,
            live_evidence: None,
            failed_check: false,
            group_source: None,
            group_parent: None,
            group_parent_binding: None,
            group_manifest: None,
        }
    }

    /// Acquire the original group's source/containing-parent holds before any
    /// staging. On every error, already acquired handles remain in this owner.
    /// Runtime preflight subsequently consumes these same holds without reopen.
    pub(super) fn acquire_group_guard(
        &mut self,
        binding: &Binding,
        source: &Binding,
        parent: &Binding,
    ) -> Result<(), Failure> {
        if binding != source && binding != parent {
            return Err(Failure::InvalidBinding);
        }
        if binding == source {
            if self.source.is_none() {
                let held =
                    GuardedSource::open(&self.source_path, MAX_ARTIFACT_BYTES).map_err(classify)?;
                self.source = Some(held);
            }
            let held = self.source.as_mut().ok_or(Failure::InvalidBinding)?;
            let bytes = held.read_exact_bytes().map_err(classify)?;
            let actual = bound(held.snapshot(), Some(&bytes));
            self.group_source = Some(actual.clone());
            if &actual != source {
                return Err(Failure::Conflict);
            }
        }
        if binding == parent {
            if self.group_parent.is_none() {
                let path = self.root_path.parent().ok_or(Failure::InvalidBinding)?;
                self.group_parent = Some(ExistingRoot::open(path).map_err(classify)?);
            }
            let held = self.group_parent.as_ref().ok_or(Failure::InvalidBinding)?;
            held.check().map_err(classify)?;
            let actual = bound(held.snapshot(), None);
            self.group_parent_binding = Some(actual.clone());
            if &actual != parent {
                return Err(Failure::Conflict);
            }
        }
        Ok(())
    }

    pub(super) fn retain_group_manifest(&mut self, bytes: &[u8]) -> Result<Binding, Failure> {
        if bytes.is_empty()
            || bytes.len() as u64 > MAX_RECORD_BYTES
            || self.group_manifest.is_some()
            || self.release.is_some()
            || self.published
            || self.group_parent.is_none()
        {
            return Err(Failure::InvalidBinding);
        }
        // The group charged this exact bounded object once before constructors.
        // Never reserve it through either unit's already charged ledger.
        let held = self
            .root()?
            .create_artifact(GROUP_MANIFEST_LEAF, bytes, MAX_RECORD_BYTES)
            .map_err(classify)?;
        let binding = bound(held.snapshot(), Some(bytes));
        self.group_manifest = Some(GroupManifest {
            held,
            binding: binding.clone(),
        });
        // Store ownership before any fallible flush/check, retaining the exact
        // handle and binding if any later operation fails or is cancelled.
        self.group_manifest
            .as_ref()
            .unwrap()
            .held
            .flush()
            .map_err(classify)?;
        self.root()?.flush().map_err(classify)?;
        self.check_group_manifest(&binding, bytes)?;
        Ok(binding)
    }

    pub(super) fn group_manifest_binding(&self) -> Option<&Binding> {
        self.group_manifest.as_ref().map(|m| &m.binding)
    }

    /// Exact known native unit objects, excluding the separately owned manifest.
    pub(super) fn retained_bindings(&self) -> Vec<Binding> {
        let mut values = self.expected.clone();
        if let Some(source) = &self.group_source
            && !values.iter().any(|old| old.identity == source.identity)
        {
            values.insert(0, source.clone());
        }
        values
    }

    pub(super) fn check_group_manifest(
        &mut self,
        binding: &Binding,
        bytes: &[u8],
    ) -> Result<(), Failure> {
        let root = self.root.as_ref().ok_or(Failure::InvalidBinding)?;
        let manifest = self
            .group_manifest
            .as_mut()
            .ok_or(Failure::InvalidBinding)?;
        if &manifest.binding != binding || manifest.held.bytes() != bytes {
            return Err(Failure::Conflict);
        }
        manifest.held.check(root).map_err(classify)?;
        let expected = self.expected.clone();
        self.check(Phase::IntentChecked, &expected)
    }

    /// Retain actual creator provenance independently from editable records.
    pub(crate) fn finalization_prior(
        &mut self,
        operation: &str,
    ) -> Result<super::finalization::PriorProof, Failure> {
        if self.failed_check {
            return Err(Failure::CallerHistory);
        }
        let current = self.custody_snapshot(operation)?;
        let evidence = self.live_evidence.as_ref().ok_or(Failure::CallerHistory)?;
        super::finalization::PriorProof::from_actual(current, evidence.clone())
    }

    fn remember(&mut self, binding: Binding) -> Binding {
        self.expected.push(binding.clone());
        binding
    }

    fn capture(&self, bindings: &[Binding]) -> Result<CallerCapture, Failure> {
        if bindings != self.expected {
            return Err(Failure::CallerHistory);
        }
        // Count before cloning: every actual caller capture has its own 64 KiB
        // ceiling inside the precharged four-capture construction allowance.
        let mut size = 256u64;
        for binding in bindings {
            size = size
                .checked_add(binding.identity.len() as u64)
                .and_then(|n| n.checked_add(binding.facts.len() as u64))
                .and_then(|n| n.checked_add(16))
                .ok_or(Failure::LengthOverflow)?;
        }
        for (kind, artifact) in &self.artifacts {
            if *kind != Artifact::Candidate {
                size = size
                    .checked_add(artifact.bytes().len() as u64)
                    .and_then(|n| n.checked_add(16))
                    .ok_or(Failure::LengthOverflow)?;
            }
        }
        if size > MAX_RECORD_BYTES {
            return Err(Failure::RecordTooLarge);
        }
        let exact_records = self
            .artifacts
            .iter()
            .filter(|(kind, _)| *kind != Artifact::Candidate)
            .map(|(kind, artifact)| (*kind, artifact.bytes().to_vec()))
            .collect();
        Ok(CallerCapture {
            bindings: bindings.to_vec(),
            exact_records,
        })
    }

    fn same_capture(&self, capture: &CallerCapture, prefix: bool) -> bool {
        (if prefix {
            self.expected.starts_with(&capture.bindings)
        } else {
            self.expected == capture.bindings
        }) && capture.exact_records.iter().all(|(kind, bytes)| {
            self.artifacts
                .iter()
                .any(|(now_kind, artifact)| kind == now_kind && bytes == artifact.bytes())
        })
    }

    fn root(&self) -> Result<&PrivateRoot, Failure> {
        self.root.as_ref().ok_or(Failure::InvalidBinding)
    }

    /// Read-only observation for an explicitly trusted caller. Parsing or
    /// obtaining this snapshot supplies no recovery-action authority.
    pub(crate) fn custody_snapshot(
        &mut self,
        operation: &str,
    ) -> Result<super::custody::CurrentBindings, Failure> {
        let records: Vec<_> = self
            .artifacts
            .iter()
            .filter(|(kind, _)| *kind != Artifact::Candidate)
            .map(|(kind, artifact)| (*kind, artifact.bytes()))
            .collect();
        let parent = self
            .parent_binding
            .as_ref()
            .ok_or(Failure::InvalidBinding)?;
        // Check the whole exact construction using borrowed views before any
        // record-content or binding clone. The original held parent observation
        // was captured with root creation, not reconstructed for this snapshot.
        super::custody::CurrentBindings::preflight_borrowed(
            operation,
            self.profile(),
            self.implementation(),
            &self.output,
            parent,
            &self.expected,
            &records,
            self.published,
        )
        .map_err(custody_failure)?;
        let expected = self.expected.clone();
        self.check(Phase::InstalledRechecked, &expected)?;
        let records: Vec<_> = self
            .artifacts
            .iter()
            .filter(|(kind, _)| *kind != Artifact::Candidate)
            .map(|(kind, artifact)| (*kind, artifact.bytes()))
            .collect();
        let parent = self
            .parent_binding
            .as_ref()
            .ok_or(Failure::InvalidBinding)?;
        super::custody::CurrentBindings::capture_borrowed(
            operation,
            self.profile(),
            self.implementation(),
            &self.output,
            parent,
            &expected,
            &records,
            self.published,
        )
        .map_err(custody_failure)
    }
}

impl Backend for WindowsBackend {
    fn profile(&self) -> &'static str {
        "windows-ntfs-unqualified-internal-v1"
    }
    fn implementation(&self) -> &'static str {
        concat!("imageinfo-storage-live-ack-v1-", env!("CARGO_PKG_VERSION"))
    }

    fn preflight(&mut self, output: &str) -> Result<Binding, Failure> {
        validate_leaf(output).map_err(classify)?;
        let grouped = self.group_source.is_some() && self.group_parent.is_some();
        if (self.source.is_some() && !grouped)
            || !self.expected.is_empty()
            || self.root.is_some()
            || self.root_path.try_exists().map_err(classify)?
        {
            return Err(Failure::Conflict);
        }
        if grouped {
            if output.eq_ignore_ascii_case(GROUP_MANIFEST_LEAF) {
                return Err(Failure::Conflict);
            }
            self.group_parent
                .as_ref()
                .unwrap()
                .check()
                .map_err(classify)?;
            let source = self.source.as_mut().ok_or(Failure::InvalidBinding)?;
            let bytes = source.read_exact_bytes().map_err(classify)?;
            let binding = bound(source.snapshot(), Some(&bytes));
            if self.group_source.as_ref() != Some(&binding) {
                return Err(Failure::Conflict);
            }
            self.output = output.into();
            return Ok(self.remember(binding));
        }
        self.output = output.into();
        let mut source =
            GuardedSource::open(&self.source_path, MAX_ARTIFACT_BYTES).map_err(classify)?;
        let bytes = source.read_exact_bytes().map_err(classify)?;
        let binding = bound(source.snapshot(), Some(&bytes));
        self.source = Some(source);
        Ok(self.remember(binding))
    }

    fn create_root(&mut self) -> Result<Binding, Failure> {
        if self.root.is_some() {
            return Err(Failure::InvalidBinding);
        }
        if let Some(parent) = &self.group_parent {
            parent.check().map_err(classify)?;
        }
        let root = PrivateRoot::create(&self.root_path).map_err(classify)?;
        let mut binding = bound(root.snapshot(), None);
        let parent_binding = bound(root.parent_snapshot(), None);
        // Bind the actual held writable containing directory separately inside
        // the root facts. Its mutable directory size/write time is historical;
        // the live SDK guard continues checking its actual namespace identity.
        binding
            .facts
            .extend_from_slice(b"held-containing-parent-v1\0");
        binding.facts.extend_from_slice(&parent_binding.facts);
        self.parent_binding = Some(parent_binding);
        self.root = Some(root);
        let binding = self.remember(binding);
        if let Some(parent) = &self.group_parent {
            parent.check().map_err(classify)?;
            if self.group_parent_binding.as_ref().map(|b| &b.identity)
                != self.parent_binding.as_ref().map(|b| &b.identity)
            {
                return Err(Failure::Conflict);
            }
        }
        Ok(binding)
    }

    fn create(&mut self, artifact: Artifact, bytes: &[u8]) -> Result<Binding, Failure> {
        if self.artifacts.iter().any(|(kind, _)| *kind == artifact) {
            return Err(Failure::Conflict);
        }
        let max = if artifact == Artifact::Candidate {
            MAX_ARTIFACT_BYTES
        } else {
            MAX_RECORD_BYTES
        };
        let held = self
            .root()?
            .create_artifact(artifact.leaf(), bytes, max)
            .map_err(classify)?;
        let binding = bound(held.snapshot(), Some(bytes));
        self.artifacts.push((artifact, held));
        Ok(self.remember(binding))
    }

    fn check(&mut self, phase: Phase, bindings: &[Binding]) -> Result<(), Failure> {
        if bindings != self.expected {
            return Err(Failure::InvalidBinding);
        }
        self.source
            .as_mut()
            .ok_or(Failure::InvalidBinding)?
            .check()
            .map_err(classify)?;
        if let Some(parent) = &self.group_parent {
            parent.check().map_err(classify)?;
        }
        let root = self.root.as_ref().ok_or(Failure::InvalidBinding)?;
        root.check().map_err(classify)?;
        for (_, artifact) in &mut self.artifacts {
            artifact.check(root).map_err(classify)?;
        }
        if let Some(manifest) = &mut self.group_manifest {
            manifest.held.check(root).map_err(classify)?;
        }
        // Exact bounded namespace, with no foreign entries or case aliases. No
        // path reopening for mutation and no attempt to remove unexpected names.
        let mut actual = Vec::new();
        for entry in fs::read_dir(root.path()).map_err(classify)?.take(7) {
            actual.push(entry.map_err(classify)?.file_name());
        }
        let mut expected: Vec<std::ffi::OsString> = self
            .artifacts
            .iter()
            .map(|(kind, _)| {
                if *kind == Artifact::Candidate && self.published {
                    self.output.clone().into()
                } else {
                    kind.leaf().into()
                }
            })
            .collect();
        // One optional exact slot, enabled only by its held native object. The
        // unit's five-artifact bound and every record/capture shape stay fixed.
        if self.group_manifest.is_some() {
            expected.push(GROUP_MANIFEST_LEAF.into());
        }
        actual.sort();
        expected.sort();
        if actual != expected {
            return Err(Failure::Conflict);
        }
        if matches!(phase, Phase::Prepublication | Phase::Final)
            && !self
                .release
                .as_ref()
                .is_some_and(|c| self.same_capture(c, true))
        {
            return Err(Failure::CallerHistory);
        }
        if phase == Phase::Final
            && !self
                .checked
                .as_ref()
                .is_some_and(|c| self.same_capture(c, false))
        {
            return Err(Failure::CallerHistory);
        }
        Ok(())
    }

    fn flush_file(&mut self, artifact: Artifact) -> Result<(), Failure> {
        self.artifacts
            .iter()
            .find(|(kind, _)| *kind == artifact)
            .ok_or(Failure::InvalidBinding)?
            .1
            .flush()
            .map_err(classify)
    }
    fn flush_root(&mut self) -> Result<(), Failure> {
        self.root()?.flush().map_err(classify)
    }
    fn flush_parent(&mut self) -> Result<(), Failure> {
        self.root()?.flush_parent().map_err(classify)
    }

    fn publish(&mut self, output: &str) -> Result<(), Failure> {
        if output != self.output || self.published {
            return Err(Failure::InvalidBinding);
        }
        let root = self.root.as_ref().ok_or(Failure::InvalidBinding)?;
        let candidate = &mut self
            .artifacts
            .iter_mut()
            .find(|(kind, _)| *kind == Artifact::Candidate)
            .ok_or(Failure::InvalidBinding)?
            .1;
        candidate
            .publish_no_replace(root, output)
            .map_err(|_| Failure::Ambiguous)?;
        self.published = true;
        Ok(())
    }

    fn caller_release(&mut self, bindings: &[Binding]) -> Result<(), Failure> {
        if self.release.is_some() {
            return Err(Failure::CallerHistory);
        }
        self.release = Some(self.capture(bindings)?);
        Ok(())
    }
    fn checked_context(&mut self, bindings: &[Binding]) -> Result<(), Failure> {
        if !self
            .release
            .as_ref()
            .is_some_and(|c| self.same_capture(c, true))
        {
            return Err(Failure::CallerHistory);
        }
        self.checked = Some(self.capture(bindings)?);
        Ok(())
    }
    fn export_terminal(&mut self, bindings: &[Binding]) -> Result<(), Failure> {
        if !self
            .checked
            .as_ref()
            .is_some_and(|c| self.same_capture(c, false))
        {
            return Err(Failure::CallerHistory);
        }
        self.terminal = Some(self.capture(bindings)?);
        Ok(())
    }
    fn retain_outcome(&mut self, phase: Phase, failure: Option<Failure>) {
        if failure.is_some_and(|failure| failure != Failure::Cancelled)
            && matches!(
                phase,
                Phase::CandidateChecked
                    | Phase::PreparedChecked
                    | Phase::IntentChecked
                    | Phase::Prepublication
                    | Phase::Installed
                    | Phase::InstalledRechecked
                    | Phase::ObservationChecked
                    | Phase::ReceiptChecked
                    | Phase::ReceiptFileChecked
                    | Phase::ReceiptParentChecked
                    | Phase::CheckedContext
                    | Phase::Final
                    | Phase::TerminalExport
            )
        {
            self.failed_check = true;
        }
    }
    fn retain_live_evidence(&mut self, evidence: &LiveEvidence) {
        self.live_evidence = Some(evidence.clone());
    }
}

/// Internal caller seam for a later admitted format layer. The validation token
/// is crate-private and is consumed without serializing/importing permission.
pub(crate) fn run(
    backend: &mut WindowsBackend,
    candidate: ValidatedCandidate<'_>,
    budget: &mut LogicalBudget,
    cancel: &Cancellation,
) -> UnitResult {
    execute(backend, candidate, budget, cancel)
}

#[cfg(test)]
mod live_ack_tests;

#[cfg(test)]
mod tests {
    use super::*;
    use crate::storage::runtime::ExpectedAbsent;
    use std::io::Cursor;
    use std::time::{SystemTime, UNIX_EPOCH};

    #[test]
    fn sdk_policy_refusals_preserve_distinct_io_and_conflict_facts() {
        for label in [
            "UNSUPPORTED_LEAF",
            "SOURCE_BOUND",
            "UNSUPPORTED_FILE_PROPERTY",
            "NONDEFAULT_STREAM",
            "LOCAL_FIXED_NTFS_REQUIRED",
        ] {
            assert_eq!(
                classify(io::Error::new(io::ErrorKind::Unsupported, label)),
                Failure::Unsupported
            );
        }
        assert_eq!(
            classify(io::Error::from(io::ErrorKind::PermissionDenied)),
            Failure::BackendIo
        );
        assert_eq!(
            classify(io::Error::other("SOURCE_PROPERTY_OR_BYTE_CONFLICT")),
            Failure::Conflict
        );
        assert_eq!(
            classify(io::Error::other("unrecognized failure")),
            Failure::BackendIo
        );
    }

    #[test]
    fn native_reserved_output_leaf_refuses_before_source_or_target_effects() {
        let workspace = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        let absent = workspace
            .join(".local")
            .join("storage-runtime-tests")
            .join(format!(
                "reserved-{}-{}",
                std::process::id(),
                SystemTime::now()
                    .duration_since(UNIX_EPOCH)
                    .unwrap()
                    .as_nanos()
            ));
        let root = absent.join("unit");
        let mut backend = WindowsBackend::new(&absent.join("no-source.bin"), &root);
        let mut bytes = Cursor::new(b"a".as_slice());
        let request = ValidatedCandidate {
            operation: "authored-invalid-leaf",
            format_revision: "authored-test-v1",
            source: &mut bytes,
            planned_len: 1,
            max_len: 1,
            output: ExpectedAbsent("CON"),
        };
        let result = run(
            &mut backend,
            request,
            &mut LogicalBudget::new(1_000_000),
            &Cancellation::default(),
        );
        assert_eq!(result.status, super::super::Status::Refused);
        assert_eq!(result.failure, Some(Failure::Unsupported));
        assert_eq!(result.phase, Phase::Preflight);
        assert!(!result.publication_possible);
        assert!(!result.release_possible);
        assert!(!result.retained_material);
        assert!(backend.source.is_none() && backend.root.is_none());
        assert!(!absent.exists());
    }

    #[test]
    fn native_source_size_policy_refuses_before_target_effects() {
        let workspace = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        let evidence = workspace
            .join(".local")
            .join("storage-runtime-tests")
            .join(format!(
                "source-bound-{}-{}",
                std::process::id(),
                SystemTime::now()
                    .duration_since(UNIX_EPOCH)
                    .unwrap()
                    .as_nanos()
            ));
        fs::create_dir_all(&evidence).unwrap();
        let source = evidence.join("source.bin");
        let fixture = fs::OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&source)
            .unwrap();
        fixture.set_len(MAX_ARTIFACT_BYTES + 1).unwrap();
        drop(fixture);
        let root = evidence.join("unit");
        let mut backend = WindowsBackend::new(&source, &root);
        let mut bytes = Cursor::new(b"a".as_slice());
        let request = ValidatedCandidate {
            operation: "authored-overlimit-source",
            format_revision: "authored-test-v1",
            source: &mut bytes,
            planned_len: 1,
            max_len: 1,
            output: ExpectedAbsent("output.bin"),
        };
        let result = run(
            &mut backend,
            request,
            &mut LogicalBudget::new(1_000_000),
            &Cancellation::default(),
        );
        fs::write(
            evidence.join("outcome.private.txt"),
            format!("{result:?}\n"),
        )
        .unwrap();
        assert_eq!(result.status, super::super::Status::Refused);
        assert_eq!(result.failure, Some(Failure::Unsupported));
        assert_eq!(result.phase, Phase::Preflight);
        assert!(!result.publication_possible);
        assert!(!result.release_possible);
        assert!(!result.retained_material);
        assert!(!root.exists());
        assert_eq!(fs::metadata(source).unwrap().len(), MAX_ARTIFACT_BYTES + 1);
    }

    #[test]
    fn actual_native_adapter_calls_protocol_and_retains_source_and_artifacts() {
        let workspace = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        let evidence = workspace
            .join(".local")
            .join("storage-runtime-tests")
            .join(format!(
                "{}-{}",
                std::process::id(),
                SystemTime::now()
                    .duration_since(UNIX_EPOCH)
                    .unwrap()
                    .as_nanos()
            ));
        fs::create_dir_all(&evidence).unwrap();
        let source = evidence.join("source.bin");
        fs::write(&source, b"authored original").unwrap();
        let root = evidence.join("unit");
        let mut backend = WindowsBackend::new(&source, &root);
        let mut bytes = Cursor::new(b"authored derivative".as_slice());
        let candidate = ValidatedCandidate {
            operation: "authored-native-unit",
            format_revision: "authored-test-v1",
            source: &mut bytes,
            planned_len: 19,
            max_len: MAX_ARTIFACT_BYTES,
            output: ExpectedAbsent("output.bin"),
        };
        let result = run(
            &mut backend,
            candidate,
            &mut LogicalBudget::new(1_000_000),
            &Cancellation::default(),
        );
        assert_eq!(fs::read(&source).unwrap(), b"authored original");
        assert_ne!(result.status, super::super::Status::Committed);
        assert_eq!(result.charged_bytes, 19 + 8 * MAX_RECORD_BYTES);
        // Record failures before asserting: a refusal is never skipped into a
        // positive native completion observation for this authored fixture.
        fs::write(
            evidence.join("outcome.private.txt"),
            format!("{result:?}\n"),
        )
        .unwrap();
        assert!(
            result.protocol_complete,
            "native runtime stopped at {:?}: {:?}",
            result.phase, result.failure
        );
        assert!(backend.terminal.is_some());
        assert_eq!(
            fs::read(root.join("output.bin")).unwrap(),
            b"authored derivative"
        );
    }
}
