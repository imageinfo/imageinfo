//! Read-only observations of three explicitly selected names in a private root.
//! Expectations describe historical observations without authenticating them.

use serde::de::{Deserializer, MapAccess, Visitor, value::MapAccessDeserializer};
use serde::{Deserialize, Serialize};
use std::{ffi::OsString, path::Path};

const SCHEMA: &str = "imageinfo.retain-inspection.v1";
const MAX_ARTIFACT_BYTES: u64 = 64 * 1024 * 1024;
const MAX_OWNER_DACL_BYTES: usize = 8192;
// The existing Windows observer accepts READONLY, ARCHIVE, NORMAL and
// NOT_CONTENT_INDEXED on plain files.
const PLAIN_ATTRIBUTES: u32 = 0x20a1;
#[cfg(windows)]
const MAX_ROOT_ENTRIES: usize = 4096;

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub(crate) struct Identity {
    pub volume_serial: u64,
    pub file_index: u64,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub(crate) struct Snapshot {
    pub size: u64,
    pub links: u64,
    pub attributes: u32,
    pub creation_time: u64,
    pub last_write_time: u64,
    pub owner_dacl: String,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub(crate) struct ArtifactObservation {
    #[serde(deserialize_with = "object")]
    pub identity: Identity,
    #[serde(deserialize_with = "object")]
    pub snapshot: Snapshot,
    pub sha256: [u8; 32],
}

#[derive(Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
struct Expectation {
    schema: String,
    #[serde(deserialize_with = "object")]
    old: ArtifactObservation,
    #[serde(deserialize_with = "object")]
    candidate: ArtifactObservation,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize)]
pub(crate) enum Issue {
    Unsupported,
    Inaccessible,
    Conflict,
    EntryBound,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize)]
pub(crate) enum Refusal {
    UnsupportedPlatform,
    InvalidSlots,
    ExpectationBound,
    MalformedExpectation,
    ContradictoryExpectation,
    Root(Issue),
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize)]
pub(crate) enum Role {
    Old,
    Candidate,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize)]
pub(crate) enum Association {
    Match(Role),
    Mismatch {
        role: Role,
        snapshot_matches: bool,
        sha256_matches: bool,
    },
    Foreign {
        same_bytes_as_old: bool,
        same_bytes_as_candidate: bool,
    },
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
pub(crate) enum SlotObservation {
    Missing,
    Unavailable(Issue),
    Present {
        artifact: ArtifactObservation,
        association: Association,
    },
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize)]
pub(crate) enum Disposition {
    OldNotMoved,
    OldRetainedCandidateStaged,
    InstalledLayoutObserved,
    ForeignCurrentTarget,
    IncompleteOrUncertain,
}

#[derive(Debug, Eq, PartialEq, Serialize)]
pub(crate) struct Report {
    pub disposition: Disposition,
    /// In the caller's target, retained, staging order.
    pub slots: [SlotObservation; 3],
    /// Present only when the selected root's bounded enumeration rechecks.
    pub unexpected_entries: Option<Vec<OsString>>,
    pub root_issue: Option<Issue>,
}

fn object<'de, T: Deserialize<'de>, D: Deserializer<'de>>(input: D) -> Result<T, D::Error> {
    struct Object<T>(std::marker::PhantomData<T>);

    impl<'de, T: Deserialize<'de>> Visitor<'de> for Object<T> {
        type Value = T;

        fn expecting(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
            formatter.write_str("a diagnostic object")
        }

        fn visit_map<M: MapAccess<'de>>(self, map: M) -> Result<T, M::Error> {
            T::deserialize(MapAccessDeserializer::new(map))
        }
    }

    input.deserialize_map(Object(std::marker::PhantomData))
}

fn parse_expectation(bytes: &[u8]) -> Result<Expectation, Refusal> {
    if bytes.len() as u64 > super::MAX_RECORD_BYTES {
        return Err(Refusal::ExpectationBound);
    }
    let mut input = serde_json::Deserializer::from_slice(bytes);
    let parsed: Expectation = object(&mut input).map_err(|_| Refusal::MalformedExpectation)?;
    input.end().map_err(|_| Refusal::MalformedExpectation)?;
    if parsed.schema != SCHEMA {
        return Err(Refusal::MalformedExpectation);
    }
    if parsed.old.identity == parsed.candidate.identity
        || parsed.old.identity.volume_serial != parsed.candidate.identity.volume_serial
    {
        return Err(Refusal::ContradictoryExpectation);
    }
    for artifact in [&parsed.old, &parsed.candidate] {
        let snapshot = &artifact.snapshot;
        if snapshot.size > MAX_ARTIFACT_BYTES || snapshot.owner_dacl.len() > MAX_OWNER_DACL_BYTES {
            return Err(Refusal::ExpectationBound);
        }
        if snapshot.links != 1
            || snapshot.attributes & !PLAIN_ATTRIBUTES != 0
            || snapshot.owner_dacl.is_empty()
            || snapshot.owner_dacl.contains('\0')
        {
            return Err(Refusal::MalformedExpectation);
        }
    }
    Ok(parsed)
}

fn validate_slots(leaves: [&str; 3]) -> Result<(), Refusal> {
    for (index, leaf) in leaves.iter().enumerate() {
        if leaf.is_empty() || leaf.len() > 100 || !leaf.is_ascii() {
            return Err(Refusal::InvalidSlots);
        }
        let stem = leaf
            .split('.')
            .next()
            .unwrap_or_default()
            .trim_end_matches(' ')
            .to_ascii_uppercase();
        if leaf
            .bytes()
            .any(|byte| byte.is_ascii_control() || b"<>:\"/\\|?*".contains(&byte))
            || leaf.ends_with(['.', ' '])
            || matches!(
                stem.as_str(),
                "CON" | "PRN" | "AUX" | "NUL" | "CONIN$" | "CONOUT$"
            )
            || (stem.len() == 4
                && (stem.starts_with("COM") || stem.starts_with("LPT"))
                && matches!(stem.as_bytes()[3], b'1'..=b'9'))
            || leaves[..index]
                .iter()
                .any(|other| other.eq_ignore_ascii_case(leaf))
        {
            return Err(Refusal::InvalidSlots);
        }
    }
    Ok(())
}

#[cfg(any(windows, test))]
fn associate(actual: &ArtifactObservation, expected: &Expectation) -> Association {
    for (role, expected) in [
        (Role::Old, &expected.old),
        (Role::Candidate, &expected.candidate),
    ] {
        if actual.identity == expected.identity {
            let snapshot_matches = actual.snapshot == expected.snapshot;
            let sha256_matches = actual.sha256 == expected.sha256;
            return if snapshot_matches && sha256_matches {
                Association::Match(role)
            } else {
                Association::Mismatch {
                    role,
                    snapshot_matches,
                    sha256_matches,
                }
            };
        }
    }
    Association::Foreign {
        same_bytes_as_old: actual.sha256 == expected.old.sha256,
        same_bytes_as_candidate: actual.sha256 == expected.candidate.sha256,
    }
}

#[cfg(any(windows, test))]
fn disposition(slots: &[SlotObservation; 3]) -> Disposition {
    use Association::{Foreign, Match};
    use Role::{Candidate, Old};
    use SlotObservation::{Missing, Present};

    match slots {
        [
            Present {
                association: Match(Old),
                ..
            },
            Missing,
            Present {
                association: Match(Candidate),
                ..
            },
        ] => Disposition::OldNotMoved,
        [
            Missing,
            Present {
                association: Match(Old),
                ..
            },
            Present {
                association: Match(Candidate),
                ..
            },
        ] => Disposition::OldRetainedCandidateStaged,
        [
            Present {
                association: Match(Candidate),
                ..
            },
            Present {
                association: Match(Old),
                ..
            },
            Missing,
        ] => Disposition::InstalledLayoutObserved,
        [
            Present {
                association: Foreign { .. },
                ..
            },
            Present {
                association: Match(Old),
                ..
            },
            Missing
            | Present {
                association: Match(Candidate),
                ..
            },
        ] => Disposition::ForeignCurrentTarget,
        _ => Disposition::IncompleteOrUncertain,
    }
}

/// Reads only supported selected default streams. Reads may affect access time;
/// comparison covers identity, length, links, attributes, creation/write time,
/// owner/DACL and default-stream bytes under the SDK's existing checks.
pub(crate) fn inspect(
    root: &Path,
    leaves: [&str; 3],
    expectation: &[u8],
) -> Result<Report, Refusal> {
    validate_slots(leaves)?;
    let expected = parse_expectation(expectation)?;
    #[cfg(windows)]
    {
        Ok(native::Inspection::collect(root, leaves)?.finish(&expected))
    }
    #[cfg(not(windows))]
    {
        let _ = (root, expected);
        Err(Refusal::UnsupportedPlatform)
    }
}

#[cfg(windows)]
mod native;
#[cfg(all(test, windows))]
#[path = "retain_inspection/tests/native.rs"]
mod native_tests;
#[cfg(test)]
mod tests;
