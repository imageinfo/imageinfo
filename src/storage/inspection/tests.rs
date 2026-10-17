use super::*;

fn field(out: &mut Vec<u8>, value: &[u8]) {
    out.extend_from_slice(&(value.len() as u32).to_le_bytes());
    out.extend_from_slice(value);
}
fn spec() -> InspectionSpec<'static> {
    InspectionSpec {
        operation: "170-authored-inspection",
        format_revision: "authored-marker-v1",
        output: "output.bin",
        candidate_len: 27,
    }
}
fn encoded(kind: Artifact, bindings: &[Binding]) -> Vec<u8> {
    let spec = spec();
    let mut out = Vec::new();
    for text in [
        PROTOCOL,
        PROFILE,
        IMPLEMENTATION,
        spec.operation,
        spec.format_revision,
        spec.output,
        kind.leaf(),
    ] {
        field(&mut out, text.as_bytes());
    }
    field(&mut out, &spec.candidate_len.to_le_bytes());
    for binding in bindings {
        field(&mut out, &binding.identity);
        field(&mut out, &binding.facts);
    }
    let index = ORDER.iter().position(|v| *v == kind).unwrap();
    for text in &PRIOR_PHASES[..[5, 9, 20, 24][index]] {
        field(&mut out, text.as_bytes());
    }
    out
}

#[test]
fn exact_parser_checks_every_truncation_and_trailing_field() {
    for (index, kind) in ORDER.iter().enumerate() {
        let bindings: Vec<_> = (0..3 + index)
            .map(|n| Binding {
                identity: vec![n as u8],
                facts: vec![n as u8, 9],
            })
            .collect();
        let bytes = encoded(*kind, &bindings);
        assert_eq!(parse(&bytes, *kind, &spec()).unwrap().len(), 3 + index);
        for length in 0..bytes.len() {
            assert!(
                parse(&bytes[..length], *kind, &spec()).is_err(),
                "{kind:?} {length}"
            );
        }
        let mut extra = bytes.clone();
        field(&mut extra, b"ReceiptFlushed");
        assert!(parse(&extra, *kind, &spec()).is_err());
        let mut wrong = bytes;
        wrong[4] ^= 1;
        assert!(parse(&wrong, *kind, &spec()).is_err());
    }
}

#[test]
fn parser_refuses_forged_lengths_aliases_revisions_and_deterministic_fuzz() {
    let bindings = vec![
        Binding {
            identity: vec![1],
            facts: vec![2]
        };
        3
    ];
    assert!(
        parse(
            &encoded(Artifact::Prepared, &bindings),
            Artifact::Prepared,
            &spec()
        )
        .is_err()
    );
    let mut seed = 0x1700_2026u64;
    for length in 0..2048 {
        let mut bytes = vec![0; length];
        for byte in &mut bytes {
            seed ^= seed << 13;
            seed ^= seed >> 7;
            seed ^= seed << 17;
            *byte = seed as u8;
        }
        assert!(parse(&bytes, Artifact::Receipt, &spec()).is_err());
    }
    assert!(
        parse(
            &vec![0; MAX_RECORD_BYTES as usize + 1],
            Artifact::Receipt,
            &spec()
        )
        .is_err()
    );
    for length in [0u32, 257, 8193, u32::MAX] {
        assert!(parse(&length.to_le_bytes(), Artifact::Prepared, &spec()).is_err());
    }
    // Start from a complete deep record, not only random invalid headers. Every
    // length word is independently forged; all field/count bounds must refuse.
    let bindings: Vec<_> = (0..6)
        .map(|n| Binding {
            identity: vec![n],
            facts: vec![9],
        })
        .collect();
    let valid = encoded(Artifact::Receipt, &bindings);
    let mut position = 0;
    while position < valid.len() {
        let length = u32::from_le_bytes(valid[position..position + 4].try_into().unwrap()) as usize;
        let mut forged = valid.clone();
        forged[position..position + 4].copy_from_slice(&u32::MAX.to_le_bytes());
        assert!(parse(&forged, Artifact::Receipt, &spec()).is_err());
        position += 4 + length;
    }
}

#[cfg(windows)]
mod windows {
    use super::*;
    use crate::storage::custody::{CurrentCallerHistory, TrustedCurrentCaller};
    use crate::storage::runtime::{Backend, ExpectedAbsent, ValidatedCandidate, execute};
    use crate::storage::windows::{WindowsBackend, run};
    use crate::storage::{Cancellation, LogicalBudget};
    use imageinfo_windows_storage::{ExistingRoot, GuardedSource, MAX_ARTIFACT_BYTES};
    use sha2::{Digest, Sha256};
    use std::{
        fs,
        io::Cursor,
        os::windows::fs::MetadataExt,
        path::PathBuf,
        sync::atomic::{AtomicU64, Ordering},
        time::{SystemTime, UNIX_EPOCH},
    };

    static NEXT: AtomicU64 = AtomicU64::new(0);
    const SOURCE: &[u8] = b"170 authored protected original";
    const CANDIDATE: &[u8] = b"170 authored new candidate!";

    /// Test controller stops the actual runtime before it creates any receipt.
    /// Every earlier check/flush/publication call executes on the native backend.
    struct StopBeforeReceipt<'a>(&'a mut WindowsBackend);
    impl Backend for StopBeforeReceipt<'_> {
        fn profile(&self) -> &'static str {
            self.0.profile()
        }
        fn implementation(&self) -> &'static str {
            self.0.implementation()
        }
        fn preflight(&mut self, output: &str) -> Result<Binding, crate::storage::Failure> {
            self.0.preflight(output)
        }
        fn create_root(&mut self) -> Result<Binding, crate::storage::Failure> {
            self.0.create_root()
        }
        fn create(
            &mut self,
            kind: Artifact,
            bytes: &[u8],
        ) -> Result<Binding, crate::storage::Failure> {
            if kind == Artifact::Receipt {
                return Err(crate::storage::Failure::Cancelled);
            }
            self.0.create(kind, bytes)
        }
        fn check(
            &mut self,
            phase: crate::storage::Phase,
            bindings: &[Binding],
        ) -> Result<(), crate::storage::Failure> {
            self.0.check(phase, bindings)
        }
        fn flush_file(&mut self, kind: Artifact) -> Result<(), crate::storage::Failure> {
            self.0.flush_file(kind)
        }
        fn flush_root(&mut self) -> Result<(), crate::storage::Failure> {
            self.0.flush_root()
        }
        fn flush_parent(&mut self) -> Result<(), crate::storage::Failure> {
            self.0.flush_parent()
        }
        fn publish(&mut self, output: &str) -> Result<(), crate::storage::Failure> {
            self.0.publish(output)
        }
        fn caller_release(&mut self, bindings: &[Binding]) -> Result<(), crate::storage::Failure> {
            self.0.caller_release(bindings)
        }
        fn checked_context(&mut self, bindings: &[Binding]) -> Result<(), crate::storage::Failure> {
            self.0.checked_context(bindings)
        }
        fn export_terminal(&mut self, bindings: &[Binding]) -> Result<(), crate::storage::Failure> {
            self.0.export_terminal(bindings)
        }
    }
    struct Fixture {
        evidence: PathBuf,
        source: PathBuf,
        root: PathBuf,
        expected: CurrentBindings,
    }
    fn directory(label: &str) -> PathBuf {
        let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join(".local")
            .join("work-wave-20261017a")
            .join(format!(
                "170-{label}-{}-{}-{}",
                std::process::id(),
                SystemTime::now()
                    .duration_since(UNIX_EPOCH)
                    .unwrap()
                    .as_nanos(),
                NEXT.fetch_add(1, Ordering::Relaxed)
            ));
        fs::create_dir_all(&path).unwrap();
        path
    }
    fn fixture(label: &str, records: usize) -> Fixture {
        assert_eq!(CANDIDATE.len() as u64, spec().candidate_len);
        let evidence = directory(label);
        let source = evidence.join("source.bin");
        let root = evidence.join("unit");
        fs::write(&source, SOURCE).unwrap();
        let mut backend = WindowsBackend::new(&source, &root);
        if records >= 3 {
            let mut bytes = Cursor::new(CANDIDATE);
            let request = ValidatedCandidate {
                operation: spec().operation,
                format_revision: spec().format_revision,
                source: &mut bytes,
                planned_len: CANDIDATE.len() as u64,
                max_len: CANDIDATE.len() as u64,
                output: ExpectedAbsent(spec().output),
            };
            let mut budget = LogicalBudget::new(1_000_000);
            let cancel = Cancellation::default();
            let result = if records == 4 {
                run(&mut backend, request, &mut budget, &cancel)
            } else {
                execute(
                    &mut StopBeforeReceipt(&mut backend),
                    request,
                    &mut budget,
                    &cancel,
                )
            };
            if records == 4 {
                assert!(
                    result.protocol_complete,
                    "actual native control must complete: {result:?}"
                );
            } else {
                assert_eq!(result.phase, crate::storage::Phase::ReceiptCreated);
                assert_eq!(result.status, crate::storage::Status::RecoveryRequired);
                assert_eq!(result.failure, Some(crate::storage::Failure::Cancelled));
                assert!(result.publication_possible && result.release_possible);
                assert!(!result.protocol_complete);
                assert!(!root.join(Artifact::Receipt.leaf()).exists());
            }
            assert_ne!(result.status, crate::storage::Status::Committed);
        } else {
            let mut bindings = vec![
                backend.preflight(spec().output).unwrap(),
                backend.create_root().unwrap(),
            ];
            bindings.push(backend.create(Artifact::Candidate, CANDIDATE).unwrap());
            for kind in &ORDER[..records] {
                let bytes = encoded(*kind, &bindings);
                bindings.push(backend.create(*kind, &bytes).unwrap());
            }
        }
        let expected = backend.custody_snapshot(spec().operation).unwrap();
        drop(backend);
        Fixture {
            evidence,
            source,
            root,
            expected,
        }
    }

    // Independent file inventory uses ordinary read handles/metadata plus a
    // separately captured full held snapshot. Directory write time is audited
    // too: read-only inspection has no namespace writes to excuse a change.
    type AuditedFile = (
        same_file::Handle,
        PathBuf,
        Vec<u8>,
        u64,
        u32,
        u64,
        u64,
        Option<imageinfo_windows_storage::FileSnapshot>,
    );
    #[derive(Debug, PartialEq, Eq)]
    struct Inventory {
        names: Vec<String>,
        files: Vec<AuditedFile>,
        root: imageinfo_windows_storage::FileSnapshot,
        parent: imageinfo_windows_storage::FileSnapshot,
    }
    fn inventory(f: &Fixture) -> Inventory {
        let root = ExistingRoot::open(&f.root).unwrap();
        let root_snapshot = root.snapshot().clone();
        let parent = root.parent_snapshot().clone();
        drop(root);
        let mut paths: Vec<_> = fs::read_dir(&f.root)
            .unwrap()
            .map(|e| e.unwrap().path())
            .collect();
        paths.sort();
        let names = paths
            .iter()
            .map(|p| p.file_name().unwrap().to_string_lossy().into_owned())
            .collect();
        paths.push(f.source.clone());
        let files = paths
            .into_iter()
            .map(|path| {
                let bytes = fs::read(&path).unwrap();
                let metadata = fs::metadata(&path).unwrap();
                let snapshot = GuardedSource::open(&path, MAX_ARTIFACT_BYTES)
                    .ok()
                    .map(|g| g.snapshot().clone());
                (
                    same_file::Handle::from_path(&path).unwrap(),
                    path,
                    Sha256::digest(&bytes).to_vec(),
                    metadata.len(),
                    metadata.file_attributes(),
                    metadata.creation_time(),
                    metadata.last_write_time(),
                    snapshot,
                )
            })
            .collect();
        Inventory {
            names,
            files,
            root: root_snapshot,
            parent,
        }
    }
    fn check_unchanged(f: &Fixture, operation: impl FnOnce()) {
        let before = inventory(f);
        operation();
        let after = inventory(f);
        assert_eq!(before, after);
        assert_eq!(fs::read(&f.source).unwrap(), SOURCE);
        fs::write(f.evidence.join("inspection-audit.private.txt"), "Independent before/after names, hashes, held identity/properties and directory properties matched; source preserved.\n").unwrap();
    }
    fn authorized(
        f: &Fixture,
        action: RestartAction,
        history: CurrentCallerHistory,
        operation: impl FnOnce(&mut Inspection, ActionAuthority),
    ) {
        let mut inspection = Inspection::collect(&f.source, &f.root, &spec()).unwrap();
        let mut caller = TrustedCurrentCaller::new();
        caller.attest_current(f.expected.clone(), history).unwrap();
        let authority = caller.authorize(action, inspection.bindings()).unwrap();
        operation(&mut inspection, authority);
    }

    #[test]
    fn actual_native_complete_receipt_requires_independent_current_authority() {
        let f = fixture("complete", 4);
        check_unchanged(&f, || {
            authorized(
                &f,
                RestartAction::RecognizeCompletion,
                CurrentCallerHistory::TerminalCompletionAndStopped,
                |inspection, authority| {
                    assert_eq!(
                        inspection.classify(RestartAction::RecognizeCompletion, authority),
                        Ok(Survivor::PreviouslyCompleted)
                    );
                },
            );
            authorized(
                &f,
                RestartAction::FinalizeExisting,
                CurrentCallerHistory::ReleasedAndStopped,
                |inspection, authority| {
                    assert_eq!(
                        inspection.classify(RestartAction::FinalizeExisting, authority),
                        Ok(Survivor::RecoverableInstalled)
                    );
                },
            );
            let inspection = Inspection::collect(&f.source, &f.root, &spec()).unwrap();
            let mut caller = TrustedCurrentCaller::new();
            assert!(
                caller
                    .authorize(RestartAction::RecognizeCompletion, inspection.bindings())
                    .is_err()
            );
        });
    }

    #[test]
    fn actual_native_stopped_unpublished_is_expected_absent_only() {
        for count in [1, 2] {
            let f = fixture("unpublished", count);
            check_unchanged(&f, || {
                authorized(
                    &f,
                    RestartAction::PruneUnpublished,
                    CurrentCallerHistory::StoppedBeforeRelease,
                    |inspection, authority| {
                        assert_eq!(
                            inspection.classify(RestartAction::PruneUnpublished, authority),
                            Ok(Survivor::ExpectedAbsent)
                        );
                    },
                )
            });
            assert!(f.root.join(Artifact::Candidate.leaf()).exists());
            assert!(!f.root.join(spec().output).exists());
        }
    }

    #[test]
    fn actual_native_all_record_truncations_missing_torn_and_extra_are_retained() {
        for kind in ORDER {
            let f = fixture("truncated", 4);
            let path = f.root.join(kind.leaf());
            let bytes = fs::read(&path).unwrap();
            fs::write(&path, &bytes[..bytes.len() / 2]).unwrap();
            check_unchanged(&f, || {
                assert!(Inspection::collect(&f.source, &f.root, &spec()).is_err())
            });
            let f = fixture("missing", 4);
            fs::remove_file(f.root.join(kind.leaf())).unwrap();
            check_unchanged(&f, || {
                if let Ok(inspection) = Inspection::collect(&f.source, &f.root, &spec()) {
                    let mut caller = TrustedCurrentCaller::new();
                    caller
                        .attest_current(
                            f.expected.clone(),
                            CurrentCallerHistory::ReleasedAndStopped,
                        )
                        .unwrap();
                    assert!(
                        caller
                            .authorize(RestartAction::FinalizeExisting, inspection.bindings())
                            .is_err()
                    );
                }
            });
        }
        for variant in ["extra", "torn", "empty", "over-bound", "foreign-record"] {
            let f = fixture(variant, 4);
            let receipt = f.root.join(Artifact::Receipt.leaf());
            match variant {
                "extra" => {
                    fs::write(f.root.join("foreign.bin"), b"retained foreign entry").unwrap()
                }
                "torn" => {
                    let mut bytes = fs::read(&receipt).unwrap();
                    bytes.extend_from_slice(b"torn");
                    fs::write(receipt, bytes).unwrap();
                }
                "empty" => fs::write(receipt, []).unwrap(),
                "over-bound" => fs::write(receipt, vec![0; MAX_RECORD_BYTES as usize + 1]).unwrap(),
                "foreign-record" => fs::write(receipt, b"foreign retained receipt").unwrap(),
                _ => unreachable!(),
            }
            check_unchanged(&f, || {
                assert!(Inspection::collect(&f.source, &f.root, &spec()).is_err())
            });
        }
    }

    #[test]
    fn actual_native_owner_edits_foreign_bindings_aliases_and_missing_output_refuse() {
        for variant in [
            "edited",
            "readonly",
            "foreign-same-bytes",
            "alias",
            "missing-output",
            "both-names",
        ] {
            let f = fixture(variant, 4);
            let output = f.root.join(spec().output);
            match variant {
                "edited" => fs::write(&output, b"later ordinary owner edit").unwrap(),
                "readonly" => {
                    let mut permissions = fs::metadata(&output).unwrap().permissions();
                    permissions.set_readonly(true);
                    fs::set_permissions(&output, permissions).unwrap();
                }
                "foreign-same-bytes" => {
                    fs::rename(&output, f.evidence.join("retained-original-output.bin")).unwrap();
                    fs::write(&output, CANDIDATE).unwrap();
                }
                "alias" => fs::hard_link(&f.source, f.evidence.join("outside-alias.bin")).unwrap(),
                "missing-output" => {
                    fs::rename(&output, f.evidence.join("retained-missing-output.bin")).unwrap()
                }
                "both-names" => {
                    fs::write(f.root.join(Artifact::Candidate.leaf()), CANDIDATE).unwrap()
                }
                _ => unreachable!(),
            }
            check_unchanged(&f, || {
                assert!(Inspection::collect(&f.source, &f.root, &spec()).is_err())
            });
        }
    }

    #[test]
    fn actual_native_stale_authority_and_changes_under_inspection_fail_closed() {
        let f = fixture("stale", 4);
        check_unchanged(&f, || {
            let mut inspection = Inspection::collect(&f.source, &f.root, &spec()).unwrap();
            let mut caller = TrustedCurrentCaller::new();
            caller
                .attest_current(
                    f.expected.clone(),
                    CurrentCallerHistory::TerminalCompletionAndStopped,
                )
                .unwrap();
            let authority = caller
                .authorize(RestartAction::RecognizeCompletion, inspection.bindings())
                .unwrap();
            caller.revoke();
            assert_eq!(
                inspection.classify(RestartAction::RecognizeCompletion, authority),
                Err(InspectionFailure::Authority)
            );
        });
        let f = fixture("fresh-conflict", 4);
        let mut inspection = Inspection::collect(&f.source, &f.root, &spec()).unwrap();
        let output = f.root.join(spec().output);
        assert!(fs::write(&output, b"writer refused by held byte/name guard").is_err());
        let mut permissions = fs::metadata(&output).unwrap().permissions();
        permissions.set_readonly(true);
        fs::set_permissions(&output, permissions).unwrap();
        assert_eq!(inspection.recheck(), Err(InspectionFailure::Changed));
        assert_eq!(inspection.recheck(), Err(InspectionFailure::Changed));
        assert_eq!(fs::read(&f.source).unwrap(), SOURCE);
    }

    #[test]
    fn actual_native_installed_before_receipt_is_distinct_from_missing_bound_receipt() {
        let f = fixture("installed-before-receipt", 3);
        check_unchanged(&f, || {
            authorized(
                &f,
                RestartAction::FinalizeExisting,
                CurrentCallerHistory::ReleasedAndStopped,
                |inspection, authority| {
                    assert_eq!(
                        inspection.classify(RestartAction::FinalizeExisting, authority),
                        Ok(Survivor::RecoverableInstalled)
                    );
                },
            );
        });
        assert!(!f.root.join(Artifact::Receipt.leaf()).exists());
        assert_eq!(fs::read(f.root.join(spec().output)).unwrap(), CANDIDATE);

        // The same physical three-record shape cannot erase a previously bound
        // receipt. The independently retained four-record B makes it refuse.
        let f = fixture("lost-bound-receipt", 4);
        fs::remove_file(f.root.join(Artifact::Receipt.leaf())).unwrap();
        check_unchanged(&f, || {
            let inspection = Inspection::collect(&f.source, &f.root, &spec()).unwrap();
            let mut caller = TrustedCurrentCaller::new();
            caller
                .attest_current(f.expected.clone(), CurrentCallerHistory::ReleasedAndStopped)
                .unwrap();
            assert!(
                caller
                    .authorize(RestartAction::FinalizeExisting, inspection.bindings())
                    .is_err()
            );
        });
    }

    #[test]
    fn actual_native_namespace_failure_cannot_be_erased_by_actor_reversion() {
        // Two names plus a foreign entry exercises an exact namespace mismatch;
        // five names plus a foreign entry exercises bounded enumeration failure.
        for records in [1, 4] {
            let f = fixture("namespace-terminal", records);
            let (action, history) = if records == 1 {
                (
                    RestartAction::PruneUnpublished,
                    CurrentCallerHistory::StoppedBeforeRelease,
                )
            } else {
                (
                    RestartAction::RecognizeCompletion,
                    CurrentCallerHistory::TerminalCompletionAndStopped,
                )
            };
            let mut inspection = Inspection::collect(&f.source, &f.root, &spec()).unwrap();
            let mut caller = TrustedCurrentCaller::new();
            caller.attest_current(f.expected.clone(), history).unwrap();
            let authority = caller.authorize(action, inspection.bindings()).unwrap();
            let foreign = f.root.join("foreign.bin");
            fs::write(&foreign, b"authored foreign namespace actor").unwrap();
            assert_eq!(inspection.recheck(), Err(InspectionFailure::Namespace));
            // Only the explicit fixture actor removes its own extra file. The
            // inspector retains every original artifact and its first failure.
            fs::remove_file(foreign).unwrap();
            check_unchanged(&f, || {
                assert_eq!(inspection.recheck(), Err(InspectionFailure::Namespace));
                assert_eq!(inspection.bindings(), &f.expected);
                assert_eq!(
                    inspection.classify(action, authority),
                    Err(InspectionFailure::Namespace)
                );
            });
            // An explicitly new check interval is possible, but never resets or
            // reuses the poisoned inspector or its consumed authority token.
            assert!(Inspection::collect(&f.source, &f.root, &spec()).is_ok());
        }
    }

    #[test]
    fn actual_native_preexisting_writer_and_source_edit_are_retained() {
        use std::os::windows::fs::OpenOptionsExt;
        let f = fixture("inaccessible", 4);
        let writer = fs::OpenOptions::new()
            .read(true)
            .write(true)
            .share_mode(7)
            .open(f.root.join(spec().output))
            .unwrap();
        check_unchanged(&f, || {
            assert!(Inspection::collect(&f.source, &f.root, &spec()).is_err())
        });
        drop(writer);
        let f = fixture("source-edit", 4);
        fs::write(&f.source, b"later authored source content").unwrap();
        let before = inventory(&f);
        assert!(Inspection::collect(&f.source, &f.root, &spec()).is_err());
        assert_eq!(before, inventory(&f));
        assert_eq!(
            fs::read(f.source).unwrap(),
            b"later authored source content"
        );
    }
}
