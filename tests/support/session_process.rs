//! Shared unchanged #0116 actual process/pipe harness; test-only watchdogs.
use imageinfo::read_session;
use serde_json::{Value, json};
use std::{
    io::{self, BufRead, BufReader, Read, Write},
    path::Path,
    process::{Child, ChildStdin, Command, ExitStatus, Stdio},
    sync::mpsc::{self, Receiver},
    thread,
    time::{Duration, Instant},
};

pub(crate) const WATCHDOG: Duration = Duration::from_secs(30);
pub(crate) const CAPTURE_BYTES: usize = 24 * 1024 * 1024;
pub(crate) const STDERR_BYTES: usize = 8192;

pub(crate) struct Process {
    pub(crate) child: Child,
    pub(crate) input: Option<ChildStdin>,
    output: Receiver<Result<Option<Vec<u8>>, String>>,
    errors: Receiver<Result<Vec<u8>, String>>,
}

impl Process {
    pub(crate) fn start(args: &[&str], cwd: Option<&Path>, broken_stdout: bool) -> Self {
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

    pub(crate) fn session(cwd: Option<&Path>) -> Self {
        Self::start(&["session", "read"], cwd, false)
    }

    pub(crate) fn frame(&self) -> Value {
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

    pub(crate) fn ready(&self) {
        let ready = self.frame();
        assert_eq!(ready["kind"], "session-ready");
        assert_eq!(ready["protocolVersion"], 1);
        assert_eq!(ready["allowApply"], false);
        assert_eq!(ready["limits"]["maxQueuedRequests"], 0);
    }

    pub(crate) fn send(&mut self, bytes: &[u8]) {
        self.input.as_mut().unwrap().write_all(bytes).unwrap();
        self.input.as_mut().unwrap().flush().unwrap();
    }

    pub(crate) fn send_large(&mut self, bytes: Vec<u8>) -> Receiver<(io::Result<()>, ChildStdin)> {
        let mut input = self.input.take().unwrap();
        let (tx, rx) = mpsc::channel();
        thread::spawn(move || {
            let result = input.write_all(&bytes).and_then(|()| input.flush());
            let _ = tx.send((result, input));
        });
        rx
    }

    pub(crate) fn retain_input(&mut self, writer: Receiver<(io::Result<()>, ChildStdin)>) {
        let (result, input) = writer.recv_timeout(WATCHDOG).expect("stdin watchdog");
        result.unwrap();
        self.input = Some(input);
    }

    pub(crate) fn finish(&mut self, expected: i32) -> Vec<u8> {
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

pub(crate) fn wait(child: &mut Child) -> ExitStatus {
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

pub(crate) fn read(id: &str, tokens: &[&str]) -> Vec<u8> {
    format!(
        "{}\n",
        json!({"protocolVersion":1,"kind":"read","id":id,"tokens":tokens})
    )
    .into_bytes()
}

pub(crate) fn close(id: &str) -> Vec<u8> {
    format!("{}\n", json!({"protocolVersion":1,"kind":"close","id":id})).into_bytes()
}

pub(crate) fn completion(frame: Value, reason: &str, frames: usize, results: usize, status: u8) {
    assert_eq!(frame["kind"], "session-complete");
    assert_eq!(frame["reason"], reason);
    assert_eq!(frame["frames"], frames);
    assert_eq!(frame["results"], results);
    assert_eq!(frame["exitStatus"], status);
}
