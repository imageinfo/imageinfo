//! Bounded authored-marker retention research; no production authority.
#[cfg(windows)]
mod windows;

fn main() {
    #[cfg(windows)]
    if let Err(error) = windows::run() {
        eprintln!("Retention probe stopped; artifacts retained: {error}");
        std::process::exit(1);
    }
    #[cfg(not(windows))]
    println!(
        "{}",
        serde_json::json!({"event":"result", "refusalCode":"WINDOWS_ONLY",
            "productionReplacementAllowed":false, "restoreAllowed":false,
            "committed":false, "enabledProfiles":0})
    );
}
