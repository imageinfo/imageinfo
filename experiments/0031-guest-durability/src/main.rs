#[cfg(target_os = "linux")]
mod linux;
fn main() {
    #[cfg(target_os = "linux")]
    let result = linux::run();
    #[cfg(not(target_os = "linux"))]
    let result: Result<(), Box<dyn std::error::Error>> =
        Err("GUEST_LINUX_PROFILE_UNVERIFIED".into());
    if let Err(error) = result {
        eprintln!(
            "{}",
            serde_json::json!({"issue":error.to_string().chars().filter(|c|!c.is_control()).take(256).collect::<String>(),"productionPublicationAllowed":false,"committed":false})
        );
        std::process::exit(5);
    }
}
