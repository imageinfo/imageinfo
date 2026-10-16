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
