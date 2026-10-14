//! Portable representation of trusted caller history, not authenticated custody.
//!
//! A captured context never proves that publication stayed unreleased. A trusted
//! supervisor must persist a release fence before continuing the worker, or
//! explicitly confirm that the worker stopped without release. Parsing cannot
//! distinguish a current journal from a fabricated or restored older snapshot.
use crate::{
    inspection_record::MAX_RECORD,
    restart_context::{self, Context, Stage},
};
use serde::{Deserialize, Serialize};

const PURPOSE: &str = "imageinfo-od11-custody-history-v1";

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(tag = "event", rename_all = "kebab-case", deny_unknown_fields)]
pub enum Event {
    Captured { context: Context },
    PublicationReleaseFenced {},
    StopConfirmedBeforePublication {},
    PublicationObserved { context: Context },
    ObservationRenewed { context: Context },
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "kebab-case")]
pub enum State {
    CapturedUnconfirmed,
    PublicationReleaseUncertain,
    StopAttestedBeforePublication,
    PublicationObserved,
    ObservationRenewed,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct Journal {
    purpose: String,
    events: Vec<Event>,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Wire {
    purpose: String,
    events: Vec<Event>,
}

impl<'de> Deserialize<'de> for Journal {
    fn deserialize<D: serde::Deserializer<'de>>(deserializer: D) -> Result<Self, D::Error> {
        let wire = Wire::deserialize(deserializer)?;
        let journal = Self {
            purpose: wire.purpose,
            events: wire.events,
        };
        journal.validate().map_err(serde::de::Error::custom)?;
        Ok(journal)
    }
}

pub fn decode(bytes: &[u8]) -> Result<Journal, &'static str> {
    if bytes.is_empty() || bytes.len() > MAX_RECORD as usize {
        return Err("CUSTODY_HISTORY_SIZE_INVALID");
    }
    serde_json::from_slice(bytes).map_err(|_| "CUSTODY_HISTORY_INVALID")
}

impl Journal {
    #[cfg(test)]
    pub fn capture(context: Context) -> Result<Self, &'static str> {
        let journal = Self {
            purpose: PURPOSE.into(),
            events: vec![Event::Captured { context }],
        };
        journal.validate()?;
        Ok(journal)
    }

    /// Append only after validating the whole proposed history. The caller owns
    /// persistence and must not release publication until its fence is flushed.
    #[cfg(test)]
    fn append(&mut self, event: Event) -> Result<(), &'static str> {
        let mut proposed = self.clone();
        proposed.events.push(event);
        proposed.validate()?;
        *self = proposed;
        Ok(())
    }

    #[cfg(test)]
    pub fn release_fence(&mut self) -> Result<(), &'static str> {
        self.append(Event::PublicationReleaseFenced {})
    }

    #[cfg(test)]
    pub fn confirm_stop(&mut self) -> Result<(), &'static str> {
        self.append(Event::StopConfirmedBeforePublication {})
    }

    #[cfg(test)]
    pub fn observe(&mut self, context: Context) -> Result<(), &'static str> {
        let event = if self.state() == State::PublicationObserved {
            Event::ObservationRenewed { context }
        } else {
            Event::PublicationObserved { context }
        };
        self.append(event)
    }

    pub fn event_count(&self) -> usize {
        self.events.len()
    }

    pub fn prefix(&self, count: usize) -> Result<Self, &'static str> {
        if count == 0 || count > self.events.len() {
            return Err("CUSTODY_PREFIX_INVALID");
        }
        let journal = Self {
            purpose: self.purpose.clone(),
            events: self.events[..count].to_vec(),
        };
        journal.validate()?;
        Ok(journal)
    }

    pub fn encode(&self) -> Result<Vec<u8>, &'static str> {
        let bytes = serde_json::to_vec(self).map_err(|_| "CUSTODY_HISTORY_INVALID")?;
        if bytes.len() > MAX_RECORD as usize {
            return Err("CUSTODY_HISTORY_SIZE_INVALID");
        }
        Ok(bytes)
    }

    pub fn state(&self) -> State {
        match self.events.last().expect("validated nonempty history") {
            Event::Captured { .. } => State::CapturedUnconfirmed,
            Event::PublicationReleaseFenced {} => State::PublicationReleaseUncertain,
            Event::StopConfirmedBeforePublication {} => State::StopAttestedBeforePublication,
            Event::PublicationObserved { .. } => State::PublicationObserved,
            Event::ObservationRenewed { .. } => State::ObservationRenewed,
        }
    }

    /// Represent an explicit caller decision, never derive authority from an
    /// absent fence or the contents of mutable transaction records.
    pub fn restart_context(&self) -> Option<Context> {
        match self.events.last()? {
            Event::StopConfirmedBeforePublication {} => {
                let Event::Captured { context } = &self.events[0] else {
                    unreachable!()
                };
                let mut context = context.clone();
                context.stopped_before_publication = true;
                Some(context)
            }
            Event::PublicationObserved { context } | Event::ObservationRenewed { context } => {
                Some(context.clone())
            }
            _ => None,
        }
    }

    fn validate(&self) -> Result<(), &'static str> {
        if self.purpose != PURPOSE || self.events.is_empty() || self.events.len() > 4 {
            return Err("CUSTODY_HISTORY_SCOPE_INVALID");
        }
        let Event::Captured { context: initial } = &self.events[0] else {
            return Err("CUSTODY_HISTORY_ORDER_INVALID");
        };
        validate_context(initial)?;
        if initial.stage != Stage::BeforePublication || initial.stopped_before_publication {
            return Err("CUSTODY_CAPTURE_STAGE_INVALID");
        }
        let mut previous = State::CapturedUnconfirmed;
        let mut observed = None;
        for event in &self.events[1..] {
            previous = match (previous, event) {
                (State::CapturedUnconfirmed, Event::PublicationReleaseFenced {}) => {
                    State::PublicationReleaseUncertain
                }
                (State::CapturedUnconfirmed, Event::StopConfirmedBeforePublication {}) => {
                    State::StopAttestedBeforePublication
                }
                (State::PublicationReleaseUncertain, Event::PublicationObserved { context }) => {
                    validate_observation(initial, context)?;
                    observed = Some(context);
                    State::PublicationObserved
                }
                (State::PublicationObserved, Event::ObservationRenewed { context }) => {
                    validate_observation(initial, context)?;
                    let old = observed.expect("preceding observation");
                    if old.records.len() != 2 || context.records.len() != 3 {
                        return Err("CUSTODY_RENEWAL_RECORD_SET_INVALID");
                    }
                    State::ObservationRenewed
                }
                _ => return Err("CUSTODY_HISTORY_ORDER_INVALID"),
            };
        }
        Ok(())
    }
}

fn validate_context(context: &Context) -> Result<(), &'static str> {
    let bytes = serde_json::to_vec(context).map_err(|_| "CUSTODY_CONTEXT_INVALID")?;
    restart_context::decode(&bytes).map(|_| ())
}

fn validate_observation(initial: &Context, observed: &Context) -> Result<(), &'static str> {
    validate_context(observed)?;
    if observed.stage != Stage::AfterPublication
        || observed.stopped_before_publication
        || observed.root != initial.root
        || observed.source != initial.source
        || observed.candidate != initial.candidate
        || observed.sha256 != initial.sha256
        || observed.persistence_mode != initial.persistence_mode
        || observed.records[..2]
            .iter()
            .zip(&initial.records)
            .any(|(now, old)| {
                now.name != old.name || now.info != old.info || now.sha256 != old.sha256
            })
    {
        return Err("CUSTODY_OBSERVATION_BINDING_INVALID");
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{
        inspection_record::Info,
        ordinary_record::PersistenceMode,
        restart_context::{OwnedRecord, RecordName},
    };

    fn context() -> Context {
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
        root.size = 0;
        root.attributes = 16;
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
            persistence_mode: PersistenceMode::WriteThrough,
            records,
        }
    }
    fn observed() -> Context {
        let mut c = context();
        c.stage = Stage::AfterPublication;
        c
    }
    fn renewed() -> Context {
        let mut c = observed();
        let mut record = c.records[0].clone();
        record.name = RecordName::Observation;
        record.info.identity = "1:6".into();
        c.records.push(record);
        c
    }
    fn released() -> Journal {
        let mut journal = Journal::capture(context()).unwrap();
        journal.release_fence().unwrap();
        journal
    }

    #[test]
    fn capture_absence_and_release_uncertainty_never_authorize_restart() {
        let captured = Journal::capture(context()).unwrap();
        assert_eq!(captured.state(), State::CapturedUnconfirmed);
        assert!(captured.restart_context().is_none());
        let released = released();
        assert_eq!(released.state(), State::PublicationReleaseUncertain);
        assert!(released.restart_context().is_none());
        // Restoring an older captured prefix cannot itself authorize prune.
        assert!(released.prefix(1).unwrap().restart_context().is_none());
    }
    #[test]
    fn explicit_stop_attestation_is_terminal_and_round_trips() {
        let mut journal = Journal::capture(context()).unwrap();
        journal.confirm_stop().unwrap();
        assert_eq!(journal.state(), State::StopAttestedBeforePublication);
        let restored = decode(&journal.encode().unwrap()).unwrap();
        assert!(
            restored
                .restart_context()
                .unwrap()
                .stopped_before_publication
        );
        for event in [
            Event::PublicationReleaseFenced {},
            Event::StopConfirmedBeforePublication {},
            Event::PublicationObserved {
                context: observed(),
            },
        ] {
            assert!(journal.append(event).is_err());
            assert_eq!(journal.state(), State::StopAttestedBeforePublication);
        }
    }
    #[test]
    fn no_stop_or_duplicate_release_after_publication_fence() {
        let mut journal = released();
        assert!(journal.confirm_stop().is_err());
        assert!(journal.release_fence().is_err());
        assert!(
            journal
                .append(Event::Captured { context: context() })
                .is_err()
        );
        assert_eq!(journal.event_count(), 2);
        assert!(journal.restart_context().is_none());
    }
    #[test]
    fn matching_observations_advance_without_commitment_or_stop_attestation() {
        let mut journal = released();
        journal.observe(observed()).unwrap();
        assert_eq!(journal.state(), State::PublicationObserved);
        assert!(
            !journal
                .restart_context()
                .unwrap()
                .stopped_before_publication
        );
        journal.observe(renewed()).unwrap();
        assert_eq!(journal.state(), State::ObservationRenewed);
        assert_eq!(journal.restart_context().unwrap().records.len(), 3);
        assert!(journal.observe(renewed()).is_err());
        let restored = decode(&journal.encode().unwrap()).unwrap();
        for n in 1..=4 {
            let prefix = restored.prefix(n).unwrap();
            assert_eq!(decode(&prefix.encode().unwrap()).unwrap().event_count(), n);
        }
        assert!(restored.prefix(0).is_err());
        assert!(restored.prefix(5).is_err());
    }
    #[test]
    fn changed_operation_or_prior_records_cannot_advance_history() {
        for n in 0..8 {
            let mut next = observed();
            match n {
                0 => next.root.creation_time += 1,
                1 => next.source.last_write_time += 1,
                2 => next.candidate.identity = "1:7".into(),
                3 => next.sha256 = "b".repeat(64),
                4 => next.persistence_mode = PersistenceMode::Buffered,
                5 => next.records[0].info.identity = "1:7".into(),
                6 => next.records[1].sha256 = "b".repeat(64),
                _ => next.stopped_before_publication = true,
            }
            let mut journal = released();
            assert!(journal.observe(next).is_err());
            assert_eq!(journal.event_count(), 2);
        }
        let mut journal = released();
        journal.observe(observed()).unwrap();
        assert!(journal.observe(observed()).is_err());
        let mut different = renewed();
        different.records[1].info.last_write_time += 1;
        assert!(journal.observe(different).is_err());
    }
    #[test]
    fn malformed_truncated_duplicate_unknown_and_oversized_history_refuse() {
        assert!(decode(&[]).is_err());
        assert!(decode(&vec![b' '; MAX_RECORD as usize + 1]).is_err());
        let bytes = released().encode().unwrap();
        for n in [1, bytes.len() / 2, bytes.len() - 1] {
            assert!(decode(&bytes[..n]).is_err());
        }
        let text = String::from_utf8(bytes).unwrap();
        let duplicate = text.replacen(
            '{',
            "{\"purpose\":\"imageinfo-od11-custody-history-v1\",",
            1,
        );
        assert!(decode(duplicate.as_bytes()).is_err());
        let mut value = serde_json::to_value(released()).unwrap();
        value["unknown"] = serde_json::json!(true);
        assert!(decode(&serde_json::to_vec(&value).unwrap()).is_err());
        for extra in [
            serde_json::json!({"event":"publication-release-fenced","context":context()}),
            serde_json::json!({"event":"stop-confirmed-before-publication","committed":true}),
        ] {
            let mut value = serde_json::to_value(released()).unwrap();
            value["events"][1] = extra;
            assert!(decode(&serde_json::to_vec(&value).unwrap()).is_err());
        }
    }
    #[test]
    fn stop_without_capture_or_observation_without_release_refuses() {
        for events in [
            serde_json::json!([]),
            serde_json::json!([{"event":"stop-confirmed-before-publication"}]),
            serde_json::json!([{"event":"captured","context":context()},{"event":"publication-observed","context":observed()}]),
        ] {
            let value = serde_json::json!({"purpose": PURPOSE,"events":events});
            assert!(decode(&serde_json::to_vec(&value).unwrap()).is_err());
        }
        let mut before = context();
        before.stopped_before_publication = true;
        assert!(Journal::capture(before).is_err());
        assert!(Journal::capture(observed()).is_err());
    }
}
