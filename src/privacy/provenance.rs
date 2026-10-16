//! Conservative provenance refusal at the in-memory OwnerName boundary.
//!
//! Only actual inspected bytes supply observations. A successful scoped check
//! confers neither authenticity nor permission to publish a file.
use crate::{reader, xmp};
use std::io::Cursor;

pub const REVISION: &str = "privacy-provenance-refusal-2026-10-16.1";

#[derive(Debug, Clone, Copy, Default)]
pub enum ProvenanceRequest<'a> {
    /// An explicitly supplied native snapshot is inspected, never discovered by name.
    Preserve {
        native_source: Option<&'a [u8]>,
    },
    /// Neither invalidation nor a force override is implemented.
    Invalidate,
    Force,
    #[default]
    SidecarOnly,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Reason {
    KnownIndicator,
    NativeInspection,
    PacketConstraint,
    UnsupportedInvalidation,
}

#[derive(Debug)]
pub struct ProvenanceRefusal {
    pub reason: Reason,
    /// Every reached native occurrence, retaining the existing code and range.
    pub native_indicators: Vec<reader::admission::Finding>,
    /// Native incomplete-scope/dependency refusals remain independently visible.
    pub native_refusals: Vec<reader::admission::Finding>,
    pub native_error: Option<reader::Error>,
    /// Each exact parsed property is retained, including duplicate/empty values.
    pub packet_indicators: Vec<xmp::Property>,
    /// Whole-property original ranges in the same order, where the bounded
    /// packet profile exposes one (complex properties can remain uninspectable).
    pub packet_ranges: Vec<Option<std::ops::Range<usize>>>,
    /// Declared coupling namespaces can refuse even without a property.
    pub packet_couplings: Vec<xmp::Coupling>,
    pub packet_constraint: Option<xmp::Refusal>,
}

impl ProvenanceRefusal {
    pub fn requested_change_performed(&self) -> bool {
        false
    }
}

fn coupling_namespace(uri: &str) -> bool {
    matches!(
        uri,
        "http://www.w3.org/2000/09/xmldsig#"
            | "http://ns.adobe.com/xap/1.0/mm/"
            | "http://ns.adobe.com/xap/1.0/"
            | "http://ns.adobe.com/xmp/note/"
            | "http://ns.adobe.com/photoshop/1.0/"
    )
}

/// Run before the operation's absent/no-op branch as well as before deletion.
/// A new derivative with unchanged bytes remains subject to this same refusal.
/// Unprovided native sources are unexamined; this API asserts no native absence.
pub fn check_owner_removal(
    packet: &xmp::Packet<'_>,
    request: ProvenanceRequest<'_>,
) -> Result<(), Box<ProvenanceRefusal>> {
    let mut result = ProvenanceRefusal {
        reason: Reason::PacketConstraint,
        native_indicators: Vec::new(),
        native_refusals: Vec::new(),
        native_error: None,
        packet_indicators: packet
            .properties()
            .iter()
            .filter(|p| coupling_namespace(&p.name.namespace))
            .cloned()
            .collect(),
        packet_ranges: packet
            .properties()
            .iter()
            .filter(|p| coupling_namespace(&p.name.namespace))
            .map(|p| packet.property_range(p.ordinal))
            .collect(),
        packet_couplings: packet.couplings().to_vec(),
        packet_constraint: packet.check_edit_constraints().err(),
    };
    if let ProvenanceRequest::Preserve {
        native_source: Some(source),
    } = request
    {
        // The date is an inspection parameter only; no date edit is executed.
        match reader::admission::inspect_with_partial(
            Cursor::new(source),
            reader::admission::DateTime::parse("2000:01:01 00:00:00")
                .expect("fixed inspection date"),
            None,
        ) {
            Ok(observation) => {
                result.native_indicators = observation.known_structures;
                result.native_refusals = observation.refusals;
            }
            Err(failure) => {
                result.native_indicators = failure.partial.known_structures;
                result.native_refusals = failure.partial.refusals;
                result.native_error = Some(failure.error);
            }
        }
    }
    result.reason = if !result.native_indicators.is_empty() {
        Reason::KnownIndicator
    } else if result.native_error.is_some() || !result.native_refusals.is_empty() {
        Reason::NativeInspection
    } else if matches!(
        request,
        ProvenanceRequest::Invalidate | ProvenanceRequest::Force
    ) {
        Reason::UnsupportedInvalidation
    } else if result.packet_constraint.is_some() {
        Reason::PacketConstraint
    } else {
        return Ok(());
    };
    Err(Box::new(result))
}
