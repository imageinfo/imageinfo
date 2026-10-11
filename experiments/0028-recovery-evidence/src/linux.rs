//! Linux research only. Descriptor binding reduces path substitution, but does
//! not supply mandatory live-file exclusion or qualify crash durability.
use crate::{
    Artifact, MAX_ARTIFACT, MAX_RECORD, Receipt, Record, decode, decode_receipt, encode,
    receipt_bytes,
};
use rustix::fs::{self, Mode, OFlags, ResolveFlags};
use sha2::{Digest, Sha256};
use std::{
    error::Error,
    fs::File,
    io::{self, Read, Write},
    os::unix::fs::MetadataExt,
    path::{Path, PathBuf},
};

type Result<T> = std::result::Result<T, Box<dyn Error>>;
const FLAGS: OFlags = OFlags::RDONLY
    .union(OFlags::CLOEXEC)
    .union(OFlags::NONBLOCK);

struct Root {
    file: File,
    path: PathBuf,
    identity: String,
}

fn identity(metadata: &std::fs::Metadata) -> String {
    format!("{:x}:{:x}", metadata.dev(), metadata.ino())
}

impl Root {
    fn open(path: &Path) -> Result<Self> {
        // std's path-based join/open cannot bind a child to this exact directory.
        // openat2 refuses symlinks throughout resolution; all child I/O uses the
        // resulting descriptor. Do not fall back when the kernel lacks this API.
        let fd = fs::openat2(
            fs::CWD,
            path,
            FLAGS | OFlags::DIRECTORY,
            Mode::empty(),
            ResolveFlags::NO_SYMLINKS,
        )?;
        let file = File::from(fd);
        let metadata = file.metadata()?;
        if metadata.uid() != rustix::process::geteuid().as_raw() || metadata.mode() & 0o777 != 0o700
        {
            return Err("PRIVATE_DIRECTORY_REQUIRED".into());
        }
        Ok(Self {
            identity: identity(&metadata),
            file,
            path: path.to_owned(),
        })
    }
    fn binding_current(&self) -> bool {
        Self::open(&self.path).is_ok_and(|r| r.identity == self.identity)
    }
    fn open_file(&self, name: &str) -> Result<File> {
        let fd = fs::openat2(
            &self.file,
            name,
            FLAGS,
            Mode::empty(),
            ResolveFlags::BENEATH | ResolveFlags::NO_SYMLINKS,
        )?;
        let file = File::from(fd);
        let metadata = file.metadata()?;
        if !metadata.is_file()
            || metadata.uid() != rustix::process::geteuid().as_raw()
            || metadata.mode() & 0o777 != 0o600
        {
            return Err("PRIVATE_REGULAR_FILE_REQUIRED".into());
        }
        Ok(file)
    }
    fn create(&self, name: &str, bytes: &[u8]) -> Result<Artifact> {
        let fd = fs::openat2(
            &self.file,
            name,
            OFlags::RDWR | OFlags::CLOEXEC | OFlags::CREATE | OFlags::EXCL,
            Mode::RUSR | Mode::WUSR,
            ResolveFlags::BENEATH | ResolveFlags::NO_SYMLINKS,
        )?;
        let mut file = File::from(fd);
        file.write_all(bytes)?;
        file.flush()?;
        file.sync_all()?;
        let metadata = file.metadata()?;
        Ok(Artifact {
            name: name.into(),
            identity: identity(&metadata),
            size: bytes.len() as u64,
            sha256: crate::digest(bytes),
        })
    }
    fn read_record(&self, name: &str) -> Result<Vec<u8>> {
        let file = self.open_file(name)?;
        if file.metadata()?.len() > MAX_RECORD as u64 {
            return Err("RECORD_TOO_LARGE".into());
        }
        let mut bytes = Vec::new();
        file.take(MAX_RECORD as u64 + 1).read_to_end(&mut bytes)?;
        if bytes.len() > MAX_RECORD {
            return Err("RECORD_TOO_LARGE".into());
        }
        Ok(bytes)
    }
    fn observe(&self, expected: &Artifact, name: &str) -> Result<bool> {
        let mut file = self.open_file(name)?;
        let before = file.metadata()?;
        if before.len() > MAX_ARTIFACT
            || before.len() != expected.size
            || identity(&before) != expected.identity
        {
            return Ok(false);
        }
        let mut hash = Sha256::new();
        let mut buffer = [0u8; 32768];
        let mut total = 0u64;
        loop {
            let count = file.read(&mut buffer)?;
            if count == 0 {
                break;
            }
            total += count as u64;
            if total > MAX_ARTIFACT {
                return Err("ARTIFACT_TOO_LARGE".into());
            }
            hash.update(&buffer[..count]);
        }
        let after = file.metadata()?;
        Ok(total == expected.size
            && crate::hex(&hash.finalize()) == expected.sha256
            && before.len() == after.len()
            && before.mtime() == after.mtime()
            && before.mtime_nsec() == after.mtime_nsec()
            && identity(&after) == expected.identity
            && after.mode() & 0o777 == 0o600)
    }
    fn name_absent(&self, name: &str) -> Result<bool> {
        match fs::statat(&self.file, name, fs::AtFlags::SYMLINK_NOFOLLOW) {
            Err(rustix::io::Errno::NOENT) => Ok(true),
            Err(error) => Err(error.into()),
            Ok(_) => Ok(false),
        }
    }
}

fn barrier(name: &str, enabled: bool) -> Result<()> {
    if enabled {
        println!("{name}");
        io::stdout().flush()?;
        let mut line = String::new();
        io::stdin().read_line(&mut line)?;
        if line.trim() != "continue" {
            return Err("COOPERATIVE_CANCELLED".into());
        }
    }
    Ok(())
}

pub fn worker(root_path: &Path, input: Option<&Path>, barriers: bool) -> Result<()> {
    let root = Root::open(root_path)?;
    if !root.name_absent("output.cr3")? {
        return Err("DESTINATION_EXISTS".into());
    }
    // This copy freezes bytes already read into memory. It does NOT prove that a
    // concurrent disk-file read was coherent. That admission/exclusion is #0029.
    let bytes = if let Some(path) = input {
        let file = File::from(fs::openat2(
            fs::CWD,
            path,
            FLAGS,
            Mode::empty(),
            ResolveFlags::NO_SYMLINKS,
        )?);
        if !file.metadata()?.is_file() || file.metadata()?.len() > MAX_ARTIFACT {
            return Err("INPUT_LIMIT_OR_TYPE".into());
        }
        let mut bytes = Vec::new();
        file.take(MAX_ARTIFACT + 1).read_to_end(&mut bytes)?;
        if bytes.len() as u64 > MAX_ARTIFACT {
            return Err("INPUT_TOO_LARGE".into());
        }
        bytes
    } else {
        vec![0x28; 65536]
    };
    let source = root.create("frozen-input.cr3", &bytes)?;
    let candidate = root.create("candidate.cr3", &bytes)?;
    barrier("staged", barriers)?;
    let mut record = Record {
        schema_version: 1,
        purpose: "imageinfo-storage-research-v1".into(),
        root_identity: root.identity.clone(),
        source,
        candidate,
        destination: "output.cr3".into(),
        expected_destination: "absent".into(),
        phase: "prepared".into(),
    };
    root.create("prepared.record", &encode(&record)?)?;
    root.file.sync_all()?;
    barrier("prepared", barriers)?;
    record.phase = "publication-intent".into();
    root.create("intent.record", &encode(&record)?)?;
    root.file.sync_all()?;
    barrier("intent", barriers)?;
    barrier("before-link", barriers)?;
    if !root.binding_current() {
        return Err("PARENT_BINDING_CHANGED".into());
    }
    if !root.observe(&record.source, &record.source.name)?
        || !root.observe(&record.candidate, &record.candidate.name)?
    {
        return Err("CANDIDATE_OR_SOURCE_CHANGED".into());
    }
    // Conditional name creation, never rename-overwrite. Private-stage mutation
    // can still race this call: observations do not enable a production profile.
    barrier("validated-before-link", barriers)?;
    fs::linkat(
        &root.file,
        "candidate.cr3",
        &root.file,
        "output.cr3",
        fs::AtFlags::empty(),
    )?;
    barrier("linked", barriers)?;
    if !root.binding_current() || !root.observe(&record.candidate, "output.cr3")? {
        return Err("POST_PUBLICATION_UNCERTAIN".into());
    }
    root.file.sync_all()?;
    barrier("namespace-flushed", barriers)?;
    root.create(
        "receipt.record",
        &receipt_bytes(&Receipt {
            schema_version: 1,
            root_identity: root.identity.clone(),
            candidate_identity: record.candidate.identity.clone(),
            candidate_sha256: record.candidate.sha256.clone(),
            observation_only: true,
        })?,
    )?;
    root.file.sync_all()?;
    barrier("receipt-flushed", barriers)?;
    println!(
        "{}",
        serde_json::json!({"outcome":"research-publication-observed","profileVerified":false,
        "durabilityProved":false,"terminalCommit":false,"sourceBytes":bytes.len()})
    );
    Ok(())
}

pub fn inspect(path: &Path) -> serde_json::Value {
    let observation = (|| -> Result<(&str, bool)> {
        let root = Root::open(path)?;
        let name = if root.name_absent("intent.record")? {
            "prepared.record"
        } else {
            "intent.record"
        };
        let bytes = root.read_record(name)?;
        let record = decode(&bytes)?;
        if record.root_identity != root.identity {
            return Err("ROOT_IDENTITY_CHANGED".into());
        }
        if !root.observe(&record.source, &record.source.name)?
            || !root.observe(&record.candidate, &record.candidate.name)?
        {
            return Err("ARTIFACT_IDENTITY_CONTENT_OR_PROPERTIES_CHANGED".into());
        }
        let receipt_present = !root.name_absent("receipt.record")?;
        if receipt_present && !decode_receipt(&root.read_record("receipt.record")?, &record) {
            return Err("RECEIPT_INVALID".into());
        }
        let state = if root.name_absent(&record.destination)? {
            "expected-absence-observed"
        } else if root
            .observe(&record.candidate, &record.destination)
            .unwrap_or(false)
        {
            "candidate-object-observed"
        } else {
            "foreign-or-uninspectable-target"
        };
        if !root.binding_current() {
            return Err("ROOT_BINDING_CHANGED".into());
        }
        Ok((state, receipt_present))
    })();
    match observation {
        Ok((state, receipt)) => serde_json::json!({"classification":state,"receiptPresent":receipt,
            "observationOnly":true,"evidenceAuthenticated":false,"profileVerified":false,
            "recoveryRequired":true,"publicationMayHaveOccurred":true,"authorizedActions":[]}),
        Err(error) => serde_json::json!({"classification":"invalid-or-uninspectable-evidence",
            "issue":error.to_string().chars().filter(|c| !c.is_control()).take(256).collect::<String>(),
            "observationOnly":true,"evidenceAuthenticated":false,"profileVerified":false,
            "recoveryRequired":true,"publicationMayHaveOccurred":true,"authorizedActions":[]}),
    }
}
