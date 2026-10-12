//! Independently authored structural fixtures. No camera image/pixel data.
use std::{
    fs,
    path::PathBuf,
    sync::atomic::{AtomicU64, Ordering},
};

pub fn atom(kind: &[u8; 4], payload: Vec<u8>) -> Vec<u8> {
    let mut out = ((payload.len() + 8) as u32).to_be_bytes().to_vec();
    out.extend(kind);
    out.extend(payload);
    out
}
fn concat(parts: Vec<Vec<u8>>) -> Vec<u8> {
    parts.into_iter().flatten().collect()
}
fn long(n: u32) -> Vec<u8> {
    n.to_le_bytes().to_vec()
}
fn short(n: u16) -> Vec<u8> {
    n.to_le_bytes().to_vec()
}
fn rational(n: u32, d: u32) -> Vec<u8> {
    concat(vec![long(n), long(d)])
}

pub fn tiff(mut entries: Vec<(u16, u16, Vec<u8>)>) -> Vec<u8> {
    entries.sort_by_key(|e| e.0);
    let mut out = b"II\x2a\0\x08\0\0\0".to_vec();
    out.extend((entries.len() as u16).to_le_bytes());
    out.resize(8 + 2 + entries.len() * 12 + 4, 0);
    for (i, (tag, format, data)) in entries.into_iter().enumerate() {
        let width = match format {
            1 | 2 | 7 => 1,
            3 => 2,
            4 => 4,
            5 => 8,
            _ => panic!("fixture type"),
        };
        let at = 10 + i * 12;
        out[at..at + 2].copy_from_slice(&tag.to_le_bytes());
        out[at + 2..at + 4].copy_from_slice(&format.to_le_bytes());
        out[at + 4..at + 8].copy_from_slice(&((data.len() / width) as u32).to_le_bytes());
        if data.len() <= 4 {
            out[at + 8..at + 8 + data.len()].copy_from_slice(&data);
        } else {
            let offset = out.len() as u32;
            out[at + 8..at + 12].copy_from_slice(&offset.to_le_bytes());
            out.extend(data);
        }
    }
    out
}

#[derive(Clone)]
pub struct Fixture {
    pub bytes: Vec<u8>,
    pub thumbnail: Vec<u8>,
    pub preview: Vec<u8>,
    pub jpeg: Vec<u8>,
}

pub fn fixture() -> Fixture {
    fixture_with_firmware("Firmware Version test")
}

pub fn fixture_with_firmware(firmware: &str) -> Fixture {
    let thumb = vec![0xff, 0xd8, 0x41, 0xff, 0xd9, 0];
    let preview = vec![0xff, 0xd8, 0x42, 0xff, 0xd9, 0, 0, 0, 0, 0];
    let jpeg = vec![0xff, 0xd8, 0x43, 0xff, 0xd9, 0, 0];
    fixture_with_previews(firmware, thumb, preview, jpeg)
}

pub fn fixture_with_previews(
    firmware: &str,
    thumb: Vec<u8>,
    preview: Vec<u8>,
    jpeg: Vec<u8>,
) -> Fixture {
    let mut settings = vec![0u8; 110];
    settings[..2].copy_from_slice(&110u16.to_le_bytes());
    settings[6..8].copy_from_slice(&4u16.to_le_bytes());
    let mut lighting = vec![0u8; 60];
    lighting[..4].copy_from_slice(&60u32.to_le_bytes());
    let cmt1 = tiff(vec![
        (256, 3, short(8192)),
        (257, 3, short(5464)),
        (271, 2, b"Canon\0".to_vec()),
        (272, 2, b"Canon EOS R5\0".to_vec()),
    ]);
    let cmt2 = tiff(vec![
        (0x829a, 5, rational(2, 500)),
        (0x829d, 5, rational(63, 10)),
        (0x8827, 3, short(800)),
        (0x920a, 5, rational(2400, 10)),
        (0x9003, 2, b"2026:01:02 03:04:05\0".to_vec()),
        (0x9011, 2, b"+00:00\0".to_vec()),
        (0x9291, 2, b"00\0".to_vec()),
        (0xa002, 4, long(8192)),
        (0xa003, 4, long(5464)),
    ]);
    let cmt3 = tiff(vec![
        (1, 3, settings),
        (7, 2, [firmware.as_bytes(), &[0]].concat()),
        (16, 4, long(0x80000421)),
        (0x4018, 4, lighting),
    ]);
    let mut thumb_header = vec![0u8; 16];
    let jpeg_length =
        |bytes: &[u8]| (bytes.windows(2).rposition(|v| v == [0xff, 0xd9]).unwrap() + 2) as u32;
    thumb_header[8..12].copy_from_slice(&jpeg_length(&thumb).to_be_bytes());
    let mut preview_header = vec![0u8; 16];
    preview_header[12..16].copy_from_slice(&jpeg_length(&preview).to_be_bytes());
    let mut cctp = vec![0; 12];
    cctp[4..8].copy_from_slice(&1u32.to_be_bytes());
    cctp[8..12].copy_from_slice(&3u32.to_be_bytes());
    for (kind, id) in [(16u64, 1u32), (1, 2), (0, 3)] {
        let mut body = kind.to_be_bytes().to_vec();
        body.extend(0u32.to_be_bytes());
        body.extend(id.to_be_bytes());
        cctp.extend(atom(b"CCDT", body));
    }
    let canon = concat(vec![
        vec![
            0x85, 0xc0, 0xb6, 0x87, 0x82, 0x0f, 0x11, 0xe0, 0x81, 0x11, 0xf4, 0xce, 0x46, 0x2b,
            0x6a, 0x48,
        ],
        atom(b"CCTP", cctp),
        atom(b"CMT1", cmt1),
        atom(b"CMT2", cmt2),
        atom(b"CMT3", cmt3),
        atom(b"CMT4", tiff(vec![])),
        atom(b"THMB", concat(vec![thumb_header, thumb.clone()])),
    ]);
    let preview_box = atom(
        b"uuid",
        concat(vec![
            vec![
                0xea, 0xf4, 0x2b, 0x5e, 0x1c, 0x98, 0x4b, 0x88, 0xb9, 0xfb, 0xb7, 0xdc, 0x40, 0x6e,
                0x4d, 0x16,
            ],
            vec![0, 0, 0, 0, 0, 0, 0, 1],
            atom(b"PRVW", concat(vec![preview_header, preview.clone()])),
        ]),
    );
    let mut timed = vec![0u8; 40];
    timed[..4].copy_from_slice(&40u32.to_le_bytes());
    timed[4..6].copy_from_slice(&5u16.to_le_bytes());
    timed[12..14].copy_from_slice(&63u16.to_le_bytes());
    timed[14..16].copy_from_slice(&10u16.to_le_bytes());
    timed[16..18].copy_from_slice(&1u16.to_le_bytes());
    timed[18..20].copy_from_slice(&250u16.to_le_bytes());
    timed[20..24].copy_from_slice(&800u32.to_le_bytes());
    let payload = concat(vec![jpeg.clone(), vec![0; 4], vec![0; 4], timed]);
    let ftyp = atom(b"ftyp", b"crx \0\0\0\x01crx isom".to_vec());
    let sizes = [jpeg.len() as u32, 4, 4, 40];
    let make_movie = |offsets: [u64; 4]| {
        atom(
            b"moov",
            concat(vec![
                atom(b"uuid", canon.clone()),
                track(1, b"CRAW", offsets[0], sizes[0], true),
                track(2, b"CRAW", offsets[1], sizes[1], false),
                track(3, b"CRAW", offsets[2], sizes[2], false),
                track(4, b"CTMD", offsets[3], sizes[3], false),
            ]),
        )
    };
    let provisional = make_movie([0; 4]);
    let start = (ftyp.len() + provisional.len() + preview_box.len() + 8) as u64;
    let movie = make_movie([
        start,
        start + u64::from(sizes[0]),
        start + u64::from(sizes[0]) + 4,
        start + u64::from(sizes[0]) + 8,
    ]);
    Fixture {
        bytes: concat(vec![ftyp, movie, preview_box, atom(b"mdat", payload)]),
        thumbnail: thumb,
        preview,
        jpeg,
    }
}

fn track(id: u32, kind: &[u8; 4], offset: u64, size: u32, jpeg: bool) -> Vec<u8> {
    let mut header = vec![0; 84];
    header[12..16].copy_from_slice(&id.to_be_bytes());
    let mut entry = if kind == b"CTMD" {
        vec![0; 76]
    } else {
        vec![0; 90]
    };
    entry[4..8].copy_from_slice(kind);
    entry[14..16].copy_from_slice(&1u16.to_be_bytes());
    if kind == b"CRAW" {
        if jpeg {
            entry.extend(atom(b"JPEG", vec![0; 4]));
        } else {
            let mut cmp = vec![0; 52];
            cmp[4..6].copy_from_slice(&0x100u16.to_be_bytes());
            cmp[8..12].copy_from_slice(&8352u32.to_be_bytes());
            cmp[12..16].copy_from_slice(&5586u32.to_be_bytes());
            cmp[24] = 14;
            entry.extend(atom(b"CMP1", cmp));
        }
    }
    let length = entry.len() as u32;
    entry[..4].copy_from_slice(&length.to_be_bytes());
    let stsd = atom(
        b"stsd",
        concat(vec![vec![0; 4], 1u32.to_be_bytes().to_vec(), entry]),
    );
    let stsc = atom(
        b"stsc",
        concat(vec![vec![0; 4], 1u32.to_be_bytes().repeat(4)]),
    );
    let stsz = atom(
        b"stsz",
        concat(vec![
            vec![0; 4],
            size.to_be_bytes().to_vec(),
            1u32.to_be_bytes().to_vec(),
        ]),
    );
    let co64 = atom(
        b"co64",
        concat(vec![
            vec![0; 4],
            1u32.to_be_bytes().to_vec(),
            offset.to_be_bytes().to_vec(),
        ]),
    );
    let dref = atom(
        b"dref",
        concat(vec![
            vec![0; 4],
            1u32.to_be_bytes().to_vec(),
            atom(b"url ", 1u32.to_be_bytes().to_vec()),
        ]),
    );
    atom(
        b"trak",
        concat(vec![
            atom(b"tkhd", header),
            atom(
                b"mdia",
                atom(
                    b"minf",
                    concat(vec![
                        atom(b"dinf", dref),
                        atom(b"stbl", concat(vec![stsd, stsc, stsz, co64])),
                    ]),
                ),
            ),
        ]),
    )
}

pub struct TempDir {
    pub path: PathBuf,
}

pub fn field_offset(bytes: &[u8], box_name: &[u8; 4], tag: u16) -> usize {
    let base = bytes.windows(4).position(|w| w == box_name).unwrap() + 4;
    let count = u16::from_le_bytes(bytes[base + 8..base + 10].try_into().unwrap()) as usize;
    for i in 0..count {
        let at = base + 10 + i * 12;
        let id = u16::from_le_bytes(bytes[at..at + 2].try_into().unwrap());
        if id == tag {
            let format = u16::from_le_bytes(bytes[at + 2..at + 4].try_into().unwrap());
            let n = u32::from_le_bytes(bytes[at + 4..at + 8].try_into().unwrap()) as usize;
            let width = match format {
                2 => 1,
                3 => 2,
                4 => 4,
                5 => 8,
                _ => panic!("fixture type"),
            };
            return if n * width <= 4 {
                at + 8
            } else {
                base + u32::from_le_bytes(bytes[at + 8..at + 12].try_into().unwrap()) as usize
            };
        }
    }
    panic!("fixture field not found")
}

pub fn big_endian_tiff_boxes(bytes: &mut [u8]) {
    for name in [b"CMT1", b"CMT2", b"CMT3", b"CMT4"] {
        let base = bytes.windows(4).position(|w| w == name).unwrap() + 4;
        let n = u16::from_le_bytes(bytes[base + 8..base + 10].try_into().unwrap()) as usize;
        let mut payloads = Vec::new();
        for i in 0..n {
            let at = base + 10 + i * 12;
            let format = u16::from_le_bytes(bytes[at + 2..at + 4].try_into().unwrap());
            let count = u32::from_le_bytes(bytes[at + 4..at + 8].try_into().unwrap()) as usize;
            let width = match format {
                2 => 1,
                3 => 2,
                4 => 4,
                5 => 8,
                _ => panic!("fixture type"),
            };
            let start = if count * width <= 4 {
                at + 8
            } else {
                base + u32::from_le_bytes(bytes[at + 8..at + 12].try_into().unwrap()) as usize
            };
            payloads.push((start, count, format, width));
        }
        bytes[base..base + 2].copy_from_slice(b"MM");
        bytes[base + 2..base + 4].reverse();
        bytes[base + 4..base + 8].reverse();
        bytes[base + 8..base + 10].reverse();
        for (i, (_, count, format, width)) in payloads.iter().enumerate() {
            let at = base + 10 + i * 12;
            bytes[at..at + 2].reverse();
            bytes[at + 2..at + 4].reverse();
            bytes[at + 4..at + 8].reverse();
            if count * width > 4 {
                bytes[at + 8..at + 12].reverse();
            } else if *format != 2 {
                for chunk in bytes[at + 8..at + 8 + count * width].chunks_exact_mut(*width) {
                    chunk.reverse();
                }
            }
        }
        for (start, count, format, width) in payloads {
            if count * width > 4 && format != 2 {
                let unit = if format == 5 { 4 } else { width };
                for chunk in bytes[start..start + count * width].chunks_exact_mut(unit) {
                    chunk.reverse();
                }
            }
        }
        bytes[base + 10 + n * 12..base + 14 + n * 12].reverse();
    }
}
impl TempDir {
    pub fn new() -> Self {
        static COUNTER: AtomicU64 = AtomicU64::new(0);
        let path = std::env::temp_dir().join(format!(
            "imageinfo-reader-{}-{}",
            std::process::id(),
            COUNTER.fetch_add(1, Ordering::Relaxed)
        ));
        fs::create_dir(&path).unwrap();
        Self { path }
    }
}
impl Drop for TempDir {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.path);
    }
}
