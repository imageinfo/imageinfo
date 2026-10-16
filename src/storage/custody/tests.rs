use super::*;

fn authored(published: bool) -> CurrentBindings {
    let binding = |n| Binding {
        identity: vec![n],
        facts: vec![n, 8],
    };
    let records = vec![(Artifact::Prepared, vec![5]), (Artifact::Intent, vec![6])];
    CurrentBindings::capture(
        "authored-operation",
        "authored-profile",
        "authored-implementation",
        "output.bin",
        &binding(9),
        &(1..=5).map(binding).collect::<Vec<_>>(),
        &records,
        published,
    )
    .unwrap()
}

#[test]
fn observations_and_new_callers_have_no_authority() {
    let observed = authored(false);
    let mut caller = TrustedCurrentCaller::new();
    assert!(matches!(
        caller.authorize(RestartAction::PruneUnpublished, &observed),
        Err(CustodyRefusal::MissingAuthority)
    ));
    // Possession of exact root, bytes, records and digests never calls attest.
    let imported = observed.clone();
    assert!(matches!(
        TrustedCurrentCaller::new().authorize(RestartAction::PruneUnpublished, &imported),
        Err(CustodyRefusal::MissingAuthority)
    ));
}

#[test]
fn explicit_current_authority_selects_only_one_exact_action() {
    let observed = authored(false);
    let mut caller = TrustedCurrentCaller::new();
    caller
        .attest_current(observed.clone(), CurrentCallerHistory::StoppedBeforeRelease)
        .unwrap();
    let authority = caller
        .authorize(RestartAction::PruneUnpublished, &observed)
        .unwrap();
    authority
        .validate(RestartAction::PruneUnpublished, &observed)
        .unwrap();
    assert!(matches!(
        caller.authorize(RestartAction::PruneUnpublished, &observed),
        Err(CustodyRefusal::MissingAuthority)
    ));
    let published = authored(true);
    caller
        .attest_current(published.clone(), CurrentCallerHistory::ReleasedAndStopped)
        .unwrap();
    assert!(matches!(
        caller.authorize(RestartAction::RecognizeCompletion, &published),
        Err(CustodyRefusal::ActionNotAuthorized)
    ));
    caller
        .attest_current(published.clone(), CurrentCallerHistory::ReleasedAndStopped)
        .unwrap();
    caller
        .authorize(RestartAction::FinalizeExisting, &published)
        .unwrap()
        .validate(RestartAction::FinalizeExisting, &published)
        .unwrap();
    caller
        .attest_current(
            published.clone(),
            CurrentCallerHistory::TerminalCompletionAndStopped,
        )
        .unwrap();
    caller
        .authorize(RestartAction::RecognizeCompletion, &published)
        .unwrap()
        .validate(RestartAction::RecognizeCompletion, &published)
        .unwrap();
}

#[test]
fn replacement_close_and_renewal_revoke_old_capabilities() {
    let observed = authored(false);
    let mut caller = TrustedCurrentCaller::new();
    caller
        .attest_current(observed.clone(), CurrentCallerHistory::StoppedBeforeRelease)
        .unwrap();
    let old = caller
        .authorize(RestartAction::PruneUnpublished, &observed)
        .unwrap();
    caller
        .attest_current(observed.clone(), CurrentCallerHistory::StoppedBeforeRelease)
        .unwrap();
    assert_eq!(
        old.validate(RestartAction::PruneUnpublished, &observed),
        Err(CustodyRefusal::StaleAuthority)
    );
    let closed = caller
        .authorize(RestartAction::PruneUnpublished, &observed)
        .unwrap();
    drop(caller);
    assert_eq!(
        closed.validate(RestartAction::PruneUnpublished, &observed),
        Err(CustodyRefusal::StaleAuthority)
    );
    assert!(matches!(
        TrustedCurrentCaller::new().authorize(RestartAction::PruneUnpublished, &observed),
        Err(CustodyRefusal::MissingAuthority)
    ));
}

#[test]
fn changed_same_byte_replaced_rolled_back_and_unknown_bindings_refuse() {
    let original = authored(false);
    let mut variants = Vec::new();
    let mut changed = original.clone();
    changed.bindings[0].facts.push(1);
    variants.push((changed, CustodyRefusal::ChangedBindings));
    let mut changed = original.clone();
    changed.bindings[3].identity.push(1);
    variants.push((changed, CustodyRefusal::ChangedBindings));
    let mut changed = original.clone();
    changed.records[0].1.push(1);
    variants.push((changed, CustodyRefusal::ChangedBindings));
    let mut changed = original.clone();
    changed.parent.identity.push(1);
    variants.push((changed, CustodyRefusal::ChangedBindings));
    let mut changed = original.clone();
    changed.output.push('x');
    variants.push((changed, CustodyRefusal::ChangedBindings));
    let mut changed = original.clone();
    changed.bindings[1].identity.push(1);
    variants.push((changed, CustodyRefusal::UnknownRoot));
    let mut changed = original.clone();
    changed.operation.push('x');
    variants.push((changed, CustodyRefusal::UnknownRoot));
    for (changed, refusal) in variants {
        let mut caller = TrustedCurrentCaller::new();
        caller
            .attest_current(original.clone(), CurrentCallerHistory::StoppedBeforeRelease)
            .unwrap();
        assert!(
            matches!(caller.authorize(RestartAction::PruneUnpublished, &changed), Err(e) if e == refusal)
        );
        // Replacing the edited material with the old matching bytes cannot
        // revive a decision already consumed by a contradictory fresh check.
        assert!(matches!(
            caller.authorize(RestartAction::PruneUnpublished, &original),
            Err(CustodyRefusal::MissingAuthority)
        ));
    }
}

#[test]
fn contradictory_history_and_all_constructions_are_bounded() {
    let mut caller = TrustedCurrentCaller::new();
    assert_eq!(
        caller.attest_current(authored(true), CurrentCallerHistory::StoppedBeforeRelease),
        Err(CustodyRefusal::ContradictoryHistory)
    );
    assert_eq!(
        caller.attest_current(authored(false), CurrentCallerHistory::Contradictory),
        Err(CustodyRefusal::ContradictoryHistory)
    );
    for _ in 0..2 {
        caller
            .attest_current(authored(false), CurrentCallerHistory::StoppedBeforeRelease)
            .unwrap();
    }
    assert_eq!(
        caller.attest_current(authored(false), CurrentCallerHistory::StoppedBeforeRelease),
        Err(CustodyRefusal::ConstructionBound)
    );
    let b = authored(false);
    assert!(b.save_bytes(SaveKind::Captured).len() <= MAX_RECORD_BYTES as usize);
    let mut records = b.records.clone();
    records[0].1 = vec![0; MAX_RECORD_BYTES as usize];
    assert_eq!(
        CurrentBindings::capture(
            &b.operation,
            &b.profile,
            &b.implementation,
            &b.output,
            &b.parent,
            &b.bindings,
            &records,
            false
        ),
        Err(CustodyRefusal::ConstructionBound)
    );
    let mut duplicate = b.bindings.clone();
    duplicate[4] = duplicate[0].clone();
    assert_eq!(
        CurrentBindings::capture(
            &b.operation,
            &b.profile,
            &b.implementation,
            &b.output,
            &b.parent,
            &duplicate,
            &b.records,
            false
        ),
        Err(CustodyRefusal::InvalidBindings)
    );
}

#[test]
fn borrowed_capture_counts_parent_before_copying_any_record_payload() {
    let observed = authored(false);
    let mut records = observed.records.clone();
    fn views(records: &[(Artifact, Vec<u8>)]) -> Vec<(Artifact, &[u8])> {
        records
            .iter()
            .map(|(kind, bytes)| (*kind, bytes.as_slice()))
            .collect::<Vec<_>>()
    }
    let base = CurrentBindings::preflight_borrowed(
        &observed.operation,
        &observed.profile,
        &observed.implementation,
        &observed.output,
        &observed.parent,
        &observed.bindings,
        &views(&records),
        false,
    )
    .unwrap();
    let parent_bytes = 16 + observed.parent.identity.len() + observed.parent.facts.len();
    // This construction fits if the independent parent is incorrectly omitted,
    // and exceeds the complete capture ceiling by exactly one byte.
    records[0].1.resize(MAX_RECORD_BYTES as usize - base + 2, 3);
    assert!(base - 1 + records[0].1.len() - parent_bytes <= MAX_RECORD_BYTES as usize);
    COPIED_RECORD_BYTES.with(|count| count.set(0));
    assert_eq!(
        CurrentBindings::capture_borrowed(
            &observed.operation,
            &observed.profile,
            &observed.implementation,
            &observed.output,
            &observed.parent,
            &observed.bindings,
            &views(&records),
            false,
        ),
        Err(CustodyRefusal::ConstructionBound)
    );
    COPIED_RECORD_BYTES.with(|count| assert_eq!(count.get(), 0));
    // Positive control demonstrates the byte-copy observer actually runs when
    // an aggregate is admitted, instead of merely observing a constant zero.
    let admitted = authored(false);
    COPIED_RECORD_BYTES.with(|count| {
        assert_eq!(
            count.get(),
            admitted
                .records
                .iter()
                .map(|(_, bytes)| bytes.len())
                .sum::<usize>()
        )
    });
}

#[cfg(windows)]
mod native {
    use super::*;
    use crate::storage::runtime::{
        self, Backend, ExpectedAbsent, LiveEvidence, ValidatedCandidate,
    };
    use crate::storage::windows::WindowsBackend;
    use crate::storage::{Cancellation, Failure, LogicalBudget, Phase};
    use sha2::{Digest, Sha256};
    use std::fs;
    use std::io::Cursor;
    use std::io::{BufRead, Read, Write};
    use std::path::PathBuf;
    use std::process::{Command, Stdio};
    use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

    const WORKER_TEST: &str = "storage::custody::tests::native::native_worker_process";
    const OPERATION: &str = "custody169-native-operation";
    const PREFIX: &str = "CUSTODY169 ";

    fn path(label: &str) -> PathBuf {
        let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join(".local")
            .join("work-wave-20261016e")
            .join(format!(
                "169-{label}-{}-{}",
                std::process::id(),
                SystemTime::now()
                    .duration_since(UNIX_EPOCH)
                    .unwrap()
                    .as_nanos()
            ));
        fs::create_dir_all(&root).unwrap();
        root
    }

    // Only the integration fixture has an observation decoder. It has no
    // authority field, and only reads the original owned child's private pipe.
    fn wire(bindings: &CurrentBindings) -> Vec<u8> {
        let pair = |b: &Binding| serde_json::json!([b.identity, b.facts]);
        let value = serde_json::json!({"operation":bindings.operation, "profile":bindings.profile,
            "implementation":bindings.implementation, "output":bindings.output,
            "parent":pair(&bindings.parent), "bindings":bindings.bindings.iter().map(pair).collect::<Vec<_>>(),
            "records":bindings.records.iter().map(|(_,b)| b).collect::<Vec<_>>(), "published":bindings.published});
        let bytes = serde_json::to_vec(&value).unwrap();
        assert!(bytes.len() <= MAX_RECORD_BYTES as usize);
        bytes
    }

    fn notice(child: &mut Child) -> Result<CurrentBindings, CustodyRefusal> {
        // Ignore only the finite test harness prefix, not arbitrary output.
        let stdout = child.stdout.as_mut().ok_or(CustodyRefusal::WorkerIo)?;
        let mut prefix_bytes = 0;
        loop {
            let mut bytes = Vec::new();
            for _ in 0..=MAX_RECORD_BYTES {
                let mut one = [0];
                stdout
                    .read_exact(&mut one)
                    .map_err(|_| CustodyRefusal::WorkerIo)?;
                if one[0] == b'\n' {
                    break;
                }
                bytes.push(one[0]);
            }
            if bytes.len() > MAX_RECORD_BYTES as usize {
                return Err(CustodyRefusal::ConstructionBound);
            }
            let Some(bytes) = bytes.strip_prefix(PREFIX.as_bytes()) else {
                prefix_bytes += bytes.len();
                if prefix_bytes > 512 {
                    return Err(CustodyRefusal::ConstructionBound);
                }
                continue;
            };
            let value: serde_json::Value =
                serde_json::from_slice(bytes).map_err(|_| CustodyRefusal::InvalidBindings)?;
            let pair = |v: &serde_json::Value| -> Binding {
                Binding {
                    identity: serde_json::from_value(v[0].clone()).unwrap(),
                    facts: serde_json::from_value(v[1].clone()).unwrap(),
                }
            };
            let bindings: Vec<_> = value["bindings"]
                .as_array()
                .unwrap()
                .iter()
                .map(pair)
                .collect();
            let records: Vec<_> = value["records"]
                .as_array()
                .unwrap()
                .iter()
                .zip([
                    Artifact::Prepared,
                    Artifact::Intent,
                    Artifact::Observation,
                    Artifact::Receipt,
                ])
                .map(|(v, kind)| (kind, serde_json::from_value(v.clone()).unwrap()))
                .collect();
            return CurrentBindings::capture(
                value["operation"].as_str().unwrap(),
                value["profile"].as_str().unwrap(),
                value["implementation"].as_str().unwrap(),
                value["output"].as_str().unwrap(),
                &pair(&value["parent"]),
                &bindings,
                &records,
                value["published"].as_bool().unwrap(),
            );
        }
    }

    fn emit(bindings: &CurrentBindings) {
        let mut out = std::io::stdout().lock();
        out.write_all(PREFIX.as_bytes()).unwrap();
        out.write_all(&wire(bindings)).unwrap();
        out.write_all(b"\n").unwrap();
        out.flush().unwrap();
    }

    struct WorkerBackend {
        inner: WindowsBackend,
        roots: u8,
    }
    impl Backend for WorkerBackend {
        fn profile(&self) -> &'static str {
            self.inner.profile()
        }
        fn implementation(&self) -> &'static str {
            self.inner.implementation()
        }
        fn preflight(&mut self, output: &str) -> Result<Binding, Failure> {
            self.inner.preflight(output)
        }
        fn create_root(&mut self) -> Result<Binding, Failure> {
            self.inner.create_root()
        }
        fn create(&mut self, a: Artifact, b: &[u8]) -> Result<Binding, Failure> {
            self.inner.create(a, b)
        }
        fn check(&mut self, p: Phase, b: &[Binding]) -> Result<(), Failure> {
            self.inner.check(p, b)
        }
        fn flush_file(&mut self, a: Artifact) -> Result<(), Failure> {
            self.inner.flush_file(a)
        }
        fn flush_root(&mut self) -> Result<(), Failure> {
            self.inner.flush_root()?;
            self.roots += 1;
            if self.roots == 4 {
                // Actual intent/root flush has succeeded, while runtime has
                // not yet begun CallerRelease or any publication attempt.
                emit(&self.inner.custody_snapshot(OPERATION)?);
                let mut command = String::new();
                std::io::stdin()
                    .lock()
                    .take(32)
                    .read_line(&mut command)
                    .map_err(|_| Failure::CallerHistory)?;
                if command != "continue\n" {
                    return Err(Failure::CallerHistory);
                }
            }
            Ok(())
        }
        fn flush_parent(&mut self) -> Result<(), Failure> {
            self.inner.flush_parent()
        }
        fn publish(&mut self, o: &str) -> Result<(), Failure> {
            self.inner.publish(o)
        }
        fn caller_release(&mut self, b: &[Binding]) -> Result<(), Failure> {
            self.inner.caller_release(b)
        }
        fn checked_context(&mut self, b: &[Binding]) -> Result<(), Failure> {
            self.inner.checked_context(b)
        }
        fn export_terminal(&mut self, b: &[Binding]) -> Result<(), Failure> {
            self.inner.export_terminal(b)
        }
        fn retain_live_evidence(&mut self, e: &LiveEvidence) {
            self.inner.retain_live_evidence(e);
        }
    }

    #[test]
    #[ignore = "dedicated actual owned-process fixture, invoked only by integration tests"]
    fn native_worker_process() {
        let base = PathBuf::from(
            std::env::var_os("IMAGEINFO_CUSTODY169_ROOT").expect("owned worker root"),
        );
        let mut backend = WorkerBackend {
            inner: WindowsBackend::new(&base.join("source.bin"), &base.join("unit")),
            roots: 0,
        };
        let mut bytes = Cursor::new(b"authored derivative".as_slice());
        let request = ValidatedCandidate {
            operation: OPERATION,
            format_revision: "custody169-authored-v1",
            source: &mut bytes,
            planned_len: 19,
            max_len: 19,
            output: ExpectedAbsent("output.bin"),
        };
        let result = runtime::execute(
            &mut backend,
            request,
            &mut LogicalBudget::new(1_000_000),
            &Cancellation::default(),
        );
        fs::write(
            base.join("worker-result.private.txt"),
            format!("{result:?}\n"),
        )
        .unwrap();
        assert!(
            result.protocol_complete,
            "actual native worker did not complete"
        );
        emit(&backend.inner.custody_snapshot(OPERATION).unwrap());
    }

    fn worker(base: &std::path::Path) -> OwnedWorker {
        if !base.join("source.bin").exists() {
            fs::write(base.join("source.bin"), b"authored source").unwrap();
        }
        let child = Command::new(std::env::current_exe().unwrap())
            .args(["--ignored", "--exact", WORKER_TEST, "--nocapture"])
            .env("IMAGEINFO_CUSTODY169_ROOT", base)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .spawn()
            .unwrap();
        OwnedWorker::new(child, OPERATION).unwrap()
    }

    fn save(base: &std::path::Path) -> impl FnOnce(SaveKind, &[u8]) -> io::Result<()> + '_ {
        |kind, bytes| {
            let path = base.join(format!("{kind:?}.caller.private"));
            let mut file = fs::OpenOptions::new()
                .create_new(true)
                .write(true)
                .open(path)?;
            file.write_all(bytes)?;
            file.sync_all()
        }
    }

    fn finish(worker: &mut OwnedWorker) {
        let until = Instant::now() + Duration::from_secs(10);
        loop {
            match worker.confirm_released_exit() {
                Ok(_) => break,
                Err(CustodyRefusal::WorkerRunning) if Instant::now() < until => {
                    std::thread::sleep(Duration::from_millis(10))
                }
                other => panic!("owned worker exit failed: {other:?}"),
            }
        }
    }

    fn file_binding(path: &std::path::Path) -> Binding {
        let mut held =
            imageinfo_windows_storage::GuardedSource::open(path, MAX_RECORD_BYTES).unwrap();
        let bytes = held.read_exact_bytes().unwrap();
        let snap = held.snapshot();
        let mut facts = snap.binding_bytes();
        facts.extend_from_slice(&Sha256::digest(&bytes));
        Binding {
            identity: snap
                .volume_serial_number
                .to_le_bytes()
                .into_iter()
                .chain(snap.file_index.to_le_bytes())
                .collect(),
            facts,
        }
    }

    #[test]
    fn actual_native_aggregate_custody_bound_refuses_before_record_copy() {
        let base = path("aggregate-bound");
        let source = base.join("source.bin");
        fs::write(&source, b"authored source").unwrap();
        let mut backend = WindowsBackend::new(&source, &base.join("unit"));
        backend.preflight("output.bin").unwrap();
        backend.create_root().unwrap();
        backend
            .create(Artifact::Candidate, b"authored candidate")
            .unwrap();
        // Each actual held record is individually within its 64 KiB limit.
        // Together their payloads plus the exact bindings/parent cross the
        // separate 64 KiB caller-capture ceiling. No invalid input mock is used.
        let bytes = vec![b'r'; 16_000];
        for kind in [
            Artifact::Prepared,
            Artifact::Intent,
            Artifact::Observation,
            Artifact::Receipt,
        ] {
            backend.create(kind, &bytes).unwrap();
        }
        COPIED_RECORD_BYTES.with(|count| count.set(0));
        assert_eq!(
            backend.custody_snapshot(OPERATION),
            Err(Failure::RecordTooLarge)
        );
        COPIED_RECORD_BYTES.with(|count| assert_eq!(count.get(), 0));
        assert_eq!(fs::read(&source).unwrap(), b"authored source");
        for kind in [
            Artifact::Prepared,
            Artifact::Intent,
            Artifact::Observation,
            Artifact::Receipt,
        ] {
            assert_eq!(
                fs::read(base.join("unit").join(kind.leaf())).unwrap(),
                bytes
            );
        }
        assert!(!base.join("unit").join("output.bin").exists());
        fs::write(base.join("audit.private.txt"),
            "actual native four-record aggregate refused as RecordTooLarge before custody-owned payload copying; each held 16000-byte record remains unchanged; source/root/candidate retained; no authority or restart effect\n").unwrap();
    }

    #[test]
    fn actual_native_worker_stop_handoff_has_exact_binding_and_owned_exit() {
        let base = path("native-stop");
        let mut owned = worker(&base);
        owned.capture_from_worker(notice, save(&base)).unwrap();
        let original = owned.expected.as_ref().unwrap().clone();
        owned.stop_before_release(save(&base)).unwrap();
        assert!(owned.child.try_wait().unwrap().is_some());
        let mut caller = TrustedCurrentCaller::new();
        owned.handoff_stopped(&mut caller).unwrap();
        caller
            .authorize(RestartAction::PruneUnpublished, &original)
            .unwrap()
            .validate(RestartAction::PruneUnpublished, &original)
            .unwrap();
        assert_eq!(
            fs::read(base.join("source.bin")).unwrap(),
            b"authored source"
        );
        assert!(base.join("unit/candidate.bin").exists());
        assert!(base.join("unit/prepared.record").exists());
        assert!(base.join("unit/intent.record").exists());
        assert!(!base.join("unit/output.bin").exists());
        // An identically named recreated worker/caller cannot adopt that root.
        assert!(matches!(
            TrustedCurrentCaller::new().authorize(RestartAction::PruneUnpublished, &original),
            Err(CustodyRefusal::MissingAuthority)
        ));
        let mut replacement = worker(&base);
        assert_eq!(
            replacement.capture_from_worker(notice, save(&base)),
            Err(CustodyRefusal::WorkerIo)
        );
        assert_eq!(
            replacement.handoff_stopped(&mut TrustedCurrentCaller::new()),
            Err(CustodyRefusal::InvalidLifecycle)
        );
        replacement.close().unwrap();
        assert!(!base.join("unit/output.bin").exists());
        fs::write(base.join("audit.private.txt"),"actual original child exited before release; exact current caller prune capability validated; no prune executed; source/root/artifacts retained\n").unwrap();
    }

    #[test]
    fn actual_native_worker_release_current_attestation_and_later_edit_refusal() {
        let base = path("native-release");
        let mut owned = worker(&base);
        owned.capture_from_worker(notice, save(&base)).unwrap();
        owned
            .release(save(&base), |child| {
                child.stdin.as_mut().unwrap().write_all(b"continue\n")
            })
            .unwrap();
        let terminal = notice(&mut owned.child).unwrap();
        finish(&mut owned);
        assert_eq!(
            owned.stop_before_release(save(&base)),
            Err(CustodyRefusal::InvalidLifecycle)
        );
        let mut caller = TrustedCurrentCaller::new();
        // New current attestation is deliberate and independently sourced from
        // the actual original worker's terminal channel plus confirmed exit.
        caller
            .attest_current(
                terminal.clone(),
                CurrentCallerHistory::TerminalCompletionAndStopped,
            )
            .unwrap();
        caller
            .authorize(RestartAction::RecognizeCompletion, &terminal)
            .unwrap()
            .validate(RestartAction::RecognizeCompletion, &terminal)
            .unwrap();
        owned.close().unwrap();
        assert_eq!(
            fs::read(base.join("unit/output.bin")).unwrap(),
            b"authored derivative"
        );
        let record = base.join("unit").join("prepared.record");
        let original_bytes = fs::read(&record).unwrap();
        fs::rename(&record, base.join("retained-prepared.original")).unwrap();
        fs::write(&record, &original_bytes).unwrap();
        let mut changed = terminal.clone();
        changed.bindings[3] = file_binding(&record);
        assert_ne!(terminal.bindings[3].identity, changed.bindings[3].identity);
        caller
            .attest_current(
                terminal.clone(),
                CurrentCallerHistory::TerminalCompletionAndStopped,
            )
            .unwrap();
        assert!(matches!(
            caller.authorize(RestartAction::RecognizeCompletion, &changed),
            Err(CustodyRefusal::ChangedBindings)
        ));
        assert!(matches!(
            caller.authorize(RestartAction::RecognizeCompletion, &terminal),
            Err(CustodyRefusal::MissingAuthority)
        ));
        fs::rename(&record, base.join("retained-prepared.replacement")).unwrap();
        fs::rename(base.join("retained-prepared.original"), &record).unwrap();
        assert_eq!(file_binding(&record), terminal.bindings[3]);
        assert!(matches!(
            caller.authorize(RestartAction::RecognizeCompletion, &terminal),
            Err(CustodyRefusal::MissingAuthority)
        ));
        // Actual same-object output editing cannot authorize rollback or a
        // fresh completion using the older independent binding.
        let output = base.join("unit").join("output.bin");
        fs::write(&output, b"later authored owner edit").unwrap();
        let mut edited = terminal.clone();
        edited.bindings[2] = file_binding(&output);
        assert_eq!(edited.bindings[2].identity, terminal.bindings[2].identity);
        caller
            .attest_current(
                terminal.clone(),
                CurrentCallerHistory::TerminalCompletionAndStopped,
            )
            .unwrap();
        assert!(matches!(
            caller.authorize(RestartAction::RecognizeCompletion, &edited),
            Err(CustodyRefusal::ChangedBindings)
        ));
        let foreign =
            imageinfo_windows_storage::PrivateRoot::create(&base.join("unknown-unit")).unwrap();
        let mut unknown = terminal.clone();
        unknown.bindings[1].identity = foreign
            .snapshot()
            .volume_serial_number
            .to_le_bytes()
            .into_iter()
            .chain(foreign.snapshot().file_index.to_le_bytes())
            .collect();
        caller
            .attest_current(
                terminal.clone(),
                CurrentCallerHistory::TerminalCompletionAndStopped,
            )
            .unwrap();
        assert!(matches!(
            caller.authorize(RestartAction::RecognizeCompletion, &unknown),
            Err(CustodyRefusal::UnknownRoot)
        ));
        fs::write(base.join("audit.private.txt"),"actual native protocol completed; original child exit confirmed; explicit current recognition capability validated; same-byte native record replacement, rollback after refusal, later same-object output edit and actual unknown-root identity refused; no restart effect executed\n").unwrap();
    }

    #[test]
    fn actual_native_worker_failed_initial_stop_fence_and_send_saves_never_prune() {
        for failure in ["initial", "stop", "fence", "send"] {
            let base = path(failure);
            let mut owned = worker(&base);
            if failure == "initial" {
                assert_eq!(
                    owned.capture_from_worker(notice, |_, _| Err(io::Error::other(
                        "authored incomplete save"
                    ))),
                    Err(CustodyRefusal::SaveFailed)
                );
            } else {
                owned.capture_from_worker(notice, save(&base)).unwrap();
                match failure {
                    "stop" => assert_eq!(
                        owned.stop_before_release(|_, _| Err(io::Error::other(
                            "authored stop save failure"
                        ))),
                        Err(CustodyRefusal::SaveFailed)
                    ),
                    "fence" => assert_eq!(
                        owned.release(
                            |_, _| Err(io::Error::other("authored partial fence")),
                            |_| panic!("failed fence continued worker")
                        ),
                        Err(CustodyRefusal::SaveFailed)
                    ),
                    "send" => assert_eq!(
                        owned.release(save(&base), |_| Err(io::Error::other(
                            "authored uncertain continuation"
                        ))),
                        Err(CustodyRefusal::ReleaseUncertain)
                    ),
                    _ => unreachable!(),
                }
            }
            assert_eq!(
                owned.stop_before_release(save(&base)),
                Err(CustodyRefusal::InvalidLifecycle)
            );
            assert_eq!(
                owned.handoff_stopped(&mut TrustedCurrentCaller::new()),
                Err(CustodyRefusal::InvalidLifecycle)
            );
            owned.close().unwrap();
            assert!(base.join("unit/candidate.bin").exists());
            assert!(!base.join("unit/output.bin").exists());
            assert_eq!(
                fs::read(base.join("source.bin")).unwrap(),
                b"authored source"
            );
            fs::write(base.join("audit.private.txt"),format!("authored {failure} failure; actual owned child stopped; no prune authority; retained source/root/artifacts\n")).unwrap();
        }
    }
}
