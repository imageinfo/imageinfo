use crate::native::PrivateSecurity;
use serde_json::json;
use std::{
    error::Error,
    fs::{File, OpenOptions},
    io::{self, BufRead, Read, Seek, SeekFrom, Write},
    os::windows::{ffi::OsStrExt, fs::OpenOptionsExt},
    path::{Component, Path, Prefix},
};
type Result<T> = std::result::Result<T, Box<dyn Error>>;
fn marker_path(path: &Path) -> Result<()> {
    let spelling: Vec<u16> = path.as_os_str().encode_wide().collect();
    if !path.is_absolute()
        || spelling.len() > 200
        || spelling.contains(&0)
        || spelling
            .split(|v| *v == 47 || *v == 92)
            .any(|p| p == [46] || p == [46, 46])
    {
        return Err("MARKER_PATH_UNVERIFIED".into());
    }
    for part in path.components() {
        match part {
            Component::Prefix(p) if matches!(p.kind(), Prefix::Disk(_)) => {}
            Component::RootDir => {}
            Component::Normal(name)
                if !name
                    .encode_wide()
                    .any(|u| u < 32 || [58, 42, 63, 34, 60, 62, 124].contains(&u))
                    && !matches!(name.encode_wide().last(), Some(32 | 46)) =>
            {
                let stem = name
                    .to_string_lossy()
                    .split('.')
                    .next()
                    .unwrap_or("")
                    .to_ascii_uppercase();
                if matches!(stem.as_str(), "CON" | "PRN" | "AUX" | "NUL")
                    || (stem.len() == 4
                        && (stem.starts_with("COM") || stem.starts_with("LPT"))
                        && matches!(stem.as_bytes()[3], b'1'..=b'9'))
                {
                    return Err("MARKER_PATH_UNVERIFIED".into());
                }
            }
            _ => return Err("MARKER_PATH_UNVERIFIED".into()),
        }
    }
    if path
        .file_name()
        .is_none_or(|v| !v.to_string_lossy().ends_with(".marker"))
    {
        return Err("MARKER_PATH_UNVERIFIED".into());
    }
    Ok(())
}
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
fn identity(file: &File) -> Result<String> {
    let i = winapi_util::file::information(file)?;
    Ok(format!(
        "{:x}:{:x}",
        i.volume_serial_number(),
        i.file_index()
    ))
}
fn contents(file: &mut File) -> Result<Vec<u8>> {
    file.seek(SeekFrom::Start(0))?;
    let mut data = Vec::new();
    file.take(65537).read_to_end(&mut data)?;
    Ok(data)
}
pub fn run() -> Result<()> {
    let args: Vec<_> = std::env::args_os().skip(1).collect();
    if args.len() != 2 {
        return Err("EXPECTED_MODE_AND_NEW_MARKER_PATH".into());
    }
    let mode = args[0].to_str().ok_or("MODE_ENCODING")?;
    if mode == "admit" {
        return emit(
            json!({"outcome":"refused-before-effects","missingCells":["existing-source-property-exclusion","authenticated-restart-custody","qualified-namespace-receipt-persistence"],"productionPublicationAllowed":false,"committed":false}),
        );
    }
    if ![
        "ordinary",
        "fresh-restricted",
        "minimal-restricted",
        "retained-security",
        "seal-after-open",
        "sealed-exit",
        "publish-restricted",
        "fresh-sealed",
        "publish-sealed",
    ]
    .contains(&mode)
    {
        return Err("MODE_UNVERIFIED".into());
    }
    let path = Path::new(&args[1]);
    marker_path(path)?;
    let ordinary = PrivateSecurity::current()?;
    let restricted = PrivateSecurity::restricted_owner()?;
    let sealed = PrivateSecurity::sealed_owner()?;
    // Minimal access excludes new property/security rights, but its creation
    // behavior is measured rather than inferred from an ACL string.
    let minimal = 0x0002_0083 | 0x0001_0000; // READ_CONTROL, read data/attributes, write data, DELETE
    let access = if mode == "minimal-restricted" {
        minimal
    } else if matches!(mode, "retained-security" | "seal-after-open") {
        minimal | 0x0004_0000
    } else {
        0xc003_0000
    };
    let security = if matches!(mode, "ordinary" | "seal-after-open") {
        &ordinary
    } else if matches!(mode, "fresh-sealed" | "publish-sealed") {
        &sealed
    } else {
        &restricted
    };
    let mut ancestors = Vec::new();
    let mut current = std::path::PathBuf::new();
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
            ancestors.push(handle);
        }
    }
    let parent = ancestors.last().ok_or("PARENT_REQUIRED")?;
    if crate::native::filesystem(parent)? != "NTFS" {
        return Err("FILESYSTEM_UNVERIFIED".into());
    }
    let root = if matches!(mode, "publish-restricted" | "publish-sealed") {
        Some(restricted.create_directory(parent, Path::new("txn"))?)
    } else {
        None
    };
    let stage_path = if root.is_some() {
        path.parent().unwrap().join("txn").join("stage.marker")
    } else {
        path.to_owned()
    };
    let mut file = security.create_file_access(&stage_path, access)?;
    let original_identity = identity(&file)?;
    file.write_all(&vec![0x33; 65536])?;
    file.sync_all()?;
    let initial_info = winapi_util::file::information(&file)?;
    barrier("created")?;
    if mode == "seal-after-open"
        && let Err(error) = restricted.apply_to_owned_marker(&file)
    {
        if error.to_string() != "PRIVATE_OWNER_OR_DACL_CHANGED" {
            return Err(error.into());
        }
        // The OS accepted SetSecurityInfo but its returned descriptor differs
        // from atomic creation's exact policy. Retain/report that distinction.
        emit(
            json!({"postSealExactPolicyMismatch":true,"productionPublicationAllowed":false,"committed":false}),
        )?;
    }
    if mode == "sealed-exit" {
        return emit(
            json!({"outcome":"sealed-marker-retained","productionPublicationAllowed":false,"committed":false}),
        );
    }
    barrier("guarded")?;
    if let Some(root) = &root {
        let output = stage_path.with_file_name("output.marker");
        crate::native::rename(&file, root, &output, false)?;
        file.sync_all()?;
        root.sync_all()?;
        let installed = OpenOptions::new()
            .access_mode(0x20080)
            .share_mode(7)
            .custom_flags(0x02200000)
            .open(&output)?;
        if identity(&installed)? != original_identity {
            return Err("INSTALLED_IDENTITY_CHANGED".into());
        }
        security.check(&installed)?;
        barrier("published")?;
    }
    let dacl_unchanged = security.check(&file).is_ok();
    let property_policy = if mode == "seal-after-open" {
        restricted.check(&file).is_ok()
    } else {
        dacl_unchanged
    };
    let info = winapi_util::file::information(&file)?;
    emit(
        json!({"outcome":"owned-marker-observed","identityUnchanged":identity(&file)?==original_identity,"contentUnchanged":contents(&mut file)?==vec![0x33;65536],"privatePropertyPolicyMatches":property_policy,"mtimeUnchanged":info.last_write_time()==initial_info.last_write_time(),"attributesUnchanged":info.file_attributes()==initial_info.file_attributes(),"defaultStreamOnly":crate::native::check_streams(&file).is_ok(),"linkCount":info.number_of_links(),"productionPublicationAllowed":false,"committed":false}),
    )?;
    // A held WRITE_DAC right may survive restrictions. This explicit holder call
    // measures that boundary; it never unseals originals or changes ownership.
    if mode == "retained-security" {
        let restored = ordinary.apply_to_owned_marker(&file).is_ok();
        emit(
            json!({"holderCanRestorePrivateDacl":restored,"productionPublicationAllowed":false,"committed":false}),
        )?;
    }
    Ok(())
}
