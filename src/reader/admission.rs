//! Read-only field/structure checks for the proposed CR3 date edit.
//!
//! These observations never authorize writes. Opaque dependency coverage and the
//! storage/integration gates remain separate; see docs/write-safety/write-admission.md.
use super::{Error, Limits, Range, Result, Value, bmff, bounded::Source, tiff};
use std::io::{Read, Seek, SeekFrom};

pub const REVISION: &str = "r5-date-admission-2026-10-12.1";
pub const CATALOG_REVISION: &str = "raw-known-provenance-2026-10-12.1";
const C2PA_BMFF: [u8; 16] = [
    0xd8, 0xfe, 0xc3, 0xd6, 0x1b, 0x0e, 0x48, 0x3c, 0x92, 0x97, 0x58, 0x28, 0x87, 0x7e, 0xc4, 0x81,
];
const C2PA_JUMBF: [u8; 16] = [
    0x63, 0x32, 0x70, 0x61, 0x00, 0x11, 0x00, 0x10, 0x80, 0x00, 0x00, 0xaa, 0x00, 0x38, 0x9b, 0x71,
];

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct DateTime([u8; 20]);
impl DateTime {
    /// Exact zone-less Gregorian date, years 1..9999, seconds 0..59. No trimming,
    /// locale parsing, partial/blank dates, leap seconds or timezone conversion.
    pub fn parse(value: &str) -> Result<Self> {
        let bytes = value.as_bytes();
        let invalid = || Error {
            code: "INVALID_DATE",
            message: "Expected a complete YYYY:MM:DD HH:MM:SS Gregorian date".into(),
        };
        if bytes.len() != 19 {
            return Err(invalid());
        }
        for (i, byte) in bytes.iter().enumerate() {
            let separator = match i {
                4 | 7 | 13 | 16 => Some(b':'),
                10 => Some(b' '),
                _ => None,
            };
            if separator.map_or_else(|| !byte.is_ascii_digit(), |expected| *byte != expected) {
                return Err(invalid());
            }
        }
        let number = |start: usize, length: usize| {
            bytes[start..start + length]
                .iter()
                .fold(0u16, |n, b| n * 10 + u16::from(b - b'0'))
        };
        let year = number(0, 4);
        let month = number(5, 2);
        let day = number(8, 2);
        let leap =
            year.is_multiple_of(4) && (!year.is_multiple_of(100) || year.is_multiple_of(400));
        let days = match month {
            1 | 3 | 5 | 7 | 8 | 10 | 12 => 31,
            4 | 6 | 9 | 11 => 30,
            2 if leap => 29,
            2 => 28,
            _ => 0,
        };
        if year == 0
            || day == 0
            || day > days
            || number(11, 2) > 23
            || number(14, 2) > 59
            || number(17, 2) > 59
        {
            return Err(invalid());
        }
        let mut encoded = [0; 20];
        encoded[..19].copy_from_slice(bytes);
        Ok(Self(encoded))
    }
    pub fn encoded(self) -> [u8; 20] {
        self.0
    }
}

#[derive(Debug)]
pub struct Finding {
    pub code: &'static str,
    pub range: Option<Range>,
}
#[derive(Debug)]
pub struct Assessment {
    pub field: Option<Range>,
    pub field_shape_verified: bool,
    pub expected_occurrence_matches: bool,
    pub value_already_matches: bool,
    pub known_structures: Vec<Finding>,
    pub refusals: Vec<Finding>,
    pub opaque_dependency_regions: usize,
    pub jpeg_markers_examined: usize,
    pub bytes_examined: u64,
}
impl Assessment {
    /// Always false: this read-only assessment is not a storage capability or an
    /// application authorization, even if the isolated field checks pass.
    pub fn production_mutation_allowed(&self) -> bool {
        false
    }
}

fn overlap(a: Range, b: Range) -> bool {
    a.length != 0 && b.length != 0 && a.offset < b.end() && b.offset < a.end()
}
fn finding(code: &'static str, range: Option<Range>) -> Finding {
    Finding { code, range }
}

/// A failed bounded inspection retains only findings actually reached before
/// its error. Incomplete observations never establish known-indicator absence.
#[derive(Debug)]
pub struct IncompleteInspection {
    pub partial: Assessment,
    pub error: Error,
}

/// Caller supplies a stable stream for this invocation. No pathname reopening,
/// mutation, cryptographic verification or imported-profile authorization occurs.
pub fn inspect<R: Read + Seek>(
    input: R,
    date: DateTime,
    expected: Option<Range>,
) -> Result<Assessment> {
    inspect_with_partial(input, date, expected).map_err(|failure| failure.error)
}

/// Same inspector and bounds as `inspect`, with reached observations retained
/// on failure. No imported assessment can be supplied as inspection authority.
pub fn inspect_with_partial<R: Read + Seek>(
    input: R,
    date: DateTime,
    expected: Option<Range>,
) -> std::result::Result<Assessment, Box<IncompleteInspection>> {
    let mut result = Assessment {
        field: None,
        field_shape_verified: false,
        expected_occurrence_matches: false,
        value_already_matches: false,
        known_structures: Vec::new(),
        refusals: Vec::new(),
        opaque_dependency_regions: 0,
        jpeg_markers_examined: 0,
        bytes_examined: 0,
    };
    match inspect_into(input, date, expected, &mut result) {
        Ok(()) => Ok(result),
        Err(error) => Err(Box::new(IncompleteInspection {
            partial: result,
            error,
        })),
    }
}

fn inspect_into<R: Read + Seek>(
    mut input: R,
    date: DateTime,
    expected: Option<Range>,
    result: &mut Assessment,
) -> Result<()> {
    if input.seek(SeekFrom::End(0))? > 256 * 1024 * 1024 {
        return Err(Error::limit("Admission source exceeds 256 MiB"));
    }
    let metadata = super::read(&mut input, Limits::default())?;
    let targets: Vec<_> = metadata
        .occurrences
        .iter()
        .filter(|o| {
            o.namespace == "exif"
                && o.name == "DateTimeOriginal"
                && o.path.iter().any(|p| p.name == "CMT2")
        })
        .collect();
    result.bytes_examined = metadata.bytes_read;
    if targets.len() != 1 {
        result
            .refusals
            .push(finding("FIELD_MISSING_OR_AMBIGUOUS", None));
    } else {
        let target = targets[0];
        result.field = Some(target.range);
        result.field_shape_verified = target.range.length == 20
            && target.encoding == "ASCII"
            && matches!(&target.value, Value::Text(text) if DateTime::parse(text).is_ok());
        result.expected_occurrence_matches = expected.is_none_or(|range| range == target.range);
        if !result.field_shape_verified {
            result
                .refusals
                .push(finding("FIELD_SHAPE_UNVERIFIED", Some(target.range)));
        }
        if !result.expected_occurrence_matches {
            result
                .refusals
                .push(finding("OCCURRENCE_CHANGED", Some(target.range)));
        }
    }
    let firmware: Vec<_> = metadata
        .occurrences
        .iter()
        .filter(|o| o.name == "CanonFirmwareVersion")
        .collect();
    if firmware.len() != 1 || firmware[0].value != Value::Text("Firmware Version 2.2.1".into()) {
        result.refusals.push(finding("FIRMWARE_UNVERIFIED", None));
    }
    let limits = Limits {
        metadata_bytes: 64 * 1024 * 1024,
        block_bytes: 1024 * 1024,
        ..Limits::default()
    };
    let mut source = Source::new(&mut input, limits)?;
    if source.length > 256 * 1024 * 1024 {
        return Err(Error::limit("Admission source exceeds 256 MiB"));
    }
    let boxes = bmff::scan(&mut source)?;
    for b in &boxes {
        if b.uuid == Some(C2PA_BMFF) {
            result
                .known_structures
                .push(finding("C2PA_BMFF_UUID", Some(b.payload)));
        }
        if matches!(&b.kind, b"jumb" | b"jumd") {
            result
                .refusals
                .push(finding("JUMBF_DEPENDENCY_UNINSPECTABLE", Some(b.payload)));
        }
        if b.uuid.is_some_and(|uuid| {
            uuid != bmff::CANON_UUID && uuid != bmff::PREVIEW_UUID && uuid != C2PA_BMFF
        }) {
            result.opaque_dependency_regions += 1;
        }
        if !matches!(&b.kind, b"CMT1" | b"CMT2" | b"CMT3" | b"CMT4") {
            continue;
        }
        // Reader namespace/parent checks remain authoritative. An extra CMT box
        // outside its known wrapper is unproved, never a selected edit location.
        if !b
            .parent
            .is_some_and(|p| boxes[p].uuid == Some(bmff::CANON_UUID))
        {
            result
                .refusals
                .push(finding("METADATA_LOCATION_UNVERIFIED", Some(b.payload)));
            continue;
        }
        let data = source.read(b.payload)?;
        let (order, entries) = tiff::entries(&data, limits)?;
        let target = result
            .field
            .filter(|r| r.offset >= b.payload.offset && r.end() <= b.payload.end());
        if let Some(selected) = target {
            if overlap(
                selected,
                Range {
                    offset: b.payload.offset,
                    length: 8,
                },
            ) {
                result
                    .refusals
                    .push(finding("FIELD_OVERLAPS_STRUCTURE", Some(selected)));
            }
            for entry in &entries {
                let count = u64::from(order.u16(&data, entry.ifd)?);
                let table = Range::checked(
                    b.payload.offset + entry.ifd as u64,
                    6 + count * 12,
                    b.payload.end(),
                )?;
                if overlap(selected, table) {
                    result
                        .refusals
                        .push(finding("FIELD_OVERLAPS_STRUCTURE", Some(selected)));
                    break;
                }
            }
        }
        for entry in &entries {
            let range = Range::checked(
                b.payload.offset + entry.offset as u64,
                entry.length as u64,
                b.payload.end(),
            )?;
            if entry.tag == 0xcd41 && matches!(&b.kind, b"CMT1" | b"CMT2") {
                result
                    .known_structures
                    .push(finding("C2PA_TIFF_TAG", Some(range)));
            }
            if b.kind == *b"CMT3" && entry.tag == 0x83 {
                result
                    .known_structures
                    .push(finding("CANON_ORIGINAL_DECISION_INDICATOR", Some(range)));
            }
            let selected = b.kind == *b"CMT2" && entry.tag == 0x9003 && target == Some(range);
            if let Some(target) = target {
                if !selected && overlap(target, range) {
                    result
                        .refusals
                        .push(finding("FIELD_ALLOCATION_ALIAS", Some(range)));
                }
                if selected {
                    result.value_already_matches =
                        data[entry.offset..entry.offset + entry.length] == date.0;
                }
            }
            // A known storage width does not prove that an undecoded entry has no
            // pointer/checksum dependency on the selected allocation. Partial
            // Canon arrays likewise remain opaque for this admission gate.
            if metadata.opaque.iter().any(|(opaque, path)| {
                *opaque == range
                    && path
                        .iter()
                        .any(|p| p.name == String::from_utf8_lossy(&b.kind))
            }) {
                result.opaque_dependency_regions += 1;
            }
        }
    }
    for preview in &metadata.previews {
        scan_jpeg(&mut source, preview.range, result)?;
    }
    if result.opaque_dependency_regions != 0 {
        result
            .refusals
            .push(finding("OPAQUE_DEPENDENCY_UNPROVEN", None));
    }
    if !result.known_structures.is_empty() {
        result
            .refusals
            .push(finding("KNOWN_AUTHENTICITY_STRUCTURE", None));
    }
    result.bytes_examined += source.bytes_read;
    Ok(())
}

struct JpegBytes<'a, R> {
    source: &'a mut Source<R>,
    range: Range,
    position: u64,
    buffer: Vec<u8>,
    index: usize,
}
impl<R: Read + Seek> JpegBytes<'_, R> {
    fn next(&mut self) -> Result<u8> {
        if self.position >= self.range.length {
            return Err(Error::invalid("Truncated embedded JPEG"));
        }
        if self.index == self.buffer.len() {
            self.buffer = self.source.read(Range::checked(
                self.range.offset + self.position,
                (self.range.length - self.position).min(65536),
                self.range.end(),
            )?)?;
            self.index = 0;
        }
        let value = self.buffer[self.index];
        self.index += 1;
        self.position += 1;
        Ok(value)
    }
    fn segment(&mut self) -> Result<Vec<u8>> {
        let length = usize::from(u16::from_be_bytes([self.next()?, self.next()?]));
        if length < 2 {
            return Err(Error::invalid("Invalid embedded JPEG segment length"));
        }
        (0..length - 2).map(|_| self.next()).collect()
    }
}
fn scan_jpeg<R: Read + Seek>(
    source: &mut Source<R>,
    range: Range,
    result: &mut Assessment,
) -> Result<()> {
    let mut bytes = JpegBytes {
        source,
        range,
        position: 0,
        buffer: Vec::new(),
        index: 0,
    };
    if bytes.next()? != 0xff || bytes.next()? != 0xd8 {
        return Err(Error::invalid("Embedded preview lacks JPEG SOI"));
    }
    let mut entropy = false;
    let mut app11 = Vec::new();
    let mut app11_instance = None;
    let mut sequence = 0u32;
    let mut app11_inspected = false;
    let outcome = (|| {
        loop {
            let byte = bytes.next()?;
            if entropy && byte != 0xff {
                continue;
            }
            if byte != 0xff {
                return Err(Error::invalid("Embedded JPEG marker expected"));
            }
            let mut marker = bytes.next()?;
            while marker == 0xff {
                marker = bytes.next()?;
            }
            if entropy && (marker == 0 || (0xd0..=0xd7).contains(&marker)) {
                continue;
            }
            if marker == 0 {
                return Err(Error::invalid("JPEG stuffing outside entropy"));
            }
            result.jpeg_markers_examined += 1;
            if result.jpeg_markers_examined > 4096 {
                return Err(Error::limit("JPEG marker limit exceeded"));
            }
            if marker == 0xd9 {
                // Preserve the reader's extraction extent, including its at-most-16
                // zero padding bytes. Any other suffix could hide another structure.
                if range.length - bytes.position > 16 {
                    return Err(Error::unsupported("JPEG trailer scope unverified"));
                }
                while bytes.position < range.length {
                    if bytes.next()? != 0 {
                        return Err(Error::unsupported("JPEG trailer scope unverified"));
                    }
                }
                if !app11.is_empty() {
                    app11_inspected = true;
                    inspect_jumbf(&app11, range, result)?;
                }
                return Ok(());
            }
            if marker == 0xd8 || (0xd0..=0xd7).contains(&marker) {
                return Err(Error::invalid("Unexpected standalone JPEG marker"));
            }
            if marker == 1 {
                continue;
            }
            entropy = false;
            let segment = bytes.segment()?;
            if marker == 0xeb {
                if segment.len() < 8 || &segment[..2] != b"JP" {
                    result
                        .refusals
                        .push(finding("APP11_SCOPE_UNINSPECTABLE", Some(range)));
                    continue;
                }
                let instance = u16::from_be_bytes([segment[2], segment[3]]);
                let part = u32::from_be_bytes(
                    segment[4..8]
                        .try_into()
                        .map_err(|_| Error::invalid("APP11 sequence missing"))?,
                );
                let continuation = app11_instance == Some(instance)
                    && Some(part) == sequence.checked_add(1)
                    && !app11.is_empty();
                if app11_instance != Some(instance) || Some(part) != sequence.checked_add(1) {
                    if !app11.is_empty() {
                        app11_inspected = true;
                        inspect_jumbf(&app11, range, result)?;
                        app11.clear();
                        app11_inspected = false;
                    }
                    if part != 1 {
                        result
                            .refusals
                            .push(finding("APP11_SEQUENCE_UNVERIFIED", Some(range)));
                    }
                }
                app11_instance = Some(instance);
                sequence = part;
                // JPEG XT repeats LBox/TBox in each continuation segment. Verify the
                // same header before excluding it from this bounded assembly.
                let body_at = if continuation {
                    if segment.len() < 16 || app11.len() < 8 || segment[8..16] != app11[..8] {
                        result
                            .refusals
                            .push(finding("APP11_SEQUENCE_UNVERIFIED", Some(range)));
                        // Retain any complete earlier structure before discarding
                        // the unsupported continuation. The existing refusal and
                        // successful assessment remain unchanged on parse failure.
                        let _ = inspect_jumbf(&app11, range, result);
                        app11.clear();
                        app11_inspected = false;
                        app11_instance = None;
                        sequence = 0;
                        continue;
                    }
                    16
                } else {
                    8
                };
                if app11.len() + segment.len() - body_at > 1024 * 1024 {
                    return Err(Error::limit("APP11 assembly limit exceeded"));
                }
                app11.extend_from_slice(&segment[body_at..]);
                app11_inspected = false;
            } else {
                if !app11.is_empty() {
                    app11_inspected = true;
                    inspect_jumbf(&app11, range, result)?;
                    app11.clear();
                    app11_inspected = false;
                    app11_instance = None;
                    sequence = 0;
                }
                if marker == 0xe1 && segment.starts_with(b"Exif\0\0") {
                    let (_, entries) = tiff::entries(&segment[6..], Limits::default())?;
                    for entry in entries {
                        if entry.tag == 0xcd41 {
                            result
                                .known_structures
                                .push(finding("C2PA_PREVIEW_TIFF_TAG", Some(range)));
                        }
                        if entry.tag == 0x927c {
                            result
                                .refusals
                                .push(finding("PREVIEW_MAKERNOTE_UNINSPECTABLE", Some(range)));
                        }
                    }
                }
                if marker == 0xda {
                    entropy = true;
                }
            }
        }
    })();
    // A later JPEG error must not erase an already complete pending APP11
    // structure. The same bounded parser retains only reached box findings;
    // failure to interpret an incomplete assembly cannot establish absence.
    if outcome.is_err() && !app11.is_empty() && !app11_inspected {
        let _ = inspect_jumbf(&app11, range, result);
    }
    outcome
}
fn inspect_jumbf(data: &[u8], range: Range, result: &mut Assessment) -> Result<()> {
    // Detect the fixed description UUID only at an actual jumb/jumd boundary;
    // arbitrary magic bytes in compressed samples are not provenance evidence.
    let mut position = 0;
    while position < data.len() {
        if data.len() - position < 8 {
            return Err(Error::invalid("Truncated JUMBF box"));
        }
        let size = u32::from_be_bytes(
            data[position..position + 4]
                .try_into()
                .map_err(|_| Error::invalid("JUMBF size missing"))?,
        ) as usize;
        if size < 8 || size > data.len() - position {
            return Err(Error::invalid("JUMBF box outside APP11 assembly"));
        }
        if &data[position + 4..position + 8] == b"jumb" {
            let body = &data[position + 8..position + size];
            if body.len() >= 25 && &body[4..8] == b"jumd" {
                let description = u32::from_be_bytes(
                    body[..4]
                        .try_into()
                        .map_err(|_| Error::invalid("JUMBF description size missing"))?,
                ) as usize;
                if description >= 25 && description <= body.len() && body[8..24] == C2PA_JUMBF {
                    result
                        .known_structures
                        .push(finding("C2PA_JPEG_JUMBF", Some(range)));
                } else {
                    result
                        .refusals
                        .push(finding("JUMBF_SCOPE_UNINSPECTABLE", Some(range)));
                }
            } else {
                result
                    .refusals
                    .push(finding("JUMBF_SCOPE_UNINSPECTABLE", Some(range)));
            }
        } else {
            result
                .refusals
                .push(finding("APP11_BOX_UNVERIFIED", Some(range)));
        }
        position += size;
    }
    Ok(())
}
