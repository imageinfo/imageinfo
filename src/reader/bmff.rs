use super::{
    Error, Part, Result,
    bounded::{Range, Source},
};
use std::{
    collections::BTreeMap,
    io::{Read, Seek},
};

pub const CANON_UUID: [u8; 16] = [
    0x85, 0xc0, 0xb6, 0x87, 0x82, 0x0f, 0x11, 0xe0, 0x81, 0x11, 0xf4, 0xce, 0x46, 0x2b, 0x6a, 0x48,
];
pub const PREVIEW_UUID: [u8; 16] = [
    0xea, 0xf4, 0x2b, 0x5e, 0x1c, 0x98, 0x4b, 0x88, 0xb9, 0xfb, 0xb7, 0xdc, 0x40, 0x6e, 0x4d, 0x16,
];

#[derive(Clone, Debug)]
pub struct BoxInfo {
    pub kind: [u8; 4],
    pub payload: Range,
    pub parent: Option<usize>,
    pub path: Vec<Part>,
    pub uuid: Option<[u8; 16]>,
}

pub fn scan<R: Read + Seek>(source: &mut Source<R>) -> Result<Vec<BoxInfo>> {
    let mut boxes = Vec::new();
    walk(source, 0, source.length, None, &[], &mut boxes)?;
    Ok(boxes)
}

fn walk<R: Read + Seek>(
    source: &mut Source<R>,
    mut offset: u64,
    end: u64,
    parent: Option<usize>,
    path: &[Part],
    boxes: &mut Vec<BoxInfo>,
) -> Result<()> {
    if path.len() > source.limits.depth {
        return Err(Error::limit("Box nesting limit exceeded"));
    }
    let mut indices = BTreeMap::new();
    while offset < end {
        if boxes.len() >= source.limits.boxes {
            return Err(Error::limit("Box count limit exceeded"));
        }
        Range::checked(offset, 8, end)?;
        let h = source.bytes::<8>(offset)?;
        let short = u32::from_be_bytes([h[0], h[1], h[2], h[3]]);
        let kind = [h[4], h[5], h[6], h[7]];
        let (size, header) = match short {
            0 => (end - offset, 8),
            1 => {
                Range::checked(offset, 16, end)?;
                (u64::from_be_bytes(source.bytes::<8>(offset + 8)?), 16)
            }
            value => (u64::from(value), 8),
        };
        if size < header {
            return Err(Error::invalid("Box size is smaller than its header"));
        }
        let range = Range::checked(offset, size, end)?;
        let mut payload = Range::checked(offset + header, size - header, end)?;
        let mut uuid = None;
        if &kind == b"uuid" {
            if payload.length < 16 {
                return Err(Error::invalid("Truncated UUID box"));
            }
            uuid = Some(source.bytes::<16>(payload.offset)?);
            payload = Range::checked(payload.offset + 16, payload.length - 16, range.end())?;
        }
        let index = indices.entry(kind).or_insert(0usize);
        let mut own_path = path.to_vec();
        own_path.push(Part::new("box", fourcc(kind), *index));
        *index += 1;
        let id = boxes.len();
        boxes.push(BoxInfo {
            kind,
            payload,
            parent,
            path: own_path.clone(),
            uuid,
        });
        let container = matches!(
            &kind,
            b"moov" | b"trak" | b"mdia" | b"minf" | b"stbl" | b"dinf"
        );
        let canon = uuid == Some(CANON_UUID) && parent.is_some_and(|p| boxes[p].kind == *b"moov");
        if container || canon {
            walk(
                source,
                payload.offset,
                payload.end(),
                Some(id),
                &own_path,
                boxes,
            )?;
        } else if uuid == Some(PREVIEW_UUID) {
            if payload.length < 8 {
                return Err(Error::invalid("Truncated preview wrapper"));
            }
            if source.bytes::<8>(payload.offset)? != [0, 0, 0, 0, 0, 0, 0, 1] {
                return Err(Error::unsupported("Unknown preview wrapper version"));
            }
            walk(
                source,
                payload.offset + 8,
                payload.end(),
                Some(id),
                &own_path,
                boxes,
            )?;
        }
        offset = range.end();
    }
    Ok(())
}

pub fn fourcc(value: [u8; 4]) -> String {
    if value.iter().all(|b| b.is_ascii_graphic() || *b == b' ') {
        String::from_utf8_lossy(&value).into_owned()
    } else {
        value.iter().map(|b| format!("{b:02x}")).collect()
    }
}

pub fn single_child(boxes: &[BoxInfo], parent: usize, kind: &[u8; 4]) -> Result<usize> {
    let found: Vec<_> = boxes
        .iter()
        .enumerate()
        .filter(|(_, b)| b.parent == Some(parent) && &b.kind == kind)
        .map(|(i, _)| i)
        .collect();
    if found.len() != 1 {
        return Err(Error::unsupported("Required box missing or ambiguous"));
    }
    Ok(found[0])
}
