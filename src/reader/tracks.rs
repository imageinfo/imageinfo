use super::{
    Error, Metadata, Occurrence, Part, Result, Value,
    bmff::{self, BoxInfo},
    bounded::{self, Range, Source},
};
use std::{
    collections::BTreeMap,
    io::{Read, Seek},
};

struct Track {
    sample: Range,
    path: Vec<Part>,
    description: Vec<u8>,
}

pub fn read_tracks<R: Read + Seek>(
    source: &mut Source<R>,
    boxes: &[BoxInfo],
    canon: usize,
    result: &mut Metadata,
) -> Result<()> {
    let cctp = &boxes[bmff::single_child(boxes, canon, b"CCTP")?];
    let map = source.read(cctp.payload)?;
    if bounded::be32(&map, 0)? != 0
        || bounded::be32(&map, 4)? != 1
        || bounded::be32(&map, 8)? != 3
        || map.len() != 84
    {
        return Err(Error::unsupported(
            "Only the declared three-image CCTP profile is supported",
        ));
    }
    let mut assignments = BTreeMap::new();
    for i in 0..3 {
        let at = 12 + i * 24;
        if bounded::be32(&map, at)? != 24
            || bounded::slice(&map, at + 4, 4)? != b"CCDT"
            || bounded::be32(&map, at + 16)? != 0
        {
            return Err(Error::unsupported("Unknown CCDT profile"));
        }
        let kind = bounded::be64(&map, at + 8)?;
        let id = bounded::be32(&map, at + 20)?;
        if !matches!(kind, 0 | 1 | 16) || assignments.insert(kind, id).is_some() {
            return Err(Error::unsupported("Ambiguous image track assignment"));
        }
    }
    if assignments
        .values()
        .copied()
        .collect::<std::collections::BTreeSet<_>>()
        .len()
        != 3
    {
        return Err(Error::invalid("Image roles alias the same track"));
    }
    let movie = boxes[canon]
        .parent
        .ok_or_else(|| Error::invalid("Missing movie parent"))?;
    let mut tracks = BTreeMap::new();
    let mut timed = None;
    for (id, node) in boxes
        .iter()
        .enumerate()
        .filter(|(_, b)| b.parent == Some(movie) && b.kind == *b"trak")
    {
        let header = &boxes[bmff::single_child(boxes, id, b"tkhd")?];
        let h = source.read(Range::checked(
            header.payload.offset,
            24,
            header.payload.end(),
        )?)?;
        let track_id = match h[0] {
            0 => bounded::be32(&h, 12)?,
            1 => bounded::be32(&h, 20)?,
            _ => return Err(Error::unsupported("Unknown track-header version")),
        };
        if track_id == 0 || tracks.contains_key(&track_id) {
            return Err(Error::invalid("Duplicate or zero track ID"));
        }
        let media = bmff::single_child(boxes, id, b"mdia")?;
        let info = bmff::single_child(boxes, media, b"minf")?;
        let dinf = bmff::single_child(boxes, info, b"dinf")?;
        let dref = &boxes[bmff::single_child(boxes, dinf, b"dref")?];
        let d = source.read(dref.payload)?;
        if d.len() != 20
            || bounded::be32(&d, 0)? != 0
            || bounded::be32(&d, 4)? != 1
            || bounded::be32(&d, 8)? != 12
            || bounded::slice(&d, 12, 4)? != b"url "
            || bounded::be32(&d, 16)? != 1
        {
            return Err(Error::unsupported(
                "External or unknown media data reference",
            ));
        }
        let table = bmff::single_child(boxes, info, b"stbl")?;
        let stsd = &boxes[bmff::single_child(boxes, table, b"stsd")?];
        let description = source.read(stsd.payload)?;
        if bounded::be32(&description, 0)? != 0
            || bounded::be32(&description, 4)? != 1
            || bounded::be32(&description, 8)? as usize != description.len() - 8
        {
            return Err(Error::unsupported(
                "Only one sample description per track is supported",
            ));
        }
        if bounded::slice(&description, 22, 2)? != [0, 1] {
            return Err(Error::unsupported(
                "Unsupported sample data-reference index",
            ));
        }
        let desc_type = bounded::slice(&description, 12, 4)?;
        if !matches!(desc_type, b"CRAW" | b"CTMD") {
            return Err(Error::unsupported("Unknown sample descriptor"));
        }
        let sample = sample_range(source, boxes, table)?;
        if !boxes.iter().any(|b| {
            b.kind == *b"mdat"
                && sample.offset >= b.payload.offset
                && sample.end() <= b.payload.end()
        }) {
            return Err(Error::invalid("Sample is outside media data"));
        }
        if desc_type == b"CTMD" && timed.replace(track_id).is_some() {
            return Err(Error::unsupported("Multiple timed-metadata tracks"));
        }
        tracks.insert(
            track_id,
            Track {
                sample,
                path: node.path.clone(),
                description,
            },
        );
    }
    if tracks.len() != 4 {
        return Err(Error::unsupported(
            "Only the four-track R5 profile is supported",
        ));
    }
    let full = tracks
        .get(
            assignments
                .get(&0)
                .ok_or_else(|| Error::invalid("No full sensor assignment"))?,
        )
        .ok_or_else(|| Error::invalid("Unresolved full sensor track"))?;
    let parts = description_parts(&full.description)?;
    let cmp: Vec<_> = parts.iter().filter(|(kind, _)| kind == b"CMP1").collect();
    if cmp.len() != 1 {
        return Err(Error::unsupported(
            "Full RAW compression descriptor missing or ambiguous",
        ));
    }
    let header = cmp[0].1;
    if header.len() < 52
        || bounded::slice(header, 4, 2)? != [1, 0]
        || header[26] != 0
        || !matches!(header[24], 12 | 14)
    {
        return Err(Error::unsupported(
            "Only declared full RAW encoding is supported; C-RAW/burst profiles are refused",
        ));
    }
    for (name, offset) in [("ImageWidth", 8), ("ImageHeight", 12)] {
        let values: Vec<_> = result
            .occurrences
            .iter()
            .filter(|o| o.name == name)
            .collect();
        if values.len() != 1 {
            return Err(Error::unsupported("Image dimension missing or ambiguous"));
        }
        let super::Value::Integer(visible) = values[0].value else {
            return Err(Error::invalid("Invalid visible image dimension"));
        };
        if visible == 0 || u64::from(bounded::be32(header, offset)?) < visible {
            return Err(Error::unsupported(
                "Main sensor descriptor is inconsistent with visible image dimensions",
            ));
        }
    }
    let jpeg = tracks
        .get(
            assignments
                .get(&16)
                .ok_or_else(|| Error::invalid("No JPEG assignment"))?,
        )
        .ok_or_else(|| Error::invalid("Unresolved JPEG track"))?;
    if !description_parts(&jpeg.description)?
        .iter()
        .any(|(kind, _)| kind == b"JPEG")
    {
        return Err(Error::unsupported("JPEG track lacks its descriptor"));
    }
    super::add_preview(
        source,
        result,
        "JpgFromRaw",
        jpeg.sample,
        jpeg.sample.length,
        jpeg.path.clone(),
    )?;
    let timed = tracks
        .get(&timed.ok_or_else(|| Error::unsupported("No timed metadata track"))?)
        .ok_or_else(|| Error::invalid("Unresolved metadata track"))?;
    read_timed(source, timed, result)?;
    Ok(())
}

fn sample_range<R: Read + Seek>(
    source: &mut Source<R>,
    boxes: &[BoxInfo],
    table: usize,
) -> Result<Range> {
    let sc = source.read(boxes[bmff::single_child(boxes, table, b"stsc")?].payload)?;
    if sc.len() != 20
        || bounded::be32(&sc, 0)? != 0
        || (
            bounded::be32(&sc, 4)?,
            bounded::be32(&sc, 8)?,
            bounded::be32(&sc, 12)?,
            bounded::be32(&sc, 16)?,
        ) != (1, 1, 1, 1)
    {
        return Err(Error::unsupported(
            "Only one local sample/chunk is supported",
        ));
    }
    let sizes = source.read(boxes[bmff::single_child(boxes, table, b"stsz")?].payload)?;
    if bounded::be32(&sizes, 0)? != 0 || bounded::be32(&sizes, 8)? != 1 {
        return Err(Error::unsupported(
            "Only single-sample RAW tracks are supported",
        ));
    }
    let default = bounded::be32(&sizes, 4)?;
    let length = if default == 0 {
        if sizes.len() != 16 {
            return Err(Error::invalid("Invalid explicit sample size"));
        }
        bounded::be32(&sizes, 12)?
    } else {
        if sizes.len() != 12 {
            return Err(Error::invalid("Invalid uniform sample size"));
        }
        default
    };
    if length == 0 {
        return Err(Error::invalid("Empty media sample"));
    }
    let candidates: Vec<_> = boxes
        .iter()
        .filter(|b| b.parent == Some(table) && matches!(&b.kind, b"stco" | b"co64"))
        .collect();
    if candidates.len() != 1 {
        return Err(Error::unsupported(
            "Chunk offset table missing or ambiguous",
        ));
    }
    let b = candidates[0];
    let offsets = source.read(b.payload)?;
    if bounded::be32(&offsets, 0)? != 0 || bounded::be32(&offsets, 4)? != 1 {
        return Err(Error::unsupported("Only one chunk offset is supported"));
    }
    let offset = if b.kind == *b"co64" {
        if offsets.len() != 16 {
            return Err(Error::invalid("Invalid 64-bit chunk offset"));
        }
        bounded::be64(&offsets, 8)?
    } else {
        if offsets.len() != 12 {
            return Err(Error::invalid("Invalid chunk offset"));
        }
        u64::from(bounded::be32(&offsets, 8)?)
    };
    Range::checked(offset, u64::from(length), source.length)
}

fn description_parts(description: &[u8]) -> Result<Vec<([u8; 4], &[u8])>> {
    if bounded::slice(description, 12, 4)? != b"CRAW" || description.len() < 98 {
        return Err(Error::unsupported("Unknown Canon image descriptor"));
    }
    let mut at = 98;
    let mut parts = Vec::new();
    while at < description.len() {
        let size = bounded::be32(description, at)? as usize;
        if size < 8 {
            return Err(Error::invalid("Invalid sample child box"));
        }
        let data = bounded::slice(description, at, size)?;
        let kind: [u8; 4] = bounded::slice(data, 4, 4)?
            .try_into()
            .map_err(|_| Error::invalid("Short child type"))?;
        parts.push((kind, &data[8..]));
        at = at
            .checked_add(size)
            .ok_or_else(|| Error::invalid("Sample child offset overflow"))?;
    }
    Ok(parts)
}

fn read_timed<R: Read + Seek>(
    source: &mut Source<R>,
    track: &Track,
    result: &mut Metadata,
) -> Result<()> {
    let mut at = track.sample.offset;
    let mut index = 0;
    while at < track.sample.end() {
        if index >= source.limits.records {
            return Err(Error::limit("Timed record limit exceeded"));
        }
        let h = source.read(Range::checked(at, 12, track.sample.end())?)?;
        let size = u64::from(bounded::le32(&h, 0)?);
        let typ = bounded::le16(&h, 4)?;
        if size < 12 {
            return Err(Error::invalid(
                "Timed record size is smaller than its header",
            ));
        }
        let record = Range::checked(at, size, track.sample.end())?;
        let mut path = track.path.clone();
        path.push(Part::new("record", format!("CTMD-type-{typ}"), index));
        if typ == 5 {
            if size < 24 {
                return Err(Error::invalid("Truncated timed exposure record"));
            }
            let data = source.read(Range::checked(at + 12, 12, record.end())?)?;
            for (name, offset, value, width, encoding) in [
                (
                    "FNumber",
                    0,
                    Value::Rational(
                        u32::from(bounded::le16(&data, 0)?),
                        u32::from(bounded::le16(&data, 2)?),
                    ),
                    4,
                    "rational32u",
                ),
                (
                    "ExposureTime",
                    4,
                    Value::Rational(
                        u32::from(bounded::le16(&data, 4)?),
                        u32::from(bounded::le16(&data, 6)?),
                    ),
                    4,
                    "rational32u",
                ),
                (
                    "ISO",
                    8,
                    Value::Integer(u64::from(bounded::le32(&data, 8)?)),
                    4,
                    "uint32",
                ),
            ] {
                let mut location = path.clone();
                location.push(Part::new("field", name, offset));
                result.occurrences.push(Occurrence {
                    name,
                    namespace: "canon:ctmd",
                    native_id: format!("5/{offset}"),
                    value,
                    range: Range::checked(at + 12 + offset as u64, width, record.end())?,
                    path: location,
                    order: "little",
                    encoding,
                });
            }
        } else {
            result
                .opaque
                .push((Range::checked(at + 12, size - 12, record.end())?, path));
        }
        at = record.end();
        index += 1;
    }
    Ok(())
}
