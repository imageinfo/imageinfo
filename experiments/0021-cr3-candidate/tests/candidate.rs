// Reuse imageinfo's independently authored structural bytes, never camera media.
#[allow(dead_code)]
#[path = "../../../tests/support/mod.rs"]
mod support;
use std::{fs, process::Command};

fn invoke(source: &std::path::Path, target: &std::path::Path) -> std::process::Output {
    Command::new(env!("CARGO_BIN_EXE_imageinfo-cr3-candidate-probe"))
        .arg("stage")
        .arg(source)
        .arg(target)
        .output()
        .unwrap()
}

#[test]
fn actual_candidate_reread_collision_and_noop_preserve_inputs() {
    let dir = support::TempDir::new();
    let fixture = support::fixture();
    let source = dir.path.join("authored.cr3");
    let target = dir.path.join("private.candidate.cr3");
    fs::write(&source, &fixture.bytes).unwrap();
    let result = invoke(&source, &target);
    assert!(
        result.status.success(),
        "{}",
        String::from_utf8_lossy(&result.stderr)
    );
    let report: serde_json::Value = serde_json::from_slice(&result.stdout).unwrap();
    assert_eq!(report["published"], false);
    let offset = report["patch"]["offset"].as_u64().unwrap() as usize;
    let candidate = fs::read(&target).unwrap();
    let mut expected = fixture.bytes.clone();
    expected[offset..offset + 20].copy_from_slice(b"2001:02:03 04:05:06\0");
    assert_eq!(candidate, expected);
    assert_eq!(fs::read(&source).unwrap(), fixture.bytes);
    assert!(!invoke(&source, &target).status.success());
    assert_eq!(fs::read(&target).unwrap(), expected);
    let noop = dir.path.join("no-op.candidate.cr3");
    let result = invoke(&target, &noop);
    assert!(result.status.success());
    assert!(!noop.exists());
    assert_eq!(
        serde_json::from_slice::<serde_json::Value>(&result.stdout).unwrap()["outcome"],
        "unchanged"
    );
}

#[test]
fn malformed_unsupported_and_unsafe_names_refuse_before_creation() {
    let dir = support::TempDir::new();
    let source = dir.path.join("source.cr3");
    let target = dir.path.join("private.candidate.cr3");
    for bytes in [vec![], vec![0; 7], {
        let mut bytes = support::fixture().bytes;
        let quality = support::field_offset(&bytes, b"CMT3", 1) + 6;
        bytes[quality..quality + 2].copy_from_slice(&3u16.to_le_bytes());
        bytes
    }] {
        fs::write(&source, &bytes).unwrap();
        assert!(!invoke(&source, &target).status.success());
        assert_eq!(fs::read(&source).unwrap(), bytes);
        assert!(!target.exists());
    }
    fs::write(&source, support::fixture().bytes).unwrap();
    let wrong_name = dir.path.join("ordinary-output.cr3");
    assert!(!invoke(&source, &wrong_name).status.success());
    assert!(!wrong_name.exists());
    assert!(!invoke(&source, &source).status.success());
}

#[test]
fn big_endian_storage_is_not_rewritten_or_relocated() {
    let dir = support::TempDir::new();
    let mut bytes = support::fixture().bytes;
    support::big_endian_tiff_boxes(&mut bytes);
    let source = dir.path.join("big-endian.cr3");
    let target = dir.path.join("big-endian.candidate.cr3");
    fs::write(&source, &bytes).unwrap();
    let result = invoke(&source, &target);
    assert!(
        result.status.success(),
        "{}",
        String::from_utf8_lossy(&result.stderr)
    );
    let report: serde_json::Value = serde_json::from_slice(&result.stdout).unwrap();
    let offset = report["patch"]["offset"].as_u64().unwrap() as usize;
    let mut expected = bytes.clone();
    expected[offset..offset + 20].copy_from_slice(b"2001:02:03 04:05:06\0");
    assert_eq!(fs::read(&target).unwrap(), expected);
    assert_eq!(fs::read(&source).unwrap(), bytes);
}
