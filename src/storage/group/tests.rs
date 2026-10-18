//! Authored protocol controls over the actual group runtime, not native/RAW or
//! persistence evidence. Counters and immutable-input witnesses are independent.
use super::*;
use crate::storage::Phase;
use crate::storage::custody::{
    CurrentBindings, CurrentCallerHistory, RestartAction, TrustedCurrentCaller,
};
use crate::storage::runtime::Artifact;
use std::cell::RefCell;
use std::rc::Rc;
use std::sync::{
    Arc,
    atomic::{AtomicBool, Ordering},
};

fn binding(id: u8) -> Binding {
    Binding {
        identity: vec![id],
        facts: vec![id, 99],
    }
}

struct Fixture {
    sources: [Binding; 2],
    parents: [Binding; 2],
    targets: [Binding; 2],
}
impl Fixture {
    fn new() -> Self {
        Self {
            sources: [binding(21), binding(11)],
            parents: [binding(31), binding(41)],
            targets: [binding(51), binding(61)],
        }
    }
    fn intent(&self) -> Intent<'_> {
        Intent {
            identity: b"group",
            original: b"frozen-original-date",
            units: [self.unit(0), self.unit(1)],
        }
    }
    fn unit(&self, index: usize) -> UnitIntent<'_> {
        UnitIntent {
            identity: if index == 0 { b"a" } else { b"b" },
            operation: "fixed-op",
            revision: "r1",
            profile: "authored-qualified-control",
            implementation: "fake-v1",
            source: &self.sources[index],
            parent: &self.parents[index],
            target: Some(&self.targets[index]),
            output: if index == 0 { "first" } else { "second" },
            candidate_len: 3,
        }
    }
}

#[derive(Default)]
struct Observed {
    log: Vec<String>,
    effects: [usize; 2],
    calls: [usize; 2],
    originals: Vec<Vec<u8>>,
    live_source: Vec<u8>,
}
struct Permit(Arc<AtomicBool>);
impl Permit {
    fn fresh() -> Self {
        Self(Arc::new(AtomicBool::new(true)))
    }
}
#[derive(Clone, Copy)]
enum Behavior {
    Commit,
    Uncertain,
    Refuse,
}
struct Staged {
    artifacts: Vec<Binding>,
    _budget: LogicalBudget,
}
struct Fake<'a> {
    index: usize,
    seen: Rc<RefCell<Observed>>,
    behavior: Behavior,
    invalid: bool,
    stage_failure: bool,
    manifest_failure: bool,
    cancel_stage: bool,
    cancel_execute: bool,
    changed_receipt: bool,
    missing_receipt: bool,
    unavailable_finalizer: bool,
    bad_finalization: bool,
    new_failed_finalization_material: bool,
    extra_uncertain_artifact: bool,
    cancel_on_manifest_check: Option<&'a Cancellation>,
    manifest_checks: usize,
    cancel_manifest_check_at: usize,
    cleanup_failed: bool,
    rename: bool,
    supports_rename: bool,
    invalid_rename: bool,
    omit_rename_artifact: bool,
    revoke_after_execute: Option<Arc<AtomicBool>>,
    current: CurrentBindings,
}
fn current(index: usize) -> CurrentBindings {
    let records = [
        (Artifact::Prepared, vec![1]),
        (Artifact::Intent, vec![2]),
        (Artifact::Observation, vec![3]),
        (Artifact::Receipt, vec![4]),
    ];
    let bindings = (0..7)
        .map(|n| binding(80 + (index * 10 + n) as u8))
        .collect::<Vec<_>>();
    CurrentBindings::capture(
        "fixed-op",
        "authored-qualified-control",
        "fake-v1",
        if index == 0 { "first" } else { "second" },
        &binding(190 + index as u8),
        &bindings,
        &records,
        true,
    )
    .unwrap()
}
impl<'a> Fake<'a> {
    fn new(index: usize, seen: Rc<RefCell<Observed>>) -> Self {
        Self {
            index,
            seen,
            behavior: Behavior::Commit,
            invalid: false,
            stage_failure: false,
            manifest_failure: false,
            cancel_stage: false,
            cancel_execute: false,
            changed_receipt: false,
            missing_receipt: false,
            unavailable_finalizer: true,
            bad_finalization: false,
            new_failed_finalization_material: false,
            extra_uncertain_artifact: false,
            cancel_on_manifest_check: None,
            manifest_checks: 0,
            cancel_manifest_check_at: 1,
            cleanup_failed: false,
            rename: false,
            supports_rename: true,
            invalid_rename: false,
            omit_rename_artifact: false,
            revoke_after_execute: None,
            current: current(index),
        }
    }
    fn note(&self, event: &str, original: Option<&[u8]>) {
        let mut seen = self.seen.borrow_mut();
        seen.log.push(format!("{event}{}", self.index));
        if let Some(original) = original {
            seen.originals.push(original.to_vec());
        }
    }
    fn receipt(&self) -> QualifiedReceipt {
        QualifiedReceipt {
            installed: binding(110 + self.index as u8),
            receipt: binding(120 + self.index as u8),
        }
    }
    fn completed(&self) -> Execution {
        Execution {
            result: UnitResult {
                status: Status::Committed,
                phase: Phase::TerminalExport,
                failure: None,
                publication_possible: true,
                release_possible: true,
                retained_material: true,
                pending_cleanup: self.cleanup_failed,
                charged_bytes: LogicalBudget::unit_charge(3).unwrap(),
                protocol_complete: true,
            },
            receipt: Some(self.receipt()),
            artifacts: vec![
                binding(110 + self.index as u8),
                binding(120 + self.index as u8),
            ],
        }
    }
}
impl UnitAdapter for Fake<'_> {
    type ExecuteAuthority = Permit;
    type Staged = Staged;
    fn supports_observed_rename(&self) -> bool {
        self.supports_rename
    }
    fn preflight(
        &mut self,
        _unit: UnitIntent<'_>,
        original: &[u8],
        authority: &Permit,
    ) -> Result<(), Refusal> {
        self.note("pre", Some(original));
        if self.invalid {
            return Err(Failure::Conflict.into());
        }
        if !authority.0.load(Ordering::Acquire) {
            return Err(Failure::CallerHistory.into());
        }
        Ok(())
    }
    fn acquire_guard(&mut self, value: &Binding) -> Result<(), Refusal> {
        self.seen
            .borrow_mut()
            .log
            .push(format!("guard:{}", value.identity[0]));
        Ok(())
    }
    fn stage(
        &mut self,
        unit: UnitIntent<'_>,
        original: &[u8],
        mut budget: LogicalBudget,
        cancel: &Cancellation,
    ) -> Result<Staged, PreparationFailure> {
        self.note("stage", Some(original));
        budget.reserve_unit(unit.candidate_len).unwrap();
        if self.stage_failure {
            return Err(PreparationFailure {
                refusal: Failure::BackendIo.into(),
                artifacts: vec![binding(130 + self.index as u8)],
            });
        }
        if self.cancel_stage {
            cancel.request();
        }
        Ok(Staged {
            artifacts: vec![binding(130 + self.index as u8)],
            _budget: budget,
        })
    }
    fn staged_artifacts(staged: &Staged) -> &[Binding] {
        &staged.artifacts
    }
    fn retain_manifest(&mut self, bytes: &[u8]) -> Result<Binding, ManifestFailure> {
        self.note("manifest", None);
        assert!(!bytes.is_empty() && bytes.len() <= 65536);
        if self.manifest_failure {
            return Err(ManifestFailure {
                refusal: Failure::BackendIo.into(),
                retained: Some(binding(200)),
            });
        }
        Ok(binding(200))
    }
    fn check_manifest(&mut self, _binding: &Binding, _bytes: &[u8]) -> Result<(), Refusal> {
        self.note("manifest-check", None);
        self.manifest_checks += 1;
        if let Some(cancel) = self.cancel_on_manifest_check
            && self.manifest_checks == self.cancel_manifest_check_at
        {
            cancel.request();
        }
        Ok(())
    }
    fn execute(
        &mut self,
        _staged: Staged,
        _unit: UnitIntent<'_>,
        original: &[u8],
        authority: Permit,
        cancel: &Cancellation,
    ) -> Execution {
        self.note("execute", Some(original));
        self.seen.borrow_mut().calls[self.index] += 1;
        let mut value = self.completed();
        if !authority.0.load(Ordering::Acquire) || matches!(self.behavior, Behavior::Refuse) {
            value.result.status = Status::Refused;
            value.result.publication_possible = false;
            value.result.failure = Some(Failure::CallerHistory);
            value.result.protocol_complete = false;
            value.receipt = None;
        } else {
            self.seen.borrow_mut().effects[self.index] += 1;
            if self.index == 0 {
                self.seen.borrow_mut().live_source = b"later-edited-source-date".to_vec();
            }
            if matches!(self.behavior, Behavior::Uncertain) {
                if self.extra_uncertain_artifact {
                    value.artifacts.push(binding(221));
                }
                value.result.status = Status::RecoveryRequired;
                value.result.protocol_complete = false;
                value.result.failure = Some(Failure::BackendIo);
                value.receipt = None;
            }
        }
        if self.cancel_execute {
            cancel.request();
        }
        if let Some(authority) = &self.revoke_after_execute {
            authority.store(false, Ordering::Release);
        }
        value
    }
    fn execute_observed_rename(
        &mut self,
        staged: Staged,
        unit: UnitIntent<'_>,
        original: &[u8],
        authority: Permit,
        cancel: &Cancellation,
    ) -> RenameExecution {
        let value = self.execute(staged, unit, original, authority, cancel);
        if !self.rename || value.result.status != Status::Committed {
            return RenameExecution::Failed(value);
        }
        let mut installed = unit.source.clone();
        installed.facts = unit.output.as_bytes().to_vec();
        if self.invalid_rename {
            installed.identity.push(0);
        }
        let artifacts = if self.omit_rename_artifact {
            vec![]
        } else {
            vec![installed.clone()]
        };
        RenameExecution::Complete(ObservedRename {
            installed,
            artifacts,
            charged_bytes: value.result.charged_bytes,
        })
    }
    fn verify_completed(
        &mut self,
        _unit: UnitIntent<'_>,
        original: &[u8],
        old: &QualifiedReceipt,
        authority: ActionAuthority,
    ) -> Result<QualifiedReceipt, Refusal> {
        self.note("verify", Some(original));
        authority
            .validate(RestartAction::RecognizeCompletion, &self.current)
            .map_err(|_| Refusal::Unit(Failure::CallerHistory))?;
        if self.missing_receipt {
            return Err(Refusal::ReceiptConflict);
        }
        let mut receipt = self.receipt();
        if self.changed_receipt {
            receipt.installed.facts.push(1);
        }
        if &receipt != old {
            return Err(Refusal::ReceiptConflict);
        }
        Ok(receipt)
    }
    fn inspect_finalize(
        &mut self,
        _unit: UnitIntent<'_>,
        original: &[u8],
        _prior: &Execution,
        authority: ActionAuthority,
    ) -> Result<Execution, Refusal> {
        self.note("inspect", Some(original));
        if self.unavailable_finalizer {
            return Err(Refusal::AdapterUnavailable);
        }
        authority
            .validate(RestartAction::FinalizeExisting, &self.current)
            .map_err(|_| Refusal::Unit(Failure::CallerHistory))?;
        let mut value = self.completed();
        if self.new_failed_finalization_material {
            value.artifacts = vec![binding(222)];
            value.result.retained_material = true;
            value.result.pending_cleanup = true;
            value.result.charged_bytes += 73;
            value.result.release_possible = true;
        }
        if self.bad_finalization {
            value.result.status = Status::Refused;
            value.result.publication_possible = false;
            value.receipt = None;
        }
        Ok(value)
    }
}
fn pair<'a>() -> (Fake<'a>, Fake<'a>, Rc<RefCell<Observed>>) {
    let seen = Rc::new(RefCell::new(Observed {
        live_source: b"frozen-original-date".to_vec(),
        ..Observed::default()
    }));
    (Fake::new(0, seen.clone()), Fake::new(1, seen.clone()), seen)
}
fn permits() -> (Option<Permit>, Option<Permit>) {
    (Some(Permit::fresh()), Some(Permit::fresh()))
}
fn authorize(index: usize, action: RestartAction) -> (TrustedCurrentCaller, ActionAuthority) {
    let mut caller = TrustedCurrentCaller::new();
    let fresh = current(index);
    caller
        .attest_current(
            fresh.clone(),
            CurrentCallerHistory::TerminalCompletionAndStopped,
        )
        .unwrap();
    let authority = caller.authorize(action, &fresh).unwrap();
    (caller, authority)
}
fn statuses<S, T>(run: &Run<'_, S, T>) -> [MemberStatus; 2] {
    run.members.each_ref().map(|m| m.status())
}

#[test]
fn actual_fixed_runtime_stages_both_and_orders_guards_before_effects() {
    let f = Fixture::new();
    let (mut a, mut b, seen) = pair();
    let cancel = Cancellation::default();
    let mut budget = LogicalBudget::new(u64::MAX);
    let run = start(f.intent(), &mut a, &mut b, permits(), &mut budget, &cancel).unwrap();
    assert_eq!(statuses(&run), [MemberStatus::Committed; 2]);
    assert_eq!(seen.borrow().effects, [1, 1]);
    assert!(run.manifest_binding().is_some());
    assert_eq!(
        budget.charged(),
        2 * LogicalBudget::unit_charge(3).unwrap() + run.manifest().len() as u64
    );
    let seen = seen.borrow();
    let position = |name: &str| seen.log.iter().position(|s| s == name).unwrap();
    assert!(position("pre1") < position("stage0"));
    assert!(position("stage1") < position("execute0"));
    assert!(position("manifest0") < position("execute0"));
    assert!(position("execute0") < position("execute1"));
    let guards = seen
        .log
        .iter()
        .filter_map(|s| s.strip_prefix("guard:").map(|s| s.parse::<u8>().unwrap()))
        .collect::<Vec<_>>();
    assert!(guards.windows(2).all(|w| w[0] <= w[1]));
    assert!(seen.originals.iter().all(|s| s == b"frozen-original-date"));
}

#[test]
fn invalid_second_prevents_any_stage_or_effect_and_retains_charge() {
    let f = Fixture::new();
    let (mut a, mut b, seen) = pair();
    b.invalid = true;
    let mut budget = LogicalBudget::new(u64::MAX);
    let run = start(
        f.intent(),
        &mut a,
        &mut b,
        permits(),
        &mut budget,
        &Cancellation::default(),
    )
    .unwrap();
    assert_eq!(
        statuses(&run),
        [MemberStatus::Unattempted, MemberStatus::Refused]
    );
    assert_eq!(seen.borrow().effects, [0, 0]);
    assert!(!seen.borrow().log.iter().any(|s| s.starts_with("stage")));
    assert!(budget.charged() > 0);
}

#[test]
fn physical_alias_and_conflicting_names_refuse_before_adapters() {
    for case in 0..3 {
        let f = Fixture::new();
        let mut intent = f.intent();
        match case {
            0 => intent.units[1].target = intent.units[0].target,
            1 => intent.units[1].target = Some(intent.units[0].source),
            _ => {
                intent.units[1].parent = intent.units[0].parent;
                intent.units[1].output = "FIRST";
            }
        }
        let (mut a, mut b, seen) = pair();
        let run = start(
            intent,
            &mut a,
            &mut b,
            permits(),
            &mut LogicalBudget::new(u64::MAX),
            &Cancellation::default(),
        )
        .unwrap();
        assert_eq!(run.members[0].refusal(), Some(Refusal::Alias));
        assert!(seen.borrow().log.is_empty());
    }
}

#[test]
fn intentional_shared_source_keeps_exact_frozen_inputs() {
    let f = Fixture::new();
    let mut intent = f.intent();
    intent.units[1].source = intent.units[0].source;
    let (mut a, mut b, seen) = pair();
    let run = start(
        intent,
        &mut a,
        &mut b,
        permits(),
        &mut LogicalBudget::new(u64::MAX),
        &Cancellation::default(),
    )
    .unwrap();
    assert_eq!(statuses(&run), [MemberStatus::Committed; 2]);
    assert!(seen.borrow().originals.iter().all(|b| b == intent.original));
    assert_eq!(seen.borrow().live_source, b"later-edited-source-date");
}

#[test]
fn second_stage_failure_retains_first_context_and_exact_partial_artifacts() {
    let f = Fixture::new();
    let (mut a, mut b, seen) = pair();
    b.stage_failure = true;
    let mut budget = LogicalBudget::new(u64::MAX);
    let run = start(
        f.intent(),
        &mut a,
        &mut b,
        permits(),
        &mut budget,
        &Cancellation::default(),
    )
    .unwrap();
    assert_eq!(seen.borrow().effects, [0, 0]);
    assert!(run.staged_a.is_some());
    assert_eq!(run.members[1].preparation_artifacts(), &[binding(131)]);
    assert!(budget.charged() > 0);
}

#[test]
fn early_cancel_has_no_adapter_calls_and_can_explicitly_resume() {
    let f = Fixture::new();
    let (mut a, mut b, seen) = pair();
    let cancel = Cancellation::default();
    cancel.request();
    let mut run = start(
        f.intent(),
        &mut a,
        &mut b,
        permits(),
        &mut LogicalBudget::new(u64::MAX),
        &cancel,
    )
    .unwrap();
    assert_eq!(
        statuses(&run),
        [
            MemberStatus::CancelledBeforePublish,
            MemberStatus::Unattempted
        ]
    );
    assert!(seen.borrow().log.is_empty());
    resume(
        &mut run,
        &mut a,
        &mut b,
        (None, None),
        permits(),
        &Cancellation::default(),
    );
    assert_eq!(seen.borrow().effects, [1, 1]);
}

#[test]
fn cancellation_after_staging_retains_contexts_and_resumes_without_reconstruction() {
    let f = Fixture::new();
    let (mut a, mut b, seen) = pair();
    b.cancel_stage = true;
    let mut run = start(
        f.intent(),
        &mut a,
        &mut b,
        permits(),
        &mut LogicalBudget::new(u64::MAX),
        &Cancellation::default(),
    )
    .unwrap();
    assert_eq!(seen.borrow().effects, [0, 0]);
    assert!(run.staged_a.is_some() && run.staged_b.is_some());
    resume(
        &mut run,
        &mut a,
        &mut b,
        (None, None),
        permits(),
        &Cancellation::default(),
    );
    assert_eq!(seen.borrow().effects, [1, 1]);
    assert_eq!(
        seen.borrow()
            .log
            .iter()
            .filter(|s| s.starts_with("stage"))
            .count(),
        2
    );
}

#[test]
fn late_cancel_preserves_committed_cleanup_and_unattempted_second() {
    let f = Fixture::new();
    let (mut a, mut b, seen) = pair();
    a.cancel_execute = true;
    a.cleanup_failed = true;
    let mut run = start(
        f.intent(),
        &mut a,
        &mut b,
        permits(),
        &mut LogicalBudget::new(u64::MAX),
        &Cancellation::default(),
    )
    .unwrap();
    assert_eq!(
        statuses(&run),
        [
            MemberStatus::Committed,
            MemberStatus::CancelledBeforePublish
        ]
    );
    assert!(run.members[0].execution().unwrap().result.pending_cleanup);
    let (_caller, authority) = authorize(0, RestartAction::RecognizeCompletion);
    resume(
        &mut run,
        &mut a,
        &mut b,
        (Some(authority), None),
        (None, Some(Permit::fresh())),
        &Cancellation::default(),
    );
    assert_eq!(seen.borrow().effects, [1, 1]);
    assert_eq!(seen.borrow().calls, [1, 1]);
}

#[test]
fn member_one_uncertainty_stops_second_and_unavailable_finalizer_never_executes() {
    let f = Fixture::new();
    let (mut a, mut b, seen) = pair();
    a.behavior = Behavior::Uncertain;
    let mut run = start(
        f.intent(),
        &mut a,
        &mut b,
        permits(),
        &mut LogicalBudget::new(u64::MAX),
        &Cancellation::default(),
    )
    .unwrap();
    assert_eq!(
        statuses(&run),
        [MemberStatus::RecoveryRequired, MemberStatus::Unattempted]
    );
    let (_caller, authority) = authorize(0, RestartAction::FinalizeExisting);
    resume(
        &mut run,
        &mut a,
        &mut b,
        (Some(authority), None),
        permits(),
        &Cancellation::default(),
    );
    assert_eq!(run.members[0].refusal(), Some(Refusal::AdapterUnavailable));
    assert_eq!(seen.borrow().calls, [1, 0]);
    assert_eq!(seen.borrow().effects, [1, 0]);
}

#[test]
fn qualified_finalization_skips_uncertain_member_and_repeated_resume_never_reapplies() {
    let f = Fixture::new();
    let (mut a, mut b, seen) = pair();
    a.behavior = Behavior::Uncertain;
    a.unavailable_finalizer = false;
    let mut run = start(
        f.intent(),
        &mut a,
        &mut b,
        permits(),
        &mut LogicalBudget::new(u64::MAX),
        &Cancellation::default(),
    )
    .unwrap();
    let (_caller, authority) = authorize(0, RestartAction::FinalizeExisting);
    resume(
        &mut run,
        &mut a,
        &mut b,
        (Some(authority), None),
        (None, Some(Permit::fresh())),
        &Cancellation::default(),
    );
    assert_eq!(statuses(&run), [MemberStatus::Committed; 2]);
    assert_eq!(seen.borrow().calls, [1, 1]);
    for _ in 0..3 {
        let (_one, x) = authorize(0, RestartAction::RecognizeCompletion);
        let (_two, y) = authorize(1, RestartAction::RecognizeCompletion);
        resume(
            &mut run,
            &mut a,
            &mut b,
            (Some(x), Some(y)),
            (None, None),
            &Cancellation::default(),
        );
    }
    assert_eq!(seen.borrow().calls, [1, 1]);
    assert_eq!(seen.borrow().effects, [1, 1]);
    assert!(
        seen.borrow()
            .originals
            .iter()
            .all(|s| s == b"frozen-original-date")
    );
}

#[test]
fn bad_finalization_cannot_erase_possible_effect_or_prior_artifacts() {
    let f = Fixture::new();
    let (mut a, mut b, seen) = pair();
    a.behavior = Behavior::Uncertain;
    a.unavailable_finalizer = false;
    a.bad_finalization = true;
    let mut run = start(
        f.intent(),
        &mut a,
        &mut b,
        permits(),
        &mut LogicalBudget::new(u64::MAX),
        &Cancellation::default(),
    )
    .unwrap();
    let (_caller, authority) = authorize(0, RestartAction::FinalizeExisting);
    resume(
        &mut run,
        &mut a,
        &mut b,
        (Some(authority), None),
        permits(),
        &Cancellation::default(),
    );
    assert_eq!(run.members[0].status(), MemberStatus::RecoveryRequired);
    assert!(
        run.members[0]
            .execution()
            .unwrap()
            .result
            .publication_possible
    );
    assert_eq!(seen.borrow().calls, [1, 0]);
}

#[test]
fn member_two_failure_preserves_member_one_commit_and_cleanup() {
    let f = Fixture::new();
    let (mut a, mut b, seen) = pair();
    b.behavior = Behavior::Uncertain;
    a.cleanup_failed = true;
    let run = start(
        f.intent(),
        &mut a,
        &mut b,
        permits(),
        &mut LogicalBudget::new(u64::MAX),
        &Cancellation::default(),
    )
    .unwrap();
    assert_eq!(
        statuses(&run),
        [MemberStatus::Committed, MemberStatus::RecoveryRequired]
    );
    assert!(run.members[0].execution().unwrap().result.pending_cleanup);
    assert_eq!(seen.borrow().effects, [1, 1]);
}

#[test]
fn changed_or_missing_receipt_blocks_dependent_resume() {
    for missing in [false, true] {
        let f = Fixture::new();
        let (mut a, mut b, seen) = pair();
        a.cancel_execute = true;
        let mut run = start(
            f.intent(),
            &mut a,
            &mut b,
            permits(),
            &mut LogicalBudget::new(u64::MAX),
            &Cancellation::default(),
        )
        .unwrap();
        a.changed_receipt = !missing;
        a.missing_receipt = missing;
        let (_caller, authority) = authorize(0, RestartAction::RecognizeCompletion);
        resume(
            &mut run,
            &mut a,
            &mut b,
            (Some(authority), None),
            permits(),
            &Cancellation::default(),
        );
        assert_eq!(run.members[0].refusal(), Some(Refusal::ReceiptConflict));
        assert_eq!(seen.borrow().calls, [1, 0]);
    }
}

#[test]
fn absent_and_stale_authorities_cannot_skip_or_execute() {
    let f = Fixture::new();
    let (mut a, mut b, seen) = pair();
    a.cancel_execute = true;
    let mut run = start(
        f.intent(),
        &mut a,
        &mut b,
        permits(),
        &mut LogicalBudget::new(u64::MAX),
        &Cancellation::default(),
    )
    .unwrap();
    resume(
        &mut run,
        &mut a,
        &mut b,
        (None, None),
        permits(),
        &Cancellation::default(),
    );
    assert_eq!(run.members[0].refusal(), Some(Refusal::MissingAuthority));
    let (mut caller, authority) = authorize(0, RestartAction::RecognizeCompletion);
    caller.revoke();
    resume(
        &mut run,
        &mut a,
        &mut b,
        (Some(authority), None),
        permits(),
        &Cancellation::default(),
    );
    assert_eq!(
        run.members[0].refusal(),
        Some(Failure::CallerHistory.into())
    );
    assert_eq!(seen.borrow().calls, [1, 0]);
    let (mut a, mut b, seen) = pair();
    let stale = Permit::fresh();
    stale.0.store(false, Ordering::Release);
    let run = start(
        f.intent(),
        &mut a,
        &mut b,
        (Some(stale), Some(Permit::fresh())),
        &mut LogicalBudget::new(u64::MAX),
        &Cancellation::default(),
    )
    .unwrap();
    assert_eq!(run.members[0].status(), MemberStatus::Refused);
    assert_eq!(seen.borrow().calls, [0, 0]);
}

#[test]
fn new_current_facts_conflict_with_old_authority() {
    let f = Fixture::new();
    let (mut a, mut b, seen) = pair();
    a.cancel_execute = true;
    let mut run = start(
        f.intent(),
        &mut a,
        &mut b,
        permits(),
        &mut LogicalBudget::new(u64::MAX),
        &Cancellation::default(),
    )
    .unwrap();
    let (_caller, authority) = authorize(0, RestartAction::RecognizeCompletion);
    a.current = current(1);
    resume(
        &mut run,
        &mut a,
        &mut b,
        (Some(authority), None),
        permits(),
        &Cancellation::default(),
    );
    assert_eq!(seen.borrow().calls, [1, 0]);
    assert_eq!(
        run.members[0].refusal(),
        Some(Failure::CallerHistory.into())
    );
}

#[test]
fn budget_overflow_manifest_bound_and_insufficient_total_precede_all_constructions() {
    let f = Fixture::new();
    for case in 0..3 {
        let (mut a, mut b, seen) = pair();
        let mut intent = f.intent();
        let large = vec![0; 65536];
        let mut budget = LogicalBudget::new(if case == 2 { 1 } else { u64::MAX });
        match case {
            0 => intent.units[1].candidate_len = u64::MAX,
            1 => intent.original = &large,
            _ => {}
        }
        let result = start(
            intent,
            &mut a,
            &mut b,
            permits(),
            &mut budget,
            &Cancellation::default(),
        );
        assert!(result.is_err());
        assert_eq!(budget.charged(), 0);
        assert!(seen.borrow().log.is_empty());
    }
}

#[test]
fn failed_charges_remain_and_retry_cannot_reset_budgets() {
    let f = Fixture::new();
    let (mut a, mut b, seen) = pair();
    b.stage_failure = true;
    let length = manifest_len(f.intent()).unwrap();
    let amount = 2 * LogicalBudget::unit_charge(3).unwrap() + length;
    let mut budget = LogicalBudget::new(amount);
    let mut run = start(
        f.intent(),
        &mut a,
        &mut b,
        permits(),
        &mut budget,
        &Cancellation::default(),
    )
    .unwrap();
    b.stage_failure = false;
    resume(
        &mut run,
        &mut a,
        &mut b,
        (None, None),
        permits(),
        &Cancellation::default(),
    );
    assert_eq!(
        run.members[1].refusal(),
        Some(Failure::BudgetExhausted.into())
    );
    assert_eq!(seen.borrow().effects, [0, 0]);
    assert!(matches!(
        start(
            f.intent(),
            &mut a,
            &mut b,
            permits(),
            &mut budget,
            &Cancellation::default()
        ),
        Err(Refusal::Unit(Failure::BudgetExhausted))
    ));
    assert_eq!(budget.charged(), amount);
}

#[test]
fn member_two_prepublication_refusal_never_reexecutes_first() {
    let f = Fixture::new();
    let (mut a, mut b, seen) = pair();
    b.behavior = Behavior::Refuse;
    let mut run = start(
        f.intent(),
        &mut a,
        &mut b,
        permits(),
        &mut LogicalBudget::new(u64::MAX),
        &Cancellation::default(),
    )
    .unwrap();
    assert_eq!(
        statuses(&run),
        [MemberStatus::Committed, MemberStatus::Refused]
    );
    let (_caller, authority) = authorize(0, RestartAction::RecognizeCompletion);
    resume(
        &mut run,
        &mut a,
        &mut b,
        (Some(authority), None),
        permits(),
        &Cancellation::default(),
    );
    assert_eq!(seen.borrow().calls, [1, 1]);
    assert_eq!(
        run.members[1].refusal(),
        Some(Failure::BudgetExhausted.into())
    );
}

#[test]
fn rejected_alias_cannot_be_resumed_into_execution() {
    let f = Fixture::new();
    let mut intent = f.intent();
    intent.units[1].target = intent.units[0].target;
    let (mut a, mut b, seen) = pair();
    let mut run = start(
        intent,
        &mut a,
        &mut b,
        permits(),
        &mut LogicalBudget::new(u64::MAX),
        &Cancellation::default(),
    )
    .unwrap();
    resume(
        &mut run,
        &mut a,
        &mut b,
        (None, None),
        permits(),
        &Cancellation::default(),
    );
    assert_eq!(run.members[0].refusal(), Some(Refusal::Alias));
    assert!(seen.borrow().log.is_empty());
}

#[test]
fn exact_manifest_ceiling_is_accepted_and_one_more_byte_refuses() {
    let f = Fixture::new();
    let base = manifest_len(f.intent()).unwrap() as usize;
    let original = vec![42; MAX_RECORD_BYTES as usize - base + f.intent().original.len()];
    let mut intent = f.intent();
    intent.original = &original;
    let (mut a, mut b, seen) = pair();
    let run = start(
        intent,
        &mut a,
        &mut b,
        permits(),
        &mut LogicalBudget::new(u64::MAX),
        &Cancellation::default(),
    )
    .unwrap();
    assert_eq!(run.manifest().len(), MAX_RECORD_BYTES as usize);
    assert_eq!(seen.borrow().effects, [1, 1]);
    let too_large = vec![42; original.len() + 1];
    intent.original = &too_large;
    assert_eq!(
        manifest_len(intent),
        Err(Refusal::Unit(Failure::RecordTooLarge))
    );
}

#[test]
fn absent_second_execution_authority_prevents_first_stage_and_effect() {
    let f = Fixture::new();
    let (mut a, mut b, seen) = pair();
    let run = start(
        f.intent(),
        &mut a,
        &mut b,
        (Some(Permit::fresh()), None),
        &mut LogicalBudget::new(u64::MAX),
        &Cancellation::default(),
    )
    .unwrap();
    assert_eq!(run.members[1].refusal(), Some(Refusal::MissingAuthority));
    assert_eq!(seen.borrow().effects, [0, 0]);
    assert!(!seen.borrow().log.iter().any(|s| s.starts_with("stage")));
}

#[test]
fn finalization_preserves_prior_cleanup_and_exact_artifacts() {
    let f = Fixture::new();
    let (mut a, mut b, seen) = pair();
    a.behavior = Behavior::Uncertain;
    a.unavailable_finalizer = false;
    a.cleanup_failed = true;
    let mut run = start(
        f.intent(),
        &mut a,
        &mut b,
        permits(),
        &mut LogicalBudget::new(u64::MAX),
        &Cancellation::default(),
    )
    .unwrap();
    a.cleanup_failed = false;
    let (_caller, authority) = authorize(0, RestartAction::FinalizeExisting);
    resume(
        &mut run,
        &mut a,
        &mut b,
        (Some(authority), None),
        (None, Some(Permit::fresh())),
        &Cancellation::default(),
    );
    assert_eq!(statuses(&run), [MemberStatus::Committed; 2]);
    assert!(run.members[0].execution().unwrap().result.pending_cleanup);
    assert_eq!(seen.borrow().calls, [1, 1]);
}

#[test]
fn failed_manifest_retains_exact_artifact_and_is_never_recreated_on_resume() {
    let f = Fixture::new();
    let (mut a, mut b, seen) = pair();
    a.manifest_failure = true;
    let mut run = start(
        f.intent(),
        &mut a,
        &mut b,
        permits(),
        &mut LogicalBudget::new(u64::MAX),
        &Cancellation::default(),
    )
    .unwrap();
    assert_eq!(run.manifest_binding(), Some(&binding(200)));
    assert_eq!(seen.borrow().effects, [0, 0]);
    a.manifest_failure = false;
    resume(
        &mut run,
        &mut a,
        &mut b,
        (None, None),
        permits(),
        &Cancellation::default(),
    );
    assert_eq!(run.members[0].refusal(), Some(Failure::Ambiguous.into()));
    assert_eq!(
        seen.borrow()
            .log
            .iter()
            .filter(|s| *s == "manifest0")
            .count(),
        1
    );
    assert_eq!(seen.borrow().effects, [0, 0]);
}

#[test]
fn failed_finalizer_preserves_new_observed_material_cleanup_and_cumulative_charge() {
    let f = Fixture::new();
    let (mut a, mut b, seen) = pair();
    a.behavior = Behavior::Uncertain;
    a.unavailable_finalizer = false;
    a.bad_finalization = true;
    a.new_failed_finalization_material = true;
    let mut run = start(
        f.intent(),
        &mut a,
        &mut b,
        permits(),
        &mut LogicalBudget::new(u64::MAX),
        &Cancellation::default(),
    )
    .unwrap();
    let prior_artifacts = run.members[0].execution().unwrap().artifacts.clone();
    let prior_charge = run.members[0].execution().unwrap().result.charged_bytes;
    let (_caller, authority) = authorize(0, RestartAction::FinalizeExisting);
    resume(
        &mut run,
        &mut a,
        &mut b,
        (Some(authority), None),
        permits(),
        &Cancellation::default(),
    );
    let retained = run.members[0].execution().unwrap();
    assert_eq!(run.members[0].status(), MemberStatus::RecoveryRequired);
    assert!(retained.artifacts.contains(&binding(222)));
    assert!(
        prior_artifacts
            .iter()
            .all(|a| retained.artifacts.contains(a))
    );
    assert!(retained.result.pending_cleanup && retained.result.retained_material);
    assert!(retained.result.publication_possible && retained.result.release_possible);
    assert_eq!(retained.result.charged_bytes, prior_charge + 73);
    assert_eq!(seen.borrow().calls, [1, 0]);
    assert_eq!(seen.borrow().effects, [1, 0]);
}

#[test]
fn cancellation_at_prepublication_check_keeps_exact_contexts_for_resume() {
    let f = Fixture::new();
    let cancel = Cancellation::default();
    let (mut a, mut b, seen) = pair();
    a.cancel_on_manifest_check = Some(&cancel);
    let mut run = start(
        f.intent(),
        &mut a,
        &mut b,
        permits(),
        &mut LogicalBudget::new(u64::MAX),
        &cancel,
    )
    .unwrap();
    assert_eq!(seen.borrow().calls, [0, 0]);
    assert!(run.staged_a.is_some() && run.staged_b.is_some());
    let first_artifacts = run.members[0].preparation_artifacts().to_vec();
    let second_artifacts = run.members[1].preparation_artifacts().to_vec();
    a.cancel_on_manifest_check = None;
    resume(
        &mut run,
        &mut a,
        &mut b,
        (None, None),
        permits(),
        &Cancellation::default(),
    );
    assert_eq!(statuses(&run), [MemberStatus::Committed; 2]);
    assert_eq!(seen.borrow().effects, [1, 1]);
    assert_eq!(run.members[0].preparation_artifacts(), first_artifacts);
    assert_eq!(run.members[1].preparation_artifacts(), second_artifacts);
    assert_eq!(
        seen.borrow()
            .log
            .iter()
            .filter(|s| s.starts_with("stage"))
            .count(),
        2
    );
}

#[test]
fn cancellation_after_second_manifest_check_keeps_dependent_context_unexecuted() {
    let f = Fixture::new();
    let cancel = Cancellation::default();
    let (mut a, mut b, seen) = pair();
    a.cancel_on_manifest_check = Some(&cancel);
    a.cancel_manifest_check_at = 2;
    let mut run = start(
        f.intent(),
        &mut a,
        &mut b,
        permits(),
        &mut LogicalBudget::new(u64::MAX),
        &cancel,
    )
    .unwrap();
    assert_eq!(
        statuses(&run),
        [
            MemberStatus::Committed,
            MemberStatus::CancelledBeforePublish
        ]
    );
    assert_eq!(seen.borrow().calls, [1, 0]);
    assert!(run.staged_b.is_some());
    let second_artifacts = run.members[1].preparation_artifacts().to_vec();
    a.cancel_on_manifest_check = None;
    let (_caller, authority) = authorize(0, RestartAction::RecognizeCompletion);
    resume(
        &mut run,
        &mut a,
        &mut b,
        (Some(authority), None),
        (None, Some(Permit::fresh())),
        &Cancellation::default(),
    );
    assert_eq!(statuses(&run), [MemberStatus::Committed; 2]);
    assert_eq!(seen.borrow().effects, [1, 1]);
    assert_eq!(seen.borrow().calls, [1, 1]);
    assert_eq!(run.members[1].preparation_artifacts(), second_artifacts);
    assert_eq!(
        seen.borrow()
            .log
            .iter()
            .filter(|s| s.starts_with("stage"))
            .count(),
        2
    );
}

#[test]
fn claimed_finalization_omitting_prior_artifact_cannot_synthesize_completion() {
    let f = Fixture::new();
    let (mut a, mut b, seen) = pair();
    a.behavior = Behavior::Uncertain;
    a.extra_uncertain_artifact = true;
    a.unavailable_finalizer = false;
    let mut run = start(
        f.intent(),
        &mut a,
        &mut b,
        permits(),
        &mut LogicalBudget::new(u64::MAX),
        &Cancellation::default(),
    )
    .unwrap();
    assert!(
        run.members[0]
            .execution()
            .unwrap()
            .artifacts
            .contains(&binding(221))
    );
    let (_caller, authority) = authorize(0, RestartAction::FinalizeExisting);
    resume(
        &mut run,
        &mut a,
        &mut b,
        (Some(authority), None),
        permits(),
        &Cancellation::default(),
    );
    let observed = run.members[0].execution().unwrap();
    assert_eq!(run.members[0].status(), MemberStatus::RecoveryRequired);
    assert_eq!(observed.result.status, Status::RecoveryRequired);
    assert!(!observed.result.protocol_complete);
    assert!(observed.artifacts.contains(&binding(221)));
    assert_eq!(seen.borrow().calls, [1, 0]);
    assert_eq!(seen.borrow().effects, [1, 0]);
}

#[test]
fn live_rename_completion_uses_shared_order_without_publication_receipts() {
    let f = Fixture::new();
    let (mut a, mut b, seen) = pair();
    a.rename = true;
    b.rename = true;
    let mut budget = LogicalBudget::new(u64::MAX);
    let run = start_observed_renames(
        f.intent(),
        &mut a,
        &mut b,
        permits(),
        &mut budget,
        &Cancellation::default(),
    )
    .unwrap();
    assert_eq!(statuses(&run), [MemberStatus::ObservedRenameComplete; 2]);
    for (index, member) in run.members().iter().enumerate() {
        assert!(member.execution().is_none());
        let observed = member.observed_rename().unwrap();
        assert_eq!(observed.installed.identity, f.sources[index].identity);
        assert_eq!(observed.installed.facts, f.unit(index).output.as_bytes());
        assert!(observed.artifacts.contains(&observed.installed));
        assert_eq!(
            observed.charged_bytes,
            LogicalBudget::unit_charge(3).unwrap()
        );
    }
    assert_eq!(
        budget.charged(),
        2 * LogicalBudget::unit_charge(3).unwrap() + run.manifest().len() as u64
    );
    assert_eq!(
        &run.manifest()[4..4 + RENAME_PROTOCOL.len()],
        RENAME_PROTOCOL
    );
    let seen = seen.borrow();
    let position = |name: &str| seen.log.iter().position(|entry| entry == name).unwrap();
    assert!(position("stage1") < position("execute0"));
    assert!(position("manifest0") < position("execute0"));
    assert!(position("execute0") < position("execute1"));
    assert!(
        seen.originals
            .iter()
            .all(|value| value == b"frozen-original-date")
    );
}

#[test]
fn live_rename_requires_both_static_adapter_opt_ins_before_any_construction() {
    for index in 0..2 {
        let f = Fixture::new();
        let (mut a, mut b, seen) = pair();
        if index == 0 {
            a.supports_rename = false;
        } else {
            b.supports_rename = false;
        }
        let mut budget = LogicalBudget::new(u64::MAX);
        let result = start_observed_renames(
            f.intent(),
            &mut a,
            &mut b,
            permits(),
            &mut budget,
            &Cancellation::default(),
        );
        assert!(matches!(result, Err(Refusal::AdapterUnavailable)));
        assert_eq!(budget.charged(), 0);
        assert!(seen.borrow().log.is_empty());
    }
}

#[test]
fn publication_entry_keeps_its_original_protocol_and_qualified_completion() {
    let f = Fixture::new();
    let (mut a, mut b, _) = pair();
    a.rename = true;
    b.rename = true;
    let run = start(
        f.intent(),
        &mut a,
        &mut b,
        permits(),
        &mut LogicalBudget::new(u64::MAX),
        &Cancellation::default(),
    )
    .unwrap();
    assert_eq!(statuses(&run), [MemberStatus::Committed; 2]);
    assert_eq!(&run.manifest()[4..4 + PROTOCOL.len()], PROTOCOL);
    assert!(
        run.members()
            .iter()
            .all(|member| member.observed_rename().is_none()
                && member.execution().unwrap().receipt.is_some())
    );
}

#[test]
fn publication_receipt_cannot_substitute_for_live_rename_observation() {
    let f = Fixture::new();
    let (mut a, mut b, seen) = pair();
    let run = start_observed_renames(
        f.intent(),
        &mut a,
        &mut b,
        permits(),
        &mut LogicalBudget::new(u64::MAX),
        &Cancellation::default(),
    )
    .unwrap();
    assert_eq!(
        statuses(&run),
        [MemberStatus::RecoveryRequired, MemberStatus::Unattempted]
    );
    assert_eq!(seen.borrow().calls, [1, 0]);
    let execution = run.members()[0].execution().unwrap();
    assert_eq!(execution.result.status, Status::RecoveryRequired);
    assert!(!execution.result.protocol_complete);
    assert!(execution.receipt.is_some()); // Retained evidence never grants continuation.
}

#[test]
fn live_rename_requires_original_identity_and_retained_installed_binding() {
    for missing in [false, true] {
        let f = Fixture::new();
        let (mut a, mut b, seen) = pair();
        a.rename = true;
        b.rename = true;
        a.invalid_rename = !missing;
        a.omit_rename_artifact = missing;
        let run = start_observed_renames(
            f.intent(),
            &mut a,
            &mut b,
            permits(),
            &mut LogicalBudget::new(u64::MAX),
            &Cancellation::default(),
        )
        .unwrap();
        assert_eq!(
            statuses(&run),
            [MemberStatus::RecoveryRequired, MemberStatus::Unattempted]
        );
        assert_eq!(
            run.members()[0].refusal(),
            Some(Failure::InvalidBinding.into())
        );
        assert!(run.members()[0].observed_rename().is_some());
        assert_eq!(seen.borrow().calls, [1, 0]);
    }
}

#[test]
fn cancellation_after_first_observed_rename_is_terminal_for_the_exact_run() {
    let f = Fixture::new();
    let (mut a, mut b, seen) = pair();
    a.rename = true;
    b.rename = true;
    a.cancel_execute = true;
    let mut run = start_observed_renames(
        f.intent(),
        &mut a,
        &mut b,
        permits(),
        &mut LogicalBudget::new(u64::MAX),
        &Cancellation::default(),
    )
    .unwrap();
    let before = statuses(&run);
    assert_eq!(
        before,
        [
            MemberStatus::ObservedRenameComplete,
            MemberStatus::CancelledBeforePublish
        ]
    );
    assert!(run.staged_b.is_some());
    let (_caller, authority) = authorize(0, RestartAction::RecognizeCompletion);
    resume(
        &mut run,
        &mut a,
        &mut b,
        (Some(authority), None),
        permits(),
        &Cancellation::default(),
    );
    assert_eq!(statuses(&run), before);
    assert_eq!(run.members()[0].refusal(), Some(Refusal::LiveOnly));
    assert_eq!(seen.borrow().calls, [1, 0]);
    assert!(
        !seen
            .borrow()
            .log
            .iter()
            .any(|entry| entry.starts_with("verify") || entry.starts_with("inspect"))
    );
}

#[test]
fn ambiguous_second_rename_retains_first_and_never_finalizes_or_replays() {
    let f = Fixture::new();
    let (mut a, mut b, seen) = pair();
    a.rename = true;
    b.rename = true;
    b.behavior = Behavior::Uncertain;
    b.extra_uncertain_artifact = true;
    b.unavailable_finalizer = false;
    let mut run = start_observed_renames(
        f.intent(),
        &mut a,
        &mut b,
        permits(),
        &mut LogicalBudget::new(u64::MAX),
        &Cancellation::default(),
    )
    .unwrap();
    assert_eq!(
        statuses(&run),
        [
            MemberStatus::ObservedRenameComplete,
            MemberStatus::RecoveryRequired
        ]
    );
    let prior = run.members()[1].execution().unwrap().artifacts.clone();
    for _ in 0..2 {
        let (_caller, authority) = authorize(1, RestartAction::FinalizeExisting);
        resume(
            &mut run,
            &mut a,
            &mut b,
            (None, Some(authority)),
            permits(),
            &Cancellation::default(),
        );
    }
    assert_eq!(run.members()[1].execution().unwrap().artifacts, prior);
    assert!(prior.contains(&binding(221)));
    assert_eq!(seen.borrow().calls, [1, 1]);
    assert_eq!(seen.borrow().effects, [1, 1]);
    assert!(
        !seen
            .borrow()
            .log
            .iter()
            .any(|entry| entry.starts_with("inspect"))
    );
}

#[test]
fn live_rename_early_cancellation_cannot_be_resumed_with_new_authority() {
    let f = Fixture::new();
    let (mut a, mut b, seen) = pair();
    let cancel = Cancellation::default();
    cancel.request();
    let mut run = start_observed_renames(
        f.intent(),
        &mut a,
        &mut b,
        permits(),
        &mut LogicalBudget::new(u64::MAX),
        &cancel,
    )
    .unwrap();
    resume(
        &mut run,
        &mut a,
        &mut b,
        (None, None),
        permits(),
        &Cancellation::default(),
    );
    assert_eq!(run.members()[0].refusal(), Some(Refusal::LiveOnly));
    assert!(seen.borrow().log.is_empty());
}

#[test]
fn revoked_second_live_authority_preserves_first_observation_without_second_effect() {
    let f = Fixture::new();
    let (mut a, mut b, seen) = pair();
    a.rename = true;
    b.rename = true;
    let second = Permit::fresh();
    a.revoke_after_execute = Some(second.0.clone());
    let run = start_observed_renames(
        f.intent(),
        &mut a,
        &mut b,
        (Some(Permit::fresh()), Some(second)),
        &mut LogicalBudget::new(u64::MAX),
        &Cancellation::default(),
    )
    .unwrap();
    assert_eq!(
        statuses(&run),
        [MemberStatus::ObservedRenameComplete, MemberStatus::Refused]
    );
    assert_eq!(seen.borrow().calls, [1, 1]);
    assert_eq!(seen.borrow().effects, [1, 0]);
    assert_eq!(
        run.members()[1].execution().unwrap().result.failure,
        Some(Failure::CallerHistory)
    );
}
