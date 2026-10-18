//! Authored local-NTFS controls; no camera media or candidate publication.
use super::{Kind, Limits, NativeStatus, Refusal, prepare};
use crate::{privacy, xmp};
use sha2::Digest;
use std::{
    fs,
    path::PathBuf,
    sync::atomic::{AtomicU64, Ordering},
};

struct Fixture {
    root: PathBuf,
    source: PathBuf,
    bytes: Vec<u8>,
}

impl Fixture {
    fn new(attribute: &str, elements: &str) -> Self {
        static NEXT: AtomicU64 = AtomicU64::new(0);
        static SESSION: std::sync::OnceLock<PathBuf> = std::sync::OnceLock::new();
        let parent = SESSION.get_or_init(|| {
            let now = std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap();
            std::env::current_dir()
                .unwrap()
                .join(".local")
                .join("test-runs")
                .join(format!("220-{}-{}", std::process::id(), now.as_nanos()))
        });
        let root = parent.join(NEXT.fetch_add(1, Ordering::Relaxed).to_string());
        fs::create_dir_all(&root).unwrap();
        let source = root.join("explicit.xmp");
        let bytes = format!("<r:RDF xmlns:r='{}' xmlns:a='{}' xmlns:u='urn:authored:kept'><r:Description {attribute}><u:before>unchanged &amp; lexical</u:before>{elements}<u:after>also kept</u:after></r:Description></r:RDF>", xmp::RDF, privacy::OWNER_NAMESPACE).into_bytes();
        fs::write(&source, &bytes).unwrap();
        fs::write(root.join("explicit.CR3"), b"unexamined authored neighbor").unwrap();
        fs::write(root.join("neighbor"), b"retained neighbor").unwrap();
        Self {
            root,
            source,
            bytes,
        }
    }
    fn witness(&self) {
        assert_eq!(fs::read(&self.source).unwrap(), self.bytes);
        assert_eq!(
            fs::read(self.root.join("explicit.CR3")).unwrap(),
            b"unexamined authored neighbor"
        );
        assert_eq!(
            fs::read(self.root.join("neighbor")).unwrap(),
            b"retained neighbor"
        );
        assert_eq!(fs::read_dir(&self.root).unwrap().count(), 3);
    }
}

#[test]
fn actual_attribute_and_element_deletion_keep_exact_complement_and_occurrence() {
    for (attribute, element, form) in [
        (
            "a:OwnerName='invented &amp; exact'",
            "",
            xmp::Form::Attribute,
        ),
        (
            "",
            "<a:OwnerName>invented &amp; exact</a:OwnerName>",
            xmp::Form::Element,
        ),
    ] {
        let f = Fixture::new(attribute, element);
        let mut p = prepare(&f.source, "explicit-authored", None, Limits::default()).unwrap();
        assert_eq!(p.kind(), Kind::Changed);
        assert_eq!(p.native_status(), NativeStatus::Unexamined);
        let occurrence = p.removed().unwrap();
        assert_eq!(occurrence.document_id, "explicit-authored");
        assert_eq!(occurrence.property.form, form);
        assert_eq!(occurrence.property.name.namespace, privacy::OWNER_NAMESPACE);
        assert_eq!(occurrence.property.name.local, privacy::OWNER_LOCAL);
        assert_eq!(
            occurrence.property.value,
            xmp::Value::Text("invented & exact".into())
        );
        let range = occurrence.deletion_range.clone();
        let expected = [&f.bytes[..range.start], &f.bytes[range.end..]].concat();
        assert_eq!(p.bytes(), expected);
        let before = xmp::inspect(&f.bytes, xmp::Limits::default()).unwrap();
        assert_eq!(
            before.properties()[occurrence.property.ordinal],
            occurrence.property
        );
        let after = xmp::inspect(p.bytes(), xmp::Limits::default()).unwrap();
        assert_eq!(after.properties().len() + 1, before.properties().len());
        assert!(
            after
                .properties()
                .iter()
                .all(|v| v.name.local != privacy::OWNER_LOCAL)
        );
        let identity = *p.candidate_identity();
        p.recheck().unwrap();
        assert_eq!(*p.candidate_identity(), identity);
        drop(p);
        f.witness();
    }
}

#[test]
fn absent_is_byte_identical_and_does_not_discover_same_stem_native() {
    let f = Fixture::new("", "");
    let mut p = prepare(&f.source, "authored-absent", None, Limits::default()).unwrap();
    assert_eq!(p.kind(), Kind::Absent);
    assert_eq!(p.native_status(), NativeStatus::Unexamined);
    assert!(p.removed().is_none());
    assert_eq!(p.bytes(), f.bytes);
    p.recheck().unwrap();
    drop(p);
    f.witness();
}

#[test]
fn duplicate_complex_and_known_provenance_refuse_even_for_absence() {
    for (index, (attribute, element)) in [
        ("a:OwnerName='one'", "<a:OwnerName>two</a:OwnerName>"),
        (
            "",
            "<a:OwnerName><r:Seq><r:li>complex</r:li></r:Seq></a:OwnerName>",
        ),
        (
            "xmlns:s='http://www.w3.org/2000/09/xmldsig#'",
            "<s:Signature>uninterpreted</s:Signature>",
        ),
        (
            "a:OwnerName='one' xmlns:s='http://www.w3.org/2000/09/xmldsig#'",
            "",
        ),
    ]
    .into_iter()
    .enumerate()
    {
        let f = Fixture::new(attribute, element);
        let result = prepare(&f.source, "authored", None, Limits::default());
        match index {
            0 => assert!(matches!(
                result,
                Err(Refusal::Removal(privacy::RemovalRefusal::Duplicate))
            )),
            1 => assert!(matches!(
                result,
                Err(Refusal::Removal(privacy::RemovalRefusal::UnsupportedTarget))
            )),
            _ => assert!(matches!(
                result,
                Err(Refusal::Removal(privacy::RemovalRefusal::Provenance(_)))
            )),
        }
        f.witness();
    }
}

#[test]
fn explicit_native_inspection_refusal_retains_actual_reason_and_source() {
    for owner in ["", "a:OwnerName='one'"] {
        let f = Fixture::new(owner, "");
        let native = f.root.join("explicit.CR3");
        let Err(Refusal::Removal(privacy::RemovalRefusal::Provenance(reason))) =
            prepare(&f.source, "authored", Some(&native), Limits::default())
        else {
            panic!("explicit invalid native must retain provenance refusal")
        };
        assert_eq!(reason.reason, privacy::provenance::Reason::NativeInspection);
        assert!(reason.native_error.is_some());
        assert!(!reason.requested_change_performed());
        f.witness();
    }
}

#[test]
fn actual_live_guards_exclude_source_write_name_and_ancestor_moves() {
    let f = Fixture::new("a:OwnerName='one'", "");
    let mut p = prepare(&f.source, "authored", None, Limits::default()).unwrap();
    assert!(fs::write(&f.source, b"foreign bytes").is_err());
    assert!(fs::rename(&f.source, f.root.join("moved.xmp")).is_err());
    assert!(fs::rename(&f.root, f.root.with_extension("moved")).is_err());
    p.recheck().unwrap();
    drop(p);
    f.witness();
}

#[test]
fn actual_property_staleness_remains_refused_after_property_restore() {
    let f = Fixture::new("a:OwnerName='one'", "");
    let mut p = prepare(&f.source, "authored", None, Limits::default()).unwrap();
    let original = fs::metadata(&f.source).unwrap().permissions();
    let mut changed = original.clone();
    changed.set_readonly(true);
    fs::set_permissions(&f.source, changed).unwrap();
    assert!(p.recheck().is_err());
    fs::set_permissions(&f.source, original).unwrap();
    assert!(matches!(p.recheck(), Err(Refusal::Stale)));
    drop(p);
    f.witness();
}

#[test]
fn identical_paths_and_physical_hardlink_aliases_refuse_without_effects() {
    let f = Fixture::new("a:OwnerName='one'", "");
    drop(prepare(&f.source, "authored", None, Limits::default()).unwrap());
    assert!(prepare(&f.source, "authored", Some(&f.source), Limits::default()).is_err());
    let alias = f.root.join("alias.xmp");
    fs::hard_link(&f.source, &alias).unwrap();
    assert!(prepare(&f.source, "authored", Some(&alias), Limits::default()).is_err());
    assert!(prepare(&alias, "authored", None, Limits::default()).is_err());
    assert_eq!(fs::read(&alias).unwrap(), f.bytes);
    fs::remove_file(alias).unwrap();
    f.witness();
}

#[test]
fn actual_junction_ancestor_refuses_without_following_selected_source() {
    let f = Fixture::new("a:OwnerName='one'", "");
    drop(prepare(&f.source, "authored", None, Limits::default()).unwrap());
    let junction = f.root.with_extension("junction");
    let status = std::process::Command::new("cmd.exe")
        .args(["/D", "/C", "mklink", "/J"])
        .arg(&junction)
        .arg(&f.root)
        .output()
        .unwrap();
    assert!(
        status.status.success(),
        "authored junction fixture creation failed"
    );
    assert!(
        prepare(
            &junction.join("explicit.xmp"),
            "authored",
            None,
            Limits::default()
        )
        .is_err()
    );
    // Retain the junction and target for independent parent inspection.
    f.witness();
}

#[test]
fn source_packet_output_document_and_native_limits_refuse_before_effects() {
    let f = Fixture::new("a:OwnerName='one'", "");
    drop(prepare(&f.source, "authored", None, Limits::default()).unwrap());
    let bounds = [
        Limits {
            sidecar_bytes: f.bytes.len() as u64 - 1,
            ..Limits::default()
        },
        Limits {
            sidecar_bytes: imageinfo_windows_storage::MAX_ARTIFACT_BYTES + 1,
            ..Limits::default()
        },
        Limits {
            packet: xmp::Limits {
                bytes: f.bytes.len() - 1,
                ..xmp::Limits::default()
            },
            ..Limits::default()
        },
        Limits {
            removal: privacy::RemovalLimits {
                output_bytes: 0,
                ..privacy::RemovalLimits::default()
            },
            ..Limits::default()
        },
        Limits {
            removal: privacy::RemovalLimits {
                document_id_bytes: 0,
                ..privacy::RemovalLimits::default()
            },
            ..Limits::default()
        },
    ];
    for limits in bounds {
        assert!(prepare(&f.source, "authored", None, limits).is_err());
    }
    assert!(prepare(&f.source, "", None, Limits::default()).is_err());
    let Err(Refusal::Guard(bound)) = prepare(
        &f.source,
        "authored",
        Some(&f.root.join("explicit.CR3")),
        Limits {
            native_bytes: 0,
            ..Limits::default()
        },
    ) else {
        panic!("native size bound must refuse in GuardedSource before provenance inspection")
    };
    assert_eq!(bound.kind(), std::io::ErrorKind::Unsupported);
    assert_eq!(bound.to_string(), "SOURCE_BOUND");
    f.witness();
}

#[test]
fn candidate_digest_occurrence_snapshot_and_context_integrity_latch_refusal() {
    for poison in 0..7 {
        let f = Fixture::new("a:OwnerName='one'", "");
        let mut p = prepare(&f.source, "authored", None, Limits::default()).unwrap();
        let old_bytes = p.candidate.clone();
        let old_identity = p.candidate_identity;
        let old_removed = p.removed.clone();
        let old_snapshot = p.sidecar_original.clone();
        match poison {
            0 => p.candidate[0] ^= 1,
            1 => p.candidate_identity[0] ^= 1,
            2 => p.removed.as_mut().unwrap().property.ordinal += 1,
            3 => p.removed.as_mut().unwrap().deletion_range.start += 1,
            4 => p.sidecar_original[0] ^= 1,
            5 => p.native_original = Some(b"invented detached context".to_vec()),
            6 => {
                // A matching forged digest cannot replace reconstruction from
                // the retained original parser-bound occurrence.
                p.candidate[0] ^= 1;
                p.candidate_identity = <[u8; 32]>::from(super::Sha256::digest(&p.candidate));
            }
            _ => unreachable!(),
        }
        assert!(p.recheck().is_err(), "poison control {poison}");
        p.candidate = old_bytes;
        p.candidate_identity = old_identity;
        p.removed = old_removed;
        p.sidecar_original = old_snapshot;
        p.native_original = None;
        assert!(matches!(p.recheck(), Err(Refusal::Stale)));
        drop(p);
        f.witness();
    }
}
