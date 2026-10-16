//! Owned Windows byte/name guards and bounded property observations.
//!
//! These primitives do not admit a storage profile, implement a format writer,
//! or establish a committed result. Errors retain created objects. Dropping a
//! guard closes handles without removing files or directories. Same-owner
//! property changes are checked at explicit boundaries, not continuously excluded.

use std::io;
#[cfg(not(windows))]
use std::path::Path;

/// Finite in-memory comparison bound, independent of a caller's logical budget.
pub const MAX_ARTIFACT_BYTES: u64 = 64 * 1024 * 1024;
pub const MAX_RECORD_BYTES: u64 = 65_536;

/// Actual held-object observation. Security text is private account information.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct FileSnapshot {
    pub volume_serial_number: u64,
    pub file_index: u64,
    pub size: u64,
    pub links: u64,
    pub attributes: u32,
    pub creation_time: u64,
    pub last_write_time: u64,
    pub owner_dacl: String,
}

impl FileSnapshot {
    /// Versioned, deterministic in-process binding encoding; not restart authority.
    pub fn binding_bytes(&self) -> Vec<u8> {
        let mut out = b"imageinfo-held-object-v1\0".to_vec();
        for value in [
            self.volume_serial_number,
            self.file_index,
            self.size,
            self.links,
            u64::from(self.attributes),
            self.creation_time,
            self.last_write_time,
            self.owner_dacl.len() as u64,
        ] {
            out.extend_from_slice(&value.to_le_bytes());
        }
        out.extend_from_slice(self.owner_dacl.as_bytes());
        out
    }
}

/// Only an ordinary single leaf is accepted. Case aliases and on-disk names are
/// additionally checked against the actual bound directory on Windows.
pub fn validate_leaf(leaf: &str) -> io::Result<()> {
    let base = leaf.split('.').next().unwrap_or("").to_ascii_uppercase();
    let numbered_device = ["COM", "LPT"].iter().any(|prefix| {
        base.strip_prefix(prefix).is_some_and(|suffix| {
            matches!(
                suffix,
                "1" | "2"
                    | "3"
                    | "4"
                    | "5"
                    | "6"
                    | "7"
                    | "8"
                    | "9"
                    | "\u{b9}"
                    | "\u{b2}"
                    | "\u{b3}"
            )
        })
    });
    if leaf.is_empty()
        || leaf.len() > 100
        || leaf == "."
        || leaf == ".."
        || leaf.chars().any(|c| c < ' ' || "\\/:*?\"<>|".contains(c))
        || leaf.ends_with([' ', '.'])
        || matches!(base.as_str(), "CON" | "PRN" | "AUX" | "NUL")
        || numbered_device
    {
        return Err(io::Error::new(
            io::ErrorKind::Unsupported,
            "UNSUPPORTED_LEAF",
        ));
    }
    Ok(())
}

#[cfg(windows)]
#[allow(unsafe_code)]
mod native;
#[cfg(windows)]
pub(crate) mod windows;
#[cfg(windows)]
pub use windows::{GuardedSource, HeldArtifact, PrivateRoot};
#[cfg(windows)]
mod existing_move;
#[cfg(windows)]
pub use existing_move::{ExistingMoveOutcome, HeldExistingMove};

#[cfg(not(windows))]
mod unsupported {
    use super::*;
    fn refusal<T>() -> io::Result<T> {
        Err(io::Error::new(
            io::ErrorKind::Unsupported,
            "WINDOWS_STORAGE_UNSUPPORTED_PLATFORM",
        ))
    }
    pub struct GuardedSource {
        _private: (),
    }
    pub struct PrivateRoot {
        _private: (),
    }
    pub struct HeldArtifact {
        _private: (),
    }
    impl GuardedSource {
        pub fn open(_: &Path, _: u64) -> io::Result<Self> {
            refusal()
        }
        pub fn snapshot(&self) -> &FileSnapshot {
            unreachable!("unconstructible")
        }
        pub fn check(&mut self) -> io::Result<()> {
            refusal()
        }
        pub fn read_exact_bytes(&mut self) -> io::Result<Vec<u8>> {
            refusal()
        }
    }
    impl PrivateRoot {
        pub fn create(_: &Path) -> io::Result<Self> {
            refusal()
        }
        pub fn path(&self) -> &Path {
            unreachable!("unconstructible")
        }
        pub fn snapshot(&self) -> &FileSnapshot {
            unreachable!("unconstructible")
        }
        pub fn check(&self) -> io::Result<()> {
            refusal()
        }
        pub fn flush(&self) -> io::Result<()> {
            refusal()
        }
        pub fn flush_parent(&self) -> io::Result<()> {
            refusal()
        }
        pub fn create_artifact(&self, _: &str, _: &[u8], _: u64) -> io::Result<HeldArtifact> {
            refusal()
        }
    }
    impl HeldArtifact {
        pub fn snapshot(&self) -> &FileSnapshot {
            unreachable!("unconstructible")
        }
        pub fn bytes(&self) -> &[u8] {
            unreachable!("unconstructible")
        }
        pub fn check(&mut self, _: &PrivateRoot) -> io::Result<()> {
            refusal()
        }
        pub fn flush(&self) -> io::Result<()> {
            refusal()
        }
        pub fn publication_attempted(&self) -> bool {
            false
        }
        pub fn publish_no_replace(&mut self, _: &PrivateRoot, _: &str) -> io::Result<()> {
            refusal()
        }
    }
}
#[cfg(not(windows))]
pub use unsupported::{GuardedSource, HeldArtifact, PrivateRoot};

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn finite_leaf_grammar() {
        for leaf in [
            "",
            ".",
            "..",
            "CON",
            "aux.txt",
            "a:b",
            "a/b",
            "a\\b",
            "a.",
            "a ",
            "x?",
            "LPT1.bin",
            "COM\u{b9}.bin",
            "LPT\u{b2}",
            "COM\u{b3}",
        ] {
            assert!(validate_leaf(leaf).is_err(), "{leaf}");
        }
        for leaf in ["candidate.bin", "prepared.record", "\u{e9}.bin"] {
            validate_leaf(leaf).unwrap();
        }
        // Independent UTF-8 byte controls do not share the matcher's Unicode
        // literal spelling; these are the actual Windows superscript names.
        for bytes in [
            b"COM\xc2\xb9.bin".as_slice(),
            b"LPT\xc2\xb2".as_slice(),
            b"COM\xc2\xb3".as_slice(),
        ] {
            assert!(validate_leaf(std::str::from_utf8(bytes).unwrap()).is_err());
        }
        validate_leaf("COM0.bin").unwrap();
    }
    #[cfg(not(windows))]
    #[test]
    fn other_platform_refuses_before_effects() {
        assert!(PrivateRoot::create(Path::new("nonexistent-root")).is_err());
        assert!(GuardedSource::open(Path::new("nonexistent-source"), 1).is_err());
        assert!(!Path::new("nonexistent-root").exists());
    }
}
