//! #0104: native-reader original-date observations to #0084 in-memory candidate.
//! No caller-supplied coverage/Metadata, file I/O, apply or publication API.
use imageinfo::reader::{self, Part, Range, Value};
use imageinfo_xmp_date_mapping_research::{ConflictPolicy, Occurrence, OriginalSnapshot};
use imageinfo_xmp_preservation_research::Prepared;
use std::io::Cursor;

pub const MAX_RAW_BYTES: usize = 256 * 1024 * 1024;

#[derive(Debug)]
pub struct SourceOccurrence {
    pub native_id: u16,
    pub range: Range,
    pub path: Vec<Part>,
    pub text: String,
}

#[derive(Debug)]
pub struct Candidate<'a> {
    pub prepared: Prepared<'a>,
    pub source: Vec<SourceOccurrence>,
    pub raw_length: u64,
    pub reader_revision: &'static str,
    pub publication_allowed: bool,
    pub raw_mutation_allowed: bool,
    pub storage_profile_admitted: bool,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Refusal {
    RawTooLarge,
    Raw { code: &'static str },
    IncompleteCmt2Coverage,
    SourcePath,
    SourceValue,
    Sidecar(imageinfo_xmp_preservation_research::Refusal),
}

fn cmt2(path: &[Part]) -> bool {
    path.iter()
        .any(|part| part.kind == "box" && part.name == "CMT2")
}

fn same_parent(a: &[Part], b: &[Part]) -> bool {
    let parent = |path: &[Part]| path.len().checked_sub(1);
    let (Some(a_end), Some(b_end)) = (parent(a), parent(b)) else {
        return false;
    };
    a.last().is_some_and(|part| part.kind == "tag")
        && b.last().is_some_and(|part| part.kind == "tag")
        && a_end == b_end
        && a[..a_end]
            .iter()
            .zip(&b[..b_end])
            .all(|(a, b)| a.kind == b.kind && a.name == b.name && a.index == b.index)
}

/// Each invocation parses actual immutable RAW bytes. Unsupported/opaque CMT2
/// entries refuse before the internal #0083 coverage attestation is constructed.
/// A caller must bound allocation before obtaining these already allocated slices.
pub fn prepare<'a>(
    raw: &'a [u8],
    sidecar: &'a [u8],
    target_ordinal: usize,
    policy: ConflictPolicy<'_>,
) -> Result<Candidate<'a>, Refusal> {
    if raw.len() > MAX_RAW_BYTES {
        return Err(Refusal::RawTooLarge);
    }
    let metadata = reader::read(Cursor::new(raw), reader::Limits::default())
        .map_err(|error| Refusal::Raw { code: error.code })?;
    // Reader success alone is partial coverage. An unrecognized CMT2 entry can
    // be an opaque pointer hiding another IFD; absent companions are defensible
    // here only for the wholly decoded CMT2 subset. Even recognized TIFF pointer
    // entries currently become opaque in the public reader, so they refuse too.
    if metadata.opaque.iter().any(|(_, path)| cmt2(path)) {
        return Err(Refusal::IncompleteCmt2Coverage);
    }
    let mut source = Vec::new();
    for occurrence in metadata.occurrences {
        if occurrence.namespace != "exif" || !cmt2(&occurrence.path) {
            continue;
        }
        let native_id = occurrence
            .native_id
            .parse::<u16>()
            .map_err(|_| Refusal::SourceValue)?;
        if ![0x9003, 0x9011, 0x9291].contains(&native_id) {
            continue;
        }
        let Value::Text(text) = occurrence.value else {
            return Err(Refusal::SourceValue);
        };
        if occurrence.encoding != "ASCII" {
            return Err(Refusal::SourceValue);
        }
        source.push(SourceOccurrence {
            native_id,
            range: occurrence.range,
            path: occurrence.path,
            text,
        });
    }
    if source
        .iter()
        .any(|item| !same_parent(&source[0].path, &item.path))
    {
        return Err(Refusal::SourcePath);
    }
    // IDs are local to this invocation's immutable original observation. They are
    // not hashes, stable cross-snapshot IDs, authority or saved apply bindings.
    let ids: Vec<_> = source
        .iter()
        .enumerate()
        .map(|(index, item)| {
            format!(
                "cmt2-{}-{}-{}-{index}",
                item.native_id, item.range.offset, item.range.length
            )
        })
        .collect();
    let select = |tag| {
        source
            .iter()
            .zip(&ids)
            .filter_map(|(item, id)| {
                (item.native_id == tag).then_some(Occurrence {
                    id,
                    text: &item.text,
                })
            })
            .collect::<Vec<_>>()
    };
    let original = select(0x9003);
    let subseconds = select(0x9291);
    let offset = select(0x9011);
    let observation = OriginalSnapshot {
        id: "immutable-original-invocation",
        raw_document: "selected-native-raw",
        sidecar_document: "selected-existing-xmp",
        complete_selected_tag_coverage: true,
        original: &original,
        subseconds: &subseconds,
        offset: &offset,
    };
    let prepared =
        imageinfo_xmp_preservation_research::prepare(sidecar, &observation, target_ordinal, policy)
            .map_err(Refusal::Sidecar)?;
    Ok(Candidate {
        prepared,
        source,
        raw_length: metadata.length,
        reader_revision: reader::READER_REVISION,
        publication_allowed: false,
        raw_mutation_allowed: false,
        storage_profile_admitted: false,
    })
}
