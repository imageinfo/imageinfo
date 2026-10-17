use super::*;
use crate::storage::resources::KnownOperations;
use std::cell::Cell;

fn bytes(default: u64) -> FileBytes<'static> {
    FileBytes {
        default: Some(default),
        streams: Streams::Complete(&[]),
    }
}
fn member() -> Member<'static> {
    Member::Replace {
        candidate: bytes(3),
        original_recovery: bytes(5),
    }
}
fn key(operation: &str) -> OperationKey<'_> {
    OperationKey {
        operation,
        root: operation,
    }
}
fn plan() -> Plan {
    Plan::build(&[member()], BackupChoice::Keep).unwrap()
}
fn charge(plan: &Plan) -> u64 {
    plan.precommit_bytes + plan.ledger_bytes
}

#[test]
fn fixed_table_charges_all_streams_restore_current_and_both_members() {
    let streams = [Some(7), Some(11)];
    let files = FileBytes {
        default: Some(13),
        streams: Streams::Complete(&streams),
    };
    let replacement = Member::Replace {
        candidate: files,
        original_recovery: files,
    };
    let restore = Member::Restore {
        restored_candidate: files,
        original_recovery: files,
        current_preservation: files,
    };
    for members in [
        &[replacement][..],
        &[restore][..],
        &[replacement, restore][..],
    ] {
        let keep = Plan::build(members, BackupChoice::Keep).unwrap();
        assert_eq!(keep, Plan::build(members, BackupChoice::NoBackup).unwrap());
        assert_eq!(keep.candidate_bytes, 31 * members.len() as u64);
        assert_eq!(keep.original_recovery_bytes, 31 * members.len() as u64);
        assert_eq!(
            keep.current_preservation_bytes,
            if members.len() == 1 && matches!(members[0], Member::Replace { .. }) {
                0
            } else {
                31
            }
        );
        assert_eq!(
            keep.records_bytes,
            MEMBER_RECORD_BYTES * members.len() as u64
                + if members.len() == 2 {
                    GROUP_RECORD_BYTES
                } else {
                    0
                }
        );
    }
}

#[test]
fn unknown_unreadable_excess_streams_member_count_and_overflow_refuse() {
    let too_many = [Some(0); MAX_STREAMS + 1];
    for (file, expected) in [
        (
            FileBytes {
                default: None,
                streams: Streams::Complete(&[]),
            },
            Failure::InvalidBinding,
        ),
        (
            FileBytes {
                default: Some(1),
                streams: Streams::Unknown,
            },
            Failure::InvalidBinding,
        ),
        (
            FileBytes {
                default: Some(1),
                streams: Streams::Complete(&[None]),
            },
            Failure::SourceIo,
        ),
        (
            FileBytes {
                default: Some(1),
                streams: Streams::Complete(&too_many),
            },
            Failure::RecordTooLarge,
        ),
        (bytes(u64::MAX), Failure::LengthOverflow),
    ] {
        assert_eq!(
            Plan::build(
                &[Member::Replace {
                    candidate: file,
                    original_recovery: bytes(1)
                }],
                BackupChoice::Keep
            ),
            Err(expected)
        );
    }
    assert_eq!(
        Plan::build(&[], BackupChoice::Keep),
        Err(Failure::Unsupported)
    );
    assert_eq!(
        Plan::build(&[member(); 3], BackupChoice::Keep),
        Err(Failure::Unsupported)
    );
}

#[test]
fn exact_limit_one_byte_over_and_availability_precede_construction() {
    let plan = plan();
    let invoked = Cell::new(false);
    let mut below =
        RetainedSession::start(charge(&plan) - 1, KnownOperations::Complete(&[])).unwrap();
    assert_eq!(
        plan.attempt(
            &mut below,
            key("over"),
            &Cancellation::default(),
            || { panic!("query before charge") },
            || {
                invoked.set(true);
                Ok(())
            }
        ),
        Err(Failure::BudgetExhausted)
    );
    assert_eq!(below.charged(), 0);
    let mut exact = RetainedSession::start(charge(&plan), KnownOperations::Complete(&[])).unwrap();
    assert_eq!(
        plan.attempt(
            &mut exact,
            key("exact"),
            &Cancellation::default(),
            || Ok(plan.precommit_bytes),
            || {
                invoked.set(true);
                Ok(())
            }
        ),
        Ok(())
    );
    assert!(invoked.get());
    assert_eq!(exact.charged(), charge(&plan));
    let mut low = RetainedSession::start(charge(&plan), KnownOperations::Complete(&[])).unwrap();
    assert_eq!(
        plan.attempt(
            &mut low,
            key("low"),
            &Cancellation::default(),
            || Ok(plan.precommit_bytes - 1),
            || { panic!("unavailable recovery space") }
        ),
        Err::<(), _>(Failure::StorageUnavailable)
    );
    assert_eq!(low.charged(), charge(&plan));
}

#[test]
fn failed_copy_cancelled_query_error_and_repeated_attempts_keep_charges() {
    let plan = plan();
    let mut session =
        RetainedSession::start(charge(&plan) * 4, KnownOperations::Complete(&[])).unwrap();
    assert_eq!(
        plan.attempt(
            &mut session,
            key("failed-copy"),
            &Cancellation::default(),
            || Ok(u64::MAX),
            || Err::<(), _>(Failure::ShortSource)
        ),
        Err(Failure::ShortSource)
    );
    let cancel = Cancellation::default();
    cancel.request();
    assert_eq!(
        plan.attempt(
            &mut session,
            key("cancelled"),
            &cancel,
            || Ok(u64::MAX),
            || { panic!("cancelled constructor") }
        ),
        Err::<(), _>(Failure::Cancelled)
    );
    assert_eq!(
        plan.attempt(
            &mut session,
            key("query-error"),
            &Cancellation::default(),
            || Err(Failure::BackendIo),
            || { panic!("failed availability query") }
        ),
        Err::<(), _>(Failure::BackendIo)
    );
    let work = session.suspend();
    let mut session = RetainedSession::adopt(
        work,
        KnownOperations::Complete(&[key("failed-copy"), key("cancelled"), key("query-error")]),
    )
    .unwrap();
    assert_eq!(session.charged(), charge(&plan) * 3);
    assert_eq!(
        plan.attempt(
            &mut session,
            key("fourth"),
            &Cancellation::default(),
            || Ok(u64::MAX),
            || Ok(())
        ),
        Ok(())
    );
    assert_eq!(
        plan.attempt(
            &mut session,
            key("fifth"),
            &Cancellation::default(),
            || { panic!("exhausted query") },
            || Ok(())
        ),
        Err(Failure::BudgetExhausted)
    );
    assert_eq!(session.charged(), charge(&plan) * 4);
}

#[test]
fn constructor_panic_retains_charge_and_refuses_further_work_or_adoption() {
    let plan = plan();
    let mut session = RetainedSession::start(u64::MAX, KnownOperations::Complete(&[])).unwrap();
    let panic = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
        let _ = plan.attempt(
            &mut session,
            key("uncertain"),
            &Cancellation::default(),
            || Ok(u64::MAX),
            || -> Result<(), Failure> { panic!("uncertain copy") },
        );
    }));
    assert!(panic.is_err());
    assert_eq!(session.charged(), charge(&plan));
    assert_eq!(
        plan.attempt(
            &mut session,
            key("next"),
            &Cancellation::default(),
            || Ok(u64::MAX),
            || Ok(())
        ),
        Err(Failure::CallerHistory)
    );
    assert!(
        RetainedSession::adopt(
            session.suspend(),
            KnownOperations::Complete(&[key("uncertain")])
        )
        .is_err()
    );
}

#[cfg(windows)]
mod native;
#[test]
fn partial_copy_and_cancelled_material_keep_full_charge_with_shared_constructions() {
    use std::io::{self, Cursor, Write};
    struct ShortWriter(Vec<u8>);
    impl Write for ShortWriter {
        fn write(&mut self, bytes: &[u8]) -> io::Result<usize> {
            if self.0.len() == 2 {
                return Err(io::Error::other("authored bounded write failure"));
            }
            let n = (2 - self.0.len()).min(bytes.len());
            self.0.extend_from_slice(&bytes[..n]);
            Ok(n)
        }
        fn flush(&mut self) -> io::Result<()> {
            Ok(())
        }
    }
    let plan = plan();
    let mut session =
        RetainedSession::start(charge(&plan) * 2 + 7, KnownOperations::Complete(&[])).unwrap();
    let mut partial = ShortWriter(Vec::new());
    assert_eq!(
        plan.attempt(
            &mut session,
            key("partial"),
            &Cancellation::default(),
            || Ok(u64::MAX),
            || {
                io::copy(&mut Cursor::new(b"abc"), &mut partial)
                    .map(|_| ())
                    .map_err(|_| Failure::BackendIo)
            }
        ),
        Err(Failure::BackendIo)
    );
    assert_eq!(partial.0, b"ab");
    let cancel = Cancellation::default();
    let mut retained = Vec::new();
    assert_eq!(
        plan.attempt(
            &mut session,
            key("cancelled-partial"),
            &cancel,
            || Ok(u64::MAX),
            || {
                retained.extend_from_slice(b"ab");
                cancel.request();
                Err::<(), _>(Failure::Cancelled)
            }
        ),
        Err(Failure::Cancelled)
    );
    assert_eq!(retained, b"ab");
    assert_eq!(
        session.construct(
            key("partial"),
            crate::storage::resources::Construction::Recovery,
            7,
            || Ok(())
        ),
        Ok(())
    );
    assert_eq!(session.charged(), charge(&plan) * 2 + 7);
    assert_eq!(
        session.operation_charge(key("partial")).unwrap(),
        charge(&plan) + 7
    );
}
