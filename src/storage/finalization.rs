//! Explicit current-caller completion of an already installed unit. No replay,
//! rename, copy, replacement, cleanup or production profile admission exists here.

use super::custody::CurrentBindings;
use super::runtime::{LiveEvidence, PROTOCOL};
use super::{Failure, Phase};

/// Creator-retained actual progress, never decoded from transaction files.
/// Moving this value into one attempt prevents an implicit retry after failure.
pub(crate) struct PriorProof {
    expected: CurrentBindings,
    evidence: LiveEvidence,
}
impl PriorProof {
    pub(super) fn from_actual(
        expected: CurrentBindings,
        evidence: LiveEvidence,
    ) -> Result<Self, Failure> {
        if !evidence.valid_prefix(expected.object_bindings())
            || !evidence
                .acknowledgements
                .iter()
                .any(|ack| ack.phase == Phase::ObservationCreated)
            || evidence.protocol != PROTOCOL
            || evidence.profile != super::inspection::PROFILE
            || evidence.implementation != super::inspection::IMPLEMENTATION
        {
            return Err(Failure::CallerHistory);
        }
        Ok(Self { expected, evidence })
    }
    pub(crate) fn bindings(&self) -> &CurrentBindings {
        &self.expected
    }
    pub(super) fn terminal(&self) -> bool {
        self.evidence.complete(self.expected.object_bindings())
    }
}

#[cfg(windows)]
mod native {
    use super::*;
    use crate::storage::custody::{ActionAuthority, RestartAction};
    use crate::storage::inspection::native::{binding, directory_matches, snapshot_length};
    use crate::storage::inspection::{InspectionSpec, ORDER, PRIOR_PHASES, parse};
    use crate::storage::runtime::{Artifact, Binding, field};
    use crate::storage::{Cancellation, LogicalBudget, MAX_RECORD_BYTES, Status, UnitResult};
    use imageinfo_windows_storage::{
        FinalizationFile, FinalizationRoot, GuardedSource, MAX_ARTIFACT_BYTES,
    };
    use std::{ffi::OsString, path::Path};

    pub(crate) struct CompletionContext {
        pub attempt: String,
        pub current: CurrentBindings,
        /// Fresh actual calls only, under this attempt and exact object revision.
        acknowledgements: Vec<(Phase, usize)>,
        /// Independent original progress links this new attempt to the old unit.
        prior: PriorProof,
    }
    impl CompletionContext {
        pub(crate) fn bindings(&self) -> &CurrentBindings {
            &self.current
        }
        pub(in crate::storage) fn complete(&self) -> bool {
            let missing = self.prior.expected.object_bindings().len() == 6;
            let expected: Vec<_> = [
                Phase::Installed,
                Phase::InstalledFlushed,
                Phase::InstalledParentFlushed,
                Phase::ParentFlushed,
                Phase::InstalledRechecked,
                Phase::ObservationChecked,
                Phase::ObservationFlushed,
                Phase::ObservationParentFlushed,
                Phase::ReceiptCreated,
                Phase::ReceiptChecked,
                Phase::ReceiptFlushed,
                Phase::ReceiptFileChecked,
                Phase::ReceiptParentFlushed,
                Phase::ReceiptParentChecked,
                Phase::CheckedContext,
                Phase::Final,
                Phase::TerminalExport,
            ]
            .into_iter()
            .filter(|phase| {
                missing
                    || !matches!(
                        phase,
                        Phase::ObservationChecked
                            | Phase::ObservationFlushed
                            | Phase::ObservationParentFlushed
                            | Phase::ReceiptCreated
                    )
            })
            .collect();
            self.prior
                .evidence
                .valid_prefix(self.prior.expected.object_bindings())
                && self.current.extends(&self.prior.expected)
                && self.acknowledgements.len() == expected.len()
                && self
                    .acknowledgements
                    .iter()
                    .zip(expected)
                    .all(|((phase, binding), expected)| {
                        *phase == expected
                            && self.current.object_bindings().len() == 7
                            && *binding
                                == if missing
                                    && !matches!(
                                        phase,
                                        Phase::ReceiptCreated
                                            | Phase::ReceiptChecked
                                            | Phase::ReceiptFlushed
                                            | Phase::ReceiptFileChecked
                                            | Phase::ReceiptParentFlushed
                                            | Phase::ReceiptParentChecked
                                            | Phase::CheckedContext
                                            | Phase::Final
                                            | Phase::TerminalExport
                                    )
                                {
                                    6
                                } else {
                                    7
                                }
                    })
        }
    }
    pub(crate) struct FinalizationResult {
        pub result: UnitResult,
        pub context: Option<CompletionContext>,
    }
    struct Held {
        root: FinalizationRoot,
        source: GuardedSource,
        files: Vec<FinalizationFile>,
        records: Vec<(Artifact, Vec<u8>)>,
        bindings: Vec<Binding>,
        parent: Binding,
        names: Vec<OsString>,
        failed: bool,
    }
    fn io_failure(_: std::io::Error) -> Failure {
        Failure::BackendIo
    }
    impl Held {
        fn open(
            source: &Path,
            root_path: &Path,
            spec: &InspectionSpec<'_>,
        ) -> Result<Self, Failure> {
            imageinfo_windows_storage::validate_leaf(spec.output).map_err(io_failure)?;
            if spec.candidate_len > MAX_ARTIFACT_BYTES
                || std::iter::once(Artifact::Candidate)
                    .chain(ORDER)
                    .any(|kind| kind.leaf().eq_ignore_ascii_case(spec.output))
            {
                return Err(Failure::InvalidBinding);
            }
            let root = FinalizationRoot::open(root_path).map_err(io_failure)?;
            let names = root.entries().map_err(io_failure)?;
            let count = ORDER
                .iter()
                .take_while(|kind| names.iter().any(|name| name == kind.leaf()))
                .count();
            let mut required = vec![OsString::from(spec.output)];
            required.extend(
                ORDER[..count]
                    .iter()
                    .map(|kind| OsString::from(kind.leaf())),
            );
            required.sort();
            if !(3..=4).contains(&count) || names != required {
                return Err(Failure::Conflict);
            }
            let mut source = GuardedSource::open(source, MAX_ARTIFACT_BYTES).map_err(io_failure)?;
            let source_bytes = source.read_exact_bytes().map_err(io_failure)?;
            let source_binding = binding(source.snapshot(), Some(&source_bytes));
            let mut output =
                FinalizationFile::open(&root_path.join(spec.output), MAX_ARTIFACT_BYTES)
                    .map_err(io_failure)?;
            let output_bytes = output.read_exact_bytes().map_err(io_failure)?;
            if output_bytes.len() as u64 != spec.candidate_len {
                return Err(Failure::Conflict);
            }
            let output_binding = binding(output.snapshot(), Some(&output_bytes));
            let mut files = vec![output];
            let mut records = Vec::new();
            for kind in &ORDER[..count] {
                let mut file =
                    FinalizationFile::open(&root_path.join(kind.leaf()), MAX_RECORD_BYTES)
                        .map_err(io_failure)?;
                records.push((*kind, file.read_exact_bytes().map_err(io_failure)?));
                files.push(file);
            }
            let first = parse(&records[0].1, Artifact::Prepared, spec)
                .map_err(|_| Failure::InvalidBinding)?;
            let length = snapshot_length(first[1].1).map_err(|_| Failure::InvalidBinding)?;
            let historic_parent = first[1].1[length..]
                .strip_prefix(b"held-containing-parent-v1\0")
                .ok_or(Failure::InvalidBinding)?;
            directory_matches(root.snapshot(), &first[1].1[..length])
                .map_err(|_| Failure::Conflict)?;
            directory_matches(root.parent_snapshot(), historic_parent)
                .map_err(|_| Failure::Conflict)?;
            let mut root_binding = binding(root.snapshot(), None);
            if root_binding.identity != first[1].0 {
                return Err(Failure::Conflict);
            }
            root_binding.facts = first[1].1.to_vec();
            let mut parent = binding(root.parent_snapshot(), None);
            parent.facts = historic_parent.to_vec();
            let mut bindings = vec![source_binding, root_binding, output_binding];
            for (index, (kind, bytes)) in records.iter().enumerate() {
                let parsed = parse(bytes, *kind, spec).map_err(|_| Failure::InvalidBinding)?;
                if parsed.iter().zip(&bindings).any(|((id, facts), expected)| {
                    *id != expected.identity || *facts != expected.facts
                }) {
                    return Err(Failure::Conflict);
                }
                bindings.push(binding(files[index + 1].snapshot(), Some(bytes)));
            }
            let mut held = Self {
                root,
                source,
                files,
                records,
                bindings,
                parent,
                names,
                failed: false,
            };
            held.check()?;
            Ok(held)
        }
        fn capture(&self, spec: &InspectionSpec<'_>) -> Result<CurrentBindings, Failure> {
            CurrentBindings::capture(
                spec.operation,
                super::super::inspection::PROFILE,
                super::super::inspection::IMPLEMENTATION,
                spec.output,
                &self.parent,
                &self.bindings,
                &self.records,
                true,
            )
            .map_err(|_| Failure::RecordTooLarge)
        }
        fn check(&mut self) -> Result<(), Failure> {
            if self.failed {
                return Err(Failure::Conflict);
            }
            let result = (|| {
                self.source.check().map_err(io_failure)?;
                self.root.check().map_err(io_failure)?;
                for file in &mut self.files {
                    file.check().map_err(io_failure)?;
                    if file.snapshot().owner_dacl != self.root.snapshot().owner_dacl {
                        return Err(Failure::Conflict);
                    }
                }
                if self.root.entries().map_err(io_failure)? != self.names {
                    return Err(Failure::Conflict);
                }
                Ok(())
            })();
            self.failed |= result.is_err();
            result
        }
        fn receipt(&mut self, spec: &InspectionSpec<'_>) -> Result<(), Failure> {
            if self.records.len() != 3 {
                return Err(Failure::Conflict);
            }
            self.check()?;
            let mut bytes = Vec::new();
            for value in [
                PROTOCOL,
                super::super::inspection::PROFILE,
                super::super::inspection::IMPLEMENTATION,
                spec.operation,
                spec.format_revision,
                spec.output,
                Artifact::Receipt.leaf(),
            ] {
                field(&mut bytes, value.as_bytes())?;
            }
            field(&mut bytes, &spec.candidate_len.to_le_bytes())?;
            for expected in &self.bindings {
                field(&mut bytes, &expected.identity)?;
                field(&mut bytes, &expected.facts)?;
            }
            for phase in &PRIOR_PHASES[..24] {
                field(&mut bytes, phase.as_bytes())?;
            }
            let file = self.root.create_receipt(&bytes).map_err(io_failure)?;
            self.bindings.push(binding(file.snapshot(), Some(&bytes)));
            self.files.push(file);
            self.records.push((Artifact::Receipt, bytes));
            self.names.push(Artifact::Receipt.leaf().into());
            self.names.sort();
            Ok(())
        }
    }

    /// Trusted callback retains the checked and then terminal context while all
    /// guards are held. Any failed/lost save is recovery-required, never success.
    #[allow(clippy::too_many_arguments)]
    pub(crate) fn finalize(
        source: &Path,
        root: &Path,
        spec: &InspectionSpec<'_>,
        attempt: &str,
        prior: PriorProof,
        authority: ActionAuthority,
        budget: &mut LogicalBudget,
        cancel: &Cancellation,
        save: impl FnMut(Phase, &CompletionContext) -> Result<(), Failure>,
    ) -> FinalizationResult {
        run(
            source,
            root,
            spec,
            attempt,
            prior,
            authority,
            budget,
            cancel,
            save,
            Admission::Unqualified,
            |_, _| Ok(()),
        )
    }

    enum Admission {
        Unqualified,
        #[cfg(test)]
        Authored,
    }
    impl Admission {
        fn accepted(&self) -> bool {
            match self {
                Self::Unqualified => false,
                #[cfg(test)]
                Self::Authored => true,
            }
        }
    }

    #[allow(clippy::too_many_arguments)]
    fn run(
        source: &Path,
        root: &Path,
        spec: &InspectionSpec<'_>,
        attempt: &str,
        prior: PriorProof,
        authority: ActionAuthority,
        budget: &mut LogicalBudget,
        cancel: &Cancellation,
        mut save: impl FnMut(Phase, &CompletionContext) -> Result<(), Failure>,
        admission: Admission,
        mut boundary: impl FnMut(Phase, bool) -> Result<(), Failure>,
    ) -> FinalizationResult {
        let mut phase = Phase::Installed;
        let mut charged = 0;
        let mut context = None;
        let result = (|| {
            if attempt.is_empty()
                || attempt.len() > 256
                || attempt == spec.operation
                || prior.evidence.operation != spec.operation
                || prior.evidence.format_revision != spec.format_revision
                || prior.evidence.output != spec.output
                || prior.evidence.candidate_len != spec.candidate_len
            {
                return Err(Failure::CallerHistory);
            }
            let amount = LogicalBudget::unit_charge(spec.candidate_len)?;
            budget.reserve_construction(amount)?;
            charged = amount;
            let mut held = Held::open(source, root, spec)?;
            let current = held.capture(spec)?;
            prior
                .expected
                .compare(&current)
                .map_err(|_| Failure::CallerHistory)?;
            authority
                .check(RestartAction::FinalizeExisting, &current)
                .map_err(|_| Failure::CallerHistory)?;
            if !prior.evidence.valid_prefix(&held.bindings) {
                return Err(Failure::CallerHistory);
            }
            let mut acks = Vec::new();
            let missing_receipt = held.records.len() == 3;
            let mut retained_prior = Some(prior);
            for step in [
                Phase::Installed,
                Phase::InstalledFlushed,
                Phase::InstalledParentFlushed,
                Phase::ParentFlushed,
                Phase::InstalledRechecked,
                Phase::ObservationChecked,
                Phase::ObservationFlushed,
                Phase::ObservationParentFlushed,
                Phase::ReceiptCreated,
                Phase::ReceiptChecked,
                Phase::ReceiptFlushed,
                Phase::ReceiptFileChecked,
                Phase::ReceiptParentFlushed,
                Phase::ReceiptParentChecked,
                Phase::CheckedContext,
                Phase::Final,
                Phase::TerminalExport,
            ] {
                // Existing receipts are never recreated or rewritten; their
                // prior observation already exists and is checked with the set.
                if !missing_receipt
                    && matches!(
                        step,
                        Phase::ObservationChecked
                            | Phase::ObservationFlushed
                            | Phase::ObservationParentFlushed
                            | Phase::ReceiptCreated
                    )
                {
                    continue;
                }
                phase = step;
                if cancel.is_requested() {
                    return Err(Failure::Cancelled);
                }
                boundary(step, false)?;
                authority
                    .check(RestartAction::FinalizeExisting, &current)
                    .map_err(|_| Failure::CallerHistory)?;
                match step {
                    Phase::InstalledFlushed => held.files[0].flush().map_err(io_failure)?,
                    Phase::InstalledParentFlushed
                    | Phase::ObservationParentFlushed
                    | Phase::ReceiptParentFlushed => held.root.flush().map_err(io_failure)?,
                    Phase::ParentFlushed => held.root.flush_parent().map_err(io_failure)?,
                    Phase::ObservationFlushed => held.files[3].flush().map_err(io_failure)?,
                    Phase::ReceiptCreated => held.receipt(spec)?,
                    Phase::ReceiptFlushed => held.files[4].flush().map_err(io_failure)?,
                    Phase::CheckedContext => {
                        held.check()?;
                        context = Some(CompletionContext {
                            attempt: attempt.into(),
                            current: held.capture(spec)?,
                            acknowledgements: acks.clone(),
                            prior: retained_prior.take().ok_or(Failure::CallerHistory)?,
                        });
                        save(step, context.as_ref().unwrap())?;
                    }
                    Phase::TerminalExport => {
                        held.check()?;
                        let current = context.as_mut().ok_or(Failure::CallerHistory)?;
                        current.acknowledgements = acks.clone();
                        save(step, current)?;
                    }
                    _ => held.check()?,
                }
                boundary(step, true)?;
                authority
                    .check(RestartAction::FinalizeExisting, &current)
                    .map_err(|_| Failure::CallerHistory)?;
                // A revision is the immutable prefix of context.current: held
                // bindings only append the newly exclusive-created receipt.
                acks.push((step, held.bindings.len()));
            }
            // The terminal callback's successful return is a separate live fact.
            context.as_mut().unwrap().acknowledgements = acks;
            Ok(())
        })();
        let complete = result.is_ok();
        if !complete {
            context = None;
        }
        FinalizationResult {
            result: UnitResult {
                status: if complete {
                    if admission.accepted() {
                        Status::Committed
                    } else {
                        Status::Refused
                    }
                } else {
                    Status::RecoveryRequired
                },
                phase,
                failure: result.err(),
                publication_possible: true,
                release_possible: true,
                retained_material: true,
                pending_cleanup: true,
                charged_bytes: charged,
                protocol_complete: complete,
            },
            context,
        }
    }

    /// Recognize independently retained terminal completion with read-only #0170
    /// guards; no new acknowledgement or storage effect is manufactured.
    pub(crate) fn recognize(
        source: &Path,
        root: &Path,
        spec: &InspectionSpec<'_>,
        prior: PriorProof,
        authority: ActionAuthority,
    ) -> Result<super::super::inspection::Survivor, Failure> {
        if !prior.evidence.complete(prior.expected.object_bindings()) {
            return Err(Failure::CallerHistory);
        }
        let mut inspection = super::super::inspection::Inspection::collect(source, root, spec)
            .map_err(|_| Failure::Conflict)?;
        prior
            .expected
            .compare(inspection.bindings())
            .map_err(|_| Failure::CallerHistory)?;
        inspection
            .classify(RestartAction::RecognizeCompletion, authority)
            .map_err(|_| Failure::CallerHistory)
    }

    /// A completed fresh attempt is independently recognizable, too. The old
    /// receipt alone cannot construct this context or its terminal live fact.
    pub(crate) fn recognize_finalized(
        source: &Path,
        root: &Path,
        spec: &InspectionSpec<'_>,
        context: CompletionContext,
        authority: ActionAuthority,
    ) -> Result<super::super::inspection::Survivor, Failure> {
        if !context.complete() {
            return Err(Failure::CallerHistory);
        }
        let mut inspection = super::super::inspection::Inspection::collect(source, root, spec)
            .map_err(|_| Failure::Conflict)?;
        context
            .current
            .compare(inspection.bindings())
            .map_err(|_| Failure::CallerHistory)?;
        inspection
            .classify(RestartAction::RecognizeCompletion, authority)
            .map_err(|_| Failure::CallerHistory)
    }

    #[cfg(test)]
    mod tests;
}
#[cfg(windows)]
#[allow(unused_imports)]
pub(crate) use native::{
    CompletionContext, FinalizationResult, finalize, recognize, recognize_finalized,
};
