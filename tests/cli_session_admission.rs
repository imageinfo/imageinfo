//! #0125: finite token-admission delta over #0116's real process/pipe harness.
#[allow(dead_code)]
#[path = "support/session_process.rs"]
mod session_process;
#[allow(dead_code)]
mod support;

use serde_json::Value;
use session_process::{Process, close, completion, read};
use std::{collections::BTreeMap, ffi::OsString, fs, path::Path, time::SystemTime};

fn inventory(path: &Path) -> BTreeMap<OsString, (Vec<u8>, SystemTime, bool)> {
    fs::read_dir(path)
        .unwrap()
        .map(|entry| {
            let entry = entry.unwrap();
            let metadata = entry.metadata().unwrap();
            assert!(metadata.is_file());
            (
                entry.file_name(),
                (
                    fs::read(entry.path()).unwrap(),
                    metadata.modified().unwrap(),
                    metadata.permissions().readonly(),
                ),
            )
        })
        .collect()
}

#[test]
fn startup_token_delta_refuses_before_session_or_media_dispatch() {
    let dir = support::TempDir::new();
    fs::write(
        dir.path.join("startup.cr3"),
        support::fixture_with_firmware("startup-witness-125").bytes,
    )
    .unwrap();
    let before = inventory(&dir.path);
    // Six cells. Startup remains ordinary argv grammar, even with valid media
    // available in the startup cwd and stdin retained open by the caller.
    for args in [
        vec![
            "--output=json",
            "session",
            "read",
            "-stay_open",
            "True",
            "startup.cr3",
        ],
        vec![
            "session",
            "--output=json",
            "read",
            "-execute",
            "startup.cr3",
        ],
        vec![
            "session",
            "read",
            "-common_args",
            "startup.cr3",
            "--output=json",
        ],
        vec![
            "--color=never",
            "session",
            "read",
            "--color=auto",
            "--output=json",
        ],
        vec!["session", "read", "--output=json", "--", "-stay_open"],
        vec!["session", "read", "--output=json", "--", "session read"],
    ] {
        let mut process = Process::start(&args, Some(&dir.path), false);
        let envelope = process.frame();
        assert!(envelope.get("protocolVersion").is_none(), "{args:?}");
        assert_eq!(envelope["summary"]["exitStatus"], 2, "{args:?}");
        let code = if args.contains(&"--") {
            "INVALID_COMMAND"
        } else {
            "INVALID_OPTION"
        };
        assert_eq!(envelope["request"]["issues"][0]["code"], code, "{args:?}");
        assert_eq!(envelope["files"], serde_json::json!([]));
        assert_eq!(envelope["summary"]["artifacts"], serde_json::json!([]));
        assert!(!process.finish(2).is_empty());
    }
    assert_eq!(inventory(&dir.path), before);
}

fn assert_read(frame: &Value, id: &str, path: &str, witness: &str, deduplicated: u32) {
    assert_eq!(frame["kind"], "read-result");
    assert_eq!(frame["id"], id);
    let result = &frame["result"];
    assert_eq!(result["requestId"], id);
    assert_eq!(result["summary"]["exitStatus"], 0);
    assert_eq!(result["summary"]["counts"]["deduplicated"], deduplicated);
    assert_eq!(result["files"].as_array().unwrap().len(), 1);
    let file = &result["files"][0];
    assert_eq!(file["path"], path);
    assert_eq!(file["snapshot"]["sources"][0]["displayPath"], path);
    let occurrences = file["snapshot"]["occurrences"].as_array().unwrap();
    assert_eq!(occurrences.len(), 1);
    assert_eq!(occurrences[0]["tag"]["name"], "CanonFirmwareVersion");
    assert_eq!(occurrences[0]["values"]["raw"]["value"]["text"], witness);
    assert_eq!(
        occurrences[0]["values"]["display"]["state"],
        if id == "post-operand" {
            "present"
        } else {
            "unavailable"
        }
    );
    assert_eq!(result["summary"]["artifacts"], serde_json::json!([]));
    assert_eq!(file["effects"]["changed"], false);
    assert_eq!(file["effects"]["publicationMayHaveOccurred"], false);
}

#[test]
fn request_token_delta_preserves_order_duplicates_and_literal_identity() {
    let dir = support::TempDir::new();
    // Every independently chosen literal path has different authored bytes.
    // A wrong dispatch cannot pass merely because all fixture contents match.
    let fixtures = [
        ("ordinary.cr3", "ordinary-witness-125"),
        ("--output=json", "output-literal-witness-125"),
        ("-stay_open", "stay-open-literal-witness-125"),
        ("session read", "session-literal-witness-125"),
    ];
    for (name, witness) in fixtures {
        fs::write(
            dir.path.join(name),
            support::fixture_with_firmware(witness).bytes,
        )
        .unwrap();
    }
    let before = inventory(&dir.path);
    let mut process = Process::session(Some(&dir.path));
    process.ready();
    // Twelve cells; #0116 already owns recursive [session, read], lifecycle,
    // framing, selector refusal and request isolation. These add token deltas.
    type ExpectedRead<'a> = (&'a str, &'a str, u32);
    type AdmissionCase<'a> = (&'a str, Vec<&'a str>, Option<ExpectedRead<'a>>);
    let cases: [AdmissionCase<'_>; 12] = [
        (
            "legacy-stay",
            vec!["metadata", "read", "-stay_open", "True", "ordinary.cr3"],
            None,
        ),
        (
            "legacy-execute",
            vec!["metadata", "read", "-execute", "ordinary.cr3"],
            None,
        ),
        (
            "legacy-common",
            vec!["metadata", "read", "-common_args", "ordinary.cr3"],
            None,
        ),
        (
            "ordered",
            vec![
                "--color=never",
                "metadata",
                "--no-interactive",
                "read",
                "--tag=CanonFirmwareVersion",
                "--",
                "ordinary.cr3",
            ],
            Some(("ordinary.cr3", "ordinary-witness-125", 0)),
        ),
        (
            "post-operand",
            vec![
                "metadata",
                "read",
                "ordinary.cr3",
                "--tag=CanonFirmwareVersion",
                "--values=all",
            ],
            Some(("ordinary.cr3", "ordinary-witness-125", 0)),
        ),
        (
            "duplicate-color",
            vec![
                "--color=never",
                "metadata",
                "read",
                "--color=auto",
                "ordinary.cr3",
            ],
            None,
        ),
        (
            "duplicate-values",
            vec![
                "metadata",
                "read",
                "--values=raw",
                "--values=all",
                "ordinary.cr3",
            ],
            None,
        ),
        (
            "repeat-tag",
            vec![
                "metadata",
                "read",
                "--tag=CanonFirmwareVersion",
                "--tag=CanonFirmwareVersion",
                "--",
                "ordinary.cr3",
            ],
            Some(("ordinary.cr3", "ordinary-witness-125", 0)),
        ),
        (
            "repeat-input",
            vec![
                "metadata",
                "read",
                "--tag=CanonFirmwareVersion",
                "--",
                "ordinary.cr3",
                "ordinary.cr3",
            ],
            Some(("ordinary.cr3", "ordinary-witness-125", 1)),
        ),
        (
            "literal-output",
            vec![
                "metadata",
                "read",
                "--tag=CanonFirmwareVersion",
                "--",
                "--output=json",
            ],
            Some(("--output=json", "output-literal-witness-125", 0)),
        ),
        (
            "literal-stay",
            vec![
                "metadata",
                "read",
                "--tag=CanonFirmwareVersion",
                "--",
                "-stay_open",
            ],
            Some(("-stay_open", "stay-open-literal-witness-125", 0)),
        ),
        (
            "literal-session",
            vec![
                "metadata",
                "read",
                "--tag=CanonFirmwareVersion",
                "--",
                "session read",
            ],
            Some(("session read", "session-literal-witness-125", 0)),
        ),
    ];
    for (id, tokens, expected) in &cases {
        process.send(&read(id, tokens));
        let frame = process.frame();
        if let Some((path, witness, deduplicated)) = expected {
            assert_read(&frame, id, path, witness, *deduplicated);
        } else {
            assert_eq!(frame["kind"], "read-result");
            assert_eq!(frame["id"], *id);
            assert_eq!(frame["result"]["summary"]["exitStatus"], 2, "{id}");
            assert_eq!(
                frame["result"]["request"]["issues"][0]["code"], "INVALID_OPTION",
                "{id}"
            );
            assert_eq!(frame["result"]["files"], serde_json::json!([]));
            assert_eq!(
                frame["result"]["summary"]["artifacts"],
                serde_json::json!([])
            );
        }
    }
    process.send(&close("done"));
    completion(process.frame(), "close", cases.len() + 1, cases.len(), 0);
    assert!(process.finish(0).is_empty());
    assert_eq!(inventory(&dir.path), before);
}
