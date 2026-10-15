use same_file::Handle;
use serde::Serialize;
use serde_json::{Value, json};
use std::{
    fs::{self, File, OpenOptions},
    io::{self, BufRead, Read, Seek, SeekFrom, Write},
    os::windows::fs::{MetadataExt, OpenOptionsExt},
    path::{Path, PathBuf},
};

const OLD: &[u8] = b"OLD094\n";
const NEW: &[u8] = b"NEW094\n";
const OTHER: &[u8] = b"OTHER094\n";
const LIMIT: u64 = 64;

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
struct Properties {
    len: u64,
    created100ns: u64,
    last_write100ns: u64,
    attributes: u32,
    readonly: bool,
    links: u64,
    volume: u64,
    index: u64,
}

fn properties(file: &File) -> io::Result<Properties> {
    let meta = file.metadata()?;
    let info = winapi_util::file::information(file)?;
    if !meta.is_file() || meta.file_attributes() & 0x400 != 0 || meta.len() > LIMIT {
        return Err(io::Error::other(
            "Not a bounded non-reparse ordinary marker",
        ));
    }
    Ok(Properties {
        len: meta.len(),
        created100ns: meta.creation_time(),
        last_write100ns: meta.last_write_time(),
        attributes: meta.file_attributes(),
        readonly: meta.permissions().readonly(),
        links: info.number_of_links(),
        volume: info.volume_serial_number(),
        index: info.file_index(),
    })
}

fn bytes(file: &File) -> io::Result<Vec<u8>> {
    properties(file)?;
    let mut reader = file.try_clone()?;
    reader.seek(SeekFrom::Start(0))?;
    let mut data = Vec::new();
    reader.take(LIMIT + 1).read_to_end(&mut data)?;
    if data.len() as u64 > LIMIT {
        return Err(io::Error::other("Marker byte limit"));
    }
    Ok(data)
}

fn open(path: &Path, share: u32) -> io::Result<Handle> {
    Handle::from_file(OpenOptions::new().read(true).share_mode(share).open(path)?)
}

fn directory(path: &Path, share: u32) -> io::Result<Handle> {
    Handle::from_file(
        OpenOptions::new()
            .access_mode(0)
            .share_mode(share)
            .custom_flags(0x0200_0000)
            .open(path)?,
    )
}

fn emit(value: Value) -> io::Result<()> {
    let mut out = io::stdout().lock();
    serde_json::to_writer(&mut out, &value)?;
    writeln!(out)?;
    out.flush()
}

fn gate(expected: &str) -> io::Result<()> {
    let mut line = String::new();
    io::stdin().lock().take(32).read_line(&mut line)?;
    if line.trim_end_matches(['\r', '\n']) != expected {
        return Err(io::Error::other("Exact protocol gate required"));
    }
    Ok(())
}

fn create(path: &Path, data: &[u8]) -> io::Result<Handle> {
    let mut file = OpenOptions::new()
        .read(true)
        .write(true)
        .create_new(true)
        .share_mode(1)
        .open(path)?;
    file.write_all(data)?;
    Handle::from_file(file)
}

struct Bound {
    leaf: &'static str,
    handle: Handle,
    expected: Vec<u8>,
    baseline: Properties,
}

impl Bound {
    fn create_owned(root: &Path, leaf: &'static str, expected: &[u8]) -> io::Result<Self> {
        let path = root.join(leaf);
        let writer = create(&path, expected)?;
        // A read handle that shares writes bridges the creator's writable handle
        // to the final read-only share-read guard without an identity-custody gap.
        let bridge = open(&path, 3)?;
        if bridge != writer {
            return Err(io::Error::other("Creation identity mismatch"));
        }
        drop(writer);
        let guard = open(&path, 1)?;
        if guard != bridge {
            return Err(io::Error::other("Guard identity mismatch"));
        }
        Self::capture(leaf, guard, expected)
    }

    fn capture(leaf: &'static str, handle: Handle, expected: &[u8]) -> io::Result<Self> {
        if bytes(handle.as_file())? != expected {
            return Err(io::Error::other("Authored marker mismatch"));
        }
        let baseline = properties(handle.as_file())?;
        if baseline.links != 1 {
            return Err(io::Error::other("Marker has extra links"));
        }
        Ok(Self {
            leaf,
            handle,
            expected: expected.to_vec(),
            baseline,
        })
    }
    fn verify(&self, root: &Path) -> Result<(), &'static str> {
        let current = open(&root.join(self.leaf), 7).map_err(|_| "NAME_OPEN")?;
        if current != self.handle {
            return Err("NAME_IDENTITY");
        }
        if bytes(self.handle.as_file()).map_err(|_| "MARKER_READ")? != self.expected {
            return Err("MARKER_BYTES");
        }
        if properties(self.handle.as_file()).map_err(|_| "PROPERTIES_READ")? != self.baseline {
            return Err("PROPERTIES_CHANGED");
        }
        Ok(())
    }
}

struct Protocol {
    root: PathBuf,
    root_handle: Handle,
    target: Bound,
    candidate: Bound,
    unrelated: Bound,
    original: Option<Bound>,
    no_backup_requested: bool,
}

impl Protocol {
    fn start(path: &Path, no_backup_requested: bool) -> io::Result<Self> {
        // Restrict the executable to this checkout's ignored authored scratch.
        let scratch = fs::canonicalize(Path::new(env!("CARGO_MANIFEST_DIR")).join("../../.local"))?;
        let parent = fs::canonicalize(
            path.parent()
                .ok_or_else(|| io::Error::other("Missing parent"))?,
        )?;
        if !path.is_absolute() || !parent.starts_with(&scratch) || path.file_name().is_none() {
            return Err(io::Error::other(
                "Fresh absolute root must be below checkout .local",
            ));
        }
        fs::create_dir(path)?;
        let root = fs::canonicalize(path)?;
        let root_handle = directory(&root, 3)?;
        Ok(Self {
            target: Bound::create_owned(&root, "target.bin", OLD)?,
            candidate: Bound::create_owned(&root, "candidate.bin", NEW)?,
            unrelated: Bound::create_owned(&root, "unrelated.marker", OTHER)?,
            root,
            root_handle,
            original: None,
            no_backup_requested,
        })
    }
    fn verify(&self) -> Result<(), &'static str> {
        if directory(&self.root, 7).map_err(|_| "ROOT_OPEN")? != self.root_handle {
            return Err("ROOT_IDENTITY");
        }
        let mut names = fs::read_dir(&self.root)
            .map_err(|_| "ROOT_LIST")?
            .map(|entry| entry.map(|entry| entry.file_name()))
            .collect::<io::Result<Vec<_>>>()
            .map_err(|_| "ROOT_LIST")?;
        names.sort();
        let mut expected: Vec<_> = ["target.bin", "candidate.bin", "unrelated.marker"]
            .into_iter()
            .map(std::ffi::OsString::from)
            .collect();
        if self.original.is_some() {
            expected.push("retained-original.bin".into());
        }
        expected.sort();
        if names != expected {
            return Err("ROOT_ENTRIES");
        }
        for bound in [&self.target, &self.candidate, &self.unrelated] {
            bound.verify(&self.root)?;
        }
        if let Some(original) = &self.original {
            original.verify(&self.root)?;
            if original.handle == self.target.handle || original.handle == self.candidate.handle {
                return Err("ORIGINAL_NOT_DISTINCT");
            }
        }
        Ok(())
    }
    fn named(&self, leaf: &str) -> Value {
        match open(&self.root.join(leaf), 7) {
            Ok(handle) => json!({"opened":true,
                "matchesOriginalTarget":handle == self.target.handle,
                "matchesRetainedOriginal":self.original.as_ref().is_some_and(|b| b.handle == handle),
                "bytes":bytes(handle.as_file()).ok(), "properties":properties(handle.as_file()).ok()}),
            Err(error) => json!({"opened":false,"osError":error.raw_os_error()}),
        }
    }
    fn event(
        &self,
        event: &str,
        refusal: Option<&str>,
        attempted: bool,
        operation: Option<&io::Result<()>>,
    ) -> io::Result<()> {
        let exact = self.verify().is_ok();
        let original_complete = self.original.as_ref().is_some_and(|b| b.expected == OLD);
        emit(json!({"event":event, "refusalCode":refusal,
            "state":if exact && original_complete {"retained-current-and-original"} else if exact {"retained-current"} else {"refusal-unverified"},
            "noBackupRequested":self.no_backup_requested,
            "target":self.named("target.bin"),"candidate":self.named("candidate.bin"),
            "original":self.named("retained-original.bin"),"unrelated":self.named("unrelated.marker"),
            "renameAttempted":attempted,"renameSucceeded":operation.is_some_and(Result::is_ok),
            "osError":operation.and_then(|r| r.as_ref().err()).and_then(io::Error::raw_os_error),
            "profile":"unsupported-original-retention-marker-v1", "productionReplacementAllowed":false,
            "restoreAllowed":false,"cleanupAllowed":false,"committed":false,"enabledProfiles":0,
            "durabilityQualified":false,"automaticCustodyQualified":false}))
    }
    fn checkpoint(&self, event: &str) -> io::Result<()> {
        self.event(event, None, false, None)?;
        gate("continue")
    }
    fn finish(
        &self,
        refusal: &str,
        attempted: bool,
        operation: Option<&io::Result<()>>,
    ) -> io::Result<()> {
        self.event("result", Some(refusal), attempted, operation)?;
        gate("exit")
    }
    fn execute(&mut self) -> io::Result<()> {
        self.checkpoint("ready")?;
        if let Err(code) = self.verify() {
            return self.finish(code, false, None);
        }
        // The create_new handle, not a later pathname reopen, establishes ownership.
        // No-backup is deliberately absent from this precommit custody sequence.
        let original = match create(&self.root.join("retained-original.bin"), b"") {
            Ok(handle) => handle,
            Err(_) => return self.finish("ORIGINAL_CREATE", false, None),
        };
        self.original = Some(Bound::capture("retained-original.bin", original, b"")?);
        self.checkpoint("retention-created")?;
        if let Err(code) = self.verify() {
            return self.finish(code, false, None);
        }
        let source = bytes(self.target.handle.as_file())?;
        let original = self.original.as_mut().expect("created original");
        let mut writer = original.handle.as_file();
        writer.seek(SeekFrom::Start(0))?;
        writer.write_all(&source)?;
        original.expected = source;
        original.baseline = properties(original.handle.as_file())?;
        self.checkpoint("retention-written")?;
        if let Err(code) = self.verify() {
            return self.finish(code, false, None);
        }
        let original = self.original.as_ref().expect("created original");
        original.handle.as_file().sync_all()?;
        self.checkpoint("retention-synced")?;
        if let Err(code) = self.verify() {
            return self.finish(code, false, None);
        }
        self.checkpoint("precommit")?;
        if let Err(code) = self.verify() {
            return self.finish(code, false, None);
        }
        // #93's unsupported std pathname operation is measured under the strong
        // guards. Never release those guards to turn a refusal into success.
        let operation = fs::rename(
            self.root.join("candidate.bin"),
            self.root.join("target.bin"),
        );
        self.finish(
            if operation.is_ok() {
                "UNSUPPORTED_REPLACEMENT_SUCCEEDED"
            } else {
                "UNSUPPORTED_REPLACEMENT_REFUSED"
            },
            true,
            Some(&operation),
        )
    }
}

pub fn run() -> io::Result<()> {
    let args: Vec<_> = std::env::args_os().skip(1).collect();
    if args.len() != 2 {
        return Err(io::Error::other(
            "Usage: imageinfo-original-retention-probe ABSENT_LOCAL_ROOT keep|no-backup",
        ));
    }
    let no_backup = match args[1].to_str() {
        Some("keep") => false,
        Some("no-backup") => true,
        _ => return Err(io::Error::other("Unknown fixed retention mode")),
    };
    Protocol::start(Path::new(&args[0]), no_backup)?.execute()
}
