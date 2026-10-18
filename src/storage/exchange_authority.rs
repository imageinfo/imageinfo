//! Exact live-caller authorization for one bounded two-name marker exchange.
//!
//! This seam is deliberately separate from publication/restart bindings: two
//! existing originals do not have a candidate, publication record or receipt.
//! Observations can be copied, but only an explicit current caller can issue a
//! nonserializable token. Its lifetime shares custody's revocation generation.

use super::MAX_RECORD_BYTES;
use super::custody::{CustodyRefusal, ExchangeGeneration, TrustedCurrentCaller};
use super::path_cycle::Plan;
use super::runtime::Binding;
use std::path::{Path, PathBuf};

/// A bounded exact observation, never an action capability or saved-phase import.
/// Original order is alpha then beta, matching the fixed three-move plan. The
/// only selected continuation is GuardHeldQuiet20Seconds in the actual adapter.
#[derive(Clone, Debug, PartialEq, Eq)]
pub(crate) struct ExchangeBindings {
    operation: String,
    names: [PathBuf; 3],
    private_record_root: PathBuf,
    originals: [Binding; 2],
}

impl ExchangeBindings {
    /// Trusted in-process capture. The native adapter supplies actual snapshot
    /// bindings and independently validates them through retained original holds.
    /// No records, receipts, parser, importer or profile claim is accepted here.
    pub(crate) fn capture(
        operation: &str,
        plan: &Plan,
        private_record_root: &Path,
        originals: [Binding; 2],
    ) -> Result<Self, CustodyRefusal> {
        Self::preflight(operation, plan, private_record_root, &originals)?;
        Ok(Self {
            operation: operation.into(),
            names: plan.names().clone(),
            private_record_root: private_record_root.into(),
            originals,
        })
    }

    fn preflight(
        operation: &str,
        plan: &Plan,
        private_record_root: &Path,
        originals: &[Binding; 2],
    ) -> Result<(), CustodyRefusal> {
        if operation.is_empty()
            || operation.len() > 256
            || private_record_root.as_os_str().is_empty()
            || originals[0].identity == originals[1].identity
        {
            return Err(CustodyRefusal::InvalidBindings);
        }
        let mut size = 128usize + operation.len();
        for path in plan
            .names()
            .iter()
            .map(PathBuf::as_path)
            .chain(std::iter::once(private_record_root))
        {
            let length = path.as_os_str().as_encoded_bytes().len();
            if length > 4096 {
                return Err(CustodyRefusal::ConstructionBound);
            }
            size = size
                .checked_add(8 + length)
                .ok_or(CustodyRefusal::ConstructionBound)?;
        }
        for binding in originals {
            if binding.identity.is_empty()
                || binding.identity.len() > 256
                || binding.facts.is_empty()
                || binding.facts.len() > 8192
            {
                return Err(CustodyRefusal::InvalidBindings);
            }
            size = size
                .checked_add(16 + binding.identity.len() + binding.facts.len())
                .ok_or(CustodyRefusal::ConstructionBound)?;
        }
        if size > MAX_RECORD_BYTES as usize {
            return Err(CustodyRefusal::ConstructionBound);
        }
        Ok(())
    }

    /// Snapshot equality binds every supplied baseline property, not just file
    /// IDs. The cycle subsequently checks these facts through the native holds.
    #[cfg(windows)]
    pub(crate) fn capture_snapshots(
        operation: &str,
        plan: &Plan,
        private_record_root: &Path,
        alpha: &imageinfo_windows_storage::FileSnapshot,
        beta: &imageinfo_windows_storage::FileSnapshot,
    ) -> Result<Self, CustodyRefusal> {
        if alpha.volume_serial_number != beta.volume_serial_number
            || alpha.file_index == beta.file_index
            || alpha.links != 1
            || beta.links != 1
            // Bound encoding allocation before copying private security text.
            || alpha.owner_dacl.len() > 8000
            || beta.owner_dacl.len() > 8000
        {
            return Err(CustodyRefusal::InvalidBindings);
        }
        Self::capture(
            operation,
            plan,
            private_record_root,
            [
                super::windows::binding_snapshot(alpha, None),
                super::windows::binding_snapshot(beta, None),
            ],
        )
    }
}

/// One explicit current-caller decision; cannot be cloned, saved or imported.
/// Dropping/revoking/replacing that caller invalidates it between native calls.
/// Complete observed exchange never manufactures a committed result or receipt.
pub(crate) struct ExchangeAuthority {
    expected: ExchangeBindings,
    generation: ExchangeGeneration,
}

impl ExchangeAuthority {
    /// The application asserts current authority independently of editable
    /// observations. This replaces all outstanding decisions for this caller,
    /// including restart tokens, and shares the existing construction ceiling.
    pub(crate) fn authorize(
        caller: &mut TrustedCurrentCaller,
        expected: ExchangeBindings,
    ) -> Result<Self, CustodyRefusal> {
        Ok(Self {
            expected,
            generation: caller.begin_exchange()?,
        })
    }

    /// Called before opening a session, each advance and immediately before an
    /// actual move. Rechecking cannot renew, widen or reconstruct authority.
    pub(crate) fn check(&self, fresh: &ExchangeBindings) -> Result<(), CustodyRefusal> {
        self.generation.check()?;
        if self.expected != *fresh {
            return Err(CustodyRefusal::ChangedBindings);
        }
        Ok(())
    }
}
