//! Tests of the intended caller, without minting any admitted capability.

use super::*;
use crate::storage::admission::{CANDIDATE_PROFILE, Operation, ProfileField, UNMET_PREDICATES};
use crate::storage::resources::{KnownOperations, OperationKey};
use serde_json::json;
use std::cell::Cell;
use std::fs;
use std::path::PathBuf;
use std::time::{SystemTime, UNIX_EPOCH};

struct DeferredConstruction<'a> {
    calls: &'a Cell<usize>,
}

impl NewOutputBuilder for DeferredConstruction<'_> {
    type Prepared = ();

    fn construct(
        self,
        _admission: &AdmittedByteSink,
        intent: NewOutputIntent<'_>,
        owner: &mut RetainedSession,
        cancel: &Cancellation,
    ) -> Result<Self::Prepared, Failure> {
        self.calls.set(self.calls.get() + 1);
        if cancel.is_requested() {
            return Err(Failure::Cancelled);
        }
        owner.attempt(
            OperationKey {
                operation: intent.operation,
                root: intent.transaction_root.to_str().unwrap(),
            },
            31,
            || Ok(31),
            || {
                let source = fs::read(intent.source).map_err(|_| Failure::SourceIo)?;
                fs::create_dir(intent.transaction_root).map_err(|_| Failure::BackendIo)?;
                fs::write(intent.transaction_root.join(intent.output_leaf), source)
                    .map_err(|_| Failure::BackendIo)
            },
        )
    }
}

#[derive(Debug, PartialEq, Eq)]
struct FileState {
    name: std::ffi::OsString,
    bytes: Vec<u8>,
    modified: SystemTime,
    readonly: bool,
    #[cfg(windows)]
    attributes: u32,
    #[cfg(windows)]
    creation_time: u64,
}

fn snapshot(root: &Path) -> Vec<FileState> {
    #[cfg(windows)]
    use std::os::windows::fs::MetadataExt;

    let mut files: Vec<_> = fs::read_dir(root)
        .unwrap()
        .map(|entry| {
            let entry = entry.unwrap();
            let metadata = entry.metadata().unwrap();
            assert!(metadata.is_file());
            FileState {
                name: entry.file_name(),
                bytes: fs::read(entry.path()).unwrap(),
                modified: metadata.modified().unwrap(),
                readonly: metadata.permissions().readonly(),
                #[cfg(windows)]
                attributes: metadata.file_attributes(),
                #[cfg(windows)]
                creation_time: metadata.creation_time(),
            }
        })
        .collect();
    files.sort_by(|left, right| left.name.cmp(&right.name));
    files
}

fn fixture() -> PathBuf {
    let path = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join(".local/storage-new-output-tests")
        .join(format!(
            "{}-{}",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
    fs::create_dir_all(&path).unwrap();
    fs::write(path.join("source.bin"), b"authored unchanged source\n").unwrap();
    fs::write(path.join("foreign.bin"), b"authored foreign sentinel\n").unwrap();
    path
}

fn assert_refused_before_construction(profile: ProfileRequest<'_>, expected: Unsupported) {
    let root = fixture();
    let source = root.join("source.bin");
    let transaction = root.join("transaction");
    let before = snapshot(&root);
    let calls = Cell::new(0);
    let mut owner = RetainedSession::start(1_000_000, KnownOperations::Complete(&[])).unwrap();
    let prior = OperationKey {
        operation: "authored-prior-cancelled",
        root: "prior-retained-root",
    };
    assert_eq!(
        owner.attempt::<()>(prior, 17, || Ok(17), || Err(Failure::Cancelled)),
        Err(Failure::Cancelled)
    );
    let before_charge = owner.charged();
    let prior_charge = owner.operation_charge(prior).unwrap();
    let cancel = Cancellation::default();
    let intent = NewOutputIntent {
        profile,
        source: &source,
        transaction_root: &transaction,
        output_leaf: "output.bin",
        operation: "authored-intended-new-output",
        format_revision: "authored-test-only-v1",
        planned_len: 26,
        max_len: 1024,
    };
    let result = prepare(
        intent,
        &mut owner,
        &cancel,
        DeferredConstruction { calls: &calls },
    );
    assert_eq!(
        result.unwrap_err(),
        PreparationRefusal::Unsupported(expected)
    );
    assert_eq!(calls.get(), 0, "deferred constructor ran before admission");
    assert_eq!(
        owner.charged(),
        before_charge,
        "refusal charged construction work"
    );
    assert_eq!(owner.operation_charge(prior).unwrap(), prior_charge);
    assert_eq!(
        owner.operation_charge(OperationKey {
            operation: intent.operation,
            root: transaction.to_str().unwrap()
        }),
        Err(Failure::CallerHistory)
    );
    assert!(!cancel.is_requested());
    assert_eq!(snapshot(&root), before);
    assert!(!transaction.exists());
    assert!(!root.join("output.bin").exists());
    // Keep authored native fixtures as evidence rather than deleting outcomes.
}

fn exact_refusal() -> Unsupported {
    if cfg!(all(windows, target_arch = "x86_64")) {
        Unsupported::NecessaryPredicates(UNMET_PREDICATES)
    } else {
        Unsupported::HostPlatform
    }
}

#[test]
fn intended_normal_caller_refuses_before_construction_charge_or_effects() {
    assert_refused_before_construction(ProfileRequest::candidate(), exact_refusal());
}

#[test]
fn intended_mismatched_callers_refuse_before_construction_charge_or_effects() {
    macro_rules! changed {
        ($field:ident, $($member:ident).+) => {
            let mut request = ProfileRequest::candidate();
            request.$($member).+ = "unqualified imported descriptor";
            assert_refused_before_construction(request, Unsupported::Mismatch(ProfileField::$field));
        };
    }
    changed!(CandidateProfile, candidate_profile);
    changed!(Protocol, protocol);
    changed!(Implementation, implementation);
    changed!(Os, configuration.os);
    changed!(Architecture, configuration.architecture);
    changed!(Filesystem, configuration.filesystem);
    changed!(Namespace, configuration.namespace);
    changed!(Controller, configuration.controller);
    changed!(DiskFormat, configuration.disk_format);
    changed!(EmulatorCache, configuration.emulator_cache);
    changed!(ExecutionUser, configuration.execution_user);
    changed!(Topology, configuration.topology);
    changed!(OutputPolicy, configuration.output_policy);
    changed!(RestartAuthority, configuration.restart_authority);
    for operation in [
        Operation::ExistingTargetReplacement,
        Operation::HeldMove,
        Operation::Group,
    ] {
        let mut request = ProfileRequest::candidate();
        request.operation = operation;
        assert_refused_before_construction(request, Unsupported::Mismatch(ProfileField::Operation));
    }
}

#[test]
fn imported_receipt_status_and_profile_claims_do_not_release_intended_constructor() {
    for profile in [CANDIDATE_PROFILE, "forged-admitted-profile"] {
        let bytes = serde_json::to_vec(&json!({
            "profile": profile,
            "status": "Committed",
            "qualification": "passed",
            "production_profile_admitted": true,
            "receipt": {"valid": true, "protocol_complete": true, "authority": "current"},
            "necessary_predicates": [],
        }))
        .unwrap();
        let imported: serde_json::Value = serde_json::from_slice(&bytes).unwrap();
        let request = ProfileRequest {
            candidate_profile: imported["profile"].as_str().unwrap(),
            ..ProfileRequest::candidate()
        };
        let expected = if profile == CANDIDATE_PROFILE {
            exact_refusal()
        } else {
            Unsupported::Mismatch(ProfileField::CandidateProfile)
        };
        assert_refused_before_construction(request, expected);
    }
}

#[test]
fn admission_refusal_precedes_source_open_and_length_budget_work() {
    let root = fixture();
    let missing_source = root.join("does-not-exist.bin");
    let transaction = root.join("transaction");
    let calls = Cell::new(0);
    let mut owner = RetainedSession::start(0, KnownOperations::Complete(&[])).unwrap();
    let cancel = Cancellation::default();
    cancel.request();
    let intent = NewOutputIntent {
        profile: ProfileRequest::candidate(),
        source: &missing_source,
        transaction_root: &transaction,
        output_leaf: "output.bin",
        operation: "authored-no-source-open",
        format_revision: "authored-test-only-v1",
        planned_len: u64::MAX,
        max_len: 0,
    };
    assert_eq!(
        prepare(
            intent,
            &mut owner,
            &cancel,
            DeferredConstruction { calls: &calls }
        )
        .unwrap_err(),
        PreparationRefusal::Unsupported(exact_refusal())
    );
    assert_eq!(calls.get(), 0);
    assert_eq!(owner.charged(), 0);
    assert!(cancel.is_requested());
    assert!(!missing_source.exists());
    assert!(!transaction.exists());
}
