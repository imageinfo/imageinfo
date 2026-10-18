//! Authored-only, retained native fixtures. The primary operator runs these
//! serially. None of the helpers delete fixtures or authorize restart actions.
use super::*;
use crate::storage::Cancellation;
use imageinfo_windows_storage::{FileSnapshot, GuardedSource, PrivateRoot};
use serde_json::{Value, json};
use std::{
    fs::{self, FileTimes, OpenOptions},
    os::windows::fs::OpenOptionsExt,
    path::{Path, PathBuf},
    process::Command,
    time::{Duration, SystemTime, UNIX_EPOCH},
};

fn observation(path: &Path) -> Value {
    let held = GuardedSource::open(path, 4096).unwrap();
    let s = held.snapshot();
    json!({"identity": [s.volume_serial_number, s.file_index],
        "bytes": fs::read(path).unwrap(),
        "properties": {"size":s.size,"links":s.links,"attributes":s.attributes,
        "created":s.creation_time,"written":s.last_write_time,"security":s.owner_dacl}})
}
fn snapshot(path: &Path) -> FileSnapshot {
    GuardedSource::open(path, 4096).unwrap().snapshot().clone()
}

fn evidence_root() -> PathBuf {
    if let Some(root) = std::env::var_os("IMAGEINFO_CYCLE_EVIDENCE_ROOT") {
        return PathBuf::from(root);
    }
    // Ordinary root/CI tests exercise real fresh fixtures too. One process-local
    // session directory keeps them together without reusing any earlier root.
    static DEFAULT_ROOT: std::sync::OnceLock<PathBuf> = std::sync::OnceLock::new();
    DEFAULT_ROOT
        .get_or_init(|| {
            std::env::current_dir()
                .unwrap()
                .join(".local")
                .join("native-cycle")
                .join(format!(
                    "session-{}-{}",
                    std::process::id(),
                    SystemTime::now()
                        .duration_since(UNIX_EPOCH)
                        .unwrap()
                        .as_nanos()
                ))
        })
        .clone()
}
struct Fixture {
    root: PathBuf,
    initial: Value,
    originals: Option<(FileSnapshot, FileSnapshot)>,
}
impl Fixture {
    fn new(cell: u8) -> Self {
        let base = evidence_root();
        fs::create_dir_all(&base).unwrap();
        let root = if let Some(path) = std::env::var_os("IMAGEINFO_CYCLE_EXIT_FIXTURE") {
            PathBuf::from(path)
        } else {
            base.join(format!(
                "{cell:02}-{}-{}",
                std::process::id(),
                SystemTime::now()
                    .duration_since(UNIX_EPOCH)
                    .unwrap()
                    .as_nanos()
            ))
        };
        let private = PrivateRoot::create(&root).unwrap();
        fs::write(
            root.join("attempt.private.json"),
            serde_json::to_vec_pretty(&json!({
                "schema":"imageinfo.native-cycle-attempt.v1","cell":cell,"authority":false
            }))
            .unwrap(),
        )
        .unwrap();
        for (name, bytes) in [
            ("a.bin", b"authored alpha original\n".as_slice()),
            ("b.bin", b"authored beta original\n".as_slice()),
        ] {
            drop(private.create_artifact(name, bytes, 4096).unwrap());
        }
        drop(private);
        let initial = json!({"alpha":observation(&root.join("a.bin")),
                             "beta":observation(&root.join("b.bin"))});
        fs::write(
            root.join("initial.private.json"),
            serde_json::to_vec_pretty(&initial).unwrap(),
        )
        .unwrap();
        let originals = Some((snapshot(&root.join("a.bin")), snapshot(&root.join("b.bin"))));
        assert_ne!(
            initial["alpha"]["properties"]["created"], initial["beta"]["properties"]["created"],
            "distinct naturally-created originals required; retain failed attempt"
        );
        Self {
            root,
            initial,
            originals,
        }
    }
    fn plan(&self) -> Plan {
        Plan::new(
            self.root.join("a.bin"),
            self.root.join("b.bin"),
            self.root.join("temp.bin"),
        )
        .unwrap()
    }
    fn open(&self) -> std::io::Result<Cycle> {
        let (alpha, beta) = self.originals.as_ref().unwrap();
        Cycle::open_with_policy(
            self.plan(),
            alpha,
            beta,
            &self.root.join("journal"),
            ContinuationPolicy::GuardHeldQuiet20Seconds,
        )
    }
    fn foreign(&mut self, slot: &str) {
        let path = self.root.join(format!("{slot}.bin"));
        let mut f = OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&path)
            .unwrap();
        std::io::Write::write_all(&mut f, b"authored foreign winner\n").unwrap();
        drop(f);
        self.initial["foreign"] = observation(&path);
    }
    #[allow(clippy::too_many_arguments)] // Fixed retained-cell audit columns.
    fn retain(
        &self,
        cell: u8,
        prefix: usize,
        foreign: Option<&str>,
        events: Value,
        classification: &str,
        kind: &str,
        changed: Value,
    ) {
        let mut map = serde_json::Map::new();
        for slot in ["a", "b", "temp"] {
            let path = self.root.join(format!("{slot}.bin"));
            map.insert(
                slot.into(),
                if path.try_exists().unwrap() {
                    observation(&path)
                } else {
                    Value::Null
                },
            );
        }
        let row = json!({"schema":"imageinfo.native-cycle-evidence.v1", "cell":cell,
            "authority":false, "initial":self.initial, "final":map, "actual_prefix":prefix,
            "foreign_slot":foreign, "events":events, "classification":classification,
            "native_error_kind":kind, "changed_property":changed});
        fs::write(
            self.root.join("evidence.private.json"),
            serde_json::to_vec_pretty(&row).unwrap(),
        )
        .unwrap();
    }
}
fn prefix(n: usize) -> Vec<Value> {
    ["a-to-temp", "b-to-a", "temp-to-b"]
        .into_iter()
        .take(n)
        .map(|id| json!({"kind":"move","id":id,"outcome":"applied"}))
        .collect()
}
fn run_n(cycle: &mut Cycle, n: usize) {
    for count in 1..=n {
        let report = cycle.advance(&Cancellation::default());
        assert_eq!(usize::from(report.confirmed_prefix), count);
        assert_eq!(
            report.outcome,
            if count == 3 {
                Outcome::CompleteObserved
            } else {
                Outcome::Ready
            }
        );
    }
}

#[test]
fn native_01_complete() {
    let f = Fixture::new(1);
    let mut c = f.open().unwrap();
    run_n(&mut c, 3);
    drop(c);
    let mut events = prefix(3);
    events.push(json!({"kind":"verify","outcome":"matched"}));
    f.retain(
        1,
        3,
        None,
        json!(events),
        "complete-observed",
        "none",
        json!({}),
    );
}
#[test]
fn native_02_occupied_initial_temp() {
    let mut f = Fixture::new(2);
    f.foreign("temp");
    let error = f.open().err().expect("occupied temp must refuse");
    fs::write(f.root.join("refusal.private.txt"), format!("{error:?}\n")).unwrap();
    f.retain(
        2,
        0,
        Some("temp"),
        json!([{"kind":"foreign","slot":"temp"},
        {"kind":"stop","reason":"foreign-winner"}]),
        "no-effect",
        "initial-map-refusal",
        json!({}),
    );
}
fn winner(cell: u8, n: usize, slot: &str) {
    let mut f = Fixture::new(cell);
    let mut c = f.open().unwrap();
    run_n(&mut c, n);
    let report = c.advance_with(&Cancellation::default(), |_, stage| {
        if stage == HookStage::BeforeCall {
            f.foreign(slot);
        }
        HookAction::Continue
    });
    assert_eq!(report.confirmed_prefix as usize, n);
    assert_eq!(
        report.outcome,
        if n == 0 {
            Outcome::NoEffect
        } else {
            Outcome::Partial
        }
    );
    // A terminal stop cannot issue a later move or compensate.
    assert_eq!(
        c.advance(&Cancellation::default()).confirmed_prefix as usize,
        n
    );
    drop(c);
    let mut events = prefix(n);
    events.push(json!({"kind":"foreign","slot":slot}));
    events.push(
        json!({"kind":"move","id":(["a-to-temp","b-to-a","temp-to-b"][n]),"outcome":"not-applied"}),
    );
    f.retain(
        cell,
        n,
        Some(slot),
        json!(events),
        if n == 0 { "no-effect" } else { "partial" },
        "none",
        json!({}),
    );
}
#[test]
fn native_03_winner_temp() {
    winner(3, 0, "temp");
}
#[test]
fn native_04_winner_a() {
    winner(4, 1, "a");
}
#[test]
fn native_05_winner_b() {
    winner(5, 2, "b");
}
fn injected_stop(cell: u8, n: usize) {
    let f = Fixture::new(cell);
    let mut c = f.open().unwrap();
    run_n(&mut c, n);
    let report = c.advance_with(&Cancellation::default(), |_, stage| {
        if stage == HookStage::BeforeCall {
            HookAction::Stop
        } else {
            HookAction::Continue
        }
    });
    assert_eq!(report.confirmed_prefix as usize, n);
    assert_eq!(report.outcome, Outcome::Partial);
    assert_eq!(
        c.advance(&Cancellation::default()).confirmed_prefix as usize,
        n
    );
    drop(c);
    let mut events = prefix(n);
    events.push(json!({"kind":"stop","reason":"cancel"}));
    f.retain(
        cell,
        n,
        None,
        json!(events),
        "partial",
        "injected-boundary-stop",
        json!({}),
    );
}
#[test]
fn native_06_stop_after_first_prefix() {
    injected_stop(6, 1);
}
#[test]
fn native_07_stop_after_second_and_third_prefix() {
    injected_stop(7, 2);
    let f = Fixture::new(7);
    let mut c = f.open().unwrap();
    run_n(&mut c, 2);
    let report = c.advance_with(&Cancellation::default(), |_, stage| {
        if stage == HookStage::Confirmed {
            HookAction::Stop
        } else {
            HookAction::Continue
        }
    });
    assert_eq!(report.confirmed_prefix, 3);
    assert_eq!(report.outcome, Outcome::Partial);
    assert_eq!(
        c.advance(&Cancellation::default()).outcome,
        Outcome::Partial
    );
    drop(c);
    let mut events = prefix(3);
    events.push(json!({"kind":"stop","reason":"cancel"}));
    f.retain(
        7,
        3,
        None,
        json!(events),
        "partial",
        "injected-boundary-stop",
        json!({}),
    );
}
#[test]
fn native_08_preopened_writer_and_name_actor() {
    for access in [0x4000_0000, 0x0001_0000] {
        let f = Fixture::new(8);
        let actor = OpenOptions::new()
            .access_mode(access)
            .share_mode(7)
            .open(f.root.join("a.bin"))
            .unwrap();
        let error = f
            .open()
            .err()
            .expect("preopened conflicting access must refuse");
        assert!(
            error.raw_os_error().is_some(),
            "expected actual OS sharing refusal: {error:?}"
        );
        fs::write(
            f.root.join("native-error.private.json"),
            serde_json::to_vec(&json!({
            "rawOsError":error.raw_os_error(),"access":access}))
            .unwrap(),
        )
        .unwrap();
        fs::write(f.root.join("refusal.private.txt"), format!("{error:?}\n")).unwrap();
        drop(actor);
        f.retain(
            8,
            0,
            None,
            json!([{"kind":"stop","reason":"property-mismatch"}]),
            "no-effect",
            "actor-open-os-error",
            json!({}),
        );
    }
}
#[test]
fn native_09_preopened_property_mismatch() {
    let f = Fixture::new(9);
    let actor = OpenOptions::new()
        .access_mode(0x100)
        .share_mode(7)
        .open(f.root.join("a.bin"))
        .unwrap();
    let mut c = f.open().unwrap();
    run_n(&mut c, 1);
    actor
        .set_times(FileTimes::new().set_modified(UNIX_EPOCH + Duration::from_secs(1_500_000_000)))
        .unwrap();
    let report = c.advance(&Cancellation::default());
    assert_eq!(report.confirmed_prefix, 1);
    assert_eq!(report.outcome, Outcome::RecoveryRequired);
    drop(c);
    drop(actor);
    let changed = json!({"alpha":observation(&f.root.join("temp.bin"))["properties"]});
    let mut events = prefix(1);
    events.push(json!({"kind":"stop","reason":"property-mismatch"}));
    f.retain(
        9,
        1,
        None,
        json!(events),
        "recovery-required",
        "property-check-refusal",
        changed,
    );
}
#[test]
fn native_10_cancellation() {
    let f = Fixture::new(10);
    let mut c = f.open().unwrap();
    run_n(&mut c, 1);
    let cancel = Cancellation::default();
    cancel.request();
    let report = c.advance(&cancel);
    assert_eq!(report.outcome, Outcome::Partial);
    assert_eq!(report.confirmed_prefix, 1);
    assert_eq!(c.advance(&Cancellation::default()).confirmed_prefix, 1);
    drop(c);
    let mut events = prefix(1);
    events.push(json!({"kind":"stop","reason":"cancel"}));
    f.retain(10, 1, None, json!(events), "partial", "cancel", json!({}));
}
#[test]
fn native_10_cancellation_during_actual_guard_held_wait() {
    let f = Fixture::new(10);
    let mut c = f.open().unwrap();
    run_n(&mut c, 1);
    let cancel = Cancellation::default();
    let report = std::thread::scope(|scope| {
        scope.spawn(|| {
            std::thread::sleep(Duration::from_millis(100));
            cancel.request();
        });
        c.advance(&cancel)
    });
    assert_eq!(report.outcome, Outcome::Partial);
    assert_eq!(report.confirmed_prefix, 1);
    let elapsed = c.quiet_elapsed_nanos()[0].expect("actual engine wait must have started");
    assert!(
        elapsed > 0 && elapsed < 20_000_000_000,
        "cancellation must stop during the fixed gap"
    );
    assert_eq!(
        c.advance(&Cancellation::default()).outcome,
        Outcome::Partial
    );
    drop(c);
    let mut events = prefix(1);
    events.push(json!({"kind":"stop","reason":"cancel"}));
    f.retain(
        10,
        1,
        None,
        json!(events),
        "partial",
        "cancel-during-wait",
        json!({}),
    );
}
#[test]
fn native_11_process_exit() {
    let base = evidence_root();
    let root = base.join(format!(
        "11-exit-{}-{}",
        std::process::id(),
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    let status = Command::new(std::env::current_exe().unwrap())
        .args([
            "--exact",
            "storage::path_cycle::native_tests::native_exit_worker",
            "--nocapture",
        ])
        .env("IMAGEINFO_CYCLE_EXIT_FIXTURE", &root)
        .env("IMAGEINFO_CYCLE_EVIDENCE_ROOT", &base)
        .status()
        .unwrap();
    assert_eq!(status.code(), Some(23));
    let f = Fixture {
        initial: serde_json::from_slice(&fs::read(root.join("initial.private.json")).unwrap())
            .unwrap(),
        root,
        originals: None,
    };
    let mut events = prefix(1);
    events.push(json!({"kind":"stop","reason":"restart"}));
    f.retain(
        11,
        1,
        None,
        json!(events),
        "recovery-required",
        "process-exit",
        json!({}),
    );
}
#[test]
fn native_exit_worker() {
    if std::env::var_os("IMAGEINFO_CYCLE_EXIT_FIXTURE").is_none() {
        return;
    }
    let f = Fixture::new(11);
    let mut c = f.open().unwrap();
    run_n(&mut c, 1);
    // This actually exits the child without unwinding its live guards. The
    // parent only observes retained objects; it never imports or replays a plan.
    std::process::exit(23);
}
#[test]
fn native_12_lost_response() {
    let f = Fixture::new(12);
    let mut c = f.open().unwrap();
    let report = c.advance_with(&Cancellation::default(), |_, stage| {
        if stage == HookStage::AfterCall {
            HookAction::LostResponse
        } else {
            HookAction::Continue
        }
    });
    assert_eq!(report.outcome, Outcome::RecoveryRequired);
    assert_eq!(report.confirmed_prefix, 0);
    assert_eq!(
        c.advance(&Cancellation::default()).outcome,
        Outcome::RecoveryRequired
    );
    drop(c);
    f.retain(
        12,
        1,
        None,
        json!([{"kind":"move","id":"a-to-temp","outcome":"unknown"}]),
        "recovery-required",
        "discarded-response",
        json!({}),
    );
}

#[test]
fn native_13_actual_property_checkpoint_failure_before_first_move() {
    let f = Fixture::new(13);
    let actor = OpenOptions::new()
        .access_mode(0x100)
        .share_mode(7)
        .open(f.root.join("a.bin"))
        .unwrap();
    let mut c = f.open().unwrap();
    let report = c.advance_with(&Cancellation::default(), |_, stage| {
        if stage == HookStage::BeforeCall {
            actor
                .set_times(
                    FileTimes::new().set_modified(UNIX_EPOCH + Duration::from_secs(1_500_000_000)),
                )
                .unwrap();
        }
        HookAction::Continue
    });
    assert_eq!(report.confirmed_prefix, 0);
    assert_eq!(report.outcome, Outcome::RecoveryRequired);
    assert!(report.uncertain);
    assert_eq!(
        c.advance(&Cancellation::default()).outcome,
        Outcome::RecoveryRequired
    );
    drop(c);
    drop(actor);
    let changed = json!({"alpha":observation(&f.root.join("a.bin"))["properties"]});
    f.retain(
        13,
        0,
        None,
        json!([{"kind":"stop","reason":"guard-lost"}]),
        "recovery-required",
        "property-check-refusal",
        changed,
    );
}

/// A second process reopens retained artifacts after every worker has exited.
/// It never constructs Cycle or imports custody/restart authority.
#[test]
#[ignore = "primary runs separately after the finite native worker suite"]
fn native_retained_inspection() {
    use sha2::{Digest, Sha256};
    let base = PathBuf::from(std::env::var_os("IMAGEINFO_CYCLE_EVIDENCE_ROOT").unwrap());
    let mut count = 0;
    for entry in fs::read_dir(&base).unwrap() {
        let root = entry.unwrap().path();
        let path = root.join("evidence.private.json");
        if !path.is_file() {
            continue;
        }
        let bytes = fs::read(&path).unwrap();
        let row: Value = serde_json::from_slice(&bytes).unwrap();
        let mut current = serde_json::Map::new();
        for slot in ["a", "b", "temp"] {
            let path = root.join(format!("{slot}.bin"));
            current.insert(
                slot.into(),
                if path.try_exists().unwrap() {
                    observation(&path)
                } else {
                    Value::Null
                },
            );
        }
        assert_eq!(Value::Object(current.clone()), row["final"]);
        let journal_path = root.join("journal");
        let mut journal = Vec::new();
        if journal_path.try_exists().unwrap() {
            for entry in fs::read_dir(&journal_path).unwrap() {
                let path = entry.unwrap().path();
                assert!(path.is_file(), "unexpected retained journal entry");
                journal.push(json!({"name":path.file_name().unwrap().to_str().unwrap(),
                    "sha256":format!("{:x}",Sha256::digest(fs::read(&path).unwrap()))}));
            }
        }
        journal.sort_by_key(|item| item["name"].as_str().unwrap().to_owned());
        fs::write(
            root.join("inspection.private.json"),
            serde_json::to_vec_pretty(&json!({
            "schema":"imageinfo.native-cycle-retained-inspection.v1",
            "evidenceSha256":format!("{:x}",Sha256::digest(&bytes)),
            "final":current,"authority":false,"journalSha256":journal}))
            .unwrap(),
        )
        .unwrap();
        count += 1;
    }
    assert_eq!(count, 16, "fresh full-suite retained root required");
}

/// One bounded candidate only. Separate from the original finite matrix until
/// the primary has reviewed its real completion and retained observations.
#[test]
#[ignore = "primary-only single selected-policy completion candidate"]
fn native_delayed_candidate_completion() {
    let f = Fixture::new(90);
    let (alpha, beta) = f.originals.as_ref().unwrap();
    assert_ne!(
        alpha.creation_time, beta.creation_time,
        "equal-time fixture cannot test preservation"
    );
    let mut c = Cycle::open_with_policy(
        f.plan(),
        alpha,
        beta,
        &f.root.join("journal"),
        ContinuationPolicy::GuardHeldQuiet20Seconds,
    )
    .unwrap();
    assert_eq!(c.policy(), ContinuationPolicy::GuardHeldQuiet20Seconds);
    let mut reports = Vec::new();
    for _ in 0..3 {
        let report = c.advance(&Cancellation::default());
        reports.push(report);
        if report.outcome != Outcome::Ready {
            break;
        }
    }
    let policy = format!("{:?}", c.policy());
    let intervals = c.quiet_elapsed_nanos();
    let outcome = c.report();
    drop(c);
    let mut final_map = serde_json::Map::new();
    for slot in ["a", "b", "temp"] {
        let path = f.root.join(format!("{slot}.bin"));
        final_map.insert(
            slot.into(),
            if path.try_exists().unwrap() {
                observation(&path)
            } else {
                Value::Null
            },
        );
    }
    // Retain the attempted result before asserting positive acceptance, so a
    // changed property or a failed boundary remains an explicit contrary fact.
    fs::write(
        f.root.join("candidate.private.json"),
        serde_json::to_vec_pretty(&json!({
            "schema":"imageinfo.cycle-delayed-candidate.v1","authority":false,
            "initial":f.initial,"final":final_map,"policy":policy,"quietElapsedNanos":intervals,
            "confirmedPrefix":outcome.confirmed_prefix,"uncertain":outcome.uncertain,
            "outcome":format!("{:?}",outcome.outcome),"reports":format!("{reports:?}")
        }))
        .unwrap(),
    )
    .unwrap();
    assert_eq!(outcome.outcome, Outcome::CompleteObserved);
    assert_eq!(outcome.confirmed_prefix, 3);
    assert!(!outcome.uncertain);
    assert!(
        intervals
            .into_iter()
            .all(|v| v.is_some_and(|n| n >= 20_000_000_000))
    );
}

#[test]
#[ignore = "primary-only read-only observation of retained immediate counterexample"]
fn native_retained_immediate_counterexample() {
    use sha2::{Digest, Sha256};
    let failed = PathBuf::from(std::env::var_os("IMAGEINFO_CYCLE_FAILED_EVIDENCE_ROOT").unwrap());
    let mut cases = fs::read_dir(&failed)
        .unwrap()
        .map(|e| e.unwrap().path())
        .filter(|p| p.file_name().unwrap().to_string_lossy().starts_with("01-"))
        .collect::<Vec<_>>();
    assert_eq!(
        cases.len(),
        1,
        "one retained failed completion fixture required"
    );
    let failed = cases.pop().unwrap();
    let bytes = fs::read(failed.join("initial.private.json")).unwrap();
    let initial: Value = serde_json::from_slice(&bytes).unwrap();
    let alpha = observation(&failed.join("temp.bin"));
    let beta = observation(&failed.join("a.bin"));
    assert!(!failed.join("b.bin").try_exists().unwrap());
    assert_eq!(alpha, initial["alpha"]);
    assert_eq!(beta["identity"], initial["beta"]["identity"]);
    assert_eq!(beta["bytes"], initial["beta"]["bytes"]);
    let mut expected = initial["beta"]["properties"].clone();
    assert_ne!(
        expected["created"],
        initial["alpha"]["properties"]["created"]
    );
    expected["created"] = initial["alpha"]["properties"]["created"].clone();
    assert_eq!(
        beta["properties"], expected,
        "only diagnosed creation-time change expected"
    );
    let out = PathBuf::from(std::env::var_os("IMAGEINFO_CYCLE_EVIDENCE_ROOT").unwrap());
    fs::create_dir_all(&out).unwrap();
    fs::write(
        out.join("immediate-counterexample.private.json"),
        serde_json::to_vec_pretty(&json!({
            "schema":"imageinfo.cycle-immediate-counterexample.v1","authority":false,
            "failedRoot":failed,"initialSha256":format!("{:x}",Sha256::digest(bytes)),
            "initial":initial,"final":{"a":beta,"b":null,"temp":alpha},
            "classification":"recovery-required","positiveAcceptance":false
        }))
        .unwrap(),
    )
    .unwrap();
}

#[test]
#[ignore = "primary-only separate process reopens the one delayed candidate"]
fn native_delayed_candidate_inspection() {
    use sha2::{Digest, Sha256};
    let base = PathBuf::from(std::env::var_os("IMAGEINFO_CYCLE_EVIDENCE_ROOT").unwrap());
    let mut count = 0;
    for entry in fs::read_dir(&base).unwrap() {
        let root = entry.unwrap().path();
        let path = root.join("candidate.private.json");
        if !path.is_file() {
            continue;
        }
        let bytes = fs::read(&path).unwrap();
        let row: Value = serde_json::from_slice(&bytes).unwrap();
        let mut map = serde_json::Map::new();
        for slot in ["a", "b", "temp"] {
            let path = root.join(format!("{slot}.bin"));
            map.insert(
                slot.into(),
                if path.try_exists().unwrap() {
                    observation(&path)
                } else {
                    Value::Null
                },
            );
        }
        assert_eq!(Value::Object(map.clone()), row["final"]);
        let mut journal = Vec::new();
        for index in 0..8 {
            let bytes =
                fs::read(root.join("journal").join(format!("cycle-{index}.record"))).unwrap();
            journal.push(format!("{:x}", Sha256::digest(bytes)));
        }
        fs::write(
            root.join("candidate-inspection.private.json"),
            serde_json::to_vec_pretty(&json!({
                "schema":"imageinfo.cycle-delayed-candidate-inspection.v1","authority":false,
                "candidateSha256":format!("{:x}",Sha256::digest(bytes)),"final":map,
                "journalSha256":journal
            }))
            .unwrap(),
        )
        .unwrap();
        count += 1;
    }
    assert_eq!(count, 1, "one fresh candidate attempt only");
}
