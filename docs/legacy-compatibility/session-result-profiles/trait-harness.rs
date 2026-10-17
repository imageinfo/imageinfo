//! Qualification-only caller-owned transport; never an OS-pipe observation.
use imageinfo::read_session;
use std::io::{self, BufRead, Cursor, Read, Write};

struct Input {
    bytes: Cursor<Vec<u8>>,
    fail: bool,
}
impl Read for Input {
    fn read(&mut self, out: &mut [u8]) -> io::Result<usize> {
        self.bytes.read(out)
    }
}
impl BufRead for Input {
    fn fill_buf(&mut self) -> io::Result<&[u8]> {
        if self.fail && self.bytes.position() as usize == self.bytes.get_ref().len() {
            Err(io::ErrorKind::Other.into())
        } else {
            self.bytes.fill_buf()
        }
    }
    fn consume(&mut self, count: usize) {
        self.bytes.consume(count);
    }
}
struct Output {
    bytes: Vec<u8>,
    flushes: usize,
    fail_flush: usize,
    fail_after: usize,
    zero: bool,
}
impl Write for Output {
    fn write(&mut self, value: &[u8]) -> io::Result<usize> {
        if self.bytes.len() >= self.fail_after {
            return if self.zero {
                Ok(0)
            } else {
                Err(io::ErrorKind::BrokenPipe.into())
            };
        }
        let count = value.len().min(3).min(self.fail_after - self.bytes.len());
        self.bytes.extend_from_slice(&value[..count]);
        Ok(count)
    }
    fn flush(&mut self) -> io::Result<()> {
        self.flushes += 1;
        if self.flushes == self.fail_flush {
            Err(io::ErrorKind::BrokenPipe.into())
        } else {
            Ok(())
        }
    }
}
fn main() {
    let args: Vec<String> = std::env::args().collect();
    let mode = &args[1];
    let data = match mode.as_str() {
        "input-empty" => Vec::new(),
        "input-partial" => b"{\"id\":".to_vec(),
        _ => b"{\"protocolVersion\":1,\"kind\":\"read\",\"id\":\"r1\",\"tokens\":[]}\n".to_vec(),
    };
    let mut input = Input {
        bytes: Cursor::new(data),
        fail: mode.starts_with("input-"),
    };
    let mut output = Output {
        bytes: Vec::new(),
        flushes: 0,
        fail_flush: mode
            .strip_prefix("flush-")
            .and_then(|n| n.parse().ok())
            .unwrap_or(0),
        fail_after: if mode.starts_with("write-") {
            17
        } else {
            usize::MAX
        },
        zero: mode == "write-zero",
    };
    let result = read_session::run(&mut input, &mut output);
    std::fs::write(&args[2], &output.bytes).unwrap();
    match result {
        Ok(value) => println!(
            "{{\"outcome\":\"complete\",\"frames\":{},\"results\":{},\"exitStatus\":{},\"reason\":\"{}\",\"consumed\":{}}}",
            value.frames,
            value.results,
            value.exit_status,
            value.reason,
            input.bytes.position()
        ),
        Err(value) => println!(
            "{{\"outcome\":\"output-incomplete\",\"frames\":{},\"results\":{},\"exitStatus\":1,\"errorKind\":\"{:?}\",\"consumed\":{}}}",
            value.frames,
            value.results,
            value.source.kind(),
            input.bytes.position()
        ),
    }
}
