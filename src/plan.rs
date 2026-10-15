//! Strict, nonexecuting saved intent for one existing CR3 date allocation.
//!
//! Parsing checks the contract, never the source, authority or storage guarantees.
//! See `docs/legacy-compatibility/cr3-preview-plan.md`.
use serde::{Deserialize, Serialize};
use std::fmt;

pub const SCHEMA: &str = "imageinfo.cr3-date-preview.v1";
pub const MODEL_REVISION: &str = "cr3-date-preview-2026-10-15.1";
pub const MAX_PLAN_BYTES: usize = 32 * 1024;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct PlanError(pub String);
impl fmt::Display for PlanError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.0)
    }
}
impl std::error::Error for PlanError {}

/// A syntactically valid digest assertion, not a computed or authenticated identity.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(try_from = "String", into = "String")]
pub struct Sha256Digest(String);
impl TryFrom<String> for Sha256Digest {
    type Error = PlanError;
    fn try_from(value: String) -> Result<Self, Self::Error> {
        if value.len() != 64
            || !value
                .bytes()
                .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
        {
            return Err(PlanError("Expected 64 lowercase SHA-256 hex digits".into()));
        }
        Ok(Self(value))
    }
}
impl From<Sha256Digest> for String {
    fn from(value: Sha256Digest) -> Self {
        value.0
    }
}
impl Sha256Digest {
    pub fn as_str(&self) -> &str {
        &self.0
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Revisions {
    pub model: String,
    pub reader: String,
    pub admission: String,
    pub registry: String,
    pub capability: String,
    pub conversion: Conversion,
    pub policy: OutputPolicy,
}
impl Default for Revisions {
    fn default() -> Self {
        Self {
            model: MODEL_REVISION.into(),
            reader: crate::reader::READER_REVISION.into(),
            admission: crate::reader::admission::REVISION.into(),
            registry: crate::reader::admission::CATALOG_REVISION.into(),
            capability: crate::CAPABILITY_DATA_REVISION.into(),
            conversion: Conversion::ExactGregorianAscii20,
            policy: OutputPolicy::OrdinaryPrivateOwnerOd11A,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SourceBinding {
    /// Locator only. Never resolved, opened or trusted by this module.
    pub path: String,
    pub length: u64,
    pub sha256: Sha256Digest,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Allocation {
    pub offset: u64,
    pub length: u64,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct OccurrencePart {
    pub kind: String,
    pub name: String,
    pub index: u32,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct OccurrenceBinding {
    pub path: Vec<OccurrencePart>,
    pub native_id: u16,
    pub allocation: Allocation,
    pub byte_order: ByteOrder,
    pub original_bytes: [u8; 20],
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct OutputSelection {
    pub path: String,
    pub policy: OutputPolicy,
    pub profile: StorageProfile,
    pub collision: CollisionPolicy,
}

macro_rules! wire_enum {
    ($name:ident { $($variant:ident => $wire:literal),+ $(,)? }) => {
        #[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
        pub enum $name { $(#[serde(rename = $wire)] $variant),+ }
    };
}
wire_enum!(ByteOrder { LittleEndian => "little-endian", BigEndian => "big-endian" });
wire_enum!(Conversion { ExactGregorianAscii20 => "exact-gregorian-ascii20" });
wire_enum!(OutputPolicy { OrdinaryPrivateOwnerOd11A => "ordinary-private-owner-od11-a" });
wire_enum!(StorageProfile { UnavailableProduction => "unavailable-production" });
wire_enum!(CollisionPolicy { RequireAbsent => "require-absent" });
wire_enum!(ApplyAuthorization { SeparateCallerRequired => "separate-caller-required" });
wire_enum!(ExecutionBindings { MustRecompute => "must-recompute-before-any-apply" });
wire_enum!(Preservation { EntireSourceExceptSelectedAllocation => "entire-source-except-selected-allocation" });
wire_enum!(Recovery { NoMutationOrRecoveryAuthority => "no-mutation-or-recovery-authority" });

/// Untrusted wire data. Even successful validation only produces preview intent.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SavedPreviewPlan {
    pub schema: String,
    pub revisions: Revisions,
    pub source: SourceBinding,
    pub occurrence: OccurrenceBinding,
    pub intended_bytes: [u8; 20],
    pub output: OutputSelection,
    pub preservation: Preservation,
    pub execution_bindings: ExecutionBindings,
    pub recovery: Recovery,
    pub apply_authorization: ApplyAuthorization,
}

/// Validated contract shape. Does not prove source freshness or grant apply authority.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(try_from = "SavedPreviewPlan", into = "SavedPreviewPlan")]
pub struct PreviewPlan(SavedPreviewPlan);
impl From<PreviewPlan> for SavedPreviewPlan {
    fn from(value: PreviewPlan) -> Self {
        value.0
    }
}
impl TryFrom<SavedPreviewPlan> for PreviewPlan {
    type Error = PlanError;
    fn try_from(value: SavedPreviewPlan) -> Result<Self, Self::Error> {
        Self::new(value)
    }
}
impl PreviewPlan {
    pub fn from_json(json: &str) -> Result<Self, PlanError> {
        if json.len() > MAX_PLAN_BYTES {
            return Err(PlanError("Saved preview exceeds 32 KiB".into()));
        }
        serde_json::from_str(json).map_err(|error| PlanError(error.to_string()))
    }

    pub fn new(value: SavedPreviewPlan) -> Result<Self, PlanError> {
        let invalid = |message: &str| PlanError(message.into());
        if value.schema != SCHEMA || value.revisions != Revisions::default() {
            return Err(invalid(
                "Unsupported schema or rule revision; replan required",
            ));
        }
        for path in [&value.source.path, &value.output.path] {
            if path.is_empty() || path.len() > 4096 || path.chars().any(char::is_control) {
                return Err(invalid(
                    "Expected a bounded nonempty path without control characters",
                ));
            }
        }
        if value.source.path == value.output.path {
            return Err(invalid("New output must differ from source locator"));
        }
        if value.source.length > 256 * 1024 * 1024 {
            return Err(invalid("Source exceeds bounded admission scope"));
        }
        let occurrence = &value.occurrence;
        if occurrence.native_id != 0x9003
            || occurrence.allocation.length != 20
            || occurrence
                .allocation
                .offset
                .checked_add(20)
                .is_none_or(|end| end > value.source.length)
        {
            return Err(invalid(
                "Expected an existing bounded DateTimeOriginal ASCII20 allocation",
            ));
        }
        let path = &occurrence.path;
        if !(3..=64).contains(&path.len())
            || path.iter().any(|part| {
                part.name.is_empty()
                    || part.name.len() > 128
                    || part.name.chars().any(char::is_control)
            })
            || path[..path.len() - 2].iter().any(|part| part.kind != "box")
            || path
                .iter()
                .filter(|part| part.kind == "box" && part.name == "CMT2")
                .count()
                != 1
            || path[path.len() - 3].name != "CMT2"
            || path[path.len() - 2].kind != "ifd"
            || path[path.len() - 2].index != 0
            || !path[path.len() - 2]
                .name
                .strip_prefix("IFD@")
                .is_some_and(|offset| {
                    !offset.is_empty()
                        && offset.bytes().all(|b| b.is_ascii_digit())
                        && offset.parse::<u32>().is_ok()
                })
            || path[path.len() - 1].kind != "tag"
            || path[path.len() - 1].name != "36867"
        {
            return Err(invalid(
                "Expected the exact bounded CMT2/IFD/36867 occurrence path",
            ));
        }
        for bytes in [&occurrence.original_bytes, &value.intended_bytes] {
            let text = std::str::from_utf8(&bytes[..19])
                .map_err(|_| invalid("Date bytes must be ASCII20"))?;
            let parsed = crate::reader::admission::DateTime::parse(text)
                .map_err(|_| invalid("Date bytes must encode a complete Gregorian date"))?;
            if parsed.encoded() != *bytes {
                return Err(invalid("Date bytes must end with one NUL"));
            }
        }
        Ok(Self(value))
    }

    pub fn saved(&self) -> &SavedPreviewPlan {
        &self.0
    }

    /// No imported flag, digest, profile label or later caller consent can enable
    /// execution through this preview-only contract.
    pub fn production_mutation_allowed(&self) -> bool {
        false
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const VALID: &str = include_str!("../docs/legacy-compatibility/preview-plan/valid.v1.json");

    #[derive(Deserialize)]
    #[serde(deny_unknown_fields)]
    struct NegativeVector {
        name: String,
        pointer: String,
        replacement: serde_json::Value,
    }

    #[test]
    fn positive_roundtrip_never_authorizes_mutation() {
        let plan = PreviewPlan::from_json(VALID).unwrap();
        assert!(!plan.production_mutation_allowed());
        assert_eq!(plan.saved().occurrence.allocation.length, 20);
        let roundtrip = serde_json::to_string(&plan).unwrap();
        assert_eq!(PreviewPlan::from_json(&roundtrip).unwrap(), plan);
        // Imported metadata uses the same strict boundary; a validated shape is
        // still only a claim about a source that has never been opened here.
        assert!(
            !serde_json::from_str::<PreviewPlan>(VALID)
                .unwrap()
                .production_mutation_allowed()
        );
    }

    #[test]
    fn typed_negative_vectors_refuse_contract_and_authority_injection() {
        let vectors: Vec<NegativeVector> = serde_json::from_str(include_str!(
            "../docs/legacy-compatibility/preview-plan/negative.v1.json"
        ))
        .unwrap();
        for vector in vectors {
            let mut plan: serde_json::Value = serde_json::from_str(VALID).unwrap();
            // Unknown members are deliberately inserted into the parent object.
            if let Some(field) = plan.pointer_mut(&vector.pointer) {
                *field = vector.replacement;
            } else {
                let (parent, name) = vector.pointer.rsplit_once('/').unwrap();
                plan.pointer_mut(parent)
                    .unwrap()
                    .as_object_mut()
                    .unwrap()
                    .insert(name.into(), vector.replacement);
            }
            assert!(
                PreviewPlan::from_json(&plan.to_string()).is_err(),
                "{}",
                vector.name
            );
        }
    }

    #[test]
    fn duplicate_members_are_rejected_at_each_struct_boundary() {
        for (member, replacement) in [
            (
                "\"schema\":",
                "\"schema\": \"imageinfo.cr3-date-preview.v1\", \"schema\":",
            ),
            ("\"length\": 4096", "\"length\": 4096, \"length\": 4096"),
            (
                "\"native_id\": 36867",
                "\"native_id\": 36867, \"native_id\": 36867",
            ),
            ("\"index\": 0", "\"index\": 0, \"index\": 0"),
            (
                "\"profile\":",
                "\"profile\": \"unavailable-production\", \"profile\":",
            ),
            (
                "\"model\":",
                "\"model\": \"cr3-date-preview-2026-10-15.1\", \"model\":",
            ),
            ("\"offset\": 256", "\"offset\": 256, \"offset\": 256"),
        ] {
            let duplicate = VALID.replacen(member, replacement, 1);
            assert_ne!(duplicate, VALID);
            assert!(PreviewPlan::from_json(&duplicate).is_err(), "{member}");
        }
    }

    #[test]
    fn overflow_trailing_data_and_oversized_input_refuse() {
        assert!(
            PreviewPlan::from_json(
                &VALID.replace("\"offset\": 256", &format!("\"offset\": {}", u64::MAX))
            )
            .is_err()
        );
        assert!(PreviewPlan::from_json(&format!("{VALID} {{}}")).is_err());
        assert!(PreviewPlan::from_json(&" ".repeat(MAX_PLAN_BYTES + 1)).is_err());
    }

    #[test]
    fn occurrence_path_is_not_a_name_only_selector() {
        let valid = PreviewPlan::from_json(VALID).unwrap();
        for index in 0..valid.saved().occurrence.path.len() {
            let mut changed = valid.saved().clone();
            changed.occurrence.path[index].kind = "foreign".into();
            assert!(PreviewPlan::new(changed).is_err());
        }
        let mut changed = valid.saved().clone();
        changed.occurrence.path[3].name = "IFD@overflow9999999999999999999".into();
        assert!(PreviewPlan::new(changed).is_err());
    }
}
