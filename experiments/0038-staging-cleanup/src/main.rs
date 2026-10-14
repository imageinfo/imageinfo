#[cfg(windows)]
#[allow(unsafe_code)] // One synchronous owned-handle disposition; see ../ffi-review.md.
mod disposition;
#[cfg(windows)]
#[allow(unsafe_code, dead_code)] // Reuse the reviewed project-owned #0032/#0033 boundary.
#[path = "../../0032-windows-publication/src/native.rs"]
mod native;
#[cfg(windows)]
#[path = "../../0034-source-oplocks/src/path.rs"]
mod path;
#[cfg(any(windows, test))]
mod staging;
#[cfg(windows)]
mod windows;
fn main() {
    #[cfg(windows)]
    let result = windows::run();
    #[cfg(not(windows))]
    let result: Result<(), Box<dyn std::error::Error>> =
        Err("STAGING_CLEANUP_WINDOWS_UNVERIFIED".into());
    if let Err(error) = result {
        eprintln!(
            "{}",
            serde_json::json!({"diagnostic":error.to_string().chars().filter(|c| !c.is_control()).take(256).collect::<String>(),"productionPublicationAllowed":false,"committed":false})
        );
        std::process::exit(5);
    }
}
