//! Bounded observational receipts. Checksums bind bytes, never caller authority.
use crate::{
    inspection_record::{Info, MAX_RECORD},
    restart_context::{self, Context, Stage},
};
use imageinfo_recovery_probe::{Envelope, digest};
use serde::{Deserialize, Serialize};

const PURPOSE: &str = "imageinfo-od11-receipt-v1";
const CONTEXT_PURPOSE: &str = "imageinfo-od11-receipt-context-v1";
const PROTOCOL: &str = "imageinfo-new-output-protocol-v1";
const PROFILE: &str = "unqualified-windows-marker-v1";

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct Receipt {
    pub purpose: String,
    pub protocol: String,
    pub profile: String,
    pub prior: Context,
}
impl Receipt {
    pub fn new(prior: Context) -> Result<Self, &'static str> {
        validate_prior(&prior)?;
        Ok(Self {
            purpose: PURPOSE.into(),
            protocol: PROTOCOL.into(),
            profile: PROFILE.into(),
            prior,
        })
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct OwnedReceipt {
    pub info: Info,
    pub sha256: String,
}

/// Retained outside the editable transaction by the trusted caller. The caller
/// must separately establish provenance and current history before using it.
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct ReceiptContext {
    pub purpose: String,
    pub prior: Context,
    pub receipt: OwnedReceipt,
}
impl ReceiptContext {
    pub fn new(prior: Context, info: Info, sha256: String) -> Result<Self, &'static str> {
        let context = Self {
            purpose: CONTEXT_PURPOSE.into(),
            prior,
            receipt: OwnedReceipt { info, sha256 },
        };
        validate_context(&context)?;
        Ok(context)
    }
}

fn bounded(bytes: &[u8]) -> Result<(), &'static str> {
    if bytes.is_empty() || bytes.len() > MAX_RECORD as usize {
        return Err("RECEIPT_SIZE_INVALID");
    }
    Ok(())
}
fn canonical_identity(identity: &str) -> bool {
    identity.split_once(':').is_some_and(|(a, b)| {
        [a, b].iter().all(|part| {
            u64::from_str_radix(part, 16).is_ok_and(|value| format!("{value:x}") == *part)
        })
    })
}
fn validate_prior(prior: &Context) -> Result<(), &'static str> {
    let bytes = serde_json::to_vec(prior).map_err(|_| "RECEIPT_PRIOR_INVALID")?;
    restart_context::decode(&bytes)?;
    if prior.stage != Stage::AfterPublication
        || prior.stopped_before_publication
        || prior.records.len() != 3
        || [&prior.root, &prior.source, &prior.candidate]
            .into_iter()
            .chain(prior.records.iter().map(|record| &record.info))
            .any(|info| !canonical_identity(&info.identity))
    {
        return Err("RECEIPT_PRIOR_INVALID");
    }
    Ok(())
}
fn validate_context(context: &ReceiptContext) -> Result<(), &'static str> {
    if context.purpose != CONTEXT_PURPOSE {
        return Err("RECEIPT_CONTEXT_SCOPE_INVALID");
    }
    validate_prior(&context.prior)?;
    let info = &context.receipt.info;
    if !canonical_identity(&info.identity)
        || info.size == 0
        || info.size > MAX_RECORD
        || info.links != 1
        || info.attributes & 0x410 != 0
        || context.receipt.sha256.len() != 64
        || !context
            .receipt
            .sha256
            .bytes()
            .all(|v| v.is_ascii_digit() || (b'a'..=b'f').contains(&v))
        || [
            &context.prior.root,
            &context.prior.source,
            &context.prior.candidate,
        ]
        .into_iter()
        .chain(context.prior.records.iter().map(|record| &record.info))
        .any(|prior| prior.identity == info.identity)
    {
        return Err("RECEIPT_CONTEXT_BINDING_INVALID");
    }
    Ok(())
}
pub fn encode(receipt: &Receipt) -> Result<Vec<u8>, serde_json::Error> {
    let body = serde_json::to_string(receipt)?;
    serde_json::to_vec(&Envelope {
        sha256: digest(body.as_bytes()),
        body,
    })
}
pub fn decode(bytes: &[u8]) -> Result<Receipt, &'static str> {
    bounded(bytes)?;
    let envelope: Envelope =
        serde_json::from_slice(bytes).map_err(|_| "RECEIPT_ENVELOPE_INVALID")?;
    if envelope.sha256 != digest(envelope.body.as_bytes()) {
        return Err("RECEIPT_CHECKSUM_INVALID");
    }
    let receipt: Receipt =
        serde_json::from_str(&envelope.body).map_err(|_| "RECEIPT_BODY_INVALID")?;
    if receipt.purpose != PURPOSE || receipt.protocol != PROTOCOL || receipt.profile != PROFILE {
        return Err("RECEIPT_SCOPE_INVALID");
    }
    validate_prior(&receipt.prior)?;
    Ok(receipt)
}
pub fn encode_context(context: &ReceiptContext) -> Result<Vec<u8>, serde_json::Error> {
    serde_json::to_vec(context)
}
pub fn decode_context(bytes: &[u8]) -> Result<ReceiptContext, &'static str> {
    bounded(bytes)?;
    let context: ReceiptContext =
        serde_json::from_slice(bytes).map_err(|_| "RECEIPT_CONTEXT_INVALID")?;
    validate_context(&context)?;
    Ok(context)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{
        ordinary_record::PersistenceMode,
        restart_context::{OwnedRecord, RecordName},
    };

    fn sample() -> Receipt {
        let file = |id: &str, size| Info {
            identity: id.into(),
            size,
            links: 1,
            attributes: 32,
            creation_time: 1,
            last_write_time: 2,
        };
        let mut root = file("1:1", 0);
        root.attributes = 16;
        Receipt::new(Context {
            purpose: "imageinfo-od11-caller-context-v1".into(),
            stage: Stage::AfterPublication,
            stopped_before_publication: false,
            root,
            source: file("1:2", 65536),
            candidate: file("1:3", 65536),
            sha256: "a".repeat(64),
            persistence_mode: PersistenceMode::WriteThrough,
            records: [
                RecordName::Prepared,
                RecordName::Intent,
                RecordName::Observation,
            ]
            .into_iter()
            .enumerate()
            .map(|(n, name)| OwnedRecord {
                name,
                info: file(&format!("1:{}", n + 4), 1024),
                sha256: "b".repeat(64),
            })
            .collect(),
        })
        .unwrap()
    }
    fn wire(body: String) -> Vec<u8> {
        serde_json::to_vec(&Envelope {
            sha256: digest(body.as_bytes()),
            body,
        })
        .unwrap()
    }
    fn context() -> ReceiptContext {
        let receipt = sample();
        let bytes = encode(&receipt).unwrap();
        let mut info = receipt.prior.records[0].info.clone();
        info.identity = "1:7".into();
        info.size = bytes.len() as u64;
        ReceiptContext::new(receipt.prior, info, digest(&bytes)).unwrap()
    }
    #[test]
    fn observational_receipt_and_external_binding_round_trip() {
        let receipt = sample();
        let parsed = decode(&encode(&receipt).unwrap()).unwrap();
        assert_eq!(parsed.profile, PROFILE);
        assert_eq!(parsed.prior.records.len(), 3);
        let context = context();
        let parsed = decode_context(&encode_context(&context).unwrap()).unwrap();
        assert_eq!(parsed.receipt.info.identity, "1:7");
        assert_eq!(parsed.receipt.sha256, context.receipt.sha256);
    }
    #[test]
    fn wrong_scope_paths_and_claimed_authority_refuse_even_with_valid_checksum() {
        for (key, value) in [
            ("purpose", serde_json::json!("another-purpose")),
            ("protocol", serde_json::json!("future-protocol")),
            ("profile", serde_json::json!("qualified")),
            ("path", serde_json::json!("../../source.cr3")),
            ("committed", serde_json::json!(true)),
            ("namespaceAcknowledged", serde_json::json!(true)),
            ("receiptFlushed", serde_json::json!(true)),
        ] {
            let mut body = serde_json::to_value(sample()).unwrap();
            body[key] = value;
            assert!(decode(&wire(body.to_string())).is_err(), "{key}");
        }
    }
    #[test]
    fn incomplete_conflicting_and_noncanonical_prior_bindings_refuse() {
        for change in 0..8 {
            let mut receipt = sample();
            match change {
                0 => receipt.prior.stage = Stage::BeforePublication,
                1 => receipt.prior.stopped_before_publication = true,
                2 => {
                    receipt.prior.records.pop();
                }
                3 => receipt.prior.records[2].name = RecordName::Prepared,
                4 => receipt.prior.records[1].info.identity = receipt.prior.source.identity.clone(),
                5 => receipt.prior.source.identity = "01:2".into(),
                6 => receipt.prior.sha256 = "A".repeat(64),
                _ => receipt.prior.records[0].info.links = 2,
            }
            assert!(
                decode(&encode(&receipt).unwrap()).is_err(),
                "change {change}"
            );
        }
    }
    #[test]
    fn duplicate_outer_body_and_nested_fields_and_damaged_checksums_refuse() {
        let body = serde_json::to_string(&sample()).unwrap();
        for body in [
            body.replacen('{', "{\"purpose\":\"imageinfo-od11-receipt-v1\",", 1),
            body.replacen(
                "\"identity\":\"1:1\"",
                "\"identity\":\"1:1\",\"identity\":\"1:1\"",
                1,
            ),
        ] {
            assert!(decode(&wire(body)).is_err());
        }
        let encoded = String::from_utf8(encode(&sample()).unwrap()).unwrap();
        assert!(decode(encoded.replacen('{', "{\"sha256\":\"bad\",", 1).as_bytes()).is_err());
        let mut envelope: Envelope = serde_json::from_str(&encoded).unwrap();
        envelope.body.push(' ');
        assert!(decode(&serde_json::to_vec(&envelope).unwrap()).is_err());
        assert!(decode(&[]).is_err());
        assert!(decode(&vec![b' '; MAX_RECORD as usize + 1]).is_err());
    }
    #[test]
    fn aliased_foreign_property_and_digest_context_bindings_refuse() {
        for change in 0..10 {
            let mut context = context();
            match change {
                0 => context.receipt.info.identity = context.prior.source.identity.clone(),
                1 => context.receipt.info.identity = context.prior.records[2].info.identity.clone(),
                2 => context.receipt.info.identity = "1:07".into(),
                3 => context.receipt.info.links = 2,
                4 => context.receipt.info.attributes |= 0x400,
                5 => context.receipt.info.attributes |= 0x10,
                6 => context.receipt.info.size = 0,
                7 => context.receipt.info.size = MAX_RECORD + 1,
                8 => context.receipt.sha256 = "0".repeat(63),
                _ => context.receipt.sha256 = "g".repeat(64),
            }
            assert!(
                decode_context(&encode_context(&context).unwrap()).is_err(),
                "change {change}"
            );
        }
    }
    #[test]
    fn context_accepts_no_extra_authority_or_duplicate_nested_fields() {
        let context = context();
        let mut value = serde_json::to_value(&context).unwrap();
        value["committed"] = serde_json::json!(true);
        assert!(decode_context(&serde_json::to_vec(&value).unwrap()).is_err());
        let bytes = String::from_utf8(encode_context(&context).unwrap()).unwrap();
        let duplicate = bytes.replacen(
            "\"identity\":\"1:7\"",
            "\"identity\":\"1:7\",\"identity\":\"1:7\"",
            1,
        );
        assert!(decode_context(duplicate.as_bytes()).is_err());
        assert!(decode_context(&[]).is_err());
        assert!(decode_context(&vec![0; MAX_RECORD as usize + 1]).is_err());
    }
}
