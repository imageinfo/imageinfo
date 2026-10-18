//! Internal Windows held-source OwnerName derivative. No output or apply path.
//!
//! The shared guards continuously exclude default-stream writes/name changes;
//! properties are compared at declared checkpoints. No native context is found
//! by filename, and an omitted context remains unexamined.
use super::{RemovalLimits, RemovalRefusal, RemovedOccurrence, provenance::ProvenanceRequest};
use crate::xmp;
use imageinfo_windows_storage::{GuardedSource, MAX_ARTIFACT_BYTES};
use sha2::{Digest, Sha256};
use std::{io, path::Path};

#[derive(Debug, Clone, Copy)]
pub(crate) struct Limits {
    pub sidecar_bytes: u64,
    pub native_bytes: u64,
    pub packet: xmp::Limits,
    pub removal: RemovalLimits,
}

impl Default for Limits {
    fn default() -> Self {
        Self {
            sidecar_bytes: 65_536,
            native_bytes: MAX_ARTIFACT_BYTES,
            packet: xmp::Limits::default(),
            removal: RemovalLimits::default(),
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum Kind {
    Changed,
    Absent,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum NativeStatus {
    Unexamined,
    /// Actual selected bytes passed the existing scoped provenance inspection.
    /// This is not complete native inventory or an authenticity assertion.
    Inspected,
}

#[derive(Debug)]
pub(crate) enum Refusal {
    Guard(io::Error),
    Alias,
    Limit,
    Removal(RemovalRefusal),
    Stale,
}

/// Owned live handles and immutable original observations; deliberately no
/// Clone, serialization, authority importer, output or transaction interface.
pub(crate) struct Prepared {
    sidecar: GuardedSource,
    native: Option<GuardedSource>,
    sidecar_original: Vec<u8>,
    native_original: Option<Vec<u8>>,
    document_id: String,
    limits: Limits,
    candidate: Vec<u8>,
    candidate_identity: [u8; 32],
    removed: Option<RemovedOccurrence>,
    failed: bool,
}

impl Prepared {
    pub(crate) fn bytes(&self) -> &[u8] {
        &self.candidate
    }

    pub(crate) fn removed(&self) -> Option<&RemovedOccurrence> {
        self.removed.as_ref()
    }

    pub(crate) fn kind(&self) -> Kind {
        if self.removed.is_some() {
            Kind::Changed
        } else {
            Kind::Absent
        }
    }

    pub(crate) fn native_status(&self) -> NativeStatus {
        if self.native.is_some() {
            NativeStatus::Inspected
        } else {
            NativeStatus::Unexamined
        }
    }

    pub(crate) fn candidate_identity(&self) -> &[u8; 32] {
        &self.candidate_identity
    }

    /// Recheck exact bytes, live object/name/property bindings and the complete
    /// derivative facts. Any observed failure permanently poisons this hold.
    pub(crate) fn recheck(&mut self) -> Result<(), Refusal> {
        if self.failed {
            return Err(Refusal::Stale);
        }
        let result = self.recheck_inner();
        self.failed |= result.is_err();
        result
    }

    fn recheck_inner(&mut self) -> Result<(), Refusal> {
        if self.sidecar.read_exact_bytes().map_err(Refusal::Guard)? != self.sidecar_original {
            return Err(Refusal::Stale);
        }
        match (&mut self.native, &self.native_original) {
            (Some(guard), Some(original)) => {
                if guard.read_exact_bytes().map_err(Refusal::Guard)? != *original {
                    return Err(Refusal::Stale);
                }
            }
            (None, None) => {}
            _ => return Err(Refusal::Stale),
        }
        if <[u8; 32]>::from(Sha256::digest(&self.candidate)) != self.candidate_identity {
            return Err(Refusal::Stale);
        }
        // Reconstruct from the original immutable source, never from an earlier
        // candidate. The existing implementation independently verifies exact
        // complement, complete supported absence and retained property semantics.
        let expected = super::remove_owner_name(
            &self.document_id,
            &self.sidecar_original,
            self.limits.packet,
            self.limits.removal,
            request(self.native_original.as_deref()),
        )
        .map_err(Refusal::Removal)?;
        if expected.bytes.as_ref() != self.candidate || expected.removed != self.removed {
            return Err(Refusal::Stale);
        }
        // Close the preparation/checkpoint interval after parsing as well.
        self.sidecar.check().map_err(Refusal::Guard)?;
        if let Some(native) = &mut self.native {
            native.check().map_err(Refusal::Guard)?;
        }
        Ok(())
    }
}

fn request(native_source: Option<&[u8]>) -> ProvenanceRequest<'_> {
    ProvenanceRequest::Preserve { native_source }
}

/// Bind one explicitly selected XMP source and an optional explicitly selected
/// native source. Refusals retain the existing provenance detail unchanged.
pub(crate) fn prepare(
    sidecar_path: &Path,
    document_id: &str,
    native_path: Option<&Path>,
    limits: Limits,
) -> Result<Prepared, Refusal> {
    let packet_max = xmp::Limits::default();
    if limits.sidecar_bytes > 65_536
        || limits.native_bytes > MAX_ARTIFACT_BYTES
        || limits.removal.output_bytes > 65_536
        || limits.removal.document_id_bytes > 128
        || limits.packet.bytes > packet_max.bytes
        || limits.packet.nodes > packet_max.nodes
        || limits.packet.depth > packet_max.depth
        || limits.packet.attributes_per_element > packet_max.attributes_per_element
        || limits.packet.namespace_declarations_per_element
            > packet_max.namespace_declarations_per_element
        || limits.packet.properties > packet_max.properties
        || limits.packet.members_per_list > packet_max.members_per_list
        || limits.packet.text_bytes > packet_max.text_bytes
    {
        return Err(Refusal::Limit);
    }
    if document_id.is_empty() || document_id.len() > limits.removal.document_id_bytes {
        return Err(Refusal::Removal(RemovalRefusal::DocumentId));
    }
    let mut sidecar =
        GuardedSource::open(sidecar_path, limits.sidecar_bytes).map_err(Refusal::Guard)?;
    let mut native = native_path
        .map(|path| GuardedSource::open(path, limits.native_bytes))
        .transpose()
        .map_err(Refusal::Guard)?;
    if let Some(native) = &native {
        let a = sidecar.snapshot();
        let b = native.snapshot();
        if a.volume_serial_number == b.volume_serial_number && a.file_index == b.file_index {
            return Err(Refusal::Alias);
        }
    }
    let sidecar_original = sidecar.read_exact_bytes().map_err(Refusal::Guard)?;
    let native_original = native
        .as_mut()
        .map(GuardedSource::read_exact_bytes)
        .transpose()
        .map_err(Refusal::Guard)?;
    let removal = super::remove_owner_name(
        document_id,
        &sidecar_original,
        limits.packet,
        limits.removal,
        request(native_original.as_deref()),
    )
    .map_err(Refusal::Removal)?;
    let candidate = removal.bytes.into_owned();
    let removed = removal.removed;
    let mut prepared = Prepared {
        sidecar,
        native,
        sidecar_original,
        native_original,
        document_id: document_id.into(),
        limits,
        candidate_identity: Sha256::digest(&candidate).into(),
        candidate,
        removed,
        failed: false,
    };
    prepared.recheck()?;
    Ok(prepared)
}

#[cfg(test)]
mod tests;
