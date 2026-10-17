//! Public authored byte-budget fixture and independently enumerated request oracle.
#![allow(dead_code)]
use super::byte_boundaries::Request;
use imageinfo::reader::{self, Limits};
use sha2::{Digest, Sha256};
use std::time::Instant;
const M: usize = 8_388_608;
const B: usize = 1_048_576;
#[derive(Clone)]
struct Node {
    kind: [u8; 4],
    start: usize,
    payload: usize,
    end: usize,
}
fn u32be(b: &[u8], at: usize) -> usize {
    u32::from_be_bytes(b[at..at + 4].try_into().unwrap()) as usize
}
fn tree(b: &[u8], start: usize, end: usize, nodes: &mut Vec<Node>) {
    let mut at = start;
    while at < end {
        let size = u32be(b, at);
        assert!(size >= 8 && at + size <= end);
        let kind: [u8; 4] = b[at + 4..at + 8].try_into().unwrap();
        let n = Node {
            kind,
            start: at,
            payload: at + 8,
            end: at + size,
        };
        nodes.push(n.clone());
        if matches!(
            &kind,
            b"moov" | b"trak" | b"mdia" | b"minf" | b"stbl" | b"dinf"
        ) {
            tree(b, n.payload, n.end, nodes);
        } else if &kind == b"uuid" {
            let skip = if b[n.payload] == 0x85 { 16 } else { 24 };
            tree(b, n.payload + skip, n.end, nodes);
        }
        at += size;
    }
    assert_eq!(at, end);
}
fn nodes(b: &[u8]) -> Vec<Node> {
    let mut n = Vec::new();
    tree(b, 0, b.len(), &mut n);
    n
}
fn grow(b: &[u8], wanted: &[usize; 8]) -> Vec<u8> {
    let all = nodes(b);
    let selected: Vec<_> = all
        .iter()
        .filter(|n| matches!(&n.kind, b"CMT1" | b"CMT2" | b"CMT3" | b"CMT4" | b"stsd"))
        .collect();
    assert_eq!(selected.len(), 8);
    let mut inserts = Vec::new();
    for (n, &length) in selected.iter().zip(wanted) {
        let extra = length - (n.end - n.payload);
        let mut padding = vec![0; extra];
        if &n.kind == b"stsd" && &b[n.payload + 12..n.payload + 16] == b"CRAW" {
            assert!(extra >= 8);
            padding[..4].copy_from_slice(&(extra as u32).to_be_bytes());
            padding[4..8].copy_from_slice(b"free");
        }
        inserts.push((n.end, padding));
    }
    let shift = |at: usize| {
        inserts
            .iter()
            .filter(|(p, _)| *p <= at)
            .map(|(_, v)| v.len())
            .sum::<usize>()
    };
    let mut out = Vec::new();
    let mut prior = 0;
    for (at, padding) in &inserts {
        out.extend_from_slice(&b[prior..*at]);
        out.extend(padding);
        prior = *at;
    }
    out.extend_from_slice(&b[prior..]);
    for n in &all {
        // An insertion at a node's end belongs to that node only when it is
        // the selected payload or an ancestor, never its preceding sibling.
        let delta: usize = inserts
            .iter()
            .filter(|(p, _)| *p > n.start && *p <= n.end)
            .map(|(_, v)| v.len())
            .sum();
        let at = n.start + shift(n.start);
        out[at..at + 4].copy_from_slice(&((n.end - n.start + delta) as u32).to_be_bytes());
        if &n.kind == b"stsd" {
            let payload = n.payload + shift(n.payload);
            let length = n.end - n.payload + delta;
            out[payload + 8..payload + 12].copy_from_slice(&((length - 8) as u32).to_be_bytes());
        }
        if &n.kind == b"co64" {
            let payload = n.payload + shift(n.payload);
            let old =
                u64::from_be_bytes(b[n.payload + 8..n.payload + 16].try_into().unwrap()) as usize;
            out[payload + 8..payload + 16]
                .copy_from_slice(&((old + shift(old)) as u64).to_be_bytes());
        }
    }
    out
}
fn req(out: &mut Vec<Request>, offset: usize, length: usize) {
    out.push(Request {
        offset: offset as u64,
        requested: length,
        returned: length,
    });
}
/// This enumerator uses the authored container's byte layout, never reader output.
pub fn oracle(b: &[u8]) -> Vec<Request> {
    let all = nodes(b);
    let mut out = Vec::new();
    for n in &all {
        req(&mut out, n.start, 8);
        if &n.kind == b"uuid" {
            req(&mut out, n.payload, 16);
            if b[n.payload] != 0x85 {
                req(&mut out, n.payload + 16, 8);
            }
        }
    }
    let one = |kind: &[u8; 4]| all.iter().find(|n| &n.kind == kind).unwrap();
    req(&mut out, one(b"ftyp").payload, 4);
    for kind in [b"CMT1", b"CMT2", b"CMT3", b"CMT4"] {
        let n = one(kind);
        req(&mut out, n.payload, n.end - n.payload);
    }
    for kind in [b"THMB", b"PRVW"] {
        let n = one(kind);
        req(&mut out, n.payload, 16);
        req(&mut out, n.payload + 16, 2);
        let d = u32be(b, n.payload + if kind == b"THMB" { 8 } else { 12 });
        req(&mut out, n.payload + 16 + d, n.end - n.payload - 16 - d);
    }
    let n = one(b"CCTP");
    req(&mut out, n.payload, n.end - n.payload);
    for n in &all {
        match &n.kind {
            b"tkhd" => req(&mut out, n.payload, 24),
            b"dref" | b"stsd" | b"stsc" | b"stsz" | b"co64" => {
                req(&mut out, n.payload, n.end - n.payload)
            }
            _ => {}
        }
    }
    let mdat = one(b"mdat");
    req(&mut out, mdat.payload, 2);
    req(&mut out, mdat.payload + 15, 12);
    req(&mut out, mdat.payload + 27, 12);
    out
}
pub fn fixture(axis: &str, delta: i32) -> Vec<u8> {
    let original = super::support::fixture().bytes;
    let n = nodes(&original);
    let mut lengths = [0; 8];
    for (slot, node) in lengths.iter_mut().zip(
        n.iter()
            .filter(|n| matches!(&n.kind, b"CMT1" | b"CMT2" | b"CMT3" | b"CMT4" | b"stsd")),
    ) {
        *slot = node.end - node.payload;
    }
    // All eight native whole-payload reads can grow independently; the rest
    // of the request oracle is invariant under these payload insertions.
    let old_total: usize = oracle(&original).iter().map(|r| r.requested).sum();
    if axis == "metadata" {
        let fixed = old_total - lengths.iter().sum::<usize>();
        lengths.fill(B);
        lengths[7] = (M as i64 + delta as i64 - fixed as i64 - 7 * B as i64) as usize;
    } else {
        assert_eq!(axis, "block");
        lengths[0] = (B as i64 + delta as i64) as usize;
        for v in &mut lengths[4..] {
            *v += 8;
        }
    }
    grow(&original, &lengths)
}
pub fn execute(axis: &str, delta: i32) -> serde_json::Value {
    let bytes = fixture(axis, delta);
    let before = Sha256::digest(&bytes);
    let expected = oracle(&bytes);
    let total: usize = expected.iter().map(|r| r.requested).sum();
    let largest = expected.iter().map(|r| r.requested).max().unwrap();
    let mut prefix = Vec::new();
    let mut consumed = 0;
    for r in &expected {
        if consumed + r.requested > M || r.requested > B {
            break;
        }
        consumed += r.requested;
        prefix.push(r.clone());
    }
    let (source, trace) = super::byte_boundaries::RecordingSource::new(&bytes);
    let started = Instant::now();
    let result = reader::read(source, Limits::default());
    let elapsed = started.elapsed().as_nanos();
    assert_eq!(trace.borrow().len(), prefix.len(), "request count");
    for (i, (actual, want)) in trace.borrow().iter().zip(&prefix).enumerate() {
        assert_eq!(actual, want, "request {i}");
    }
    assert_eq!(Sha256::digest(&bytes), before);
    let expected_success = delta <= 0;
    let (code, reported) = match result {
        Ok(m) => {
            assert!(expected_success);
            assert_eq!(m.bytes_read, consumed as u64);
            assert_eq!(m.previews.len(), 3);
            ("OK", Some(m.bytes_read))
        }
        Err(e) => {
            assert!(!expected_success);
            assert_eq!(e.code, "LIMIT_EXCEEDED");
            assert_eq!(e.message, "Metadata byte budget exceeded");
            (e.code, None)
        }
    };
    assert_eq!(
        total,
        if axis == "metadata" {
            (M as i64 + delta as i64) as usize
        } else {
            total
        }
    );
    if axis == "block" {
        assert_eq!(largest, (B as i64 + delta as i64) as usize);
    }
    serde_json::json!({"axis":axis,"delta":delta,"status":code,"complete":expected_success,"sourceBytes":bytes.len(),"sourceSha256":format!("{before:x}"),"sourceUnchanged":true,"plannedRequestedBytes":total,"largestRequestBytes":largest,"underlyingRequestedBytes":consumed,"reportedChargedBytes":reported,"readElapsedNs":elapsed,"requests":*trace.borrow(),"plannedRequests":expected})
}
