//! One bounded in-memory R5P-026 sidecar derivative. No file publication.
pub mod provenance;

use crate::xmp::{self, Form, Property, Value};
use provenance::{ProvenanceRefusal, ProvenanceRequest};
use std::{borrow::Cow, ops::Range};

pub const OWNER_NAMESPACE: &str = "http://ns.adobe.com/exif/1.0/aux/";
pub const OWNER_LOCAL: &str = "OwnerName";
pub const OWNER_SELECTOR: &str = "R5P-026";

#[derive(Debug, Clone, Copy)]
pub struct RemovalLimits {
    pub output_bytes: usize,
    pub document_id_bytes: usize,
}
impl Default for RemovalLimits {
    fn default() -> Self {
        Self {
            output_bytes: 65_536,
            document_id_bytes: 128,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RemovedOccurrence {
    pub document_id: String,
    pub property: Property,
    /// Whole property only; surrounding whitespace and declarations are retained.
    pub deletion_range: Range<usize>,
}

#[derive(Debug, PartialEq, Eq)]
pub struct OwnerRemoval<'a> {
    pub bytes: Cow<'a, [u8]>,
    /// None means complete supported absence, not an uninspectable inventory.
    pub removed: Option<RemovedOccurrence>,
}

#[derive(Debug)]
pub enum RemovalRefusal {
    Packet(xmp::Refusal),
    Provenance(Box<ProvenanceRefusal>),
    DocumentId,
    Duplicate,
    UnsupportedTarget,
    Range,
    OutputLimit,
    Allocation,
    Verification,
}

/// Inspect the actual immutable snapshot, gate provenance even for an absent
/// target, and prepare one exact deletion. Native/other documents remain outside
/// the result unless explicitly inspected by the provenance request.
pub fn remove_owner_name<'a>(
    document_id: &str,
    original: &'a [u8],
    packet_limits: xmp::Limits,
    limits: RemovalLimits,
    request: ProvenanceRequest<'_>,
) -> Result<OwnerRemoval<'a>, RemovalRefusal> {
    if document_id.is_empty() || document_id.len() > limits.document_id_bytes {
        return Err(RemovalRefusal::DocumentId);
    }
    let packet = xmp::inspect(original, packet_limits).map_err(RemovalRefusal::Packet)?;
    provenance::check_owner_removal(&packet, request).map_err(RemovalRefusal::Provenance)?;
    packet
        .check_edit_constraints()
        .map_err(RemovalRefusal::Packet)?;
    let mut targets = packet.properties().iter().filter(|p| is_owner(p));
    let target = targets.next();
    if targets.next().is_some() {
        return Err(RemovalRefusal::Duplicate);
    }
    let Some(target) = target else {
        if original.len() > limits.output_bytes {
            return Err(RemovalRefusal::OutputLimit);
        }
        return Ok(OwnerRemoval {
            bytes: Cow::Borrowed(original),
            removed: None,
        });
    };
    if !matches!(target.value, Value::Text(_)) {
        return Err(RemovalRefusal::UnsupportedTarget);
    }
    let range = packet
        .deletion_range(target.ordinal)
        .ok_or(RemovalRefusal::UnsupportedTarget)?;
    if range.start >= range.end
        || range.end > original.len()
        || !packet.source().is_char_boundary(range.start)
        || !packet.source().is_char_boundary(range.end)
    {
        return Err(RemovalRefusal::Range);
    }
    // Attribute ranges omit separators. The parser supplies the exact entire
    // name/equal/quoted-value range; preserving both separators keeps XML valid.
    if target.form == Form::Attribute && range.start == 0 {
        return Err(RemovalRefusal::Range);
    }
    let output_len = original
        .len()
        .checked_sub(range.len())
        .ok_or(RemovalRefusal::Range)?;
    if output_len > limits.output_bytes {
        return Err(RemovalRefusal::OutputLimit);
    }
    let mut bytes = Vec::new();
    bytes
        .try_reserve_exact(output_len)
        .map_err(|_| RemovalRefusal::Allocation)?;
    bytes.extend_from_slice(&original[..range.start]);
    bytes.extend_from_slice(&original[range.end..]);
    // Independent exact complement check, followed by a fresh semantic parse.
    if bytes.len() != output_len
        || bytes[..range.start] != original[..range.start]
        || bytes[range.start..] != original[range.end..]
    {
        return Err(RemovalRefusal::Verification);
    }
    let derivative = xmp::inspect(&bytes, packet_limits).map_err(RemovalRefusal::Packet)?;
    if derivative.packet_mode() != packet.packet_mode()
        || derivative.couplings() != packet.couplings()
        || derivative.properties().iter().any(is_owner)
    {
        return Err(RemovalRefusal::Verification);
    }
    let mut remaining = packet
        .properties()
        .iter()
        .filter(|p| p.ordinal != target.ordinal);
    for actual in derivative.properties() {
        let Some(expected) = remaining.next() else {
            return Err(RemovalRefusal::Verification);
        };
        if actual.name != expected.name
            || actual.form != expected.form
            || actual.value != expected.value
        {
            return Err(RemovalRefusal::Verification);
        }
    }
    if remaining.next().is_some() {
        return Err(RemovalRefusal::Verification);
    }
    let mut id = String::new();
    id.try_reserve_exact(document_id.len())
        .map_err(|_| RemovalRefusal::Allocation)?;
    id.push_str(document_id);
    let removed = RemovedOccurrence {
        document_id: id,
        property: target.clone(),
        deletion_range: range,
    };
    Ok(OwnerRemoval {
        bytes: Cow::Owned(bytes),
        removed: Some(removed),
    })
}

fn is_owner(property: &Property) -> bool {
    property.name.namespace == OWNER_NAMESPACE && property.name.local == OWNER_LOCAL
}
