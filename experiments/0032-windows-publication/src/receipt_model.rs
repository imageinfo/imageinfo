//! Finite protocol research for #0045; no runtime backend calls this model.
//!
//! A `QualifiedModel` profile is a hypothetical premise for protocol reasoning,
//! not a statement that any Windows profile is qualified. Raw API observations
//! intentionally cannot manufacture the phase-bound acknowledgements below.

use std::collections::HashSet;

#[derive(Clone, Copy, Debug, Eq, Hash, PartialEq)]
struct Binding {
    operation: u8,
    unit: u8,
    root: u8,
    source: u8,
    destination_parent: u8,
    candidate: u8,
    content_revision: u8,
    profile_revision: u8,
}

const OWNED: Binding = Binding {
    operation: 1,
    unit: 1,
    root: 1,
    source: 1,
    destination_parent: 1,
    candidate: 1,
    content_revision: 1,
    profile_revision: 1,
};

#[derive(Clone, Copy, Debug, Eq, Hash, PartialEq)]
enum Profile {
    Unqualified,
    QualifiedModel,
}

#[derive(Clone, Copy, Debug, Eq, Hash, PartialEq)]
enum Phase {
    CandidateReady,
    CandidatePersisted,
    PreparedPersisted,
    IntentPersisted,
    PublicationInFlight,
    InstalledVerified,
    InstalledFilePersisted,
    NamespaceAcknowledged,
    ObservationPersisted,
    ReceiptWritten,
    ReceiptPersisted,
    FinalInstalledVerified,
    ModelQualifiedCommitted,
    RefusedBeforePublication,
    RecoveryRequired,
}

#[derive(Clone, Copy, Debug, Eq, Hash, PartialEq)]
enum AckPhase {
    Candidate,
    Prepared,
    Intent,
    InstalledFile,
    Namespace,
    Observation,
    Receipt,
}

#[derive(Clone, Copy, Debug, Eq, Hash, PartialEq)]
enum Artifact {
    Candidate,
    PreparedRecord,
    IntentRecord,
    InstalledOutput,
    DestinationParent,
    ObservationRecord,
    ReceiptRecord,
}

#[derive(Clone, Copy, Debug, Eq, Hash, PartialEq)]
struct Ack {
    binding: Binding,
    phase: AckPhase,
    artifact: Artifact,
    artifact_revision: u8,
}

#[derive(Clone, Copy, Debug, Eq, Hash, PartialEq)]
enum Event {
    RawApiSuccess,
    RawFlushSuccess,
    MatchingEditableRecord,
    Acknowledge(Ack),
    PublicationAttempt,
    InstalledCheck {
        binding: Binding,
        properties: bool,
    },
    ReceiptWritten {
        binding: Binding,
        namespace_ack: Ack,
    },
    Commit,
    LoseGuard,
    Fail,
    Interrupt {
        within_qualified_scope: bool,
    },
    CleanupFailed,
}

#[derive(Clone, Copy, Debug, Eq, Hash, PartialEq)]
struct Model {
    profile: Profile,
    phase: Phase,
    guards: bool,
    publication_attempted: bool,
    cleanup_pending: bool,
}

impl Model {
    fn new(profile: Profile) -> Self {
        Self {
            profile,
            phase: Phase::CandidateReady,
            guards: true,
            publication_attempted: false,
            cleanup_pending: false,
        }
    }

    /// Rejected events leave the complete prior state intact. Acknowledgements
    /// stand for an independently qualified adapter contract, never flush returns.
    fn apply(&mut self, event: Event) -> bool {
        let next = match event {
            Event::RawApiSuccess | Event::RawFlushSuccess | Event::MatchingEditableRecord => {
                return true;
            }
            Event::CleanupFailed if self.phase == Phase::ModelQualifiedCommitted => {
                self.cleanup_pending = true;
                return true;
            }
            Event::Fail | Event::Interrupt { .. } => {
                let qualified_commit_survives = self.phase == Phase::ModelQualifiedCommitted
                    && matches!(
                        event,
                        Event::Interrupt {
                            within_qualified_scope: true
                        }
                    );
                if qualified_commit_survives {
                    return true;
                }
                if self.publication_attempted {
                    Phase::RecoveryRequired
                } else {
                    Phase::RefusedBeforePublication
                }
            }
            Event::LoseGuard => {
                self.guards = false;
                if self.publication_attempted {
                    Phase::RecoveryRequired
                } else {
                    Phase::RefusedBeforePublication
                }
            }
            Event::PublicationAttempt if self.phase == Phase::IntentPersisted && self.guards => {
                self.publication_attempted = true;
                Phase::PublicationInFlight
            }
            Event::InstalledCheck {
                binding,
                properties,
            } if self.phase == Phase::PublicationInFlight
                && self.guards
                && binding == OWNED
                && properties =>
            {
                Phase::InstalledVerified
            }
            Event::InstalledCheck {
                binding,
                properties,
            } if matches!(
                self.phase,
                Phase::PublicationInFlight | Phase::ReceiptPersisted
            ) && (binding != OWNED || !properties) =>
            {
                Phase::RecoveryRequired
            }
            Event::Acknowledge(ack)
                if self.profile == Profile::QualifiedModel
                    && self.guards
                    && ack.binding == OWNED
                    && ack.artifact == artifact_for(ack.phase)
                    && ack.artifact_revision == 1 =>
            {
                match (self.phase, ack.phase) {
                    (Phase::CandidateReady, AckPhase::Candidate) => Phase::CandidatePersisted,
                    (Phase::CandidatePersisted, AckPhase::Prepared) => Phase::PreparedPersisted,
                    (Phase::PreparedPersisted, AckPhase::Intent) => Phase::IntentPersisted,
                    (Phase::InstalledVerified, AckPhase::InstalledFile) => {
                        Phase::InstalledFilePersisted
                    }
                    (Phase::InstalledFilePersisted, AckPhase::Namespace) => {
                        Phase::NamespaceAcknowledged
                    }
                    (Phase::NamespaceAcknowledged, AckPhase::Observation) => {
                        Phase::ObservationPersisted
                    }
                    (Phase::ReceiptWritten, AckPhase::Receipt) => Phase::ReceiptPersisted,
                    _ => return false,
                }
            }
            Event::ReceiptWritten {
                binding,
                namespace_ack,
            } if self.phase == Phase::ObservationPersisted
                && self.guards
                && binding == OWNED
                && namespace_ack == acknowledgement(AckPhase::Namespace) =>
            {
                Phase::ReceiptWritten
            }
            Event::InstalledCheck {
                binding,
                properties,
            } if self.phase == Phase::ReceiptPersisted
                && self.guards
                && binding == OWNED
                && properties =>
            {
                Phase::FinalInstalledVerified
            }
            Event::Commit if self.phase == Phase::FinalInstalledVerified && self.guards => {
                Phase::ModelQualifiedCommitted
            }
            _ => return false,
        };
        self.phase = next;
        true
    }
}

// Restart evidence is supplied by a trusted current caller and a separately
// qualified backend. Inspecting matching files cannot produce either premise.
#[derive(Clone, Copy, Debug)]
struct RestartEvidence {
    current_caller_history: bool,
    fresh_guards: bool,
    bindings_and_properties_match: bool,
    stopped_before_release: bool,
    publication_may_have_run: bool,
    target: Target,
    qualified_finalize_available: bool,
    qualified_receipt_survives: bool,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum Target {
    ExpectedAbsent,
    OwnedCandidate,
    ForeignOrMissing,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum RestartDecision {
    OriginalEstablished,
    FinalizeWithoutRepublish,
    ModelQualifiedCommitted,
    RecoveryRequired,
}

impl RestartEvidence {
    fn decide(self) -> RestartDecision {
        if !self.current_caller_history
            || !self.fresh_guards
            || !self.bindings_and_properties_match
            || (self.stopped_before_release && self.publication_may_have_run)
            || (self.qualified_receipt_survives && self.target != Target::OwnedCandidate)
        {
            return RestartDecision::RecoveryRequired;
        }
        match self.target {
            Target::ExpectedAbsent
                if self.stopped_before_release && !self.publication_may_have_run =>
            {
                RestartDecision::OriginalEstablished
            }
            Target::OwnedCandidate if self.publication_may_have_run => {
                if self.qualified_receipt_survives {
                    RestartDecision::ModelQualifiedCommitted
                } else if self.qualified_finalize_available {
                    RestartDecision::FinalizeWithoutRepublish
                } else {
                    RestartDecision::RecoveryRequired
                }
            }
            _ => RestartDecision::RecoveryRequired,
        }
    }

    fn prune_owned_unpublished_allowed(self) -> bool {
        self.decide() == RestartDecision::OriginalEstablished
    }
}

fn artifact_for(phase: AckPhase) -> Artifact {
    match phase {
        AckPhase::Candidate => Artifact::Candidate,
        AckPhase::Prepared => Artifact::PreparedRecord,
        AckPhase::Intent => Artifact::IntentRecord,
        AckPhase::InstalledFile => Artifact::InstalledOutput,
        AckPhase::Namespace => Artifact::DestinationParent,
        AckPhase::Observation => Artifact::ObservationRecord,
        AckPhase::Receipt => Artifact::ReceiptRecord,
    }
}

fn acknowledgement(phase: AckPhase) -> Ack {
    Ack {
        binding: OWNED,
        phase,
        artifact: artifact_for(phase),
        artifact_revision: 1,
    }
}

fn ack(phase: AckPhase) -> Event {
    Event::Acknowledge(acknowledgement(phase))
}

fn ordered_trace() -> [Event; 12] {
    [
        ack(AckPhase::Candidate),
        ack(AckPhase::Prepared),
        ack(AckPhase::Intent),
        Event::PublicationAttempt,
        Event::InstalledCheck {
            binding: OWNED,
            properties: true,
        },
        ack(AckPhase::InstalledFile),
        ack(AckPhase::Namespace),
        ack(AckPhase::Observation),
        Event::ReceiptWritten {
            binding: OWNED,
            namespace_ack: acknowledgement(AckPhase::Namespace),
        },
        ack(AckPhase::Receipt),
        Event::InstalledCheck {
            binding: OWNED,
            properties: true,
        },
        Event::Commit,
    ]
}

#[test]
fn ordered_protocol_needs_every_distinct_phase() {
    let trace = ordered_trace();
    let mut complete = Model::new(Profile::QualifiedModel);
    for event in trace {
        assert!(complete.apply(event));
    }
    assert_eq!(complete.phase, Phase::ModelQualifiedCommitted);
    for omitted in 0..trace.len() {
        let mut model = Model::new(Profile::QualifiedModel);
        for (index, event) in trace.into_iter().enumerate() {
            if index != omitted {
                model.apply(event);
            }
        }
        assert_ne!(
            model.phase,
            Phase::ModelQualifiedCommitted,
            "omitted {omitted}"
        );
    }
    for swapped in 0..trace.len() - 1 {
        let mut reordered = trace;
        reordered.swap(swapped, swapped + 1);
        let mut model = Model::new(Profile::QualifiedModel);
        for event in reordered {
            model.apply(event);
        }
        assert_ne!(
            model.phase,
            Phase::ModelQualifiedCommitted,
            "swapped {swapped}"
        );
    }
}

#[test]
fn acknowledgements_bind_each_identity_and_current_phase() {
    let substitutions = [
        Binding {
            operation: 2,
            ..OWNED
        },
        Binding { unit: 2, ..OWNED },
        Binding { root: 2, ..OWNED },
        Binding { source: 2, ..OWNED },
        Binding {
            destination_parent: 2,
            ..OWNED
        },
        Binding {
            candidate: 2,
            ..OWNED
        },
        Binding {
            content_revision: 2,
            ..OWNED
        },
        Binding {
            profile_revision: 2,
            ..OWNED
        },
    ];
    let mut model = Model::new(Profile::QualifiedModel);
    for event in ordered_trace() {
        if let Event::Acknowledge(expected) = event {
            for bad in [
                Ack {
                    artifact_revision: 2,
                    ..expected
                },
                Ack {
                    artifact: if expected.artifact == Artifact::Candidate {
                        Artifact::ReceiptRecord
                    } else {
                        Artifact::Candidate
                    },
                    ..expected
                },
            ] {
                let before = model;
                assert!(!model.apply(Event::Acknowledge(bad)));
                assert_eq!(model, before);
            }
            for binding in substitutions {
                let before = model;
                assert!(!model.apply(Event::Acknowledge(Ack {
                    binding,
                    ..expected
                })));
                assert_eq!(model, before);
            }
        }
        assert!(model.apply(event));
        if let Event::Acknowledge(_) = event {
            let before = model;
            assert!(!model.apply(event), "earlier acknowledgement was reused");
            assert_eq!(model, before);
        }
    }
}

#[test]
fn current_unqualified_profile_and_raw_successes_never_commit() {
    let mut model = Model::new(Profile::Unqualified);
    for _ in 0..3 {
        for event in ordered_trace() {
            model.apply(Event::RawApiSuccess);
            model.apply(Event::RawFlushSuccess);
            model.apply(Event::MatchingEditableRecord);
            model.apply(event);
        }
    }
    assert_eq!(model.phase, Phase::CandidateReady);
    assert!(!model.publication_attempted);
    let mut in_flight = Model::new(Profile::QualifiedModel);
    for event in ordered_trace().into_iter().take(4) {
        assert!(in_flight.apply(event));
    }
    for event in [
        Event::RawApiSuccess,
        Event::RawFlushSuccess,
        Event::MatchingEditableRecord,
    ] {
        assert!(in_flight.apply(event));
    }
    assert!(!in_flight.apply(Event::Commit));
    assert_eq!(in_flight.phase, Phase::PublicationInFlight);
    assert!(in_flight.apply(Event::Fail));
    assert_eq!(in_flight.phase, Phase::RecoveryRequired);
    // Counterexamples to the tempting alternative rules: all three observations
    // can be true while the actual protocol still refuses publication/commit.
    let api_success = true;
    let flush_success = true;
    let matching_record = true;
    let naive_commit = api_success && flush_success && matching_record;
    assert!(naive_commit, "the unsafe alternative would report commit");
    assert_ne!(model.phase, Phase::ModelQualifiedCommitted);
}

#[test]
fn every_interruption_preserves_the_publication_uncertainty_boundary() {
    for prefix in 0..=ordered_trace().len() {
        for within_qualified_scope in [false, true] {
            let mut model = Model::new(Profile::QualifiedModel);
            for event in ordered_trace().into_iter().take(prefix) {
                assert!(model.apply(event));
            }
            assert!(model.apply(Event::Interrupt {
                within_qualified_scope
            }));
            let expected = if prefix == ordered_trace().len() && within_qualified_scope {
                Phase::ModelQualifiedCommitted
            } else if prefix >= 4 {
                Phase::RecoveryRequired
            } else {
                Phase::RefusedBeforePublication
            };
            assert_eq!(model.phase, expected, "prefix {prefix}");
            if expected != Phase::ModelQualifiedCommitted {
                assert!(!model.apply(Event::Commit));
            }
        }
    }
}

#[test]
fn cleanup_failure_cannot_reapply_or_undo_a_commit() {
    let mut model = Model::new(Profile::QualifiedModel);
    for event in ordered_trace() {
        assert!(model.apply(event));
    }
    assert!(model.apply(Event::CleanupFailed));
    assert!(model.cleanup_pending);
    assert_eq!(model.phase, Phase::ModelQualifiedCommitted);
    assert!(!model.apply(Event::PublicationAttempt));
}

#[test]
fn finite_reachable_graph_rejects_foreign_and_out_of_order_evidence() {
    let mut events = ordered_trace().to_vec();
    events.extend([
        Event::RawApiSuccess,
        Event::RawFlushSuccess,
        Event::MatchingEditableRecord,
        Event::LoseGuard,
        Event::Fail,
        Event::Interrupt {
            within_qualified_scope: false,
        },
        Event::Interrupt {
            within_qualified_scope: true,
        },
        Event::CleanupFailed,
        Event::InstalledCheck {
            binding: OWNED,
            properties: false,
        },
        Event::InstalledCheck {
            binding: Binding {
                candidate: 2,
                ..OWNED
            },
            properties: true,
        },
    ]);
    for phase in [
        AckPhase::Candidate,
        AckPhase::Prepared,
        AckPhase::Intent,
        AckPhase::InstalledFile,
        AckPhase::Namespace,
        AckPhase::Observation,
        AckPhase::Receipt,
    ] {
        events.push(Event::Acknowledge(Ack {
            binding: Binding {
                operation: 2,
                ..OWNED
            },
            ..acknowledgement(phase)
        }));
    }
    // InstalledCheck appears twice in the ordered trace. Explore each distinct
    // event once per state rather than counting the duplicate as more coverage.
    let mut distinct_events = HashSet::new();
    events.retain(|event| distinct_events.insert(*event));
    assert_eq!(events.len(), 28);
    let mut seen = HashSet::from([
        Model::new(Profile::QualifiedModel),
        Model::new(Profile::Unqualified),
    ]);
    let mut queue: Vec<_> = seen.iter().copied().collect();
    while let Some(model) = queue.pop() {
        for &event in &events {
            let mut next = model;
            let accepted = next.apply(event);
            if !accepted {
                assert_eq!(next, model);
            }
            if next.phase == Phase::ModelQualifiedCommitted {
                assert_eq!(next.profile, Profile::QualifiedModel);
                assert!(next.guards && next.publication_attempted);
                if model.phase != Phase::ModelQualifiedCommitted {
                    assert_eq!(model.phase, Phase::FinalInstalledVerified);
                    assert_eq!(event, Event::Commit);
                }
            }
            if !next.guards {
                assert!(matches!(
                    next.phase,
                    Phase::RefusedBeforePublication | Phase::RecoveryRequired
                ));
            }
            if seen.insert(next) {
                queue.push(next);
            }
        }
    }
    assert_eq!(seen.len(), 23);
    assert_eq!(seen.len() * events.len(), 644);
}

#[test]
fn restart_truth_table_never_infers_history_or_prune_from_absence() {
    for bits in 0_u16..128 {
        for target in [
            Target::ExpectedAbsent,
            Target::OwnedCandidate,
            Target::ForeignOrMissing,
        ] {
            let evidence = RestartEvidence {
                current_caller_history: bits & 1 != 0,
                fresh_guards: bits & 2 != 0,
                bindings_and_properties_match: bits & 4 != 0,
                stopped_before_release: bits & 8 != 0,
                publication_may_have_run: bits & 16 != 0,
                qualified_finalize_available: bits & 32 != 0,
                qualified_receipt_survives: bits & 64 != 0,
                target,
            };
            let decision = evidence.decide();
            if evidence.qualified_receipt_survives && target != Target::OwnedCandidate {
                assert_eq!(decision, RestartDecision::RecoveryRequired);
            }
            if decision != RestartDecision::RecoveryRequired {
                assert!(
                    evidence.current_caller_history
                        && evidence.fresh_guards
                        && evidence.bindings_and_properties_match
                );
            }
            if evidence.prune_owned_unpublished_allowed() {
                assert!(evidence.stopped_before_release && !evidence.publication_may_have_run);
                assert_eq!(target, Target::ExpectedAbsent);
            }
            if decision == RestartDecision::ModelQualifiedCommitted {
                assert!(evidence.qualified_receipt_survives && evidence.publication_may_have_run);
                assert_eq!(target, Target::OwnedCandidate);
            }
        }
    }
    let stale_absent = RestartEvidence {
        current_caller_history: false,
        fresh_guards: true,
        bindings_and_properties_match: true,
        stopped_before_release: true,
        publication_may_have_run: false,
        target: Target::ExpectedAbsent,
        qualified_finalize_available: false,
        qualified_receipt_survives: false,
    };
    assert_eq!(stale_absent.decide(), RestartDecision::RecoveryRequired);
    assert!(!stale_absent.prune_owned_unpublished_allowed());
}

#[test]
fn receipt_bytes_cannot_acknowledge_their_own_later_persistence() {
    let mut model = Model::new(Profile::QualifiedModel);
    for event in ordered_trace().into_iter().take(9) {
        assert!(model.apply(event));
    }
    assert_eq!(model.phase, Phase::ReceiptWritten);
    // A readable matching receipt may claim "flushed" but was serialized before
    // its own file/parent calls. That assertion supplies no external ack.
    assert!(model.apply(Event::MatchingEditableRecord));
    assert!(!model.apply(Event::Commit));
    assert!(model.apply(ack(AckPhase::Receipt)));
    assert_eq!(model.phase, Phase::ReceiptPersisted);
    assert!(!model.apply(Event::Commit));
    assert!(model.apply(Event::InstalledCheck {
        binding: OWNED,
        properties: false
    }));
    assert_eq!(model.phase, Phase::RecoveryRequired);
    assert!(!model.apply(Event::InstalledCheck {
        binding: OWNED,
        properties: true
    }));
    assert!(!model.apply(Event::Commit));
}

#[test]
fn receipt_must_bind_the_actual_namespace_acknowledgement() {
    let mut model = Model::new(Profile::QualifiedModel);
    for event in ordered_trace().into_iter().take(8) {
        assert!(model.apply(event));
    }
    let expected = acknowledgement(AckPhase::Namespace);
    for namespace_ack in [
        Ack {
            binding: Binding {
                operation: 2,
                ..OWNED
            },
            ..expected
        },
        Ack {
            artifact_revision: 2,
            ..expected
        },
        acknowledgement(AckPhase::InstalledFile),
    ] {
        let before = model;
        assert!(!model.apply(Event::ReceiptWritten {
            binding: OWNED,
            namespace_ack
        }));
        assert_eq!(model, before);
    }
    assert_eq!(model.phase, Phase::ObservationPersisted);
}
