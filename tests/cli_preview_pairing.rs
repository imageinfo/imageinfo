#[allow(dead_code)]
mod support;
use std::{
    fs,
    process::{Command, Output},
};

fn run(args: &[&str]) -> Output {
    Command::new(env!("CARGO_BIN_EXE_imageinfo"))
        .args(args)
        .env("NO_COLOR", "1")
        .output()
        .unwrap()
}
fn json(output: &Output, status: i32) -> serde_json::Value {
    assert_eq!(
        output.status.code(),
        Some(status),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    let value: serde_json::Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(value["summary"]["exitStatus"], status);
    assert_eq!(value["summary"]["artifacts"], serde_json::json!([]));
    for file in value["files"].as_array().unwrap() {
        assert_eq!(file["effects"]["changed"], false);
        assert_eq!(file["effects"]["publicationMayHaveOccurred"], false);
        assert_eq!(file["effects"]["cleanupPending"], false);
        assert_eq!(file["transactionId"], serde_json::Value::Null);
    }
    value
}
fn fixture() -> Vec<u8> {
    support::fixture_with_previews(
        "Firmware Version 2.2.1",
        vec![0xff, 0xd8, 0xff, 0xd9],
        vec![0xff, 0xd8, 0xff, 0xd9],
        vec![0xff, 0xd8, 0xff, 0xd9],
    )
    .bytes
}

#[test]
fn contextual_help_is_available_at_root_groups_and_leaves_without_inputs() {
    let root = run(&["--help"]);
    assert!(String::from_utf8_lossy(&root.stdout).contains("preview"));
    assert!(String::from_utf8_lossy(&root.stdout).contains("sidecar"));
    for (group, leaf) in [("preview", "date-time-original"), ("sidecar", "pair")] {
        let group_help = run(&[group]);
        assert_eq!(group_help.status.code(), Some(0));
        assert!(String::from_utf8_lossy(&group_help.stdout).contains(leaf));
        let expected = run(&[group, leaf, "--help"]);
        assert_eq!(expected.status.code(), Some(0));
        assert!(expected.stderr.is_empty());
        for args in [
            vec!["help", group, leaf],
            vec![group, "help", leaf],
            vec![group, leaf, "help"],
        ] {
            let actual = run(&args);
            assert_eq!(actual.status.code(), Some(0));
            assert_eq!(actual.stdout, expected.stdout);
            assert!(actual.stderr.is_empty());
        }
    }
}

#[test]
fn actual_preview_refusal_reports_advisory_partition_without_filesystem_effects() {
    let dir = support::TempDir::new();
    let path = dir.path.join("source.cr3");
    let bytes = fixture();
    fs::write(&path, &bytes).unwrap();
    let modified = fs::metadata(&path).unwrap().modified().unwrap();
    let output = run(&[
        "preview",
        "date-time-original",
        path.to_str().unwrap(),
        "--value",
        "2000:02:29 23:59:59",
        "--output",
        "json",
    ]);
    let value = json(&output, 1);
    assert_eq!(value["request"]["mode"], "preview");
    assert_eq!(value["files"][0]["state"], "refused");
    let preview = &value["files"][0]["snapshot"]["preview"];
    assert_eq!(preview["production_mutation_allowed"], false);
    assert_eq!(preview["refusals"][0]["code"], "OPAQUE_DEPENDENCY_UNPROVEN");
    assert!(preview["changed_bytes"].as_u64().unwrap() > 0);
    assert_eq!(
        preview["changed_bytes"].as_u64().unwrap() + preview["preserved_bytes"].as_u64().unwrap(),
        bytes.len() as u64
    );
    let stale = json(
        &run(&[
            "--output=json",
            "preview",
            "date-time-original",
            path.to_str().unwrap(),
            "--value",
            "2000:02:29 23:59:59",
            "--offset",
            "0",
        ]),
        1,
    );
    assert!(
        stale["files"][0]["issues"]
            .as_array()
            .unwrap()
            .iter()
            .any(|i| i["code"] == "OCCURRENCE_CHANGED")
    );
    assert_eq!(
        stale["files"][0]["snapshot"]["preview"]["original_bytes"],
        serde_json::Value::Null
    );
    assert_eq!(fs::read(&path).unwrap(), bytes);
    assert_eq!(fs::metadata(path).unwrap().modified().unwrap(), modified);
    assert_eq!(fs::read_dir(dir.path.clone()).unwrap().count(), 1);
}

#[test]
fn explicit_pair_preserves_files_and_does_not_require_content_interpretation() {
    let dir = support::TempDir::new();
    let raw = dir.path.join("photo.cr3");
    let sidecar = dir.path.join("chosen.xmp");
    fs::write(&raw, b"raw marker, not parsed").unwrap();
    fs::write(&sidecar, b"sidecar marker, not parsed").unwrap();
    let output = run(&[
        "sidecar",
        "pair",
        raw.to_str().unwrap(),
        "--sidecar",
        sidecar.to_str().unwrap(),
        "--output=json",
    ]);
    let value = json(&output, 0);
    assert!(output.stderr.is_empty());
    assert_eq!(
        value["files"][0]["snapshot"]["pair"]["association"],
        "explicit_paths"
    );
    assert_eq!(value["files"][0]["state"], "read");
    let missing = dir.path.join("missing.xmp");
    let value = json(
        &run(&[
            "sidecar",
            "pair",
            raw.to_str().unwrap(),
            "--sidecar",
            missing.to_str().unwrap(),
            "--output=json",
        ]),
        1,
    );
    assert_eq!(value["files"][0]["issues"][0]["code"], "SIDECAR_MISSING");
    assert!(!missing.exists());
    assert_eq!(fs::read(raw).unwrap(), b"raw marker, not parsed");
    assert_eq!(fs::read(sidecar).unwrap(), b"sidecar marker, not parsed");
    assert_eq!(fs::read_dir(dir.path.clone()).unwrap().count(), 2);
}

#[test]
fn pairing_never_infers_a_matching_basename_or_accepts_aliases() {
    let dir = support::TempDir::new();
    let raw = dir.path.join("photo.cr3");
    fs::write(&raw, b"unchanged").unwrap();
    fs::write(dir.path.join("photo.xmp"), b"unchanged sidecar").unwrap();
    let value = json(
        &run(&["sidecar", "pair", raw.to_str().unwrap(), "--output=json"]),
        1,
    );
    assert_eq!(
        value["files"][0]["issues"][0]["code"],
        "EXPLICIT_SIDECAR_REQUIRED"
    );
    let alias = dir.path.join(".").join("photo.cr3");
    let value = json(
        &run(&[
            "sidecar",
            "pair",
            raw.to_str().unwrap(),
            "--sidecar",
            alias.to_str().unwrap(),
            "--output=json",
        ]),
        1,
    );
    assert_eq!(value["files"][0]["issues"][0]["code"], "PAIRING_SAME_FILE");
    assert_eq!(fs::read(raw).unwrap(), b"unchanged");
}

#[test]
fn new_commands_preserve_json_syntax_routing_and_have_no_output_or_apply_option() {
    for args in [
        vec!["preview", "date-time-original", "missing", "--output=json"],
        vec![
            "preview",
            "date-time-original",
            "missing",
            "--value",
            "1900:02:29 00:00:00",
            "--output=json",
        ],
        vec![
            "preview",
            "date-time-original",
            "missing",
            "--value",
            "2000:01:01 00:00:00",
            "--offset",
            "-1",
            "--output=json",
        ],
        vec![
            "preview",
            "date-time-original",
            "--help",
            "--apply",
            "--output=json",
        ],
        vec![
            "sidecar",
            "pair",
            "missing",
            "--output-file",
            "new.xmp",
            "--output=json",
        ],
        vec!["sidecar", "pair", "--help", "--bogus", "--output=json"],
        vec!["sidecar", "pair", "one", "two", "--output=json"],
    ] {
        let value = json(&run(&args), 2);
        assert_eq!(value["files"], serde_json::json!([]));
        assert!(!value["request"]["issues"].as_array().unwrap().is_empty());
    }
    let output = run(&[
        "--output=json",
        "sidecar",
        "pair",
        "--output=text",
        "missing",
    ]);
    assert_eq!(output.status.code(), Some(2));
    assert!(output.stdout.is_empty());
}

#[test]
fn preview_refuses_a_directory_before_reader_io() {
    let dir = support::TempDir::new();
    let value = json(
        &run(&[
            "preview",
            "date-time-original",
            dir.path.to_str().unwrap(),
            "--value",
            "2000:01:01 00:00:00",
            "--output=json",
        ]),
        1,
    );
    assert_eq!(
        value["files"][0]["issues"][0]["code"],
        "CAPABILITY_UNSUPPORTED"
    );
    assert_eq!(value["files"][0]["snapshot"], serde_json::Value::Null);
    assert_eq!(fs::read_dir(&dir.path).unwrap().count(), 0);
}
