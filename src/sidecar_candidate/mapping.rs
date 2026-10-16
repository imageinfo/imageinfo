//! Reviewed promotion of #0083 mapping; invocation-local facts only.
use crate::xmp::{Packet, Value};

pub const MAPPING: &str = "r5-cmt2-original-to-xmp-exif-original/1";
pub const TARGET_NAMESPACE: &str = "http://ns.adobe.com/exif/1.0/";
pub const TARGET_LOCAL: &str = "DateTimeOriginal";

#[derive(Debug, Clone, Copy)]
pub struct Occurrence<'a> {
    pub id: &'a str,
    /// Exact decoded stored EXIF text, excluding its terminator; never display text.
    pub text: &'a str,
}

#[derive(Debug)]
pub struct OriginalSnapshot<'a> {
    pub id: &'a str,
    /// Names one explicitly selected original CMT2 TIFF document; not a path authority.
    pub raw_document: &'a str,
    /// Explicitly selected sidecar document from the same immutable observation.
    pub sidecar_document: &'a str,
    /// Coverage attestation for all three exact tags in this selected CMT2 block.
    /// Caller data is not authenticated; this model cannot establish this fact.
    pub complete_selected_tag_coverage: bool,
    /// CMT2 EXIF 0x9003 only; other date aliases are never selected.
    pub original: &'a [Occurrence<'a>],
    /// Same CMT2 EXIF 0x9291; zero means observed absence, not unexamined.
    pub subseconds: &'a [Occurrence<'a>],
    /// Same CMT2 EXIF 0x9011; zero means observed absence, not unexamined.
    pub offset: &'a [Occurrence<'a>],
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Loss {
    DestinationFractionDiscarded,
    DestinationZoneDiscarded,
}

#[derive(Debug, Clone, Copy, Default)]
pub enum ConflictPolicy<'a> {
    #[default]
    Refuse,
    KeepDestination,
    /// Names the exact loss set the caller permits; no catch-all allow-loss flag.
    ReplaceSelected {
        acknowledged: &'a [Loss],
    },
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Decision {
    NoOp,
    ConflictRefused,
    KeepDestination,
    LossRefused,
    ReplaceIntentOnly,
}

#[derive(Debug, PartialEq, Eq)]
pub struct Comparison<'a> {
    pub mapping: &'static str,
    pub snapshot: &'a str,
    pub raw_document: &'a str,
    pub sidecar_document: &'a str,
    pub source_occurrences: Vec<&'a str>,
    pub target_ordinal: usize,
    pub previous: String,
    pub mapped: String,
    pub destination_losses: Vec<Loss>,
    pub decision: Decision,
    pub production_mutation_allowed: bool,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Refusal {
    IncompleteCoverage,
    InvalidIdentity,
    SourceCardinality,
    SourceDate,
    SourceFraction,
    SourceOffset,
    TargetCardinality,
    TargetSelection,
    TargetType,
    TargetDate,
}

#[derive(Debug)]
struct Date<'a> {
    fraction: Option<&'a str>,
    zone: Option<&'a str>,
}

fn calendar(value: &[u8], separator: u8, time_separator: u8) -> bool {
    if value.len() != 19
        || value[4] != separator
        || value[7] != separator
        || value[10] != time_separator
        || value[13] != b':'
        || value[16] != b':'
    {
        return false;
    }
    if value
        .iter()
        .enumerate()
        .any(|(i, b)| ![4, 7, 10, 13, 16].contains(&i) && !b.is_ascii_digit())
    {
        return false;
    }
    let number = |start: usize, end: usize| {
        value[start..end]
            .iter()
            .fold(0_u32, |n, b| n * 10 + u32::from(b - b'0'))
    };
    let year = number(0, 4);
    let month = number(5, 7);
    let day = number(8, 10);
    let leap = year.is_multiple_of(4) && (!year.is_multiple_of(100) || year.is_multiple_of(400));
    let days = match month {
        2 if leap => 29,
        2 => 28,
        4 | 6 | 9 | 11 => 30,
        1 | 3 | 5 | 7 | 8 | 10 | 12 => 31,
        _ => 0,
    };
    year != 0
        && day != 0
        && day <= days
        && number(11, 13) < 24
        && number(14, 16) < 60
        && number(17, 19) < 60
}

fn fraction(value: &str) -> bool {
    (1..=9).contains(&value.len()) && value.bytes().all(|b| b.is_ascii_digit())
}

fn offset(value: &str) -> bool {
    let b = value.as_bytes();
    if b.len() != 6
        || !matches!(b[0], b'+' | b'-')
        || b[3] != b':'
        || [1, 2, 4, 5].iter().any(|&i| !b[i].is_ascii_digit())
        || value == "-00:00"
    {
        return false;
    }
    let hour = (b[1] - b'0') * 10 + b[2] - b'0';
    let minute = (b[4] - b'0') * 10 + b[5] - b'0';
    hour <= 14 && minute < 60 && (hour < 14 || minute == 0)
}

fn parse_target(value: &str) -> Option<Date<'_>> {
    let b = value.as_bytes();
    if b.len() < 19 || !calendar(&b[..19], b'-', b'T') {
        return None;
    }
    let mut end = 19;
    let frac = if b.get(end) == Some(&b'.') {
        let start = end + 1;
        end = start;
        while b.get(end).is_some_and(u8::is_ascii_digit) {
            end += 1;
        }
        let f = &value[start..end];
        if !fraction(f) {
            return None;
        }
        Some(f)
    } else {
        None
    };
    let zone = &value[end..];
    if !zone.is_empty() && zone != "Z" && !offset(zone) {
        return None;
    }
    Some(Date {
        fraction: frac,
        zone: (!zone.is_empty()).then_some(zone),
    })
}

/// Compare original values only. The model never consumes its previous output as
/// an edit overlay, and cannot authenticate imported snapshots or admit a write.
pub fn compare<'a>(
    original: &'a OriginalSnapshot<'a>,
    sidecar: &Packet<'_>,
    selected_target_ordinal: usize,
    policy: ConflictPolicy<'_>,
) -> Result<Comparison<'a>, Refusal> {
    if !original.complete_selected_tag_coverage {
        return Err(Refusal::IncompleteCoverage);
    }
    if original.id.is_empty()
        || original.raw_document.is_empty()
        || original.sidecar_document.is_empty()
        || original.raw_document == original.sidecar_document
    {
        return Err(Refusal::InvalidIdentity);
    }
    if original.original.len() != 1 || original.subseconds.len() > 1 || original.offset.len() > 1 {
        return Err(Refusal::SourceCardinality);
    }
    let mut ids = Vec::new();
    for item in original
        .original
        .iter()
        .chain(original.subseconds)
        .chain(original.offset)
    {
        if item.id.is_empty() || ids.contains(&item.id) {
            return Err(Refusal::InvalidIdentity);
        }
        ids.push(item.id);
    }
    let source = original.original[0].text;
    if !calendar(source.as_bytes(), b':', b' ') {
        return Err(Refusal::SourceDate);
    }
    let mut mapped = format!(
        "{}-{}-{}T{}",
        &source[..4],
        &source[5..7],
        &source[8..10],
        &source[11..]
    );
    if let Some(subsecond) = original.subseconds.first() {
        if !fraction(subsecond.text) {
            return Err(Refusal::SourceFraction);
        }
        mapped.push('.');
        mapped.push_str(subsecond.text);
    }
    if let Some(zone) = original.offset.first() {
        if !offset(zone.text) {
            return Err(Refusal::SourceOffset);
        }
        mapped.push_str(zone.text);
    }
    let mut targets = sidecar
        .properties()
        .iter()
        .filter(|p| p.name.namespace == TARGET_NAMESPACE && p.name.local == TARGET_LOCAL);
    let target = targets.next().ok_or(Refusal::TargetCardinality)?;
    if targets.next().is_some() {
        return Err(Refusal::TargetCardinality);
    }
    if target.ordinal != selected_target_ordinal {
        return Err(Refusal::TargetSelection);
    }
    let Value::Text(previous) = &target.value else {
        return Err(Refusal::TargetType);
    };
    let before = parse_target(previous).ok_or(Refusal::TargetDate)?;
    let after = parse_target(&mapped).ok_or(Refusal::SourceDate)?;
    let mut losses = Vec::new();
    if before.fraction.is_some() && before.fraction != after.fraction {
        losses.push(Loss::DestinationFractionDiscarded);
    }
    if before.zone.is_some() && before.zone != after.zone {
        losses.push(Loss::DestinationZoneDiscarded);
    }
    let decision = if previous == &mapped {
        Decision::NoOp
    } else {
        match policy {
            ConflictPolicy::Refuse => Decision::ConflictRefused,
            ConflictPolicy::KeepDestination => Decision::KeepDestination,
            ConflictPolicy::ReplaceSelected { acknowledged } => {
                let exact = acknowledged.len() == losses.len()
                    && losses.iter().all(|loss| acknowledged.contains(loss));
                if exact {
                    Decision::ReplaceIntentOnly
                } else {
                    Decision::LossRefused
                }
            }
        }
    };
    Ok(Comparison {
        mapping: MAPPING,
        snapshot: original.id,
        raw_document: original.raw_document,
        sidecar_document: original.sidecar_document,
        source_occurrences: ids,
        target_ordinal: target.ordinal,
        previous: previous.clone(),
        mapped,
        destination_losses: losses,
        decision,
        production_mutation_allowed: false,
    })
}
