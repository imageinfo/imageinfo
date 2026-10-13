#[cfg(windows)]
#[allow(unsafe_code, dead_code)] // Reuse project-owned reviewed ABI boundary; #0033 additions reviewed separately.
#[path = "../../0032-windows-publication/src/native.rs"]
mod native;
#[cfg(windows)]
mod windows;
fn main() {
    #[cfg(windows)]
    let result = windows::run();
    #[cfg(not(windows))]
    let result: Result<(), Box<dyn std::error::Error>> =
        Err("OWNER_RIGHTS_WINDOWS_UNVERIFIED".into());
    if let Err(error) = result {
        eprintln!(
            "{}",
            serde_json::json!({"diagnostic":error.to_string().chars().filter(|c|!c.is_control()).take(256).collect::<String>(),"productionPublicationAllowed":false,"committed":false})
        );
        std::process::exit(5);
    }
}
