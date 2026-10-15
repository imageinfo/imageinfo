use same_file::Handle;
use serde::Serialize;
use serde_json::{Value, json};
use std::{
    fs::{self, File, OpenOptions},
    io::{self, BufRead, Read, Seek, SeekFrom, Write},
    os::windows::fs::{MetadataExt, OpenOptionsExt},
    path::{Path, PathBuf},
};

const OLD: &[u8] = b"OLD093\n";
const NEW: &[u8] = b"NEW093\n";
const INPUT: &[u8] = b"INPUT093\n";
const MARKER_LIMIT: u64 = 64;
const BACKUP_SEMANTICS: u32 = 0x0200_0000;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Mode {
    Unguarded,
    Target,
    Source,
    Both,
    WeakTarget,
}

impl Mode {
    fn parse(value: &str) -> io::Result<Self> {
        match value {
            "unguarded-control" => Ok(Self::Unguarded),
            "target-guard" => Ok(Self::Target),
            "source-guard" => Ok(Self::Source),
            "both-guard" => Ok(Self::Both),
            "weak-target-control" => Ok(Self::WeakTarget),
            _ => Err(io::Error::other("Unknown fixed marker mode")),
        }
    }
    fn strong(self) -> bool {
        matches!(self, Self::Target | Self::Source | Self::Both)
    }
}

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

fn read_marker(file: &File) -> io::Result<Vec<u8>> {
    if !file.metadata()?.is_file() || file.metadata()?.len() > MARKER_LIMIT {
        return Err(io::Error::other("Not a bounded ordinary marker"));
    }
    let mut reader = file.try_clone()?;
    reader.seek(SeekFrom::Start(0))?;
    let mut data = Vec::new();
    reader.take(MARKER_LIMIT + 1).read_to_end(&mut data)?;
    if data.len() as u64 > MARKER_LIMIT {
        return Err(io::Error::other("Marker exceeds byte bound"));
    }
    Ok(data)
}

fn open_file(path: &Path, share: u32) -> io::Result<Handle> {
    Handle::from_file(OpenOptions::new().read(true).share_mode(share).open(path)?)
}

fn open_directory(path: &Path, share: u32) -> io::Result<Handle> {
    Handle::from_file(
        OpenOptions::new()
            .access_mode(0)
            .share_mode(share)
            .custom_flags(BACKUP_SEMANTICS)
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
    let mut input = String::new();
    io::stdin().lock().take(32).read_line(&mut input)?;
    if input.trim_end_matches(['\r', '\n']) != expected {
        return Err(io::Error::other("Expected exact protocol gate"));
    }
    Ok(())
}

fn create_marker(path: &Path, bytes: &[u8]) -> io::Result<()> {
    let mut file = OpenOptions::new().write(true).create_new(true).open(path)?;
    file.write_all(bytes)
}

struct Baseline {
    root: PathBuf,
    directory: Handle,
    target: Handle,
    candidate: Handle,
    input: Handle,
    target_properties: Properties,
    candidate_properties: Properties,
    input_properties: Properties,
}

impl Baseline {
    fn create(root: &Path) -> io::Result<Self> {
        if !root.is_absolute() {
            return Err(io::Error::other(
                "Use a fresh absolute disposable marker root",
            ));
        }
        let parent = fs::canonicalize(
            root.parent()
                .ok_or_else(|| io::Error::other("Fresh root needs an existing parent"))?,
        )?;
        let rendered = parent.to_string_lossy();
        if rendered.starts_with(r"\\?\UNC\") || rendered.starts_with(r"\\.\") {
            return Err(io::Error::other(
                "Network/device paths are outside this local marker probe",
            ));
        }
        // No recursion, reuse, replacement or cleanup of caller-selected paths.
        fs::create_dir(root)?;
        let root = fs::canonicalize(root)?;
        create_marker(&root.join("target.bin"), OLD)?;
        create_marker(&root.join("candidate.bin"), NEW)?;
        create_marker(&root.join("input.marker"), INPUT)?;
        create_marker(&root.join("unrelated.marker"), b"OTHER093\n")?;
        let target = open_file(&root.join("target.bin"), 7)?;
        let candidate = open_file(&root.join("candidate.bin"), 7)?;
        let input = open_file(&root.join("input.marker"), 1)?;
        let target_properties = properties(target.as_file())?;
        let candidate_properties = properties(candidate.as_file())?;
        let input_properties = properties(input.as_file())?;
        Ok(Self {
            directory: open_directory(&root, 7)?,
            root,
            target,
            candidate,
            input,
            target_properties,
            candidate_properties,
            input_properties,
        })
    }

    fn verify(&self) -> Result<(), &'static str> {
        let current_root = open_directory(&self.root, 7).map_err(|_| "ROOT_OPEN")?;
        if current_root != self.directory {
            return Err("ROOT_IDENTITY");
        }
        for (leaf, held, expected, baseline) in [
            ("target.bin", &self.target, OLD, &self.target_properties),
            (
                "candidate.bin",
                &self.candidate,
                NEW,
                &self.candidate_properties,
            ),
            ("input.marker", &self.input, INPUT, &self.input_properties),
        ] {
            let current = open_file(&self.root.join(leaf), 7).map_err(|_| "NAME_OPEN")?;
            if current != *held {
                return Err("NAME_IDENTITY");
            }
            if read_marker(held.as_file()).map_err(|_| "MARKER_READ")? != expected {
                return Err("MARKER_BYTES");
            }
            let observed = properties(held.as_file()).map_err(|_| "PROPERTIES_READ")?;
            if &observed != baseline {
                return Err("PROPERTIES_CHANGED");
            }
        }
        Ok(())
    }

    fn named(&self, leaf: &str) -> Value {
        match open_file(&self.root.join(leaf), 7) {
            Ok(handle) => json!({
                "opened": true,
                "matchesOriginalTarget": handle == self.target,
                "matchesOriginalCandidate": handle == self.candidate,
                "matchesProtectedInput": handle == self.input,
                "properties": properties(handle.as_file()).ok(),
                "bytes": read_marker(handle.as_file()).ok(),
            }),
            Err(error) => json!({"opened": false, "osError": error.raw_os_error()}),
        }
    }

    fn result(
        &self,
        refusal: Option<&str>,
        attempted: bool,
        operation: Option<io::Result<()>>,
    ) -> io::Result<()> {
        let succeeded = operation.as_ref().is_some_and(Result::is_ok);
        let os_error = operation
            .as_ref()
            .and_then(|result| result.as_ref().err())
            .and_then(io::Error::raw_os_error);
        emit(json!({
            "event": "result", "refusalCode": refusal,
            "renameAttempted": attempted, "renameSucceeded": succeeded,
            "osError": os_error,
            "target": self.named("target.bin"), "candidate": self.named("candidate.bin"),
            "protectedInput": self.named("input.marker"),
            "unrelated": self.named("unrelated.marker"),
            "heldProtectedInputBytes": read_marker(self.input.as_file()).ok(),
            "heldProtectedInputProperties": properties(self.input.as_file()).ok(),
            "heldOriginalTargetBytes": read_marker(self.target.as_file()).ok(),
            "heldOriginalCandidateBytes": read_marker(self.candidate.as_file()).ok(),
            "heldOriginalTargetProperties": properties(self.target.as_file()).ok(),
            "heldOriginalCandidateProperties": properties(self.candidate.as_file()).ok(),
            "productionReplacementAllowed": false, "committed": false,
            "enabledProfiles": 0, "profile": "unsupported-std-path-replacement-marker-v1",
            "securityPropertyCoverage": false, "streamPropertyCoverage": false,
            "ancestorExclusionQualified": false, "durabilityQualified": false,
        }))?;
        // Retain captured object identities and active sharing guards while the
        // independent caller measures the result. Nothing is cleaned up here.
        gate("exit")
    }
}

pub fn run() -> io::Result<()> {
    let args: Vec<_> = std::env::args_os().skip(1).collect();
    if args.len() != 2 {
        return Err(io::Error::other(
            "Usage: imageinfo-conditional-replacement-probe ABSENT_ROOT MODE",
        ));
    }
    let mode = Mode::parse(
        args[1]
            .to_str()
            .ok_or_else(|| io::Error::other("Mode must be ASCII"))?,
    )?;
    let baseline = Baseline::create(Path::new(&args[0]))?;
    emit(
        json!({"event": "ready", "target": baseline.named("target.bin"), "candidate": baseline.named("candidate.bin"), "protectedInput": baseline.named("input.marker")}),
    )?;
    gate("continue")?;
    let _directory_guard = if mode.strong() {
        match open_directory(&baseline.root, 3) {
            Ok(handle) => Some(handle),
            Err(_) => return baseline.result(Some("ROOT_GUARD_OPEN"), false, None),
        }
    } else {
        None
    };
    let _target_guard = if matches!(mode, Mode::Target | Mode::Both | Mode::WeakTarget) {
        match open_file(
            &baseline.root.join("target.bin"),
            if mode == Mode::WeakTarget { 5 } else { 1 },
        ) {
            Ok(handle) => Some(handle),
            Err(_) => return baseline.result(Some("TARGET_GUARD_OPEN"), false, None),
        }
    } else {
        None
    };
    let _candidate_guard = if matches!(mode, Mode::Source | Mode::Both) {
        match open_file(&baseline.root.join("candidate.bin"), 1) {
            Ok(handle) => Some(handle),
            Err(_) => return baseline.result(Some("SOURCE_GUARD_OPEN"), false, None),
        }
    } else {
        None
    };
    if let Err(code) = baseline.verify() {
        return baseline.result(Some(code), false, None);
    }
    emit(
        json!({"event": "validated", "target": baseline.named("target.bin"), "candidate": baseline.named("candidate.bin"), "renewedChecksRequired": mode.strong()}),
    )?;
    gate("continue")?;
    if mode.strong()
        && let Err(code) = baseline.verify()
    {
        return baseline.result(Some(code), false, None);
    }
    // These are disposable-marker API observations, never admitted replacement.
    // Controls intentionally omit renewed checks to expose the pathname gap.
    let operation = fs::rename(
        baseline.root.join("candidate.bin"),
        baseline.root.join("target.bin"),
    );
    baseline.result(None, true, Some(operation))
}
