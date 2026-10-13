use crate::{
    native::{self, PrivateSecurity},
    oplock::{self, Oplock},
    path::marker_path,
};
use serde_json::json;
use std::{
    error::Error,
    fs::{File, OpenOptions},
    io::{self, BufRead, Read, Write},
    os::windows::fs::OpenOptionsExt,
    path::{Path, PathBuf},
};
type Result<T> = std::result::Result<T, Box<dyn Error>>;
fn emit(value: serde_json::Value) -> Result<()> {
    println!("{value}");
    io::stdout().flush()?;
    Ok(())
}
fn barrier(name: &str) -> Result<()> {
    emit(json!({"barrier":name,"productionPublicationAllowed":false,"committed":false}))?;
    let mut line = String::new();
    io::stdin().lock().take(32).read_line(&mut line)?;
    if line != "continue\n" && line != "continue\r\n" {
        return Err("CONTROL_STOP".into());
    }
    Ok(())
}
fn ancestors(path: &Path) -> Result<Vec<File>> {
    let mut result = Vec::new();
    let mut current = PathBuf::new();
    for component in path.parent().ok_or("PARENT_REQUIRED")?.components() {
        current.push(component.as_os_str());
        if current.has_root() {
            let handle = OpenOptions::new()
                .access_mode(0x20080)
                .share_mode(3)
                .custom_flags(0x02200000)
                .open(&current)?;
            let info = winapi_util::file::information(&handle)?;
            if info.file_attributes() & 0x400 != 0 || info.file_attributes() & 0x10 == 0 {
                return Err("PARENT_REPARSE_OR_TYPE".into());
            }
            result.push(handle);
        }
    }
    if native::filesystem(result.last().ok_or("PARENT_REQUIRED")?)? != "NTFS" {
        return Err("FILESYSTEM_UNVERIFIED".into());
    }
    Ok(result)
}
pub fn run() -> Result<()> {
    let args: Vec<_> = std::env::args_os().skip(1).collect();
    if args.len() != 2 {
        return Err("EXPECTED_MODE_AND_OWNED_EXISTING_MARKER".into());
    }
    let mode = args[0].to_str().ok_or("MODE_ENCODING")?;
    if mode == "admit" {
        return emit(
            json!({"outcome":"refused-before-effects","missingCells":["complete-existing-source-property-exclusion","authenticated-restart-custody","qualified-windows-namespace-receipt-persistence"],"productionPublicationAllowed":false,"committed":false}),
        );
    }
    let level = match mode {
        "prepare" | "sharing" => 0,
        "rh" => 3,
        "rw" => 5,
        "rwh" => 7,
        _ => return Err("MODE_UNVERIFIED".into()),
    };
    let path = Path::new(&args[1]);
    marker_path(path)?;
    let _ancestors = ancestors(path)?;
    let ordinary = PrivateSecurity::current()?;
    if mode == "prepare" {
        let mut file = ordinary.create_file(path)?;
        file.write_all(&vec![b'3'; 65536])?;
        file.sync_all()?;
        return emit(
            json!({"outcome":"owned-marker-prepared","productionPublicationAllowed":false,"committed":false}),
        );
    }
    // An existing source is read/control only. No ACL, timestamp or content set.
    // Overlapped I/O is required by the oplock protocol; reads use a separate
    // bounded OVERLAPPED request on the same held object, not a pathname reopen.
    let file = OpenOptions::new()
        .access_mode(0x80020000)
        .share_mode(1)
        .custom_flags(0x40200000)
        .open(path)?;
    let initial = winapi_util::file::information(&file)?;
    if initial.file_attributes() & 0x410 != 0
        || initial.number_of_links() != 1
        || initial.file_size() != 65536
    {
        return Err("SOURCE_SHAPE_UNVERIFIED".into());
    }
    ordinary.check(&file)?;
    native::check_streams(&file)?;
    if !oplock::marker_matches(&file)? {
        return Err("SOURCE_BYTES_UNVERIFIED".into());
    }
    let mut lock = if level == 0 {
        None
    } else {
        match Oplock::request(file.try_clone()?, level) {
            Ok(value) => Some(value),
            Err(error) => {
                return emit(
                    json!({"outcome":"source-guard-refused","winError":error.raw_os_error(),"productionPublicationAllowed":false,"committed":false}),
                );
            }
        }
    };
    emit(
        json!({"outcome":"source-held","requestedLevel":level,"oplockGranted":lock.is_some(),"productionPublicationAllowed":false,"committed":false}),
    )?;
    barrier("held")?;
    let state = match lock.as_mut() {
        Some(value) => value.observe()?,
        None => json!({"broken":false}),
    };
    let live = winapi_util::file::information(&file)?;
    emit(
        json!({"outcome":"held-source-observed","oplock":state,"identityUnchanged":live.volume_serial_number()==initial.volume_serial_number() && live.file_index()==initial.file_index(),"contentUnchanged":oplock::marker_matches(&file)?,"securityUnchanged":ordinary.check(&file).is_ok(),"mtimeUnchanged":live.last_write_time()==initial.last_write_time(),"attributesUnchanged":live.file_attributes()==initial.file_attributes(),"defaultStreamOnly":native::check_streams(&file).is_ok(),"linkCount":live.number_of_links(),"productionPublicationAllowed":false,"committed":false}),
    )?;
    barrier("observed")?;
    // Close the original and duplicated holder together. No explicit ACK that
    // pretends to retain full exclusion after a break is attempted.
    drop(lock);
    drop(file);
    emit(
        json!({"outcome":"holder-released","productionPublicationAllowed":false,"committed":false}),
    )
}
