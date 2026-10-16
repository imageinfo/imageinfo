#![cfg(windows)]
use imageinfo_windows_storage::{GuardedSource, PrivateRoot};
use std::{
    fs::{self, OpenOptions},
    io::Write,
    os::windows::fs::OpenOptionsExt,
    path::PathBuf,
    sync::atomic::{AtomicU64, Ordering},
};

static NEXT: AtomicU64 = AtomicU64::new(0);
fn fixture(name: &str) -> PathBuf {
    let path = std::env::current_dir()
        .unwrap()
        .join(".local")
        .join("native-166")
        .join(format!(
            "{}-{}-{}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed),
            name
        ));
    fs::create_dir_all(&path).unwrap();
    path
}

#[test]
fn actual_owned_handles_no_clobber_source_preservation_and_owner_editing() {
    let base = fixture("normal");
    let source = base.join("source.bin");
    fs::write(&source, b"authored source").unwrap();
    let before = fs::metadata(&source).unwrap().modified().unwrap();
    let mut held_source = GuardedSource::open(&source, 1024).unwrap();
    let source_snapshot = held_source.snapshot().clone();
    assert!(OpenOptions::new().write(true).open(&source).is_err());
    assert!(fs::rename(&source, base.join("stolen.bin")).is_err());
    let root_path = base.join("transaction");
    let root = PrivateRoot::create(&root_path).unwrap();
    assert!(PrivateRoot::create(&root_path).is_err());
    let mut artifact = root
        .create_artifact("candidate.bin", b"complete authored candidate", 1024)
        .unwrap();
    let snapshot = artifact.snapshot().clone();
    assert!(
        OpenOptions::new()
            .write(true)
            .open(root_path.join("candidate.bin"))
            .is_err()
    );
    assert!(fs::rename(&root_path, base.join("moved-root")).is_err());
    assert!(fs::rename(&base, base.with_extension("moved")).is_err());
    artifact.flush().unwrap();
    root.flush().unwrap();
    root.flush_parent().unwrap();
    artifact.publish_no_replace(&root, "output.bin").unwrap();
    artifact.check(&root).unwrap();
    assert_eq!(artifact.snapshot(), &snapshot);
    assert!(artifact.publication_attempted());
    assert!(artifact.publish_no_replace(&root, "second.bin").is_err());
    held_source.check().unwrap();
    assert_eq!(held_source.snapshot(), &source_snapshot);
    assert_eq!(held_source.read_exact_bytes().unwrap(), b"authored source");
    drop(artifact);
    drop(root);
    drop(held_source);
    // Independent pathname reads after handles close audit retained artifacts.
    assert!(!root_path.join("candidate.bin").exists());
    assert_eq!(
        fs::read(root_path.join("output.bin")).unwrap(),
        b"complete authored candidate"
    );
    assert_eq!(fs::read(&source).unwrap(), b"authored source");
    assert_eq!(fs::metadata(&source).unwrap().modified().unwrap(), before);
    fs::write(root_path.join("output.bin"), b"ordinary owner edit").unwrap();
    assert_eq!(
        fs::read(root_path.join("output.bin")).unwrap(),
        b"ordinary owner edit"
    );
}

#[test]
fn occupied_case_winner_alias_and_property_conflicts_retain_objects() {
    let base = fixture("conflicts");
    let root = PrivateRoot::create(&base.join("transaction")).unwrap();
    let mut artifact = root
        .create_artifact("candidate.bin", b"candidate", 1024)
        .unwrap();
    fs::write(root.path().join("OUTPUT.bin"), b"foreign winner").unwrap();
    assert!(artifact.publish_no_replace(&root, "output.bin").is_err());
    assert!(artifact.publication_attempted());
    drop(artifact);
    assert_eq!(
        fs::read(root.path().join("OUTPUT.bin")).unwrap(),
        b"foreign winner"
    );
    assert_eq!(
        fs::read(root.path().join("candidate.bin")).unwrap(),
        b"candidate"
    );
    let mut linked = root.create_artifact("linked.bin", b"linked", 1024).unwrap();
    fs::hard_link(
        root.path().join("linked.bin"),
        root.path().join("alias.bin"),
    )
    .unwrap();
    assert!(linked.check(&root).is_err());
    drop(linked);
    assert_eq!(fs::read(root.path().join("alias.bin")).unwrap(), b"linked");
    let mut properties = root
        .create_artifact("properties.bin", b"properties", 1024)
        .unwrap();
    let mut permissions = fs::metadata(root.path().join("properties.bin"))
        .unwrap()
        .permissions();
    permissions.set_readonly(true);
    fs::set_permissions(root.path().join("properties.bin"), permissions).unwrap();
    assert!(properties.check(&root).is_err());
    drop(properties);
    assert_eq!(
        fs::read(root.path().join("properties.bin")).unwrap(),
        b"properties"
    );
}

#[test]
fn acquisition_refuses_writable_handle_alias_stream_and_oversize_without_root_effects() {
    let base = fixture("refusals");
    let source = base.join("source.bin");
    fs::write(&source, b"original").unwrap();
    let writer = OpenOptions::new()
        .write(true)
        .share_mode(7)
        .open(&source)
        .unwrap();
    assert!(GuardedSource::open(&source, 1024).is_err());
    drop(writer);
    assert!(GuardedSource::open(&base.join("SOURCE.bin"), 1024).is_err());
    assert!(GuardedSource::open(&source, 1).is_err());
    fs::hard_link(&source, base.join("alias.bin")).unwrap();
    assert!(GuardedSource::open(&source, 1024).is_err());
    let other = base.join("other.bin");
    fs::write(&other, b"other").unwrap();
    let mut ads = OpenOptions::new()
        .create_new(true)
        .write(true)
        .open(base.join("other.bin:extra"))
        .unwrap();
    ads.write_all(b"authored ads").unwrap();
    drop(ads);
    assert!(GuardedSource::open(&other, 1024).is_err());
    assert!(!base.join("transaction").exists());
    assert_eq!(fs::read(source).unwrap(), b"original");
}

#[test]
fn property_conflict_is_terminal_after_owner_reversion_and_root_ads_is_detected() {
    let base = fixture("property-boundaries");
    let root = PrivateRoot::create(&base.join("transaction")).unwrap();
    assert!(root.create_artifact("over.bin", b"over", 1).is_err());
    assert!(!root.path().join("over.bin").exists());
    let mut artifact = root.create_artifact("time.bin", b"time", 1024).unwrap();
    let actor = OpenOptions::new()
        .access_mode(0x100)
        .share_mode(7)
        .open(root.path().join("time.bin"))
        .unwrap();
    let original = actor.metadata().unwrap().modified().unwrap();
    actor
        .set_times(fs::FileTimes::new().set_modified(std::time::SystemTime::UNIX_EPOCH))
        .unwrap();
    assert!(artifact.check(&root).is_err());
    actor
        .set_times(fs::FileTimes::new().set_modified(original))
        .unwrap();
    assert!(artifact.check(&root).is_err());
    assert!(artifact.publish_no_replace(&root, "output.bin").is_err());
    assert!(!artifact.publication_attempted());
    drop(actor);
    drop(artifact);
    let mut ads_path = root.path().as_os_str().to_os_string();
    ads_path.push(":authored-actor");
    let ads_file = OpenOptions::new()
        .write(true)
        .create_new(true)
        .share_mode(7)
        .open(PathBuf::from(ads_path))
        .unwrap();
    drop(ads_file);
    assert!(root.check().is_err());
    assert_eq!(fs::read(root.path().join("time.bin")).unwrap(), b"time");
}

#[test]
fn junction_parent_is_refused_without_creating_transaction() {
    let base = fixture("junction");
    let real = base.join("real");
    fs::create_dir(&real).unwrap();
    let junction = base.join("junction");
    let result = std::process::Command::new("cmd.exe")
        .args(["/C", "mklink", "/J"])
        .arg(&junction)
        .arg(&real)
        .output()
        .unwrap();
    assert!(result.status.success(), "authored junction creation failed");
    assert!(PrivateRoot::create(&junction.join("transaction")).is_err());
    assert!(!real.join("transaction").exists());
    assert!(junction.exists());
}
