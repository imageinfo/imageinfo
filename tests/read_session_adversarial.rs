//! Independent authored-input review of the caller-owned session runtime.
#[allow(dead_code)]
mod support;

use imageinfo::{read_request, read_session};
use serde_json::{Value, json};
use std::{
    cell::Cell,
    collections::BTreeMap,
    ffi::OsString,
    fs,
    io::{self, BufRead, Cursor, Read, Write},
    path::Path,
    rc::Rc,
    time::SystemTime,
};

const FRAME_CAP: usize = 524_288;

fn wire(value: Value) -> Vec<u8> {
    let mut bytes = serde_json::to_vec(&value).unwrap();
    bytes.push(b'\n');
    bytes
}

fn read_frame(id: &str, tokens: &[&str]) -> Vec<u8> {
    wire(json!({"protocolVersion":1,"kind":"read","id":id,"tokens":tokens}))
}

fn records(bytes: &[u8]) -> Vec<Value> {
    assert!(bytes.ends_with(b"\n"));
    assert!(!bytes.contains(&b'\r'));
    bytes[..bytes.len() - 1]
        .split(|byte| *byte == b'\n')
        .map(|line| serde_json::from_slice(line).unwrap())
        .collect()
}

fn run(input: &[u8]) -> Vec<Value> {
    let mut output = Vec::new();
    read_session::run(&mut Cursor::new(input), &mut output).unwrap();
    records(&output)
}

fn expect_error(input: &[u8], code: &str) {
    let output = run(input);
    assert_eq!(output.len(), 3);
    assert_eq!(
        output[1],
        json!({"protocolVersion":1,"kind":"protocol-error","id":null,"code":code})
    );
    assert_eq!(output[2]["reason"], "protocol-error");
    assert_eq!(output[2]["exitStatus"], 2);
    assert_eq!(output[2]["frames"], 1);
    assert_eq!(output[2]["results"], 0);
}

fn expand(case: &Value) -> Vec<u8> {
    if let Some(text) = case["utf8"].as_str() {
        return text.as_bytes().to_vec();
    }
    if let Some(hex) = case["hex"].as_str() {
        return (0..hex.len())
            .step_by(2)
            .map(|at| u8::from_str_radix(&hex[at..at + 2], 16).unwrap())
            .collect();
    }
    let recipe = &case["recipe"];
    let count = |field: &str| recipe[field].as_u64().unwrap() as usize;
    match recipe["kind"].as_str().unwrap() {
        "count" => {
            let mut bytes = Vec::new();
            for index in 0..count("count") {
                bytes.extend(read_frame(&format!("r{index}"), &[]));
            }
            bytes.extend(recipe["tail"].as_str().unwrap_or("").as_bytes());
            bytes
        }
        "padding" => {
            let mut bytes = wire(json!({"protocolVersion":1,"kind":"close","id":"done"}));
            bytes.pop();
            bytes.resize(count("bytes") - 1, b' ');
            bytes.push(b'\n');
            bytes
        }
        "unterminated" => vec![b' '; count("bytes")],
        "depth" => {
            let depth = count("depth");
            let mut bytes = vec![b'['; depth];
            bytes.push(b'0');
            bytes.extend(vec![b']'; depth]);
            bytes.push(b'\n');
            bytes
        }
        "tokens" => {
            let tokens: Vec<String> = recipe["tokens"]
                .as_array()
                .unwrap()
                .iter()
                .map(|item| {
                    item["text"]
                        .as_str()
                        .unwrap()
                        .repeat(item["repeat"].as_u64().unwrap() as usize)
                })
                .collect();
            wire(json!({"protocolVersion":1,"kind":"read","id":"r1","tokens":tokens}))
        }
        kind => panic!("unknown independent fixture recipe: {kind}"),
    }
}

#[test]
fn all_56_existing_authored_framing_cases_execute_against_runtime() {
    let vectors: Value = serde_json::from_str(include_str!(
        "../docs/legacy-compatibility/read-session/vectors.v1.json"
    ))
    .unwrap();
    let cases = vectors["cases"].as_array().unwrap();
    assert_eq!(cases.len(), 56);
    for case in cases {
        let output = run(&expand(case));
        assert_eq!(output[0]["kind"], "session-ready", "{}", case["id"]);
        let mut actual = output.last().unwrap().as_object().unwrap().clone();
        actual.remove("kind");
        actual.remove("protocolVersion");
        actual.insert(
            "error".into(),
            output
                .iter()
                .find(|record| record["kind"] == "protocol-error")
                .map_or(Value::Null, |record| record["code"].clone()),
        );
        assert_eq!(Value::Object(actual), case["expect"], "{}", case["id"]);
        // Response stubs in the old model are intentionally not injected. Every
        // admitted read here passes through the actual native request API.
        for record in output
            .iter()
            .filter(|record| record["kind"] == "read-result")
        {
            assert_eq!(record["id"], record["result"]["requestId"]);
            assert_eq!(record["id"], record["result"]["request"]["requestId"]);
            assert_eq!(record["id"], record["result"]["summary"]["requestId"]);
        }
    }
}

#[test]
fn combined_errors_respect_full_json_before_unicode_and_schema() {
    for input in [
        r#"{"x":"\ud800","x":0}"#,
        r#"{"x":"\ud800","\u0078":0}"#,
        r#"{"\ud800":0,"\ud800":1}"#,
        r#"{"unknown":{"x":"\ud800","x":1}}"#,
        r#"{"x":"\ud800","later":]}"#,
        r#"{"x":"\ud800"} trailing"#,
        r#"{"x":"\ud800","later":"\q"}"#,
        r#"{"x":"\ud800","later":01}"#,
        r#"{"x":NaN,"later":"\ud800"}"#,
        r#"{"x":Infinity,"later":"\ud800"}"#,
        r#"{"x":1e400,"x":"\ud800"}"#,
        r#"{"x":1e400,"later":]}"#,
    ] {
        expect_error(format!("{input}\n").as_bytes(), "FRAME_JSON");
    }
    for input in [
        r#"{"x":"\ud800"}"#,
        r#"{"\udfff":0}"#,
        r#"{"protocolVersion":2,"kind":"close","id":"bad id","x":"\ud800"}"#,
        r#"{"protocolVersion":1,"kind":"read","id":"r","tokens":["\ud800"]}"#,
        r#"{"x":1e400,"later":"\ud800"}"#,
    ] {
        expect_error(format!("{input}\n").as_bytes(), "FRAME_ENCODING");
    }
    let mut invalid_utf8 = b"[[[[[[[[[".to_vec();
    invalid_utf8.extend([0xff, b'\n']);
    expect_error(&invalid_utf8, "FRAME_ENCODING");
    expect_error(b"[[[[[[[[[\"\\ud800\" broken\n", "FRAME_SCHEMA");
    expect_error(b"[[[[[[[[0]]]]]]]]\n", "FRAME_SCHEMA");
    expect_error(
        b"{\"protocolVersion\":1,\"kind\":\"read\",\"id\":\"r\",\"tokens\":[\"\\u0000\"]}\n",
        "FRAME_SCHEMA",
    );
    let paired = run(
        b"{\"protocolVersion\":1,\"kind\":\"read\",\"id\":\"r\",\"tokens\":[\"\\ud83d\\ude00\"]}\n",
    );
    assert_eq!(paired.last().unwrap()["reason"], "eof");
    assert_eq!(paired.last().unwrap()["results"], 1);
}

#[test]
fn every_raw_string_control_is_json_error_even_after_bad_unicode() {
    for control in (0..0x20).filter(|byte| *byte != b'\n') {
        let mut bytes = br#"{"bad":"\ud800","later":""#.to_vec();
        bytes.push(control);
        bytes.extend(b"\"}\n");
        expect_error(&bytes, "FRAME_JSON");
    }
}

#[test]
fn numeric_protocol_versions_follow_existing_schema_value_semantics() {
    for version in ["1", "1.0", "1e0", "1.00000000000000001"] {
        let input =
            format!("{{\"protocolVersion\":{version},\"kind\":\"close\",\"id\":\"done\"}}\n");
        assert_eq!(run(input.as_bytes()).last().unwrap()["reason"], "close");
    }
    for version in ["true", "false", "null", "\"1\"", "2", "1.0001", "1e400"] {
        let input =
            format!("{{\"protocolVersion\":{version},\"kind\":\"close\",\"id\":\"done\"}}\n");
        expect_error(input.as_bytes(), "FRAME_SCHEMA");
    }
}

/// Panics if admission asks the caller for even one byte beyond its boundary.
struct TailGuard {
    bytes: Vec<u8>,
    position: usize,
    stop: usize,
}

impl Read for TailGuard {
    fn read(&mut self, buffer: &mut [u8]) -> io::Result<usize> {
        let available = self.fill_buf()?;
        let count = buffer.len().min(available.len());
        buffer[..count].copy_from_slice(&available[..count]);
        self.consume(count);
        Ok(count)
    }
}

impl BufRead for TailGuard {
    fn fill_buf(&mut self) -> io::Result<&[u8]> {
        assert!(
            self.position < self.stop,
            "read past terminal admission boundary"
        );
        // Caller-owned buffering may already contain the entire next frame.
        Ok(&self.bytes[self.position..])
    }
    fn consume(&mut self, amount: usize) {
        assert!(
            self.position + amount <= self.stop,
            "consumed past terminal admission boundary"
        );
        self.position += amount;
    }
}

#[test]
fn no_caller_bytes_are_consumed_after_close_fatal_size_or_attempt_256() {
    let mut cases = vec![
        wire(json!({"protocolVersion":1,"kind":"close","id":"done"})),
        b"{bad\n".to_vec(),
        vec![b' '; FRAME_CAP],
    ];
    let mut maximum = Vec::new();
    for index in 0..256 {
        maximum.extend(read_frame(&format!("r{index}"), &[]));
    }
    cases.push(maximum);
    for prefix in cases {
        let stop = prefix.len();
        let mut bytes = prefix;
        bytes.extend(b"never admitted caller bytes");
        let mut input = TailGuard {
            bytes,
            position: 0,
            stop,
        };
        let mut output = Vec::new();
        read_session::run(&mut input, &mut output).unwrap();
        assert_eq!(input.position, stop);
        assert_eq!(records(&output).last().unwrap()["kind"], "session-complete");
    }
}

#[test]
fn crlf_delimiter_counts_both_bytes_at_exact_frame_boundary() {
    let mut exact = wire(json!({"protocolVersion":1,"kind":"close","id":"done"}));
    exact.pop();
    exact.resize(FRAME_CAP - 2, b' ');
    exact.extend(b"\r\n");
    assert_eq!(run(&exact).last().unwrap()["reason"], "close");
    exact.insert(FRAME_CAP - 2, b' ');
    expect_error(&exact, "FRAME_TOO_LARGE");
}

#[derive(Default)]
struct TransportState {
    consumed: Cell<usize>,
    flushes: Cell<usize>,
    output_failed: Cell<bool>,
}

struct OrderedReader {
    bytes: Vec<u8>,
    state: Rc<TransportState>,
    interrupted: bool,
    fail_at: Option<usize>,
}

impl Read for OrderedReader {
    fn read(&mut self, buffer: &mut [u8]) -> io::Result<usize> {
        let available = self.fill_buf()?;
        let count = available.len().min(buffer.len());
        buffer[..count].copy_from_slice(&available[..count]);
        self.consume(count);
        Ok(count)
    }
}

impl BufRead for OrderedReader {
    fn fill_buf(&mut self) -> io::Result<&[u8]> {
        assert!(
            !self.state.output_failed.get(),
            "input read after output fault"
        );
        let position = self.state.consumed.get();
        let preceding_frames = self.bytes[..position]
            .iter()
            .filter(|byte| **byte == b'\n')
            .count();
        assert!(
            self.state.flushes.get() > preceding_frames,
            "next input before complete previous flush"
        );
        if self.interrupted {
            self.interrupted = false;
            return Err(io::ErrorKind::Interrupted.into());
        }
        if self.fail_at == Some(position) {
            return Err(io::ErrorKind::ConnectionReset.into());
        }
        if position == self.bytes.len() {
            return Ok(&[]);
        }
        Ok(&self.bytes[position..position + 1])
    }
    fn consume(&mut self, amount: usize) {
        self.state.consumed.set(self.state.consumed.get() + amount);
    }
}

struct FaultWriter {
    bytes: Vec<u8>,
    state: Rc<TransportState>,
    fail_flush: Option<usize>,
    fail_write_after: Option<usize>,
    zero: bool,
}

impl Write for FaultWriter {
    fn write(&mut self, buffer: &[u8]) -> io::Result<usize> {
        assert!(
            !self.state.output_failed.get(),
            "output continued after fault"
        );
        if self
            .fail_write_after
            .is_some_and(|limit| self.bytes.len() >= limit)
        {
            self.state.output_failed.set(true);
            return if self.zero {
                Ok(0)
            } else {
                Err(io::ErrorKind::BrokenPipe.into())
            };
        }
        let count = buffer.len().min(3).min(
            self.fail_write_after
                .map_or(usize::MAX, |limit| limit - self.bytes.len()),
        );
        self.bytes.extend(&buffer[..count]);
        Ok(count)
    }
    fn flush(&mut self) -> io::Result<()> {
        let next = self.state.flushes.get() + 1;
        if self.fail_flush == Some(next) {
            self.state.output_failed.set(true);
            return Err(io::ErrorKind::BrokenPipe.into());
        }
        self.state.flushes.set(next);
        Ok(())
    }
}

fn transports(bytes: Vec<u8>) -> (OrderedReader, FaultWriter) {
    let state = Rc::new(TransportState::default());
    (
        OrderedReader {
            bytes,
            state: Rc::clone(&state),
            interrupted: false,
            fail_at: None,
        },
        FaultWriter {
            bytes: Vec::new(),
            state,
            fail_flush: None,
            fail_write_after: None,
            zero: false,
        },
    )
}

#[test]
fn actual_short_writes_interrupted_reads_and_flush_order() {
    let mut bytes = read_frame("r1", &[]);
    bytes.extend(read_frame("r2", &[]));
    let (mut input, mut output) = transports(bytes);
    input.interrupted = true;
    let outcome = read_session::run(&mut input, &mut output).unwrap();
    assert_eq!(
        (outcome.frames, outcome.results, outcome.exit_status),
        (2, 2, 0)
    );
    assert_eq!(output.state.flushes.get(), 4);
    assert_eq!(records(&output.bytes).last().unwrap()["results"], 2);
}

#[test]
fn actual_input_faults_override_pending_truncation_and_count_only_started_frames() {
    for (bytes, at, frames) in [(Vec::new(), 0, 0), (b"{\"id\":".to_vec(), 6, 1)] {
        let (mut input, mut output) = transports(bytes);
        input.fail_at = Some(at);
        let outcome = read_session::run(&mut input, &mut output).unwrap();
        assert_eq!(
            (outcome.frames, outcome.results, outcome.exit_status),
            (frames, 0, 1)
        );
        let values = records(&output.bytes);
        assert_eq!(values[1]["code"], "INPUT_IO");
        assert_eq!(values[2]["reason"], "input-error");
        assert_eq!(values[2]["frames"], frames);
        assert_eq!(values[2]["results"], 0);
    }
}

#[test]
fn actual_output_faults_stop_all_further_input_in_every_lifecycle_position() {
    let first = read_frame("r1", &[]);
    let mut two = first.clone();
    two.extend(read_frame("r2", &[]));
    for flush in 1..=4 {
        let (mut input, mut output) = transports(two.clone());
        output.fail_flush = Some(flush);
        let error = read_session::run(&mut input, &mut output).unwrap_err();
        assert_eq!(
            (error.frames, error.results),
            match flush {
                1 => (0, 0),
                2 => (1, 0),
                3 => (2, 1),
                _ => (2, 2),
            }
        );
        assert!(output.state.output_failed.get());
        assert_eq!(
            output.state.consumed.get(),
            match flush {
                1 => 0,
                2 => first.len(),
                _ => two.len(),
            }
        );
        if flush == 2 {
            // A whole visible result remains incomplete transport when flush fails.
            assert_eq!(
                records(&output.bytes).last().unwrap()["kind"],
                "read-result"
            );
        }
    }
    for zero in [false, true] {
        for after in [0, 17] {
            let (mut input, mut output) = transports(two.clone());
            output.fail_write_after = Some(after);
            output.zero = zero;
            let error = read_session::run(&mut input, &mut output).unwrap_err();
            assert_eq!((error.frames, error.results), (0, 0));
            assert_eq!(
                error.source.kind(),
                if zero {
                    io::ErrorKind::WriteZero
                } else {
                    io::ErrorKind::BrokenPipe
                }
            );
            assert!(output.state.output_failed.get());
            assert_eq!(input.state.consumed.get(), 0);
        }
    }
    let mut baseline = Vec::new();
    read_session::run(&mut Cursor::new(&two), &mut baseline).unwrap();
    let ends: Vec<usize> = baseline
        .iter()
        .enumerate()
        .filter_map(|(at, byte)| (*byte == b'\n').then_some(at + 1))
        .collect();
    for phase in 1..=3 {
        for zero in [false, true] {
            let (mut input, mut output) = transports(two.clone());
            output.fail_write_after = Some(ends[phase - 1] + 7);
            output.zero = zero;
            let error = read_session::run(&mut input, &mut output).unwrap_err();
            assert_eq!(
                (error.frames, error.results),
                match phase {
                    1 => (1, 0),
                    2 => (2, 1),
                    _ => (2, 2),
                }
            );
            assert_eq!(
                input.state.consumed.get(),
                if phase == 1 { first.len() } else { two.len() }
            );
            assert!(output.state.output_failed.get());
        }
    }
    let (mut input, mut output) = transports(b"{bad\nignored\n".to_vec());
    output.fail_flush = Some(2);
    let error = read_session::run(&mut input, &mut output).unwrap_err();
    assert_eq!((error.frames, error.results), (1, 0));
    assert_eq!(input.state.consumed.get(), 5);
    assert!(output.state.output_failed.get());
}

fn inventory(path: &Path) -> BTreeMap<OsString, (Vec<u8>, SystemTime, bool)> {
    fs::read_dir(path)
        .unwrap()
        .map(|entry| {
            let entry = entry.unwrap();
            let metadata = entry.metadata().unwrap();
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
fn actual_authored_cr3_results_match_direct_api_and_reset_every_request() {
    let directory = support::TempDir::new();
    let path = directory.path.join("雪 authored.cr3");
    fs::write(&path, support::fixture().bytes).unwrap();
    fs::write(directory.path.join("untouched.xmp"), b"retained marker").unwrap();
    let before = inventory(&directory.path);
    let path = path.to_str().unwrap();
    let requests: Vec<(&str, Vec<&str>)> = vec![
        (
            "selected",
            vec![
                "metadata", "read", "--tag", "ISO", "--values", "all", "--", path,
            ],
        ),
        (
            "budget",
            vec!["metadata", "read", "--max-bytes", "16", "--", path],
        ),
        (
            "usage",
            vec!["metadata", "read", "--output", "json", "--", path],
        ),
        ("fresh", vec!["metadata", "read", "--", path]),
        (
            "mixed",
            vec![
                "metadata",
                "read",
                "--",
                path,
                "missing-authored-session.cr3",
            ],
        ),
        ("literal", vec!["metadata", "read", "--", "--output"]),
    ];
    let mut bytes = Vec::new();
    for (id, tokens) in &requests {
        bytes.extend(read_frame(id, tokens));
    }
    let output = run(&bytes);
    assert_eq!(output.last().unwrap()["exitStatus"], 0);
    assert_eq!(output.last().unwrap()["results"], requests.len());
    let mut statuses = Vec::new();
    for ((id, tokens), row) in requests.iter().zip(output.iter().skip(1)) {
        let native: Vec<OsString> = tokens.iter().map(OsString::from).collect();
        let expected = read_request::execute(id, &native);
        assert_eq!(row["result"], serde_json::to_value(&expected).unwrap());
        statuses.push(expected.summary.exit_status);
        assert!(expected.summary.artifacts.is_empty());
        for file in &expected.files {
            assert!(!file.effects.changed);
            assert!(!file.effects.publication_may_have_occurred);
            assert!(!file.effects.cleanup_pending);
            assert!(file.effects.recovery_ids.is_empty());
        }
    }
    assert_eq!(statuses, [0, 1, 2, 0, 3, 1]);
    assert_eq!(inventory(&directory.path), before);
}
