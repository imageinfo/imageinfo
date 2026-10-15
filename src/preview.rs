//! Bounded read-only description of one existing CR3 date intent.
//!
//! This is an advisory byte proposal, never an executable or source-bound plan.
use crate::reader::{self, Range, admission};
use std::io::{Read, Seek, SeekFrom};

#[derive(Clone, Copy, Debug, PartialEq, Eq, serde::Serialize)]
pub struct ByteRange {
    pub offset: u64,
    pub length: u64,
}
impl From<Range> for ByteRange {
    fn from(value: Range) -> Self {
        Self {
            offset: value.offset,
            length: value.length,
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, serde::Serialize)]
#[serde(rename_all = "snake_case")]
pub enum PreviewStatus {
    Previewed,
    Refused,
}

#[derive(Debug, serde::Serialize)]
pub struct PreviewFinding {
    pub code: &'static str,
    pub range: Option<ByteRange>,
}
impl From<admission::Finding> for PreviewFinding {
    fn from(value: admission::Finding) -> Self {
        Self {
            code: value.code,
            range: value.range.map(Into::into),
        }
    }
}

#[derive(Debug, serde::Serialize)]
pub struct DatePreview {
    pub status: PreviewStatus,
    pub field: &'static str,
    pub source_length: u64,
    pub allocation: Option<ByteRange>,
    pub original_bytes: Option<[u8; 20]>,
    pub proposed_bytes: [u8; 20],
    /// Exact differing spans in the proposed allocation. No candidate is written.
    pub changed_ranges: Vec<ByteRange>,
    /// Complement of changed_ranges across the source, in the hypothetical proposal.
    /// This does not attest opaque semantic/checksum independence or a later source.
    pub preserved_ranges: Vec<ByteRange>,
    pub changed_bytes: u64,
    pub preserved_bytes: Option<u64>,
    pub value_already_matches: bool,
    pub field_shape_verified: bool,
    pub expected_occurrence_matches: bool,
    pub known_structures: Vec<PreviewFinding>,
    pub refusals: Vec<PreviewFinding>,
    pub bytes_examined: u64,
    pub production_mutation_allowed: bool,
}

/// Inspect one caller-provided stable stream with the actual admission checks.
/// The only supported intent is a complete zone-less Gregorian DateTimeOriginal.
/// A supplied expected allocation must match exactly; omission still requires a
/// unique existing CMT2 occurrence. No path is opened and no output is created.
pub fn date_time_original<R: Read + Seek>(
    mut input: R,
    proposed: &str,
    expected: Option<Range>,
) -> reader::Result<DatePreview> {
    let date = admission::DateTime::parse(proposed)?;
    let assessment = admission::inspect(&mut input, date, expected)?;
    let source_length = input.seek(SeekFrom::End(0))?;
    let mut result = DatePreview {
        status: if assessment.refusals.is_empty() {
            PreviewStatus::Previewed
        } else {
            PreviewStatus::Refused
        },
        field: "exif:DateTimeOriginal",
        source_length,
        allocation: assessment.field.map(Into::into),
        original_bytes: None,
        proposed_bytes: date.encoded(),
        changed_ranges: Vec::new(),
        preserved_ranges: Vec::new(),
        changed_bytes: 0,
        preserved_bytes: None,
        value_already_matches: assessment.value_already_matches,
        field_shape_verified: assessment.field_shape_verified,
        expected_occurrence_matches: assessment.expected_occurrence_matches,
        known_structures: assessment
            .known_structures
            .into_iter()
            .map(Into::into)
            .collect(),
        refusals: assessment.refusals.into_iter().map(Into::into).collect(),
        bytes_examined: assessment.bytes_examined,
        production_mutation_allowed: false,
    };
    if !result.field_shape_verified || !result.expected_occurrence_matches {
        return Ok(result);
    }
    if let Some(field) = assessment.field {
        Range::checked(field.offset, 20, source_length)?;
        let mut original = [0; 20];
        input.seek(SeekFrom::Start(field.offset))?;
        input.read_exact(&mut original)?;
        result.bytes_examined += 20;
        // Revalidate the exact stored encoding instead of inferring its bytes
        // from a decoded string. This is still no continuous source guard.
        let valid = std::str::from_utf8(&original[..19])
            .ok()
            .and_then(|s| admission::DateTime::parse(s).ok())
            .is_some_and(|date| date.encoded() == original);
        if !valid {
            result.status = PreviewStatus::Refused;
            result.field_shape_verified = false;
            result.refusals.push(PreviewFinding {
                code: "FIELD_SHAPE_UNVERIFIED",
                range: Some(field.into()),
            });
            return Ok(result);
        }
        result.original_bytes = Some(original);
        result.value_already_matches = original == result.proposed_bytes;
        let mut index = 0;
        while index < 20 {
            if original[index] == result.proposed_bytes[index] {
                index += 1;
                continue;
            }
            let start = index;
            while index < 20 && original[index] != result.proposed_bytes[index] {
                index += 1;
            }
            result.changed_ranges.push(ByteRange {
                offset: field.offset + start as u64,
                length: (index - start) as u64,
            });
        }
        let mut position = 0;
        for range in &result.changed_ranges {
            if position < range.offset {
                result.preserved_ranges.push(ByteRange {
                    offset: position,
                    length: range.offset - position,
                });
            }
            position = range.offset + range.length;
            result.changed_bytes += range.length;
        }
        if position < source_length {
            result.preserved_ranges.push(ByteRange {
                offset: position,
                length: source_length - position,
            });
        }
        result.preserved_bytes = Some(source_length - result.changed_bytes);
    }
    Ok(result)
}
