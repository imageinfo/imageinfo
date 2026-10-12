//! Bounded, read-only Canon EOS R5 full RAW metadata slice.
pub mod admission;
mod bmff;
mod bounded;
mod extract;
mod tiff;
mod tracks;
mod wire;

pub use bounded::Range;
pub use extract::extract;
use std::{
    fmt,
    fs::File,
    io::{Read, Seek},
    path::Path,
};
pub use wire::{NAMES, select, selector, text_value};

pub const READER_REVISION: &str = "r5-read-slice-2026-10-11.1";
pub type Result<T> = std::result::Result<T, Error>;

#[derive(Clone, Debug)]
pub struct Error {
    pub code: &'static str,
    pub message: String,
}
impl Error {
    fn invalid(message: &str) -> Self {
        Self {
            code: "INVALID_STRUCTURE",
            message: message.into(),
        }
    }
    fn limit(message: &str) -> Self {
        Self {
            code: "LIMIT_EXCEEDED",
            message: message.into(),
        }
    }
    fn unsupported(message: &str) -> Self {
        Self {
            code: "CAPABILITY_UNSUPPORTED",
            message: message.into(),
        }
    }
}
impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}: {}", self.code, self.message)
    }
}
impl std::error::Error for Error {}
impl From<std::io::Error> for Error {
    fn from(error: std::io::Error) -> Self {
        Self {
            code: "INPUT_IO",
            message: format!("Input I/O failed ({:?})", error.kind()),
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Limits {
    pub metadata_bytes: u64,
    pub block_bytes: u64,
    pub boxes: usize,
    pub depth: usize,
    pub entries: usize,
    pub records: usize,
    pub preview_bytes: u64,
}
impl Default for Limits {
    fn default() -> Self {
        Self {
            metadata_bytes: 8 * 1024 * 1024,
            block_bytes: 1024 * 1024,
            boxes: 4096,
            depth: 16,
            entries: 4096,
            records: 4096,
            preview_bytes: 64 * 1024 * 1024,
        }
    }
}

#[derive(Clone, Debug, serde::Serialize)]
pub struct Part {
    pub kind: &'static str,
    pub name: String,
    pub index: usize,
}
impl Part {
    fn new(kind: &'static str, name: impl Into<String>, index: usize) -> Self {
        Self {
            kind,
            name: name.into(),
            index,
        }
    }
}

#[derive(Clone, Debug, PartialEq)]
pub enum Value {
    Integer(u64),
    Rational(u32, u32),
    Text(String),
    Binary(Range),
}
impl Value {
    pub fn display(&self, name: &str) -> String {
        match self {
            Self::Integer(n) => match (name, *n) {
                ("Quality", 4) => "RAW".into(),
                ("DualPixelRaw", 0) => "Off".into(),
                ("DualPixelRaw", 1) => "On".into(),
                ("CanonModelID", 0x80000421) => "EOS R5".into(),
                _ => n.to_string(),
            },
            Self::Text(s) => s.clone(),
            Self::Binary(range) => format!("[{} stored bytes]", range.length),
            Self::Rational(n, d) if *d == 0 => format!("{n}/0 (invalid)"),
            Self::Rational(n, d) => {
                let v = f64::from(*n) / f64::from(*d);
                match name {
                    "ExposureTime" if *n == 1 && *d > 1 => format!("1/{d}"),
                    "FocalLength" => format!("{v:.1} mm"),
                    "FNumber" => format!("{v:.1}"),
                    _ => v.to_string(),
                }
            }
        }
    }
}

#[derive(Clone, Debug)]
pub struct Occurrence {
    pub name: &'static str,
    pub namespace: &'static str,
    pub native_id: String,
    pub value: Value,
    pub range: Range,
    pub path: Vec<Part>,
    pub order: &'static str,
    pub encoding: &'static str,
}

#[derive(Clone, Debug)]
pub struct Preview {
    pub name: &'static str,
    pub range: Range,
    pub path: Vec<Part>,
}

#[derive(Debug)]
pub struct Metadata {
    pub length: u64,
    pub bytes_read: u64,
    pub occurrences: Vec<Occurrence>,
    pub previews: Vec<Preview>,
    pub opaque: Vec<(Range, Vec<Part>)>,
}

pub fn read_file(path: &Path, limits: Limits) -> Result<Metadata> {
    if !std::fs::metadata(path)?.is_file() {
        return Err(Error::unsupported("Only regular file inputs are supported"));
    }
    let mut file = File::open(path)?;
    let before = file.metadata()?;
    let result = read(&mut file, limits)?;
    let after = file.metadata()?;
    if before.len() != after.len() || before.modified().ok() != after.modified().ok() {
        return Err(Error {
            code: "SOURCE_CHANGED",
            message: "Source changed while reading".into(),
        });
    }
    Ok(result)
}

/// Reads bounded metadata, never sensor pixels. Caller-provided streams must be
/// stable for this invocation; snapshots do not grant authority to reopen paths.
pub fn read<R: Read + Seek>(input: R, limits: Limits) -> Result<Metadata> {
    if limits.depth > 64
        || limits.boxes > 65536
        || limits.entries > 65536
        || limits.records > 65536
        || limits.metadata_bytes > 256 * 1024 * 1024
        || limits.block_bytes > 8 * 1024 * 1024
        || limits.preview_bytes > 1024 * 1024 * 1024
    {
        return Err(Error::limit("Reader limit exceeds its supported ceiling"));
    }
    let mut source = bounded::Source::new(input, limits)?;
    let boxes = bmff::scan(&mut source)?;
    let top: Vec<_> = boxes
        .iter()
        .filter(|b| b.parent.is_none() && b.kind == *b"ftyp")
        .collect();
    if top.len() != 1 {
        return Err(Error::unsupported("No unambiguous RAW file type box"));
    }
    if top[0].payload.length < 8
        || (top[0].payload.length - 8) % 4 != 0
        || source.bytes::<4>(top[0].payload.offset)? != *b"crx "
    {
        return Err(Error::unsupported(
            "Input is not the supported CR3 container",
        ));
    }
    let roots: Vec<_> = boxes
        .iter()
        .enumerate()
        .filter(|(_, b)| {
            b.uuid == Some(bmff::CANON_UUID) && b.parent.is_some_and(|p| boxes[p].kind == *b"moov")
        })
        .map(|(i, _)| i)
        .collect();
    if roots.len() != 1 {
        return Err(Error::unsupported(
            "Canon metadata container missing or ambiguous",
        ));
    }
    let canon = roots[0];
    let mut result = Metadata {
        length: source.length,
        bytes_read: 0,
        occurrences: Vec::new(),
        previews: Vec::new(),
        opaque: Vec::new(),
    };
    for (kind, namespace) in [
        (b"CMT1", "exif"),
        (b"CMT2", "exif"),
        (b"CMT3", "canon"),
        (b"CMT4", "gps"),
    ] {
        let id = bmff::single_child(&boxes, canon, kind)?;
        let b = &boxes[id];
        let data = source.read(b.payload)?;
        let (order, entries) = tiff::entries(&data, limits)?;
        for entry in entries {
            let range = Range::checked(
                b.payload.offset + entry.offset as u64,
                entry.length as u64,
                b.payload.end(),
            )?;
            let mut path = b.path.clone();
            path.push(Part::new("ifd", format!("IFD@{}", entry.ifd), 0));
            path.push(Part::new("tag", entry.tag.to_string(), entry.ordinal));
            if let Some((name, value, encoding)) = decode_entry(kind, &entry, &data, order)? {
                result.occurrences.push(Occurrence {
                    name,
                    namespace,
                    native_id: entry.tag.to_string(),
                    value,
                    range,
                    path,
                    order: order.name(),
                    encoding,
                });
            } else if kind == b"CMT3" && (entry.tag == 1 || entry.tag == 0x4018) {
                let (name, index, width) = if entry.tag == 1 {
                    ("Quality", 3usize, 2usize)
                } else {
                    ("DualPixelRaw", 11, 4)
                };
                if entry.format != if width == 2 { 3 } else { 4 } || entry.count as usize <= index {
                    return Err(Error::invalid("Invalid selected Canon array"));
                }
                let declared = if width == 2 {
                    usize::from(order.u16(&data, entry.offset)?)
                } else {
                    order.u32(&data, entry.offset)? as usize
                };
                if declared != entry.length {
                    return Err(Error::invalid(
                        "Canon array length header disagrees with its entry",
                    ));
                }
                let offset = entry.offset + index * width;
                let value = if width == 2 {
                    u64::from(order.u16(&data, offset)?)
                } else {
                    u64::from(order.u32(&data, offset)?)
                };
                path.push(Part::new("field", name, index));
                result.occurrences.push(Occurrence {
                    name,
                    namespace,
                    native_id: format!("{}/{index}", entry.tag),
                    value: Value::Integer(value),
                    range: Range::checked(
                        b.payload.offset + offset as u64,
                        width as u64,
                        b.payload.end(),
                    )?,
                    path,
                    order: order.name(),
                    encoding: if width == 2 { "uint16" } else { "uint32" },
                });
                result.opaque.push((range, b.path.clone()));
            } else {
                result.opaque.push((range, path));
            }
        }
    }
    let singleton = |name: &str| -> Result<&Value> {
        let found: Vec<_> = result
            .occurrences
            .iter()
            .filter(|o| o.name == name)
            .collect();
        if found.len() != 1 {
            return Err(Error::unsupported("Camera/mode field missing or ambiguous"));
        }
        Ok(&found[0].value)
    };
    if singleton("Make")? != &Value::Text("Canon".into())
        || singleton("Model")? != &Value::Text("Canon EOS R5".into())
        || singleton("CanonModelID")? != &Value::Integer(0x80000421)
    {
        return Err(Error::unsupported(
            "Only the declared Canon EOS R5 profile is supported",
        ));
    }
    if singleton("Quality")? != &Value::Integer(4)
        || singleton("DualPixelRaw")? != &Value::Integer(0)
    {
        return Err(Error::unsupported(
            "Only full RAW with Dual Pixel RAW off is supported",
        ));
    }
    let thumb = &boxes[bmff::single_child(&boxes, canon, b"THMB")?];
    let h = source.read(Range::checked(
        thumb.payload.offset,
        16,
        thumb.payload.end(),
    )?)?;
    if h[0] != 0 {
        return Err(Error::unsupported("Only JPEG THMB version 0 is supported"));
    }
    let declared = u64::from(bounded::be32(&h, 8)?);
    add_preview(
        &mut source,
        &mut result,
        "ThumbnailImage",
        Range::checked(
            thumb.payload.offset + 16,
            thumb.payload.length - 16,
            thumb.payload.end(),
        )?,
        declared,
        thumb.path.clone(),
    )?;
    let previews: Vec<_> = boxes
        .iter()
        .filter(|b| {
            b.kind == *b"PRVW"
                && b.parent
                    .is_some_and(|p| boxes[p].uuid == Some(bmff::PREVIEW_UUID))
        })
        .collect();
    if previews.len() != 1 {
        return Err(Error::unsupported("Preview box missing or ambiguous"));
    }
    let prv = previews[0];
    let h = source.read(Range::checked(prv.payload.offset, 16, prv.payload.end())?)?;
    add_preview(
        &mut source,
        &mut result,
        "PreviewImage",
        Range::checked(
            prv.payload.offset + 16,
            prv.payload.length - 16,
            prv.payload.end(),
        )?,
        u64::from(bounded::be32(&h, 12)?),
        prv.path.clone(),
    )?;
    tracks::read_tracks(&mut source, &boxes, canon, &mut result)?;
    for b in &boxes {
        if !matches!(
            &b.kind,
            b"ftyp"
                | b"moov"
                | b"trak"
                | b"mdia"
                | b"minf"
                | b"stbl"
                | b"dinf"
                | b"CMT1"
                | b"CMT2"
                | b"CMT3"
                | b"CMT4"
                | b"THMB"
                | b"PRVW"
        ) && b.payload.length > 0
        {
            result.opaque.push((b.payload, b.path.clone()));
        }
    }
    result.bytes_read = source.bytes_read;
    Ok(result)
}

fn decode_entry(
    kind: &[u8; 4],
    entry: &tiff::Entry,
    data: &[u8],
    order: tiff::Order,
) -> Result<Option<(&'static str, Value, &'static str)>> {
    let name = match (kind, entry.tag) {
        (b"CMT1", 0x010f) => "Make",
        (b"CMT1", 0x0110) => "Model",
        (b"CMT1", 0x0100) => "ImageWidth",
        (b"CMT1", 0x0101) => "ImageHeight",
        (b"CMT2", 0x829a) => "ExposureTime",
        (b"CMT2", 0x829d) => "FNumber",
        (b"CMT2", 0x8827) => "ISO",
        (b"CMT2", 0x920a) => "FocalLength",
        (b"CMT2", 0x9003) => "DateTimeOriginal",
        (b"CMT2", 0x9011) => "OffsetTimeOriginal",
        (b"CMT2", 0x9291) => "SubSecTimeOriginal",
        (b"CMT2", 0xa002) => "PixelXDimension",
        (b"CMT2", 0xa003) => "PixelYDimension",
        (b"CMT3", 7) => "CanonFirmwareVersion",
        (b"CMT3", 16) => "CanonModelID",
        _ => return Ok(None),
    };
    let string_field = matches!(
        name,
        "Make"
            | "Model"
            | "CanonFirmwareVersion"
            | "DateTimeOriginal"
            | "OffsetTimeOriginal"
            | "SubSecTimeOriginal"
    );
    let rational_field = matches!(name, "ExposureTime" | "FNumber" | "FocalLength");
    if string_field && (entry.format != 2 || entry.length > 4096) {
        return Err(Error::unsupported(
            "Selected string has an unsupported storage shape/length",
        ));
    }
    if rational_field && (entry.format != 5 || entry.count != 1) {
        return Err(Error::unsupported(
            "Selected rational has an unsupported storage shape",
        ));
    }
    if !string_field && !rational_field && (!matches!(entry.format, 3 | 4) || entry.count != 1) {
        return Err(Error::unsupported(
            "Selected integer has an unsupported storage shape",
        ));
    }
    let (value, encoding) = match entry.format {
        2 => (
            Value::Text(tiff::text(bounded::slice(
                data,
                entry.offset,
                entry.length,
            )?)?),
            "ASCII",
        ),
        3 if entry.count == 1 => (
            Value::Integer(u64::from(order.u16(data, entry.offset)?)),
            "uint16",
        ),
        4 if entry.count == 1 => (
            Value::Integer(u64::from(order.u32(data, entry.offset)?)),
            "uint32",
        ),
        5 if entry.count == 1 => (
            Value::Rational(
                order.u32(data, entry.offset)?,
                order.u32(data, entry.offset + 4)?,
            ),
            "rational64u",
        ),
        _ => {
            return Err(Error::unsupported(
                "Selected tag has an unsupported storage shape",
            ));
        }
    };
    Ok(Some((name, value, encoding)))
}

fn add_preview<R: Read + Seek>(
    source: &mut bounded::Source<R>,
    result: &mut Metadata,
    name: &'static str,
    range: Range,
    declared: u64,
    path: Vec<Part>,
) -> Result<()> {
    if range.length > source.limits.preview_bytes {
        return Err(Error::limit("Preview size limit exceeded"));
    }
    if declared < 2 || range.length < 2 || declared > range.length || range.length - declared > 16 {
        return Err(Error::invalid("Invalid declared preview length"));
    }
    if source.bytes::<2>(range.offset)? != [0xff, 0xd8] {
        return Err(Error::unsupported("Resource is not a stored JPEG preview"));
    }
    if range.length > declared
        && source
            .read(Range::checked(
                range.offset + declared,
                range.length - declared,
                range.end(),
            )?)?
            .iter()
            .any(|b| *b != 0)
    {
        return Err(Error::unsupported("Unknown nonzero preview trailer"));
    }
    // The stored extent, including its verified padding, is the extraction unit.
    // Trimming to the JPEG length would lose bytes observed in the reference.
    result.occurrences.push(Occurrence {
        name,
        namespace: "canon:binary",
        native_id: match name {
            "ThumbnailImage" => "THMB",
            "PreviewImage" => "PRVW",
            _ => "JPEG-sample",
        }
        .into(),
        value: Value::Binary(range),
        range,
        path: path.clone(),
        order: "not-applicable",
        encoding: "binary",
    });
    result.previews.push(Preview { name, range, path });
    Ok(())
}
