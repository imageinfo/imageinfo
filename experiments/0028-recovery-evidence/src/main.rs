use std::{error::Error, path::Path};

fn main() {
    if let Err(error) = run() {
        eprintln!("Research operation failed: {error}");
        std::process::exit(1);
    }
}

fn run() -> Result<(), Box<dyn Error>> {
    let args: Vec<_> = std::env::args_os().skip(1).collect();
    if args.len() < 2 {
        return Err(
            "Use inspect DIR, worker DIR [INPUT] [--barriers], or hold-directory DIR".into(),
        );
    }
    let command = args[0].to_str().ok_or("Invalid command")?;
    let root = Path::new(&args[1]);
    if command == "hold-directory" && args.len() == 2 {
        return hold_directory(root);
    }
    #[cfg(target_os = "linux")]
    {
        use imageinfo_recovery_probe::linux;
        if command == "inspect" && args.len() == 2 {
            println!("{}", linux::inspect(root));
            return Ok(());
        }
        if command == "worker" && (2..=4).contains(&args.len()) {
            let barriers = args.last().is_some_and(|a| a == "--barriers");
            let input = args.get(2).filter(|a| *a != "--barriers").map(Path::new);
            if args.len() == 4 && !barriers {
                return Err("Invalid worker arguments".into());
            }
            return linux::worker(root, input, barriers);
        }
    }
    #[cfg(not(target_os = "linux"))]
    if matches!(command, "inspect" | "worker") {
        return Err(
            "STORAGE_PROFILE_UNVERIFIED: Linux descriptor probe only; no Windows/macOS backend"
                .into(),
        );
    }
    Err("Invalid research command/arguments".into())
}

#[cfg(windows)]
fn hold_directory(path: &Path) -> Result<(), Box<dyn Error>> {
    use std::{
        fs::OpenOptions,
        io::{self, Write},
        os::windows::fs::{MetadataExt, OpenOptionsExt},
    };
    // Qualification of an ordinary read directory handle, not an elevated volume
    // flush or a complete Windows persistence protocol. No host privileges change.
    let file = OpenOptions::new()
        .read(true)
        .share_mode(1)
        .custom_flags(0x02000000 | 0x00200000)
        .open(path)?;
    if !file.metadata()?.is_dir() || file.metadata()?.file_attributes() & 0x400 != 0 {
        return Err("DIRECT_DIRECTORY_REQUIRED".into());
    }
    println!("directory-open");
    io::stdout().flush()?;
    let mut line = String::new();
    io::stdin().read_line(&mut line)?;
    let result = file.sync_all();
    println!(
        "{}",
        serde_json::json!({"directoryFlushCallSucceeded":result.is_ok(),
        "osError":result.err().and_then(|e|e.raw_os_error()),"profileVerified":false})
    );
    Ok(())
}
#[cfg(not(windows))]
fn hold_directory(_: &Path) -> Result<(), Box<dyn Error>> {
    Err("Windows directory qualification only".into())
}
