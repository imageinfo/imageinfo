//! Deferred new-name sidecar preparation. This is neither apply nor admission.
use super::{Intent, Kind, Limits, Prepared};
use crate::storage::admission::{AdmittedByteSink, ProfileRequest, Unsupported};
use crate::storage::new_output::{
    self, NewOutputBuilder, NewOutputIntent, PreparationRefusal, PreparedNewOutput,
};
use crate::storage::resources::RetainedSession;
use crate::storage::{Cancellation, Failure, Phase, Status, UnitResult};
use std::path::{Component, Path};

/// Live borrowed selections only; no serialized plan or imported receipt enters
/// this interface. Creating the request does not open either selected source.
pub(super) struct Operation<'a> {
    pub profile: ProfileRequest<'a>,
    pub raw: &'a Path,
    pub sidecar: &'a Path,
    pub transaction_root: &'a Path,
    pub output_leaf: &'a str,
    pub operation: &'a str,
    pub create_new: bool,
    pub intent: Intent<'a>,
    pub limits: Limits,
}

/// Holds never escape to a public transport or executor. Even the changed hold
/// lacks independent derivative admission and cannot authorize publication.
// Keep this single-operation, move-only guard bundle inline. Boxing only the
// larger variant would add an unnecessary allocation outside retained resource
// accounting; the bounded stack footprint is preferable at this inert boundary.
#[allow(clippy::large_enum_variant)]
pub(super) enum CandidatePreparation {
    NoOp(UnitResult),
    AwaitingDerivativeAdmission(Prepared),
}

// The enclosing result deliberately retains the same inline guard ownership as
// CandidatePreparation, without allocating merely to compact its refusal case.
#[allow(clippy::large_enum_variant)]
pub(super) enum Preparation {
    AwaitingIntegration(PreparedNewOutput<CandidatePreparation>),
    Stopped {
        result: UnitResult,
        unsupported: Option<Unsupported>,
    },
}

struct Deferred<'a> {
    operation: Operation<'a>,
}

fn valid_intent(operation: &Operation<'_>) -> bool {
    let mut components = Path::new(operation.output_leaf).components();
    operation.create_new
        && !operation.operation.is_empty()
        && matches!(components.next(), Some(Component::Normal(_)))
        && components.next().is_none()
        // Fail closed on Windows alternate streams, separators and ambiguous
        // trailing spelling, even before any future sink checks actual names.
        && !operation.output_leaf.contains([':', '/', '\\'])
        && !operation.output_leaf.ends_with(['.', ' '])
        && !operation.raw.file_name().is_some_and(|name| name.to_string_lossy().eq_ignore_ascii_case(operation.output_leaf))
        && !operation.sidecar.file_name().is_some_and(|name| name.to_string_lossy().eq_ignore_ascii_case(operation.output_leaf))
}

impl NewOutputBuilder for Deferred<'_> {
    type Prepared = CandidatePreparation;

    fn construct(
        self,
        _admission: &AdmittedByteSink,
        _intent: NewOutputIntent<'_>,
        _owner: &mut RetainedSession,
        cancel: &Cancellation,
    ) -> Result<Self::Prepared, Failure> {
        #[cfg(test)]
        tests::CONSTRUCTIONS.with(|count| count.set(count.get() + 1));
        if cancel.is_requested() {
            return Err(Failure::Cancelled);
        }
        if !valid_intent(&self.operation) {
            return Err(Failure::InvalidBinding);
        }
        let candidate = super::prepare(
            self.operation.raw,
            self.operation.sidecar,
            &[self.operation.intent],
            self.operation.limits,
        )
        .map_err(|_| Failure::InvalidBinding)?;
        if cancel.is_requested() {
            return Err(Failure::Cancelled);
        }
        // This is the post-storage-admission no-op boundary. Candidate reads and
        // guards have occurred, but no backend/transaction/output was created,
        // no logical construction charged and no serializer invoked.
        Ok(match candidate.kind() {
            Kind::NoOp => CandidatePreparation::NoOp(no_effects(None)),
            Kind::Derivative => CandidatePreparation::AwaitingDerivativeAdmission(candidate),
        })
    }
}

/// Only pre-effect failures may use this mapping; it cannot summarize an actual
/// sink failure after construction or publication. Retained session charges are
/// deliberately not returned as this operation's newly charged bytes.
fn no_effects(failure: Option<Failure>) -> UnitResult {
    let status = match failure {
        None => Status::Unchanged,
        Some(Failure::Cancelled) => Status::CancelledBeforePublish,
        Some(Failure::Conflict) => Status::Conflict,
        Some(Failure::Unsupported | Failure::InvalidBinding | Failure::CallerHistory) => {
            Status::Refused
        }
        Some(_) => Status::FailedBeforePublish,
    };
    UnitResult {
        status,
        phase: Phase::Preflight,
        failure,
        publication_possible: false,
        release_possible: false,
        retained_material: false,
        pending_cleanup: false,
        charged_bytes: 0,
        protocol_complete: false,
    }
}

/// The real selector is first, including ahead of intent validation, source
/// opens, candidate parsing, cancellation and collision probing. It currently
/// always refuses. No qualification runtime or substituted selector is used.
pub(super) fn prepare(
    operation: Operation<'_>,
    owner: &mut RetainedSession,
    cancel: &Cancellation,
) -> Preparation {
    let intent = NewOutputIntent {
        profile: operation.profile,
        source: operation.sidecar,
        transaction_root: operation.transaction_root,
        output_leaf: operation.output_leaf,
        operation: operation.operation,
        format_revision: "sidecar-date-deferred-v1",
        // Upper bound only: no candidate has been constructed before selection.
        planned_len: operation.limits.sidecar_bytes,
        max_len: operation.limits.sidecar_bytes,
    };
    match new_output::prepare(intent, owner, cancel, Deferred { operation }) {
        Ok(prepared) => Preparation::AwaitingIntegration(prepared),
        Err(PreparationRefusal::Unsupported(reason)) => Preparation::Stopped {
            result: no_effects(Some(Failure::Unsupported)),
            unsupported: Some(reason),
        },
        Err(PreparationRefusal::Construction(failure)) => Preparation::Stopped {
            result: no_effects(Some(failure)),
            unsupported: None,
        },
    }
}

#[cfg(test)]
mod tests;
