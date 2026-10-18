//! One live caller's bounded, unqualified two-name exchange.
//!
//! The adapter owns the actual three-move session and both original guards.
//! CompleteObserved is an observation, never a durable commitment or a receipt.
//! No saved phase, parsed record or result can construct or resume this caller.

use super::{Failure, path_cycle};

/// Exchange facts retain the cycle's last observed map, including unknown slots.
/// A missing failure is not a commitment claim; the cycle outcome is decisive.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(crate) struct ExchangeReport {
    pub cycle: path_cycle::Report,
    pub failure: Option<Failure>,
    pub terminal: bool,
}

impl ExchangeReport {
    fn from_cycle(cycle: path_cycle::Report, failure: Option<Failure>, terminal: bool) -> Self {
        Self {
            failure: if cycle.uncertain {
                Some(Failure::Ambiguous)
            } else {
                failure
            },
            terminal: terminal || cycle.outcome != path_cycle::Outcome::Ready,
            cycle,
        }
    }
}

#[cfg(windows)]
mod native {
    use super::*;
    use crate::storage::{
        Cancellation,
        custody::CustodyRefusal,
        exchange_authority::{ExchangeAuthority, ExchangeBindings},
        path_cycle::{ContinuationPolicy, Cycle, HookAction, HookStage, Plan},
    };
    use imageinfo_windows_storage::FileSnapshot;
    use std::{io, path::PathBuf};

    /// Explicit original snapshot/plan observation. Possession is not authority.
    pub(crate) struct ExchangePlan {
        plan: Plan,
        record_root: PathBuf,
        originals: [FileSnapshot; 2],
        bindings: ExchangeBindings,
    }

    impl ExchangePlan {
        pub(crate) fn new(
            operation: &str,
            plan: Plan,
            record_root: PathBuf,
            alpha: &FileSnapshot,
            beta: &FileSnapshot,
        ) -> Result<Self, CustodyRefusal> {
            let bindings =
                ExchangeBindings::capture_snapshots(operation, &plan, &record_root, alpha, beta)?;
            Ok(Self {
                plan,
                record_root,
                originals: [alpha.clone(), beta.clone()],
                bindings,
            })
        }

        pub(crate) fn bindings(&self) -> &ExchangeBindings {
            &self.bindings
        }
    }

    /// Not cloneable and intentionally has no reopen/import constructor.
    pub(crate) struct Exchange {
        cycle: Cycle,
        authority: ExchangeAuthority,
        bindings: ExchangeBindings,
        report: ExchangeReport,
    }

    impl Exchange {
        pub(crate) fn open(
            plan: ExchangePlan,
            authority: ExchangeAuthority,
        ) -> Result<Self, Failure> {
            authority
                .check(&plan.bindings)
                .map_err(|_| Failure::CallerHistory)?;
            // Never select the immediate diagnostic or reset any property.
            let cycle = Cycle::open_with_policy(
                plan.plan,
                &plan.originals[0],
                &plan.originals[1],
                &plan.record_root,
                ContinuationPolicy::GuardHeldQuiet20Seconds,
            )
            .map_err(classify_open)?;
            let report = ExchangeReport::from_cycle(cycle.report(), None, false);
            Ok(Self {
                cycle,
                authority,
                bindings: plan.bindings,
                report,
            })
        }

        pub(crate) fn report(&self) -> ExchangeReport {
            self.report
        }

        pub(crate) fn plan(&self) -> &Plan {
            self.cycle.plan()
        }

        pub(crate) fn policy(&self) -> ContinuationPolicy {
            self.cycle.policy()
        }

        pub(crate) fn quiet_elapsed_nanos(&self) -> [Option<u64>; 2] {
            self.cycle.quiet_elapsed_nanos()
        }

        pub(crate) fn advance(&mut self, cancel: &Cancellation) -> ExchangeReport {
            self.advance_with(cancel, |_, _| HookAction::Continue)
        }

        /// Hooks support bounded qualification only; an uncertain return is
        /// terminal even when an observer knows the actual underlying result.
        pub(crate) fn advance_with(
            &mut self,
            cancel: &Cancellation,
            mut hook: impl FnMut(u8, HookStage) -> HookAction,
        ) -> ExchangeReport {
            if self.report.terminal {
                return self.report;
            }
            if self.authority.check(&self.bindings).is_err() {
                // No next call begins. Retain the live guards and last observed
                // prefix, without waiting for or resuming a revoked operation.
                let mut cycle = self.cycle.report();
                cycle.outcome = if cycle.confirmed_prefix == 0 {
                    path_cycle::Outcome::NoEffect
                } else {
                    path_cycle::Outcome::Partial
                };
                self.report = ExchangeReport::from_cycle(cycle, Some(Failure::CallerHistory), true);
                return self.report;
            }
            let mut failure = None;
            let authority = &self.authority;
            let bindings = &self.bindings;
            let cycle = self.cycle.advance_with(cancel, |prefix, stage| {
                // BeforeCall runs after the selected quiet gap. Recheck both
                // before and after a qualification hook so it cannot revoke the
                // caller and then accidentally permit the next native call.
                if authority.check(bindings).is_err() {
                    failure = Some(Failure::CallerHistory);
                    return HookAction::Stop;
                }
                let action = hook(prefix, stage);
                if authority.check(bindings).is_err() {
                    failure = Some(Failure::CallerHistory);
                    return HookAction::Stop;
                }
                if action == HookAction::LostResponse {
                    failure = Some(Failure::Ambiguous);
                }
                action
            });
            if failure.is_none()
                && cancel.is_requested()
                && cycle.outcome != path_cycle::Outcome::CompleteObserved
            {
                failure = Some(Failure::Cancelled);
            }
            if failure.is_none() && cycle.bindings.contains(&path_cycle::Binding::Foreign) {
                failure = Some(Failure::Conflict);
            }
            self.report = ExchangeReport::from_cycle(cycle, failure, false);
            self.report
        }
    }

    fn classify_open(error: io::Error) -> Failure {
        if error.kind() == io::ErrorKind::AlreadyExists {
            Failure::Conflict
        } else if error.kind() == io::ErrorKind::Unsupported {
            Failure::Unsupported
        } else if error.to_string() == "CYCLE_INITIAL_MAP" {
            Failure::Conflict
        } else {
            Failure::BackendIo
        }
    }
}

#[cfg(windows)]
#[allow(unused_imports)] // Qualification-only caller until an exact profile is admitted.
pub(crate) use native::{Exchange, ExchangePlan};

#[cfg(test)]
#[path = "exchange/tests.rs"]
mod tests;
