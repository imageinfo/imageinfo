//! Caller-level controls: synthetic authority checks are separate from actual
//! retained Windows exchange observations. No fixture authorizes restart work.
use crate::storage::custody::{CustodyRefusal, TrustedCurrentCaller};
use crate::storage::exchange_authority::{ExchangeAuthority, ExchangeBindings};
use crate::storage::path_cycle::Plan;
use crate::storage::runtime::Binding;
use std::path::Path;

fn plan_at(root: &str) -> Plan {
    let root = Path::new(root);
    Plan::new(
        root.join("a.bin"),
        root.join("b.bin"),
        root.join("temp.bin"),
    )
    .unwrap()
}
fn originals() -> [Binding; 2] {
    [
        Binding {
            identity: vec![1],
            facts: vec![11],
        },
        Binding {
            identity: vec![2],
            facts: vec![22],
        },
    ]
}
fn captured(
    operation: &str,
    root: &str,
    record: &str,
    originals: [Binding; 2],
) -> ExchangeBindings {
    ExchangeBindings::capture(operation, &plan_at(root), Path::new(record), originals).unwrap()
}
fn expected() -> ExchangeBindings {
    captured("authored-exchange", "authored", "records", originals())
}

#[test]
fn portable_authority_binds_every_caller_field() {
    let mut caller = TrustedCurrentCaller::new();
    let authority = ExchangeAuthority::authorize(&mut caller, expected()).unwrap();
    authority.check(&expected()).unwrap();
    let mut changed_identity = originals();
    changed_identity[0].identity = vec![9];
    let mut changed_property = originals();
    changed_property[1].facts = vec![99];
    let mut swapped = originals();
    swapped.swap(0, 1);
    for different in [
        captured("different-operation", "authored", "records", originals()),
        captured(
            "authored-exchange",
            "different-parent",
            "records",
            originals(),
        ),
        captured(
            "authored-exchange",
            "authored",
            "different-records",
            originals(),
        ),
        captured("authored-exchange", "authored", "records", changed_identity),
        captured("authored-exchange", "authored", "records", changed_property),
        captured("authored-exchange", "authored", "records", swapped),
    ] {
        assert!(authority.check(&different).is_err());
    }
    // A mismatch is not permission to substitute a new plan.
    authority.check(&expected()).unwrap();
}

#[test]
fn portable_revoked_dropped_and_replaced_callers_do_not_resurrect() {
    let mut caller = TrustedCurrentCaller::new();
    let revoked = ExchangeAuthority::authorize(&mut caller, expected()).unwrap();
    caller.revoke();
    assert_eq!(
        revoked.check(&expected()),
        Err(CustodyRefusal::StaleAuthority)
    );
    let replaced = ExchangeAuthority::authorize(&mut caller, expected()).unwrap();
    let current = ExchangeAuthority::authorize(&mut caller, expected()).unwrap();
    assert_eq!(
        replaced.check(&expected()),
        Err(CustodyRefusal::StaleAuthority)
    );
    current.check(&expected()).unwrap();
    drop(caller);
    assert_eq!(
        current.check(&expected()),
        Err(CustodyRefusal::StaleAuthority)
    );
    let mut fresh_caller = TrustedCurrentCaller::new();
    let fresh = ExchangeAuthority::authorize(&mut fresh_caller, expected()).unwrap();
    fresh.check(&expected()).unwrap();
    assert_eq!(
        revoked.check(&expected()),
        Err(CustodyRefusal::StaleAuthority)
    );
}

#[test]
fn portable_authority_construction_is_bounded() {
    let mut caller = TrustedCurrentCaller::new();
    let mut last = None;
    for _ in 0..4 {
        last = Some(ExchangeAuthority::authorize(&mut caller, expected()).unwrap());
    }
    assert!(matches!(
        ExchangeAuthority::authorize(&mut caller, expected()),
        Err(CustodyRefusal::ConstructionBound)
    ));
    assert_eq!(
        last.unwrap().check(&expected()),
        Err(CustodyRefusal::StaleAuthority)
    );
}

#[test]
fn portable_invalid_originals_cannot_be_authorized() {
    let mut duplicate = originals();
    duplicate[1].identity = duplicate[0].identity.clone();
    let mut empty = originals();
    empty[0].facts.clear();
    for invalid in [duplicate, empty] {
        assert!(
            ExchangeBindings::capture(
                "authored",
                &plan_at("authored"),
                Path::new("records"),
                invalid
            )
            .is_err()
        );
    }
}

#[cfg(windows)]
mod native {
    use super::*;
    use crate::storage::exchange::{Exchange, ExchangePlan, ExchangeReport};
    use crate::storage::path_cycle::{
        Binding as NameBinding, ContinuationPolicy, HookAction, HookStage, Outcome,
    };
    use crate::storage::{Cancellation, Failure};
    use imageinfo_windows_storage::{FileSnapshot, GuardedSource, PrivateRoot};
    use serde_json::{Value, json};
    use std::fs::{self, FileTimes, OpenOptions};
    use std::os::windows::fs::OpenOptionsExt;
    use std::path::PathBuf;
    use std::time::{Duration, SystemTime, UNIX_EPOCH};

    fn observe(path: &Path) -> Value {
        let guard = GuardedSource::open(path, 4096).unwrap();
        let s = guard.snapshot();
        json!({"identity":[s.volume_serial_number,s.file_index],"bytes":fs::read(path).unwrap(),
            "properties":{"size":s.size,"links":s.links,"attributes":s.attributes,
            "created":s.creation_time,"written":s.last_write_time,"security":s.owner_dacl}})
    }
    fn snap(path: &Path) -> FileSnapshot {
        GuardedSource::open(path, 4096).unwrap().snapshot().clone()
    }
    struct Fixture {
        root: PathBuf,
        initial: [Value; 2],
        snapshots: [FileSnapshot; 2],
    }
    impl Fixture {
        fn new(cell: u8) -> Self {
            let base = std::env::var_os("IMAGEINFO_EXCHANGE_EVIDENCE_ROOT")
                .map(PathBuf::from)
                .unwrap_or_else(|| {
                    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                        .join(".local")
                        .join("xchg")
                });
            fs::create_dir_all(&base).unwrap();
            let root = base.join(format!(
                "{cell}-{}-{}",
                std::process::id(),
                SystemTime::now()
                    .duration_since(UNIX_EPOCH)
                    .unwrap()
                    .as_nanos()
            ));
            let private = PrivateRoot::create(&root).unwrap();
            drop(
                private
                    .create_artifact("a.bin", b"authored exchange alpha\n", 4096)
                    .unwrap(),
            );
            // Fixture setup only: naturally different original creation times,
            // never a timestamp reset or continuation-policy substitution.
            std::thread::sleep(Duration::from_millis(2));
            drop(
                private
                    .create_artifact("b.bin", b"authored exchange beta\n", 4096)
                    .unwrap(),
            );
            drop(private);
            let initial = [observe(&root.join("a.bin")), observe(&root.join("b.bin"))];
            assert_ne!(initial[0]["identity"], initial[1]["identity"]);
            assert_ne!(
                initial[0]["properties"]["created"],
                initial[1]["properties"]["created"]
            );
            let snapshots = [snap(&root.join("a.bin")), snap(&root.join("b.bin"))];
            fs::write(
                root.join("initial.private.json"),
                serde_json::to_vec_pretty(&json!({
                "schema":"imageinfo.exchange-originals.v1","cell":cell,"originals":initial,
                "sourceManifests":source_manifests(),"authority":false}))
                .unwrap(),
            )
            .unwrap();
            Self {
                root,
                initial,
                snapshots,
            }
        }
        fn plan(&self) -> ExchangePlan {
            ExchangePlan::new(
                "authored-two-name-exchange",
                Plan::new(
                    self.root.join("a.bin"),
                    self.root.join("b.bin"),
                    self.root.join("temp.bin"),
                )
                .unwrap(),
                self.root.join("journal"),
                &self.snapshots[0],
                &self.snapshots[1],
            )
            .unwrap()
        }
        fn open(&self, caller: &mut TrustedCurrentCaller) -> Result<Exchange, Failure> {
            let plan = self.plan();
            let authority = ExchangeAuthority::authorize(caller, plan.bindings().clone()).unwrap();
            Exchange::open(plan, authority)
        }
        fn foreign(&self, leaf: &str) -> Value {
            use std::io::Write;
            let path = self.root.join(leaf);
            let mut file = OpenOptions::new()
                .write(true)
                .create_new(true)
                .open(&path)
                .unwrap();
            file.write_all(b"authored exchange foreign winner\n")
                .unwrap();
            drop(file);
            observe(&path)
        }
        fn retain(
            &self,
            cell: u8,
            report: Option<ExchangeReport>,
            map: [Option<usize>; 3],
            foreign: Option<(usize, Value)>,
            property_changed: bool,
            injected: bool,
        ) {
            let leaves = ["a.bin", "b.bin", "temp.bin"];
            let actual: Vec<Value> = leaves
                .iter()
                .map(|leaf| {
                    let path = self.root.join(leaf);
                    if path.try_exists().unwrap() {
                        observe(&path)
                    } else {
                        Value::Null
                    }
                })
                .collect();
            for (slot, original) in map.iter().enumerate() {
                if let Some(original) = original {
                    assert_eq!(
                        actual[slot]["identity"],
                        self.initial[*original]["identity"]
                    );
                    assert_eq!(actual[slot]["bytes"], self.initial[*original]["bytes"]);
                    if !property_changed || *original != 0 {
                        assert_eq!(
                            actual[slot]["properties"],
                            self.initial[*original]["properties"]
                        );
                    } else {
                        assert_ne!(
                            actual[slot]["properties"]["written"],
                            self.initial[*original]["properties"]["written"]
                        );
                        for field in ["size", "links", "attributes", "created", "security"] {
                            assert_eq!(
                                actual[slot]["properties"][field],
                                self.initial[*original]["properties"][field]
                            );
                        }
                    }
                } else if foreign
                    .as_ref()
                    .is_some_and(|(foreign_slot, _)| *foreign_slot == slot)
                {
                    assert_eq!(actual[slot], foreign.as_ref().unwrap().1);
                } else {
                    assert!(actual[slot].is_null());
                }
            }
            let mut journal = Vec::new();
            if self.root.join("journal").try_exists().unwrap() {
                let mut entries: Vec<_> = fs::read_dir(self.root.join("journal"))
                    .unwrap()
                    .map(|entry| entry.unwrap().path())
                    .collect();
                entries.sort();
                for path in entries {
                    let bytes = fs::read(&path).unwrap();
                    let record: Value = serde_json::from_slice(&bytes).unwrap();
                    assert_eq!(record["qualified"], false);
                    assert_eq!(record["restartAuthority"], false);
                    assert_eq!(record["continuationPolicy"], "GuardHeldQuiet20Seconds");
                    journal.push(json!({"leaf":path.file_name().unwrap().to_str().unwrap(),
                        "bytes":bytes,"record":record}));
                }
            }
            fs::write(
                self.root.join("evidence.private.json"),
                serde_json::to_vec_pretty(&json!({
                "schema":"imageinfo.exchange-caller-evidence.v1","cell":cell,
                "report":report.map(|r| json!({"outcome":format!("{:?}",r.cycle.outcome),
                "confirmedPrefix":r.cycle.confirmed_prefix,"bindings":r.cycle.bindings.map(|b| format!("{b:?}")),
                "uncertain":r.cycle.uncertain,"failure":r.failure.map(|f|format!("{f:?}")),"terminal":r.terminal})),
                "initial":self.initial,"actual":actual,
                "expectedOriginalMap":map,"foreign":foreign,"propertyChanged":property_changed,
                "injectedLostResponse":injected,"journal":journal,"authority":false,
                "committed":false,"restartAuthority":false}))
                .unwrap(),
            )
            .unwrap();
        }
    }
    fn source_manifests() -> Vec<Value> {
        use sha2::{Digest, Sha256};
        [
            "src/storage/exchange.rs",
            "src/storage/exchange/tests.rs",
            "src/storage/exchange_authority.rs",
            "src/storage/custody.rs",
            "src/storage/path_cycle.rs",
            "src/storage/windows.rs",
            "src/storage/runtime.rs",
            "src/storage/mod.rs",
            "Cargo.toml",
            "Cargo.lock",
            "crates/imageinfo-windows-storage/src/lib.rs",
            "crates/imageinfo-windows-storage/src/existing_move.rs",
            "crates/imageinfo-windows-storage/src/existing_properties.rs",
            "crates/imageinfo-windows-storage/src/native.rs",
            "crates/imageinfo-windows-storage/src/windows.rs",
        ]
        .iter()
        .map(|name| {
            let bytes = fs::read(Path::new(env!("CARGO_MANIFEST_DIR")).join(name)).unwrap();
            json!({"path":name,"bytes":bytes.len(),"sha256":format!("{:x}",Sha256::digest(&bytes))})
        })
        .collect()
    }
    fn first(exchange: &mut Exchange) {
        assert_eq!(
            exchange.policy(),
            ContinuationPolicy::GuardHeldQuiet20Seconds
        );
        let r = exchange.advance(&Cancellation::default());
        assert_eq!(r.cycle.confirmed_prefix, 1);
        assert_eq!(r.cycle.outcome, Outcome::Ready);
        assert!(!r.terminal);
    }
    fn terminal_same(exchange: &mut Exchange, report: ExchangeReport) {
        let journal = exchange.plan().names()[0].parent().unwrap().join("journal");
        let inventory = || {
            let mut entries: Vec<_> = fs::read_dir(&journal)
                .unwrap()
                .map(|entry| {
                    let path = entry.unwrap().path();
                    (
                        path.file_name().unwrap().to_os_string(),
                        fs::read(&path).unwrap(),
                    )
                })
                .collect();
            entries.sort();
            entries
        };
        let before = inventory();
        let again = exchange.advance(&Cancellation::default());
        assert_eq!(format!("{again:?}"), format!("{report:?}"));
        assert!(again.terminal);
        assert_eq!(
            inventory(),
            before,
            "terminal advance must retain the exact journal"
        );
    }

    #[test]
    fn native_01_complete_exchange() {
        let f = Fixture::new(1);
        let mut caller = TrustedCurrentCaller::new();
        let mut exchange = f.open(&mut caller).unwrap();
        first(&mut exchange);
        assert_eq!(
            exchange
                .advance(&Cancellation::default())
                .cycle
                .confirmed_prefix,
            2
        );
        let report = exchange.advance(&Cancellation::default());
        assert_eq!(report.cycle.outcome, Outcome::CompleteObserved);
        assert_eq!(
            report.cycle.bindings,
            [NameBinding::Beta, NameBinding::Alpha, NameBinding::Absent]
        );
        assert_eq!(report.failure, None);
        assert!(
            exchange
                .quiet_elapsed_nanos()
                .iter()
                .all(|n| n.is_some_and(|n| n >= 20_000_000_000))
        );
        terminal_same(&mut exchange, report);
        drop(exchange);
        f.retain(
            1,
            Some(report),
            [Some(1), Some(0), None],
            None,
            false,
            false,
        );
    }
    #[test]
    fn native_02_occupied_temp() {
        let f = Fixture::new(2);
        let foreign = f.foreign("temp.bin");
        let mut caller = TrustedCurrentCaller::new();
        assert!(f.open(&mut caller).is_err());
        f.retain(
            2,
            None,
            [Some(0), Some(1), None],
            Some((2, foreign)),
            false,
            false,
        );
    }
    #[test]
    fn native_03_late_foreign_winner() {
        let f = Fixture::new(3);
        let mut caller = TrustedCurrentCaller::new();
        let mut exchange = f.open(&mut caller).unwrap();
        first(&mut exchange);
        let foreign = f.foreign("a.bin");
        let report = exchange.advance(&Cancellation::default());
        assert_eq!(report.cycle.confirmed_prefix, 1);
        assert_eq!(report.cycle.outcome, Outcome::Partial);
        assert_eq!(
            report.cycle.bindings,
            [NameBinding::Foreign, NameBinding::Beta, NameBinding::Alpha]
        );
        terminal_same(&mut exchange, report);
        drop(exchange);
        f.retain(
            3,
            Some(report),
            [None, Some(1), Some(0)],
            Some((0, foreign)),
            false,
            false,
        );
    }
    #[test]
    fn native_04_property_identity_binding_mismatch() {
        let f = Fixture::new(4);
        // A real preopened setter remains effective through the original guard.
        let actor = OpenOptions::new()
            .access_mode(0x100)
            .share_mode(7)
            .open(f.root.join("a.bin"))
            .unwrap();
        let mut caller = TrustedCurrentCaller::new();
        let mut exchange = f.open(&mut caller).unwrap();
        first(&mut exchange);
        actor
            .set_times(
                FileTimes::new().set_modified(UNIX_EPOCH + Duration::from_secs(1_500_000_000)),
            )
            .unwrap();
        let report = exchange.advance(&Cancellation::default());
        assert_eq!(report.cycle.confirmed_prefix, 1);
        assert_eq!(report.cycle.outcome, Outcome::RecoveryRequired);
        assert!(report.cycle.uncertain);
        terminal_same(&mut exchange, report);
        drop(exchange);
        drop(actor);
        f.retain(4, Some(report), [None, Some(1), Some(0)], None, true, false);
    }
    #[test]
    fn native_05_cancel_at_confirmed_prefix() {
        let f = Fixture::new(5);
        let mut caller = TrustedCurrentCaller::new();
        let mut exchange = f.open(&mut caller).unwrap();
        first(&mut exchange);
        let cancel = Cancellation::default();
        cancel.request();
        let report = exchange.advance(&cancel);
        assert_eq!(report.cycle.confirmed_prefix, 1);
        assert_eq!(report.cycle.outcome, Outcome::Partial);
        assert_eq!(report.failure, Some(Failure::Cancelled));
        terminal_same(&mut exchange, report);
        drop(exchange);
        f.retain(
            5,
            Some(report),
            [None, Some(1), Some(0)],
            None,
            false,
            false,
        );
    }
    #[test]
    fn native_06_injected_uncertain_response() {
        let f = Fixture::new(6);
        let mut caller = TrustedCurrentCaller::new();
        let mut exchange = f.open(&mut caller).unwrap();
        let report = exchange.advance_with(&Cancellation::default(), |_, stage| {
            if stage == HookStage::AfterCall {
                HookAction::LostResponse
            } else {
                HookAction::Continue
            }
        });
        assert_eq!(report.cycle.confirmed_prefix, 0);
        assert_eq!(report.cycle.outcome, Outcome::RecoveryRequired);
        assert_eq!(
            report.cycle.bindings,
            [
                NameBinding::Unknown,
                NameBinding::Beta,
                NameBinding::Unknown
            ]
        );
        assert_eq!(report.failure, Some(Failure::Ambiguous));
        terminal_same(&mut exchange, report);
        drop(exchange);
        // The auditor sees actual moved alpha; caller still reports unknown.
        f.retain(6, Some(report), [None, Some(1), Some(0)], None, false, true);
    }
}

#[test]
fn portable_uncertainty_preserves_unknown_names_and_dominates_failure() {
    use crate::storage::Failure;
    use crate::storage::exchange::ExchangeReport;
    use crate::storage::path_cycle::{Binding as NameBinding, Outcome, Report};
    let cycle = Report {
        outcome: Outcome::RecoveryRequired,
        confirmed_prefix: 1,
        bindings: [
            NameBinding::Unknown,
            NameBinding::Unknown,
            NameBinding::Alpha,
        ],
        uncertain: true,
    };
    let report = ExchangeReport::from_cycle(cycle, Some(Failure::Cancelled), false);
    assert_eq!(report.cycle, cycle);
    assert_eq!(report.failure, Some(Failure::Ambiguous));
    assert!(report.terminal);
    let complete = ExchangeReport::from_cycle(
        Report {
            outcome: Outcome::CompleteObserved,
            confirmed_prefix: 3,
            bindings: [NameBinding::Beta, NameBinding::Alpha, NameBinding::Absent],
            uncertain: false,
        },
        None,
        false,
    );
    assert_eq!(complete.cycle.outcome, Outcome::CompleteObserved);
    assert!(complete.terminal);
    assert_eq!(complete.failure, None);
}

#[test]
fn portable_restart_and_exchange_share_revocation_and_construction_budget() {
    use crate::storage::custody::{CurrentBindings, CurrentCallerHistory, RestartAction};
    use crate::storage::runtime::Artifact;
    let binding = |n| Binding {
        identity: vec![n],
        facts: vec![n, 8],
    };
    // This independent legacy restart observation is a test control only. It is
    // never constructed by the exchange adapter or relabeled as exchange data.
    let restart = CurrentBindings::capture(
        "legacy-control",
        "authored",
        "authored",
        "output.bin",
        &binding(9),
        &(1..=5).map(binding).collect::<Vec<_>>(),
        &[(Artifact::Prepared, vec![5]), (Artifact::Intent, vec![6])],
        false,
    )
    .unwrap();
    let mut caller = TrustedCurrentCaller::new();
    caller
        .attest_current(restart.clone(), CurrentCallerHistory::StoppedBeforeRelease)
        .unwrap();
    let old_restart = caller
        .authorize(RestartAction::PruneUnpublished, &restart)
        .unwrap();
    let exchange = ExchangeAuthority::authorize(&mut caller, expected()).unwrap();
    assert_eq!(
        old_restart.validate(RestartAction::PruneUnpublished, &restart),
        Err(CustodyRefusal::StaleAuthority)
    );
    assert!(matches!(
        caller.authorize(RestartAction::PruneUnpublished, &restart),
        Err(CustodyRefusal::MissingAuthority)
    ));
    caller
        .attest_current(restart.clone(), CurrentCallerHistory::StoppedBeforeRelease)
        .unwrap();
    assert_eq!(
        exchange.check(&expected()),
        Err(CustodyRefusal::StaleAuthority)
    );
    let fourth = ExchangeAuthority::authorize(&mut caller, expected()).unwrap();
    assert_eq!(
        caller.attest_current(restart, CurrentCallerHistory::StoppedBeforeRelease),
        Err(CustodyRefusal::ConstructionBound)
    );
    assert_eq!(
        fourth.check(&expected()),
        Err(CustodyRefusal::StaleAuthority)
    );
}
