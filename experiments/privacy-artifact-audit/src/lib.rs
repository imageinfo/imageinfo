//! Bounded immutable-snapshot observations. No discovery, custody or privacy certificate.
use imageinfo::xmp;
use imageinfo_privacy_coverage_research::{
    self as coverage, Cell, CoverageState, ObservedProperty,
};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

pub const MAX_SLOTS: usize = 64;
pub const MAX_INPUT_BYTES: usize = 256 * 1024 * 1024;
pub const MAX_CELLS: usize = 8192;
pub const MAX_ID_BYTES: usize = 128;
pub const MAX_EFFECTS: usize = 128;

#[derive(Debug, Clone, Copy)]
pub struct Limits {
    pub slots: usize,
    pub input_bytes: usize,
    /// Conservative construction reservations, not just final emitted cells.
    pub cells: usize,
    pub id_bytes: usize,
    pub effects: usize,
}
impl Default for Limits {
    fn default() -> Self {
        Self {
            slots: MAX_SLOTS,
            input_bytes: MAX_INPUT_BYTES,
            cells: MAX_CELLS,
            id_bytes: MAX_ID_BYTES,
            effects: MAX_EFFECTS,
        }
    }
}
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
pub enum ArtifactKind {
    Raw,
    Xmp,
    RecognizedPreview,
    Opaque,
}
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
pub enum Role {
    Original,
    Derivative,
    Backup,
    PartialStaging,
    Recovery,
    Report,
    Failure,
    Other,
}
#[derive(Debug, Clone)]
pub struct ManifestSlot<'a> {
    pub slot_id: &'a str,
    pub operation_id: &'a str,
    pub attempt_id: &'a str,
    pub document_id: &'a str,
    pub kind: ArtifactKind,
    pub role: Role,
    pub parent_slot: Option<&'a str>,
    pub length: usize,
    pub sha256: [u8; 32],
}
#[derive(Debug, Clone)]
pub struct Snapshot<'a> {
    pub slot_id: &'a str,
    pub operation_id: &'a str,
    pub attempt_id: &'a str,
    pub bytes: &'a [u8],
}
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
pub enum RequestedEffect {
    Removed,
    Absent,
}
#[derive(Debug, Clone)]
pub struct EffectClaim<'a> {
    pub before_slot: &'a str,
    pub after_slot: &'a str,
    pub selector: &'a str,
    pub requested: RequestedEffect,
}
#[derive(Debug)]
pub struct Request<'a> {
    pub operation_id: &'a str,
    pub attempt_id: &'a str,
    pub manifest: &'a [ManifestSlot<'a>],
    pub snapshots: &'a [Snapshot<'a>],
    pub claims: &'a [EffectClaim<'a>],
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub enum Issue {
    MissingSnapshot,
    UnexpectedSnapshot,
    DuplicateSlot,
    DuplicateDocument,
    BindingMismatch,
    ConflictingLineage,
    Uninspectable,
    FalseEffectClaim,
}
#[derive(Debug, Serialize)]
pub struct ArtifactReport {
    pub slot_id: String,
    pub document_id: String,
    pub kind: ArtifactKind,
    pub role: Role,
    pub length: usize,
    pub sha256: [u8; 32],
    pub binding_valid: bool,
    pub issues: Vec<Issue>,
    pub cells: Vec<Cell>,
}
#[derive(Debug, Serialize)]
pub struct EffectObservation {
    pub before_slot: String,
    pub after_slot: String,
    pub selector: String,
    pub requested: RequestedEffect,
    /// Same-parser recomputation only, never independent format evidence.
    pub supported: bool,
    pub before_inspectable: bool,
    pub after_inspectable: bool,
    /// Counts are meaningful only when the corresponding inspectable flag is true.
    pub before_occurrences: usize,
    pub after_occurrences: usize,
}
#[derive(Debug, Serialize)]
pub struct Report {
    pub operation_id: String,
    pub attempt_id: String,
    pub catalog_entries: usize,
    pub location_templates: usize,
    pub artifacts: Vec<ArtifactReport>,
    pub effects: Vec<EffectObservation>,
    pub issues: Vec<Issue>,
    pub declared_set_complete: bool,
    /// This API cannot independently enumerate a whole operation or external copies.
    pub independently_enumerated_operation_complete: bool,
    pub privacy_absence_certified: bool,
    pub custody_established: bool,
    pub independent_format_evidence: bool,
    pub construction_cell_reservation: usize,
}
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Refusal {
    Limits,
    Identifier,
    Catalog,
}

pub fn hash(bytes: &[u8]) -> [u8; 32] {
    Sha256::digest(bytes).into()
}

#[derive(Deserialize)]
struct Catalog {
    entries: Vec<Entry>,
}
#[derive(Deserialize)]
struct Entry {
    id: String,
    selector: Selector,
}
#[derive(Deserialize)]
struct Selector {
    kind: String,
    #[serde(rename = "namespaceUri")]
    namespace: Option<String>,
    #[serde(rename = "localName")]
    local: Option<String>,
    locations: Vec<String>,
}

fn valid_id(id: &str, limit: usize) -> bool {
    !id.is_empty() && id.len() <= limit && !id.chars().any(char::is_control)
}

/// Inspect only the declared immutable set. There is deliberately no caller
/// `removed`, `clean`, `complete` or custody assertion accepted by this API.
/// RAW reserves #0088's full 4096-cell construction ceiling before invoking it;
/// its own 32768 opaque-region and root-reader bounds still apply. XMP has at
/// most 128 properties, 13 cells and 128 occurrences per cell. No values or
/// input bytes are copied into this report.
pub fn audit(request: &Request<'_>, limits: Limits) -> Result<Report, Refusal> {
    if limits.slots > MAX_SLOTS
        || limits.input_bytes > MAX_INPUT_BYTES
        || limits.cells > MAX_CELLS
        || limits.id_bytes > MAX_ID_BYTES
        || limits.effects > MAX_EFFECTS
        || request.manifest.len() > limits.slots
        || request.snapshots.len() > limits.slots
        || request.claims.len() > limits.effects
    {
        return Err(Refusal::Limits);
    }
    let id_ok = |id: &str| valid_id(id, limits.id_bytes);
    if !id_ok(request.operation_id) || !id_ok(request.attempt_id) {
        return Err(Refusal::Identifier);
    }
    let mut reservation = 0usize;
    let mut expected_bytes = 0usize;
    for slot in request.manifest {
        if ![
            slot.slot_id,
            slot.operation_id,
            slot.attempt_id,
            slot.document_id,
        ]
        .into_iter()
        .all(id_ok)
            || slot.parent_slot.is_some_and(|id| !id_ok(id))
        {
            return Err(Refusal::Identifier);
        }
        expected_bytes = expected_bytes
            .checked_add(slot.length)
            .ok_or(Refusal::Limits)?;
        reservation = reservation
            .checked_add(match slot.kind {
                ArtifactKind::Raw => coverage::MAX_CELLS,
                ArtifactKind::Xmp => 13,
                ArtifactKind::RecognizedPreview => 28,
                ArtifactKind::Opaque => 0,
            })
            .ok_or(Refusal::Limits)?;
    }
    let mut actual_bytes = 0usize;
    for snapshot in request.snapshots {
        if ![snapshot.slot_id, snapshot.operation_id, snapshot.attempt_id]
            .into_iter()
            .all(id_ok)
        {
            return Err(Refusal::Identifier);
        }
        actual_bytes = actual_bytes
            .checked_add(snapshot.bytes.len())
            .ok_or(Refusal::Limits)?;
    }
    for claim in request.claims {
        if ![claim.before_slot, claim.after_slot, claim.selector]
            .into_iter()
            .all(id_ok)
        {
            return Err(Refusal::Identifier);
        }
    }
    if expected_bytes > limits.input_bytes
        || actual_bytes > limits.input_bytes
        || reservation > limits.cells
    {
        return Err(Refusal::Limits);
    }
    // All caller-controlled dimensions are bounded before constructing results.
    let catalog: Catalog =
        serde_json::from_str(include_str!("../../../docs/privacy/r5-catalog.v1.json"))
            .map_err(|_| Refusal::Catalog)?;
    let native = catalog
        .entries
        .iter()
        .flat_map(|e| &e.selector.locations)
        .filter(|l| l.starts_with("cr3."))
        .count();
    let sidecar = catalog
        .entries
        .iter()
        .flat_map(|e| &e.selector.locations)
        .filter(|l| l.as_str() == "sidecar.xmp")
        .count();
    let preview = catalog
        .entries
        .iter()
        .flat_map(|e| &e.selector.locations)
        .filter(|l| l.starts_with("preview."))
        .count();
    if catalog.entries.len() != 31 || (native, sidecar, preview) != (18, 13, 28) {
        return Err(Refusal::Catalog);
    }
    let mut report = Report {
        operation_id: request.operation_id.into(),
        attempt_id: request.attempt_id.into(),
        catalog_entries: 31,
        location_templates: 59,
        artifacts: Vec::new(),
        effects: Vec::new(),
        issues: Vec::new(),
        declared_set_complete: true,
        independently_enumerated_operation_complete: false,
        privacy_absence_certified: false,
        custody_established: false,
        independent_format_evidence: false,
        construction_cell_reservation: reservation,
    };
    for snapshot in request.snapshots {
        if !request
            .manifest
            .iter()
            .any(|s| s.slot_id == snapshot.slot_id)
        {
            report.issues.push(Issue::UnexpectedSnapshot);
            report.declared_set_complete = false;
        }
    }
    for slot in request.manifest {
        let mut artifact = ArtifactReport {
            slot_id: slot.slot_id.into(),
            document_id: slot.document_id.into(),
            kind: slot.kind,
            role: slot.role,
            length: slot.length,
            sha256: slot.sha256,
            binding_valid: false,
            issues: Vec::new(),
            cells: Vec::new(),
        };
        if request
            .manifest
            .iter()
            .filter(|s| s.slot_id == slot.slot_id)
            .count()
            != 1
        {
            artifact.issues.push(Issue::DuplicateSlot);
        }
        if request
            .manifest
            .iter()
            .filter(|s| s.document_id == slot.document_id)
            .count()
            != 1
        {
            artifact.issues.push(Issue::DuplicateDocument);
        }
        if slot.operation_id != request.operation_id || slot.attempt_id != request.attempt_id {
            artifact.issues.push(Issue::BindingMismatch);
        }
        // Resolve the entire ancestry and detect self-links, cycles and missing/ambiguous parents.
        let mut ancestor = slot.parent_slot;
        let mut steps = 0;
        while let Some(id) = ancestor {
            steps += 1;
            let mut parents = request.manifest.iter().filter(|s| s.slot_id == id);
            match (parents.next(), parents.next()) {
                (Some(parent), None)
                    if steps <= request.manifest.len()
                        && parent.slot_id != slot.slot_id
                        && parent.operation_id == slot.operation_id
                        && parent.attempt_id == slot.attempt_id =>
                {
                    ancestor = parent.parent_slot;
                }
                _ => {
                    artifact.issues.push(Issue::ConflictingLineage);
                    break;
                }
            }
        }
        let mut matching = request
            .snapshots
            .iter()
            .filter(|s| s.slot_id == slot.slot_id);
        match (matching.next(), matching.next()) {
            (None, _) => artifact.issues.push(Issue::MissingSnapshot),
            (Some(_), Some(_)) => artifact.issues.push(Issue::DuplicateSlot),
            (Some(snapshot), None) => {
                if snapshot.operation_id != slot.operation_id
                    || snapshot.attempt_id != slot.attempt_id
                    || snapshot.bytes.len() != slot.length
                    || hash(snapshot.bytes) != slot.sha256
                {
                    artifact.issues.push(Issue::BindingMismatch);
                }
                if artifact.issues.is_empty() {
                    artifact.binding_valid = true;
                    artifact.cells = inspect(slot, snapshot.bytes, &catalog);
                    if slot.kind == ArtifactKind::Opaque
                        || artifact.cells.is_empty()
                        || artifact.cells.iter().any(|c| {
                            matches!(
                                c.state,
                                CoverageState::Uninspectable | CoverageState::Unexamined
                            )
                        })
                    {
                        artifact.issues.push(Issue::Uninspectable);
                    }
                }
            }
        }
        if artifact.issues.iter().any(|i| *i != Issue::Uninspectable) {
            report.declared_set_complete = false;
        }
        report.artifacts.push(artifact);
    }
    for claim in request.claims {
        let before = report
            .artifacts
            .iter()
            .find(|a| a.slot_id == claim.before_slot);
        let after = report
            .artifacts
            .iter()
            .find(|a| a.slot_id == claim.after_slot);
        let count = |artifact: Option<&ArtifactReport>| -> Option<usize> {
            let a = artifact.filter(|a| a.binding_valid)?;
            let cells: Vec<_> = a
                .cells
                .iter()
                .filter(|c| c.entry_id == claim.selector)
                .collect();
            if cells.is_empty()
                || cells.iter().any(|c| {
                    !matches!(
                        c.state,
                        CoverageState::ObservedRetained
                            | CoverageState::CheckedNoExactPropertyMatch
                    )
                })
            {
                return None;
            }
            Some(cells.iter().map(|c| c.occurrences.len()).sum())
        };
        let before_count = count(before);
        let after_count = count(after);
        let lineage = request
            .manifest
            .iter()
            .find(|s| s.slot_id == claim.after_slot)
            .is_some_and(|s| s.parent_slot == Some(claim.before_slot));
        let supported = lineage
            && after_count == Some(0)
            && match claim.requested {
                RequestedEffect::Removed => before_count.is_some_and(|n| n > 0),
                RequestedEffect::Absent => before_count.is_some(),
            };
        if !supported {
            report.issues.push(Issue::FalseEffectClaim);
        }
        report.effects.push(EffectObservation {
            before_slot: claim.before_slot.into(),
            after_slot: claim.after_slot.into(),
            selector: claim.selector.into(),
            requested: claim.requested,
            supported,
            before_inspectable: before_count.is_some(),
            after_inspectable: after_count.is_some(),
            before_occurrences: before_count.unwrap_or(0),
            after_occurrences: after_count.unwrap_or(0),
        });
    }
    Ok(report)
}

fn inspect(slot: &ManifestSlot<'_>, bytes: &[u8], catalog: &Catalog) -> Vec<Cell> {
    if slot.kind == ArtifactKind::Opaque {
        return Vec::new();
    }
    if slot.kind == ArtifactKind::Raw {
        return coverage::inspect(bytes, None)
            .map(|r| {
                r.cells
                    .into_iter()
                    .filter(|c| c.location != "sidecar.xmp")
                    .map(|mut c| {
                        c.document = format!("{}/{}", slot.document_id, c.document);
                        c
                    })
                    .collect()
            })
            .unwrap_or_default();
    }
    let packet = if slot.kind == ArtifactKind::Xmp {
        Some(xmp::inspect(bytes, xmp::Limits::default()))
    } else {
        None
    };
    let mut cells = Vec::new();
    for entry in &catalog.entries {
        for location in &entry.selector.locations {
            if (slot.kind == ArtifactKind::Xmp && location != "sidecar.xmp")
                || (slot.kind == ArtifactKind::RecognizedPreview
                    && !location.starts_with("preview."))
            {
                continue;
            }
            let mut cell = Cell {
                entry_id: entry.id.clone(),
                location: location.clone(),
                document: slot.document_id.into(),
                state: CoverageState::Uninspectable,
                reason: "unsupported-nested-preview-metadata-or-xmp-packet",
                occurrences: Vec::new(),
                allocation_candidates: Vec::new(),
            };
            if let Some(Ok(packet)) = &packet
                && entry.selector.kind == "xmp"
            {
                for property in packet.properties() {
                    if Some(&property.name.namespace) == entry.selector.namespace.as_ref()
                        && Some(&property.name.local) == entry.selector.local.as_ref()
                    {
                        cell.occurrences.push(ObservedProperty {
                            ordinal: property.ordinal,
                            form: match property.form {
                                xmp::Form::Attribute => "attribute",
                                xmp::Form::Element => "element",
                            },
                            path: format!("rdf-description/property[{}]", property.ordinal),
                        });
                    }
                }
                cell.state = if cell.occurrences.is_empty() {
                    CoverageState::CheckedNoExactPropertyMatch
                } else {
                    CoverageState::ObservedRetained
                };
                cell.reason = "same-root-parser-expanded-name-property-list-observation";
            }
            cells.push(cell);
        }
    }
    cells
}
