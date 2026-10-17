use super::*;
use crate::storage::custody::{CurrentCallerHistory, TrustedCurrentCaller};
use crate::storage::inspection::{InspectionSpec, ORDER};
use crate::storage::runtime::{Backend, ExpectedAbsent, LiveEvidence, ValidatedCandidate, execute};
use crate::storage::windows::WindowsBackend;
use crate::storage::{LogicalBudget, Phase};
use std::os::windows::fs::OpenOptionsExt;
use std::{
    fs,
    io::Cursor,
    path::PathBuf,
    time::{SystemTime, UNIX_EPOCH},
};

const SOURCE: &[u8] = b"172 protected original";
const OUTPUT: &[u8] = b"172 derivative";
struct Stop {
    backend: WindowsBackend,
    at: Phase,
}
impl Backend for Stop {
    fn profile(&self) -> &'static str {
        self.backend.profile()
    }
    fn implementation(&self) -> &'static str {
        self.backend.implementation()
    }
    fn preflight(&mut self, output: &str) -> Result<Binding, Failure> {
        self.backend.preflight(output)
    }
    fn create_root(&mut self) -> Result<Binding, Failure> {
        self.backend.create_root()
    }
    fn create(&mut self, kind: Artifact, bytes: &[u8]) -> Result<Binding, Failure> {
        self.backend.create(kind, bytes)
    }
    fn check(&mut self, phase: Phase, bindings: &[Binding]) -> Result<(), Failure> {
        if phase == self.at {
            return Err(Failure::Cancelled);
        }
        self.backend.check(phase, bindings)
    }
    fn flush_file(&mut self, kind: Artifact) -> Result<(), Failure> {
        self.backend.flush_file(kind)
    }
    fn flush_root(&mut self) -> Result<(), Failure> {
        self.backend.flush_root()
    }
    fn flush_parent(&mut self) -> Result<(), Failure> {
        self.backend.flush_parent()
    }
    fn publish(&mut self, output: &str) -> Result<(), Failure> {
        self.backend.publish(output)
    }
    fn caller_release(&mut self, bindings: &[Binding]) -> Result<(), Failure> {
        self.backend.caller_release(bindings)
    }
    fn checked_context(&mut self, bindings: &[Binding]) -> Result<(), Failure> {
        self.backend.checked_context(bindings)
    }
    fn export_terminal(&mut self, bindings: &[Binding]) -> Result<(), Failure> {
        if self.at == Phase::TerminalExport {
            return Err(Failure::Cancelled);
        }
        self.backend.export_terminal(bindings)
    }
    fn retain_live_evidence(&mut self, evidence: &LiveEvidence) {
        self.backend.retain_live_evidence(evidence);
    }
    fn retain_outcome(&mut self, phase: Phase, failure: Option<Failure>) {
        self.backend.retain_outcome(phase, failure);
    }
}
struct Fixture {
    path: PathBuf,
    expected: CurrentBindings,
    prior: Option<crate::storage::finalization::PriorProof>,
    source: imageinfo_windows_storage::FileSnapshot,
    originals: Vec<(String, Vec<u8>, imageinfo_windows_storage::FileSnapshot)>,
}
impl Fixture {
    fn root(&self) -> PathBuf {
        self.path.join("unit")
    }
    fn source_path(&self) -> PathBuf {
        self.path.join("source.bin")
    }
    fn spec(&self) -> InspectionSpec<'static> {
        InspectionSpec {
            operation: "172-authored",
            format_revision: "172-v1",
            output: "output.bin",
            candidate_len: OUTPUT.len() as u64,
        }
    }
    fn authority(&self, action: RestartAction) -> (TrustedCurrentCaller, ActionAuthority) {
        let mut caller = TrustedCurrentCaller::new();
        let history = if action == RestartAction::PruneUnpublished {
            CurrentCallerHistory::StoppedBeforeRelease
        } else {
            CurrentCallerHistory::TerminalCompletionAndStopped
        };
        caller
            .attest_current(self.expected.clone(), history)
            .unwrap();
        let authority = caller.authorize(action, &self.expected).unwrap();
        (caller, authority)
    }
    fn prune(&self) -> (TrustedCurrentCaller, CleanupRequest) {
        let (caller, authority) = self.authority(RestartAction::PruneUnpublished);
        (
            caller,
            CleanupRequest::unpublished(self.expected.clone(), authority).unwrap(),
        )
    }
    fn completed(&mut self, kinds: &[Artifact]) -> (TrustedCurrentCaller, CleanupRequest) {
        let (caller, authority) = self.authority(RestartAction::CleanupCompleted);
        let request = CleanupRequest::completed(
            self.prior.take().unwrap(),
            authority,
            UnneededRecords::recovery_resolved(kinds).unwrap(),
        )
        .unwrap();
        (caller, request)
    }
    fn audit(&self, removed: &[&str]) {
        let mut source = GuardedSource::open(&self.source_path(), MAX_ARTIFACT_BYTES).unwrap();
        assert_eq!(source.snapshot(), &self.source);
        assert_eq!(source.read_exact_bytes().unwrap(), SOURCE);
        assert!(self.root().is_dir());
        let mut actual: Vec<_> = fs::read_dir(self.root())
            .unwrap()
            .map(|e| e.unwrap().file_name().to_string_lossy().to_string())
            .collect();
        actual.sort();
        let mut expected = Vec::new();
        for (leaf, bytes, snapshot) in &self.originals {
            if removed.contains(&leaf.as_str()) {
                assert!(!self.root().join(leaf).exists());
                continue;
            }
            expected.push(leaf.clone());
            let mut held =
                GuardedSource::open(&self.root().join(leaf), MAX_ARTIFACT_BYTES).unwrap();
            assert_eq!(held.snapshot(), snapshot);
            assert_eq!(&held.read_exact_bytes().unwrap(), bytes);
        }
        expected.sort();
        assert_eq!(actual, expected);
        fs::write(self.path.join("independent-audit.private.txt"), format!("Source identity/bytes/properties and root retained; exact original identities/bytes/properties for every survivor; exact removed-name set {removed:?}; no candidate/output replay.\n")).unwrap();
    }
}
fn fixture(label: &str, stop: Phase) -> Fixture {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join(".local")
        .join("work-wave-20261017c")
        .join(format!(
            "172-{label}-{}-{}",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
    fs::create_dir_all(&path).unwrap();
    fs::write(path.join("source.bin"), SOURCE).unwrap();
    let mut stop = Stop {
        backend: WindowsBackend::new(&path.join("source.bin"), &path.join("unit")),
        at: stop,
    };
    let mut reader = Cursor::new(OUTPUT);
    let result = execute(
        &mut stop,
        ValidatedCandidate {
            operation: "172-authored",
            format_revision: "172-v1",
            source: &mut reader,
            planned_len: OUTPUT.len() as u64,
            max_len: OUTPUT.len() as u64,
            output: ExpectedAbsent("output.bin"),
        },
        &mut LogicalBudget::new(1_000_000),
        &Cancellation::default(),
    );
    assert_ne!(result.status, crate::storage::Status::Committed);
    let expected = stop.backend.custody_snapshot("172-authored").unwrap();
    let prior = if result.publication_possible {
        Some(stop.backend.finalization_prior("172-authored").unwrap())
    } else {
        None
    };
    assert!(if stop.at == Phase::SourceRead {
        result.protocol_complete
    } else {
        result.failure == Some(Failure::Cancelled)
    });
    drop(stop);
    let source = GuardedSource::open(&path.join("source.bin"), MAX_ARTIFACT_BYTES)
        .unwrap()
        .snapshot()
        .clone();
    let mut originals = Vec::new();
    for entry in fs::read_dir(path.join("unit")).unwrap() {
        let entry = entry.unwrap();
        let mut held = GuardedSource::open(&entry.path(), MAX_ARTIFACT_BYTES).unwrap();
        originals.push((
            entry.file_name().to_string_lossy().to_string(),
            held.read_exact_bytes().unwrap(),
            held.snapshot().clone(),
        ));
    }
    Fixture {
        path,
        expected,
        prior,
        source,
        originals,
    }
}

#[test]
fn native_prune_exact_unpublished_owned_files_and_live_early_candidate() {
    for phase in [Phase::CandidateChecked, Phase::IntentChecked] {
        let f = fixture("prune", phase);
        let (_caller, request) = f.prune();
        let result = cleanup(
            &f.source_path(),
            &f.root(),
            request,
            &Cancellation::default(),
        );
        assert_eq!(result.status, CleanupStatus::Removed, "{result:?}");
        assert!(!result.pending_cleanup && !result.terminal_completion_preserved);
        let names: Vec<_> = f
            .originals
            .iter()
            .map(|(name, _, _)| name.as_str())
            .collect();
        f.audit(&names);
    }
}
#[test]
fn native_positive_postcommit_cleanup_retains_output_and_needed_records() {
    let mut f = fixture("postcommit", Phase::SourceRead);
    let (_caller, request) = f.completed(&[Artifact::Prepared, Artifact::Intent]);
    let result = cleanup(
        &f.source_path(),
        &f.root(),
        request,
        &Cancellation::default(),
    );
    assert_eq!(result.status, CleanupStatus::Removed, "{result:?}");
    assert!(result.terminal_completion_preserved && !result.pending_cleanup);
    assert_eq!(
        result
            .residuals
            .iter()
            .filter(|r| r.disposition == Disposition::RecoveryEvidence)
            .count(),
        2
    );
    f.audit(&["prepared.record", "intent.record"]);
}
#[test]
fn native_reader_deferral_reports_pending_then_reader_close_unlinks() {
    let f = fixture("reader", Phase::IntentChecked);
    let (_caller, request) = f.prune();
    let mut reader = None;
    let result = run(
        &f.source_path(),
        &f.root(),
        request,
        &Cancellation::default(),
        |_, _| {
            reader = Some(
                fs::OpenOptions::new()
                    .read(true)
                    .share_mode(7)
                    .open(f.root().join("candidate.bin"))
                    .unwrap(),
            );
            Ok(())
        },
    );
    assert_eq!(result.status, CleanupStatus::Pending, "{result:?}");
    assert!(result.pending_cleanup);
    assert_eq!(
        reader.as_ref().unwrap().metadata().unwrap().len(),
        OUTPUT.len() as u64
    );
    drop(reader);
    f.audit(&["candidate.bin"]);
}
#[test]
fn native_partial_removal_stale_retry_and_cancellation_are_truthful() {
    let f = fixture("partial", Phase::IntentChecked);
    let (_caller, request) = f.prune();
    let result = run(
        &f.source_path(),
        &f.root(),
        request,
        &Cancellation::default(),
        |effect, _| {
            if effect == 1 {
                Err(Failure::BackendIo)
            } else {
                Ok(())
            }
        },
    );
    assert_eq!(result.status, CleanupStatus::Partial);
    assert!(result.pending_cleanup);
    f.audit(&["candidate.bin"]);
    let (_caller2, request2) = f.prune();
    let result2 = cleanup(
        &f.source_path(),
        &f.root(),
        request2,
        &Cancellation::default(),
    );
    assert_eq!(result2.status, CleanupStatus::Refused);
    f.audit(&["candidate.bin"]);
    let fresh = fixture("cancel", Phase::IntentChecked);
    let (_caller, request) = fresh.prune();
    let cancel = Cancellation::default();
    cancel.request();
    assert_eq!(
        cleanup(&fresh.source_path(), &fresh.root(), request, &cancel).failure,
        Some(Failure::Cancelled)
    );
    fresh.audit(&[]);
}
#[test]
fn native_foreign_reinsertion_extra_entry_changed_and_inaccessible_refuse() {
    for mode in [
        "foreign",
        "extra",
        "changed",
        "missing",
        "source-changed",
        "reader-block",
    ] {
        let f = fixture(mode, Phase::IntentChecked);
        let (_caller, request) = f.prune();
        let candidate = f.root().join("candidate.bin");
        let reader = match mode {
            "foreign" => {
                fs::rename(&candidate, f.path.join("retained-original.bin")).unwrap();
                fs::write(&candidate, b"foreign").unwrap();
                None
            }
            "extra" => {
                fs::write(f.root().join("foreign.bin"), b"foreign").unwrap();
                None
            }
            "changed" => {
                fs::write(&candidate, b"changed").unwrap();
                None
            }
            "missing" => {
                fs::rename(&candidate, f.path.join("retained-original.bin")).unwrap();
                None
            }
            "source-changed" => {
                fs::write(f.source_path(), b"changed-source").unwrap();
                None
            }
            _ => Some(
                fs::OpenOptions::new()
                    .read(true)
                    .share_mode(1)
                    .open(&candidate)
                    .unwrap(),
            ),
        };
        let before: Vec<_> = fs::read_dir(f.root())
            .unwrap()
            .map(|e| {
                let p = e.unwrap().path();
                (p.file_name().unwrap().to_owned(), fs::read(p).unwrap())
            })
            .collect();
        let result = cleanup(
            &f.source_path(),
            &f.root(),
            request,
            &Cancellation::default(),
        );
        assert_eq!(result.status, CleanupStatus::Refused, "{mode}: {result:?}");
        drop(reader);
        for (name, bytes) in before {
            assert_eq!(fs::read(f.root().join(name)).unwrap(), bytes);
        }
        assert_eq!(
            fs::read(f.source_path()).unwrap(),
            if mode == "source-changed" {
                b"changed-source".as_slice()
            } else {
                SOURCE
            }
        );
        assert!(f.root().exists());
    }
}
#[test]
fn released_uncertain_incomplete_terminal_and_revoked_authority_never_prune() {
    let f = fixture("released", Phase::TerminalExport);
    let mut caller = TrustedCurrentCaller::new();
    caller
        .attest_current(f.expected.clone(), CurrentCallerHistory::ReleasedAndStopped)
        .unwrap();
    assert!(
        caller
            .authorize(RestartAction::PruneUnpublished, &f.expected)
            .is_err()
    );
    assert!(
        caller
            .authorize(RestartAction::CleanupCompleted, &f.expected)
            .is_err()
    );
    let (_caller, authority) = f.authority(RestartAction::CleanupCompleted);
    assert!(
        CleanupRequest::completed(
            f.prior.unwrap(),
            authority,
            UnneededRecords::recovery_resolved(&[Artifact::Intent]).unwrap()
        )
        .is_err()
    );
    let fresh = fixture("revoked", Phase::IntentChecked);
    let (mut caller, request) = fresh.prune();
    caller.revoke();
    assert_eq!(
        cleanup(
            &fresh.source_path(),
            &fresh.root(),
            request,
            &Cancellation::default()
        )
        .failure,
        Some(Failure::CallerHistory)
    );
    fresh.audit(&[]);
}
#[test]
fn postcommit_partial_failure_preserves_terminal_completion_and_never_reapplies() {
    let mut f = fixture("committed-partial", Phase::SourceRead);
    let (_caller, request) = f.completed(&ORDER);
    let result = run(
        &f.source_path(),
        &f.root(),
        request,
        &Cancellation::default(),
        |effect, _| {
            if effect == 1 {
                Err(Failure::BackendIo)
            } else {
                Ok(())
            }
        },
    );
    assert_eq!(result.status, CleanupStatus::Partial);
    assert!(result.terminal_completion_preserved && result.pending_cleanup);
    f.audit(&["prepared.record"]);
}
#[test]
fn unneeded_decision_cannot_select_candidate_or_duplicate_records() {
    assert!(UnneededRecords::recovery_resolved(&[Artifact::Candidate]).is_err());
    assert!(UnneededRecords::recovery_resolved(&[Artifact::Intent, Artifact::Intent]).is_err());
    assert!(UnneededRecords::recovery_resolved(&[]).is_err());
}

#[test]
fn native_fresh_property_checkpoint_and_mid_action_extra_entry_refuse_next_effect() {
    for mode in ["property", "extra", "revoke"] {
        let f = fixture(mode, Phase::IntentChecked);
        let (mut caller, request) = f.prune();
        let result = run(
            &f.source_path(),
            &f.root(),
            request,
            &Cancellation::default(),
            |effect, _| {
                if effect != 1 {
                    return Ok(());
                }
                match mode {
                    "property" => {
                        let setter = fs::OpenOptions::new()
                            .access_mode(0x100)
                            .share_mode(7)
                            .open(f.root().join("prepared.record"))
                            .unwrap();
                        setter
                            .set_times(
                                fs::FileTimes::new()
                                    .set_modified(UNIX_EPOCH + std::time::Duration::from_secs(10)),
                            )
                            .unwrap();
                    }
                    "extra" => {
                        fs::write(f.root().join("foreign.bin"), b"foreign-extra").unwrap();
                    }
                    _ => caller.revoke(),
                }
                Ok(())
            },
        );
        assert_eq!(result.status, CleanupStatus::Partial, "{mode}: {result:?}");
        assert!(result.pending_cleanup);
        assert!(!f.root().join("candidate.bin").exists());
        for kind in [Artifact::Prepared, Artifact::Intent] {
            let original = f
                .originals
                .iter()
                .find(|(leaf, _, _)| leaf == kind.leaf())
                .unwrap();
            let mut held =
                GuardedSource::open(&f.root().join(kind.leaf()), MAX_RECORD_BYTES).unwrap();
            assert_eq!(held.read_exact_bytes().unwrap(), original.1);
            if mode == "property" && kind == Artifact::Prepared {
                assert_ne!(held.snapshot().last_write_time, original.2.last_write_time);
                assert_eq!(held.snapshot().file_index, original.2.file_index);
            } else {
                assert_eq!(held.snapshot(), &original.2);
            }
        }
        assert_eq!(fs::read(f.source_path()).unwrap(), SOURCE);
        if mode == "extra" {
            assert_eq!(
                fs::read(f.root().join("foreign.bin")).unwrap(),
                b"foreign-extra"
            );
        }
    }
}

#[test]
fn completed_fresh_finalization_supplies_actual_cleanup_proof_without_admitting_profile() {
    let mut f = fixture("finalized", Phase::TerminalExport);
    let mut caller = TrustedCurrentCaller::new();
    caller
        .attest_current(f.expected.clone(), CurrentCallerHistory::ReleasedAndStopped)
        .unwrap();
    let authority = caller
        .authorize(RestartAction::FinalizeExisting, &f.expected)
        .unwrap();
    let finalized = crate::storage::finalization::finalize(
        &f.source_path(),
        &f.root(),
        &f.spec(),
        "172-fresh-finalization",
        f.prior.take().unwrap(),
        authority,
        &mut LogicalBudget::new(1_000_000),
        &Cancellation::default(),
        |_, _| Ok(()),
    );
    assert!(finalized.result.protocol_complete);
    assert_ne!(finalized.result.status, crate::storage::Status::Committed);
    let context = finalized.context.unwrap();
    caller
        .attest_current(
            context.bindings().clone(),
            CurrentCallerHistory::TerminalCompletionAndStopped,
        )
        .unwrap();
    let authority = caller
        .authorize(RestartAction::CleanupCompleted, context.bindings())
        .unwrap();
    let request = CleanupRequest::finalized(
        context,
        authority,
        UnneededRecords::recovery_resolved(&[Artifact::Intent]).unwrap(),
    )
    .unwrap();
    let result = cleanup(
        &f.source_path(),
        &f.root(),
        request,
        &Cancellation::default(),
    );
    assert_eq!(result.status, CleanupStatus::Removed, "{result:?}");
    assert!(result.terminal_completion_preserved);
    f.audit(&["intent.record"]);
}

#[test]
fn native_sdk_readonly_disposition_error_has_no_pathname_fallback() {
    let f = fixture("readonly-sdk", Phase::IntentChecked);
    let marker = f.path.join("readonly-owned.bin");
    fs::write(&marker, b"172 readonly disposition control").unwrap();
    let mut permissions = fs::metadata(&marker).unwrap().permissions();
    permissions.set_readonly(true);
    fs::set_permissions(&marker, permissions).unwrap();
    let file = CleanupFile::open(&marker, MAX_ARTIFACT_BYTES).unwrap();
    let expected = file.snapshot().clone();
    let bytes = file.bytes().to_vec();
    let error = file.remove().unwrap_err();
    assert!(error.disposition_attempted);
    assert!(error.error.raw_os_error().is_some());
    let mut survivor = GuardedSource::open(&marker, MAX_ARTIFACT_BYTES).unwrap();
    assert_eq!(survivor.snapshot(), &expected);
    assert_eq!(survivor.read_exact_bytes().unwrap(), bytes);
    f.audit(&[]);
}
