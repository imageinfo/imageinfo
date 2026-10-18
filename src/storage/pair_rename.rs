//! Explicit ordered RAW/XMP names; no basename inference or public admission.
use super::path_rename::RenamePlan;
use std::path::Path;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum PairPlanError {
    DifferentParent,
    WrongKind,
    Alias,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub(crate) struct PairNames {
    plans: [RenamePlan; 2],
}
impl PairNames {
    pub(crate) fn new(plans: [RenamePlan; 2]) -> Result<Self, PairPlanError> {
        let parent = plans[0].source().parent();
        for (index, plan) in plans.iter().enumerate() {
            if plan.source().parent() != parent {
                return Err(PairPlanError::DifferentParent);
            }
            let extension = if index == 0 { "cr3" } else { "xmp" };
            if [plan.source(), plan.destination()].iter().any(|p| {
                !p.extension()
                    .and_then(|s| s.to_str())
                    .is_some_and(|s| s.eq_ignore_ascii_case(extension))
            }) {
                return Err(PairPlanError::WrongKind);
            }
        }
        for a in std::iter::once(plans[0].source()).chain(plans[0].steps()) {
            for b in std::iter::once(plans[1].source()).chain(plans[1].steps()) {
                if a.as_os_str()
                    .to_string_lossy()
                    .eq_ignore_ascii_case(&b.as_os_str().to_string_lossy())
                {
                    return Err(PairPlanError::Alias);
                }
            }
        }
        Ok(Self { plans })
    }
    pub(crate) fn plans(&self) -> &[RenamePlan; 2] {
        &self.plans
    }
    pub(crate) fn paths(&self) -> Vec<&Path> {
        self.plans
            .iter()
            .flat_map(|p| std::iter::once(p.source()).chain(p.steps()))
            .collect()
    }
}

#[cfg(windows)]
mod native {
    use super::*;
    use crate::storage::{
        self, Cancellation, Failure, LogicalBudget, Phase, Status, UnitResult,
        custody::CustodyRefusal,
        group::{
            self, Execution, ManifestFailure, ObservedRename, PreparationFailure, Refusal,
            RenameExecution, UnitAdapter, UnitIntent,
        },
        pair_rename_authority::{PairAuthority, PairBindings},
        path_rename::{PreparedRename, RenameObservation, RenameState, StopReason},
        runtime::Binding,
    };
    use imageinfo_windows_storage::{FileSnapshot, HeldArtifact, PrivateRoot};
    use std::{cell::RefCell, path::PathBuf, rc::Rc};

    pub(crate) struct PairPlan {
        names: PairNames,
        record_root: PathBuf,
        originals: [FileSnapshot; 2],
        parent: FileSnapshot,
        bindings: PairBindings,
        original_bytes: Vec<u8>,
        sources: [Binding; 2],
        parent_binding: Binding,
    }
    impl PairPlan {
        pub(crate) fn new(
            operation: &str,
            names: PairNames,
            record_root: PathBuf,
            originals: [&FileSnapshot; 2],
            parent: &FileSnapshot,
        ) -> Result<Self, CustodyRefusal> {
            if record_root.parent() != names.plans[0].source().parent()
                || names.paths().contains(&record_root.as_path())
            {
                return Err(CustodyRefusal::InvalidBindings);
            }
            let bindings = PairBindings::capture_snapshots(
                operation,
                &names,
                &record_root,
                originals,
                parent,
            )?;
            let original_bytes = bindings.bytes().to_vec();
            Ok(Self {
                sources: originals.map(|s| storage::windows::binding_snapshot(s, None)),
                parent_binding: storage::windows::binding_snapshot(parent, None),
                names,
                record_root,
                originals: originals.map(Clone::clone),
                parent: parent.clone(),
                bindings,
                original_bytes,
            })
        }
        pub(crate) fn bindings(&self) -> &PairBindings {
            &self.bindings
        }
    }
    #[derive(Clone, Copy, Debug, PartialEq, Eq)]
    pub(crate) enum HookStage {
        BeforeStep,
        AfterStep,
    }
    #[derive(Clone, Copy, Debug, PartialEq, Eq)]
    pub(crate) enum HookAction {
        Continue,
        Stop,
        LostResponse,
    }
    #[derive(Clone, Debug)]
    pub(crate) struct PairReport {
        pub statuses: [group::MemberStatus; 2],
        pub observations: [Option<RenameObservation>; 2],
        pub refusals: [Option<Refusal>; 2],
        pub manifest_binding: Option<Binding>,
        pub retained_root: Option<Binding>,
    }
    pub(crate) struct Pair {
        plan: PairPlan,
        authority: PairAuthority,
        sessions: [Option<PreparedRename>; 2],
        root: Option<PrivateRoot>,
        manifest: Option<HeldArtifact>,
        used: bool,
    }
    impl Pair {
        pub(crate) fn open(plan: PairPlan, authority: PairAuthority) -> Result<Self, Failure> {
            authority
                .check(&plan.bindings)
                .map_err(|_| Failure::CallerHistory)?;
            Ok(Self {
                plan,
                authority,
                sessions: [None, None],
                root: None,
                manifest: None,
                used: false,
            })
        }
        pub(crate) fn execute(
            &mut self,
            cancel: &Cancellation,
            budget: &mut LogicalBudget,
        ) -> Result<PairReport, Refusal> {
            self.execute_with(cancel, budget, |_, _| HookAction::Continue)
        }
        pub(crate) fn execute_with(
            &mut self,
            cancel: &Cancellation,
            budget: &mut LogicalBudget,
            mut hook: impl FnMut(usize, HookStage) -> HookAction,
        ) -> Result<PairReport, Refusal> {
            if self.used {
                return Err(Refusal::InvalidIntent);
            }
            self.used = true;
            let plan = &self.plan;
            let outputs = plan
                .names
                .plans
                .each_ref()
                .map(|p| p.destination().file_name().unwrap().to_str().unwrap());
            let units = std::array::from_fn(|i| UnitIntent {
                identity: if i == 0 { b"raw" } else { b"xmp" },
                operation: "explicit-pair-name-move",
                revision: "v1",
                profile: "unqualified-held-same-parent-ntfs",
                implementation: "retained-path-rename-v1",
                source: &plan.sources[i],
                parent: &plan.parent_binding,
                target: None,
                output: outputs[i],
                candidate_len: 0,
            });
            let intent = group::Intent {
                identity: b"explicit-raw-xmp-pair-v1",
                original: &plan.original_bytes,
                units,
            };
            let shared = Rc::new(RefCell::new(
                &mut hook as &mut dyn FnMut(usize, HookStage) -> HookAction,
            ));
            let [left, right] = &mut self.sessions;
            let mut a = Member {
                index: 0,
                plan,
                authority: &self.authority,
                session: left,
                root: &mut self.root,
                manifest: &mut self.manifest,
                hook: shared.clone(),
                charged: 0,
            };
            let mut unused_root = None;
            let mut unused_manifest = None;
            let mut b = Member {
                index: 1,
                plan,
                authority: &self.authority,
                session: right,
                root: &mut unused_root,
                manifest: &mut unused_manifest,
                hook: shared,
                charged: 0,
            };
            let run = group::start_observed_renames(
                intent,
                &mut a,
                &mut b,
                (Some(()), Some(())),
                budget,
                cancel,
            )?;
            let mut statuses = run.members().each_ref().map(|m| m.status());
            let mut refusals = run.members().each_ref().map(|m| m.refusal());
            let manifest_binding = run.manifest_binding().cloned();
            drop(run);
            drop(a);
            drop(b);
            if self.authority.check(&plan.bindings).is_err()
                && let Some(index) = statuses
                    .iter()
                    .rposition(|s| *s != group::MemberStatus::Unattempted)
            {
                statuses[index] = if self.sessions[index].as_ref().is_some_and(|s| {
                    s.observe().completed_steps > 0
                        || s.observe().state == RenameState::RecoveryRequired
                }) {
                    group::MemberStatus::RecoveryRequired
                } else {
                    group::MemberStatus::Refused
                };
                refusals[index] = Some(Failure::CallerHistory.into());
            }
            for (i, session) in self.sessions.iter_mut().enumerate() {
                if let Some(session) = session
                    && session.checkpoint().state == RenameState::RecoveryRequired
                {
                    statuses[i] = group::MemberStatus::RecoveryRequired;
                }
            }
            Ok(PairReport {
                statuses,
                refusals,
                manifest_binding,
                retained_root: self
                    .root
                    .as_ref()
                    .map(|r| storage::windows::binding_snapshot(r.snapshot(), None)),
                observations: self
                    .sessions
                    .each_ref()
                    .map(|s| s.as_ref().map(PreparedRename::observe)),
            })
        }
    }
    struct Stage {
        artifacts: Vec<Binding>,
    }
    struct Member<'a, 'h> {
        index: usize,
        plan: &'a PairPlan,
        authority: &'a PairAuthority,
        session: &'a mut Option<PreparedRename>,
        root: &'a mut Option<PrivateRoot>,
        manifest: &'a mut Option<HeldArtifact>,
        hook: Rc<RefCell<&'h mut dyn FnMut(usize, HookStage) -> HookAction>>,
        charged: u64,
    }
    impl Member<'_, '_> {
        fn source(&self) -> Binding {
            self.plan.sources[self.index].clone()
        }
        fn current(&self) -> Result<(), Refusal> {
            self.authority
                .check(&self.plan.bindings)
                .map_err(|_| Refusal::Unit(Failure::CallerHistory))
        }
        fn failure(&self, error: Failure) -> Execution {
            let changed = self.session.as_ref().is_some_and(|s| {
                let o = s.observe();
                o.completed_steps > 0 || o.state == RenameState::RecoveryRequired
            });
            Execution {
                result: UnitResult {
                    status: if changed {
                        Status::RecoveryRequired
                    } else if error == Failure::Cancelled {
                        Status::CancelledBeforePublish
                    } else {
                        Status::Refused
                    },
                    phase: Phase::Prepublication,
                    failure: Some(error),
                    publication_possible: changed,
                    release_possible: changed,
                    retained_material: true,
                    pending_cleanup: false,
                    charged_bytes: self.charged,
                    protocol_complete: false,
                },
                receipt: None,
                artifacts: vec![self.source()],
            }
        }
        fn same(&self, unit: UnitIntent<'_>, original: &[u8]) -> bool {
            original == self.plan.original_bytes
                && unit.identity == if self.index == 0 { b"raw" } else { b"xmp" }
                && unit.operation == "explicit-pair-name-move"
                && unit.revision == "v1"
                && unit.profile == "unqualified-held-same-parent-ntfs"
                && unit.implementation == "retained-path-rename-v1"
                && unit.candidate_len == 0
                && unit.source == &self.plan.sources[self.index]
                && unit.parent == &self.plan.parent_binding
                && unit.target.is_none()
                && unit.output
                    == self.plan.names.plans[self.index]
                        .destination()
                        .file_name()
                        .unwrap()
                        .to_str()
                        .unwrap()
        }
    }
    impl UnitAdapter for Member<'_, '_> {
        type ExecuteAuthority = ();
        type Staged = Stage;
        fn supports_observed_rename(&self) -> bool {
            true
        }
        fn preflight(
            &mut self,
            unit: UnitIntent<'_>,
            original: &[u8],
            _: &(),
        ) -> Result<(), Refusal> {
            self.current()?;
            if !self.same(unit, original) {
                return Err(Refusal::InvalidIntent);
            }
            Ok(())
        }
        fn acquire_guard(&mut self, _: &Binding) -> Result<(), Refusal> {
            self.current()?;
            if self.session.is_none() {
                *self.session = Some(
                    PreparedRename::open(
                        self.plan.names.plans[self.index].clone(),
                        &self.plan.originals[self.index],
                    )
                    .map_err(|_| Refusal::Unit(Failure::Conflict))?,
                );
            }
            Ok(())
        }
        fn stage(
            &mut self,
            _: UnitIntent<'_>,
            _: &[u8],
            budget: LogicalBudget,
            cancel: &Cancellation,
        ) -> Result<Stage, PreparationFailure> {
            self.charged = budget.charged();
            if cancel.is_requested() {
                return Err(PreparationFailure {
                    refusal: Failure::Cancelled.into(),
                    artifacts: vec![self.source()],
                });
            }
            Ok(Stage {
                artifacts: vec![self.source()],
            })
        }
        fn staged_artifacts(staged: &Stage) -> &[Binding] {
            &staged.artifacts
        }
        fn retain_manifest(&mut self, bytes: &[u8]) -> Result<Binding, ManifestFailure> {
            let result = (|| -> Result<Binding, Failure> {
                self.current().map_err(|_| Failure::CallerHistory)?;
                let root =
                    PrivateRoot::create(&self.plan.record_root).map_err(|_| Failure::BackendIo)?;
                *self.root = Some(root);
                let root = self.root.as_ref().unwrap();
                let p = root.parent_snapshot();
                let expected = &self.plan.parent;
                if p.volume_serial_number != expected.volume_serial_number
                    || p.file_index != expected.file_index
                    || p.attributes != expected.attributes
                    || p.creation_time != expected.creation_time
                    || p.owner_dacl != expected.owner_dacl
                {
                    return Err(Failure::InvalidBinding);
                }
                root.check()
                    .and_then(|_| root.flush())
                    .and_then(|_| root.flush_parent())
                    .map_err(|_| Failure::BackendIo)?;
                *self.manifest = Some(
                    root.create_artifact("pair-manifest", bytes, storage::MAX_RECORD_BYTES)
                        .map_err(|_| Failure::BackendIo)?,
                );
                let manifest = self.manifest.as_mut().unwrap();
                manifest
                    .check(root)
                    .and_then(|_| manifest.flush())
                    .and_then(|_| root.flush())
                    .map_err(|_| Failure::BackendIo)?;
                Ok(storage::windows::binding_snapshot(
                    manifest.snapshot(),
                    Some(bytes),
                ))
            })();
            result.map_err(|f| ManifestFailure {
                refusal: f.into(),
                retained: self
                    .manifest
                    .as_ref()
                    .map(|m| storage::windows::binding_snapshot(m.snapshot(), Some(m.bytes()))),
            })
        }
        fn check_manifest(&mut self, binding: &Binding, bytes: &[u8]) -> Result<(), Refusal> {
            self.current()?;
            if let Some(session) = self.session.as_mut()
                && session.checkpoint().state == RenameState::RecoveryRequired
            {
                return Err(Failure::Conflict.into());
            }
            let root = self.root.as_ref().ok_or(Refusal::InvalidIntent)?;
            root.check()
                .map_err(|_| Refusal::Unit(Failure::InvalidBinding))?;
            let manifest = self.manifest.as_mut().ok_or(Refusal::InvalidIntent)?;
            manifest
                .check(root)
                .map_err(|_| Refusal::Unit(Failure::InvalidBinding))?;
            if manifest.bytes() != bytes
                || storage::windows::binding_snapshot(manifest.snapshot(), Some(bytes)) != *binding
            {
                return Err(Refusal::InvalidIntent);
            }
            Ok(())
        }
        fn execute(
            &mut self,
            _: Stage,
            _: UnitIntent<'_>,
            _: &[u8],
            _: (),
            _: &Cancellation,
        ) -> Execution {
            self.failure(Failure::Unsupported)
        }
        fn execute_observed_rename(
            &mut self,
            _: Stage,
            unit: UnitIntent<'_>,
            original: &[u8],
            _: (),
            cancel: &Cancellation,
        ) -> RenameExecution {
            if !self.same(unit, original) {
                return RenameExecution::Failed(self.failure(Failure::InvalidBinding));
            }
            loop {
                if self.current().is_err() {
                    return RenameExecution::Failed(self.failure(Failure::CallerHistory));
                }
                let action = (self.hook.borrow_mut())(self.index, HookStage::BeforeStep);
                if self.current().is_err() {
                    return RenameExecution::Failed(self.failure(Failure::CallerHistory));
                }
                if action == HookAction::Stop || cancel.is_requested() {
                    self.session.as_mut().unwrap().advance(true);
                    return RenameExecution::Failed(self.failure(Failure::Cancelled));
                }
                if action == HookAction::LostResponse {
                    #[cfg(test)]
                    self.session.as_mut().unwrap().lose_next_response();
                    #[cfg(not(test))]
                    return RenameExecution::Failed(self.failure(Failure::Unsupported));
                }
                let observation = self.session.as_mut().unwrap().advance(false);
                let action = (self.hook.borrow_mut())(self.index, HookStage::AfterStep);
                // A completed OS call does not bypass the current caller boundary.
                // Preserve its confirmed prefix while refusing further completion.
                if self.current().is_err() {
                    return RenameExecution::Failed(self.failure(Failure::CallerHistory));
                }
                if action == HookAction::LostResponse {
                    return RenameExecution::Failed(self.failure(Failure::Unsupported));
                }
                if observation.state == RenameState::Finished {
                    return RenameExecution::Complete(ObservedRename {
                        installed: self.source(),
                        artifacts: vec![self.source()],
                        charged_bytes: self.charged,
                    });
                }
                if !matches!(
                    observation.state,
                    RenameState::Ready | RenameState::AtTemporary
                ) {
                    let error = match observation.reason {
                        Some(StopReason::UnknownResult) => Failure::Ambiguous,
                        Some(StopReason::Cancelled) => Failure::Cancelled,
                        _ => Failure::Conflict,
                    };
                    return RenameExecution::Failed(self.failure(error));
                }
                if action == HookAction::Stop {
                    self.session.as_mut().unwrap().advance(true);
                    return RenameExecution::Failed(self.failure(Failure::Cancelled));
                }
            }
        }
    }
}
#[cfg(windows)]
#[allow(unused_imports)] // Disabled qualification caller; no public selector.
pub(crate) use native::{HookAction, HookStage, Pair, PairPlan, PairReport};
#[cfg(test)]
#[path = "pair_rename/tests.rs"]
mod tests;
