use imageinfo_recovery_probe::{Envelope, digest};
use rustix::fs::{self, AtFlags, Mode, OFlags, ResolveFlags};
use serde::{Deserialize, Serialize};
use serde_json::json;
use std::{
    error::Error,
    fs::File,
    io::{self, BufRead, Read, Seek, SeekFrom, Write},
    os::{fd::AsRawFd, unix::fs::MetadataExt},
    path::{Path, PathBuf},
};
type Result<T> = std::result::Result<T, Box<dyn Error>>;
#[derive(Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
struct Artifact {
    identity: String,
    size: u64,
    sha256: String,
}
#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Record {
    version: u32,
    purpose: String,
    root_identity: String,
    recovery: Artifact,
    candidate: Artifact,
    phase: String,
}
struct Root {
    file: File,
    path: PathBuf,
    identity: String,
}
fn identity(file: &File) -> Result<String> {
    let m = file.metadata()?;
    Ok(format!("{:x}:{:x}", m.dev(), m.ino()))
}
impl Root {
    fn open(path: &Path) -> Result<Self> {
        let file = File::from(fs::openat2(
            fs::CWD,
            path,
            OFlags::RDONLY | OFlags::DIRECTORY | OFlags::CLOEXEC,
            Mode::empty(),
            ResolveFlags::NO_SYMLINKS,
        )?);
        let m = file.metadata()?;
        if m.uid() != rustix::process::geteuid().as_raw() || m.mode() & 0o777 != 0o700 {
            return Err("PRIVATE_ROOT_REQUIRED".into());
        }
        Ok(Self {
            identity: identity(&file)?,
            file,
            path: path.to_owned(),
        })
    }
    fn binding(&self) -> bool {
        Self::open(&self.path).is_ok_and(|root| root.identity == self.identity)
    }
    fn open_file(&self, name: &str) -> Result<File> {
        let file = File::from(fs::openat2(
            &self.file,
            name,
            OFlags::RDONLY | OFlags::CLOEXEC | OFlags::NONBLOCK,
            Mode::empty(),
            ResolveFlags::BENEATH | ResolveFlags::NO_SYMLINKS,
        )?);
        let m = file.metadata()?;
        if !m.is_file()
            || m.uid() != rustix::process::geteuid().as_raw()
            || m.mode() & 0o777 != 0o600
            || m.nlink() != 1
        {
            return Err("PRIVATE_FILE_REQUIRED".into());
        }
        Ok(file)
    }
    fn create(&self, name: &str, bytes: &[u8], fault: Option<&str>) -> Result<File> {
        let mut file = File::from(fs::openat2(
            &self.file,
            name,
            OFlags::RDWR | OFlags::CLOEXEC | OFlags::CREATE | OFlags::EXCL,
            Mode::RUSR | Mode::WUSR,
            ResolveFlags::BENEATH | ResolveFlags::NO_SYMLINKS,
        )?);
        file.write_all(bytes)?;
        sync(&file, name, fault)?;
        Ok(file)
    }
    fn absent(&self, name: &str) -> Result<bool> {
        match fs::statat(&self.file, name, AtFlags::SYMLINK_NOFOLLOW) {
            Err(rustix::io::Errno::NOENT) => Ok(true),
            Ok(_) => Ok(false),
            Err(e) => Err(e.into()),
        }
    }
    fn read(&self, name: &str, max: u64) -> Result<Vec<u8>> {
        let file = self.open_file(name)?;
        if file.metadata()?.len() > max {
            return Err("ARTIFACT_BOUND".into());
        }
        let mut bytes = Vec::new();
        file.take(max + 1).read_to_end(&mut bytes)?;
        if bytes.len() as u64 > max {
            return Err("ARTIFACT_BOUND".into());
        }
        Ok(bytes)
    }
}
fn artifact(file: &File, bytes: &[u8]) -> Result<Artifact> {
    Ok(Artifact {
        identity: identity(file)?,
        size: bytes.len() as u64,
        sha256: digest(bytes),
    })
}
fn sync(file: &File, phase: &str, fault: Option<&str>) -> Result<()> {
    // Deterministic protocol fault, explicitly separate from a device/fsync error.
    // This tests refusal ordering without pretending to qualify native failure I/O.
    if fault == Some(phase) {
        return Err(format!("INJECTED_FLUSH_FAILURE:{phase}").into());
    }
    file.sync_all()?;
    Ok(())
}
fn encode(record: &Record) -> Result<Vec<u8>> {
    let body = serde_json::to_string(record)?;
    Ok(serde_json::to_vec(&Envelope {
        sha256: digest(body.as_bytes()),
        body,
    })?)
}
fn decode(bytes: &[u8]) -> Result<Record> {
    if bytes.len() > 65536 {
        return Err("RECORD_BOUND".into());
    }
    let envelope: Envelope = serde_json::from_slice(bytes)?;
    if digest(envelope.body.as_bytes()) != envelope.sha256 {
        return Err("RECORD_CHECKSUM".into());
    }
    let r: Record = serde_json::from_str(&envelope.body)?;
    if r.version != 1
        || r.purpose != "imageinfo-anonymous-guest-marker-v1"
        || !matches!(
            r.phase.as_str(),
            "prepared" | "publication-intent" | "observation-only"
        )
        || r.candidate.size != 65536
        || r.recovery.size != 65536
    {
        return Err("RECORD_SCOPE".into());
    }
    Ok(r)
}
fn barrier(name: &str) -> Result<()> {
    println!(
        "{}",
        json!({"barrier":name,"committed":false,"productionPublicationAllowed":false})
    );
    io::stdout().flush()?;
    let mut line = String::new();
    io::stdin().lock().take(32).read_line(&mut line)?;
    if line != "continue\n" {
        return Err("CONTROL_STOP".into());
    }
    Ok(())
}
fn observe(root: &Root, expected: &Artifact, name: &str) -> Result<bool> {
    let mut file = root.open_file(name)?;
    let mut data = Vec::new();
    (&mut file).take(65537).read_to_end(&mut data)?;
    Ok(identity(&file)? == expected.identity
        && data.len() as u64 == expected.size
        && digest(&data) == expected.sha256)
}
fn worker(path: &Path, fault: Option<&str>) -> Result<()> {
    let root = Root::open(path)?;
    // Producer data is immutable authored memory, never a mutable image source.
    let marker = vec![0x31; 65536];
    let recovery = root.create("recovery.bin", &marker, fault)?;
    let mut stage = File::from(fs::openat(
        &root.file,
        ".",
        OFlags::TMPFILE | OFlags::RDWR | OFlags::CLOEXEC,
        Mode::RUSR | Mode::WUSR,
    )?);
    stage.write_all(&marker)?;
    sync(&stage, "candidate", fault)?;
    sync(&root.file, "staged-namespace", fault)?;
    barrier("staged")?;
    let mut record = Record {
        version: 1,
        purpose: "imageinfo-anonymous-guest-marker-v1".into(),
        root_identity: root.identity.clone(),
        recovery: artifact(&recovery, &marker)?,
        candidate: artifact(&stage, &marker)?,
        phase: "prepared".into(),
    };
    let _prepared = root.create("prepared.record", &encode(&record)?, fault)?;
    sync(&root.file, "prepared-namespace", fault)?;
    barrier("prepared")?;
    record.phase = "publication-intent".into();
    let _intent = root.create("intent.record", &encode(&record)?, fault)?;
    sync(&root.file, "intent-namespace", fault)?;
    barrier("intent")?;
    let proc = File::from(fs::open(
        "/proc/self/fd",
        OFlags::RDONLY | OFlags::DIRECTORY | OFlags::CLOEXEC,
        Mode::empty(),
    )?);
    if fs::fstatfs(&proc)?.f_type != fs::PROC_SUPER_MAGIC {
        return Err("PROCFS_REQUIRED".into());
    }
    if !root.binding() || !observe(&root, &record.recovery, "recovery.bin")? {
        return Err("BINDING_OR_RECOVERY_CHANGED".into());
    }
    stage.seek(SeekFrom::Start(0))?;
    let mut current = Vec::new();
    (&mut stage).take(65537).read_to_end(&mut current)?;
    if current != marker || identity(&stage)? != record.candidate.identity {
        return Err("CANDIDATE_CHANGED".into());
    }
    barrier("validated-before-link")?;
    fs::linkat(
        &proc,
        stage.as_raw_fd().to_string(),
        &root.file,
        "output.bin",
        AtFlags::SYMLINK_FOLLOW,
    )?;
    barrier("linked")?;
    if !root.binding() || !observe(&root, &record.candidate, "output.bin")? {
        return Err("POST_LINK_UNCERTAIN".into());
    }
    sync(&stage, "output", fault)?;
    barrier("output-flushed")?;
    sync(&root.file, "output-namespace", fault)?;
    barrier("namespace-flushed")?;
    record.phase = "observation-only".into();
    let _receipt = root.create("observation.record", &encode(&record)?, fault)?;
    barrier("observation-file-flushed")?;
    sync(&root.file, "observation-namespace", fault)?;
    barrier("observation-namespace-flushed")?;
    println!(
        "{}",
        json!({"outcome":"marker-publication-observed","committed":false,"profileVerified":false,"productionPublicationAllowed":false})
    );
    Ok(())
}
fn inspect(path: &Path) -> serde_json::Value {
    let result = (|| -> Result<(String, bool)> {
        let root = Root::open(path)?;
        let name = if root.absent("intent.record")? {
            "prepared.record"
        } else {
            "intent.record"
        };
        let record = decode(&root.read(name, 65536)?)?;
        if record.phase
            != if name == "intent.record" {
                "publication-intent"
            } else {
                "prepared"
            }
        {
            return Err("RECORD_PHASE".into());
        }
        if record.root_identity != root.identity
            || !observe(&root, &record.recovery, "recovery.bin")?
        {
            return Err("ROOT_OR_RECOVERY_CHANGED".into());
        }
        if name == "intent.record" && !root.absent("prepared.record")? {
            let prepared = decode(&root.read("prepared.record", 65536)?)?;
            if prepared.phase != "prepared"
                || prepared.root_identity != record.root_identity
                || prepared.candidate != record.candidate
                || prepared.recovery != record.recovery
            {
                return Err("PREPARED_RECORD_CHANGED".into());
            }
        }
        let state = if root.absent("output.bin")? {
            "expected-absence-observed"
        } else if observe(&root, &record.candidate, "output.bin").unwrap_or(false) {
            "candidate-object-observed"
        } else {
            "foreign-or-uninspectable-target"
        };
        let receipt_present = !root.absent("observation.record")?;
        if receipt_present {
            let receipt = decode(&root.read("observation.record", 65536)?)?;
            if receipt.phase != "observation-only"
                || receipt.root_identity != record.root_identity
                || receipt.candidate != record.candidate
                || receipt.recovery != record.recovery
            {
                return Err("OBSERVATION_RECORD_CHANGED".into());
            }
        }
        if !root.binding() {
            return Err("ROOT_BINDING_CHANGED".into());
        }
        Ok((state.into(), receipt_present))
    })();
    match result {
        Ok((state, receipt)) => {
            json!({"classification":state,"observationPresent":receipt,"observationOnly":true,"recoveryRequired":true,"authorizedActions":[],"profileVerified":false,"evidenceAuthenticated":false,"committed":false})
        }
        Err(error) => {
            json!({"classification":"invalid-or-uninspectable-evidence","issue":error.to_string().chars().filter(|c|!c.is_control()).take(256).collect::<String>(),"observationOnly":true,"recoveryRequired":true,"authorizedActions":[],"profileVerified":false,"evidenceAuthenticated":false,"committed":false})
        }
    }
}
pub fn run() -> Result<()> {
    let args: Vec<_> = std::env::args_os().skip(1).collect();
    if args.len() != 2 {
        return Err("EXPECTED_MODE_AND_ROOT".into());
    }
    let path = Path::new(&args[1]);
    match args[0].to_str() {
        Some("worker") => worker(path, None),
        Some(mode) if mode.starts_with("worker-fail-") => {
            let phase = &mode[12..];
            if ![
                "recovery.bin",
                "candidate",
                "staged-namespace",
                "prepared.record",
                "prepared-namespace",
                "intent.record",
                "intent-namespace",
                "output",
                "output-namespace",
                "observation.record",
                "observation-namespace",
            ]
            .contains(&phase)
            {
                return Err("FAULT_UNVERIFIED".into());
            }
            worker(path, Some(phase))
        }
        Some("inspect") => {
            println!("{}", inspect(path));
            Ok(())
        }
        Some("finalize" | "prune" | "admit") => {
            println!(
                "{}",
                json!({"outcome":"refused-before-mutation","missingCells":["custody-authentication","complete-source-path-property-exclusion","qualified-durable-receipt"],"authorizedActions":[],"committed":false,"productionPublicationAllowed":false})
            );
            Ok(())
        }
        _ => Err("MODE_UNVERIFIED".into()),
    }
}
