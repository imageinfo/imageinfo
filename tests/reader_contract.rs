mod support;
use imageinfo::reader::{self, Limits, Value};
use std::{fs, io::Cursor, process::Command};

#[test]
fn authored_profile_preserves_duplicate_iso_and_stored_fraction() {
    let fixture = support::fixture();
    let metadata = reader::read(Cursor::new(&fixture.bytes), Limits::default()).unwrap();
    let iso: Vec<_> = metadata
        .occurrences
        .iter()
        .filter(|o| o.name == "ISO")
        .collect();
    assert_eq!(iso.len(), 2);
    assert_ne!(iso[0].namespace, iso[1].namespace);
    assert_eq!(iso[0].value, Value::Integer(800));
    assert_eq!(iso[1].value, Value::Integer(800));
    let exposure = metadata
        .occurrences
        .iter()
        .find(|o| o.name == "ExposureTime" && o.namespace == "exif")
        .unwrap();
    assert_eq!(exposure.value, Value::Rational(2, 500));
    assert_eq!(metadata.previews.len(), 3);
    assert!(metadata.bytes_read < fixture.bytes.len() as u64);
}

#[test]
fn preview_outputs_retain_every_stored_byte_and_never_replace() {
    let data = support::fixture();
    let dir = support::TempDir::new();
    let input = dir.path.join("source.cr3");
    fs::write(&input, &data.bytes).unwrap();
    for (tag, bytes) in [
        ("ThumbnailImage", &data.thumbnail),
        ("PreviewImage", &data.preview),
        ("JpgFromRaw", &data.jpeg),
    ] {
        let target = dir.path.join(format!("{tag}.jpg"));
        assert_eq!(
            reader::extract(&input, &target, tag, Limits::default(), true).unwrap(),
            bytes.len() as u64
        );
        assert!(!target.exists());
        reader::extract(&input, &target, tag, Limits::default(), false).unwrap();
        assert_eq!(&fs::read(&target).unwrap(), bytes);
        assert_eq!(
            reader::extract(&input, &target, tag, Limits::default(), false)
                .unwrap_err()
                .code,
            "DESTINATION_EXISTS"
        );
        assert_eq!(&fs::read(&target).unwrap(), bytes);
    }
    assert_eq!(fs::read(&input).unwrap(), data.bytes);
    assert!(!dir.path.read_dir().unwrap().any(|entry| {
        entry
            .unwrap()
            .file_name()
            .to_string_lossy()
            .ends_with(".tmp")
    }));
}

#[test]
fn lengths_cycles_and_limits_fail_without_panics() {
    let fixture = support::fixture();
    for bytes in [
        vec![],
        vec![0; 7],
        vec![0, 0, 0, 4, b'f', b'r', b'e', b'e'],
        [
            vec![0, 0, 0, 1, b'm', b'o', b'o', b'v'],
            u64::MAX.to_be_bytes().to_vec(),
        ]
        .concat(),
    ] {
        assert!(reader::read(Cursor::new(bytes), Limits::default()).is_err());
    }
    for end in [8, 24, 100, fixture.bytes.len() - 1] {
        assert!(reader::read(Cursor::new(&fixture.bytes[..end]), Limits::default()).is_err());
    }
    for limits in [
        Limits {
            metadata_bytes: 32,
            ..Limits::default()
        },
        Limits {
            boxes: 1,
            ..Limits::default()
        },
        Limits {
            depth: 1,
            ..Limits::default()
        },
        Limits {
            entries: 1,
            ..Limits::default()
        },
        Limits {
            records: 0,
            ..Limits::default()
        },
        Limits {
            preview_bytes: 1,
            ..Limits::default()
        },
    ] {
        assert_eq!(
            reader::read(Cursor::new(&fixture.bytes), limits)
                .unwrap_err()
                .code,
            "LIMIT_EXCEEDED"
        );
    }
    let mut cycle = fixture.bytes.clone();
    let at = cycle.windows(4).position(|w| w == b"CMT1").unwrap() + 4;
    let count = u16::from_le_bytes(cycle[at + 8..at + 10].try_into().unwrap()) as usize;
    cycle[at + 10 + count * 12..at + 14 + count * 12].copy_from_slice(&8u32.to_le_bytes());
    assert_eq!(
        reader::read(Cursor::new(cycle), Limits::default())
            .unwrap_err()
            .code,
        "INVALID_STRUCTURE"
    );
}

#[test]
fn unsupported_camera_mode_encoding_and_external_references_are_refused() {
    let fixture = support::fixture();
    let mut variants = Vec::new();
    let mut model = fixture.bytes.clone();
    let at = model
        .windows(12)
        .position(|w| w == b"Canon EOS R5")
        .unwrap();
    model[at + 11] = b'6';
    variants.push(model);
    let mut wavelet = fixture.bytes.clone();
    let at = wavelet.windows(4).rposition(|w| w == b"CMP1").unwrap() + 4;
    wavelet[at + 26] = 3;
    variants.push(wavelet);
    let mut external = fixture.bytes.clone();
    let at = external.windows(4).position(|w| w == b"url ").unwrap() + 4;
    external[at + 3] = 0;
    variants.push(external);
    let mut quality = fixture.bytes.clone();
    let at = support::field_offset(&quality, b"CMT3", 1);
    quality[at + 6..at + 8].copy_from_slice(&3u16.to_le_bytes());
    variants.push(quality);
    let mut dual = fixture.bytes.clone();
    let at = support::field_offset(&dual, b"CMT3", 0x4018);
    dual[at + 44..at + 48].copy_from_slice(&1u32.to_le_bytes());
    variants.push(dual);
    for bytes in variants {
        assert_eq!(
            reader::read(Cursor::new(bytes), Limits::default())
                .unwrap_err()
                .code,
            "CAPABILITY_UNSUPPORTED"
        );
    }
}

#[test]
fn big_endian_tiff_and_64_bit_bmff_headers_preserve_the_same_values() {
    let fixture = support::fixture();
    let expected = reader::read(Cursor::new(&fixture.bytes), Limits::default()).unwrap();
    let mut bytes = fixture.bytes.clone();
    support::big_endian_tiff_boxes(&mut bytes);
    let actual = reader::read(Cursor::new(&bytes), Limits::default()).unwrap();
    assert_eq!(
        expected
            .occurrences
            .iter()
            .map(|o| &o.value)
            .collect::<Vec<_>>(),
        actual
            .occurrences
            .iter()
            .map(|o| &o.value)
            .collect::<Vec<_>>()
    );
    let mut extended = fixture.bytes.clone();
    let at = extended.windows(4).position(|w| w == b"mdat").unwrap() - 4;
    let original_size = u32::from_be_bytes(extended[at..at + 4].try_into().unwrap());
    extended[at..at + 4].copy_from_slice(&1u32.to_be_bytes());
    extended.splice(at + 8..at + 8, (u64::from(original_size) + 8).to_be_bytes());
    let offsets: Vec<_> = extended
        .windows(4)
        .enumerate()
        .filter(|(_, w)| *w == b"co64")
        .map(|(p, _)| p + 12)
        .collect();
    for offset in offsets {
        let value = u64::from_be_bytes(extended[offset..offset + 8].try_into().unwrap()) + 8;
        extended[offset..offset + 8].copy_from_slice(&value.to_be_bytes());
    }
    assert!(reader::read(Cursor::new(extended), Limits::default()).is_ok());
}

#[test]
fn invalid_rational_is_a_partial_failed_file_and_long_text_is_not_truncated() {
    let fixture = support::fixture();
    let dir = support::TempDir::new();
    let mut bytes = fixture.bytes.clone();
    let at = support::field_offset(&bytes, b"CMT2", 0x829a);
    bytes[at + 4..at + 8].copy_from_slice(&0u32.to_le_bytes());
    let invalid = dir.path.join("invalid.cr3");
    fs::write(&invalid, bytes).unwrap();
    let output = Command::new(env!("CARGO_BIN_EXE_imageinfo"))
        .args(["metadata", "read", "--output", "json", "--"])
        .arg(&invalid)
        .output()
        .unwrap();
    assert_eq!(output.status.code(), Some(1));
    let value: serde_json::Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(value["files"][0]["state"], "failed");
    assert_eq!(
        value["files"][0]["snapshot"]["issues"][0]["code"],
        "ZERO_DENOMINATOR"
    );
    let mut paths = Vec::new();
    for i in 0..8 {
        let path = dir.path.join(format!("source-{i}.cr3"));
        fs::write(&path, &fixture.bytes).unwrap();
        paths.push(path);
    }
    let output = Command::new(env!("CARGO_BIN_EXE_imageinfo"))
        .args(["metadata", "read", "--values", "all", "--"])
        .args(&paths)
        .output()
        .unwrap();
    assert!(output.status.success());
    assert!(output.stdout.len() > 4096);
    let text = String::from_utf8(output.stdout).unwrap();
    assert!(text.contains("source-7.cr3"));
    assert_eq!(text.matches("canon:ctmd:ISO").count(), 8);
}

#[test]
fn read_list_extract_and_mixed_failure_use_real_file_records() {
    let data = support::fixture();
    let dir = support::TempDir::new();
    let path = dir.path.join("写真 🦆.jpg");
    fs::write(&path, &data.bytes).unwrap();
    let output = Command::new(env!("CARGO_BIN_EXE_imageinfo"))
        .args([
            "metadata", "read", "--output", "json", "--values", "all", "--tag", "ISO", "--",
        ])
        .arg(&path)
        .output()
        .unwrap();
    assert!(output.status.success());
    let value: serde_json::Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(value["files"][0]["state"], "read");
    assert_eq!(
        value["files"][0]["snapshot"]["occurrences"]
            .as_array()
            .unwrap()
            .len(),
        2
    );
    assert_eq!(
        value["files"][0]["snapshot"]["coverage"][0]["state"],
        "partial"
    );
    let list = Command::new(env!("CARGO_BIN_EXE_imageinfo"))
        .args(["binary", "list", "--output", "json", "--"])
        .arg(&path)
        .output()
        .unwrap();
    assert!(list.status.success());
    let value: serde_json::Value = serde_json::from_slice(&list.stdout).unwrap();
    assert_eq!(
        value["files"][0]["snapshot"]["occurrences"]
            .as_array()
            .unwrap()
            .len(),
        3
    );
    let target = dir.path.join("new.jpg");
    let extract = Command::new(env!("CARGO_BIN_EXE_imageinfo"))
        .args([
            "binary",
            "extract",
            "--tag",
            "PreviewImage",
            "--output-file",
        ])
        .arg(&target)
        .arg("--")
        .arg(&path)
        .output()
        .unwrap();
    assert!(extract.status.success());
    assert_eq!(fs::read(target).unwrap(), data.preview);
    let mixed = Command::new(env!("CARGO_BIN_EXE_imageinfo"))
        .args(["metadata", "read", "--output", "json", "--"])
        .arg(&path)
        .arg(dir.path.join("missing.cr3"))
        .output()
        .unwrap();
    assert_eq!(mixed.status.code(), Some(3));
    let value: serde_json::Value = serde_json::from_slice(&mixed.stdout).unwrap();
    assert_eq!(value["summary"]["counts"]["byState"]["read"], 1);
    assert_eq!(value["summary"]["counts"]["byState"]["failed"], 1);
}

#[test]
fn empty_paths_and_unregistered_selectors_fail_before_reading() {
    for args in [
        vec!["metadata", "read", "--output", "json", "--", ""],
        vec![
            "metadata",
            "read",
            "--output",
            "json",
            "--tag",
            "NoSuchTag",
            "missing.cr3",
        ],
        vec![
            "binary",
            "extract",
            "--output",
            "json",
            "--tag",
            "PreviewImage",
            "--output-file",
            "",
            "missing.cr3",
        ],
    ] {
        let output = Command::new(env!("CARGO_BIN_EXE_imageinfo"))
            .args(&args)
            .output()
            .unwrap();
        assert_eq!(output.status.code(), Some(2), "{args:?}");
        let value: serde_json::Value = serde_json::from_slice(&output.stdout).unwrap();
        assert_eq!(value["files"], serde_json::json!([]));
        assert_eq!(value["summary"]["counts"]["discovered"], 0);
    }
}

#[test]
fn seeded_mutational_fuzz_smoke_exercises_the_actual_reader() {
    let fixture = support::fixture();
    let mut seed = 0x1a2b3c4d_u64;
    for iteration in 0..10000 {
        let mut input = fixture.bytes.clone();
        for _ in 0..1 + iteration % 8 {
            seed = seed.wrapping_mul(6364136223846793005).wrapping_add(1);
            let at = (seed as usize) % input.len();
            input[at] ^= (seed >> 32) as u8;
        }
        if iteration % 4 == 0 {
            input.truncate((seed as usize) % input.len());
        }
        let result = std::panic::catch_unwind(|| {
            reader::read(
                Cursor::new(input),
                Limits {
                    metadata_bytes: 256 * 1024,
                    ..Limits::default()
                },
            )
        });
        assert!(result.is_ok(), "seeded mutation panicked at {iteration}");
    }
}
