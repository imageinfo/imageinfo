//! One live, optional two-step marker operation in a fresh private root.
//! Its observations never authorize restart, cleanup, rollback or another call.

use super::{Failure, LogicalBudget};

const MARKER_LIMIT: u64 = 64 * 1024 * 1024;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(crate) enum ContinuationPolicy {
    GuardHeldQuiet20Seconds,
    #[cfg(all(windows, test))]
    ImmediateDiagnostic,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, serde::Serialize)]
pub(crate) enum Binding {
    Absent,
    Old,
    Candidate,
    Foreign,
    Unknown,
}

use Binding::{Absent, Candidate, Foreign, Old, Unknown};

const PREFIXES: [[Binding; 3]; 3] = [
    [Old, Absent, Candidate],
    [Absent, Old, Candidate],
    [Candidate, Old, Absent],
];

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(crate) enum Outcome {
    Ready,
    Refused,
    PartialObserved,
    CompleteObserved,
    RecoveryRequired,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(crate) struct Report {
    pub outcome: Outcome,
    pub failure: Option<Failure>,
    pub confirmed_prefix: u8,
    /// Target, retained, staging. Independently observed slots can survive a
    /// diagnostic failure; an unknown slot never authorizes another call.
    pub bindings: [Binding; 3],
    /// Actual or possible native call, separate from verified prefix.
    pub attempted: [bool; 2],
    pub response_discarded: [bool; 2],
    pub quiet_elapsed_nanos: Option<u64>,
}

impl Report {
    fn refused(failure: Failure) -> Self {
        Self {
            outcome: Outcome::Refused,
            failure: Some(failure),
            confirmed_prefix: 0,
            bindings: [Unknown; 3],
            attempted: [false; 2],
            response_discarded: [false; 2],
            quiet_elapsed_nanos: None,
        }
    }

    fn confirm(&mut self, bindings: [Binding; 3]) -> bool {
        let step = usize::from(self.confirmed_prefix);
        self.bindings = bindings;
        if !self.attempted.get(step).copied().unwrap_or(false)
            || self.response_discarded[step]
            || bindings != PREFIXES[step + 1]
        {
            return false;
        }
        self.confirmed_prefix += 1;
        true
    }
}

fn precharge(budget: &mut LogicalBudget, candidate_len: u64) -> Result<(), Failure> {
    if candidate_len > MARKER_LIMIT {
        return Err(Failure::CandidateTooLarge);
    }
    budget.reserve_construction(LogicalBudget::unit_charge(candidate_len)?)
}

fn admissible_stop_map(prefix: u8, bindings: [Binding; 3]) -> bool {
    matches!(
        (prefix, bindings),
        (0, [Old, Absent | Foreign, Candidate])
            | (1, [Absent | Foreign, Old, Candidate])
            | (2, [Candidate, Old, Absent])
    )
}

#[cfg(not(windows))]
pub(crate) fn unsupported() -> Report {
    Report::refused(Failure::Unsupported)
}

#[cfg(windows)]
mod native {
    use super::*;
    use crate::storage::{
        Cancellation, MAX_RECORD_BYTES,
        custody::{ExchangeGeneration, TrustedCurrentCaller},
    };
    use imageinfo_windows_storage::{
        ArtifactBinding, ExistingMoveBinding, ExistingMoveOutcome, FileSnapshot, HeldArtifact,
        HeldExistingMoveSession, PrivateRoot, validate_leaf,
    };
    use serde_json::json;
    use sha2::{Digest, Sha256};
    use std::{
        io,
        path::PathBuf,
        time::{Duration, Instant},
    };

    const QUIET_GAP: Duration = Duration::from_secs(20);
    const OBSERVATION_NAMES: [&str; 8] = [
        "retain-install-0.record",
        "retain-install-1.record",
        "retain-install-2.record",
        "retain-install-3.record",
        "retain-install-4.record",
        "retain-install-5.record",
        "retain-install-6.record",
        "retain-install-7.record",
    ];

    /// The only candidate construction uses the ordinary owner-private,
    /// default-stream SDK constructor. Times and ordinary attributes are those
    /// assigned to this fresh object and checked exactly from that point.
    pub(crate) struct Plan {
        leaves: [String; 3],
        old: FileSnapshot,
        candidate: Vec<u8>,
        policy: ContinuationPolicy,
    }

    impl Plan {
        pub(crate) fn new(
            leaves: [&str; 3],
            old: FileSnapshot,
            candidate: Vec<u8>,
            policy: ContinuationPolicy,
        ) -> Result<Self, Failure> {
            for (index, leaf) in leaves.iter().enumerate() {
                if !leaf.is_ascii()
                    || validate_leaf(leaf).is_err()
                    || leaves[..index]
                        .iter()
                        .chain(OBSERVATION_NAMES.iter())
                        .any(|other| other.eq_ignore_ascii_case(leaf))
                {
                    return Err(Failure::InvalidBinding);
                }
            }
            if candidate.len() as u64 > MARKER_LIMIT {
                return Err(Failure::CandidateTooLarge);
            }
            if old.links != 1 || old.size > MARKER_LIMIT || old.owner_dacl.len() > 8000 {
                return Err(Failure::InvalidBinding);
            }
            Ok(Self {
                leaves: leaves.map(str::to_owned),
                old,
                candidate,
                policy,
            })
        }
    }

    #[derive(Clone, Copy, Debug, Eq, PartialEq)]
    pub(crate) enum Stage {
        Waiting,
        BeforeCall,
        AfterCall,
    }

    /// Consumes the actual fresh root and selected plan. The caller's finite
    /// revocation generation and all live guards stay with this single session.
    pub(crate) struct Session {
        leaves: [String; 3],
        paths: [PathBuf; 3],
        policy: ContinuationPolicy,
        caller: ExchangeGeneration,
        root: PrivateRoot,
        old: HeldExistingMoveSession,
        candidate: HeldArtifact,
        records: Vec<HeldArtifact>,
        confirmed_at: Option<Instant>,
        report: Report,
    }

    impl Session {
        pub(crate) fn open(
            plan: Plan,
            root: PrivateRoot,
            caller: &mut TrustedCurrentCaller,
            budget: &mut LogicalBudget,
            cancel: &Cancellation,
        ) -> Result<Self, Report> {
            if cancel.is_requested() {
                return Err(Report::refused(Failure::Cancelled));
            }
            precharge(budget, plan.candidate.len() as u64).map_err(Report::refused)?;
            let caller = caller
                .begin_exchange()
                .map_err(|_| Report::refused(Failure::CallerHistory))?;
            let paths = plan.leaves.each_ref().map(|leaf| root.path().join(leaf));
            root.check()
                .map_err(|_| Report::refused(Failure::InvalidBinding))?;
            let old = HeldExistingMoveSession::open(&paths[0], &plan.old, &paths)
                .map_err(|_| Report::refused(Failure::InvalidBinding))?;
            if cancel.is_requested() {
                return Err(Report::refused(Failure::Cancelled));
            }
            let candidate = root
                .create_artifact(&plan.leaves[2], &plan.candidate, MARKER_LIMIT)
                .map_err(|_| Report::refused(Failure::BackendIo))?;
            let mut value = Self {
                leaves: plan.leaves,
                paths,
                policy: plan.policy,
                caller,
                root,
                old,
                candidate,
                records: Vec::new(),
                confirmed_at: None,
                report: Report {
                    outcome: Outcome::Ready,
                    failure: None,
                    ..Report::refused(Failure::InvalidBinding)
                },
            };
            if let Err(failure) = value.checkpoint(0) {
                value.stop(failure, false);
            } else if value.save("prepared", None).is_err() {
                value.stop(Failure::BackendIo, false);
            }
            Ok(value)
        }

        pub(crate) fn report(&self) -> Report {
            self.report
        }

        pub(crate) fn advance(&mut self, cancel: &Cancellation) -> Report {
            self.advance_with(cancel, |_, _| false)
        }

        fn check_objects(&mut self) -> io::Result<()> {
            self.root.check()?;
            // Current-object check is correct even after the candidate occupies
            // the old object's vacated target. Last-move inspection is not.
            self.old.check()?;
            self.candidate.check_object(&self.root)?;
            for record in &mut self.records {
                record.check(&self.root)?;
            }
            Ok(())
        }

        fn observe(&self) -> [Binding; 3] {
            std::array::from_fn(|slot| {
                use ArtifactBinding as A;
                use ExistingMoveBinding as O;
                match (
                    self.old.binding(&self.paths[slot]),
                    self.candidate.binding(&self.root, &self.leaves[slot]),
                ) {
                    (Ok(O::Absent), Ok(A::Absent)) => Absent,
                    (Ok(O::HeldObject), Ok(A::ForeignObject)) => Old,
                    (Ok(O::ForeignObject), Ok(A::HeldObject)) => Candidate,
                    (Ok(O::ForeignObject), Ok(A::ForeignObject)) => Foreign,
                    _ => Unknown,
                }
            })
        }

        fn checkpoint(&mut self, prefix: usize) -> Result<(), Failure> {
            self.report.bindings = self.observe();
            self.check_objects().map_err(|_| Failure::InvalidBinding)?;
            if self.report.bindings != PREFIXES[prefix] {
                return Err(if admissible_stop_map(prefix as u8, self.report.bindings) {
                    Failure::Conflict
                } else {
                    Failure::InvalidBinding
                });
            }
            Ok(())
        }

        fn save(&mut self, phase: &str, next_call: Option<usize>) -> io::Result<()> {
            let leaf = OBSERVATION_NAMES
                .get(self.records.len())
                .ok_or_else(|| io::Error::other("RETAIN_INSTALL_RECORD_BOUND"))?;
            let encoded = serde_json::to_vec(&json!({
                "schema": "imageinfo.private-retain-install-observation.v1",
                "phase": phase,
                "selectedLeaves": self.leaves,
                "root": self.root.snapshot().binding_bytes(),
                "old": self.old.snapshot().binding_bytes(),
                "candidate": self.candidate.snapshot().binding_bytes(),
                "candidateSha256": format!("{:x}", Sha256::digest(self.candidate.bytes())),
                "candidateConstruction": "fresh-owner-private-default-stream",
                "continuationPolicy": format!("{:?}", self.policy),
                "quietElapsedNanos": self.report.quiet_elapsed_nanos,
                "confirmedPrefix": self.report.confirmed_prefix,
                "bindings": self.report.bindings,
                "attempted": self.report.attempted,
                "responseDiscarded": self.report.response_discarded,
                "nextCallMayFollow": next_call,
                "outcome": format!("{:?}", self.report.outcome),
                "failure": self.report.failure.map(|failure| format!("{failure:?}")),
                "qualified": false,
                "restartAuthority": false,
            }))?;
            let record = self
                .root
                .create_artifact(leaf, &encoded, MAX_RECORD_BYTES)?;
            self.records.push(record);
            Ok(())
        }

        fn stop(&mut self, failure: Failure, possibly_unconfirmed_effect: bool) -> Report {
            self.report.bindings = self.observe();
            let prefix = self.report.confirmed_prefix;
            let trustworthy =
                admissible_stop_map(prefix, self.report.bindings) && self.check_objects().is_ok();
            self.report.failure = Some(failure);
            self.report.outcome = if possibly_unconfirmed_effect || (prefix > 0 && !trustworthy) {
                self.old.mark_uncertain();
                Outcome::RecoveryRequired
            } else if prefix == 0 {
                Outcome::Refused
            } else {
                Outcome::PartialObserved
            };
            if self.save("terminal-stop", None).is_err() && prefix > 0 {
                self.old.mark_uncertain();
                self.report.outcome = Outcome::RecoveryRequired;
            }
            self.report
        }

        fn check_permission(&self, cancel: &Cancellation) -> Result<(), Failure> {
            if cancel.is_requested() {
                return Err(Failure::Cancelled);
            }
            self.caller.check().map_err(|_| Failure::CallerHistory)
        }

        fn wait(
            &mut self,
            cancel: &Cancellation,
            hook: &mut impl FnMut(usize, Stage) -> bool,
        ) -> Result<(), Failure> {
            let confirmed = self.confirmed_at.ok_or(Failure::InvalidBinding)?;
            loop {
                let elapsed = confirmed.elapsed();
                self.report.quiet_elapsed_nanos = u64::try_from(elapsed.as_nanos()).ok();
                if self.report.quiet_elapsed_nanos.is_none() {
                    return Err(Failure::LengthOverflow);
                }
                hook(1, Stage::Waiting);
                self.check_permission(cancel)?;
                if self.policy != ContinuationPolicy::GuardHeldQuiet20Seconds
                    || elapsed >= QUIET_GAP
                {
                    return Ok(());
                }
                std::thread::sleep((QUIET_GAP - elapsed).min(Duration::from_millis(50)));
            }
        }

        // Test hooks can discard a returned namespace-call result. They cannot
        // synthesize one or alter the observed confirmation rules.
        pub(crate) fn advance_with(
            &mut self,
            cancel: &Cancellation,
            mut hook: impl FnMut(usize, Stage) -> bool,
        ) -> Report {
            if self.report.outcome != Outcome::Ready {
                return self.report;
            }
            let step = usize::from(self.report.confirmed_prefix);
            if let Err(failure) = self.check_permission(cancel) {
                return self.stop(failure, false);
            }
            if step == 1
                && let Err(failure) = self.wait(cancel, &mut hook)
            {
                return self.stop(failure, false);
            }
            if let Err(failure) = self.checkpoint(step) {
                return self.stop(failure, step > 0 && failure == Failure::InvalidBinding);
            }
            if self.save("call-may-follow", Some(step)).is_err() {
                return self.stop(Failure::BackendIo, false);
            }
            hook(step, Stage::BeforeCall);
            if let Err(failure) = self
                .checkpoint(step)
                .and_then(|()| self.check_permission(cancel))
            {
                return self.stop(failure, step > 0 && failure == Failure::InvalidBinding);
            }
            self.report.attempted[step] = true;
            let result = if step == 0 {
                let result = self.old.move_to(&self.paths[1], false);
                self.report.attempted[step] = self.old.attempted_steps() != 0;
                match result {
                    ExistingMoveOutcome::ObservedMoved => Ok(()),
                    ExistingMoveOutcome::ObservedNoEffect => Err((Failure::Conflict, false)),
                    ExistingMoveOutcome::NotAttempted => Err((Failure::InvalidBinding, false)),
                    ExistingMoveOutcome::RecoveryRequired => Err((Failure::Ambiguous, true)),
                }
            } else {
                let result = self
                    .candidate
                    .publish_no_replace(&self.root, &self.leaves[0]);
                self.report.attempted[step] = self.candidate.publication_attempted();
                result.map_err(|error| {
                    if error.kind() == io::ErrorKind::AlreadyExists {
                        (Failure::Conflict, false)
                    } else {
                        (Failure::BackendIo, self.report.attempted[step])
                    }
                })
            };
            if hook(step, Stage::AfterCall) {
                self.report.response_discarded[step] = true;
                return self.stop(Failure::Ambiguous, true);
            }
            if let Err((failure, possibly_unconfirmed_effect)) = result {
                return self.stop(failure, possibly_unconfirmed_effect);
            }
            if let Err(failure) = self.checkpoint(step + 1) {
                return self.stop(failure, true);
            }
            // A returned installation is observable even if the caller loses
            // authority before confirmation. Keep its actual map in the stop.
            if step == 1 && self.caller.check().is_err() {
                return self.stop(Failure::CallerHistory, true);
            }
            if !self.report.confirm(self.report.bindings) {
                return self.stop(Failure::InvalidBinding, true);
            }
            if step == 0 {
                self.confirmed_at = Some(Instant::now());
                if self.save("retention-observed", None).is_err() {
                    return self.stop(Failure::BackendIo, true);
                }
                if let Err(failure) = self.check_permission(cancel) {
                    return self.stop(failure, false);
                }
            } else {
                self.report.outcome = Outcome::CompleteObserved;
                if self.save("installation-observed", None).is_err() {
                    return self.stop(Failure::BackendIo, true);
                }
                if let Err(failure) = self.checkpoint(2) {
                    return self.stop(failure, true);
                }
                if self.caller.check().is_err() {
                    return self.stop(Failure::CallerHistory, true);
                }
            }
            self.report
        }
    }
}

#[cfg(windows)]
#[allow(unused_imports)] // Explicit research caller; no production writer is admitted.
pub(crate) use native::{Plan, Session, Stage};

#[cfg(test)]
#[path = "retain_install/tests.rs"]
mod tests;
