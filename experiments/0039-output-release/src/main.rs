#[cfg(windows)]
#[allow(unsafe_code, dead_code)] // Existing reviewed boundary; see ../ffi-review.md.
#[path = "../../0032-windows-publication/src/native.rs"]
mod native;
#[cfg(windows)]
#[path = "../../0034-source-oplocks/src/path.rs"]
mod path;
#[cfg(windows)]
mod windows;
fn main() {
    #[cfg(windows)]
    let result = windows::run();
    #[cfg(not(windows))]
    let result: Result<(), Box<dyn std::error::Error>> =
        Err("OUTPUT_RELEASE_WINDOWS_UNVERIFIED".into());
    if let Err(error) = result {
        eprintln!(
            "{}",
            serde_json::json!({"diagnostic":error.to_string().chars().filter(|c| !c.is_control()).take(256).collect::<String>(),"committed":false,"productionPublicationAllowed":false})
        );
        std::process::exit(5);
    }
}
