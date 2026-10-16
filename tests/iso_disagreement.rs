//! P0A-003 uses authored binary storage, not a JSON-only disagreement example.
#[allow(dead_code)]
mod support;

use imageinfo::reader::{self, Limits, Value};
use serde_json::Value as Json;
use sha2::{Digest, Sha256};
use std::{fs, io::Cursor, path::Path, process::Command};

fn fixture(exif_iso: u16) -> (Vec<u8>, usize, usize) {
    let source = support::fixture();
    let mut bytes = source.bytes;
    let exif = support::field_offset(&bytes, b"CMT2", 0x8827);
    let tiff = bytes.windows(4).position(|w| w == b"CMT2").unwrap() + 4;
    assert_eq!(&bytes[tiff..tiff + 8], b"II\x2a\0\x08\0\0\0");
    assert_eq!(&bytes[exif - 8..exif - 6], &0x8827u16.to_le_bytes());
    assert_eq!(&bytes[exif - 6..exif - 4], &3u16.to_le_bytes());
    assert_eq!(&bytes[exif - 4..exif], &1u32.to_le_bytes());
    assert_eq!(&bytes[exif..exif + 2], &800u16.to_le_bytes());
    let before = bytes.clone();
    bytes[exif..exif + 2].copy_from_slice(&exif_iso.to_le_bytes());
    assert_eq!(&bytes[..exif], &before[..exif]);
    assert_eq!(&bytes[exif + 2..], &before[exif + 2..]);
    // This authored builder ends with one 40-byte type-5 CTMD record.
    let record = bytes.len() - 40;
    let mdat = bytes.windows(4).position(|w| w == b"mdat").unwrap();
    let mdat_size = u32::from_be_bytes(bytes[mdat - 4..mdat].try_into().unwrap()) as usize;
    assert_eq!(mdat - 4 + mdat_size, bytes.len());
    assert_eq!(record, mdat + 4 + source.jpeg.len() + 8);
    assert_eq!(&bytes[record..record + 4], &40u32.to_le_bytes());
    assert_eq!(&bytes[record + 4..record + 6], &5u16.to_le_bytes());
    let ctmd = record + 20;
    assert_eq!(&bytes[ctmd..ctmd + 4], &800u32.to_le_bytes());
    assert_eq!((bytes.len(), exif, ctmd), (2331, 287, 2311));
    let expected = match exif_iso {
        400 => "e19356f8baeca53ed23eabd106d045b66f43e0fa3c2b14b5fb9c210f2317b27a",
        800 => "7781896f985d5af5153e17b8959df04053fe8418262ca99a7ef2290d853992af",
        _ => panic!("outside the two authored cases"),
    };
    assert_eq!(format!("{:x}", Sha256::digest(&bytes)), expected);
    (bytes, exif, ctmd)
}

fn occurrences(snapshot: &Json) -> &[Json] {
    snapshot["occurrences"].as_array().unwrap()
}

fn by_namespace<'a>(snapshot: &'a Json, namespace: &str) -> &'a Json {
    let matched: Vec<_> = occurrences(snapshot)
        .iter()
        .filter(|o| o["tag"]["namespace"] == namespace)
        .collect();
    assert_eq!(matched.len(), 1);
    matched[0]
}

fn assert_values(snapshot: &Json, exif_iso: u16, display: bool) {
    assert_eq!(occurrences(snapshot).len(), 2);
    assert_eq!(snapshot["coverage"][0]["state"], "partial");
    let exif = by_namespace(snapshot, "exif");
    let ctmd = by_namespace(snapshot, "canon:ctmd");
    assert_ne!(exif["id"], ctmd["id"]);
    assert_ne!(exif["ordinal"], ctmd["ordinal"]);
    assert_ne!(exif["path"], ctmd["path"]);
    for (item, native_id, encoding) in [(exif, "34855", "uint16"), (ctmd, "5/8", "uint32")] {
        assert_eq!(item["tag"]["nativeId"], native_id);
        assert_eq!(item["origin"]["byteOrder"], "little");
        assert_eq!(item["origin"]["encoding"], encoding);
    }
    let has_part = |item: &Json, kind: &str, name: &str, index: usize| {
        item["path"]
            .as_array()
            .unwrap()
            .iter()
            .any(|p| p["kind"] == kind && p["name"] == name && p["index"] == index)
    };
    assert!(has_part(exif, "box", "CMT2", 0));
    assert!(has_part(exif, "ifd", "IFD@8", 0));
    assert!(has_part(exif, "tag", "34855", 2));
    assert!(has_part(ctmd, "box", "trak", 3));
    assert!(has_part(ctmd, "record", "CTMD-type-5", 0));
    assert!(has_part(ctmd, "field", "ISO", 8));
    for (item, expected) in [(exif, exif_iso.to_string()), (ctmd, "800".into())] {
        assert_eq!(item["tag"]["name"], "ISO");
        for mode in ["raw", "normalized"] {
            assert_eq!(item["values"][mode]["state"], "present");
            assert_eq!(item["values"][mode]["value"]["kind"], "integer");
            assert_eq!(item["values"][mode]["value"]["decimal"], expected);
        }
        if display {
            assert_eq!(item["values"]["display"]["state"], "present");
            assert_eq!(item["values"]["display"]["text"], expected);
        } else {
            assert_eq!(item["values"]["display"]["state"], "unavailable");
        }
    }
}

fn assert_range(snapshot: &Json, namespace: &str, offset: usize, length: usize) {
    let item = by_namespace(snapshot, namespace);
    let resource = snapshot["resources"]
        .as_array()
        .unwrap()
        .iter()
        .find(|r| r["id"] == item["origin"]["resourceRef"])
        .unwrap();
    let ranges = resource["content"]["ranges"].as_array().unwrap();
    assert_eq!(ranges.len(), 1);
    assert_eq!(ranges[0]["ref"], "src-raw");
    assert_eq!(ranges[0]["offset"], offset.to_string());
    assert_eq!(ranges[0]["length"], length.to_string());
    assert_eq!(resource["byteLength"], length.to_string());
}

const SELECTORS: &[(&[&str], &[&str])] = &[
    (&["EXIF:ISO"], &["exif"]),
    (&["exif:ISO"], &["exif"]),
    (&["CTMD:ISO"], &["canon:ctmd"]),
    (&["canon:ctmd:ISO"], &["canon:ctmd"]),
    (&["CTMD:ISO", "EXIF:ISO"], &["exif", "canon:ctmd"]),
    (&["ISO", "EXIF:ISO", "CTMD:ISO"], &["exif", "canon:ctmd"]),
];

fn assert_selection(selected: &Json, full: &Json, namespaces: &[&str]) {
    assert_eq!(occurrences(selected).len(), namespaces.len());
    for namespace in namespaces {
        assert_eq!(
            by_namespace(selected, namespace),
            by_namespace(full, namespace)
        );
        let item = by_namespace(selected, namespace);
        let id = &item["origin"]["resourceRef"];
        let resource = |snapshot: &Json| {
            snapshot["resources"]
                .as_array()
                .unwrap()
                .iter()
                .find(|r| &r["id"] == id)
                .unwrap()
                .clone()
        };
        assert_eq!(resource(selected), resource(full));
    }
    assert_eq!(selected["coverage"][0]["state"], "partial");
}

#[test]
fn native_disagreement_and_equal_control_preserve_source_occurrences() {
    for exif_iso in [400, 800] {
        let (bytes, exif, ctmd) = fixture(exif_iso);
        let metadata = reader::read(Cursor::new(&bytes), Limits::default()).unwrap();
        let iso = reader::select(&metadata, &["ISO".into()]).unwrap();
        assert_eq!(iso.len(), 2);
        for (namespace, value, offset, length) in [
            ("exif", u64::from(exif_iso), exif, 2),
            ("canon:ctmd", 800, ctmd, 4),
        ] {
            let matched: Vec<_> = iso
                .iter()
                .map(|&i| &metadata.occurrences[i])
                .filter(|o| o.namespace == namespace)
                .collect();
            assert_eq!(matched.len(), 1);
            assert_eq!(matched[0].value, Value::Integer(value));
            assert_eq!(matched[0].range.offset, offset as u64);
            assert_eq!(matched[0].range.length, length);
        }
        let full = metadata.snapshot("authored", "authored.cr3", &iso, true);
        assert_values(&full, exif_iso, true);
        assert_range(&full, "exif", exif, 2);
        assert_range(&full, "canon:ctmd", ctmd, 4);
        for (selectors, namespaces) in SELECTORS {
            let tags = selectors.iter().map(|s| (*s).into()).collect::<Vec<_>>();
            let selected = reader::select(&metadata, &tags).unwrap();
            assert_selection(
                &metadata.snapshot("authored", "authored.cr3", &selected, true),
                &full,
                namespaces,
            );
        }
    }
}

fn cli(path: &Path, mode: &str, selectors: &[&str]) -> Json {
    let mut command = Command::new(env!("CARGO_BIN_EXE_imageinfo"));
    command.args(["metadata", "read", "--output", "json", "--values", mode]);
    for selector in selectors {
        command.args(["--tag", selector]);
    }
    let output = command.arg("--").arg(path).output().unwrap();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert!(output.stderr.is_empty());
    let envelope: Json = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(envelope["files"].as_array().unwrap().len(), 1);
    assert_eq!(envelope["files"][0]["state"], "read");
    assert_eq!(envelope["summary"]["artifacts"], serde_json::json!([]));
    envelope["files"][0]["snapshot"].clone()
}

#[test]
fn cli_value_views_and_qualified_selectors_preserve_disagreement_without_effects() {
    let dir = support::TempDir::new();
    for exif_iso in [400, 800] {
        let (bytes, exif, ctmd) = fixture(exif_iso);
        let path = dir.path.join(format!("authored-{exif_iso}.cr3"));
        fs::write(&path, &bytes).unwrap();
        for mode in ["all", "raw", "normalized", "display"] {
            let full = cli(&path, mode, &["ISO"]);
            assert_values(&full, exif_iso, matches!(mode, "all" | "display"));
            assert_range(&full, "exif", exif, 2);
            assert_range(&full, "canon:ctmd", ctmd, 4);
            for (selectors, namespaces) in SELECTORS {
                assert_selection(&cli(&path, mode, selectors), &full, namespaces);
            }
        }
        assert_eq!(fs::read(&path).unwrap(), bytes);
    }
    assert_eq!(fs::read_dir(&dir.path).unwrap().count(), 2);
}
