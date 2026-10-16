//! Authored-fixture driver for the actual strict refusal boundary. It does not
//! create/open either input. Run via tests/existing_properties_native.py.
use imageinfo_windows_storage::existing_properties::{
    ExistingTargetRequest, ModificationTimePolicy,
};

fn main() {
    let args: Vec<_> = std::env::args_os().skip(1).collect();
    assert_eq!(args.len(), 3, "candidate target update|preserve required");
    let time = match args[2].to_str() {
        Some("update") => ModificationTimePolicy::UpdateForContentEdit,
        Some("preserve") => ModificationTimePolicy::PreserveOriginal,
        _ => panic!("unknown time policy"),
    };
    let refusal = ExistingTargetRequest::new(args[0].clone().into(), args[1].clone().into(), time)
        .refuse_unsupported();
    assert_eq!(refusal.modification_time(), time);
    assert_eq!(refusal.requirements().len(), 3);
    println!("{refusal}");
}
