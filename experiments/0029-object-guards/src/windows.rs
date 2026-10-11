use std::{
    error::Error,
    fs::{File, OpenOptions},
    io::{self, Read, Seek, SeekFrom, Write},
    os::windows::fs::{MetadataExt, OpenOptionsExt},
    path::{Component, Path, PathBuf},
};
type Result<T> = std::result::Result<T, Box<dyn Error>>;
const FLAGS: u32 = 0x02000000 | 0x00200000; // BACKUP_SEMANTICS | OPEN_REPARSE_POINT
const MAX: u64 = 256 * 1024 * 1024;

fn information(file: &File) -> Result<serde_json::Value> {
    let info = winapi_util::file::information(file)?;
    Ok(
        serde_json::json!({"identity":format!("{:x}:{:x}",info.volume_serial_number(),info.file_index()),
        "size":info.file_size(),"links":info.number_of_links(),"attributes":info.file_attributes(),
        "lastWriteTime":info.last_write_time()}),
    )
}
fn ancestor_handles(path: &Path) -> Result<Vec<File>> {
    if !path.is_absolute() || path.as_os_str().len() > 240 {
        return Err("Absolute bounded local test path required".into());
    }
    let mut current = PathBuf::new();
    let mut held = Vec::new();
    let parent = path.parent().ok_or("Missing parent")?;
    for component in parent.components() {
        match component {
            Component::Prefix(prefix) => {
                if !matches!(prefix.kind(), std::path::Prefix::Disk(_)) {
                    return Err("UNC/device/verbatim paths unverified".into());
                }
                current.push(component.as_os_str());
            }
            Component::RootDir | Component::Normal(_) => current.push(component.as_os_str()),
            _ => return Err("Dot/parent path components refused".into()),
        }
        if current.has_root() {
            let handle = OpenOptions::new()
                .read(true)
                .share_mode(1)
                .custom_flags(FLAGS)
                .open(&current)?;
            let metadata = handle.metadata()?;
            if !metadata.is_dir() || metadata.file_attributes() & 0x400 != 0 {
                return Err("Reparse ancestor refused".into());
            }
            held.push(handle);
        }
    }
    Ok(held)
}
fn bytes(file: &mut File) -> Result<Vec<u8>> {
    if file.metadata()?.len() > MAX {
        return Err("Input exceeds research bound".into());
    }
    file.seek(SeekFrom::Start(0))?;
    let mut value = Vec::new();
    file.take(MAX + 1).read_to_end(&mut value)?;
    if value.len() as u64 > MAX {
        return Err("Input grew beyond research bound".into());
    }
    Ok(value)
}
fn observe(mut file: File, held: Vec<File>) -> Result<()> {
    let before = information(&file)?;
    let data = bytes(&mut file)?;
    println!(
        "{}",
        serde_json::json!({"barrier":"guard-held","before":before,
        "dataSha256":imageinfo_recovery_probe::digest(&data),"heldAncestors":held.len(),"profileVerified":false})
    );
    io::stdout().flush()?;
    let mut line = String::new();
    io::stdin().read_line(&mut line)?;
    let after = information(&file)?;
    let current = bytes(&mut file)?;
    println!(
        "{}",
        serde_json::json!({"contentUnchanged":data==current,"objectUnchanged":before["identity"]==after["identity"],
        "propertiesUnchanged":before==after,"after":after,"profileVerified":false,
        "productionPublicationAllowed":false,"note":"Sharing protects content/delete opens, not every metadata right"})
    );
    drop(held);
    Ok(())
}
pub fn hold_source(path: &Path) -> Result<()> {
    let held = ancestor_handles(path)?;
    let file = OpenOptions::new()
        .read(true)
        .share_mode(1)
        .custom_flags(0x00200000)
        .open(path)?;
    let metadata = file.metadata()?;
    if !metadata.is_file() || metadata.file_attributes() & 0x400 != 0 {
        return Err("Direct regular source required".into());
    }
    observe(file, held)
}
pub fn hold_stage(root: &Path) -> Result<()> {
    let stage = root.join("guard-stage.bin");
    let held = ancestor_handles(&stage)?;
    // Atomic new-file construction plus FILE_SHARE_READ excludes later content
    // writers through all aliases while this handle remains live. ACL/attributes
    // and a real publication backend are different gates, not inferred here.
    let mut file = OpenOptions::new()
        .read(true)
        .write(true)
        .create_new(true)
        .share_mode(1)
        .custom_flags(0x00200000)
        .open(&stage)?;
    file.write_all(&vec![0x29; 65536])?;
    file.flush()?;
    file.sync_all()?;
    observe(file, held)
}
