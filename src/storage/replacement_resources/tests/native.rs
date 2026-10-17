//! Explicit opt-in helper. Only the guest script's fresh 128 MiB authored
//! secondary-volume fixture may select this test; normal tests never fill disks.
use super::*;
use crate::storage::windows::WindowsBackend;
use sha2::{Digest, Sha256};
use std::{fs, io::Write, path::PathBuf};

#[test]
#[ignore = "requires independently checked fresh disposable 128 MiB guest volume"]
fn guest_bounded_storage_full_refusal() {
    let drive =
        PathBuf::from(std::env::var_os("IMAGEINFO_197_DRIVE").expect("explicit guest fixture"));
    assert_eq!(drive.components().count(), 2);
    assert_ne!(
        drive.to_string_lossy()[..2].to_ascii_lowercase(),
        std::env::var("SystemDrive").unwrap().to_ascii_lowercase()
    );
    assert_eq!(
        fs::read(drive.join("fixture197.marker")).unwrap(),
        b"imageinfo-0197-fresh-authored-128m-v1\n"
    );
    let source = drive.join("source.bin");
    let original = drive.join("original.bin");
    let before_source = fs::read(&source).unwrap();
    let before_original = fs::read(&original).unwrap();
    assert_eq!(before_source.len(), 4096);
    assert_eq!(before_original.len(), 4096);
    let root = drive.join("operation197");
    assert!(!root.exists());
    let backend = WindowsBackend::new(&source, &root);
    let available_before = backend.available_bytes().unwrap();
    assert!(available_before > 64 * 1024 * 1024);
    let filler = drive.join("bounded-fill197.bin");
    let mut file = fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&filler)
        .unwrap();
    let chunk = [0x37; 65536];
    let mut written = 0u64;
    let failure = loop {
        assert!(
            written < 128 * 1024 * 1024,
            "bounded volume did not become full"
        );
        match file.write_all(&chunk) {
            Ok(()) => written += chunk.len() as u64,
            Err(error) => break error,
        }
    };
    assert_eq!(failure.raw_os_error(), Some(112));
    drop(file);
    let available_full = backend.available_bytes().unwrap();
    let streams = [Some(64)];
    let plan = Plan::build(
        &[Member::Replace {
            candidate: FileBytes {
                default: Some(64 * 1024 * 1024),
                streams: Streams::Complete(&streams),
            },
            original_recovery: bytes(4096),
        }],
        BackupChoice::NoBackup,
    )
    .unwrap();
    assert!(available_full < plan.precommit_bytes);
    let mut session =
        RetainedSession::start(charge(&plan) * 2, KnownOperations::Complete(&[])).unwrap();
    for name in ["full-first", "full-retry"] {
        assert_eq!(
            plan.attempt(
                &mut session,
                key(name),
                &Cancellation::default(),
                || backend.available_bytes(),
                || -> Result<(), Failure> { panic!("storage full must refuse before effects") }
            ),
            Err(Failure::StorageUnavailable)
        );
        assert!(!root.exists());
    }
    assert_eq!(session.charged(), charge(&plan) * 2);
    assert_eq!(fs::read(&source).unwrap(), before_source);
    assert_eq!(fs::read(&original).unwrap(), before_original);
    println!(
        "IMAGEINFO197 {{\"schema\":\"imageinfo-0197-full-v1\",\"windowsError\":112,\"availableBefore\":{available_before},\"availableFull\":{available_full},\"fillerCompleteBytes\":{written},\"retainedCharge\":{},\"planCharge\":{},\"sourceSha256\":\"{:x}\",\"originalSha256\":\"{:x}\",\"attempts\":2,\"constructorCalls\":0,\"operationRootAbsent\":true,\"publicationPossible\":false}}",
        session.charged(),
        charge(&plan),
        Sha256::digest(&before_source),
        Sha256::digest(&before_original)
    );
}
