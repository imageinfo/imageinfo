//! Explicit caller-held marker context, separate from editable transaction records.
use crate::{
    inspection_record::{Info, MAX_RECORD},
    ordinary_record::{PersistenceMode, validate_bindings},
};
use serde::{Deserialize, Serialize};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Stage {
    BeforePublication,
    AfterPublication,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum RecordName {
    Prepared,
    Intent,
    Observation,
}
#[cfg(windows)]
impl RecordName {
    pub fn leaf(self) -> &'static str {
        match self {
            Self::Prepared => "prepared.record",
            Self::Intent => "intent.record",
            Self::Observation => "observation.record",
        }
    }
    pub fn phase(self) -> &'static str {
        match self {
            Self::Prepared => "prepared",
            Self::Intent => "publication-intent",
            Self::Observation => "recovery-required",
        }
    }
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct OwnedRecord {
    pub name: RecordName,
    pub info: Info,
    pub sha256: String,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct Context {
    pub purpose: String,
    pub stage: Stage,
    // Exported false while the live worker can still continue. Only the trusted
    // supervisor may confirm that it stopped before releasing publication.
    #[serde(default)]
    pub stopped_before_publication: bool,
    pub root: Info,
    pub source: Info,
    pub candidate: Info,
    pub sha256: String,
    pub persistence_mode: PersistenceMode,
    pub records: Vec<OwnedRecord>,
}
pub fn decode(bytes: &[u8]) -> Result<Context, &'static str> {
    if bytes.is_empty() || bytes.len() > MAX_RECORD as usize {
        return Err("CALLER_CONTEXT_SIZE_INVALID");
    }
    let context: Context = serde_json::from_slice(bytes).map_err(|_| "CALLER_CONTEXT_INVALID")?;
    if context.purpose != "imageinfo-od11-caller-context-v1" {
        return Err("CALLER_CONTEXT_SCOPE_INVALID");
    }
    if context.stage == Stage::AfterPublication && context.stopped_before_publication {
        return Err("CALLER_CONTEXT_HISTORY_INVALID");
    }
    validate_bindings(
        &context.root,
        &context.source,
        &context.candidate,
        &context.sha256,
    )?;
    let expected = [
        RecordName::Prepared,
        RecordName::Intent,
        RecordName::Observation,
    ];
    if !(2..=3).contains(&context.records.len())
        || context.stage == Stage::BeforePublication && context.records.len() != 2
    {
        return Err("CALLER_CONTEXT_RECORD_SET_INVALID");
    }
    for (r, name) in context.records.iter().zip(expected) {
        // Reuse the existing bounded identity/regular-file checks for records,
        // whose actual variable size is separately constrained below.
        let mut shape = r.info.clone();
        shape.size = 65536;
        validate_bindings(&context.root, &shape, &context.candidate, &r.sha256)?;
        if r.name != name
            || r.info.size == 0
            || r.info.size > MAX_RECORD
            || [&context.root, &context.source, &context.candidate]
                .iter()
                .any(|i| i.identity == r.info.identity)
        {
            return Err("CALLER_CONTEXT_RECORD_BINDING_INVALID");
        }
    }
    if context.source.identity == context.candidate.identity
        || context.root.identity == context.source.identity
        || context.root.identity == context.candidate.identity
    {
        return Err("CALLER_CONTEXT_IDENTITIES_ALIAS");
    }
    for (n, r) in context.records.iter().enumerate() {
        if context.records[..n]
            .iter()
            .any(|old| old.info.identity == r.info.identity)
        {
            return Err("CALLER_CONTEXT_IDENTITIES_ALIAS");
        }
    }
    Ok(context)
}

#[cfg(test)]
mod tests {
    use super::*;
    fn sample() -> Context {
        let file = Info {
            identity: "1:2".into(),
            size: 65536,
            links: 1,
            attributes: 32,
            creation_time: 1,
            last_write_time: 2,
        };
        let mut root = file.clone();
        root.identity = "1:1".into();
        root.attributes = 16;
        root.size = 0;
        let mut candidate = file.clone();
        candidate.identity = "1:3".into();
        let records = [RecordName::Prepared, RecordName::Intent]
            .into_iter()
            .enumerate()
            .map(|(n, name)| {
                let mut info = file.clone();
                info.identity = format!("1:{}", n + 4);
                info.size = 1024;
                OwnedRecord {
                    name,
                    info,
                    sha256: "a".repeat(64),
                }
            })
            .collect();
        Context {
            purpose: "imageinfo-od11-caller-context-v1".into(),
            stage: Stage::BeforePublication,
            stopped_before_publication: false,
            root,
            source: file,
            candidate,
            sha256: "a".repeat(64),
            persistence_mode: PersistenceMode::Buffered,
            records,
        }
    }
    #[test]
    fn context_is_explicit_fixed_scope_and_not_a_transaction_record() {
        let c = sample();
        let bytes = serde_json::to_vec(&c).unwrap();
        assert_eq!(decode(&bytes).unwrap().stage, Stage::BeforePublication);
        for (key, value) in [
            ("path", serde_json::json!("../../source.cr3")),
            ("committed", serde_json::json!(true)),
            ("stage", serde_json::json!("any-operation")),
        ] {
            let mut v = serde_json::to_value(&c).unwrap();
            v[key] = value;
            assert!(decode(&serde_json::to_vec(&v).unwrap()).is_err());
        }
    }
    #[test]
    fn size_duplicate_fields_and_unknown_record_names_refuse() {
        assert!(decode(&[]).is_err());
        assert!(decode(&vec![0; MAX_RECORD as usize + 1]).is_err());
        let bytes = serde_json::to_string(&sample()).unwrap().replacen(
            '{',
            "{\"stage\":\"after-publication\",",
            1,
        );
        assert!(decode(bytes.as_bytes()).is_err());
        let mut c = sample();
        c.records[0].name = RecordName::Observation;
        assert!(decode(&serde_json::to_vec(&c).unwrap()).is_err());
    }
    #[test]
    fn aliased_missing_oversized_and_property_changed_bindings_refuse() {
        for n in 0..5 {
            let mut c = sample();
            match n {
                0 => c.candidate.identity = c.source.identity.clone(),
                1 => c.records.clear(),
                2 => c.records[0].info.size = MAX_RECORD + 1,
                3 => c.records[0].info.links = 2,
                _ => c.records[1].info.identity = c.records[0].info.identity.clone(),
            };
            assert!(decode(&serde_json::to_vec(&c).unwrap()).is_err());
        }
    }
    #[test]
    fn observation_context_is_allowed_only_after_publication() {
        let mut c = sample();
        let mut r = c.records[0].clone();
        r.name = RecordName::Observation;
        r.info.identity = "1:6".into();
        c.records.push(r);
        assert!(decode(&serde_json::to_vec(&c).unwrap()).is_err());
        c.stage = Stage::AfterPublication;
        assert!(decode(&serde_json::to_vec(&c).unwrap()).is_ok());
        c.stopped_before_publication = true;
        assert!(decode(&serde_json::to_vec(&c).unwrap()).is_err());
    }
}
