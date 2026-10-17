//! Code-defined storage admission boundary for the selected single-output candidate.
//!
//! The request describes what a caller wants; it is not an observation of the
//! machine, an authority assertion, or an imported qualification decision. There
//! is currently no supported profile. Neither receipts nor editable evidence
//! summaries participate in selection, and selection performs no target effects.

use std::convert::Infallible;

use super::runtime::PROTOCOL;

pub(crate) const CANDIDATE_PROFILE: &str = "windows-ntfs-single-new-output-26300.9457-v1";
pub(crate) const IMPLEMENTATION: &str =
    concat!("imageinfo-storage-live-ack-v1-", env!("CARGO_PKG_VERSION"));

/// Requested scope only. These values cannot establish live configuration facts.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) struct Configuration<'a> {
    pub os: &'a str,
    pub architecture: &'a str,
    pub filesystem: &'a str,
    pub namespace: &'a str,
    pub controller: &'a str,
    pub disk_format: &'a str,
    pub emulator_cache: &'a str,
    pub execution_user: &'a str,
    pub topology: &'a str,
    pub output_policy: &'a str,
    pub restart_authority: &'a str,
}

/// Publicly described portion of the #0165/#0175 candidate, not its admission.
/// Device/volume/driver/cache and actual executable bindings remain necessary;
/// these labels cannot substitute for the retained exact fixture observations.
pub(crate) const CANDIDATE_CONFIGURATION: Configuration<'static> = Configuration {
    os: "Windows 11 EnterpriseEval 10.0.26300.9457",
    architecture: "x86_64",
    filesystem: "local NTFS system volume",
    namespace: "ordinary DOS, held physical parent and ancestors",
    controller: "QEMU q35/KVM, standard SATA AHCI, if=ide",
    disk_format: "qcow2",
    emulator_cache: "writeback, host caches survive VM-off",
    execution_user: "standard user",
    topology: "single source, fresh private root, same-parent same-volume no-replace rename",
    output_policy: "ordinary owner-editable, boundary property checks, no source ACL changes",
    restart_authority: "trusted explicit current caller, no authority from receipt survival",
};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum Operation {
    SingleNewOutput,
    ExistingTargetReplacement,
    HeldMove,
    Group,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) struct ProfileRequest<'a> {
    pub candidate_profile: &'a str,
    pub protocol: &'a str,
    pub implementation: &'a str,
    pub configuration: Configuration<'a>,
    pub operation: Operation,
}

impl ProfileRequest<'static> {
    /// Construct a request for the selected candidate, never a capability.
    pub(crate) fn candidate() -> Self {
        Self {
            candidate_profile: CANDIDATE_PROFILE,
            protocol: PROTOCOL,
            implementation: IMPLEMENTATION,
            configuration: CANDIDATE_CONFIGURATION,
            operation: Operation::SingleNewOutput,
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum ProfileField {
    CandidateProfile,
    Protocol,
    Implementation,
    Operation,
    Os,
    Architecture,
    Filesystem,
    Namespace,
    Controller,
    DiskFormat,
    EmulatorCache,
    ExecutionUser,
    Topology,
    OutputPolicy,
    RestartAuthority,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum Predicate {
    PreparedSourceNamespacePreservedOnNativeError,
    NativeCandidateFileFlushError,
    NativeInstalledNamespaceFlushError,
    NativeReceiptFileFlushError,
    ExactLiveConfigurationAndImplementationBinding,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum EvidenceDisposition {
    ContraryObservation,
    NotProduced,
    NotImplemented,
}

/// A concrete corrective obligation, not an editable qualification status.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) struct UnmetPredicate {
    pub predicate: Predicate,
    pub disposition: EvidenceDisposition,
    pub evidence: &'static str,
    pub corrective_owner: &'static str,
    pub correction: &'static str,
}

/// Compiled necessary failures. External JSON, saved results and test admission
/// cannot change this set. #0175's twelve bounded observations do not close any
/// of these #0174/profile-binding obligations; physical power is not an obligation.
pub(crate) const UNMET_PREDICATES: &[UnmetPredicate] = &[
    UnmetPredicate {
        predicate: Predicate::PreparedSourceNamespacePreservedOnNativeError,
        disposition: EvidenceDisposition::ContraryObservation,
        evidence: "docs/write-safety/production-native-errors.md",
        corrective_owner: "#0022 storage integration; #0176 admission",
        correction: "Resolve the staged native-error prepared-source/transaction namespace loss and substantiate preservation for the exact proposed configuration. Old-name bytes do not establish prepared-name or property preservation; the cause remains unproven.",
    },
    UnmetPredicate {
        predicate: Predicate::NativeCandidateFileFlushError,
        disposition: EvidenceDisposition::NotProduced,
        evidence: "docs/write-safety/production-native-errors.md",
        corrective_owner: "#0022 storage integration; #0176 admission",
        correction: "Supply actual candidate-file native flush-failure behavior under the exact profile. Successful guest flushes and emulator drain EIO do not produce this error class.",
    },
    UnmetPredicate {
        predicate: Predicate::NativeInstalledNamespaceFlushError,
        disposition: EvidenceDisposition::NotProduced,
        evidence: "docs/write-safety/production-native-errors.md",
        corrective_owner: "#0022 storage integration; #0176 admission",
        correction: "Supply actual post-publication installed-root native flush-failure behavior and retained uncertainty/preservation checks under the exact profile.",
    },
    UnmetPredicate {
        predicate: Predicate::NativeReceiptFileFlushError,
        disposition: EvidenceDisposition::NotProduced,
        evidence: "docs/write-safety/production-native-errors.md",
        corrective_owner: "#0022 storage integration; #0176 admission",
        correction: "Supply actual receipt-file native flush-failure behavior under the exact profile; receipt survival and flush-return success cannot substitute.",
    },
    UnmetPredicate {
        predicate: Predicate::ExactLiveConfigurationAndImplementationBinding,
        disposition: EvidenceDisposition::NotImplemented,
        evidence: "docs/write-safety/new-output-contract.md",
        corrective_owner: "#0176 admission implementation",
        correction: "Before any positive grant, implement reviewed live binding of OS/servicing/filesystem/volume/controller/cache/executable facts and held operation identities to an actually qualified exact profile. Requested labels and frozen fixture summaries cannot establish current bindings.",
    },
];

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum Unsupported {
    HostPlatform,
    Mismatch(ProfileField),
    NecessaryPredicates(&'static [UnmetPredicate]),
}

/// Opaque downstream storage capability. It deliberately has no inhabitant or
/// constructor, including in test builds. Adding a positive production path
/// requires a reviewed implementation change, not a status/receipt toggle.
/// Independent format validation and explicit apply would still be mandatory.
#[derive(Debug)]
pub(crate) struct AdmittedByteSink {
    _unavailable: Infallible,
}

/// Select before opening source/target paths, constructing storage objects,
/// charging a budget, or releasing a worker. No callback, backend or I/O is
/// accepted. Request matching never asserts that the actual machine matches.
pub(crate) fn select_profile(
    request: &ProfileRequest<'_>,
) -> Result<AdmittedByteSink, Unsupported> {
    let expected = ProfileRequest::candidate();
    let fields = [
        (
            request.candidate_profile,
            expected.candidate_profile,
            ProfileField::CandidateProfile,
        ),
        (request.protocol, expected.protocol, ProfileField::Protocol),
        (
            request.implementation,
            expected.implementation,
            ProfileField::Implementation,
        ),
        (
            request.configuration.os,
            expected.configuration.os,
            ProfileField::Os,
        ),
        (
            request.configuration.architecture,
            expected.configuration.architecture,
            ProfileField::Architecture,
        ),
        (
            request.configuration.filesystem,
            expected.configuration.filesystem,
            ProfileField::Filesystem,
        ),
        (
            request.configuration.namespace,
            expected.configuration.namespace,
            ProfileField::Namespace,
        ),
        (
            request.configuration.controller,
            expected.configuration.controller,
            ProfileField::Controller,
        ),
        (
            request.configuration.disk_format,
            expected.configuration.disk_format,
            ProfileField::DiskFormat,
        ),
        (
            request.configuration.emulator_cache,
            expected.configuration.emulator_cache,
            ProfileField::EmulatorCache,
        ),
        (
            request.configuration.execution_user,
            expected.configuration.execution_user,
            ProfileField::ExecutionUser,
        ),
        (
            request.configuration.topology,
            expected.configuration.topology,
            ProfileField::Topology,
        ),
        (
            request.configuration.output_policy,
            expected.configuration.output_policy,
            ProfileField::OutputPolicy,
        ),
        (
            request.configuration.restart_authority,
            expected.configuration.restart_authority,
            ProfileField::RestartAuthority,
        ),
    ];
    if request.operation != Operation::SingleNewOutput {
        return Err(Unsupported::Mismatch(ProfileField::Operation));
    }
    for (actual, expected, field) in fields {
        if actual != expected {
            return Err(Unsupported::Mismatch(field));
        }
    }
    if !cfg!(all(windows, target_arch = "x86_64")) {
        return Err(Unsupported::HostPlatform);
    }
    Err(Unsupported::NecessaryPredicates(UNMET_PREDICATES))
}

#[cfg(test)]
mod tests;
