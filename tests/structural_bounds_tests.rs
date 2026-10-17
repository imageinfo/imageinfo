#[path = "support/byte_boundaries.rs"]
mod recording;
#[path = "support/structural_boundaries.rs"]
mod structures;
#[allow(dead_code)]
mod support;
use imageinfo::reader::{self, Limits};
use sha2::{Digest, Sha256};
use std::{fs, io::Cursor};

#[test]
fn actual_default_structural_boundaries_and_exportable_corpus() {
    let export = std::env::var_os("IMAGEINFO_STRUCTURE_FIXTURE_DIR").map(std::path::PathBuf::from);
    if let Some(dir) = &export {
        fs::create_dir_all(dir).unwrap();
    }
    let mut manifest = Vec::new();
    for (name, bytes, refusal) in structures::corpus() {
        let original = bytes.clone();
        let (source, trace) = recording::RecordingSource::new(&bytes);
        let result = reader::read(source, Limits::default());
        match refusal {
            Some(message) => {
                let error = result.unwrap_err();
                assert_eq!(error.code, "LIMIT_EXCEEDED", "{name}");
                assert_eq!(error.message, message, "{name}");
                let mut raised = Limits::default();
                if name.starts_with("boxes") {
                    raised.boxes += 1;
                } else if name.contains("depth") {
                    raised.depth += 1;
                } else if name.starts_with("entries") {
                    raised.entries += 1;
                } else {
                    raised.records += 1;
                }
                reader::read(Cursor::new(&bytes), raised)
                    .unwrap_or_else(|e| panic!("orthogonal valid control {name}: {e}"));
                let requests = trace.borrow();
                let inventory = structures::boxes(&bytes);
                if name.starts_with("boxes") {
                    let unrequested = inventory[4096].start as u64;
                    assert_eq!(
                        requests.last().unwrap().offset,
                        inventory[4095].start as u64
                    );
                    assert!(!requests.iter().any(|r| r.offset == unrequested));
                } else if name.starts_with("bmff") {
                    let leaf = inventory.last().unwrap().start as u64;
                    assert_eq!(requests.last().unwrap().offset, leaf - 8);
                    assert!(!requests.iter().any(|r| r.offset == leaf));
                } else if name.starts_with("tiff") || name.starts_with("entries") {
                    let cmt = inventory.iter().find(|v| &v.kind == b"CMT4").unwrap();
                    let last = requests.last().unwrap();
                    assert_eq!(
                        (last.offset, last.returned),
                        (cmt.start as u64 + 8, cmt.end - cmt.start - 8)
                    );
                } else {
                    let records = structures::timed_records(&bytes);
                    assert_eq!(records.len(), 4097);
                    let next = records[4096].0 as u64;
                    let last = requests.last().unwrap();
                    assert_eq!((last.offset, last.returned), (next - 40 + 12, 12));
                    assert!(!requests.iter().any(|r| r.offset == next));
                }
            }
            None => {
                let metadata = result.unwrap_or_else(|e| panic!("{name}: {e}"));
                assert_eq!(metadata.previews.len(), 3, "{name}");
                let timed = metadata
                    .occurrences
                    .iter()
                    .filter(|v| v.namespace == "canon:ctmd")
                    .count();
                let expected = if name == "timed-records-below" {
                    4095 * 3
                } else if name == "timed-records-at" {
                    4096 * 3
                } else {
                    3
                };
                assert_eq!(timed, expected, "{name}");
            }
        }
        assert_eq!(original, bytes);
        if let Some(dir) = &export {
            fs::write(dir.join(format!("{name}.cr3")), &bytes).unwrap();
            fs::write(
                dir.join(format!("{name}.requests.json")),
                serde_json::to_vec_pretty(&*trace.borrow()).unwrap(),
            )
            .unwrap();
        }
        let scope = name.rsplit_once('-').unwrap().0;
        let default = if scope.contains("depth") { 16 } else { 4096 };
        let denominator = if name.ends_with("below") {
            default - 1
        } else if name.ends_with("above") {
            default + 1
        } else {
            default
        };
        let directories = structures::cmt4_directories(&bytes);
        let records = structures::timed_records(&bytes);
        if scope == "timed-records" {
            assert_eq!(records.len(), denominator);
        }
        if scope == "entries-per-cmt" {
            assert_eq!(directories.iter().map(|v| v.2).sum::<usize>(), denominator);
        }
        if scope == "tiff-depth" {
            assert_eq!(directories.last().unwrap().1, denominator);
        }
        let boundary = if refusal.is_none() {
            serde_json::Value::Null
        } else if scope == "entries-per-cmt" {
            serde_json::json!({"ifdOffset":directories[0].0,"entryIndex":0,"declaredCount":4097,"priorEntries":0})
        } else if scope.contains("depth") {
            serde_json::json!({"depth":17})
        } else {
            serde_json::json!({"index":4096})
        };
        manifest.push(serde_json::json!({"id":name,"length":bytes.len(),"sha256":format!("{:x}",Sha256::digest(&bytes)),"boxes":structures::boxes(&bytes).len(),"scope":scope,"denominator":denominator,"default":default,"refusal":refusal,"requests":trace.borrow().len(),"logicalRequestedBytes":trace.borrow().iter().map(|r|r.requested).sum::<usize>(),"lastRequest":trace.borrow().last(),"firstRefusedBoundary":boundary,"cmt4Directories":directories,"timedRecordExtents":records}));
    }
    if let Some(dir) = &export {
        fs::write(
            dir.join("structural-manifest.json"),
            serde_json::to_vec_pretty(&manifest).unwrap(),
        )
        .unwrap();
    }
}

#[test]
fn entry_denominator_is_per_cmt_not_whole_file() {
    let bytes = structures::entries(4096);
    let metadata = reader::read(Cursor::new(&bytes), Limits::default()).unwrap();
    // CMT4 alone has 4096 ignored one-byte fields; other CMTs add their
    // ordinary entries, so success excludes a whole-file 4096 denominator.
    assert!(metadata.opaque.len() > 4096);
    reader::read(
        Cursor::new(structures::split_entries(2048)),
        Limits::default(),
    )
    .unwrap();
    let bytes = structures::split_entries(2049);
    assert_eq!(
        structures::cmt4_directories(&bytes)
            .iter()
            .map(|v| v.2)
            .sum::<usize>(),
        4097
    );
    assert_eq!(
        reader::read(Cursor::new(&bytes), Limits::default())
            .unwrap_err()
            .message,
        "TIFF entry limit exceeded"
    );
    reader::read(
        Cursor::new(&bytes),
        Limits {
            entries: 4097,
            ..Limits::default()
        },
    )
    .unwrap();
}

#[test]
fn hard_configuration_ceilings_are_checked_without_saturated_inputs() {
    let bytes = support::fixture().bytes;
    for count in [65535, 65536, 65537] {
        for which in 0..3 {
            let mut limits = Limits::default();
            match which {
                0 => limits.boxes = count,
                1 => limits.entries = count,
                _ => limits.records = count,
            }
            let (source, trace) = recording::RecordingSource::new(&bytes);
            let result = reader::read(source, limits);
            if count <= 65536 {
                result.unwrap();
            } else {
                assert!(trace.borrow().is_empty());
                assert_eq!(
                    result.unwrap_err().message,
                    "Reader limit exceeds its supported ceiling"
                );
            }
        }
    }
    for depth in [63, 64, 65] {
        let (source, trace) = recording::RecordingSource::new(&bytes);
        let result = reader::read(
            source,
            Limits {
                depth,
                ..Limits::default()
            },
        );
        if depth <= 64 {
            result.unwrap();
        } else {
            assert!(trace.borrow().is_empty());
            assert_eq!(
                result.unwrap_err().message,
                "Reader limit exceeds its supported ceiling"
            );
        }
    }
}
