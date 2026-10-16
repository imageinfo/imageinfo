//! Retained authored native cases. Never use these helpers with real media.
#![cfg(windows)]
use imageinfo_windows_storage::{
    ExistingMoveOutcome as Outcome, FileSnapshot, GuardedSource, HeldExistingMove, PrivateRoot,
};
use std::{
    fs::{self, FileTimes, OpenOptions},
    os::windows::fs::OpenOptionsExt,
    path::{Path, PathBuf},
    time::{Duration, SystemTime, UNIX_EPOCH},
};

fn fixture(label: &str) -> PathBuf {
    let base = std::env::var_os("IMAGEINFO_EXISTING_MOVE_EVIDENCE_ROOT")
        .map(PathBuf::from)
        .unwrap_or_else(|| {
            std::env::current_dir()
                .unwrap()
                .join(".local")
                .join("native-195")
        });
    let nonce = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    let root = base.join(format!("{label}-{}-{nonce}", std::process::id()));
    fs::create_dir_all(&base).unwrap();
    let private = PrivateRoot::create(&root).unwrap();
    let authored = private
        .create_artifact("source.bin", b"authored existing-object marker\n", 1024)
        .unwrap();
    // End creator custody before acquiring the existing object under test.
    drop(authored);
    drop(private);
    fs::write(
        root.join("initial-observation.private.txt"),
        format!("{:?}\n", snapshot(&root.join("source.bin"))),
    )
    .unwrap();
    root
}
fn snapshot(path: &Path) -> FileSnapshot {
    GuardedSource::open(path, 1024).unwrap().snapshot().clone()
}
fn retain_winner(root: &Path, observed: &FileSnapshot, bytes: Option<&[u8]>) {
    fs::write(
        root.join("winner-initial-observation.private.txt"),
        format!("{observed:?}\n"),
    )
    .unwrap();
    if let Some(bytes) = bytes {
        fs::write(root.join("winner-initial.private.bin"), bytes).unwrap();
    }
}
fn prepare(root: &Path) -> HeldExistingMove {
    let source = root.join("source.bin");
    HeldExistingMove::open(&source, &root.join("destination.bin"), &snapshot(&source)).unwrap()
}
fn moved(root: &Path, expected: &FileSnapshot) {
    assert!(!root.join("source.bin").exists());
    let actual = snapshot(&root.join("destination.bin"));
    assert_eq!(actual.volume_serial_number, expected.volume_serial_number);
    assert_eq!(actual.file_index, expected.file_index);
    assert_eq!(actual.creation_time, expected.creation_time);
    assert_eq!(actual.last_write_time, expected.last_write_time);
    assert_eq!(actual.attributes, expected.attributes);
    assert_eq!(actual.owner_dacl, expected.owner_dacl);
    assert_eq!(
        fs::read(root.join("destination.bin")).unwrap(),
        b"authored existing-object marker\n"
    );
}

#[test]
fn native_01_normal_same_object_move() {
    let root = fixture("01-normal");
    let mut operation = prepare(&root);
    let before = operation.snapshot().clone();
    assert_eq!(operation.execute(false), Outcome::ObservedMoved);
    drop(operation);
    moved(&root, &before);
}
#[test]
fn native_02_foreign_collision() {
    let root = fixture("02-foreign-collision");
    fs::write(root.join("destination.bin"), b"foreign winner\n").unwrap();
    let winner = snapshot(&root.join("destination.bin"));
    retain_winner(&root, &winner, Some(b"foreign winner\n"));
    let mut operation = prepare(&root);
    assert_eq!(operation.execute(false), Outcome::ObservedNoEffect);
    drop(operation);
    assert_eq!(snapshot(&root.join("destination.bin")), winner);
    assert_eq!(
        fs::read(root.join("destination.bin")).unwrap(),
        b"foreign winner\n"
    );
    assert!(root.join("source.bin").exists());
}
#[test]
fn native_03_same_bytes_different_object_collision() {
    let root = fixture("03-same-bytes-collision");
    fs::copy(root.join("source.bin"), root.join("destination.bin")).unwrap();
    let winner = snapshot(&root.join("destination.bin"));
    retain_winner(&root, &winner, Some(b"authored existing-object marker\n"));
    let mut operation = prepare(&root);
    assert_ne!(winner.file_index, operation.snapshot().file_index);
    assert_eq!(operation.execute(false), Outcome::ObservedNoEffect);
    drop(operation);
    assert_eq!(snapshot(&root.join("destination.bin")), winner);
    assert!(root.join("source.bin").exists());
}
#[test]
fn native_04_directory_collision() {
    let root = fixture("04-directory-collision");
    let directory = PrivateRoot::create(&root.join("destination.bin")).unwrap();
    retain_winner(&root, directory.snapshot(), None);
    drop(directory);
    let mut operation = prepare(&root);
    assert_eq!(operation.execute(false), Outcome::ObservedNoEffect);
    drop(operation);
    assert!(root.join("destination.bin").is_dir());
    assert!(root.join("source.bin").is_file());
}
#[test]
fn native_05_initial_source_alias_refuses() {
    let root = fixture("05-source-alias");
    let expected = snapshot(&root.join("source.bin"));
    fs::hard_link(root.join("source.bin"), root.join("alias.bin")).unwrap();
    assert!(
        HeldExistingMove::open(
            &root.join("source.bin"),
            &root.join("destination.bin"),
            &expected
        )
        .is_err()
    );
    assert!(root.join("source.bin").exists());
    assert!(!root.join("destination.bin").exists());
}
#[test]
fn native_06_preopened_writer_refuses() {
    let root = fixture("06-preopened-writer");
    let expected = snapshot(&root.join("source.bin"));
    let actor = OpenOptions::new()
        .write(true)
        .share_mode(7)
        .open(root.join("source.bin"))
        .unwrap();
    assert!(
        HeldExistingMove::open(
            &root.join("source.bin"),
            &root.join("destination.bin"),
            &expected
        )
        .is_err()
    );
    drop(actor);
    assert!(root.join("source.bin").exists());
    assert!(!root.join("destination.bin").exists());
}
#[test]
fn native_07_preopened_rename_handle_refuses() {
    let root = fixture("07-preopened-rename");
    let expected = snapshot(&root.join("source.bin"));
    let actor = OpenOptions::new()
        .access_mode(0x0001_0000)
        .share_mode(7)
        .open(root.join("source.bin"))
        .unwrap();
    assert!(
        HeldExistingMove::open(
            &root.join("source.bin"),
            &root.join("destination.bin"),
            &expected
        )
        .is_err()
    );
    drop(actor);
    assert!(root.join("source.bin").exists());
    assert!(!root.join("destination.bin").exists());
}
#[test]
fn native_08_source_substitution_refuses_actor() {
    let root = fixture("08-source-substitution");
    let mut operation = prepare(&root);
    let before = operation.snapshot().clone();
    assert!(fs::rename(root.join("source.bin"), root.join("actor-moved.bin")).is_err());
    assert!(fs::write(root.join("source.bin"), b"foreign substitution\n").is_err());
    assert_eq!(operation.execute(false), Outcome::ObservedMoved);
    drop(operation);
    moved(&root, &before);
}
#[test]
fn native_09_parent_move_refuses_actor() {
    let root = fixture("09-parent-move");
    let mut operation = prepare(&root);
    let before = operation.snapshot().clone();
    assert!(fs::rename(&root, root.with_extension("actor-moved")).is_err());
    assert_eq!(operation.execute(false), Outcome::ObservedMoved);
    drop(operation);
    moved(&root, &before);
}
#[test]
fn native_10_preopened_property_edit_is_retained() {
    let root = fixture("10-property-edit");
    let path = root.join("source.bin");
    let actor = OpenOptions::new()
        .access_mode(0x100)
        .share_mode(7)
        .open(&path)
        .unwrap();
    let mut operation = prepare(&root);
    let mut before = operation.snapshot().clone();
    let changed = UNIX_EPOCH + Duration::from_secs(1_500_000_000);
    actor
        .set_times(FileTimes::new().set_modified(changed))
        .unwrap();
    before.last_write_time = winapi_util::file::information(&actor)
        .unwrap()
        .last_write_time()
        .unwrap();
    assert_ne!(before.last_write_time, operation.snapshot().last_write_time);
    fs::write(
        root.join("expected-after-actor.private.txt"),
        format!("{before:?}\n"),
    )
    .unwrap();
    assert_eq!(operation.execute(false), Outcome::ObservedMoved);
    drop(operation);
    drop(actor);
    moved(&root, &before);
}
#[test]
fn native_11_cancel_before_call_has_no_effect() {
    let root = fixture("11-cancel");
    let mut operation = prepare(&root);
    let before = operation.snapshot().clone();
    assert_eq!(operation.execute(true), Outcome::NotAttempted);
    assert!(!operation.attempted());
    drop(operation);
    assert_eq!(snapshot(&root.join("source.bin")), before);
    assert!(!root.join("destination.bin").exists());
}
#[test]
fn native_12_lost_response_inspects_without_replay() {
    let root = fixture("12-lost-response");
    let mut operation = prepare(&root);
    let before = operation.snapshot().clone();
    let _discarded_response = operation.execute(false);
    assert!(operation.attempted());
    assert_eq!(operation.inspect(), Outcome::ObservedMoved);
    // A second execution only inspects; it never retries the old source name.
    assert_eq!(operation.execute(false), Outcome::ObservedMoved);
    // An independent winner at the released old name is retained. Its presence
    // makes the complete requested name map uncertain, never a rollback target.
    fs::write(root.join("source.bin"), b"foreign old-name winner\n").unwrap();
    retain_winner(
        &root,
        &snapshot(&root.join("source.bin")),
        Some(b"foreign old-name winner\n"),
    );
    assert_eq!(operation.inspect(), Outcome::RecoveryRequired);
    assert_eq!(operation.execute(false), Outcome::RecoveryRequired);
    drop(operation);
    let installed = snapshot(&root.join("destination.bin"));
    assert_eq!(installed, before);
    assert_eq!(
        fs::read(root.join("destination.bin")).unwrap(),
        b"authored existing-object marker\n"
    );
    assert_eq!(
        fs::read(root.join("source.bin")).unwrap(),
        b"foreign old-name winner\n"
    );
}
