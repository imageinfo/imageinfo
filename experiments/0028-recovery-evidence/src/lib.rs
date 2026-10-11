//! Experimental evidence decoding; hashes establish integrity, never authority.
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

pub const MAX_RECORD: usize = 65536;
pub const MAX_ARTIFACT: u64 = 256 * 1024 * 1024;

#[cfg(target_os = "linux")]
pub mod linux;

#[derive(Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Receipt {
    pub schema_version: u32,
    pub root_identity: String,
    pub candidate_identity: String,
    pub candidate_sha256: String,
    pub observation_only: bool,
}

pub fn receipt_bytes(receipt: &Receipt) -> Result<Vec<u8>, serde_json::Error> {
    let body = serde_json::to_string(receipt)?;
    serde_json::to_vec(&Envelope {
        sha256: digest(body.as_bytes()),
        body,
    })
}

pub fn decode_receipt(bytes: &[u8], record: &Record) -> bool {
    if bytes.len() > MAX_RECORD {
        return false;
    }
    let Ok(envelope) = serde_json::from_slice::<Envelope>(bytes) else {
        return false;
    };
    if envelope.sha256 != digest(envelope.body.as_bytes()) {
        return false;
    }
    let Ok(receipt) = serde_json::from_str::<Receipt>(&envelope.body) else {
        return false;
    };
    receipt.schema_version == 1
        && receipt.root_identity == record.root_identity
        && receipt.candidate_identity == record.candidate.identity
        && receipt.candidate_sha256 == record.candidate.sha256
        && receipt.observation_only
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Envelope {
    pub body: String,
    pub sha256: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Artifact {
    pub name: String,
    pub identity: String,
    pub size: u64,
    pub sha256: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Record {
    pub schema_version: u32,
    pub purpose: String,
    pub root_identity: String,
    pub source: Artifact,
    pub candidate: Artifact,
    pub destination: String,
    pub expected_destination: String,
    pub phase: String,
}

pub fn digest(bytes: &[u8]) -> String {
    hex(&Sha256::digest(bytes))
}

pub fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

pub fn encode(record: &Record) -> Result<Vec<u8>, serde_json::Error> {
    let body = serde_json::to_string(record)?;
    serde_json::to_vec(&Envelope {
        sha256: digest(body.as_bytes()),
        body,
    })
}

pub fn decode(bytes: &[u8]) -> Result<Record, &'static str> {
    if bytes.len() > MAX_RECORD {
        return Err("RECORD_TOO_LARGE");
    }
    let envelope: Envelope = serde_json::from_slice(bytes).map_err(|_| "RECORD_INVALID")?;
    if envelope.sha256 != digest(envelope.body.as_bytes()) {
        return Err("RECORD_CHECKSUM_INVALID");
    }
    let record: Record = serde_json::from_str(&envelope.body).map_err(|_| "RECORD_INVALID")?;
    if record.schema_version != 1
        || record.purpose != "imageinfo-storage-research-v1"
        || record.source.name != "frozen-input.cr3"
        || record.candidate.name != "candidate.cr3"
        || record.destination != "output.cr3"
        || record.expected_destination != "absent"
        || !matches!(record.phase.as_str(), "prepared" | "publication-intent")
    {
        return Err("RECORD_SCOPE_INVALID");
    }
    if !identity_valid(&record.root_identity)
        || [&record.source, &record.candidate].iter().any(|a| {
            a.size > MAX_ARTIFACT || !identity_valid(&a.identity) || !hash_valid(&a.sha256)
        })
    {
        return Err("RECORD_ARTIFACT_INVALID");
    }
    Ok(record)
}

fn hash_valid(value: &str) -> bool {
    value.len() == 64
        && value
            .bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
}
fn identity_valid(value: &str) -> bool {
    value.len() <= 40
        && value.split_once(':').is_some_and(|(a, b)| {
            !a.is_empty()
                && !b.is_empty()
                && a.bytes().chain(b.bytes()).all(|c| c.is_ascii_hexdigit())
        })
}

#[cfg(test)]
mod tests {
    use super::*;
    fn example() -> Record {
        Record {
            schema_version: 1,
            purpose: "imageinfo-storage-research-v1".into(),
            root_identity: "12:34".into(),
            source: Artifact {
                name: "frozen-input.cr3".into(),
                identity: "12:35".into(),
                size: 3,
                sha256: digest(b"abc"),
            },
            candidate: Artifact {
                name: "candidate.cr3".into(),
                identity: "12:36".into(),
                size: 3,
                sha256: digest(b"abc"),
            },
            destination: "output.cr3".into(),
            expected_destination: "absent".into(),
            phase: "prepared".into(),
        }
    }
    #[test]
    fn bounded_strict_records_and_hash_vector() {
        assert_eq!(
            digest(b"abc"),
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        );
        let bytes = encode(&example()).unwrap();
        assert!(decode(&bytes).is_ok());
        assert_eq!(
            decode(&vec![b' '; MAX_RECORD + 1]).unwrap_err(),
            "RECORD_TOO_LARGE"
        );
        for bytes in [
            b"{}".as_slice(),
            b"null",
            b"{\"body\":\"x\",\"body\":\"y\",\"sha256\":\"x\"}",
        ] {
            assert!(decode(bytes).is_err());
        }
        let mut envelope: Envelope = serde_json::from_slice(&bytes).unwrap();
        envelope.body.push(' ');
        assert_eq!(
            decode(&serde_json::to_vec(&envelope).unwrap()).unwrap_err(),
            "RECORD_CHECKSUM_INVALID"
        );
    }
    #[test]
    fn recomputed_checksum_cannot_expand_scope() {
        for name in [
            "../foreign",
            "/absolute",
            "C:\\foreign",
            "candidate.cr3/leaf",
            "candidate.cr3:stream",
            "other.cr3",
        ] {
            let mut record = example();
            record.destination = name.into();
            assert!(decode(&encode(&record).unwrap()).is_err());
        }
        let mut record = example();
        record.phase = "committed".into();
        assert!(decode(&encode(&record).unwrap()).is_err());
        let mut record = example();
        record.candidate.size = MAX_ARTIFACT + 1;
        assert!(decode(&encode(&record).unwrap()).is_err());
        let mut record = example();
        record.candidate.identity = "".into();
        assert!(decode(&encode(&record).unwrap()).is_err());
    }
}
