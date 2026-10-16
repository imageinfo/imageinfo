//! Internal live RAW/XMP candidate binding. No output effects or apply authority.
//! Mapping/preservation promote the independently authored #0083/#0084/#0104
//! mechanisms through the adopted production XMP packet profile.
mod adapter;
mod mapping;
mod preservation;

use imageinfo_windows_storage::GuardedSource;
use sha2::{Digest, Sha256};
use std::{io, path::Path};

pub(crate) use mapping::ConflictPolicy;
pub(crate) type Loss = mapping::Loss;
pub(crate) use preservation::{Facts, Kind};

/// Bounds are additionally capped by the shared held-source implementation.
pub(crate) struct Limits {
    pub raw_bytes: u64,
    pub sidecar_bytes: u64,
}

impl Default for Limits {
    fn default() -> Self {
        Self {
            raw_bytes: imageinfo_windows_storage::MAX_ARTIFACT_BYTES,
            sidecar_bytes: 65_536,
        }
    }
}

pub(crate) struct Intent<'a> {
    pub target_ordinal: usize,
    pub policy: ConflictPolicy<'a>,
}

#[derive(Debug)]
pub(crate) enum Refusal {
    Selection(crate::pairing::PairingError),
    Guard(io::Error),
    Alias,
    IntentCount,
    InvalidIntent,
    Limit,
    Adapter(adapter::Refusal),
    Stale,
}

/// Deliberately neither Clone nor deserializable. Fields and constructors remain
/// private: a saved plan, byte vector, hash or boolean cannot construct this hold.
pub(crate) struct Prepared {
    raw: GuardedSource,
    sidecar: GuardedSource,
    raw_original: Vec<u8>,
    sidecar_original: Vec<u8>,
    candidate: Vec<u8>,
    candidate_identity: [u8; 32],
    source: Vec<adapter::SourceOccurrence>,
    facts: Facts,
    kind: Kind,
    failed: bool,
}

impl Prepared {
    pub(crate) fn bytes(&self) -> &[u8] {
        &self.candidate
    }

    pub(crate) fn kind(&self) -> Kind {
        self.kind
    }

    pub(crate) fn facts(&self) -> &Facts {
        &self.facts
    }

    pub(crate) fn source(&self) -> &[adapter::SourceOccurrence] {
        &self.source
    }

    pub(crate) fn candidate_identity(&self) -> &[u8; 32] {
        &self.candidate_identity
    }

    /// Fresh declared boundary; any observed conflict permanently poisons it.
    /// Property snapshots are checked by the shared guards without rebasing.
    pub(crate) fn recheck(&mut self) -> Result<(), Refusal> {
        if self.failed {
            return Err(Refusal::Stale);
        }
        let result = (|| {
            if self.raw.read_exact_bytes().map_err(Refusal::Guard)? != self.raw_original
                || self.sidecar.read_exact_bytes().map_err(Refusal::Guard)? != self.sidecar_original
                || <[u8; 32]>::from(Sha256::digest(&self.candidate)) != self.candidate_identity
            {
                return Err(Refusal::Stale);
            }
            Ok(())
        })();
        self.failed |= result.is_err();
        result
    }
}

/// Read one explicitly selected pair from actual guarded objects. Exactly one
/// destination intent is supported: no previous intent/output supplies mapping
/// input. Pair resolution is advisory and never replaces the retained guards.
pub(crate) fn prepare(
    raw_path: &Path,
    sidecar_path: &Path,
    intents: &[Intent<'_>],
    limits: Limits,
) -> Result<Prepared, Refusal> {
    if intents.len() != 1 {
        return Err(Refusal::IntentCount);
    }
    if let ConflictPolicy::ReplaceSelected { acknowledged } = intents[0].policy
        && (acknowledged.len() > 2
            || acknowledged
                .iter()
                .enumerate()
                .any(|(index, loss)| acknowledged[..index].contains(loss)))
    {
        return Err(Refusal::InvalidIntent);
    }
    if limits.raw_bytes > imageinfo_windows_storage::MAX_ARTIFACT_BYTES
        || limits.sidecar_bytes > 65_536
    {
        return Err(Refusal::Limit);
    }
    let pair =
        crate::pairing::resolve_pair(raw_path, Some(sidecar_path)).map_err(Refusal::Selection)?;
    // Open the actual selected spellings: canonical resolver paths cannot hide a
    // selected alias/reparse. The guard independently checks complete ancestry.
    let mut raw = GuardedSource::open(raw_path, limits.raw_bytes).map_err(Refusal::Guard)?;
    let mut sidecar =
        GuardedSource::open(sidecar_path, limits.sidecar_bytes).map_err(Refusal::Guard)?;
    let a = raw.snapshot();
    let b = sidecar.snapshot();
    if a.volume_serial_number == b.volume_serial_number && a.file_index == b.file_index {
        return Err(Refusal::Alias);
    }
    // A fresh resolver observation under both holds must match the first one.
    let fresh =
        crate::pairing::resolve_pair(raw_path, Some(sidecar_path)).map_err(Refusal::Selection)?;
    if pair.raw_path != fresh.raw_path || pair.sidecar_path != fresh.sidecar_path {
        return Err(Refusal::Stale);
    }
    let raw_original = raw.read_exact_bytes().map_err(Refusal::Guard)?;
    let sidecar_original = sidecar.read_exact_bytes().map_err(Refusal::Guard)?;
    let intent = &intents[0];
    let candidate = adapter::prepare(
        &raw_original,
        &sidecar_original,
        intent.target_ordinal,
        intent.policy,
    )
    .map_err(Refusal::Adapter)?;
    let bytes = candidate.prepared.bytes.into_owned();
    let source = candidate.source;
    let facts = candidate.prepared.facts;
    let kind = candidate.prepared.kind;
    let mut prepared = Prepared {
        raw,
        sidecar,
        raw_original,
        sidecar_original,
        candidate_identity: Sha256::digest(&bytes).into(),
        candidate: bytes,
        source,
        facts,
        kind,
        failed: false,
    };
    prepared.recheck()?;
    Ok(prepared)
}

#[cfg(test)]
mod tests;
