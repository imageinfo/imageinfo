//! Private candidate experiment, not an enabled metadata writer or publisher.
use imageinfo::reader::{self, Limits, Range, Value};
use std::{
    error::Error,
    fs::{self, File, OpenOptions},
    io::{self, Read, Seek, SeekFrom, Write},
    path::Path,
};

type Result<T> = std::result::Result<T, Box<dyn Error>>;
const MAX_FILE: u64 = 256 * 1024 * 1024;
const NEW_DATE: &[u8; 20] = b"2001:02:03 04:05:06\0";

fn main() {
    if let Err(error) = run() {
        eprintln!("Candidate experiment failed: {error}");
        std::process::exit(1);
    }
}

fn run() -> Result<()> {
    let args: Vec<_> = std::env::args_os().skip(1).collect();
    if args.len() != 3 || args[0] != "stage" {
        return Err("Usage: imageinfo-cr3-candidate-probe stage SOURCE DEST.candidate.cr3".into());
    }
    let source_path = Path::new(&args[1]);
    let destination = Path::new(&args[2]);
    if !destination
        .file_name()
        .is_some_and(|s| s.to_string_lossy().ends_with(".candidate.cr3"))
    {
        return Err("Private staging name must end in .candidate.cr3".into());
    }
    if !fs::symlink_metadata(source_path)?.is_file() {
        return Err("Only a regular, directly named source is admitted by this experiment".into());
    }
    let mut source = guarded_source(source_path)?;
    let length = source.metadata()?.len();
    if length > MAX_FILE {
        return Err("Research source exceeds 256 MiB".into());
    }
    let before = reader::read(&mut source, Limits::default())?;
    let targets: Vec<_> = before
        .occurrences
        .iter()
        .filter(|o| o.namespace == "exif" && o.name == "DateTimeOriginal")
        .collect();
    if targets.len() != 1 {
        return Err("Original-date occurrence is missing or ambiguous".into());
    }
    let target = targets[0];
    if target.range.length != 20
        || target.encoding != "ASCII"
        || !target.path.iter().any(|p| p.name == "CMT2")
        || !matches!(target.value, Value::Text(_))
    {
        return Err("Only the declared existing CMT2 20-byte ASCII value is admitted".into());
    }
    if before.occurrences.iter().any(|other| {
        !std::ptr::eq(other, target)
            && other.range.offset < target.range.offset + target.range.length
            && target.range.offset < other.range.offset + other.range.length
    }) {
        return Err("Selected field overlaps another decoded occurrence".into());
    }
    source.seek(SeekFrom::Start(target.range.offset))?;
    let mut old = [0u8; 20];
    source.read_exact(&mut old)?;
    if &old == NEW_DATE {
        println!("{{\"outcome\":\"unchanged\",\"candidateCreated\":false}}");
        return Ok(());
    }

    // create_new is a collision guard for the private staging name. This artifact
    // is not a published output: errors/forced termination may leave it partial.
    let mut candidate = OpenOptions::new()
        .read(true)
        .write(true)
        .create_new(true)
        .open(destination)?;
    copy_with_patch(&mut source, &mut candidate, length, target.range, NEW_DATE)?;
    candidate.flush()?;
    candidate.sync_all()?;
    verify_complement(&mut source, &mut candidate, length, target.range, NEW_DATE)?;
    let after = reader::read(&mut candidate, Limits::default())?;
    if after.length != before.length
        || after.occurrences.len() != before.occurrences.len()
        || after.previews.len() != before.previews.len()
    {
        return Err("Candidate reread changed the declared structure".into());
    }
    for (a, b) in before.occurrences.iter().zip(&after.occurrences) {
        if a.name != b.name || a.namespace != b.namespace || a.range != b.range {
            return Err("Candidate reread moved an occurrence".into());
        }
        if a.range == target.range {
            if b.value != Value::Text("2001:02:03 04:05:06".into()) {
                return Err("Candidate reread did not observe the intended value".into());
            }
        } else if a.value != b.value {
            return Err("Candidate reread changed an unselected value".into());
        }
    }
    for (a, b) in before.previews.iter().zip(&after.previews) {
        if a.name != b.name || a.range != b.range {
            return Err("Candidate reread moved a preview".into());
        }
    }
    println!(
        "{}",
        serde_json::json!({
            "schemaVersion": 1, "outcome": "private-candidate-validated",
            "published": false, "sourceBytes": length,
            "patch": {"offset": target.range.offset, "length": target.range.length},
            "complementBytesCompared": length - target.range.length,
            "preservedDateFields": ["OffsetTimeOriginal", "SubSecTimeOriginal", "all other occurrences"],
            "warning": "Date copies are intentionally not synchronized; storage, authenticity and publication remain unverified"
        })
    );
    Ok(())
}

fn guarded_source(path: &Path) -> io::Result<File> {
    let mut options = OpenOptions::new();
    options.read(true);
    #[cfg(windows)]
    {
        use std::os::windows::fs::OpenOptionsExt;
        // The Windows probe excludes new write/delete handles through the copy
        // and comparison. This does not bind ancestor directories or properties,
        // and is not a certified storage profile. Other platforms lack this guard.
        options.share_mode(1); // FILE_SHARE_READ
    }
    options.open(path)
}

fn copy_with_patch<R: Read + Seek, W: Write>(
    source: &mut R,
    candidate: &mut W,
    length: u64,
    patch: Range,
    replacement: &[u8],
) -> io::Result<()> {
    let end = patch.offset.checked_add(patch.length);
    if end.is_none_or(|end| end > length) || patch.length != replacement.len() as u64 {
        return Err(io::Error::new(io::ErrorKind::InvalidInput, "Invalid patch"));
    }
    source.seek(SeekFrom::Start(0))?;
    let mut buffer = [0u8; 32768];
    let mut position = 0;
    while position < length {
        let count = (length - position).min(buffer.len() as u64) as usize;
        source.read_exact(&mut buffer[..count])?;
        let overlap_start = position.max(patch.offset);
        let overlap_end = (position + count as u64).min(patch.offset + patch.length);
        if overlap_start < overlap_end {
            let start = (overlap_start - position) as usize;
            let finish = (overlap_end - position) as usize;
            let from = (overlap_start - patch.offset) as usize;
            buffer[start..finish].copy_from_slice(&replacement[from..from + finish - start]);
        }
        candidate.write_all(&buffer[..count])?;
        position += count as u64;
    }
    Ok(())
}

fn verify_complement<R: Read + Seek, C: Read + Seek>(
    source: &mut R,
    candidate: &mut C,
    length: u64,
    patch: Range,
    replacement: &[u8],
) -> io::Result<()> {
    source.seek(SeekFrom::Start(0))?;
    candidate.seek(SeekFrom::Start(0))?;
    let mut original = [0u8; 32768];
    let mut output = [0u8; 32768];
    let mut position = 0;
    while position < length {
        let count = (length - position).min(original.len() as u64) as usize;
        source.read_exact(&mut original[..count])?;
        candidate.read_exact(&mut output[..count])?;
        for index in 0..count {
            let absolute = position + index as u64;
            let expected = if absolute >= patch.offset && absolute < patch.offset + patch.length {
                replacement[(absolute - patch.offset) as usize]
            } else {
                original[index]
            };
            if output[index] != expected {
                return Err(io::Error::new(
                    io::ErrorKind::InvalidData,
                    "Unexpected candidate byte",
                ));
            }
        }
        position += count as u64;
    }
    let mut extra = [0u8; 1];
    if candidate.read(&mut extra)? != 0 {
        return Err(io::Error::new(io::ErrorKind::InvalidData, "Candidate grew"));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Cursor;

    #[test]
    fn patch_boundaries_and_independent_corruption_checks() {
        for offset in [0, 32760, 65516] {
            let bytes: Vec<u8> = (0..65536).map(|n| (n % 251) as u8).collect();
            let patch = Range { offset, length: 20 };
            let mut source = Cursor::new(&bytes);
            let mut candidate = Vec::new();
            copy_with_patch(
                &mut source,
                &mut candidate,
                bytes.len() as u64,
                patch,
                NEW_DATE,
            )
            .unwrap();
            let mut expected = bytes.clone();
            expected[offset as usize..offset as usize + 20].copy_from_slice(NEW_DATE);
            assert_eq!(candidate, expected);
            verify_complement(
                &mut source,
                &mut Cursor::new(&candidate),
                bytes.len() as u64,
                patch,
                NEW_DATE,
            )
            .unwrap();
            let untouched = if offset == 0 { 100 } else { 0 };
            candidate[untouched] ^= 1;
            assert!(
                verify_complement(
                    &mut source,
                    &mut Cursor::new(&candidate),
                    bytes.len() as u64,
                    patch,
                    NEW_DATE
                )
                .is_err()
            );
        }
    }

    #[test]
    fn invalid_or_short_source_cannot_finish_candidate() {
        for patch in [
            Range {
                offset: u64::MAX,
                length: 20,
            },
            Range {
                offset: 5,
                length: 20,
            },
            Range {
                offset: 0,
                length: 19,
            },
        ] {
            let mut target = Vec::new();
            assert!(
                copy_with_patch(&mut Cursor::new([0; 20]), &mut target, 20, patch, NEW_DATE)
                    .is_err()
            );
            assert!(target.is_empty());
        }
        assert!(
            copy_with_patch(
                &mut Cursor::new([0; 10]),
                &mut Vec::new(),
                20,
                Range {
                    offset: 0,
                    length: 20
                },
                NEW_DATE
            )
            .is_err()
        );
    }

    #[test]
    fn write_failure_is_not_a_validated_candidate() {
        struct FailAfter(usize);
        impl Write for FailAfter {
            fn write(&mut self, bytes: &[u8]) -> io::Result<usize> {
                if self.0 == 0 {
                    return Err(io::Error::other("Injected scratch failure"));
                }
                let count = self.0.min(bytes.len());
                self.0 -= count;
                Ok(count)
            }
            fn flush(&mut self) -> io::Result<()> {
                Ok(())
            }
        }
        assert!(
            copy_with_patch(
                &mut Cursor::new([0; 40]),
                &mut FailAfter(10),
                40,
                Range {
                    offset: 0,
                    length: 20
                },
                NEW_DATE
            )
            .is_err()
        );
    }

    #[test]
    fn seeded_patch_and_corruption_smoke() {
        let mut state = 0x21c3_u64;
        let mut next = || {
            state = state.wrapping_mul(6364136223846793005).wrapping_add(1);
            state
        };
        for _ in 0..512 {
            let length = 21 + (next() % 70000) as usize;
            let offset = (next() % (length - 19) as u64) as usize;
            let bytes: Vec<_> = (0..length).map(|_| next() as u8).collect();
            let mut source = Cursor::new(&bytes);
            let mut candidate = Vec::new();
            let patch = Range {
                offset: offset as u64,
                length: 20,
            };
            copy_with_patch(&mut source, &mut candidate, length as u64, patch, NEW_DATE).unwrap();
            let mut expected = bytes.clone();
            expected[offset..offset + 20].copy_from_slice(NEW_DATE);
            assert_eq!(candidate, expected);
            // Corrupt a byte outside the permitted span. The independent reread
            // must reject it even when the intended value remains correct.
            let untouched = if offset > 0 { offset - 1 } else { 20 };
            candidate[untouched] ^= 1;
            assert!(
                verify_complement(
                    &mut source,
                    &mut Cursor::new(candidate),
                    length as u64,
                    patch,
                    NEW_DATE
                )
                .is_err()
            );
        }
    }
}
