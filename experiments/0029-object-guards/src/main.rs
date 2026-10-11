//! Guard qualification only: no production publication capability is enabled.
use std::{error::Error, path::Path};
#[cfg(target_os = "linux")]
mod linux;
#[cfg(windows)]
mod windows;

fn main() {
    if let Err(error) = run() {
        eprintln!("Guard probe refused: {error}");
        std::process::exit(1);
    }
}
fn run() -> Result<(), Box<dyn Error>> {
    let args: Vec<_> = std::env::args_os().skip(1).collect();
    if args.len() != 2 {
        return Err(
            "Use hold-source FILE, hold-stage DIRECTORY, or anonymous-stage DIRECTORY".into(),
        );
    }
    let name = args[0].to_str().ok_or("Invalid command")?;
    let path = Path::new(&args[1]);
    #[cfg(windows)]
    match name {
        "hold-source" => return windows::hold_source(path),
        "hold-stage" => return windows::hold_stage(path),
        _ => {}
    }
    #[cfg(target_os = "linux")]
    if name == "anonymous-stage" {
        return linux::anonymous_stage(path);
    }
    let _ = (name, path);
    Err("GUARD_PROFILE_UNVERIFIED: no alternate/advisory implementation".into())
}
