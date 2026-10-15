//! Bounded read-only privacy coverage observations; no absence certificate/removal.
use imageinfo::reader::{self, Part};
use imageinfo_xmp_model_research::{Limits as XmpLimits, inspect as inspect_xmp};
use serde::{Deserialize, Serialize};
use std::io::Cursor;

pub const MAX_RAW_BYTES: usize = 256 * 1024 * 1024;
pub const MAX_CELLS: usize = 4096;
pub const MAX_OPAQUE_REGIONS: usize = 32_768;

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct Catalog {
    schema_version: u32,
    catalog_id: String,
    revision: u32,
    status: String,
    entries: Vec<Entry>,
}
#[derive(Deserialize)]
struct Entry {
    id: String,
    selector: Selector,
}
#[derive(Deserialize)]
#[serde(tag = "kind", rename_all = "lowercase")]
enum Selector {
    Native {
        namespace: String,
        #[serde(rename = "nativeId")]
        native_id: String,
        locations: Vec<String>,
    },
    Xmp {
        #[serde(rename = "namespaceUri")]
        namespace_uri: String,
        #[serde(rename = "localName")]
        local_name: String,
        locations: Vec<String>,
    },
}
impl Selector {
    fn locations(&self) -> &[String] {
        match self {
            Self::Native { locations, .. } | Self::Xmp { locations, .. } => locations,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum CoverageState {
    ObservedRetained,
    CheckedNoExactPropertyMatch,
    Uninspectable,
    Unexamined,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct AllocationCandidate {
    pub offset: u64,
    pub length: u64,
    pub path: Vec<Part>,
}
#[derive(Debug, Serialize)]
pub struct ObservedProperty {
    pub ordinal: usize,
    pub form: &'static str,
    /// Logical #0081 property-list locator, not an XML byte offset.
    pub path: String,
}
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Cell {
    pub entry_id: String,
    pub location: String,
    pub document: String,
    pub state: CoverageState,
    pub reason: &'static str,
    pub occurrences: Vec<ObservedProperty>,
    /// CMT/numeric tag resemblance only: the public reader loses pointer/IFD role.
    /// These are NOT exact catalog matches or semantically inspected occurrences.
    pub allocation_candidates: Vec<AllocationCandidate>,
}
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DeclaredPreview {
    pub document: String,
    pub reader_name: &'static str,
    pub offset: u64,
    pub length: u64,
}
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Report {
    pub schema_version: u32,
    pub catalog_id: String,
    pub catalog_revision: u32,
    pub reader_revision: &'static str,
    pub source_length: u64,
    pub catalog_entries: usize,
    pub location_templates: usize,
    pub expanded_cells: usize,
    pub declared_previews: Vec<DeclaredPreview>,
    pub cells: Vec<Cell>,
    pub opaque_regions: Vec<AllocationCandidate>,
    pub residuals: Vec<&'static str>,
    pub privacy_absence_certified: bool,
    pub anonymity_established: bool,
    pub removal_implemented: bool,
    pub production_mutation_allowed: bool,
}
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Refusal {
    RawTooLarge,
    Raw { code: &'static str },
    Catalog,
    ReportLimit,
}

fn candidate(path: &[Part], box_name: &str, native_id: u16) -> bool {
    path.iter()
        .any(|part| part.kind == "box" && part.name == box_name)
        && path
            .last()
            .is_some_and(|part| part.kind == "tag" && part.name.parse::<u16>() == Ok(native_id))
}

/// Reads actual immutable RAW bytes with the existing partial native reader. No
/// decoded values, filesystem paths or content hashes are emitted; structural
/// paths and counts/ranges can still be
/// sensitive, so reports from restricted fixtures must remain private.
pub fn inspect(raw: &[u8], sidecar: Option<&[u8]>) -> Result<Report, Refusal> {
    if raw.len() > MAX_RAW_BYTES {
        return Err(Refusal::RawTooLarge);
    }
    let catalog: Catalog =
        serde_json::from_str(include_str!("../../../docs/privacy/r5-catalog.v1.json"))
            .map_err(|_| Refusal::Catalog)?;
    let templates: usize = catalog
        .entries
        .iter()
        .map(|e| e.selector.locations().len())
        .sum();
    if catalog.schema_version != 1
        || catalog.catalog_id != "r5-gps-owner-serial-core"
        || catalog.revision != 1
        || catalog.status != "proposal-only"
        || catalog.entries.len() != 31
        || templates != 59
    {
        return Err(Refusal::Catalog);
    }
    let metadata = reader::read(Cursor::new(raw), reader::Limits::default())
        .map_err(|error| Refusal::Raw { code: error.code })?;
    if metadata.opaque.len() > MAX_OPAQUE_REGIONS {
        return Err(Refusal::ReportLimit);
    }
    let count = metadata
        .previews
        .len()
        .checked_mul(28)
        .and_then(|n| n.checked_add(31))
        .filter(|&n| n <= MAX_CELLS)
        .ok_or(Refusal::ReportLimit)?;
    let sidecar_packet = sidecar.map(|bytes| inspect_xmp(bytes, XmpLimits::default()));
    let previews: Vec<_> = metadata
        .previews
        .iter()
        .enumerate()
        .map(|(index, preview)| DeclaredPreview {
            document: format!("preview-{index}"),
            reader_name: preview.name,
            offset: preview.range.offset,
            length: preview.range.length,
        })
        .collect();
    let mut cells = Vec::with_capacity(count);
    for entry in &catalog.entries {
        for location in entry.selector.locations() {
            if location.starts_with("preview.") {
                for preview in &previews {
                    cells.push(Cell {
                        entry_id: entry.id.clone(),
                        location: location.clone(),
                        document: preview.document.clone(),
                        state: CoverageState::Uninspectable,
                        reason: "declared-preview-metadata-not-parsed",
                        occurrences: Vec::new(),
                        allocation_candidates: Vec::new(),
                    });
                }
                continue;
            }
            let mut cell = Cell {
                entry_id: entry.id.clone(),
                location: location.clone(),
                document: "raw-original".into(),
                state: CoverageState::Uninspectable,
                reason: "native-namespace-role-and-value-uninspectable",
                occurrences: Vec::new(),
                allocation_candidates: Vec::new(),
            };
            match &entry.selector {
                Selector::Native {
                    namespace,
                    native_id,
                    ..
                } => {
                    let box_name = match (namespace.as_str(), location.as_str()) {
                        ("tiff-gps", "cr3.cmt4.gps") => "CMT4",
                        ("tiff-exif", "cr3.cmt2.exif") => "CMT2",
                        ("canon-main", "cr3.cmt3.canon") => "CMT3",
                        _ => return Err(Refusal::Catalog),
                    };
                    let tag = u16::from_str_radix(
                        native_id.strip_prefix("0x").ok_or(Refusal::Catalog)?,
                        16,
                    )
                    .map_err(|_| Refusal::Catalog)?;
                    for (range, path) in &metadata.opaque {
                        if candidate(path, box_name, tag) {
                            cell.allocation_candidates.push(AllocationCandidate {
                                offset: range.offset,
                                length: range.length,
                                path: path.clone(),
                            });
                        }
                    }
                }
                Selector::Xmp {
                    namespace_uri,
                    local_name,
                    ..
                } => {
                    if location != "sidecar.xmp" {
                        return Err(Refusal::Catalog);
                    }
                    cell.document = "explicit-sidecar".into();
                    match &sidecar_packet {
                        None => {
                            cell.state = CoverageState::Unexamined;
                            cell.reason = "sidecar-not-explicitly-selected";
                        }
                        Some(Err(_)) => {
                            cell.reason = "selected-sidecar-outside-bounded-xmp-subset";
                        }
                        Some(Ok(packet)) => {
                            cell.occurrences = packet
                                .properties
                                .iter()
                                .filter(|property| {
                                    &property.name.namespace == namespace_uri
                                        && &property.name.local == local_name
                                })
                                .map(|property| ObservedProperty {
                                    ordinal: property.ordinal,
                                    form: match property.form {
                                        imageinfo_xmp_model_research::Form::Attribute => {
                                            "attribute"
                                        }
                                        imageinfo_xmp_model_research::Form::Element => "element",
                                    },
                                    path: format!("rdf-description/property[{}]", property.ordinal),
                                })
                                .collect();
                            if cell.occurrences.is_empty() {
                                cell.state = CoverageState::CheckedNoExactPropertyMatch;
                                cell.reason =
                                    "no-exact-name-in-completely-parsed-supported-property-list";
                            } else {
                                cell.state = CoverageState::ObservedRetained;
                                cell.reason = "exact-expanded-name-properties-retained-value-validation-not-performed";
                            }
                        }
                    }
                }
            }
            cells.push(cell);
        }
    }
    if cells.len() != count {
        return Err(Refusal::Catalog);
    }
    let opaque_regions = metadata
        .opaque
        .into_iter()
        .map(|(range, path)| AllocationCandidate {
            offset: range.offset,
            length: range.length,
            path,
        })
        .collect();
    Ok(Report {
        schema_version: 1,
        catalog_id: catalog.catalog_id,
        catalog_revision: catalog.revision,
        reader_revision: reader::READER_REVISION,
        source_length: metadata.length,
        catalog_entries: 31,
        location_templates: templates,
        expanded_cells: count,
        declared_previews: previews,
        cells,
        opaque_regions,
        residuals: vec![
            "recognized-preview-inventory-is-not-complete-arbitrary-container-discovery",
            "native-ifd-pointer-role-not-preserved-by-public-reader-candidates-are-not-confirmed-catalog-occurrences",
            "opaque-regions-can-overlap-and-are-not-byte-coverage-or-privacy-completeness",
            "root-embedded-xmp-other-namespaces-canon-substructures-and-catalog-exclusions-remain-uninspectable",
            "sidecar-results-cover-only-the-explicit-supported-packet-property-list",
            "pixels-rendering-data-filenames-logs-backups-recovery-and-external-copies-remain-outside-scope",
        ],
        privacy_absence_certified: false,
        anonymity_established: false,
        removal_implemented: false,
        production_mutation_allowed: false,
    })
}
