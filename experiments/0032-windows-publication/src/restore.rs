//! #0108: typed live marker custody, followed by a separately authorized fresh copy.
use crate::{
    inspection_record::Info,
    native::{self, PrivateSecurity},
};
use serde_json::{Value, json};
use std::{
    error::Error,
    fs::{self, File, OpenOptions},
    io::{self, BufRead, Read, Seek, SeekFrom, Write},
    os::windows::fs::{MetadataExt, OpenOptionsExt},
    path::Path,
};

type Result<T> = std::result::Result<T, Box<dyn Error>>;
const ORIGINAL: &str = "retained-original.marker";
const CURRENT: &str = "current.marker";
const OTHER: &str = "unrelated.marker";
const CANDIDATE: &str = "restored-candidate.marker";
const OUTPUT: &str = "restored.marker";
const SAVED: &str = "original-before-actor.marker";
const OLD: &[u8] = b"OLD108\n";
const LATER: &[u8] = b"LATER108\n";
const UNRELATED: &[u8] = b"OTHER108\n";

fn info(file: &File) -> Result<Info> {
    let v = winapi_util::file::information(file)?;
    Ok(Info {
        identity: format!("{:x}:{:x}", v.volume_serial_number(), v.file_index()),
        size: v.file_size(),
        links: v.number_of_links().try_into()?,
        attributes: v.file_attributes().try_into()?,
        creation_time: file.metadata()?.creation_time(),
        last_write_time: v.last_write_time().ok_or("MTIME_UNAVAILABLE")?,
    })
}
fn emit(mut value: Value) -> Result<()> {
    for key in [
        "committed",
        "namespaceAcknowledged",
        "productionPublicationAllowed",
        "repairAllowed",
        "profileEnabled",
        "durableCustody",
    ] {
        value[key] = json!(false);
    }
    println!("{value}");
    io::stdout().flush()?;
    Ok(())
}
fn gate(name: &str, captured: &Captured, candidate: Option<&Info>) -> Result<()> {
    emit(
        json!({"barrier":name,"root":captured.root,"original":captured.original,"current":captured.current,"unrelated":captured.other,"candidate":candidate,"destination":OUTPUT,"typedLiveFixture":true,"priorActorStopped":true}),
    )?;
    let mut line = String::new();
    io::stdin().lock().take(32).read_line(&mut line)?;
    let command = line
        .strip_suffix("\r\n")
        .or_else(|| line.strip_suffix('\n'))
        .ok_or("CONTROL_INVALID")?;
    if command == "cancel" {
        return Err("CONTROL_CANCEL".into());
    }
    if command == "fail" {
        return Err("INJECTED_PROTOCOL_FAILURE".into());
    }
    if command
        != if name == "authorize-restore" {
            "restore-fresh"
        } else {
            "continue"
        }
    {
        return Err("CONTROL_INVALID".into());
    }
    Ok(())
}
fn open(path: &Path, share: u32, directory: bool) -> Result<File> {
    Ok(OpenOptions::new()
        .access_mode(0x80020000)
        .share_mode(share)
        .custom_flags(if directory { 0x02200000 } else { 0x00200000 })
        .open(path)?)
}
fn binding(path: &Path, held: &File) -> Result<()> {
    let observed = OpenOptions::new()
        .access_mode(0x20080)
        .share_mode(7)
        .custom_flags(0x02200000)
        .open(path)?;
    if info(&observed)?.identity != info(held)?.identity {
        return Err("PATH_BINDING_CHANGED".into());
    }
    Ok(())
}
fn read(file: &mut File) -> Result<Vec<u8>> {
    if info(file)?.size > 64 {
        return Err("MARKER_SIZE_BOUND".into());
    }
    file.seek(SeekFrom::Start(0))?;
    let mut bytes = Vec::new();
    file.take(65).read_to_end(&mut bytes)?;
    if bytes.len() > 64 {
        return Err("MARKER_SIZE_BOUND".into());
    }
    Ok(bytes)
}
fn write(file: &mut File, bytes: &[u8]) -> Result<()> {
    file.seek(SeekFrom::Start(0))?;
    file.write_all(bytes)?;
    file.set_len(bytes.len() as u64)?;
    Ok(())
}
// The bridge closes the creator without losing identity custody, and captures
// timestamps only after the writable creator closes. Fresh restore holds are
// acquired separately after the fixture actor has synchronously stopped.
fn finish_creator(root: &Path, name: &str, creator: File) -> Result<File> {
    let path = root.join(name);
    let bridge = open(&path, 7, false)?;
    if info(&bridge)?.identity != info(&creator)?.identity {
        return Err("CREATOR_BINDING_CHANGED".into());
    }
    drop(creator);
    let held = open(&path, 1, false)?;
    if info(&bridge)?.identity != info(&held)?.identity {
        return Err("CREATOR_BRIDGE_CHANGED".into());
    }
    Ok(held)
}
// This type has no Deserialize implementation or public constructor. Observation
// JSON cannot reconstruct authority. No external #0094 file is accepted: its
// inherited descriptor is not evidence of this fixture's canonical private DACL.
struct Captured {
    root: Info,
    original: Info,
    current: Info,
    other: Info,
    original_bytes: Vec<u8>,
    current_bytes: Vec<u8>,
    other_bytes: Vec<u8>,
}
fn setup(root: &Path, mode: &str, security: &PrivateSecurity) -> Result<Captured> {
    let ancestors = crate::windows::ancestors(root.parent().ok_or("PARENT_REQUIRED")?)?;
    let parent = ancestors.last().ok_or("PARENT_REQUIRED")?;
    if native::filesystem(parent)? != "NTFS" {
        return Err("FILESYSTEM_UNVERIFIED".into());
    }
    let dir = security.create_directory(
        parent,
        Path::new(root.file_name().ok_or("ROOT_LEAF_REQUIRED")?),
    )?;
    let mut current = security.create_file(&root.join(CURRENT))?;
    write(&mut current, OLD)?;
    current.sync_all()?;
    let original_bytes = read(&mut current)?;
    let wrong = PrivateSecurity::restricted_owner()?;
    let mut original = if mode == "-wrong-security" {
        // Narrow fixed existing-create access avoids asking the restricted
        // descriptor for denied attribute/EA rights. No SDK boundary changes.
        wrong.create_file_access(&root.join(ORIGINAL), 0x80030002)?
    } else {
        security.create_file(&root.join(ORIGINAL))?
    };
    let incomplete_original = info(&original)?;
    write(&mut original, &original_bytes)?;
    original.sync_all()?;
    // The later current version is an actual edit, made before its fresh plan.
    let earlier_current = info(&current)?;
    write(&mut current, LATER)?;
    current.sync_all()?;
    let mut other = security.create_file(&root.join(OTHER))?;
    write(&mut other, UNRELATED)?;
    other.sync_all()?;
    let mut original = finish_creator(root, ORIGINAL, original)?;
    let mut current = finish_creator(root, CURRENT, current)?;
    let mut other = finish_creator(root, OTHER, other)?;
    let original_bytes = read(&mut original)?;
    let current_bytes = read(&mut current)?;
    let other_bytes = read(&mut other)?;
    if original_bytes != OLD || current_bytes != LATER || other_bytes != UNRELATED {
        return Err("FIXTURE_BYTES_CHANGED".into());
    }
    let captured = Captured {
        root: if mode == "-wrong-root" {
            info(parent)?
        } else {
            info(&dir)?
        },
        original: if mode == "-stale-context" {
            incomplete_original
        } else {
            info(&original)?
        },
        current: if mode == "-stale-current" {
            earlier_current
        } else {
            info(&current)?
        },
        other: info(&other)?,
        original_bytes,
        current_bytes,
        other_bytes,
    };
    // Dropping these handles ends the only synchronous fixture actor. No child
    // PID, saved record, external stop assertion or resumed actor is trusted.
    drop((original, current, other, dir, ancestors));
    if matches!(mode, "-foreign-original" | "-same-byte-original") {
        fs::rename(root.join(ORIGINAL), root.join(SAVED))?;
        let mut replacement = security.create_file(&root.join(ORIGINAL))?;
        write(
            &mut replacement,
            if mode == "-same-byte-original" {
                OLD
            } else {
                b"FOREIGN108\n"
            },
        )?;
        replacement.sync_all()?;
    } else if mode == "-corrupt-original" {
        // Authored negative actor only; this is never a restore repair action.
        fs::write(root.join(ORIGINAL), b"CORRUPT108\n")?;
    }
    Ok(captured)
}
fn check_file(
    root: &Path,
    name: &str,
    file: &mut File,
    expected: &Info,
    bytes: &[u8],
    security: &PrivateSecurity,
) -> Result<()> {
    binding(&root.join(name), file)?;
    security.check(file)?;
    native::check_streams(file)?;
    let before = info(file)?;
    if before != *expected || before.links != 1 || before.attributes & 0x410 != 0 {
        return Err("FILE_PROPERTIES_OR_IDENTITY_CHANGED".into());
    }
    if read(file)? != bytes || info(file)? != before {
        return Err("FILE_CONTENT_OR_PROPERTIES_CHANGED".into());
    }
    Ok(())
}
struct Held {
    dir: File,
    original: File,
    current: File,
    other: File,
}
impl Held {
    fn acquire(root: &Path) -> Result<Self> {
        Ok(Self {
            dir: open(root, 3, true)?,
            original: open(&root.join(ORIGINAL), 1, false)?,
            current: open(&root.join(CURRENT), 1, false)?,
            other: open(&root.join(OTHER), 1, false)?,
        })
    }
    fn check(
        &mut self,
        root: &Path,
        c: &Captured,
        security: &PrivateSecurity,
        candidate: bool,
        published: bool,
    ) -> Result<()> {
        security.check(&self.dir)?;
        binding(root, &self.dir)?;
        let now = info(&self.dir)?;
        if now.identity != c.root.identity
            || now.creation_time != c.root.creation_time
            || now.attributes & !32 != c.root.attributes & !32
            || now.attributes & 0x410 != 0x10
        {
            return Err("ROOT_BINDING_OR_PROPERTIES_CHANGED".into());
        }
        check_file(
            root,
            ORIGINAL,
            &mut self.original,
            &c.original,
            &c.original_bytes,
            security,
        )?;
        check_file(
            root,
            CURRENT,
            &mut self.current,
            &c.current,
            &c.current_bytes,
            security,
        )?;
        check_file(
            root,
            OTHER,
            &mut self.other,
            &c.other,
            &c.other_bytes,
            security,
        )?;
        if c.original.identity == c.current.identity
            || c.original.identity == c.other.identity
            || c.current.identity == c.other.identity
        {
            return Err("ALIASED_INPUTS".into());
        }
        let mut names = fs::read_dir(root)?
            // At most four entries are owned here; one extra establishes refusal.
            .take(5)
            .map(|e| Ok(e?.file_name().into_string().map_err(|_| "ENTRY_ENCODING")?))
            .collect::<Result<Vec<_>>>()?;
        names.sort();
        let mut expected = vec![ORIGINAL.to_string(), CURRENT.to_string(), OTHER.to_string()];
        if candidate {
            expected.push(if published { OUTPUT } else { CANDIDATE }.to_string());
        }
        expected.sort();
        if names != expected {
            return Err("NAMESPACE_OR_DESTINATION_CHANGED".into());
        }
        Ok(())
    }
}
fn action(root: &Path, mode: &str, attempted: &mut bool) -> Result<()> {
    let security = PrivateSecurity::current()?;
    let captured = setup(root, mode, &security)?;
    gate("captured", &captured, None)?;
    let _ancestors = crate::windows::ancestors(root.parent().ok_or("PARENT_REQUIRED")?)?;
    let mut held = Held::acquire(root)?;
    held.check(root, &captured, &security, false, false)?;
    gate("guarded", &captured, None)?;
    gate("authorize-restore", &captured, None)?;
    held.check(root, &captured, &security, false, false)?;
    let mut candidate = security.create_file(&root.join(CANDIDATE))?;
    let empty = info(&candidate)?;
    gate("candidate-created", &captured, Some(&empty))?;
    held.check(root, &captured, &security, true, false)?;
    check_file(root, CANDIDATE, &mut candidate, &empty, b"", &security)?;
    let bytes = read(&mut held.original)?;
    if bytes != captured.original_bytes {
        return Err("ORIGINAL_CHANGED".into());
    }
    crate::staging::copy_exact(
        &mut io::Cursor::new(&bytes),
        &mut candidate,
        bytes.len() as u64,
    )?;
    let completed = info(&candidate)?;
    if [
        captured.original.identity.as_str(),
        captured.current.identity.as_str(),
        captured.other.identity.as_str(),
    ]
    .contains(&completed.identity.as_str())
    {
        return Err("ALIASED_CANDIDATE".into());
    }
    candidate.sync_all()?;
    check_file(root, CANDIDATE, &mut candidate, &completed, OLD, &security)?;
    gate("candidate-synced", &captured, Some(&completed))?;
    held.check(root, &captured, &security, true, false)?;
    check_file(root, CANDIDATE, &mut candidate, &completed, OLD, &security)?;
    gate("prepublish", &captured, Some(&completed))?;
    held.check(root, &captured, &security, true, false)?;
    check_file(root, CANDIDATE, &mut candidate, &completed, OLD, &security)?;
    if mode == "-late-collision" {
        // This authored actor runs after the final validation to exercise the
        // native no-replace operation itself, rather than an existence check.
        let mut winner = security.create_file(&root.join(OUTPUT))?;
        write(&mut winner, b"WINNER108\n")?;
        winner.sync_all()?;
    }
    *attempted = true;
    native::rename(&candidate, &held.dir, &root.join(OUTPUT), false)?;
    gate("published", &captured, Some(&completed))?;
    held.check(root, &captured, &security, true, true)?;
    check_file(root, OUTPUT, &mut candidate, &completed, OLD, &security)?;
    emit(
        json!({"outcome":"restored-copy-observed","publicationAttempted":true,"publicationMayHaveOccurred":true,"root":captured.root,"original":captured.original,"current":captured.current,"unrelated":captured.other,"candidate":completed,"destination":OUTPUT,"allArtifactsRetained":true}),
    )
}
pub fn run(root: &Path, mode: &str) -> Result<()> {
    if ![
        "",
        "-stale-context",
        "-wrong-root",
        "-foreign-original",
        "-same-byte-original",
        "-corrupt-original",
        "-stale-current",
        "-wrong-security",
        "-late-collision",
    ]
    .contains(&mode)
    {
        return Err("RESTORE_MODE_UNVERIFIED".into());
    }
    let scratch = fs::canonicalize(Path::new(env!("CARGO_MANIFEST_DIR")).join("../../.local"))?;
    let parent = fs::canonicalize(root.parent().ok_or("PARENT_REQUIRED")?)?;
    if !root.is_absolute() || !parent.starts_with(&scratch) || root.file_name().is_none() {
        return Err("RESTORE_ROOT_MUST_BE_BELOW_CHECKOUT_LOCAL".into());
    }
    let mut attempted = false;
    match action(root, mode, &mut attempted) {
        Ok(()) => Ok(()),
        Err(error) => {
            emit(
                json!({"outcome":if attempted {"recovery-required"} else {"refused"},"diagnostic":error.to_string(),"publicationAttempted":attempted,"publicationMayHaveOccurred":attempted,"allArtifactsRetained":true}),
            )?;
            Ok(())
        }
    }
}
