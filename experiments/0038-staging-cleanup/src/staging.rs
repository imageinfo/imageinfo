//! Portable #0040 logical-byte limits, not filesystem allocation reservations.
use std::io::{self, Read, Write};

/// Check every planned artifact before the caller creates any of them.
pub fn check_budget(lengths: &[u64], limit: u64) -> io::Result<u64> {
    let total = lengths.iter().try_fold(0u64, |total, length| {
        total
            .checked_add(*length)
            .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidInput, "SCRATCH_SIZE_OVERFLOW"))
    })?;
    if total > limit {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "SCRATCH_BYTE_LIMIT_EXCEEDED",
        ));
    }
    Ok(total)
}

/// Write at most `length` bytes to a fresh destination; require exact source EOF.
/// Errors can leave a partial destination. They never authorize publication or
/// return its capacity to a budget: retained partial files still consume space.
pub fn copy_exact<R: Read, W: Write>(
    source: &mut R,
    destination: &mut W,
    length: u64,
) -> io::Result<()> {
    if io::copy(&mut Read::by_ref(source).take(length), destination)? != length {
        return Err(io::Error::new(
            io::ErrorKind::UnexpectedEof,
            "STAGE_SOURCE_SHORT",
        ));
    }
    // Probe without writing the extra byte. `length + 1` would overflow at
    // u64::MAX, and copying that byte would exceed the planned scratch bound.
    loop {
        match source.read(&mut [0; 1]) {
            Ok(0) => return Ok(()),
            Ok(_) => {
                return Err(io::Error::new(
                    io::ErrorKind::InvalidData,
                    "STAGE_SOURCE_LONG",
                ));
            }
            Err(error) if error.kind() == io::ErrorKind::Interrupted => continue,
            Err(error) => return Err(error),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Cursor;

    #[test]
    fn total_includes_all_artifacts_and_checks_the_exact_boundary() {
        assert_eq!(check_budget(&[65536, 31], 65567).unwrap(), 65567);
        assert_eq!(
            check_budget(&[65536, 31], 65566).unwrap_err().to_string(),
            "SCRATCH_BYTE_LIMIT_EXCEEDED"
        );
        assert_eq!(check_budget(&[], 0).unwrap(), 0);
        assert_eq!(check_budget(&[0, 0], 0).unwrap(), 0);
    }

    #[test]
    fn total_never_wraps_or_saturates_into_an_admitted_budget() {
        assert_eq!(check_budget(&[u64::MAX], u64::MAX).unwrap(), u64::MAX);
        assert_eq!(
            check_budget(&[u64::MAX, 1], u64::MAX)
                .unwrap_err()
                .to_string(),
            "SCRATCH_SIZE_OVERFLOW"
        );
    }

    #[test]
    fn exact_streams_cover_empty_small_and_multi_buffer_copies() {
        for length in [0, 1, 65535, 65536, 65537, 131073] {
            let data: Vec<_> = (0..length).map(|n| (n % 251) as u8).collect();
            let mut destination = Vec::new();
            copy_exact(&mut Cursor::new(&data), &mut destination, length as u64).unwrap();
            assert_eq!(destination, data);
        }
    }

    #[test]
    fn shorter_source_leaves_only_its_written_prefix() {
        let mut destination = Vec::new();
        let error = copy_exact(&mut Cursor::new(b"short"), &mut destination, 6).unwrap_err();
        assert_eq!(error.kind(), io::ErrorKind::UnexpectedEof);
        assert_eq!(destination, b"short");
    }

    #[test]
    fn longer_source_never_writes_the_extra_byte() {
        for length in [0, 1, 16] {
            let mut destination = Vec::new();
            let error = copy_exact(&mut io::repeat(8), &mut destination, length).unwrap_err();
            assert_eq!(error.kind(), io::ErrorKind::InvalidData);
            assert_eq!(destination, vec![8; length as usize]);
        }
    }

    struct Chunks {
        bytes: Cursor<Vec<u8>>,
        interrupt: bool,
    }
    impl Read for Chunks {
        fn read(&mut self, buffer: &mut [u8]) -> io::Result<usize> {
            if std::mem::take(&mut self.interrupt) {
                return Err(io::ErrorKind::Interrupted.into());
            }
            self.interrupt = true;
            let length = buffer.len().min(3);
            self.bytes.read(&mut buffer[..length])
        }
    }

    #[test]
    fn short_reads_and_interrupted_reads_including_eof_probe_are_supported() {
        let data = vec![4; 23];
        let mut source = Chunks {
            bytes: Cursor::new(data.clone()),
            interrupt: true,
        };
        let mut destination = Vec::new();
        copy_exact(&mut source, &mut destination, 23).unwrap();
        assert_eq!(destination, data);
    }

    struct LimitedWriter {
        bytes: Vec<u8>,
        remaining: usize,
        zero: bool,
        interrupt: bool,
    }
    impl Write for LimitedWriter {
        fn write(&mut self, buffer: &[u8]) -> io::Result<usize> {
            if std::mem::take(&mut self.interrupt) {
                return Err(io::ErrorKind::Interrupted.into());
            }
            self.interrupt = true;
            if self.remaining == 0 {
                return if self.zero {
                    Ok(0)
                } else {
                    Err(io::Error::other("INJECTED_SINK_FAILURE"))
                };
            }
            let length = buffer.len().min(self.remaining).min(3);
            self.bytes.extend_from_slice(&buffer[..length]);
            self.remaining -= length;
            Ok(length)
        }
        fn flush(&mut self) -> io::Result<()> {
            panic!("copy does not claim persistence")
        }
    }

    #[test]
    fn short_writes_and_interrupted_writes_are_supported() {
        let mut destination = LimitedWriter {
            bytes: Vec::new(),
            remaining: 23,
            zero: false,
            interrupt: true,
        };
        copy_exact(&mut Cursor::new([2; 23]), &mut destination, 23).unwrap();
        assert_eq!(destination.bytes, [2; 23]);
    }

    #[test]
    fn sink_failure_or_write_zero_retains_a_partial_prefix_without_success() {
        for zero in [false, true] {
            let mut destination = LimitedWriter {
                bytes: Vec::new(),
                remaining: 5,
                zero,
                interrupt: false,
            };
            let error = copy_exact(&mut Cursor::new([9; 23]), &mut destination, 23).unwrap_err();
            assert_eq!(
                error.kind(),
                if zero {
                    io::ErrorKind::WriteZero
                } else {
                    io::ErrorKind::Other
                }
            );
            assert_eq!(destination.bytes, [9; 5]);
        }
    }

    struct BrokenReader;
    impl Read for BrokenReader {
        fn read(&mut self, _: &mut [u8]) -> io::Result<usize> {
            Err(io::Error::other("INJECTED_SOURCE_FAILURE"))
        }
    }

    #[test]
    fn source_and_eof_probe_errors_are_not_eof_or_success() {
        for length in [0, 1] {
            let mut destination = Vec::new();
            let error = copy_exact(&mut BrokenReader, &mut destination, length).unwrap_err();
            assert_eq!(error.to_string(), "INJECTED_SOURCE_FAILURE");
            assert!(destination.is_empty());
        }
    }

    #[test]
    fn large_lengths_do_not_require_a_large_allocation_or_an_overflowing_probe() {
        let mut destination = Vec::new();
        assert_eq!(
            copy_exact(&mut Cursor::new([1, 2]), &mut destination, u64::MAX)
                .unwrap_err()
                .kind(),
            io::ErrorKind::UnexpectedEof
        );
        assert_eq!(destination, [1, 2]);
    }
}
