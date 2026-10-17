//! Finite concurrent read qualification; authored structural fixtures only.
#[allow(dead_code)]
mod support;

use imageinfo::{output::ResultEnvelope, read_request, read_session};
use serde_json::{Value, json};
use std::{
    ffi::OsString,
    fs,
    io::{self, BufRead, Cursor, Read, Write},
    path::Path,
    sync::{Arc, Condvar, Mutex},
    thread,
    time::{Duration, Instant},
};

const WORKERS: usize = 12;

struct Rendezvous {
    participants: usize,
    timeout: Duration,
    state: Mutex<([usize; 2], bool)>,
    changed: Condvar,
}
impl Rendezvous {
    fn new(participants: usize, timeout: Duration) -> Self {
        Self {
            participants,
            timeout,
            state: Mutex::new(([0; 2], false)),
            changed: Condvar::new(),
        }
    }
    fn arrive(&self, phase: usize) -> io::Result<()> {
        let deadline = Instant::now() + self.timeout;
        let mut state = self.state.lock().map_err(|_| io::ErrorKind::Other)?;
        if state.1 {
            return Err(io::ErrorKind::TimedOut.into());
        }
        state.0[phase] += 1;
        self.changed.notify_all();
        while state.0[phase] < self.participants && !state.1 {
            let Some(remaining) = deadline.checked_duration_since(Instant::now()) else {
                state.1 = true;
                self.changed.notify_all();
                return Err(io::ErrorKind::TimedOut.into());
            };
            state = self
                .changed
                .wait_timeout(state, remaining)
                .map_err(|_| io::ErrorKind::Other)?
                .0;
        }
        if state.1 {
            Err(io::ErrorKind::TimedOut.into())
        } else {
            Ok(())
        }
    }
}

// The first two flushes occur inside run: ready, then the first read-result.
// The latter retains the actual read record plus the session's ID set.
struct OverlapSink {
    gate: Arc<Rendezvous>,
    flushes: usize,
    bytes: Vec<u8>,
}
impl Write for OverlapSink {
    fn write(&mut self, bytes: &[u8]) -> io::Result<usize> {
        self.bytes.extend_from_slice(bytes);
        Ok(bytes.len())
    }
    fn flush(&mut self) -> io::Result<()> {
        if self.flushes < 2 {
            self.gate.arrive(self.flushes)?;
        }
        self.flushes += 1;
        Ok(())
    }
}

fn session_success(result: &Value, path: &Path, index: usize) {
    let (name, display, expected) = match index % 6 {
        0 => (
            "CanonFirmwareVersion",
            false,
            json!({"kind":"string","text":format!("Authored caller {index:02}")}),
        ),
        1 => (
            "ExposureTime",
            true,
            json!({"kind":"rational","numerator":"2","denominator":"500"}),
        ),
        2 => (
            "ImageWidth",
            false,
            json!({"kind":"integer","decimal":"8192"}),
        ),
        3 => (
            "CanonFirmwareVersion",
            true,
            json!({"kind":"string","text":format!("Authored caller {index:02}")}),
        ),
        _ => unreachable!("success oracle requires a successful authored case"),
    };
    assert_eq!(result["summary"]["exitStatus"], 0);
    let files = result["files"].as_array().unwrap();
    assert_eq!(files.len(), 1);
    assert_eq!(files[0]["path"], path.to_string_lossy().as_ref());
    assert_eq!(files[0]["state"], "read");
    let occurrences = files[0]["snapshot"]["occurrences"].as_array().unwrap();
    assert_eq!(occurrences.len(), 1);
    let occurrence = &occurrences[0];
    assert_eq!(occurrence["tag"]["name"], name, "session selected tag");
    assert_eq!(occurrence["values"]["raw"]["state"], "present");
    assert_eq!(occurrence["values"]["normalized"]["state"], "present");
    assert_eq!(occurrence["values"]["raw"]["value"], expected);
    assert_eq!(occurrence["values"]["normalized"]["value"], expected);
    assert_eq!(
        occurrence["values"]["display"]["state"],
        if display { "present" } else { "unavailable" },
        "session display view"
    );
}

#[test]
fn missing_overlap_participant_times_out_and_aborts_late_arrivals() {
    let gate = Arc::new(Rendezvous::new(2, Duration::from_millis(20)));
    let mut sink = OverlapSink {
        gate: Arc::clone(&gate),
        flushes: 0,
        bytes: Vec::new(),
    };
    assert_eq!(sink.flush().unwrap_err().kind(), io::ErrorKind::TimedOut);
    assert_eq!(gate.arrive(0).unwrap_err().kind(), io::ErrorKind::TimedOut);
    assert_eq!(gate.arrive(1).unwrap_err().kind(), io::ErrorKind::TimedOut);
    assert!(gate.state.lock().unwrap().1);
}

fn oracle_control() -> Value {
    json!({"summary":{"exitStatus":0},"files":[{"path":"oracle.cr3","state":"read","snapshot":{"occurrences":[{"tag":{"name":"ExposureTime"},"values":{"raw":{"state":"present","value":{"kind":"rational","numerator":"2","denominator":"500"}},"normalized":{"state":"present","value":{"kind":"rational","numerator":"2","denominator":"500"}},"display":{"state":"present"}}}]}}]})
}

#[test]
#[should_panic(expected = "session display view")]
fn forced_raw_session_view_is_rejected_by_oracle() {
    let mut control = oracle_control();
    session_success(&control, Path::new("oracle.cr3"), 1);
    control["files"][0]["snapshot"]["occurrences"][0]["values"]["display"]["state"] =
        json!("unavailable");
    session_success(&control, Path::new("oracle.cr3"), 1);
}

#[test]
#[should_panic(expected = "session selected tag")]
fn wrong_session_selector_is_rejected_by_oracle() {
    let mut control = oracle_control();
    session_success(&control, Path::new("oracle.cr3"), 1);
    control["files"][0]["snapshot"]["occurrences"][0]["tag"]["name"] = json!("ImageWidth");
    session_success(&control, Path::new("oracle.cr3"), 1);
}

fn tokens(path: &Path, options: &[&str]) -> Vec<OsString> {
    ["metadata", "read"]
        .into_iter()
        .chain(options.iter().copied())
        .chain(["--"])
        .map(OsString::from)
        .chain([path.as_os_str().to_owned()])
        .collect()
}

fn preserved(record: &ResultEnvelope) {
    assert!(record.summary.artifacts.is_empty());
    for file in &record.files {
        assert!(!file.effects.changed);
        assert!(!file.effects.publication_may_have_occurred);
        assert!(!file.effects.cleanup_pending);
        assert!(file.effects.recovery_ids.is_empty());
    }
}

fn selected(record: &ResultEnvelope, path: &Path, name: &str, display: bool) -> Value {
    assert_eq!(record.summary.exit_status, 0);
    assert!(record.request.issues.is_empty());
    assert_eq!(record.files.len(), 1);
    let file = &record.files[0];
    assert_eq!(file.path, path.to_string_lossy());
    assert_eq!(file.state, "read");
    assert_eq!(file.request_id, record.request_id);
    assert_eq!(file.input_id, "input-0");
    let snapshot = file.snapshot.as_ref().unwrap();
    assert_eq!(snapshot["id"], format!("{}-snapshot-0", record.request_id));
    let occurrences = snapshot["occurrences"].as_array().unwrap();
    assert_eq!(occurrences.len(), 1);
    let occurrence = &occurrences[0];
    assert_eq!(occurrence["tag"]["name"], name);
    assert_eq!(occurrence["values"]["raw"]["state"], "present");
    assert_eq!(
        occurrence["values"]["normalized"],
        occurrence["values"]["raw"]
    );
    assert_eq!(
        occurrence["values"]["display"]["state"],
        if display { "present" } else { "unavailable" }
    );
    preserved(record);
    occurrence["values"]["raw"]["value"].clone()
}

// A caller-owned sink with a recoverable injected failure. Each worker owns its
// own instance; changing the flag after a call checks that ownership survived.
#[derive(Default)]
struct Sink {
    fail: bool,
    bytes: Vec<u8>,
}
impl Write for Sink {
    fn write(&mut self, bytes: &[u8]) -> io::Result<usize> {
        if self.fail {
            Err(io::ErrorKind::BrokenPipe.into())
        } else {
            self.bytes.extend_from_slice(bytes);
            Ok(bytes.len())
        }
    }
    fn flush(&mut self) -> io::Result<()> {
        Ok(())
    }
}

struct Input {
    fail: bool,
    cursor: Cursor<Vec<u8>>,
}
impl Read for Input {
    fn read(&mut self, bytes: &mut [u8]) -> io::Result<usize> {
        if self.fail {
            Err(io::ErrorKind::Other.into())
        } else {
            self.cursor.read(bytes)
        }
    }
}
impl BufRead for Input {
    fn fill_buf(&mut self) -> io::Result<&[u8]> {
        if self.fail {
            Err(io::ErrorKind::Other.into())
        } else {
            self.cursor.fill_buf()
        }
    }
    fn consume(&mut self, count: usize) {
        self.cursor.consume(count);
    }
}

#[test]
fn twelve_concurrent_callers_keep_settings_errors_results_and_streams_local() {
    let directory = support::TempDir::new();
    let mut paths = Vec::new();
    let mut originals = Vec::new();
    for index in 0..WORKERS {
        let path = directory.path.join(format!("caller-{index}.cr3"));
        let bytes = support::fixture_with_firmware(&format!("Authored caller {index:02}")).bytes;
        fs::write(&path, &bytes).unwrap();
        originals.push((
            path.clone(),
            bytes,
            fs::metadata(&path).unwrap().modified().unwrap(),
        ));
        paths.push(path);
    }
    let gate = Arc::new(Rendezvous::new(WORKERS, Duration::from_secs(10)));
    let handles: Vec<_> = paths
        .iter()
        .cloned()
        .enumerate()
        .map(|(index, path)| {
            let gate = Arc::clone(&gate);
            thread::spawn(move || {
                let id = format!("parallel-{index}");
                let options: &[&str] = match index % 6 {
                    0 => &["--tag", "CanonFirmwareVersion", "--values", "raw"],
                    1 => &["--tag", "EXIF:ExposureTime", "--values", "all"],
                    2 => &["--tag", "EXIF:ImageWidth", "--values", "normalized"],
                    3 => &["--tag", "CanonFirmwareVersion", "--values", "display"],
                    4 => &["--max-bytes", "16"],
                    _ => &["--max-bytes", "8388609"],
                };
                let record = read_request::execute(&id, &tokens(&path, options));
                assert_eq!(record.request_id, id);
                match index % 6 {
                    0 | 3 => assert_eq!(
                        selected(&record, &path, "CanonFirmwareVersion", index % 6 == 3),
                        json!({"kind":"string","text":format!("Authored caller {index:02}")})
                    ),
                    1 => assert_eq!(
                        selected(&record, &path, "ExposureTime", true),
                        json!({"kind":"rational","numerator":"2","denominator":"500"})
                    ),
                    2 => assert_eq!(
                        selected(&record, &path, "ImageWidth", false),
                        json!({"kind":"integer","decimal":"8192"})
                    ),
                    4 => {
                        assert_eq!(record.summary.exit_status, 1);
                        assert_eq!(record.files.len(), 1);
                        assert_eq!(record.files[0].path, path.to_string_lossy());
                        assert_eq!(record.files[0].state, "failed");
                        assert!(record.files[0].snapshot.is_none());
                        assert_eq!(record.files[0].issues[0].code, "LIMIT_EXCEEDED");
                        assert!(record.request.issues.is_empty());
                    }
                    _ => {
                        assert_eq!(record.summary.exit_status, 2);
                        assert!(record.files.is_empty());
                        assert_eq!(record.request.issues[0].code, "REQUEST_LIMIT");
                    }
                }
                preserved(&record);
                // Every owned result remains alive across the next read;
                // no serial baseline produced the expected values above.
                let next = read_request::execute(
                    &format!("next-{index}"),
                    &tokens(&path, &["--tag", "CanonFirmwareVersion"]),
                );
                assert_eq!(
                    selected(&next, &path, "CanonFirmwareVersion", false),
                    json!({"kind":"string","text":format!("Authored caller {index:02}")})
                );
                let mut sink = Sink { fail: true, ..Sink::default() };
                assert_eq!(read_request::write_result(&mut sink, &record).unwrap_err().kind(), io::ErrorKind::BrokenPipe);
                sink.fail = false;
                read_request::write_result(&mut sink, &record).unwrap();
                assert_eq!(serde_json::from_slice::<Value>(&sink.bytes).unwrap()["requestId"], id);

                // Exercise independent session ownership/ID sets with the same
                // IDs in all callers. Each session's read settings differ.
                let frame = json!({"protocolVersion":1,"kind":"read","id":"shared-id","tokens":tokens(&path, options).iter().map(|s|s.to_str().unwrap()).collect::<Vec<_>>()});
                let input = format!("{frame}\n{{\"protocolVersion\":1,\"kind\":\"close\",\"id\":\"stop\"}}\ntail-{index}");
                let mut input = Cursor::new(input.into_bytes());
                let mut output = OverlapSink { gate, flushes: 0, bytes: Vec::new() };
                let outcome = read_session::run(&mut input, &mut output).unwrap();
                assert_eq!((outcome.reason, outcome.results, outcome.frames), ("close", 1, 2));
                let frames: Vec<Value> = output.bytes.split(|b| *b == b'\n').filter(|v| !v.is_empty()).map(|v| serde_json::from_slice(v).unwrap()).collect();
                assert_eq!(frames[1]["id"], "shared-id");
                let result = &frames[1]["result"];
                assert_eq!(result["requestId"], "shared-id");
                assert_eq!(result["summary"]["exitStatus"], record.summary.exit_status);
                if index % 6 < 4 {
                    session_success(result, &path, index);
                } else if index % 6 == 4 {
                    assert_eq!(result["files"][0]["issues"][0]["code"], "LIMIT_EXCEEDED");
                } else {
                    assert_eq!(result["request"]["issues"][0]["code"], "REQUEST_LIMIT");
                }
                let mut tail = String::new();
                input.read_to_string(&mut tail).unwrap();
                assert_eq!(tail, format!("tail-{index}"));
                output.write_all(b"caller-after-success").unwrap();

                let mut bad_input = Cursor::new(b"{}\ncaller-after-protocol-error".to_vec());
                let mut bad_output = Vec::new();
                let outcome = read_session::run(&mut bad_input, &mut bad_output).unwrap();
                assert_eq!((outcome.reason, outcome.exit_status), ("protocol-error", 2));
                let mut tail = String::new();
                bad_input.read_to_string(&mut tail).unwrap();
                assert_eq!(tail, "caller-after-protocol-error");
                bad_output.write_all(b"caller-after-protocol-error").unwrap();

                let mut input = Input { fail: true, cursor: Cursor::new(b"caller-after-input-error".to_vec()) };
                let mut output = Vec::new();
                assert_eq!(read_session::run(&mut input, &mut output).unwrap().reason, "input-error");
                input.fail = false;
                let mut tail = String::new();
                input.read_to_string(&mut tail).unwrap();
                assert_eq!(tail, "caller-after-input-error");
                output.write_all(b"caller-after-input-error").unwrap();

                let mut input = Cursor::new(b"caller-after-output-error".to_vec());
                let mut output = Sink { fail: true, ..Sink::default() };
                assert_eq!(read_session::run(&mut input, &mut output).unwrap_err().source.kind(), io::ErrorKind::BrokenPipe);
                assert_eq!(input.position(), 0);
                let mut tail = String::new();
                input.read_to_string(&mut tail).unwrap();
                assert_eq!(tail, "caller-after-output-error");
                output.fail = false;
                output.write_all(b"caller-after-output-error").unwrap();
                // Return both retained envelopes beyond the worker lifetime.
                (record, next)
            })
        })
        .collect();
    // Join every worker before propagating an assertion failure, so fixture
    // cleanup cannot race any surviving reader.
    let joined: Vec<_> = handles.into_iter().map(|h| h.join()).collect();
    let retained: Vec<_> = joined.into_iter().map(Result::unwrap).collect();
    let overlap = gate.state.lock().unwrap();
    assert_eq!(overlap.0, [WORKERS, WORKERS]);
    assert!(!overlap.1);
    drop(overlap);
    for (index, (_, next)) in retained.iter().enumerate() {
        assert_eq!(
            selected(next, &paths[index], "CanonFirmwareVersion", false),
            json!({"kind":"string","text":format!("Authored caller {index:02}")})
        );
    }
    for (path, bytes, modified) in &originals {
        assert_eq!(fs::read(path).unwrap(), *bytes);
        assert_eq!(fs::metadata(path).unwrap().modified().unwrap(), *modified);
    }
    assert_eq!(fs::read_dir(&directory.path).unwrap().count(), WORKERS);

    // Sequential same-path reads observe a deliberate caller edit after all
    // threads finish. The earlier owned snapshot stays unchanged; it held no
    // continuous source/name guard and does not promise one between reads.
    let old = &retained[0].1;
    fs::write(
        &paths[0],
        support::fixture_with_firmware("Authored later edit").bytes,
    )
    .unwrap();
    let later = read_request::execute(
        "later",
        &tokens(&paths[0], &["--tag", "CanonFirmwareVersion"]),
    );
    assert_eq!(
        selected(&later, &paths[0], "CanonFirmwareVersion", false),
        json!({"kind":"string","text":"Authored later edit"})
    );
    assert_eq!(
        selected(old, &paths[0], "CanonFirmwareVersion", false),
        json!({"kind":"string","text":"Authored caller 00"})
    );
}
