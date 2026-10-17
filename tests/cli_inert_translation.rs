//! Actual executable cases: stdin data never becomes a native media request.
#[allow(dead_code)]
mod support;
use serde_json::{Value, json};
use std::{
    fs,
    io::Write,
    process::{Command, Stdio},
};
fn invoke(bytes: &[u8], cwd: &std::path::Path) -> std::process::Output {
    let mut child = Command::new(env!("CARGO_BIN_EXE_imageinfo"))
        .args(["compat", "translate"])
        .current_dir(cwd)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    let mut stdin = child.stdin.take().unwrap();
    let data = bytes.to_vec();
    let writer = std::thread::spawn(move || {
        let _ = stdin.write_all(&data);
    });
    let result = child.wait_with_output().unwrap();
    writer.join().unwrap();
    result
}
#[test]
fn all_twelve_cli_reports_match_frozen_vectors_and_leave_artifacts_untouched() {
    let dir = support::TempDir::new();
    for name in [
        "photo.cr3",
        "photo.xmp",
        "source.cr3",
        "target.cr3",
        "edits.json",
        "custom.config",
        "args.txt",
    ] {
        fs::write(
            dir.path.join(name),
            b"authored inert sentinel, not valid media/config",
        )
        .unwrap();
    }
    let mut before = fs::read_dir(&dir.path)
        .unwrap()
        .map(|x| x.unwrap().file_name())
        .collect::<Vec<_>>();
    before.sort();
    let vectors: Value = serde_json::from_str(include_str!(
        "../docs/legacy-compatibility/inert-translation/vectors.v1.json"
    ))
    .unwrap();
    for case in vectors["reports"].as_array().unwrap().iter().take(12) {
        let result = invoke(
            &serde_json::to_vec(&case["report"]["request"]).unwrap(),
            &dir.path,
        );
        assert_eq!(
            result.status.code(),
            case["report"]["exitStatus"].as_i64().map(|s| s as i32)
        );
        assert!(result.stderr.is_empty());
        let report: Value = serde_json::from_slice(&result.stdout).unwrap();
        assert_eq!(report, case["report"]);
    }
    let mut after = fs::read_dir(&dir.path)
        .unwrap()
        .map(|x| x.unwrap().file_name())
        .collect::<Vec<_>>();
    after.sort();
    assert_eq!(before, after);
    for name in before {
        assert_eq!(
            fs::read(dir.path.join(name)).unwrap(),
            b"authored inert sentinel, not valid media/config"
        );
    }
}
#[test]
fn actual_cli_malformed_limits_unknown_and_literal_suggestion_are_inert() {
    let dir = support::TempDir::new();
    for bytes in [
        b"{}".to_vec(),
        b"\xff".to_vec(),
        vec![b' '; 131073],
        b"[[[[[[[[[0]]]]]]]]]".to_vec(),
    ] {
        let result = invoke(&bytes, &dir.path);
        assert_eq!(result.status.code(), Some(2));
        let report: Value = serde_json::from_slice(&result.stdout).unwrap();
        assert!(report["request"].is_null());
    }
    for (args, status) in [
        (json!(["-n", "-ISO", "$(literal);-missing.cr3"]), 0),
        (json!(["-unknown", "missing"]), 1),
        (json!(["-n", "-n", "-ISO", "missing"]), 1),
    ] {
        let request = json!({"schemaVersion":1,"kind":"legacy-invocation","id":"cli","pathStyle":"posix","workingDirectory":"/does/not/exist","arguments":args});
        let result = invoke(&serde_json::to_vec(&request).unwrap(), &dir.path);
        assert_eq!(result.status.code(), Some(status));
        let report: Value = serde_json::from_slice(&result.stdout).unwrap();
        assert_eq!(report["request"], request);
    }
    assert_eq!(fs::read_dir(&dir.path).unwrap().count(), 0);
}
#[test]
fn cli_help_and_fixed_output_are_explicit() {
    for args in [vec!["compat", "help"], vec!["compat", "translate", "help"]] {
        let result = Command::new(env!("CARGO_BIN_EXE_imageinfo"))
            .args(args)
            .output()
            .unwrap();
        assert!(result.status.success());
        assert!(result.stderr.is_empty());
    }
    let result = Command::new(env!("CARGO_BIN_EXE_imageinfo"))
        .args(["compat", "translate", "--output", "json"])
        .output()
        .unwrap();
    assert_eq!(result.status.code(), Some(2));
}
