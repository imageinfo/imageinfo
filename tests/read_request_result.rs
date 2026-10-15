//! Actual request-local integration using authored structural bytes only.
#[allow(dead_code)]
mod support;

use imageinfo::{output::ResultEnvelope, read_request};
use serde_json::{Value, json};
use std::{
    collections::BTreeMap,
    ffi::OsString,
    fs,
    io::{self, Write},
    path::Path,
    process::Command,
    time::SystemTime,
};

fn tokens(path: &Path, options: &[&str]) -> Vec<OsString> {
    let mut args: Vec<OsString> = ["metadata", "read"]
        .into_iter()
        .chain(options.iter().copied())
        .map(OsString::from)
        .collect();
    args.push("--".into());
    args.push(path.as_os_str().to_owned());
    args
}

fn value(record: &ResultEnvelope) -> Value {
    serde_json::to_value(record).unwrap()
}

fn no_mutation(record: &ResultEnvelope) {
    assert!(record.summary.artifacts.is_empty());
    for file in &record.files {
        assert!(!file.effects.changed);
        assert!(!file.effects.publication_may_have_occurred);
        assert!(!file.effects.cleanup_pending);
        assert!(file.effects.recovery_ids.is_empty());
    }
}

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

fn normalized_ids(mut record: Value) -> Value {
    let id = record["requestId"].as_str().unwrap().to_owned();
    assert_eq!(record["request"]["requestId"], id);
    assert_eq!(record["summary"]["requestId"], id);
    record["requestId"] = json!("request");
    record["request"]["requestId"] = json!("request");
    record["summary"]["requestId"] = json!("request");
    for file in record["files"].as_array_mut().unwrap() {
        assert_eq!(file["requestId"], id);
        file["requestId"] = json!("request");
        if let Some(snapshot) = file["snapshot"].as_object_mut() {
            let snapshot_id = snapshot["id"].as_str().unwrap();
            assert!(snapshot_id.starts_with(&format!("{id}-snapshot-")));
            let normalized = format!("request{}", &snapshot_id[id.len()..]);
            snapshot.insert("id".into(), json!(normalized));
        }
    }
    record
}

#[test]
fn actual_token_array_matches_ordinary_cli_without_mutation() {
    let directory = support::TempDir::new();
    let path = directory
        .path
        .join("literal Unicode 雪 ; $quoted (sample).cr3");
    fs::write(&path, support::fixture().bytes).unwrap();
    fs::write(
        directory.path.join("unrelated.xmp"),
        b"unchanged owned marker",
    )
    .unwrap();
    let before = inventory(&directory.path);
    let args = tokens(&path, &["--values", "all"]);
    let record = read_request::execute("caller-actual", &args);
    assert_eq!(record.summary.exit_status, 0);
    assert_eq!(record.request_id, "caller-actual");
    no_mutation(&record);
    let cli = Command::new(env!("CARGO_BIN_EXE_imageinfo"))
        .args(["--output", "json"])
        .args(&args)
        .output()
        .unwrap();
    assert!(cli.status.success(), "{:?}", cli.stderr);
    assert!(cli.stderr.is_empty());
    let wire: Value = serde_json::from_slice(&cli.stdout).unwrap();
    assert_eq!(normalized_ids(value(&record)), normalized_ids(wire));
    assert_eq!(inventory(&directory.path), before);
    let snapshot = record.files[0].snapshot.as_ref().unwrap();
    assert_eq!(
        snapshot["sources"][0]["displayPath"],
        path.to_string_lossy().as_ref()
    );
    assert_eq!(snapshot["coverage"][0]["state"], "partial");
    assert_eq!(snapshot["sources"][0]["identity"]["kind"], "unavailable");
}

#[test]
fn consecutive_requests_do_not_retain_selectors_views_or_budgets() {
    let directory = support::TempDir::new();
    let path = directory.path.join("authored.cr3");
    fs::write(&path, support::fixture().bytes).unwrap();
    let before = inventory(&directory.path);
    let first = read_request::execute(
        "caller-iso",
        &tokens(&path, &["--tag", "ISO", "--values", "all"]),
    );
    assert_eq!(first.summary.exit_status, 0);
    let selected = first.files[0].snapshot.as_ref().unwrap()["occurrences"]
        .as_array()
        .unwrap();
    assert_eq!(selected.len(), 2);
    assert_ne!(
        selected[0]["tag"]["namespace"],
        selected[1]["tag"]["namespace"]
    );
    assert!(
        selected
            .iter()
            .all(|item| item["values"]["display"]["state"] == "present")
    );
    let limited = read_request::execute("caller-limited", &tokens(&path, &["--max-bytes", "16"]));
    assert_eq!(limited.summary.exit_status, 1);
    assert_eq!(limited.files[0].issues[0].code, "LIMIT_EXCEEDED");
    let next = read_request::execute("caller-default", &tokens(&path, &[]));
    assert_eq!(next.summary.exit_status, 0);
    let all = next.files[0].snapshot.as_ref().unwrap()["occurrences"]
        .as_array()
        .unwrap();
    assert!(all.len() > selected.len());
    assert!(
        all.iter()
            .all(|item| item["values"]["display"]["state"] == "unavailable")
    );
    let rational = all
        .iter()
        .find(|item| item["tag"]["name"] == "ExposureTime" && item["tag"]["namespace"] == "exif")
        .unwrap();
    assert_eq!(rational["values"]["raw"]["value"]["numerator"], "2");
    assert_eq!(rational["values"]["raw"]["value"]["denominator"], "500");
    for record in [&first, &limited, &next] {
        no_mutation(record);
    }
    assert_eq!(inventory(&directory.path), before);
}

#[test]
fn malformed_and_non_read_tokens_refuse_before_any_output_artifact() {
    let directory = support::TempDir::new();
    let path = directory.path.join("authored.cr3");
    let destination = directory.path.join("never-created.jpg");
    fs::write(&path, support::fixture().bytes).unwrap();
    let before = inventory(&directory.path);
    let cases: Vec<Vec<OsString>> = vec![
        vec![],
        ["metadata", "read"].map(OsString::from).to_vec(),
        tokens(&path, &["--bogus"]),
        tokens(&path, &["--values", "invalid"]),
        tokens(&path, &["--tag", "unknown-authored-tag"]),
        tokens(&path, &["--output", "json"]),
        tokens(&path, &["--output=json"]),
        ["help"].map(OsString::from).to_vec(),
        ["version"].map(OsString::from).to_vec(),
        vec![
            "binary".into(),
            "extract".into(),
            "--tag".into(),
            "PreviewImage".into(),
            "--output-file".into(),
            destination.as_os_str().to_owned(),
            "--".into(),
            path.as_os_str().to_owned(),
        ],
        vec![
            "sidecar".into(),
            "pair".into(),
            "--".into(),
            path.as_os_str().to_owned(),
        ],
        vec![
            "binary".into(),
            "list".into(),
            "--".into(),
            path.as_os_str().to_owned(),
        ],
        vec![
            "preview".into(),
            "date-time-original".into(),
            "--value".into(),
            "2027:02:03 04:05:06".into(),
            "--".into(),
            path.as_os_str().to_owned(),
        ],
    ];
    for args in cases {
        let result = read_request::execute("caller-refusal", &args);
        assert_eq!(result.summary.exit_status, 2, "{args:?}");
        assert!(result.files.is_empty(), "{args:?}");
        assert!(!result.request.issues.is_empty(), "{args:?}");
        no_mutation(&result);
        assert_eq!(inventory(&directory.path), before);
    }
    assert!(!destination.exists());
}

#[test]
fn output_selector_tokens_after_double_dash_are_literal_native_inputs() {
    let args = ["metadata", "read", "--", "--output=authored-no-such-file"].map(OsString::from);
    let record = read_request::execute("caller-literal", &args);
    assert_eq!(record.files.len(), 1);
    assert_eq!(record.files[0].path, "--output=authored-no-such-file");
    assert_eq!(record.files[0].state, "failed");
    assert_eq!(record.summary.exit_status, 1);
    no_mutation(&record);
}

#[test]
fn integration_input_and_token_bounds_are_finite_before_io() {
    let directory = support::TempDir::new();
    let path = directory.path.join("authored.cr3");
    fs::write(&path, support::fixture().bytes).unwrap();
    let before = inventory(&directory.path);
    let mut too_many = tokens(&path, &[]);
    too_many.extend(std::iter::repeat_n(path.as_os_str().to_owned(), 4));
    let cases = [
        too_many,
        vec![OsString::from("x"); 129],
        vec![OsString::from("x".repeat(32769))],
        vec![OsString::from("x".repeat(24000)); 3],
        tokens(&path, &["--max-bytes", "8388609"]),
    ];
    for args in cases {
        let result = read_request::execute("caller-bound", &args);
        assert_eq!(result.summary.exit_status, 2);
        assert!(result.files.is_empty());
        no_mutation(&result);
    }
    for id in ["".to_owned(), "a".repeat(129), "bad\nidentity".to_owned()] {
        let result = read_request::execute(&id, &tokens(&path, &[]));
        assert_eq!(result.summary.exit_status, 2);
        assert!(result.files.is_empty());
        assert!(!result.request_id.is_empty());
        assert!(!result.request_id.chars().any(char::is_control));
        no_mutation(&result);
    }
    assert_eq!(inventory(&directory.path), before);
}

#[test]
fn maximum_token_count_and_request_id_are_accepted_at_the_boundary() {
    let directory = support::TempDir::new();
    let path = directory.path.join("authored.cr3");
    fs::write(&path, support::fixture().bytes).unwrap();
    let before = inventory(&directory.path);
    let mut args: Vec<OsString> = ["metadata", "read"].map(OsString::from).to_vec();
    args.extend(std::iter::repeat_n(OsString::from("--tag=ISO"), 124));
    args.extend([OsString::from("--"), path.into_os_string()]);
    assert_eq!(args.len(), 128);
    let id = "a".repeat(128);
    let record = read_request::execute(&id, &args);
    assert_eq!(record.summary.exit_status, 0);
    assert_eq!(record.request_id, id);
    assert_eq!(
        record.files[0].snapshot.as_ref().unwrap()["occurrences"]
            .as_array()
            .unwrap()
            .len(),
        2
    );
    no_mutation(&record);
    assert_eq!(inventory(&directory.path), before);
}

#[test]
fn mixed_inputs_and_exact_duplicate_paths_keep_outcomes() {
    let directory = support::TempDir::new();
    let path = directory.path.join("authored.cr3");
    let broken = directory.path.join("broken.cr3");
    let missing = directory.path.join("missing.cr3");
    fs::write(&path, support::fixture().bytes).unwrap();
    fs::write(&broken, b"authored invalid bytes").unwrap();
    let before = inventory(&directory.path);
    let mut args = tokens(&path, &[]);
    args.extend([
        broken.into_os_string(),
        missing.into_os_string(),
        path.clone().into_os_string(),
    ]);
    let record = read_request::execute("caller-mixed", &args);
    assert_eq!(record.summary.exit_status, 3);
    assert_eq!(record.files.len(), 3);
    assert_eq!(record.files[0].state, "read");
    assert_eq!(record.files[1].state, "failed");
    assert_eq!(record.files[2].state, "failed");
    assert_eq!(record.summary.counts.deduplicated, 1);
    assert_eq!(record.summary.counts.discovered, 3);
    no_mutation(&record);
    assert_eq!(inventory(&directory.path), before);
}

#[test]
fn invalid_rational_retains_partial_snapshot_and_exact_invalid_state() {
    let directory = support::TempDir::new();
    let path = directory.path.join("invalid-rational.cr3");
    let mut bytes = support::fixture().bytes;
    let pair = [2u32.to_le_bytes(), 500u32.to_le_bytes()].concat();
    let at = bytes
        .windows(pair.len())
        .position(|part| part == pair)
        .unwrap();
    bytes[at + 4..at + 8].fill(0);
    fs::write(&path, &bytes).unwrap();
    let before = inventory(&directory.path);
    let result = read_request::execute("caller-invalid", &tokens(&path, &["--values", "all"]));
    assert_eq!(result.summary.exit_status, 1);
    assert_eq!(result.files[0].state, "failed");
    let occurrences = result.files[0].snapshot.as_ref().unwrap()["occurrences"]
        .as_array()
        .unwrap();
    let invalid = occurrences
        .iter()
        .find(|item| item["values"]["raw"]["code"] == "ZERO_DENOMINATOR")
        .unwrap();
    assert_eq!(invalid["values"]["raw"]["state"], "invalid");
    assert_eq!(invalid["values"]["normalized"]["state"], "invalid");
    assert_eq!(invalid["values"]["display"]["state"], "unavailable");
    assert!(invalid["origin"]["resourceRef"].is_string());
    no_mutation(&result);
    assert_eq!(inventory(&directory.path), before);
}

#[test]
fn actual_oversized_result_is_refused_without_creating_a_truncated_success() {
    let directory = support::TempDir::new();
    // Reserve authored CMT3 space, then replace its entire TIFF payload. Every
    // submitted string allocation is <=4096 bytes; duplicate logical entries
    // share that valid allocation. This tests result expansion without weakening
    // the reader's string/block/input limits or confusing a parser refusal with
    // the integration result bound.
    let mut bytes = support::fixture_with_firmware(&"x".repeat(32768)).bytes;
    let kind = bytes.windows(4).position(|part| part == b"CMT3").unwrap();
    let box_size = u32::from_be_bytes(bytes[kind - 4..kind].try_into().unwrap()) as usize;
    let capacity = box_size - 8;
    let copies = 1024;
    let count = copies + 3;
    let mut tiff = b"II\x2a\0\x08\0\0\0".to_vec();
    tiff.extend((count as u16).to_le_bytes());
    tiff.resize(8 + 2 + count * 12 + 4, 0);
    let settings = tiff.len();
    tiff.extend([0u8; 110]);
    tiff[settings..settings + 2].copy_from_slice(&110u16.to_le_bytes());
    tiff[settings + 6..settings + 8].copy_from_slice(&4u16.to_le_bytes());
    let firmware = tiff.len();
    tiff.extend(std::iter::repeat_n(b'\\', 4095));
    tiff.push(0);
    let lighting = tiff.len();
    tiff.extend([0u8; 60]);
    tiff[lighting..lighting + 4].copy_from_slice(&60u32.to_le_bytes());
    for index in 0..count {
        let (tag, format, elements, data) = if index == 0 {
            (1u16, 3u16, 55u32, settings as u32)
        } else if index <= copies {
            (7, 2, 4096, firmware as u32)
        } else if index == copies + 1 {
            (16, 4, 1, 0x80000421)
        } else {
            (0x4018, 4, 15, lighting as u32)
        };
        let at = 10 + index * 12;
        tiff[at..at + 2].copy_from_slice(&tag.to_le_bytes());
        tiff[at + 2..at + 4].copy_from_slice(&format.to_le_bytes());
        tiff[at + 4..at + 8].copy_from_slice(&elements.to_le_bytes());
        tiff[at + 8..at + 12].copy_from_slice(&data.to_le_bytes());
    }
    assert!(tiff.len() < capacity);
    tiff.resize(capacity, 0);
    bytes[kind + 4..kind + 4 + capacity].copy_from_slice(&tiff);
    let metadata = imageinfo::reader::read(
        std::io::Cursor::new(&bytes),
        imageinfo::reader::Limits::default(),
    )
    .unwrap();
    assert_eq!(
        metadata
            .occurrences
            .iter()
            .filter(|item| item.name == "CanonFirmwareVersion")
            .count(),
        copies
    );
    let path = directory.path.join("large-result.cr3");
    fs::write(&path, &bytes).unwrap();
    let before = inventory(&directory.path);
    let record = read_request::execute("caller-result-bound", &tokens(&path, &["--values", "all"]));
    assert_eq!(record.summary.exit_status, 1);
    assert!(record.files.is_empty());
    assert_eq!(record.request.issues[0].code, "RESULT_LIMIT");
    let mut wire = Vec::new();
    read_request::write_result(&mut wire, &record).unwrap();
    assert!(wire.len() < 4096);
    assert_eq!(
        serde_json::from_slice::<Value>(&wire).unwrap()["summary"]["exitStatus"],
        1
    );
    no_mutation(&record);
    assert_eq!(inventory(&directory.path), before);
}

struct PartialFailure {
    remaining: usize,
    bytes: Vec<u8>,
}
impl Write for PartialFailure {
    fn write(&mut self, bytes: &[u8]) -> io::Result<usize> {
        if self.remaining == 0 {
            return Err(io::ErrorKind::BrokenPipe.into());
        }
        let count = self.remaining.min(bytes.len());
        self.bytes.extend_from_slice(&bytes[..count]);
        self.remaining -= count;
        Ok(count)
    }
    fn flush(&mut self) -> io::Result<()> {
        Ok(())
    }
}

struct FlushFailure {
    bytes: Vec<u8>,
}

#[derive(Default)]
struct CountingSink {
    writes: usize,
    flushes: usize,
}
impl Write for CountingSink {
    fn write(&mut self, bytes: &[u8]) -> io::Result<usize> {
        self.writes += 1;
        Ok(bytes.len())
    }
    fn flush(&mut self) -> io::Result<()> {
        self.flushes += 1;
        Ok(())
    }
}

#[test]
fn result_limit_is_preflighted_before_touching_the_transport() {
    let mut record = read_request::execute("caller-writer-bound", &["help".into()]);
    record.request.issues[0].message = "x".repeat(read_request::MAX_RESULT_BYTES);
    let mut sink = CountingSink::default();
    assert_eq!(
        read_request::write_result(&mut sink, &record)
            .unwrap_err()
            .kind(),
        io::ErrorKind::FileTooLarge
    );
    assert_eq!(sink.writes, 0);
    assert_eq!(sink.flushes, 0);
}
impl Write for FlushFailure {
    fn write(&mut self, bytes: &[u8]) -> io::Result<usize> {
        self.bytes.extend_from_slice(bytes);
        Ok(bytes.len())
    }
    fn flush(&mut self) -> io::Result<()> {
        Err(io::ErrorKind::Other.into())
    }
}

#[test]
fn actual_result_transport_distinguishes_complete_partial_and_failed_flush() {
    let directory = support::TempDir::new();
    let path = directory.path.join("authored.cr3");
    fs::write(&path, support::fixture().bytes).unwrap();
    let before = inventory(&directory.path);
    let result = read_request::execute("caller-transport", &tokens(&path, &[]));
    assert_eq!(result.summary.exit_status, 0);
    let mut complete = Vec::new();
    read_request::write_result(&mut complete, &result).unwrap();
    assert_eq!(complete.last(), Some(&b'\n'));
    assert_eq!(
        serde_json::from_slice::<Value>(&complete).unwrap(),
        value(&result)
    );
    let mut partial = PartialFailure {
        remaining: 37,
        bytes: Vec::new(),
    };
    assert_eq!(
        read_request::write_result(&mut partial, &result)
            .unwrap_err()
            .kind(),
        io::ErrorKind::BrokenPipe
    );
    assert_eq!(partial.bytes.len(), 37);
    assert!(serde_json::from_slice::<Value>(&partial.bytes).is_err());
    let mut flush = FlushFailure { bytes: Vec::new() };
    assert_eq!(
        read_request::write_result(&mut flush, &result)
            .unwrap_err()
            .kind(),
        io::ErrorKind::Other
    );
    assert_eq!(flush.bytes, complete);
    // The operation envelope can be complete while delivery still failed. Its
    // summary must never replace the caller's transport Result check.
    assert!(result.summary.output_complete);
    no_mutation(&result);
    assert_eq!(inventory(&directory.path), before);
}

#[cfg(target_os = "linux")]
#[test]
fn native_non_unicode_input_is_read_without_reconstructing_display_path() {
    use std::os::unix::ffi::OsStringExt;
    let directory = support::TempDir::new();
    let path = directory
        .path
        .join(OsString::from_vec(b"native-\xff.cr3".to_vec()));
    fs::write(&path, support::fixture().bytes).unwrap();
    let before = inventory(&directory.path);
    let result = read_request::execute("caller-native", &tokens(&path, &[]));
    assert_eq!(result.summary.exit_status, 0);
    assert!(
        result.files[0]
            .issues
            .iter()
            .any(|issue| issue.code == "PATH_DISPLAY_LOSSY")
    );
    assert!(result.files[0].path.contains('\u{fffd}'));
    no_mutation(&result);
    assert_eq!(inventory(&directory.path), before);
}

#[cfg(target_os = "macos")]
#[test]
fn native_macos_illegal_bytes_refuse_without_reopening_lossy_display_neighbor() {
    use std::os::unix::ffi::OsStringExt;
    let directory = support::TempDir::new();
    let invalid = directory
        .path
        .join(OsString::from_vec(b"native-\xff.cr3".to_vec()));
    // APFS rejects illegal UTF-8 names. A valid fixture at the lossy display
    // label makes a mistaken String conversion/reopen observable as false success.
    let lossy_neighbor = directory.path.join("native-\u{fffd}.cr3");
    let fixture = support::fixture().bytes;
    fs::write(&lossy_neighbor, &fixture).unwrap();
    let before = inventory(&directory.path);

    let positive = read_request::execute("caller-macos-neighbor", &tokens(&lossy_neighbor, &[]));
    assert_eq!(positive.summary.exit_status, 0);
    assert_eq!(positive.files[0].state, "read");
    no_mutation(&positive);

    let negative = read_request::execute("caller-macos-illegal", &tokens(&invalid, &[]));
    assert_eq!(negative.summary.exit_status, 1);
    assert_eq!(negative.files.len(), 1);
    assert_eq!(negative.files[0].state, "failed");
    assert!(negative.files[0].snapshot.is_none());
    assert!(
        negative.files[0]
            .issues
            .iter()
            .any(|issue| issue.code == "INPUT_IO")
    );
    assert_eq!(
        negative.files[0].path,
        lossy_neighbor.to_string_lossy().as_ref()
    );
    no_mutation(&negative);
    assert_eq!(inventory(&directory.path), before);
}

#[cfg(windows)]
#[test]
fn native_windows_unpaired_surrogate_path_is_read_without_lossy_reopen() {
    use std::os::windows::ffi::OsStringExt;
    let directory = support::TempDir::new();
    let name = OsString::from_wide(&[
        b'n' as u16,
        b'-' as u16,
        0xd800,
        b'.' as u16,
        b'c' as u16,
        b'r' as u16,
        b'3' as u16,
    ]);
    let path = directory.path.join(name);
    fs::write(&path, support::fixture().bytes).unwrap();
    let before = inventory(&directory.path);
    let result = read_request::execute("caller-native", &tokens(&path, &[]));
    assert_eq!(result.summary.exit_status, 0);
    assert!(
        result.files[0]
            .issues
            .iter()
            .any(|issue| issue.code == "PATH_DISPLAY_LOSSY")
    );
    assert!(result.files[0].path.contains('\u{fffd}'));
    no_mutation(&result);
    assert_eq!(inventory(&directory.path), before);
}
