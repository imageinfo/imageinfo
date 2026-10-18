//! Authored portable controls and retained native controls. Parent alone runs
//! native cells. Lost responses are injected at the caller boundary, never
//! described as an ambiguous Windows return or a qualified commitment.

use super::*;
use crate::storage::path_rename::RenamePlan;
use std::path::Path;

fn rename(root: &str, old: &str, new: &str, temp: Option<&str>) -> RenamePlan {
    let root = Path::new(root);
    RenamePlan::new(
        &root.join(old),
        &root.join(new),
        temp.map(|t| root.join(t)).as_deref(),
    )
    .unwrap()
}

#[test]
fn portable_explicit_pair_preserves_order_and_bounded_steps() {
    let raw = rename("selected", "image.cr3", "IMAGE.CR3", Some("raw.tmp"));
    let xmp = rename("selected", "unrelated.xmp", "XMP.xmp", None);
    let pair = PairNames::new([raw.clone(), xmp.clone()]).unwrap();
    assert_eq!(pair.plans(), &[raw, xmp]);
    assert_eq!(pair.plans()[0].steps().len(), 2);
    assert_eq!(pair.plans()[1].steps().len(), 1);
    // Explicit pairing permits unrelated basenames; no inference is performed.
}

#[test]
fn portable_pair_rejects_cross_member_aliases_and_parents() {
    let a = rename("selected", "a.cr3", "a-new.cr3", None);
    for b in [
        rename("other", "b.xmp", "b-new.xmp", None),
        rename("selected", "b.xmp", "B.XMP", Some("A.CR3")),
        rename("selected", "b.xmp", "B.XMP", Some("a-new.cr3")),
    ] {
        assert!(PairNames::new([a.clone(), b]).is_err());
    }
}

#[test]
fn portable_pair_roles_are_explicit_and_not_swappable() {
    let raw = rename("selected", "a.cr3", "a-new.cr3", None);
    let xmp = rename("selected", "b.xmp", "b-new.xmp", None);
    assert_eq!(PairNames::new([xmp, raw]), Err(PairPlanError::WrongKind));
}

#[test]
fn portable_authority_binds_plan_originals_parent_and_live_generation() {
    use crate::storage::{
        custody::TrustedCurrentCaller,
        pair_rename_authority::{PairAuthority, PairBindings},
        runtime::Binding,
    };
    let names = PairNames::new([
        rename("selected", "a.cr3", "b.cr3", None),
        rename("selected", "a.xmp", "b.xmp", None),
    ])
    .unwrap();
    let binding = |id| Binding {
        identity: vec![id],
        facts: vec![id + 10],
    };
    let capture = |operation: &str, original: u8, parent: u8, root: &str| {
        PairBindings::capture(
            operation,
            &names,
            Path::new(root),
            [binding(original), binding(2)],
            binding(parent),
        )
        .unwrap()
    };
    let expected = capture("explicit", 1, 3, "selected/journal");
    let mut caller = TrustedCurrentCaller::new();
    let authority = PairAuthority::authorize(&mut caller, expected.clone()).unwrap();
    for changed in [
        capture("changed", 1, 3, "selected/journal"),
        capture("explicit", 4, 3, "selected/journal"),
        capture("explicit", 1, 4, "selected/journal"),
        capture("explicit", 1, 3, "selected/other"),
    ] {
        assert!(authority.check(&changed).is_err());
    }
    authority.check(&expected).unwrap();
    caller.revoke();
    assert!(authority.check(&expected).is_err());
    let current = PairAuthority::authorize(&mut caller, expected.clone()).unwrap();
    drop(caller);
    assert!(current.check(&expected).is_err());
}

#[test]
fn portable_pair_exchange_and_restart_share_generation_and_construction_bound() {
    use crate::storage::{
        custody::{
            CurrentBindings, CurrentCallerHistory, CustodyRefusal, RestartAction,
            TrustedCurrentCaller,
        },
        exchange_authority::{ExchangeAuthority, ExchangeBindings},
        pair_rename_authority::{PairAuthority, PairBindings},
        path_cycle::Plan,
        runtime::{Artifact, Binding},
    };
    let binding = |n| Binding {
        identity: vec![n],
        facts: vec![n, 8],
    };
    let names = PairNames::new([
        rename("selected", "a.cr3", "b.cr3", None),
        rename("selected", "a.xmp", "b.xmp", None),
    ])
    .unwrap();
    let pair = PairBindings::capture(
        "pair",
        &names,
        Path::new("selected/journal"),
        [binding(1), binding(2)],
        binding(9),
    )
    .unwrap();
    let exchange = ExchangeBindings::capture(
        "exchange",
        &Plan::new(
            Path::new("selected/a.bin").into(),
            Path::new("selected/b.bin").into(),
            Path::new("selected/temp.bin").into(),
        )
        .unwrap(),
        Path::new("selected/exchange"),
        [binding(1), binding(2)],
    )
    .unwrap();
    let restart = CurrentBindings::capture(
        "authored-operation",
        "authored-profile",
        "authored-implementation",
        "output.bin",
        &binding(9),
        &(1..=5).map(binding).collect::<Vec<_>>(),
        &[(Artifact::Prepared, vec![5]), (Artifact::Intent, vec![6])],
        false,
    )
    .unwrap();
    let mut caller = TrustedCurrentCaller::new();
    let first = PairAuthority::authorize(&mut caller, pair.clone()).unwrap();
    let second = PairAuthority::authorize(&mut caller, pair.clone()).unwrap();
    assert_eq!(first.check(&pair), Err(CustodyRefusal::StaleAuthority));
    second.check(&pair).unwrap();
    let exchange_authority = ExchangeAuthority::authorize(&mut caller, exchange.clone()).unwrap();
    assert_eq!(second.check(&pair), Err(CustodyRefusal::StaleAuthority));
    caller
        .attest_current(restart.clone(), CurrentCallerHistory::StoppedBeforeRelease)
        .unwrap();
    assert_eq!(
        exchange_authority.check(&exchange),
        Err(CustodyRefusal::StaleAuthority)
    );
    let restart_authority = caller
        .authorize(RestartAction::PruneUnpublished, &restart)
        .unwrap();
    assert!(matches!(
        PairAuthority::authorize(&mut caller, pair),
        Err(CustodyRefusal::ConstructionBound)
    ));
    assert_eq!(
        restart_authority.validate(RestartAction::PruneUnpublished, &restart),
        Err(CustodyRefusal::StaleAuthority)
    );
}

#[cfg(windows)]
mod native {
    use super::super::*;
    use crate::storage::custody::TrustedCurrentCaller;
    use crate::storage::group::MemberStatus;
    use crate::storage::pair_rename_authority::PairAuthority;
    use crate::storage::path_rename::RenamePlan;
    use crate::storage::path_rename::RenameState;
    use crate::storage::{Cancellation, LogicalBudget};
    use imageinfo_windows_storage::{FileSnapshot, GuardedSource, PrivateRoot};
    use serde_json::{Value, json};
    use std::fs::{self, OpenOptions};
    use std::io::Write;
    use std::path::{Path, PathBuf};
    use std::time::{SystemTime, UNIX_EPOCH};

    const NAMES: [&str; 6] = [
        "source.cr3",
        "source.xmp",
        "RENAMED.cr3",
        "RENAMED.xmp",
        "raw.tmp",
        "xmp.tmp",
    ];
    fn observe(path: &Path) -> Value {
        use sha2::{Digest, Sha256};
        let guard =
            GuardedSource::open(path, imageinfo_windows_storage::MAX_ARTIFACT_BYTES).unwrap();
        let s = guard.snapshot();
        let bytes = fs::read(path).unwrap();
        json!({"identity":[s.volume_serial_number,s.file_index], "sha256":format!("{:x}",Sha256::digest(&bytes)),"readLength":bytes.len(),
            "properties":{"size":s.size,"links":s.links,"attributes":s.attributes,
                "created":s.creation_time,"written":s.last_write_time,"security":s.owner_dacl}})
    }
    fn snap(path: &Path) -> FileSnapshot {
        GuardedSource::open(path, imageinfo_windows_storage::MAX_ARTIFACT_BYTES)
            .unwrap()
            .snapshot()
            .clone()
    }
    struct Fixture {
        root: PathBuf,
        initial: [Value; 2],
        snapshots: [FileSnapshot; 2],
        parent: FileSnapshot,
    }
    /// Parent selects two separately authorized working copies before execution.
    /// These paths are read through guards only; every move acts on fresh fixture
    /// copies. This test-only option grants no media or format authority.
    fn fixture_inputs() -> ([Vec<u8>; 2], Value) {
        let raw = std::env::var_os("IMAGEINFO_PAIR_212_RAW_INPUT");
        let xmp = std::env::var_os("IMAGEINFO_PAIR_212_XMP_INPUT");
        match (raw, xmp) {
            (None, None) => (
                [
                    b"authored RAW-role original; no camera admission\n".to_vec(),
                    b"authored XMP-role original; no format admission\n".to_vec(),
                ],
                json!({"kind":"authored markers only"}),
            ),
            (Some(raw), Some(xmp)) => {
                let paths = [PathBuf::from(raw), PathBuf::from(xmp)];
                assert!(
                    paths.iter().all(|p| p.is_absolute()),
                    "input copies require exact absolute paths"
                );
                assert_eq!(
                    paths[0].parent(),
                    paths[1].parent(),
                    "input copies require one explicitly scoped directory"
                );
                assert_ne!(paths[0], paths[1], "input copies must be distinct");
                for (path, extension) in paths.iter().zip(["cr3", "xmp"]) {
                    assert!(
                        path.extension()
                            .and_then(|s| s.to_str())
                            .is_some_and(|e| e.eq_ignore_ascii_case(extension)),
                        "input role requires explicit extension"
                    );
                }
                let mut guards = paths.each_ref().map(|path| {
                    GuardedSource::open(path, imageinfo_windows_storage::MAX_ARTIFACT_BYTES)
                        .unwrap()
                });
                assert_ne!(
                    (
                        guards[0].snapshot().volume_serial_number,
                        guards[0].snapshot().file_index
                    ),
                    (
                        guards[1].snapshot().volume_serial_number,
                        guards[1].snapshot().file_index
                    ),
                    "input copies must be distinct actual objects"
                );
                let bytes = guards
                    .each_mut()
                    .map(|guard| guard.read_exact_bytes().unwrap());
                for guard in &mut guards {
                    guard.check().unwrap();
                }
                use sha2::{Digest, Sha256};
                let inputs = std::array::from_fn::<_, 2, _>(
                    |i| json!({"path":paths[i],"readLength":bytes[i].len(),"sha256":format!("{:x}",Sha256::digest(&bytes[i]))}),
                );
                (
                    bytes,
                    json!({"kind":"parent-selected working-copy bytes; separate grant/phase review required","inputs":inputs}),
                )
            }
            _ => panic!("both RAW_INPUT and XMP_INPUT must be supplied together"),
        }
    }
    impl Fixture {
        fn new(cell: u8) -> Self {
            let (inputs, input_record) = fixture_inputs();
            let base = std::env::var_os("IMAGEINFO_PAIR_212_EVIDENCE_ROOT")
                .map(PathBuf::from)
                .unwrap_or_else(|| {
                    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                        .join(".local")
                        .join("pair-212")
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
                    .create_artifact(
                        NAMES[0],
                        &inputs[0],
                        imageinfo_windows_storage::MAX_ARTIFACT_BYTES,
                    )
                    .unwrap(),
            );
            drop(
                private
                    .create_artifact(
                        NAMES[1],
                        &inputs[1],
                        imageinfo_windows_storage::MAX_ARTIFACT_BYTES,
                    )
                    .unwrap(),
            );
            let parent = private.snapshot().clone();
            drop(private);
            let initial = [observe(&root.join(NAMES[0])), observe(&root.join(NAMES[1]))];
            let snapshots = [snap(&root.join(NAMES[0])), snap(&root.join(NAMES[1]))];
            assert_ne!(initial[0]["identity"], initial[1]["identity"]);
            fs::write(root.join("initial.private.json"),serde_json::to_vec_pretty(&json!({"cell":cell,"originals":initial,"fixture":input_record,"sourceManifests":source_manifests()})).unwrap()).unwrap();
            Self {
                root,
                initial,
                snapshots,
                parent,
            }
        }
        fn names(&self, case_only: bool) -> PairNames {
            PairNames::new(std::array::from_fn(|i| {
                RenamePlan::new(
                    &self.root.join(NAMES[i]),
                    &self.root.join(if case_only {
                        ["SOURCE.CR3", "SOURCE.XMP"][i]
                    } else {
                        NAMES[i + 2]
                    }),
                    case_only.then(|| self.root.join(NAMES[i + 4])).as_deref(),
                )
                .unwrap()
            }))
            .unwrap()
        }
        fn open(&self, caller: &mut TrustedCurrentCaller, case_only: bool) -> Pair {
            let plan = PairPlan::new(
                "authored-explicit-pair",
                self.names(case_only),
                self.root.join("journal"),
                [&self.snapshots[0], &self.snapshots[1]],
                &self.parent,
            )
            .unwrap();
            let authority = PairAuthority::authorize(caller, plan.bindings().clone()).unwrap();
            Pair::open(plan, authority).unwrap()
        }
        fn foreign(&self, name: &str) -> Value {
            let path = self.root.join(name);
            let mut file = OpenOptions::new()
                .write(true)
                .create_new(true)
                .open(&path)
                .unwrap();
            file.write_all(b"independent foreign pair winner\n")
                .unwrap();
            drop(file);
            let facts = observe(&path);
            fs::write(
                self.root.join("foreign-before.private.json"),
                serde_json::to_vec_pretty(&json!({"name":name,"facts":facts})).unwrap(),
            )
            .unwrap();
            facts
        }
        /// Exact enumeration avoids case-insensitive Path::exists aliases.
        /// Each object is freshly opened and independently read after pair drop.
        fn audit(
            &self,
            cell: u8,
            report: Value,
            expected: &[(&str, usize)],
            foreign: Option<(&str, Value)>,
            injected: bool,
        ) {
            let mut all_names: Vec<String> = fs::read_dir(&self.root)
                .unwrap()
                .map(|e| e.unwrap().file_name().into_string().unwrap())
                .collect();
            all_names.sort();
            let mut actual_names: Vec<String> = all_names
                .iter()
                .filter(|name| !name.ends_with(".private.json") && name.as_str() != "journal")
                .cloned()
                .collect();
            actual_names.sort();
            let mut wanted: Vec<String> = expected
                .iter()
                .map(|(name, _)| (*name).to_owned())
                .collect();
            if let Some((name, _)) = &foreign {
                wanted.push((*name).to_owned());
            }
            wanted.sort();
            assert_eq!(actual_names, wanted, "exact complete fixture namespace");
            let entries: Vec<_> = expected
                .iter()
                .map(|(name, index)| {
                    let facts = observe(&self.root.join(name));
                    assert_eq!(
                        facts, self.initial[*index],
                        "retained original identity/bytes/properties: {name}"
                    );
                    json!({"name":name,"original":index,"facts":facts})
                })
                .collect();
            if let Some((name, facts)) = &foreign {
                assert_eq!(
                    &observe(&self.root.join(name)),
                    facts,
                    "foreign winner identity/bytes/properties"
                );
            }
            let journal = if self.root.join("journal").try_exists().unwrap() {
                let mut paths: Vec<_> = fs::read_dir(self.root.join("journal"))
                    .unwrap()
                    .map(|e| e.unwrap().path())
                    .collect();
                paths.sort();
                paths.iter().map(|p|json!({"name":p.file_name().unwrap(),"facts":observe(p),"bytes":fs::read(p).unwrap()})).collect::<Vec<_>>()
            } else {
                Vec::new()
            };
            fs::write(self.root.join("evidence.private.json"),serde_json::to_vec_pretty(&json!({
                "schema":"imageinfo.pair-rename-evidence.v1","cell":cell,"initial":self.initial,
                "allDirectoryNames":all_names,"exactNames":actual_names,"entries":entries,"foreign":foreign,
                "report":report,"journal":journal,"injectedLostResponse":injected,"committed":false,
                "restartAuthority":false,"profileAdmission":false})).unwrap()).unwrap();
        }
    }
    fn source_manifests() -> Vec<Value> {
        use sha2::{Digest, Sha256};
        [
            "src/storage/pair_rename.rs",
            "src/storage/pair_rename/tests.rs",
            "src/storage/pair_rename_authority.rs",
            "src/storage/group.rs",
            "src/storage/path_rename.rs",
            "src/storage/custody.rs",
            "src/storage/windows.rs",
            "src/storage/mod.rs",
            "Cargo.toml",
            "Cargo.lock",
            "crates/imageinfo-windows-storage/src/existing_move.rs",
            "crates/imageinfo-windows-storage/src/existing_properties.rs",
            "crates/imageinfo-windows-storage/src/native.rs",
        ]
        .iter()
        .map(|name| {
            let bytes = fs::read(Path::new(env!("CARGO_MANIFEST_DIR")).join(name)).unwrap();
            json!({"path":name,"bytes":bytes.len(),"sha256":format!("{:x}",Sha256::digest(bytes))})
        })
        .collect()
    }

    fn execute(pair: &mut Pair) -> PairReport {
        pair.execute(
            &Cancellation::default(),
            &mut LogicalBudget::new(16 * 1024 * 1024),
        )
        .unwrap()
    }
    fn report_value(report: &PairReport) -> Value {
        json!({"statuses":report.statuses.map(|s|format!("{s:?}")),"refusals":report.refusals.map(|r|r.map(|r|format!("{r:?}"))),
            "manifestBinding":report.manifest_binding.as_ref().map(|b|json!({"identity":b.identity,"facts":b.facts})),
            "retainedRoot":report.retained_root.as_ref().map(|b|json!({"identity":b.identity,"facts":b.facts})),
            "observations":report.observations.each_ref().map(|o|o.as_ref().map(|o|json!({
                "state":format!("{:?}",o.state),"completedSteps":o.completed_steps,
                "reason":o.reason.map(|r|format!("{r:?}")),
                "names":o.names.iter().map(|(p,b)|json!({"path":p,"binding":b.map(|v|format!("{v:?}"))})).collect::<Vec<_>>()
            }))),"terminal":true,"qualified":false,"restartAuthority":false})
    }
    fn terminal(pair: &mut Pair, report: &PairReport) {
        let again = pair.execute(
            &Cancellation::default(),
            &mut LogicalBudget::new(16 * 1024 * 1024),
        );
        assert!(
            again.is_err(),
            "a consumed pair has no replay or resume entry point: {report:?}"
        );
    }
    #[test]
    fn native_01_ordinary_pair_success() {
        let f = Fixture::new(1);
        let mut caller = TrustedCurrentCaller::new();
        let mut pair = f.open(&mut caller, false);
        let report = execute(&mut pair);
        assert_eq!(report.statuses, [MemberStatus::ObservedRenameComplete; 2]);
        assert!(
            report
                .observations
                .iter()
                .all(|o| o.as_ref().unwrap().state == RenameState::Finished)
        );
        terminal(&mut pair, &report);
        drop(pair);
        f.audit(
            1,
            report_value(&report),
            &[(NAMES[2], 0), (NAMES[3], 1)],
            None,
            false,
        );
    }
    #[test]
    fn native_02_case_only_pair_success() {
        let f = Fixture::new(2);
        let mut caller = TrustedCurrentCaller::new();
        let mut pair = f.open(&mut caller, true);
        let report = execute(&mut pair);
        assert_eq!(report.statuses, [MemberStatus::ObservedRenameComplete; 2]);
        assert!(
            report
                .observations
                .iter()
                .all(|o| o.as_ref().unwrap().completed_steps == 2)
        );
        terminal(&mut pair, &report);
        drop(pair);
        f.audit(
            2,
            report_value(&report),
            &[("SOURCE.CR3", 0), ("SOURCE.XMP", 1)],
            None,
            false,
        );
    }
    #[test]
    fn native_03_missing_or_ambiguous_explicit_pair() {
        let f = Fixture::new(3);
        let raw = RenamePlan::new(&f.root.join(NAMES[0]), &f.root.join(NAMES[2]), None).unwrap();
        assert!(PairNames::new([raw.clone(), raw]).is_err());
        let cross_alias = RenamePlan::new(
            &f.root.join(NAMES[0]),
            &f.root.join("SOURCE.CR3"),
            Some(&f.root.join(NAMES[1])),
        )
        .unwrap();
        assert_eq!(
            PairNames::new([cross_alias, f.names(false).plans()[1].clone()]),
            Err(PairPlanError::Alias)
        );
        let missing =
            RenamePlan::new(&f.root.join("missing.xmp"), &f.root.join(NAMES[3]), None).unwrap();
        let names = PairNames::new([f.names(false).plans()[0].clone(), missing]).unwrap();
        let plan = PairPlan::new(
            "missing-explicit-pair",
            names,
            f.root.join("journal"),
            [&f.snapshots[0], &f.snapshots[1]],
            &f.parent,
        )
        .unwrap();
        let mut caller = TrustedCurrentCaller::new();
        let authority = PairAuthority::authorize(&mut caller, plan.bindings().clone()).unwrap();
        let mut pair = Pair::open(plan, authority).unwrap();
        let report = execute(&mut pair);
        assert_eq!(
            report.statuses,
            [MemberStatus::Refused, MemberStatus::Unattempted]
        );
        terminal(&mut pair, &report);
        drop(pair);
        f.audit(
            3,
            report_value(&report),
            &[(NAMES[0], 0), (NAMES[1], 1)],
            None,
            false,
        );
    }
    #[test]
    fn native_04_late_foreign_temp_collision() {
        let f = Fixture::new(4);
        let mut caller = TrustedCurrentCaller::new();
        let mut pair = f.open(&mut caller, true);
        let mut foreign = None;
        let report = pair
            .execute_with(
                &Cancellation::default(),
                &mut LogicalBudget::new(16 * 1024 * 1024),
                |member, stage| {
                    if member == 0 && stage == HookStage::AfterStep && foreign.is_none() {
                        foreign = Some(f.foreign(NAMES[5]));
                    }
                    HookAction::Continue
                },
            )
            .unwrap();
        assert_eq!(report.statuses[0], MemberStatus::ObservedRenameComplete);
        assert_ne!(report.statuses[1], MemberStatus::ObservedRenameComplete);
        terminal(&mut pair, &report);
        drop(pair);
        f.audit(
            4,
            report_value(&report),
            &[("SOURCE.CR3", 0), (NAMES[1], 1)],
            Some((NAMES[5], foreign.unwrap())),
            false,
        );
    }
    #[test]
    fn native_05_cancel_after_first_confirmed_member() {
        let f = Fixture::new(5);
        let mut caller = TrustedCurrentCaller::new();
        let mut pair = f.open(&mut caller, false);
        let cancel = Cancellation::default();
        let report = pair
            .execute_with(
                &cancel,
                &mut LogicalBudget::new(16 * 1024 * 1024),
                |member, stage| {
                    if member == 0 && stage == HookStage::AfterStep {
                        cancel.request();
                    }
                    HookAction::Continue
                },
            )
            .unwrap();
        assert_eq!(report.statuses[0], MemberStatus::ObservedRenameComplete);
        assert_ne!(report.statuses[1], MemberStatus::ObservedRenameComplete);
        assert!(
            report.observations[1]
                .as_ref()
                .is_none_or(|o| o.completed_steps == 0)
        );
        terminal(&mut pair, &report);
        drop(pair);
        f.audit(
            5,
            report_value(&report),
            &[(NAMES[2], 0), (NAMES[1], 1)],
            None,
            false,
        );
    }
    #[test]
    fn native_06_injected_second_response_loss() {
        let f = Fixture::new(6);
        let mut caller = TrustedCurrentCaller::new();
        let mut pair = f.open(&mut caller, false);
        let report = pair
            .execute_with(
                &Cancellation::default(),
                &mut LogicalBudget::new(16 * 1024 * 1024),
                |member, stage| {
                    if member == 1 && stage == HookStage::BeforeStep {
                        HookAction::LostResponse
                    } else {
                        HookAction::Continue
                    }
                },
            )
            .unwrap();
        assert_eq!(
            report.statuses,
            [
                MemberStatus::ObservedRenameComplete,
                MemberStatus::RecoveryRequired
            ]
        );
        assert_eq!(
            report.observations[1].as_ref().unwrap().state,
            RenameState::RecoveryRequired
        );
        assert_eq!(
            report.observations[1].as_ref().unwrap().completed_steps,
            0,
            "injected loss does not acknowledge the second member move"
        );
        terminal(&mut pair, &report);
        drop(pair);
        f.audit(
            6,
            report_value(&report),
            &[(NAMES[2], 0), (NAMES[3], 1)],
            None,
            true,
        );
    }

    #[test]
    fn native_07_revoke_after_final_confirmed_move() {
        let f = Fixture::new(7);
        let mut caller = TrustedCurrentCaller::new();
        let mut pair = f.open(&mut caller, false);
        let report = pair
            .execute_with(
                &Cancellation::default(),
                &mut LogicalBudget::new(16 * 1024 * 1024),
                |member, stage| {
                    if member == 1 && stage == HookStage::AfterStep {
                        caller.revoke();
                    }
                    HookAction::Continue
                },
            )
            .unwrap();
        assert_eq!(
            report.statuses,
            [
                MemberStatus::ObservedRenameComplete,
                MemberStatus::RecoveryRequired
            ]
        );
        assert_eq!(
            report.refusals[1],
            Some(crate::storage::group::Refusal::Unit(
                crate::storage::Failure::CallerHistory
            )),
            "final authority boundary preserves the concrete revocation cause"
        );
        assert_eq!(report.observations[1].as_ref().unwrap().completed_steps, 1);
        terminal(&mut pair, &report);
        drop(pair);
        f.audit(
            7,
            report_value(&report),
            &[(NAMES[2], 0), (NAMES[3], 1)],
            None,
            false,
        );
    }
}
