//! Authored native byte-budget process probe; no media inputs or filesystem writes.
#[path = "../tests/support/byte_boundaries.rs"]
mod byte_boundaries;
#[path = "../tests/support/byte_budget_fixtures.rs"]
mod byte_budget_fixtures;
#[allow(dead_code)]
#[path = "../tests/support/mod.rs"]
mod support;
fn main() {
    let args: Vec<_> = std::env::args().collect();
    assert_eq!(args.len(), 3, "axis and -1/0/1 delta required");
    let delta: i32 = args[2].parse().unwrap();
    assert!([-1, 0, 1].contains(&delta));
    let result = byte_budget_fixtures::execute(&args[1], delta);
    println!("{}", serde_json::to_string(&result).unwrap());
}
