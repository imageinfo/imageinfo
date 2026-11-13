use super::*;
use crate::storage::MAX_RECORD_BYTES;

#[test]
fn exact_map_and_call_flags_control_confirmation() {
    let mut report = Report::refused(Failure::Conflict);
    assert!(!report.confirm(PREFIXES[1]));
    report.attempted[0] = true;
    assert!(!report.confirm([Foreign, Old, Candidate]));
    assert!(!report.confirm([Unknown, Old, Candidate]));
    assert_eq!(report.confirmed_prefix, 0);
    assert!(report.confirm(PREFIXES[1]));
    report.attempted[1] = true;
    report.response_discarded[1] = true;
    assert!(!report.confirm(PREFIXES[2]));
    assert_eq!(report.confirmed_prefix, 1);
    report.response_discarded[1] = false;
    assert!(report.confirm(PREFIXES[2]));
    assert!(!report.confirm(PREFIXES[2]));
}

#[test]
fn stop_maps_only_allow_foreign_winners_in_the_vacant_selected_slot() {
    for (prefix, exact) in PREFIXES.into_iter().enumerate() {
        assert!(admissible_stop_map(prefix as u8, exact));
        for slot in 0..3 {
            let mut map = exact;
            map[slot] = Unknown;
            assert!(!admissible_stop_map(prefix as u8, map));
            map[slot] = Foreign;
            assert_eq!(
                admissible_stop_map(prefix as u8, map),
                (prefix, slot) == (0, 1) || (prefix, slot) == (1, 0)
            );
        }
    }
}

#[test]
fn precharge_is_bounded_cumulative_and_never_refunded() {
    let charge = MARKER_LIMIT + 8 * MAX_RECORD_BYTES;
    let mut budget = LogicalBudget::new(charge);
    assert_eq!(
        precharge(&mut budget, MARKER_LIMIT + 1),
        Err(Failure::CandidateTooLarge)
    );
    assert_eq!(budget.charged(), 0);
    precharge(&mut budget, MARKER_LIMIT).unwrap();
    assert_eq!(budget.charged(), charge);
    assert_eq!(precharge(&mut budget, 0), Err(Failure::BudgetExhausted));
    assert_eq!(budget.charged(), charge);
}

#[cfg(not(windows))]
#[test]
fn unsupported_platform_has_no_call_or_inferred_map() {
    let report = unsupported();
    assert_eq!(report.outcome, Outcome::Refused);
    assert_eq!(report.failure, Some(Failure::Unsupported));
    assert_eq!(report.bindings, [Unknown; 3]);
    assert_eq!(report.attempted, [false; 2]);
}

#[cfg(windows)]
#[path = "native_tests.rs"]
mod native;
