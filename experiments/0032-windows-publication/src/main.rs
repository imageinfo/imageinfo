#[cfg(windows)]
#[allow(unsafe_code)] // Reviewed native ABI boundary; see the experiment's FFI review.
mod native;
#[cfg(windows)]
mod windows;

fn main() {
    #[cfg(windows)]
    let result = windows::run();
    #[cfg(not(windows))]
    let result: Result<(), Box<dyn std::error::Error>> = Err("WINDOWS_BACKEND_UNVERIFIED".into());
    if let Err(error) = result {
        eprintln!(
            "{}",
            serde_json::json!({"diagnostic":error.to_string().chars().filter(|c|!c.is_control()).take(256).collect::<String>(),
            "productionPublicationAllowed":false,"committed":false})
        );
        std::process::exit(5);
    }
}
