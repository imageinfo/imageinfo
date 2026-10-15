//! Explicit, read-only path association. A result is an observation, not a lease.
use serde::Serialize;
use std::{
    fmt, fs,
    path::{Path, PathBuf},
};

/// Maximum entries examined in each selected file's parent directory.
pub const MAX_DIRECTORY_ENTRIES: usize = 4096;

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct ResolvedPair {
    pub raw_path: PathBuf,
    pub sidecar_path: PathBuf,
    pub association: &'static str,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct PairingError {
    pub code: &'static str,
    pub message: String,
}

impl PairingError {
    fn new(code: &'static str, message: &str) -> Self {
        Self {
            code,
            message: message.into(),
        }
    }
}
impl fmt::Display for PairingError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}: {}", self.code, self.message)
    }
}
impl std::error::Error for PairingError {}

fn io_error(error: std::io::Error) -> PairingError {
    PairingError {
        code: "PAIRING_IO",
        message: format!("Pairing input I/O failed ({:?})", error.kind()),
    }
}

/// Associate exactly the two supplied existing regular-file paths.
///
/// No filename convention selects a sidecar. Contents are not read or validated.
/// Symlinks are followed, but aliases to the same file are refused. Identity is
/// compared while both read-only file handles remain open. Returned paths have
/// no continuing binding once the call returns.
pub fn resolve_pair(raw: &Path, sidecar: Option<&Path>) -> Result<ResolvedPair, PairingError> {
    let sidecar = sidecar.ok_or_else(|| {
        PairingError::new(
            "EXPLICIT_SIDECAR_REQUIRED",
            "Select an existing sidecar path explicitly; no basename association is inferred.",
        )
    })?;
    let raw_path = canonical_file(raw, false)?;
    let sidecar_path = canonical_file(sidecar, true)?;
    if raw_path == sidecar_path {
        return Err(PairingError::new(
            "PAIRING_SAME_FILE",
            "RAW and sidecar paths resolve to the same file.",
        ));
    }
    // Check both caller spellings and resolved names: a symlink must not hide
    // ambiguity at either selected directory entry.
    for path in [raw, sidecar, raw_path.as_path(), sidecar_path.as_path()] {
        check_case(path)?;
    }
    different_files(&raw_path, &sidecar_path)?;
    Ok(ResolvedPair {
        raw_path,
        sidecar_path,
        association: "explicit_paths",
    })
}

fn canonical_file(path: &Path, sidecar: bool) -> Result<PathBuf, PairingError> {
    let canonical = fs::canonicalize(path).map_err(|error| {
        if error.kind() == std::io::ErrorKind::NotFound {
            PairingError::new(
                if sidecar {
                    "SIDECAR_MISSING"
                } else {
                    "RAW_MISSING"
                },
                "Selected input does not exist; pairing never creates files.",
            )
        } else {
            io_error(error)
        }
    })?;
    if !fs::metadata(&canonical).map_err(io_error)?.is_file() {
        return Err(PairingError::new(
            "PAIRING_NOT_FILE",
            "Both selected inputs must be existing regular files.",
        ));
    }
    Ok(canonical)
}

fn check_case(path: &Path) -> Result<(), PairingError> {
    let name = path
        .file_name()
        .and_then(|name| name.to_str())
        .filter(|name| name.is_ascii())
        .ok_or_else(|| {
            PairingError::new(
                "PAIRING_NAME_UNSUPPORTED",
                "Selected leaf names must be ASCII; Unicode case equivalence is not qualified.",
            )
        })?;
    let parent = path
        .parent()
        .filter(|parent| !parent.as_os_str().is_empty())
        .unwrap_or_else(|| Path::new("."));
    let mut matches = 0;
    for (index, entry) in fs::read_dir(parent).map_err(io_error)?.enumerate() {
        if index >= MAX_DIRECTORY_ENTRIES {
            return Err(PairingError::new(
                "PAIRING_DIRECTORY_LIMIT",
                "Selected parent directory exceeds the bounded entry scan.",
            ));
        }
        let entry = entry.map_err(io_error)?;
        if entry
            .file_name()
            .to_str()
            .is_some_and(|other| other.eq_ignore_ascii_case(name))
        {
            matches += 1;
        }
    }
    if matches != 1 {
        return Err(PairingError::new(
            "PAIRING_CASE_AMBIGUITY",
            "Selected leaf has absent or multiple ASCII case-equivalent directory entries.",
        ));
    }
    Ok(())
}

#[cfg(any(unix, windows))]
fn different_files(raw: &Path, sidecar: &Path) -> Result<(), PairingError> {
    let raw =
        same_file::Handle::from_file(fs::File::open(raw).map_err(io_error)?).map_err(io_error)?;
    let sidecar = same_file::Handle::from_file(fs::File::open(sidecar).map_err(io_error)?)
        .map_err(io_error)?;
    if !raw.as_file().metadata().map_err(io_error)?.is_file()
        || !sidecar.as_file().metadata().map_err(io_error)?.is_file()
    {
        return Err(PairingError::new(
            "PAIRING_NOT_FILE",
            "Both opened inputs must be regular files.",
        ));
    }
    if raw == sidecar {
        Err(PairingError::new(
            "PAIRING_SAME_FILE",
            "Selected paths are aliases of the same held file.",
        ))
    } else {
        Ok(())
    }
}

#[cfg(not(any(unix, windows)))]
fn different_files(_raw: &Path, _sidecar: &Path) -> Result<(), PairingError> {
    Err(PairingError::new(
        "PAIRING_IDENTITY_UNAVAILABLE",
        "File identity is not supported on this platform.",
    ))
}
