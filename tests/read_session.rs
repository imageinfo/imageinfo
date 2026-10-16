//! Actual opt-in sessions over caller-owned streams and authored CR3 bytes.
#[allow(dead_code)]
mod support;

use imageinfo::{read_request, read_session};
use serde_json::{Value, json};
use std::{ffi::OsString, fs, io::Cursor};

fn run(bytes: &[u8]) -> (read_session::SessionOutcome, Vec<Value>, usize) {
    let mut input = Cursor::new(bytes);
    let mut output = Vec::new();
    let outcome = read_session::run(&mut input, &mut output).unwrap();
    assert_eq!(output.last(), Some(&b'\n'));
    assert!(!output.contains(&b'\r'));
    let frames = output
        .split(|byte| *byte == b'\n')
        .filter(|bytes| !bytes.is_empty())
        .map(|bytes| serde_json::from_slice(bytes).unwrap())
        .collect();
    (outcome, frames, input.position() as usize)
}

#[test]
fn ready_and_empty_eof_have_exact_lifecycle() {
    let (outcome, wire, consumed) = run(b"");
    assert_eq!(outcome.exit_status, 0);
    assert_eq!(outcome.reason, "eof");
    assert_eq!((outcome.frames, outcome.results, consumed), (0, 0, 0));
    assert_eq!(wire.len(), 2);
    assert_eq!(wire[0]["kind"], "session-ready");
    assert_eq!(wire[0]["limits"]["maxInputFrameBytes"], 524288);
    assert_eq!(wire[0]["limits"]["maxOutputFrameBytes"], 16777728);
    assert_eq!(wire[0]["allowApply"], false);
    assert_eq!(
        wire[1],
        json!({"protocolVersion":1,"kind":"session-complete",
        "reason":"eof","exitStatus":0,"frames":0,"results":0,"closeId":null})
    );
}

#[test]
fn actual_native_read_matches_direct_api_and_preserves_source() {
    let dir = support::TempDir::new();
    let path = dir.path.join("réad-112.cr3");
    let bytes = support::fixture().bytes;
    fs::write(&path, &bytes).unwrap();
    let before = fs::metadata(&path).unwrap();
    let tokens = vec![
        "metadata",
        "read",
        "--tag",
        "ISO",
        "--",
        path.to_str().unwrap(),
    ];
    let request = json!({"protocolVersion":1,"kind":"read","id":"read-1","tokens":tokens});
    let input = format!(
        "{request}\r\n{{\"protocolVersion\":1,\"kind\":\"close\",\"id\":\"stop\"}}\nunused"
    );
    let (outcome, wire, consumed) = run(input.as_bytes());
    let native: Vec<OsString> = tokens.iter().map(OsString::from).collect();
    let expected = serde_json::to_value(read_request::execute("read-1", &native)).unwrap();
    assert_eq!(wire[1]["result"], expected);
    assert_eq!(wire[1]["id"], "read-1");
    assert_eq!(wire[1]["result"]["summary"]["exitStatus"], 0);
    assert_eq!(outcome.reason, "close");
    assert_eq!((outcome.frames, outcome.results), (2, 1));
    assert_eq!(&input.as_bytes()[consumed..], b"unused");
    assert_eq!(fs::read(&path).unwrap(), bytes);
    let after = fs::metadata(&path).unwrap();
    assert_eq!(before.modified().unwrap(), after.modified().unwrap());
    assert_eq!(
        before.permissions().readonly(),
        after.permissions().readonly()
    );
    assert_eq!(fs::read_dir(&dir.path).unwrap().count(), 1);
}

#[test]
fn request_failure_is_not_session_failure_or_configuration() {
    let input = concat!(
        "{\"protocolVersion\":1,\"kind\":\"read\",\"id\":\"usage\",\"tokens\":[\"help\"]}\n",
        "{\"protocolVersion\":1,\"kind\":\"read\",\"id\":\"next\",\"tokens\":[\"metadata\",\"read\",\"--\",\"missing-112.cr3\"]}\n"
    );
    let (outcome, wire, _) = run(input.as_bytes());
    assert_eq!(outcome.exit_status, 0);
    assert_eq!((outcome.frames, outcome.results), (2, 2));
    assert_eq!(wire[1]["result"]["summary"]["exitStatus"], 2);
    assert_eq!(wire[2]["result"]["summary"]["exitStatus"], 1);
    assert_eq!(wire[2]["result"]["requestId"], "next");
    assert_eq!(wire[3]["reason"], "eof");
}

#[test]
fn delimiter_inclusive_frame_cap_and_immediate_oversize_stop() {
    let close = b"{\"protocolVersion\":1,\"kind\":\"close\",\"id\":\"last\"}";
    let mut exact = close.to_vec();
    exact.resize(read_session::MAX_INPUT_FRAME_BYTES - 1, b' ');
    exact.push(b'\n');
    let (outcome, _, consumed) = run(&exact);
    assert_eq!(outcome.reason, "close");
    assert_eq!(consumed, exact.len());
    exact.insert(exact.len() - 1, b' ');
    exact.extend_from_slice(b"must-remain");
    let (outcome, wire, consumed) = run(&exact);
    assert_eq!(outcome.exit_status, 2);
    assert_eq!(wire[1]["code"], "FRAME_TOO_LARGE");
    assert_eq!(consumed, read_session::MAX_INPUT_FRAME_BYTES);
    assert_eq!(&exact[consumed..], b"\nmust-remain");
}

#[test]
fn scalar_checks_follow_complete_syntax_and_duplicate_member_checks() {
    for (input, expected) in [
        (r#"{"x":"\ud800"}"#, "FRAME_ENCODING"),
        (r#"{"x":"\ud800","x":1}"#, "FRAME_JSON"),
        (r#"{"x":"\ud800",}"#, "FRAME_JSON"),
        (r#"{"\ud800":0,"\ud800":1}"#, "FRAME_JSON"),
        (r#"{"x":"\ud800\udc00"}"#, "FRAME_SCHEMA"),
    ] {
        let (_, wire, _) = run(format!("{input}\n").as_bytes());
        assert_eq!(wire[1]["code"], expected, "{input}");
    }
}
