//! Actual subprocess pipes; watchdogs and capture caps belong only to this harness.
#[allow(dead_code)]
mod support;

use imageinfo::{read_request, read_session};
use serde_json::{Value, json};
use std::{
    ffi::OsString,
    fs,
    io::{self, BufRead, BufReader, Read, Write},
    path::Path,
    process::{Child, ChildStdin, Command, ExitStatus, Stdio},
    sync::mpsc::{self, Receiver},
    thread,
    time::{Duration, Instant},
};

const WATCHDOG: Duration = Duration::from_secs(30);
const CAPTURE_BYTES: usize = 24 * 1024 * 1024;
const STDERR_BYTES: usize = 8192;

struct Process {
    child: Child,
    input: Option<ChildStdin>,
    output: Receiver<Result<Option<Vec<u8>>, String>>,
    errors: Receiver<Result<Vec<u8>, String>>,
}

impl Process {
    fn start(args: &[&str], cwd: Option<&Path>, broken_stdout: bool) -> Self {
        let mut command = Command::new(env!("CARGO_BIN_EXE_imageinfo"));
        command
            .args(args)
            .stdin(Stdio::piped())
            .stderr(Stdio::piped())
            .env("NO_COLOR", "1")
            .env("PAGER", "imageinfo-must-not-run-a-pager")
            .env("EXIFTOOL_HOME", "imageinfo-must-not-load-config");
        if let Some(cwd) = cwd {
            command.current_dir(cwd);
        }
        if broken_stdout {
            // Close the reader before spawning, so even the ready write fails.
            let (reader, writer) = io::pipe().unwrap();
            drop(reader);
            command.stdout(writer);
        } else {
            command.stdout(Stdio::piped());
        }
        let mut child = command.spawn().unwrap();
        let input = child.stdin.take();
        let stdout = child.stdout.take();
        let stderr = child.stderr.take().unwrap();
        let (output_tx, output) = mpsc::channel();
        thread::spawn(move || {
            let Some(stdout) = stdout else {
                let _ = output_tx.send(Ok(None));
                return;
            };
            let mut reader = BufReader::new(stdout);
            let mut total = 0;
            loop {
                let mut bytes = Vec::new();
                let limit = read_session::MAX_OUTPUT_FRAME_BYTES + 1;
                let result = (&mut reader)
                    .take(limit as u64)
                    .read_until(b'\n', &mut bytes);
                if let Err(error) = result {
                    let _ = output_tx.send(Err(error.to_string()));
                    return;
                }
                total += bytes.len();
                if bytes.len() > read_session::MAX_OUTPUT_FRAME_BYTES || total > CAPTURE_BYTES {
                    let _ = output_tx.send(Err("stdout capture limit exceeded".into()));
                    return;
                }
                if bytes.is_empty() {
                    let _ = output_tx.send(Ok(None));
                    return;
                }
                if output_tx.send(Ok(Some(bytes))).is_err() {
                    return;
                }
            }
        });
        let (error_tx, errors) = mpsc::channel();
        thread::spawn(move || {
            let mut bytes = Vec::new();
            let result = stderr
                .take((STDERR_BYTES + 1) as u64)
                .read_to_end(&mut bytes);
            let result = match result {
                Err(error) => Err(error.to_string()),
                Ok(_) if bytes.len() > STDERR_BYTES => Err("stderr capture limit exceeded".into()),
                Ok(_) => Ok(bytes),
            };
            let _ = error_tx.send(result);
        });
        Self {
            child,
            input,
            output,
            errors,
        }
    }

    fn session(cwd: Option<&Path>) -> Self {
        Self::start(&["session", "read"], cwd, false)
    }

    fn frame(&self) -> Value {
        let bytes = self
            .output
            .recv_timeout(WATCHDOG)
            .expect("stdout watchdog")
            .expect("bounded stdout")
            .expect("expected another frame");
        assert_eq!(bytes.last(), Some(&b'\n'));
        assert!(!bytes.contains(&b'\r'), "output must use canonical LF");
        serde_json::from_slice(&bytes).expect("complete JSON frame")
    }

    fn ready(&self) {
        let ready = self.frame();
        assert_eq!(ready["kind"], "session-ready");
        assert_eq!(ready["protocolVersion"], 1);
        assert_eq!(ready["allowApply"], false);
        assert_eq!(ready["limits"]["maxQueuedRequests"], 0);
    }

    fn send(&mut self, bytes: &[u8]) {
        self.input.as_mut().unwrap().write_all(bytes).unwrap();
        self.input.as_mut().unwrap().flush().unwrap();
    }

    fn send_large(&mut self, bytes: Vec<u8>) -> Receiver<(io::Result<()>, ChildStdin)> {
        let mut input = self.input.take().unwrap();
        let (tx, rx) = mpsc::channel();
        thread::spawn(move || {
            let result = input.write_all(&bytes).and_then(|()| input.flush());
            let _ = tx.send((result, input));
        });
        rx
    }

    fn retain_input(&mut self, writer: Receiver<(io::Result<()>, ChildStdin)>) {
        let (result, input) = writer.recv_timeout(WATCHDOG).expect("stdin watchdog");
        result.unwrap();
        self.input = Some(input);
    }

    fn finish(&mut self, expected: i32) -> Vec<u8> {
        let status = wait(&mut self.child);
        assert_eq!(status.code(), Some(expected));
        assert!(
            self.output
                .recv_timeout(WATCHDOG)
                .expect("stdout EOF watchdog")
                .expect("bounded stdout")
                .is_none(),
            "unexpected trailing stdout"
        );
        self.errors
            .recv_timeout(WATCHDOG)
            .expect("stderr watchdog")
            .expect("bounded stderr")
    }
}

impl Drop for Process {
    fn drop(&mut self) {
        self.input.take();
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

fn wait(child: &mut Child) -> ExitStatus {
    let started = Instant::now();
    loop {
        if let Some(status) = child.try_wait().unwrap() {
            return status;
        }
        assert!(started.elapsed() < WATCHDOG, "child exit watchdog");
        // Polling the watchdog establishes no product timing or ordering claim.
        thread::sleep(Duration::from_millis(10));
    }
}

fn read(id: &str, tokens: &[&str]) -> Vec<u8> {
    format!(
        "{}\n",
        json!({"protocolVersion":1,"kind":"read","id":id,"tokens":tokens})
    )
    .into_bytes()
}

fn close(id: &str) -> Vec<u8> {
    format!("{}\n", json!({"protocolVersion":1,"kind":"close","id":id})).into_bytes()
}

fn completion(frame: Value, reason: &str, frames: usize, results: usize, status: u8) {
    assert_eq!(frame["kind"], "session-complete");
    assert_eq!(frame["reason"], reason);
    assert_eq!(frame["frames"], frames);
    assert_eq!(frame["results"], results);
    assert_eq!(frame["exitStatus"], status);
}

#[test]
fn open_stdin_ready_and_results_flush_with_native_request_isolation() {
    let dir = support::TempDir::new();
    let path = dir.path.join("réad-116.cr3");
    let sidecar = dir.path.join("réad-116.xmp");
    let bytes = support::fixture().bytes;
    fs::write(&path, &bytes).unwrap();
    fs::write(&sidecar, b"authored sidecar must remain untouched").unwrap();
    let before: Vec<_> = [&path, &sidecar]
        .into_iter()
        .map(|path| {
            let metadata = fs::metadata(path).unwrap();
            (
                fs::read(path).unwrap(),
                metadata.modified().unwrap(),
                metadata.permissions().readonly(),
            )
        })
        .collect();
    let mut process = Process::session(Some(&dir.path));
    process.ready(); // No input byte has been sent and stdin is still open.
    let source = path.to_str().unwrap();
    let missing = dir.path.join("missing.cr3");
    let missing = missing.to_str().unwrap();
    let cases: Vec<(&str, Vec<&str>, u8)> = vec![
        (
            "selected",
            vec![
                "metadata", "read", "--tag", "ISO", "--values", "all", "--", source,
            ],
            0,
        ),
        (
            "budget",
            vec!["metadata", "read", "--max-bytes", "1", "--", source],
            1,
        ),
        ("missing", vec!["metadata", "read", "--", missing], 1),
        ("usage", vec!["metadata", "read", "--bogus", source], 2),
        ("nested", vec!["session", "read"], 2),
        ("nonread", vec!["binary", "list", source], 2),
        (
            "selector",
            vec!["metadata", "read", "--output=json", source],
            2,
        ),
        ("mixed", vec!["metadata", "read", "--", source, missing], 3),
        ("fresh", vec!["metadata", "read", "--", source], 0),
    ];
    for (id, tokens, status) in &cases {
        let mut input = read(id, tokens);
        if *id == "selected" {
            input.insert(input.len() - 1, b'\r');
        }
        process.send(&input);
        let frame = process.frame(); // Receive LF before sending the next request.
        assert_eq!(frame["kind"], "read-result");
        assert_eq!(frame["id"], *id);
        let native: Vec<_> = tokens.iter().map(OsString::from).collect();
        assert_eq!(
            frame["result"],
            serde_json::to_value(read_request::execute(id, &native)).unwrap()
        );
        assert_eq!(frame["result"]["summary"]["exitStatus"], *status);
        if *id == "nested" {
            assert_eq!(
                frame["result"]["request"]["issues"][0]["code"],
                "REQUEST_OPERATION_UNSUPPORTED"
            );
        }
    }
    // Relative Unicode input uses startup cwd.
    process.send(&read(
        "relative",
        &["metadata", "read", "--", "réad-116.cr3"],
    ));
    assert_eq!(process.frame()["result"]["summary"]["exitStatus"], 0);
    let mut tail = close("done");
    tail.extend(read("forbidden", &["session", "read"]));
    tail.extend(b"{malformed\n");
    process.send(&tail);
    let done = process.frame();
    assert_eq!(done["closeId"], "done");
    completion(done, "close", cases.len() + 2, cases.len() + 1, 0);
    assert!(process.finish(0).is_empty()); // Parent still owns open stdin.
    for (index, path) in [&path, &sidecar].into_iter().enumerate() {
        let metadata = fs::metadata(path).unwrap();
        assert_eq!(
            before[index],
            (
                fs::read(path).unwrap(),
                metadata.modified().unwrap(),
                metadata.permissions().readonly()
            )
        );
    }
    assert_eq!(fs::read_dir(&dir.path).unwrap().count(), 2);
}

#[test]
fn clean_pipe_eof_is_distinct_from_unterminated_final_input() {
    for (input, status, code) in [
        (b"".as_slice(), 0, None),
        (b"{}".as_slice(), 2, Some("FRAME_TRUNCATED")),
    ] {
        let mut process = Process::session(None);
        process.ready();
        process.send(input);
        process.input.take();
        if let Some(code) = code {
            assert_eq!(process.frame()["code"], code);
        }
        completion(
            process.frame(),
            if status == 0 { "eof" } else { "protocol-error" },
            usize::from(!input.is_empty()),
            0,
            status,
        );
        assert!(process.finish(i32::from(status)).is_empty());
    }
}

#[test]
fn fatal_pipe_frames_keep_prior_result_and_never_emit_tail_results() {
    for (bad, code) in [
        (b"{broken\n".to_vec(), "FRAME_JSON"),
        (vec![0xff, b'\n'], "FRAME_ENCODING"),
        (
            b"{\"protocolVersion\":2,\"kind\":\"close\",\"id\":\"bad\"}\n".to_vec(),
            "FRAME_SCHEMA",
        ),
        (
            b"{\"protocolVersion\":1,\"kind\":\"close\",\"id\":\"first\"}\n".to_vec(),
            "DUPLICATE_ID",
        ),
        (
            b"{\"protocolVersion\":1,\"kind\":\"close\",\"id\":\"bad\",\"extra\":true}\n".to_vec(),
            "FRAME_SCHEMA",
        ),
    ] {
        let mut process = Process::session(None);
        process.ready();
        process.send(&read("first", &[]));
        assert_eq!(process.frame()["id"], "first");
        let mut input = bad;
        input.extend(read("must-not-dispatch", &[]));
        process.send(&input);
        let error = process.frame();
        assert_eq!(error["kind"], "protocol-error");
        assert_eq!(error["code"], code);
        assert_eq!(error["id"], Value::Null);
        completion(process.frame(), "protocol-error", 2, 1, 2);
        assert!(process.finish(2).is_empty());
    }
    let mut fresh = Process::session(None);
    fresh.ready();
    fresh.send(&read("first", &[]));
    assert_eq!(fresh.frame()["id"], "first");
    fresh.send(&close("again"));
    completion(fresh.frame(), "close", 2, 1, 0);
    assert!(fresh.finish(0).is_empty());
}

#[test]
fn exact_frame_caps_count_crlf_and_oversize_does_not_wait_for_lf_or_eof() {
    for crlf in [false, true] {
        let mut process = Process::session(None);
        process.ready();
        let mut input = close("exact");
        input.pop();
        input.resize(
            read_session::MAX_INPUT_FRAME_BYTES - if crlf { 2 } else { 1 },
            b' ',
        );
        if crlf {
            input.push(b'\r');
        }
        input.push(b'\n');
        assert_eq!(input.len(), read_session::MAX_INPUT_FRAME_BYTES);
        let writer = process.send_large(input);
        completion(process.frame(), "close", 1, 0, 0);
        process.retain_input(writer);
        assert!(process.finish(0).is_empty());
    }
    let mut process = Process::session(None);
    process.ready();
    let writer = process.send_large(vec![b' '; read_session::MAX_INPUT_FRAME_BYTES]);
    assert_eq!(process.frame()["code"], "FRAME_TOO_LARGE");
    completion(process.frame(), "protocol-error", 1, 0, 2);
    process.retain_input(writer); // No LF or EOF supplied; parent retains stdin.
    assert!(process.finish(2).is_empty());
}

#[test]
fn frame_limit_finishes_with_open_stdin_and_queued_tail_has_no_result() {
    let mut process = Process::session(None);
    process.ready();
    let mut input = Vec::new();
    for index in 0..=read_session::MAX_FRAMES {
        input.extend(read(&format!("r{index}"), &[]));
    }
    let writer = process.send_large(input);
    for index in 0..read_session::MAX_FRAMES {
        let result = process.frame();
        assert_eq!(result["kind"], "read-result");
        assert_eq!(result["id"], format!("r{index}"));
        assert_eq!(result["result"]["summary"]["exitStatus"], 2);
    }
    completion(
        process.frame(),
        "limit",
        read_session::MAX_FRAMES,
        read_session::MAX_FRAMES,
        0,
    );
    // The complete tail fits stdin's ordinary pipe buffering on supported runners;
    // no claim is made about which bytes the OS or StdinLock physically fetched.
    let (result, input) = writer.recv_timeout(WATCHDOG).expect("stdin watchdog");
    if let Err(error) = result {
        assert_eq!(error.kind(), io::ErrorKind::BrokenPipe);
    }
    process.input = Some(input);
    assert!(process.finish(0).is_empty());
}

#[test]
fn closed_stdout_before_spawn_returns_one_without_waiting_for_stdin() {
    let mut process = Process::start(&["session", "read"], None, true);
    let errors = process.finish(1);
    assert!(errors.len() <= 512);
    assert!(
        String::from_utf8(errors)
            .unwrap()
            .contains("OUTPUT_INCOMPLETE")
    );
}

#[test]
fn stdout_closed_after_ready_stops_on_the_next_result_with_stdin_open() {
    // Retain the actual read end so it can be closed at a deterministic boundary.
    let (mut reader, writer) = io::pipe().unwrap();
    let mut child = Command::new(env!("CARGO_BIN_EXE_imageinfo"))
        .args(["session", "read"])
        .stdin(Stdio::piped())
        .stdout(writer)
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    let (tx, rx) = mpsc::channel();
    thread::spawn(move || {
        let mut ready = Vec::new();
        // Read exactly through LF, with no reader buffer retaining the endpoint.
        for _ in 0..4096 {
            let mut byte = [0];
            reader.read_exact(&mut byte).unwrap();
            ready.push(byte[0]);
            if byte[0] == b'\n' {
                break;
            }
        }
        drop(reader);
        let _ = tx.send(ready);
    });
    let guard = ChildGuard(&mut child);
    let ready: Value = serde_json::from_slice(&rx.recv_timeout(WATCHDOG).unwrap()).unwrap();
    assert_eq!(ready["kind"], "session-ready");
    let mut stdin = guard.0.stdin.take().unwrap();
    stdin.write_all(&read("output-failure", &[])).unwrap();
    assert_eq!(wait(guard.0).code(), Some(1));
    let mut errors = Vec::new();
    guard
        .0
        .stderr
        .take()
        .unwrap()
        .take(513)
        .read_to_end(&mut errors)
        .unwrap();
    assert!(errors.len() <= 512);
    let errors = String::from_utf8(errors).unwrap();
    assert!(errors.contains("OUTPUT_INCOMPLETE"));
    assert!(!errors.contains("output-failure"));
}

// A guard also covers the tests that supply their own pipe endpoint.
struct ChildGuard<'a>(&'a mut Child);
impl Drop for ChildGuard<'_> {
    fn drop(&mut self) {
        let _ = self.0.kill();
        let _ = self.0.wait();
    }
}

#[test]
fn large_result_survives_a_paused_then_resumed_pipe_consumer() {
    let dir = support::TempDir::new();
    let path = dir.path.join("large-authored.cr3");
    let mut bytes = support::fixture_with_firmware(&"x".repeat(32768)).bytes;
    let kind = bytes.windows(4).position(|part| part == b"CMT3").unwrap();
    let box_size = u32::from_be_bytes(bytes[kind - 4..kind].try_into().unwrap()) as usize;
    let capacity = box_size - 8;
    // Bounded duplicate authored occurrences share one <=4096-byte allocation.
    // This expands a valid result without exceeding reader or result limits.
    let copies = 256_usize;
    let count = copies + 3;
    let mut tiff = b"II\x2a\0\x08\0\0\0".to_vec();
    tiff.extend((count as u16).to_le_bytes());
    tiff.resize(8 + 2 + count * 12 + 4, 0);
    let settings = tiff.len() as u32;
    tiff.extend([0; 110]);
    tiff[settings as usize..settings as usize + 2].copy_from_slice(&110_u16.to_le_bytes());
    tiff[settings as usize + 6..settings as usize + 8].copy_from_slice(&4_u16.to_le_bytes());
    let firmware = tiff.len() as u32;
    tiff.extend(std::iter::repeat_n(b'x', 4095));
    tiff.push(0);
    let lighting = tiff.len() as u32;
    tiff.extend([0; 60]);
    tiff[lighting as usize..lighting as usize + 4].copy_from_slice(&60_u32.to_le_bytes());
    for index in 0..count {
        let (tag, format, elements, offset) = if index == 0 {
            (1_u16, 3_u16, 55_u32, settings)
        } else if index <= copies {
            (7, 2, 4096, firmware)
        } else if index == copies + 1 {
            (16, 4, 1, 0x80000421)
        } else {
            (0x4018, 4, 15, lighting)
        };
        let at = 10 + index * 12;
        tiff[at..at + 2].copy_from_slice(&tag.to_le_bytes());
        tiff[at + 2..at + 4].copy_from_slice(&format.to_le_bytes());
        tiff[at + 4..at + 8].copy_from_slice(&elements.to_le_bytes());
        tiff[at + 8..at + 12].copy_from_slice(&offset.to_le_bytes());
    }
    assert!(tiff.len() < capacity);
    tiff.resize(capacity, 0);
    bytes[kind + 4..kind + 4 + capacity].copy_from_slice(&tiff);
    fs::write(&path, &bytes).unwrap();
    let tokens = [
        "metadata",
        "read",
        "--tag",
        "CanonFirmwareVersion",
        "--values",
        "all",
        "--",
        path.to_str().unwrap(),
    ];
    let native: Vec<_> = tokens.iter().map(OsString::from).collect();
    let expected = serde_json::to_value(read_request::execute("large", &native)).unwrap();
    assert_eq!(expected["summary"]["exitStatus"], 0);
    assert!(serde_json::to_vec(&expected).unwrap().len() > 3 * 1024 * 1024);

    let (reader, writer) = io::pipe().unwrap();
    let mut child = Command::new(env!("CARGO_BIN_EXE_imageinfo"))
        .args(["session", "read"])
        .stdin(Stdio::piped())
        .stdout(writer)
        .stderr(Stdio::null())
        .spawn()
        .unwrap();
    let guard = ChildGuard(&mut child);
    let (ready_tx, ready_rx) = mpsc::channel();
    let (paused_tx, paused_rx) = mpsc::channel();
    let (resume_tx, resume_rx) = mpsc::channel();
    let (done_tx, done_rx) = mpsc::channel();
    thread::spawn(move || {
        let result = (|| -> io::Result<Vec<u8>> {
            let mut reader = BufReader::new(reader);
            let mut output = Vec::new();
            reader.by_ref().take(4096).read_until(b'\n', &mut output)?;
            ready_tx.send(output.clone()).unwrap();
            let mut prefix = [0; 4096];
            reader.read_exact(&mut prefix)?;
            output.extend(prefix);
            paused_tx.send(()).unwrap();
            // An explicit handshake pauses/resumes the consumer. No sleep or
            // guessed pipe capacity is used as dispatch-order evidence.
            resume_rx.recv_timeout(WATCHDOG).expect("resume watchdog");
            reader
                .take((CAPTURE_BYTES + 1 - output.len()) as u64)
                .read_to_end(&mut output)?;
            assert!(output.len() <= CAPTURE_BYTES);
            Ok(output)
        })();
        let _ = done_tx.send(result);
    });
    let ready: Value = serde_json::from_slice(&ready_rx.recv_timeout(WATCHDOG).unwrap()).unwrap();
    assert_eq!(ready["kind"], "session-ready");
    let mut stdin = guard.0.stdin.take().unwrap();
    let mut input = read("large", &tokens);
    input.extend(read("next", &[]));
    input.extend(close("done"));
    stdin.write_all(&input).unwrap();
    paused_rx.recv_timeout(WATCHDOG).unwrap();
    resume_tx.send(()).unwrap();
    let output = done_rx
        .recv_timeout(WATCHDOG)
        .expect("large output watchdog")
        .unwrap();
    assert_eq!(wait(guard.0).code(), Some(0));
    assert_eq!(output.last(), Some(&b'\n'));
    assert!(!output.contains(&b'\r'));
    let frames: Vec<Value> = output
        .split(|byte| *byte == b'\n')
        .filter(|bytes| !bytes.is_empty())
        .map(|bytes| serde_json::from_slice(bytes).unwrap())
        .collect();
    assert_eq!(frames.len(), 4);
    assert_eq!(frames[1]["result"], expected);
    assert_eq!(frames[2]["id"], "next");
    completion(frames[3].clone(), "close", 3, 2, 0);
    assert_eq!(fs::read(&path).unwrap(), bytes);
}
