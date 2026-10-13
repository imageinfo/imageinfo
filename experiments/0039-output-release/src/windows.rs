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
fn check(file: &mut File, before: &Snapshot) -> Result<()> {
    if &snapshot(file)? != before || before.links != 1 || before.mtime.is_none() {
        return Err("OWNED_OBJECT_BINDING_CHANGED".into());
    }
    native::check_streams(file)?;
    file.seek(SeekFrom::Start(0))?;
    let mut data = Vec::new();
    Read::by_ref(file).take(65537).read_to_end(&mut data)?;
    if data != vec![b'3'; 65536] {
        return Err("OWNED_CONTENT_CHANGED".into());
    }
    Ok(())
}
fn emit(mut value: Value) -> Result<()> {
    for key in [
        "committed",
        "productionPublicationAllowed",
        "namespaceAcknowledged",
        "restartRepairAllowed",
    ] {
        value[key] = json!(false);
    }
    println!("{value}");
    io::stdout().flush()?;
    Ok(())
}
fn barrier(name: &str) -> Result<()> {
    emit(json!({"barrier":name}))?;
    let mut line = String::new();
    io::stdin().lock().take(32).read_line(&mut line)?;
    if !["continue\n", "continue\r\n"].contains(&line.as_str()) {
        return Err("CONTROL_STOP".into());
    }
    Ok(())
}
fn ancestors(root: &Path) -> Result<Vec<File>> {
    let mut current = PathBuf::new();
    let mut held = Vec::new();
    for part in root.parent().ok_or("PARENT_REQUIRED")?.components() {
        current.push(part.as_os_str());
        if current.has_root() {
            let file = OpenOptions::new()
                .access_mode(0x20080)
                .share_mode(3)
                .custom_flags(0x02200000)
                .open(&current)?;
            if winapi_util::file::information(&file)?.file_attributes() & 0x410 != 0x10 {
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
pub fn run() -> Result<()> {
    let args: Vec<_> = std::env::args_os().skip(1).collect();
    if args.len() != 2 {
        return Err("EXPECTED_MODE_AND_NEW_ROOT".into());
    }
    let mode = args[0].to_str().ok_or("MODE_ENCODING")?;
    if ["admit", "finalize", "prune"].contains(&mode) {
        return emit(json!({"outcome":"refused-before-effects","workerArtifacts":0}));
    }
    if ![
        "release",
        "full-control",
        "ordinary-control",
        "no-write-dac",
        "inject-before-release",
        "inject-after-release",
    ]
    .contains(&mode)
    {
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
    // Rights are requested at exclusive fresh creation, before another actor can
    // open this object. Never reopen by path to obtain restoration authority.
    let access = if mode == "full-control" {
        0x001f01ff
    } else {
        0xc0030000 | if mode == "no-write-dac" { 0 } else { 0x40000 }
    };
    let policy = if mode == "ordinary-control" {
        &ordinary
    } else {
        &sealed
    };
    let mut file = policy.create_file_access(&root.join("stage.marker"), access)?;
    file.write_all(&vec![b'3'; 65536])?;
    file.sync_all()?;
    let before = snapshot(&file)?;
    barrier("guarded")?;
    ordinary.check(&directory)?;
    policy.check(&file)?;
    check(&mut file, &before)?;
    native::rename(&file, &directory, &root.join("output.marker"), false)?;
    file.sync_all()?;
    directory.sync_all()?;
    barrier("published-sealed")?;
    ordinary.check(&directory)?;
    policy.check(&file)?;
    check(&mut file, &before)?;
    if mode == "inject-before-release" {
        return Err("INJECTED_BEFORE_POLICY_RELEASE".into());
    }
    // Releasing the policy ends property exclusion. This is a visible boundary,
    // not a committed receipt or permission to restore an original on restart.
    let release = ordinary.apply_to_owned_marker(&file);
    let error_code = release.as_ref().err().and_then(|e| e.raw_os_error());
    let policy_matches = release.is_ok();
    emit(
        json!({"releaseExactCreationPolicyMatches":policy_matches,"releaseOsError":error_code,"releaseDiagnostic":release.err().map(|e|e.to_string()),"contentAndIdentityUnchanged":check(&mut file,&before).is_ok()}),
    )?;
    barrier("policy-release-attempted")?;
    if mode == "inject-after-release" {
        return Err("INJECTED_AFTER_POLICY_RELEASE".into());
    }
    emit(
        json!({"outcome":if policy_matches {"owned-output-policy-matches"} else {"owned-output-policy-release-unverified"},"rootRetained":true}),
    )
}
