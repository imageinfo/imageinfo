//! Authored finite structural corpus and independent length/count oracle.
#![allow(dead_code)]
use super::support;

#[derive(Clone, Debug)]
pub struct BoxExtent {
    pub start: usize,
    pub end: usize,
    pub children: usize,
    pub kind: [u8; 4],
    pub depth: usize,
}

pub fn boxes(bytes: &[u8]) -> Vec<BoxExtent> {
    fn visit(b: &[u8], start: usize, end: usize, depth: usize, out: &mut Vec<BoxExtent>) {
        let mut at = start;
        while at < end {
            let len = u32::from_be_bytes(b[at..at + 4].try_into().unwrap()) as usize;
            assert!(len >= 8 && at + len <= end);
            let kind: [u8; 4] = b[at + 4..at + 8].try_into().unwrap();
            let children = match &kind {
                b"moov" | b"trak" | b"mdia" | b"minf" | b"stbl" | b"dinf" => at + 8,
                b"uuid"
                    if b[at + 8..at + 24]
                        == [
                            0x85, 0xc0, 0xb6, 0x87, 0x82, 0x0f, 0x11, 0xe0, 0x81, 0x11, 0xf4, 0xce,
                            0x46, 0x2b, 0x6a, 0x48,
                        ] =>
                {
                    at + 24
                }
                b"uuid"
                    if b[at + 8..at + 24]
                        == [
                            0xea, 0xf4, 0x2b, 0x5e, 0x1c, 0x98, 0x4b, 0x88, 0xb9, 0xfb, 0xb7, 0xdc,
                            0x40, 0x6e, 0x4d, 0x16,
                        ] =>
                {
                    at + 32
                }
                _ => at + len,
            };
            out.push(BoxExtent {
                start: at,
                end: at + len,
                children,
                kind,
                depth,
            });
            visit(b, children, at + len, depth + 1, out);
            at += len;
        }
        assert_eq!(at, end);
    }
    let mut out = Vec::new();
    visit(bytes, 0, bytes.len(), 0, &mut out);
    out
}

pub fn box_count(n: usize) -> Vec<u8> {
    let mut b = support::fixture().bytes;
    let base = boxes(&b).len();
    assert!(n >= base);
    for _ in base..n {
        b.extend(support::atom(b"free", vec![]));
    }
    assert_eq!(boxes(&b).len(), n);
    b
}

/// Depth is the parent path length at a traversal call; a leaf at path n+1
/// is accepted when n containers precede it and the configured limit is n.
pub fn bmff_depth(n: usize) -> Vec<u8> {
    let mut b = support::fixture().bytes;
    let mut nested = support::atom(b"free", vec![]);
    for _ in 0..n {
        nested = support::atom(b"dinf", nested);
    }
    b.extend(nested);
    assert_eq!(boxes(&b).iter().map(|v| v.depth).max(), Some(n));
    b
}

fn replace_cmt4(payload: Vec<u8>) -> Vec<u8> {
    let mut b = support::fixture().bytes;
    let inventory = boxes(&b);
    let old = inventory.iter().find(|v| &v.kind == b"CMT4").unwrap();
    let replacement = support::atom(b"CMT4", payload);
    let delta = replacement.len() as i64 - (old.end - old.start) as i64;
    for v in &inventory {
        if v.start < old.start && v.end >= old.end {
            let length = ((v.end - v.start) as i64 + delta) as u32;
            b[v.start..v.start + 4].copy_from_slice(&length.to_be_bytes());
        }
        if &v.kind == b"co64" {
            let at = v.start + 16;
            let offset = u64::from_be_bytes(b[at..at + 8].try_into().unwrap());
            b[at..at + 8].copy_from_slice(&((offset as i64 + delta) as u64).to_be_bytes());
        }
    }
    b.splice(old.start..old.end, replacement);
    boxes(&b);
    b
}

pub fn entries(n: usize) -> Vec<u8> {
    replace_cmt4(support::tiff(
        (0..n).map(|_| (0xe000, 1, vec![0x5a])).collect(),
    ))
}

pub fn split_entries(second: usize) -> Vec<u8> {
    let mut first = support::tiff((0..2048).map(|_| (0xe000, 1, vec![1])).collect());
    let next = first.len() as u32;
    let tail = first.len() - 4;
    first[tail..].copy_from_slice(&next.to_le_bytes());
    first.extend(&support::tiff((0..second).map(|_| (0xe001, 1, vec![2])).collect())[8..]);
    replace_cmt4(first)
}

/// Independent classic-TIFF chain oracle over the generated CMT4 only.
/// Tuples are absolute IFD offset, zero-based depth, and declared entry count.
pub fn cmt4_directories(bytes: &[u8]) -> Vec<(usize, usize, usize)> {
    let inventory = boxes(bytes);
    let cmt = inventory.iter().find(|v| &v.kind == b"CMT4").unwrap();
    let base = cmt.start + 8;
    assert_eq!(&bytes[base..base + 4], b"II\x2a\0");
    let mut offset = u32::from_le_bytes(bytes[base + 4..base + 8].try_into().unwrap()) as usize;
    let mut directories = Vec::new();
    while offset != 0 {
        assert!(!directories.iter().any(|(at, _, _)| *at == base + offset));
        let count = u16::from_le_bytes(bytes[base + offset..base + offset + 2].try_into().unwrap())
            as usize;
        assert!(base + offset + 6 + count * 12 <= cmt.end);
        directories.push((base + offset, directories.len(), count));
        let next_at = base + offset + 2 + 12 * count;
        offset = u32::from_le_bytes(bytes[next_at..next_at + 4].try_into().unwrap()) as usize;
    }
    directories
}

/// A next-IFD chain: first IFD depth 0, last IFD depth n, all counts zero.
pub fn tiff_depth(n: usize) -> Vec<u8> {
    let mut t = b"II\x2a\0\x08\0\0\0".to_vec();
    for i in 0..=n {
        t.extend(0u16.to_le_bytes());
        t.extend(if i == n { 0 } else { (8 + (i + 1) * 6) as u32 }.to_le_bytes());
    }
    replace_cmt4(t)
}

pub fn records(n: usize) -> Vec<u8> {
    let mut b = support::fixture().bytes;
    let inventory = boxes(&b);
    let sample_size = inventory
        .iter()
        .rfind(|v| &v.kind == b"stsz")
        .unwrap()
        .start
        + 12;
    b[sample_size..sample_size + 4].copy_from_slice(&((n * 40) as u32).to_be_bytes());
    let mdat = inventory.iter().find(|v| &v.kind == b"mdat").unwrap();
    let record = b[b.len() - 40..].to_vec();
    b.truncate(b.len() - 40);
    for _ in 0..n {
        b.extend(&record);
    }
    let size = (b.len() - mdat.start) as u32;
    b[mdat.start..mdat.start + 4].copy_from_slice(&size.to_be_bytes());
    b
}

/// Locate the CTMD track by its encoded sample-description type, obtain the
/// single sample's size and offset from its own tables, then walk stored sizes.
/// Returned tuples are absolute record offsets and declared record lengths.
pub fn timed_records(bytes: &[u8]) -> Vec<(usize, usize)> {
    let inventory = boxes(bytes);
    let stsd = inventory
        .iter()
        .find(|v| &v.kind == b"stsd" && &bytes[v.start + 20..v.start + 24] == b"CTMD")
        .unwrap();
    let stbl = inventory
        .iter()
        .find(|v| &v.kind == b"stbl" && v.start < stsd.start && v.end >= stsd.end)
        .unwrap();
    let size_table = inventory
        .iter()
        .find(|v| &v.kind == b"stsz" && v.start > stbl.start && v.end <= stbl.end)
        .unwrap();
    assert_eq!(
        u32::from_be_bytes(
            bytes[size_table.start + 16..size_table.start + 20]
                .try_into()
                .unwrap()
        ),
        1
    );
    let length = u32::from_be_bytes(
        bytes[size_table.start + 12..size_table.start + 16]
            .try_into()
            .unwrap(),
    ) as usize;
    let offset_table = inventory
        .iter()
        .find(|v| &v.kind == b"co64" && v.start > stbl.start && v.end <= stbl.end)
        .unwrap();
    assert_eq!(
        u32::from_be_bytes(
            bytes[offset_table.start + 12..offset_table.start + 16]
                .try_into()
                .unwrap()
        ),
        1
    );
    let start = u64::from_be_bytes(
        bytes[offset_table.start + 16..offset_table.start + 24]
            .try_into()
            .unwrap(),
    ) as usize;
    let end = start.checked_add(length).unwrap();
    let mdat = inventory
        .iter()
        .find(|v| &v.kind == b"mdat" && v.start + 8 <= start && end <= v.end)
        .unwrap();
    assert!(end <= mdat.end);
    let mut at = start;
    let mut records = Vec::new();
    while at < end {
        assert!(at + 12 <= end);
        let size = u32::from_le_bytes(bytes[at..at + 4].try_into().unwrap()) as usize;
        assert!(size >= 12 && at + size <= end);
        assert_eq!(
            u16::from_le_bytes(bytes[at + 4..at + 6].try_into().unwrap()),
            5
        );
        records.push((at, size));
        at += size;
    }
    assert_eq!(at, end);
    records
}

pub fn corpus() -> Vec<(String, Vec<u8>, Option<&'static str>)> {
    let mut out = Vec::new();
    type Maker = fn(usize) -> Vec<u8>;
    for (name, limit, make, refusal) in [
        (
            "boxes",
            4096,
            box_count as Maker,
            "Box count limit exceeded",
        ),
        (
            "bmff-depth",
            16,
            bmff_depth as Maker,
            "Box nesting limit exceeded",
        ),
        (
            "tiff-depth",
            16,
            tiff_depth as Maker,
            "IFD depth limit exceeded",
        ),
        (
            "entries-per-cmt",
            4096,
            entries as Maker,
            "TIFF entry limit exceeded",
        ),
        (
            "timed-records",
            4096,
            records as Maker,
            "Timed record limit exceeded",
        ),
    ] {
        for (label, n) in [("below", limit - 1), ("at", limit), ("above", limit + 1)] {
            out.push((
                format!("{name}-{label}"),
                make(n),
                if n > limit { Some(refusal) } else { None },
            ));
        }
    }
    out
}
