use imageinfo::pairing::{MAX_DIRECTORY_ENTRIES, infer_same_stem};
use std::{
    collections::BTreeMap,
    fs,
    path::{Path, PathBuf},
    sync::atomic::{AtomicU64, Ordering},
};

struct Fixture(PathBuf);
impl Fixture {
    fn new() -> Self {
        static NEXT: AtomicU64 = AtomicU64::new(0);
        let path = std::env::temp_dir().join(format!(
            "imageinfo-inference-{}-{}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
        fs::create_dir(&path).unwrap();
        Self(path)
    }
    fn file(&self, name: &str) -> PathBuf {
        let path = self.0.join(name);
        fs::write(&path, b"authored equal bytes").unwrap();
        path
    }
    fn inventory(&self) -> BTreeMap<PathBuf, Option<Vec<u8>>> {
        fn visit(root: &Path, path: &Path, out: &mut BTreeMap<PathBuf, Option<Vec<u8>>>) {
            for entry in fs::read_dir(path).unwrap() {
                let path = entry.unwrap().path();
                let is_dir = fs::symlink_metadata(&path).unwrap().is_dir();
                out.insert(
                    path.strip_prefix(root).unwrap().to_path_buf(),
                    if is_dir {
                        None
                    } else {
                        Some(fs::read(&path).unwrap())
                    },
                );
                if is_dir {
                    visit(root, &path, out);
                }
            }
        }
        let mut result = BTreeMap::new();
        visit(&self.0, &self.0, &mut result);
        result
    }
    fn refuses(&self, raw: &Path, code: &str) {
        let before = self.inventory();
        assert_eq!(infer_same_stem(raw).unwrap_err().code, code);
        assert_eq!(self.inventory(), before);
    }
}
impl Drop for Fixture {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}

#[test]
fn unique_equal_byte_distinct_pair_retains_origins_and_neighbors() {
    let f = Fixture::new();
    let raw = f.file("Camera.CR3");
    let xmp = f.file("camera.XMP");
    f.file("other.nef");
    fs::create_dir(f.0.join("neighbors")).unwrap();
    f.file("neighbors/Camera.xmp");
    let before = f.inventory();
    let proposal = infer_same_stem(&raw).unwrap();
    assert_eq!(proposal.raw_origin, raw);
    assert_eq!(proposal.sidecar_origin, xmp);
    assert_eq!(proposal.pair.association, "inferred_same_stem");
    assert_eq!(proposal.rule, "ascii-cr3-xmp-v1");
    proposal.revalidate().unwrap();
    let json = serde_json::to_value(&proposal).unwrap();
    assert!(json.get("raw_identity").is_none());
    assert_eq!(f.inventory(), before);
}

#[test]
fn missing_does_not_search_other_directories_or_create() {
    let f = Fixture::new();
    let raw = f.file("camera.cr3");
    fs::create_dir(f.0.join("extra")).unwrap();
    f.file("extra/camera.xmp");
    f.file("other.xmp");
    f.refuses(&raw, "SIDECAR_MISSING");
}

#[test]
fn conflicting_extensions_and_same_stem_directories_refuse() {
    for conflict in ["camera.nef", "camera.cr2", "camera.txt", "camera"] {
        let f = Fixture::new();
        let raw = f.file("camera.cr3");
        f.file("camera.xmp");
        f.file(conflict);
        f.refuses(&raw, "PAIRING_INFERENCE_AMBIGUOUS");
    }
    let f = Fixture::new();
    let raw = f.file("camera.cr3");
    fs::create_dir(f.0.join("camera.xmp")).unwrap();
    f.refuses(&raw, "PAIRING_INFERENCE_AMBIGUOUS");
}

#[test]
fn stale_replacement_and_missing_are_explicit() {
    let f = Fixture::new();
    let raw = f.file("camera.cr3");
    let xmp = f.file("camera.xmp");
    let proposal = infer_same_stem(&raw).unwrap();
    fs::rename(&xmp, f.0.join("old.xmp")).unwrap();
    assert_eq!(
        proposal.revalidate().unwrap_err().code,
        "PAIRING_INFERENCE_STALE"
    );
    f.file("camera.xmp");
    let before = f.inventory();
    assert_eq!(
        proposal.revalidate().unwrap_err().code,
        "PAIRING_INFERENCE_STALE"
    );
    assert_eq!(f.inventory(), before);
}

#[test]
fn unsupported_names_and_directory_bound_refuse() {
    let f = Fixture::new();
    let raw = f.file("camera.cr3");
    f.file("camera.xmp");
    let unsupported = f.file("different.nef");
    f.refuses(&unsupported, "PAIRING_NAME_UNSUPPORTED");
    fs::remove_file(unsupported).unwrap();
    let unicode = f.file("café.txt");
    f.refuses(&raw, "PAIRING_NAME_UNSUPPORTED");
    fs::remove_file(unicode).unwrap();
    for i in 2..MAX_DIRECTORY_ENTRIES {
        f.file(&format!("neighbor-{i}"));
    }
    assert!(infer_same_stem(&raw).is_ok());
    f.file("overflow");
    f.refuses(&raw, "PAIRING_DIRECTORY_LIMIT");
}

#[test]
fn revalidation_keeps_content_edits_distinct_from_path_freshness() {
    let f = Fixture::new();
    let raw = f.file("camera.cr3");
    let xmp = f.file("camera.xmp");
    let proposal = infer_same_stem(&raw).unwrap();
    fs::write(&xmp, b"new in-place authored contents").unwrap();
    let before = f.inventory();
    proposal.revalidate().unwrap();
    assert_eq!(f.inventory(), before);
    f.file("camera.nef");
    let before = f.inventory();
    assert_eq!(
        proposal.revalidate().unwrap_err().code,
        "PAIRING_INFERENCE_AMBIGUOUS"
    );
    assert_eq!(f.inventory(), before);
}

#[test]
fn hard_link_alias_refuses_without_effects() {
    let f = Fixture::new();
    let raw = f.file("camera.cr3");
    fs::hard_link(&raw, f.0.join("camera.xmp")).unwrap();
    f.refuses(&raw, "PAIRING_SAME_FILE");
}

#[test]
fn case_behavior_requires_unique_observed_directory_entries() {
    let f = Fixture::new();
    let raw = f.file("camera.cr3");
    f.file("camera.xmp");
    f.file("CAMERA.XMP");
    let before = f.inventory();
    if before.len() == 3 {
        f.refuses(&raw, "PAIRING_INFERENCE_AMBIGUOUS");
    } else {
        assert_eq!(before.len(), 2);
        assert!(infer_same_stem(&raw).is_ok());
    }
    assert_eq!(f.inventory(), before);
}

#[cfg(unix)]
#[test]
fn symlink_candidates_cannot_redirect_selected_parent() {
    let f = Fixture::new();
    let raw = f.file("camera.cr3");
    let elsewhere = f.file("elsewhere.xmp");
    std::os::unix::fs::symlink(elsewhere, f.0.join("camera.xmp")).unwrap();
    f.refuses(&raw, "PAIRING_INFERENCE_AMBIGUOUS");
}

#[test]
fn cli_requires_opt_in_and_reports_proposal_without_effects() {
    let f = Fixture::new();
    let raw = f.file("camera.cr3");
    let xmp = f.file("camera.xmp");
    let before = f.inventory();
    let run = |args: &[&std::ffi::OsStr]| {
        std::process::Command::new(env!("CARGO_BIN_EXE_imageinfo"))
            .args(args)
            .output()
            .unwrap()
    };
    let implicit = run(&[
        "sidecar".as_ref(),
        "pair".as_ref(),
        raw.as_os_str(),
        "--output".as_ref(),
        "json".as_ref(),
    ]);
    assert_eq!(implicit.status.code(), Some(1));
    assert!(
        String::from_utf8(implicit.stdout)
            .unwrap()
            .contains("EXPLICIT_SIDECAR_REQUIRED")
    );
    let result = run(&[
        "sidecar".as_ref(),
        "pair".as_ref(),
        raw.as_os_str(),
        "--infer-same-stem".as_ref(),
        "--output".as_ref(),
        "json".as_ref(),
    ]);
    assert!(result.status.success());
    let json: serde_json::Value = serde_json::from_slice(&result.stdout).unwrap();
    assert_eq!(
        json["files"][0]["snapshot"]["kind"],
        "inferred-pair-preview"
    );
    assert_eq!(json["files"][0]["snapshot"]["mutationAllowed"], false);
    let conflict = run(&[
        "sidecar".as_ref(),
        "pair".as_ref(),
        raw.as_os_str(),
        "--infer-same-stem".as_ref(),
        "--sidecar".as_ref(),
        xmp.as_os_str(),
    ]);
    assert_eq!(conflict.status.code(), Some(2));
    assert_eq!(f.inventory(), before);
}
