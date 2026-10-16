//! Bounded single-unit publication machinery; no production profile is admitted.
//!
//! Execution is deliberately crate-private until independent format and storage
//! admission exist. Public result/cancellation/budget values confer no authority.

use std::sync::atomic::{AtomicBool, Ordering};

/// Each of the four records and at most four caller captures has this limit.
pub const MAX_RECORD_BYTES: u64 = 65_536;

/// Cooperative cancellation is observed between synchronous backend operations.
#[derive(Debug, Default)]
pub struct Cancellation(AtomicBool);

impl Cancellation {
    pub fn request(&self) {
        self.0.store(true, Ordering::Release);
    }

    pub fn is_requested(&self) -> bool {
        self.0.load(Ordering::Acquire)
    }
}

/// Process-local cumulative logical construction accounting, never an OS quota.
/// There is intentionally no refund: failed and uncertain work remains charged.
#[derive(Debug)]
pub struct LogicalBudget {
    limit: u64,
    charged: u64,
}

impl LogicalBudget {
    pub fn new(limit: u64) -> Self {
        Self { limit, charged: 0 }
    }

    pub fn charged(&self) -> u64 {
        self.charged
    }

    fn reserve_unit(&mut self, candidate_len: u64) -> Result<u64, Failure> {
        let amount = candidate_len
            .checked_add(8 * MAX_RECORD_BYTES)
            .ok_or(Failure::LengthOverflow)?;
        let next = self
            .charged
            .checked_add(amount)
            .ok_or(Failure::LengthOverflow)?;
        if next > self.limit {
            return Err(Failure::BudgetExhausted);
        }
        self.charged = next;
        Ok(amount)
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Status {
    Unchanged,
    Refused,
    Conflict,
    FailedBeforePublish,
    CancelledBeforePublish,
    Committed,
    RecoveredOriginal,
    RecoveryRequired,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Failure {
    LengthOverflow,
    CandidateTooLarge,
    BudgetExhausted,
    ShortSource,
    OverlongSource,
    SourceIo,
    Cancelled,
    BackendIo,
    Unsupported,
    Conflict,
    Ambiguous,
    InvalidBinding,
    RecordTooLarge,
    CallerHistory,
}

/// Backend facts, not optimistic transport status. No cleanup is implicit.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct UnitResult {
    pub status: Status,
    pub phase: Phase,
    pub failure: Option<Failure>,
    pub publication_possible: bool,
    /// Caller release has begun; stop-before-release authority is unavailable.
    pub release_possible: bool,
    pub retained_material: bool,
    pub pending_cleanup: bool,
    pub charged_bytes: u64,
    /// An unqualified backend never emits a public commitment claim.
    pub protocol_complete: bool,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Phase {
    Preflight,
    SourceRead,
    RootCreated,
    RootFlushed,
    ParentFlushed,
    CandidateCreated,
    CandidateChecked,
    CandidateFlushed,
    CandidateParentFlushed,
    PreparedCreated,
    PreparedChecked,
    PreparedFlushed,
    PreparedParentFlushed,
    IntentCreated,
    IntentChecked,
    IntentFlushed,
    IntentParentFlushed,
    CallerRelease,
    Prepublication,
    Publish,
    Installed,
    InstalledFlushed,
    InstalledParentFlushed,
    InstalledRechecked,
    ObservationCreated,
    ObservationChecked,
    ObservationFlushed,
    ObservationParentFlushed,
    ReceiptCreated,
    ReceiptChecked,
    ReceiptFlushed,
    ReceiptFileChecked,
    ReceiptParentFlushed,
    ReceiptParentChecked,
    CheckedContext,
    Final,
    TerminalExport,
}

// Disabled internal implementation is compiled before a format/profile caller
// exists. Keep the unsafe/native boundary in the separate reviewed crate.
#[allow(dead_code)]
pub(crate) mod custody;
#[allow(dead_code)]
pub(crate) mod runtime;
#[cfg(windows)]
#[allow(dead_code)]
pub(crate) mod windows;
