//! Read-only bounded restart inspection. Record parsing supplies observations,
//! never authority, replay, cleanup or a claim of an admitted storage profile.

use super::MAX_RECORD_BYTES;
#[cfg(windows)]
use super::custody::{ActionAuthority, CurrentBindings, RestartAction};
#[cfg(any(windows, test))]
use super::runtime::Binding;
use super::runtime::{Artifact, PROTOCOL};

pub(crate) const PROFILE: &str = "windows-ntfs-unqualified-internal-v1";
pub(crate) const IMPLEMENTATION: &str =
    concat!("imageinfo-storage-live-ack-v1-", env!("CARGO_PKG_VERSION"));

/// Explicit caller inputs; records never select filesystem paths or revisions.
pub(crate) struct InspectionSpec<'a> {
    pub operation: &'a str,
    pub format_revision: &'a str,
    pub output: &'a str,
    pub candidate_len: u64,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum InspectionFailure {
    Bound,
    Malformed,
    Changed,
    Namespace,
    Inaccessible,
    Authority,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum Survivor {
    ExpectedAbsent,
    RecoverableInstalled,
    PreviouslyCompleted,
    RecoveryRequired,
}

const ORDER: [Artifact; 4] = [
    Artifact::Prepared,
    Artifact::Intent,
    Artifact::Observation,
    Artifact::Receipt,
];
const PRIOR_PHASES: &[&str] = &[
    "RootFlushed",
    "ParentFlushed",
    "CandidateChecked",
    "CandidateFlushed",
    "CandidateParentFlushed",
    "PreparedCreated",
    "PreparedChecked",
    "PreparedFlushed",
    "PreparedParentFlushed",
    "IntentCreated",
    "IntentChecked",
    "IntentFlushed",
    "IntentParentFlushed",
    "CallerRelease",
    "Prepublication",
    "Publish",
    "Installed",
    "InstalledFlushed",
    "InstalledParentFlushed",
    "InstalledRechecked",
    "ObservationCreated",
    "ObservationChecked",
    "ObservationFlushed",
    "ObservationParentFlushed",
];

struct Cursor<'a> {
    bytes: &'a [u8],
    position: usize,
}
impl<'a> Cursor<'a> {
    fn field(&mut self, max: usize) -> Result<&'a [u8], InspectionFailure> {
        let head = self
            .position
            .checked_add(4)
            .ok_or(InspectionFailure::Bound)?;
        let size = self
            .bytes
            .get(self.position..head)
            .ok_or(InspectionFailure::Malformed)?;
        let size =
            u32::from_le_bytes(size.try_into().map_err(|_| InspectionFailure::Malformed)?) as usize;
        if size > max {
            return Err(InspectionFailure::Bound);
        }
        let end = head.checked_add(size).ok_or(InspectionFailure::Bound)?;
        let value = self
            .bytes
            .get(head..end)
            .ok_or(InspectionFailure::Malformed)?;
        self.position = end;
        Ok(value)
    }
    fn exact(&mut self, value: &[u8]) -> Result<(), InspectionFailure> {
        if self.field(value.len())? != value {
            return Err(InspectionFailure::Malformed);
        }
        Ok(())
    }
}

/// A fixed-schema record has a known binding/phase count; no untrusted count,
/// nesting, path or extension is allocated. Values are borrowed until validated.
type ParsedBindings<'a> = Vec<(&'a [u8], &'a [u8])>;

fn parse<'a>(
    bytes: &'a [u8],
    kind: Artifact,
    spec: &InspectionSpec<'_>,
) -> Result<ParsedBindings<'a>, InspectionFailure> {
    if bytes.is_empty() || bytes.len() > MAX_RECORD_BYTES as usize {
        return Err(InspectionFailure::Bound);
    }
    let index = ORDER
        .iter()
        .position(|v| *v == kind)
        .ok_or(InspectionFailure::Malformed)?;
    let mut cursor = Cursor { bytes, position: 0 };
    for value in [
        PROTOCOL,
        PROFILE,
        IMPLEMENTATION,
        spec.operation,
        spec.format_revision,
        spec.output,
        kind.leaf(),
    ] {
        if value.is_empty() || value.len() > 256 {
            return Err(InspectionFailure::Bound);
        }
        cursor.exact(value.as_bytes())?;
    }
    cursor.exact(&spec.candidate_len.to_le_bytes())?;
    let mut bindings = Vec::with_capacity(3 + index);
    for _ in 0..3 + index {
        let identity = cursor.field(256)?;
        let facts = cursor.field(8192)?;
        if identity.is_empty()
            || facts.is_empty()
            || bindings.iter().any(|(old, _)| *old == identity)
        {
            return Err(InspectionFailure::Malformed);
        }
        bindings.push((identity, facts));
    }
    let phases = [5, 9, 20, 24][index];
    for phase in &PRIOR_PHASES[..phases] {
        cursor.exact(phase.as_bytes())?;
    }
    if cursor.position != bytes.len() {
        return Err(InspectionFailure::Malformed);
    }
    Ok(bindings)
}

#[cfg(windows)]
mod native {
    use super::*;
    use imageinfo_windows_storage::{
        ExistingRoot, FileSnapshot, GuardedSource, MAX_ARTIFACT_BYTES, validate_leaf,
    };
    use sha2::{Digest, Sha256};
    use std::{ffi::OsString, path::Path};

    fn binding(snapshot: &FileSnapshot, bytes: Option<&[u8]>) -> Binding {
        let mut identity = snapshot.volume_serial_number.to_le_bytes().to_vec();
        identity.extend_from_slice(&snapshot.file_index.to_le_bytes());
        let mut facts = snapshot.binding_bytes();
        if let Some(bytes) = bytes {
            facts.extend_from_slice(&Sha256::digest(bytes));
        }
        Binding { identity, facts }
    }
    const PREFIX: &[u8] = b"imageinfo-held-object-v1\0";
    const PARENT: &[u8] = b"held-containing-parent-v1\0";

    fn snapshot_length(bytes: &[u8]) -> Result<usize, InspectionFailure> {
        if !bytes.starts_with(PREFIX) {
            return Err(InspectionFailure::Malformed);
        }
        let start = PREFIX.len() + 7 * 8;
        let length = bytes
            .get(start..start + 8)
            .ok_or(InspectionFailure::Malformed)?;
        let length = usize::try_from(u64::from_le_bytes(length.try_into().unwrap()))
            .map_err(|_| InspectionFailure::Bound)?;
        let end = start
            .checked_add(8)
            .and_then(|n| n.checked_add(length))
            .ok_or(InspectionFailure::Bound)?;
        if end > bytes.len() || length > 8192 {
            return Err(InspectionFailure::Bound);
        }
        Ok(end)
    }

    /// Mutable directory size/write time and the archive bit are excluded by the
    /// existing declared directory policy. All other captured facts must match.
    fn directory_matches(now: &FileSnapshot, old: &[u8]) -> Result<(), InspectionFailure> {
        let length = snapshot_length(old)?;
        if length != old.len() {
            return Err(InspectionFailure::Malformed);
        }
        let mut actual = now.binding_bytes();
        if actual.len() != old.len() {
            return Err(InspectionFailure::Changed);
        }
        for slot in [2, 6] {
            let range = PREFIX.len() + slot * 8..PREFIX.len() + (slot + 1) * 8;
            actual[range.clone()].copy_from_slice(&old[range]);
        }
        let range = PREFIX.len() + 4 * 8..PREFIX.len() + 5 * 8;
        let historic = u64::from_le_bytes(old[range.clone()].try_into().unwrap());
        if u64::from(now.attributes) & !32 != historic & !32 {
            return Err(InspectionFailure::Changed);
        }
        actual[range.clone()].copy_from_slice(&old[range]);
        if actual != old {
            return Err(InspectionFailure::Changed);
        }
        Ok(())
    }

    /// Holds every reacquired read-only guard until dropped. Reacquisition proves
    /// a new check interval only. No mutation-capable object is exposed here.
    pub(crate) struct Inspection {
        root: ExistingRoot,
        source: GuardedSource,
        artifacts: Vec<GuardedSource>,
        names: Vec<OsString>,
        fresh: CurrentBindings,
        installed: bool,
        records: usize,
        /// The first failed fresh check permanently closes this attempt. An
        /// actor reverting a namespace/property change cannot erase its history.
        failed: Option<InspectionFailure>,
        /// Actual current observations remain distinct from historic directory B.
        pub current_root: FileSnapshot,
        pub current_parent: FileSnapshot,
    }
    impl Inspection {
        pub(crate) fn collect(
            source: &Path,
            root_path: &Path,
            spec: &InspectionSpec<'_>,
        ) -> Result<Self, InspectionFailure> {
            validate_leaf(spec.output).map_err(|_| InspectionFailure::Namespace)?;
            if ORDER.iter().any(|v| v.leaf() == spec.output)
                || spec.output == Artifact::Candidate.leaf()
                || spec.candidate_len > MAX_ARTIFACT_BYTES
            {
                return Err(InspectionFailure::Bound);
            }
            let root =
                ExistingRoot::open(root_path).map_err(|_| InspectionFailure::Inaccessible)?;
            let names = root.entries().map_err(|_| InspectionFailure::Namespace)?;
            let contains = |name: &str| names.iter().any(|v| v == name);
            let installed = contains(spec.output);
            if installed == contains(Artifact::Candidate.leaf()) {
                return Err(InspectionFailure::Namespace);
            }
            let count = ORDER.iter().take_while(|v| contains(v.leaf())).count();
            let mut expected = vec![OsString::from(if installed {
                spec.output
            } else {
                Artifact::Candidate.leaf()
            })];
            expected.extend(ORDER[..count].iter().map(|v| OsString::from(v.leaf())));
            expected.sort();
            if names != expected || count == 0 || (!installed && count > 2) {
                return Err(InspectionFailure::Namespace);
            }
            let mut source = GuardedSource::open(source, MAX_ARTIFACT_BYTES)
                .map_err(|_| InspectionFailure::Inaccessible)?;
            let source_bytes = source
                .read_exact_bytes()
                .map_err(|_| InspectionFailure::Changed)?;
            let source_binding = binding(source.snapshot(), Some(&source_bytes));
            let mut candidate = GuardedSource::open(
                &root_path.join(if installed {
                    spec.output
                } else {
                    Artifact::Candidate.leaf()
                }),
                MAX_ARTIFACT_BYTES,
            )
            .map_err(|_| InspectionFailure::Inaccessible)?;
            let candidate_bytes = candidate
                .read_exact_bytes()
                .map_err(|_| InspectionFailure::Changed)?;
            if candidate_bytes.len() as u64 != spec.candidate_len {
                return Err(InspectionFailure::Changed);
            }
            let candidate_binding = binding(candidate.snapshot(), Some(&candidate_bytes));
            let mut artifacts = vec![candidate];
            let mut record_bytes = Vec::new();
            for kind in &ORDER[..count] {
                let mut guard = GuardedSource::open(&root_path.join(kind.leaf()), MAX_RECORD_BYTES)
                    .map_err(|_| InspectionFailure::Inaccessible)?;
                record_bytes.push((
                    *kind,
                    guard
                        .read_exact_bytes()
                        .map_err(|_| InspectionFailure::Changed)?,
                ));
                artifacts.push(guard);
            }
            let first = parse(&record_bytes[0].1, Artifact::Prepared, spec)?;
            let root_end = snapshot_length(first[1].1)?;
            let historic_root = &first[1].1[..root_end];
            let suffix = first[1]
                .1
                .get(root_end..)
                .ok_or(InspectionFailure::Malformed)?;
            let historic_parent = suffix
                .strip_prefix(PARENT)
                .ok_or(InspectionFailure::Malformed)?;
            directory_matches(root.snapshot(), historic_root)?;
            directory_matches(root.parent_snapshot(), historic_parent)?;
            let mut root_binding = binding(root.snapshot(), None);
            if root_binding.identity != first[1].0 {
                return Err(InspectionFailure::Changed);
            }
            root_binding.facts = first[1].1.to_vec();
            let mut parent = binding(root.parent_snapshot(), None);
            parent.facts = historic_parent.to_vec();
            let mut bindings = vec![source_binding, root_binding, candidate_binding];
            for (index, (kind, bytes)) in record_bytes.iter().enumerate() {
                let parsed = parse(bytes, *kind, spec)?;
                if parsed
                    .iter()
                    .zip(&bindings)
                    .any(|((identity, facts), actual)| {
                        *identity != actual.identity || *facts != actual.facts
                    })
                {
                    return Err(InspectionFailure::Changed);
                }
                bindings.push(binding(artifacts[index + 1].snapshot(), Some(bytes)));
            }
            // Every owned regular file must retain the root's ordinary private
            // owner/DACL policy; the independent source has its own exact policy.
            if artifacts
                .iter()
                .any(|g| g.snapshot().owner_dacl != root.snapshot().owner_dacl)
            {
                return Err(InspectionFailure::Changed);
            }
            let fresh = CurrentBindings::capture(
                spec.operation,
                PROFILE,
                IMPLEMENTATION,
                spec.output,
                &parent,
                &bindings,
                &record_bytes,
                installed,
            )
            .map_err(|_| InspectionFailure::Bound)?;
            let current_root = root.snapshot().clone();
            let current_parent = root.parent_snapshot().clone();
            let mut result = Self {
                root,
                source,
                artifacts,
                names,
                fresh,
                installed,
                records: count,
                failed: None,
                current_root,
                current_parent,
            };
            result.recheck()?;
            Ok(result)
        }
        pub(crate) fn bindings(&self) -> &CurrentBindings {
            &self.fresh
        }
        pub(crate) fn recheck(&mut self) -> Result<(), InspectionFailure> {
            if let Some(failure) = self.failed {
                return Err(failure);
            }
            let result = self.recheck_inner();
            if let Err(failure) = result {
                self.failed = Some(failure);
            }
            result
        }
        fn recheck_inner(&mut self) -> Result<(), InspectionFailure> {
            self.source
                .check()
                .map_err(|_| InspectionFailure::Changed)?;
            self.root.check().map_err(|_| InspectionFailure::Changed)?;
            for artifact in &mut self.artifacts {
                artifact.check().map_err(|_| InspectionFailure::Changed)?;
            }
            if self
                .root
                .entries()
                .map_err(|_| InspectionFailure::Namespace)?
                != self.names
            {
                return Err(InspectionFailure::Namespace);
            }
            Ok(())
        }
        /// This consumes one explicit current authority token. A checksum, phase,
        /// current PID, matching path or successful parse cannot invoke it.
        pub(crate) fn classify(
            &mut self,
            action: RestartAction,
            authority: ActionAuthority,
        ) -> Result<Survivor, InspectionFailure> {
            self.recheck()?;
            authority
                .validate(action, &self.fresh)
                .map_err(|_| InspectionFailure::Authority)?;
            match (self.installed, self.records, action) {
                (false, 1..=2, RestartAction::PruneUnpublished) => Ok(Survivor::ExpectedAbsent),
                (true, 4, RestartAction::RecognizeCompletion) => Ok(Survivor::PreviouslyCompleted),
                (true, 3..=4, RestartAction::FinalizeExisting) => {
                    Ok(Survivor::RecoverableInstalled)
                }
                _ => Ok(Survivor::RecoveryRequired),
            }
        }
    }
}
#[cfg(windows)]
#[allow(unused_imports)]
pub(crate) use native::Inspection;

#[cfg(test)]
mod tests;
