//! Startup grammar remains ordinary CLI grammar before session transport begins.
use imageinfo::cli::{self, Invocation, OutputFormat};
use std::process::{Command, Output};

fn run(args: &[&str]) -> Output {
    Command::new(env!("CARGO_BIN_EXE_imageinfo"))
        .args(args)
        .env("NO_COLOR", "1")
        .output()
        .unwrap()
}

#[test]
fn contextual_session_help_is_equivalent_and_never_emits_ready() {
    for forms in [
        vec![
            vec!["session"],
            vec!["help", "session"],
            vec!["session", "help"],
            vec!["session", "--help"],
        ],
        vec![
            vec!["help", "session", "read"],
            vec!["session", "help", "read"],
            vec!["session", "read", "help"],
            vec!["session", "read", "--help"],
        ],
    ] {
        let expected = run(&forms[0]);
        for form in forms {
            let actual = run(&form);
            assert_eq!(actual.status.code(), Some(0), "{form:?}");
            assert_eq!(actual.stdout, expected.stdout, "{form:?}");
            assert!(actual.stderr.is_empty());
            assert!(!actual.stdout.contains(&0x1b));
            assert!(!String::from_utf8_lossy(&actual.stdout).contains("session-ready"));
        }
    }
    let help = run(&["session", "read", "--output=json", "--help"]);
    assert_eq!(help.status.code(), Some(0));
    assert!(help.stdout.starts_with(b"Read metadata"));
}

#[test]
fn session_startup_admits_only_intrinsic_transport_and_ordinary_preferences() {
    assert!(matches!(
        cli::parse(["imageinfo", "session", "read"]).unwrap(),
        Invocation::ReadSession
    ));
    assert!(matches!(
        cli::parse([
            "imageinfo",
            "--color",
            "never",
            "session",
            "--no-interactive",
            "read"
        ])
        .unwrap(),
        Invocation::ReadSession
    ));
    for args in [
        vec!["imageinfo", "--output=text", "session", "read"],
        vec!["imageinfo", "session", "--output=json", "read"],
        vec!["imageinfo", "session", "read", "--output=text"],
    ] {
        let error = cli::parse(args).unwrap_err();
        assert_eq!(error.code, "INVALID_OPTION");
        assert!(error.message.contains("omit --output"));
    }
    assert_eq!(
        cli::parse(["imageinfo", "session", "read", "--interactive"])
            .unwrap_err()
            .code,
        "INTERACTION_UNAVAILABLE"
    );
}

#[test]
fn session_startup_errors_keep_json_routing_and_no_session_prefix() {
    for args in [
        vec!["--output=json", "session", "read"],
        vec!["session", "--output=json", "read"],
        vec!["session", "read", "--output=json"],
        vec!["session", "read", "--help", "--bogus", "--output=json"],
        vec!["session", "read", "unexpected.cr3", "--output=json"],
        vec!["session", "read", "--max-bytes=1", "--output=json"],
        vec!["session", "read", "--allow-apply", "--output=json"],
        vec!["session", "read", "--interactive", "--output=json"],
    ] {
        let output = run(&args);
        assert_eq!(output.status.code(), Some(2), "{args:?}");
        let record: serde_json::Value = serde_json::from_slice(&output.stdout).unwrap();
        assert_eq!(record["schemaVersion"], 1);
        assert_eq!(record["summary"]["exitStatus"], 2);
        assert_eq!(record["files"], serde_json::json!([]));
        assert_eq!(record["summary"]["artifacts"], serde_json::json!([]));
        assert!(record.get("protocolVersion").is_none());
        assert!(!output.stderr.is_empty());
    }
    for args in [
        vec!["session", "read", "--output=text"],
        vec!["session", "read", "--output=bad"],
        vec!["--output=json", "session", "read", "--output=json"],
        vec!["session", "read", "--help", "--bogus"],
    ] {
        let output = run(&args);
        assert_eq!(output.status.code(), Some(2), "{args:?}");
        assert!(output.stdout.is_empty(), "{args:?}");
        assert!(!output.stderr.is_empty());
    }
}

#[test]
fn version_preserves_existing_precedence_and_output_contract() {
    assert_eq!(
        cli::parse(["imageinfo", "session", "read", "--version", "--output=json"]).unwrap(),
        Invocation::Version(OutputFormat::Json)
    );
    let output = run(&["session", "read", "--version", "--output=json"]);
    assert_eq!(output.status.code(), Some(0));
    let value: serde_json::Value = serde_json::from_slice(&output.stdout).unwrap();
    assert!(value.get("protocolVersion").is_none());
    assert!(output.stderr.is_empty());
}
