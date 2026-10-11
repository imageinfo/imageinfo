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
            media_reading_implemented: true,
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

/// Request, per-file outcomes and summary share one versioned result envelope.
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ResultEnvelope {
    pub schema_version: u32,
    pub request_id: String,
    pub request: RequestRecord,
    pub files: Vec<FileRecord>,
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
    pub artifacts: Vec<ArtifactRecord>,
    pub issues: Vec<Issue>,
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

impl ResultEnvelope {
    pub fn new(
        request_id: String,
        operation: Option<&'static str>,
        code: &'static str,
        message: String,
        exit_status: u8,
    ) -> Self {
        let mut report = Self::base(request_id, operation, operation.map(|_| "read"));
        report.request.issues.push(Issue {
            code,
            severity: "error",
            message,
            input_id: None,
            path: None,
            occurrence_ref: None,
        });
        report.summary.exit_status = exit_status;
        report
    }

    fn base(
        request_id: String,
        operation: Option<&'static str>,
        mode: Option<&'static str>,
    ) -> Self {
        Self {
            schema_version: 1,
            request_id: request_id.clone(),
            request: RequestRecord {
                schema_version: 1,
                kind: "request",
                request_id: request_id.clone(),
                operation,
                mode,
                issues: Vec::new(),
            },
            files: Vec::new(),
            summary: SummaryRecord {
                schema_version: 1,
                kind: "summary",
                request_id,
                exit_status: 0,
                selection_complete: false,
                counts: Counts::default(),
                artifacts: Vec::new(),
                issues: Vec::new(),
                interrupted: false,
                output_complete: true,
            },
        }
    }
}

#[derive(Debug, Serialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct Effects {
    pub publication_may_have_occurred: bool,
    pub changed: bool,
    pub cleanup_pending: bool,
    pub recovery_ids: Vec<String>,
    pub notes: Vec<String>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct FileRecord {
    pub schema_version: u32,
    pub kind: &'static str,
    pub request_id: String,
    pub input_id: String,
    pub path: String,
    pub state: &'static str,
    pub snapshot: Option<serde_json::Value>,
    pub transaction_id: Option<String>,
    pub effects: Effects,
    pub issues: Vec<Issue>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ArtifactRecord {
    pub kind: &'static str,
    pub path: String,
    pub retained_path: Option<String>,
    pub state: &'static str,
    pub transaction_id: Option<String>,
    pub recovery_ids: Vec<String>,
}

impl ResultEnvelope {
    pub fn empty(request_id: String, operation: &'static str, mode: &'static str) -> Self {
        let mut report = Self::base(request_id, Some(operation), Some(mode));
        report.summary.selection_complete = true;
        report
    }
}
