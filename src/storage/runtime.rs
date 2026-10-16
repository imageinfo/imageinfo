use super::{Cancellation, Failure, LogicalBudget, MAX_RECORD_BYTES, Phase, Status, UnitResult};
use std::io::Read;

pub(crate) const PROTOCOL: &str = "windows-new-output-contract-v1";

/// Acknowledgements exist only in the live executor. Transaction records encode
/// prior acknowledgements for diagnostics; decoding them cannot recreate these.
#[derive(Clone, Debug, PartialEq, Eq)]
pub(crate) struct LiveAcknowledgement {
    pub phase: Phase,
    pub target: AckTarget,
    pub bindings: Vec<Binding>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum AckTarget {
    Source,
    Root,
    ContainingParent,
    Artifact(Artifact),
    CompleteSet,
    Caller,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub(crate) struct LiveEvidence {
    pub protocol: &'static str,
    pub profile: &'static str,
    pub implementation: &'static str,
    pub operation: String,
    pub format_revision: String,
    pub output: String,
    pub candidate_len: u64,
    pub acknowledgements: Vec<LiveAcknowledgement>,
}

impl LiveEvidence {
    fn target(phase: Phase) -> AckTarget {
        use Artifact::*;
        use Phase::*;
        match phase {
            Preflight | SourceRead => AckTarget::Source,
            RootCreated
            | RootFlushed
            | CandidateParentFlushed
            | PreparedParentFlushed
            | IntentParentFlushed
            | InstalledParentFlushed
            | ObservationParentFlushed
            | ReceiptParentFlushed => AckTarget::Root,
            ParentFlushed => AckTarget::ContainingParent,
            CandidateCreated | CandidateFlushed | InstalledFlushed | Publish => {
                AckTarget::Artifact(Candidate)
            }
            PreparedCreated | PreparedFlushed => AckTarget::Artifact(Prepared),
            IntentCreated | IntentFlushed => AckTarget::Artifact(Intent),
            ObservationCreated | ObservationFlushed => AckTarget::Artifact(Observation),
            ReceiptCreated | ReceiptFlushed => AckTarget::Artifact(Receipt),
            CallerRelease | CheckedContext | TerminalExport => AckTarget::Caller,
            _ => AckTarget::CompleteSet,
        }
    }

    pub(crate) fn complete(&self, bindings: &[Binding]) -> bool {
        use Phase::*;
        const REQUIRED: &[Phase] = &[
            Preflight,
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
        ];
        self.protocol == PROTOCOL
            && !self.profile.is_empty()
            && !self.implementation.is_empty()
            && self.acknowledgements.len() == REQUIRED.len()
            && self
                .acknowledgements
                .iter()
                .zip(REQUIRED)
                .all(|(ack, phase)| {
                    ack.phase == *phase
                        && ack.target == Self::target(*phase)
                        && !ack.bindings.is_empty()
                        && ack.bindings.len()
                            == match phase {
                                Preflight => 1,
                                RootCreated | RootFlushed | ParentFlushed => 2,
                                CandidateCreated
                                | CandidateChecked
                                | CandidateFlushed
                                | CandidateParentFlushed => 3,
                                PreparedCreated
                                | PreparedChecked
                                | PreparedFlushed
                                | PreparedParentFlushed => 4,
                                IntentCreated
                                | IntentChecked
                                | IntentFlushed
                                | IntentParentFlushed
                                | CallerRelease
                                | Prepublication
                                | Publish
                                | Installed
                                | InstalledFlushed
                                | InstalledParentFlushed
                                | InstalledRechecked => 5,
                                ObservationCreated
                                | ObservationChecked
                                | ObservationFlushed
                                | ObservationParentFlushed => 6,
                                _ => 7,
                            }
                        && bindings.starts_with(&ack.bindings)
                })
            && self
                .acknowledgements
                .last()
                .is_some_and(|ack| ack.bindings == bindings)
    }
}

trait SuccessfulEffect {
    fn binding(&self) -> Option<&Binding> {
        None
    }
}
impl SuccessfulEffect for () {}
impl SuccessfulEffect for usize {}
impl SuccessfulEffect for Binding {
    fn binding(&self) -> Option<&Binding> {
        Some(self)
    }
}

/// Only a format implementation inside this crate may construct this decision.
/// A parsed plan, receipt or application boolean cannot manufacture it.
pub(crate) struct ValidatedCandidate<'a> {
    pub operation: &'a str,
    pub format_revision: &'a str,
    pub source: &'a mut dyn Read,
    pub planned_len: u64,
    pub max_len: u64,
    pub output: ExpectedAbsent<'a>,
}

pub(crate) struct ExpectedAbsent<'a>(pub &'a str);

#[derive(Clone, Debug, PartialEq, Eq)]
pub(crate) struct Binding {
    pub identity: Vec<u8>,
    /// Backend-native identity, properties and exact content fingerprint.
    /// It must be captured from the held object, not predicted from a path.
    pub facts: Vec<u8>,
}

impl Binding {
    fn validate(&self) -> Result<(), Failure> {
        if self.identity.is_empty()
            || self.identity.len() > 256
            || self.facts.is_empty()
            || self.facts.len() > 8192
        {
            Err(Failure::InvalidBinding)
        } else {
            Ok(())
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum Artifact {
    Candidate,
    Prepared,
    Intent,
    Observation,
    Receipt,
}

impl Artifact {
    pub fn leaf(self) -> &'static str {
        match self {
            Self::Candidate => "candidate.bin",
            Self::Prepared => "prepared.record",
            Self::Intent => "intent.record",
            Self::Observation => "observation.record",
            Self::Receipt => "receipt.record",
        }
    }
}

/// Required actual effects/checks. Success means that operation completed on the
/// retained objects; a profile string or saved Boolean cannot implement success.
/// No method may reacquire a lost continuous guard or rebase a captured snapshot.
pub(crate) trait Backend {
    fn profile(&self) -> &'static str;
    fn implementation(&self) -> &'static str;
    fn preflight(&mut self, output: &str) -> Result<Binding, Failure>;
    fn create_root(&mut self) -> Result<Binding, Failure>;
    fn create(&mut self, artifact: Artifact, bytes: &[u8]) -> Result<Binding, Failure>;
    fn check(&mut self, phase: Phase, bindings: &[Binding]) -> Result<(), Failure>;
    fn flush_file(&mut self, artifact: Artifact) -> Result<(), Failure>;
    fn flush_root(&mut self) -> Result<(), Failure>;
    fn flush_parent(&mut self) -> Result<(), Failure>;
    /// Called only once, after publication_possible becomes permanently true.
    fn publish(&mut self, output: &str) -> Result<(), Failure>;
    /// Retain full exact bindings outside the transaction before release. Any
    /// failed/uncertain save prevents continuation; old history is never erased.
    fn caller_release(&mut self, bindings: &[Binding]) -> Result<(), Failure>;
    fn checked_context(&mut self, bindings: &[Binding]) -> Result<(), Failure>;
    /// Must export while guards remain held; lost response is uncertainty.
    fn export_terminal(&mut self, bindings: &[Binding]) -> Result<(), Failure>;
    /// Retains actual live results independently of transaction-file claims.
    /// Called before executor return while all continuous guards remain held.
    fn retain_live_evidence(&mut self, _evidence: &LiveEvidence) {}
}

struct Attempt {
    phase: Phase,
    possible: bool,
    release_possible: bool,
    retained: bool,
    charged: u64,
    evidence: LiveEvidence,
    acknowledged_bindings: Vec<Binding>,
}

impl Attempt {
    fn result(&self, failure: Option<Failure>, complete: bool, admitted: bool) -> UnitResult {
        let status = if complete {
            if admitted {
                Status::Committed
            } else {
                Status::Refused
            }
        } else if self.possible {
            Status::RecoveryRequired
        } else {
            match failure {
                Some(Failure::Cancelled) => Status::CancelledBeforePublish,
                Some(Failure::Conflict | Failure::InvalidBinding) => Status::Conflict,
                Some(
                    Failure::BackendIo
                    | Failure::SourceIo
                    | Failure::ShortSource
                    | Failure::OverlongSource
                    | Failure::Ambiguous,
                ) => Status::FailedBeforePublish,
                _ => Status::Refused,
            }
        };
        UnitResult {
            status,
            phase: self.phase,
            failure,
            publication_possible: self.possible,
            release_possible: self.release_possible,
            retained_material: self.retained,
            pending_cleanup: self.retained,
            charged_bytes: self.charged,
            protocol_complete: complete,
        }
    }

    fn step<T: SuccessfulEffect>(
        &mut self,
        phase: Phase,
        cancel: &Cancellation,
        effect: impl FnOnce() -> Result<T, Failure>,
    ) -> Result<T, Failure> {
        self.phase = phase;
        if cancel.is_requested() {
            return Err(Failure::Cancelled);
        }
        let value = effect()?;
        if let Some(binding) = value.binding() {
            capture(&mut self.acknowledged_bindings, binding.clone())?;
        }
        if phase != Phase::SourceRead {
            self.evidence.acknowledgements.push(LiveAcknowledgement {
                phase,
                target: LiveEvidence::target(phase),
                bindings: self.acknowledged_bindings.clone(),
            });
        }
        Ok(value)
    }
}

fn field(out: &mut Vec<u8>, value: &[u8]) -> Result<(), Failure> {
    let len = u32::try_from(value.len()).map_err(|_| Failure::RecordTooLarge)?;
    let total = out
        .len()
        .checked_add(4)
        .and_then(|n| n.checked_add(value.len()))
        .ok_or(Failure::LengthOverflow)?;
    if total > MAX_RECORD_BYTES as usize {
        return Err(Failure::RecordTooLarge);
    }
    out.extend_from_slice(&len.to_le_bytes());
    out.extend_from_slice(value);
    Ok(())
}

/// Exact length-prefixed records bind only previous actual objects and successful
/// phases. No record contains its own future identity or flush assertion.
fn record(
    kind: Artifact,
    request: &ValidatedCandidate<'_>,
    backend: &impl Backend,
    bindings: &[Binding],
    phases: &[Phase],
) -> Result<Vec<u8>, Failure> {
    let mut bytes = Vec::new();
    for value in [
        PROTOCOL,
        backend.profile(),
        backend.implementation(),
        request.operation,
        request.format_revision,
        request.output.0,
        kind.leaf(),
    ] {
        field(&mut bytes, value.as_bytes())?;
    }
    field(&mut bytes, &request.planned_len.to_le_bytes())?;
    for binding in bindings {
        binding.validate()?;
        field(&mut bytes, &binding.identity)?;
        field(&mut bytes, &binding.facts)?;
    }
    // Versioned protocol enum names are diagnostic; advancement uses actual
    // successful method calls in this process, never record decoding.
    for phase in phases {
        field(&mut bytes, format!("{phase:?}").as_bytes())?;
    }
    Ok(bytes)
}

fn capture(bindings: &mut Vec<Binding>, binding: Binding) -> Result<(), Failure> {
    binding.validate()?;
    if bindings.iter().any(|old| old.identity == binding.identity) {
        return Err(Failure::InvalidBinding);
    }
    bindings.push(binding);
    Ok(())
}

pub(crate) fn execute(
    backend: &mut impl Backend,
    request: ValidatedCandidate<'_>,
    budget: &mut LogicalBudget,
    cancel: &Cancellation,
) -> UnitResult {
    execute_inner(backend, request, budget, cancel, Admission::Unqualified)
}

/// The format caller resolves a no-op before constructing a publication request.
/// None is an explicit bypass, never an inference from candidate byte equality.
pub(crate) fn execute_resolved(
    backend: &mut impl Backend,
    request: Option<ValidatedCandidate<'_>>,
    budget: &mut LogicalBudget,
    cancel: &Cancellation,
) -> UnitResult {
    match request {
        Some(request) => execute(backend, request, budget, cancel),
        None => UnitResult {
            status: Status::Unchanged,
            phase: Phase::Preflight,
            failure: None,
            publication_possible: false,
            release_possible: false,
            retained_material: false,
            pending_cleanup: false,
            charged_bytes: 0,
            protocol_complete: false,
        },
    }
}

/// Exact authored-test capability. This type and constructor do not exist in a
/// production build; #0176 must supply a separately reviewed admission path.
#[cfg(test)]
pub(crate) struct TestAdmission {
    profile: &'static str,
    implementation: &'static str,
}

enum Admission {
    Unqualified,
    #[cfg(test)]
    Authored(TestAdmission),
}

impl Admission {
    fn accepts(&self, _backend: &impl Backend) -> bool {
        match self {
            Self::Unqualified => false,
            #[cfg(test)]
            Self::Authored(admission) => {
                admission.profile == _backend.profile()
                    && admission.implementation == _backend.implementation()
            }
        }
    }
}

#[cfg(test)]
impl TestAdmission {
    pub(crate) fn exact(backend: &impl Backend) -> Self {
        Self {
            profile: backend.profile(),
            implementation: backend.implementation(),
        }
    }
}

#[cfg(test)]
pub(crate) fn execute_test_admitted(
    backend: &mut impl Backend,
    request: ValidatedCandidate<'_>,
    budget: &mut LogicalBudget,
    cancel: &Cancellation,
    admission: TestAdmission,
) -> UnitResult {
    execute_inner(
        backend,
        request,
        budget,
        cancel,
        Admission::Authored(admission),
    )
}

fn execute_inner(
    backend: &mut impl Backend,
    request: ValidatedCandidate<'_>,
    budget: &mut LogicalBudget,
    cancel: &Cancellation,
    admission: Admission,
) -> UnitResult {
    let admitted = admission.accepts(backend);
    let mut attempt = Attempt {
        phase: Phase::Preflight,
        possible: false,
        release_possible: false,
        retained: false,
        charged: 0,
        evidence: LiveEvidence {
            protocol: PROTOCOL,
            profile: backend.profile(),
            implementation: backend.implementation(),
            // Refused diagnostics must not copy any unvalidated caller text.
            // Populate these only after borrowed bounds and budget admission.
            operation: String::new(),
            format_revision: String::new(),
            output: String::new(),
            candidate_len: request.planned_len,
            acknowledgements: Vec::new(),
        },
        acknowledged_bindings: Vec::new(),
    };
    let mut bindings = Vec::new();
    let mut phases = Vec::new();
    let run = (|| -> Result<(), Failure> {
        if request.operation.is_empty()
            || request.operation.len() > 256
            || request.format_revision.is_empty()
            || request.format_revision.len() > 256
            || request.output.0.is_empty()
            || request.output.0.len() > 255
            || request.output.0.contains(['/', '\\', ':'])
            || [".", ".."].contains(&request.output.0)
            || [
                Artifact::Candidate,
                Artifact::Prepared,
                Artifact::Intent,
                Artifact::Observation,
                Artifact::Receipt,
            ]
            .iter()
            .any(|a| a.leaf().eq_ignore_ascii_case(request.output.0))
        {
            return Err(Failure::InvalidBinding);
        }
        if request.planned_len > request.max_len {
            return Err(Failure::CandidateTooLarge);
        }
        let capacity = usize::try_from(request.planned_len).map_err(|_| Failure::LengthOverflow)?;
        // Full planned construction bound, including all records and at most
        // four caller-state captures, is charged before allocation/effects.
        attempt.charged = budget.reserve_unit(request.planned_len)?;
        attempt.evidence.operation = request.operation.into();
        attempt.evidence.format_revision = request.format_revision.into();
        attempt.evidence.output = request.output.0.into();
        capture(
            &mut bindings,
            attempt.step(Phase::Preflight, cancel, || {
                backend.preflight(request.output.0)
            })?,
        )?;
        let mut candidate = Vec::new();
        candidate
            .try_reserve_exact(capacity)
            .map_err(|_| Failure::CandidateTooLarge)?;
        let mut buffer = [0u8; 16 * 1024];
        let mut remaining = request.planned_len;
        while remaining > 0 {
            let want = usize::try_from(remaining.min(buffer.len() as u64))
                .map_err(|_| Failure::LengthOverflow)?;
            let count = attempt.step(Phase::SourceRead, cancel, || {
                request
                    .source
                    .read(&mut buffer[..want])
                    .map_err(|_| Failure::SourceIo)
            })?;
            if count == 0 {
                return Err(Failure::ShortSource);
            }
            candidate.extend_from_slice(&buffer[..count]);
            remaining -= count as u64;
        }
        let extra = attempt.step(Phase::SourceRead, cancel, || {
            request
                .source
                .read(&mut buffer[..1])
                .map_err(|_| Failure::SourceIo)
        })?;
        if extra != 0 {
            return Err(Failure::OverlongSource);
        }
        // A create error may leave partial owned material: retain conservatively.
        if cancel.is_requested() {
            return Err(Failure::Cancelled);
        }
        attempt.retained = true;
        capture(
            &mut bindings,
            attempt.step(Phase::RootCreated, cancel, || backend.create_root())?,
        )?;
        attempt.step(Phase::RootFlushed, cancel, || backend.flush_root())?;
        attempt.step(Phase::ParentFlushed, cancel, || backend.flush_parent())?;
        capture(
            &mut bindings,
            attempt.step(Phase::CandidateCreated, cancel, || {
                backend.create(Artifact::Candidate, &candidate)
            })?,
        )?;
        attempt.step(Phase::CandidateChecked, cancel, || {
            backend.check(Phase::CandidateChecked, &bindings)
        })?;
        attempt.step(Phase::CandidateFlushed, cancel, || {
            backend.flush_file(Artifact::Candidate)
        })?;
        attempt.step(Phase::CandidateParentFlushed, cancel, || {
            backend.flush_root()
        })?;
        phases.extend([
            Phase::RootFlushed,
            Phase::ParentFlushed,
            Phase::CandidateChecked,
            Phase::CandidateFlushed,
            Phase::CandidateParentFlushed,
        ]);
        for (kind, created, checked, flushed, parent) in [
            (
                Artifact::Prepared,
                Phase::PreparedCreated,
                Phase::PreparedChecked,
                Phase::PreparedFlushed,
                Phase::PreparedParentFlushed,
            ),
            (
                Artifact::Intent,
                Phase::IntentCreated,
                Phase::IntentChecked,
                Phase::IntentFlushed,
                Phase::IntentParentFlushed,
            ),
        ] {
            let bytes = record(kind, &request, backend, &bindings, &phases)?;
            capture(
                &mut bindings,
                attempt.step(created, cancel, || backend.create(kind, &bytes))?,
            )?;
            attempt.step(checked, cancel, || backend.check(checked, &bindings))?;
            attempt.step(flushed, cancel, || backend.flush_file(kind))?;
            attempt.step(parent, cancel, || backend.flush_root())?;
            phases.extend([created, checked, flushed, parent]);
        }
        if cancel.is_requested() {
            return Err(Failure::Cancelled);
        }
        attempt.release_possible = true;
        attempt.step(Phase::CallerRelease, cancel, || {
            backend.caller_release(&bindings)
        })?;
        attempt.step(Phase::Prepublication, cancel, || {
            backend.check(Phase::Prepublication, &bindings)
        })?;
        // Cancellation here can still report no publication. Set possible before
        // entering the native call, including errors with lost responses.
        attempt.phase = Phase::Publish;
        if cancel.is_requested() {
            return Err(Failure::Cancelled);
        }
        attempt.possible = true;
        attempt.step(Phase::Publish, cancel, || backend.publish(request.output.0))?;
        attempt.step(Phase::Installed, cancel, || {
            backend.check(Phase::Installed, &bindings)
        })?;
        attempt.step(Phase::InstalledFlushed, cancel, || {
            backend.flush_file(Artifact::Candidate)
        })?;
        attempt.step(Phase::InstalledParentFlushed, cancel, || {
            backend.flush_root()
        })?;
        attempt.step(Phase::InstalledRechecked, cancel, || {
            backend.check(Phase::InstalledRechecked, &bindings)
        })?;
        phases.extend([
            Phase::CallerRelease,
            Phase::Prepublication,
            Phase::Publish,
            Phase::Installed,
            Phase::InstalledFlushed,
            Phase::InstalledParentFlushed,
            Phase::InstalledRechecked,
        ]);
        for (kind, created, checked, flushed, parent) in [
            (
                Artifact::Observation,
                Phase::ObservationCreated,
                Phase::ObservationChecked,
                Phase::ObservationFlushed,
                Phase::ObservationParentFlushed,
            ),
            (
                Artifact::Receipt,
                Phase::ReceiptCreated,
                Phase::ReceiptChecked,
                Phase::ReceiptFlushed,
                Phase::ReceiptParentFlushed,
            ),
        ] {
            let bytes = record(kind, &request, backend, &bindings, &phases)?;
            capture(
                &mut bindings,
                attempt.step(created, cancel, || backend.create(kind, &bytes))?,
            )?;
            attempt.step(checked, cancel, || backend.check(checked, &bindings))?;
            attempt.step(flushed, cancel, || backend.flush_file(kind))?;
            if kind == Artifact::Receipt {
                attempt.step(Phase::ReceiptFileChecked, cancel, || {
                    backend.check(Phase::ReceiptFileChecked, &bindings)
                })?;
            }
            attempt.step(parent, cancel, || backend.flush_root())?;
            if kind == Artifact::Receipt {
                attempt.step(Phase::ReceiptParentChecked, cancel, || {
                    backend.check(Phase::ReceiptParentChecked, &bindings)
                })?;
            }
            phases.extend([created, checked, flushed, parent]);
        }
        attempt.step(Phase::CheckedContext, cancel, || {
            backend.checked_context(&bindings)
        })?;
        attempt.step(Phase::Final, cancel, || {
            backend.check(Phase::Final, &bindings)
        })?;
        attempt.step(Phase::TerminalExport, cancel, || {
            backend.export_terminal(&bindings)
        })?;
        if !attempt.evidence.complete(&bindings) {
            return Err(Failure::InvalidBinding);
        }
        Ok(())
    })();
    backend.retain_live_evidence(&attempt.evidence);
    match run {
        Ok(()) => attempt.result(None, true, admitted),
        Err(error) => attempt.result(Some(error), false, false),
    }
}

#[cfg(test)]
mod tests;
