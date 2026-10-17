//! Intended production new-output caller boundary, distinct from unqualified
//! protocol qualification. Admission precedes deferred format/backend/candidate
//! construction and accounting. No positive executor is enabled here.

use std::path::Path;

use super::admission::{AdmittedByteSink, ProfileRequest, Unsupported, select_profile};
use super::resources::RetainedSession;
use super::{Cancellation, Failure};

/// Borrowed intended operation, not imported apply or format authority. Paths
/// are not opened or inspected at this boundary. The deferred format builder
/// must validate its own source/candidate and explicit caller authority; matching
/// storage labels cannot establish either.
#[derive(Clone, Copy, Debug)]
pub(crate) struct NewOutputIntent<'a> {
    pub profile: ProfileRequest<'a>,
    pub source: &'a Path,
    pub transaction_root: &'a Path,
    pub output_leaf: &'a str,
    pub operation: &'a str,
    pub format_revision: &'a str,
    pub planned_len: u64,
    pub max_len: u64,
}

/// Construction is deferred until storage admission. Merely creating this
/// builder must not open paths, create a backend/candidate, charge a budget or
/// release a worker; those actions belong in `construct`. In particular callers
/// must not pass an already constructed backend or candidate as a substitute.
/// The move-only capability retained by the preparation cannot be forged by
/// implementing this trait or returning an optimistic construction value.
pub(crate) trait NewOutputBuilder {
    type Prepared;

    fn construct(
        self,
        admission: &AdmittedByteSink,
        intent: NewOutputIntent<'_>,
        owner: &mut RetainedSession,
        cancel: &Cancellation,
    ) -> Result<Self::Prepared, Failure>;
}

/// Storage admission and construction stay together. There is deliberately no
/// constructor, capability extractor, or execute method: no profile is admitted
/// and independent format/apply integration is not implemented by this scope.
#[derive(Debug)]
pub(crate) struct PreparedNewOutput<T> {
    _admission: AdmittedByteSink,
    _construction: T,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum PreparationRefusal {
    Unsupported(Unsupported),
    Construction(Failure),
}

/// The intended format adapter calls this entry before constructing or charging
/// any storage work. Existing internal qualification runtimes intentionally do
/// not call this entry: they cannot grant an admitted production preparation.
/// The actual selector currently refuses every request, so `construct` cannot
/// run. This is tested through this caller, not inferred from helper-only tests.
pub(crate) fn prepare<B: NewOutputBuilder>(
    intent: NewOutputIntent<'_>,
    owner: &mut RetainedSession,
    cancel: &Cancellation,
    builder: B,
) -> Result<PreparedNewOutput<B::Prepared>, PreparationRefusal> {
    let admission = select_profile(&intent.profile).map_err(PreparationRefusal::Unsupported)?;
    let construction = builder
        .construct(&admission, intent, owner, cancel)
        .map_err(PreparationRefusal::Construction)?;
    Ok(PreparedNewOutput {
        _admission: admission,
        _construction: construction,
    })
}

#[cfg(test)]
mod tests;
