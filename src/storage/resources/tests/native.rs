use super::*;
use crate::storage::windows::WindowsBackend;
use std::{
    fs,
    path::PathBuf,
    time::{SystemTime, UNIX_EPOCH},
};

#[derive(Clone, Copy, PartialEq, Eq)]
enum Mode {
    Complete,
    FailedCreate,
    CancelledCreate,
    LostTerminal,
}

struct Observed<'a> {
    native: WindowsBackend,
    mode: Mode,
    cancel: &'a Cancellation,
    created: Vec<(Artifact, usize)>,
    captures: usize,
}

impl Backend for Observed<'_> {
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
        let binding = self.native.create(kind, bytes)?;
        self.created.push((kind, bytes.len()));
        if kind == Artifact::Prepared && self.mode == Mode::FailedCreate {
            return Err(Failure::BackendIo);
        }
        if kind == Artifact::Candidate && self.mode == Mode::CancelledCreate {
            self.cancel.request();
        }
        Ok(binding)
    }
    fn check(&mut self, phase: Phase, bindings: &[Binding]) -> Result<(), Failure> {
        self.native.check(phase, bindings)
    }
    fn flush_file(&mut self, kind: Artifact) -> Result<(), Failure> {
        self.native.flush_file(kind)
    }
    fn flush_root(&mut self) -> Result<(), Failure> {
        self.native.flush_root()
    }
    fn flush_parent(&mut self) -> Result<(), Failure> {
        self.native.flush_parent()
    }
    fn publish(&mut self, output: &str) -> Result<(), Failure> {
        self.native.publish(output)
    }
    fn caller_release(&mut self, bindings: &[Binding]) -> Result<(), Failure> {
        self.captures += 1;
        self.native.caller_release(bindings)
    }
    fn checked_context(&mut self, bindings: &[Binding]) -> Result<(), Failure> {
        self.captures += 1;
        self.native.checked_context(bindings)
    }
    fn export_terminal(&mut self, bindings: &[Binding]) -> Result<(), Failure> {
        self.captures += 1;
        self.native.export_terminal(bindings)?;
        if self.mode == Mode::LostTerminal {
            return Err(Failure::BackendIo);
        }
        Ok(())
    }
    fn retain_live_evidence(&mut self, evidence: &crate::storage::runtime::LiveEvidence) {
        self.native.retain_live_evidence(evidence);
    }
}

#[test]
fn actual_repeated_native_work_retains_failed_cancelled_successful_and_cleanup_charges() {
    let evidence = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join(".local")
        .join("work-wave-20261017a")
        .join(format!(
            "173-native-{}-{}",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
    fs::create_dir_all(&evidence).unwrap();
    let source = evidence.join("source.bin");
    fs::write(&source, b"authored original").unwrap();
    let base = 3 + 9 * MAX_RECORD_BYTES;
    let limit = 5 * base + MAX_RECORD_BYTES + 48;
    let mut session = RetainedSession::start(limit, KnownOperations::Complete(&[])).unwrap();
    let modes = [
        Mode::Complete,
        Mode::FailedCreate,
        Mode::CancelledCreate,
        Mode::Complete,
        Mode::LostTerminal,
    ];
    let names = [
        "completed",
        "failed-create",
        "cancelled",
        "short-source",
        "lost-terminal",
    ];
    let mut audit = String::from("#173 actual native construction/retention audit\n");
    for (index, (operation, mode)) in names.iter().zip(modes).enumerate() {
        let root = evidence.join(operation);
        let cancel = Cancellation::default();
        let mut backend = Observed {
            native: WindowsBackend::new(&source, &root),
            mode,
            cancel: &cancel,
            created: Vec::new(),
            captures: 0,
        };
        let mut bytes = Cursor::new(if index == 3 {
            b"ab".as_slice()
        } else {
            b"abc".as_slice()
        });
        let result = session
            .run(
                key(operation),
                &mut backend,
                ValidatedCandidate {
                    operation,
                    format_revision: "authored-resource-v1",
                    source: &mut bytes,
                    planned_len: 3,
                    max_len: 3,
                    output: ExpectedAbsent("output.bin"),
                },
                &cancel,
                |backend| backend.native.available_bytes(),
            )
            .unwrap();
        assert_eq!(result.charged_bytes, base);
        assert_eq!(
            session.charged(),
            base * (index as u64 + 1) + if index == 0 { 0 } else { MAX_RECORD_BYTES }
        );
        assert_eq!(fs::read(&source).unwrap(), b"authored original");
        match index {
            0 => {
                assert!(
                    result.protocol_complete,
                    "actual native completion required: {result:?}"
                );
                assert_eq!(fs::read(root.join("output.bin")).unwrap(), b"abc");
                session
                    .capture_custody(key(operation), &mut backend.native)
                    .unwrap();
                // Account for the actual extra bounded capture separately from
                // the three runtime-native captures in the base allowance.
                assert_eq!(
                    session.operation_charge(key(operation)).unwrap(),
                    base + MAX_RECORD_BYTES
                );
            }
            1 => assert_eq!(result.status, Status::FailedBeforePublish),
            2 => assert_eq!(result.status, Status::CancelledBeforePublish),
            3 => {
                assert_eq!(result.failure, Some(Failure::ShortSource));
                assert!(!root.exists());
            }
            4 => assert_eq!(result.status, Status::RecoveryRequired),
            _ => unreachable!(),
        }
        let candidate_count = backend
            .created
            .iter()
            .filter(|(kind, _)| *kind == Artifact::Candidate)
            .count();
        let records: Vec<_> = backend
            .created
            .iter()
            .filter(|(kind, _)| *kind != Artifact::Candidate)
            .collect();
        assert!(candidate_count <= 1 && records.len() <= 4 && backend.captures <= 3);
        assert!(
            records
                .iter()
                .all(|(_, bytes)| *bytes as u64 <= MAX_RECORD_BYTES)
        );
        let actual_disk: u64 = if root.exists() {
            fs::read_dir(&root)
                .unwrap()
                .map(|entry| entry.unwrap().metadata().unwrap().len())
                .sum()
        } else {
            0
        };
        assert!(actual_disk <= 3 + 4 * MAX_RECORD_BYTES);
        audit.push_str(&format!("{operation}: status={:?}, phase={:?}, candidate-constructions={candidate_count}, record-constructions={}, native-captures={}, observed-disk-logical-bytes={actual_disk}, reserved-base={base}\n", result.status, result.phase, records.len(), backend.captures));
    }
    // Explicit authored operator removal after handles close. This is not a
    // production cleanup implementation or authority for any other object.
    let removed = evidence.join("failed-create/candidate.bin");
    assert_eq!(fs::read(&removed).unwrap(), b"abc");
    fs::remove_file(&removed).unwrap();
    assert!(evidence.join("failed-create/prepared.record").exists());
    assert_eq!(session.charged(), 5 * base + MAX_RECORD_BYTES);
    assert_eq!(
        session.construct(key("failed-create"), Construction::Recovery, 32, || {
            let bytes = vec![0x52; 32];
            fs::write(evidence.join("failed-recovery.record"), &bytes)
                .map_err(|_| Failure::BackendIo)?;
            Err::<(), _>(Failure::BackendIo)
        }),
        Err(Failure::BackendIo)
    );
    session
        .construct(key("completed"), Construction::Manifest, 16, || {
            fs::write(evidence.join("manifest.record"), [0x4d; 16]).map_err(|_| Failure::BackendIo)
        })
        .unwrap();
    assert_eq!(session.charged(), limit);
    let known: Vec<_> = names.iter().map(|name| key(name)).collect();
    let (_, retained) =
        RetainedSession::adopt(session.suspend(), KnownOperations::Complete(&known[..4]))
            .err()
            .unwrap();
    let mut recreated =
        RetainedSession::adopt(retained, KnownOperations::Complete(&known)).unwrap();
    let mut backend = NoEffects::default();
    assert_eq!(
        refused(&mut recreated, &mut backend, "new-root", 3, Ok(u64::MAX)),
        Err(Failure::BudgetExhausted)
    );
    assert_eq!(backend.calls, 0);
    assert_eq!(recreated.charged(), limit);
    audit.push_str(&format!("partial external authored removal: candidate removed, prepared retained; refund=0\nfailed recovery constructed=32; manifest constructed=16; final cumulative charge={limit}; exact complete set adopted; next operation refused before backend effects\nNo storage profile/admission, reservation, allocation quota or durable global accounting is asserted.\n"));
    fs::write(evidence.join("audit.private.txt"), audit).unwrap();
}

#[test]
fn actual_selected_windows_seam_uses_its_own_parent_advisory() {
    let evidence = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join(".local")
        .join("work-wave-20261017a")
        .join(format!(
            "173-seam-{}-{}",
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
    let amount = 3 + 9 * MAX_RECORD_BYTES;
    let mut session = RetainedSession::start(amount, KnownOperations::Complete(&[])).unwrap();
    let mut backend = WindowsBackend::new(&source, &root);
    let result = session
        .run_windows(
            key("selected-native"),
            &mut backend,
            ValidatedCandidate {
                operation: "selected-native",
                format_revision: "authored-resource-v1",
                source: &mut Cursor::new(b"abc"),
                planned_len: 3,
                max_len: 3,
                output: ExpectedAbsent("output.bin"),
            },
            &Cancellation::default(),
        )
        .unwrap();
    fs::write(
        evidence.join("outcome.private.txt"),
        format!("{result:?}\n"),
    )
    .unwrap();
    assert!(
        result.protocol_complete,
        "actual selected native seam: {result:?}"
    );
    assert_eq!(fs::read(root.join("output.bin")).unwrap(), b"abc");
    assert_eq!(session.charged(), amount);
}
