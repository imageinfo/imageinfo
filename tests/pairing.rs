use imageinfo::pairing::{MAX_DIRECTORY_ENTRIES, resolve_pair};
use std::{
    fs,
    path::PathBuf,
    sync::atomic::{AtomicU64, Ordering},
};

struct Files(PathBuf);
impl Files {
    fn new() -> Self {
        static NEXT: AtomicU64 = AtomicU64::new(0);
        let path = std::env::temp_dir().join(format!(
            "imageinfo-pairing-{}-{}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
        fs::create_dir(&path).unwrap();
        Self(path)
    }
    fn file(&self, name: &str) -> PathBuf {
        let path = self.0.join(name);
        fs::write(&path, name.as_bytes()).unwrap();
        path
    }
}
impl Drop for Files {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}

#[test]
fn explicit_selection_accepts_different_stems_and_directories_without_effects() {
    let files = Files::new();
    let raw = files.file("camera.CR3");
    let inferred = files.file("camera.xmp");
    fs::create_dir(files.0.join("chosen")).unwrap();
    let sidecar = files.file("chosen/custom.xmp");
    let unrelated = files.file("camera.nef");
    let result = resolve_pair(&raw, Some(&sidecar)).unwrap();
    assert_eq!(result.raw_path, fs::canonicalize(&raw).unwrap());
    assert_eq!(result.sidecar_path, fs::canonicalize(&sidecar).unwrap());
    assert_eq!(result.association, "explicit_paths");
    for (path, bytes) in [
        (&raw, b"camera.CR3".as_slice()),
        (&inferred, b"camera.xmp"),
        (&sidecar, b"chosen/custom.xmp"),
        (&unrelated, b"camera.nef"),
    ] {
        assert_eq!(fs::read(path).unwrap(), bytes);
    }
    assert_eq!(fs::read_dir(&files.0).unwrap().count(), 4);
}

#[test]
fn matching_basename_never_infers_association() {
    let files = Files::new();
    let raw = files.file("camera.CR3");
    files.file("camera.xmp");
    assert_eq!(
        resolve_pair(&raw, None).unwrap_err().code,
        "EXPLICIT_SIDECAR_REQUIRED"
    );
}

#[test]
fn missing_selected_sidecar_is_not_created_or_replaced_by_neighbor() {
    let files = Files::new();
    let raw = files.file("camera.CR3");
    files.file("camera.xmp");
    let absent = files.0.join("absent.xmp");
    assert_eq!(
        resolve_pair(&raw, Some(&absent)).unwrap_err().code,
        "SIDECAR_MISSING"
    );
    assert!(!absent.exists());
    assert_eq!(fs::read_dir(&files.0).unwrap().count(), 2);
}

#[test]
fn same_path_and_lexical_alias_refuse() {
    let files = Files::new();
    let raw = files.file("camera.CR3");
    for alias in [raw.clone(), files.0.join(".").join("camera.CR3")] {
        assert_eq!(
            resolve_pair(&raw, Some(&alias)).unwrap_err().code,
            "PAIRING_SAME_FILE"
        );
    }
}

#[test]
fn hard_link_alias_refuses_while_distinct_equal_bytes_are_allowed() {
    let files = Files::new();
    let raw = files.file("camera.CR3");
    let alias = files.0.join("alias.xmp");
    fs::hard_link(&raw, &alias).unwrap();
    assert_eq!(
        resolve_pair(&raw, Some(&alias)).unwrap_err().code,
        "PAIRING_SAME_FILE"
    );
    let distinct = files.file("distinct.xmp");
    fs::write(&distinct, fs::read(&raw).unwrap()).unwrap();
    assert!(resolve_pair(&raw, Some(&distinct)).is_ok());
}

#[test]
fn directories_and_non_ascii_selected_leaf_refuse() {
    let files = Files::new();
    let raw = files.file("camera.CR3");
    assert_eq!(
        resolve_pair(&raw, Some(&files.0)).unwrap_err().code,
        "PAIRING_NOT_FILE"
    );
    let sidecar = files.file("caf\u{e9}.xmp");
    assert_eq!(
        resolve_pair(&raw, Some(&sidecar)).unwrap_err().code,
        "PAIRING_NAME_UNSUPPORTED"
    );
}

#[test]
fn directory_scan_bound_refuses_before_pairing() {
    let files = Files::new();
    let raw = files.file("camera.CR3");
    let sidecar = files.file("chosen.xmp");
    for index in 0..MAX_DIRECTORY_ENTRIES - 2 {
        files.file(&format!("other-{index}"));
    }
    assert!(resolve_pair(&raw, Some(&sidecar)).is_ok());
    files.file("beyond-limit");
    assert_eq!(
        resolve_pair(&raw, Some(&sidecar)).unwrap_err().code,
        "PAIRING_DIRECTORY_LIMIT"
    );
    assert_eq!(fs::read(&raw).unwrap(), b"camera.CR3");
    assert_eq!(fs::read(&sidecar).unwrap(), b"chosen.xmp");
}

#[cfg(unix)]
#[test]
fn unix_symlink_alias_and_case_collision_refuse() {
    use std::os::unix::fs::symlink;
    let files = Files::new();
    let raw = files.file("camera.CR3");
    let alias = files.0.join("alias.xmp");
    symlink(&raw, &alias).unwrap();
    assert_eq!(
        resolve_pair(&raw, Some(&alias)).unwrap_err().code,
        "PAIRING_SAME_FILE"
    );
    let sidecar = files.file("camera.xmp");
    files.file("CAMERA.XMP");
    assert_eq!(
        resolve_pair(&raw, Some(&sidecar)).unwrap_err().code,
        "PAIRING_CASE_AMBIGUITY"
    );
}

#[cfg(windows)]
#[test]
fn windows_case_alias_refuses() {
    let files = Files::new();
    let raw = files.file("camera.CR3");
    assert_eq!(
        resolve_pair(&raw, Some(&files.0.join("CAMERA.CR3")))
            .unwrap_err()
            .code,
        "PAIRING_SAME_FILE"
    );
}
