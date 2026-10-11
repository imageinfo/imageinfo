use super::{Error, Limits, Result};
use std::{
    fs::{self, File, OpenOptions},
    io::{Read, Seek, SeekFrom, Write},
    path::Path,
    time::{SystemTime, UNIX_EPOCH},
};

/// Reparse the live source and resolve a named preview. Imported snapshot ranges
/// are never accepted as authority to read or write a filesystem path.
pub fn extract(
    source_path: &Path,
    destination: &Path,
    name: &str,
    limits: Limits,
    dry_run: bool,
) -> Result<u64> {
    if !fs::metadata(source_path)?.is_file() {
        return Err(Error::unsupported("Only regular file inputs are supported"));
    }
    let mut source = File::open(source_path)?;
    let before = source.metadata()?;
    let metadata = super::read(&mut source, limits)?;
    let choices: Vec<_> = metadata
        .previews
        .iter()
        .filter(|p| p.name == name)
        .collect();
    if choices.len() != 1 {
        return Err(Error::unsupported(
            "Preview selector is missing or ambiguous",
        ));
    }
    let preview = choices[0];
    match fs::symlink_metadata(destination) {
        Ok(_) => {
            return Err(Error {
                code: "DESTINATION_EXISTS",
                message: "Extraction refuses an existing destination".into(),
            });
        }
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => {}
        Err(e) => return Err(e.into()),
    }
    if dry_run {
        return Ok(preview.range.length);
    }
    let parent = destination
        .parent()
        .filter(|p| !p.as_os_str().is_empty())
        .unwrap_or_else(|| Path::new("."));
    let stamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos();
    let stage = parent.join(format!(
        ".imageinfo-extract-{}-{stamp}.tmp",
        std::process::id()
    ));
    let mut output = OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&stage)?;
    let operation = (|| -> Result<u64> {
        source.seek(SeekFrom::Start(preview.range.offset))?;
        let mut remaining = preview.range.length;
        let mut buffer = [0u8; 32768];
        while remaining > 0 {
            let count = remaining.min(buffer.len() as u64) as usize;
            source.read_exact(&mut buffer[..count])?;
            output.write_all(&buffer[..count])?;
            remaining -= count as u64;
        }
        output.flush()?;
        output.sync_all()?;
        drop(output);
        let after = source.metadata()?;
        if before.len() != after.len() || before.modified().ok() != after.modified().ok() {
            return Err(Error {
                code: "SOURCE_CHANGED",
                message: "Source changed during extraction".into(),
            });
        }
        // rename() replaces an existing destination on Unix. A same-directory
        // hard link instead publishes without clobbering a racing destination.
        // Unsupported filesystems fail; there is no weaker overwrite fallback.
        fs::hard_link(&stage, destination).map_err(|e| Error {
            code: if e.kind() == std::io::ErrorKind::AlreadyExists {
                "DESTINATION_EXISTS"
            } else {
                "OUTPUT_IO"
            },
            message: format!("No-clobber publication failed ({:?})", e.kind()),
        })?;
        Ok(preview.range.length)
    })();
    let cleanup = fs::remove_file(&stage);
    match (operation, cleanup) {
        (Ok(_), Err(_)) => Err(Error {
            code: "CLEANUP_REQUIRED",
            message: "Extraction published, but its temporary link requires cleanup".into(),
        }),
        (result, _) => result,
    }
}
