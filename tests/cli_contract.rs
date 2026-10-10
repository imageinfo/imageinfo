use imageinfo::cli::{self, Invocation, OutputFormat, ValueView};
use std::{ffi::OsString, path::PathBuf, process::Command};

fn run(args: &[&str]) -> std::process::Output {
    Command::new(env!("CARGO_BIN_EXE_imageinfo"))
        .args(args)
        .env("NO_COLOR", "1")
        .env("PAGER", "imageinfo-must-not-run-a-pager")
        .env("EXIFTOOL_HOME", "imageinfo-must-not-load-exiftool-config")
        .output()
        .expect("run imageinfo test executable")
}

#[test]
fn help_forms_are_equivalent_at_every_level() {
    for forms in [
        vec![vec![], vec!["help"], vec!["--help"]],
        vec![
            vec!["metadata"],
            vec!["metadata", "help"],
            vec!["help", "metadata"],
            vec!["metadata", "--help"],
        ],
        vec![
            vec!["metadata", "read", "help"],
            vec!["help", "metadata", "read"],
            vec!["metadata", "help", "read"],
            vec!["metadata", "read", "--help"],
        ],
    ] {
        let expected = run(&forms[0]);
        assert_eq!(expected.status.code(), Some(0));
        for form in forms {
            let actual = run(&form);
            assert_eq!(
                actual.status.code(),
                Some(0),
                "{form:?}: {:?}",
                actual.stderr
            );
            assert_eq!(actual.stdout, expected.stdout, "{form:?}");
            assert!(actual.stderr.is_empty());
            assert!(!actual.stdout.contains(&0x1b));
        }
    }
}

#[test]
fn malformed_syntax_wins_over_help_in_either_order() {
    for args in [
        vec!["metadata", "read", "--help", "--bogus"],
        vec!["metadata", "read", "--bogus", "--help"],
        vec!["metadata", "read", "--output", "bad", "--help"],
        vec!["metadata", "read", "--values", "bad", "--help"],
        vec!["metadata", "read", "--out", "json", "--help"],
        vec![
            "metadata",
            "read",
            "--interactive",
            "--no-interactive",
            "--help",
        ],
        vec!["help", "metadata", "wrong"],
        vec!["metadata", "wriet", "--help"],
    ] {
        let actual = run(&args);
        assert_eq!(actual.status.code(), Some(2), "{args:?}");
        assert!(actual.stdout.is_empty());
        assert!(!actual.stderr.is_empty());
        assert!(!actual.stderr.contains(&0x1b));
        assert!(
            String::from_utf8(actual.stderr).unwrap().contains("help"),
            "{args:?}"
        );
    }
}

#[test]
fn scalar_options_cannot_repeat_within_or_across_scopes() {
    for args in [
        vec!["version", "--output", "json", "--output", "json"],
        vec!["--output", "json", "version", "--output", "text"],
        vec![
            "--color", "never", "metadata", "--color", "never", "read", "--help",
        ],
        vec![
            "metadata", "read", "--values", "raw", "--values", "display", "x",
        ],
    ] {
        assert_eq!(run(&args).status.code(), Some(2), "{args:?}");
    }
}

#[test]
fn parser_retains_paths_and_repeated_tag_values() {
    let args: Vec<OsString> = [
        "imageinfo",
        "--output",
        "json",
        "metadata",
        "read",
        "--values",
        "all",
        "--tag",
        "ISO",
        "--tag",
        "Model",
        "--",
        "help",
        "-photo.cr3",
        "写真 🦆.cr3",
        "line\nbreak.cr3",
    ]
    .iter()
    .map(OsString::from)
    .collect();
    let Invocation::Read(request) = cli::parse(args).expect("valid read request") else {
        panic!("not a read request")
    };
    assert_eq!(
        request.inputs,
        ["help", "-photo.cr3", "写真 🦆.cr3", "line\nbreak.cr3"].map(PathBuf::from)
    );
    assert_eq!(request.tags, ["ISO", "Model"]);
    assert_eq!(request.values, ValueView::All);
    assert_eq!(request.output, OutputFormat::Json);
}

#[cfg(unix)]
#[test]
fn non_unicode_path_bytes_remain_intact() {
    use std::os::unix::ffi::OsStringExt;
    let path = OsString::from_vec(vec![b'x', 0xff, b'.', b'c', b'r', b'3']);
    let args = vec![
        "imageinfo".into(),
        "metadata".into(),
        "read".into(),
        "--".into(),
        path.clone(),
    ];
    let Invocation::Read(request) = cli::parse(args).expect("valid path") else {
        panic!("not read")
    };
    assert_eq!(request.inputs, [PathBuf::from(path)]);
}

#[test]
fn redirected_help_remains_plain_and_does_not_enter_guided_mode() {
    let actual = run(&[
        "metadata",
        "read",
        "--interactive",
        "--color",
        "always",
        "--output",
        "json",
        "--help",
    ]);
    assert_eq!(actual.status.code(), Some(0));
    assert!(actual.stderr.is_empty());
    assert!(!actual.stdout.contains(&0x1b));
    assert!(
        String::from_utf8(actual.stdout)
            .unwrap()
            .contains("not implemented")
    );
}

#[test]
fn an_explicit_guided_request_never_silently_runs_another_action() {
    for args in [
        vec!["--interactive"],
        vec!["metadata", "--interactive"],
        vec!["version", "--interactive"],
    ] {
        let output = run(&args);
        assert_eq!(output.status.code(), Some(2), "{args:?}");
        assert!(output.stdout.is_empty());
        assert!(
            String::from_utf8(output.stderr)
                .unwrap()
                .contains("INTERACTION_UNAVAILABLE")
        );
    }
}

#[test]
fn missing_inputs_are_usage_errors_and_valid_read_is_an_explicit_refusal() {
    let missing = run(&["metadata", "read"]);
    assert_eq!(missing.status.code(), Some(2));
    assert!(
        String::from_utf8(missing.stderr)
            .unwrap()
            .contains("MISSING_ARGUMENT")
    );
    let refusal = run(&["metadata", "read", "--", "never-created-写真.cr3"]);
    assert_eq!(refusal.status.code(), Some(1));
    assert!(refusal.stdout.is_empty());
    assert!(
        String::from_utf8(refusal.stderr)
            .unwrap()
            .contains("CAPABILITY_UNSUPPORTED")
    );
}

#[test]
fn json_refusal_and_post_parse_validation_errors_have_complete_envelopes() {
    for (args, status, code) in [
        (
            vec!["metadata", "read", "--output", "json", "photo.cr3"],
            1,
            "CAPABILITY_UNSUPPORTED",
        ),
        (
            vec!["metadata", "read", "--output", "json"],
            2,
            "MISSING_ARGUMENT",
        ),
    ] {
        let output = run(&args);
        assert_eq!(output.status.code(), Some(status));
        let record: serde_json::Value =
            serde_json::from_slice(&output.stdout).expect("JSON stdout");
        assert_eq!(record["request"]["issues"][0]["code"], code);
        assert_eq!(record["summary"]["exitStatus"], status);
        assert_eq!(record["summary"]["outputComplete"], true);
        assert_eq!(record["summary"]["selectionComplete"], false);
        assert_eq!(record["files"], serde_json::json!([]));
        assert_eq!(record["requestId"], record["request"]["requestId"]);
        assert_eq!(record["requestId"], record["summary"]["requestId"]);
        assert!(!output.stderr.is_empty());
    }
}

#[test]
fn version_forms_agree_and_json_is_deterministic() {
    let expected = run(&["version", "--output", "json"]);
    for args in [
        vec!["--version", "--output=json"],
        vec!["--output", "json", "version"],
        vec!["metadata", "--version", "--output", "json"],
    ] {
        let actual = run(&args);
        assert_eq!(actual.status.code(), Some(0));
        assert_eq!(actual.stdout, expected.stdout);
        assert!(actual.stderr.is_empty());
    }
    let version: imageinfo::output::VersionInfo = serde_json::from_slice(&expected.stdout).unwrap();
    assert!(!version.media_reading_implemented);
    assert_eq!(version.version, imageinfo::VERSION);
}

#[test]
fn user_control_characters_do_not_reach_the_terminal() {
    let output = run(&["--bad\u{1b}[31m"]);
    assert_eq!(output.status.code(), Some(2));
    assert!(!output.stderr.contains(&0x1b));
}

#[test]
fn diagnostic_output_is_bounded_for_a_long_invalid_argument() {
    let argument = format!("--{}", "x".repeat(12000));
    let output = run(&[&argument]);
    assert_eq!(output.status.code(), Some(2));
    assert!(output.stderr.len() < 4200);
    assert!(String::from_utf8(output.stderr).unwrap().contains("..."));
}

#[test]
fn command_tree_is_introspectable_and_internally_valid() {
    let tree = cli::command();
    tree.clone().debug_assert();
    let metadata = tree.find_subcommand("metadata").unwrap();
    let read = metadata.find_subcommand("read").unwrap();
    assert!(
        read.get_arguments()
            .any(|arg| arg.get_long() == Some("values"))
    );
    assert!(
        read.get_about()
            .unwrap()
            .to_string()
            .contains("not implemented")
    );
}
