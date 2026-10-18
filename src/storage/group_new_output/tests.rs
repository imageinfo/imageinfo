//! Real authored Windows file controls. These exercise the unqualified adapter;
//! no admitted receipt, format permission or positive storage profile is created.
use super::*;
use crate::storage::group::{self, ManifestFailure, PreparationFailure, UnitAdapter, UnitIntent};
use crate::storage::runtime::Binding;
use crate::storage::{Cancellation, Failure, LogicalBudget};
use std::cell::RefCell;
use std::fs;
use std::path::{Path, PathBuf};
use std::rc::Rc;
use std::time::{SystemTime, UNIX_EPOCH};

struct NativeFiles {
    directory: PathBuf,
    sources: [PathBuf; 2],
}
impl NativeFiles {
    fn new(label: &str) -> Self {
        let directory = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join(".local")
            .join("storage-group-new-output-tests")
            .join(format!(
                "{label}-{}-{}",
                std::process::id(),
                SystemTime::now()
                    .duration_since(UNIX_EPOCH)
                    .unwrap()
                    .as_nanos()
            ));
        fs::create_dir_all(&directory).unwrap();
        let sources = [
            directory.join("source-a.bin"),
            directory.join("source-b.bin"),
        ];
        for (index, path) in sources.iter().enumerate() {
            fs::write(path, format!("authored original {index}")).unwrap();
        }
        Self { directory, sources }
    }
    fn check_originals(&self) {
        for (index, path) in self.sources.iter().enumerate() {
            assert_eq!(
                fs::read(path).unwrap(),
                format!("authored original {index}").as_bytes()
            );
        }
    }
    fn record(&self, label: &str, result: impl std::fmt::Debug) {
        fs::write(
            self.directory.join(format!("{label}.private.txt")),
            format!("{result:#?}\n"),
        )
        .unwrap();
    }
}

/// Delegates every actual operation. Independent observations occur between
/// adapter calls and never fabricate acknowledgement/binding/admission results.
struct Observed<A> {
    inner: A,
    index: usize,
    trace: Rc<RefCell<Vec<String>>>,
    second_root: PathBuf,
    after_stage: Option<Box<dyn FnOnce()>>,
    before_execute: Option<Box<dyn FnOnce()>>,
}
impl<A: UnitAdapter> UnitAdapter for Observed<A> {
    type ExecuteAuthority = A::ExecuteAuthority;
    type Staged = A::Staged;
    fn preflight(
        &mut self,
        unit: UnitIntent<'_>,
        original: &[u8],
        authority: &Self::ExecuteAuthority,
    ) -> Result<(), group::Refusal> {
        self.trace
            .borrow_mut()
            .push(format!("{} preflight", self.index));
        self.inner.preflight(unit, original, authority)
    }
    fn acquire_guard(&mut self, binding: &Binding) -> Result<(), group::Refusal> {
        self.inner.acquire_guard(binding)
    }
    fn stage(
        &mut self,
        unit: UnitIntent<'_>,
        original: &[u8],
        budget: LogicalBudget,
        cancel: &Cancellation,
    ) -> Result<Self::Staged, PreparationFailure> {
        let result = self.inner.stage(unit, original, budget, cancel);
        self.trace
            .borrow_mut()
            .push(format!("{} staged {}", self.index, result.is_ok()));
        if let Some(effect) = self.after_stage.take() {
            effect();
        }
        result
    }
    fn staged_artifacts(staged: &Self::Staged) -> &[Binding] {
        A::staged_artifacts(staged)
    }
    fn retain_manifest(&mut self, bytes: &[u8]) -> Result<Binding, ManifestFailure> {
        self.trace
            .borrow_mut()
            .push(format!("{} manifest", self.index));
        self.inner.retain_manifest(bytes)
    }
    fn check_manifest(&mut self, binding: &Binding, bytes: &[u8]) -> Result<(), group::Refusal> {
        self.inner.check_manifest(binding, bytes)
    }
    fn execute(
        &mut self,
        staged: Self::Staged,
        unit: UnitIntent<'_>,
        original: &[u8],
        authority: Self::ExecuteAuthority,
        cancel: &Cancellation,
    ) -> group::Execution {
        self.trace
            .borrow_mut()
            .push(format!("{} execute", self.index));
        // This tests real staged material before caller release/publication.
        assert!(self.second_root.join("candidate.bin").is_file());
        assert!(self.second_root.join("prepared.record").is_file());
        assert!(self.second_root.join("intent.record").is_file());
        if let Some(effect) = self.before_execute.take() {
            effect();
        }
        self.inner
            .execute(staged, unit, original, authority, cancel)
    }
}

fn names(root: &Path) -> Vec<String> {
    let mut names: Vec<_> = fs::read_dir(root)
        .unwrap()
        .map(|entry| entry.unwrap().file_name().into_string().unwrap())
        .collect();
    names.sort();
    names
}

#[derive(Clone, Copy, Debug)]
enum Case {
    Normal,
    MissingSecond,
    ShortSecond,
    CancelAfterSecondStage,
    CancelAtContinuation,
    ForeignEntry,
    ManifestCaseAlias,
    ManifestIdentity,
}

fn native_case(case: Case) {
    use crate::storage::runtime::{Backend, ExpectedAbsent, ValidatedCandidate};
    use crate::storage::windows::{WindowsBackend, binding_snapshot};
    use imageinfo_windows_storage::{ExistingRoot, GuardedSource, MAX_ARTIFACT_BYTES, PrivateRoot};
    use std::io::Cursor;

    let files = NativeFiles::new(&format!("{case:?}"));
    let parents = [
        files.directory.join("parent-a"),
        files.directory.join("parent-b"),
    ];
    for parent in &parents {
        drop(PrivateRoot::create(parent).unwrap());
    }
    let roots = [parents[0].join("unit"), parents[1].join("unit")];
    let sources: [Binding; 2] = std::array::from_fn(|index| {
        let mut source = GuardedSource::open(&files.sources[index], MAX_ARTIFACT_BYTES).unwrap();
        let bytes = source.read_exact_bytes().unwrap();
        binding_snapshot(source.snapshot(), Some(&bytes))
    });
    let parent_bindings: [Binding; 2] = std::array::from_fn(|index| {
        let parent = ExistingRoot::open(&parents[index]).unwrap();
        binding_snapshot(parent.snapshot(), None)
    });
    let backend_a = WindowsBackend::new(&files.sources[0], &roots[0]);
    let backend_b = WindowsBackend::new(&files.sources[1], &roots[1]);
    let output = if matches!(case, Case::ManifestCaseAlias) {
        "GROUP.MANIFEST"
    } else {
        "first.bin"
    };
    let candidate = b"authored derivative";
    let units = [0, 1].map(|index| UnitIntent {
        identity: if index == 0 {
            b"first".as_slice()
        } else {
            b"second".as_slice()
        },
        operation: "authored-group-native",
        revision: "authored-v1",
        profile: backend_a.profile(),
        implementation: backend_a.implementation(),
        source: &sources[index],
        parent: &parent_bindings[index],
        target: None,
        output: if index == 0 { output } else { "second.bin" },
        candidate_len: candidate.len() as u64,
    });
    let original = b"authored fixed original input";
    let intent = group::Intent {
        identity: b"authored-group",
        original,
        units,
    };
    let mut bytes_a = Cursor::new(candidate.as_slice());
    let mut bytes_b = Cursor::new(if matches!(case, Case::ShortSecond) {
        b"short".as_slice()
    } else {
        candidate.as_slice()
    });
    let request_a = ValidatedCandidate {
        operation: units[0].operation,
        format_revision: units[0].revision,
        source: &mut bytes_a,
        planned_len: units[0].candidate_len,
        max_len: MAX_ARTIFACT_BYTES,
        output: ExpectedAbsent(units[0].output),
    };
    let request_b = ValidatedCandidate {
        operation: units[1].operation,
        format_revision: units[1].revision,
        source: &mut bytes_b,
        planned_len: units[1].candidate_len,
        max_len: MAX_ARTIFACT_BYTES,
        output: ExpectedAbsent(units[1].output),
    };
    let (a, authority_a) = WindowsUnit::new(backend_a, units[0], original, request_a);
    let (b, authority_b) = WindowsUnit::new(backend_b, units[1], original, request_b);
    let trace = Rc::new(RefCell::new(Vec::new()));
    let cancel = Rc::new(Cancellation::default());
    let mut a = Observed {
        inner: a,
        index: 0,
        trace: trace.clone(),
        second_root: roots[1].clone(),
        after_stage: None,
        before_execute: None,
    };
    let mut b = Observed {
        inner: b,
        index: 1,
        trace: trace.clone(),
        second_root: roots[1].clone(),
        after_stage: None,
        before_execute: None,
    };
    if matches!(case, Case::MissingSecond) {
        fs::remove_file(&files.sources[1]).unwrap();
    }
    if matches!(case, Case::CancelAfterSecondStage) {
        let signal = cancel.clone();
        b.after_stage = Some(Box::new(move || signal.request()));
    }
    if matches!(case, Case::CancelAtContinuation) {
        let signal = cancel.clone();
        a.before_execute = Some(Box::new(move || signal.request()));
    }
    if matches!(case, Case::ForeignEntry) {
        let path = roots[0].join("foreign.bin");
        b.after_stage = Some(Box::new(move || {
            fs::write(path, b"foreign retained").unwrap()
        }));
    }
    if matches!(case, Case::ManifestIdentity) {
        let path = roots[0].join("group.manifest");
        a.before_execute = Some(Box::new(move || {
            // Same bytes cannot replace the creator-held identity or namespace.
            assert!(fs::rename(&path, path.with_extension("moved")).is_err());
            assert!(fs::write(&path, b"foreign replacement").is_err());
        }));
    }
    let mut budget = LogicalBudget::new(4_000_000);
    let run = group::start(
        intent,
        &mut a,
        &mut b,
        (Some(authority_a), Some(authority_b)),
        &mut budget,
        &cancel,
    )
    .unwrap();
    files.record("trace", &*trace.borrow());
    files.record("members", run.members());
    let exact_charge = 2 * LogicalBudget::unit_charge(candidate.len() as u64).unwrap()
        + run.manifest().len() as u64;
    assert_eq!(budget.charged(), exact_charge);
    assert!(
        run.members()
            .iter()
            .all(|m| m.execution().is_none_or(|e| e.receipt.is_none()))
    );
    assert!(!roots[1].join("second.bin").exists());
    assert_ne!(run.members()[1].status(), group::MemberStatus::Committed);
    match case {
        Case::Normal | Case::ManifestIdentity => {
            let events = trace.borrow();
            let staged = events.iter().position(|s| s == "1 staged true").unwrap();
            let executed = events.iter().position(|s| s == "0 execute").unwrap();
            assert!(staged < executed);
            let first = run.members()[0].execution().unwrap();
            assert!(
                first.result.protocol_complete,
                "native unit1 failed: {:?}",
                first.result
            );
            assert_eq!(first.result.status, crate::storage::Status::Refused);
            assert_eq!(first.result.failure, None);
            assert!(first.result.publication_possible && first.result.release_possible);
            assert_eq!(
                first.result.charged_bytes,
                LogicalBudget::unit_charge(candidate.len() as u64).unwrap()
            );
            assert_eq!(first.artifacts.len(), 7);
            assert!(!first.artifacts.contains(run.manifest_binding().unwrap()));
            assert_eq!(run.members()[1].status(), group::MemberStatus::Unattempted);
            assert_eq!(run.members()[1].preparation_artifacts().len(), 5);
            assert_eq!(fs::read(roots[0].join(output)).unwrap(), candidate);
            assert_eq!(
                fs::read(roots[0].join("group.manifest")).unwrap(),
                run.manifest()
            );
            assert!(run.manifest_binding().is_some());
            assert_eq!(names(&roots[0]).len(), 6);
            assert_eq!(
                names(&roots[1]),
                ["candidate.bin", "intent.record", "prepared.record"]
            );
        }
        Case::MissingSecond | Case::ManifestCaseAlias => {
            assert!(run.members().iter().all(|m| m.execution().is_none()));
            assert!(!roots[0].exists() && !roots[1].exists());
            assert!(
                !trace
                    .borrow()
                    .iter()
                    .any(|s| s.contains("staged") || s.contains("execute"))
            );
        }
        Case::ShortSecond => {
            assert!(run.members().iter().all(|m| m.execution().is_none()));
            assert_eq!(
                run.members()[1].refusal(),
                Some(group::Refusal::Unit(Failure::ShortSource))
            );
            assert_eq!(run.members()[0].preparation_artifacts().len(), 5);
            assert!(!roots[0].join(output).exists());
            assert!(!roots[1].exists());
            assert!(fs::write(roots[0].join("candidate.bin"), b"foreign").is_err());
        }
        Case::CancelAtContinuation => {
            let first = run.members()[0].execution().unwrap();
            assert_eq!(
                first.result.status,
                crate::storage::Status::CancelledBeforePublish
            );
            assert_eq!(first.result.failure, Some(Failure::Cancelled));
            assert!(!first.result.publication_possible && !first.result.release_possible);
            assert_eq!(first.artifacts.len(), 5);
            assert!(!roots[0].join(output).exists());
            assert_eq!(run.members()[1].status(), group::MemberStatus::Unattempted);
            assert_eq!(run.members()[1].preparation_artifacts().len(), 5);
            assert!(fs::write(roots[0].join("candidate.bin"), b"foreign").is_err());
        }
        Case::CancelAfterSecondStage | Case::ForeignEntry => {
            assert!(run.members().iter().all(|m| m.execution().is_none()));
            assert!(
                run.members()
                    .iter()
                    .all(|m| m.preparation_artifacts().len() == 5)
            );
            assert!(!roots[0].join(output).exists());
            assert!(fs::write(roots[0].join("candidate.bin"), b"foreign").is_err());
            assert!(fs::rename(&roots[1], parents[1].join("moved-unit")).is_err());
            if matches!(case, Case::ForeignEntry) {
                assert_eq!(
                    fs::read(roots[0].join("foreign.bin")).unwrap(),
                    b"foreign retained"
                );
            }
        }
    }
    if !matches!(case, Case::MissingSecond) {
        files.check_originals();
    }
    if matches!(case, Case::ManifestIdentity) {
        let binding = run.manifest_binding().unwrap();
        a.check_manifest(binding, run.manifest()).unwrap();
        a.check_manifest(binding, run.manifest()).unwrap();
        assert_eq!(budget.charged(), exact_charge);
        let mut wrong_identity = binding.clone();
        wrong_identity.identity.push(0);
        assert!(a.check_manifest(&wrong_identity, run.manifest()).is_err());
    }
    // The adapter, rather than the diagnostic Run, owns continuous native holds.
    drop(run);
    assert_eq!(budget.charged(), exact_charge);
    if roots[0].join("candidate.bin").exists() {
        assert!(fs::write(roots[0].join("candidate.bin"), b"foreign after Run drop").is_err());
    }
    if roots[0].join(output).exists() {
        assert!(fs::write(roots[0].join(output), b"foreign after Run drop").is_err());
    }
    if roots[0].exists() {
        assert!(fs::write(&files.sources[0], b"foreign source after Run drop").is_err());
        assert!(fs::write(&files.sources[1], b"foreign source after Run drop").is_err());
    }
    drop((a, b));
}

#[test]
fn native_both_staged_before_first_release_and_second_unattempted() {
    native_case(Case::Normal);
}
#[test]
fn native_invalid_second_source_prevents_all_publication() {
    native_case(Case::MissingSecond);
}
#[test]
fn native_short_second_retains_first_staging_and_charge() {
    native_case(Case::ShortSecond);
}
#[test]
fn native_cancel_after_staging_retains_both_holds_and_charge() {
    native_case(Case::CancelAfterSecondStage);
}
#[test]
fn native_cancel_at_continuation_retains_both_holds_and_charge() {
    native_case(Case::CancelAtContinuation);
}
#[test]
fn native_foreign_namespace_entry_prevents_release() {
    native_case(Case::ForeignEntry);
}
#[test]
fn native_reserved_manifest_case_alias_refuses_before_effects() {
    native_case(Case::ManifestCaseAlias);
}
#[test]
fn native_manifest_keeps_actual_creator_identity_held() {
    native_case(Case::ManifestIdentity);
}
