//! Fixed dependent two-unit orchestration. Unit adapters own admission, guards,
//! receipt verification and finalization; this module owns no storage backend.
//! No parser, record-selected code, automatic continuation or rollback exists.
use super::custody::ActionAuthority;
use super::runtime::{Binding, field};
use super::{Cancellation, Failure, LogicalBudget, MAX_RECORD_BYTES, Status, UnitResult};

const PROTOCOL: &[u8] = b"imageinfo-two-unit-group-v1";
const RENAME_PROTOCOL: &[u8] = b"imageinfo-two-unit-live-observed-renames-v1";

#[derive(Clone, Copy, PartialEq, Eq)]
enum Completion {
    QualifiedPublication,
    ObservedRename,
}

impl Completion {
    fn protocol(self) -> &'static [u8] {
        match self {
            Self::QualifiedPublication => PROTOCOL,
            Self::ObservedRename => RENAME_PROTOCOL,
        }
    }

    fn accepts(self, status: MemberStatus) -> bool {
        status
            == match self {
                Self::QualifiedPublication => MemberStatus::Committed,
                Self::ObservedRename => MemberStatus::ObservedRenameComplete,
            }
    }
}

/// Immutable values captured by the format caller before either member changes.
/// The borrow lasts for the entire run and every explicit resume.
#[derive(Clone, Copy)]
pub(crate) struct Intent<'a> {
    pub identity: &'a [u8],
    pub original: &'a [u8],
    pub units: [UnitIntent<'a>; 2],
}

#[derive(Clone, Copy)]
pub(crate) struct UnitIntent<'a> {
    pub identity: &'a [u8],
    pub operation: &'a str,
    pub revision: &'a str,
    pub profile: &'a str,
    pub implementation: &'a str,
    pub source: &'a Binding,
    pub parent: &'a Binding,
    pub target: Option<&'a Binding>,
    pub output: &'a str,
    pub candidate_len: u64,
}

/// A native adapter may return this only after its independently admitted
/// qualified receipt and fresh held identity/content/property checks succeed.
/// This is an internal typed handoff, never an imported receipt assertion.
#[derive(Debug, PartialEq, Eq)]
pub(crate) struct QualifiedReceipt {
    pub installed: Binding,
    pub receipt: Binding,
}

#[derive(Debug)]
pub(crate) struct Execution {
    pub result: UnitResult,
    pub receipt: Option<QualifiedReceipt>,
    /// Exact retained artifacts, including failed cleanup; never discarded when
    /// the other member fails. At most the single-unit protocol's seven objects.
    pub artifacts: Vec<Binding>,
}

/// A successful live same-object rename observation. The selected adapter must
/// retain its original guard and verify current bytes, properties and exact name
/// after every planned step. This is neither a receipt nor a durable commitment.
/// It is intentionally separate from UnitResult and has no restart constructor.
#[derive(Debug)]
pub(crate) struct ObservedRename {
    pub installed: Binding,
    pub artifacts: Vec<Binding>,
    pub charged_bytes: u64,
}

#[derive(Debug)]
pub(crate) enum RenameExecution {
    Complete(ObservedRename),
    /// Includes every retained object and possible effect after any failed or
    /// uncertain call. Even a supplied publication receipt cannot complete a
    /// live rename member through this variant.
    Failed(Execution),
}

#[derive(Debug)]
pub(crate) struct PreparationFailure {
    pub refusal: Refusal,
    pub artifacts: Vec<Binding>,
}

#[derive(Debug)]
pub(crate) struct ManifestFailure {
    pub refusal: Refusal,
    pub retained: Option<Binding>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum Refusal {
    InvalidIntent,
    Alias,
    AdapterUnavailable,
    MissingAuthority,
    ReceiptConflict,
    LiveOnly,
    Unit(Failure),
}

impl From<Failure> for Refusal {
    fn from(value: Failure) -> Self {
        Self::Unit(value)
    }
}

/// Two concrete, statically selected implementations only. An implementation
/// must preserve acquired guards across staging/publication and must check the
/// original snapshot against current bindings rather than read edited values.
/// ExecuteAuthority is an adapter-owned live capability, with no record importer;
/// preflight AND execute must check it for revocation/staleness. Restart actions
/// use the selected shared current-caller ActionAuthority and fresh bindings.
/// Admission is per unit; this interface cannot enable a profile or operation.
pub(crate) trait UnitAdapter {
    type ExecuteAuthority;
    type Staged;

    /// Static implementation opt-in, checked before staging or effects. Existing
    /// publication adapters cannot accidentally enter the live rename path.
    fn supports_observed_rename(&self) -> bool {
        false
    }

    fn preflight(
        &mut self,
        unit: UnitIntent<'_>,
        original: &[u8],
        authority: &Self::ExecuteAuthority,
    ) -> Result<(), Refusal>;
    fn acquire_guard(&mut self, binding: &Binding) -> Result<(), Refusal>;
    fn stage(
        &mut self,
        unit: UnitIntent<'_>,
        original: &[u8],
        budget: LogicalBudget,
        cancel: &Cancellation,
    ) -> Result<Self::Staged, PreparationFailure>;
    fn staged_artifacts(staged: &Self::Staged) -> &[Binding];
    /// Unit 1 retains the ONE private manifest through its existing record
    /// storage. Success includes exact-byte verification and required flushes,
    /// under its guards, before either member's caller release/publication.
    fn retain_manifest(&mut self, bytes: &[u8]) -> Result<Binding, ManifestFailure>;
    fn check_manifest(&mut self, binding: &Binding, bytes: &[u8]) -> Result<(), Refusal>;
    fn execute(
        &mut self,
        staged: Self::Staged,
        unit: UnitIntent<'_>,
        original: &[u8],
        authority: Self::ExecuteAuthority,
        cancel: &Cancellation,
    ) -> Execution;
    /// Selected only by start_observed_renames. Existing publication adapters
    /// retain their execute and qualified receipt contracts without alteration.
    fn execute_observed_rename(
        &mut self,
        staged: Self::Staged,
        unit: UnitIntent<'_>,
        original: &[u8],
        authority: Self::ExecuteAuthority,
        cancel: &Cancellation,
    ) -> RenameExecution {
        RenameExecution::Failed(self.execute(staged, unit, original, authority, cancel))
    }
    /// Validate current authority and fresh qualified receipt against the exact
    /// old witness. No publication/reapplication is permitted by this method.
    fn verify_completed(
        &mut self,
        _unit: UnitIntent<'_>,
        _original: &[u8],
        _receipt: &QualifiedReceipt,
        _authority: ActionAuthority,
    ) -> Result<QualifiedReceipt, Refusal> {
        Err(Refusal::AdapterUnavailable)
    }
    /// Independently admitted unit inspection/finalization only. An unavailable
    /// replacement/finalizer is an explicit refusal, never execution fallback.
    /// Returned charged_bytes is the adapter-owned cumulative unit total,
    /// including any finalizer constructions charged by its retained ledger.
    /// Failed/uncertain responses must still return every actual retained object.
    /// Err is permitted only before actions or retained constructions; once an
    /// action starts, return its Execution even on failure/uncertainty.
    fn inspect_finalize(
        &mut self,
        _unit: UnitIntent<'_>,
        _original: &[u8],
        _prior: &Execution,
        _authority: ActionAuthority,
    ) -> Result<Execution, Refusal> {
        Err(Refusal::AdapterUnavailable)
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum MemberStatus {
    Unattempted,
    Refused,
    CancelledBeforePublish,
    Committed,
    ObservedRenameComplete,
    RecoveryRequired,
}

#[derive(Debug)]
pub(crate) struct Member {
    status: MemberStatus,
    execution: Option<Execution>,
    observed_rename: Option<ObservedRename>,
    refusal: Option<Refusal>,
    preparation_artifacts: Vec<Binding>,
}

impl Member {
    fn new() -> Self {
        Self {
            status: MemberStatus::Unattempted,
            execution: None,
            observed_rename: None,
            refusal: None,
            preparation_artifacts: Vec::new(),
        }
    }

    pub(crate) fn status(&self) -> MemberStatus {
        self.status
    }
    pub(crate) fn execution(&self) -> Option<&Execution> {
        self.execution.as_ref()
    }
    pub(crate) fn observed_rename(&self) -> Option<&ObservedRename> {
        self.observed_rename.as_ref()
    }
    pub(crate) fn refusal(&self) -> Option<Refusal> {
        self.refusal
    }
    pub(crate) fn preparation_artifacts(&self) -> &[Binding] {
        &self.preparation_artifacts
    }

    fn refuse(&mut self, why: Refusal) {
        self.refusal = Some(why);
        if self.execution.is_none() && self.observed_rename.is_none() {
            self.status = if why == Refusal::Unit(Failure::Cancelled) {
                MemberStatus::CancelledBeforePublish
            } else {
                MemberStatus::Refused
            };
        }
    }

    fn capture(&mut self, execution: Execution) {
        let result = &execution.result;
        self.status = if result.status == Status::Committed
            && result.protocol_complete
            && execution.receipt.is_some()
            && valid_execution(&execution)
        {
            MemberStatus::Committed
        } else if result.publication_possible
            || matches!(result.status, Status::RecoveryRequired | Status::Committed)
        {
            MemberStatus::RecoveryRequired
        } else if result.status == Status::CancelledBeforePublish {
            MemberStatus::CancelledBeforePublish
        } else {
            MemberStatus::Refused
        };
        self.refusal = None;
        self.execution = Some(execution);
    }

    fn capture_rename(&mut self, outcome: RenameExecution, source: &Binding) {
        match outcome {
            RenameExecution::Complete(observed) => {
                let valid = valid_binding(&observed.installed)
                    && observed.installed.identity == source.identity
                    && valid_artifacts(&observed.artifacts)
                    && observed.artifacts.contains(&observed.installed);
                self.status = if valid {
                    MemberStatus::ObservedRenameComplete
                } else {
                    MemberStatus::RecoveryRequired
                };
                self.refusal = (!valid).then_some(Failure::InvalidBinding.into());
                self.observed_rename = Some(observed);
            }
            RenameExecution::Failed(mut execution) => {
                if execution.result.status == Status::Committed {
                    execution.result.status = Status::RecoveryRequired;
                }
                execution.result.protocol_complete = false;
                self.capture(execution);
            }
        }
    }
}

/// In-memory provenance: created only by start, not Clone or deserializable.
/// A member's effects survive every later refusal. There is no group Committed
/// boolean or self-attesting group receipt. The manifest grants no authority.
pub(crate) struct Run<'a, S, T> {
    intent: Intent<'a>,
    completion: Completion,
    manifest: Vec<u8>,
    manifest_binding: Option<Binding>,
    manifest_failed: bool,
    members: [Member; 2],
    budgets: [Option<LogicalBudget>; 2],
    staged_a: Option<S>,
    staged_b: Option<T>,
}

impl<S, T> Run<'_, S, T> {
    pub(crate) fn members(&self) -> &[Member; 2] {
        &self.members
    }
    pub(crate) fn manifest(&self) -> &[u8] {
        &self.manifest
    }
    pub(crate) fn manifest_binding(&self) -> Option<&Binding> {
        self.manifest_binding.as_ref()
    }
}

fn valid_binding(value: &Binding) -> bool {
    !value.identity.is_empty()
        && value.identity.len() <= 256
        && !value.facts.is_empty()
        && value.facts.len() <= 8192
}

fn valid_artifacts(values: &[Binding]) -> bool {
    values.len() <= 7
        && values.iter().all(valid_binding)
        && values.iter().enumerate().all(|(index, value)| {
            !values[..index]
                .iter()
                .any(|old| old.identity == value.identity)
        })
}

fn valid_execution(value: &Execution) -> bool {
    valid_artifacts(&value.artifacts)
        && value.receipt.as_ref().is_some_and(|r| {
            valid_binding(&r.installed)
                && valid_binding(&r.receipt)
                && r.installed.identity != r.receipt.identity
                && value.artifacts.contains(&r.installed)
                && value.artifacts.contains(&r.receipt)
        })
}

fn fields(
    intent: Intent<'_>,
    completion: Completion,
    mut put: impl FnMut(&[u8]) -> Result<(), Failure>,
) -> Result<(), Failure> {
    put(completion.protocol())?;
    put(intent.identity)?;
    put(intent.original)?;
    // Declared order is encoded; it is never selected from a record at runtime.
    for unit in intent.units {
        for value in [
            unit.identity,
            unit.operation.as_bytes(),
            unit.revision.as_bytes(),
            unit.profile.as_bytes(),
            unit.implementation.as_bytes(),
            unit.output.as_bytes(),
        ] {
            put(value)?;
        }
        put(&unit.candidate_len.to_le_bytes())?;
        for binding in [Some(unit.source), Some(unit.parent), unit.target] {
            match binding {
                Some(binding) => {
                    put(&binding.identity)?;
                    put(&binding.facts)?;
                }
                None => {
                    put(&[])?;
                    put(&[])?;
                }
            }
        }
    }
    Ok(())
}

fn manifest_len(intent: Intent<'_>) -> Result<u64, Refusal> {
    manifest_len_for(intent, Completion::QualifiedPublication)
}

fn manifest_len_for(intent: Intent<'_>, completion: Completion) -> Result<u64, Refusal> {
    if intent.identity.is_empty()
        || intent.identity.len() > 256
        || intent.original.is_empty()
        || intent.units[0].identity == intent.units[1].identity
    {
        return Err(Refusal::InvalidIntent);
    }
    for unit in intent.units {
        if unit.identity.is_empty()
            || unit.identity.len() > 256
            || [
                unit.operation,
                unit.revision,
                unit.profile,
                unit.implementation,
            ]
            .iter()
            .any(|text| text.is_empty() || text.len() > 256)
            || unit.output.is_empty()
            || unit.output.len() > 255
            || unit.output.contains(['/', '\\', ':'])
            || [".", ".."].contains(&unit.output)
            || !valid_binding(unit.source)
            || !valid_binding(unit.parent)
            || unit.target.is_some_and(|binding| !valid_binding(binding))
        {
            return Err(Refusal::InvalidIntent);
        }
    }
    let mut length = 0u64;
    fields(intent, completion, |bytes| {
        length = length
            .checked_add(4)
            .and_then(|n| n.checked_add(bytes.len() as u64))
            .ok_or(Failure::LengthOverflow)?;
        if length > MAX_RECORD_BYTES {
            return Err(Failure::RecordTooLarge);
        }
        Ok(())
    })?;
    Ok(length)
}

fn aliases(intent: Intent<'_>) -> bool {
    let [a, b] = intent.units;
    if a.parent.identity == b.parent.identity && a.output.eq_ignore_ascii_case(b.output) {
        return true;
    }
    for target in [a.target, b.target].into_iter().flatten() {
        if [a.source, b.source, a.parent, b.parent]
            .iter()
            .any(|b| b.identity == target.identity)
        {
            return true;
        }
    }
    if a.target
        .zip(b.target)
        .is_some_and(|(a, b)| a.identity == b.identity)
    {
        return true;
    }
    // Intentional shared source/parent is allowed only with identical frozen facts.
    for left in [a.source, a.parent] {
        for right in [b.source, b.parent] {
            if left.identity == right.identity && left != right {
                return true;
            }
        }
    }
    false
}

fn guards<A: UnitAdapter, B: UnitAdapter>(
    intent: Intent<'_>,
    a: &mut A,
    b: &mut B,
) -> Result<(), Refusal> {
    let [x, y] = intent.units;
    let mut order = [
        (0, x.source),
        (0, x.parent),
        (0, x.target.unwrap_or(x.parent)),
        (1, y.source),
        (1, y.parent),
        (1, y.target.unwrap_or(y.parent)),
    ];
    order.sort_by(|(ai, a), (bi, b)| a.identity.cmp(&b.identity).then(ai.cmp(bi)));
    let mut previous: Option<(usize, &Binding)> = None;
    for (unit, binding) in order {
        if previous == Some((unit, binding)) {
            continue;
        }
        if unit == 0 {
            a.acquire_guard(binding)?;
        } else {
            b.acquire_guard(binding)?;
        }
        previous = Some((unit, binding));
    }
    Ok(())
}

/// No unit adapter is called, and no owned manifest is constructed, until BOTH
/// unit allowances plus this exact bounded manifest have been charged atomically.
pub(crate) fn start<'a, A: UnitAdapter, B: UnitAdapter>(
    intent: Intent<'a>,
    a: &mut A,
    b: &mut B,
    authorities: (Option<A::ExecuteAuthority>, Option<B::ExecuteAuthority>),
    budget: &mut LogicalBudget,
    cancel: &Cancellation,
) -> Result<Run<'a, A::Staged, B::Staged>, Refusal> {
    start_with_completion(
        intent,
        a,
        b,
        authorities,
        budget,
        cancel,
        Completion::QualifiedPublication,
    )
}

/// The same fixed executor and ordering, explicitly selected for two live
/// same-object rename observations. Its manifest uses a distinct domain. No
/// member gains committed status, receipt authority or any resume path.
pub(crate) fn start_observed_renames<'a, A: UnitAdapter, B: UnitAdapter>(
    intent: Intent<'a>,
    a: &mut A,
    b: &mut B,
    authorities: (Option<A::ExecuteAuthority>, Option<B::ExecuteAuthority>),
    budget: &mut LogicalBudget,
    cancel: &Cancellation,
) -> Result<Run<'a, A::Staged, B::Staged>, Refusal> {
    if !a.supports_observed_rename() || !b.supports_observed_rename() {
        return Err(Refusal::AdapterUnavailable);
    }
    start_with_completion(
        intent,
        a,
        b,
        authorities,
        budget,
        cancel,
        Completion::ObservedRename,
    )
}

fn start_with_completion<'a, A: UnitAdapter, B: UnitAdapter>(
    intent: Intent<'a>,
    a: &mut A,
    b: &mut B,
    authorities: (Option<A::ExecuteAuthority>, Option<B::ExecuteAuthority>),
    budget: &mut LogicalBudget,
    cancel: &Cancellation,
    completion: Completion,
) -> Result<Run<'a, A::Staged, B::Staged>, Refusal> {
    let length = manifest_len_for(intent, completion)?;
    let [first, second] = budget.reserve_group(intent.units.map(|u| u.candidate_len), length)?;
    let mut manifest = Vec::with_capacity(length as usize);
    fields(intent, completion, |bytes| field(&mut manifest, bytes))?;
    let mut run = Run {
        intent,
        completion,
        manifest,
        manifest_binding: None,
        manifest_failed: false,
        members: [Member::new(), Member::new()],
        budgets: [Some(first), Some(second)],
        staged_a: None,
        staged_b: None,
    };
    if aliases(intent) {
        run.members[0].refuse(Refusal::Alias);
        return Ok(run);
    }
    continue_unattempted(&mut run, a, b, authorities, cancel);
    Ok(run)
}

fn continue_unattempted<A: UnitAdapter, B: UnitAdapter>(
    run: &mut Run<'_, A::Staged, B::Staged>,
    a: &mut A,
    b: &mut B,
    authorities: (Option<A::ExecuteAuthority>, Option<B::ExecuteAuthority>),
    cancel: &Cancellation,
) {
    if run.manifest_failed {
        run.members[0].refuse(Failure::Ambiguous.into());
        return;
    }
    if aliases(run.intent) {
        run.members[0].refuse(Refusal::Alias);
        return;
    }
    let (first, second) = authorities;
    let needs = run
        .members
        .each_ref()
        .map(|m| !run.completion.accepts(m.status));
    let checked = (|| -> Result<(), (usize, Refusal)> {
        if cancel.is_requested() {
            return Err((usize::from(!needs[0]), Failure::Cancelled.into()));
        }
        if needs[0] {
            a.preflight(
                run.intent.units[0],
                run.intent.original,
                first.as_ref().ok_or((0, Refusal::MissingAuthority))?,
            )
            .map_err(|e| (0, e))?;
        }
        if needs[1] {
            b.preflight(
                run.intent.units[1],
                run.intent.original,
                second.as_ref().ok_or((1, Refusal::MissingAuthority))?,
            )
            .map_err(|e| (1, e))?;
        }
        guards(run.intent, a, b).map_err(|e| (0, e))?;
        Ok(())
    })();
    if let Err((index, why)) = checked {
        run.members[index].refuse(why);
        return;
    }
    // Both candidates/recovery material must be staged before the first effect.
    if needs[0] && cancel.is_requested() {
        run.members[0].refuse(Failure::Cancelled.into());
        return;
    }
    if needs[0] && run.staged_a.is_none() {
        let Some(budget) = run.budgets[0].take() else {
            run.members[0].refuse(Failure::BudgetExhausted.into());
            return;
        };
        match a.stage(run.intent.units[0], run.intent.original, budget, cancel) {
            Ok(staged) => {
                if !valid_artifacts(A::staged_artifacts(&staged)) {
                    run.members[0].refuse(Failure::InvalidBinding.into());
                    return;
                }
                run.members[0].preparation_artifacts = A::staged_artifacts(&staged).to_vec();
                run.staged_a = Some(staged);
            }
            Err(e) => {
                run.members[0].preparation_artifacts = e.artifacts;
                run.members[0].refuse(e.refusal);
                return;
            }
        }
    }
    if needs[1] && cancel.is_requested() {
        run.members[1].refuse(Failure::Cancelled.into());
        return;
    }
    if needs[1] && run.staged_b.is_none() {
        let Some(budget) = run.budgets[1].take() else {
            run.members[1].refuse(Failure::BudgetExhausted.into());
            return;
        };
        match b.stage(run.intent.units[1], run.intent.original, budget, cancel) {
            Ok(staged) => {
                if !valid_artifacts(B::staged_artifacts(&staged)) {
                    run.members[1].refuse(Failure::InvalidBinding.into());
                    return;
                }
                run.members[1].preparation_artifacts = B::staged_artifacts(&staged).to_vec();
                run.staged_b = Some(staged);
            }
            Err(e) => {
                run.members[1].preparation_artifacts = e.artifacts;
                run.members[1].refuse(e.refusal);
                return;
            }
        }
    }
    if cancel.is_requested() {
        run.members[usize::from(!needs[0])].refuse(Failure::Cancelled.into());
        return;
    }
    if run.manifest_binding.is_none() {
        match a.retain_manifest(&run.manifest) {
            Ok(binding) if valid_binding(&binding) => run.manifest_binding = Some(binding),
            Ok(binding) => {
                run.manifest_binding = Some(binding);
                run.manifest_failed = true;
                run.members[0].refuse(Failure::InvalidBinding.into());
                return;
            }
            Err(e) => {
                run.manifest_binding = e.retained;
                run.manifest_failed = true;
                run.members[0].refuse(e.refusal);
                return;
            }
        }
    }
    if let Some(binding) = &run.manifest_binding
        && let Err(e) = a.check_manifest(binding, &run.manifest)
    {
        run.members[0].refuse(e);
        return;
    }
    if needs[0] && cancel.is_requested() {
        run.members[0].refuse(Failure::Cancelled.into());
        return;
    }
    if let (Some(staged), Some(authority)) = (run.staged_a.take(), first) {
        match run.completion {
            Completion::QualifiedPublication => run.members[0].capture(a.execute(
                staged,
                run.intent.units[0],
                run.intent.original,
                authority,
                cancel,
            )),
            Completion::ObservedRename => run.members[0].capture_rename(
                a.execute_observed_rename(
                    staged,
                    run.intent.units[0],
                    run.intent.original,
                    authority,
                    cancel,
                ),
                run.intent.units[0].source,
            ),
        }
        if !run.completion.accepts(run.members[0].status) {
            return;
        }
    }
    if needs[1] && cancel.is_requested() {
        run.members[1].refuse(Failure::Cancelled.into());
        return;
    }
    if needs[1]
        && let Some(binding) = &run.manifest_binding
        && let Err(e) = a.check_manifest(binding, &run.manifest)
    {
        run.members[1].refuse(e);
        return;
    }
    if needs[1] && cancel.is_requested() {
        run.members[1].refuse(Failure::Cancelled.into());
        return;
    }
    if let (Some(staged), Some(authority)) = (run.staged_b.take(), second) {
        match run.completion {
            Completion::QualifiedPublication => run.members[1].capture(b.execute(
                staged,
                run.intent.units[1],
                run.intent.original,
                authority,
                cancel,
            )),
            Completion::ObservedRename => run.members[1].capture_rename(
                b.execute_observed_rename(
                    staged,
                    run.intent.units[1],
                    run.intent.original,
                    authority,
                    cancel,
                ),
                run.intent.units[1].source,
            ),
        }
    }
}

fn select<A: UnitAdapter>(
    member: &mut Member,
    adapter: &mut A,
    unit: UnitIntent<'_>,
    original: &[u8],
    authority: Option<ActionAuthority>,
) -> Result<(), Refusal> {
    match member.status {
        MemberStatus::Committed => {
            let old = member
                .execution
                .as_ref()
                .and_then(|e| e.receipt.as_ref())
                .ok_or(Refusal::ReceiptConflict)?;
            let fresh = adapter.verify_completed(
                unit,
                original,
                old,
                authority.ok_or(Refusal::MissingAuthority)?,
            )?;
            if &fresh != old {
                return Err(Refusal::ReceiptConflict);
            }
            member.refusal = None;
        }
        MemberStatus::RecoveryRequired => {
            let prior = member.execution.as_ref().ok_or(Refusal::ReceiptConflict)?;
            let mut observed = adapter.inspect_finalize(
                unit,
                original,
                prior,
                authority.ok_or(Refusal::MissingAuthority)?,
            )?;
            let qualified = observed.result.status == Status::Committed
                && observed.result.protocol_complete
                && valid_execution(&observed)
                && prior
                    .artifacts
                    .iter()
                    .all(|a| observed.artifacts.contains(a));
            // Finalization is a real unit action: even a refused/uncertain reply
            // can have retained NEW artifacts. Preserve it alongside prior facts,
            // before deciding whether the dependent member may proceed.
            for artifact in &prior.artifacts {
                if !observed.artifacts.contains(artifact) {
                    observed.artifacts.push(artifact.clone());
                }
            }
            observed.result.publication_possible |= prior.result.publication_possible;
            observed.result.release_possible |= prior.result.release_possible;
            observed.result.retained_material |= prior.result.retained_material;
            observed.result.pending_cleanup |= prior.result.pending_cleanup;
            observed.result.charged_bytes = observed
                .result
                .charged_bytes
                .max(prior.result.charged_bytes);
            if !qualified || !valid_execution(&observed) {
                observed.result.status = Status::RecoveryRequired;
                observed.result.protocol_complete = false;
            }
            member.capture(observed);
            if member.status != MemberStatus::Committed {
                return Err(Refusal::ReceiptConflict);
            }
        }
        _ => {}
    }
    Ok(())
}

/// Explicit caller invocation only, on this exact non-importable original run.
/// Completed/uncertain units never receive execute; receipt/authority conflicts
/// terminate selection. Failed staging budgets are never reset or replenished.
pub(crate) fn resume<A: UnitAdapter, B: UnitAdapter>(
    run: &mut Run<'_, A::Staged, B::Staged>,
    a: &mut A,
    b: &mut B,
    restart: (Option<ActionAuthority>, Option<ActionAuthority>),
    execution: (Option<A::ExecuteAuthority>, Option<B::ExecuteAuthority>),
    cancel: &Cancellation,
) {
    if run.completion == Completion::ObservedRename {
        run.members[0].refuse(Refusal::LiveOnly);
        return;
    }
    if cancel.is_requested() {
        return;
    }
    if let Err(e) = select(
        &mut run.members[0],
        a,
        run.intent.units[0],
        run.intent.original,
        restart.0,
    ) {
        run.members[0].refuse(e);
        return;
    }
    if let Err(e) = select(
        &mut run.members[1],
        b,
        run.intent.units[1],
        run.intent.original,
        restart.1,
    ) {
        run.members[1].refuse(e);
        return;
    }
    if run
        .members
        .iter()
        .all(|m| m.status == MemberStatus::Committed)
    {
        return;
    }
    continue_unattempted(run, a, b, execution, cancel);
}

#[cfg(test)]
mod tests;
