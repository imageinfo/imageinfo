//! Explicit exact-owned cleanup, independent of publication and admission.
//! Caller authority and actual terminal evidence cannot be decoded from records.

use super::Failure;
use super::custody::{ActionAuthority, CurrentBindings};
use super::runtime::{Artifact, Binding};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum Purpose {
    Source,
    ContainingParent,
    TransactionRoot,
    InstalledOutput,
    UnpublishedCandidate,
    Record(Artifact),
}
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum Disposition {
    Protected,
    RecoveryEvidence,
    Retained,
    Removed,
    RemovalRequested,
}
/// Exact expected identities remain visible even after a failed fresh check.
/// `verified` distinguishes current observations from expected residuals.
#[derive(Clone, Debug, PartialEq, Eq)]
pub(crate) struct Residual {
    pub purpose: Purpose,
    pub binding: Binding,
    pub disposition: Disposition,
    pub verified: bool,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum CleanupStatus {
    Removed,
    Pending,
    Partial,
    Refused,
}
#[derive(Debug)]
pub(crate) struct CleanupResult {
    pub status: CleanupStatus,
    pub failure: Option<Failure>,
    /// Actual prior terminal evidence is preserved; no new Committed claim.
    pub terminal_completion_preserved: bool,
    pub pending_cleanup: bool,
    pub residuals: Vec<Residual>,
}

/// An explicit per-record current retention decision, made independently by the
/// trusted caller only after all recovery obligations are resolved elsewhere.
/// Possession of records, an inspection or an optimistic UnitResult is insufficient.
pub(crate) struct UnneededRecords {
    kinds: Vec<Artifact>,
}
impl UnneededRecords {
    pub(crate) fn recovery_resolved(kinds: &[Artifact]) -> Result<Self, Failure> {
        if kinds.is_empty()
            || kinds.len() > 4
            || kinds
                .iter()
                .enumerate()
                .any(|(i, k)| *k == Artifact::Candidate || kinds[..i].contains(k))
        {
            return Err(Failure::InvalidBinding);
        }
        Ok(Self {
            kinds: kinds.to_vec(),
        })
    }
}

pub(crate) struct CleanupRequest {
    expected: CurrentBindings,
    authority: ActionAuthority,
    selected: Vec<Artifact>,
    completed: bool,
}
impl CleanupRequest {
    pub(crate) fn unpublished(
        expected: CurrentBindings,
        authority: ActionAuthority,
    ) -> Result<Self, Failure> {
        let (_, _, _, _, _, records, published) = expected.cleanup_parts();
        if published || records.len() > 2 {
            return Err(Failure::CallerHistory);
        }
        let selected = std::iter::once(Artifact::Candidate)
            .chain(records.iter().map(|(k, _)| *k))
            .collect();
        Ok(Self {
            expected,
            authority,
            selected,
            completed: false,
        })
    }
    pub(crate) fn completed(
        prior: super::finalization::PriorProof,
        authority: ActionAuthority,
        unneeded: UnneededRecords,
    ) -> Result<Self, Failure> {
        if !prior.terminal() {
            return Err(Failure::CallerHistory);
        }
        Self::terminal(prior.bindings().clone(), authority, unneeded)
    }
    #[cfg(windows)]
    pub(crate) fn finalized(
        context: super::finalization::CompletionContext,
        authority: ActionAuthority,
        unneeded: UnneededRecords,
    ) -> Result<Self, Failure> {
        if !context.complete() {
            return Err(Failure::CallerHistory);
        }
        Self::terminal(context.bindings().clone(), authority, unneeded)
    }
    fn terminal(
        expected: CurrentBindings,
        authority: ActionAuthority,
        unneeded: UnneededRecords,
    ) -> Result<Self, Failure> {
        let (_, _, _, _, _, records, published) = expected.cleanup_parts();
        if !published
            || records.len() != 4
            || unneeded
                .kinds
                .iter()
                .any(|kind| !records.iter().any(|(k, _)| k == kind))
        {
            return Err(Failure::CallerHistory);
        }
        Ok(Self {
            expected,
            authority,
            selected: unneeded.kinds,
            completed: true,
        })
    }
    fn residuals(&self) -> Vec<Residual> {
        let (_, _, _, _, parent, records, published) = self.expected.cleanup_parts();
        let mut out: Vec<_> = self
            .expected
            .object_bindings()
            .iter()
            .enumerate()
            .map(|(i, b)| Residual {
                purpose: match i {
                    0 => Purpose::Source,
                    1 => Purpose::TransactionRoot,
                    2 if published => Purpose::InstalledOutput,
                    2 => Purpose::UnpublishedCandidate,
                    _ => Purpose::Record(records[i - 3].0),
                },
                binding: b.clone(),
                disposition: if i < 2 || (i == 2 && published) {
                    Disposition::Protected
                } else if i > 2 && !self.selected.contains(&records[i - 3].0) {
                    Disposition::RecoveryEvidence
                } else {
                    Disposition::Retained
                },
                verified: false,
            })
            .collect();
        out.push(Residual {
            purpose: Purpose::ContainingParent,
            binding: parent.clone(),
            disposition: Disposition::Protected,
            verified: false,
        });
        out
    }
}

#[cfg(windows)]
mod native {
    use super::*;
    use crate::storage::custody::RestartAction;
    use crate::storage::inspection::native::{binding, directory_matches, snapshot_length};
    use crate::storage::{Cancellation, MAX_RECORD_BYTES};
    use imageinfo_windows_storage::{CleanupFile, ExistingRoot, GuardedSource, MAX_ARTIFACT_BYTES};
    use std::{ffi::OsString, io, path::Path};

    enum File {
        Delete(CleanupFile),
        Retain(GuardedSource),
    }
    impl File {
        fn check(&mut self) -> io::Result<()> {
            match self {
                Self::Delete(f) => f.check(),
                Self::Retain(f) => f.check(),
            }
        }
        fn binding(&mut self) -> Result<Binding, Failure> {
            match self {
                Self::Delete(f) => Ok(binding(f.snapshot(), Some(f.bytes()))),
                Self::Retain(f) => {
                    let bytes = f.read_exact_bytes().map_err(io_failure)?;
                    Ok(binding(f.snapshot(), Some(&bytes)))
                }
            }
        }
    }
    fn io_failure(error: io::Error) -> Failure {
        if matches!(
            error.kind(),
            io::ErrorKind::NotFound | io::ErrorKind::Unsupported
        ) {
            Failure::Conflict
        } else {
            Failure::BackendIo
        }
    }
    struct Held {
        source: GuardedSource,
        root: ExistingRoot,
        files: Vec<Option<File>>,
        names: Vec<OsString>,
        fresh: CurrentBindings,
    }
    impl Held {
        fn open(source: &Path, root: &Path, request: &CleanupRequest) -> Result<Self, Failure> {
            let (operation, profile, implementation, output, parent, records, published) =
                request.expected.cleanup_parts();
            imageinfo_windows_storage::validate_leaf(output).map_err(io_failure)?;
            let root_path = root;
            let root = ExistingRoot::open(root).map_err(io_failure)?;
            let mut names = vec![OsString::from(if published {
                output
            } else {
                Artifact::Candidate.leaf()
            })];
            names.extend(records.iter().map(|(kind, _)| OsString::from(kind.leaf())));
            names.sort();
            if root.entries().map_err(io_failure)? != names {
                return Err(Failure::Conflict);
            }
            let mut source = GuardedSource::open(source, MAX_ARTIFACT_BYTES).map_err(io_failure)?;
            let bytes = source.read_exact_bytes().map_err(io_failure)?;
            let mut bindings = vec![binding(source.snapshot(), Some(&bytes))];
            let old_root = &request.expected.object_bindings()[1];
            let end = snapshot_length(&old_root.facts).map_err(|_| Failure::InvalidBinding)?;
            directory_matches(root.snapshot(), &old_root.facts[..end])
                .map_err(|_| Failure::Conflict)?;
            let old_parent = old_root.facts[end..]
                .strip_prefix(b"held-containing-parent-v1\0")
                .ok_or(Failure::InvalidBinding)?;
            if old_parent != parent.facts {
                return Err(Failure::InvalidBinding);
            }
            directory_matches(root.parent_snapshot(), old_parent).map_err(|_| Failure::Conflict)?;
            let mut root_binding = binding(root.snapshot(), None);
            root_binding.facts = old_root.facts.clone();
            bindings.push(root_binding);
            let mut files = Vec::new();
            for kind in std::iter::once(Artifact::Candidate).chain(records.iter().map(|(k, _)| *k))
            {
                let leaf = if kind == Artifact::Candidate && published {
                    output
                } else {
                    kind.leaf()
                };
                let path = root_path.join(leaf);
                let limit = if kind == Artifact::Candidate {
                    MAX_ARTIFACT_BYTES
                } else {
                    MAX_RECORD_BYTES
                };
                let mut file = if request.selected.contains(&kind) {
                    File::Delete(CleanupFile::open(&path, limit).map_err(io_failure)?)
                } else {
                    File::Retain(GuardedSource::open(&path, limit).map_err(io_failure)?)
                };
                let current = file.binding()?;
                let snapshot = match &file {
                    File::Delete(f) => f.snapshot(),
                    File::Retain(f) => f.snapshot(),
                };
                if snapshot.owner_dacl != root.snapshot().owner_dacl {
                    return Err(Failure::Conflict);
                }
                bindings.push(current);
                files.push(Some(file));
            }
            let fresh = CurrentBindings::capture(
                operation,
                profile,
                implementation,
                output,
                parent,
                &bindings,
                records,
                published,
            )
            .map_err(|_| Failure::RecordTooLarge)?;
            request
                .expected
                .compare(&fresh)
                .map_err(|_| Failure::CallerHistory)?;
            let mut result = Self {
                source,
                root,
                files,
                names,
                fresh,
            };
            result.check()?;
            Ok(result)
        }
        fn check(&mut self) -> Result<(), Failure> {
            self.source.check().map_err(io_failure)?;
            self.root.check().map_err(io_failure)?;
            for file in self.files.iter_mut().flatten() {
                file.check().map_err(io_failure)?;
            }
            if self.root.entries().map_err(io_failure)? != self.names {
                return Err(Failure::Conflict);
            }
            Ok(())
        }
    }

    pub(crate) fn cleanup(
        source: &Path,
        root: &Path,
        request: CleanupRequest,
        cancel: &Cancellation,
    ) -> CleanupResult {
        run(source, root, request, cancel, |_, _| Ok(()))
    }
    fn run(
        source: &Path,
        root: &Path,
        request: CleanupRequest,
        cancel: &Cancellation,
        mut before: impl FnMut(usize, &CleanupRequest) -> Result<(), Failure>,
    ) -> CleanupResult {
        let mut residuals = request.residuals();
        let mut effects = 0;
        let mut deferred = false;
        let action = if request.completed {
            RestartAction::CleanupCompleted
        } else {
            RestartAction::PruneUnpublished
        };
        let result = (|| {
            // Validate authorization before opening any deletion-capable handle.
            request
                .authority
                .check(action, &request.expected)
                .map_err(|_| Failure::CallerHistory)?;
            let mut held = Held::open(source, root, &request)?;
            for residual in &mut residuals {
                residual.verified = true;
            }
            let (_, _, _, output, _, records, published) = request.expected.cleanup_parts();
            let kinds: Vec<_> = std::iter::once(Artifact::Candidate)
                .chain(records.iter().map(|(k, _)| *k))
                .collect();
            for (index, kind) in kinds.iter().enumerate() {
                if !request.selected.contains(kind) {
                    continue;
                }
                if cancel.is_requested() {
                    return Err(Failure::Cancelled);
                }
                before(effects, &request)?;
                request
                    .authority
                    .check(action, &held.fresh)
                    .map_err(|_| Failure::CallerHistory)?;
                held.check()?;
                let file = held.files[index].take().ok_or(Failure::InvalidBinding)?;
                let File::Delete(file) = file else {
                    return Err(Failure::InvalidBinding);
                };
                // Once issued, uncertainty cannot be erased by reapplying an edit.
                match file.remove() {
                    Ok(()) => {
                        effects += 1;
                        residuals[index + 2].disposition = Disposition::RemovalRequested;
                    }
                    Err(error) => {
                        if error.disposition_attempted {
                            effects += 1;
                            residuals[index + 2].disposition = Disposition::RemovalRequested;
                        }
                        return Err(io_failure(error.error));
                    }
                }
                let leaf = OsString::from(if *kind == Artifact::Candidate && published {
                    output
                } else {
                    kind.leaf()
                });
                let current = held.root.entries().map_err(io_failure)?;
                if !current.contains(&leaf) {
                    held.names.retain(|name| name != &leaf);
                    residuals[index + 2].disposition = Disposition::Removed;
                } else {
                    // Compatible readers can keep a delete-pending name alive.
                    // A new foreign occupant is also possible after our handle
                    // closes. Do not claim its identity or act on that name.
                    residuals[index + 2].verified = false;
                    // Stop: no checks of a removed handle or optimistic retry.
                    deferred = true;
                }
                if current != held.names {
                    return Err(Failure::Conflict);
                }
                if deferred {
                    break;
                }
                held.check()?;
            }
            Ok(())
        })();
        let failure = result.err();
        if failure.is_some() {
            for residual in &mut residuals {
                if residual.disposition != Disposition::Removed {
                    residual.verified = false;
                }
            }
        }
        // All selected objects must be actually observed absent for Removed.
        let pending = residuals.iter().any(|r| {
            matches!(
                r.disposition,
                Disposition::Retained | Disposition::RemovalRequested
            )
        });
        CleanupResult {
            status: if effects == 0 && failure.is_some() {
                CleanupStatus::Refused
            } else if failure.is_some() {
                CleanupStatus::Partial
            } else if deferred || pending {
                CleanupStatus::Pending
            } else {
                CleanupStatus::Removed
            },
            failure,
            terminal_completion_preserved: request.completed,
            pending_cleanup: pending,
            residuals,
        }
    }
    #[cfg(test)]
    mod tests;
}
#[cfg(windows)]
#[allow(unused_imports)]
pub(crate) use native::cleanup;
