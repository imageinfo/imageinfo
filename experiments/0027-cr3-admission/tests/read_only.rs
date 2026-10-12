#[allow(dead_code)]
#[path = "../../../tests/support/mod.rs"]
mod support;
use std::{fs, process::Command};

#[test]
fn executable_reports_refusal_and_retains_all_existing_source_and_directory_bytes() {
    let root = support::TempDir::new();
    let path = root.path.join("camera with spaces.cr3");
    let bytes = support::fixture_with_previews(
        "Firmware Version 2.2.1",
        vec![0xff, 0xd8, 0xff, 0xd9],
        vec![0xff, 0xd8, 0xff, 0xd9],
        vec![0xff, 0xd8, 0xff, 0xd9],
    )
    .bytes;
    fs::write(&path, &bytes).unwrap();
    let mtime = fs::metadata(&path).unwrap().modified().unwrap();
    for extra in [vec![], vec!["1"]] {
        let result = Command::new(env!("CARGO_BIN_EXE_imageinfo-cr3-admission-probe"))
            .args(["inspect"])
            .arg(&path)
            .arg("2026:01:02 03:04:05")
            .args(extra)
            .output()
            .unwrap();
        assert!(
            result.status.success(),
            "{}",
            String::from_utf8_lossy(&result.stderr)
        );
        let report: serde_json::Value = serde_json::from_slice(&result.stdout).unwrap();
        assert_eq!(report["productionMutationAllowed"], false);
        assert_eq!(report["artifactsCreated"], false);
        assert_eq!(report["generalAuthenticityAbsenceEstablished"], false);
        assert_eq!(fs::read(&path).unwrap(), bytes);
        assert_eq!(fs::metadata(&path).unwrap().modified().unwrap(), mtime);
        assert_eq!(fs::read_dir(&root.path).unwrap().count(), 1);
    }
}

#[test]
fn invalid_request_is_bounded_and_never_opens_or_creates_an_input() {
    let root = support::TempDir::new();
    let path = root.path.join("missing.cr3");
    for date in [
        "1900:02:29 00:00:00",
        "2026:01:01 00:00:60",
        "2026:01:01 00:00:00\n",
    ] {
        let result = Command::new(env!("CARGO_BIN_EXE_imageinfo-cr3-admission-probe"))
            .arg("inspect")
            .arg(&path)
            .arg(date)
            .output()
            .unwrap();
        assert_eq!(result.status.code(), Some(2));
        let report: serde_json::Value = serde_json::from_slice(&result.stderr).unwrap();
        assert!(
            report["issue"]
                .as_str()
                .unwrap()
                .starts_with("INVALID_DATE")
        );
        assert_eq!(report["productionMutationAllowed"], false);
        assert!(result.stderr.len() < 512 && result.stdout.is_empty());
        assert_eq!(fs::read_dir(&root.path).unwrap().count(), 0);
    }
}
