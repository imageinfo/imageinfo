//! Strict existing-target replacement admission. No existing-target profile is
//! qualified. This boundary refuses before opening either path or creating any
//! recovery/staging artifact; a property snapshot cannot supply missing exclusion.
//!
//! OD-11's new-output checkpoints and the same-object no-replace move are not
//! replacement mechanisms. There is deliberately no prepared operation or execute
//! method. Adding one requires a separately reviewed positive mechanism.

use std::{error::Error, fmt, path::PathBuf};

/// Requested last-write semantics; neither choice relaxes original recovery.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ModificationTimePolicy {
    /// A genuine content edit would receive its actual modification time.
    UpdateForContentEdit,
    /// An explicit request would preserve the original last-write time.
    PreserveOriginal,
}

/// Owned request data, not object identity, a guard, or replacement authority.
/// Fields are deliberately private so callers use the refusal boundary rather
/// than mistaking this request for a prepared operation.
#[derive(Debug)]
pub struct ExistingTargetRequest {
    candidate: PathBuf,
    target: PathBuf,
    modification_time: ModificationTimePolicy,
}

impl ExistingTargetRequest {
    pub fn new(
        candidate: PathBuf,
        target: PathBuf,
        modification_time: ModificationTimePolicy,
    ) -> Self {
        Self {
            candidate,
            target,
            modification_time,
        }
    }

    /// Consume the owned request and return the exact unsupported disposition.
    /// No path lookup, handle acquisition, copy, setter, rename, privilege change,
    /// cleanup, publication attempt, or recovery action occurs. Inputs never
    /// select a weaker profile, including for paths that do not exist.
    #[must_use]
    pub fn refuse_unsupported(self) -> ExistingTargetRefusal {
        let Self {
            candidate,
            target,
            modification_time,
        } = self;
        // Retain no paths in the public error: they may contain private data.
        drop((candidate, target));
        ExistingTargetRefusal { modification_time }
    }
}

/// Missing independent strict-contract premises. These are not claims that a
/// particular file's properties were inspected, excluded, or recovered.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum UnqualifiedRequirement {
    ExpectedOriginalReplacement,
    ContinuousPropertyAndAliasExclusion,
    CompleteRequiredOriginalRecovery,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ExistingTargetRefusal {
    modification_time: ModificationTimePolicy,
}

impl ExistingTargetRefusal {
    pub const CODE: &'static str = "EXISTING_TARGET_STRICT_PROPERTIES_UNSUPPORTED";

    pub const fn requirements(self) -> [UnqualifiedRequirement; 3] {
        [
            UnqualifiedRequirement::ExpectedOriginalReplacement,
            UnqualifiedRequirement::ContinuousPropertyAndAliasExclusion,
            UnqualifiedRequirement::CompleteRequiredOriginalRecovery,
        ]
    }

    pub const fn modification_time(self) -> ModificationTimePolicy {
        self.modification_time
    }
}

impl fmt::Display for ExistingTargetRefusal {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(Self::CODE)
    }
}
impl Error for ExistingTargetRefusal {}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn owned_boundary_has_one_refusal_for_both_time_policies_and_all_paths() {
        for modification_time in [
            ModificationTimePolicy::UpdateForContentEdit,
            ModificationTimePolicy::PreserveOriginal,
        ] {
            for target in ["", "target", "missing-parent/target", "target:stream"] {
                let refusal = ExistingTargetRequest::new(
                    PathBuf::from("candidate"),
                    PathBuf::from(target),
                    modification_time,
                )
                .refuse_unsupported();
                assert_eq!(refusal.to_string(), ExistingTargetRefusal::CODE);
                assert_eq!(refusal.modification_time(), modification_time);
                assert_eq!(
                    refusal.requirements(),
                    [
                        UnqualifiedRequirement::ExpectedOriginalReplacement,
                        UnqualifiedRequirement::ContinuousPropertyAndAliasExclusion,
                        UnqualifiedRequirement::CompleteRequiredOriginalRecovery,
                    ]
                );
                assert!(!refusal.to_string().contains(target) || target.is_empty());
            }
        }
    }
}
