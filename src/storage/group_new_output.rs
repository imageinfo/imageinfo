//! Internal expected-absent two-new-output adapter preparation. The surviving
//! in-process owner retains each native backend, original unit and charged ledger;
//! the group Run retains only a move-only stage marker. No receipt qualification,
//! imported authority, automatic restart or production selector is provided.

use super::group::{
    Execution, ManifestFailure, PreparationFailure, Refusal, UnitAdapter, UnitIntent,
};
use super::runtime::{self, Artifact, Backend, Binding, Preparation, ValidatedCandidate};
use super::windows::{GROUP_MANIFEST_LEAF, WindowsBackend};
use super::{Cancellation, Failure, LogicalBudget, Phase, Status, UnitResult};
use imageinfo_windows_storage::{MAX_ARTIFACT_BYTES, validate_leaf};
use std::{cell::Cell, rc::Rc};

struct CurrentOwner {
    active: Cell<bool>,
}

/// Current in-process permission for this exact owner, never profile admission.
/// Neither this capability nor the Run/staged state is Clone or deserializable.
pub(crate) struct ExecuteAuthority(Rc<CurrentOwner>);

impl ExecuteAuthority {
    pub(crate) fn revoke(&self) {
        self.0.active.set(false);
    }
}

/// Only this adapter can construct a marker. The actual prepared backend stays
/// with its surviving owner even when a stage fails, is cancelled or is unattempted.
pub(crate) struct Staged {
    owner: Rc<CurrentOwner>,
    artifacts: Vec<Binding>,
}

pub(crate) struct WindowsUnit<'a> {
    frozen: UnitIntent<'a>,
    original: &'a [u8],
    request: Option<ValidatedCandidate<'a>>,
    backend: Option<WindowsBackend>,
    preparation: Option<Preparation<WindowsBackend>>,
    // The exact helper supplied by the group survives preparation/continuation.
    // The cumulative external owner already retains the full group charge.
    ledger: Option<LogicalBudget>,
    owner: Rc<CurrentOwner>,
    result: Option<UnitResult>,
    stage_used: bool,
}

impl<'a> WindowsUnit<'a> {
    /// Captures borrowed, immutable original inputs without native constructors.
    /// Both group preflights run before guard acquisition or candidate staging.
    pub(crate) fn new(
        backend: WindowsBackend,
        frozen: UnitIntent<'a>,
        original: &'a [u8],
        request: ValidatedCandidate<'a>,
    ) -> (Self, ExecuteAuthority) {
        let owner = Rc::new(CurrentOwner {
            active: Cell::new(true),
        });
        let authority = ExecuteAuthority(owner.clone());
        (
            Self {
                frozen,
                original,
                request: Some(request),
                backend: Some(backend),
                preparation: None,
                ledger: None,
                owner,
                result: None,
                stage_used: false,
            },
            authority,
        )
    }

    pub(crate) fn result(&self) -> Option<&UnitResult> {
        self.result.as_ref()
    }

    pub(crate) fn retained_artifacts(&self) -> Vec<Binding> {
        self.backend_ref().retained_bindings()
    }

    fn backend_ref(&self) -> &WindowsBackend {
        if let Some(preparation) = &self.preparation {
            preparation.backend()
        } else {
            self.backend
                .as_ref()
                .expect("native backend always retained")
        }
    }

    fn backend_mut(&mut self) -> &mut WindowsBackend {
        if let Some(preparation) = &mut self.preparation {
            preparation.backend_mut()
        } else {
            self.backend
                .as_mut()
                .expect("native backend always retained")
        }
    }

    fn same_input(&self, unit: UnitIntent<'_>, original: &[u8]) -> bool {
        let frozen = self.frozen;
        original == self.original
            && unit.identity == frozen.identity
            && unit.operation == frozen.operation
            && unit.revision == frozen.revision
            && unit.profile == frozen.profile
            && unit.implementation == frozen.implementation
            && unit.source == frozen.source
            && unit.parent == frozen.parent
            && unit.target == frozen.target
            && unit.output == frozen.output
            && unit.candidate_len == frozen.candidate_len
    }

    fn current(&self, authority: &ExecuteAuthority) -> bool {
        Rc::ptr_eq(&self.owner, &authority.0) && self.owner.active.get()
    }

    fn refuse_execution(&mut self, error: Failure) -> Execution {
        let mut result = self.result.clone().unwrap_or(UnitResult {
            status: Status::Refused,
            phase: Phase::Preflight,
            failure: None,
            publication_possible: false,
            release_possible: false,
            retained_material: false,
            pending_cleanup: false,
            charged_bytes: 0,
            protocol_complete: false,
        });
        result.failure = Some(error);
        result.protocol_complete = false;
        result.status = if result.publication_possible {
            Status::RecoveryRequired
        } else if error == Failure::Cancelled {
            Status::CancelledBeforePublish
        } else {
            Status::Refused
        };
        let artifacts = self.retained_artifacts();
        self.result = Some(result.clone());
        Execution {
            result,
            receipt: None,
            artifacts,
        }
    }
}

impl UnitAdapter for WindowsUnit<'_> {
    type ExecuteAuthority = ExecuteAuthority;
    type Staged = Staged;

    fn preflight(
        &mut self,
        unit: UnitIntent<'_>,
        original: &[u8],
        authority: &ExecuteAuthority,
    ) -> Result<(), Refusal> {
        if !self.current(authority) {
            return Err(Refusal::MissingAuthority);
        }
        if !self.same_input(unit, original)
            || unit.target.is_some()
            || unit.profile != self.backend_ref().profile()
            || unit.implementation != self.backend_ref().implementation()
        {
            return Err(Refusal::InvalidIntent);
        }
        validate_leaf(unit.output).map_err(|_| Refusal::Unit(Failure::Unsupported))?;
        if unit.output.eq_ignore_ascii_case(GROUP_MANIFEST_LEAF)
            || [
                Artifact::Candidate,
                Artifact::Prepared,
                Artifact::Intent,
                Artifact::Observation,
                Artifact::Receipt,
            ]
            .iter()
            .any(|kind| kind.leaf().eq_ignore_ascii_case(unit.output))
        {
            return Err(Refusal::InvalidIntent);
        }
        if let Some(request) = &self.request
            && (request.operation != unit.operation
                || request.format_revision != unit.revision
                || request.output.0 != unit.output
                || request.planned_len != unit.candidate_len
                || request.planned_len > request.max_len
                || request.planned_len > MAX_ARTIFACT_BYTES)
        {
            return Err(Refusal::InvalidIntent);
        }
        Ok(())
    }

    fn acquire_guard(&mut self, binding: &Binding) -> Result<(), Refusal> {
        let frozen = self.frozen;
        self.backend_mut()
            .acquire_group_guard(binding, frozen.source, frozen.parent)?;
        Ok(())
    }

    fn stage(
        &mut self,
        unit: UnitIntent<'_>,
        original: &[u8],
        budget: LogicalBudget,
        cancel: &Cancellation,
    ) -> Result<Staged, PreparationFailure> {
        if !self.same_input(unit, original) || self.stage_used || !self.owner.active.get() {
            return Err(PreparationFailure {
                refusal: Refusal::InvalidIntent,
                artifacts: self.retained_artifacts(),
            });
        }
        self.stage_used = true;
        self.ledger = Some(budget);
        let preparation = runtime::prepare(
            self.backend.take().expect("first stage owns backend"),
            self.request
                .take()
                .expect("first stage owns original request"),
            self.ledger.as_mut().unwrap(),
            cancel,
        );
        let result = preparation.result();
        let ready = preparation.ready();
        let artifacts = preparation.backend().retained_bindings();
        self.preparation = Some(preparation);
        self.result = Some(result.clone());
        if !ready {
            return Err(PreparationFailure {
                refusal: result.failure.unwrap_or(Failure::Ambiguous).into(),
                artifacts,
            });
        }
        Ok(Staged {
            owner: self.owner.clone(),
            artifacts,
        })
    }

    fn staged_artifacts(staged: &Staged) -> &[Binding] {
        &staged.artifacts
    }

    fn retain_manifest(&mut self, bytes: &[u8]) -> Result<Binding, ManifestFailure> {
        if !self.preparation.as_ref().is_some_and(Preparation::ready) {
            return Err(ManifestFailure {
                refusal: Refusal::InvalidIntent,
                retained: None,
            });
        }
        self.backend_mut()
            .retain_group_manifest(bytes)
            .map_err(|error| ManifestFailure {
                refusal: error.into(),
                retained: self.backend_ref().group_manifest_binding().cloned(),
            })
    }

    fn check_manifest(&mut self, binding: &Binding, bytes: &[u8]) -> Result<(), Refusal> {
        self.backend_mut().check_group_manifest(binding, bytes)?;
        Ok(())
    }

    fn execute(
        &mut self,
        staged: Staged,
        unit: UnitIntent<'_>,
        original: &[u8],
        authority: ExecuteAuthority,
        cancel: &Cancellation,
    ) -> Execution {
        if !self.same_input(unit, original)
            || !self.current(&authority)
            || !Rc::ptr_eq(&self.owner, &staged.owner)
            || !self.preparation.as_ref().is_some_and(Preparation::ready)
            || staged.artifacts != self.retained_artifacts()
        {
            return self.refuse_execution(Failure::CallerHistory);
        }
        self.owner.active.set(false);
        let completion = runtime::continue_prepared(self.preparation.take().unwrap(), cancel);
        let (backend, result) = completion.into_parts();
        let artifacts = backend.retained_bindings();
        self.backend = Some(backend);
        self.result = Some(result.clone());
        // This adapter is unqualified. Receipt verification/finalization retain
        // the trait's unavailable defaults; never manufacture QualifiedReceipt.
        Execution {
            result,
            receipt: None,
            artifacts,
        }
    }
}

#[cfg(test)]
mod tests;
