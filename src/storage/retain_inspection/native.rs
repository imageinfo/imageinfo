use super::*;
use imageinfo_windows_storage::{ExistingRoot, FileSnapshot, GuardedSource};
use sha2::{Digest, Sha256};
use std::{fs, io, os::windows::fs::MetadataExt};

pub(super) struct Inspection {
    root: ExistingRoot,
    path: std::path::PathBuf,
    leaves: [String; 3],
    names: Vec<OsString>,
    slots: [SlotRead; 3],
}

enum SlotRead {
    Missing,
    Unavailable(Issue),
    Present {
        guard: Box<GuardedSource>,
        artifact: ArtifactObservation,
    },
}

fn issue(error: io::Error) -> Issue {
    match error.kind() {
        io::ErrorKind::Unsupported => Issue::Unsupported,
        io::ErrorKind::NotFound => Issue::Conflict,
        io::ErrorKind::Other if error.raw_os_error().is_none() => Issue::Conflict,
        _ => Issue::Inaccessible,
    }
}

fn entries(root: &ExistingRoot, path: &Path) -> Result<Vec<OsString>, Issue> {
    // ExistingRoot::entries has a separate five-entry protocol limit. Keep its
    // checked lineage and bracket this diagnostic's own bounded listing.
    root.check().map_err(issue)?;
    let mut names = Vec::new();
    for entry in fs::read_dir(path)
        .map_err(issue)?
        .take(MAX_ROOT_ENTRIES + 1)
    {
        if names.len() == MAX_ROOT_ENTRIES {
            return Err(Issue::EntryBound);
        }
        names.push(entry.map_err(issue)?.file_name());
    }
    root.check().map_err(issue)?;
    names.sort();
    Ok(names)
}

impl ArtifactObservation {
    pub(super) fn observed(snapshot: &FileSnapshot, bytes: &[u8]) -> Self {
        Self {
            identity: Identity {
                volume_serial: snapshot.volume_serial_number,
                file_index: snapshot.file_index,
            },
            snapshot: Snapshot {
                size: snapshot.size,
                links: snapshot.links,
                attributes: snapshot.attributes,
                creation_time: snapshot.creation_time,
                last_write_time: snapshot.last_write_time,
                owner_dacl: snapshot.owner_dacl.clone(),
            },
            sha256: Sha256::digest(bytes).into(),
        }
    }
}

fn folded_matches(name: &std::ffi::OsStr, leaf: &str) -> bool {
    // Match the SDK's case-fold rejection for observed names, including an
    // observed non-ASCII spelling that folds to a selected ASCII name.
    name.to_string_lossy().to_uppercase() == leaf.to_ascii_uppercase()
}

fn absent(path: &Path) -> Result<(), Issue> {
    // Read only no-follow metadata for the explicitly selected spelling. This
    // catches resolvable aliases (including DOS short names) absent from the
    // long-name listing, without reading any aliased default stream.
    match fs::symlink_metadata(path) {
        Err(error) if error.kind() == io::ErrorKind::NotFound => Ok(()),
        Err(error) => Err(issue(error)),
        Ok(_) => Err(Issue::Conflict),
    }
}

fn read_slot(root: &Path, names: &[OsString], leaf: &str) -> Result<SlotRead, Issue> {
    let mut matching = names.iter().filter(|name| folded_matches(name, leaf));
    let path = root.join(leaf);
    match matching.next() {
        None => {
            absent(&path)?;
            return Ok(SlotRead::Missing);
        }
        Some(name) if name != leaf || matching.next().is_some() => return Err(Issue::Unsupported),
        Some(_) => {}
    }

    let metadata = fs::symlink_metadata(&path).map_err(issue)?;
    // FILE_ATTRIBUTE_REPARSE_POINT also covers junctions and other reparse
    // types that std does not describe as symbolic links.
    if metadata.file_attributes() & 0x400 != 0 || !metadata.is_file() {
        return Err(Issue::Unsupported);
    }
    let mut guard = GuardedSource::open(&path, MAX_ARTIFACT_BYTES).map_err(issue)?;
    let bytes = guard.read_exact_bytes().map_err(issue)?;
    let artifact = ArtifactObservation::observed(guard.snapshot(), &bytes);
    if artifact.snapshot.owner_dacl.len() > MAX_OWNER_DACL_BYTES {
        return Err(Issue::Unsupported);
    }
    Ok(SlotRead::Present {
        guard: Box::new(guard),
        artifact,
    })
}

impl Inspection {
    pub(super) fn collect(path: &Path, leaves: [&str; 3]) -> Result<Self, Refusal> {
        // Validate all joined native path lengths even for currently missing
        // slots, whose metadata-only probes do not use GuardedSource::open.
        use std::os::windows::ffi::OsStrExt;
        if leaves.iter().any(|leaf| {
            path.join(leaf).as_os_str().encode_wide().count() > 200
                || imageinfo_windows_storage::validate_leaf(leaf).is_err()
        }) {
            return Err(Refusal::InvalidSlots);
        }
        let root = ExistingRoot::open(path).map_err(|error| Refusal::Root(issue(error)))?;
        let names = entries(&root, path).map_err(Refusal::Root)?;
        let slots =
            leaves.map(|leaf| read_slot(path, &names, leaf).unwrap_or_else(SlotRead::Unavailable));
        Ok(Self {
            root,
            path: path.into(),
            leaves: leaves.map(str::to_owned),
            names,
            slots,
        })
    }

    pub(super) fn finish(mut self, expected: &Expectation) -> Report {
        // Recheck every selected observation while all successful file guards
        // remain held, then confirm the complete bounded root listing again.
        let slots = std::array::from_fn(|index| match &mut self.slots[index] {
            SlotRead::Missing => match absent(&self.path.join(&self.leaves[index])) {
                Ok(()) => SlotObservation::Missing,
                Err(issue) => SlotObservation::Unavailable(issue),
            },
            SlotRead::Unavailable(issue) => SlotObservation::Unavailable(*issue),
            SlotRead::Present { guard, artifact } => match guard.check() {
                Ok(()) => SlotObservation::Present {
                    association: associate(artifact, expected),
                    artifact: artifact.clone(),
                },
                Err(error) => SlotObservation::Unavailable(issue(error)),
            },
        });
        let listing = entries(&self.root, &self.path).and_then(|names| {
            if names == self.names {
                Ok(names)
            } else {
                Err(Issue::Conflict)
            }
        });
        match listing {
            Ok(names) => Report {
                disposition: disposition(&slots),
                slots,
                unexpected_entries: Some(
                    names
                        .into_iter()
                        .filter(|name| !self.leaves.iter().any(|leaf| name == leaf.as_str()))
                        .collect(),
                ),
                root_issue: None,
            },
            Err(issue) => Report {
                disposition: Disposition::IncompleteOrUncertain,
                slots: slots.map(|slot| match slot {
                    SlotObservation::Unavailable(_) => slot,
                    _ => SlotObservation::Unavailable(issue),
                }),
                unexpected_entries: None,
                root_issue: Some(issue),
            },
        }
    }
}
