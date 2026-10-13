//! Ordinary, platform-independent parsing of the existing #0032 record wire form.
use imageinfo_recovery_probe::{Envelope, digest};
use serde::Deserialize;
pub const MAX_RECORD: u64 = 65536;
#[derive(Clone, Debug, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct Info {
    pub identity: String,
    pub size: u64,
    pub links: u32,
    pub attributes: u32,
    pub creation_time: u64,
    pub last_write_time: u64,
}
#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct Body {
    pub purpose: String,
    pub phase: String,
    pub observation_only: bool,
    pub committed: bool,
    pub namespace_acknowledged: bool,
    pub expected_absence: bool,
    pub target: String,
    pub root: Info,
    pub candidate: Info,
    pub candidate_sha256: String,
}
fn identity_valid(value: &str) -> bool {
    value.split_once(':').is_some_and(|(a, b)| {
        [a, b].iter().all(|v| {
            !v.is_empty()
                && v.len() <= 16
                && v.bytes()
                    .all(|c| c.is_ascii_digit() || (b'a'..=b'f').contains(&c))
        })
    })
}
pub fn decode(bytes: &[u8], phase: &str) -> Result<Body, &'static str> {
    if bytes.is_empty() || bytes.len() > MAX_RECORD as usize {
        return Err("RECORD_SIZE_INVALID");
    }
    let envelope: Envelope =
        serde_json::from_slice(bytes).map_err(|_| "RECORD_ENVELOPE_INVALID")?;
    if envelope.sha256 != digest(envelope.body.as_bytes()) {
        return Err("RECORD_CHECKSUM_INVALID");
    }
    let body: Body = serde_json::from_str(&envelope.body).map_err(|_| "RECORD_BODY_INVALID")?;
    if body.purpose != "imageinfo-bound-windows-research-v1"
        || body.phase != phase
        || !body.observation_only
        || body.committed
        || body.namespace_acknowledged
        || !body.expected_absence
        || body.target != "output.bin"
    {
        return Err("RECORD_SCOPE_INVALID");
    }
    if !identity_valid(&body.root.identity)
        || !identity_valid(&body.candidate.identity)
        || body.candidate.size != 65536
        || body.candidate.links != 1
        || body.candidate_sha256.len() != 64
        || !body
            .candidate_sha256
            .bytes()
            .all(|c| c.is_ascii_digit() || (b'a'..=b'f').contains(&c))
    {
        return Err("RECORD_BINDING_INVALID");
    }
    Ok(body)
}
pub fn classify(
    has_records: bool,
    has_intent: bool,
    candidate: Option<bool>,
    output: Option<bool>,
) -> &'static str {
    if !has_records {
        "unattributed-artifacts"
    } else if candidate.is_some() && output.is_some() {
        "candidate-and-output-conflict"
    } else if candidate == Some(false) {
        "candidate-conflict"
    } else if output == Some(false) {
        "output-conflict"
    } else if output.is_some() && !has_intent {
        "output-without-intent"
    } else if output.is_some() {
        "matching-output-recovery-required"
    } else if candidate.is_some() {
        "candidate-retained-output-absent"
    } else {
        "candidate-missing-output-absent"
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::{Value, json};
    fn body() -> Value {
        let info = json!({"identity":"1:2","size":65536,"links":1,"attributes":32,"creationTime":1,"lastWriteTime":2});
        let mut root = info.clone();
        root["size"] = json!(0);
        root["attributes"] = json!(16);
        json!({"purpose":"imageinfo-bound-windows-research-v1","phase":"prepared","observationOnly":true,"committed":false,"namespaceAcknowledged":false,"expectedAbsence":true,"target":"output.bin","root":root,"candidate":info,"candidateSha256":"a".repeat(64)})
    }
    fn envelope(text: String) -> Vec<u8> {
        serde_json::to_vec(&json!({"sha256":digest(text.as_bytes()),"body":text})).unwrap()
    }
    #[test]
    fn exact_record_is_observation_not_commit_permission() {
        let record = decode(&envelope(body().to_string()), "prepared").unwrap();
        assert!(!record.committed && !record.namespace_acknowledged && record.observation_only);
        assert_eq!(record.target, "output.bin");
        assert!(decode(&envelope(body().to_string()), "publication-intent").is_err());
    }
    #[test]
    fn untrusted_paths_permission_flags_and_unknown_fields_refuse() {
        for (key, value) in [
            ("target", json!("../../original.cr3")),
            ("committed", json!(true)),
            ("namespaceAcknowledged", json!(true)),
            ("extra", json!("authority")),
        ] {
            let mut value_body = body();
            value_body[key] = value;
            assert!(decode(&envelope(value_body.to_string()), "prepared").is_err());
        }
        let mut value = body();
        value["candidate"]["links"] = json!(2);
        assert!(decode(&envelope(value.to_string()), "prepared").is_err());
    }
    #[test]
    fn duplicate_members_and_checksums_refuse() {
        let text = body()
            .to_string()
            .replacen('{', "{\"target\":\"output.bin\",", 1);
        assert_eq!(
            decode(&envelope(text), "prepared").unwrap_err(),
            "RECORD_BODY_INVALID"
        );
        let mut envelope_value: Value =
            serde_json::from_slice(&envelope(body().to_string())).unwrap();
        envelope_value["sha256"] = json!("0".repeat(64));
        assert_eq!(
            decode(&serde_json::to_vec(&envelope_value).unwrap(), "prepared").unwrap_err(),
            "RECORD_CHECKSUM_INVALID"
        );
    }
    #[test]
    fn bounded_malformed_records_do_not_panic() {
        let input = envelope(body().to_string());
        for i in 0..1024 {
            let mut changed = input.clone();
            let n = i % changed.len();
            changed[n] ^= (i as u8).wrapping_add(1);
            let _ = decode(&changed, "prepared");
        }
        assert_eq!(
            decode(&vec![b' '; MAX_RECORD as usize + 1], "prepared").unwrap_err(),
            "RECORD_SIZE_INVALID"
        );
    }
    #[test]
    fn state_classification_requires_actual_presence_and_matching_bindings() {
        for (records, intent, candidate, output, expected) in [
            (false, false, None, None, "unattributed-artifacts"),
            (
                true,
                false,
                Some(true),
                None,
                "candidate-retained-output-absent",
            ),
            (
                true,
                true,
                None,
                Some(true),
                "matching-output-recovery-required",
            ),
            (true, true, None, Some(false), "output-conflict"),
            (true, true, Some(false), None, "candidate-conflict"),
            (true, true, None, None, "candidate-missing-output-absent"),
            (
                true,
                true,
                Some(true),
                Some(false),
                "candidate-and-output-conflict",
            ),
            (true, false, None, Some(true), "output-without-intent"),
        ] {
            assert_eq!(classify(records, intent, candidate, output), expected);
        }
    }
}
