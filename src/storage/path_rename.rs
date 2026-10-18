//! Disabled single-marker same-parent rename planning. Every move is no-replace;
//! a temporary name still contains the original and is never cleanup material.

use std::path::{Path, PathBuf};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum PlanError {
    UnsupportedName,
    DifferentParent,
    Unchanged,
    TemporaryRequired,
    UnexpectedTemporary,
    TemporaryAlias,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub(crate) struct RenamePlan {
    source: PathBuf,
    destination: PathBuf,
    temporary: Option<PathBuf>,
}

fn leaf(path: &Path) -> Result<&str, PlanError> {
    let name = path
        .file_name()
        .and_then(|s| s.to_str())
        .ok_or(PlanError::UnsupportedName)?;
    // This finite marker subset matches the native session's component policy.
    // Native admission still checks actual directory comparison and aliases.
    if name.is_empty()
        || name.len() > 100
        || !name.is_ascii()
        || name.bytes().any(|c| c < 32 || b"<>:\"/\\|?*".contains(&c))
        || name.ends_with(['.', ' '])
        || name == "."
        || name == ".."
    {
        return Err(PlanError::UnsupportedName);
    }
    let stem = name.split('.').next().unwrap_or("").to_ascii_uppercase();
    if matches!(stem.as_str(), "CON" | "PRN" | "AUX" | "NUL")
        || (stem.len() == 4
            && (stem.starts_with("COM") || stem.starts_with("LPT"))
            && matches!(stem.as_bytes()[3], b'1'..=b'9'))
    {
        return Err(PlanError::UnsupportedName);
    }
    Ok(name)
}

impl RenamePlan {
    /// A case-only preview must name the exact fresh temporary component. This
    /// classifies the bounded ASCII request; it does not admit a filesystem.
    pub(crate) fn new(
        source: &Path,
        destination: &Path,
        temporary: Option<&Path>,
    ) -> Result<Self, PlanError> {
        let old = leaf(source)?;
        let new = leaf(destination)?;
        let parent = source
            .parent()
            .filter(|p| !p.as_os_str().is_empty())
            .ok_or(PlanError::DifferentParent)?;
        if destination.parent() != Some(parent) {
            return Err(PlanError::DifferentParent);
        }
        if old == new {
            return Err(PlanError::Unchanged);
        }
        let case_only = old.eq_ignore_ascii_case(new);
        match (case_only, temporary) {
            (true, None) => return Err(PlanError::TemporaryRequired),
            (false, Some(_)) => return Err(PlanError::UnexpectedTemporary),
            (_, Some(temp)) => {
                let temp_leaf = leaf(temp)?;
                if temp.parent() != Some(parent) {
                    return Err(PlanError::DifferentParent);
                }
                if temp_leaf.eq_ignore_ascii_case(old) || temp_leaf.eq_ignore_ascii_case(new) {
                    return Err(PlanError::TemporaryAlias);
                }
            }
            _ => {}
        }
        Ok(Self {
            source: source.into(),
            destination: destination.into(),
            temporary: temporary.map(Into::into),
        })
    }

    pub(crate) fn source(&self) -> &Path {
        &self.source
    }
    pub(crate) fn destination(&self) -> &Path {
        &self.destination
    }
    pub(crate) fn temporary(&self) -> Option<&Path> {
        self.temporary.as_deref()
    }
    pub(crate) fn steps(&self) -> Vec<&Path> {
        self.temporary
            .iter()
            .map(PathBuf::as_path)
            .chain(std::iter::once(self.destination.as_path()))
            .collect()
    }
}

#[cfg(windows)]
mod native {
    use super::*;
    use imageinfo_windows_storage::{
        ExistingMoveBinding as Binding, ExistingMoveOutcome as Outcome, FileSnapshot,
        HeldExistingMoveSession,
    };
    use std::io;

    #[derive(Clone, Copy, Debug, PartialEq, Eq)]
    pub(crate) enum RenameState {
        Ready,
        AtTemporary,
        Finished,
        Stopped,
        RecoveryRequired,
    }

    #[derive(Clone, Copy, Debug, PartialEq, Eq)]
    pub(crate) enum StopReason {
        Cancelled,
        CheckpointFailed,
        NameMapChanged,
        MoveNotAttempted,
        MoveNoEffect,
        UnknownResult,
    }

    /// Every row is in preview order: source, optional temporary, destination.
    /// Unknown observations stay unknown; a retained original is never deleted.
    #[derive(Clone, Debug, PartialEq, Eq)]
    pub(crate) struct RenameObservation {
        pub state: RenameState,
        pub completed_steps: usize,
        pub reason: Option<StopReason>,
        pub names: Vec<(PathBuf, Option<Binding>)>,
    }

    pub(crate) struct PreparedRename {
        plan: RenamePlan,
        held: HeldExistingMoveSession,
        state: RenameState,
        completed_steps: usize,
        reason: Option<StopReason>,
        #[cfg(test)]
        lose_next_response: bool,
    }

    impl PreparedRename {
        /// The SDK resolves the actual parent comparison mode, lineage, exact
        /// spelling, identity, default stream and admitted property/stream set.
        pub(crate) fn open(plan: RenamePlan, expected: &FileSnapshot) -> io::Result<Self> {
            let names = std::iter::once(plan.source.clone())
                .chain(plan.steps().into_iter().map(Path::to_path_buf))
                .collect::<Vec<_>>();
            let held = HeldExistingMoveSession::open(plan.source(), expected, &names)?;
            let mut result = Self {
                plan,
                held,
                state: RenameState::Ready,
                completed_steps: 0,
                reason: None,
                #[cfg(test)]
                lose_next_response: false,
            };
            if !result.expected_map() || result.held.check().is_err() {
                return Err(io::Error::other("RENAME_INITIAL_MAP_OR_PROPERTIES"));
            }
            Ok(result)
        }

        fn paths(&self) -> Vec<&Path> {
            std::iter::once(self.plan.source())
                .chain(self.plan.steps())
                .collect()
        }

        fn expected_map(&self) -> bool {
            let current = if self.completed_steps == 0 {
                self.plan.source()
            } else {
                self.plan.steps()[self.completed_steps - 1]
            };
            self.paths().into_iter().all(|path| {
                let expected = if path == current {
                    Binding::HeldObject
                } else if leaf(path)
                    .ok()
                    .zip(leaf(current).ok())
                    .is_some_and(|(a, b)| a.eq_ignore_ascii_case(b))
                {
                    Binding::CaseAlias
                } else {
                    Binding::Absent
                };
                self.held.binding(path).ok() == Some(expected)
            })
        }

        pub(crate) fn observe(&self) -> RenameObservation {
            RenameObservation {
                state: self.state,
                completed_steps: self.completed_steps,
                reason: self.reason,
                names: self
                    .paths()
                    .into_iter()
                    .map(|p| (p.into(), self.held.binding(p).ok()))
                    .collect(),
            }
        }

        /// Issue at most one step, allowing the caller to stop between the two
        /// case-only calls. Cancellation is terminal and performs no cleanup.
        pub(crate) fn advance(&mut self, cancelled: bool) -> RenameObservation {
            if !matches!(self.state, RenameState::Ready | RenameState::AtTemporary) {
                return self.observe();
            }
            let refusal = if cancelled {
                Some(StopReason::Cancelled)
            } else if self.held.check().is_err() {
                Some(StopReason::CheckpointFailed)
            } else if !self.expected_map() {
                Some(StopReason::NameMapChanged)
            } else {
                None
            };
            if let Some(reason) = refusal {
                self.state = RenameState::Stopped;
                self.reason = Some(reason);
                return self.observe();
            }
            let target = self.plan.steps()[self.completed_steps].to_path_buf();
            let outcome = self.held.move_to(&target, false);
            // Exercise loss at the SDK/planner boundary: the retained native
            // session has issued the call, but this planner has not consumed its
            // outcome or advanced its acknowledged prefix. This is a test-only
            // lost response, not evidence of an ambiguous Windows API return.
            #[cfg(test)]
            let outcome = if std::mem::take(&mut self.lose_next_response) {
                self.held.mark_uncertain();
                Outcome::RecoveryRequired
            } else {
                outcome
            };
            match outcome {
                Outcome::ObservedMoved => {
                    self.completed_steps += 1;
                    self.state = if self.completed_steps == self.plan.steps().len() {
                        RenameState::Finished
                    } else {
                        RenameState::AtTemporary
                    };
                    if !self.expected_map() {
                        self.state = RenameState::RecoveryRequired;
                        self.reason = Some(StopReason::NameMapChanged);
                    } else if self.held.check().is_err() {
                        self.state = RenameState::RecoveryRequired;
                        self.reason = Some(StopReason::CheckpointFailed);
                    }
                }
                Outcome::RecoveryRequired => {
                    self.state = RenameState::RecoveryRequired;
                    self.reason = Some(StopReason::UnknownResult);
                }
                Outcome::NotAttempted => {
                    self.state = RenameState::Stopped;
                    self.reason = Some(StopReason::MoveNotAttempted);
                }
                Outcome::ObservedNoEffect => {
                    self.state = RenameState::Stopped;
                    self.reason = Some(StopReason::MoveNoEffect);
                }
            }
            self.observe()
        }

        /// A lost response never authorizes a second move or automatic repair.
        /// The fresh map is reported separately from the unknown call history.
        pub(crate) fn mark_uncertain(&mut self) -> RenameObservation {
            self.held.mark_uncertain();
            self.state = RenameState::RecoveryRequired;
            self.reason = Some(StopReason::UnknownResult);
            self.observe()
        }

        #[cfg(test)]
        pub(crate) fn lose_next_response(&mut self) {
            self.lose_next_response = true;
        }

        pub(crate) fn snapshot(&self) -> &FileSnapshot {
            self.held.snapshot()
        }
    }
}

#[cfg(windows)]
#[allow(unused_imports)] // Disabled callers consume these types in later adapters.
pub(crate) use native::{PreparedRename, RenameObservation, RenameState, StopReason};

#[cfg(test)]
#[path = "path_rename/tests.rs"]
mod tests;

#[cfg(all(test, windows))]
#[path = "path_rename/native_tests.rs"]
mod native_tests;
