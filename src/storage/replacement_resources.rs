//! Fixed, disabled retained-original resource admission. This supplies no
//! replacement, restoration, stream-copy mechanism or qualified profile.

use super::resources::{ENTRY_BYTES, OperationKey, RetainedSession};
use super::{Cancellation, Failure, MAX_RECORD_BYTES};

pub(crate) const MAX_STREAMS: usize = 16;
pub(crate) const MEMBER_RECORD_BYTES: u64 = 8 * MAX_RECORD_BYTES;
pub(crate) const GROUP_RECORD_BYTES: u64 = MAX_RECORD_BYTES;

/// Complete supported-stream inventory from the selected live guard. Unknown
/// enumeration and unreadable extents must not become an empty inventory.
#[derive(Clone, Copy, Debug)]
pub(crate) enum Streams<'a> {
    Complete(&'a [Option<u64>]),
    Unknown,
}

#[derive(Clone, Copy, Debug)]
pub(crate) struct FileBytes<'a> {
    pub default: Option<u64>,
    pub streams: Streams<'a>,
}

impl FileBytes<'_> {
    fn total(self) -> Result<u64, Failure> {
        let mut total = self.default.ok_or(Failure::InvalidBinding)?;
        let Streams::Complete(streams) = self.streams else {
            return Err(Failure::InvalidBinding);
        };
        if streams.len() > MAX_STREAMS {
            return Err(Failure::RecordTooLarge);
        }
        for bytes in streams {
            total = total
                .checked_add(bytes.ok_or(Failure::SourceIo)?)
                .ok_or(Failure::LengthOverflow)?;
        }
        Ok(total)
    }
}

#[derive(Clone, Copy, Debug)]
pub(crate) enum Member<'a> {
    Replace {
        candidate: FileBytes<'a>,
        original_recovery: FileBytes<'a>,
    },
    Restore {
        restored_candidate: FileBytes<'a>,
        original_recovery: FileBytes<'a>,
        current_preservation: FileBytes<'a>,
    },
}

#[derive(Clone, Copy, Debug)]
pub(crate) enum BackupChoice {
    Keep,
    NoBackup,
}

/// Fixed table: candidate + original recovery + (restore current preservation)
/// plus eight bounded records/captures per member and one two-member manifest.
/// The original recovery row is required for both backup choices before commit.
#[derive(Debug, PartialEq, Eq)]
pub(crate) struct Plan {
    candidate_bytes: u64,
    original_recovery_bytes: u64,
    current_preservation_bytes: u64,
    records_bytes: u64,
    precommit_bytes: u64,
    ledger_bytes: u64,
}

impl Plan {
    pub(crate) fn build(members: &[Member<'_>], _backup: BackupChoice) -> Result<Self, Failure> {
        if !(1..=2).contains(&members.len()) {
            return Err(Failure::Unsupported);
        }
        let mut plan = Self {
            candidate_bytes: 0,
            original_recovery_bytes: 0,
            current_preservation_bytes: 0,
            records_bytes: MEMBER_RECORD_BYTES * members.len() as u64
                + if members.len() == 2 {
                    GROUP_RECORD_BYTES
                } else {
                    0
                },
            precommit_bytes: 0,
            ledger_bytes: ENTRY_BYTES,
        };
        for member in members {
            let (candidate, recovery, current) = match *member {
                Member::Replace {
                    candidate,
                    original_recovery,
                } => (candidate, original_recovery, None),
                Member::Restore {
                    restored_candidate,
                    original_recovery,
                    current_preservation,
                } => (
                    restored_candidate,
                    original_recovery,
                    Some(current_preservation),
                ),
            };
            plan.candidate_bytes = add(plan.candidate_bytes, candidate.total()?)?;
            plan.original_recovery_bytes = add(plan.original_recovery_bytes, recovery.total()?)?;
            if let Some(current) = current {
                plan.current_preservation_bytes =
                    add(plan.current_preservation_bytes, current.total()?)?;
            }
        }
        plan.precommit_bytes = add(
            add(
                add(plan.candidate_bytes, plan.original_recovery_bytes)?,
                plan.current_preservation_bytes,
            )?,
            plan.records_bytes,
        )?;
        // Check the shared ledger row before any caller query or construction.
        add(plan.precommit_bytes, plan.ledger_bytes)?;
        Ok(plan)
    }

    pub(crate) fn attempt<T>(
        &self,
        session: &mut RetainedSession,
        key: OperationKey<'_>,
        cancel: &Cancellation,
        available: impl FnOnce() -> Result<u64, Failure>,
        constructor: impl FnOnce() -> Result<T, Failure>,
    ) -> Result<T, Failure> {
        session.attempt(key, self.precommit_bytes, available, || {
            if cancel.is_requested() {
                Err(Failure::Cancelled)
            } else {
                constructor()
            }
        })
    }
}

fn add(left: u64, right: u64) -> Result<u64, Failure> {
    left.checked_add(right).ok_or(Failure::LengthOverflow)
}

#[cfg(test)]
mod tests;
