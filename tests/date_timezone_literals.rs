//! P0A-004: authored stored strings, without instant or zone conversion.
#[allow(dead_code)]
mod support;

use imageinfo::reader::{self, Limits, Value};
use serde_json::{Value as Json, json};
use sha2::{Digest, Sha256};
use std::{fs, path::Path, process::Command};

const FIELDS: [(&str, u16, &str); 3] = [
    ("DateTimeOriginal", 0x9003, "2020:11:01 01:30:00"),
    ("OffsetTimeOriginal", 0x9011, "-04:00"),
    ("SubSecTimeOriginal", 0x9291, "050"),
];
const ZONES: [&str; 2] = ["UTC", "America/New_York"];
const OFFSETS: [usize; 3] = [383, 403, 335];

fn fixture() -> Vec<u8> {
    let mut bytes = support::fixture().bytes;
    assert_eq!(
        format!("{:x}", Sha256::digest(&bytes)),
        "7781896f985d5af5153e17b8959df04053fe8418262ca99a7ef2290d853992af"
    );
    let before = bytes.clone();
    let mut authored_ranges = Vec::new();
    for ((_, tag, expected), offset) in FIELDS.into_iter().zip(OFFSETS) {
        let at = support::field_offset(&bytes, b"CMT2", tag);
        assert_eq!(at, offset);
        if tag == 0x9291 {
            // The existing inline ASCII slot has four bytes. Increase its
            // authored count from three to four without moving any allocation.
            assert_eq!(&bytes[at - 8..at - 6], &tag.to_le_bytes());
            assert_eq!(&bytes[at - 6..at - 4], &2u16.to_le_bytes());
            assert_eq!(&bytes[at - 4..at], &3u32.to_le_bytes());
            bytes[at - 4..at].copy_from_slice(&4u32.to_le_bytes());
            authored_ranges.push(at - 4..at);
        }
        bytes[at..at + expected.len()].copy_from_slice(expected.as_bytes());
        bytes[at + expected.len()] = 0;
        authored_ranges.push(at..at + expected.len() + 1);
    }
    for (at, (old, new)) in before.iter().zip(&bytes).enumerate() {
        if !authored_ranges.iter().any(|r| r.contains(&at)) {
            assert_eq!(old, new);
        }
    }
    assert_eq!(bytes.len(), 2331);
    assert_eq!(
        format!("{:x}", Sha256::digest(&bytes)),
        "a2f26feaf5a28c6ef42a85ea6fb213d59d0c01a944e29e013aebff82690dbbac"
    );
    bytes
}

fn assert_snapshot(snapshot: &Json, bytes: &[u8]) {
    let occurrences = snapshot["occurrences"].as_array().unwrap();
    assert_eq!(occurrences.len(), 3);
    assert_eq!(snapshot["coverage"][0]["state"], "partial");
    for (name, tag, expected) in FIELDS {
        let matched: Vec<_> = occurrences
            .iter()
            .filter(|o| o["tag"]["name"] == name)
            .collect();
        assert_eq!(matched.len(), 1);
        let item = matched[0];
        assert_eq!(item["tag"]["namespace"], "exif");
        assert_eq!(item["tag"]["nativeId"], tag.to_string());
        assert_eq!(item["origin"]["encoding"], "ASCII");
        assert_eq!(item["origin"]["byteOrder"], "little");
        for mode in ["raw", "normalized"] {
            assert_eq!(
                item["values"][mode],
                json!({
                    "state":"present", "value":{"kind":"string", "text":expected}
                })
            );
        }
        assert_eq!(item["values"]["display"]["text"], expected);
        assert_eq!(item["values"]["display"]["timeZone"], Json::Null);
        assert_eq!(
            item["values"]["normalization"]["ruleRef"],
            "identity-exact-stored-value"
        );
        let offset = support::field_offset(bytes, b"CMT2", tag);
        let resource = snapshot["resources"]
            .as_array()
            .unwrap()
            .iter()
            .find(|r| r["id"] == item["origin"]["resourceRef"])
            .unwrap();
        assert_eq!(
            resource["content"]["ranges"],
            json!([{
                "space":"source", "ref":"src-raw", "offset":offset.to_string(),
                "length":(expected.len() + 1).to_string()
            }])
        );
        assert_eq!(&bytes[offset..offset + expected.len()], expected.as_bytes());
        assert_eq!(bytes[offset + expected.len()], 0);
    }
    for (i, first) in occurrences.iter().enumerate() {
        for second in &occurrences[i + 1..] {
            for key in ["id", "ordinal", "path"] {
                assert_ne!(first[key], second[key]);
            }
        }
    }
}

fn checked_output(command: &mut Command) -> Vec<u8> {
    let output = command.output().unwrap();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert!(output.stderr.is_empty());
    output.stdout
}

// This entry runs only when the parent explicitly supplies the fixture and TZ.
// Separate processes avoid unsafe process-global environment mutation in tests.
#[test]
fn native_child() {
    let Some(path) = std::env::var_os("IMAGEINFO_DATE_TZ_FIXTURE") else {
        return;
    };
    assert!(ZONES.contains(&std::env::var("TZ").unwrap().as_str()));
    let bytes = fixture();
    assert_eq!(fs::read(&path).unwrap(), bytes);
    let metadata = reader::read_file(Path::new(&path), Limits::default()).unwrap();
    let selectors = FIELDS.map(|(name, _, _)| name.to_string());
    let selected = reader::select(&metadata, &selectors).unwrap();
    for (name, tag, expected) in FIELDS {
        let matching: Vec<_> = selected
            .iter()
            .map(|&i| &metadata.occurrences[i])
            .filter(|o| o.name == name)
            .collect();
        assert_eq!(matching.len(), 1);
        assert_eq!(matching[0].value, Value::Text(expected.to_string()));
        assert_eq!(
            matching[0].range.offset,
            support::field_offset(&bytes, b"CMT2", tag) as u64
        );
        assert_eq!(matching[0].range.length, (expected.len() + 1) as u64);
    }
    let snapshot = metadata.snapshot(
        "authored-date",
        &Path::new(&path).display().to_string(),
        &selected,
        true,
    );
    assert_snapshot(&snapshot, &bytes);
    println!(
        "DATE_TZ_NATIVE={}",
        serde_json::to_string(&snapshot).unwrap()
    );
}

#[test]
fn native_and_cli_keep_exact_literals_in_two_process_tz_environments() {
    let dir = support::TempDir::new();
    let path = dir.path.join("authored-date.cr3");
    let bytes = fixture();
    fs::write(&path, &bytes).unwrap();
    let held_identity = same_file::Handle::from_path(&path).unwrap();
    let before_modified = fs::metadata(&path).unwrap().modified().unwrap();
    let mut native_snapshots = Vec::new();
    let mut cli_envelopes = Vec::new();
    for zone in ZONES {
        let native = checked_output(
            Command::new(std::env::current_exe().unwrap())
                .args(["--exact", "native_child", "--nocapture"])
                .env("TZ", zone)
                .env("IMAGEINFO_DATE_TZ_FIXTURE", &path),
        );
        let native = String::from_utf8(native).unwrap();
        let line = native
            .lines()
            .find_map(|s| s.strip_prefix("DATE_TZ_NATIVE="))
            .unwrap();
        let snapshot: Json = serde_json::from_str(line).unwrap();
        assert_snapshot(&snapshot, &bytes);
        native_snapshots.push(snapshot);

        let mut command = Command::new(env!("CARGO_BIN_EXE_imageinfo"));
        command
            .env("TZ", zone)
            .args(["metadata", "read", "--output", "json", "--values", "all"]);
        for (name, _, _) in FIELDS {
            command.args(["--tag", name]);
        }
        let output = checked_output(command.arg("--").arg(&path));
        let mut envelope: Json = serde_json::from_slice(&output).unwrap();
        assert_eq!(envelope["files"].as_array().unwrap().len(), 1);
        assert_eq!(envelope["files"][0]["state"], "read");
        assert_eq!(envelope["summary"]["artifacts"], json!([]));
        assert_snapshot(&envelope["files"][0]["snapshot"], &bytes);
        // Only the CLI request and snapshot IDs are request-local. Keep all
        // source, occurrence, resource and path identities in the comparison.
        let request_id = envelope["request"]["requestId"]
            .as_str()
            .unwrap()
            .to_string();
        assert!(request_id.starts_with("req-"));
        assert_eq!(envelope["requestId"], request_id);
        assert_eq!(envelope["files"][0]["requestId"], request_id);
        assert_eq!(envelope["summary"]["requestId"], request_id);
        envelope["request"]["requestId"] = json!("compared-request");
        envelope["requestId"] = json!("compared-request");
        envelope["files"][0]["requestId"] = json!("compared-request");
        envelope["summary"]["requestId"] = json!("compared-request");
        envelope["files"][0]["snapshot"]["id"] = json!("authored-date");
        assert_eq!(
            envelope["files"][0]["snapshot"],
            native_snapshots.last().unwrap().clone()
        );
        cli_envelopes.push(envelope);

        assert_eq!(fs::read(&path).unwrap(), bytes);
        assert_eq!(same_file::Handle::from_path(&path).unwrap(), held_identity);
        assert_eq!(
            fs::metadata(&path).unwrap().modified().unwrap(),
            before_modified
        );
        assert_eq!(fs::read_dir(&dir.path).unwrap().count(), 1);
    }
    assert_eq!(native_snapshots[0], native_snapshots[1]);
    assert_eq!(cli_envelopes[0], cli_envelopes[1]);
}
