//! One held existing object, one same-parent no-replace rename.
//!
//! This preserves the live object rather than replaying a property snapshot.
//! It grants neither occupied-target replacement nor a committed result.
use crate::{FileSnapshot, MAX_ARTIFACT_BYTES, native, validate_leaf, windows};
use std::{
    fs::{self, File, OpenOptions},
    io::{self, Read, Seek, SeekFrom},
    os::windows::fs::OpenOptionsExt,
    path::{Path, PathBuf},
};

/// A synchronous observation, not a persistence acknowledgement.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ExistingMoveOutcome {
    /// No rename call was issued. No rollback or cleanup is necessary.
    NotAttempted,
    /// The issued call failed and guarded observations retain the original map.
    ObservedNoEffect,
    /// The held object is observed at the new name and absent at the old name.
    ObservedMoved,
    /// A call was issued but its exact final bindings could not be established.
    RecoveryRequired,
}

/// Keeps source identity/content/name custody and the entire parent lineage.
/// Drop only closes handles. It never restores, deletes, or retries a rename.
pub struct HeldExistingMove {
    source: File,
    lineage: Vec<(PathBuf, File)>,
    old_name: PathBuf,
    new_name: PathBuf,
    original: FileSnapshot,
    bytes: Vec<u8>,
    attempted: bool,
    call_succeeded: bool,
}

fn ordinary_ascii_leaf(path: &Path) -> io::Result<&str> {
    let leaf = path
        .file_name()
        .and_then(|p| p.to_str())
        .ok_or_else(|| io::Error::other("MOVE_LEAF_UNSUPPORTED"))?;
    validate_leaf(leaf)?;
    if !leaf.is_ascii() {
        return Err(io::Error::other("MOVE_LEAF_UNSUPPORTED"));
    }
    Ok(leaf)
}

fn directory_spelling(parent: &Path, source: &str, destination: &str) -> io::Result<()> {
    let mut source_seen = false;
    for (index, entry) in fs::read_dir(parent)?.enumerate() {
        if index >= 4096 {
            return Err(io::Error::other("MOVE_DIRECTORY_BOUND"));
        }
        let name = entry?.file_name();
        let name = name
            .to_str()
            .ok_or_else(|| io::Error::other("MOVE_DIRECTORY_ENCODING"))?;
        if name.eq_ignore_ascii_case(source) {
            if name != source || source_seen {
                return Err(io::Error::other("MOVE_SOURCE_ALIAS"));
            }
            source_seen = true;
        }
        // The kernel also enforces collision safety. An exactly spelled occupied
        // destination is permitted here so the no-replace call can classify it.
        if name.eq_ignore_ascii_case(destination) && name != destination {
            return Err(io::Error::other("MOVE_DESTINATION_CASE_ALIAS"));
        }
    }
    if !source_seen {
        return Err(io::Error::other("MOVE_SOURCE_SPELLING"));
    }
    Ok(())
}

impl HeldExistingMove {
    /// Acquire the expected existing object without changing its ACL or properties.
    /// The supplied snapshot is only an expectation, never authority to restore it.
    pub fn open(source: &Path, destination: &Path, expected: &FileSnapshot) -> io::Result<Self> {
        windows::validate_path(source)?;
        windows::validate_path(destination)?;
        let source_leaf = ordinary_ascii_leaf(source)?;
        let destination_leaf = ordinary_ascii_leaf(destination)?;
        if source.parent() != destination.parent()
            || source_leaf.eq_ignore_ascii_case(destination_leaf)
        {
            return Err(io::Error::other("MOVE_REQUIRES_DISTINCT_SAME_PARENT_NAMES"));
        }
        let parent = source
            .parent()
            .ok_or_else(|| io::Error::other("MOVE_PARENT_REQUIRED"))?;
        let lineage = windows::hold_ancestors(parent, false)?;
        native::check_local_ntfs(
            &lineage
                .last()
                .ok_or_else(|| io::Error::other("MOVE_PARENT_REQUIRED"))?
                .1,
            source,
        )?;
        // OPEN_EXISTING is supplied by OpenOptions::open (no create/truncate).
        // DELETE belongs to this retained handle, while FILE_SHARE_READ refuses
        // conflicting default-stream writers and other DELETE-capable opens.
        let mut held = OpenOptions::new()
            .access_mode(0x8003_0000)
            .share_mode(1)
            .custom_flags(0x0020_0000)
            .open(source)?;
        let observed = windows::observe(&held)?;
        if observed != *expected
            || observed.links != 1
            || observed.size > MAX_ARTIFACT_BYTES
            || !held.metadata()?.is_file()
            || observed.attributes & !(0x20 | 0x80 | 0x2000) != 0
        {
            return Err(io::Error::other("MOVE_SOURCE_UNSUPPORTED_OR_CHANGED"));
        }
        native::check_streams(&held)?;
        windows::check_binding(source, &held)?;
        directory_spelling(parent, source_leaf, destination_leaf)?;
        let mut bytes = Vec::new();
        (&mut held)
            .take(MAX_ARTIFACT_BYTES + 1)
            .read_to_end(&mut bytes)?;
        if bytes.len() as u64 != observed.size {
            return Err(io::Error::other("MOVE_SOURCE_LENGTH_CHANGED"));
        }
        held.seek(SeekFrom::Start(0))?;
        Ok(Self {
            source: held,
            lineage,
            old_name: source.into(),
            new_name: destination.into(),
            original: observed,
            bytes,
            attempted: false,
            call_succeeded: false,
        })
    }

    pub fn snapshot(&self) -> &FileSnapshot {
        &self.original
    }
    pub fn attempted(&self) -> bool {
        self.attempted
    }

    fn check_lineage(&self) -> io::Result<()> {
        for (path, file) in &self.lineage {
            windows::check_binding(path, file)?;
            native::check_case(file)?;
            let metadata = file.metadata()?;
            use std::os::windows::fs::MetadataExt;
            if !metadata.is_dir() || metadata.file_attributes() & 0x400 != 0 {
                return Err(io::Error::other("MOVE_ANCESTRY_CHANGED"));
            }
        }
        Ok(())
    }

    fn check_bytes(&mut self) -> io::Result<()> {
        self.source.seek(SeekFrom::Start(0))?;
        let mut current = Vec::new();
        (&mut self.source)
            .take(MAX_ARTIFACT_BYTES + 1)
            .read_to_end(&mut current)?;
        if current != self.bytes {
            return Err(io::Error::other("MOVE_CONTENT_CHANGED"));
        }
        Ok(())
    }

    fn binding(&self, path: &Path) -> io::Result<Option<bool>> {
        let observed = match OpenOptions::new()
            .access_mode(0)
            .share_mode(7)
            .custom_flags(0x0220_0000)
            .open(path)
        {
            Ok(file) => file,
            Err(error) if error.kind() == io::ErrorKind::NotFound => return Ok(None),
            Err(error) => return Err(error),
        };
        let information = winapi_util::file::information(&observed)?;
        Ok(Some(
            information.volume_serial_number() == self.original.volume_serial_number
                && information.file_index() == self.original.file_index,
        ))
    }

    /// Issue at most one no-replace call. Cancellation is checked before it.
    /// Property edits are never reset or copied from `snapshot()`.
    pub fn execute(&mut self, cancelled: bool) -> ExistingMoveOutcome {
        if self.attempted {
            return self.inspect();
        }
        if cancelled
            || self.check_lineage().is_err()
            || windows::check_binding(&self.old_name, &self.source).is_err()
            || self.check_bytes().is_err()
        {
            return ExistingMoveOutcome::NotAttempted;
        }
        self.attempted = true;
        self.call_succeeded = native::rename(&self.source, &self.new_name).is_ok();
        self.inspect()
    }

    /// Classify actual retained bindings after an issued call, including a caller
    /// losing its earlier return value. Never replay or repair an uncertain call.
    pub fn inspect(&mut self) -> ExistingMoveOutcome {
        if !self.attempted {
            return ExistingMoveOutcome::NotAttempted;
        }
        if self.check_lineage().is_err() || self.check_bytes().is_err() {
            return ExistingMoveOutcome::RecoveryRequired;
        }
        let (old, new) = match (self.binding(&self.old_name), self.binding(&self.new_name)) {
            (Ok(old), Ok(new)) => (old, new),
            _ => return ExistingMoveOutcome::RecoveryRequired,
        };
        if self.call_succeeded && new == Some(true) && old.is_none() {
            return ExistingMoveOutcome::ObservedMoved;
        }
        if !self.call_succeeded && old == Some(true) && new != Some(true) {
            return ExistingMoveOutcome::ObservedNoEffect;
        }
        ExistingMoveOutcome::RecoveryRequired
    }
}
