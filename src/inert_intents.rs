//! Decode caller-supplied scalar-v1 documents against an immutable local observation table.
//!
//! The decoder uses only the supplied bytes and observations. The returned data carries
//! local occurrence identity and has no freshness, filesystem, or execution authority.

mod csv;
mod json;

use std::{
    collections::{HashMap, HashSet},
    fmt,
    num::NonZeroU32,
    str::{self, FromStr},
};

const MAX_INPUT_BYTES: usize = 1_048_576;
const MAX_EDITS: usize = 64;
const MAX_BINDINGS: usize = 16;
const MAX_TEXT_BYTES: usize = 4_096;
const MAX_IDENTITY_CHARS: usize = 256;
const MAX_SOURCE_KEY_BYTES: usize = 64;

/// The caller selects the transport explicitly.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Format {
    JsonV1,
    CsvV1,
}

/// One entry in the caller's local observation table.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SourceObservation {
    pub source_key: String,
    pub snapshot_id: String,
    pub occurrences: Vec<OccurrenceObservation>,
}

/// The complete local identity of an occurrence within a snapshot.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct OccurrenceObservation {
    pub occurrence_id: String,
    pub namespace: String,
    pub native_id: String,
    pub document_ref: String,
    pub path: Vec<PathPart>,
    pub ordinal: usize,
}

/// A segment of an indexed metadata path. The observation supplies its name if present.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct PathPart {
    pub kind: String,
    pub name: Option<String>,
    pub index: usize,
}

/// The exact proposed replacement scalar.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Scalar {
    Integer(u64),
    Rational {
        numerator: u32,
        denominator: NonZeroU32,
    },
    Text(String),
}

/// An owned, nonexecuting set intent bound to the caller's local observation.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Intent {
    pub source_key: String,
    pub snapshot_id: String,
    pub occurrence: OccurrenceObservation,
    pub value: Scalar,
}

/// Where the decoder encountered an error.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ErrorLocation {
    /// Input encoding, framing, envelope, header, or a whole-batch bound.
    Input,
    /// One-based logical edit index, excluding the CSV header and quoted newlines.
    Row(usize),
    /// One-based index in the caller's observation table.
    Binding(usize),
}

/// Fixed reasons for decoding or matching refusal.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ErrorKind {
    InputBytes,
    Utf8,
    Bom,
    JsonSyntax,
    /// Wrong JSON type, missing field, unknown field, duplicate field, or unknown value kind.
    JsonShape,
    JsonProfile,
    CsvHeader,
    CsvWidth,
    CsvRecordEnding,
    CsvQuote,
    CsvAfterQuote,
    CsvUnusedCell,
    EditCount,
    BindingCount,
    Operation,
    ValueKind,
    SourceKey,
    IdentityLength,
    DecimalSpelling,
    DecimalRange,
    ZeroDenominator,
    TextBytes,
    DuplicateSourceKey,
    DuplicateSnapshotId,
    DuplicateOccurrenceId,
    DuplicateTarget,
    UnknownSource,
    SnapshotMismatch,
    UnknownOccurrence,
    IdentityMismatch,
}

/// A refusal exposes only its location and reason, without partially decoded intents.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct DecodeError {
    pub location: ErrorLocation,
    pub kind: ErrorKind,
}

impl fmt::Display for DecodeError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self.location {
            ErrorLocation::Input => write!(f, "Inert scalar input refused ({:?})", self.kind),
            ErrorLocation::Row(row) => {
                write!(f, "Inert scalar row {row} refused ({:?})", self.kind)
            }
            ErrorLocation::Binding(binding) => {
                write!(
                    f,
                    "Inert scalar binding {binding} refused ({:?})",
                    self.kind
                )
            }
        }
    }
}

impl std::error::Error for DecodeError {}

/// Decode the complete batch in input order or return one attributable refusal.
///
/// Input is limited to 1 MiB, 1–64 edits, 1–16 observation bindings and 4,096
/// UTF-8 bytes per text value. The decoder checks the uniqueness of the table's
/// matching keys. Document references, path segments and ordinals are copied as
/// supplied by the caller. Returned intents can outlive both arguments.
pub fn decode(
    input: &[u8],
    format: Format,
    bindings: &[SourceObservation],
) -> Result<Vec<Intent>, DecodeError> {
    let input_error = |kind| DecodeError {
        location: ErrorLocation::Input,
        kind,
    };
    if input.len() > MAX_INPUT_BYTES {
        return Err(input_error(ErrorKind::InputBytes));
    }
    let text = str::from_utf8(input).map_err(|_| input_error(ErrorKind::Utf8))?;
    if text.starts_with('\u{feff}') {
        return Err(input_error(ErrorKind::Bom));
    }
    let edits = match format {
        Format::JsonV1 => json::decode(text)?,
        Format::CsvV1 => csv::decode(text)?,
    };
    if edits.is_empty() {
        return Err(input_error(ErrorKind::EditCount));
    }
    if !(1..=MAX_BINDINGS).contains(&bindings.len()) {
        return Err(input_error(ErrorKind::BindingCount));
    }
    let sources = index_observations(bindings)?;
    let mut seen = HashSet::new();
    edits
        .into_iter()
        .enumerate()
        .map(|(index, edit)| {
            let error = |kind| DecodeError {
                location: ErrorLocation::Row(index + 1),
                kind,
            };
            let identity = edit.identity;
            identity.validate().map_err(error)?;
            let (source, occurrences) = sources
                .get(identity.source_key.as_str())
                .ok_or_else(|| error(ErrorKind::UnknownSource))?;
            if source.snapshot_id != identity.snapshot_id {
                return Err(error(ErrorKind::SnapshotMismatch));
            }
            let occurrence = occurrences
                .get(identity.occurrence_id.as_str())
                .ok_or_else(|| error(ErrorKind::UnknownOccurrence))?;
            if occurrence.namespace != identity.namespace
                || occurrence.native_id != identity.native_id
            {
                return Err(error(ErrorKind::IdentityMismatch));
            }
            // A source key already identifies its single snapshot.
            if !seen.insert((
                source.source_key.as_str(),
                occurrence.occurrence_id.as_str(),
            )) {
                return Err(error(ErrorKind::DuplicateTarget));
            }
            Ok(Intent {
                source_key: source.source_key.clone(),
                snapshot_id: source.snapshot_id.clone(),
                occurrence: (*occurrence).clone(),
                value: edit.value.into_scalar().map_err(error)?,
            })
        })
        .collect()
}

type OccurrenceIndex<'a> = HashMap<&'a str, &'a OccurrenceObservation>;
type SourceIndex<'a> = HashMap<&'a str, (&'a SourceObservation, OccurrenceIndex<'a>)>;

fn index_observations(bindings: &[SourceObservation]) -> Result<SourceIndex<'_>, DecodeError> {
    let mut sources = HashMap::new();
    let mut snapshots = HashSet::new();
    for (index, source) in bindings.iter().enumerate() {
        let error = |kind| DecodeError {
            location: ErrorLocation::Binding(index + 1),
            kind,
        };
        if sources.contains_key(source.source_key.as_str()) {
            return Err(error(ErrorKind::DuplicateSourceKey));
        }
        if !snapshots.insert(source.snapshot_id.as_str()) {
            return Err(error(ErrorKind::DuplicateSnapshotId));
        }
        let mut occurrences = HashMap::new();
        for occurrence in &source.occurrences {
            if occurrences
                .insert(occurrence.occurrence_id.as_str(), occurrence)
                .is_some()
            {
                return Err(error(ErrorKind::DuplicateOccurrenceId));
            }
        }
        sources.insert(source.source_key.as_str(), (source, occurrences));
    }
    Ok(sources)
}

struct Edit {
    identity: Identity,
    value: WireValue,
}

struct Identity {
    source_key: String,
    snapshot_id: String,
    occurrence_id: String,
    namespace: String,
    native_id: String,
}

impl Identity {
    fn validate(&self) -> Result<(), ErrorKind> {
        if !(1..=MAX_SOURCE_KEY_BYTES).contains(&self.source_key.len())
            || !self
                .source_key
                .bytes()
                .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'_' | b'-'))
        {
            return Err(ErrorKind::SourceKey);
        }
        for value in [
            &self.snapshot_id,
            &self.occurrence_id,
            &self.namespace,
            &self.native_id,
        ] {
            if value.is_empty()
                || value.chars().take(MAX_IDENTITY_CHARS + 1).count() > MAX_IDENTITY_CHARS
            {
                return Err(ErrorKind::IdentityLength);
            }
        }
        Ok(())
    }
}

#[derive(serde::Deserialize)]
#[serde(tag = "kind", rename_all = "lowercase", deny_unknown_fields)]
enum WireValue {
    Integer {
        decimal: String,
    },
    Rational {
        numerator: String,
        denominator: String,
    },
    String {
        text: String,
    },
}

impl WireValue {
    fn into_scalar(self) -> Result<Scalar, ErrorKind> {
        match self {
            Self::Integer { decimal } => decimal_uint(&decimal).map(Scalar::Integer),
            Self::Rational {
                numerator,
                denominator,
            } => Ok(Scalar::Rational {
                numerator: decimal_uint(&numerator)?,
                denominator: NonZeroU32::new(decimal_uint(&denominator)?)
                    .ok_or(ErrorKind::ZeroDenominator)?,
            }),
            Self::String { text } if text.len() <= MAX_TEXT_BYTES => Ok(Scalar::Text(text)),
            Self::String { .. } => Err(ErrorKind::TextBytes),
        }
    }
}

fn decimal_uint<T: FromStr>(text: &str) -> Result<T, ErrorKind> {
    if text.is_empty()
        || text.len() > 20
        || (text.len() > 1 && text.starts_with('0'))
        || !text.bytes().all(|byte| byte.is_ascii_digit())
    {
        return Err(ErrorKind::DecimalSpelling);
    }
    text.parse().map_err(|_| ErrorKind::DecimalRange)
}
