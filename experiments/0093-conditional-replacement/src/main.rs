//! Authored disposable-marker observations; every profile remains unsupported.
#[cfg(windows)]
mod windows;

fn main() {
    #[cfg(windows)]
    if let Err(error) = windows::run() {
        eprintln!("Probe failed: {error}");
        std::process::exit(1);
    }
    #[cfg(not(windows))]
    println!(
        "{}",
        serde_json::json!({
            "event": "result", "refusalCode": "WINDOWS_ONLY",
            "renameAttempted": false, "renameSucceeded": false, "osError": null,
            "productionReplacementAllowed": false, "committed": false, "enabledProfiles": 0
        })
    );
}
