use super::*;
use crate::storage::Phase;
#[cfg(windows)]
use crate::storage::Status;
use crate::storage::runtime::{Artifact, Binding, ExpectedAbsent};
use std::io::Cursor;

#[derive(Default)]
struct NoEffects {
    calls: usize,
    preflight_ok: bool,
}

impl Backend for NoEffects {
    fn profile(&self) -> &'static str {
        "authored-unqualified"
    }
    fn implementation(&self) -> &'static str {
        "resource-refusal-v1"
    }
    fn preflight(&mut self, _: &str) -> Result<Binding, Failure> {
        self.calls += 1;
        if self.preflight_ok {
            Ok(Binding {
                identity: vec![1],
                facts: vec![2],
            })
        } else {
            Err(Failure::BackendIo)
        }
    }
    fn create_root(&mut self) -> Result<Binding, Failure> {
        panic!("unexpected effect")
    }
    fn create(&mut self, _: Artifact, _: &[u8]) -> Result<Binding, Failure> {
        panic!("unexpected effect")
    }
    fn check(&mut self, _: Phase, _: &[Binding]) -> Result<(), Failure> {
        panic!("unexpected effect")
    }
    fn flush_file(&mut self, _: Artifact) -> Result<(), Failure> {
        panic!("unexpected effect")
    }
    fn flush_root(&mut self) -> Result<(), Failure> {
        panic!("unexpected effect")
    }
    fn flush_parent(&mut self) -> Result<(), Failure> {
        panic!("unexpected effect")
    }
    fn publish(&mut self, _: &str) -> Result<(), Failure> {
        panic!("unexpected effect")
    }
    fn caller_release(&mut self, _: &[Binding]) -> Result<(), Failure> {
        panic!("unexpected effect")
    }
    fn checked_context(&mut self, _: &[Binding]) -> Result<(), Failure> {
        panic!("unexpected effect")
    }
    fn export_terminal(&mut self, _: &[Binding]) -> Result<(), Failure> {
        panic!("unexpected effect")
    }
}

fn key(operation: &str) -> OperationKey<'_> {
    OperationKey {
        operation,
        root: operation,
    }
}

fn refused(
    session: &mut RetainedSession,
    backend: &mut NoEffects,
    operation: &str,
    len: u64,
    available: Result<u64, Failure>,
) -> Result<UnitResult, Failure> {
    session.run(
        key(operation),
        backend,
        ValidatedCandidate {
            operation,
            format_revision: "authored-v1",
            source: &mut Cursor::new(b"abc"),
            planned_len: len,
            max_len: u64::MAX,
            output: ExpectedAbsent("output.bin"),
        },
        &Cancellation::default(),
        |_| available,
    )
}

#[test]
fn exact_limit_below_limit_and_checked_overflow_precede_effects() {
    let amount = LogicalBudget::unit_charge(3).unwrap() + ENTRY_BYTES;
    let mut backend = NoEffects::default();
    let mut below = RetainedSession::start(amount - 1, KnownOperations::Complete(&[])).unwrap();
    assert_eq!(
        refused(&mut below, &mut backend, "below", 3, Ok(u64::MAX)),
        Err(Failure::BudgetExhausted)
    );
    assert_eq!(below.charged(), 0);
    let mut exact = RetainedSession::start(amount, KnownOperations::Complete(&[])).unwrap();
    assert_eq!(
        refused(&mut exact, &mut backend, "exact", 3, Ok(u64::MAX))
            .unwrap()
            .failure,
        Some(Failure::BackendIo)
    );
    assert_eq!(exact.charged(), amount);
    assert_eq!(
        refused(&mut exact, &mut backend, "next", 3, Ok(u64::MAX)),
        Err(Failure::BudgetExhausted)
    );
    let mut overflow = RetainedSession::start(u64::MAX, KnownOperations::Complete(&[])).unwrap();
    assert_eq!(
        refused(
            &mut overflow,
            &mut backend,
            "overflow",
            u64::MAX,
            Ok(u64::MAX)
        ),
        Err(Failure::LengthOverflow)
    );
    assert_eq!(overflow.charged(), 0);
    assert_eq!(backend.calls, 1);
}

#[test]
fn availability_low_or_failed_is_advisory_and_preserves_logical_charge() {
    let amount = LogicalBudget::unit_charge(3).unwrap() + ENTRY_BYTES;
    let mut session = RetainedSession::start(amount * 3, KnownOperations::Complete(&[])).unwrap();
    let mut backend = NoEffects::default();
    let low = refused(&mut session, &mut backend, "low", 3, Ok(0)).unwrap();
    assert_eq!(low.failure, Some(Failure::StorageUnavailable));
    let failed = refused(
        &mut session,
        &mut backend,
        "query-failed",
        3,
        Err(Failure::BackendIo),
    )
    .unwrap();
    assert_eq!(failed.failure, Some(Failure::BackendIo));
    assert_eq!(failed.status, crate::storage::Status::FailedBeforePublish);
    assert_eq!(backend.calls, 0);
    assert_eq!(session.charged(), amount * 2);
    assert!(!low.retained_material && !failed.retained_material);
}

#[test]
fn actual_candidate_capacity_failure_retains_the_complete_reservation() {
    let length = (isize::MAX as u64) + 1;
    let mut session = RetainedSession::start(u64::MAX, KnownOperations::Complete(&[])).unwrap();
    let mut backend = NoEffects {
        preflight_ok: true,
        ..NoEffects::default()
    };
    let result = refused(
        &mut session,
        &mut backend,
        "allocation-failed",
        length,
        Ok(u64::MAX),
    )
    .unwrap();
    assert_eq!(result.failure, Some(Failure::CandidateTooLarge));
    assert_eq!(backend.calls, 1);
    assert!(!result.retained_material);
    assert_eq!(session.charged(), length + 9 * MAX_RECORD_BYTES);
}

#[test]
fn adoption_requires_the_exact_complete_set_and_keeps_prior_charges() {
    assert!(matches!(
        RetainedSession::start(u64::MAX, KnownOperations::Unknown),
        Err(Failure::CallerHistory)
    ));
    assert!(matches!(
        RetainedSession::start(u64::MAX, KnownOperations::Complete(&[key("unknown")])),
        Err(Failure::CallerHistory)
    ));
    let amount = LogicalBudget::unit_charge(3).unwrap() + ENTRY_BYTES;
    let mut session = RetainedSession::start(amount * 2, KnownOperations::Complete(&[])).unwrap();
    let mut backend = NoEffects::default();
    refused(&mut session, &mut backend, "retained", 3, Ok(u64::MAX)).unwrap();
    let work = session.suspend();
    let (_, work) = RetainedSession::adopt(work, KnownOperations::Unknown)
        .err()
        .unwrap();
    let (_, work) = RetainedSession::adopt(work, KnownOperations::Complete(&[]))
        .err()
        .unwrap();
    let (_, work) = RetainedSession::adopt(work, KnownOperations::Complete(&[key("foreign")]))
        .err()
        .unwrap();
    let mut recreated =
        RetainedSession::adopt(work, KnownOperations::Complete(&[key("retained")])).unwrap();
    assert_eq!(recreated.charged(), amount);
    assert_eq!(
        refused(&mut recreated, &mut backend, "retained", 3, Ok(u64::MAX)),
        Err(Failure::CallerHistory)
    );
    refused(&mut recreated, &mut backend, "next", 3, Ok(u64::MAX)).unwrap();
    assert_eq!(recreated.charged(), amount * 2);
    assert_eq!(
        refused(&mut recreated, &mut backend, "reset", 3, Ok(u64::MAX)),
        Err(Failure::BudgetExhausted)
    );
}

#[test]
fn custody_recovery_and_manifest_callbacks_are_charged_before_construction() {
    let amount = LogicalBudget::unit_charge(3).unwrap() + ENTRY_BYTES;
    let mut session = RetainedSession::start(amount + 6, KnownOperations::Complete(&[])).unwrap();
    refused(
        &mut session,
        &mut NoEffects::default(),
        "owned",
        3,
        Ok(u64::MAX),
    )
    .unwrap();
    for kind in [
        Construction::Custody,
        Construction::Recovery,
        Construction::Manifest,
    ] {
        assert_eq!(
            session.construct(key("owned"), kind, 2, || Err::<(), _>(Failure::BackendIo)),
            Err(Failure::BackendIo)
        );
    }
    let mut invoked = false;
    assert_eq!(
        session.construct(key("owned"), Construction::Recovery, 1, || {
            invoked = true;
            Ok(())
        }),
        Err(Failure::BudgetExhausted)
    );
    assert!(!invoked);
    assert_eq!(session.operation_charge(key("owned")).unwrap(), amount + 6);
    assert_eq!(session.charged(), amount + 6);
}

#[test]
fn uncertain_constructor_blocks_later_effects_and_recreated_adoption() {
    let mut session = RetainedSession::start(u64::MAX, KnownOperations::Complete(&[])).unwrap();
    let mut backend = NoEffects::default();
    refused(&mut session, &mut backend, "owned", 3, Ok(u64::MAX)).unwrap();
    let panic = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
        let _ = session.construct(
            key("owned"),
            Construction::Recovery,
            1,
            || -> Result<(), Failure> { panic!("authored uncertain constructor") },
        );
    }));
    assert!(panic.is_err());
    assert_eq!(
        refused(&mut session, &mut backend, "next", 3, Ok(u64::MAX)),
        Err(Failure::CallerHistory)
    );
    assert!(
        RetainedSession::adopt(
            session.suspend(),
            KnownOperations::Complete(&[key("owned")])
        )
        .is_err()
    );
}

#[test]
fn two_unit_reservation_is_atomic_and_helpers_cannot_be_reused() {
    let unit = LogicalBudget::unit_charge(3).unwrap();
    let total = unit * 2 + 42;
    let mut budget = LogicalBudget::new(total - 1);
    assert!(matches!(
        budget.reserve_group([3, 3], 42),
        Err(Failure::BudgetExhausted)
    ));
    assert_eq!(budget.charged(), 0);
    let mut budget = LogicalBudget::new(total);
    let mut units = budget.reserve_group([3, 3], 42).unwrap();
    for helper in &mut units {
        assert_eq!(helper.reserve_unit(3), Ok(unit));
        assert_eq!(helper.reserve_unit(3), Err(Failure::BudgetExhausted));
    }
    assert_eq!(budget.charged(), total);
    assert!(matches!(
        LogicalBudget::new(u64::MAX).reserve_group([u64::MAX, 3], 0),
        Err(Failure::LengthOverflow)
    ));
    assert!(matches!(
        LogicalBudget::new(u64::MAX).reserve_group([3, 3], MAX_RECORD_BYTES + 1),
        Err(Failure::RecordTooLarge)
    ));
}

#[cfg(windows)]
mod native;
