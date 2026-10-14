//! Ordinary checksummed marker evidence under OD-11; never repair authority.
use crate::inspection_record::{Info, MAX_RECORD};
use imageinfo_recovery_probe::{Envelope, digest};
use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct Record {
    pub purpose: String,
    pub phase: String,
    pub target: String,
    pub expected_absence: bool,
    pub observation_only: bool,
    pub committed: bool,
    pub namespace_acknowledged: bool,
    pub root: Info,
    pub source: Info,
    pub candidate: Info,
    pub sha256: String,
}
pub fn encode(record: &Record) -> Result<Vec<u8>, serde_json::Error> {
    let body = serde_json::to_string(record)?;
    serde_json::to_vec(&Envelope {
        sha256: digest(body.as_bytes()),
        body,
    })
}
pub fn decode(bytes: &[u8], phase: &str) -> Result<Record, &'static str> {
    if bytes.is_empty() || bytes.len() > MAX_RECORD as usize {
        return Err("RECORD_SIZE_INVALID");
    }
    let envelope: Envelope =
        serde_json::from_slice(bytes).map_err(|_| "RECORD_ENVELOPE_INVALID")?;
    if envelope.sha256 != digest(envelope.body.as_bytes()) {
        return Err("RECORD_CHECKSUM_INVALID");
    }
    let record: Record = serde_json::from_str(&envelope.body).map_err(|_| "RECORD_BODY_INVALID")?;
    if record.purpose != "imageinfo-od11-marker-v1"
        || record.phase != phase
        || !["prepared", "publication-intent", "recovery-required"].contains(&phase)
        || record.target != "output.marker"
        || !record.expected_absence
        || !record.observation_only
        || record.committed
        || record.namespace_acknowledged
    {
        return Err("RECORD_SCOPE_INVALID");
    }
    for info in [&record.root, &record.source, &record.candidate] {
        if !info.identity.split_once(':').is_some_and(|(a, b)| {
            [a, b].iter().all(|p| {
                !p.is_empty()
                    && p.len() <= 16
                    && p.bytes()
                        .all(|v| v.is_ascii_digit() || (b'a'..=b'f').contains(&v))
            })
        }) {
            return Err("RECORD_IDENTITY_INVALID");
        }
    }
    if record.source.size != 65536
        || record.candidate.size != 65536
        || record.source.links != 1
        || record.candidate.links != 1
        || record.root.attributes & 0x410 != 0x10
        || record.source.attributes & 0x410 != 0
        || record.candidate.attributes & 0x410 != 0
        || record.sha256.len() != 64
        || !record
            .sha256
            .bytes()
            .all(|v| v.is_ascii_digit() || (b'a'..=b'f').contains(&v))
    {
        return Err("RECORD_BINDING_INVALID");
    }
    Ok(record)
}

#[cfg(test)]
mod tests {
    use super::*;
    fn sample() -> Record {
        let file = Info {
            identity: "1:2".into(),
            size: 65536,
            links: 1,
            attributes: 32,
            creation_time: 1,
            last_write_time: 2,
        };
        let mut root = file.clone();
        root.attributes = 16;
        root.size = 0;
        Record {
            purpose: "imageinfo-od11-marker-v1".into(),
            phase: "prepared".into(),
            target: "output.marker".into(),
            expected_absence: true,
            observation_only: true,
            committed: false,
            namespace_acknowledged: false,
            root,
            source: file.clone(),
            candidate: file,
            sha256: digest(&[3; 65536]),
        }
    }
    #[test]
    fn records_are_fixed_scope_observations() {
        let r = decode(&encode(&sample()).unwrap(), "prepared").unwrap();
        assert!(r.observation_only && !r.committed && !r.namespace_acknowledged);
        assert!(decode(&encode(&sample()).unwrap(), "publication-intent").is_err());
    }
    #[test]
    fn arbitrary_paths_and_claimed_authority_refuse() {
        for field in [
            "target",
            "committed",
            "namespaceAcknowledged",
            "expectedAbsence",
            "extra",
        ] {
            let mut body = serde_json::to_value(sample()).unwrap();
            body[field] = if field == "expectedAbsence" {
                serde_json::json!(false)
            } else if field == "target" {
                serde_json::json!("../../source.cr3")
            } else {
                serde_json::json!(true)
            };
            let body = body.to_string();
            let wire = serde_json::to_vec(&Envelope {
                sha256: digest(body.as_bytes()),
                body,
            })
            .unwrap();
            assert!(decode(&wire, "prepared").is_err());
        }
    }
    #[test]
    fn checksum_duplicate_identity_and_size_errors_refuse() {
        let mut r = sample();
        r.source.identity = "not-an-id".into();
        assert!(decode(&encode(&r).unwrap(), "prepared").is_err());
        r = sample();
        r.candidate.links = 2;
        assert!(decode(&encode(&r).unwrap(), "prepared").is_err());
        let body = serde_json::to_string(&sample()).unwrap().replacen(
            '{',
            "{\"target\":\"output.marker\",",
            1,
        );
        let wire = serde_json::to_vec(&Envelope {
            sha256: digest(body.as_bytes()),
            body,
        })
        .unwrap();
        assert!(decode(&wire, "prepared").is_err());
        let mut wire = encode(&sample()).unwrap();
        wire[20] ^= 1;
        assert!(decode(&wire, "prepared").is_err());
        assert!(decode(&vec![0; MAX_RECORD as usize + 1], "prepared").is_err());
    }
}
