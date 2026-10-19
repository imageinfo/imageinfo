//! Advisory comparison of saved intent with a newly captured source snapshot.
//!
//! No filesystem identity, guard, admission or authority is represented here.
use crate::{plan::PreviewPlan, reader, source_binding};
use std::io::{Read, Seek};

/// Exact fields that changed, in deterministic contract order.
#[derive(Clone, Copy, Debug, PartialEq, Eq, serde::Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ChangedField {
    Schema,
    Revisions,
    SourceLocator,
    SourceLength,
    SourceDigest,
    OccurrencePath,
    NativeId,
    Allocation,
    ByteOrder,
    OriginalBytes,
    IntendedBytes,
    OutputLocator,
    OutputPolicy,
    StorageProfile,
    CollisionPolicy,
    Preservation,
    ExecutionBindings,
    Recovery,
    ApplyAuthorization,
}

/// Pure field comparison. Equality proves only equality of advisory assertions.
pub fn changed_fields(saved: &PreviewPlan, current: &PreviewPlan) -> Vec<ChangedField> {
    let a = saved.saved();
    let b = current.saved();
    let mut changed = Vec::new();
    macro_rules! compare {
        ($field:ident, $left:expr, $right:expr) => {
            if $left != $right {
                changed.push(ChangedField::$field);
            }
        };
    }
    compare!(Schema, a.schema, b.schema);
    compare!(Revisions, a.revisions, b.revisions);
    compare!(SourceLocator, a.source.path, b.source.path);
    compare!(SourceLength, a.source.length, b.source.length);
    compare!(SourceDigest, a.source.sha256, b.source.sha256);
    compare!(OccurrencePath, a.occurrence.path, b.occurrence.path);
    compare!(NativeId, a.occurrence.native_id, b.occurrence.native_id);
    compare!(Allocation, a.occurrence.allocation, b.occurrence.allocation);
    compare!(ByteOrder, a.occurrence.byte_order, b.occurrence.byte_order);
    compare!(
        OriginalBytes,
        a.occurrence.original_bytes,
        b.occurrence.original_bytes
    );
    compare!(IntendedBytes, a.intended_bytes, b.intended_bytes);
    compare!(OutputLocator, a.output.path, b.output.path);
    compare!(OutputPolicy, a.output.policy, b.output.policy);
    compare!(StorageProfile, a.output.profile, b.output.profile);
    compare!(CollisionPolicy, a.output.collision, b.output.collision);
    compare!(Preservation, a.preservation, b.preservation);
    compare!(
        ExecutionBindings,
        a.execution_bindings,
        b.execution_bindings
    );
    compare!(Recovery, a.recovery, b.recovery);
    compare!(
        ApplyAuthorization,
        a.apply_authorization,
        b.apply_authorization
    );
    changed
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, serde::Serialize)]
#[serde(rename_all = "snake_case")]
pub enum DateValueEffect {
    AlreadyEqual,
    ReplaceAscii20,
}

/// Requested byte/name effects, not evidence that either effect is permissible.
#[derive(Clone, Debug, PartialEq, Eq, serde::Serialize)]
pub struct RequestedEffects {
    pub date_value: DateValueEffect,
    /// Explicit fresh-name copy intent remains even when the date is equal.
    pub new_output_locator: String,
    pub collision: crate::plan::CollisionPolicy,
}

pub fn requested_effects(plan: &PreviewPlan) -> RequestedEffects {
    let saved = plan.saved();
    RequestedEffects {
        date_value: if saved.occurrence.original_bytes == saved.intended_bytes {
            DateValueEffect::AlreadyEqual
        } else {
            DateValueEffect::ReplaceAscii20
        },
        new_output_locator: saved.output.path.clone(),
        collision: saved.output.collision,
    }
}

#[derive(Debug, serde::Serialize)]
pub struct SnapshotComparison {
    pub changed_fields: Vec<ChangedField>,
    /// Full fresh advisory proposal exposes changed bytes/ranges and refusals.
    pub current: source_binding::BoundPreview,
    pub requested_effects: RequestedEffects,
}

impl SnapshotComparison {
    pub fn production_mutation_allowed(&self) -> bool {
        false
    }
}

/// Recompute using the actual bounded reader, date parser and admission preview.
/// Inputs are supplied explicitly by the caller; saved locators are never opened.
/// One fresh snapshot supplies all current content/occurrence/value observations.
/// Invalid or ambiguous current input returns an error, never a successful no-op.
/// The saved intent is retained; changes are reported rather than accepted.
pub fn recompute<R: Read + Seek>(
    input: R,
    saved: &PreviewPlan,
    current_source_locator: &str,
    current_output_locator: &str,
    proposed: &str,
) -> reader::Result<SnapshotComparison> {
    let current = source_binding::capture(
        input,
        current_source_locator,
        current_output_locator,
        proposed,
    )?;
    Ok(SnapshotComparison {
        changed_fields: changed_fields(saved, &current.plan),
        requested_effects: requested_effects(&current.plan),
        current,
    })
}
