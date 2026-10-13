#[allow(dead_code)]
mod support;
use imageinfo::cli::{self, OutputFormat};
use std::{ffi::OsString, fs, process::Command};

fn run(args: &[&str]) -> std::process::Output {
    Command::new(env!("CARGO_BIN_EXE_imageinfo"))
        .args(args)
        .env("NO_COLOR", "1")
        .env("PAGER", "imageinfo-must-not-launch-pager")
        .output()
        .unwrap()
}
fn error_envelope(output: &std::process::Output) -> serde_json::Value {
    assert_eq!(output.status.code(), Some(2));
    let value: serde_json::Value =
        serde_json::from_slice(&output.stdout).expect("complete JSON error envelope");
    assert_eq!(value["schemaVersion"], 1);
    assert_eq!(value["request"]["operation"], serde_json::Value::Null);
    assert_eq!(value["request"]["mode"], serde_json::Value::Null);
    assert_eq!(value["files"], serde_json::json!([]));
    assert_eq!(value["summary"]["artifacts"], serde_json::json!([]));
    assert_eq!(
        value["summary"]["counts"],
        serde_json::json!({"discovered":0,"excluded":0,"deduplicated":0,"byState":{}})
    );
    assert_eq!(value["summary"]["selectionComplete"], false);
    assert_eq!(value["summary"]["outputComplete"], true);
    assert_eq!(value["summary"]["exitStatus"], 2);
    assert_eq!(value["summary"]["interrupted"], false);
    assert_eq!(value["requestId"], value["request"]["requestId"]);
    assert_eq!(value["requestId"], value["summary"]["requestId"]);
    assert!(!output.stderr.is_empty());
    assert!(!output.stdout.contains(&0x1b) && !output.stderr.contains(&0x1b));
    value
}

#[test]
fn explicit_json_routes_syntax_errors_in_any_option_order() {
    for args in [
        vec!["--output=json", "--bogus"],
        vec!["--bogus", "--output", "json"],
        vec!["--output", "json", "metadata", "wrong"],
        vec!["metadata", "wrong", "--output=json"],
        vec!["metadata", "--output=json", "read", "--bogus"],
        vec!["metadata", "read", "--bogus", "--output=json"],
        vec!["metadata", "read", "--values=bad", "--output=json"],
        vec!["metadata", "read", "--max-bytes=0", "--output=json"],
        vec!["binary", "extract", "--output=json", "--tag=bad"],
        vec!["binary", "list", "--bogus", "--output=json"],
        vec!["version", "--bogus", "--output=json"],
        vec!["help", "metadata", "--bogus", "--output=json"],
    ] {
        error_envelope(&run(&args));
    }
}

#[test]
fn invalid_or_duplicate_output_selection_keeps_plain_stderr() {
    for args in [
        vec!["--output=bad", "--bogus"],
        vec!["--output=json", "--output=bad", "--bogus"],
        vec!["--output=json", "version", "--output=text"],
        vec!["--output=json", "--output=json"],
        vec!["--output=json", "--output"],
        vec!["--output", "--bogus"],
        vec!["--out=json", "--bogus"],
        vec!["--output=text", "--bogus"],
    ] {
        let output = run(&args);
        assert_eq!(output.status.code(), Some(2), "{args:?}");
        assert!(output.stdout.is_empty(), "{args:?}");
        assert!(!output.stderr.is_empty());
    }
}

#[test]
fn literal_operands_and_attached_values_do_not_select_a_channel() {
    for args in [
        vec!["metadata", "read", "--bogus", "--", "--output=json"],
        vec!["metadata", "read", "--tag=--output=json", "--bogus"],
        vec![
            "binary",
            "extract",
            "--output-file=--output=json",
            "--bogus",
        ],
        vec!["metadata", "read", "--tag=--output", "json", "--bogus"],
    ] {
        let output = run(&args);
        assert_eq!(output.status.code(), Some(2));
        assert!(output.stdout.is_empty(), "{args:?}");
    }
    error_envelope(&run(&[
        "--output=json",
        "metadata",
        "read",
        "--bogus",
        "--",
        "--output=text",
    ]));
    error_envelope(&run(&[
        "metadata",
        "read",
        "--tag",
        "--output=json",
        "--bogus",
    ]));
    error_envelope(&run(&[
        "binary",
        "extract",
        "--output-file",
        "--output=json",
        "--bogus",
    ]));
}

#[test]
fn help_version_and_other_scalar_errors_preserve_the_declared_boundary() {
    for args in [
        vec!["--output=json", "--help", "--bogus"],
        vec!["--bogus", "--version", "--output=json"],
        vec![
            "metadata",
            "--output=json",
            "--color=never",
            "read",
            "--color=always",
        ],
        vec!["metadata", "read", "--output=json", "--color=bad"],
        vec![
            "--output=json",
            "--interactive",
            "--no-interactive",
            "--help",
        ],
    ] {
        error_envelope(&run(&args));
    }
    let help = run(&["metadata", "read", "--output=json", "--help"]);
    assert_eq!(help.status.code(), Some(0));
    assert!(help.stderr.is_empty());
    assert!(String::from_utf8(help.stdout).unwrap().starts_with("Read"));
}

#[test]
fn json_syntax_errors_are_bounded_and_terminal_safe() {
    let argument = format!("--\u{1b}[31m{}", "x".repeat(12000));
    let output = run(&["--color=always", "--output=json", &argument]);
    let envelope = error_envelope(&output);
    assert!(
        envelope["request"]["issues"][0]["message"]
            .as_str()
            .unwrap()
            .len()
            <= 4096
    );
    assert!(output.stderr.len() < 4200);
    assert!(output.stdout.len() < 5500);
}

#[test]
fn syntax_errors_do_not_read_or_extract_an_authored_input() {
    let directory = support::TempDir::new();
    let input = directory.path.join("source.cr3");
    let destination = directory.path.join("preview.jpg");
    let fixture = support::fixture();
    fs::write(&input, &fixture.bytes).unwrap();
    let modified = fs::metadata(&input).unwrap().modified().unwrap();
    let output = Command::new(env!("CARGO_BIN_EXE_imageinfo"))
        .args([
            OsString::from("binary"),
            "extract".into(),
            input.clone().into_os_string(),
            "--tag=JpgFromRaw".into(),
            "--output-file".into(),
            destination.clone().into_os_string(),
            "--bogus".into(),
            "--output=json".into(),
        ])
        .output()
        .unwrap();
    error_envelope(&output);
    assert_eq!(fs::read(&input).unwrap(), fixture.bytes);
    assert_eq!(fs::metadata(&input).unwrap().modified().unwrap(), modified);
    assert!(!destination.exists());
    assert_eq!(fs::read_dir(&directory.path).unwrap().count(), 1);
}

#[test]
fn command_values_keep_output_tokens_unambiguous() {
    fn check(tree: &clap::Command) {
        for arg in tree.get_arguments() {
            assert!(
                !arg.is_allow_hyphen_values_set(),
                "{}: {}",
                tree.get_name(),
                arg.get_id()
            );
        }
        for child in tree.get_subcommands() {
            check(child);
        }
    }
    let mut tree = cli::command();
    tree.build();
    check(&tree);
}

#[cfg(unix)]
#[test]
fn non_unicode_selectors_refuse_while_unrelated_argv_is_preserved() {
    use std::os::unix::ffi::OsStringExt;
    let invalid = OsString::from_vec(b"--output=\xff".to_vec());
    let error = cli::parse(vec![
        "imageinfo".into(),
        "--output=json".into(),
        invalid,
        "--bogus".into(),
    ])
    .unwrap_err();
    assert_eq!(error.output, OutputFormat::Text);
    let path = OsString::from_vec(b"photo-\xff.cr3".to_vec());
    let error = cli::parse(vec![
        "imageinfo".into(),
        "metadata".into(),
        "read".into(),
        "--bogus".into(),
        "--output=json".into(),
        "--".into(),
        path,
    ])
    .unwrap_err();
    assert_eq!(error.output, OutputFormat::Json);
}

#[cfg(windows)]
#[test]
fn unpaired_utf16_selector_refuses_without_lossy_decoding() {
    use std::os::windows::ffi::OsStringExt;
    let mut units: Vec<u16> = "--output=".encode_utf16().collect();
    units.push(0xd800);
    let invalid = OsString::from_wide(&units);
    let error = cli::parse(vec![
        "imageinfo".into(),
        "--output=json".into(),
        invalid,
        "--bogus".into(),
    ])
    .unwrap_err();
    assert_eq!(error.output, OutputFormat::Text);
}
