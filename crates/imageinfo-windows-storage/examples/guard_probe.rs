//! Test actor endpoint, authored files only. No production CLI integration.
use imageinfo_windows_storage::GuardedSource;
use std::{
    io::{self, Write},
    path::Path,
};
fn main() {
    let path = std::env::args_os().nth(1).expect("authored source path");
    #[cfg(windows)]
    if std::env::args_os()
        .nth(2)
        .is_some_and(|arg| arg == "--existing-access")
    {
        use std::{fs::OpenOptions, os::windows::fs::OpenOptionsExt};
        match OpenOptions::new()
            .access_mode(0x8003_0000)
            .share_mode(1)
            .custom_flags(0x0020_0000)
            .open(&path)
        {
            Err(error) => println!("acquisition-refused:{:?}", error.raw_os_error()),
            Ok(_held) => println!("existing-access-acquired"),
        }
        return;
    }
    let mut source = match GuardedSource::open(Path::new(&path), 1024) {
        Ok(source) => source,
        Err(error) => {
            println!("acquisition-refused:{:?}", error.raw_os_error());
            return;
        }
    };
    println!("guard-acquired");
    io::stdout().flush().unwrap();
    let mut line = String::new();
    io::stdin().read_line(&mut line).unwrap();
    println!(
        "check-{}",
        if source.check().is_ok() {
            "matched"
        } else {
            "conflict"
        }
    );
}
