use crate::native::PrivateSecurity;
use serde_json::{Value, json};
use std::{
    error::Error,
    fs::{File, OpenOptions},
    io::{self, BufRead, Read, Seek, SeekFrom, Write},
    os::windows::{
        ffi::OsStrExt,
        fs::{MetadataExt, OpenOptionsExt},
    },
    path::{Component, Path, PathBuf},
};
use windows_sys::Win32::Storage::FileSystem::{
    FILE_ATTRIBUTE_ARCHIVE, FILE_ATTRIBUTE_DIRECTORY, FILE_ATTRIBUTE_NORMAL,
    FILE_ATTRIBUTE_NOT_CONTENT_INDEXED,
};
type Result<T> = std::result::Result<T, Box<dyn Error>>;
fn emit(value: Value) -> Result<()> {
    println!("{value}");
    io::stdout().flush()?;
    Ok(())
}
fn barrier(name: &str) -> Result<()> {
    emit(json!({"barrier":name,"productionPublicationAllowed":false}))?;
    control()
}
fn control() -> Result<()> {
    let mut line = String::new();
    io::stdin().lock().take(32).read_line(&mut line)?;
    if !line.ends_with('\n') {
        return Err("CONTROL_INVALID".into());
    }
    match line.trim() {
        "continue" => Ok(()),
        "cancel" => Err("CONTROL_CANCEL".into()),
        "fail" => Err("CONTROL_FAILURE".into()),
        _ => Err("CONTROL_INVALID".into()),
    }
}
fn information(file: &File) -> Result<Value> {
    let i = winapi_util::file::information(file)?;
    Ok(
        json!({"identity":format!("{:x}:{:x}",i.volume_serial_number(),i.file_index()),"size":i.file_size(),"links":i.number_of_links(),"attributes":i.file_attributes(),"creationTime":file.metadata()?.creation_time(),"lastWriteTime":i.last_write_time()}),
    )
}
fn path_valid(root: &Path) -> Result<()> {
    if !root.is_absolute() || root.as_os_str().len() > 200 {
        return Err("PATH_UNVERIFIED".into());
    }
    let spelling: Vec<u16> = root.as_os_str().encode_wide().collect();
    if spelling
        .split(|u| *u == b'\\' as u16 || *u == b'/' as u16)
        .any(|part| part == [46] || part == [46, 46])
    {
        return Err("PATH_UNVERIFIED".into());
    }
    for part in root.components() {
        match part {
            Component::Prefix(p) if matches!(p.kind(), std::path::Prefix::Disk(_)) => {}
            Component::RootDir => {}
            Component::Normal(n)
                if !n.encode_wide().any(|u| u < 32 || u == b':' as u16)
                    && !matches!(n.encode_wide().last(), Some(32 | 46))
                    && !n.to_str().is_some_and(|name| {
                        let base = name.split('.').next().unwrap_or("").to_ascii_uppercase();
                        matches!(base.as_str(), "CON" | "PRN" | "AUX" | "NUL")
                            || (base.len() == 4
                                && (base.starts_with("COM") || base.starts_with("LPT"))
                                && matches!(base.as_bytes()[3], b'1'..=b'9'))
                    }) => {}
            _ => return Err("PATH_UNVERIFIED".into()),
        }
    }
    if root.file_name().is_none() {
        return Err("ROOT_LEAF_REQUIRED".into());
    }
    Ok(())
}
fn ancestors(path: &Path) -> Result<Vec<File>> {
    let mut current = PathBuf::new();
    let mut held = Vec::new();
    for part in path.components() {
        current.push(part.as_os_str());
        if current.has_root() {
            // Sharing writes permits directory-entry operations; sharing no DELETE
            // excludes parent rename/deletion. Stage contents use their own guard.
            let file = OpenOptions::new()
                .read(true)
                .share_mode(3)
                .custom_flags(0x02200000)
                .open(&current)?;
            if !file.metadata()?.is_dir() || file.metadata()?.file_attributes() & 0x400 != 0 {
                return Err("REPARSE_OR_TYPE".into());
            }
            held.push(file);
        }
    }
    Ok(held)
}
fn observe_path(path: &Path) -> Result<File> {
    // Attribute/security inspection requests no content-write/delete access, and
    // its sharing permits the retained stage's own read/write/delete handle.
    Ok(OpenOptions::new()
        .access_mode(0x20080)
        .share_mode(7)
        .custom_flags(0x02200000)
        .open(path)?)
}
fn check_binding(path: &Path, held: &File) -> Result<()> {
    if information(&observe_path(path)?)?["identity"] != information(held)?["identity"] {
        return Err("PATH_OBJECT_CHANGED".into());
    }
    Ok(())
}
fn contents(file: &mut File) -> Result<Vec<u8>> {
    file.seek(SeekFrom::Start(0))?;
    let mut bytes = Vec::new();
    file.take(65537).read_to_end(&mut bytes)?;
    if bytes.len() != 65536 {
        return Err("MARKER_LENGTH_CHANGED".into());
    }
    Ok(bytes)
}
fn check_stage(
    file: &mut File,
    security: &PrivateSecurity,
    before: &Value,
    hash: &str,
) -> Result<()> {
    security.check(file)?;
    crate::native::check_streams(file)?;
    if file.metadata()?.file_attributes()
        & !(FILE_ATTRIBUTE_ARCHIVE | FILE_ATTRIBUTE_NORMAL | FILE_ATTRIBUTE_NOT_CONTENT_INDEXED)
        != 0
    {
        return Err("STAGE_ATTRIBUTES_UNSUPPORTED".into());
    }
    if information(file)? != *before || imageinfo_recovery_probe::digest(&contents(file)?) != hash {
        return Err("STAGE_PROPERTY_OR_CONTENT_CHANGED".into());
    }
    Ok(())
}
fn record(
    root: &Path,
    security: &PrivateSecurity,
    name: &str,
    phase: &str,
    directory: &File,
    stage: &File,
    hash: &str,
) -> Result<File> {
    let mut file = security.create_file(&root.join(name))?;
    let body=json!({"purpose":"imageinfo-bound-windows-research-v1","phase":phase,"observationOnly":true,"committed":false,"namespaceAcknowledged":false,
        "expectedAbsence":true,"target":"output.bin","root":information(directory)?,"candidate":information(stage)?,"candidateSha256":hash}).to_string();
    let envelope = json!({"body":body,"sha256":imageinfo_recovery_probe::digest(body.as_bytes())});
    file.write_all(envelope.to_string().as_bytes())?;
    file.sync_all()?;
    security.check(&file)?;
    Ok(file)
}
fn check_directory(
    path: &Path,
    file: &File,
    security: &PrivateSecurity,
    initial_attributes: u32,
) -> Result<()> {
    security.check(file)?;
    check_binding(path, file)?;
    let attributes = file.metadata()?.file_attributes();
    // NOT_CONTENT_INDEXED is an inherited indexing preference, not weaker ACLs
    // or a storage/provider transformation. Preserve it; reject every unsupported
    // attribute and a concurrent change of that explicitly captured preference.
    if !file.metadata()?.is_dir()
        || attributes
            & !(FILE_ATTRIBUTE_DIRECTORY
                | FILE_ATTRIBUTE_ARCHIVE
                | FILE_ATTRIBUTE_NOT_CONTENT_INDEXED)
            != 0
        || attributes & FILE_ATTRIBUTE_NOT_CONTENT_INDEXED
            != initial_attributes & FILE_ATTRIBUTE_NOT_CONTENT_INDEXED
    {
        return Err(format!(
            "DIRECTORY_ATTRIBUTES_CHANGED_{:08X}",
            file.metadata()?.file_attributes()
        )
        .into());
    }
    Ok(())
}
pub fn run() -> Result<()> {
    let args: Vec<_> = std::env::args_os().skip(1).collect();
    if args.len() != 2 {
        return Err("EXPECTED_ROOT_AND_MODE".into());
    }
    let root = PathBuf::from(&args[0]);
    path_valid(&root)?;
    let rooted = match args[1].to_str() {
        Some("rooted") => true,
        Some("absolute") => false,
        Some("admit") => {
            emit(
                json!({"outcome":"refused-before-effects","missingCells":["mandatory-property-protection","namespace-persistence-qualification","durable-receipt-and-recovery"],"productionPublicationAllowed":false,"committed":false,"workerArtifacts":0}),
            )?;
            return Ok(());
        }
        _ => return Err("MODE_UNVERIFIED".into()),
    };
    let _ancestors = ancestors(root.parent().ok_or("PARENT_MISSING")?)?;
    let parent = _ancestors.last().ok_or("PARENT_NOT_HELD")?;
    if crate::native::filesystem(parent)? != "NTFS" {
        return Err("FILESYSTEM_UNVERIFIED".into());
    }
    let security = PrivateSecurity::current()?;
    let directory = security.create_directory(
        parent,
        Path::new(root.file_name().ok_or("ROOT_LEAF_REQUIRED")?),
    )?;
    let root_info = information(&directory)?;
    let root_attributes = directory.metadata()?.file_attributes();
    check_binding(&root, &directory)?;
    emit(
        json!({"barrier":"root-created","rootIdentity":root_info["identity"],"rootAttributes":root_info["attributes"],"productionPublicationAllowed":false}),
    )?;
    control()?;
    let mut file = security.create_file(&root.join("candidate.bin"))?;
    file.write_all(&vec![0x32; 65536])?;
    file.sync_all()?;
    directory.sync_all()?;
    let before = information(&file)?;
    let hash = imageinfo_recovery_probe::digest(&contents(&mut file)?);
    check_stage(&mut file, &security, &before, &hash)?;
    emit(
        json!({"barrier":"candidate-flushed","candidate":before,"sha256":hash,"productionPublicationAllowed":false}),
    )?;
    control()?;
    let prepared = record(
        &root,
        &security,
        "prepared.record",
        "prepared",
        &directory,
        &file,
        &hash,
    )?;
    directory.sync_all()?;
    barrier("prepared-record-flushed")?;
    let intent = record(
        &root,
        &security,
        "intent.record",
        "publication-intent",
        &directory,
        &file,
        &hash,
    )?;
    directory.sync_all()?;
    barrier("intent-record-flushed")?;
    check_directory(&root, &directory, &security, root_attributes)?;
    check_stage(&mut file, &security, &before, &hash)?;
    security.check(&prepared)?;
    security.check(&intent)?;
    barrier("validated-before-publish")?;
    let destination = if rooted {
        PathBuf::from("output.bin")
    } else {
        root.join("output.bin")
    };
    if let Err(error) = crate::native::rename(&file, &directory, &destination, rooted) {
        emit(
            json!({"outcome":"publication-refused-or-uncertain","errorCode":error.raw_os_error(),"productionPublicationAllowed":false,"committed":false,"retained":true}),
        )?;
        return Ok(());
    }
    barrier("published")?;
    check_binding(&root.join("output.bin"), &file)?;
    check_binding(&root, &directory)?;
    check_directory(&root, &directory, &security, root_attributes)?;
    check_stage(&mut file, &security, &before, &hash)?;
    file.sync_all()?;
    barrier("output-file-flushed")?;
    let flush = directory.sync_all();
    emit(
        json!({"barrier":"directory-flush-attempted","callSucceeded":flush.is_ok(),"errorCode":flush.err().and_then(|e|e.raw_os_error()),"namespaceAcknowledged":false,"productionPublicationAllowed":false}),
    )?;
    control()?;
    let observation = record(
        &root,
        &security,
        "observation.record",
        "recovery-required",
        &directory,
        &file,
        &hash,
    )?;
    barrier("observation-record-flushed")?;
    check_directory(&root, &directory, &security, root_attributes)?;
    check_stage(&mut file, &security, &before, &hash)?;
    check_binding(&root.join("output.bin"), &file)?;
    security.check(&prepared)?;
    security.check(&intent)?;
    security.check(&observation)?;
    emit(
        json!({"outcome":"recovery-required","rootIdentityStable":information(&directory)?["identity"]==root_info["identity"],"heldCandidateIdentityStable":information(&file)?["identity"]==before["identity"],"namespaceAcknowledged":false,"committed":false,"productionPublicationAllowed":false}),
    )?;
    Ok(())
}
