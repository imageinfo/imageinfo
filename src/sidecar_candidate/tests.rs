//! Actual authored filesystem tests of the compiled internal production module.
#[allow(dead_code)]
#[path = "../../tests/support/mod.rs"]
mod support;
use super::{ConflictPolicy, Intent, Kind, Limits, Loss, Refusal, prepare};
use crate::xmp;
use std::{
    fs,
    path::PathBuf,
    sync::atomic::{AtomicU64, Ordering},
};

struct FixtureDir {
    path: PathBuf,
}

impl FixtureDir {
    fn new() -> Self {
        static NEXT: AtomicU64 = AtomicU64::new(0);
        // Preserve old fixtures while bounding each new session's directory.
        static SESSION: std::sync::OnceLock<PathBuf> = std::sync::OnceLock::new();
        let parent = SESSION.get_or_init(|| {
            let now = std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap();
            std::env::current_dir()
                .unwrap()
                .join(".local")
                .join("test-runs")
                .join((now.as_secs() / 86_400).to_string())
                .join(format!("186-{}-{}", std::process::id(), now.as_nanos()))
        });
        let path = parent.join(format!(
            "{}-{}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
        fs::create_dir_all(path.parent().unwrap()).unwrap();
        fs::create_dir(&path).unwrap();
        Self { path }
    }
}

const OLD: &str = "2020-02-29T01:02:03";
const MAPPED: &str = "2026-01-02T03:04:05.00+00:00";

struct Fixture {
    dir: FixtureDir,
    raw: PathBuf,
    sidecar: PathBuf,
    raw_bytes: Vec<u8>,
    sidecar_bytes: Vec<u8>,
}

impl Fixture {
    fn new(date: &str) -> Self {
        let dir = FixtureDir::new();
        let raw = dir.path.join("selected.CR3");
        let sidecar = dir.path.join("different.xmp");
        let raw_bytes = support::fixture_with_previews(
            "Firmware Version 2.2.1",
            vec![255, 216, 255, 217],
            vec![255, 216, 255, 217],
            vec![255, 216, 255, 217],
        )
        .bytes;
        let sidecar_bytes = format!("<r:RDF xmlns:r='{}' xmlns:e='http://ns.adobe.com/exif/1.0/' xmlns:u='urn:authored:kept'><r:Description><u:note>original</u:note><e:DateTimeOriginal>{date}</e:DateTimeOriginal></r:Description></r:RDF>", xmp::RDF).into_bytes();
        fs::write(&raw, &raw_bytes).unwrap();
        fs::write(&sidecar, &sidecar_bytes).unwrap();
        fs::write(dir.path.join("neighbor"), b"neighbor retained").unwrap();
        Self {
            dir,
            raw,
            sidecar,
            raw_bytes,
            sidecar_bytes,
        }
    }

    fn witness(&self) {
        assert_eq!(fs::read(&self.raw).unwrap(), self.raw_bytes);
        assert_eq!(fs::read(&self.sidecar).unwrap(), self.sidecar_bytes);
        assert_eq!(
            fs::read(self.dir.path.join("neighbor")).unwrap(),
            b"neighbor retained"
        );
        assert_eq!(fs::read_dir(&self.dir.path).unwrap().count(), 3);
    }
}

fn intent(policy: ConflictPolicy<'_>) -> [Intent<'_>; 1] {
    [Intent {
        target_ordinal: 1,
        policy,
    }]
}

fn replace() -> [Intent<'static>; 1] {
    intent(ConflictPolicy::ReplaceSelected { acknowledged: &[] })
}

#[test]
fn live_derivative_retains_original_occurrences_facts_and_exact_complement() {
    let f = Fixture::new(OLD);
    let mut candidate = prepare(&f.raw, &f.sidecar, &replace(), Limits::default()).unwrap();
    assert_eq!(candidate.kind(), Kind::Derivative);
    let expected = String::from_utf8(f.sidecar_bytes.clone())
        .unwrap()
        .replacen(OLD, MAPPED, 1);
    assert_eq!(candidate.bytes(), expected.as_bytes());
    assert_eq!(candidate.facts().previous, OLD);
    assert_eq!(candidate.facts().mapped, MAPPED);
    assert_eq!(candidate.facts().target_ordinal, 1);
    assert_eq!(
        candidate.facts().mapping,
        "r5-cmt2-original-to-xmp-exif-original/1"
    );
    assert!(candidate.facts().losses.is_empty());
    assert!(candidate.facts().acknowledged.is_empty());
    assert_eq!(candidate.source().len(), 3);
    for item in candidate.source() {
        let stored = &f.raw_bytes
            [item.range.offset as usize..(item.range.offset + item.range.length) as usize];
        assert_eq!(stored.last(), Some(&0));
        assert_eq!(&stored[..stored.len() - 1], item.text.as_bytes());
    }
    candidate.recheck().unwrap();
    drop(candidate);
    f.witness();
}

#[test]
fn live_noop_has_exact_original_bytes_and_no_effects() {
    let f = Fixture::new(MAPPED);
    let mut candidate = prepare(
        &f.raw,
        &f.sidecar,
        &intent(ConflictPolicy::Refuse),
        Limits::default(),
    )
    .unwrap();
    assert_eq!(candidate.kind(), Kind::NoOp);
    assert_eq!(candidate.bytes(), f.sidecar_bytes);
    candidate.recheck().unwrap();
    drop(candidate);
    f.witness();
}

#[test]
fn actual_held_sources_exclude_substitution_data_and_ancestor_moves() {
    let f = Fixture::new(OLD);
    let mut candidate = prepare(&f.raw, &f.sidecar, &replace(), Limits::default()).unwrap();
    assert!(fs::rename(&f.raw, f.dir.path.join("moved.CR3")).is_err());
    assert!(fs::write(&f.sidecar, b"foreign replacement").is_err());
    assert!(fs::rename(&f.dir.path, f.dir.path.with_extension("moved")).is_err());
    candidate.recheck().unwrap();
    drop(candidate);
    f.witness();
}

#[test]
fn property_staleness_latches_without_rebasing() {
    let f = Fixture::new(OLD);
    let mut candidate = prepare(&f.raw, &f.sidecar, &replace(), Limits::default()).unwrap();
    let original_permissions = fs::metadata(&f.sidecar).unwrap().permissions();
    let mut permissions = original_permissions.clone();
    permissions.set_readonly(true);
    fs::set_permissions(&f.sidecar, permissions).unwrap();
    assert!(candidate.recheck().is_err());
    fs::set_permissions(&f.sidecar, original_permissions).unwrap();
    assert!(matches!(candidate.recheck(), Err(Refusal::Stale)));
    drop(candidate);
    f.witness();
}

#[test]
fn aliases_and_actual_read_limits_refuse_before_output_effects() {
    let f = Fixture::new(OLD);
    assert!(prepare(&f.raw, &f.raw, &replace(), Limits::default()).is_err());
    assert!(
        prepare(
            &f.raw,
            &f.sidecar,
            &replace(),
            Limits {
                raw_bytes: f.raw_bytes.len() as u64 - 1,
                sidecar_bytes: 65_536
            },
        )
        .is_err()
    );
    assert!(
        prepare(
            &f.raw,
            &f.sidecar,
            &replace(),
            Limits {
                raw_bytes: imageinfo_windows_storage::MAX_ARTIFACT_BYTES,
                sidecar_bytes: f.sidecar_bytes.len() as u64 - 1
            },
        )
        .is_err()
    );
    f.witness();
}

#[test]
fn physical_hard_link_alias_refuses_and_retains_both_names() {
    let f = Fixture::new(OLD);
    let alias = f.dir.path.join("alias.CR3");
    fs::hard_link(&f.raw, &alias).unwrap();
    assert!(prepare(&f.raw, &alias, &replace(), Limits::default()).is_err());
    // Even when RAW/XMP differ, the guard's single-link requirement refuses.
    assert!(prepare(&alias, &f.sidecar, &replace(), Limits::default()).is_err());
    assert_eq!(fs::read(&alias).unwrap(), f.raw_bytes);
    assert_eq!(fs::read_dir(&f.dir.path).unwrap().count(), 4);
    fs::remove_file(alias).unwrap();
    f.witness();
}

#[test]
fn original_snapshot_drives_mapping_and_duplicate_intents_refuse() {
    let f = Fixture::new(OLD);
    let first = prepare(&f.raw, &f.sidecar, &replace(), Limits::default()).unwrap();
    let earlier_derivative = first.bytes().to_vec();
    let second = prepare(&f.raw, &f.sidecar, &replace(), Limits::default()).unwrap();
    assert_eq!(second.facts().previous, OLD);
    assert_eq!(second.bytes(), earlier_derivative);
    assert_eq!(second.candidate_identity(), first.candidate_identity());
    assert!(matches!(
        prepare(&f.raw, &f.sidecar, &[], Limits::default()),
        Err(Refusal::IntentCount)
    ));
    let duplicate = [
        replace().into_iter().next().unwrap(),
        replace().into_iter().next().unwrap(),
    ];
    assert!(matches!(
        prepare(&f.raw, &f.sidecar, &duplicate, Limits::default()),
        Err(Refusal::IntentCount)
    ));
    drop((first, second));
    f.witness();
}

#[test]
fn actual_conflicts_explicit_losses_and_destination_selection() {
    let f = Fixture::new("2020-02-29T01:02:03.7-05:00");
    assert!(
        prepare(
            &f.raw,
            &f.sidecar,
            &intent(ConflictPolicy::Refuse),
            Limits::default()
        )
        .is_err()
    );
    assert!(prepare(&f.raw, &f.sidecar, &replace(), Limits::default()).is_err());
    let losses = [
        Loss::DestinationFractionDiscarded,
        Loss::DestinationZoneDiscarded,
    ];
    let candidate = prepare(
        &f.raw,
        &f.sidecar,
        &intent(ConflictPolicy::ReplaceSelected {
            acknowledged: &losses,
        }),
        Limits::default(),
    )
    .unwrap();
    assert_eq!(candidate.facts().losses, losses);
    assert_eq!(candidate.facts().acknowledged, losses);
    assert!(
        prepare(
            &f.raw,
            &f.sidecar,
            &[Intent {
                target_ordinal: 0,
                policy: ConflictPolicy::ReplaceSelected {
                    acknowledged: &losses
                }
            }],
            Limits::default()
        )
        .is_err()
    );
    drop(candidate);
    f.witness();
}

#[test]
fn actual_incomplete_cmt2_and_coupled_packets_refuse() {
    let mut f = Fixture::new(OLD);
    let base = f.raw_bytes.windows(4).position(|v| v == b"CMT2").unwrap() + 4;
    // First known TIFF entry becomes an opaque unrecognized native tag.
    f.raw_bytes[base + 10..base + 12].copy_from_slice(&0xc001u16.to_le_bytes());
    fs::write(&f.raw, &f.raw_bytes).unwrap();
    assert!(prepare(&f.raw, &f.sidecar, &replace(), Limits::default()).is_err());
    f.witness();
    let mut f = Fixture::new(OLD);
    f.sidecar_bytes = String::from_utf8(f.sidecar_bytes)
        .unwrap()
        .replacen(
            "<r:RDF ",
            "<r:RDF xmlns:signature='http://www.w3.org/2000/09/xmldsig#' ",
            1,
        )
        .into_bytes();
    fs::write(&f.sidecar, &f.sidecar_bytes).unwrap();
    assert!(prepare(&f.raw, &f.sidecar, &replace(), Limits::default()).is_err());
    f.witness();
}

#[test]
fn actual_duplicate_destination_and_acknowledgments_refuse() {
    let mut f = Fixture::new(OLD);
    let original = String::from_utf8(f.sidecar_bytes).unwrap();
    f.sidecar_bytes = original
        .replacen(
            "</r:Description>",
            &format!("<e:DateTimeOriginal>{OLD}</e:DateTimeOriginal></r:Description>"),
            1,
        )
        .into_bytes();
    fs::write(&f.sidecar, &f.sidecar_bytes).unwrap();
    assert!(prepare(&f.raw, &f.sidecar, &replace(), Limits::default()).is_err());
    let duplicate = [Loss::DestinationFractionDiscarded; 2];
    assert!(matches!(
        prepare(
            &f.raw,
            &f.sidecar,
            &intent(ConflictPolicy::ReplaceSelected {
                acknowledged: &duplicate
            }),
            Limits::default()
        ),
        Err(Refusal::InvalidIntent)
    ));
    f.witness();
}
