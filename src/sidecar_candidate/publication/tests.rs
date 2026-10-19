use super::super::ConflictPolicy;
use super::*;
use crate::storage::admission::{ProfileField, UNMET_PREDICATES};
use crate::storage::resources::{KnownOperations, OperationKey};
use std::cell::Cell;

thread_local! { pub(super) static CONSTRUCTIONS: Cell<usize> = const { Cell::new(0) }; }

fn operation() -> Operation<'static> {
    Operation {
        profile: ProfileRequest::candidate(),
        raw: Path::new("missing-authored-source.cr3"),
        sidecar: Path::new("missing-authored-sidecar.xmp"),
        transaction_root: Path::new("uncreated-authored-transaction"),
        output_leaf: "new-authored-sidecar.xmp",
        operation: "authored-sidecar-new-name",
        create_new: true,
        intent: Intent {
            target_ordinal: 0,
            policy: ConflictPolicy::Refuse,
        },
        limits: Limits::default(),
    }
}

fn unsupported() -> Unsupported {
    if cfg!(all(windows, target_arch = "x86_64")) {
        Unsupported::NecessaryPredicates(UNMET_PREDICATES)
    } else {
        Unsupported::HostPlatform
    }
}

fn assert_selector_refusal(operation: Operation<'_>, cancelled: bool, expected: Unsupported) {
    let mut owner = RetainedSession::start(1_000_000, KnownOperations::Complete(&[])).unwrap();
    let prior = OperationKey {
        operation: "prior-failed-work",
        root: "prior-retained-root",
    };
    assert_eq!(
        owner.attempt::<()>(prior, 13, || Ok(13), || Err(Failure::Cancelled)),
        Err(Failure::Cancelled)
    );
    let charge = owner.charged();
    let prior_charge = owner.operation_charge(prior);
    let cancel = Cancellation::default();
    if cancelled {
        cancel.request();
    }
    CONSTRUCTIONS.with(|count| count.set(0));
    let Preparation::Stopped {
        result,
        unsupported,
    } = prepare(operation, &mut owner, &cancel)
    else {
        panic!("selector incorrectly admitted sidecar construction");
    };
    assert_eq!(unsupported, Some(expected));
    assert_eq!(result, no_effects(Some(Failure::Unsupported)));
    CONSTRUCTIONS.with(|count| assert_eq!(count.get(), 0));
    assert_eq!(owner.charged(), charge);
    assert_eq!(owner.operation_charge(prior), prior_charge);
    assert_eq!(cancel.is_requested(), cancelled);
}

#[test]
fn real_selector_precedes_candidate_source_and_resource_construction() {
    assert_selector_refusal(operation(), false, unsupported());
}

#[test]
fn real_selector_still_precedes_cancel_invalid_intent_and_name_conflict() {
    assert_selector_refusal(operation(), true, unsupported());
    let mut invalid = operation();
    invalid.create_new = false;
    assert_selector_refusal(invalid, false, unsupported());
    let mut conflicting_name = operation();
    conflicting_name.output_leaf = "MISSING-AUTHORED-SIDECAR.XMP";
    assert_selector_refusal(conflicting_name, false, unsupported());
}

#[test]
fn imported_profile_label_cannot_release_deferred_candidate() {
    let mut imported = operation();
    imported.profile.candidate_profile = "saved-plan-claims-committed";
    assert_selector_refusal(
        imported,
        false,
        Unsupported::Mismatch(ProfileField::CandidateProfile),
    );
}

#[test]
fn pure_explicit_new_name_validation_refuses_unsafe_or_original_spellings() {
    assert!(valid_intent(&operation()));
    for leaf in [
        "",
        ".",
        "..",
        "a/b.xmp",
        "a\\b.xmp",
        "a:b.xmp",
        "a.",
        "a ",
        "MISSING-AUTHORED-SOURCE.CR3",
        "MISSING-AUTHORED-SIDECAR.XMP",
    ] {
        let mut invalid = operation();
        invalid.output_leaf = leaf;
        assert!(!valid_intent(&invalid), "accepted {leaf}");
    }
    let mut implicit = operation();
    implicit.create_new = false;
    assert!(!valid_intent(&implicit));
}

#[test]
fn pure_pre_effect_result_mapping_preserves_status_without_receipt_claims() {
    for (failure, status) in [
        (None, Status::Unchanged),
        (Some(Failure::Unsupported), Status::Refused),
        (Some(Failure::InvalidBinding), Status::Refused),
        (Some(Failure::Cancelled), Status::CancelledBeforePublish),
        (Some(Failure::Conflict), Status::Conflict),
        (Some(Failure::BackendIo), Status::FailedBeforePublish),
    ] {
        let result = no_effects(failure);
        assert_eq!(result.status, status);
        assert_eq!(result.failure, failure);
        assert_eq!(result.phase, Phase::Preflight);
        assert!(!result.publication_possible);
        assert!(!result.release_possible);
        assert!(!result.retained_material);
        assert!(!result.pending_cleanup);
        assert_eq!(result.charged_bytes, 0);
        assert!(!result.protocol_complete);
    }
}
