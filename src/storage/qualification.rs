//! Authored-marker guest actor for #0175. Built only into the library test
//! executable. Every storage effect uses the actual internal production code;
//! the observer/gates confer neither format nor profile admission.

use super::cleanup::{CleanupRequest, UnneededRecords, cleanup_observed};
use super::custody::{CurrentCallerHistory, RestartAction, TrustedCurrentCaller};
use super::finalization::{CompletionContext, finalize_observed};
use super::inspection::{Inspection, InspectionSpec};
use super::resources::{Construction, KnownOperations, OperationKey, RetainedSession};
use super::runtime::{
    Artifact, Backend, Binding, ExpectedAbsent, LiveEvidence, ValidatedCandidate,
};
use super::windows::WindowsBackend;
use super::{Cancellation, Failure, LogicalBudget, Phase, UnitResult};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::fs::{self, OpenOptions};
use std::io::{self, Cursor, Read, Write};
use std::os::windows::fs::MetadataExt;
use std::path::{Path, PathBuf};

const SOURCE: &[u8] = b"imageinfo-0175 protected authored source v1\n";
const CANDIDATE: &[u8] = b"imageinfo-0175 authored output candidate v1\n";
const OPERATION: &str = "0175-authored-single-output-v1";
const FORMAT: &str = "0175-marker-only-v1";
const OUTPUT: &str = "output.bin";
const CHECKPOINTS: &[&str] = &[
    "none",
    "candidate-ready",
    "intent-ready",
    "possible-publication",
    "publication-api-response",
    "installed-ack",
    "receipt-before-ack",
    "final-success-response",
    "completed-predicate",
    "finalize-receipt-created",
    "cleanup-one-removed",
];

fn spec() -> InspectionSpec<'static> {
    InspectionSpec {
        operation: OPERATION,
        format_revision: FORMAT,
        output: OUTPUT,
        candidate_len: CANDIDATE.len() as u64,
    }
}

fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

/// These are observations, never decoded back into a capability or prior proof.
fn result(result: &UnitResult) -> Value {
    json!({
        "status": format!("{:?}", result.status),
        "phase": format!("{:?}", result.phase),
        "failure": result.failure.map(|e| format!("{e:?}")),
        "publication_possible": result.publication_possible,
        "release_possible": result.release_possible,
        "protocol_complete": result.protocol_complete,
        "retained_material": result.retained_material,
        "pending_cleanup": result.pending_cleanup,
        "charged_bytes": result.charged_bytes,
        "production_profile_admitted": false,
        "raw_admitted": false,
    })
}

fn inventory(path: &Path) -> io::Result<Value> {
    let mut paths = vec![path.join("source.bin")];
    let root = path.join("unit");
    if root.try_exists()? {
        let mut entries: Vec<_> = fs::read_dir(&root)?.take(8).collect::<io::Result<_>>()?;
        if entries.len() > 6 {
            return Err(io::Error::other("QUALIFICATION_NAMESPACE_BOUND"));
        }
        entries.sort_by_key(|entry| entry.file_name());
        paths.extend(entries.into_iter().map(|entry| entry.path()));
    }
    let mut files = Vec::new();
    for file in paths {
        let meta = fs::symlink_metadata(&file)?;
        if !meta.is_file() || meta.len() > 65_536 || meta.file_attributes() & 0x400 != 0 {
            return Err(io::Error::other("QUALIFICATION_FILE_BOUND"));
        }
        let bytes = fs::read(&file)?;
        if bytes.len() as u64 != meta.len() {
            return Err(io::Error::other("QUALIFICATION_INVENTORY_RACE"));
        }
        files.push(json!({
            "path": file.strip_prefix(path).unwrap().to_string_lossy(),
            "size": meta.len(),
            "sha256": hex(&Sha256::digest(&bytes)),
            "attributes": meta.file_attributes(),
            "creation_time": meta.creation_time(),
            "last_write_time": meta.last_write_time(),
        }));
    }
    Ok(json!(files))
}

fn save_finalization(
    path: &Path,
    phase: Phase,
    context: &CompletionContext,
) -> Result<(), Failure> {
    let name = match phase {
        Phase::CheckedContext => "finalize-checked.capture.json",
        Phase::TerminalExport => "finalize-terminal.capture.json",
        _ => return Err(Failure::CallerHistory),
    };
    let bindings: Vec<_> = context
        .bindings()
        .object_bindings()
        .iter()
        .map(|binding| json!({"identity": hex(&binding.identity), "facts": hex(&binding.facts)}))
        .collect();
    let bytes = serde_json::to_vec(&json!({"schema": "imageinfo-0175-finalize-observation-v1",
        "attempt": context.attempt, "phase": format!("{phase:?}"), "bindings": bindings,
        "authority_importable": false}))
    .map_err(|_| Failure::BackendIo)?;
    if bytes.len() > super::MAX_RECORD_BYTES as usize {
        return Err(Failure::RecordTooLarge);
    }
    let mut file = OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(path.join(name))
        .map_err(|_| Failure::BackendIo)?;
    file.write_all(&bytes)
        .and_then(|_| file.flush())
        .and_then(|_| file.sync_all())
        .map_err(|_| Failure::BackendIo)
}

struct Notices {
    path: PathBuf,
    log_path: PathBuf,
    checkpoint: String,
    sequence: u64,
    gated: bool,
}

impl Notices {
    fn emit(&mut self, name: &str, facts: Value) -> Result<(), Failure> {
        self.sequence += 1;
        let gate = self.checkpoint == name && !self.gated;
        let event = json!({
            "schema": "imageinfo-0175-event-v1",
            "sequence": self.sequence,
            "pid": std::process::id(),
            "event": name,
            "gate": gate,
            "facts": facts,
            "inventory": inventory(&self.path).map_err(|_| Failure::BackendIo)?,
        });
        let mut file = OpenOptions::new()
            .append(true)
            .open(&self.log_path)
            .map_err(|_| Failure::BackendIo)?;
        serde_json::to_writer(&mut file, &event).map_err(|_| Failure::BackendIo)?;
        file.write_all(b"\n").map_err(|_| Failure::BackendIo)?;
        // Complete readable diagnostic framing without forcing this volume's
        // device cache. An unrelated file flush here could persist the receipt
        // before the actual protocol reaches its receipt-flush boundary.
        // The controller retains the private-pipe notice outside the guest.
        file.flush().map_err(|_| Failure::BackendIo)?;
        println!("IMAGEINFO175 {}", event);
        io::stdout().flush().map_err(|_| Failure::BackendIo)?;
        if gate {
            self.gated = true;
            // A bounded private pipe continuation. EOF/other input refuses;
            // observations in a file can never supply a continuation.
            let mut input = [0u8; 9];
            io::stdin()
                .read_exact(&mut input)
                .map_err(|_| Failure::CallerHistory)?;
            if &input != b"continue\n" {
                return Err(Failure::CallerHistory);
            }
        }
        Ok(())
    }
}

struct Actor<'a> {
    native: WindowsBackend,
    notices: &'a mut Notices,
    stop_before_receipt: bool,
}

impl Actor<'_> {
    fn bindings(&self) -> Vec<Value> {
        self.native
            .qualification_bindings()
            .iter()
            .map(
                |binding| json!({"identity": hex(&binding.identity), "facts": hex(&binding.facts)}),
            )
            .collect()
    }
    fn notice(&mut self, name: &str) -> Result<(), Failure> {
        let bindings = self.bindings();
        self.notices.emit(
            name,
            json!({"bindings": bindings, "authority": "none-exported"}),
        )
    }
    fn outcome_notice(&mut self, name: &str, outcome: &UnitResult) -> Result<(), Failure> {
        let mut facts = result(outcome);
        facts["bindings"] = json!(self.bindings());
        self.notices.emit(name, facts)
    }
}

impl Backend for Actor<'_> {
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
    fn create(&mut self, artifact: Artifact, bytes: &[u8]) -> Result<Binding, Failure> {
        if artifact == Artifact::Receipt && self.stop_before_receipt {
            return Err(Failure::Cancelled);
        }
        let binding = self.native.create(artifact, bytes)?;
        if artifact == Artifact::Receipt {
            self.notice("receipt-before-ack")?;
        }
        Ok(binding)
    }
    fn check(&mut self, phase: Phase, bindings: &[Binding]) -> Result<(), Failure> {
        self.native.check(phase, bindings)?;
        match phase {
            Phase::CandidateChecked => self.notice("candidate-ready")?,
            Phase::IntentChecked => self.notice("intent-ready")?,
            Phase::Installed => self.notice("installed-ack")?,
            _ => {}
        }
        Ok(())
    }
    fn flush_file(&mut self, artifact: Artifact) -> Result<(), Failure> {
        self.native.flush_file(artifact)
    }
    fn flush_root(&mut self) -> Result<(), Failure> {
        self.native.flush_root()
    }
    fn flush_parent(&mut self) -> Result<(), Failure> {
        self.native.flush_parent()
    }
    fn publish(&mut self, output: &str) -> Result<(), Failure> {
        // Runtime already set publication_possible before calling this method.
        self.notice("possible-publication")?;
        self.native.publish(output)?;
        self.notice("publication-api-response")
    }
    fn caller_release(&mut self, bindings: &[Binding]) -> Result<(), Failure> {
        self.native.caller_release(bindings)
    }
    fn checked_context(&mut self, bindings: &[Binding]) -> Result<(), Failure> {
        self.native.checked_context(bindings)
    }
    fn export_terminal(&mut self, bindings: &[Binding]) -> Result<(), Failure> {
        self.native.export_terminal(bindings)
    }
    fn retain_live_evidence(&mut self, evidence: &LiveEvidence) {
        self.native.retain_live_evidence(evidence);
    }
    fn retain_outcome(&mut self, phase: Phase, failure: Option<Failure>) {
        self.native.retain_outcome(phase, failure);
    }
}

fn run_cell(path: &Path, mode: &str, checkpoint: &str) -> Result<(), Failure> {
    let source = path.join("source.bin");
    let root = path.join("unit");
    let mut notices = Notices {
        path: path.into(),
        log_path: path.join(if mode == "inspect" {
            "inspect-events.jsonl"
        } else {
            "events.jsonl"
        }),
        checkpoint: checkpoint.into(),
        sequence: 0,
        gated: false,
    };
    if mode == "inspect" {
        // A new actor/caller has no imported capability. Even a matching receipt
        // remains read-only and cannot recognize/finalize/clean up by itself.
        let inspection = Inspection::collect(&source, &root, &spec());
        let (collected, refusal, bindings, directories) = match inspection {
            Ok(mut held) => {
                let bindings: Vec<_> = held.bindings().object_bindings().iter()
                    .map(|binding| json!({"identity": hex(&binding.identity), "facts": hex(&binding.facts)}))
                    .collect();
                let directories = json!({"current_root": hex(&held.current_root.binding_bytes()),
                    "current_parent": hex(&held.current_parent.binding_bytes())});
                let refusal = held.recheck().err().map(|error| format!("{error:?}"));
                (refusal.is_none(), refusal, bindings, directories)
            }
            Err(error) => (false, Some(format!("{error:?}")), Vec::new(), Value::Null),
        };
        return notices.emit(
            "read-only-inspection",
            json!({
                "collected": collected, "refusal": refusal,
                "bindings": bindings, "directories": directories,
                "survivor": "RecoveryRequired", "authority": "MissingAuthority",
                "mutation_attempted": false, "production_profile_admitted": false,
            }),
        );
    }
    let mut actor = Actor {
        native: WindowsBackend::new(&source, &root),
        notices: &mut notices,
        stop_before_receipt: mode == "finalize",
    };
    let mut reader = Cursor::new(CANDIDATE);
    let root_key = root.to_str().ok_or(Failure::InvalidBinding)?;
    let key = OperationKey {
        operation: OPERATION,
        root: root_key,
    };
    let mut retained = RetainedSession::start(2_000_000, KnownOperations::Complete(&[]))?;
    let outcome = retained.run(
        key,
        &mut actor,
        ValidatedCandidate {
            operation: OPERATION,
            format_revision: FORMAT,
            source: &mut reader,
            planned_len: CANDIDATE.len() as u64,
            max_len: CANDIDATE.len() as u64,
            output: ExpectedAbsent(OUTPUT),
        },
        &Cancellation::default(),
        |actor| actor.native.available_bytes(),
    )?;
    actor.outcome_notice("runtime-result", &outcome)?;
    if mode == "run" {
        if outcome.protocol_complete {
            actor.outcome_notice("final-success-response", &outcome)?;
            actor.outcome_notice("completed-predicate", &outcome)?;
        }
        return if outcome.protocol_complete {
            Ok(())
        } else {
            Err(outcome.failure.unwrap_or(Failure::Unsupported))
        };
    }
    // This actual current actor retains the original live proof through a guard
    // restart. No JSON, editable record or newly created caller recreates it.
    if mode == "finalize"
        && (outcome.phase != Phase::ReceiptCreated || outcome.failure != Some(Failure::Cancelled))
    {
        return Err(Failure::CallerHistory);
    }
    if mode == "cleanup" && !outcome.protocol_complete {
        return Err(Failure::CallerHistory);
    }
    let prior = retained.construct(key, Construction::Recovery, super::MAX_RECORD_BYTES, || {
        actor.native.finalization_prior(OPERATION)
    })?;
    let prior_bindings = actor.bindings();
    drop(actor);
    let mut caller = TrustedCurrentCaller::new();
    let action = if mode == "finalize" {
        RestartAction::FinalizeExisting
    } else {
        RestartAction::CleanupCompleted
    };
    caller
        .attest_current(
            prior.bindings().clone(),
            if mode == "finalize" {
                CurrentCallerHistory::ReleasedAndStopped
            } else {
                CurrentCallerHistory::TerminalCompletionAndStopped
            },
        )
        .map_err(|_| Failure::CallerHistory)?;
    let authority = caller
        .authorize(action, prior.bindings())
        .map_err(|_| Failure::CallerHistory)?;
    notices.emit(
        "current-caller-action",
        json!({"action": format!("{action:?}"),
        "authority": "actual-live-proof-in-this-process", "imported_authority": false,
        "guard_restart": true, "process_restart": false}),
    )?;
    if mode == "finalize" {
        // Additional execution allowance is charged to the same surviving
        // cumulative owner before the fresh guarded action, never reset.
        let attempt_root = format!("{root_key}#finalize");
        let amount = LogicalBudget::unit_charge(spec().candidate_len)?;
        let mut budget = LogicalBudget::new(amount);
        let output = retained.attempt(
            OperationKey {
                operation: "0175-fresh-finalize-v1",
                root: &attempt_root,
            },
            amount,
            || imageinfo_windows_storage::available_bytes(path).map_err(|_| Failure::BackendIo),
            || {
                Ok(finalize_observed(
                    &source,
                    &root,
                    &spec(),
                    "0175-fresh-finalize-v1",
                    prior,
                    authority,
                    &mut budget,
                    &Cancellation::default(),
                    |phase, context| save_finalization(path, phase, context),
                    |phase, after, current| {
                        if phase == Phase::ReceiptCreated && after {
                            let bindings: Vec<_> = current
                                .iter()
                                .map(|binding| {
                                    json!({
                                "identity": hex(&binding.identity), "facts": hex(&binding.facts)})
                                })
                                .collect();
                            notices.emit(
                                "finalize-receipt-created",
                                json!({"phase": "ReceiptCreated", "after": true,
                                    "prior_bindings": prior_bindings, "bindings": bindings,
                                    "fresh_receipt_binding_exported": true}),
                            )?;
                        }
                        Ok(())
                    },
                ))
            },
        )?;
        notices.emit("finalize-result", result(&output.result))?;
        if !output.result.protocol_complete {
            return Err(output.result.failure.unwrap_or(Failure::Unsupported));
        }
    } else {
        let request = CleanupRequest::completed(
            prior,
            authority,
            UnneededRecords::recovery_resolved(&[
                Artifact::Prepared,
                Artifact::Intent,
                Artifact::Observation,
                Artifact::Receipt,
            ])?,
        )?;
        let outcome = cleanup_observed(
            &source,
            &root,
            request,
            &Cancellation::default(),
            |removed, _| {
                if removed == 1 {
                    notices.emit(
                        "cleanup-one-removed",
                        json!({"successful_removals": 1, "bindings": prior_bindings}),
                    )?;
                }
                Ok(())
            },
        );
        notices.emit(
            "cleanup-result",
            json!({"status": format!("{:?}", outcome.status),
            "failure": outcome.failure.map(|e| format!("{e:?}")),
            "pending_cleanup": outcome.pending_cleanup,
            "terminal_completion_preserved": outcome.terminal_completion_preserved,
            "residuals": format!("{:?}", outcome.residuals)}),
        )?;
        if let Some(failure) = outcome.failure {
            return Err(failure);
        }
    }
    Ok(())
}

/// Entrypoint executed explicitly by the retained guest controller. No arbitrary
/// paths, phase labels or imported action claims are parsed from transaction data.
#[test]
#[ignore = "explicit authored-marker qualification actor; requires bounded controller"]
fn guest_actor() {
    let path = PathBuf::from(std::env::var_os("IMAGEINFO_175_CELL_DIR").expect("cell directory"));
    let mode = std::env::var("IMAGEINFO_175_MODE").expect("actor mode");
    let checkpoint = std::env::var("IMAGEINFO_175_CHECKPOINT").unwrap_or_else(|_| "none".into());
    assert!(path.is_absolute() && path.is_dir());
    assert!(["run", "inspect", "finalize", "cleanup"].contains(&mode.as_str()));
    assert!(CHECKPOINTS.contains(&checkpoint.as_str()));
    assert!(mode != "inspect" || checkpoint == "none");
    // create_new makes accidental reuse an explicit refusal and preserves every
    // partial artifact. Inspect appends into its separate fresh notices file.
    let events = path.join(if mode == "inspect" {
        "inspect-events.jsonl"
    } else {
        "events.jsonl"
    });
    OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&events)
        .expect("fresh notices")
        .sync_all()
        .unwrap();
    if mode != "inspect" {
        let mut source = OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(path.join("source.bin"))
            .expect("fresh source");
        source.write_all(SOURCE).unwrap();
        source.sync_all().unwrap();
        assert!(!path.join("unit").exists());
    }
    run_cell(&path, &mode, &checkpoint)
        .expect("actual actor outcome; inspect retained facts on failure");
}

#[test]
fn finite_contract_has_unique_bounded_checkpoints_and_authored_distinct_bytes() {
    assert_ne!(SOURCE, CANDIDATE);
    for (index, checkpoint) in CHECKPOINTS.iter().enumerate() {
        assert!(checkpoint.len() <= 32 && !CHECKPOINTS[..index].contains(checkpoint));
    }
}

#[test]
fn actual_actor_controls_use_unqualified_runtime_and_preserve_read_only_inspection() {
    use std::process::{Command, Stdio};
    use std::time::{SystemTime, UNIX_EPOCH};
    let base = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join(".local")
        .join("work-wave-20261017d")
        .join(format!(
            "175-actor-controls-{}-{}",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
    fs::create_dir_all(&base).unwrap();
    for mode in ["run", "finalize", "cleanup"] {
        let path = base.join(mode);
        fs::create_dir(&path).unwrap();
        let invoke = |mode: &str| {
            let stdout = fs::File::create(path.join(format!("{mode}-stdout.txt"))).unwrap();
            let stderr = fs::File::create(path.join(format!("{mode}-stderr.txt"))).unwrap();
            Command::new(std::env::current_exe().unwrap())
                .args([
                    "--exact",
                    "storage::qualification::guest_actor",
                    "--ignored",
                    "--nocapture",
                    "--test-threads=1",
                ])
                .env("IMAGEINFO_175_CELL_DIR", &path)
                .env("IMAGEINFO_175_MODE", mode)
                .env("IMAGEINFO_175_CHECKPOINT", "none")
                .stdin(Stdio::null())
                .stdout(stdout)
                .stderr(stderr)
                .status()
                .unwrap()
        };
        assert!(
            invoke(mode).success(),
            "retained actor evidence {}",
            path.display()
        );
        assert_eq!(fs::read(path.join("source.bin")).unwrap(), SOURCE);
        assert_eq!(fs::read(path.join("unit/output.bin")).unwrap(), CANDIDATE);
        assert!(!path.join("unit/candidate.bin").exists());
        let events: Vec<Value> = fs::read_to_string(path.join("events.jsonl"))
            .unwrap()
            .lines()
            .map(|line| serde_json::from_str(line).unwrap())
            .collect();
        let runtime = events
            .iter()
            .find(|e| e["event"] == "runtime-result")
            .unwrap();
        assert_eq!(runtime["facts"]["production_profile_admitted"], false);
        assert_eq!(runtime["facts"]["raw_admitted"], false);
        if mode != "finalize" {
            assert_eq!(runtime["facts"]["status"], "Refused");
            assert_eq!(runtime["facts"]["protocol_complete"], true);
        } else {
            assert_eq!(runtime["facts"]["failure"], "Cancelled");
            let finished = events
                .iter()
                .find(|e| e["event"] == "finalize-result")
                .unwrap();
            assert_eq!(finished["facts"]["status"], "Refused");
            assert_eq!(finished["facts"]["protocol_complete"], true);
        }
        let before = inventory(&path).unwrap();
        assert!(invoke("inspect").success());
        assert_eq!(before, inventory(&path).unwrap());
        let inspected: Value = serde_json::from_str(
            fs::read_to_string(path.join("inspect-events.jsonl"))
                .unwrap()
                .trim(),
        )
        .unwrap();
        assert_eq!(inspected["facts"]["authority"], "MissingAuthority");
        assert_eq!(inspected["facts"]["mutation_attempted"], false);
        if mode == "cleanup" {
            let entries: Vec<_> = fs::read_dir(path.join("unit")).unwrap().collect();
            assert_eq!(entries.len(), 1);
        }
    }
}

#[test]
fn actual_gates_hold_exact_native_boundaries_until_private_pipe_continuation() {
    use std::process::{Command, Stdio};
    use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};
    let base = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join(".local")
        .join("work-wave-20261017d")
        .join(format!(
            "175-actor-gates-{}-{}",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
    fs::create_dir_all(&base).unwrap();
    for (mode, checkpoint) in [
        ("run", "possible-publication"),
        ("finalize", "finalize-receipt-created"),
        ("cleanup", "cleanup-one-removed"),
    ] {
        let path = base.join(mode);
        fs::create_dir(&path).unwrap();
        let mut child = Command::new(std::env::current_exe().unwrap())
            .args([
                "--exact",
                "storage::qualification::guest_actor",
                "--ignored",
                "--nocapture",
                "--test-threads=1",
            ])
            .env("IMAGEINFO_175_CELL_DIR", &path)
            .env("IMAGEINFO_175_MODE", mode)
            .env("IMAGEINFO_175_CHECKPOINT", checkpoint)
            .stdin(Stdio::piped())
            .stdout(fs::File::create(path.join("stdout.txt")).unwrap())
            .stderr(fs::File::create(path.join("stderr.txt")).unwrap())
            .spawn()
            .unwrap();
        let deadline = Instant::now() + Duration::from_secs(30);
        loop {
            let armed = fs::read_to_string(path.join("events.jsonl"))
                .ok()
                .is_some_and(|text| {
                    text.lines()
                        .filter_map(|line| serde_json::from_str::<Value>(line).ok())
                        .any(|event| event["event"] == checkpoint && event["gate"] == true)
                });
            if armed {
                break;
            }
            if child.try_wait().unwrap().is_some() || Instant::now() >= deadline {
                let _ = child.kill();
                let _ = child.wait();
                panic!("gate not reached; retained evidence {}", path.display());
            }
            std::thread::sleep(Duration::from_millis(10));
        }
        assert!(child.try_wait().unwrap().is_none());
        match mode {
            "run" => {
                assert!(path.join("unit/candidate.bin").is_file());
                assert!(!path.join("unit/output.bin").exists());
            }
            "finalize" => assert!(path.join("unit/receipt.record").is_file()),
            "cleanup" => {
                assert!(!path.join("unit/prepared.record").exists());
                assert!(path.join("unit/intent.record").is_file());
            }
            _ => unreachable!(),
        }
        child
            .stdin
            .take()
            .unwrap()
            .write_all(b"continue\n")
            .unwrap();
        loop {
            if let Some(status) = child.try_wait().unwrap() {
                assert!(status.success(), "retained evidence {}", path.display());
                break;
            }
            if Instant::now() >= deadline {
                let _ = child.kill();
                let _ = child.wait();
                panic!(
                    "continuation deadline; retained evidence {}",
                    path.display()
                );
            }
            std::thread::sleep(Duration::from_millis(10));
        }
    }
}
