use super::{
    GateError, MAX_ACK_BYTES, MAX_EVENTS, Notices, PREFIX, parse_ack, read_ack_line, receive_ack,
};
use serde_json::{Value, json};
use std::io::{self, BufRead, Cursor, Read, Write};
use std::sync::mpsc;
use std::time::Duration;

const UNIT: &str = "authored-normal";
const STAGE: &str = "create-Candidate";
const COMMAND: &str = "release";

fn ack(seq: u64, stage: &str, command: &str) -> Vec<u8> {
    format!(
        "{{\"v\":1,\"unit\":\"{UNIT}\",\"seq\":{seq},\"stage\":\"{stage}\",\"command\":\"{command}\"}}\n"
    )
    .into_bytes()
}

fn parse(line: &[u8]) -> Result<(), GateError> {
    parse_ack(line, UNIT, 2, STAGE, COMMAND)
}

#[test]
fn exact_acknowledgement_is_accepted() {
    assert_eq!(parse(&ack(2, STAGE, COMMAND)), Ok(()));
}

#[test]
fn acknowledgements_bind_current_unit_sequence_stage_and_command() {
    for line in [
        ack(1, STAGE, COMMAND),
        ack(3, STAGE, COMMAND),
        ack(2, "prepared", COMMAND),
        ack(2, STAGE, "continue"),
        String::from_utf8(ack(2, STAGE, COMMAND))
            .unwrap()
            .replace(UNIT, "different-unit")
            .into_bytes(),
    ] {
        assert_eq!(parse(&line), Err(GateError::Mismatch));
    }
}

#[test]
fn cancellation_only_applies_to_the_current_gate() {
    assert_eq!(parse(&ack(2, STAGE, "cancel")), Err(GateError::Cancelled));
    assert_eq!(parse(&ack(1, STAGE, "cancel")), Err(GateError::Mismatch));
    assert_eq!(
        parse(&ack(2, "prepared", "cancel")),
        Err(GateError::Mismatch)
    );
}

#[test]
fn malformed_or_ambiguous_json_cannot_release_a_gate() {
    let valid = String::from_utf8(ack(2, STAGE, COMMAND)).unwrap();
    for line in [
        String::new(),
        "[]\n".into(),
        "null\n".into(),
        "{\n".into(),
        valid.replace("\"seq\":2", "\"seq\":\"2\""),
        valid.replace("\"seq\":2", "\"seq\":-1"),
        valid.replace("\"seq\":2", "\"seq\":2.0"),
        valid.replace("\"seq\":2", "\"seq\":18446744073709551616"),
        valid.replace("\"seq\":2,", ""),
        valid.replace("\"seq\":2", "\"seq\":2,\"seq\":2"),
        valid.replace("\"v\":1", "\"v\":1,\"extra\":false"),
        format!("{}{{}}\n", valid.trim_end()),
    ] {
        assert_eq!(parse(line.as_bytes()), Err(GateError::Malformed));
    }
    assert_eq!(parse(&[0xff, b'\n']), Err(GateError::Malformed));
}

#[test]
fn line_reader_requires_complete_lf_and_retains_next_line() {
    let expected = ack(2, STAGE, COMMAND);
    let mut two_lines = expected.clone();
    two_lines.extend_from_slice(b"next\n");
    let mut input = Cursor::new(two_lines);
    assert_eq!(read_ack_line(&mut input), Ok(expected.clone()));
    assert_eq!(read_ack_line(&mut input), Ok(b"next\n".to_vec()));
    assert_eq!(read_ack_line(&mut input), Err(GateError::Eof));
    assert_eq!(
        read_ack_line(&mut Cursor::new(&expected[..expected.len() - 1])),
        Err(GateError::Eof)
    );
}

#[test]
fn line_reader_bounds_exact_wire_bytes_and_refuses_crlf() {
    let mut exact = vec![b'x'; MAX_ACK_BYTES - 1];
    exact.push(b'\n');
    assert_eq!(read_ack_line(&mut Cursor::new(&exact)), Ok(exact));
    let mut over = vec![b'x'; MAX_ACK_BYTES];
    over.push(b'\n');
    assert_eq!(
        read_ack_line(&mut Cursor::new(over)),
        Err(GateError::TooLong)
    );
    assert_eq!(
        read_ack_line(&mut Cursor::new(vec![b'x'; MAX_ACK_BYTES + 1])),
        Err(GateError::TooLong)
    );
    assert_eq!(
        read_ack_line(&mut Cursor::new(b"ack\r\n")),
        Err(GateError::Malformed)
    );
}

#[test]
fn line_reader_preserves_input_failure_as_a_refusal() {
    struct BrokenReader;
    impl Read for BrokenReader {
        fn read(&mut self, _: &mut [u8]) -> io::Result<usize> {
            Err(io::Error::other("authored input failure"))
        }
    }
    impl BufRead for BrokenReader {
        fn fill_buf(&mut self) -> io::Result<&[u8]> {
            Err(io::Error::other("authored input failure"))
        }
        fn consume(&mut self, _: usize) {}
    }
    assert_eq!(read_ack_line(&mut BrokenReader), Err(GateError::Io));
}

#[test]
fn receive_ack_refuses_timeout_closed_input_and_reader_failure() {
    let (sender, receiver) = mpsc::channel();
    assert_eq!(
        receive_ack(&receiver, Duration::ZERO, UNIT, 2, STAGE, COMMAND),
        Err(GateError::Timeout)
    );
    sender.send(Err(GateError::TooLong)).unwrap();
    assert_eq!(
        receive_ack(&receiver, Duration::ZERO, UNIT, 2, STAGE, COMMAND),
        Err(GateError::TooLong)
    );
    drop(sender);
    assert_eq!(
        receive_ack(&receiver, Duration::ZERO, UNIT, 2, STAGE, COMMAND),
        Err(GateError::Eof)
    );
}

#[test]
fn duplicate_release_cannot_release_the_following_gate() {
    let (sender, receiver) = mpsc::channel();
    sender.send(Ok(ack(2, STAGE, COMMAND))).unwrap();
    sender.send(Ok(ack(2, STAGE, COMMAND))).unwrap();
    assert_eq!(
        receive_ack(&receiver, Duration::ZERO, UNIT, 2, STAGE, COMMAND),
        Ok(())
    );
    assert_eq!(
        receive_ack(
            &receiver,
            Duration::ZERO,
            UNIT,
            3,
            "inspection-complete",
            COMMAND
        ),
        Err(GateError::Mismatch)
    );
}

#[test]
fn event_sequence_is_contiguous_and_never_claims_admission() {
    let (_sender, input) = mpsc::channel();
    let mut notices = Notices {
        unit: UNIT.into(),
        sequence: 0,
        input,
        output: Vec::new(),
        failed: None,
    };
    assert_eq!(
        notices.emit("before_operation", STAGE, Value::Null, json!([])),
        Ok(1)
    );
    assert_eq!(
        notices.emit(
            "candidate_result",
            STAGE,
            json!({"success": true, "failure": null, "native_error_kind": null, "native_os_error": null}),
            json!([])
        ),
        Ok(2)
    );
    let lines: Vec<_> = notices
        .output
        .split_inclusive(|byte| *byte == b'\n')
        .collect();
    assert_eq!(lines.len(), 2);
    for (index, line) in lines.into_iter().enumerate() {
        assert!(line.starts_with(PREFIX));
        let record: Value = serde_json::from_slice(&line[PREFIX.len()..]).unwrap();
        assert_eq!(record["seq"], (index + 1) as u64);
        for flag in [
            "committed",
            "production_profile_admitted",
            "raw_admitted",
            "authority_importable",
        ] {
            assert_eq!(record[flag], false);
        }
    }
    notices.sequence = MAX_EVENTS;
    let prior = notices.output.clone();
    assert_eq!(
        notices.emit("before_operation", STAGE, Value::Null, json!([])),
        Err(GateError::EventBound)
    );
    assert_eq!(notices.output, prior);
}

#[test]
fn failed_output_flush_does_not_advance_event_sequence() {
    struct FlushFailure;
    impl Write for FlushFailure {
        fn write(&mut self, bytes: &[u8]) -> io::Result<usize> {
            Ok(bytes.len())
        }
        fn flush(&mut self) -> io::Result<()> {
            Err(io::Error::other("authored flush failure"))
        }
    }
    let (_sender, input) = mpsc::channel();
    let mut notices = Notices {
        unit: UNIT.into(),
        sequence: 0,
        input,
        output: FlushFailure,
        failed: None,
    };
    assert_eq!(
        notices.emit("before_operation", STAGE, Value::Null, json!([])),
        Err(GateError::Output)
    );
    assert_eq!(notices.sequence, 0);
}
