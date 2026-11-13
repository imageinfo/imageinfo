//! Explicit pure-data-v1 requests over immutable caller-selected observations.

mod expression;
mod native;
mod number;
mod request;

use std::{
    collections::{BTreeMap, BTreeSet},
    fmt,
    sync::Arc,
};

use expression::{Comparison, Node, Predicate, PredicateKind, View};
pub use number::ExactNumber;

const FIELD_BYTES: usize = 1_024;
const MAX_PREDICATE_VISITS: usize = 128;
const MAX_BOOLEAN_VISITS: usize = 256;

/// Immutable selector and built-in declarations for one exact registry revision.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Registry(Arc<RegistryData>);

#[derive(Debug, Eq, PartialEq)]
struct RegistryData {
    revision: String,
    native: bool,
    selectors: BTreeSet<String>,
    builtin_names: BTreeSet<String>,
    builtin_expanded_names: BTreeSet<(String, String)>,
}

impl Registry {
    /// Supply canonical selectors and built-in collision identities explicitly.
    pub fn new(
        revision: impl Into<String>,
        selectors: impl IntoIterator<Item = impl Into<String>>,
        builtin_names: impl IntoIterator<Item = impl Into<String>>,
        builtin_expanded_names: impl IntoIterator<Item = (impl Into<String>, impl Into<String>)>,
    ) -> Result<Self, CompileError> {
        let revision = revision.into();
        if !request::valid_revision(&revision) {
            return Err(CompileError::Registry);
        }
        let mut data = RegistryData {
            revision,
            native: false,
            selectors: BTreeSet::new(),
            builtin_names: BTreeSet::new(),
            builtin_expanded_names: BTreeSet::new(),
        };
        for selector in selectors {
            let selector = selector.into();
            if !request::bounded_nonempty(&selector) || !data.selectors.insert(selector) {
                return Err(CompileError::Registry);
            }
        }
        for name in builtin_names {
            let name = name.into();
            if !request::bounded_nonempty(&name) || !data.builtin_names.insert(name) {
                return Err(CompileError::Registry);
            }
        }
        for (namespace, local_name) in builtin_expanded_names {
            let (namespace, local_name) = (namespace.into(), local_name.into());
            if !request::valid_namespace(&namespace)
                || !request::bounded_nonempty(&local_name)
                || !data.builtin_expanded_names.insert((namespace, local_name))
            {
                return Err(CompileError::Registry);
            }
        }
        Ok(Self(Arc::new(data)))
    }

    pub fn revision(&self) -> &str {
        &self.0.revision
    }
}

/// A scalar as supplied by a caller's observation or a compiled literal.
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum Scalar {
    String(String),
    Number(ExactNumber),
    Boolean(bool),
    Null,
}

/// A scalar interpretation carried by a declaration.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ScalarType {
    String,
    Number,
    Integer,
    Boolean,
    Null,
}

/// Retained data declaration. This declares no occurrence or conversion.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct XmpDefinition {
    pub name: String,
    pub namespace: String,
    pub local_name: String,
    pub scalar_type: ScalarType,
    pub provenance: String,
    pub revision: String,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Coverage {
    Complete,
    Incomplete,
}

/// One eligible retained occurrence. `None` represents an unavailable view.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Occurrence {
    pub raw: Option<Scalar>,
    pub normalized: Option<Scalar>,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SelectorObservation {
    pub coverage: Coverage,
    pub occurrences: Vec<Occurrence>,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ObservationError {
    UnknownSelector,
    DuplicateSelector,
}

impl fmt::Display for ObservationError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(formatter, "invalid filter observation: {self:?}")
    }
}

impl std::error::Error for ObservationError {}

/// One input's explicit observations. Unspecified selectors have incomplete coverage.
#[derive(Clone, Debug)]
pub struct Observations {
    registry: Registry,
    selectors: BTreeMap<String, SelectorObservation>,
}

impl Observations {
    pub fn new(registry: &Registry) -> Self {
        Self {
            registry: registry.clone(),
            selectors: BTreeMap::new(),
        }
    }

    pub fn insert(
        &mut self,
        selector: &str,
        observation: SelectorObservation,
    ) -> Result<(), ObservationError> {
        if !self.registry.0.selectors.contains(selector) {
            return Err(ObservationError::UnknownSelector);
        }
        if self.selectors.contains_key(selector) {
            return Err(ObservationError::DuplicateSelector);
        }
        self.selectors.insert(selector.to_owned(), observation);
        Ok(())
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum CompileError {
    RequestBytes,
    Utf8,
    Bom,
    Json {
        line: usize,
        column: usize,
    },
    Version,
    Registry,
    RegistryMismatch,
    DeclarationCount {
        group: &'static str,
    },
    Declaration {
        group: &'static str,
        index: usize,
        kind: DeclarationError,
    },
    Expression {
        offset: usize,
        kind: ExpressionError,
    },
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum DeclarationError {
    InvalidShape,
    InvalidName,
    NameCollision,
    InvalidSelector,
    InvalidScalar,
    TypeMismatch,
    InvalidDefinition,
    ExpandedNameCollision,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ExpressionError {
    Bytes,
    Tokens,
    Nesting,
    Predicates,
    Syntax,
    String,
    Number,
    UnknownSelector,
    UnknownAlias,
    UnknownParameter,
}

impl fmt::Display for CompileError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(formatter, "invalid pure-data-v1 request: {self:?}")
    }
}

impl std::error::Error for CompileError {}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Truth {
    True,
    False,
    Unknown,
}

impl Truth {
    fn negate(self) -> Self {
        match self {
            Self::True => Self::False,
            Self::False => Self::True,
            Self::Unknown => Self::Unknown,
        }
    }
}

impl From<bool> for Truth {
    fn from(value: bool) -> Self {
        if value { Self::True } else { Self::False }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum IssueKind {
    RegistryMismatch,
    IncompleteCoverage,
    AmbiguousOccurrence,
    MissingOccurrence,
    UnavailableView,
    TypeMismatch,
    UnsupportedOrdering,
    BudgetExhausted,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Issue {
    pub selector: Option<String>,
    /// Byte offset in the decoded filter expression, when attributable to a node.
    pub expression_offset: Option<usize>,
    pub kind: IssueKind,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Evaluation {
    pub truth: Truth,
    /// Issues from visited branches in evaluation order.
    pub issues: Vec<Issue>,
}

impl Evaluation {
    fn registry_mismatch() -> Self {
        Self {
            truth: Truth::Unknown,
            issues: vec![Issue {
                selector: None,
                expression_offset: None,
                kind: IssueKind::RegistryMismatch,
            }],
        }
    }
}

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub enum UnknownPolicy {
    #[default]
    Fail,
    Continue,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum BatchStatus {
    Complete,
    Partial,
    Failed,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct BatchEvaluation {
    pub status: BatchStatus,
    /// Input ordinals in caller order, after applying the unknown policy.
    pub selected: Vec<usize>,
    /// Owned evaluations in caller order, including false and unknown inputs.
    pub evaluations: Vec<Evaluation>,
}

/// An owned, fully preflighted request for one explicit registry.
#[derive(Debug)]
pub struct CompiledFilter {
    registry: Registry,
    definitions: Vec<XmpDefinition>,
    expression: Node,
}

/// Compile an explicit strict UTF-8 pure-data-v1 JSON request.
pub fn compile(input: &[u8], registry: &Registry) -> Result<CompiledFilter, CompileError> {
    request::compile(input, registry)
}

impl CompiledFilter {
    pub fn registry_revision(&self) -> &str {
        self.registry.revision()
    }

    pub fn definitions(&self) -> &[XmpDefinition] {
        &self.definitions
    }

    pub fn evaluate(&self, observations: &Observations) -> Evaluation {
        if !Arc::ptr_eq(&self.registry.0, &observations.registry.0)
            && self.registry != observations.registry
        {
            return Evaluation::registry_mismatch();
        }
        self.evaluate_with(|selector| observations.selectors.get(selector))
    }

    pub fn evaluate_batch<'a>(
        &self,
        observations: impl IntoIterator<Item = &'a Observations>,
        policy: UnknownPolicy,
    ) -> BatchEvaluation {
        let evaluations: Vec<_> = observations
            .into_iter()
            .map(|input| self.evaluate(input))
            .collect();
        let has_unknown = evaluations
            .iter()
            .any(|input| input.truth == Truth::Unknown);
        let mut selected: Vec<_> = evaluations
            .iter()
            .enumerate()
            .filter_map(|(index, input)| (input.truth == Truth::True).then_some(index))
            .collect();
        let status = if !has_unknown {
            BatchStatus::Complete
        } else if policy == UnknownPolicy::Continue && !selected.is_empty() {
            BatchStatus::Partial
        } else {
            selected.clear();
            BatchStatus::Failed
        };
        BatchEvaluation {
            status,
            selected,
            evaluations,
        }
    }

    fn evaluate_with<'a>(
        &self,
        observe: impl FnMut(&str) -> Option<&'a SelectorObservation>,
    ) -> Evaluation {
        let mut evaluator = Evaluator {
            observe,
            issues: Vec::new(),
            predicates: 0,
            booleans: 0,
        };
        let truth = evaluator.visit(&self.expression).unwrap_or(Truth::Unknown);
        Evaluation {
            truth,
            issues: evaluator.issues,
        }
    }
}

struct Evaluator<F> {
    observe: F,
    issues: Vec<Issue>,
    predicates: usize,
    booleans: usize,
}

impl<'a, F: FnMut(&str) -> Option<&'a SelectorObservation>> Evaluator<F> {
    fn visit(&mut self, node: &Node) -> Result<Truth, ()> {
        if let Node::Predicate(predicate) = node {
            self.predicates += 1;
            if self.predicates > MAX_PREDICATE_VISITS {
                self.issues
                    .push(predicate.issue(IssueKind::BudgetExhausted));
                return Err(());
            }
            let observed = (self.observe)(&predicate.selector);
            return Ok(
                evaluate_predicate(predicate, observed).unwrap_or_else(|kind| {
                    self.issues.push(predicate.issue(kind));
                    Truth::Unknown
                }),
            );
        }

        self.booleans += 1;
        if self.booleans > MAX_BOOLEAN_VISITS {
            self.issues.push(Issue {
                selector: None,
                expression_offset: Some(node.offset()),
                kind: IssueKind::BudgetExhausted,
            });
            return Err(());
        }
        match node {
            Node::Not(_, operand) => Ok(self.visit(operand)?.negate()),
            Node::And(_, left, right) => self.visit_pair(left, right, Truth::False, Truth::True),
            Node::Or(_, left, right) => self.visit_pair(left, right, Truth::True, Truth::False),
            Node::Predicate(_) => unreachable!(),
        }
    }

    fn visit_pair(
        &mut self,
        left: &Node,
        right: &Node,
        short_circuit: Truth,
        identity: Truth,
    ) -> Result<Truth, ()> {
        let left = self.visit(left)?;
        if left == short_circuit {
            return Ok(left);
        }
        let right = self.visit(right)?;
        Ok(if left == identity || right == short_circuit {
            right
        } else {
            left
        })
    }
}

fn evaluate_predicate(
    predicate: &Predicate,
    observed: Option<&SelectorObservation>,
) -> Result<Truth, IssueKind> {
    let complete = observed.is_some_and(|value| value.coverage == Coverage::Complete);
    let occurrences = observed.map_or(&[][..], |value| value.occurrences.as_slice());
    match &predicate.kind {
        PredicateKind::Exists | PredicateKind::Absent => {
            let present = if !occurrences.is_empty() {
                true
            } else if complete {
                false
            } else {
                return Err(IssueKind::IncompleteCoverage);
            };
            Ok((present == matches!(predicate.kind, PredicateKind::Exists)).into())
        }
        PredicateKind::Value {
            view,
            comparison,
            literal,
        } => {
            if !complete {
                return Err(IssueKind::IncompleteCoverage);
            }
            let occurrence = match occurrences {
                [occurrence] => occurrence,
                [] => return Err(IssueKind::MissingOccurrence),
                _ => return Err(IssueKind::AmbiguousOccurrence),
            };
            let selected = match view {
                View::Raw => &occurrence.raw,
                View::Normalized => &occurrence.normalized,
            };
            compare(
                selected.as_ref().ok_or(IssueKind::UnavailableView)?,
                *comparison,
                literal,
            )
        }
    }
}

fn compare(left: &Scalar, comparison: Comparison, right: &Scalar) -> Result<Truth, IssueKind> {
    use std::cmp::Ordering;
    let ordering = match (left, right) {
        (Scalar::String(left), Scalar::String(right)) => left.cmp(right),
        (Scalar::Number(left), Scalar::Number(right)) => left.cmp(right),
        (Scalar::Boolean(left), Scalar::Boolean(right)) if comparison.is_equality() => {
            left.cmp(right)
        }
        (Scalar::Null, Scalar::Null) if comparison.is_equality() => Ordering::Equal,
        (Scalar::Boolean(_), Scalar::Boolean(_)) | (Scalar::Null, Scalar::Null) => {
            return Err(IssueKind::UnsupportedOrdering);
        }
        _ => return Err(IssueKind::TypeMismatch),
    };
    Ok(comparison.test(ordering).into())
}
