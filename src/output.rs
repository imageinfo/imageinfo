//! Versioned output records for the foundation's implemented operations.

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

use crate::{CAPABILITY_DATA_REVISION, VERSION};

#[derive(Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct VersionInfo {
    pub schema_version: u32,
    pub kind: String,
    pub version: String,
    pub capability_data_revision: String,
    pub media_reading_implemented: bool,
}

impl Default for VersionInfo {
    fn default() -> Self {
        Self {
            schema_version: 1,
            kind: "version".into(),
            version: VERSION.into(),
            capability_data_revision: CAPABILITY_DATA_REVISION.into(),
            media_reading_implemented: false,
        }
    }
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Issue {
    pub code: &'static str,
    pub severity: &'static str,
    pub message: String,
    pub input_id: Option<String>,
    pub path: Option<String>,
    pub occurrence_ref: Option<OccurrenceRef>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct OccurrenceRef {
    pub snapshot_id: String,
    pub occurrence_id: String,
}

/// A request-level refusal before selection or media access. File and artifact
/// arrays are empty because this foundation never discovers or processes inputs.
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ErrorEnvelope {
    pub schema_version: u32,
    pub request_id: String,
    pub request: RequestRecord,
    pub files: [(); 0],
    pub summary: SummaryRecord,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct RequestRecord {
    pub schema_version: u32,
    pub kind: &'static str,
    pub request_id: String,
    pub operation: Option<&'static str>,
    pub mode: Option<&'static str>,
    pub issues: Vec<Issue>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SummaryRecord {
    pub schema_version: u32,
    pub kind: &'static str,
    pub request_id: String,
    pub exit_status: u8,
    pub selection_complete: bool,
    pub counts: Counts,
    pub artifacts: [(); 0],
    pub issues: [(); 0],
    pub interrupted: bool,
    pub output_complete: bool,
}

#[derive(Debug, Serialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct Counts {
    pub discovered: u32,
    pub excluded: u32,
    pub deduplicated: u32,
    pub by_state: BTreeMap<String, u32>,
}

impl ErrorEnvelope {
    pub fn new(
        request_id: String,
        operation: Option<&'static str>,
        code: &'static str,
        message: String,
        exit_status: u8,
    ) -> Self {
        Self {
            schema_version: 1,
            request_id: request_id.clone(),
            request: RequestRecord {
                schema_version: 1,
                kind: "request",
                request_id: request_id.clone(),
                operation,
                mode: operation.map(|_| "read"),
                issues: vec![Issue {
                    code,
                    severity: "error",
                    message,
                    input_id: None,
                    path: None,
                    occurrence_ref: None,
                }],
            },
            files: [],
            summary: SummaryRecord {
                schema_version: 1,
                kind: "summary",
                request_id,
                exit_status,
                selection_complete: false,
                counts: Counts::default(),
                artifacts: [],
                issues: [],
                interrupted: false,
                output_complete: true,
            },
        }
    }
}
