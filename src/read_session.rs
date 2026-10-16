//! Opt-in bounded JSONL sessions over caller-owned buffered input and output.
//!
//! This transport only dispatches [`crate::read_request::execute`]. It does not
//! open streams, change the working directory, queue work or add CLI syntax.
use crate::read_request;
use serde::{Deserialize, Deserializer, Serialize, de::Visitor};
use serde_json::{Value, json};
use std::{
    collections::{BTreeMap, BTreeSet},
    ffi::OsString,
    fmt,
    io::{self, BufRead, Write},
};

pub const MAX_INPUT_FRAME_BYTES: usize = 524_288;
pub const MAX_OUTPUT_FRAME_BYTES: usize = read_request::MAX_RESULT_BYTES + 512;
pub const MAX_FRAMES: usize = 256;
pub const MAX_DEPTH: usize = 8;

/// A completely flushed session completion, including protocol/input failures.
#[derive(Debug, PartialEq, Eq)]
pub struct SessionOutcome {
    pub exit_status: u8,
    pub frames: usize,
    pub results: usize,
    /// One of `eof`, `close`, `limit`, `protocol-error`, or `input-error`.
    pub reason: &'static str,
}

/// Output transport failed: status 1, with no promised final frame or replay.
#[derive(Debug)]
pub struct SessionError {
    pub source: io::Error,
    pub frames: usize,
    /// Only read-result frames whose flush returned successfully are counted.
    pub results: usize,
}
impl fmt::Display for SessionError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "read-session output transport failed: {}", self.source)
    }
}
impl std::error::Error for SessionError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        Some(&self.source)
    }
}

enum Frame {
    Eof,
    Complete(Vec<u8>),
    Error(&'static str, bool),
}

fn frame(input: &mut impl BufRead) -> Frame {
    let mut bytes = Vec::new();
    loop {
        let available = match input.fill_buf() {
            Ok(available) => available,
            Err(error) if error.kind() == io::ErrorKind::Interrupted => continue,
            Err(_) => return Frame::Error("INPUT_IO", !bytes.is_empty()),
        };
        if available.is_empty() {
            return if bytes.is_empty() {
                Frame::Eof
            } else {
                Frame::Error("FRAME_TRUNCATED", true)
            };
        }
        let available = &available[..available.len().min(MAX_INPUT_FRAME_BYTES - bytes.len())];
        let length = available
            .iter()
            .position(|byte| *byte == b'\n')
            .map_or(available.len(), |end| end + 1);
        bytes.extend_from_slice(&available[..length]);
        input.consume(length);
        if bytes.last() == Some(&b'\n') {
            return Frame::Complete(bytes);
        }
        // At this many non-LF bytes even the next LF would exceed the cap.
        if bytes.len() == MAX_INPUT_FRAME_BYTES {
            return Frame::Error("FRAME_TOO_LARGE", true);
        }
    }
}

// Values retain decoded string bytes until *all* syntax and member-uniqueness
// checks finish. serde_json's byte visitor preserves lone surrogates as WTF-8;
// ordinary String/Value decoding would reject them too early for v1 precedence.
enum Json {
    Scalar(Value),
    String(Vec<u8>),
    Array(Vec<Json>),
    Object(BTreeMap<Vec<u8>, Json>),
}
impl Json {
    fn value(self) -> Value {
        match self {
            Self::Scalar(value) => value,
            Self::String(bytes) => {
                Value::String(String::from_utf8(bytes).expect("scalars checked"))
            }
            Self::Array(values) => Value::Array(values.into_iter().map(Self::value).collect()),
            Self::Object(values) => Value::Object(
                values
                    .into_iter()
                    .map(|(key, value)| {
                        (
                            String::from_utf8(key).expect("scalars checked"),
                            value.value(),
                        )
                    })
                    .collect(),
            ),
        }
    }
}

struct StringBytes(Vec<u8>);
impl<'de> Deserialize<'de> for StringBytes {
    fn deserialize<D: Deserializer<'de>>(deserializer: D) -> Result<Self, D::Error> {
        struct BytesVisitor;
        impl Visitor<'_> for BytesVisitor {
            type Value = StringBytes;
            fn expecting(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
                f.write_str("a JSON string")
            }
            fn visit_bytes<E: serde::de::Error>(self, value: &[u8]) -> Result<Self::Value, E> {
                Ok(StringBytes(value.to_vec()))
            }
        }
        deserializer.deserialize_bytes(BytesVisitor)
    }
}

struct Parser<'a> {
    bytes: &'a [u8],
    at: usize,
    invalid_scalar: bool,
    number_out_of_range: bool,
}
impl Parser<'_> {
    fn whitespace(&mut self) {
        while self
            .bytes
            .get(self.at)
            .is_some_and(|byte| b" \t\r\n".contains(byte))
        {
            self.at += 1;
        }
    }
    fn string(&mut self) -> Result<Vec<u8>, ()> {
        let start = self.at;
        self.at += 1;
        let mut escaped = false;
        while let Some(&byte) = self.bytes.get(self.at) {
            self.at += 1;
            if escaped {
                escaped = false;
            } else if byte == b'\\' {
                escaped = true;
            } else if byte < 0x20 {
                // The byte visitor permits raw controls as well as WTF-8. JSON
                // syntax must still reject those controls before scalar checks.
                return Err(());
            } else if byte == b'"' {
                let StringBytes(value) =
                    serde_json::from_slice(&self.bytes[start..self.at]).map_err(|_| ())?;
                self.invalid_scalar |= std::str::from_utf8(&value).is_err();
                return Ok(value);
            }
        }
        Err(())
    }
    fn value(&mut self) -> Result<Json, ()> {
        self.whitespace();
        match self.bytes.get(self.at).copied().ok_or(())? {
            b'"' => self.string().map(Json::String),
            b'{' => {
                self.at += 1;
                self.whitespace();
                let mut members = BTreeMap::new();
                if self.bytes.get(self.at) == Some(&b'}') {
                    self.at += 1;
                    return Ok(Json::Object(members));
                }
                loop {
                    self.whitespace();
                    if self.bytes.get(self.at) != Some(&b'"') {
                        return Err(());
                    }
                    let key = self.string()?;
                    self.whitespace();
                    if self.bytes.get(self.at) != Some(&b':') {
                        return Err(());
                    }
                    self.at += 1;
                    let value = self.value()?;
                    if members.insert(key, value).is_some() {
                        return Err(());
                    }
                    self.whitespace();
                    match self.bytes.get(self.at) {
                        Some(b',') => self.at += 1,
                        Some(b'}') => {
                            self.at += 1;
                            return Ok(Json::Object(members));
                        }
                        _ => return Err(()),
                    }
                }
            }
            b'[' => {
                self.at += 1;
                self.whitespace();
                let mut values = Vec::new();
                if self.bytes.get(self.at) == Some(&b']') {
                    self.at += 1;
                    return Ok(Json::Array(values));
                }
                loop {
                    values.push(self.value()?);
                    self.whitespace();
                    match self.bytes.get(self.at) {
                        Some(b',') => self.at += 1,
                        Some(b']') => {
                            self.at += 1;
                            return Ok(Json::Array(values));
                        }
                        _ => return Err(()),
                    }
                }
            }
            _ => {
                let start = self.at;
                while self
                    .bytes
                    .get(self.at)
                    .is_some_and(|byte| !b" \t\r\n,]}".contains(byte))
                {
                    self.at += 1;
                }
                let primitive = &self.bytes[start..self.at];
                // Syntax-only decoding accepts JSON numeric grammar independently
                // of f64 range. A large exponent must not mask a later invalid
                // Unicode scalar; no such number fits v1's sole numeric field.
                serde_json::from_slice::<serde::de::IgnoredAny>(primitive).map_err(|_| ())?;
                let value = serde_json::from_slice(primitive).unwrap_or_else(|_| {
                    self.number_out_of_range = true;
                    Value::Null
                });
                if matches!(value, Value::Null | Value::Bool(_) | Value::Number(_)) {
                    Ok(Json::Scalar(value))
                } else {
                    Err(())
                }
            }
        }
    }
}

fn json_value(bytes: &[u8]) -> Result<Value, &'static str> {
    if std::str::from_utf8(bytes).is_err() || bytes.starts_with(&[0xef, 0xbb, 0xbf]) {
        return Err("FRAME_ENCODING");
    }
    let (mut depth, mut quoted, mut escaped) = (0_isize, false, false);
    for &byte in bytes {
        if quoted {
            if escaped {
                escaped = false;
            } else if byte == b'\\' {
                escaped = true;
            } else if byte == b'"' {
                quoted = false;
            }
        } else {
            match byte {
                b'"' => quoted = true,
                b'[' | b'{' => {
                    depth += 1;
                    if depth > MAX_DEPTH as isize {
                        return Err("FRAME_SCHEMA");
                    }
                }
                b']' | b'}' => depth -= 1,
                _ => {}
            }
        }
    }
    let mut parser = Parser {
        bytes,
        at: 0,
        invalid_scalar: false,
        number_out_of_range: false,
    };
    let value = parser.value().map_err(|_| "FRAME_JSON")?;
    parser.whitespace();
    if parser.at != bytes.len() {
        return Err("FRAME_JSON");
    }
    if parser.invalid_scalar {
        return Err("FRAME_ENCODING");
    }
    if parser.number_out_of_range {
        return Err("FRAME_SCHEMA");
    }
    Ok(value.value())
}

enum Request {
    Read(String, Vec<OsString>),
    Close(String),
}
fn request(bytes: &[u8]) -> Result<Request, &'static str> {
    let value = json_value(bytes)?;
    let object = value.as_object().ok_or("FRAME_SCHEMA")?;
    if object.get("protocolVersion").and_then(Value::as_f64) != Some(1.0) {
        return Err("FRAME_SCHEMA");
    }
    let id = object
        .get("id")
        .and_then(Value::as_str)
        .filter(|id| {
            !id.is_empty()
                && id.len() <= read_request::MAX_REQUEST_ID_BYTES
                && id.as_bytes()[0].is_ascii_alphabetic()
                && id
                    .bytes()
                    .all(|byte| byte.is_ascii_alphanumeric() || b"._:-".contains(&byte))
        })
        .ok_or("FRAME_SCHEMA")?
        .to_owned();
    match object.get("kind").and_then(Value::as_str) {
        Some("close") if object.len() == 3 => Ok(Request::Close(id)),
        Some("read") if object.len() == 4 => {
            let tokens = object
                .get("tokens")
                .and_then(Value::as_array)
                .ok_or("FRAME_SCHEMA")?;
            if tokens.len() > read_request::MAX_TOKENS {
                return Err("FRAME_SCHEMA");
            }
            let mut total = 0;
            let mut native = Vec::with_capacity(tokens.len());
            for token in tokens {
                let token = token.as_str().ok_or("FRAME_SCHEMA")?;
                total += token.len();
                if token.contains('\0')
                    || token.len() > read_request::MAX_TOKEN_BYTES
                    || total > read_request::MAX_TOTAL_TOKEN_BYTES
                {
                    return Err("FRAME_SCHEMA");
                }
                native.push(OsString::from(token));
            }
            Ok(Request::Read(id, native))
        }
        _ => Err("FRAME_SCHEMA"),
    }
}

struct Count(usize);
impl Write for Count {
    fn write(&mut self, bytes: &[u8]) -> io::Result<usize> {
        self.0 = self
            .0
            .checked_add(bytes.len())
            .filter(|size| *size < MAX_OUTPUT_FRAME_BYTES)
            .ok_or(io::ErrorKind::FileTooLarge)?;
        Ok(bytes.len())
    }
    fn flush(&mut self) -> io::Result<()> {
        Ok(())
    }
}
fn serialization(error: serde_json::Error) -> io::Error {
    io::Error::new(
        error.io_error_kind().unwrap_or(io::ErrorKind::InvalidData),
        error,
    )
}
fn output(writer: &mut impl Write, value: &impl Serialize) -> io::Result<()> {
    serde_json::to_writer(Count(0), value).map_err(serialization)?;
    serde_json::to_writer(&mut *writer, value).map_err(serialization)?;
    writer.write_all(b"\n")?;
    writer.flush()
}

/// Run the fixed v1 read-only session, leaving unconsumed bytes in `input`.
///
/// The caller owns buffering: `fill_buf` may prefetch bytes, but only bytes
/// through the current LF (or the first size violation) are consumed. Keep the
/// supplied buffered reader to recover its trailing bytes after this call.
/// Protocol and input errors return a flushed completion with status 2 and 1,
/// respectively. Any output error returns immediately with status 1 semantics.
/// No elapsed-time, cancellation, OS pipe or process-exit guarantee is made.
pub fn run(
    input: &mut impl BufRead,
    writer: &mut impl Write,
) -> Result<SessionOutcome, SessionError> {
    let (mut frames, mut results) = (0, 0);
    let send = |writer: &mut _, value: &Value, frames, results| {
        output(writer, value).map_err(|source| SessionError {
            source,
            frames,
            results,
        })
    };
    send(
        writer,
        &json!({"protocolVersion":1,"kind":"session-ready","limits":{
            "maxInputFrameBytes":MAX_INPUT_FRAME_BYTES,"maxOutputFrameBytes":MAX_OUTPUT_FRAME_BYTES,
            "maxFrames":MAX_FRAMES,"maxQueuedRequests":0,"maxTokens":read_request::MAX_TOKENS,
            "maxTokenBytes":read_request::MAX_TOKEN_BYTES,"maxTotalTokenBytes":read_request::MAX_TOTAL_TOKEN_BYTES,
            "maxInputs":read_request::MAX_API_INPUTS,"maxMetadataBytes":read_request::MAX_METADATA_BYTES,
            "maxResultBytes":read_request::MAX_RESULT_BYTES},"allowApply":false}),
        frames,
        results,
    )?;
    let mut ids = BTreeSet::new();
    let (reason, status, close_id) = loop {
        let admitted = match frame(input) {
            Frame::Eof => break ("eof", 0, None),
            Frame::Error(code, attempted) => {
                frames += usize::from(attempted);
                Err(code)
            }
            Frame::Complete(bytes) => {
                frames += 1;
                request(&bytes)
            }
        };
        let admitted = admitted.and_then(|request| {
            let id = match &request {
                Request::Read(id, _) | Request::Close(id) => id,
            };
            if !ids.insert(id.clone()) {
                Err("DUPLICATE_ID")
            } else {
                Ok(request)
            }
        });
        match admitted {
            Err(code) => {
                send(
                    writer,
                    &json!({"protocolVersion":1,"kind":"protocol-error","id":null,"code":code}),
                    frames,
                    results,
                )?;
                break if code == "INPUT_IO" {
                    ("input-error", 1, None)
                } else {
                    ("protocol-error", 2, None)
                };
            }
            Ok(Request::Close(id)) => break ("close", 0, Some(id)),
            Ok(Request::Read(id, tokens)) => {
                let record = read_request::execute(&id, &tokens);
                #[derive(Serialize)]
                #[serde(rename_all = "camelCase")]
                struct ReadResult<'a> {
                    protocol_version: u8,
                    kind: &'static str,
                    id: &'a str,
                    result: &'a crate::output::ResultEnvelope,
                }
                output(
                    writer,
                    &ReadResult {
                        protocol_version: 1,
                        kind: "read-result",
                        id: &id,
                        result: &record,
                    },
                )
                .map_err(|source| SessionError {
                    source,
                    frames,
                    results,
                })?;
                results += 1;
                if frames == MAX_FRAMES {
                    break ("limit", 0, None);
                }
            }
        }
    };
    send(
        writer,
        &json!({"protocolVersion":1,"kind":"session-complete","reason":reason,
            "exitStatus":status,"frames":frames,"results":results,"closeId":close_id}),
        frames,
        results,
    )?;
    Ok(SessionOutcome {
        exit_status: status,
        frames,
        results,
        reason,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn complete_outer_size_is_preflighted_at_exact_limit_before_delivery() {
        #[derive(Default)]
        struct Sink {
            bytes: usize,
            flushes: usize,
        }
        impl Write for Sink {
            fn write(&mut self, bytes: &[u8]) -> io::Result<usize> {
                self.bytes += bytes.len();
                Ok(bytes.len())
            }
            fn flush(&mut self) -> io::Result<()> {
                self.flushes += 1;
                Ok(())
            }
        }
        // Two JSON quotes and one LF are part of the outer serialized cap.
        let mut value = "x".repeat(MAX_OUTPUT_FRAME_BYTES - 3);
        let mut exact = Sink::default();
        output(&mut exact, &value).unwrap();
        assert_eq!(exact.bytes, MAX_OUTPUT_FRAME_BYTES);
        assert_eq!(exact.flushes, 1);
        value.push('x');
        let mut oversized = Sink::default();
        assert_eq!(
            output(&mut oversized, &value).unwrap_err().kind(),
            io::ErrorKind::FileTooLarge
        );
        assert_eq!((oversized.bytes, oversized.flushes), (0, 0));
    }
}
