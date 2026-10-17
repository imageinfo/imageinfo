use crate::{FileSnapshot, MAX_ARTIFACT_BYTES, native, validate_leaf};
use std::{
    cell::Cell,
    fs::{self, File, OpenOptions},
    io::{self, Read, Seek, SeekFrom, Write},
    os::windows::{
        ffi::OsStrExt,
        fs::{MetadataExt, OpenOptionsExt},
    },
    path::{Component, Path, PathBuf, Prefix},
};
use windows_sys::Win32::Storage::FileSystem::*;

pub(crate) fn validate_path(path: &Path) -> io::Result<()> {
    if !path.is_absolute() || path.as_os_str().encode_wide().count() > 200 {
        return Err(io::Error::new(
            io::ErrorKind::Unsupported,
            "UNSUPPORTED_DOS_PATH",
        ));
    }
    let spelling = path.as_os_str().to_string_lossy();
    if spelling.contains('/') || spelling.split('\\').any(|p| matches!(p, "." | "..")) {
        return Err(io::Error::new(
            io::ErrorKind::Unsupported,
            "UNSUPPORTED_PATH_COMPONENT",
        ));
    }
    for part in path.components() {
        match part {
            Component::Prefix(p) if matches!(p.kind(), Prefix::Disk(_)) => {}
            Component::RootDir => {}
            Component::Normal(n) => {
                validate_leaf(n.to_str().ok_or_else(|| {
                    io::Error::new(io::ErrorKind::Unsupported, "NON_UNICODE_PATH")
                })?)?
            }
            _ => {
                return Err(io::Error::new(
                    io::ErrorKind::Unsupported,
                    "UNSUPPORTED_PATH_COMPONENT",
                ));
            }
        }
    }
    Ok(())
}

fn exact_existing(path: &Path) -> io::Result<()> {
    let Some(name) = path.file_name() else {
        return Ok(());
    };
    let parent = path
        .parent()
        .ok_or_else(|| io::Error::other("PARENT_REQUIRED"))?;
    let mut exact = false;
    let mut folded = 0usize;
    for entry in fs::read_dir(parent)?.take(4097) {
        let name_now = entry?.file_name();
        if name_now.to_string_lossy().to_uppercase() == name.to_string_lossy().to_uppercase() {
            folded += 1;
        }
        exact |= name_now == name;
    }
    // Bounded enumeration must be complete, including names unrelated to ours.
    if fs::read_dir(parent)?.take(4097).count() > 4096 || !exact || folded != 1 {
        return Err(io::Error::new(
            io::ErrorKind::Unsupported,
            "CASE_ALIAS_OR_DIRECTORY_BOUND",
        ));
    }
    Ok(())
}

pub(crate) fn hold_ancestors(
    path: &Path,
    writable_parent: bool,
) -> io::Result<Vec<(PathBuf, File)>> {
    validate_path(path)?;
    let mut current = PathBuf::new();
    let mut held = Vec::new();
    for part in path.components() {
        current.push(part.as_os_str());
        if !current.has_root() {
            continue;
        }
        let file = OpenOptions::new()
            .read(true)
            .write(writable_parent && current == path)
            .share_mode(FILE_SHARE_READ | FILE_SHARE_WRITE)
            .custom_flags(FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT)
            .open(&current)?;
        let meta = file.metadata()?;
        if !meta.is_dir() || meta.file_attributes() & FILE_ATTRIBUTE_REPARSE_POINT != 0 {
            return Err(io::Error::new(
                io::ErrorKind::Unsupported,
                "REPARSE_OR_NOT_DIRECTORY",
            ));
        }
        if writable_parent
            && current == path
            && meta.file_attributes()
                & (FILE_ATTRIBUTE_COMPRESSED | FILE_ATTRIBUTE_ENCRYPTED | FILE_ATTRIBUTE_OFFLINE)
                != 0
        {
            return Err(io::Error::new(
                io::ErrorKind::Unsupported,
                "UNSUPPORTED_PARENT_INHERITANCE",
            ));
        }
        native::check_case(&file)?;
        exact_existing(&current)?;
        held.push((current.clone(), file));
    }
    if held.is_empty() {
        return Err(io::Error::other("ANCESTRY_REQUIRED"));
    }
    Ok(held)
}

pub(crate) fn observe(file: &File) -> io::Result<FileSnapshot> {
    let info = winapi_util::file::information(file)?;
    Ok(FileSnapshot {
        volume_serial_number: info.volume_serial_number(),
        file_index: info.file_index(),
        size: info.file_size(),
        links: info.number_of_links(),
        attributes: info.file_attributes() as u32,
        creation_time: file.metadata()?.creation_time(),
        last_write_time: info
            .last_write_time()
            .ok_or_else(|| io::Error::other("TIME_UNAVAILABLE"))?,
        owner_dacl: native::security(file)?,
    })
}

pub(crate) fn open_source(path: &Path) -> io::Result<File> {
    OpenOptions::new()
        .access_mode(0x80020000)
        .share_mode(FILE_SHARE_READ)
        .custom_flags(FILE_FLAG_OPEN_REPARSE_POINT)
        .open(path)
}

pub(crate) fn check_binding(path: &Path, file: &File) -> io::Result<()> {
    let observed = OpenOptions::new()
        .access_mode(0x20080)
        .share_mode(7)
        .custom_flags(FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT)
        .open(path)?;
    let a = observe(file)?;
    let b = observe(&observed)?;
    if a.volume_serial_number != b.volume_serial_number || a.file_index != b.file_index {
        return Err(io::Error::other("PATH_OBJECT_CHANGED"));
    }
    exact_existing(path)
}

fn bounded_read(file: &mut File, size: u64) -> io::Result<Vec<u8>> {
    file.seek(SeekFrom::Start(0))?;
    let mut bytes = Vec::new();
    file.take(size + 1).read_to_end(&mut bytes)?;
    if bytes.len() as u64 != size {
        return Err(io::Error::other("ARTIFACT_SIZE_CHANGED"));
    }
    Ok(bytes)
}

fn check_plain(file: &File, snapshot: &FileSnapshot) -> io::Result<()> {
    if snapshot.links != 1
        || snapshot.attributes
            & !(FILE_ATTRIBUTE_ARCHIVE
                | FILE_ATTRIBUTE_NORMAL
                | FILE_ATTRIBUTE_NOT_CONTENT_INDEXED
                | FILE_ATTRIBUTE_READONLY)
            != 0
    {
        return Err(io::Error::new(
            io::ErrorKind::Unsupported,
            "UNSUPPORTED_FILE_PROPERTY",
        ));
    }
    if !file.metadata()?.is_file() {
        return Err(io::Error::new(
            io::ErrorKind::Unsupported,
            "REGULAR_FILE_REQUIRED",
        ));
    }
    native::check_streams(file)
}

/// Source opened without write/delete access. Original bytes, creation/write
/// times, attributes and owner/DACL are never rebased after the initial read.
pub struct GuardedSource {
    file: File,
    path: PathBuf,
    before: FileSnapshot,
    bytes: Vec<u8>,
    ancestry: Vec<(PathBuf, File)>,
    failed: bool,
}
impl GuardedSource {
    pub fn open(path: &Path, max_bytes: u64) -> io::Result<Self> {
        validate_path(path)?;
        if max_bytes > MAX_ARTIFACT_BYTES {
            return Err(io::Error::new(io::ErrorKind::Unsupported, "SOURCE_BOUND"));
        }
        let ancestry = hold_ancestors(
            path.parent()
                .ok_or_else(|| io::Error::other("PARENT_REQUIRED"))?,
            false,
        )?;
        native::check_local_ntfs(&ancestry.last().unwrap().1, path)?;
        let mut file = open_source(path)?;
        let before = observe(&file)?;
        if before.size > max_bytes {
            return Err(io::Error::new(io::ErrorKind::Unsupported, "SOURCE_BOUND"));
        }
        check_plain(&file, &before)?;
        check_binding(path, &file)?;
        let bytes = bounded_read(&mut file, before.size)?;
        if observe(&file)? != before {
            return Err(io::Error::other("SOURCE_CHANGED_DURING_READ"));
        }
        Ok(Self {
            file,
            path: path.into(),
            before,
            bytes,
            ancestry,
            failed: false,
        })
    }
    pub fn snapshot(&self) -> &FileSnapshot {
        &self.before
    }
    pub fn check(&mut self) -> io::Result<()> {
        if self.failed {
            return Err(io::Error::other("SOURCE_PREVIOUS_CONFLICT"));
        }
        let result = self.check_inner();
        self.failed |= result.is_err();
        result
    }
    fn check_inner(&mut self) -> io::Result<()> {
        for (path, held) in &self.ancestry {
            check_binding(path, held)?;
            native::check_case(held)?;
            if held.metadata()?.file_attributes() & FILE_ATTRIBUTE_REPARSE_POINT != 0 {
                return Err(io::Error::other("ANCESTOR_REPARSE_CONFLICT"));
            }
        }
        check_binding(&self.path, &self.file)?;
        check_plain(&self.file, &self.before)?;
        if observe(&self.file)? != self.before
            || bounded_read(&mut self.file, self.before.size)? != self.bytes
            || observe(&self.file)? != self.before
        {
            return Err(io::Error::other("SOURCE_PROPERTY_OR_BYTE_CONFLICT"));
        }
        Ok(())
    }
    pub fn read_exact_bytes(&mut self) -> io::Result<Vec<u8>> {
        self.check()?;
        Ok(self.bytes.clone())
    }
}

/// Read-only restart directory/ancestry hold. This type exposes no creation,
/// flush, rename or removal operation. Dropping it only closes read handles.
pub struct ExistingRoot {
    path: PathBuf,
    ancestry: Vec<(PathBuf, File)>,
    before: FileSnapshot,
    parent_before: FileSnapshot,
    security: native::PrivateSecurity,
    failed: Cell<bool>,
}
impl ExistingRoot {
    pub fn open(path: &Path) -> io::Result<Self> {
        let ancestry = hold_ancestors(path, false)?;
        if ancestry.len() < 2 {
            return Err(io::Error::other("ROOT_PARENT_REQUIRED"));
        }
        let file = &ancestry.last().unwrap().1;
        native::check_local_ntfs(file, path)?;
        let before = observe(file)?;
        let parent_before = observe(&ancestry[ancestry.len() - 2].1)?;
        let root = Self {
            path: path.into(),
            ancestry,
            before,
            parent_before,
            security: native::PrivateSecurity::current()?,
            failed: Cell::new(false),
        };
        root.check()?;
        Ok(root)
    }
    pub fn snapshot(&self) -> &FileSnapshot {
        &self.before
    }
    pub fn parent_snapshot(&self) -> &FileSnapshot {
        &self.parent_before
    }
    pub fn check(&self) -> io::Result<()> {
        if self.failed.get() {
            return Err(io::Error::other("ROOT_PREVIOUS_CONFLICT"));
        }
        let result = self.check_inner();
        self.failed.set(result.is_err());
        result
    }
    fn check_inner(&self) -> io::Result<()> {
        for (path, file) in &self.ancestry {
            check_binding(path, file)?;
            native::check_case(file)?;
            if file.metadata()?.file_attributes() & FILE_ATTRIBUTE_REPARSE_POINT != 0 {
                return Err(io::Error::other("ANCESTOR_REPARSE_CONFLICT"));
            }
        }
        let file = &self.ancestry.last().unwrap().1;
        self.security.check(file)?;
        native::check_directory_streams(file)?;
        let now = observe(file)?;
        // Directory size/write time change as children are created. Compare the
        // declared stable properties, never substitute file snapshot values.
        if !same_directory_properties(&now, &self.before)
            || now.attributes
                & !(FILE_ATTRIBUTE_DIRECTORY
                    | FILE_ATTRIBUTE_ARCHIVE
                    | FILE_ATTRIBUTE_NOT_CONTENT_INDEXED)
                != 0
            || !same_directory_properties(
                &observe(&self.ancestry[self.ancestry.len() - 2].1)?,
                &self.parent_before,
            )
        {
            return Err(io::Error::other("ROOT_PROPERTIES_CONFLICT"));
        }
        Ok(())
    }
    /// Complete bounded exact namespace; names are observations, never paths
    /// imported from a transaction record.
    pub fn entries(&self) -> io::Result<Vec<std::ffi::OsString>> {
        self.check()?;
        let mut names = Vec::new();
        for entry in fs::read_dir(&self.path)?.take(7) {
            names.push(entry?.file_name());
        }
        if names.len() > 5 {
            return Err(io::Error::other("ROOT_ENTRY_BOUND"));
        }
        self.check()?;
        names.sort();
        Ok(names)
    }
}

fn same_directory_properties(a: &FileSnapshot, b: &FileSnapshot) -> bool {
    a.volume_serial_number == b.volume_serial_number
        && a.file_index == b.file_index
        && a.links == b.links
        && a.attributes & !FILE_ATTRIBUTE_ARCHIVE == b.attributes & !FILE_ATTRIBUTE_ARCHIVE
        && a.creation_time == b.creation_time
        && a.owner_dacl == b.owner_dacl
}

/// Caller-available logical bytes on the selected existing local NTFS parent.
/// Complete ancestry stays held and identity/properties are checked around the
/// read-only query. This is advisory: no reservation, quota or free-space promise.
pub fn available_bytes(parent: &Path) -> io::Result<u64> {
    let ancestry = hold_ancestors(parent, false)?;
    native::check_local_ntfs(&ancestry.last().unwrap().1, parent)?;
    let before: Vec<_> = ancestry
        .iter()
        .map(|(_, file)| observe(file))
        .collect::<io::Result<_>>()?;
    let check = || -> io::Result<()> {
        for ((path, file), expected) in ancestry.iter().zip(&before) {
            check_binding(path, file)?;
            native::check_case(file)?;
            native::check_directory_streams(file)?;
            if file.metadata()?.file_attributes() & FILE_ATTRIBUTE_REPARSE_POINT != 0
                || !same_directory_properties(&observe(file)?, expected)
            {
                return Err(io::Error::other("AVAILABILITY_PARENT_CONFLICT"));
            }
        }
        Ok(())
    };
    check()?;
    let available = native::available_bytes(parent)?;
    check()?;
    Ok(available)
}

/// Fresh ordinary owner-only directory. Destruction retains the entire namespace.
pub struct PrivateRoot {
    file: File,
    path: PathBuf,
    before: FileSnapshot,
    parent_before: FileSnapshot,
    security: native::PrivateSecurity,
    ancestry: Vec<(PathBuf, File)>,
    failed: Cell<bool>,
}
impl PrivateRoot {
    pub fn create(path: &Path) -> io::Result<Self> {
        validate_path(path)?;
        let parent = path
            .parent()
            .ok_or_else(|| io::Error::other("PARENT_REQUIRED"))?;
        let leaf = path
            .file_name()
            .ok_or_else(|| io::Error::other("ROOT_LEAF_REQUIRED"))?;
        validate_leaf(
            leaf.to_str()
                .ok_or_else(|| io::Error::new(io::ErrorKind::Unsupported, "ROOT_ENCODING"))?,
        )?;
        let ancestry = hold_ancestors(parent, true)?;
        let parent_file = &ancestry.last().unwrap().1;
        native::check_local_ntfs(parent_file, path)?;
        // Probe required writable parent flush before creating a target artifact.
        parent_file.sync_all()?;
        let parent_before = observe(parent_file)?;
        let security = native::PrivateSecurity::current()?;
        let file = security.create_directory(parent_file, Path::new(leaf))?;
        let before = observe(&file)?;
        let root = Self {
            file,
            path: path.into(),
            before,
            parent_before,
            security,
            ancestry,
            failed: Cell::new(false),
        };
        root.check()?;
        Ok(root)
    }
    pub fn path(&self) -> &Path {
        &self.path
    }
    pub fn snapshot(&self) -> &FileSnapshot {
        &self.before
    }
    /// Actual containing-directory observation captured from its continuously
    /// held writable handle before root creation. This is never a path reopen.
    pub fn parent_snapshot(&self) -> &FileSnapshot {
        &self.parent_before
    }
    pub fn check(&self) -> io::Result<()> {
        if self.failed.get() {
            return Err(io::Error::other("ROOT_PREVIOUS_CONFLICT"));
        }
        let result = self.check_inner();
        if result.is_err() {
            self.failed.set(true);
        }
        result
    }
    fn check_inner(&self) -> io::Result<()> {
        for (path, held) in &self.ancestry {
            check_binding(path, held)?;
            native::check_case(held)?;
            if held.metadata()?.file_attributes() & FILE_ATTRIBUTE_REPARSE_POINT != 0 {
                return Err(io::Error::other("ANCESTOR_REPARSE_CONFLICT"));
            }
        }
        check_binding(&self.path, &self.file)?;
        self.security.check(&self.file)?;
        native::check_case(&self.file)?;
        native::check_directory_streams(&self.file)?;
        let now = observe(&self.file)?;
        if now.creation_time != self.before.creation_time
            || now.attributes & !FILE_ATTRIBUTE_ARCHIVE
                != self.before.attributes & !FILE_ATTRIBUTE_ARCHIVE
            || now.attributes
                & !(FILE_ATTRIBUTE_DIRECTORY
                    | FILE_ATTRIBUTE_ARCHIVE
                    | FILE_ATTRIBUTE_NOT_CONTENT_INDEXED)
                != 0
        {
            return Err(io::Error::other("ROOT_PROPERTIES_CONFLICT"));
        }
        Ok(())
    }
    pub fn flush(&self) -> io::Result<()> {
        self.file.sync_all()
    }
    pub fn flush_parent(&self) -> io::Result<()> {
        self.ancestry.last().unwrap().1.sync_all()
    }
    pub fn create_artifact(
        &self,
        leaf: &str,
        bytes: &[u8],
        max_bytes: u64,
    ) -> io::Result<HeldArtifact> {
        validate_leaf(leaf)?;
        if max_bytes > MAX_ARTIFACT_BYTES || bytes.len() as u64 > max_bytes {
            return Err(io::Error::new(io::ErrorKind::Unsupported, "ARTIFACT_BOUND"));
        }
        self.check()?;
        let path = self.path.join(leaf);
        let mut file = self.security.create_file(&path)?;
        file.write_all(bytes)?;
        let before = observe(&file)?;
        let mut artifact = HeldArtifact {
            file,
            path,
            before,
            bytes: bytes.to_vec(),
            root_identity: (self.before.volume_serial_number, self.before.file_index),
            publication_attempted: false,
            failed: false,
        };
        artifact.check(self)?;
        Ok(artifact)
    }
}

/// Exclusive-created artifact. Call failures never delete or reopen it for write.
pub struct HeldArtifact {
    file: File,
    path: PathBuf,
    before: FileSnapshot,
    bytes: Vec<u8>,
    root_identity: (u64, u64),
    publication_attempted: bool,
    failed: bool,
}
impl HeldArtifact {
    pub fn snapshot(&self) -> &FileSnapshot {
        &self.before
    }
    pub fn bytes(&self) -> &[u8] {
        &self.bytes
    }
    pub fn publication_attempted(&self) -> bool {
        self.publication_attempted
    }
    pub fn check(&mut self, root: &PrivateRoot) -> io::Result<()> {
        if self.failed {
            return Err(io::Error::other("ARTIFACT_PREVIOUS_CONFLICT"));
        }
        let result = self.check_inner(root);
        self.failed |= result.is_err();
        result
    }
    fn check_inner(&mut self, root: &PrivateRoot) -> io::Result<()> {
        if self.root_identity != (root.before.volume_serial_number, root.before.file_index) {
            return Err(io::Error::other("FOREIGN_ROOT"));
        }
        root.check()?;
        root.security.check(&self.file)?;
        check_binding(&self.path, &self.file)?;
        check_plain(&self.file, &self.before)?;
        if observe(&self.file)? != self.before
            || bounded_read(&mut self.file, self.before.size)? != self.bytes
            || observe(&self.file)? != self.before
        {
            return Err(io::Error::other("ARTIFACT_PROPERTY_OR_BYTE_CONFLICT"));
        }
        Ok(())
    }
    pub fn flush(&self) -> io::Result<()> {
        self.file.sync_all()
    }
    /// One held-object, zero-replacement-flags rename. Once attempted, every
    /// error is possible publication; a caller must retain uncertainty/artifacts.
    pub fn publish_no_replace(&mut self, root: &PrivateRoot, output_leaf: &str) -> io::Result<()> {
        if self.publication_attempted {
            return Err(io::Error::other("PUBLICATION_ALREADY_ATTEMPTED"));
        }
        validate_leaf(output_leaf)?;
        self.check(root)?;
        let destination = root.path.join(output_leaf);
        if destination == self.path {
            return Err(io::Error::other("DISTINCT_OUTPUT_REQUIRED"));
        }
        self.publication_attempted = true;
        native::rename(&self.file, &destination)?;
        self.path = destination;
        self.check(root)
    }
}
