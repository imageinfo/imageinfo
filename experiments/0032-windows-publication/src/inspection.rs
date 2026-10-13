//! #0036 read-only restart observations for the existing marker record format.
use crate::inspection_record::{Body, Info, MAX_RECORD, classify, decode};
use crate::{
    native::{self, PrivateSecurity},
    windows,
};
use imageinfo_recovery_probe::digest;
use serde_json::{Value, json};
use std::{
    error::Error,
    fs::{self, File, OpenOptions},
    io::{Read, Write},
    os::windows::fs::{MetadataExt, OpenOptionsExt},
    path::Path,
};
type Result<T> = std::result::Result<T, Box<dyn Error>>;
const NAMES: [&str; 5] = [
    "prepared.record",
    "intent.record",
    "observation.record",
    "candidate.bin",
    "output.bin",
];

fn info(file: &File) -> Result<Info> {
    let i = winapi_util::file::information(file)?;
    Ok(Info {
        identity: format!("{:x}:{:x}", i.volume_serial_number(), i.file_index()),
        size: i.file_size(),
        links: i.number_of_links().try_into()?,
        attributes: i.file_attributes().try_into()?,
        creation_time: file.metadata()?.creation_time(),
        last_write_time: i.last_write_time().ok_or("FILE_MTIME_UNAVAILABLE")?,
    })
}
fn open(path: &Path, directory: bool, security: &PrivateSecurity) -> Result<File> {
    let file = OpenOptions::new()
        .access_mode(if directory { 0x20080 } else { 0x80020000 })
        .share_mode(if directory { 3 } else { 1 })
        .custom_flags(0x02200000)
        .open(path)?;
    let i = info(&file)?;
    if i.attributes & 0x400 != 0 || (i.attributes & 0x10 != 0) != directory {
        return Err("REPARSE_OR_TYPE_REFUSED".into());
    }
    if !directory && i.links != 1 {
        return Err("MULTILINK_ARTIFACT_REFUSED".into());
    }
    security.check(&file)?;
    if !directory {
        native::check_streams(&file)?;
    }
    Ok(file)
}
fn bytes(file: &mut File, maximum: u64) -> Result<Vec<u8>> {
    if file.metadata()?.len() > maximum {
        return Err("ARTIFACT_SIZE_BOUND".into());
    }
    let mut bytes = Vec::new();
    file.take(maximum + 1).read_to_end(&mut bytes)?;
    if bytes.len() as u64 > maximum {
        return Err("ARTIFACT_SIZE_BOUND".into());
    }
    Ok(bytes)
}
fn observe(root: &Path) -> Result<Value> {
    let _ancestors = windows::ancestors(root.parent().ok_or("PARENT_MISSING")?)?;
    if native::filesystem(_ancestors.last().ok_or("PARENT_MISSING")?)? != "NTFS" {
        return Err("FILESYSTEM_UNVERIFIED".into());
    }
    let security = PrivateSecurity::current()?;
    let directory = open(root, true, &security)?;
    let actual_root = info(&directory)?;
    let mut present = Vec::new();
    for entry in fs::read_dir(root)?.take(17) {
        let name = entry?.file_name();
        let name = name.to_str().ok_or("UNEXPECTED_ROOT_ENTRY")?;
        if !NAMES.contains(&name) || present.len() >= 16 {
            return Err("UNEXPECTED_ROOT_ENTRY".into());
        }
        present.push(name.to_owned());
    }
    let mut records = Vec::new();
    let mut held = Vec::new();
    for (name, phase) in [
        ("prepared.record", "prepared"),
        ("intent.record", "publication-intent"),
        ("observation.record", "recovery-required"),
    ] {
        if present.iter().any(|v| v == name) {
            let mut file = open(&root.join(name), false, &security)?;
            let before = info(&file)?;
            let body = decode(&bytes(&mut file, MAX_RECORD)?, phase)?;
            if before != info(&file)? {
                return Err("RECORD_CHANGED_DURING_READ".into());
            }
            if body.root.identity != actual_root.identity
                || body.root.creation_time != actual_root.creation_time
                || body.root.attributes & 0x400 != 0
                || body.root.attributes & 0x10 == 0
            {
                return Err("RECORD_ROOT_BINDING_CONFLICT".into());
            }
            if let Some(previous) = records.first() {
                let previous: &Body = previous;
                if body.candidate != previous.candidate
                    || body.candidate_sha256 != previous.candidate_sha256
                {
                    return Err("RECORDS_DISAGREE".into());
                }
            }
            records.push(body);
            held.push(file);
        }
    }
    let has = |name: &str| present.iter().any(|v| v == name);
    if (has("intent.record") && !has("prepared.record"))
        || (has("observation.record") && !has("intent.record"))
    {
        return Err("RECORD_SEQUENCE_INVALID".into());
    }
    let mut matches = Vec::new();
    for name in ["candidate.bin", "output.bin"] {
        if has(name) {
            let mut file = open(&root.join(name), false, &security)?;
            let before = info(&file)?;
            let data = bytes(&mut file, 65536)?;
            let matching = records.first().is_some_and(|record| {
                before == record.candidate && digest(&data) == record.candidate_sha256
            });
            if before != info(&file)? {
                return Err("ARTIFACT_CHANGED_DURING_READ".into());
            }
            matches.push((name, matching));
            held.push(file);
        }
    }
    // These are held, bounded observations. Checksums and IDs neither create
    // repair authority nor make several independent opens an atomic snapshot.
    security.check(&directory)?;
    for file in &held {
        security.check(file)?;
        native::check_streams(file)?;
    }
    let candidate = has("candidate.bin");
    let output = has("output.bin");
    let matching = |name: &str| matches.iter().any(|(n, m)| *n == name && *m);
    let status = |name: &str| matches.iter().find(|(n, _)| *n == name).map(|(_, m)| *m);
    let outcome = classify(
        !records.is_empty(),
        has("intent.record"),
        status("candidate.bin"),
        status("output.bin"),
    );
    Ok(
        json!({"outcome":outcome,"recordCount":records.len(),"candidatePresent":candidate,"outputPresent":output,"matchingCandidate":matching("candidate.bin"),"matchingOutput":matching("output.bin")}),
    )
}
pub fn run(root: &Path) -> Result<()> {
    let mut report = match observe(root) {
        Ok(value) => value,
        Err(error) => {
            json!({"outcome":"uninspectable","diagnostic":error.to_string().chars().filter(|c| !c.is_control()).take(128).collect::<String>()})
        }
    };
    let fields = report.as_object_mut().ok_or("REPORT_TYPE")?;
    for key in [
        "committed",
        "productionPublicationAllowed",
        "repairAllowed",
        "cleanupAllowed",
        "namespaceAcknowledged",
    ] {
        fields.insert(key.into(), json!(false));
    }
    fields.insert("observationOnly".into(), json!(true));
    println!("{report}");
    std::io::stdout().flush()?;
    Ok(())
}
