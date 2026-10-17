#[path = "support/byte_boundaries.rs"]
mod byte_boundaries;
#[path = "support/byte_budget_fixtures.rs"]
mod byte_budget_fixtures;
#[allow(dead_code)]
mod support;
use imageinfo::reader::{self, Limits};
#[test]
fn default_byte_limits_have_exact_native_below_at_above_cells() {
    for axis in ["metadata", "block"] {
        for delta in [-1, 0, 1] {
            byte_budget_fixtures::execute(axis, delta);
        }
    }
}
#[test]
fn byte_hard_ceiling_configuration_is_separate_from_capacity() {
    let bytes = support::fixture().bytes;
    for axis in ["metadata", "block"] {
        for delta in [-1i64, 0, 1] {
            let mut limits = Limits::default();
            let cap = if axis == "metadata" {
                268_435_456
            } else {
                8_388_608
            };
            if axis == "metadata" {
                limits.metadata_bytes = (cap + delta) as u64;
            } else {
                limits.block_bytes = (cap + delta) as u64;
            }
            let (source, trace) = byte_boundaries::RecordingSource::new(&bytes);
            let result = reader::read(source, limits);
            if delta <= 0 {
                assert!(result.is_ok());
                assert!(!trace.borrow().is_empty());
            } else {
                let e = result.unwrap_err();
                assert_eq!(e.code, "LIMIT_EXCEEDED");
                assert_eq!(e.message, "Reader limit exceeds its supported ceiling");
                assert!(trace.borrow().is_empty());
            }
        }
    }
}

#[test]
fn above_default_cells_are_structurally_valid_with_only_that_budget_raised() {
    for axis in ["metadata", "block"] {
        let bytes = byte_budget_fixtures::fixture(axis, 1);
        let mut limits = Limits::default();
        if axis == "metadata" {
            limits.metadata_bytes += 1;
        } else {
            limits.block_bytes += 1;
        }
        let (source, trace) = byte_boundaries::RecordingSource::new(&bytes);
        let result = reader::read(source, limits).unwrap();
        let oracle = byte_budget_fixtures::oracle(&bytes);
        assert_eq!(*trace.borrow(), oracle);
        assert_eq!(
            result.bytes_read,
            oracle.iter().map(|r| r.requested as u64).sum::<u64>()
        );
        assert_eq!(result.previews.len(), 3);
    }
}
