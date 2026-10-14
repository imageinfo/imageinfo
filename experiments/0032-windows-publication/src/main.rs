#[cfg(windows)]
#[allow(unsafe_code)] // Reused owned-handle disposition; no new SDK call.
#[path = "../../0038-staging-cleanup/src/disposition.rs"]
mod disposition;
#[cfg(windows)]
mod inspection;
#[cfg(any(windows, test))]
mod inspection_record;
#[cfg(windows)]
#[allow(unsafe_code)] // Reviewed native ABI boundary; see the experiment's FFI review.
mod native;
#[cfg(windows)]
mod ordinary;
#[cfg(any(windows, test))]
mod ordinary_record;
#[cfg(any(windows, test))]
#[path = "../../0038-staging-cleanup/src/staging.rs"]
mod staging;
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
