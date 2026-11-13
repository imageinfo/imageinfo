//! Fresh authored NTFS fixtures, retained for independent identity/property audit.
use super::*;
use crate::storage::{Cancellation, custody::TrustedCurrentCaller};
use imageinfo_windows_storage::{FileSnapshot, GuardedSource, PrivateRoot};
use serde_json::{Value, json};
use std::{
    fs::{self, File, FileTimes, OpenOptions},
    io::Write,
    os::windows::fs::OpenOptionsExt,
    path::{Path, PathBuf},
    time::{Duration, Instant, SystemTime, UNIX_EPOCH},
};

const LEAVES: [&str; 3] = ["target.bin", "retained.bin", "staged.bin"];
const OLD_BYTES: &[u8] = b"authored retained original\n";
const NEW_BYTES: &[u8] = b"authored fresh candidate\n";
const WINNER_BYTES: &[u8] = b"authored foreign winner\n";

fn inspect(path: &Path) -> Option<(FileSnapshot, Vec<u8>)> {
    if !path.try_exists().unwrap() {
        return None;
    }
    let mut file = GuardedSource::open(path, 4096).unwrap();
    Some((file.snapshot().clone(), file.read_exact_bytes().unwrap()))
}

fn encode(snapshot: &FileSnapshot, bytes: &[u8]) -> Value {
    json!({
        "volume": snapshot.volume_serial_number, "file": snapshot.file_index,
        "size": snapshot.size, "links": snapshot.links, "attributes": snapshot.attributes,
        "created": snapshot.creation_time, "written": snapshot.last_write_time,
        "security": snapshot.owner_dacl, "bytes": bytes
    })
}

struct Fixture {
    path: PathBuf,
    old: FileSnapshot,
    root: Option<PrivateRoot>,
}

impl Fixture {
    fn new(cell: &str) -> Self {
        let base = std::env::var_os("IMAGEINFO_RETAIN_INSTALL_EVIDENCE_ROOT").map_or_else(
            || {
                std::env::current_dir()
                    .unwrap()
                    .join(".local")
                    .join("native-retain-install")
            },
            PathBuf::from,
        );
        fs::create_dir_all(&base).unwrap();
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let path = base.join(format!("{cell}-{}-{now}", std::process::id()));
        let root = PrivateRoot::create(&path).unwrap();
        drop(root.create_artifact(LEAVES[0], OLD_BYTES, 4096).unwrap());
        let (old, bytes) = inspect(&path.join(LEAVES[0])).unwrap();
        fs::write(
            path.join("initial.private.json"),
            serde_json::to_vec(&encode(&old, &bytes)).unwrap(),
        )
        .unwrap();
        // Positive acceptance must use naturally distinct creation times.
        std::thread::sleep(Duration::from_millis(30));
        Self {
            path,
            old,
            root: Some(root),
        }
    }

    fn slot(&self, index: usize) -> PathBuf {
        self.path.join(LEAVES[index])
    }

    fn open(
        &mut self,
        caller: &mut TrustedCurrentCaller,
        budget: &mut LogicalBudget,
        cancel: &Cancellation,
        policy: ContinuationPolicy,
    ) -> Result<Session, Report> {
        Session::open(
            Plan::new(LEAVES, self.old.clone(), NEW_BYTES.to_vec(), policy).unwrap(),
            self.root.take().unwrap(),
            caller,
            budget,
            cancel,
        )
    }

    fn start(&mut self, caller: &mut TrustedCurrentCaller) -> Session {
        let mut budget = LogicalBudget::new(u64::MAX);
        let session = self
            .open(
                caller,
                &mut budget,
                &Cancellation::default(),
                ContinuationPolicy::GuardHeldQuiet20Seconds,
            )
            .unwrap_or_else(|report| panic!("open refused: {report:?}"));
        assert_eq!(
            budget.charged(),
            NEW_BYTES.len() as u64 + 8 * crate::storage::MAX_RECORD_BYTES
        );
        session
    }

    fn winner(&self, slot: usize, bytes: &[u8]) {
        let mut file = OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(self.slot(slot))
            .unwrap();
        file.write_all(bytes).unwrap();
    }

    fn finish(&self, report: Report) -> [Option<(FileSnapshot, Vec<u8>)>; 3] {
        let actual = std::array::from_fn(|i| inspect(&self.slot(i)));
        let slots = actual.each_ref().map(|slot| {
            slot.as_ref()
                .map_or(Value::Null, |(snapshot, bytes)| encode(snapshot, bytes))
        });
        fs::write(
            self.path.join("terminal.private.json"),
            serde_json::to_vec(&json!({
                "schema":"imageinfo.private-retain-install-fixture.v1",
                "report": format!("{report:?}"), "slots": slots
            }))
            .unwrap(),
        )
        .unwrap();
        actual
    }
}

fn retained_prefix(session: &mut Session, cancel: &Cancellation) {
    let report = session.advance(cancel);
    assert_eq!(report.outcome, Outcome::Ready, "{report:?}");
    assert_eq!(report.confirmed_prefix, 1);
    assert_eq!(report.attempted, [true, false]);
    assert_eq!(report.bindings, PREFIXES[1]);
}

fn terminal(session: &mut Session, report: Report) {
    assert_eq!(
        session.advance_with(&Cancellation::default(), |_, _| panic!("terminal replay")),
        report
    );
}

fn check_old(actual: &Option<(FileSnapshot, Vec<u8>)>, expected: &FileSnapshot) {
    let (snapshot, bytes) = actual.as_ref().unwrap();
    assert_eq!(snapshot, expected);
    assert_eq!(bytes, OLD_BYTES);
}

#[test]
fn native_selected_policy_preserves_exact_distinct_objects_and_properties() {
    let mut f = Fixture::new("selected");
    let mut caller = TrustedCurrentCaller::new();
    let mut session = f.start(&mut caller);
    let cancel = Cancellation::default();
    retained_prefix(&mut session, &cancel);
    let report = session.advance(&cancel);
    terminal(&mut session, report);
    drop(session);
    let actual = f.finish(report);
    assert_eq!(report.outcome, Outcome::CompleteObserved, "{report:?}");
    assert_eq!(report.confirmed_prefix, 2);
    assert_eq!(report.attempted, [true, true]);
    assert_eq!(report.bindings, PREFIXES[2]);
    assert!(report.quiet_elapsed_nanos.unwrap() >= 20_000_000_000);
    check_old(&actual[1], &f.old);
    assert!(actual[2].is_none());
    let (candidate, bytes) = actual[0].as_ref().unwrap();
    assert_ne!(candidate.file_index, f.old.file_index);
    assert_ne!(candidate.creation_time, f.old.creation_time);
    assert_eq!(bytes, NEW_BYTES);
    let prepared: Value =
        serde_json::from_slice(&fs::read(f.path.join("retain-install-0.record")).unwrap()).unwrap();
    assert_eq!(prepared["candidate"], json!(candidate.binding_bytes()));
}

#[test]
fn native_initial_retained_winners_are_never_adopted_or_overwritten() {
    for (cell, bytes) in [
        ("retained-foreign", WINNER_BYTES),
        ("retained-same-bytes", OLD_BYTES),
    ] {
        let mut f = Fixture::new(cell);
        f.winner(1, bytes);
        let winner = inspect(&f.slot(1)).unwrap();
        let mut caller = TrustedCurrentCaller::new();
        let mut session = f.start(&mut caller);
        let report = session.report();
        terminal(&mut session, report);
        drop(session);
        let actual = f.finish(report);
        assert_eq!(report.outcome, Outcome::Refused);
        assert_eq!(report.bindings, [Old, Foreign, Candidate]);
        assert_eq!(report.attempted, [false, false]);
        check_old(&actual[0], &f.old);
        assert_eq!(actual[1].as_ref(), Some(&winner));
        assert_eq!(actual[2].as_ref().unwrap().1, NEW_BYTES);
    }
}

#[test]
fn native_later_target_winners_are_never_adopted_or_overwritten() {
    // Keep independent authored identity/content choices. The winner arrives
    // inside the actual held wait, after the target gap became observable.
    std::thread::scope(|scope| {
        for (cell, bytes) in [
            ("target-foreign", WINNER_BYTES),
            ("target-same-bytes", NEW_BYTES),
        ] {
            scope.spawn(move || {
                let mut f = Fixture::new(cell);
                let mut caller = TrustedCurrentCaller::new();
                let mut session = f.start(&mut caller);
                let cancel = Cancellation::default();
                retained_prefix(&mut session, &cancel);
                assert!(!f.slot(0).exists());
                let mut winner = None;
                let report = session.advance_with(&cancel, |step, stage| {
                    if (step, stage) == (1, Stage::Waiting) && winner.is_none() {
                        f.winner(0, bytes);
                        winner = inspect(&f.slot(0));
                    }
                    false
                });
                terminal(&mut session, report);
                drop(session);
                let actual = f.finish(report);
                assert_eq!(report.outcome, Outcome::PartialObserved, "{report:?}");
                assert_eq!(report.confirmed_prefix, 1);
                assert_eq!(report.attempted, [true, false]);
                assert_eq!(report.bindings, [Foreign, Old, Candidate]);
                assert_eq!(actual[0], winner);
                check_old(&actual[1], &f.old);
                assert_eq!(actual[2].as_ref().unwrap().1, NEW_BYTES);
            });
        }
    });
}

#[test]
fn native_incompatible_writer_delete_and_prepared_substitution_refuse() {
    for (cell, access) in [("writer", 0x4000_0000), ("deleter", 0x0001_0000)] {
        let mut f = Fixture::new(cell);
        let conflict = OpenOptions::new()
            .access_mode(access)
            .share_mode(7)
            .open(f.slot(0))
            .unwrap();
        let mut caller = TrustedCurrentCaller::new();
        let mut budget = LogicalBudget::new(u64::MAX);
        let report = f
            .open(
                &mut caller,
                &mut budget,
                &Cancellation::default(),
                ContinuationPolicy::GuardHeldQuiet20Seconds,
            )
            .err()
            .expect("incompatible pre-open");
        drop(conflict);
        let actual = f.finish(report);
        assert_eq!(report.outcome, Outcome::Refused);
        assert_eq!(report.attempted, [false, false]);
        assert_eq!(
            budget.charged(),
            NEW_BYTES.len() as u64 + 8 * crate::storage::MAX_RECORD_BYTES
        );
        check_old(&actual[0], &f.old);
        assert!(actual[1].is_none() && actual[2].is_none());
    }
    let mut f = Fixture::new("substitution-before-open");
    fs::rename(f.slot(0), f.path.join("displaced.bin")).unwrap();
    f.winner(0, OLD_BYTES);
    let winner = inspect(&f.slot(0)).unwrap();
    let mut caller = TrustedCurrentCaller::new();
    let report = f
        .open(
            &mut caller,
            &mut LogicalBudget::new(u64::MAX),
            &Cancellation::default(),
            ContinuationPolicy::GuardHeldQuiet20Seconds,
        )
        .err()
        .expect("replacement must refuse");
    let actual = f.finish(report);
    assert_eq!(report.attempted, [false, false]);
    assert_eq!(actual[0].as_ref(), Some(&winner));
    check_old(&inspect(&f.path.join("displaced.bin")), &f.old);
}

#[test]
fn native_live_old_candidate_and_ancestor_rename_attempts_fail() {
    let mut f = Fixture::new("guarded-substitution");
    let mut caller = TrustedCurrentCaller::new();
    let mut session = f.start(&mut caller);
    assert!(fs::rename(f.slot(0), f.path.join("displaced-old.bin")).is_err());
    assert!(fs::rename(f.slot(2), f.path.join("displaced-candidate.bin")).is_err());
    assert!(fs::rename(&f.path, f.path.with_extension("moved")).is_err());
    let cancel = Cancellation::default();
    cancel.request();
    let report = session.advance(&cancel);
    drop(session);
    let actual = f.finish(report);
    check_old(&actual[0], &f.old);
    assert_eq!(actual[2].as_ref().unwrap().1, NEW_BYTES);
}

fn change_time(path: &Path) {
    let actor: File = OpenOptions::new()
        .access_mode(0x100)
        .share_mode(7)
        .open(path)
        .unwrap();
    actor
        .set_times(FileTimes::new().set_modified(UNIX_EPOCH + Duration::from_secs(1_500_000_000)))
        .unwrap();
}

#[test]
fn native_property_changes_before_and_after_retention_are_preserved() {
    for after_retention in [false, true] {
        let mut f = Fixture::new(if after_retention {
            "property-after-retain"
        } else {
            "property-before-retain"
        });
        let mut caller = TrustedCurrentCaller::new();
        let mut session = f.start(&mut caller);
        let cancel = Cancellation::default();
        let slot = usize::from(after_retention);
        if after_retention {
            retained_prefix(&mut session, &cancel);
        }
        let report = session.advance_with(&cancel, |step, stage| {
            if (!after_retention && (step, stage) == (0, Stage::BeforeCall))
                || (after_retention
                    && (step, stage) == (1, Stage::Waiting)
                    && !cancel.is_requested())
            {
                change_time(&f.slot(slot));
                if after_retention {
                    cancel.request();
                }
            }
            false
        });
        terminal(&mut session, report);
        drop(session);
        let actual = f.finish(report);
        assert_eq!(
            report.outcome,
            if after_retention {
                Outcome::RecoveryRequired
            } else {
                Outcome::Refused
            }
        );
        assert_eq!(report.attempted, [after_retention, false]);
        let (snapshot, bytes) = actual[slot].as_ref().unwrap();
        assert_eq!(snapshot.file_index, f.old.file_index);
        assert_ne!(snapshot.last_write_time, f.old.last_write_time);
        assert_eq!(bytes, OLD_BYTES);
    }
}

#[test]
fn native_cancellation_and_authority_revocation_stop_at_actual_prefixes() {
    for cell in [
        "cancel-before-open",
        "cancel-before-call",
        "cancel-after-retain",
        "cancel-during-wait",
        "revoke-during-wait",
    ] {
        let mut f = Fixture::new(cell);
        let mut caller = TrustedCurrentCaller::new();
        let cancel = Cancellation::default();
        let mut budget = LogicalBudget::new(u64::MAX);
        if cell == "cancel-before-open" {
            cancel.request();
            let report = f
                .open(
                    &mut caller,
                    &mut budget,
                    &cancel,
                    ContinuationPolicy::GuardHeldQuiet20Seconds,
                )
                .err()
                .unwrap();
            f.finish(report);
            assert_eq!(report.failure, Some(Failure::Cancelled));
            assert_eq!(budget.charged(), 0);
            continue;
        }
        let mut session = f.start(&mut caller);
        let report = match cell {
            "cancel-before-call" => session.advance_with(&cancel, |_, stage| {
                if stage == Stage::BeforeCall {
                    cancel.request();
                }
                false
            }),
            "cancel-after-retain" => {
                retained_prefix(&mut session, &cancel);
                cancel.request();
                session.advance(&cancel)
            }
            _ => {
                retained_prefix(&mut session, &cancel);
                let wait = Instant::now();
                session.advance_with(&cancel, |_, stage| {
                    if stage == Stage::Waiting && wait.elapsed() >= Duration::from_millis(45) {
                        if cell == "revoke-during-wait" {
                            caller.revoke();
                        } else {
                            cancel.request();
                        }
                    }
                    false
                })
            }
        };
        terminal(&mut session, report);
        drop(session);
        let actual = f.finish(report);
        assert_eq!(
            report.failure,
            Some(if cell == "revoke-during-wait" {
                Failure::CallerHistory
            } else {
                Failure::Cancelled
            })
        );
        let partial = cell != "cancel-before-call";
        assert_eq!(
            report.outcome,
            if partial {
                Outcome::PartialObserved
            } else {
                Outcome::Refused
            }
        );
        assert_eq!(report.attempted, [partial, false]);
        check_old(&actual[usize::from(partial)], &f.old);
        if cell.ends_with("during-wait") {
            assert!(report.quiet_elapsed_nanos.unwrap() >= 45_000_000);
            assert!(report.quiet_elapsed_nanos.unwrap() < 20_000_000_000);
        }
    }
}

#[test]
fn native_discarded_responses_stop_without_confirming_or_replaying_either_call() {
    for step in [0, 1] {
        let mut f = Fixture::new(if step == 0 {
            "discard-retain"
        } else {
            "discard-install"
        });
        let mut caller = TrustedCurrentCaller::new();
        let mut session = f.start(&mut caller);
        let cancel = Cancellation::default();
        if step == 1 {
            retained_prefix(&mut session, &cancel);
        }
        let report = session.advance_with(&cancel, |actual_step, stage| {
            actual_step == step && stage == Stage::AfterCall
        });
        terminal(&mut session, report);
        drop(session);
        let actual = f.finish(report);
        assert_eq!(report.outcome, Outcome::RecoveryRequired);
        assert_eq!(report.confirmed_prefix as usize, step);
        assert!(report.response_discarded[step]);
        assert_eq!(report.attempted, [true, step == 1]);
        assert_eq!(report.bindings, PREFIXES[step + 1]);
        check_old(&actual[1], &f.old);
        assert_eq!(
            actual[if step == 0 { 2 } else { 0 }].as_ref().unwrap().1,
            NEW_BYTES
        );
    }
}

#[test]
fn native_revocation_after_install_call_preserves_map_and_stops_confirmation() {
    let mut f = Fixture::new("revoke-after-install-call");
    let mut caller = TrustedCurrentCaller::new();
    let mut session = f.start(&mut caller);
    let cancel = Cancellation::default();
    retained_prefix(&mut session, &cancel);
    let report = session.advance_with(&cancel, |step, stage| {
        if (step, stage) == (1, Stage::AfterCall) {
            caller.revoke();
        }
        false
    });
    terminal(&mut session, report);
    drop(session);
    let actual = f.finish(report);
    check_old(&actual[1], &f.old);
    assert!(actual[2].is_none());
    let (candidate, bytes) = actual[0].as_ref().unwrap();
    let record = |index| -> Value {
        serde_json::from_slice(
            &fs::read(f.path.join(format!("retain-install-{index}.record"))).unwrap(),
        )
        .unwrap()
    };
    assert_eq!(bytes, NEW_BYTES);
    assert_eq!(record(0)["candidate"], json!(candidate.binding_bytes()));
    assert_eq!(record(4)["phase"], "terminal-stop");
    assert_eq!(record(4)["outcome"], "RecoveryRequired");
    assert_eq!(record(4)["failure"], "CallerHistory");
    assert_eq!(report.outcome, Outcome::RecoveryRequired);
    assert_eq!(report.failure, Some(Failure::CallerHistory));
    assert_eq!(report.confirmed_prefix, 1);
    assert_eq!(report.attempted, [true, true]);
    assert_eq!(report.response_discarded, [false, false]);
    assert_eq!(report.bindings, PREFIXES[2]);
}

#[test]
fn native_property_conflict_after_installation_requires_recovery_without_reset() {
    let mut f = Fixture::new("property-after-install");
    let mut caller = TrustedCurrentCaller::new();
    let mut session = f.start(&mut caller);
    let cancel = Cancellation::default();
    retained_prefix(&mut session, &cancel);
    let report = session.advance_with(&cancel, |step, stage| {
        if (step, stage) == (1, Stage::AfterCall) {
            change_time(&f.slot(0));
        }
        false
    });
    terminal(&mut session, report);
    drop(session);
    let actual = f.finish(report);
    check_old(&actual[1], &f.old);
    let (candidate, bytes) = actual[0].as_ref().unwrap();
    assert_eq!(bytes, NEW_BYTES);
    assert_eq!(candidate.last_write_time, 131_444_736_000_000_000);
    assert_eq!(report.outcome, Outcome::RecoveryRequired);
    assert_eq!(report.confirmed_prefix, 1);
    assert_eq!(report.attempted, [true, true]);
    assert_eq!(report.bindings, PREFIXES[2]);
}

#[test]
fn native_immediate_diagnostic_records_actual_recent_history_separately() {
    let mut f = Fixture::new("immediate-diagnostic");
    let mut caller = TrustedCurrentCaller::new();
    let cancel = Cancellation::default();
    let mut session = f
        .open(
            &mut caller,
            &mut LogicalBudget::new(u64::MAX),
            &cancel,
            ContinuationPolicy::ImmediateDiagnostic,
        )
        .unwrap_or_else(|report| panic!("open refused: {report:?}"));
    retained_prefix(&mut session, &cancel);
    let report = session.advance(&cancel);
    terminal(&mut session, report);
    drop(session);
    let actual = f.finish(report);
    check_old(&actual[1], &f.old);
    let (candidate, _) = actual[0].as_ref().unwrap();
    let prepared: Value =
        serde_json::from_slice(&fs::read(f.path.join("retain-install-0.record")).unwrap()).unwrap();
    assert_eq!(prepared["continuationPolicy"], "ImmediateDiagnostic");
    let differs = prepared["candidate"] != json!(candidate.binding_bytes());
    assert_eq!(
        report.outcome,
        if differs {
            Outcome::RecoveryRequired
        } else {
            Outcome::CompleteObserved
        }
    );
    assert_eq!(report.attempted, [true, true]);
    assert!(report.quiet_elapsed_nanos.unwrap() < 20_000_000_000);
}
