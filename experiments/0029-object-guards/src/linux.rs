use rustix::fs::{self, Mode, OFlags, ResolveFlags};
use std::{
    error::Error,
    fs::File,
    io::{self, Read, Seek, SeekFrom, Write},
    os::{fd::AsRawFd, unix::fs::MetadataExt},
    path::Path,
};
type Result<T> = std::result::Result<T, Box<dyn Error>>;

pub fn anonymous_stage(path: &Path) -> Result<()> {
    let root = File::from(fs::openat2(
        fs::CWD,
        path,
        OFlags::RDONLY | OFlags::DIRECTORY | OFlags::CLOEXEC,
        Mode::empty(),
        ResolveFlags::NO_SYMLINKS,
    )?);
    let metadata = root.metadata()?;
    if metadata.uid() != rustix::process::geteuid().as_raw() || metadata.mode() & 0o777 != 0o700 {
        return Err("Private native directory required".into());
    }
    // The named-stage race in #0028 cannot be repaired with another hash check.
    // O_TMPFILE keeps this candidate unnamed; the known live descriptor supplies
    // the link source. Unsupported filesystems/proc layouts refuse, never fall back.
    let mut stage = File::from(fs::openat(
        &root,
        ".",
        OFlags::TMPFILE | OFlags::RDWR | OFlags::CLOEXEC,
        Mode::RUSR | Mode::WUSR,
    )?);
    let marker = vec![0x29; 65536];
    stage.write_all(&marker)?;
    stage.flush()?;
    stage.sync_all()?;
    let original = stage.metadata()?;
    let proc_root = File::from(fs::open(
        "/proc/self/fd",
        OFlags::RDONLY | OFlags::DIRECTORY | OFlags::CLOEXEC,
        Mode::empty(),
    )?);
    if fs::fstatfs(&proc_root)?.f_type != fs::PROC_SUPER_MAGIC {
        return Err("Trusted procfs FD view unavailable".into());
    }
    println!(
        "{}",
        serde_json::json!({"barrier":"anonymous-held","links":original.nlink(),"profileVerified":false})
    );
    io::stdout().flush()?;
    let mut line = String::new();
    io::stdin().read_line(&mut line)?;
    if line.trim() != "continue" {
        return Err("Cancelled before research link".into());
    }
    let source = stage.as_raw_fd().to_string();
    // AT_EMPTY_PATH requires an extra capability on common Linux setups. The
    // documented /proc/self/fd alternative needs no elevation and follows only
    // our generated descriptor name under the checked kernel procfs directory.
    fs::linkat(
        &proc_root,
        &source,
        &root,
        "output.bin",
        fs::AtFlags::SYMLINK_FOLLOW,
    )?;
    let installed = fs::statat(&root, "output.bin", fs::AtFlags::SYMLINK_NOFOLLOW)?;
    if installed.st_dev != original.dev() || installed.st_ino != original.ino() {
        return Err("Installed object differs".into());
    }
    stage.seek(SeekFrom::Start(0))?;
    let mut current = Vec::new();
    stage.take(65537).read_to_end(&mut current)?;
    println!(
        "{}",
        serde_json::json!({"boundObjectPublished":true,"bytesUnchanged":current==marker,
        "profileVerified":false,"productionPublicationAllowed":false,
        "note":"Anonymous pre-link stage is not a live source/path/property/durability guarantee; post-link writes remain possible"})
    );
    Ok(())
}
