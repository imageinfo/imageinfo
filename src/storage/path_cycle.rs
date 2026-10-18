//! Bounded three-move marker exchange. No qualified profile or restart authority.
//!
//! The protocol is #0097's existing contract. Every call moves one retained
//! original, never a copied artifact, and every uncertain boundary is terminal.
#[cfg(any(windows, test))]
use std::path::Path;
use std::{io, path::PathBuf};

#[derive(Clone, Debug)]
pub(crate) struct Plan {
    names: [PathBuf; 3],
}

impl Plan {
    pub(crate) fn new(a: PathBuf, b: PathBuf, temp: PathBuf) -> io::Result<Self> {
        let names = [a, b, temp];
        let parent = names[0]
            .parent()
            .filter(|p| !p.as_os_str().is_empty())
            .ok_or_else(|| io::Error::other("CYCLE_PARENT_REQUIRED"))?;
        let mut leaves = Vec::new();
        for path in &names {
            if path.parent() != Some(parent) || path.components().count() > 64 {
                return Err(io::Error::other("CYCLE_SAME_PARENT_REQUIRED"));
            }
            let leaf = path
                .file_name()
                .and_then(|s| s.to_str())
                .ok_or_else(|| io::Error::other("CYCLE_COMPONENT_REQUIRED"))?;
            if !leaf.is_ascii()
                || leaf.len() > 100
                || leaf.is_empty()
                || leaf.ends_with([' ', '.'])
                || leaf.chars().any(|c| c < ' ' || "\\/:*?\"<>|".contains(c))
                || leaf == "."
                || leaf == ".."
            {
                return Err(io::Error::other("CYCLE_COMPONENT_UNSUPPORTED"));
            }
            let base = leaf.split('.').next().unwrap_or("").to_ascii_uppercase();
            if matches!(base.as_str(), "CON" | "PRN" | "AUX" | "NUL")
                || ["COM", "LPT"].iter().any(|p| {
                    base.strip_prefix(p).is_some_and(|s| {
                        matches!(s, "1" | "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9")
                    })
                })
                || leaves
                    .iter()
                    .any(|other: &&str| other.eq_ignore_ascii_case(leaf))
            {
                return Err(io::Error::other("CYCLE_ALIAS_OR_RESERVED_COMPONENT"));
            }
            leaves.push(leaf);
        }
        // Components containing traversal are refused before any path is opened.
        if names.iter().any(|p| {
            p.components().any(|c| {
                matches!(
                    c,
                    std::path::Component::ParentDir | std::path::Component::CurDir
                )
            })
        }) {
            return Err(io::Error::other("CYCLE_PATH_TRAVERSAL"));
        }
        Ok(Self { names })
    }

    pub(crate) fn names(&self) -> &[PathBuf; 3] {
        &self.names
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(crate) enum Binding {
    Absent,
    Alpha,
    Beta,
    Foreign,
    Unknown,
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(crate) enum Outcome {
    Ready,
    NoEffect,
    Partial,
    CompleteObserved,
    RecoveryRequired,
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(crate) struct Report {
    pub outcome: Outcome,
    pub confirmed_prefix: u8,
    /// Last observed map; uncertainty forbids treating this as current custody.
    pub bindings: [Binding; 3],
    pub uncertain: bool,
}

const PREFIXES: [[Binding; 3]; 4] = [
    [Binding::Alpha, Binding::Beta, Binding::Absent],
    [Binding::Absent, Binding::Beta, Binding::Alpha],
    [Binding::Beta, Binding::Absent, Binding::Alpha],
    [Binding::Beta, Binding::Alpha, Binding::Absent],
];
// (held original index, source slot, destination slot), exactly #0097.
const MOVES: [(usize, usize, usize); 3] = [(0, 0, 2), (1, 1, 0), (0, 2, 1)];

#[cfg(windows)]
mod native {
    use super::*;
    use crate::storage::{Cancellation, MAX_RECORD_BYTES};
    use imageinfo_windows_storage::{
        ExistingMoveBinding, ExistingMoveOutcome, FileSnapshot, HeldArtifact,
        HeldExistingMoveSession, PrivateRoot,
    };
    use std::time::{Duration, Instant};

    /// Preliminary finite candidate, not a tunnel-cache or preservation guarantee.
    #[derive(Clone, Copy, Debug, Eq, PartialEq)]
    pub(crate) enum ContinuationPolicy {
        GuardHeldQuiet20Seconds,
        /// Retains the original contrary method for explicit diagnostics only.
        ImmediateDiagnostic,
    }

    const QUIET_GAP: Duration = Duration::from_secs(20);

    #[derive(Clone, Copy, Debug, Eq, PartialEq)]
    pub(crate) enum HookStage {
        BeforeCall,
        AfterCall,
        Confirmed,
    }
    #[derive(Clone, Copy, Debug, Eq, PartialEq)]
    pub(crate) enum HookAction {
        Continue,
        Stop,
        LostResponse,
    }

    /// Owns both original guards and all private record guards until drop.
    /// No constructor imports a prefix and no method retries a terminal attempt.
    pub(crate) struct Cycle {
        plan: Plan,
        held: [HeldExistingMoveSession; 2],
        root: PrivateRoot,
        records: Vec<HeldArtifact>,
        report: Report,
        terminal: bool,
        policy: ContinuationPolicy,
        confirmed_at: Option<Instant>,
        quiet_elapsed_nanos: [Option<u64>; 2],
    }

    impl Cycle {
        pub(crate) fn open(
            plan: Plan,
            alpha: &FileSnapshot,
            beta: &FileSnapshot,
            private_record_root: &Path,
        ) -> io::Result<Self> {
            Self::open_with_policy(
                plan,
                alpha,
                beta,
                private_record_root,
                ContinuationPolicy::ImmediateDiagnostic,
            )
        }

        pub(crate) fn open_with_policy(
            plan: Plan,
            alpha: &FileSnapshot,
            beta: &FileSnapshot,
            private_record_root: &Path,
            policy: ContinuationPolicy,
        ) -> io::Result<Self> {
            if alpha.volume_serial_number != beta.volume_serial_number
                || alpha.file_index == beta.file_index
                || alpha.links != 1
                || beta.links != 1
            {
                return Err(io::Error::other("CYCLE_ORIGINAL_IDENTITIES"));
            }
            let first = HeldExistingMoveSession::open(&plan.names[0], alpha, &plan.names)?;
            let second = HeldExistingMoveSession::open(&plan.names[1], beta, &plan.names)?;
            let mut value = Self {
                plan,
                held: [first, second],
                root: PrivateRoot::create(private_record_root)?,
                records: Vec::with_capacity(8),
                report: Report {
                    outcome: Outcome::Ready,
                    confirmed_prefix: 0,
                    bindings: PREFIXES[0],
                    uncertain: false,
                },
                terminal: false,
                policy,
                confirmed_at: None,
                quiet_elapsed_nanos: [None; 2],
            };
            value.check()?;
            value.report.bindings = value.observe()?;
            if value.report.bindings != PREFIXES[0] {
                return Err(io::Error::other("CYCLE_INITIAL_MAP"));
            }
            value.save("prepared", None)?;
            Ok(value)
        }

        pub(crate) fn report(&self) -> Report {
            self.report
        }
        pub(crate) fn plan(&self) -> &Plan {
            &self.plan
        }
        pub(crate) fn policy(&self) -> ContinuationPolicy {
            self.policy
        }
        pub(crate) fn quiet_elapsed_nanos(&self) -> [Option<u64>; 2] {
            self.quiet_elapsed_nanos
        }
        pub(crate) fn advance(&mut self, cancel: &Cancellation) -> Report {
            self.advance_with(cancel, |_, _| HookAction::Continue)
        }

        fn check(&mut self) -> io::Result<()> {
            self.held[0].check()?;
            self.held[1].check()?;
            self.root.check()?;
            for record in &mut self.records {
                record.check(&self.root)?;
            }
            Ok(())
        }

        fn observe(&self) -> io::Result<[Binding; 3]> {
            let mut map = [Binding::Unknown; 3];
            for (index, path) in self.plan.names.iter().enumerate() {
                let a = self.held[0].binding(path)?;
                let b = self.held[1].binding(path)?;
                map[index] = match (a, b) {
                    (ExistingMoveBinding::Absent, ExistingMoveBinding::Absent) => Binding::Absent,
                    (ExistingMoveBinding::HeldObject, ExistingMoveBinding::ForeignObject) => {
                        Binding::Alpha
                    }
                    (ExistingMoveBinding::ForeignObject, ExistingMoveBinding::HeldObject) => {
                        Binding::Beta
                    }
                    (ExistingMoveBinding::ForeignObject, ExistingMoveBinding::ForeignObject) => {
                        Binding::Foreign
                    }
                    _ => return Err(io::Error::other("CYCLE_BINDING_UNPROVABLE")),
                };
            }
            Ok(map)
        }

        fn save(&mut self, phase: &str, in_flight: Option<u8>) -> io::Result<()> {
            if self.records.len() >= 8 {
                return Err(io::Error::other("CYCLE_RECORD_BOUND"));
            }
            // Exact snapshots include private security data; only an owner-private
            // fresh root receives this bounded record. No JSON import exists.
            let encoded = serde_json::to_vec(&serde_json::json!({
                "schema":"imageinfo.private-cycle-observation.v1", "phase":phase,
                "names":self.plan.names, "originals":[
                    self.held[0].snapshot().binding_bytes(), self.held[1].snapshot().binding_bytes()],
                "confirmedPrefix":self.report.confirmed_prefix,
                "inFlight":in_flight, "bindings":format!("{:?}", self.report.bindings),
                "uncertain":self.report.uncertain, "qualified":false,
                "restartAuthority":false
                ,"continuationPolicy":format!("{:?}", self.policy),
                "quietElapsedNanos":self.quiet_elapsed_nanos
            }))?;
            if encoded.len() as u64 > MAX_RECORD_BYTES {
                return Err(io::Error::other("CYCLE_RECORD_BOUND"));
            }
            let record = self.root.create_artifact(
                &format!("cycle-{}.record", self.records.len()),
                &encoded,
                MAX_RECORD_BYTES,
            )?;
            self.records.push(record);
            Ok(())
        }

        fn stop(&mut self, uncertain: bool) -> Report {
            self.terminal = true;
            self.report.uncertain |= uncertain;
            self.report.outcome = if self.report.uncertain {
                Outcome::RecoveryRequired
            } else if self.report.confirmed_prefix == 0 {
                Outcome::NoEffect
            } else {
                Outcome::Partial
            };
            if self.report.uncertain {
                self.held[0].mark_uncertain();
                self.held[1].mark_uncertain();
            }
            // Retain the terminal observation too. A failed save cannot turn
            // a post-effect stop into a trustworthy current-prefix report.
            if self.save("terminal-stop", None).is_err() && self.report.confirmed_prefix > 0 {
                self.report.uncertain = true;
                self.report.outcome = Outcome::RecoveryRequired;
                self.held[0].mark_uncertain();
                self.held[1].mark_uncertain();
            }
            self.report
        }

        /// Qualification hooks never release a guard. A lost return is terminal,
        /// even if the test knows whether the underlying call actually succeeded.
        pub(crate) fn advance_with(
            &mut self,
            cancel: &Cancellation,
            mut hook: impl FnMut(u8, HookStage) -> HookAction,
        ) -> Report {
            if self.terminal {
                return self.report;
            }
            let prefix = self.report.confirmed_prefix as usize;
            if cancel.is_requested() {
                return self.stop(false);
            }
            if prefix > 0 && self.policy == ContinuationPolicy::GuardHeldQuiet20Seconds {
                let Some(confirmed_at) = self.confirmed_at else {
                    return self.stop(true);
                };
                // One fixed candidate, never retry with an increased wait. Both
                // original/ancestor handles remain owned throughout this gap.
                // Elapsed time does not prove quiet namespace history or expiry.
                loop {
                    let elapsed = confirmed_at.elapsed();
                    self.quiet_elapsed_nanos[prefix - 1] = u64::try_from(elapsed.as_nanos()).ok();
                    if self.quiet_elapsed_nanos[prefix - 1].is_none() {
                        return self.stop(true);
                    }
                    if cancel.is_requested() {
                        return self.stop(false);
                    }
                    if elapsed >= QUIET_GAP {
                        break;
                    }
                    std::thread::sleep((QUIET_GAP - elapsed).min(Duration::from_millis(50)));
                }
                if cancel.is_requested() {
                    return self.stop(false);
                }
            }
            // This is also the mandatory fresh full checkpoint after waiting.
            if self.check().is_err() {
                return self.stop(true);
            }
            self.report.bindings = match self.observe() {
                Ok(map) => map,
                Err(_) => return self.stop(true),
            };
            if self.report.bindings != PREFIXES[prefix] {
                return self.stop(false);
            }
            // Save both the confirmed prefix and possible next call before effects.
            if self.save("call-may-follow", Some(prefix as u8)).is_err() {
                return self.stop(prefix > 0);
            }
            let before = hook(prefix as u8, HookStage::BeforeCall);
            if before == HookAction::LostResponse {
                return self.stop(true);
            }
            if before == HookAction::Stop || cancel.is_requested() {
                return self.stop(false);
            }
            // Recheck after hooks; destination insertion remains protected by the
            // SDK no-replace call if it occurs after this last observation.
            if self.check().is_err() {
                return self.stop(true);
            }
            self.report.bindings = match self.observe() {
                Ok(map) => map,
                Err(_) => return self.stop(true),
            };
            if self.report.bindings != PREFIXES[prefix] {
                return self.stop(false);
            }
            let (original, source, destination) = MOVES[prefix];
            let result =
                self.held[original].move_to(&self.plan.names[destination], cancel.is_requested());
            let after = hook(prefix as u8, HookStage::AfterCall);
            if after != HookAction::Continue || result == ExistingMoveOutcome::RecoveryRequired {
                self.report.bindings[source] = Binding::Unknown;
                self.report.bindings[destination] = Binding::Unknown;
                return self.stop(true);
            }
            if result != ExistingMoveOutcome::ObservedMoved {
                self.report.bindings = match self.observe() {
                    Ok(map) => map,
                    Err(_) => return self.stop(true),
                };
                let uncertain = self.check().is_err();
                return self.stop(uncertain);
            }
            // A call is confirmed only after both originals, all bindings and
            // every baseline property match the expected next prefix.
            if self.check().is_err() {
                return self.stop(true);
            }
            self.report.bindings = match self.observe() {
                Ok(map) => map,
                Err(_) => return self.stop(true),
            };
            if self.report.bindings != PREFIXES[prefix + 1] {
                return self.stop(true);
            }
            self.report.confirmed_prefix += 1;
            self.confirmed_at = Some(Instant::now());
            if self.save("confirmed-prefix", None).is_err() {
                return self.stop(true);
            }
            let confirmed = hook(prefix as u8, HookStage::Confirmed);
            if confirmed != HookAction::Continue {
                return self.stop(confirmed != HookAction::Stop);
            }
            if prefix == 2 {
                if self.check().is_err() {
                    return self.stop(true);
                }
                self.report.bindings = match self.observe() {
                    Ok(map) => map,
                    Err(_) => return self.stop(true),
                };
                if self.report.bindings != PREFIXES[3] {
                    return self.stop(true);
                }
                // This record is the eighth and last. It is an observation only.
                if self.save("complete-observed", None).is_err() {
                    return self.stop(true);
                }
                self.report.outcome = Outcome::CompleteObserved;
                self.terminal = true;
            }
            self.report
        }
    }
}

#[cfg(windows)]
#[allow(unused_imports)] // Qualification-only caller; no production profile is admitted.
pub(crate) use native::{ContinuationPolicy, Cycle, HookAction, HookStage};
#[cfg(all(test, windows))]
#[path = "path_cycle/native_tests.rs"]
mod native_tests;
#[cfg(test)]
#[path = "path_cycle/plan_tests.rs"]
mod plan_tests;
