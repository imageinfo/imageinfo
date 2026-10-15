//! Source-content revalidation for the nonexecuting single-date preview contract.
use crate::{plan::*, preview, reader};
use sha2::{Digest, Sha256};
use std::{
    fs::File,
    io::{Cursor, Read, Seek, SeekFrom},
    path::Path,
};

pub const MAX_SOURCE_BYTES: u64 = 256 * 1024 * 1024;

#[derive(Debug, serde::Serialize)]
pub struct BoundPreview {
    pub plan: PreviewPlan,
    pub preview: preview::DatePreview,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, serde::Serialize)]
#[serde(rename_all = "snake_case")]
pub enum BindingFinding {
    SourceRevisionChanged,
    OccurrenceMissingOrAmbiguous,
    OccurrenceChanged,
    OriginalBytesChanged,
    FormatAdmissionRefused,
    StorageProfileUnavailable,
}

#[derive(Debug, serde::Serialize)]
pub struct BindingReport {
    /// Equality of the bounded snapshot and exact occurrence only; no live guard.
    pub binding_matches: bool,
    pub source_revision_matches: bool,
    pub occurrence_matches: bool,
    pub original_bytes_match: bool,
    pub findings: Vec<BindingFinding>,
    /// Present only when the exact saved binding still matches. No replanning.
    pub preview: Option<preview::DatePreview>,
    pub production_mutation_allowed: bool,
}

fn error(code: &'static str, message: &str) -> reader::Error {
    reader::Error {
        code,
        message: message.into(),
    }
}

/// Snapshot bytes from a caller-supplied stable stream. Bounded source reads do
/// not establish continuous exclusion or an atomic filesystem snapshot.
fn snapshot<R: Read + Seek>(input: &mut R) -> reader::Result<Vec<u8>> {
    let length = input.seek(SeekFrom::End(0))?;
    if length > MAX_SOURCE_BYTES {
        return Err(error(
            "LIMIT_EXCEEDED",
            "Source exceeds 256 MiB binding bound",
        ));
    }
    input.seek(SeekFrom::Start(0))?;
    let mut bytes = Vec::new();
    input.take(MAX_SOURCE_BYTES + 1).read_to_end(&mut bytes)?;
    if bytes.len() as u64 != length || input.seek(SeekFrom::End(0))? != length {
        return Err(error(
            "SOURCE_CHANGED",
            "Source length changed during bounded snapshot",
        ));
    }
    Ok(bytes)
}

fn digest(bytes: &[u8]) -> Sha256Digest {
    // SHA-256 produces exactly 32 bytes; this format is always validated hex.
    let hex = format!("{:x}", Sha256::digest(bytes));
    Sha256Digest::try_from(hex).expect("SHA-256 hex has the contract shape")
}

fn unique_occurrence(metadata: &reader::Metadata) -> Option<&reader::Occurrence> {
    let mut targets = metadata.occurrences.iter().filter(|o| {
        o.namespace == "exif"
            && o.name == "DateTimeOriginal"
            && o.path.iter().any(|p| p.kind == "box" && p.name == "CMT2")
    });
    let only = targets.next()?;
    if targets.next().is_some() {
        None
    } else {
        Some(only)
    }
}

fn occurrence(bytes: &[u8], target: &reader::Occurrence) -> reader::Result<OccurrenceBinding> {
    let range = reader::Range::checked(target.range.offset, 20, bytes.len() as u64)?;
    if target.range.length != 20 || target.encoding != "ASCII" {
        return Err(error(
            "FIELD_SHAPE_UNVERIFIED",
            "Expected existing ASCII20 allocation",
        ));
    }
    let original_bytes = bytes[range.offset as usize..range.end() as usize]
        .try_into()
        .expect("checked 20-byte range");
    let byte_order = match target.order {
        "little" => ByteOrder::LittleEndian,
        "big" => ByteOrder::BigEndian,
        _ => return Err(error("FIELD_SHAPE_UNVERIFIED", "Unknown TIFF byte order")),
    };
    let path = target
        .path
        .iter()
        .map(|part| {
            Ok(OccurrencePart {
                kind: part.kind.into(),
                name: part.name.clone(),
                index: u32::try_from(part.index)
                    .map_err(|_| error("LIMIT_EXCEEDED", "Occurrence index exceeds contract"))?,
            })
        })
        .collect::<reader::Result<Vec<_>>>()?;
    Ok(OccurrenceBinding {
        path,
        native_id: 0x9003,
        allocation: Allocation {
            offset: range.offset,
            length: range.length,
        },
        byte_order,
        original_bytes,
    })
}

/// Capture a source-content assertion and exact intent, even when format
/// admission refuses. Source/output strings are inert caller-supplied locators.
pub fn capture<R: Read + Seek>(
    mut input: R,
    source_path: &str,
    output_path: &str,
    proposed: &str,
) -> reader::Result<BoundPreview> {
    let date = reader::admission::DateTime::parse(proposed)?;
    let bytes = snapshot(&mut input)?;
    let metadata = reader::read(Cursor::new(&bytes), reader::Limits::default())?;
    let target = unique_occurrence(&metadata).ok_or_else(|| {
        error(
            "FIELD_MISSING_OR_AMBIGUOUS",
            "Expected exactly one CMT2 DateTimeOriginal",
        )
    })?;
    let selected = occurrence(&bytes, target)?;
    let preview = preview::date_time_original(Cursor::new(&bytes), proposed, Some(target.range))?;
    if !preview.field_shape_verified || preview.original_bytes != Some(selected.original_bytes) {
        return Err(error(
            "FIELD_SHAPE_UNVERIFIED",
            "Stored bytes are not the supported Gregorian ASCII20 date",
        ));
    }
    let plan = PreviewPlan::new(SavedPreviewPlan {
        schema: SCHEMA.into(),
        revisions: Revisions::default(),
        source: SourceBinding {
            path: source_path.into(),
            length: bytes.len() as u64,
            sha256: digest(&bytes),
        },
        occurrence: selected,
        intended_bytes: date.encoded(),
        output: OutputSelection {
            path: output_path.into(),
            policy: OutputPolicy::OrdinaryPrivateOwnerOd11A,
            profile: StorageProfile::UnavailableProduction,
            collision: CollisionPolicy::RequireAbsent,
        },
        preservation: Preservation::EntireSourceExceptSelectedAllocation,
        execution_bindings: ExecutionBindings::MustRecompute,
        recovery: Recovery::NoMutationOrRecoveryAuthority,
        apply_authorization: ApplyAuthorization::SeparateCallerRequired,
    })
    .map_err(|e| error("INVALID_PLAN", &e.to_string()))?;
    Ok(BoundPreview { plan, preview })
}

/// Compare imported intent against current bounded bytes and current reader/rule
/// revisions. A match never grants format, storage or caller authorization.
pub fn revalidate<R: Read + Seek>(
    mut input: R,
    plan: &PreviewPlan,
) -> reader::Result<BindingReport> {
    PreviewPlan::new(plan.saved().clone()).map_err(|e| error("INVALID_PLAN", &e.to_string()))?;
    let saved = plan.saved();
    let bytes = snapshot(&mut input)?;
    let source_revision_matches =
        bytes.len() as u64 == saved.source.length && digest(&bytes) == saved.source.sha256;
    let metadata = reader::read(Cursor::new(&bytes), reader::Limits::default())?;
    let target = unique_occurrence(&metadata);
    let current = target
        .map(|target| occurrence(&bytes, target))
        .transpose()?;
    let occurrence_matches = current.as_ref().is_some_and(|current| {
        current.path == saved.occurrence.path
            && current.native_id == saved.occurrence.native_id
            && current.allocation == saved.occurrence.allocation
            && current.byte_order == saved.occurrence.byte_order
    });
    let original_bytes_match = current
        .as_ref()
        .is_some_and(|current| current.original_bytes == saved.occurrence.original_bytes);
    let binding_matches = source_revision_matches && occurrence_matches && original_bytes_match;
    let mut findings = Vec::new();
    if !source_revision_matches {
        findings.push(BindingFinding::SourceRevisionChanged);
    }
    if target.is_none() {
        findings.push(BindingFinding::OccurrenceMissingOrAmbiguous);
    } else if !occurrence_matches {
        findings.push(BindingFinding::OccurrenceChanged);
    }
    if !original_bytes_match {
        findings.push(BindingFinding::OriginalBytesChanged);
    }
    let preview = if binding_matches {
        let proposed = std::str::from_utf8(&saved.intended_bytes[..19])
            .expect("validated plan contains ASCII date bytes");
        let report = preview::date_time_original(
            Cursor::new(&bytes),
            proposed,
            Some(reader::Range {
                offset: saved.occurrence.allocation.offset,
                length: 20,
            }),
        )?;
        if !report.refusals.is_empty() {
            findings.push(BindingFinding::FormatAdmissionRefused);
        }
        Some(report)
    } else {
        None
    };
    findings.push(BindingFinding::StorageProfileUnavailable);
    Ok(BindingReport {
        binding_matches,
        source_revision_matches,
        occurrence_matches,
        original_bytes_match,
        findings,
        preview,
        production_mutation_allowed: false,
    })
}

fn with_file<T>(
    path: &Path,
    inspect: impl FnOnce(&mut File) -> reader::Result<T>,
) -> reader::Result<T> {
    // Refuse known pipes/devices/directories before opening; the held check
    // below still validates the opened object. This is no pathname race guard.
    if !std::fs::metadata(path)?.is_file() {
        return Err(error(
            "CAPABILITY_UNSUPPORTED",
            "Only regular file inputs are supported",
        ));
    }
    let mut file = File::open(path)?;
    let before = file.metadata()?;
    if !before.is_file() {
        return Err(error(
            "CAPABILITY_UNSUPPORTED",
            "Only regular file inputs are supported",
        ));
    }
    let result = inspect(&mut file)?;
    let after = file.metadata()?;
    if before.len() != after.len() || before.modified().ok() != after.modified().ok() {
        return Err(error(
            "SOURCE_CHANGED",
            "File observations changed during preview binding",
        ));
    }
    Ok(result)
}

pub fn capture_file(source: &Path, output: &Path, proposed: &str) -> reader::Result<BoundPreview> {
    let source_path = source
        .to_str()
        .ok_or_else(|| error("INVALID_PLAN", "Source locator must be UTF-8"))?;
    let output_path = output
        .to_str()
        .ok_or_else(|| error("INVALID_PLAN", "Output locator must be UTF-8"))?;
    with_file(source, |file| {
        capture(file, source_path, output_path, proposed)
    })
}

/// Opens only the saved source locator, read-only. The destination is never opened.
pub fn revalidate_file(plan: &PreviewPlan) -> reader::Result<BindingReport> {
    with_file(Path::new(&plan.saved().source.path), |file| {
        revalidate(file, plan)
    })
}
