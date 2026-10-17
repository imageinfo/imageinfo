//! Explicit caller-owned retained-work accounting. Nothing is inferred from a
//! directory listing, a transaction record, or a free-space observation.

use super::runtime::{Backend, ValidatedCandidate, execute};
use super::{Cancellation, Failure, LogicalBudget, MAX_RECORD_BYTES, UnitResult};

/// Bounds ledger identity/result storage before either identity is copied.
pub(crate) const ENTRY_BYTES: u64 = MAX_RECORD_BYTES;
const MAX_OPERATIONS: usize = 256;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) struct OperationKey<'a> {
    pub operation: &'a str,
    /// Explicit caller identity for the root; never discovered by scanning it.
    pub root: &'a str,
}

impl OperationKey<'_> {
    fn valid(self) -> bool {
        !self.operation.is_empty()
            && self.operation.len() <= 256
            && !self.root.is_empty()
            && self.root.len() <= 4096
    }
}

/// The trusted caller must explicitly assert its complete ownership scope.
/// Unknown retained state is never converted into an empty scope.
pub(crate) enum KnownOperations<'a> {
    Complete(&'a [OperationKey<'a>]),
    Unknown,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum Construction {
    Custody,
    Recovery,
    Manifest,
}

#[derive(Debug)]
struct Entry {
    operation: String,
    root: String,
    charged: u64,
    /// None means execution was interrupted/uncertain in this caller.
    result: Option<UnitResult>,
    extra: [u64; 3],
}

/// Move-only complete ownership handoff. No importer, Clone or constructor from
/// editable transaction files exists. This is not automatic durable custody.
#[derive(Debug)]
pub(crate) struct RetainedWork {
    budget: LogicalBudget,
    entries: Vec<Entry>,
    uncertain: bool,
}

/// All helpers borrow this single owner. Failed/cancelled/completed operations
/// and attempted custody/recovery constructions retain their full charge.
pub(crate) struct RetainedSession {
    retained: RetainedWork,
}

impl RetainedSession {
    pub(crate) fn start(limit: u64, known: KnownOperations<'_>) -> Result<Self, Failure> {
        match known {
            KnownOperations::Complete([]) => Ok(Self {
                retained: RetainedWork {
                    budget: LogicalBudget::new(limit),
                    entries: Vec::new(),
                    uncertain: false,
                },
            }),
            _ => Err(Failure::CallerHistory),
        }
    }

    /// Adoption consumes the original complete accounting object and compares
    /// the independently selected complete set. A recreated helper cannot omit
    /// old failed attempts or synthesize their charges from directory sizes.
    pub(crate) fn adopt(
        work: RetainedWork,
        known: KnownOperations<'_>,
    ) -> Result<Self, (Failure, RetainedWork)> {
        let KnownOperations::Complete(keys) = known else {
            return Err((Failure::CallerHistory, work));
        };
        if work.uncertain
            || keys.len() != work.entries.len()
            || keys.iter().enumerate().any(|(index, key)| {
                !key.valid()
                    || keys[..index].iter().any(|old| old == key)
                    || !work
                        .entries
                        .iter()
                        .any(|entry| entry.operation == key.operation && entry.root == key.root)
            })
            || work.entries.iter().any(|entry| entry.result.is_none())
        {
            return Err((Failure::CallerHistory, work));
        }
        Ok(Self { retained: work })
    }

    pub(crate) fn suspend(self) -> RetainedWork {
        self.retained
    }

    pub(crate) fn charged(&self) -> u64 {
        self.retained.budget.charged()
    }

    pub(crate) fn operation_charge(&self, key: OperationKey<'_>) -> Result<u64, Failure> {
        self.index(key)
            .map(|index| self.retained.entries[index].charged)
    }

    fn index(&self, key: OperationKey<'_>) -> Result<usize, Failure> {
        self.retained
            .entries
            .iter()
            .position(|entry| entry.operation == key.operation && entry.root == key.root)
            .ok_or(Failure::CallerHistory)
    }

    /// `available` performs the selected read-only native availability query.
    /// Its value is advisory: another allocator may consume it immediately.
    /// Neither success nor a logical charge reserves physical space.
    pub(crate) fn run<B: Backend>(
        &mut self,
        key: OperationKey<'_>,
        backend: &mut B,
        request: ValidatedCandidate<'_>,
        cancel: &Cancellation,
        available: impl FnOnce(&mut B) -> Result<u64, Failure>,
    ) -> Result<UnitResult, Failure> {
        if self.retained.uncertain
            || !key.valid()
            || key.operation != request.operation
            || self.retained.entries.len() >= MAX_OPERATIONS
            || self.retained.entries.iter().any(|entry| {
                entry.result.is_none() || entry.operation == key.operation || entry.root == key.root
            })
        {
            return Err(Failure::CallerHistory);
        }
        let unit = LogicalBudget::unit_charge(request.planned_len)?;
        let total = unit
            .checked_add(ENTRY_BYTES)
            .ok_or(Failure::LengthOverflow)?;
        // Reserve ledger capacity and all logical construction before copying
        // identity strings, creating candidates, captures or backend objects.
        self.retained.budget.reserve_construction(total)?;
        self.retained.uncertain = true;
        self.retained
            .entries
            .try_reserve(1)
            .map_err(|_| Failure::BackendIo)?;
        self.retained.entries.push(Entry {
            operation: key.operation.into(),
            root: key.root.into(),
            charged: total,
            result: None,
            extra: [0; 3],
        });
        self.retained.uncertain = false;
        let index = self.retained.entries.len() - 1;
        let outcome = match available(backend) {
            Ok(bytes) if bytes >= unit => {
                // The cumulative owner was already charged. This unexported
                // local helper grants exactly one execution, never a reset.
                let mut allowance = LogicalBudget::new(unit);
                Ok(execute(backend, request, &mut allowance, cancel))
            }
            Ok(_) => Err(Failure::StorageUnavailable),
            Err(error) => Err(error),
        };
        // A known terminal preflight refusal remains a retained charged entry.
        // Panics before here leave None and refuse all future effects/adoption.
        let result = match outcome {
            Ok(mut result) => {
                result.charged_bytes = total;
                result
            }
            Err(error) => UnitResult {
                status: match error {
                    Failure::BackendIo | Failure::SourceIo => super::Status::FailedBeforePublish,
                    Failure::Conflict => super::Status::Conflict,
                    Failure::Cancelled => super::Status::CancelledBeforePublish,
                    _ => super::Status::Refused,
                },
                phase: super::Phase::Preflight,
                failure: Some(error),
                publication_possible: false,
                release_possible: false,
                retained_material: false,
                pending_cleanup: false,
                charged_bytes: total,
                protocol_complete: false,
            },
        };
        self.retained.entries[index].result = Some(result.clone());
        Ok(result)
    }

    /// Actual native admission always queries that backend's selected parent.
    /// An arbitrary availability callback is not part of this Windows seam.
    #[cfg(windows)]
    pub(crate) fn run_windows(
        &mut self,
        key: OperationKey<'_>,
        backend: &mut super::windows::WindowsBackend,
        request: ValidatedCandidate<'_>,
        cancel: &Cancellation,
    ) -> Result<UnitResult, Failure> {
        self.run(key, backend, request, cancel, |backend| {
            backend.available_bytes()
        })
    }

    /// Reserve a finite extra custody/recovery/manifest construction before
    /// its allocation/copy/effect callback. Size must come from borrowed bounds,
    /// never an already copied payload. Uncertain/failed callbacks stay charged.
    /// The constructor is trusted crate implementation, not an external plugin.
    pub(crate) fn construct<T>(
        &mut self,
        key: OperationKey<'_>,
        kind: Construction,
        bounded_bytes: u64,
        constructor: impl FnOnce() -> Result<T, Failure>,
    ) -> Result<T, Failure> {
        if bounded_bytes > MAX_RECORD_BYTES {
            return Err(Failure::RecordTooLarge);
        }
        if self.retained.uncertain
            || self
                .retained
                .entries
                .iter()
                .any(|entry| entry.result.is_none())
        {
            return Err(Failure::CallerHistory);
        }
        let index = self.index(key)?;
        let category = kind as usize;
        let entry = &self.retained.entries[index];
        let charged = entry
            .charged
            .checked_add(bounded_bytes)
            .ok_or(Failure::LengthOverflow)?;
        let extra = entry.extra[category]
            .checked_add(bounded_bytes)
            .ok_or(Failure::LengthOverflow)?;
        self.retained.budget.reserve_construction(bounded_bytes)?;
        self.retained.entries[index].charged = charged;
        self.retained.entries[index].extra[category] = extra;
        self.retained.uncertain = true;
        let outcome = constructor();
        self.retained.uncertain = false;
        outcome
    }

    /// The existing native capture enforces the same whole borrowed-input
    /// ceiling before copying. Charge its maximum before invoking it.
    #[cfg(windows)]
    pub(crate) fn capture_custody(
        &mut self,
        key: OperationKey<'_>,
        backend: &mut super::windows::WindowsBackend,
    ) -> Result<super::custody::CurrentBindings, Failure> {
        self.construct(key, Construction::Custody, MAX_RECORD_BYTES, || {
            backend.custody_snapshot(key.operation)
        })
    }
}

#[cfg(test)]
mod tests;
