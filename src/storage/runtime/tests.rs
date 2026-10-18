use super::*;
use std::collections::BTreeMap;
use std::io::{self, Cursor};

#[derive(Default)]
struct Fake<'a> {
    calls: usize,
    fail_at: Option<usize>,
    fault: Option<Failure>,
    cancel_after: Option<usize>,
    cancel: Option<&'a Cancellation>,
    duplicate: bool,
    empty_binding: bool,
    published: bool,
    creates: BTreeMap<String, Vec<u8>>,
    history: Vec<String>,
    evidence: Option<LiveEvidence>,
    held_owner: Option<std::rc::Rc<()>>,
    outcomes: Vec<(Phase, Option<Failure>)>,
}

impl Fake<'_> {
    fn call(&mut self, label: String) -> Result<(), Failure> {
        self.calls += 1;
        self.history.push(label);
        if self.cancel_after == Some(self.calls) {
            self.cancel.unwrap().request();
        }
        if self.fail_at == Some(self.calls) {
            return Err(self.fault.unwrap_or(Failure::BackendIo));
        }
        Ok(())
    }

    fn binding(&self) -> Binding {
        Binding {
            identity: if self.duplicate {
                vec![42]
            } else {
                self.calls.to_le_bytes().to_vec()
            },
            facts: if self.empty_binding {
                vec![]
            } else {
                self.calls.to_le_bytes().to_vec()
            },
        }
    }
}

impl Backend for Fake<'_> {
    fn profile(&self) -> &'static str {
        "authored-unqualified"
    }
    fn implementation(&self) -> &'static str {
        "deterministic-v1"
    }
    fn preflight(&mut self, _: &str) -> Result<Binding, Failure> {
        self.call("preflight".into())?;
        Ok(self.binding())
    }
    fn create_root(&mut self) -> Result<Binding, Failure> {
        self.call("create-root".into())?;
        Ok(self.binding())
    }
    fn create(&mut self, artifact: Artifact, bytes: &[u8]) -> Result<Binding, Failure> {
        // Partial creates can remain even when the call returns failure.
        self.creates.insert(artifact.leaf().into(), bytes.to_vec());
        self.call(format!("create-{artifact:?}"))?;
        Ok(self.binding())
    }
    fn check(&mut self, phase: Phase, _: &[Binding]) -> Result<(), Failure> {
        self.call(format!("check-{phase:?}"))
    }
    fn flush_file(&mut self, artifact: Artifact) -> Result<(), Failure> {
        self.call(format!("file-{artifact:?}"))
    }
    fn flush_root(&mut self) -> Result<(), Failure> {
        self.call("root-flush".into())
    }
    fn flush_parent(&mut self) -> Result<(), Failure> {
        self.call("parent-flush".into())
    }
    fn publish(&mut self, _: &str) -> Result<(), Failure> {
        self.published = true;
        self.call("publish".into())
    }
    fn caller_release(&mut self, _: &[Binding]) -> Result<(), Failure> {
        self.call("caller-release".into())
    }
    fn checked_context(&mut self, _: &[Binding]) -> Result<(), Failure> {
        self.call("context".into())
    }
    fn export_terminal(&mut self, _: &[Binding]) -> Result<(), Failure> {
        self.call("terminal".into())
    }
    fn retain_live_evidence(&mut self, evidence: &LiveEvidence) {
        self.evidence = Some(evidence.clone());
    }
    fn retain_outcome(&mut self, phase: Phase, failure: Option<Failure>) {
        self.outcomes.push((phase, failure));
    }
}

#[test]
fn complete_predicate_rejects_missing_reordered_reused_or_foreign_acknowledgements() {
    let mut fake = Fake::default();
    let admission = TestAdmission::exact(&fake);
    let mut reader = Cursor::new(b"abc".as_slice());
    let result = execute_test_admitted(
        &mut fake,
        ValidatedCandidate {
            operation: "authored-unit-1",
            format_revision: "authored-bytes-v1",
            source: &mut reader,
            planned_len: 3,
            max_len: 3,
            output: ExpectedAbsent("output.bin"),
        },
        &mut LogicalBudget::new(u64::MAX),
        &Cancellation::default(),
        admission,
    );
    assert_eq!(result.status, Status::Committed);
    let evidence = fake.evidence.unwrap();
    let bindings = evidence.acknowledgements.last().unwrap().bindings.clone();
    assert!(evidence.complete(&bindings));
    let mut wrong_protocol = evidence.clone();
    wrong_protocol.protocol = "foreign-revision";
    assert!(!wrong_protocol.complete(&bindings));
    for index in 0..evidence.acknowledgements.len() {
        let mut missing = evidence.clone();
        missing.acknowledgements.remove(index);
        assert!(!missing.complete(&bindings));
        let mut foreign = evidence.clone();
        foreign.acknowledgements[index].bindings[0].facts.push(99);
        assert!(!foreign.complete(&bindings));
        let mut incomplete_binding = evidence.clone();
        incomplete_binding.acknowledgements[index].bindings.pop();
        assert!(!incomplete_binding.complete(&bindings));
        let mut wrong_target = evidence.clone();
        wrong_target.acknowledgements[index].target = AckTarget::Source;
        if index != 0 {
            assert!(!wrong_target.complete(&bindings));
        }
        if index > 0 {
            let mut replayed = evidence.clone();
            replayed.acknowledgements[index] = replayed.acknowledgements[index - 1].clone();
            assert!(!replayed.complete(&bindings));
            let mut reordered = evidence.clone();
            reordered.acknowledgements.swap(index, index - 1);
            assert!(!reordered.complete(&bindings));
        }
    }
}

#[test]
fn oversized_borrowed_request_fields_are_not_copied_into_refused_evidence() {
    let oversized = "x".repeat(4 * 1024 * 1024);
    for field in 0..3 {
        let mut reader = Cursor::new(b"abc".as_slice());
        let mut fake = Fake::default();
        let mut budget = LogicalBudget::new(u64::MAX);
        let request = ValidatedCandidate {
            operation: if field == 0 { &oversized } else { "authored" },
            format_revision: if field == 1 { &oversized } else { "v1" },
            output: ExpectedAbsent(if field == 2 { &oversized } else { "output.bin" }),
            source: &mut reader,
            planned_len: 3,
            max_len: 3,
        };
        let result = execute(&mut fake, request, &mut budget, &Cancellation::default());
        assert_eq!(result.failure, Some(Failure::InvalidBinding));
        assert_eq!(result.status, Status::Conflict);
        assert_eq!(budget.charged(), 0);
        assert_eq!(reader.position(), 0);
        assert_eq!(fake.calls, 0);
        assert!(fake.creates.is_empty());
        let evidence = fake.evidence.unwrap();
        for text in [
            &evidence.operation,
            &evidence.format_revision,
            &evidence.output,
        ] {
            assert!(text.is_empty());
            assert_eq!(text.capacity(), 0);
        }
        assert!(evidence.acknowledgements.is_empty());
        assert!(!result.publication_possible && !result.retained_material);
    }
    // Even valid bounded identity text is not copied before budget admission.
    let mut reader = Cursor::new(b"abc".as_slice());
    let mut fake = Fake::default();
    let result = execute(
        &mut fake,
        ValidatedCandidate {
            operation: "authored",
            format_revision: "v1",
            output: ExpectedAbsent("output.bin"),
            source: &mut reader,
            planned_len: 3,
            max_len: 3,
        },
        &mut LogicalBudget::new(0),
        &Cancellation::default(),
    );
    assert_eq!(result.failure, Some(Failure::BudgetExhausted));
    assert_eq!(fake.calls, 0);
    let evidence = fake.evidence.unwrap();
    assert!(
        evidence.operation.is_empty()
            && evidence.format_revision.is_empty()
            && evidence.output.is_empty()
    );
}

fn run(
    fake: &mut Fake<'_>,
    bytes: &[u8],
    planned_len: u64,
    budget: &mut LogicalBudget,
    cancel: &Cancellation,
) -> UnitResult {
    let mut reader = Cursor::new(bytes);
    execute(
        fake,
        ValidatedCandidate {
            operation: "authored-unit-1",
            format_revision: "authored-bytes-v1",
            source: &mut reader,
            planned_len,
            max_len: 1024 * 1024,
            output: ExpectedAbsent("output.bin"),
        },
        budget,
        cancel,
    )
}

#[test]
fn ordered_complete_execution_remains_unqualified() {
    let mut fake = Fake::default();
    let result = run(
        &mut fake,
        b"abc",
        3,
        &mut LogicalBudget::new(u64::MAX),
        &Cancellation::default(),
    );
    assert!(result.protocol_complete);
    assert_eq!(result.status, Status::Refused);
    assert!(result.publication_possible && result.retained_material && result.pending_cleanup);
    assert_eq!(fake.creates.len(), 5);
    assert!(
        fake.creates
            .values()
            .all(|v| v.len() <= MAX_RECORD_BYTES as usize)
    );
    let at = |name: &str| fake.history.iter().position(|v| v == name).unwrap();
    for (earlier, later) in [
        ("parent-flush", "create-Candidate"),
        ("file-Candidate", "create-Prepared"),
        ("file-Prepared", "create-Intent"),
        ("file-Intent", "caller-release"),
        ("caller-release", "publish"),
        ("publish", "file-Candidate"),
        ("check-InstalledRechecked", "create-Observation"),
        ("file-Observation", "create-Receipt"),
        ("file-Receipt", "check-ReceiptFileChecked"),
        ("check-ReceiptParentChecked", "context"),
        ("check-Final", "terminal"),
    ] {
        if earlier == "publish" && later == "file-Candidate" {
            assert!(fake.history.iter().rposition(|v| v == later).unwrap() > at(earlier));
        } else {
            assert!(at(earlier) < at(later), "{earlier} before {later}");
        }
    }
    // Receipt bytes cannot assert that the receipt's own later flush completed.
    let receipt = String::from_utf8_lossy(&fake.creates["receipt.record"]);
    assert!(!receipt.contains("ReceiptFlushed"));
    assert!(!receipt.contains("ReceiptParentChecked"));
}

#[test]
fn every_backend_failure_is_terminal_and_keeps_publication_uncertainty() {
    let mut baseline = Fake::default();
    run(
        &mut baseline,
        b"abc",
        3,
        &mut LogicalBudget::new(u64::MAX),
        &Cancellation::default(),
    );
    let publish = baseline
        .history
        .iter()
        .position(|v| v == "publish")
        .unwrap()
        + 1;
    for fault in [
        Failure::BackendIo,
        Failure::Conflict,
        Failure::Ambiguous,
        Failure::Unsupported,
    ] {
        for at in 1..=baseline.calls {
            let mut fake = Fake {
                fail_at: Some(at),
                fault: Some(fault),
                ..Fake::default()
            };
            let result = run(
                &mut fake,
                b"abc",
                3,
                &mut LogicalBudget::new(u64::MAX),
                &Cancellation::default(),
            );
            assert!(!result.protocol_complete);
            assert_eq!(fake.calls, at, "no resumption after failed check");
            assert_eq!(result.publication_possible, at >= publish);
            if at >= publish {
                assert_eq!(result.status, Status::RecoveryRequired);
            }
            assert_eq!(result.charged_bytes, 3 + 8 * MAX_RECORD_BYTES);
        }
    }
}

#[test]
fn cancellation_after_each_operation_never_relabels_possible_publication() {
    let mut baseline = Fake::default();
    run(
        &mut baseline,
        b"abc",
        3,
        &mut LogicalBudget::new(u64::MAX),
        &Cancellation::default(),
    );
    let publish = baseline
        .history
        .iter()
        .position(|v| v == "publish")
        .unwrap()
        + 1;
    for at in 1..baseline.calls {
        let cancel = Cancellation::default();
        let mut fake = Fake {
            cancel_after: Some(at),
            cancel: Some(&cancel),
            ..Fake::default()
        };
        let result = run(
            &mut fake,
            b"abc",
            3,
            &mut LogicalBudget::new(u64::MAX),
            &cancel,
        );
        assert_eq!(fake.calls, at);
        assert_eq!(result.failure, Some(Failure::Cancelled));
        assert_eq!(
            result.status,
            if at >= publish {
                Status::RecoveryRequired
            } else {
                Status::CancelledBeforePublish
            }
        );
    }
}

#[test]
fn retained_attempts_exhaust_shared_budget_before_new_effects() {
    let unit = 3 + 8 * MAX_RECORD_BYTES;
    let mut budget = LogicalBudget::new(unit * 2);
    for _ in 0..2 {
        let mut fake = Fake {
            fail_at: Some(3),
            ..Fake::default()
        };
        assert!(
            !run(&mut fake, b"abc", 3, &mut budget, &Cancellation::default()).protocol_complete
        );
    }
    let mut fake = Fake::default();
    let result = run(&mut fake, b"abc", 3, &mut budget, &Cancellation::default());
    assert_eq!(result.failure, Some(Failure::BudgetExhausted));
    assert_eq!(fake.calls, 0);
    assert_eq!(budget.charged(), 2 * unit);
}

#[test]
fn exact_length_short_overlong_and_overflow_are_bounded() {
    for (bytes, expected) in [
        (b"ab".as_slice(), Failure::ShortSource),
        (b"abcd".as_slice(), Failure::OverlongSource),
    ] {
        let mut fake = Fake::default();
        let result = run(
            &mut fake,
            bytes,
            3,
            &mut LogicalBudget::new(u64::MAX),
            &Cancellation::default(),
        );
        assert_eq!(result.failure, Some(expected));
        assert_eq!(fake.calls, 1);
        assert!(fake.creates.is_empty());
        assert!(!result.publication_possible);
    }
    let mut budget = LogicalBudget::new(u64::MAX);
    assert_eq!(budget.reserve_unit(u64::MAX), Err(Failure::LengthOverflow));
    assert_eq!(budget.charged(), 0);
}

#[test]
fn actual_candidate_length_can_exceed_the_old_marker_fixture() {
    let bytes = vec![0x61; 70_001];
    let mut fake = Fake::default();
    let mut budget = LogicalBudget::new(u64::MAX);
    let result = run(
        &mut fake,
        &bytes,
        bytes.len() as u64,
        &mut budget,
        &Cancellation::default(),
    );
    assert!(result.protocol_complete);
    assert_eq!(fake.creates["candidate.bin"], bytes);
    assert_eq!(result.charged_bytes, 70_001 + 8 * MAX_RECORD_BYTES);
}

#[test]
fn already_cancelled_attempt_has_no_backend_or_target_effects() {
    let cancel = Cancellation::default();
    cancel.request();
    let mut fake = Fake::default();
    let result = run(
        &mut fake,
        b"abc",
        3,
        &mut LogicalBudget::new(u64::MAX),
        &cancel,
    );
    assert_eq!(result.status, Status::CancelledBeforePublish);
    assert_eq!(fake.calls, 0);
    assert!(!result.retained_material);
    assert!(!result.publication_possible);
    assert!(!result.release_possible);
}

#[test]
fn malformed_duplicate_and_foreign_bindings_never_advance() {
    for mut fake in [
        Fake {
            duplicate: true,
            ..Fake::default()
        },
        Fake {
            empty_binding: true,
            ..Fake::default()
        },
        Fake {
            fail_at: Some(6),
            fault: Some(Failure::Conflict),
            ..Fake::default()
        },
    ] {
        let result = run(
            &mut fake,
            b"abc",
            3,
            &mut LogicalBudget::new(u64::MAX),
            &Cancellation::default(),
        );
        assert_eq!(result.status, Status::Conflict);
        assert!(!result.publication_possible);
    }
}

struct Broken;
impl Read for Broken {
    fn read(&mut self, _: &mut [u8]) -> io::Result<usize> {
        Err(io::Error::other("authored"))
    }
}

#[test]
fn source_io_and_record_bound_have_no_unaccounted_effects() {
    let mut reader = Broken;
    let mut fake = Fake::default();
    let request = ValidatedCandidate {
        operation: "authored",
        format_revision: "v1",
        source: &mut reader,
        planned_len: 1,
        max_len: 1,
        output: ExpectedAbsent("o"),
    };
    let result = execute(
        &mut fake,
        request,
        &mut LogicalBudget::new(u64::MAX),
        &Cancellation::default(),
    );
    assert_eq!(result.failure, Some(Failure::SourceIo));
    assert!(fake.creates.is_empty());
    let mut bytes = vec![0; MAX_RECORD_BYTES as usize - 3];
    assert_eq!(field(&mut bytes, b""), Err(Failure::RecordTooLarge));
}

// Frozen original single-unit effect sequence: the preparation seam must not
// reorder native methods or the existing #0195 caller-history boundaries.
const ORIGINAL_METHOD_TRACE: &[&str] = &[
    "preflight",
    "create-root",
    "root-flush",
    "parent-flush",
    "create-Candidate",
    "check-CandidateChecked",
    "file-Candidate",
    "root-flush",
    "create-Prepared",
    "check-PreparedChecked",
    "file-Prepared",
    "root-flush",
    "create-Intent",
    "check-IntentChecked",
    "file-Intent",
    "root-flush",
    "caller-release",
    "check-Prepublication",
    "publish",
    "check-Installed",
    "file-Candidate",
    "root-flush",
    "check-InstalledRechecked",
    "create-Observation",
    "check-ObservationChecked",
    "file-Observation",
    "root-flush",
    "create-Receipt",
    "check-ReceiptChecked",
    "file-Receipt",
    "check-ReceiptFileChecked",
    "root-flush",
    "check-ReceiptParentChecked",
    "context",
    "check-Final",
    "terminal",
];

fn stage<'a>(
    fake: Fake<'a>,
    budget: &mut LogicalBudget,
    cancel: &Cancellation,
) -> Preparation<Fake<'a>> {
    let mut source = Cursor::new(b"abc".as_slice());
    prepare(
        fake,
        ValidatedCandidate {
            operation: "authored-unit-1",
            format_revision: "authored-bytes-v1",
            source: &mut source,
            planned_len: 3,
            max_len: 1024 * 1024,
            output: ExpectedAbsent("output.bin"),
        },
        budget,
        cancel,
    )
}

#[test]
fn split_preparation_preserves_original_method_trace_records_and_live_state() {
    let cancel = Cancellation::default();
    let mut ordinary = Fake::default();
    let ordinary_result = run(
        &mut ordinary,
        b"abc",
        3,
        &mut LogicalBudget::new(u64::MAX),
        &cancel,
    );
    assert_eq!(ordinary.history, ORIGINAL_METHOD_TRACE);
    let mut budget = LogicalBudget::new(u64::MAX);
    let staged = stage(Fake::default(), &mut budget, &cancel);
    assert!(staged.ready());
    assert_eq!(staged.backend().history, ORIGINAL_METHOD_TRACE[..16]);
    assert_eq!(staged.result().phase, Phase::IntentParentFlushed);
    assert_eq!(staged.bindings().len(), 5);
    assert!(staged.evidence().valid_prefix(staged.bindings()));
    assert_eq!(staged.evidence().operation, "authored-unit-1");
    assert_eq!(staged.evidence().format_revision, "authored-bytes-v1");
    assert_eq!(staged.evidence().output, "output.bin");
    assert!(!staged.result().publication_possible && !staged.result().release_possible);
    let charged = budget.charged();
    let completed = continue_prepared(staged, &cancel);
    assert_eq!(completed.result(), &ordinary_result);
    assert_eq!(budget.charged(), charged);
    assert_eq!(completed.backend().history, ORIGINAL_METHOD_TRACE);
    assert_eq!(completed.backend().creates, ordinary.creates);
    assert_eq!(completed.backend().evidence, ordinary.evidence);
    assert_eq!(completed.backend().outcomes, ordinary.outcomes);
    let (_, result) = completed.into_parts();
    assert_eq!(result.charged_bytes, charged);
}

#[test]
fn failed_preparations_retain_backend_artifacts_exact_failure_and_charge() {
    for at in 1..=16 {
        let hold = std::rc::Rc::new(());
        let fake = Fake {
            fail_at: Some(at),
            held_owner: Some(hold.clone()),
            ..Fake::default()
        };
        let cancel = Cancellation::default();
        let mut budget = LogicalBudget::new(u64::MAX);
        let staged = stage(fake, &mut budget, &cancel);
        assert!(!staged.ready());
        assert_eq!(std::rc::Rc::strong_count(&hold), 2);
        assert!(std::rc::Rc::ptr_eq(
            staged.backend().held_owner.as_ref().unwrap(),
            &hold
        ));
        let failed = staged.result();
        let artifacts = staged.backend().creates.clone();
        assert_eq!(failed.failure, Some(Failure::BackendIo));
        assert_eq!(failed.charged_bytes, 3 + 8 * MAX_RECORD_BYTES);
        assert_eq!(staged.backend().history, ORIGINAL_METHOD_TRACE[..at]);
        // A later cancellation cannot replace the original failure provenance.
        cancel.request();
        let completed = continue_prepared(staged, &cancel);
        assert_eq!(completed.result(), &failed);
        assert_eq!(
            completed.backend().outcomes,
            [(failed.phase, failed.failure)]
        );
        assert_eq!(completed.backend().history, ORIGINAL_METHOD_TRACE[..at]);
        assert_eq!(completed.backend().creates, artifacts);
        assert_eq!(budget.charged(), failed.charged_bytes);
        assert_eq!(std::rc::Rc::strong_count(&hold), 2);
        drop(completed);
        assert_eq!(std::rc::Rc::strong_count(&hold), 1);
    }
}

#[test]
fn cancelled_preparation_and_continuation_retain_original_holds_and_artifacts() {
    for at in 1..=16 {
        let cancel = Cancellation::default();
        let hold = std::rc::Rc::new(());
        let fake = Fake {
            cancel_after: Some(at),
            cancel: Some(&cancel),
            held_owner: Some(hold.clone()),
            ..Fake::default()
        };
        let mut budget = LogicalBudget::new(u64::MAX);
        let staged = stage(fake, &mut budget, &cancel);
        // Cancellation after the final stage method is observed by continuation.
        assert_eq!(staged.ready(), at == 16);
        let artifacts = staged.backend().creates.clone();
        let completed = continue_prepared(staged, &cancel);
        assert_eq!(completed.result().failure, Some(Failure::Cancelled));
        assert_eq!(completed.result().status, Status::CancelledBeforePublish);
        assert!(!completed.result().release_possible);
        assert_eq!(completed.backend().history, ORIGINAL_METHOD_TRACE[..at]);
        assert_eq!(completed.backend().creates, artifacts);
        assert_eq!(completed.result().charged_bytes, budget.charged());
        assert_eq!(std::rc::Rc::strong_count(&hold), 2);
        drop(completed);
        assert_eq!(std::rc::Rc::strong_count(&hold), 1);
    }
}

#[test]
fn continuation_failures_retain_exact_original_backend_and_terminal_provenance() {
    for at in 17..=ORIGINAL_METHOD_TRACE.len() {
        let cancel = Cancellation::default();
        let mut ordinary = Fake {
            fail_at: Some(at),
            ..Fake::default()
        };
        let expected = run(
            &mut ordinary,
            b"abc",
            3,
            &mut LogicalBudget::new(u64::MAX),
            &cancel,
        );
        let hold = std::rc::Rc::new(());
        let fake = Fake {
            fail_at: Some(at),
            held_owner: Some(hold.clone()),
            ..Fake::default()
        };
        let mut budget = LogicalBudget::new(u64::MAX);
        let staged = stage(fake, &mut budget, &cancel);
        assert!(staged.ready());
        assert!(staged.backend().outcomes.is_empty());
        let completed = continue_prepared(staged, &cancel);
        assert_eq!(completed.result(), &expected);
        assert_eq!(completed.backend().history, ORIGINAL_METHOD_TRACE[..at]);
        assert_eq!(completed.backend().creates, ordinary.creates);
        assert_eq!(completed.backend().evidence, ordinary.evidence);
        assert_eq!(completed.backend().outcomes, ordinary.outcomes);
        assert_eq!(completed.backend().outcomes.len(), 1);
        assert_eq!(completed.result().charged_bytes, budget.charged());
        assert_eq!(std::rc::Rc::strong_count(&hold), 2);
        drop(completed);
        assert_eq!(std::rc::Rc::strong_count(&hold), 1);
    }
}

#[test]
fn continuation_cancellation_keeps_same_holds_artifacts_and_publication_uncertainty() {
    for at in 17..ORIGINAL_METHOD_TRACE.len() {
        let cancel = Cancellation::default();
        let hold = std::rc::Rc::new(());
        let fake = Fake {
            cancel_after: Some(at),
            cancel: Some(&cancel),
            held_owner: Some(hold.clone()),
            ..Fake::default()
        };
        let mut budget = LogicalBudget::new(u64::MAX);
        let staged = stage(fake, &mut budget, &cancel);
        assert!(staged.ready());
        let completed = continue_prepared(staged, &cancel);
        let result = completed.result();
        assert_eq!(result.failure, Some(Failure::Cancelled));
        assert!(result.release_possible);
        assert_eq!(result.publication_possible, at >= 19);
        assert_eq!(
            result.status,
            if at >= 19 {
                Status::RecoveryRequired
            } else {
                Status::CancelledBeforePublish
            }
        );
        assert_eq!(completed.backend().history, ORIGINAL_METHOD_TRACE[..at]);
        assert_eq!(
            completed.backend().outcomes,
            [(result.phase, result.failure)]
        );
        assert_eq!(result.charged_bytes, budget.charged());
        assert_eq!(std::rc::Rc::strong_count(&hold), 2);
        drop(completed);
        assert_eq!(std::rc::Rc::strong_count(&hold), 1);
    }
}
