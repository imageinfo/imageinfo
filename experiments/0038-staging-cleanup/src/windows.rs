use crate::{
    native::{self, PrivateSecurity},
    path::marker_path,
};
use serde_json::{Value, json};
use std::{
    error::Error,
    fs::{File, OpenOptions},
    io::{self, BufRead, Read, Seek, SeekFrom, Write},
    os::windows::fs::OpenOptionsExt,
    path::{Path, PathBuf},
};
type Result<T> = std::result::Result<T, Box<dyn Error>>;
#[derive(PartialEq, Eq)]
struct Snapshot {
    identity: (u64, u64),
    size: u64,
    links: u64,
    attributes: u64,
    mtime: Option<u64>,
}
fn snapshot(file: &File) -> Result<Snapshot> {
    let i = winapi_util::file::information(file)?;
    Ok(Snapshot {
        identity: (i.volume_serial_number(), i.file_index()),
        size: i.file_size(),
        links: i.number_of_links(),
        attributes: i.file_attributes(),
        mtime: i.last_write_time(),
    })
}
struct OwnedArtifact {
    file: File,
    before: Snapshot,
    bytes: Vec<u8>,
    name: &'static str,
}
impl OwnedArtifact {
    fn create(
        root: &Path,
        security: &PrivateSecurity,
        name: &'static str,
        bytes: Vec<u8>,
        no_delete: bool,
    ) -> Result<Self> {
        let mut file = if no_delete {
            security.create_file_access(&root.join(name), 0xc0020000)?
        } else {
            security.create_file(&root.join(name))?
        };
        file.write_all(&bytes)?;
        file.sync_all()?;
        let before = snapshot(&file)?;
        Ok(Self {
            file,
            before,
            bytes,
            name,
        })
    }
    fn check(&mut self, security: &PrivateSecurity) -> Result<()> {
        security.check(&self.file)?;
        native::check_streams(&self.file)?;
        if self.before != snapshot(&self.file)?
            || self.before.links != 1
            || self.before.mtime.is_none()
        {
            return Err("OWNED_OBJECT_BINDING_CHANGED".into());
        }
        self.file.seek(SeekFrom::Start(0))?;
        let mut data = Vec::new();
        Read::by_ref(&mut self.file)
            .take(self.bytes.len() as u64 + 1)
            .read_to_end(&mut data)?;
        if data != self.bytes {
            return Err("OWNED_OBJECT_CONTENT_CHANGED".into());
        }
        Ok(())
    }
}
fn emit(value: Value) -> Result<()> {
    println!("{value}");
    io::stdout().flush()?;
    Ok(())
}
fn barrier(name: &str) -> Result<bool> {
    emit(json!({"barrier":name,"committed":false,"productionPublicationAllowed":false}))?;
    let mut line = String::new();
    io::stdin().lock().take(32).read_line(&mut line)?;
    match line.as_str() {
        "continue\n" | "continue\r\n" => Ok(false),
        "cancel\n" | "cancel\r\n" => Ok(true),
        _ => Err("CONTROL_INVALID".into()),
    }
}
fn ancestors(root: &Path) -> Result<Vec<File>> {
    let mut current = PathBuf::new();
    let mut held = Vec::new();
    for component in root.parent().ok_or("PARENT_REQUIRED")?.components() {
        current.push(component.as_os_str());
        if current.has_root() {
            let file = OpenOptions::new()
                .access_mode(0x20080)
                .share_mode(3)
                .custom_flags(0x02200000)
                .open(&current)?;
            let i = winapi_util::file::information(&file)?;
            if i.file_attributes() & 0x410 != 0x10 {
                return Err("PARENT_REPARSE_OR_TYPE".into());
            }
            held.push(file);
        }
    }
    if native::filesystem(held.last().ok_or("PARENT_REQUIRED")?)? != "NTFS" {
        return Err("FILESYSTEM_UNVERIFIED".into());
    }
    Ok(held)
}
fn report(outcome: &str, closed: usize, pending: bool, attempted: bool) -> Result<()> {
    emit(
        json!({"outcome":outcome,"ownedHandlesMarkedAndClosed":closed,"cleanupPending":pending,"rootRetained":true,"publicationAttempted":attempted,"committed":false,"productionPublicationAllowed":false}),
    )
}
pub fn run() -> Result<()> {
    let args: Vec<_> = std::env::args_os().skip(1).collect();
    if args.len() != 2 {
        return Err("EXPECTED_MODE_AND_NEW_ROOT".into());
    }
    let mode = args[0].to_str().ok_or("MODE_ENCODING")?;
    if ["admit", "finalize", "prune"].contains(&mode) {
        return emit(
            json!({"outcome":"refused-before-effects","workerArtifacts":0,"committed":false,"productionPublicationAllowed":false,"missingCells":["qualified-complete-storage-recovery-profile","validated-restart-artifact-ownership"]}),
        );
    }
    if !["abort", "publish", "inject-error", "no-delete"].contains(&mode) {
        return Err("MODE_UNVERIFIED".into());
    }
    let root = Path::new(&args[1]);
    marker_path(root)?;
    let held = ancestors(root)?;
    let ordinary = PrivateSecurity::current()?;
    let sealed = PrivateSecurity::sealed_owner()?;
    let directory = ordinary.create_directory(
        held.last().ok_or("PARENT_REQUIRED")?,
        Path::new(root.file_name().ok_or("ROOT_LEAF_REQUIRED")?),
    )?;
    let mut artifacts = vec![
        OwnedArtifact::create(
            root,
            &sealed,
            "stage.marker",
            vec![b'8'; 65536],
            mode == "no-delete",
        )?,
        OwnedArtifact::create(
            root,
            &sealed,
            "record.marker",
            b"owned-prepublication-marker-v1\n".to_vec(),
            mode == "no-delete",
        )?,
    ];
    directory.sync_all()?;
    let cancel = barrier("prepared")?;
    let guard = (|| -> Result<()> {
        ordinary.check(&directory)?;
        for artifact in &mut artifacts {
            artifact.check(&sealed)?;
        }
        Ok(())
    })();
    if let Err(error) = guard {
        emit(
            json!({"guardDiagnostic":error.to_string().chars().filter(|c| !c.is_control()).take(128).collect::<String>(),"committed":false,"productionPublicationAllowed":false}),
        )?;
        return report("cleanup-refused-live-guard", 0, true, false);
    }
    if mode == "publish" && !cancel {
        // Crossing the namespace call boundary permanently disqualifies this
        // live abort path, even if the call later returns an error/collision.
        let call = native::rename(
            &artifacts[0].file,
            &directory,
            &root.join("output.marker"),
            false,
        );
        emit(
            json!({"publicationCallSucceeded":call.is_ok(),"errorCode":call.err().and_then(|e| e.raw_os_error()),"committed":false,"productionPublicationAllowed":false}),
        )?;
        barrier("publication-attempted")?;
        return report("cleanup-refused-after-publication-attempt", 0, true, true);
    }
    if !cancel {
        return Err("EXPECTED_CANCELLATION_BEFORE_PUBLICATION".into());
    }
    let mut closed = 0;
    while let Some(mut artifact) = artifacts.pop() {
        // Stop at the first partial/error boundary. Never retry an old name or
        // sweep the retained root; a new entry can belong to an unrelated writer.
        if ordinary.check(&directory).is_err() || artifact.check(&sealed).is_err() {
            return report("cleanup-partial-live-guard", closed, true, false);
        }
        if mode == "inject-error" && closed == 1 {
            return report("cleanup-partial-injected-error", closed, true, false);
        }
        if let Err(error) = crate::disposition::mark_owned_file(&artifact.file) {
            emit(
                json!({"dispositionErrorCode":error.raw_os_error(),"committed":false,"productionPublicationAllowed":false}),
            )?;
            return report("cleanup-partial-native-error", closed, true, false);
        }
        emit(
            json!({"markedOwnedRole":artifact.name,"committed":false,"productionPublicationAllowed":false}),
        )?;
        barrier("delete-marked")?;
        drop(artifact.file);
        closed += 1;
        emit(
            json!({"closedOwnedRole":artifact.name,"committed":false,"productionPublicationAllowed":false}),
        )?;
        barrier("owned-handle-closed")?;
    }
    // Compatible readers can defer removal beyond this holder's close. Report
    // retained entries/pending work without reopening them for deletion.
    let pending = std::fs::read_dir(root)
        .map(|mut entries| entries.next().is_some())
        .unwrap_or(true);
    report("cancelled-before-publication", closed, pending, false)
}
