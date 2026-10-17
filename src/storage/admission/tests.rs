//! Authored boundary checks. No test constructs an admitted production sink.

use super::*;
use serde_json::json;
use std::fs;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

fn normal_refusal() -> Unsupported {
    select_profile(&ProfileRequest::candidate()).expect_err("no current profile is admitted")
}

#[test]
fn exact_current_request_never_returns_a_sink() {
    let refusal = normal_refusal();
    #[cfg(not(all(windows, target_arch = "x86_64")))]
    assert_eq!(refusal, Unsupported::HostPlatform);
    #[cfg(all(windows, target_arch = "x86_64"))]
    assert_eq!(refusal, Unsupported::NecessaryPredicates(UNMET_PREDICATES));
}

#[test]
fn necessary_predicates_name_the_actual_contrary_missing_and_binding_obligations() {
    let obligations: Vec<_> = UNMET_PREDICATES
        .iter()
        .map(|item| (item.predicate, item.disposition))
        .collect();
    assert_eq!(
        obligations,
        [
            (
                Predicate::PreparedSourceNamespacePreservedOnNativeError,
                EvidenceDisposition::ContraryObservation
            ),
            (
                Predicate::NativeCandidateFileFlushError,
                EvidenceDisposition::NotProduced
            ),
            (
                Predicate::NativeInstalledNamespaceFlushError,
                EvidenceDisposition::NotProduced
            ),
            (
                Predicate::NativeReceiptFileFlushError,
                EvidenceDisposition::NotProduced
            ),
            (
                Predicate::ExactLiveConfigurationAndImplementationBinding,
                EvidenceDisposition::NotImplemented
            ),
        ]
    );
    for item in UNMET_PREDICATES {
        assert!(!item.corrective_owner.is_empty());
        assert!(!item.correction.is_empty());
        assert!(
            Path::new(env!("CARGO_MANIFEST_DIR"))
                .join(item.evidence)
                .is_file()
        );
    }
}

fn mismatches() -> Vec<(ProfileRequest<'static>, ProfileField)> {
    let mut cases = Vec::new();
    macro_rules! changed {
        ($field:ident, $($member:ident).+) => {
            for value in ["", "unknown-or-imported"] {
                let mut request = ProfileRequest::candidate();
                request.$($member).+ = value;
                cases.push((request, ProfileField::$field));
            }
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
        cases.push((request, ProfileField::Operation));
    }
    cases
}

#[test]
fn every_exact_descriptor_field_and_other_operation_refuses_precisely() {
    for (request, field) in mismatches() {
        assert_eq!(
            select_profile(&request).unwrap_err(),
            Unsupported::Mismatch(field)
        );
    }
}

#[test]
fn profile_labels_are_not_case_or_whitespace_normalized_into_a_match() {
    for profile in [
        CANDIDATE_PROFILE.to_uppercase(),
        format!(" {CANDIDATE_PROFILE}"),
        format!("{CANDIDATE_PROFILE}\n"),
    ] {
        let request = ProfileRequest {
            candidate_profile: &profile,
            ..ProfileRequest::candidate()
        };
        assert_eq!(
            select_profile(&request).unwrap_err(),
            Unsupported::Mismatch(ProfileField::CandidateProfile)
        );
    }
}

/// These are editable transport claims, deliberately not capability inputs.
#[test]
fn imported_profile_receipt_and_status_claims_cannot_change_selection() {
    let expected = normal_refusal();
    for status in ["qualified", "Committed", "complete", "admitted"] {
        let claim = json!({
            "profile": CANDIDATE_PROFILE,
            "status": status,
            "production_profile_admitted": true,
            "raw_admitted": true,
            "receipt": {"protocol_complete": true, "committed": true},
            "necessary_predicates": [],
        });
        let bytes = serde_json::to_vec(&claim).unwrap();
        let imported: serde_json::Value = serde_json::from_slice(&bytes).unwrap();
        // Only the descriptor string can be presented to the selector. There
        // is no importer for any of the apparent authority/status fields.
        let mut request = ProfileRequest::candidate();
        request.candidate_profile = imported["profile"].as_str().unwrap();
        assert_eq!(select_profile(&request).unwrap_err(), expected);
    }
}

fn fixture() -> PathBuf {
    let path = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join(".local/storage-admission-tests")
        .join(format!(
            "{}-{}",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
    fs::create_dir_all(&path).unwrap();
    fs::write(path.join("source.bin"), b"authored protected source\n").unwrap();
    fs::write(path.join("foreign.bin"), b"authored foreign sentinel\n").unwrap();
    path
}

#[derive(Debug, PartialEq, Eq)]
struct FileState {
    name: std::ffi::OsString,
    bytes: Vec<u8>,
    readonly: bool,
    modified: SystemTime,
    #[cfg(windows)]
    attributes: u32,
    #[cfg(windows)]
    creation_time: u64,
}

fn inventory(path: &Path) -> Vec<FileState> {
    #[cfg(windows)]
    use std::os::windows::fs::MetadataExt;

    let mut entries: Vec<_> = fs::read_dir(path)
        .unwrap()
        .map(|entry| {
            let entry = entry.unwrap();
            let metadata = fs::metadata(entry.path()).unwrap();
            assert!(metadata.is_file());
            FileState {
                name: entry.file_name(),
                bytes: fs::read(entry.path()).unwrap(),
                readonly: metadata.permissions().readonly(),
                modified: metadata.modified().unwrap(),
                #[cfg(windows)]
                attributes: metadata.file_attributes(),
                #[cfg(windows)]
                creation_time: metadata.creation_time(),
            }
        })
        .collect();
    entries.sort_by(|a, b| a.name.cmp(&b.name));
    entries
}

#[test]
fn refusal_has_no_source_foreign_file_or_target_namespace_effects() {
    let root = fixture();
    let before = inventory(&root);
    let expected = normal_refusal();
    for _ in 0..3 {
        assert_eq!(normal_refusal(), expected);
        assert_eq!(inventory(&root), before);
        assert!(!root.join("transaction").exists());
        assert!(!root.join("output.bin").exists());
    }
    for (request, field) in mismatches() {
        assert_eq!(
            select_profile(&request).unwrap_err(),
            Unsupported::Mismatch(field)
        );
        assert_eq!(inventory(&root), before);
    }
    // Retain authored fixture evidence, matching the other native storage tests.
}

#[cfg(not(all(windows, target_arch = "x86_64")))]
#[test]
fn requested_windows_descriptor_does_not_override_actual_host_platform() {
    let request = ProfileRequest::candidate();
    assert_eq!(
        select_profile(&request).unwrap_err(),
        Unsupported::HostPlatform
    );
}
