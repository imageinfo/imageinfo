//! One research handle/barrier for unrelated-writer tests, not a storage backend.
use std::{
    fs::OpenOptions,
    io::{self, Write},
    path::PathBuf,
};

fn main() -> io::Result<()> {
    let path = std::env::args_os()
        .nth(1)
        .map(PathBuf::from)
        .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidInput, "Source path required"))?;
    let mut options = OpenOptions::new();
    options.read(true);
    #[cfg(windows)]
    {
        use std::os::windows::fs::OpenOptionsExt;
        options.share_mode(1); // Same guard as the candidate experiment.
    }
    let handle = options.open(path)?;
    println!("guard-open");
    io::stdout().flush()?;
    let mut line = String::new();
    io::stdin().read_line(&mut line)?;
    drop(handle);
    Ok(())
}
