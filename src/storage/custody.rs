//! Explicit trusted-current-caller authority, independent of transaction parsing.
//!
//! This is an internal handoff boundary, not a restart executor or an importer.
//! The application supplying a current attestation is trusted to know the exact
//! operation independently. Checksums, paths, PIDs and editable records are only
//! observations. No deserializer or constructor for an action token exists.

use super::MAX_RECORD_BYTES;
use super::runtime::{Artifact, Binding};
use std::io;
use std::process::{Child, ExitStatus};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Weak};

#[cfg(test)]
thread_local! {
    static COPIED_RECORD_BYTES: std::cell::Cell<usize> = const { std::cell::Cell::new(0) };
}

/// Every refusal retains all storage artifacts. This module never removes one.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum CustodyRefusal {
    MissingAuthority,
    UnknownRoot,
    ChangedBindings,
    ContradictoryHistory,
    ActionNotAuthorized,
    StaleAuthority,
    InvalidBindings,
    ConstructionBound,
    SaveFailed,
    ReleaseUncertain,
    WorkerRunning,
    WorkerFailed,
    WorkerIo,
    InvalidLifecycle,
}

/// Complete bounded observation; possession of it grants no action authority.
/// Fields and exact record bytes are private and have no serialization importer.
#[derive(Clone, Debug, PartialEq, Eq)]
pub(crate) struct CurrentBindings {
    operation: String,
    profile: String,
    implementation: String,
    output: String,
    parent: Binding,
    bindings: Vec<Binding>,
    records: Vec<(Artifact, Vec<u8>)>,
    published: bool,
}

type CleanupParts<'a> = (
    &'a str,
    &'a str,
    &'a str,
    &'a str,
    &'a Binding,
    &'a [(Artifact, Vec<u8>)],
    bool,
);

impl CurrentBindings {
    /// Called by the native adapter after actual fresh held-object checks. The
    /// source/root/candidate prefix and each actual owned record are mandatory.
    /// Parent is captured separately from the retained native directory handle.
    #[allow(clippy::too_many_arguments)]
    pub(crate) fn capture(
        operation: &str,
        profile: &str,
        implementation: &str,
        output: &str,
        parent: &Binding,
        bindings: &[Binding],
        records: &[(Artifact, Vec<u8>)],
        published: bool,
    ) -> Result<Self, CustodyRefusal> {
        if records.len() > 4 {
            return Err(CustodyRefusal::InvalidBindings);
        }
        let records: Vec<_> = records
            .iter()
            .map(|(kind, bytes)| (*kind, bytes.as_slice()))
            .collect();
        Self::capture_borrowed(
            operation,
            profile,
            implementation,
            output,
            parent,
            bindings,
            &records,
            published,
        )
    }

    /// Native record payloads stay borrowed until the full capture, including
    /// the independently held parent, fits the construction ceiling.
    #[allow(clippy::too_many_arguments)]
    pub(crate) fn capture_borrowed(
        operation: &str,
        profile: &str,
        implementation: &str,
        output: &str,
        parent: &Binding,
        bindings: &[Binding],
        records: &[(Artifact, &[u8])],
        published: bool,
    ) -> Result<Self, CustodyRefusal> {
        Self::preflight_borrowed(
            operation,
            profile,
            implementation,
            output,
            parent,
            bindings,
            records,
            published,
        )?;
        Ok(Self {
            operation: operation.into(),
            profile: profile.into(),
            implementation: implementation.into(),
            output: output.into(),
            parent: parent.clone(),
            bindings: bindings.to_vec(),
            records: records
                .iter()
                .map(|(kind, bytes)| {
                    #[cfg(test)]
                    COPIED_RECORD_BYTES.with(|count| count.set(count.get() + bytes.len()));
                    (*kind, bytes.to_vec())
                })
                .collect(),
            published,
        })
    }

    /// Size and shape only; borrows all payloads and allocates no owned byte
    /// buffers. Native adapters call this before copying an expected-binding
    /// argument for their existing full-check API.
    #[allow(clippy::too_many_arguments)]
    pub(crate) fn preflight_borrowed(
        operation: &str,
        profile: &str,
        implementation: &str,
        output: &str,
        parent: &Binding,
        bindings: &[Binding],
        records: &[(Artifact, &[u8])],
        _published: bool,
    ) -> Result<usize, CustodyRefusal> {
        let strings = [operation, profile, implementation, output];
        if strings.iter().any(|s| s.is_empty() || s.len() > 256)
            || output.contains(['/', '\\', ':'])
            || [".", ".."].contains(&output)
            || records.len() > 4
            || bindings.len() != 3 + records.len()
        {
            return Err(CustodyRefusal::InvalidBindings);
        }
        let order = [
            Artifact::Prepared,
            Artifact::Intent,
            Artifact::Observation,
            Artifact::Receipt,
        ];
        if records
            .iter()
            .zip(order)
            .any(|((kind, _), expected)| *kind != expected)
        {
            return Err(CustodyRefusal::InvalidBindings);
        }
        let mut size = 128usize;
        for text in strings {
            size = size
                .checked_add(8 + text.len())
                .ok_or(CustodyRefusal::ConstructionBound)?;
        }
        for (index, binding) in std::iter::once(parent).chain(bindings).enumerate() {
            if binding.identity.is_empty()
                || binding.identity.len() > 256
                || binding.facts.is_empty()
                || binding.facts.len() > 8192
                || (index > 0
                    && bindings[..index - 1]
                        .iter()
                        .any(|b| b.identity == binding.identity))
                || (index > 0 && parent.identity == binding.identity)
            {
                return Err(CustodyRefusal::InvalidBindings);
            }
            size = size
                .checked_add(16 + binding.identity.len() + binding.facts.len())
                .ok_or(CustodyRefusal::ConstructionBound)?;
        }
        for (kind, bytes) in records {
            if bytes.is_empty() {
                return Err(CustodyRefusal::InvalidBindings);
            }
            size = size
                .checked_add(32 + kind.leaf().len() + bytes.len())
                .ok_or(CustodyRefusal::ConstructionBound)?;
        }
        if size > MAX_RECORD_BYTES as usize {
            return Err(CustodyRefusal::ConstructionBound);
        }
        Ok(size)
    }

    pub(super) fn compare(&self, fresh: &Self) -> Result<(), CustodyRefusal> {
        if self.operation != fresh.operation
            || self.bindings[1].identity != fresh.bindings[1].identity
        {
            return Err(CustodyRefusal::UnknownRoot);
        }
        if self != fresh {
            return Err(CustodyRefusal::ChangedBindings);
        }
        Ok(())
    }

    /// One finalization may append a receipt while every prior field stays exact.
    pub(super) fn extends(&self, prior: &Self) -> bool {
        self.operation == prior.operation
            && self.profile == prior.profile
            && self.implementation == prior.implementation
            && self.output == prior.output
            && self.parent == prior.parent
            && self.published == prior.published
            && self.bindings.starts_with(&prior.bindings)
            && self.records.starts_with(&prior.records)
    }

    /// Borrow the already bounded actual object revision; no decoder or authority.
    pub(super) fn object_bindings(&self) -> &[Binding] {
        &self.bindings
    }

    pub(super) fn cleanup_parts(&self) -> CleanupParts<'_> {
        (
            &self.operation,
            &self.profile,
            &self.implementation,
            &self.output,
            &self.parent,
            &self.records,
            self.published,
        )
    }

    /// External caller saves are bounded observations, never a decoder/authority
    /// format. Exact opaque fields are length-prefixed, not debug text or paths.
    fn save_bytes(&self, kind: SaveKind) -> Vec<u8> {
        fn field(out: &mut Vec<u8>, bytes: &[u8]) {
            out.extend_from_slice(&(bytes.len() as u64).to_le_bytes());
            out.extend_from_slice(bytes);
        }
        let mut out = b"imageinfo-caller-observation-v1\0".to_vec();
        out.push(kind as u8);
        out.push(u8::from(self.published));
        for text in [
            &self.operation,
            &self.profile,
            &self.implementation,
            &self.output,
        ] {
            field(&mut out, text.as_bytes());
        }
        for binding in std::iter::once(&self.parent).chain(&self.bindings) {
            field(&mut out, &binding.identity);
            field(&mut out, &binding.facts);
        }
        for (kind, bytes) in &self.records {
            field(&mut out, kind.leaf().as_bytes());
            field(&mut out, bytes);
        }
        out
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum RestartAction {
    RecognizeCompletion,
    FinalizeExisting,
    PruneUnpublished,
    CleanupCompleted,
}

/// A statement made by the selected trusted *current* caller, independently of
/// the editable transaction. This is not a claim of automatic durable custody.
/// No conversion from UnitResult, record flags, PID, checksum or JSON is offered.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum CurrentCallerHistory {
    StoppedBeforeRelease,
    ReleasedAndStopped,
    TerminalCompletionAndStopped,
    Contradictory,
}

/// One known operation, one explicitly selected action. Replacing/closing this
/// live caller revokes outstanding tokens. A newly created caller starts empty.
pub(crate) struct TrustedCurrentCaller {
    generation: Arc<AtomicU64>,
    retained: Option<(CurrentBindings, CurrentCallerHistory)>,
    constructions: u8,
}

impl TrustedCurrentCaller {
    pub(crate) fn new() -> Self {
        Self {
            generation: Arc::new(AtomicU64::new(1)),
            retained: None,
            constructions: 0,
        }
    }

    /// The explicit trusted-current-caller boundary selected in #0165. The
    /// application must obtain `expected` and history independently of editable
    /// transaction data. Calling this intentionally asserts that authority now;
    /// matching observations never call it implicitly. After OS/caller restart
    /// this is a new attestation, not revival of a former local capability.
    pub(crate) fn attest_current(
        &mut self,
        expected: CurrentBindings,
        history: CurrentCallerHistory,
    ) -> Result<(), CustodyRefusal> {
        self.revoke();
        if self.constructions >= 4 {
            return Err(CustodyRefusal::ConstructionBound);
        }
        self.constructions += 1;
        if history == CurrentCallerHistory::Contradictory
            || (history == CurrentCallerHistory::StoppedBeforeRelease && expected.published)
        {
            return Err(CustodyRefusal::ContradictoryHistory);
        }
        self.retained = Some((expected, history));
        Ok(())
    }

    pub(crate) fn authorize(
        &mut self,
        action: RestartAction,
        fresh: &CurrentBindings,
    ) -> Result<ActionAuthority, CustodyRefusal> {
        // Even a conflicting attempt consumes the old authorization. A later
        // matching edit cannot erase the failure or revive this decision.
        let (expected, history) = self
            .retained
            .take()
            .ok_or(CustodyRefusal::MissingAuthority)?;
        expected.compare(fresh)?;
        let allowed = match action {
            RestartAction::PruneUnpublished => {
                history == CurrentCallerHistory::StoppedBeforeRelease && !expected.published
            }
            RestartAction::RecognizeCompletion | RestartAction::CleanupCompleted => {
                history == CurrentCallerHistory::TerminalCompletionAndStopped && expected.published
            }
            RestartAction::FinalizeExisting => {
                matches!(
                    history,
                    CurrentCallerHistory::ReleasedAndStopped
                        | CurrentCallerHistory::TerminalCompletionAndStopped
                ) && expected.published
            }
        };
        if !allowed {
            return Err(CustodyRefusal::ActionNotAuthorized);
        }
        Ok(ActionAuthority {
            expected,
            action,
            generation: self.generation.load(Ordering::Acquire),
            caller: Arc::downgrade(&self.generation),
        })
    }

    pub(crate) fn revoke(&mut self) {
        self.retained = None;
        self.generation.fetch_add(1, Ordering::AcqRel);
    }

    /// Issue only the live generation component of the bounded exchange seam.
    /// Exchange bindings are checked separately; this cannot authorize any
    /// restart action or construct the publication-shaped `CurrentBindings`.
    pub(super) fn begin_exchange(&mut self) -> Result<ExchangeGeneration, CustodyRefusal> {
        self.revoke();
        if self.constructions >= 4 {
            return Err(CustodyRefusal::ConstructionBound);
        }
        self.constructions += 1;
        Ok(ExchangeGeneration {
            generation: self.generation.load(Ordering::Acquire),
            caller: Arc::downgrade(&self.generation),
        })
    }

    /// The paired live-name operation shares the existing finite generation
    /// and revocation domain; it grants no publication or restart authority.
    pub(super) fn begin_pair_rename(&mut self) -> Result<ExchangeGeneration, CustodyRefusal> {
        self.begin_exchange()
    }
}

impl Drop for TrustedCurrentCaller {
    fn drop(&mut self) {
        self.revoke();
    }
}

/// Same caller lifetime/revocation domain as restart tokens, with no restart
/// action or record-shaped authority. Exact exchange and paired live-name seams
/// bind their operation-specific observations separately.
pub(super) struct ExchangeGeneration {
    generation: u64,
    caller: Weak<AtomicU64>,
}

impl ExchangeGeneration {
    pub(super) fn check(&self) -> Result<(), CustodyRefusal> {
        let caller = self
            .caller
            .upgrade()
            .ok_or(CustodyRefusal::StaleAuthority)?;
        if caller.load(Ordering::Acquire) != self.generation {
            return Err(CustodyRefusal::StaleAuthority);
        }
        Ok(())
    }
}

/// Non-cloneable, nonserializable, single-use handoff to a later action layer.
/// Validation grants no storage mutation by itself; #0170-0172 own action checks.
pub(crate) struct ActionAuthority {
    expected: CurrentBindings,
    action: RestartAction,
    generation: u64,
    caller: Weak<AtomicU64>,
}

impl ActionAuthority {
    pub(crate) fn validate(
        self,
        action: RestartAction,
        fresh: &CurrentBindings,
    ) -> Result<(), CustodyRefusal> {
        self.check(action, fresh)
    }

    /// Keep the same live authority revocable throughout one guarded action.
    /// Rechecking never issues a new token or widens its exact starting binding.
    pub(super) fn check(
        &self,
        action: RestartAction,
        fresh: &CurrentBindings,
    ) -> Result<(), CustodyRefusal> {
        let caller = self
            .caller
            .upgrade()
            .ok_or(CustodyRefusal::StaleAuthority)?;
        if caller.load(Ordering::Acquire) != self.generation {
            return Err(CustodyRefusal::StaleAuthority);
        }
        if action != self.action {
            return Err(CustodyRefusal::ActionNotAuthorized);
        }
        self.expected.compare(fresh)
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum SaveKind {
    Captured,
    ReleaseFence,
    Stopped,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum WorkerState {
    New,
    Captured,
    Uncertain,
    Released,
    Stopped,
    ReleasedStopped,
    Closed,
}

/// The owned `Child` handle, never a PID, establishes actual process custody.
/// Save callbacks are trusted caller IO; success means complete save/flush as
/// required by that caller. No successful checksum is treated as authentication.
pub(crate) struct OwnedWorker {
    child: Child,
    operation: String,
    state: WorkerState,
    expected: Option<CurrentBindings>,
    saves: u8,
}

impl OwnedWorker {
    /// Caller launches the reviewed worker for this operation with private
    /// pipes. Executable selection and the worker's observation decoder are
    /// trusted application responsibilities, as in #0114; no PID adoption.
    pub(crate) fn new(mut child: Child, operation: &str) -> Result<Self, CustodyRefusal> {
        if operation.is_empty() || operation.len() > 256 {
            let _ = child.kill();
            let _ = child.wait();
            return Err(CustodyRefusal::InvalidBindings);
        }
        Ok(Self {
            child,
            operation: operation.into(),
            state: WorkerState::New,
            expected: None,
            saves: 0,
        })
    }

    fn save(
        &mut self,
        kind: SaveKind,
        save: impl FnOnce(SaveKind, &[u8]) -> io::Result<()>,
    ) -> Result<(), CustodyRefusal> {
        if self.saves >= 4 {
            return Err(CustodyRefusal::ConstructionBound);
        }
        self.saves += 1;
        let bytes = self
            .expected
            .as_ref()
            .ok_or(CustodyRefusal::InvalidLifecycle)?
            .save_bytes(kind);
        if bytes.len() > MAX_RECORD_BYTES as usize {
            return Err(CustodyRefusal::ConstructionBound);
        }
        save(kind, &bytes).map_err(|_| CustodyRefusal::SaveFailed)
    }

    /// Read the known operation's notice from the actual owned child's private
    /// channel. The callback must bound decoding to MAX_RECORD_BYTES and use
    /// that Child's pipe, never an editable transaction, PID lookup or path.
    /// The callback and selected worker are trusted; same-process malicious
    /// callers are outside this boundary's security assumptions.
    pub(crate) fn capture_from_worker(
        &mut self,
        observe: impl FnOnce(&mut Child) -> Result<CurrentBindings, CustodyRefusal>,
        save: impl FnOnce(SaveKind, &[u8]) -> io::Result<()>,
    ) -> Result<(), CustodyRefusal> {
        if self.state != WorkerState::New {
            return Err(CustodyRefusal::InvalidLifecycle);
        }
        self.state = WorkerState::Uncertain;
        let expected = observe(&mut self.child)?;
        if expected.operation != self.operation {
            return Err(CustodyRefusal::UnknownRoot);
        }
        if expected.published {
            return Err(CustodyRefusal::ContradictoryHistory);
        }
        self.expected = Some(expected);
        self.save(SaveKind::Captured, save)?;
        self.state = WorkerState::Captured;
        Ok(())
    }

    pub(crate) fn release(
        &mut self,
        save: impl FnOnce(SaveKind, &[u8]) -> io::Result<()>,
        send: impl FnOnce(&mut Child) -> io::Result<()>,
    ) -> Result<(), CustodyRefusal> {
        if self.state != WorkerState::Captured {
            return Err(CustodyRefusal::InvalidLifecycle);
        }
        // Set before even trying the save. Failed/partial/ambiguous save or
        // continuation permanently prevents stop-before-release authority.
        self.state = WorkerState::Uncertain;
        self.save(SaveKind::ReleaseFence, save)?;
        send(&mut self.child).map_err(|_| CustodyRefusal::ReleaseUncertain)?;
        self.state = WorkerState::Released;
        Ok(())
    }

    pub(crate) fn stop_before_release(
        &mut self,
        save: impl FnOnce(SaveKind, &[u8]) -> io::Result<()>,
    ) -> Result<(), CustodyRefusal> {
        if self.state != WorkerState::Captured {
            return Err(CustodyRefusal::InvalidLifecycle);
        }
        self.state = WorkerState::Uncertain;
        if self
            .child
            .try_wait()
            .map_err(|_| CustodyRefusal::WorkerIo)?
            .is_none()
        {
            self.child.kill().map_err(|_| CustodyRefusal::WorkerIo)?;
        }
        self.child.wait().map_err(|_| CustodyRefusal::WorkerIo)?;
        self.save(SaveKind::Stopped, save)?;
        self.state = WorkerState::Stopped;
        Ok(())
    }

    /// Confirm the actual original child exited; a replacement PID/process or
    /// caller-supplied exit code is not accepted. Nonzero exit remains failure.
    pub(crate) fn confirm_released_exit(&mut self) -> Result<ExitStatus, CustodyRefusal> {
        if self.state != WorkerState::Released {
            return Err(CustodyRefusal::InvalidLifecycle);
        }
        let result = self.child.try_wait().map_err(|_| {
            self.state = WorkerState::Uncertain;
            CustodyRefusal::WorkerIo
        })?;
        let status = result.ok_or(CustodyRefusal::WorkerRunning)?;
        if !status.success() {
            self.state = WorkerState::Uncertain;
            return Err(CustodyRefusal::WorkerFailed);
        }
        self.state = WorkerState::ReleasedStopped;
        Ok(status)
    }

    pub(crate) fn handoff_stopped(
        &mut self,
        caller: &mut TrustedCurrentCaller,
    ) -> Result<(), CustodyRefusal> {
        if self.state != WorkerState::Stopped {
            return Err(CustodyRefusal::InvalidLifecycle);
        }
        let expected = self
            .expected
            .take()
            .ok_or(CustodyRefusal::InvalidLifecycle)?;
        self.state = WorkerState::Closed;
        caller.attest_current(expected, CurrentCallerHistory::StoppedBeforeRelease)
    }

    /// Close never transfers authority. Artifacts remain and uncertain children
    /// are stopped using only the original owned handle; no process-name sweep.
    pub(crate) fn close(&mut self) -> Result<(), CustodyRefusal> {
        self.state = WorkerState::Closed;
        self.expected = None;
        if self
            .child
            .try_wait()
            .map_err(|_| CustodyRefusal::WorkerIo)?
            .is_none()
        {
            self.child.kill().map_err(|_| CustodyRefusal::WorkerIo)?;
        }
        self.child.wait().map_err(|_| CustodyRefusal::WorkerIo)?;
        Ok(())
    }
}

impl Drop for OwnedWorker {
    fn drop(&mut self) {
        let _ = self.close();
    }
}

#[cfg(test)]
mod tests;
