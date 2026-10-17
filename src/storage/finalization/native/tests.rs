use super::*;
use crate::storage::custody::{CurrentCallerHistory, TrustedCurrentCaller};
use crate::storage::runtime::{Backend, ExpectedAbsent, ValidatedCandidate, execute};
use crate::storage::windows::WindowsBackend;
use std::os::windows::fs::MetadataExt;
use std::{
    fs,
    io::Cursor,
    path::PathBuf,
    sync::atomic::{AtomicU64, Ordering},
    time::{SystemTime, UNIX_EPOCH},
};

const SOURCE: &[u8] = b"171 protected authored original";
const OUTPUT: &[u8] = b"171 installed authored derivative";
static NEXT: AtomicU64 = AtomicU64::new(0);
fn spec() -> InspectionSpec<'static> {
    InspectionSpec {
        operation: "171-authored-operation",
        format_revision: "171-authored-v1",
        output: "output.bin",
        candidate_len: OUTPUT.len() as u64,
    }
}

struct Stop {
    native: WindowsBackend,
    at: Phase,
    last: Phase,
}
impl Stop {
    fn gate(&self, phase: Phase) -> Result<(), Failure> {
        if self.at == phase {
            Err(Failure::Cancelled)
        } else {
            Ok(())
        }
    }
}
impl Backend for Stop {
    fn profile(&self) -> &'static str {
        self.native.profile()
    }
    fn implementation(&self) -> &'static str {
        self.native.implementation()
    }
    fn preflight(&mut self, output: &str) -> Result<Binding, Failure> {
        self.native.preflight(output)
    }
    fn create_root(&mut self) -> Result<Binding, Failure> {
        self.native.create_root()
    }
    fn create(&mut self, kind: Artifact, bytes: &[u8]) -> Result<Binding, Failure> {
        let phase = match kind {
            Artifact::Receipt => Phase::ReceiptCreated,
            Artifact::Observation => Phase::ObservationCreated,
            _ => Phase::CandidateCreated,
        };
        self.gate(phase)?;
        self.last = phase;
        self.native.create(kind, bytes)
    }
    fn check(&mut self, phase: Phase, bindings: &[Binding]) -> Result<(), Failure> {
        self.gate(phase)?;
        self.last = phase;
        self.native.check(phase, bindings)
    }
    fn flush_file(&mut self, kind: Artifact) -> Result<(), Failure> {
        let phase = match kind {
            Artifact::Receipt => Phase::ReceiptFlushed,
            Artifact::Observation => Phase::ObservationFlushed,
            _ => Phase::CandidateFlushed,
        };
        self.gate(phase)?;
        self.last = phase;
        self.native.flush_file(kind)
    }
    fn flush_root(&mut self) -> Result<(), Failure> {
        let phase = match self.last {
            Phase::ObservationFlushed => Phase::ObservationParentFlushed,
            Phase::ReceiptFileChecked => Phase::ReceiptParentFlushed,
            _ => Phase::RootFlushed,
        };
        self.gate(phase)?;
        self.last = phase;
        self.native.flush_root()
    }
    fn flush_parent(&mut self) -> Result<(), Failure> {
        self.native.flush_parent()
    }
    fn publish(&mut self, output: &str) -> Result<(), Failure> {
        self.native.publish(output)
    }
    fn caller_release(&mut self, bindings: &[Binding]) -> Result<(), Failure> {
        self.native.caller_release(bindings)
    }
    fn checked_context(&mut self, bindings: &[Binding]) -> Result<(), Failure> {
        self.gate(Phase::CheckedContext)?;
        self.native.checked_context(bindings)
    }
    fn export_terminal(&mut self, bindings: &[Binding]) -> Result<(), Failure> {
        self.gate(Phase::TerminalExport)?;
        self.native.export_terminal(bindings)
    }
    fn retain_live_evidence(&mut self, evidence: &LiveEvidence) {
        self.native.retain_live_evidence(evidence);
    }
    fn retain_outcome(&mut self, phase: Phase, failure: Option<Failure>) {
        self.native.retain_outcome(phase, failure);
    }
}
struct Fixture {
    path: PathBuf,
    prior: PriorProof,
    original: imageinfo_windows_storage::FileSnapshot,
    output: imageinfo_windows_storage::FileSnapshot,
    records: Vec<(Artifact, Vec<u8>, imageinfo_windows_storage::FileSnapshot)>,
}
fn fixture(label: &str, stop: Phase) -> Fixture {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join(".local")
        .join("work-wave-20261017b")
        .join(format!(
            "171-{label}-{}-{}-{}",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
    fs::create_dir_all(&path).unwrap();
    fs::write(path.join("source.bin"), SOURCE).unwrap();
    let mut backend = Stop {
        native: WindowsBackend::new(&path.join("source.bin"), &path.join("unit")),
        at: stop,
        last: Phase::Preflight,
    };
    let mut reader = Cursor::new(OUTPUT);
    let result = execute(
        &mut backend,
        ValidatedCandidate {
            operation: spec().operation,
            format_revision: spec().format_revision,
            source: &mut reader,
            planned_len: spec().candidate_len,
            max_len: spec().candidate_len,
            output: ExpectedAbsent(spec().output),
        },
        &mut LogicalBudget::new(1_000_000),
        &Cancellation::default(),
    );
    if stop != Phase::SourceRead {
        assert_eq!(result.phase, stop);
        assert_eq!(result.failure, Some(Failure::Cancelled));
    } else {
        assert!(result.protocol_complete);
    }
    let prior = backend.native.finalization_prior(spec().operation).unwrap();
    drop(backend);
    let original = GuardedSource::open(&path.join("source.bin"), MAX_ARTIFACT_BYTES)
        .unwrap()
        .snapshot()
        .clone();
    let output = GuardedSource::open(&path.join("unit").join("output.bin"), MAX_ARTIFACT_BYTES)
        .unwrap()
        .snapshot()
        .clone();
    let records = ORDER
        .iter()
        .filter_map(|kind| {
            let p = path.join("unit").join(kind.leaf());
            if !p.exists() {
                return None;
            }
            let mut held = GuardedSource::open(&p, MAX_RECORD_BYTES).unwrap();
            Some((
                *kind,
                held.read_exact_bytes().unwrap(),
                held.snapshot().clone(),
            ))
        })
        .collect();
    Fixture {
        path,
        prior,
        original,
        output,
        records,
    }
}
fn authorize(prior: &PriorProof, action: RestartAction) -> (TrustedCurrentCaller, ActionAuthority) {
    let mut caller = TrustedCurrentCaller::new();
    let history = if action == RestartAction::RecognizeCompletion {
        CurrentCallerHistory::TerminalCompletionAndStopped
    } else {
        CurrentCallerHistory::ReleasedAndStopped
    };
    caller
        .attest_current(prior.bindings().clone(), history)
        .unwrap();
    let authority = caller.authorize(action, prior.bindings()).unwrap();
    (caller, authority)
}
fn audit(fixture: &Fixture, context: Option<&CompletionContext>) {
    let mut source =
        GuardedSource::open(&fixture.path.join("source.bin"), MAX_ARTIFACT_BYTES).unwrap();
    assert_eq!(source.snapshot(), &fixture.original);
    assert_eq!(source.read_exact_bytes().unwrap(), SOURCE);
    let mut output = GuardedSource::open(
        &fixture.path.join("unit").join("output.bin"),
        MAX_ARTIFACT_BYTES,
    )
    .unwrap();
    assert_eq!(output.snapshot(), &fixture.output);
    assert_eq!(output.read_exact_bytes().unwrap(), OUTPUT);
    assert!(!fixture.path.join("unit").join("candidate.bin").exists());
    for (kind, bytes, snapshot) in &fixture.records {
        let mut held = GuardedSource::open(
            &fixture.path.join("unit").join(kind.leaf()),
            MAX_RECORD_BYTES,
        )
        .unwrap();
        assert_eq!(held.snapshot(), snapshot);
        assert_eq!(&held.read_exact_bytes().unwrap(), bytes);
    }
    drop((source, output));
    if let Some(context) = context {
        assert_eq!(context.attempt, "171-fresh-attempt");
        let inspection = crate::storage::inspection::Inspection::collect(
            &fixture.path.join("source.bin"),
            &fixture.path.join("unit"),
            &spec(),
        )
        .unwrap();
        context.current.compare(inspection.bindings()).unwrap();
    }
    fs::write(fixture.path.join("audit.txt"), "Independent pathname reopening: exact source/output identity, complete bytes and properties; original prior records unchanged; candidate name absent. New receipt checked against completion context when available. No republish.\n").unwrap();
}

#[test]
fn eligible_actual_unfinished_phases_finish_and_unqualified_gate_stays_closed() {
    for stop in [
        Phase::ObservationChecked,
        Phase::ObservationFlushed,
        Phase::ObservationParentFlushed,
        Phase::ReceiptCreated,
        Phase::ReceiptChecked,
        Phase::ReceiptFlushed,
        Phase::ReceiptFileChecked,
        Phase::ReceiptParentFlushed,
        Phase::ReceiptParentChecked,
        Phase::CheckedContext,
        Phase::Final,
        Phase::TerminalExport,
    ] {
        let mut fixture = fixture(&format!("positive-{stop:?}"), stop);
        let (_caller, authority) = authorize(&fixture.prior, RestartAction::FinalizeExisting);
        let proof = std::mem::replace(&mut fixture.prior, placeholder());
        let mut saves = Vec::new();
        let result = run(
            &fixture.path.join("source.bin"),
            &fixture.path.join("unit"),
            &spec(),
            "171-fresh-attempt",
            proof,
            authority,
            &mut LogicalBudget::new(1_000_000),
            &Cancellation::default(),
            |phase, _| {
                saves.push(phase);
                Ok(())
            },
            Admission::Authored,
            |_, _, _| Ok(()),
        );
        assert_eq!(
            result.result.status,
            Status::Committed,
            "{stop:?}: {:?}",
            result.result
        );
        assert!(result.result.protocol_complete);
        assert_eq!(saves, [Phase::CheckedContext, Phase::TerminalExport]);
        audit(&fixture, result.context.as_ref());
    }
    let mut fixture = fixture("production-unqualified", Phase::ReceiptCreated);
    let (_caller, authority) = authorize(&fixture.prior, RestartAction::FinalizeExisting);
    let proof = std::mem::replace(&mut fixture.prior, placeholder());
    let result = finalize(
        &fixture.path.join("source.bin"),
        &fixture.path.join("unit"),
        &spec(),
        "171-fresh-attempt",
        proof,
        authority,
        &mut LogicalBudget::new(1_000_000),
        &Cancellation::default(),
        |_, _| Ok(()),
    );
    assert_eq!(result.result.status, Status::Refused);
    assert!(result.result.protocol_complete);
    audit(&fixture, result.context.as_ref());
}

// Only a test move helper: never supplied to an executor or an authority caller.
fn placeholder() -> PriorProof {
    use crate::storage::runtime::AckTarget;
    let b: Vec<_> = (1..=6)
        .map(|n| Binding {
            identity: vec![n],
            facts: vec![n],
        })
        .collect();
    let parent = Binding {
        identity: vec![99],
        facts: vec![99],
    };
    PriorProof {
        expected: CurrentBindings::capture(
            "unused",
            "unused",
            "unused",
            "unused",
            &parent,
            &b,
            &[
                (Artifact::Prepared, vec![1]),
                (Artifact::Intent, vec![2]),
                (Artifact::Observation, vec![3]),
            ],
            true,
        )
        .unwrap(),
        evidence: LiveEvidence {
            protocol: PROTOCOL,
            profile: "unused",
            implementation: "unused",
            operation: "unused".into(),
            format_revision: "unused".into(),
            output: "unused".into(),
            candidate_len: 0,
            acknowledgements: vec![crate::storage::runtime::LiveAcknowledgement {
                phase: Phase::Preflight,
                target: AckTarget::Source,
                bindings: b,
            }],
        },
    }
}

#[test]
fn errors_and_lost_responses_at_every_actual_boundary_retain_without_republish() {
    for at in [
        Phase::Installed,
        Phase::InstalledFlushed,
        Phase::InstalledParentFlushed,
        Phase::ParentFlushed,
        Phase::InstalledRechecked,
        Phase::ObservationChecked,
        Phase::ObservationFlushed,
        Phase::ObservationParentFlushed,
        Phase::ReceiptCreated,
        Phase::ReceiptChecked,
        Phase::ReceiptFlushed,
        Phase::ReceiptFileChecked,
        Phase::ReceiptParentFlushed,
        Phase::ReceiptParentChecked,
        Phase::CheckedContext,
        Phase::Final,
        Phase::TerminalExport,
    ] {
        for after in [false, true] {
            let mut fixture = fixture(&format!("fault-{at:?}-{after}"), Phase::ReceiptCreated);
            let (_caller, authority) = authorize(&fixture.prior, RestartAction::FinalizeExisting);
            let proof = std::mem::replace(&mut fixture.prior, placeholder());
            let result = run(
                &fixture.path.join("source.bin"),
                &fixture.path.join("unit"),
                &spec(),
                "171-fresh-attempt",
                proof,
                authority,
                &mut LogicalBudget::new(1_000_000),
                &Cancellation::default(),
                |_, _| Ok(()),
                Admission::Authored,
                |phase, returned, _| {
                    if phase == at && returned == after {
                        Err(Failure::BackendIo)
                    } else {
                        Ok(())
                    }
                },
            );
            assert_eq!(result.result.status, Status::RecoveryRequired);
            assert!(!result.result.protocol_complete);
            assert!(result.context.is_none());
            assert_eq!(result.result.phase, at);
            audit(&fixture, None);
        }
    }
}

#[test]
fn conflicts_missing_objects_stale_authority_and_receipt_winner_preserve_artifacts() {
    for case in [
        "missing-output",
        "missing-record",
        "missing-receipt",
        "changed-source",
        "changed-output",
        "stale",
        "winner",
        "budget",
        "cancel",
        "incomplete-acks",
        "revoked-during-attempt",
        "save-failed",
    ] {
        let mut fixture = fixture(
            case,
            if case == "missing-receipt" {
                Phase::ReceiptFlushed
            } else {
                Phase::ReceiptCreated
            },
        );
        let (mut caller, authority) = authorize(&fixture.prior, RestartAction::FinalizeExisting);
        let before_source = fs::metadata(fixture.path.join("source.bin"))
            .unwrap()
            .last_write_time();
        match case {
            "missing-output" => {
                fs::remove_file(fixture.path.join("unit").join("output.bin")).unwrap()
            }
            "missing-record" => {
                fs::remove_file(fixture.path.join("unit").join("prepared.record")).unwrap()
            }
            "missing-receipt" => {
                fs::remove_file(fixture.path.join("unit").join("receipt.record")).unwrap()
            }
            "changed-source" => {
                fs::write(fixture.path.join("source.bin"), b"later source").unwrap()
            }
            "changed-output" => fs::write(
                fixture.path.join("unit").join("output.bin"),
                b"later output",
            )
            .unwrap(),
            "stale" => caller.revoke(),
            "incomplete-acks" => {
                fixture.prior.evidence.acknowledgements.remove(4);
            }
            _ => {}
        }
        // Independently capture even the actor-modified survivor set. Refusal
        // must preserve those later bytes/properties, not restore old content.
        let mut paths = vec![fixture.path.join("source.bin")];
        paths.extend(
            fs::read_dir(fixture.path.join("unit"))
                .unwrap()
                .map(|entry| entry.unwrap().path()),
        );
        let before: Vec<_> = paths
            .into_iter()
            .map(|path| {
                let mut held = GuardedSource::open(&path, MAX_ARTIFACT_BYTES).unwrap();
                (
                    path,
                    held.snapshot().clone(),
                    held.read_exact_bytes().unwrap(),
                )
            })
            .collect();
        let proof = std::mem::replace(&mut fixture.prior, placeholder());
        let cancel = Cancellation::default();
        if case == "cancel" {
            cancel.request();
        }
        let root = fixture.path.join("unit");
        let result = run(
            &fixture.path.join("source.bin"),
            &root,
            &spec(),
            "171-fresh-attempt",
            proof,
            authority,
            &mut LogicalBudget::new(if case == "budget" { 1 } else { 1_000_000 }),
            &cancel,
            |_, _| {
                if case == "save-failed" {
                    Err(Failure::CallerHistory)
                } else {
                    Ok(())
                }
            },
            Admission::Authored,
            |phase, after, _| {
                if case == "revoked-during-attempt" && phase == Phase::ReceiptCreated && !after {
                    caller.revoke();
                }
                if case == "winner" && phase == Phase::ReceiptCreated && !after {
                    fs::write(root.join("receipt.record"), b"foreign winner").unwrap();
                }
                Ok(())
            },
        );
        assert_eq!(result.result.status, Status::RecoveryRequired, "{case}");
        assert!(!result.result.protocol_complete);
        assert!(result.context.is_none());
        for (path, snapshot, bytes) in before {
            let mut held = GuardedSource::open(&path, MAX_ARTIFACT_BYTES).unwrap();
            assert_eq!(held.snapshot(), &snapshot, "{case}: {}", path.display());
            assert_eq!(
                held.read_exact_bytes().unwrap(),
                bytes,
                "{case}: {}",
                path.display()
            );
        }
        if case == "missing-output" {
            assert!(!root.join("output.bin").exists());
        }
        if case == "missing-record" {
            assert!(!root.join("prepared.record").exists());
        }
        if case == "missing-receipt" {
            assert!(!root.join("receipt.record").exists());
        }
        if case == "winner" {
            assert_eq!(
                fs::read(root.join("receipt.record")).unwrap(),
                b"foreign winner"
            );
        }
        if case != "changed-source" {
            assert_eq!(fs::read(fixture.path.join("source.bin")).unwrap(), SOURCE);
            assert_eq!(
                fs::metadata(fixture.path.join("source.bin"))
                    .unwrap()
                    .last_write_time(),
                before_source
            );
        }
        assert!(!root.join("candidate.bin").exists());
        fs::write(fixture.path.join("audit.txt"), format!("{case}: refused; source/foreign preservation and zero candidate republish checked.\n")).unwrap();
    }
}

#[test]
fn independently_retained_completion_is_recognized_read_only_and_later_edit_refuses() {
    for changed in [false, true] {
        let fixture = fixture("recognize", Phase::SourceRead);
        let (_caller, authority) = authorize(&fixture.prior, RestartAction::RecognizeCompletion);
        if changed {
            fs::write(
                fixture.path.join("unit").join("output.bin"),
                b"owner later edit",
            )
            .unwrap();
        }
        let source = fixture.path.join("source.bin");
        let root = fixture.path.join("unit");
        if changed {
            assert!(recognize(&source, &root, &spec(), fixture.prior, authority).is_err());
        } else {
            assert_eq!(
                recognize(&source, &root, &spec(), fixture.prior, authority).unwrap(),
                crate::storage::inspection::Survivor::PreviouslyCompleted
            );
            assert_eq!(fs::read(root.join("output.bin")).unwrap(), OUTPUT);
        }
    }
}

#[test]
fn fresh_completion_has_its_own_terminal_recognition_without_duplicate_effects() {
    let mut fixture = fixture("new-recognition", Phase::ReceiptCreated);
    let (_caller, authority) = authorize(&fixture.prior, RestartAction::FinalizeExisting);
    let proof = std::mem::replace(&mut fixture.prior, placeholder());
    let result = run(
        &fixture.path.join("source.bin"),
        &fixture.path.join("unit"),
        &spec(),
        "171-fresh-attempt",
        proof,
        authority,
        &mut LogicalBudget::new(1_000_000),
        &Cancellation::default(),
        |_, context| {
            assert!(
                !context.complete(),
                "a save cannot attest its own future terminal return"
            );
            Ok(())
        },
        Admission::Authored,
        |_, _, _| Ok(()),
    );
    assert_eq!(result.result.status, Status::Committed);
    let context = result.context.unwrap();
    assert!(context.complete());
    audit(&fixture, Some(&context));
    let mut caller = TrustedCurrentCaller::new();
    caller
        .attest_current(
            context.bindings().clone(),
            CurrentCallerHistory::TerminalCompletionAndStopped,
        )
        .unwrap();
    let authority = caller
        .authorize(RestartAction::RecognizeCompletion, context.bindings())
        .unwrap();
    assert_eq!(
        recognize_finalized(
            &fixture.path.join("source.bin"),
            &fixture.path.join("unit"),
            &spec(),
            context,
            authority
        )
        .unwrap(),
        crate::storage::inspection::Survivor::PreviouslyCompleted
    );
    audit(&fixture, None);
}

#[test]
fn sdk_exclusive_receipt_creation_preserves_a_foreign_winner() {
    let fixture = fixture("sdk-winner", Phase::ReceiptCreated);
    let root = FinalizationRoot::open(&fixture.path.join("unit")).unwrap();
    fs::write(
        fixture.path.join("unit").join("receipt.record"),
        b"foreign winner",
    )
    .unwrap();
    assert_eq!(
        root.create_receipt(b"new receipt").err().unwrap().kind(),
        std::io::ErrorKind::AlreadyExists
    );
    drop(root);
    assert_eq!(
        fs::read(fixture.path.join("unit").join("receipt.record")).unwrap(),
        b"foreign winner"
    );
    audit(&fixture, None);
}

#[test]
fn source_output_and_prior_record_writers_remain_excluded_through_terminal_save() {
    let mut fixture = fixture("held-through-export", Phase::ReceiptCreated);
    let (_caller, authority) = authorize(&fixture.prior, RestartAction::FinalizeExisting);
    let proof = std::mem::replace(&mut fixture.prior, placeholder());
    let result = finalize(
        &fixture.path.join("source.bin"),
        &fixture.path.join("unit"),
        &spec(),
        "171-fresh-attempt",
        proof,
        authority,
        &mut LogicalBudget::new(1_000_000),
        &Cancellation::default(),
        |_, _| {
            for path in [
                fixture.path.join("source.bin"),
                fixture.path.join("unit").join("output.bin"),
                fixture.path.join("unit").join("prepared.record"),
            ] {
                assert!(fs::OpenOptions::new().write(true).open(path).is_err());
            }
            Ok(())
        },
    );
    assert!(result.result.protocol_complete);
    assert_eq!(result.result.status, Status::Refused);
    audit(&fixture, result.context.as_ref());
}
